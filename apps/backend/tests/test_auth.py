"""Tests for user registration, login, /me, token expiration, and Alembic migration."""

from datetime import timedelta
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from alembic import command
from alembic.config import Config

from savora_backend.auth import create_access_token


async def test_register_login_and_me(db_client: httpx.AsyncClient) -> None:
    reg = await db_client.post(
        "/api/auth/register",
        json={
            "email": "User@Example.com",
            "password": "securepassword123",
            "displayName": "Asha Sharma",
        },
    )
    assert reg.status_code == 201
    reg_body = reg.json()
    assert reg_body["success"] is True
    assert reg_body["source"] == "auth"
    assert reg_body["data"]["user"]["email"] == "user@example.com"
    assert reg_body["data"]["user"]["displayName"] == "Asha Sharma"
    token = reg_body["data"]["accessToken"]
    assert isinstance(token, str) and len(token) > 10

    login = await db_client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "securepassword123"},
    )
    assert login.status_code == 200
    login_body = login.json()
    assert login_body["data"]["user"]["id"] == reg_body["data"]["user"]["id"]

    me = await db_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["data"]["email"] == "user@example.com"


async def test_duplicate_email_returns_409(db_client: httpx.AsyncClient) -> None:
    payload = {
        "email": "dup@example.com",
        "password": "securepassword123",
        "displayName": "First User",
    }
    first = await db_client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    second = await db_client.post(
        "/api/auth/register",
        json={**payload, "email": "DUP@example.com"},
    )
    assert second.status_code == 409
    body = second.json()
    assert body["success"] is False
    assert body["status"] == 409


async def test_bad_password_and_short_password(db_client: httpx.AsyncClient) -> None:
    short = await db_client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "short", "displayName": "Short"},
    )
    assert short.status_code == 422
    assert "password" in short.json()["description"]

    await db_client.post(
        "/api/auth/register",
        json={
            "email": "valid@example.com",
            "password": "securepassword123",
            "displayName": "Valid",
        },
    )
    bad = await db_client.post(
        "/api/auth/login",
        json={"email": "valid@example.com", "password": "wrongpassword"},
    )
    assert bad.status_code == 401
    assert bad.json()["message"] == "Invalid email or password"

    missing_user = await db_client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "securepassword123"},
    )
    assert missing_user.status_code == 401
    assert missing_user.json()["message"] == "Invalid email or password"


async def test_expired_and_invalid_tokens_return_401(db_client: httpx.AsyncClient) -> None:
    reg = await db_client.post(
        "/api/auth/register",
        json={
            "email": "token@example.com",
            "password": "securepassword123",
            "displayName": "Token User",
        },
    )
    user_id = UUID(reg.json()["data"]["user"]["id"])

    expired = create_access_token(user_id, expires_delta=timedelta(seconds=-10))
    res_exp = await db_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert res_exp.status_code == 401
    assert res_exp.json()["success"] is False

    db_client.cookies.clear()  # registration set a session cookie
    res_no_hdr = await db_client.get("/api/auth/me")
    assert res_no_hdr.status_code == 401

    res_bad = await db_client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert res_bad.status_code == 401


def test_alembic_upgrade_and_downgrade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "alembic_test.db"
    alembic_ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "-1")
    command.upgrade(cfg, "head")


async def test_session_cookie_login_requests_and_logout(db_client: httpx.AsyncClient) -> None:
    reg = await db_client.post(
        "/api/auth/register",
        json={"email": "cookie@example.com", "password": "securepassword123", "displayName": "C"},
    )
    assert reg.status_code == 201
    set_cookie = reg.headers["set-cookie"].lower()
    assert set_cookie.startswith("savora_session=")
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie and "path=/api" in set_cookie
    assert "secure" not in set_cookie  # development; Secure only with APP_ENV=production

    me = await db_client.get("/api/auth/me")  # the client sends the cookie, no header
    assert me.status_code == 200
    assert me.json()["data"]["email"] == "cookie@example.com"

    # A cookie-authenticated write without the client header is refused (CSRF).
    body = {"weekStart": "2026-10-19"}
    forged = await db_client.post("/api/meal-plans", json=body)
    assert forged.status_code == 403
    assert "X-Savora-Client" in forged.json()["message"]
    sent = await db_client.post("/api/meal-plans", json=body, headers={"X-Savora-Client": "web"})
    assert sent.status_code == 409  # authenticated; no profile yet

    out = await db_client.post("/api/auth/logout")
    assert out.status_code == 200
    assert 'savora_session=""' in out.headers["set-cookie"] or "max-age=0" in (
        out.headers["set-cookie"].lower()
    )
    assert (await db_client.get("/api/auth/me")).status_code == 401


class _Outbox:
    """Captures the reset mail instead of sending it."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))

    def last_token(self) -> str:
        return self.sent[-1][2].split("token=")[1].split()[0]


def _outbox(db_client: httpx.AsyncClient) -> _Outbox:
    from savora_backend.auth.mailer import get_mailer

    outbox = _Outbox()
    app = db_client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[get_mailer] = lambda: outbox
    return outbox


async def _register(db_client: httpx.AsyncClient, email: str = "forgot@example.com") -> None:
    reg = await db_client.post(
        "/api/auth/register",
        json={"email": email, "password": "oldpassword123", "displayName": "F"},
    )
    assert reg.status_code == 201
    db_client.cookies.clear()


async def test_forgot_password_answers_the_same_for_unknown_emails(
    db_client: httpx.AsyncClient,
) -> None:
    outbox = _outbox(db_client)
    await _register(db_client)
    known = await db_client.post("/api/auth/forgot-password", json={"email": "Forgot@example.com"})
    unknown = await db_client.post(
        "/api/auth/forgot-password", json={"email": "nobody@example.com"}
    )
    assert known.status_code == unknown.status_code == 200
    assert known.json()["message"] == unknown.json()["message"]
    assert known.json()["data"] == unknown.json()["data"]
    assert [m[0] for m in outbox.sent] == ["forgot@example.com"]  # nothing sent to the stranger
    assert "/reset-password?token=" in outbox.sent[0][2]


async def test_reset_password_changes_the_password_once_and_ends_old_sessions(
    db_client: httpx.AsyncClient,
) -> None:
    outbox = _outbox(db_client)
    await _register(db_client)
    old_session = (
        await db_client.post(
            "/api/auth/login", json={"email": "forgot@example.com", "password": "oldpassword123"}
        )
    ).json()["data"]["accessToken"]
    db_client.cookies.clear()
    await db_client.post("/api/auth/forgot-password", json={"email": "forgot@example.com"})
    token = outbox.last_token()

    # Sessions are second-resolution: make the old one strictly older than the reset.
    import asyncio

    await asyncio.sleep(1.1)
    done = await db_client.post(
        "/api/auth/reset-password", json={"token": token, "password": "newpassword456"}
    )
    assert done.status_code == 200

    old = await db_client.post(
        "/api/auth/login", json={"email": "forgot@example.com", "password": "oldpassword123"}
    )
    assert old.status_code == 401
    new = await db_client.post(
        "/api/auth/login", json={"email": "forgot@example.com", "password": "newpassword456"}
    )
    assert new.status_code == 200
    db_client.cookies.clear()
    stale = await db_client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_session}"})
    assert stale.status_code == 401  # issued before the reset
    fresh_token = new.json()["data"]["accessToken"]
    fresh = await db_client.get("/api/auth/me", headers={"Authorization": f"Bearer {fresh_token}"})
    assert fresh.status_code == 200

    again = await db_client.post(
        "/api/auth/reset-password", json={"token": token, "password": "anotherpass789"}
    )
    assert again.status_code == 400  # single use


async def _age_reset_tokens(
    db_client: httpx.AsyncClient, *, created_ago: int, expires_in: int
) -> None:
    """Sets every reset link's age and remaining life, in minutes."""
    from datetime import UTC, datetime

    from sqlalchemy import update

    from savora_backend.core.users import PasswordResetTokenEntity
    from savora_backend.database import get_session

    app = db_client._transport.app  # type: ignore[attr-defined]
    now = datetime.now(UTC)
    async for session in app.dependency_overrides[get_session]():
        await session.execute(
            update(PasswordResetTokenEntity).values(
                created_at=now - timedelta(minutes=created_ago),
                expires_at=now + timedelta(minutes=expires_in),
            )
        )


async def test_reset_password_refuses_unknown_expired_and_replaced_links(
    db_client: httpx.AsyncClient,
) -> None:
    outbox = _outbox(db_client)
    await _register(db_client)
    body = {"password": "newpassword456"}
    bogus = await db_client.post("/api/auth/reset-password", json={"token": "x" * 43, **body})
    assert bogus.status_code == 400
    short = await db_client.post("/api/auth/reset-password", json={"token": "short", **body})
    assert short.status_code == 422

    await db_client.post("/api/auth/forgot-password", json={"email": "forgot@example.com"})
    first = outbox.last_token()
    # Within a minute a second request mails nothing new, so the first link stays valid.
    await db_client.post("/api/auth/forgot-password", json={"email": "forgot@example.com"})
    assert len(outbox.sent) == 1

    await _age_reset_tokens(db_client, created_ago=61, expires_in=-1)  # expired
    expired = await db_client.post("/api/auth/reset-password", json={"token": first, **body})
    assert expired.status_code == 400

    await db_client.post("/api/auth/forgot-password", json={"email": "forgot@example.com"})
    second = outbox.last_token()
    assert second != first and len(outbox.sent) == 2
    await _age_reset_tokens(db_client, created_ago=5, expires_in=55)  # past the cooldown
    await db_client.post("/api/auth/forgot-password", json={"email": "forgot@example.com"})
    third = outbox.last_token()
    assert len(outbox.sent) == 3
    replaced = await db_client.post("/api/auth/reset-password", json={"token": second, **body})
    assert replaced.status_code == 400  # a newer link ends the earlier ones
    ok = await db_client.post("/api/auth/reset-password", json={"token": third, **body})
    assert ok.status_code == 200
