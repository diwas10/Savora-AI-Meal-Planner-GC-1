"""Onboarding seed dishes (ADR 0005): cold-start suggestions and pick validation."""

import json
from pathlib import Path

import pytest

from savora_ai.core.food_data.catalogue import build_recipe
from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.food_data.nutrition_convert import FDA_1993
from savora_ai.core.recommendation.seeds import (
    MAX_SEED_PICKS,
    is_seed_eligible,
    suggest_seed_dishes,
    validate_seed_picks,
)
from savora_ai.schemas.enums import CulinaryRole

REPO = Path(__file__).parents[3]
CATALOGUE = sorted((REPO / "Data/catalogue").glob("*_catalogue.json"))[-1]  # latest export


def dish(source_id: int, cuisine: str, count: int | None, *tags: str) -> CatalogueRecipe:
    recipe = build_recipe(
        source_id,
        f"{cuisine} dish {source_id}",
        ["main-dish", cuisine.lower(), *tags],
        [400.0, 20, 10, 10, 20, 10, 20],
        ["x"],
        FDA_1993,
    )
    assert isinstance(recipe, CatalogueRecipe)
    return recipe.model_copy(update={"training_interactions": count})


INDIAN = [dish(i, "Indian", 100 - i) for i in range(1, 6)]  # most popular cuisine
THAI = [dish(i, "Thai", 50 - i) for i in range(11, 14)]
MEXICAN = [dish(i, "Mexican", 10 - i) for i in range(21, 23)]
ALL = (*INDIAN, *THAI, *MEXICAN)


def ids(dishes: list[CatalogueRecipe]) -> list[str]:
    return [d.recipe_id for d in dishes]


def test_suggestions_interleave_cuisines_by_popularity() -> None:
    result = suggest_seed_dishes(ALL, limit=6)
    assert [s.recipe_id for s in result.suggestions] == [
        INDIAN[0].recipe_id,
        THAI[0].recipe_id,
        MEXICAN[0].recipe_id,
        INDIAN[1].recipe_id,
        THAI[1].recipe_id,
        MEXICAN[1].recipe_id,
    ]
    assert [s.rank for s in result.suggestions] == [1, 2, 3, 4, 5, 6]


def test_preferred_cuisines_come_first_and_the_rest_fill_in() -> None:
    result = suggest_seed_dishes(ALL, preferred_cuisines=("Mexican", "Korean"), limit=10)
    cuisines = [s.cuisines[0] for s in result.suggestions]
    mexican = cuisines.count("Mexican")
    assert cuisines[:mexican] == ["Mexican"] * mexican  # Korean has no dish: ignored
    assert len(result.suggestions) == 10  # Mexican runs out; the others top the list up
    assert 0 < mexican < 10
    assert len({s.recipe_id for s in result.suggestions}) == 10


def test_only_supplied_food_com_anchor_dishes_are_offered() -> None:
    staple = INDIAN[0].model_copy(update={"recipe_id": "USDA_1", "training_interactions": None})
    side = INDIAN[1].model_copy(update={"roles": (CulinaryRole.VEGETABLE,)})
    result = suggest_seed_dishes((staple, side, INDIAN[2]), limit=3)
    assert [s.recipe_id for s in result.suggestions] == [INDIAN[2].recipe_id]
    assert not is_seed_eligible(staple) and not is_seed_eligible(side)


def test_suggestions_are_deterministic_and_wire_camel_case() -> None:
    first = suggest_seed_dishes(ALL)
    assert first == suggest_seed_dishes(tuple(reversed(ALL)))
    wire = first.model_dump(by_alias=True)
    assert set(wire) == {"suggestions", "method", "minPicks", "maxPicks"}
    assert set(wire["suggestions"][0]) == {"recipeId", "name", "cuisines", "rank", "swaps"}


def test_too_few_suggestions_is_a_caller_error() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        suggest_seed_dishes(ALL, limit=2)


def test_valid_picks_become_history_in_pick_order() -> None:
    safe = {d.recipe_id: d for d in ALL}
    picks = [THAI[0].recipe_id, INDIAN[3].recipe_id, MEXICAN[1].recipe_id]
    assert validate_seed_picks(picks, safe) == tuple(picks)


@pytest.mark.parametrize(
    ("picks", "message"),
    [
        (ids(INDIAN[:2]), "pick 3 to 5"),
        (ids([*INDIAN, *THAI[:1]]), "pick 3 to 5"),
        ([INDIAN[0].recipe_id] * 3, "only once"),
        ([*ids(INDIAN[:2]), "FC_999"], "not rule-safe"),
    ],
)
def test_invalid_picks_are_rejected(picks: list[str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_seed_picks(picks, {d.recipe_id: d for d in ALL})


def test_a_safe_dish_that_cannot_seed_is_rejected() -> None:
    side = INDIAN[0].model_copy(update={"roles": (CulinaryRole.VEGETABLE,)})
    safe = {d.recipe_id: d for d in (side, *INDIAN[1:3])}
    with pytest.raises(ValueError, match="can seed"):
        validate_seed_picks(ids([side, *INDIAN[1:3]]), safe)


def test_the_shipped_catalogue_offers_a_full_mixed_shortlist() -> None:
    raw = json.loads(CATALOGUE.read_text(encoding="utf-8"))["recipes"]
    dishes = [CatalogueRecipe.model_validate_json(json.dumps(r)) for r in raw]
    result = suggest_seed_dishes(dishes)
    assert len(result.suggestions) == 12
    assert len({s.cuisines[0] for s in result.suggestions}) >= 7
    assert len(result.suggestions) >= MAX_SEED_PICKS
