"""T4: the ranking API scores only supplied IDs and falls back explicitly (ADR 0004 D5)."""

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from savora_ai.core.recommendation.ranking import (
    Aggregation,
    FallbackReason,
    PopularityScorer,
    RankingContext,
    combination_dishes,
    load_scorer,
    popularity_from_catalogue,
    rank_combinations,
    rank_recipes,
)


class FakeScorer:
    """Deterministic test double: knows FC_1..FC_9, prefers higher IDs after FC_1."""

    model_version = "fake-v1"

    def knows(self, recipe_id: str) -> bool:
        return recipe_id in {f"FC_{i}" for i in range(1, 10)}

    def score(self, history: Sequence[str], candidates: Sequence[str]) -> Mapping[str, float]:
        assert all(self.knows(h) for h in history)  # the API strips unknown history
        return {c: float(c.removeprefix("FC_")) for c in candidates}


POP = PopularityScorer({"FC_2": 100, "FC_3": 5})
CTX = RankingContext(slot_id="D2_LUNCH")


def test_only_supplied_candidates_are_ranked() -> None:
    result = rank_recipes(
        ["FC_1"], ["FC_3", "FC_7", "FC_5"], CTX, scorer=FakeScorer(), fallback=POP
    )
    assert [c.recipe_id for c in result.ranked_candidates] == ["FC_7", "FC_5", "FC_3"]
    assert [c.rank for c in result.ranked_candidates] == [1, 2, 3]
    assert sum(c.score for c in result.ranked_candidates) == pytest.approx(1.0, abs=1e-5)
    assert result.model_version == "fake-v1" and result.fallback_reason is None
    assert result.slot_id == "D2_LUNCH"


def test_no_known_history_falls_back_to_popularity_and_says_so() -> None:
    result = rank_recipes(["FC_99"], ["FC_3", "FC_2"], CTX, scorer=FakeScorer(), fallback=POP)
    assert result.fallback_reason is FallbackReason.NO_HISTORY
    assert result.model_version == "popularity-fallback-v1"
    assert result.ranked_candidates[0].recipe_id == "FC_2"


def test_missing_model_falls_back_and_says_so() -> None:
    result = rank_recipes(["FC_1"], ["FC_3", "FC_2"], CTX, scorer=None, fallback=POP)
    assert result.fallback_reason is FallbackReason.MODEL_UNAVAILABLE


def test_candidates_the_model_cannot_score_go_last() -> None:
    result = rank_recipes(["FC_1"], ["FC_50", "FC_2"], CTX, scorer=FakeScorer(), fallback=POP)
    assert [c.recipe_id for c in result.ranked_candidates] == ["FC_2", "FC_50"]
    assert result.ranked_candidates[-1].score == 0.0


@pytest.mark.parametrize("candidates", [[], ["FC_1", "FC_1"]])
def test_empty_or_duplicate_candidates_are_rejected(candidates: list[str]) -> None:
    with pytest.raises(ValueError):
        rank_recipes(["FC_1"], candidates, CTX, scorer=FakeScorer(), fallback=POP)


def test_wire_format_matches_the_architecture_contract() -> None:
    combos = ["C_MAIN_STAPLE__FC_5__USDA_169757"]
    result = rank_combinations(["FC_1"], combos, CTX, scorer=FakeScorer(), fallback=POP)
    wire = result.model_dump(mode="json", by_alias=True)
    assert set(wire) == {
        "slotId",
        "rankedCandidates",
        "modelVersion",
        "aggregation",
        "fallbackReason",
        "unscoredCandidates",
    }
    assert set(wire["rankedCandidates"][0]) == {"combinationId", "rank", "score"}
    assert "nutrition" not in str(wire)  # raw ranking makes no nutrition claim


# --- combinations -------------------------------------------------------------------


def test_combination_ids_parse_to_dishes_anchor_first() -> None:
    assert combination_dishes("C_MAIN_STAPLE_VEGETABLE__FC_1__USDA_2__FC_3") == (
        "FC_1",
        "USDA_2",
        "FC_3",
    )
    with pytest.raises(ValueError):
        combination_dishes("FC_1")


def test_anchor_aggregation_ignores_staples_and_ties_break_by_id() -> None:
    combos = [
        "C_MAIN_STAPLE__FC_5__USDA_169757",
        "C_MAIN_STAPLE__FC_5__USDA_2707713",
        "C_ONE_DISH__FC_8",
    ]
    result = rank_combinations(["FC_1"], combos, CTX, scorer=FakeScorer(), fallback=POP)
    order = [c.combination_id for c in result.ranked_candidates]
    assert order == ["C_ONE_DISH__FC_8", combos[0], combos[1]]
    assert result.ranked_candidates[1].score == result.ranked_candidates[2].score  # same anchor


def test_mean_aggregation_is_an_ablation_over_scorable_dishes() -> None:
    combos = ["C_MAIN_STAPLE_VEGETABLE__FC_2__USDA_1__FC_9", "C_ONE_DISH__FC_5"]
    anchor = rank_combinations(["FC_1"], combos, CTX, scorer=FakeScorer(), fallback=POP)
    mean = rank_combinations(
        ["FC_1"], combos, CTX, scorer=FakeScorer(), fallback=POP, aggregation=Aggregation.MEAN
    )
    assert anchor.ranked_candidates[0].combination_id == "C_ONE_DISH__FC_5"  # 5 > 2
    assert mean.ranked_candidates[0].combination_id == combos[0]  # (2 + 9) / 2 = 5.5 > 5
    assert mean.aggregation is Aggregation.MEAN


def test_load_scorer_without_a_model_file_returns_none(tmp_path: Path) -> None:
    assert load_scorer(tmp_path / "missing.pt") is None


def test_popularity_fallback_comes_from_the_catalogue_export() -> None:
    scorer = popularity_from_catalogue(
        [
            {"recipeId": "FC_1", "trainingInteractions": 50},
            {"recipeId": "FC_2", "trainingInteractions": 0},
            {"recipeId": "USDA_169757", "trainingInteractions": None},
        ]
    )
    result = rank_recipes([], ["FC_2", "FC_1"], CTX, scorer=None, fallback=scorer)
    assert result.ranked_candidates[0].recipe_id == "FC_1"
    assert scorer.counts == {"FC_1": 50, "FC_2": 0}


# --- review regressions -------------------------------------------------------------


def test_model_that_scores_no_candidate_falls_back_explicitly() -> None:
    # Review: the model knew the history but no candidate; it used to rank by ID under
    # the model's name with no fallback reason.
    result = rank_recipes(["FC_1"], ["FC_50", "FC_2"], CTX, scorer=FakeScorer(), fallback=POP)
    assert result.ranked_candidates[0].recipe_id == "FC_2"  # FakeScorer knows FC_2
    none_known = rank_recipes(["FC_1"], ["FC_50", "FC_60"], CTX, scorer=FakeScorer(), fallback=POP)
    assert none_known.fallback_reason is FallbackReason.CANDIDATES_UNKNOWN_TO_MODEL
    assert none_known.model_version == "popularity-fallback-v1"


def test_unscored_candidates_are_listed_and_ordered_by_popularity() -> None:
    pop = PopularityScorer({"FC_70": 50, "FC_60": 5})
    result = rank_recipes(
        ["FC_1"], ["FC_60", "FC_2", "FC_70"], CTX, scorer=FakeScorer(), fallback=pop
    )
    assert [c.recipe_id for c in result.ranked_candidates] == ["FC_2", "FC_70", "FC_60"]
    assert result.unscored_candidates == ("FC_70", "FC_60")
