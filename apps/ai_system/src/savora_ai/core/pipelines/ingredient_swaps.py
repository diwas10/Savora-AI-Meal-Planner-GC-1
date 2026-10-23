"""Cook-it-without: EXCLUDED ingredients (preferences) that are a minor part of a dish.

    exclusion_swaps(dish, excluded, allergies) -> tuple[IngredientSwap, ...] | None

A user who excludes onion and garlic loses most Indian and Nepali dishes, yet those dishes
are routinely cooked without them. So an excluded ingredient blocks a dish only when it is
a MAIN ingredient; when it is minor, the dish stays and says what to do instead
(a curated swap such as onion -> hing, else "leave it out").

The catalogue has no ingredient amounts (Food.com lists names only), so "main" is judged
from what is there. An excluded word is MAIN when it appears:
- in the dish name ("mushroom risotto", "onion bhaji"), or
- in the first ingredient line, which on Food.com is usually the base of the dish, or
- in a third or more of the ingredient lines.
A STRUCTURAL ingredient (flour, egg, rice, milk, tofu, ...) always blocks: leaving it out
breaks the recipe however few lines it takes.

ALLERGIES ARE NEVER RELAXED. Allergens block in any amount, with the derived-allergen
table (`allergens.py`), because a trace can cause a reaction; nor is a swap allowed whose
own words hit an allergy or another exclusion (no "use paneer" for a milk allergy).

Nutrition shown for the dish still includes the omitted ingredient (minor by definition);
the explanation says so. Curation: `ai-review:claude`, conventional home-cooking swaps.
"""

from collections.abc import Sequence

from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.pipelines.allergens import block_rules
from savora_ai.core.recommendation.seeds import IngredientSwap

SWAPS_VERSION = "ingredient-swaps.v2"
MAIN_SHARE = 1 / 3  # an excluded word in this share of ingredient lines is a main one
LEAVE_OUT = "leave it out"

# excluded word -> what to cook with instead (plain words, checked against allergies)
INGREDIENT_SWAPS: dict[str, str] = {
    "onion": "hing (asafoetida)",
    "red onion": "hing (asafoetida)",
    "shallot": "hing (asafoetida)",
    "scallion": "chives",
    "green onion": "chives",
    "spring onion": "chives",
    "leek": "celery",
    "garlic": "ginger or hing",
    "mushroom": "potato or more vegetables",
    "cilantro": "parsley or mint",
    "coriander leaves": "parsley or mint",
    "chili": "sweet paprika",
    "green chili": "black pepper",
    "tomato": "tamarind or lemon",
    "eggplant": "zucchini",
    "bell pepper": "zucchini or carrot",
    "cabbage": "spinach or carrot",
    "potato": "sweet potato or cauliflower",
}

# Excluded words that hold a recipe together: never "left out".
# fmt: off
STRUCTURAL: frozenset[str] = frozenset({
    "flour", "wheat", "egg", "eggs", "milk", "butter", "cream", "cheese", "yogurt",
    "rice", "pasta", "noodle", "noodles", "bread", "dough", "tofu", "lentil", "lentils",
    "chickpea", "chickpeas", "bean", "beans", "oat", "oats", "corn", "cornmeal",
    "semolina", "gelatin", "meat", "chicken", "beef", "pork", "fish",
})
# fmt: on


def exclusion_swaps(
    dish: CatalogueRecipe, excluded: Sequence[str], allergies: Sequence[str]
) -> tuple[IngredientSwap, ...] | None:
    """How to cook `dish` without the user's excluded ingredients, or None if it cannot be.

    Empty tuple: nothing excluded is in the dish. Allergies are only used to vet swaps;
    the caller blocks allergens separately and strictly."""
    lines = dish.ingredients
    swaps: list[IngredientSwap] = []
    for rule in block_rules(tuple(excluded)):
        hits = [line for line in lines if rule.blocks(line)]
        in_name = rule.blocks(dish.name)
        if not hits and not in_name:
            continue
        word = rule.word.strip().lower()
        main = (
            in_name
            or (bool(lines) and rule.blocks(lines[0]))
            or len(hits) >= max(1, len(lines)) * MAIN_SHARE
        )
        if main or word in STRUCTURAL or rule.derived:
            return None
        instead = INGREDIENT_SWAPS.get(word, LEAVE_OUT)
        guard = block_rules((*excluded, *allergies))
        if instead != LEAVE_OUT and any(r.blocks(instead) for r in guard):
            instead = LEAVE_OUT
        swaps.append(IngredientSwap(ingredient=rule.word, instead=instead))
    return tuple(swaps)
