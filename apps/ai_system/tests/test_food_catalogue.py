"""Tests for nutrition conversion, catalogue building and the deterministic selection."""

import csv
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from savora_ai.core.food_data.build_catalogue import build
from savora_ai.core.food_data.catalogue import (
    apply_serving_masses,
    build_recipe,
    meal_types_for,
    parse_string_list,
    select_catalogue,
)
from savora_ai.core.food_data.models import CatalogueRecipe, ServingMassOverride
from savora_ai.core.food_data.nutrition_convert import (
    FDA_1993,
    energy_ratio,
    parse_nutrition,
    per_100g,
    to_serving_nutrition,
)
from savora_ai.schemas.enums import MealType, RejectionReason

# [kcal, fat%, sugar%, sodium%, protein%, sat fat%, carbs%] -> 13 g fat, 60 g carbs, 10 g protein
GOOD_NUTRITION = [400.0, 20.0, 10.0, 10.0, 20.0, 10.0, 20.0]
GOOD_TAGS = ["main-dish", "indian", "vegetarian"]
GOOD_INGREDIENTS = ["lentils", "rice"]


def make(
    source_id: int = 1,
    *,
    name: str = "dal",
    tags: object = GOOD_TAGS,
    nutrition: object = GOOD_NUTRITION,
    ingredients: object = GOOD_INGREDIENTS,
) -> CatalogueRecipe | RejectionReason:
    return build_recipe(source_id, name, tags, nutrition, ingredients, FDA_1993)


def make_ok(source_id: int = 1, **kwargs: object) -> CatalogueRecipe:
    result = make(source_id, **kwargs)  # type: ignore[arg-type]
    assert isinstance(result, CatalogueRecipe)
    return result


# --- parsing and conversion ---------------------------------------------------------


def test_parse_nutrition_accepts_text_and_lists() -> None:
    assert parse_nutrition("[51.5, 0.0, 13.0, 0.0, 2.0, 0.0, 4.0]")[0] == 51.5
    assert parse_nutrition([1, 2, 3, 4, 5, 6, 7])[6] == 7.0


@pytest.mark.parametrize(
    "bad", ["[1, 2]", "not a list", [1, 2, 3, 4, 5, 6, -1], [True] * 7, [1, 2, 3, 4, 5, 6, "x"]]
)
def test_parse_nutrition_rejects_bad_vectors(bad: object) -> None:
    with pytest.raises(ValueError):
        parse_nutrition(bad)


def test_percent_dv_converts_with_reference() -> None:
    n = to_serving_nutrition(parse_nutrition(GOOD_NUTRITION), FDA_1993)
    assert n.fat_g == pytest.approx(13.0)  # 20% of 65 g
    assert n.saturated_fat_g == pytest.approx(2.0)  # 10% of 20 g
    assert n.carbohydrate_g == pytest.approx(60.0)  # 20% of 300 g
    assert n.protein_g == pytest.approx(10.0)  # 20% of 50 g
    assert n.sodium_mg == pytest.approx(240.0)  # 10% of 2400 mg
    assert n.sugars_g is None  # unknown, never converted or zero


def test_energy_ratio_matches_atwater() -> None:
    n = to_serving_nutrition(parse_nutrition(GOOD_NUTRITION), FDA_1993)
    assert energy_ratio(n) == pytest.approx((9 * 13 + 4 * 60 + 4 * 10) / 400)


def test_per_100g_needs_a_verified_mass() -> None:
    n = to_serving_nutrition(parse_nutrition(GOOD_NUTRITION), FDA_1993)
    assert per_100g(n, None) is None
    half = per_100g(n, 200.0)
    assert half is not None and half.energy_kcal == pytest.approx(200.0)
    assert half.sugars_g is None


def test_parse_string_list() -> None:
    assert parse_string_list("['a', ' b ']") == ("a", "b")
    with pytest.raises(ValueError):
        parse_string_list("[1, 2]")


# --- row validation -----------------------------------------------------------------


def test_good_row_becomes_catalogue_entry() -> None:
    recipe = make_ok(137739)
    assert recipe.recipe_id == "FC_137739"
    assert recipe.cuisines == ("Indian",)
    assert recipe.diet_tags == ("vegetarian",)
    assert recipe.meal_types == (MealType.DINNER,)  # dinner comes from main-dish
    assert recipe.serving_mass_g is None and recipe.serving_mass_source is None


def test_meal_types_are_ordered_and_multi_valued() -> None:
    both = meal_types_for(frozenset({"lunch", "breakfast", "main-dish"}))
    assert both == (MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER)


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"nutrition": "oops"}, RejectionReason.MALFORMED_NUTRITION),
        ({"tags": "oops"}, RejectionReason.MALFORMED_METADATA),
        ({"ingredients": []}, RejectionReason.MALFORMED_METADATA),
        ({"name": "  "}, RejectionReason.MALFORMED_METADATA),
        ({"nutrition": [10.0, 1, 1, 1, 1, 1, 1]}, RejectionReason.NUTRITION_OUT_OF_RANGE),
        ({"nutrition": [5000.0, 20, 10, 10, 20, 10, 20]}, RejectionReason.NUTRITION_OUT_OF_RANGE),
        ({"nutrition": [400.0, 20, 10, 10, 20, 10, 9999]}, RejectionReason.NUTRITION_OUT_OF_RANGE),
        ({"nutrition": [900.0, 20, 10, 10, 20, 10, 20]}, RejectionReason.ENERGY_INCONSISTENT),
        ({"tags": ["dessert", "indian"]}, RejectionReason.NO_MEAL_TYPE),
    ],
)
def test_rejections_name_their_reason(kwargs: dict[str, object], reason: RejectionReason) -> None:
    assert make(**kwargs) is reason  # type: ignore[arg-type]


def test_non_positive_source_id_is_rejected() -> None:
    assert make(0) is RejectionReason.MALFORMED_METADATA


# --- selection ----------------------------------------------------------------------


def pool(n: int) -> list[CatalogueRecipe]:
    return [make_ok(i, tags=["main-dish", "breakfast"]) for i in range(1, n + 1)]


def test_selection_is_deterministic_and_seed_sensitive() -> None:
    quotas = {MealType.BREAKFAST: 3, MealType.LUNCH: 0, MealType.DINNER: 2}
    a = select_catalogue(pool(30), quotas, "seed-a")
    assert a == select_catalogue(list(reversed(pool(30))), quotas, "seed-a")
    assert a != select_catalogue(pool(30), quotas, "seed-b")


def test_selection_respects_quotas_and_counts_each_recipe_once() -> None:
    quotas = {MealType.BREAKFAST: 3, MealType.LUNCH: 0, MealType.DINNER: 2}
    chosen = select_catalogue(pool(30), quotas, "s")
    assert len({r.recipe_id for r in chosen}) == len(chosen)
    assert sum(MealType.BREAKFAST in r.meal_types for r in chosen) >= 3
    assert len(chosen) == 3  # the 2 dinner slots are filled by already-chosen dishes


def test_cuisine_labelled_recipes_are_preferred() -> None:
    labelled = make_ok(1, tags=["main-dish", "thai"])
    plain = [make_ok(i, tags=["main-dish"]) for i in range(2, 20)]
    chosen = select_catalogue([*plain, labelled], {MealType.DINNER: 1}, "s")
    assert chosen == (labelled,)


# --- serving mass overrides ---------------------------------------------------------


def test_override_sets_mass_and_source() -> None:
    recipe = make_ok(1)
    [updated] = apply_serving_masses(
        [recipe], [ServingMassOverride(recipe_id="FC_1", serving_mass_g=250.0, source="weighed")]
    )
    assert updated.serving_mass_g == 250.0 and updated.serving_mass_source == "weighed"


def test_unknown_override_id_is_an_error() -> None:
    override = ServingMassOverride(recipe_id="FC_99", serving_mass_g=100.0, source="weighed")
    with pytest.raises(ValueError):
        apply_serving_masses([make_ok(1)], [override])


def test_mass_without_source_is_rejected() -> None:
    data = make_ok(1).model_dump() | {"serving_mass_g": 100.0}
    with pytest.raises(ValidationError):
        CatalogueRecipe.model_validate(data)


# --- end to end ---------------------------------------------------------------------


def write_source(path: Path) -> None:
    fields = ["name", "id", "tags", "nutrition", "ingredients"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for i in range(1, 6):
            writer.writerow(
                {
                    "name": f"dish {i}",
                    "id": str(i),
                    "tags": str(GOOD_TAGS),
                    "nutrition": str(GOOD_NUTRITION),
                    "ingredients": str(GOOD_INGREDIENTS),
                }
            )
        writer.writerow(
            {"name": "bad", "id": "9", "tags": "[]", "nutrition": "oops", "ingredients": "[]"}
        )


def test_build_reports_and_is_reproducible(tmp_path: Path) -> None:
    source = tmp_path / "RAW_recipes.csv"
    write_source(source)
    first = build(source, seed="s", dv_name=FDA_1993.name, overrides_path=None)
    assert first == build(source, seed="s", dv_name=FDA_1993.name, overrides_path=None)
    report = first["report"]
    assert isinstance(report, dict)
    assert report["rawRecipes"] == 6
    assert report["eligibleCandidates"] == 5
    assert report["rejections"] == {"MALFORMED_NUTRITION": 1}
    assert json.dumps(first)  # fully JSON serializable
