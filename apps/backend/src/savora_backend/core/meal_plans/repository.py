"""Plan, slot and substitution persistence; every read is scoped to the owner."""

from datetime import date
from uuid import UUID

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from savora_backend.core.meal_plans.entity import (
    MealPlanEntity,
    MealPlanJobStatus,
    MealPlanSlotEntity,
    MealPlanSubstitutionEntity,
)

_GENERATING = MealPlanJobStatus.GENERATING.value


class MealPlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, plan_id: UUID) -> MealPlanEntity | None:
        return await self._session.scalar(
            select(MealPlanEntity).where(MealPlanEntity.id == plan_id)
        )

    async def get_owned_plan(self, plan_id: UUID, user_id: UUID) -> MealPlanEntity | None:
        stmt = select(MealPlanEntity).where(
            MealPlanEntity.id == plan_id, MealPlanEntity.user_id == user_id
        )
        return await self._session.scalar(stmt)

    async def get_substitution_by_id(
        self, substitution_id: UUID
    ) -> MealPlanSubstitutionEntity | None:
        stmt = select(MealPlanSubstitutionEntity).where(
            MealPlanSubstitutionEntity.id == substitution_id
        )
        return await self._session.scalar(stmt)

    async def get_owned_substitution(
        self, substitution_id: UUID, user_id: UUID
    ) -> MealPlanSubstitutionEntity | None:
        stmt = select(MealPlanSubstitutionEntity).where(
            MealPlanSubstitutionEntity.id == substitution_id,
            MealPlanSubstitutionEntity.user_id == user_id,
        )
        return await self._session.scalar(stmt)

    async def has_generating_job(self, user_id: UUID) -> bool:
        plan = select(MealPlanEntity.id).where(
            MealPlanEntity.user_id == user_id, MealPlanEntity.status == _GENERATING
        )
        if await self._session.scalar(plan) is not None:
            return True
        sub = select(MealPlanSubstitutionEntity.id).where(
            MealPlanSubstitutionEntity.user_id == user_id,
            MealPlanSubstitutionEntity.status == _GENERATING,
        )
        return await self._session.scalar(sub) is not None

    async def next_revision_for_week(self, user_id: UUID, week_start: date) -> int:
        stmt = (
            select(MealPlanEntity.revision)
            .where(MealPlanEntity.user_id == user_id, MealPlanEntity.week_start == week_start)
            .order_by(desc(MealPlanEntity.revision))
        )
        latest = await self._session.scalar(stmt)
        return 1 if latest is None else int(latest) + 1

    async def list_plans(
        self, user_id: UUID, *, current_only: bool = False
    ) -> list[MealPlanEntity]:
        stmt = select(MealPlanEntity).where(MealPlanEntity.user_id == user_id)
        if current_only:
            stmt = stmt.where(MealPlanEntity.is_current.is_(True))
        stmt = stmt.order_by(desc(MealPlanEntity.created_at), desc(MealPlanEntity.revision))
        return list((await self._session.scalars(stmt)).all())

    async def get_slots(self, plan_id: UUID) -> list[MealPlanSlotEntity]:
        stmt = (
            select(MealPlanSlotEntity)
            .where(MealPlanSlotEntity.plan_id == plan_id)
            .order_by(MealPlanSlotEntity.day_index, MealPlanSlotEntity.id)
        )
        return list((await self._session.scalars(stmt)).all())

    async def stale_plans(self) -> list[MealPlanEntity]:
        stmt = select(MealPlanEntity).where(MealPlanEntity.status == _GENERATING)
        return list((await self._session.scalars(stmt)).all())

    async def stale_substitutions(self) -> list[MealPlanSubstitutionEntity]:
        stmt = select(MealPlanSubstitutionEntity).where(
            MealPlanSubstitutionEntity.status == _GENERATING
        )
        return list((await self._session.scalars(stmt)).all())

    async def create_plan(self, plan: MealPlanEntity) -> MealPlanEntity:
        self._session.add(plan)
        await self._session.flush()
        return plan

    async def create_substitution(
        self, sub: MealPlanSubstitutionEntity
    ) -> MealPlanSubstitutionEntity:
        self._session.add(sub)
        await self._session.flush()
        return sub

    async def add_slots(self, slots: list[MealPlanSlotEntity]) -> None:
        self._session.add_all(slots)
        await self._session.flush()

    async def clear_current_for_user(self, user_id: UUID) -> None:
        stmt = (
            update(MealPlanEntity)
            .where(MealPlanEntity.user_id == user_id, MealPlanEntity.is_current.is_(True))
            .values(is_current=False)
        )
        await self._session.execute(stmt)
