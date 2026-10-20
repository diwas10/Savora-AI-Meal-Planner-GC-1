"""Weekly meal plans: entities, DTOs, repository, background job runner, and routes."""

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import Field
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
from savora_ai.core.pipelines.planning import DayTotals, SearchSummary
from savora_backend.ai.gateway import AiGateway, get_ai_gateway
from savora_backend.auth import CurrentUser
from savora_backend.core.common import CamelModel
from savora_backend.core.nutrition_profiles import ProfileRepository, to_planning_profile
from savora_backend.database import CommonEntity, JsonbType, get_session, get_session_factory
from savora_backend.decorators import response_message
from savora_backend.exceptions import RuntimeException
from savora_backend.interceptors import TransformRoute

logger = logging.getLogger(__name__)


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


class GeneratePlanRequest(CamelModel):
    week_start: date


class GeneratePlanAcceptedDto(CamelModel):
    plan_id: UUID
    status: MealPlanJobStatus = MealPlanJobStatus.GENERATING


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

    async def has_generating_plan(self, user_id: UUID) -> bool:
        stmt = select(MealPlanEntity.id).where(
            MealPlanEntity.user_id == user_id,
            MealPlanEntity.status == MealPlanJobStatus.GENERATING.value,
        )
        found = await self._session.scalar(stmt)
        return found is not None

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
    """On startup, mark any plans left in GENERATING as FAILED with 'server restarted'."""
    factory = session_factory or get_session_factory()
    async with factory() as session, session.begin():
        stmt = select(MealPlanEntity).where(
            MealPlanEntity.status == MealPlanJobStatus.GENERATING.value
        )
        scalars = await session.scalars(stmt)
        stale = list(scalars.all())
        for plan in stale:
            plan.status = MealPlanJobStatus.FAILED.value
            plan.message = "server restarted"
        await session.flush()
        return len(stale)


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
        if await self._plan_repo.has_generating_plan(user_id):
            raise RuntimeException(
                "A meal plan is already generating for this user",
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
