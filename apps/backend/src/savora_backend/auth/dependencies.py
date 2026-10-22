"""`CurrentUser`: Bearer token or session cookie -> active user, else a 401 envelope."""

from typing import Annotated

from fastapi import Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from savora_backend.auth.security import decode_access_token
from savora_backend.auth.session import CLIENT_HEADER, SAFE_METHODS, SESSION_COOKIE
from savora_backend.contexts import RequestContextProvider
from savora_backend.core.users import UserEntity, UserRepository
from savora_backend.database import get_session
from savora_backend.exceptions import RuntimeException


async def current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserEntity:
    header = request.headers.get("Authorization", "")
    token = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
    if not token:
        token = request.cookies.get(SESSION_COOKIE, "")
        if token and request.method not in SAFE_METHODS and not request.headers.get(CLIENT_HEADER):
            raise RuntimeException(
                f"Cookie-authenticated requests must send {CLIENT_HEADER}",
                status_code=status.HTTP_403_FORBIDDEN,
                source="auth",
            )
    if not token:
        raise RuntimeException(
            "Authentication required",
            status_code=status.HTTP_401_UNAUTHORIZED,
            source="auth",
        )
    user = await UserRepository(session).get_by_id(decode_access_token(token))
    if user is None or not user.is_active:
        raise RuntimeException(
            "Invalid authentication token",
            status_code=status.HTTP_401_UNAUTHORIZED,
            source="auth",
        )
    RequestContextProvider.set_user_id(user.id)
    return user


CurrentUser = Annotated[UserEntity, Depends(current_user)]
