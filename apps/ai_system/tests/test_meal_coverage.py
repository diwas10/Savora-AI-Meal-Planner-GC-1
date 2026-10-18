"""Stage 10: coverage counts meals per scenario; the proxy fails closed on missing tags."""

from pathlib import Path

from savora_ai.core.food_data.catalogue import build_recipe
from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.food_data.nutrition_convert import FDA_1993
from savora_ai.core.food_data.portions import serving_portions, with_portions
from savora_ai.core.food_data.usda_staples import load_extract, load_spec, staple_dishes
from savora_ai.core.meal_composition.composer import compose
from savora_ai.core.meal_composition.coverage import (
    Scenario,
    coverage_report,
    needed_distinct,
    scenario_coverage,
)
from savora_ai.core.meal_composition.models import MealCombination
from savora_ai.core.meal_composition.pairings import load_pairings
from savora_ai.core.meal_composition.templates import load_templates
from savora_ai.schemas.enums import CuisinePolicy, MealType

REPO = Path(__file__).parents[3]
STAPLES = staple_dishes(
    load_spec(REPO / "Data/curated/usda_staples.json"),
    load_extract(REPO / "Data/curated/usda_staples_extract.json"),
)


def dish(
    source_id: int, name: str, *tags: str, ingredients: tuple[str, ...] = ("x",)
) -> CatalogueRecipe:
    recipe = build_recipe(
        source_id, name, list(tags), [400.0, 20, 10, 10, 20, 10, 20], list(ingredients), FDA_1993
    )
    assert isinstance(recipe, CatalogueRecipe)
    return with_portions(recipe, serving_portions(recipe))


def catalogue() -> tuple[tuple[CatalogueRecipe, ...], tuple[MealCombination, ...]]:
    mains = [
        dish(i, f"curry {chr(97 + i)}", "main-dish", "one-dish-meal", "indian", "vegetarian")
        for i in range(1, 9)
    ]
    peanut = dish(
        20, "peanut curry", "main-dish", "one-dish-meal", "indian", ingredients=("peanuts",)
    )
    untagged = dish(21, "plain dal", "main-dish", "one-dish-meal", "indian")  # no diet tag
    dishes = (*mains, peanut, untagged, *STAPLES)
    combos = compose(
        dishes,
        load_templates(REPO / "Data/curated/meal_templates.json"),
        load_pairings(REPO / "Data/curated/pairings.json"),
        "s",
    ).combinations
    return dishes, combos


def lunch_dinner(result: dict[str, object]) -> dict[str, object]:
    value = result["lunchDinner"]
    assert isinstance(value, dict)
    return value  # type: ignore[return-value]


def test_needed_distinct_meals_follow_the_repetition_limit() -> None:
    assert needed_distinct(MealType.BREAKFAST) == 4  # 7 slots, at most 2 each
    assert needed_distinct(MealType.LUNCH) == 7  # 14 lunch + dinner slots


def test_vegetarian_proxy_fails_closed_on_a_missing_tag() -> None:
    dishes, combos = catalogue()
    scenario = Scenario("veg", CuisinePolicy.STRICT, ("Indian",), "vegetarian")
    result = scenario_coverage(scenario, combos, {d.recipe_id: d for d in dishes})
    assert lunch_dinner(result)["distinctAnchorDishes"] == 8  # untagged dal and peanut out
    assert lunch_dinner(result)["sufficient"] is True


def test_explicit_exclusion_removes_matching_ingredients() -> None:
    dishes, combos = catalogue()
    by_id = {d.recipe_id: d for d in dishes}
    everything = scenario_coverage(Scenario("all", CuisinePolicy.MIXED, ()), combos, by_id)
    no_peanut = scenario_coverage(
        Scenario("np", CuisinePolicy.MIXED, (), None, ("peanut",)), combos, by_id
    )
    assert lunch_dinner(everything)["distinctAnchorDishes"] == 10
    assert lunch_dinner(no_peanut)["distinctAnchorDishes"] == 9


def test_strict_cuisine_with_no_dishes_is_reported_short() -> None:
    dishes, combos = catalogue()
    result = scenario_coverage(
        Scenario("thai", CuisinePolicy.STRICT, ("Thai",)), combos, {d.recipe_id: d for d in dishes}
    )
    assert result["sufficient"] is False
    assert lunch_dinner(result)["combinations"] == 0


def test_report_has_static_counts_and_states_its_method() -> None:
    dishes, combos = catalogue()
    report = coverage_report(dishes, combos)
    static = report["static"]
    assert isinstance(static, dict)
    assert static["dishes"] == len(dishes) and static["combinations"] == len(combos)
    assert "not the Rule Engine" in str(report["method"])
    assert report["scenariosTotal"] == 8
