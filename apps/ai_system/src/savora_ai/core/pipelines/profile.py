"""The profile facts a pipeline needs, and the stand-in profile screen.

`PlanningProfile` is what the backend maps its stored, user-confirmed profile into; the
AI layer never reads the database. The screen below is a STAND-IN for the Rule Engine's
diet/allergy/cultural rules, which do not exist yet (no production KB): it uses the same
proxy as the coverage report (`meal_composition/coverage.py`):

- diet: every dish must carry the Food.com diet tag (unverified metadata); a missing tag
  excludes the dish (fail closed).
- allergies: whole-word match on the dish name and ingredients, in ANY amount ("egg"
  never matches "eggplant"). A word naming a known allergen group ("milk",
  "tree nut", "gluten") also blocks the ingredients that contain it (ghee, pesto, soy
  sauce; `allergens.py`). The table is team-reviewed but cannot see what a recipe omits, so
  results are never reported as allergy-verified; see `SafetyVerification`.
- excluded ingredients (preferences): block only as a MAIN ingredient; a minor one is
  swapped or left out, and the meal says so (`ingredient_swaps.py`, `dish_swaps`).
- conditions (type 2 diabetes, hypertension, dyslipidemia) are NOT enforced; results say so.

When Member 2 ships the production KB, these checks move into `filter_candidates` and
this screen is deleted; the pipeline signatures do not change.
"""

from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.alias_generators import to_camel

from savora_ai.core.explainability.explanation import (
    MealExplanation,
    Reason,
    ReasonKind,
    RecipeExplanation,
)
from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.meal_composition.models import MealCombination
from savora_ai.core.pipelines.allergens import all_derived, block_rules
from savora_ai.core.pipelines.ingredient_swaps import exclusion_swaps
from savora_ai.core.recommendation.seeds import IngredientSwap
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


class DayTargets(_PipelineModel):
    """The day's estimated targets that planning sizes portions toward (ADR 0006).

    Copied from the profile version's `NutritionTargets`; general-population estimates,
    not clinical limits."""

    energy_kcal_min: float = Field(gt=0)
    energy_kcal_target: float = Field(gt=0)
    energy_kcal_max: float = Field(gt=0)
    protein_g_min: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def check_order(self) -> Self:
        if not self.energy_kcal_min <= self.energy_kcal_target <= self.energy_kcal_max:
            raise ValueError("energy bounds must satisfy min <= target <= max")
        return self


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
    targets: DayTargets | None = None  # None: meals keep their STANDARD portions


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
            "ingredients, using a stand-in list. Do not rely on this for allergy safety."
        )
    elif profile.allergies:
        parts.append(
            "Some allergies were matched by ingredient name only; derived ingredients are "
            "not detected for them. Do not rely on this for allergy safety."
        )
    if profile.excluded_ingredients:
        parts.append(
            "Ingredients you avoid remove a dish only when they are a main ingredient; a "
            "minor one is listed on the meal to leave out or swap."
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


def dish_swaps(
    dish: CatalogueRecipe, profile: PlanningProfile
) -> tuple[IngredientSwap, ...] | None:
    """None when the dish is not allowed; else how to cook it without the user's EXCLUDED
    ingredients (empty when none is in it).

    Diet tag present and no allergen term in the name or any ingredient, in any amount
    (fail closed). An excluded ingredient blocks only as a main ingredient; a minor one is
    swapped or left out (`ingredient_swaps.py`)."""
    if profile.diet is not None and profile.diet.value.lower() not in dish.diet_tags:
        return None
    allergens = block_rules(tuple(profile.allergies))
    if any(r.blocks(t) for t in (dish.name, *dish.ingredients) for r in allergens):
        return None
    return exclusion_swaps(dish, profile.excluded_ingredients, profile.allergies)


def dish_allowed(dish: CatalogueRecipe, profile: PlanningProfile) -> bool:
    return dish_swaps(dish, profile) is not None


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


def with_cook_without[E: (MealExplanation, RecipeExplanation)](
    explanation: E, dishes: Sequence[CatalogueRecipe], profile: PlanningProfile
) -> E:
    """Adds what to leave out or swap, when an excluded ingredient is a minor part."""
    lines: list[str] = []
    refs: list[str] = []
    for dish in dishes:
        for swap in dish_swaps(dish, profile) or ():
            instead = "leave it out" if swap.instead == "leave it out" else f"use {swap.instead}"
            lines.append(f"no {swap.ingredient} in {dish.name.strip()}: {instead}")
            refs.append(dish.recipe_id)
    if not lines:
        return explanation
    reason = Reason(
        kind=ReasonKind.COMPOSITION,
        code="COOK_WITHOUT_EXCLUDED",
        message="Cook it your way: "
        + "; ".join(lines)
        + ". These are a minor part of the recipe; the nutrition shown still includes them.",
        references=tuple(dict.fromkeys(refs)),
    )
    return explanation.model_copy(update={"reasons": (*explanation.reasons, reason)})
