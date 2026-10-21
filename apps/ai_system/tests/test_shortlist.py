"""Per-slot shortlist: ranked meals become a bounded, ordered set of FIXED CSP options."""

import json
from pathlib import Path

import pytest

from savora_ai.core.meal_composition.models import MealCombination
from savora_ai.core.recommendation.ranking import (
    CombinationRanking,
    PopularityScorer,
    RankingContext,
    rank_combinations,
)
from savora_ai.core.recommendation.shortlist import (
    ShortlistLimits,
    shortlist_day,
    shortlist_slot,
)
from savora_ai.schemas.enums import MealType, PortionPreset

EXPORT = Path(__file__).parents[3] / "Data/catalogue"


def meals() -> dict[str, MealCombination]:
    path = sorted(EXPORT.glob("*_combinations.json"))[-1]
    raw = json.loads(path.read_text(encoding="utf-8"))["combinations"]
    return {c["combinationId"]: MealCombination.model_validate_json(json.dumps(c)) for c in raw}


MEALS = meals()


def ranking(ids: list[str]) -> CombinationRanking:
    return rank_combinations([], ids, RankingContext(), scorer=None, fallback=PopularityScorer({}))


def test_default_shortlist_is_two_combinations_by_four_presets_in_order() -> None:
    lunch = [c for c, m in MEALS.items() if MealType.LUNCH in m.meal_types][:10]
    slot = shortlist_slot(MealType.LUNCH, ranking(lunch), MEALS)
    combos = list(dict.fromkeys(o.combination_id for o in slot.options))
    assert len(combos) == 2 and len(slot.options) <= 8
    first = [o for o in slot.options if o.combination_id == combos[0]]
    assert first[0].preset is PortionPreset.STANDARD
    order = list(PortionPreset)
    assert [order.index(o.preset) for o in first] == sorted(order.index(o.preset) for o in first)
    assert all(":" in o.option_id and "#" not in o.option_id for o in slot.options)


def test_meals_that_do_not_suit_the_slot_are_skipped_and_reported() -> None:
    breakfast = [c for c, m in MEALS.items() if m.meal_types == (MealType.BREAKFAST,)][:3]
    lunch = [c for c, m in MEALS.items() if MealType.LUNCH in m.meal_types][:3]
    slot = shortlist_slot(MealType.LUNCH, ranking([*breakfast, *lunch]), MEALS)
    assert set(slot.skipped_unsuitable) <= set(breakfast)
    assert all(o.combination_id in lunch for o in slot.options)


def test_a_day_fits_member2_budgets_and_ranked_ids_must_be_supplied() -> None:
    by_meal = {
        meal: ranking([c for c, m in MEALS.items() if meal in m.meal_types][:20])
        for meal in MealType
    }
    day = shortlist_day(by_meal, MEALS)
    distinct = {o.option_id for s in day.values() for o in s.options}
    assert len(distinct) <= 150 and all(len(s.options) <= 50 for s in day.values())
    with pytest.raises(ValueError):
        shortlist_slot(MealType.LUNCH, ranking(["C_ONE_DISH__FC_0"]), MEALS)


def test_limits_reject_shortlists_beyond_the_per_slot_budget() -> None:
    with pytest.raises(ValueError):
        ShortlistLimits(combinations_per_slot=20, configurations_per_combination=5)
