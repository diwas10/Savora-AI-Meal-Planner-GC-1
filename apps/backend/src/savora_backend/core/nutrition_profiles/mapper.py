"""Stored profile -> the AI layer's `PlanningProfile` (section 9)."""

import json

from savora_ai.core.nutrition.models import NutritionTargets
from savora_ai.core.pipelines import DayTargets, DietPattern, PlanningProfile
from savora_ai.schemas.enums import CuisinePolicy, HealthCondition
from savora_backend.core.nutrition_profiles.entity import (
    UserNutritionProfileEntity,
    UserProfileEntity,
)


def to_day_targets(snapshot: UserNutritionProfileEntity | None) -> DayTargets | None:
    """The energy band and protein minimum planning sizes portions toward (ADR 0006)."""
    if snapshot is None:
        return None
    targets = NutritionTargets.model_validate_json(json.dumps(snapshot.targets))
    energy = targets.energy_kcal
    if energy.min is None or energy.target is None or energy.max is None or energy.min <= 0:
        return None
    protein = next((b.bounds for b in targets.nutrient_bounds if b.nutrient == "protein_g"), None)
    return DayTargets(
        energy_kcal_min=energy.min,
        energy_kcal_target=energy.target,
        energy_kcal_max=energy.max,
        protein_g_min=None if protein is None else protein.min,
    )


def to_planning_profile(
    entity: UserProfileEntity, snapshot: UserNutritionProfileEntity | None = None
) -> PlanningProfile:
    """`snapshot` is the profile version's target snapshot; planning needs it, a craving
    does not."""
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
        targets=to_day_targets(snapshot),
    )
