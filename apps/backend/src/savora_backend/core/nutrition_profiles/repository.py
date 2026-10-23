"""Profile and target-snapshot persistence."""

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from savora_backend.core.nutrition_profiles.entity import (
    UserNutritionProfileEntity,
    UserProfileEntity,
)


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: UUID) -> UserProfileEntity | None:
        stmt = select(UserProfileEntity).where(UserProfileEntity.user_id == user_id)
        return await self._session.scalar(stmt)

    async def lock_by_user_id(self, user_id: UUID) -> UserProfileEntity | None:
        """The profile row, locked until the transaction ends (SELECT ... FOR UPDATE).

        Serialises one user's job starts, so two concurrent requests cannot both pass the
        "no job is generating" check. SQLite ignores the lock (tests run one at a time)."""
        stmt = (
            select(UserProfileEntity)
            .where(UserProfileEntity.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self._session.scalar(stmt)

    async def get_latest_nutrition(
        self, user_id: UUID, profile_version: int, *, lock: bool = False
    ) -> UserNutritionProfileEntity | None:
        stmt = (
            select(UserNutritionProfileEntity)
            .where(
                UserNutritionProfileEntity.user_id == user_id,
                UserNutritionProfileEntity.profile_version == profile_version,
            )
            .order_by(desc(UserNutritionProfileEntity.created_at))
        )
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return await self._session.scalar(stmt)

    async def save_profile(self, profile: UserProfileEntity) -> UserProfileEntity:
        self._session.add(profile)
        await self._session.flush()
        return profile

    async def save_nutrition_snapshot(
        self, snapshot: UserNutritionProfileEntity
    ) -> UserNutritionProfileEntity:
        self._session.add(snapshot)
        await self._session.flush()
        return snapshot
