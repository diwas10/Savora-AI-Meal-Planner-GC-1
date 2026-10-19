"""Stage 8: curated portion presets from per-slot rules (ADR 0002 D2).

Scaling every component by one factor cannot trade rice for dal, which a high-protein,
lower-carbohydrate user needs. So each preset says, per template slot, how many STEPS to
move from the dish's standard portion along its own discrete options:

    Food.com servings 0.5 | 0.75 | [1.0] | 1.25 | 1.5      roti pieces 1 | [2] | 3 | 4

+1 on a main = 1.25 servings; -1 on roti = 1 piece. Steps clamp to the ends, so -9 means
"smallest". The CSP then picks among about 4 configurations per meal instead of the
5 x 4 x 3 = 60 free products, which keeps the search bounded. Values are PROVISIONAL.
"""

from collections.abc import Mapping

from savora_ai.core.food_data.models import CatalogueRecipe, PortionOption
from savora_ai.schemas.enums import PortionPreset

SMALLEST = -9  # clamps to the first option

PRESET_STEPS: dict[PortionPreset, dict[str, int]] = {
    PortionPreset.STANDARD: {
        "COMPLETE": 0, "MAIN": 0, "STAPLE": 0, "VEGETABLE": 0,
        "BASE": 0, "FRUIT": 0, "PROTEIN": 0,
    },
    # More of the protein-bearing main, less staple.
    PortionPreset.HIGHER_PROTEIN: {
        "COMPLETE": 1, "MAIN": 2, "STAPLE": -1, "VEGETABLE": 0,
        "BASE": 1, "FRUIT": -1, "PROTEIN": 1,
    },
    # Smallest staple and fruit, more vegetables; the main grows a little to hold energy.
    PortionPreset.LOWER_CARB: {
        "COMPLETE": -1, "MAIN": 1, "STAPLE": SMALLEST, "VEGETABLE": 1,
        "BASE": -1, "FRUIT": SMALLEST, "PROTEIN": 0,
    },
    PortionPreset.HIGHER_ENERGY: {
        "COMPLETE": 2, "MAIN": 1, "STAPLE": 1, "VEGETABLE": 0,
        "BASE": 2, "FRUIT": 1, "PROTEIN": 1,
    },
    PortionPreset.LOWER_ENERGY: {
        "COMPLETE": -1, "MAIN": -1, "STAPLE": -1, "VEGETABLE": 1,
        "BASE": -1, "FRUIT": -1, "PROTEIN": 0,
    },
}  # fmt: skip


# Slot names a template may use; templates.py rejects any other name at load time.
PRESET_SLOTS: frozenset[str] = frozenset(PRESET_STEPS[PortionPreset.STANDARD])
if any(set(steps) != PRESET_SLOTS for steps in PRESET_STEPS.values()):
    raise RuntimeError("every preset must give a step for every slot")


def step_portion(dish: CatalogueRecipe, steps: int) -> PortionOption:
    """Move `steps` options away from the standard portion, clamped to the ends."""
    if not dish.portions:
        raise ValueError(f"{dish.recipe_id} has no portions")
    standard = next(i for i, p in enumerate(dish.portions) if p.is_standard)
    index = min(max(standard + steps, 0), len(dish.portions) - 1)
    return dish.portions[index]


def preset_portions(
    slots: tuple[str, ...], dishes: tuple[CatalogueRecipe, ...]
) -> Mapping[PortionPreset, tuple[PortionOption, ...]]:
    """One portion tuple per preset; presets that give an identical tuple are dropped,
    keeping the first in enum order (STANDARD always survives)."""
    seen: set[tuple[str, ...]] = set()
    result: dict[PortionPreset, tuple[PortionOption, ...]] = {}
    for preset in PortionPreset:
        steps = PRESET_STEPS[preset]
        options = tuple(
            step_portion(dish, steps[slot]) for slot, dish in zip(slots, dishes, strict=True)
        )
        key = tuple(o.portion_id for o in options)
        if key not in seen:
            seen.add(key)
            result[preset] = options
    return result
