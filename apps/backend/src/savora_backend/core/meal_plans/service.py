"""Weekly plan generation and reads (section 4.2)."""

from uuid import UUID

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from savora_backend.ai.gateway import AiGateway
from savora_backend.core.meal_plans.dto import (
    GeneratePlanAcceptedDto,
    GeneratePlanRequest,
    MealPlanDetailDto,
    MealPlanSummaryDto,
)
from savora_backend.core.meal_plans.entity import MealPlanEntity, MealPlanJobStatus
from savora_backend.core.meal_plans.jobs import (
    SessionFactory,
    run_plan_week_job,
    track_background_task,
)
from savora_backend.core.meal_plans.mapper import to_detail_dto
from savora_backend.core.meal_plans.repository import MealPlanRepository
from savora_backend.core.nutrition_profiles import ProfileRepository, to_planning_profile
from savora_backend.database import get_session_factory
from savora_backend.exceptions import RuntimeException

SOURCE = "meal-plans"
JOB_RUNNING = "A meal plan or swap is already being prepared. Please wait for it to finish."


def conflict(message: str, source: str = SOURCE) -> RuntimeException:
    return RuntimeException(message, status_code=status.HTTP_409_CONFLICT, source=source)


def not_found(message: str, source: str = SOURCE) -> RuntimeException:
    return RuntimeException(message, status_code=status.HTTP_404_NOT_FOUND, source=source)


class MealPlanService:
    def __init__(
        self,
        session: AsyncSession,
        gateway: AiGateway,
        job_session_factory: SessionFactory | None = None,
    ) -> None:
        self._session = session
        self._plans = MealPlanRepository(session)
        self._profiles = ProfileRepository(session)
        self._gateway = gateway
        self._job_session_factory = job_session_factory

    async def start_generation(
        self, user_id: UUID, body: GeneratePlanRequest
    ) -> GeneratePlanAcceptedDto:
        """Insert a GENERATING plan, commit, then start the job (202 + polling)."""
        # Locking the profile row serialises this user's job starts (no check-then-insert
        # race); the partial unique index uq_meal_plans_user_generating backs it up.
        profile = await self._profiles.lock_by_user_id(user_id)
        if profile is None:
            raise conflict("complete onboarding first")
        if await self._plans.has_generating_job(user_id):
            raise conflict(JOB_RUNNING)
        plan = MealPlanEntity(
            user_id=user_id,
            week_start=body.week_start,
            revision=await self._plans.next_revision_for_week(user_id, body.week_start),
            status=MealPlanJobStatus.GENERATING.value,
            message="Generating your 7-day plan",
            profile_version=profile.version,
            catalogue_version=self._gateway.bundle.version,
            is_current=False,
        )
        try:
            await self._plans.create_plan(plan)
        except IntegrityError as exc:
            raise conflict(JOB_RUNNING) from exc
        planning_profile = to_planning_profile(profile)
        await self._session.commit()  # the job must see the committed row
        track_background_task(
            run_plan_week_job(
                plan_id=plan.id,
                user_id=user_id,
                planning_profile=planning_profile,
                week_start=body.week_start,
                gateway=self._gateway,
                session_factory=self._job_factory(),
            )
        )
        return GeneratePlanAcceptedDto(plan_id=plan.id)

    def _job_factory(self) -> SessionFactory:
        return self._job_session_factory or get_session_factory()

    async def get_plan(self, user_id: UUID, plan_id: UUID) -> MealPlanDetailDto:
        plan = await self._plans.get_owned_plan(plan_id, user_id)
        if plan is None:
            raise not_found("Meal plan not found")
        feasible = plan.status == MealPlanJobStatus.FEASIBLE.value
        return to_detail_dto(plan, await self._plans.get_slots(plan.id) if feasible else [])

    async def list_plans(
        self, user_id: UUID, *, current_only: bool = False
    ) -> list[MealPlanSummaryDto]:
        plans = await self._plans.list_plans(user_id, current_only=current_only)
        return [MealPlanSummaryDto.model_validate(p) for p in plans]
