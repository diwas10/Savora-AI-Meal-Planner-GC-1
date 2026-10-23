"""The derived-ingredient table behind the stand-in allergy screen."""

import pytest

from savora_ai.core.pipelines.allergens import GROUPS, all_derived, block_rules
from savora_ai.core.pipelines.profile import PlanningProfile, safety_verification


def blocked(word: str, text: str) -> bool:
    return any(rule.blocks(text) for rule in block_rules((word,)))


@pytest.mark.parametrize(
    ("allergy", "ingredient"),
    [
        ("milk", "ghee"),
        ("milk", "paneer cheese"),
        ("dairy", "unsalted butter"),
        ("Milk", "natural yoghurt"),
        ("egg", "low-fat mayonnaise"),
        ("wheat", "dark soy sauce"),
        ("wheat", "panko breadcrumbs"),
        ("gluten", "pearl barley"),
        ("soy", "firm tofu"),
        ("tree nut", "pesto sauce"),
        ("tree nuts", "shelled pistachios"),
        ("peanut", "satay ayam"),
        ("fish", "worcestershire sauce"),
        ("shellfish", "thai red curry paste"),
        ("shellfish", "dried shrimp paste"),
        ("seafood", "tuna steaks"),
        ("sesame", "tahini"),
        ("sesame", "za'atar spice mix"),
    ],
)
def test_derived_ingredient_is_blocked(allergy: str, ingredient: str) -> None:
    assert blocked(allergy, ingredient)


@pytest.mark.parametrize(
    ("allergy", "ingredient"),
    [
        ("milk", "canned unsweetened coconut milk"),
        ("milk", "chunky peanut butter"),
        ("milk", "butter lettuce"),
        ("egg", "japanese eggplants"),
        ("wheat", "rice flour"),
        ("wheat", "bean thread noodles"),
        ("wheat", "corn tortillas"),
        ("tree nut", "ground nutmeg"),
        ("tree nut", "butternut squash"),
        ("tree nut", "water chestnuts"),
        ("sesame", "olive oil"),
    ],
)
def test_names_without_the_allergen_are_kept(allergy: str, ingredient: str) -> None:
    assert not blocked(allergy, ingredient)


def test_exemptions_do_not_hide_a_second_mention() -> None:
    assert blocked("milk", "coconut milk and whole milk")  # "whole" + "milk" survive
    assert blocked("gluten", "barley flour")  # wheat-free, not gluten-free
    assert blocked("wheat", "barley flour")  # fail closed: flour is not named rice/corn


def test_unknown_words_still_match_themselves() -> None:
    assert blocked("mushroom", "button mushrooms")
    assert not blocked("mushroom", "dried porcini")
    assert not all_derived(("mushroom",))
    assert all_derived(("milk", "tree nut"))


def test_every_group_name_resolves_to_its_group() -> None:
    for group in GROUPS:
        for name in group.names:
            assert block_rules((name,))[0].derived, name


def test_safety_label_says_which_check_ran() -> None:
    def label(*allergies: str) -> str:
        user = PlanningProfile(profile_id="p", profile_version=1, allergies=allergies)
        return safety_verification(user).allergens_checked_by

    assert label() == "NOT_APPLICABLE"
    assert label("milk", "peanut") == "DERIVED_TERM_MAP"
    assert label("milk", "lupin") == "INGREDIENT_NAME_MATCH"
