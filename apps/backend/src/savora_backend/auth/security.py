"""Password hashing (argon2) and HS256 access tokens."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import status
from pwdlib import PasswordHash

from savora_backend.config import Settings, get_settings
from savora_backend.exceptions import RuntimeException

_password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(plain_password, password_hash)
    except Exception:
        return False


def create_access_token(
    user_id: UUID,
    *,
    settings: Settings | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    cfg = settings or get_settings()
    now = datetime.now(UTC)
    exp = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=cfg.access_token_expire_minutes)
    )
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, cfg.jwt_secret_key, algorithm=cfg.jwt_algorithm)


def _invalid_token() -> RuntimeException:
    return RuntimeException(
        "Invalid authentication token",
        status_code=status.HTTP_401_UNAUTHORIZED,
        source="auth",
    )


def decode_access_token(token: str, *, settings: Settings | None = None) -> UUID:
    cfg = settings or get_settings()
    try:
        payload = jwt.decode(token, cfg.jwt_secret_key, algorithms=[cfg.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise RuntimeException(
            "Authentication token has expired",
            status_code=status.HTTP_401_UNAUTHORIZED,
            source="auth",
        ) from exc
    except jwt.PyJWTError as exc:
        raise _invalid_token() from exc
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise _invalid_token()
    try:
        return UUID(sub)
    except ValueError as exc:
        raise _invalid_token() from exc
