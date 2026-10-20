"""Weekly meal plans and substitutions: entities, DTOs, repository, background jobs, and routes."""

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import Field, StringConstraints
from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    desc,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from savora_ai.core.pipelines import (
    PlannedMeal,
    PlanningProfile,
    PlanStatus,
    SafetyVerification,
)
from savora_ai.core.pipelines.planning import SLOT_ID, DayTotals, SearchSummary
from savora_backend.ai.gateway import AiGateway, get_ai_gateway
from savora_backend.auth import CurrentUser
from savora_backend.core.common import CamelModel
from savora_backend.core.nutrition_profiles import ProfileRepository, to_planning_profile
from savora_backend.database import (
    CommonEntity,
    JsonbType,
    StringArrayType,
    get_session,
    get_session_factory,
)
from savora_backend.decorators import response_message
from savora_backend.exceptions import RuntimeException
from savora_backend.interceptors import TransformRoute

logger = logging.getLogger(__name__)

_SlotIdStr = Annotated[str, StringConstraints(pattern=SLOT_ID)]


class MealPlanJobStatus(StrEnum):
    GENERATING = "GENERATING"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"


class MealPlanEntity(CommonEntity):
    __tablename__ = "meal_plans"
    __table_args__ = (
        Index("ix_meal_plans_user_current", "user_id", "is_current"),
        Index("ix_meal_plans_user_week_start", "user_id", "week_start"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=MealPlanJobStatus.GENERATING.value, nullable=False
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    catalogue_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kb_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kb_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    safety: Mapped[dict[str, Any] | None] = mapped_column(JsonbType, nullable=True)
    search: Mapped[dict[str, Any] | None] = mapped_column(JsonbType, nullable=True)
    day_totals: Mapped[list[dict[str, Any]] | None] = mapped_column(JsonbType, nullable=True)
    parent_plan_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("meal_plans.id", ondelete="SET NULL"), nullable=True
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MealPlanSlotEntity(CommonEntity):
    __tablename__ = "meal_plan_slots"
    __table_args__ = (
        UniqueConstraint("plan_id", "slot_id", name="uq_meal_plan_slots_plan_slot"),
    )

    plan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("meal_plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    slot_id: Mapped[str] = mapped_column(String(32), nullable=False)
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    calendar_date: Mapped[str] = mapped_column(String(16), nullable=False)
    meal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    option_id: Mapped[str] = mapped_column(String(255), nullable=False)
    combination_id: Mapped[str] = mapped_column(String(255), nullable=False)
    configuration_id: Mapped[str] = mapped_column(String(255), nullable=False)
    preset: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JsonbType, nullable=False)


class MealPlanSubstitutionEntity(CommonEntity):
    __tablename__ = "meal_plan_substitutions"

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    from_plan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("meal_plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    to_plan_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("meal_plans.id", ondelete="SET NULL"), nullable=True
    )
    slot_id: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=MealPlanJobStatus.GENERATING.value, nullable=False
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JsonbType, nullable=True)
    after_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JsonbType, nullable=True)
    excluded_combination_ids: Mapped[list[str]] = mapped_column(
        StringArrayType, default=list, nullable=False
    )


class GeneratePlanRequest(CamelModel):
    week_start: date


class GeneratePlanAcceptedDto(CamelModel):
    plan_id: UUID
    status: MealPlanJobStatus = MealPlanJobStatus.GENERATING


class CreateSubstitutionRequest(CamelModel):
    slot_id: _SlotIdStr
    expected_revision: int = Field(ge=1)
    exclude_combination_ids: list[str] = Field(default_factory=list)


class CreateSubstitutionAcceptedDto(CamelModel):
    substitution_id: UUID
    status: MealPlanJobStatus = MealPlanJobStatus.GENERATING


class SubstitutionDetailDto(CamelModel):
    id: UUID
    status: MealPlanJobStatus
    message: str | None
    from_plan_id: UUID
    to_plan_id: UUID | None = None
    slot_id: str
    before_snapshot: PlannedMeal | None = None
    after_snapshot: PlannedMeal | None = None


class MealPlanSlotDto(CamelModel):
    slot_id: str
    day_index: int
    calendar_date: str
    meal_type: str
    option_id: str
    combination_id: str
    configuration_id: str
    preset: str
    snapshot: PlannedMeal


class MealPlanSummaryDto(CamelModel):
    id: UUID
    user_id: UUID
    week_start: date
    revision: int
    status: MealPlanJobStatus
    message: str | None
    profile_version: int
    catalogue_version: str | None
    model_version: str | None
    fallback_reason: str | None
    kb_id: str | None
    kb_version: str | None
    parent_plan_id: UUID | None
    is_current: bool
    created_at: datetime
    updated_at: datetime


class MealPlanDetailDto(MealPlanSummaryDto):
    safety: SafetyVerification | None = None
    search: SearchSummary | None = None
    day_totals: list[DayTotals] = Field(default_factory=list)
    slots: list[MealPlanSlotDto] = Field(default_factory=list)


class MealPlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, plan_id: UUID) -> MealPlanEntity | None:
        stmt = select(MealPlanEntity).where(MealPlanEntity.id == plan_id)
        return await self._session.scalar(stmt)

    async def get_owned_plan(self, plan_id: UUID, user_id: UUID) -> MealPlanEntity | None:
        stmt = select(MealPlanEntity).where(
            MealPlanEntity.id == plan_id,
            MealPlanEntity.user_id == user_id,
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
        plan_stmt = select(MealPlanEntity.id).where(
            MealPlanEntity.user_id == user_id,
            MealPlanEntity.status == MealPlanJobStatus.GENERATING.value,
        )
        if await self._session.scalar(plan_stmt) is not None:
            return True
        sub_stmt = select(MealPlanSubstitutionEntity.id).where(
            MealPlanSubstitutionEntity.user_id == user_id,
            MealPlanSubstitutionEntity.status == MealPlanJobStatus.GENERATING.value,
        )
        return await self._session.scalar(sub_stmt) is not None

    async def next_revision_for_week(self, user_id: UUID, week_start: date) -> int:
        stmt = (
            select(MealPlanEntity.revision)
            .where(
                MealPlanEntity.user_id == user_id,
                MealPlanEntity.week_start == week_start,
            )
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
        scalars = await self._session.scalars(stmt)
        return list(scalars.all())

    async def get_slots(self, plan_id: UUID) -> list[MealPlanSlotEntity]:
        stmt = (
            select(MealPlanSlotEntity)
            .where(MealPlanSlotEntity.plan_id == plan_id)
            .order_by(MealPlanSlotEntity.day_index, MealPlanSlotEntity.id)
        )
        scalars = await self._session.scalars(stmt)
        return list(scalars.all())

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


_background_tasks: set[asyncio.Task[None]] = set()


def track_background_task(coro: Any) -> asyncio.Task[None]:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def wait_for_background_tasks() -> None:
    if _background_tasks:
        await asyncio.gather(*list(_background_tasks), return_exceptions=True)


async def mark_stale_generating_jobs_failed(
    session_factory: Callable[[], Any] | None = None,
) -> int:
    """On startup, mark any plans or substitutions left in GENERATING as FAILED."""
    factory = session_factory or get_session_factory()
    async with factory() as session, session.begin():
        plan_stmt = select(MealPlanEntity).where(
            MealPlanEntity.status == MealPlanJobStatus.GENERATING.value
        )
        stale_plans = list((await session.scalars(plan_stmt)).all())
        for plan in stale_plans:
            plan.status = MealPlanJobStatus.FAILED.value
            plan.message = "server restarted"

        sub_stmt = select(MealPlanSubstitutionEntity).where(
            MealPlanSubstitutionEntity.status == MealPlanJobStatus.GENERATING.value
        )
        stale_subs = list((await session.scalars(sub_stmt)).all())
        for sub in stale_subs:
            sub.status = MealPlanJobStatus.FAILED.value
            sub.message = "server restarted"

        await session.flush()
        return len(stale_plans) + len(stale_subs)


async def _run_plan_week_job(
    *,
    plan_id: UUID,
    user_id: UUID,
    planning_profile: PlanningProfile,
    week_start: date,
    gateway: AiGateway,
    session_factory: Callable[[], Any],
) -> None:
    try:
        week_plan = await gateway.plan_week(
            planning_profile,
            week_id=str(plan_id),
            start_date=week_start,
        )
        async with session_factory() as session, session.begin():
            repo = MealPlanRepository(session)
            plan = await repo.get_by_id(plan_id)
            if plan is None:
                return
            plan.status = week_plan.status.value
            plan.message = week_plan.message
            plan.catalogue_version = week_plan.catalogue_version
            plan.model_version = week_plan.model_version
            plan.fallback_reason = (
                week_plan.fallback_reason.value if week_plan.fallback_reason else None
            )
            plan.kb_id = week_plan.kb_id
            plan.kb_version = week_plan.kb_version
            plan.safety = week_plan.safety.model_dump(mode="json", by_alias=True)
            plan.search = (
                week_plan.search.model_dump(mode="json", by_alias=True)
                if week_plan.search
                else None
            )
            plan.day_totals = [
                dt.model_dump(mode="json", by_alias=True) for dt in week_plan.day_totals
            ]
            if week_plan.status is PlanStatus.FEASIBLE:
                await repo.clear_current_for_user(user_id)
                plan.is_current = True
                slot_entities = [
                    MealPlanSlotEntity(
                        plan_id=plan.id,
                        slot_id=meal.slot_id,
                        day_index=meal.day_index,
                        calendar_date=meal.calendar_date,
                        meal_type=meal.meal_type.value,
                        option_id=meal.option_id,
                        combination_id=meal.combination_id,
                        configuration_id=meal.configuration_id,
                        preset=meal.preset.value,
                        snapshot=meal.model_dump(mode="json", by_alias=True),
                    )
                    for meal in week_plan.meals
                ]
                await repo.add_slots(slot_entities)
    except Exception as exc:
        logger.exception("Plan generation job %s failed", plan_id, exc_info=exc)
        async with session_factory() as session, session.begin():
            repo = MealPlanRepository(session)
            plan = await repo.get_by_id(plan_id)
            if plan is not None:
                plan.status = MealPlanJobStatus.FAILED.value
                plan.message = str(exc) or "Plan generation failed"


async def _run_substitute_job(
    *,
    substitution_id: UUID,
    from_plan_id: UUID,
    user_id: UUID,
    planning_profile: PlanningProfile,
    current_options: dict[str, str],
    slot_id: str,
    week_start: date,
    exclude_combination_ids: list[str],
    gateway: AiGateway,
    session_factory: Callable[[], Any],
) -> None:
    try:
        swapped = await gateway.substitute(
            planning_profile,
            current=current_options,
            slot=slot_id,
            week_id=f"{from_plan_id}-sub-{substitution_id}",
            start_date=week_start,
            exclude_combination_ids=exclude_combination_ids,
        )
        async with session_factory() as session, session.begin():
            repo = MealPlanRepository(session)
            sub = await repo.get_substitution_by_id(substitution_id)
            parent_plan = await repo.get_by_id(from_plan_id)
            if sub is None or parent_plan is None:
                return
            sub.status = swapped.status.value
            sub.message = swapped.message

            if swapped.status is PlanStatus.FEASIBLE:
                parent_slots = await repo.get_slots(parent_plan.id)
                new_meal = next((m for m in swapped.meals if m.slot_id == slot_id), None)
                if new_meal is None:
                    sub.status = MealPlanJobStatus.FAILED.value
                    sub.message = f"Solver did not return replacement for slot {slot_id}"
                    return

                new_snapshot = new_meal.model_dump(mode="json", by_alias=True)
                await repo.clear_current_for_user(user_id)
                next_rev = await repo.next_revision_for_week(user_id, parent_plan.week_start)
                if next_rev <= parent_plan.revision:
                    next_rev = parent_plan.revision + 1

                new_plan = MealPlanEntity(
                    user_id=user_id,
                    week_start=parent_plan.week_start,
                    revision=next_rev,
                    status=MealPlanJobStatus.FEASIBLE.value,
                    message=swapped.message,
                    profile_version=parent_plan.profile_version,
                    catalogue_version=swapped.catalogue_version,
                    model_version=swapped.model_version,
                    fallback_reason=(
                        swapped.fallback_reason.value if swapped.fallback_reason else None
                    ),
                    kb_id=swapped.kb_id,
                    kb_version=swapped.kb_version,
                    safety=swapped.safety.model_dump(mode="json", by_alias=True),
                    search=(
                        swapped.search.model_dump(mode="json", by_alias=True)
                        if swapped.search
                        else None
                    ),
                    day_totals=[
                        dt.model_dump(mode="json", by_alias=True) for dt in swapped.day_totals
                    ],
                    parent_plan_id=parent_plan.id,
                    is_current=True,
                )
                await repo.create_plan(new_plan)

                slot_entities: list[MealPlanSlotEntity] = []
                for ps in parent_slots:
                    if ps.slot_id == slot_id:
                        slot_entities.append(
                            MealPlanSlotEntity(
                                plan_id=new_plan.id,
                                slot_id=new_meal.slot_id,
                                day_index=new_meal.day_index,
                                calendar_date=new_meal.calendar_date,
                                meal_type=new_meal.meal_type.value,
                                option_id=new_meal.option_id,
                                combination_id=new_meal.combination_id,
                                configuration_id=new_meal.configuration_id,
                                preset=new_meal.preset.value,
                                snapshot=new_snapshot,
                            )
                        )
                    else:
                        # Copy the 20 locked slot snapshots verbatim from parent plan
                        slot_entities.append(
                            MealPlanSlotEntity(
                                plan_id=new_plan.id,
                                slot_id=ps.slot_id,
                                day_index=ps.day_index,
                                calendar_date=ps.calendar_date,
                                meal_type=ps.meal_type,
                                option_id=ps.option_id,
                                combination_id=ps.combination_id,
                                configuration_id=ps.configuration_id,
                                preset=ps.preset,
                                snapshot=dict(ps.snapshot),
                            )
                        )
                await repo.add_slots(slot_entities)
                sub.to_plan_id = new_plan.id
                sub.after_snapshot = new_snapshot
    except Exception as exc:
        logger.exception("Substitution job %s failed", substitution_id, exc_info=exc)
        async with session_factory() as session, session.begin():
            repo = MealPlanRepository(session)
            sub = await repo.get_substitution_by_id(substitution_id)
            if sub is not None:
                sub.status = MealPlanJobStatus.FAILED.value
                sub.message = str(exc) or "Substitution failed"


def get_job_session_factory(request: Request) -> Callable[[], Any]:
    override = getattr(request.app.state, "job_session_factory", None)
    if callable(override):
        return override
    return get_session_factory()


def _to_detail_dto(
    plan: MealPlanEntity, slot_entities: list[MealPlanSlotEntity]
) -> MealPlanDetailDto:
    safety = (
        SafetyVerification.model_validate_json(json.dumps(plan.safety))
        if plan.safety
        else None
    )
    search = (
        SearchSummary.model_validate_json(json.dumps(plan.search)) if plan.search else None
    )
    day_totals = [
        DayTotals.model_validate_json(json.dumps(dt)) for dt in (plan.day_totals or [])
    ]
    meal_order = {"BREAKFAST": 0, "LUNCH": 1, "DINNER": 2}
    sorted_slots = sorted(
        slot_entities,
        key=lambda s: (s.day_index, meal_order.get(s.meal_type, 9)),
    )
    slot_dtos = [
        MealPlanSlotDto(
            slot_id=s.slot_id,
            day_index=s.day_index,
            calendar_date=s.calendar_date,
            meal_type=s.meal_type,
            option_id=s.option_id,
            combination_id=s.combination_id,
            configuration_id=s.configuration_id,
            preset=s.preset,
            snapshot=PlannedMeal.model_validate_json(json.dumps(s.snapshot)),
        )
        for s in sorted_slots
    ]
    return MealPlanDetailDto(
        id=plan.id,
        user_id=plan.user_id,
        week_start=plan.week_start,
        revision=plan.revision,
        status=MealPlanJobStatus(plan.status),
        message=plan.message,
        profile_version=plan.profile_version,
        catalogue_version=plan.catalogue_version,
        model_version=plan.model_version,
        fallback_reason=plan.fallback_reason,
        kb_id=plan.kb_id,
        kb_version=plan.kb_version,
        parent_plan_id=plan.parent_plan_id,
        is_current=plan.is_current,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        safety=safety,
        search=search,
        day_totals=day_totals,
        slots=slot_dtos,
    )


def _to_substitution_dto(sub: MealPlanSubstitutionEntity) -> SubstitutionDetailDto:
    before = (
        PlannedMeal.model_validate_json(json.dumps(sub.before_snapshot))
        if sub.before_snapshot
        else None
    )
    after = (
        PlannedMeal.model_validate_json(json.dumps(sub.after_snapshot))
        if sub.after_snapshot
        else None
    )
    return SubstitutionDetailDto(
        id=sub.id,
        status=MealPlanJobStatus(sub.status),
        message=sub.message,
        from_plan_id=sub.from_plan_id,
        to_plan_id=sub.to_plan_id,
        slot_id=sub.slot_id,
        before_snapshot=before,
        after_snapshot=after,
    )


class MealPlanService:
    def __init__(
        self,
        session: AsyncSession,
        gateway: AiGateway,
        job_session_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._plan_repo = MealPlanRepository(session)
        self._profile_repo = ProfileRepository(session)
        self._gateway = gateway
        self._job_session_factory = job_session_factory or get_session_factory()

    async def start_generation(
        self, user_id: UUID, body: GeneratePlanRequest
    ) -> tuple[GeneratePlanAcceptedDto, Callable[[], None]]:
        profile_entity = await self._profile_repo.get_by_user_id(user_id)
        if profile_entity is None:
            raise RuntimeException(
                "complete onboarding first",
                status_code=status.HTTP_409_CONFLICT,
                source="meal-plans",
            )
        if await self._plan_repo.has_generating_job(user_id):
            raise RuntimeException(
                "A meal plan or substitution job is already generating for this user",
                status_code=status.HTTP_409_CONFLICT,
                source="meal-plans",
            )
        revision = await self._plan_repo.next_revision_for_week(user_id, body.week_start)
        plan = MealPlanEntity(
            user_id=user_id,
            week_start=body.week_start,
            revision=revision,
            status=MealPlanJobStatus.GENERATING.value,
            message="Generating weekly meal plan",
            profile_version=profile_entity.version,
            catalogue_version=self._gateway.bundle.version,
            is_current=False,
        )
        await self._plan_repo.create_plan(plan)
        planning_profile = to_planning_profile(profile_entity)
        plan_id = plan.id

        def launch() -> None:
            track_background_task(
                _run_plan_week_job(
                    plan_id=plan_id,
                    user_id=user_id,
                    planning_profile=planning_profile,
                    week_start=body.week_start,
                    gateway=self._gateway,
                    session_factory=self._job_session_factory,
                )
            )

        return (
            GeneratePlanAcceptedDto(
                plan_id=plan_id,
                status=MealPlanJobStatus.GENERATING,
            ),
            launch,
        )

    async def start_substitution(
        self,
        user_id: UUID,
        plan_id: UUID,
        body: CreateSubstitutionRequest,
    ) -> tuple[CreateSubstitutionAcceptedDto, Callable[[], None]]:
        plan = await self._plan_repo.get_owned_plan(plan_id, user_id)
        if plan is None:
            raise RuntimeException(
                "Meal plan not found",
                status_code=status.HTTP_404_NOT_FOUND,
                source="substitutions",
            )
        if not plan.is_current or plan.status != MealPlanJobStatus.FEASIBLE.value:
            raise RuntimeException(
                "Substitutions are only allowed on a current feasible meal plan",
                status_code=status.HTTP_409_CONFLICT,
                source="substitutions",
            )
        if body.expected_revision != plan.revision:
            raise RuntimeException(
                f"Revision mismatch: expected {body.expected_revision}, current is {plan.revision}",
                status_code=status.HTTP_409_CONFLICT,
                source="substitutions",
            )
        profile_entity = await self._profile_repo.get_by_user_id(user_id)
        if profile_entity is None or profile_entity.version != plan.profile_version:
            raise RuntimeException(
                "profile changed; generate a new plan",
                status_code=status.HTTP_409_CONFLICT,
                source="substitutions",
            )
        if await self._plan_repo.has_generating_job(user_id):
            raise RuntimeException(
                "A meal plan or substitution job is already generating for this user",
                status_code=status.HTTP_409_CONFLICT,
                source="substitutions",
            )

        slots = await self._plan_repo.get_slots(plan.id)
        target_slot = next((s for s in slots if s.slot_id == body.slot_id), None)
        if target_slot is None:
            raise RuntimeException(
                f"Slot {body.slot_id} not found on meal plan",
                status_code=status.HTTP_404_NOT_FOUND,
                source="substitutions",
            )

        current_options = {s.slot_id: s.option_id for s in slots}
        sub = MealPlanSubstitutionEntity(
            user_id=user_id,
            from_plan_id=plan.id,
            to_plan_id=None,
            slot_id=body.slot_id,
            status=MealPlanJobStatus.GENERATING.value,
            message=f"Substituting slot {body.slot_id}",
            before_snapshot=dict(target_slot.snapshot),
            after_snapshot=None,
            excluded_combination_ids=list(body.exclude_combination_ids),
        )
        await self._plan_repo.create_substitution(sub)
        planning_profile = to_planning_profile(profile_entity)
        sub_id = sub.id
        week_start = plan.week_start
        excluded = list(body.exclude_combination_ids)

        def launch() -> None:
            track_background_task(
                _run_substitute_job(
                    substitution_id=sub_id,
                    from_plan_id=plan_id,
                    user_id=user_id,
                    planning_profile=planning_profile,
                    current_options=current_options,
                    slot_id=body.slot_id,
                    week_start=week_start,
                    exclude_combination_ids=excluded,
                    gateway=self._gateway,
                    session_factory=self._job_session_factory,
                )
            )

        return (
            CreateSubstitutionAcceptedDto(
                substitution_id=sub_id,
                status=MealPlanJobStatus.GENERATING,
            ),
            launch,
        )

    async def get_substitution(
        self, user_id: UUID, substitution_id: UUID
    ) -> SubstitutionDetailDto:
        sub = await self._plan_repo.get_owned_substitution(substitution_id, user_id)
        if sub is None:
            raise RuntimeException(
                "Substitution not found",
                status_code=status.HTTP_404_NOT_FOUND,
                source="substitutions",
            )
        return _to_substitution_dto(sub)

    async def get_plan(self, user_id: UUID, plan_id: UUID) -> MealPlanDetailDto:
        plan = await self._plan_repo.get_owned_plan(plan_id, user_id)
        if plan is None:
            raise RuntimeException(
                "Meal plan not found",
                status_code=status.HTTP_404_NOT_FOUND,
                source="meal-plans",
            )
        slots = (
            await self._plan_repo.get_slots(plan.id)
            if plan.status == MealPlanJobStatus.FEASIBLE.value
            else []
        )
        return _to_detail_dto(plan, slots)

    async def list_plans(
        self, user_id: UUID, *, current_only: bool = False
    ) -> list[MealPlanSummaryDto]:
        plans = await self._plan_repo.list_plans(user_id, current_only=current_only)
        return [MealPlanSummaryDto.model_validate(p) for p in plans]


meal_plans_router = APIRouter(
    prefix="/meal-plans",
    tags=["meal-plans"],
    route_class=TransformRoute,
)

substitutions_router = APIRouter(
    prefix="/substitutions",
    tags=["substitutions"],
    route_class=TransformRoute,
)


@meal_plans_router.post("", status_code=status.HTTP_202_ACCEPTED)
@response_message("Meal plan generation started")
async def create_meal_plan(
    body: GeneratePlanRequest,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[AiGateway, Depends(get_ai_gateway)],
    job_factory: Annotated[Callable[[], Any], Depends(get_job_session_factory)],
) -> GeneratePlanAcceptedDto:
    service = MealPlanService(session, gateway, job_factory)
    dto, launch = await service.start_generation(user.id, body)
    await session.commit()
    launch()
    return dto


@meal_plans_router.get("")
@response_message("Meal plans retrieved")
async def list_meal_plans(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[AiGateway, Depends(get_ai_gateway)],
    current: bool = Query(default=False),
) -> list[MealPlanSummaryDto]:
    return await MealPlanService(session, gateway).list_plans(user.id, current_only=current)


@meal_plans_router.get("/{plan_id}")
@response_message("Meal plan retrieved")
async def get_meal_plan(
    plan_id: UUID,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[AiGateway, Depends(get_ai_gateway)],
) -> MealPlanDetailDto:
    return await MealPlanService(session, gateway).get_plan(user.id, plan_id)


@meal_plans_router.post("/{plan_id}/substitutions", status_code=status.HTTP_202_ACCEPTED)
@response_message("Meal plan substitution started")
async def create_meal_plan_substitution(
    plan_id: UUID,
    body: CreateSubstitutionRequest,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[AiGateway, Depends(get_ai_gateway)],
    job_factory: Annotated[Callable[[], Any], Depends(get_job_session_factory)],
) -> CreateSubstitutionAcceptedDto:
    service = MealPlanService(session, gateway, job_factory)
    dto, launch = await service.start_substitution(user.id, plan_id, body)
    await session.commit()
    launch()
    return dto


@substitutions_router.get("/{substitution_id}")
@response_message("Substitution retrieved")
async def get_substitution(
    substitution_id: UUID,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[AiGateway, Depends(get_ai_gateway)],
) -> SubstitutionDetailDto:
    return await MealPlanService(session, gateway).get_substitution(user.id, substitution_id)
