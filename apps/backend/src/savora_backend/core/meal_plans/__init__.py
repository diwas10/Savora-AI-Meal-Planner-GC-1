"""Weekly meal plans (section 4.2): entities, DTOs, repository, jobs, service, routes."""

from savora_backend.core.meal_plans.controller import meal_plans_router
from savora_backend.core.meal_plans.dto import (
    CreateSubstitutionAcceptedDto,
    CreateSubstitutionRequest,
    GeneratePlanAcceptedDto,
    GeneratePlanRequest,
    MealPlanDetailDto,
    MealPlanSlotDto,
    MealPlanSummaryDto,
    ReplacementOptionsDto,
    ReplacementOptionsRequest,
    SubstitutionDetailDto,
)
from savora_backend.core.meal_plans.entity import (
    MealPlanEntity,
    MealPlanJobStatus,
    MealPlanSlotEntity,
    MealPlanSubstitutionEntity,
)
from savora_backend.core.meal_plans.jobs import (
    mark_stale_generating_jobs_failed,
    track_background_task,
    wait_for_background_tasks,
)
from savora_backend.core.meal_plans.repository import MealPlanRepository
from savora_backend.core.meal_plans.service import MealPlanService

__all__ = [
    "CreateSubstitutionAcceptedDto",
    "CreateSubstitutionRequest",
    "GeneratePlanAcceptedDto",
    "GeneratePlanRequest",
    "MealPlanDetailDto",
    "MealPlanEntity",
    "MealPlanJobStatus",
    "MealPlanRepository",
    "MealPlanService",
    "MealPlanSlotDto",
    "MealPlanSlotEntity",
    "MealPlanSubstitutionEntity",
    "MealPlanSummaryDto",
    "ReplacementOptionsDto",
    "ReplacementOptionsRequest",
    "SubstitutionDetailDto",
    "mark_stale_generating_jobs_failed",
    "meal_plans_router",
    "track_background_task",
    "wait_for_background_tasks",
]
