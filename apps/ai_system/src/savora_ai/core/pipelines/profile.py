"""The profile facts a pipeline needs, and the stand-in profile screen.

`PlanningProfile` is what the backend maps its stored, user-confirmed profile into; the
AI layer never reads the database. The screen below is a STAND-IN for the Rule Engine's
diet/allergy/cultural rules, which do not exist yet (no production KB): it uses the same
proxy as the coverage report (`meal_composition/coverage.py`):

- diet: every dish must carry the Food.com diet tag (unverified metadata); a missing tag
  excludes the dish (fail closed).
- explicit exclusions and allergies: whole-word match on the dish name and ingredients
  ("egg" never matches "eggplant"). A word naming a known allergen group ("milk",
  "tree nut", "gluten") also blocks the ingredients that contain it (ghee, pesto, soy
  sauce; `allergens.py`). The table is unreviewed and cannot see what a recipe omits, so
  results are never reported as allergy-verified; see `SafetyVerification`.
- conditions (type 2 diabetes, hypertension, dyslipidemia) are NOT enforced; results say so.

When Member 2 ships the production KB, these checks move into `filter_candidates` and
this screen is deleted; the pipeline signatures do not change.
"""

from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel

from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.meal_composition.models import MealCombination
from savora_ai.core.pipelines.allergens import all_derived, block_rules
from savora_ai.schemas.enums import CuisinePolicy, HealthCondition

_Word = Annotated[str, StringConstraints(min_length=1, max_length=64, strip_whitespace=True)]


class _PipelineModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        allow_inf_nan=False,
    )


class DietPattern(StrEnum):
    VEGETARIAN = "VEGETARIAN"
    VEGAN = "VEGAN"


class PlanningProfile(_PipelineModel):
    """User-confirmed facts only; never inferred from religion or ethnicity (section 1)."""

    profile_id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")]
    profile_version: int = Field(ge=1)
    diet: DietPattern | None = None
    cuisine_policy: CuisinePolicy = CuisinePolicy.MIXED
    cuisines: tuple[str, ...] = ()  # catalogue names, e.g. "Nepali"; required for STRICT
    excluded_ingredients: Annotated[tuple[_Word, ...], Field(max_length=50)] = ()
    allergies: Annotated[tuple[_Word, ...], Field(max_length=50)] = ()  # confirmed only
    conditions: tuple[HealthCondition, ...] = ()
    seed_recipe_ids: Annotated[tuple[str, ...], Field(max_length=5)] = ()  # ADR 0005 D1


class SafetyVerification(_PipelineModel):
    """Attached to every pipeline result while the stand-in KB is in use."""

    status: Literal["STAND_IN_UNVERIFIED"] = "STAND_IN_UNVERIFIED"
    kb_environment: Literal["SYNTHETIC"] = "SYNTHETIC"
    allergens_checked_by: Literal["DERIVED_TERM_MAP", "INGREDIENT_NAME_MATCH", "NOT_APPLICABLE"]
    diet_checked_by: Literal["FOODCOM_TAG", "NOT_APPLICABLE"]
    conditions_not_enforced: tuple[HealthCondition, ...]
    message: str


def safety_verification(profile: PlanningProfile) -> SafetyVerification:
    parts = ["Results come from a non-production stand-in rule set."]
    derived = all_derived(profile.allergies)
    if profile.allergies and derived:
        parts.append(
            "Allergens were matched by ingredient name, including common derived "
            "ingredients, using an unreviewed list. Do not rely on this for allergy safety."
        )
    elif profile.allergies:
        parts.append(
            "Some allergies were matched by ingredient name only; derived ingredients are "
            "not detected for them. Do not rely on this for allergy safety."
        )
    if profile.diet is not None:
        parts.append("Diet is checked with unverified Food.com tags.")
    if profile.conditions:
        parts.append("Health-condition rules are not applied yet.")
    return SafetyVerification(
        allergens_checked_by=(
            "NOT_APPLICABLE"
            if not profile.allergies
            else "DERIVED_TERM_MAP"
            if derived
            else "INGREDIENT_NAME_MATCH"
        ),
        diet_checked_by="FOODCOM_TAG" if profile.diet is not None else "NOT_APPLICABLE",
        conditions_not_enforced=profile.conditions,
        message=" ".join(parts),
    )


def dish_allowed(dish: CatalogueRecipe, profile: PlanningProfile) -> bool:
    """Diet tag present and no excluded or allergen term in the dish name or any
    ingredient (fail closed)."""
    if profile.diet is not None and profile.diet.value.lower() not in dish.diet_tags:
        return False
    rules = block_rules((*profile.excluded_ingredients, *profile.allergies))
    return not any(r.blocks(t) for t in (dish.name, *dish.ingredients) for r in rules)


def cuisine_allowed(cuisines: Sequence[str], profile: PlanningProfile) -> bool:
    """STRICT keeps the profile's cuisines only; MAJORITY and MIXED keep everything (the
    MAJORITY share is a weekly balance, not enforced by the stand-in)."""
    if profile.cuisine_policy is not CuisinePolicy.STRICT:
        return True
    return bool(set(cuisines) & set(profile.cuisines))


def combination_allowed(
    combination: MealCombination, dishes: Mapping[str, CatalogueRecipe], profile: PlanningProfile
) -> bool:
    return cuisine_allowed(combination.cuisines, profile) and all(
        dish_allowed(dishes[c.dish_id], profile) for c in combination.components
    )
