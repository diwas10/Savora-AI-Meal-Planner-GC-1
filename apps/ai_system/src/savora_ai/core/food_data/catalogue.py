"""Validate raw Food.com rows and classify them; selection lives in selection.py.

Pure functions over plain values so they can be tested without pandas or the dataset.
The thresholds below are PROVISIONAL (ADR 0001) and are named so they can change in one place.
"""

import ast
from collections.abc import Iterable, Sequence

from savora_ai.core.food_data.classification import classify
from savora_ai.core.food_data.foodcom_cuisines import get_cuisines, normalize_tags
from savora_ai.core.food_data.models import (
    CatalogueRecipe,
    DvReference,
    NutrientVector,
    NutritionRecord,
    QuarantinedRow,
    ServingMassOverride,
)
from savora_ai.core.food_data.nutrition_convert import (
    energy_ratio,
    implied_energy_kcal,
    parse_nutrition,
    to_serving_nutrition,
)
from savora_ai.schemas.enums import NutritionBasis, NutritionSource, QuarantineReason

# --- PROVISIONAL sanity limits (one recipe serving) ---------------------------------
# Below this a serving is seasoning, water or a data error, whatever its role. Meal dishes
# have a higher, role-aware floor (classification.MIN_MEAL_KCAL); sides may be light.
MIN_KCAL = 10.0
MAX_KCAL = 1500.0  # above this the row is probably a whole batch, not one serving
MAX_PDV = 300.0  # %DV of any macro above this is treated as an extreme outlier
# Atwater-implied energy / stated energy must fall inside this band (median is ~0.98).
ENERGY_RATIO_RANGE = (0.75, 1.25)
# Food.com stores whole-number %DV. Rounding each of fat, carbohydrate and protein by up to
# 0.5 %DV moves implied energy by up to ~10 kcal (2.9 + 6.0 + 1.0), which dominates the
# ratio for light dishes. A gap within this many kcal is rounding, not inconsistency.
ENERGY_ABS_TOLERANCE_KCAL = 10.0

# Diet labels we keep as unverified metadata for later rule-engine use.
DIET_TAGS = frozenset({"vegetarian", "vegan"})


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


def energy_consistent(nutrition: NutrientVector) -> bool:
    """Stated energy agrees with the macros within the ratio band or the rounding gap."""
    ratio = energy_ratio(nutrition)
    implied = implied_energy_kcal(nutrition)
    if ratio is None or implied is None or nutrition.energy_kcal is None:
        return False
    gap = abs(implied - nutrition.energy_kcal)
    return ENERGY_RATIO_RANGE[0] <= ratio <= ENERGY_RATIO_RANGE[1] or (
        gap <= ENERGY_ABS_TOLERANCE_KCAL
    )


def build_recipe(
    source_id: int,
    name: str,
    tags_raw: object,
    nutrition_raw: object,
    ingredients_raw: object,
    ref: DvReference,
) -> CatalogueRecipe | QuarantinedRow:
    """Return an accepted entry, or the quarantined row with EVERY defect found.

    Accepted recipes carry their Stage 2 classification; one with no usable course
    evidence is accepted as REQUIRES_REVIEW, not quarantined.
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
            if not energy_consistent(nutrition):
                reasons.append(QuarantineReason.ENERGY_INCONSISTENT)

    if reasons or nutrition is None:
        return QuarantinedRow(source_id=str(source_id), name=name, reasons=tuple(reasons))

    classification = classify(name, tags, nutrition.energy_kcal or 0.0)
    return CatalogueRecipe(
        recipe_id=f"FC_{source_id}",
        name=name.strip(),
        ingredients=ingredients,
        cuisines=tuple(get_cuisines(tags_raw)),
        diet_tags=tuple(sorted(tags & DIET_TAGS)),
        roles=classification.roles,
        dish_class=classification.dish_class,
        meal_types=classification.meal_types,
        classification_status=classification.status,
        classification_evidence=classification.evidence,
        nutrition=NutritionRecord(
            source=NutritionSource.FOODCOM_DERIVED,
            basis=NutritionBasis.PER_SERVING,
            values=nutrition,
            source_reference=ref.name,
        ),
        provenance=(
            "Food.com RAW_recipes.csv",
            f"%DV converted with {ref.name}; sugar left unknown",
            "serving mass unverified",
        ),
    )


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
