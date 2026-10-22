"""Weekly plan, replacement-option and substitution DTOs."""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints

from savora_ai.core.pipelines import (
    PlannedMeal,
    ReplacementOptions,
    SafetyVerification,
    SwapProof,
)
from savora_ai.core.pipelines.planning import SLOT_ID, DayTotals, SearchSummary
from savora_ai.schemas.craving import CravingRequest
from savora_backend.core.common import CamelModel
from savora_backend.core.cravings import CravingParseMeta
from savora_backend.core.meal_plans.entity import MealPlanJobStatus

SlotIdStr = Annotated[str, StringConstraints(pattern=SLOT_ID)]
_CombinationIds = Annotated[list[str], Field(default_factory=list, max_length=50)]


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


class ReplacementOptionsRequest(CamelModel):
    """Optional words for what the user would like instead ("something spicy, no rice")."""

    preference_text: str | None = Field(default=None, max_length=500)
    exclude_combination_ids: _CombinationIds


class ReplacementOptionsDto(CamelModel):
    parse: CravingParseMeta | None = None  # how the words were read, when given
    result: ReplacementOptions


class CreateSubstitutionRequest(CamelModel):
    slot_id: SlotIdStr
    expected_revision: int = Field(ge=1)
    exclude_combination_ids: _CombinationIds
    replacement_combination_id: str | None = Field(default=None, max_length=255)
    preference_text: str | None = Field(default=None, max_length=500)


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
    replacement_combination_id: str | None = None
    preference: CravingRequest | None = None
    before_snapshot: PlannedMeal | None = None
    after_snapshot: PlannedMeal | None = None
    proof: SwapProof | None = None  # Member 2's compact B1 decision, when it ran
    created_at: datetime
    updated_at: datetime
