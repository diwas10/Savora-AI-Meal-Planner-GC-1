"""Authentication: argon2 passwords, HS256 access tokens, `CurrentUser`, auth routes."""

from savora_backend.auth.controller import auth_router
from savora_backend.auth.dependencies import CurrentUser, current_user
from savora_backend.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from savora_backend.auth.service import AuthService

__all__ = [
    "AuthService",
    "CurrentUser",
    "auth_router",
    "create_access_token",
    "current_user",
    "decode_access_token",
    "hash_password",
    "verify_password",
]
