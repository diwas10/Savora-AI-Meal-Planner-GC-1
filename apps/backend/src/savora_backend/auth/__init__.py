"""Authentication service, JWT helpers, current_user dependency, and auth routes."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, Request, status
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from savora_backend.config import Settings, get_settings
from savora_backend.contexts import RequestContextProvider
from savora_backend.core.users import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserDto,
    UserEntity,
    UserRepository,
)
from savora_backend.database import get_session
from savora_backend.decorators import response_message
from savora_backend.exceptions import RuntimeException
from savora_backend.interceptors import TransformRoute

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


def decode_access_token(token: str, *, settings: Settings | None = None) -> UUID:
    cfg = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            cfg.jwt_secret_key,
            algorithms=[cfg.jwt_algorithm],
        )
        sub = payload.get("sub")
        if not isinstance(sub, str):
            raise RuntimeException(
                "Invalid authentication token",
                status_code=status.HTTP_401_UNAUTHORIZED,
                source="auth",
            )
        return UUID(sub)
    except jwt.ExpiredSignatureError as exc:
        raise RuntimeException(
            "Authentication token has expired",
            status_code=status.HTTP_401_UNAUTHORIZED,
            source="auth",
        ) from exc
    except (jwt.PyJWTError, ValueError) as exc:
        raise RuntimeException(
            "Invalid authentication token",
            status_code=status.HTTP_401_UNAUTHORIZED,
            source="auth",
        ) from exc


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self._repo = UserRepository(session)
        self._settings = settings or get_settings()

    async def register(self, body: RegisterRequest) -> AuthResponse:
        existing = await self._repo.get_by_email(body.email)
        if existing is not None:
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
        if user is None or not user.is_active or not verify_password(
            body.password, user.password_hash
        ):
            raise RuntimeException(
                "Invalid email or password",
                status_code=status.HTTP_401_UNAUTHORIZED,
                source="auth",
            )
        RequestContextProvider.set_user_id(user.id)
        token = create_access_token(user.id, settings=self._settings)
        return AuthResponse(user=UserDto.model_validate(user), access_token=token)


async def current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserEntity:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise RuntimeException(
            "Authentication required",
            status_code=status.HTTP_401_UNAUTHORIZED,
            source="auth",
        )
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise RuntimeException(
            "Authentication required",
            status_code=status.HTTP_401_UNAUTHORIZED,
            source="auth",
        )
    user_id = decode_access_token(token)
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if user is None or not user.is_active:
        raise RuntimeException(
            "Invalid authentication token",
            status_code=status.HTTP_401_UNAUTHORIZED,
            source="auth",
        )
    RequestContextProvider.set_user_id(user.id)
    return user


CurrentUser = Annotated[UserEntity, Depends(current_user)]

auth_router = APIRouter(prefix="/auth", tags=["auth"], route_class=TransformRoute)


@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
@response_message("User registered")
async def register(
    body: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    return await AuthService(session).register(body)


@auth_router.post("/login")
@response_message("Logged in")
async def login(
    body: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    return await AuthService(session).login(body)


@auth_router.get("/me")
@response_message("Current user retrieved")
async def get_me(user: CurrentUser) -> UserDto:
    return UserDto.model_validate(user)
