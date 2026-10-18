"""Stage 2: roles, dish class and meal types are derived from course evidence."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from savora_ai.core.food_data.catalogue import build_recipe
from savora_ai.core.food_data.classification import (
    Classification,
    ClassificationOverride,
    ClassificationOverrideFile,
    apply_override,
    classify,
    index_overrides,
    is_plannable,
    meals_for_roles,
)
from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.food_data.nutrition_convert import FDA_1993
from savora_ai.schemas.enums import ClassificationStatus, CulinaryRole, DishClass, MealType

AUTO = ClassificationStatus.AUTO
REVIEW = ClassificationStatus.REQUIRES_REVIEW
LUNCH_DINNER = (MealType.LUNCH, MealType.DINNER)


def run(name: str, *tags: str, kcal: float = 400.0) -> Classification:
    return classify(name, frozenset(tags), kcal)


# --- roles come from course tags, ingredient tags only qualify them -----------------


def test_dal_is_a_main_that_needs_an_accompaniment() -> None:
    result = run("yellow dal", "main-dish", "indian")
    assert result.roles == (CulinaryRole.MAIN_DISH,)
    assert result.dish_class is DishClass.REQUIRES_ACCOMPANIMENT
    assert result.meal_types == LUNCH_DINNER  # main-dish no longer means dinner only
    assert result.status is AUTO


@pytest.mark.parametrize(
    ("name", "tags"),
    [
        ("chicken biryani", ("main-dish",)),
        ("vegetable lasagna", ("main-dish",)),
        ("shepherds pie", ("main-dish", "one-dish-meal")),
        ("tuna melt", ("main-dish", "sandwiches")),
    ],
)
def test_self_contained_mains_are_complete_meals(name: str, tags: tuple[str, ...]) -> None:
    assert run(name, *tags).dish_class is DishClass.COMPLETE_MEAL


def test_vegetable_ingredient_tag_alone_does_not_make_a_side() -> None:
    # "vegetables" is a main-ingredient tag; a vegetable soup is not a vegetable side.
    result = run("vegetable soup", "vegetables", "soups-stews")
    assert CulinaryRole.VEGETABLE not in result.roles


def test_side_dishes_are_qualified_by_their_main_ingredient() -> None:
    assert run("jeera rice", "side-dishes", "rice").roles == (CulinaryRole.STAPLE,)
    veg = run("garlic green beans", "side-dishes", "vegetables")
    assert veg.roles == (CulinaryRole.VEGETABLE,)
    assert veg.dish_class is DishClass.COMPONENT
    assert veg.meal_types == LUNCH_DINNER


def test_pasta_salad_is_a_staple_and_green_salad_a_vegetable() -> None:
    assert run("pasta salad", "salads", "pasta").roles == (CulinaryRole.STAPLE,)
    assert run("green salad", "salads").roles == (CulinaryRole.VEGETABLE,)


def test_sweet_breads_are_not_staples() -> None:
    assert run("banana muffins", "breads").roles == ()
    assert run("chocolate loaf", "breads", "chocolate").roles == ()
    assert run("garlic naan", "breads").roles == (CulinaryRole.STAPLE,)


def test_breakfast_dish_stands_alone() -> None:
    result = run("masala omelette", "breakfast")
    assert result.roles == (CulinaryRole.BREAKFAST_BASE,)
    assert result.dish_class is DishClass.COMPLETE_MEAL
    assert result.meal_types == (MealType.BREAKFAST,)


def test_multiple_roles_union_their_meals_in_enum_order() -> None:
    result = run("frittata", "main-dish", "brunch")
    assert result.roles == (CulinaryRole.MAIN_DISH, CulinaryRole.BREAKFAST_BASE)
    assert result.meal_types == (MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER)


def test_meals_for_roles_is_ordered() -> None:
    roles = [CulinaryRole.VEGETABLE, CulinaryRole.BREAKFAST_BASE]
    assert meals_for_roles(roles) == (MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER)


# --- non-meal dishes, conflicts and weak evidence -----------------------------------


def test_desserts_are_confidently_not_planning_dishes() -> None:
    result = run("brownies", "desserts", "chocolate")
    assert result.roles == () and result.dish_class is None and result.meal_types == ()
    assert result.status is AUTO


def test_meal_course_next_to_non_meal_course_needs_review() -> None:
    result = run("mini meatballs", "main-dish", "appetizers")
    assert result.status is REVIEW
    assert result.roles == (CulinaryRole.MAIN_DISH,)  # kept as a suggestion for review
    assert "conflict: meal course and non-meal course" in result.evidence


@pytest.mark.parametrize(
    "tags", [("soups-stews",), ("lunch",), ("side-dishes",), ("easy", "indian")]
)
def test_weak_or_missing_evidence_needs_review(tags: tuple[str, ...]) -> None:
    assert run("something", *tags).status is REVIEW


def test_strong_main_is_not_weakened_by_an_unqualified_side_tag() -> None:
    assert run("coconut dhal", "main-dish", "side-dishes").status is AUTO


def test_main_with_soup_tag_is_settled() -> None:
    result = run("chicken stew", "main-dish", "soups-stews")
    assert result.status is AUTO and result.roles == (CulinaryRole.MAIN_DISH,)


def test_energy_floors_and_ceilings_depend_on_the_dish_class() -> None:
    assert run("broth", "main-dish", kcal=30).status is REVIEW  # a meal below 50 kcal
    assert run("steamed greens", "side-dishes", "vegetables", kcal=30).status is AUTO
    loaf = run("whole wheat bread", "breads", kcal=1200)  # a whole loaf, not a serving
    assert loaf.status is REVIEW


def test_classification_is_deterministic() -> None:
    tags = ("main-dish", "brunch", "side-dishes", "rice")
    assert run("x", *tags) == run("x", *reversed(tags))


def test_classification_fields_must_agree() -> None:
    with pytest.raises(ValidationError):
        Classification(
            roles=(CulinaryRole.MAIN_DISH,),
            dish_class=None,
            meal_types=LUNCH_DINNER,
            status=AUTO,
            evidence=("x",),
        )


# --- curated overrides --------------------------------------------------------------


def recipe(tags: list[str], source_id: int = 1) -> CatalogueRecipe:
    result = build_recipe(
        source_id, "dal", tags, [400.0, 20, 10, 10, 20, 10, 20], ["lentils"], FDA_1993
    )
    assert isinstance(result, CatalogueRecipe)
    return result


def make_override(**changes: object) -> ClassificationOverride:
    fields: dict[str, object] = {
        "recipe_id": "FC_1",
        "roles": (CulinaryRole.MAIN_DISH,),
        "dish_class": DishClass.REQUIRES_ACCOMPANIMENT,
        "meal_types": LUNCH_DINNER,
        "rationale": "dal is eaten with rice or roti",
        "curated_by": "tester",
    }
    return ClassificationOverride.model_validate(fields | changes)


def test_override_settles_a_review_dish_and_keeps_the_audit_trail() -> None:
    before = recipe(["soups-stews"])
    assert before.classification_status is REVIEW and not is_plannable(before)
    after = apply_override(before, make_override())
    assert after.classification_status is ClassificationStatus.CURATED
    assert is_plannable(after)
    assert after.classification_evidence[:-1] == before.classification_evidence
    assert after.classification_evidence[-1].startswith("curated by tester")


def test_cuisine_only_override_keeps_the_auto_classification() -> None:
    before = recipe(["main-dish"])
    after = apply_override(
        before, make_override(roles=None, dish_class=None, meal_types=None, cuisines=("Nepali",))
    )
    assert after.cuisines == ("Nepali",)
    assert after.roles == before.roles and after.classification_status is AUTO


def test_exclusion_override_makes_a_dish_unplannable() -> None:
    excluded = apply_override(
        recipe(["main-dish"]), make_override(roles=(), dish_class=None, meal_types=())
    )
    assert excluded.classification_status is ClassificationStatus.CURATED
    assert not is_plannable(excluded)


@pytest.mark.parametrize(
    "changes",
    [
        {"meal_types": None},  # roles without meal types
        {"roles": None, "meal_types": None},  # dish class without roles, nothing else
        {"dish_class": None},  # plannable roles without a dish class
        {"roles": (), "meal_types": ()},  # exclusion that still names a dish class
        {"roles": None, "dish_class": None, "meal_types": None},  # changes nothing
    ],
)
def test_incomplete_overrides_are_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make_override(**changes)


def test_override_for_another_recipe_or_duplicates_are_errors() -> None:
    with pytest.raises(ValueError):
        apply_override(recipe(["main-dish"], source_id=2), make_override())
    with pytest.raises(ValueError):
        index_overrides([make_override(), make_override()])


def test_committed_override_file_is_valid_and_has_no_duplicates() -> None:
    path = Path(__file__).parents[3] / "Data/curated/classification_overrides.json"
    curated = ClassificationOverrideFile.model_validate_json(path.read_text(encoding="utf-8"))
    assert index_overrides(curated.overrides)  # raises on a duplicate recipe
    assert all(o.rationale and o.curated_by for o in curated.overrides)


# --- review regressions -------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "complete"),
    [
        ("bacon wrapped chicken", False),  # 'wrap' inside 'wrapped'
        ("licorice glazed pork", False),  # 'rice' inside 'licorice'
        ("chicken wraps", True),  # plural of a whole word
        ("steamed momos", True),
        ("chicken fried rice", True),
    ],
)
def test_self_contained_name_words_match_whole_words_only(name: str, complete: bool) -> None:
    result = run(name, "main-dish")
    assert (result.dish_class is DishClass.COMPLETE_MEAL) is complete
