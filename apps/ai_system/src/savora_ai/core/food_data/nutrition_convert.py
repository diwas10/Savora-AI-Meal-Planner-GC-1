"""Convert Food.com nutrition (kcal + %DV) into physical units; pure functions only.

Food.com `nutrition` is [calories kcal, total fat %DV, sugar %DV, sodium %DV,
protein %DV, saturated fat %DV, carbohydrates %DV]. A %DV is a share of a reference
daily amount, so grams = %DV / 100 * reference. Which reference was used by the
source is verified in docs/adr/0001-catalogue-v0-and-nutrition-basis.md.
"""

import ast

from savora_ai.core.food_data.models import DvReference, ServingNutrition

# FDA labelling table in force before 2016 (2,000 kcal diet). Best fit to Food.com:
# see ADR 0001 for the energy-consistency evidence. Sodium and saturated fat are
# ASSUMED to follow the same table; the energy check cannot confirm them.
FDA_1993 = DvReference(
    name="FDA_1993_LABEL_2000KCAL",
    fat_g=65.0,
    saturated_fat_g=20.0,
    carbohydrate_g=300.0,
    protein_g=50.0,
    sodium_mg=2400.0,
)

# FDA labelling update of 2016, kept only to let the ADR comparison be re-run.
FDA_2016 = DvReference(
    name="FDA_2016_LABEL_2000KCAL",
    fat_g=78.0,
    saturated_fat_g=20.0,
    carbohydrate_g=275.0,
    protein_g=50.0,
    sodium_mg=2300.0,
)

DV_REFERENCES: dict[str, DvReference] = {ref.name: ref for ref in (FDA_1993, FDA_2016)}

# Atwater general factors: kcal per gram of fat, carbohydrate and protein.
_KCAL_PER_G_FAT = 9.0
_KCAL_PER_G_CARBOHYDRATE = 4.0
_KCAL_PER_G_PROTEIN = 4.0


def parse_nutrition(value: object) -> tuple[float, float, float, float, float, float, float]:
    """Parse the raw seven-value vector; fail loudly instead of guessing."""
    if isinstance(value, str):
        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError) as exc:
            raise ValueError("nutrition must be a literal list of seven numbers") from exc
    if not isinstance(value, list | tuple) or len(value) != 7:
        raise ValueError("nutrition must contain exactly seven values")
    numbers: list[float] = []
    for item in value:
        # bool is an int subclass; reject it so True never becomes 1.0.
        if isinstance(item, bool) or not isinstance(item, int | float):
            raise ValueError("nutrition values must be numbers")
        if item != item or item in (float("inf"), float("-inf")) or item < 0:
            raise ValueError("nutrition values must be finite and non-negative")
        numbers.append(float(item))
    calories, fat, sugar, sodium, protein, sat_fat, carbs = numbers
    return calories, fat, sugar, sodium, protein, sat_fat, carbs


def to_serving_nutrition(
    raw: tuple[float, float, float, float, float, float, float], ref: DvReference
) -> ServingNutrition:
    """Turn %DV into grams/mg per serving. Sugar stays unknown (no verified reference)."""
    calories, fat, _sugar, sodium, protein, sat_fat, carbs = raw
    return ServingNutrition(
        energy_kcal=calories,
        fat_g=fat / 100.0 * ref.fat_g,
        saturated_fat_g=sat_fat / 100.0 * ref.saturated_fat_g,
        carbohydrate_g=carbs / 100.0 * ref.carbohydrate_g,
        protein_g=protein / 100.0 * ref.protein_g,
        sodium_mg=sodium / 100.0 * ref.sodium_mg,
        sugars_g=None,
    )


def implied_energy_kcal(nutrition: ServingNutrition) -> float:
    """Energy implied by the macros; used only as a data-consistency check."""
    return (
        _KCAL_PER_G_FAT * nutrition.fat_g
        + _KCAL_PER_G_CARBOHYDRATE * nutrition.carbohydrate_g
        + _KCAL_PER_G_PROTEIN * nutrition.protein_g
    )


def energy_ratio(nutrition: ServingNutrition) -> float | None:
    """Implied / stated energy. None when stated energy is zero (ratio undefined)."""
    if nutrition.energy_kcal <= 0:
        return None
    return implied_energy_kcal(nutrition) / nutrition.energy_kcal


def per_100g(nutrition: ServingNutrition, serving_mass_g: float | None) -> ServingNutrition | None:
    """Scale a serving to 100 g. Unknown serving mass gives None, never a guess."""
    if serving_mass_g is None:
        return None
    factor = 100.0 / serving_mass_g
    return ServingNutrition(
        energy_kcal=nutrition.energy_kcal * factor,
        fat_g=nutrition.fat_g * factor,
        saturated_fat_g=nutrition.saturated_fat_g * factor,
        carbohydrate_g=nutrition.carbohydrate_g * factor,
        protein_g=nutrition.protein_g * factor,
        sodium_mg=nutrition.sodium_mg * factor,
        sugars_g=None if nutrition.sugars_g is None else nutrition.sugars_g * factor,
    )
