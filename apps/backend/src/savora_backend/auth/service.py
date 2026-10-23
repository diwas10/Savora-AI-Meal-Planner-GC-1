"""Registration, login and password reset."""

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from savora_backend.auth.mailer import Mailer
from savora_backend.auth.security import create_access_token, hash_password, verify_password
from savora_backend.config import Settings, get_settings
from savora_backend.contexts import RequestContextProvider
from savora_backend.core.users import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserDto,
    UserRepository,
)
from savora_backend.exceptions import RuntimeException

logger = logging.getLogger(__name__)

# One reset link per account per minute: a repeated request mails nothing new.
RESET_COOLDOWN = timedelta(seconds=60)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


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

    async def request_password_reset(self, body: ForgotPasswordRequest) -> tuple[str, str] | None:
        """A fresh reset link for the account, or None when there is nothing to send.

        The caller answers the same way either way, so the response never shows whether
        an email is registered. Returns (email, link) for the mailer."""
        user = await self._repo.get_by_email(body.email)
        if user is None or not user.is_active:
            return None
        now = datetime.now(UTC)
        latest = await self._repo.latest_reset_token(user.id)
        if latest is not None and now - _aware(latest.created_at) < RESET_COOLDOWN:
            return None
        token = secrets.token_urlsafe(32)
        await self._repo.use_all_reset_tokens(user.id, now)
        await self._repo.add_reset_token(
            user.id,
            _digest(token),
            now + timedelta(minutes=self._settings.password_reset_expire_minutes),
        )
        base = self._settings.frontend_url.rstrip("/")
        return user.email, f"{base}/reset-password?token={token}"

    async def reset_password(self, body: ResetPasswordRequest) -> None:
        now = datetime.now(UTC)
        record = await self._repo.get_reset_token(_digest(body.token))
        user = await self._repo.get_by_id(record.user_id) if record is not None else None
        if (
            record is None
            or user is None
            or not user.is_active
            or record.used_at is not None
            or _aware(record.expires_at) <= now
        ):
            raise RuntimeException(
                "This reset link is invalid or has expired. Request a new one.",
                status_code=status.HTTP_400_BAD_REQUEST,
                source="auth",
            )
        user.password_hash = hash_password(body.password)
        user.password_changed_at = now
        await self._repo.use_all_reset_tokens(user.id, now)


async def send_reset_email(mailer: Mailer, email: str, link: str, minutes: int) -> None:
    """Background task: a mail failure is logged, never shown (it would reveal the account)."""
    body = (
        "Hello,\n\nUse this link to choose a new Savora password. It works once and expires "
        f"in {minutes} minutes:\n\n{link}\n\nIf you did not ask for this, ignore this email; "
        "your password stays the same.\n"
    )
    try:
        await mailer.send(email, "Reset your Savora password", body)
    except Exception:
        logger.exception("Could not send the password reset email")
