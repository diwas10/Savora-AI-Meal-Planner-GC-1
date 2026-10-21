"""Stored profile -> the AI layer's `PlanningProfile` (section 9)."""

from savora_ai.core.pipelines import DietPattern, PlanningProfile
from savora_ai.schemas.enums import CuisinePolicy, HealthCondition
from savora_backend.core.nutrition_profiles.entity import UserProfileEntity


def to_planning_profile(entity: UserProfileEntity) -> PlanningProfile:
    return PlanningProfile(
        profile_id=str(entity.user_id),
        profile_version=entity.version,
        diet=DietPattern(entity.diet) if entity.diet else None,
        cuisine_policy=CuisinePolicy(entity.cuisine_policy),
        cuisines=tuple(entity.cuisines),
        excluded_ingredients=tuple(entity.excluded_ingredients),
        allergies=tuple(entity.allergies),
        conditions=tuple(HealthCondition(c) for c in entity.conditions),
        seed_recipe_ids=tuple(entity.seed_recipe_ids[:5]),
    )
