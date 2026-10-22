"""The browser session: the access token in an httpOnly cookie (no script can read it).

The web app talks to FastAPI through the Next.js `/api` rewrite, so the cookie is
first-party. SameSite=Lax keeps it off cross-site POSTs, and a cookie-authenticated
unsafe request must also carry `X-Savora-Client` (a custom header a cross-site form
cannot send, and which forces a CORS preflight). Bearer tokens keep working for API
clients and tests.
"""

from fastapi import Response

from savora_backend.config import Settings, get_settings

SESSION_COOKIE = "savora_session"
CLIENT_HEADER = "X-Savora-Client"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def set_session_cookie(response: Response, token: str, settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=cfg.access_token_expire_minutes * 60,
        path="/api",
        httponly=True,
        secure=cfg.app_env == "production",
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    response.delete_cookie(
        SESSION_COOKIE,
        path="/api",
        httponly=True,
        secure=cfg.app_env == "production",
        samesite="lax",
    )
