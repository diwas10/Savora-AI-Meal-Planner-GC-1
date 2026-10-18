"""Stage 10: static and scenario coverage of the catalogue (ADR 0001 D7).

Static coverage counts what the catalogue holds. Scenario coverage asks the question
that matters: for a representative profile, are there ENOUGH distinct meals to fill a
week? A dish may repeat at most twice a week, so 7 breakfasts need at least 4 distinct
breakfast meals and 14 lunches + dinners at least 7 distinct main meals.

IMPORTANT: the scenario filter is a PROXY, not the Rule Engine. It reads Food.com diet
tags (unverified metadata) and matches excluded ingredients by word. It tells Member 1
where the catalogue is thin; it does not decide eligibility. The authoritative check is
Member 2's filter_candidates and solve_week on the same scenarios, once real rules exist.
All profiles are synthetic and have no clinical meaning.
"""

import math
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.meal_composition.models import MealCombination
from savora_ai.schemas.enums import CuisinePolicy, MealType

MAX_REPEATS_PER_WEEK = 2  # PROVISIONAL weekly repetition limit per meal
SLOTS_PER_WEEK: dict[MealType, int] = {
    MealType.BREAKFAST: 7,
    MealType.LUNCH: 14,  # lunch and dinner draw on the same main meals
}


def needed_distinct(meal: MealType) -> int:
    return math.ceil(SLOTS_PER_WEEK[meal] / MAX_REPEATS_PER_WEEK)


@dataclass(frozen=True)
class Scenario:
    """A synthetic profile. Exclusions are explicit user choices, never inferred."""

    name: str
    policy: CuisinePolicy
    cuisines: tuple[str, ...]  # STRICT: allowed cuisines; MIXED: ignored
    diet: str | None = None  # "vegetarian" | "vegan" | None
    excluded_ingredients: tuple[str, ...] = ()


SCENARIOS: tuple[Scenario, ...] = (
    Scenario("mixed, no restriction", CuisinePolicy.MIXED, ()),
    Scenario("Indian vegetarian, strict", CuisinePolicy.STRICT, ("Indian",), "vegetarian"),
    Scenario("Nepali, strict", CuisinePolicy.STRICT, ("Nepali",)),
    Scenario("Indian or Nepali, explicit beef exclusion", CuisinePolicy.STRICT,
             ("Indian", "Nepali"), None, ("beef",)),
    Scenario("Thai, strict, peanut excluded", CuisinePolicy.STRICT, ("Thai",), None, ("peanut",)),
    Scenario("Chinese, strict, pork excluded", CuisinePolicy.STRICT, ("Chinese",), None, ("pork",)),
    Scenario("Mexican vegetarian, strict", CuisinePolicy.STRICT, ("Mexican",), "vegetarian"),
    Scenario("vegan, mixed", CuisinePolicy.MIXED, (), "vegan"),
)  # fmt: skip


def _proxy_allows(
    combo: MealCombination, dishes: Mapping[str, CatalogueRecipe], scenario: Scenario
) -> bool:
    if scenario.policy is CuisinePolicy.STRICT and not set(combo.cuisines) & set(scenario.cuisines):
        return False
    parts = [dishes[c.dish_id] for c in combo.components]
    if scenario.diet is not None and any(scenario.diet not in d.diet_tags for d in parts):
        return False  # unverified tag proxy: missing tag counts as NOT allowed (fail closed)
    return not any(
        word in ingredient.lower()
        for d in parts
        for ingredient in d.ingredients
        for word in scenario.excluded_ingredients
    )


def scenario_coverage(
    scenario: Scenario,
    combinations: Iterable[MealCombination],
    dishes: Mapping[str, CatalogueRecipe],
) -> dict[str, object]:
    allowed = [c for c in combinations if _proxy_allows(c, dishes, scenario)]
    result: dict[str, object] = {
        "scenario": scenario.name,
        "policy": scenario.policy.value,
        "cuisines": list(scenario.cuisines),
        "diet": scenario.diet,
        "excludedIngredients": list(scenario.excluded_ingredients),
    }
    sufficient = True
    for meal in SLOTS_PER_WEEK:
        meal_combos = [c for c in allowed if meal in c.meal_types]
        # Repetition is limited per anchor dish, so count distinct anchors too.
        anchors = {c.components[0].dish_id for c in meal_combos}
        need = needed_distinct(meal)
        key = "breakfast" if meal is MealType.BREAKFAST else "lunchDinner"
        result[key] = {
            "combinations": len(meal_combos),
            "distinctAnchorDishes": len(anchors),
            "needed": need,
            "sufficient": len(anchors) >= need,
        }
        sufficient = sufficient and len(anchors) >= need
    result["sufficient"] = sufficient
    return result


def static_coverage(
    dishes: Iterable[CatalogueRecipe], combinations: Iterable[MealCombination]
) -> dict[str, object]:
    items = list(dishes)
    combos = list(combinations)

    def count(values: Iterable[str]) -> dict[str, int]:
        return dict(sorted(Counter(values).items()))

    return {
        "dishes": len(items),
        "dishesByCuisine": count(c for d in items for c in d.cuisines or ("(neutral)",)),
        "dishesByMealType": count(m.value for d in items for m in d.meal_types),
        "dishesByRole": count(r.value for d in items for r in d.roles),
        "dishesByDishClass": count(str(d.dish_class) for d in items),
        "dishesByNutritionSource": count(d.nutrition.source.value for d in items),
        "vegetarianTaggedDishes": sum("vegetarian" in d.diet_tags for d in items),
        "combinations": len(combos),
        "combinationsByMealAndCuisine": count(
            f"{m.value}/{c}" for combo in combos for m in combo.meal_types for c in combo.cuisines
        ),
    }


def coverage_report(
    dishes: Iterable[CatalogueRecipe],
    combinations: Iterable[MealCombination],
    scenarios: Iterable[Scenario] = SCENARIOS,
) -> dict[str, object]:
    items = list(dishes)
    combos = list(combinations)
    by_id = {d.recipe_id: d for d in items}
    scenario_results = [scenario_coverage(s, combos, by_id) for s in scenarios]
    return {
        "static": static_coverage(items, combos),
        "scenarios": scenario_results,
        "scenariosSufficient": sum(bool(r["sufficient"]) for r in scenario_results),
        "scenariosTotal": len(scenario_results),
        "method": "proxy filter on unverified diet tags and ingredient words; "
        "not the Rule Engine (Member 2 owns eligibility)",
        "repetition": {"maxRepeatsPerWeek": MAX_REPEATS_PER_WEEK},
    }
