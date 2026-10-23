"""Convert Food.com nutrition (kcal + %DV) into physical units; pure functions only.

Food.com `nutrition` is [calories kcal, total fat %DV, sugar %DV, sodium %DV,
protein %DV, saturated fat %DV, carbohydrates %DV]. A %DV is a share of a reference
daily amount, so grams = %DV / 100 * reference. Which reference was used by the
source is verified in docs/adr/0001-catalogue-v0-and-nutrition-basis.md.
"""

import ast

from savora_ai.core.food_data.models import NUTRIENT_FIELDS, DvReference, NutrientVector

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

# Food.com's sugar %DV uses a 25 g reference, independent of the table above: on
# single-ingredient recipes the Food.com/USDA sugars-per-kcal ratio is 0.97-1.05 at 25 g
# and about 2.0 at 50 g (6 foods, 38 recipes; docs/eval/dv_verification.json, ADR 0001 D2).
SUGAR_DV_G = 25.0
# Sugars are part of carbohydrate; a value above it (beyond rounding) is a data error and
# stays unknown rather than being trusted.
_SUGAR_CARB_TOLERANCE_G = 1.0

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
) -> NutrientVector:
    """Turn %DV into grams/mg per serving. Sugar uses its own verified 25 g reference and
    is unknown (None) when it exceeds carbohydrate."""
    calories, fat, sugar, sodium, protein, sat_fat, carbs = raw
    carbohydrate_g = carbs / 100.0 * ref.carbohydrate_g
    sugars_g = sugar / 100.0 * SUGAR_DV_G
    return NutrientVector(
        energy_kcal=calories,
        fat_g=fat / 100.0 * ref.fat_g,
        saturated_fat_g=sat_fat / 100.0 * ref.saturated_fat_g,
        carbohydrate_g=carbohydrate_g,
        protein_g=protein / 100.0 * ref.protein_g,
        sodium_mg=sodium / 100.0 * ref.sodium_mg,
        sugars_g=sugars_g if sugars_g <= carbohydrate_g + _SUGAR_CARB_TOLERANCE_G else None,
    )


def implied_energy_kcal(nutrition: NutrientVector) -> float | None:
    """Energy implied by the macros; None if any macro is unknown. A consistency check only."""
    fat, carbs, protein = nutrition.fat_g, nutrition.carbohydrate_g, nutrition.protein_g
    if fat is None or carbs is None or protein is None:
        return None
    return _KCAL_PER_G_FAT * fat + _KCAL_PER_G_CARBOHYDRATE * carbs + _KCAL_PER_G_PROTEIN * protein


def energy_ratio(nutrition: NutrientVector) -> float | None:
    """Implied / stated energy. None when either side is unknown or stated energy is 0."""
    implied = implied_energy_kcal(nutrition)
    if implied is None or nutrition.energy_kcal is None or nutrition.energy_kcal <= 0:
        return None
    return implied / nutrition.energy_kcal


def scale(nutrition: NutrientVector, factor: float) -> NutrientVector:
    """Multiply every known nutrient by `factor`; unknown stays unknown."""
    if factor < 0:
        raise ValueError("scale factor must be non-negative")
    values = {name: getattr(nutrition, name) for name in NUTRIENT_FIELDS}
    return NutrientVector(**{k: None if v is None else v * factor for k, v in values.items()})


def rounded(nutrition: NutrientVector, places: int = 3) -> NutrientVector:
    """Round known values for stable, readable exports; far below nutrient precision."""
    values = {name: getattr(nutrition, name) for name in NUTRIENT_FIELDS}
    return NutrientVector(**{k: None if v is None else round(v, places) for k, v in values.items()})


def per_100g(nutrition: NutrientVector, serving_mass_g: float | None) -> NutrientVector | None:
    """Scale a serving to 100 g. Unknown serving mass gives None, never a guess."""
    if serving_mass_g is None:
        return None
    return scale(nutrition, 100.0 / serving_mass_g)
