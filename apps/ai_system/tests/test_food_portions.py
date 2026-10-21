"""Stage 4: discrete portions carry absolute nutrients; no mass is ever invented."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from savora_ai.core.food_data.catalogue import apply_serving_masses, build_recipe
from savora_ai.core.food_data.models import CatalogueRecipe, ServingMassOverride
from savora_ai.core.food_data.nutrition_convert import FDA_1993
from savora_ai.core.food_data.portions import (
    FOODCOM_SERVING_QUANTITIES,
    portion_nutrients,
    serving_portions,
    standard_portion,
    with_portions,
)
from savora_ai.core.food_data.usda_staples import load_extract, load_spec, staple_dishes
from savora_ai.schemas.enums import PortionUnit

REPO = Path(__file__).parents[3]


def dal() -> CatalogueRecipe:
    result = build_recipe(
        7, "dal", ["main-dish", "indian"], [400.0, 20, 10, 10, 20, 10, 20], ["lentils"], FDA_1993
    )
    assert isinstance(result, CatalogueRecipe)
    return result


def staples() -> dict[str, CatalogueRecipe]:
    spec = load_spec(REPO / "Data/curated/usda_staples.json")
    data = load_extract(REPO / "Data/curated/usda_staples_extract.json")
    return {d.name: d for d in staple_dishes(spec, data)}


def test_foodcom_portions_are_serving_multiples_without_invented_grams() -> None:
    portions = serving_portions(dal())
    assert tuple(p.quantity for p in portions) == FOODCOM_SERVING_QUANTITIES
    assert all(p.unit is PortionUnit.SERVING and p.grams is None for p in portions)
    one_and_half = portions[-1]
    assert one_and_half.portion_id == "FC_7:1.5xSERVING"
    assert one_and_half.nutrients.energy_kcal == pytest.approx(600.0)  # 1.5 x 400 kcal
    assert one_and_half.nutrients.sugars_g == pytest.approx(3.75)  # 1.5 x 10% of 25 g
    assert standard_portion(with_portions(dal(), portions)).quantity == 1.0


def test_verified_serving_mass_gives_grams() -> None:
    weighed = ServingMassOverride(recipe_id="FC_7", serving_mass_g=250.0, source="weighed")
    [recipe] = apply_serving_masses([dal()], [weighed])
    assert serving_portions(recipe)[0].grams == pytest.approx(125.0)  # 0.5 x 250 g


def test_staple_portions_use_real_usda_masses() -> None:
    roti = staples()["roti (chapati)"]
    two = next(p for p in roti.portions if p.quantity == 2.0)
    assert two.unit is PortionUnit.PIECE and two.grams == pytest.approx(80.0)  # 2 x 40 g
    per_100 = roti.nutrition.values.energy_kcal
    assert per_100 is not None
    assert two.nutrients.energy_kcal == pytest.approx(per_100 * 0.8)
    assert two.is_standard and two.label == "2 pieces (80 g)"


def test_sr_legacy_half_cup_portion_scales_to_cups() -> None:
    broccoli = staples()["steamed broccoli"]  # USDA row is "0.5 cup, chopped" = 78 g
    one_cup = next(p for p in broccoli.portions if p.quantity == 1.0)
    assert one_cup.grams == pytest.approx(156.0)


def test_every_catalogue_staple_has_one_standard_portion() -> None:
    for dish in staples().values():
        assert len(dish.portions) >= 2
        assert sum(p.is_standard for p in dish.portions) == 1


def test_per_serving_nutrition_cannot_be_portioned_in_grams() -> None:
    with pytest.raises(ValueError):
        portion_nutrients(dal().nutrition, 100.0, PortionUnit.GRAM, 100.0)


def test_per_100_g_nutrition_needs_grams() -> None:
    rice = staples()["steamed white rice"]
    with pytest.raises(ValueError):
        portion_nutrients(rice.nutrition, 1.0, PortionUnit.CUP, None)


def test_portions_must_be_ordered_unique_and_have_one_standard() -> None:
    portions = serving_portions(dal())
    with pytest.raises(ValidationError):
        with_portions(dal(), tuple(reversed(portions)))
    no_standard = tuple(
        p.model_copy(update={"is_standard": False}) for p in portions
    )  # model_copy skips validation; the recipe validator must still catch it
    with pytest.raises(ValidationError):
        with_portions(dal(), no_standard)
