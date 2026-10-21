"""The deterministic grounding step keeps only what the user's words support."""

import pytest

from savora_ai.core.craving_nlu.grounding import ground

CUISINES = {"THAI": "Thai", "INDIAN": "Indian", "MIDDLE_EASTERN": "Middle Eastern"}


def body(**fields: object) -> dict[str, object]:
    base: dict[str, object] = {
        "intent": "CRAVING_RECOMMEND",
        "cuisineIds": [],
        "flavorTags": [],
        "excludedIngredientIds": [],
        "mealSlotId": None,
        "requiresClarification": False,
    }
    return base | fields


def test_unsupported_values_are_dropped() -> None:
    got = ground(
        "something thai",
        body(flavorTags=["SPICY"], excludedIngredientIds=["NOODLES"], cuisineIds=["INDIAN"]),
        CUISINES,
    )
    assert got["cuisineIds"] == ["THAI"]  # a named cuisine beats the model's guess
    assert got["flavorTags"] == [] and got["excludedIngredientIds"] == []


def test_supported_values_are_kept_and_typos_match() -> None:
    got = ground(
        "spicy thia curry, I don't want peanuts",
        body(flavorTags=["SPICY"], excludedIngredientIds=["PEANUTS"]),
        CUISINES,
    )
    assert got == body(cuisineIds=["THAI"], flavorTags=["SPICY"], excludedIngredientIds=["PEANUTS"])


def test_negated_flavor_is_not_kept() -> None:
    assert ground("not too spicy please", body(flavorTags=["SPICY"]), CUISINES)["flavorTags"] == []


@pytest.mark.parametrize(
    ("text", "slot"),
    [
        ("swap friday lunch", "D5_LUNCH"),
        ("change day 2 dinner", "D2_DINNER"),
        ("swap d7 breakfast", "D7_BREAKFAST"),
    ],
)
def test_slot_is_read_from_the_words(text: str, slot: str) -> None:
    got = ground(text, body(intent="SWAP_MEAL", mealSlotId="D1_BREAKFAST"), CUISINES)
    assert got["mealSlotId"] == slot and got["requiresClarification"] is False


def test_swap_without_slot_and_allergy_force_clarification() -> None:
    swap = ground("swap my lunch", body(intent="SWAP_MEAL", mealSlotId="D5_LUNCH"), CUISINES)
    assert swap["mealSlotId"] is None and swap["requiresClarification"] is True
    allergy = ground("I'm allergic to peanuts", body(excludedIngredientIds=["PEANUTS"]), CUISINES)
    assert allergy["requiresClarification"] is True and allergy["excludedIngredientIds"] == []


def test_non_object_answer_is_rejected() -> None:
    with pytest.raises(ValueError):
        ground("thai", [], CUISINES)  # type: ignore[arg-type]
