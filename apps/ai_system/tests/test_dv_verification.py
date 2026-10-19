"""The %DV verification method itself is tested, so its evidence can be trusted."""

import pytest

from savora_ai.core.food_data.dv_verification import (
    FOODS,
    compare_food,
    per_100_kcal_foodcom,
    reference_amounts,
    single_ingredient_recipes,
)
from savora_ai.core.food_data.nutrition_convert import FDA_1993

# A fictional food per 100 g: 400 kcal, 20 g fat, 8 g sat fat, 50 g carbs, 10 g protein,
# 480 mg sodium, 25 g sugar. Encode one 200 kcal serving as Food.com %DV (1993 table).
USDA = {"energy_kcal": 400.0, "fat_g": 20.0, "saturated_fat_g": 8.0, "carbohydrate_g": 50.0,
        "protein_g": 10.0, "sodium_mg": 480.0, "sugars_g": 25.0}  # fmt: skip
HALF = 0.5  # 200 kcal = 50 g of the food
NUTRITION = [
    200.0,
    USDA["fat_g"] * HALF / 65 * 100,
    USDA["sugars_g"] * HALF / 25 * 100,
    USDA["sodium_mg"] * HALF / 2400 * 100,
    USDA["protein_g"] * HALF / 50 * 100,
    USDA["saturated_fat_g"] * HALF / 20 * 100,
    USDA["carbohydrate_g"] * HALF / 300 * 100,
]


def test_the_right_table_gives_ratio_one_and_the_wrong_one_does_not() -> None:
    result = compare_food([("FC_1", NUTRITION)], USDA)
    ratios = result["foodcomToUsdaRatio"]
    assert isinstance(ratios, dict)
    assert ratios["fat_g"]["FDA_1993"]["medianRatio"] == pytest.approx(1.0, abs=0.001)
    assert ratios["fat_g"]["FDA_2016"]["medianRatio"] == pytest.approx(78 / 65, abs=0.001)
    assert ratios["sodium_mg"]["FDA_2016"]["medianRatio"] == pytest.approx(2300 / 2400, abs=0.001)
    assert ratios["sugars_g"]["sugar_dv_25g"]["medianRatio"] == pytest.approx(1.0, abs=0.001)
    assert ratios["sugars_g"]["sugar_dv_50g"]["medianRatio"] == pytest.approx(2.0, abs=0.001)


def test_small_percent_dv_is_skipped_because_rounding_dominates() -> None:
    reference = reference_amounts(FDA_1993, 25.0)
    assert per_100_kcal_foodcom([100.0, 4, 0, 0, 0, 0, 0], "fat_g", reference) is None
    assert per_100_kcal_foodcom([100.0, 5, 0, 0, 0, 0, 0], "fat_g", reference) == pytest.approx(
        3.25
    )


def test_nutrients_the_food_barely_contains_are_not_compared() -> None:
    almonds_like = USDA | {"sodium_mg": 1.0}  # 0.25 mg per 100 kcal: salt would dominate
    ratios = compare_food([("FC_1", NUTRITION)], almonds_like)["foodcomToUsdaRatio"]
    assert isinstance(ratios, dict) and "sodium_mg" not in ratios


def test_only_true_single_ingredient_recipes_are_used() -> None:
    rows = [
        {"id": "1", "ingredients": "['eggs', 'water']", "nutrition": str(NUTRITION)},
        {"id": "2", "ingredients": "['eggs', 'salt']", "nutrition": str(NUTRITION)},  # 2 foods
        {"id": "3", "ingredients": "['bacon']", "nutrition": str(NUTRITION)},
        {"id": "4", "ingredients": "not a list", "nutrition": str(NUTRITION)},
    ]
    found = single_ingredient_recipes(rows)
    assert [r for r, _ in found["eggs"]] == ["FC_1"] and [r for r, _ in found["bacon"]] == ["FC_3"]


def test_verification_foods_are_distinct_usda_identities() -> None:
    assert len({f.fdc_id for f in FOODS}) == len(FOODS)
    names = [i for f in FOODS for i in f.ingredients]
    assert len(names) == len(set(names))
