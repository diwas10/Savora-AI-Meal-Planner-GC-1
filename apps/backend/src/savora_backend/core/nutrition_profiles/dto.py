"""Profile DTOs."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from savora_ai.core.nutrition.models import NutritionTargets
from savora_ai.core.pipelines import DietPattern
from savora_ai.schemas.enums import ActivityLevel, CuisinePolicy, Goal, HealthCondition, Sex
from savora_backend.core.common import CamelModel


class ProfileUpsertRequest(CamelModel):
    age_years: int = Field(ge=19, le=100)
    sex: Sex
    height_cm: float = Field(ge=100, le=250)
    weight_kg: float = Field(ge=30, le=300)
    activity: ActivityLevel
    goal: Goal
    diet: DietPattern | None = None
    cuisine_policy: Literal[CuisinePolicy.MIXED, CuisinePolicy.STRICT] = CuisinePolicy.MIXED
    cuisines: list[str] = Field(default_factory=list, max_length=25)
    excluded_ingredients: list[str] = Field(default_factory=list, max_length=50)
    allergies: list[str] = Field(default_factory=list, max_length=50)
    allergies_confirmed: bool = False
    conditions: list[HealthCondition] = Field(default_factory=list, max_length=10)


class UserProfileDto(CamelModel):
    id: UUID
    user_id: UUID
    version: int
    age_years: int
    sex: Sex
    height_cm: float
    weight_kg: float
    activity: ActivityLevel
    goal: Goal
    diet: DietPattern | None
    cuisine_policy: CuisinePolicy
    cuisines: list[str]
    excluded_ingredients: list[str]
    allergies: list[str]
    allergies_confirmed_at: datetime | None
    conditions: list[HealthCondition]
    seed_recipe_ids: list[str]


class ProfileEnvelopeData(CamelModel):
    profile: UserProfileDto
    targets: NutritionTargets
    needs_seed_picks: bool
