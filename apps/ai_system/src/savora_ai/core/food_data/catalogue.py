"""Validate raw Food.com rows, assign meal types and pick a reproducible catalogue.

Pure functions over plain values so they can be tested without pandas or the dataset.
The thresholds below are PROVISIONAL (ADR 0001) and are named so they can change in one place.
"""

import ast
import hashlib
from collections.abc import Iterable, Mapping, Sequence

from savora_ai.core.food_data.foodcom_cuisines import get_cuisines, normalize_tags
from savora_ai.core.food_data.models import (
    CatalogueRecipe,
    DvReference,
    QuarantinedRow,
    ServingMassOverride,
)
from savora_ai.core.food_data.nutrition_convert import (
    energy_ratio,
    parse_nutrition,
    to_serving_nutrition,
)
from savora_ai.schemas.enums import MealType, QuarantineReason

# --- PROVISIONAL sanity limits (one recipe serving) ---------------------------------
MIN_KCAL = 50.0  # below this a "meal" is a condiment or a data error
MAX_KCAL = 1500.0  # above this the row is probably a whole batch, not one serving
MAX_PDV = 300.0  # %DV of any macro above this is treated as an extreme outlier
# Atwater-implied energy / stated energy must fall inside this band (median is ~0.98).
ENERGY_RATIO_RANGE = (0.75, 1.25)

# Exact Food.com course tag -> meal type. Food.com has NO "dinner" tag, so dinner is
# derived from "main-dish". A recipe may serve several meals.
MEAL_TAGS: dict[str, MealType] = {
    "breakfast": MealType.BREAKFAST,
    "lunch": MealType.LUNCH,
    "main-dish": MealType.DINNER,
}

# Diet labels we keep as unverified metadata for later rule-engine use.
DIET_TAGS = frozenset({"vegetarian", "vegan"})

# PROVISIONAL catalogue size per meal type (a recipe is counted once overall).
DEFAULT_QUOTAS: dict[MealType, int] = {
    MealType.BREAKFAST: 60,
    MealType.LUNCH: 90,
    MealType.DINNER: 90,
}


def parse_string_list(value: object) -> tuple[str, ...]:
    """Parse a Python-list-as-text column such as ingredients; fail loudly."""
    if isinstance(value, str):
        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError) as exc:
            raise ValueError("expected a literal list of strings") from exc
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise ValueError("expected a list of strings")
    return tuple(item.strip() for item in value if item.strip())


def meal_types_for(tags: frozenset[str]) -> tuple[MealType, ...]:
    """Meal types in a fixed (enum) order so output is deterministic."""
    found = {MEAL_TAGS[tag] for tag in tags if tag in MEAL_TAGS}
    return tuple(meal for meal in MealType if meal in found)


def _order_key(recipe: CatalogueRecipe, seed: str) -> tuple[bool, str]:
    """Cuisine-labelled recipes first (cuisine policies need them), then a seeded hash."""
    digest = hashlib.sha256(f"{seed}:{recipe.recipe_id}".encode()).hexdigest()
    return not recipe.cuisines, digest


def build_recipe(
    source_id: int,
    name: str,
    tags_raw: object,
    nutrition_raw: object,
    ingredients_raw: object,
    ref: DvReference,
) -> CatalogueRecipe | QuarantinedRow:
    """Return an accepted entry, or the quarantined row with EVERY defect found.

    A recipe without a meal tag is accepted with empty `meal_types` (unclassified).
    """

    reasons: list[QuarantineReason] = []

    raw = None

    try:
        raw = parse_nutrition(nutrition_raw)
    except ValueError:
        reasons.append(QuarantineReason.MALFORMED_NUTRITION)

    tags: frozenset[str] = frozenset()
    ingredients: tuple[str, ...] = ()

    try:
        tags = normalize_tags(tags_raw)
        ingredients = parse_string_list(ingredients_raw)
    except ValueError:
        reasons.append(QuarantineReason.MALFORMED_METADATA)
    else:
        if not name.strip() or not ingredients or source_id <= 0:
            reasons.append(QuarantineReason.MALFORMED_METADATA)

    nutrition = None
    if raw is not None:
        calories, fat, _sugar, sodium, protein, sat_fat, carbs = raw

        if (
            not MIN_KCAL <= calories <= MAX_KCAL
            or max(fat, protein, sat_fat, carbs, sodium) > MAX_PDV
        ):
            reasons.append(QuarantineReason.NUTRITION_OUT_OF_RANGE)
        else:
            nutrition = to_serving_nutrition(raw, ref)
            ratio = energy_ratio(nutrition)
            if ratio is None or not ENERGY_RATIO_RANGE[0] <= ratio <= ENERGY_RATIO_RANGE[1]:
                reasons.append(QuarantineReason.ENERGY_INCONSISTENT)

    if reasons or nutrition is None:
        return QuarantinedRow(source_id=str(source_id), name=name, reasons=tuple(reasons))

    return CatalogueRecipe(
        recipe_id=f"FC_{source_id}",
        name=name.strip(),
        ingredients=ingredients,
        cuisines=tuple(get_cuisines(tags_raw)),
        diet_tags=tuple(sorted(tags & DIET_TAGS)),
        meal_types=meal_types_for(tags),
        nutrition_per_serving=nutrition,
        dv_reference=ref.name,
        provenance=(
            "Food.com RAW_recipes.csv",
            f"%DV converted with {ref.name}; sugar left unknown",
            "serving mass unverified",
        ),
    )


def select_catalogue(
    candidates: Iterable[CatalogueRecipe],
    quotas: Mapping[MealType, int],
    seed: str,
) -> tuple[CatalogueRecipe, ...]:
    """Pick a reproducible subset: same candidates + quotas + seed => same result."""
    ordered = sorted(candidates, key=lambda r: _order_key(r, seed))
    chosen: dict[str, CatalogueRecipe] = {}
    for meal in MealType:
        taken = sum(1 for r in chosen.values() if meal in r.meal_types)
        for recipe in ordered:
            if taken >= quotas.get(meal, 0):
                break
            if meal in recipe.meal_types and recipe.recipe_id not in chosen:
                chosen[recipe.recipe_id] = recipe
                taken += 1
    return tuple(sorted(chosen.values(), key=lambda r: r.recipe_id))


def apply_serving_masses(
    recipes: Sequence[CatalogueRecipe], overrides: Iterable[ServingMassOverride]
) -> tuple[CatalogueRecipe, ...]:
    """Attach human-verified serving masses; unknown recipe IDs are an error."""
    by_id = {o.recipe_id: o for o in overrides}
    known = {r.recipe_id for r in recipes}
    unknown = sorted(set(by_id) - known)
    if unknown:
        raise ValueError(f"overrides reference recipes not in the catalogue: {unknown}")
    updated: list[CatalogueRecipe] = []
    for recipe in recipes:
        override = by_id.get(recipe.recipe_id)
        if override is None:
            updated.append(recipe)
            continue
        updated.append(
            CatalogueRecipe.model_validate(
                {
                    **recipe.model_dump(),
                    "serving_mass_g": override.serving_mass_g,
                    "serving_mass_source": override.source,
                }
            )
        )
    return tuple(updated)
