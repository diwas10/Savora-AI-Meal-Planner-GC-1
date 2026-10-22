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
