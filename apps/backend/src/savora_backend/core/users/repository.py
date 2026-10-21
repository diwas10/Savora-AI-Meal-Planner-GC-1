"""User persistence."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from savora_backend.core.users.entity import UserEntity


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
