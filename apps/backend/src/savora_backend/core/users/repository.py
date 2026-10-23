"""User persistence."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from savora_backend.core.users.entity import PasswordResetTokenEntity, UserEntity


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> UserEntity | None:
        stmt = select(UserEntity).where(UserEntity.id == user_id)
        return await self._session.scalar(stmt)

    async def get_by_email(self, email: str) -> UserEntity | None:
        normalized = email.strip().lower()
        stmt = select(UserEntity).where(UserEntity.email == normalized)
        return await self._session.scalar(stmt)

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str,
    ) -> UserEntity:
        user = UserEntity(
            email=email.strip().lower(),
            password_hash=password_hash,
            display_name=display_name.strip(),
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def latest_reset_token(self, user_id: UUID) -> PasswordResetTokenEntity | None:
        stmt = (
            select(PasswordResetTokenEntity)
            .where(PasswordResetTokenEntity.user_id == user_id)
            .order_by(PasswordResetTokenEntity.created_at.desc())
            .limit(1)
        )
        return await self._session.scalar(stmt)

    async def add_reset_token(
        self, user_id: UUID, token_hash: str, expires_at: datetime
    ) -> PasswordResetTokenEntity:
        token = PasswordResetTokenEntity(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_reset_token(self, token_hash: str) -> PasswordResetTokenEntity | None:
        stmt = select(PasswordResetTokenEntity).where(
            PasswordResetTokenEntity.token_hash == token_hash
        )
        return await self._session.scalar(stmt)

    async def use_all_reset_tokens(self, user_id: UUID, now: datetime) -> None:
        """Marks every unused link of the user as used (a reset ends all earlier links)."""
        await self._session.execute(
            update(PasswordResetTokenEntity)
            .where(
                PasswordResetTokenEntity.user_id == user_id,
                PasswordResetTokenEntity.used_at.is_(None),
            )
            .values(used_at=now)
        )
