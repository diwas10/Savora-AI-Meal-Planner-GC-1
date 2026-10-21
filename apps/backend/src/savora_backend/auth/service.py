"""Registration and login."""

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from savora_backend.auth.security import create_access_token, hash_password, verify_password
from savora_backend.config import Settings, get_settings
from savora_backend.contexts import RequestContextProvider
from savora_backend.core.users import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserDto,
    UserRepository,
)
from savora_backend.exceptions import RuntimeException


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self._repo = UserRepository(session)
        self._settings = settings or get_settings()

    async def register(self, body: RegisterRequest) -> AuthResponse:
        if await self._repo.get_by_email(body.email) is not None:
            raise RuntimeException(
                "Email is already registered",
                status_code=status.HTTP_409_CONFLICT,
                source="auth",
            )
        user = await self._repo.create(
            email=body.email,
            password_hash=hash_password(body.password),
            display_name=body.display_name,
        )
        RequestContextProvider.set_user_id(user.id)
        token = create_access_token(user.id, settings=self._settings)
        return AuthResponse(user=UserDto.model_validate(user), access_token=token)

    async def login(self, body: LoginRequest) -> AuthResponse:
        user = await self._repo.get_by_email(body.email)
        if (
            user is None
            or not user.is_active
            or not verify_password(body.password, user.password_hash)
        ):
            raise RuntimeException(
                "Invalid email or password",
                status_code=status.HTTP_401_UNAUTHORIZED,
                source="auth",
            )
        RequestContextProvider.set_user_id(user.id)
        token = create_access_token(user.id, settings=self._settings)
        return AuthResponse(user=UserDto.model_validate(user), access_token=token)
