"""Stage 4: discrete portion options with absolute nutrient vectors (ADR 0003 D2).

Two kinds of dish, two kinds of portion:

- a Food.com dish is measured in recipe SERVINGS. Its nutrition is per serving and its
  mass is unknown, so 1.5 servings = 1.5 x the serving vector and `grams` stays None;
- a USDA staple is measured in a household unit with a real mass from USDA
  food_portion.csv (1 medium roti = 40 g), so 2 roti = 80 g = 0.8 x the per-100 g vector.

Either way every option carries the nutrients of exactly that quantity, so the CSP only
adds vectors. No mass is ever estimated (ADR 0001 D3).
"""

from savora_ai.core.food_data.models import (
    CatalogueRecipe,
    NutrientVector,
    NutritionRecord,
    PortionOption,
)
from savora_ai.core.food_data.nutrition_convert import rounded, scale
from savora_ai.schemas.enums import NutritionBasis, PortionUnit

# PROVISIONAL serving multiples for a Food.com dish (ADR 0002 presets pick from these).
FOODCOM_SERVING_QUANTITIES: tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5)
FOODCOM_STANDARD_QUANTITY = 1.0


def portion_id(dish_id: str, quantity: float, unit: PortionUnit) -> str:
    return f"{dish_id}:{quantity:g}x{unit.value}"


def portion_nutrients(
    record: NutritionRecord, quantity: float, unit: PortionUnit, grams: float | None
) -> NutrientVector:
    """Nutrients of one quantity, rounded to 3 decimals; the basis decides the factor."""
    if record.basis is NutritionBasis.PER_SERVING:
        if unit is not PortionUnit.SERVING:
            raise ValueError("per-serving nutrition can only be portioned in servings")
        return rounded(scale(record.values, quantity))
    if grams is None:
        raise ValueError("per-100 g nutrition needs the portion mass in grams")
    return rounded(scale(record.values, grams / 100.0))


def _label(quantity: float, unit: PortionUnit, grams: float | None) -> str:
    word = unit.value.lower() + ("" if quantity == 1 else "s")
    return f"{quantity:g} {word}" + ("" if grams is None else f" ({grams:g} g)")


def serving_portions(recipe: CatalogueRecipe) -> tuple[PortionOption, ...]:
    """Food.com dish: serving multiples; grams only if a person verified the serving mass."""
    options: list[PortionOption] = []
    for quantity in FOODCOM_SERVING_QUANTITIES:
        grams = None if recipe.serving_mass_g is None else quantity * recipe.serving_mass_g
        options.append(
            PortionOption(
                portion_id=portion_id(recipe.recipe_id, quantity, PortionUnit.SERVING),
                quantity=quantity,
                unit=PortionUnit.SERVING,
                grams=grams,
                label=_label(quantity, PortionUnit.SERVING, grams),
                is_standard=quantity == FOODCOM_STANDARD_QUANTITY,
                nutrients=portion_nutrients(recipe.nutrition, quantity, PortionUnit.SERVING, grams),
            )
        )
    return tuple(options)


def measured_portions(
    recipe: CatalogueRecipe,
    unit: PortionUnit,
    grams_per_unit: float,
    quantities: tuple[float, ...],
    standard: float,
) -> tuple[PortionOption, ...]:
    """USDA staple: household units with a real mass per unit."""
    if grams_per_unit <= 0:
        raise ValueError("grams per unit must be positive")
    options: list[PortionOption] = []
    for quantity in quantities:
        grams = round(quantity * grams_per_unit, 3)
        options.append(
            PortionOption(
                portion_id=portion_id(recipe.recipe_id, quantity, unit),
                quantity=quantity,
                unit=unit,
                grams=grams,
                label=_label(quantity, unit, grams),
                is_standard=quantity == standard,
                nutrients=portion_nutrients(recipe.nutrition, quantity, unit, grams),
            )
        )
    return tuple(options)


def with_portions(recipe: CatalogueRecipe, portions: tuple[PortionOption, ...]) -> CatalogueRecipe:
    return CatalogueRecipe.model_validate({**recipe.model_dump(), "portions": portions})


def standard_portion(recipe: CatalogueRecipe) -> PortionOption:
    [standard] = [p for p in recipe.portions if p.is_standard]
    return standard
