"""Excluded ingredients block only as a main ingredient; allergies block in any amount."""

import json

from savora_ai.core.explainability.explanation import RecipeExplanation
from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.pipelines.profile import (
    PlanningProfile,
    dish_allowed,
    dish_swaps,
    with_cook_without,
)


def dish(name: str, *ingredients: str, tags: tuple[str, ...] = ("vegetarian",)) -> CatalogueRecipe:
    return CatalogueRecipe.model_construct(
        recipe_id="FC_1", name=name, ingredients=ingredients, diet_tags=tags
    )


def profile(**fields: object) -> PlanningProfile:
    body = {"profileId": "u", "profileVersion": 1, **fields}
    return PlanningProfile.model_validate_json(json.dumps(body))


ONION_GARLIC = profile(excludedIngredients=["onion", "garlic"])
CURRY = ("chickpeas", "tomatoes", "red onion", "garlic cloves", "ginger", "cumin", "oil")


def test_a_minor_excluded_ingredient_is_swapped_not_filtered() -> None:
    swaps = dish_swaps(dish("chana masala", *CURRY), ONION_GARLIC)
    assert [(s.ingredient, s.instead) for s in swaps or ()] == [
        ("onion", "hing (asafoetida)"),
        ("garlic", "ginger or hing"),
    ]


def test_a_dish_that_already_fits_needs_no_swap() -> None:
    assert dish_swaps(dish("aloo gobi", "potato", "cauliflower"), ONION_GARLIC) == ()


def test_an_excluded_ingredient_without_a_curated_swap_is_left_out() -> None:
    user = profile(excludedIngredients=["raisins"])
    swaps = dish_swaps(dish("pulao", "basmati rice", "peas", "raisins", "cumin"), user)
    assert [(s.ingredient, s.instead) for s in swaps or ()] == [("raisins", "leave it out")]


def test_a_main_excluded_ingredient_still_blocks() -> None:
    mushroom = profile(excludedIngredients=["mushroom"])
    assert not dish_allowed(dish("mushroom masala", "mushrooms", "onion", "spices"), mushroom)
    assert not dish_allowed(dish("veg stir fry", "mushrooms", "carrot", "soy sauce"), mushroom)
    # In a third or more of the lines it is main, even if the first line is something else.
    assert not dish_allowed(
        dish("stew", "carrot", "button mushrooms", "shiitake mushrooms", "salt"), mushroom
    )


def test_a_structural_excluded_ingredient_still_blocks() -> None:
    user = profile(excludedIngredients=["egg"])
    assert not dish_allowed(
        dish("banana bread", "flour", "banana", "sugar", "egg", "baking soda", "salt"), user
    )


def test_allergies_are_never_relaxed_however_small_the_amount() -> None:
    peanut = profile(allergies=["peanut"])
    one_line = dish("vegetable curry", *CURRY, "peanut oil", "salt", "water", "rice")
    assert not dish_allowed(one_line, peanut)
    milk = profile(allergies=["milk"])
    assert not dish_allowed(dish("dal", "lentils", "turmeric", "salt", "ghee"), milk)  # derived


def test_diet_is_never_relaxed() -> None:
    vegan = profile(diet="VEGAN", excludedIngredients=["onion"])
    assert not dish_allowed(dish("chana", *CURRY), vegan)  # no vegan tag


def test_a_swap_that_hits_an_allergy_or_exclusion_becomes_leave_it_out() -> None:
    # Potato's swap is "sweet potato or cauliflower"; with cauliflower excluded too, the
    # swap would reintroduce it, so the advice is to leave potato out.
    user = profile(excludedIngredients=["potato", "cauliflower"])
    swaps = dish_swaps(dish("vegetable korma", *CURRY, "potato"), user)
    assert [(s.ingredient, s.instead) for s in swaps or ()] == [("potato", "leave it out")]


def test_the_explanation_says_what_to_leave_out() -> None:
    base = RecipeExplanation.model_construct(reasons=())
    out = with_cook_without(base, [dish("chana masala", *CURRY)], ONION_GARLIC)
    (reason,) = out.reasons
    assert reason.code == "COOK_WITHOUT_EXCLUDED"
    assert "no onion in chana masala: use hing (asafoetida)" in reason.message
    assert "nutrition shown still includes them" in reason.message
    assert with_cook_without(base, [dish("aloo gobi", "potato")], ONION_GARLIC) is base
