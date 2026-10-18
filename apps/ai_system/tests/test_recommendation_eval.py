"""T1/T2: leakage-safe split, full-ranking metrics and baselines (ADR 0004)."""

import math
import random
from datetime import date
from pathlib import Path

import pytest

from savora_ai.core.recommendation.baselines import (
    ItemKNN,
    Markov,
    Popularity,
    PopularityOrder,
    full_rank,
    top_k,
)
from savora_ai.core.recommendation.metrics import (
    catalogue_coverage,
    intra_list_diversity,
    rank_metrics,
)
from savora_ai.core.recommendation.sequences import (
    Interaction,
    load_interactions,
    split,
)

TRAIN_END, VALID_END = date(2012, 1, 1), date(2013, 1, 1)


def event(user: str, recipe: int, day: str, order: int) -> Interaction:
    return Interaction(user, f"FC_{recipe}", date.fromisoformat(day), order)


# --- the split ----------------------------------------------------------------------


def test_split_uses_only_the_past_and_the_first_case_per_period() -> None:
    events = [
        event("u", 1, "2010-01-01", 0),
        event("u", 2, "2011-06-01", 1),
        event("u", 3, "2012-03-01", 2),  # first validation interaction
        event("u", 4, "2012-09-01", 3),
        event("u", 5, "2014-01-01", 4),  # first test interaction
        event("u", 6, "2015-01-01", 5),
    ]
    data = split(events, TRAIN_END, VALID_END)
    assert data.train_sequences == {"u": ("FC_1", "FC_2")}  # weights see only these
    [valid] = data.validation
    assert valid.history == ("FC_1", "FC_2") and valid.target == "FC_3"
    [test] = data.test
    assert test.history == ("FC_1", "FC_2", "FC_3", "FC_4") and test.target == "FC_5"
    assert data.train_counts == {"FC_1": 1, "FC_2": 1}  # never counts later periods


def test_cutoff_day_belongs_to_the_later_period() -> None:
    data = split([event("u", 1, "2011-12-31", 0), event("u", 2, "2012-01-01", 1)])
    assert data.validation[0].target == "FC_2"


def test_user_without_history_gives_no_case() -> None:
    data = split([event("new", 9, "2014-02-02", 0)])
    assert data.test == () and data.train_sequences == {}


def test_same_day_order_follows_the_file() -> None:
    events = [event("u", 2, "2010-01-01", 1), event("u", 1, "2010-01-01", 0)]
    assert split(events).train_sequences["u"] == ("FC_1", "FC_2")


def test_split_rejects_reversed_dates() -> None:
    with pytest.raises(ValueError):
        split([], VALID_END, TRAIN_END)


def test_loader_reads_multiline_reviews(tmp_path: Path) -> None:
    path = tmp_path / "RAW_interactions.csv"
    path.write_text(
        'user_id,recipe_id,date,rating,review\n1,5,2003-02-17,4,"a\nb"\n2,6,2004-01-01,5,x\n',
        encoding="utf-8",
    )
    rows = load_interactions(path)
    assert [(r.user_id, r.recipe_id, r.order) for r in rows] == [("1", "FC_5", 0), ("2", "FC_6", 1)]


# --- metrics ------------------------------------------------------------------------


def test_rank_metrics() -> None:
    m = rank_metrics([1, 2, 20], k=10)
    assert m["hr@10"] == pytest.approx(2 / 3)
    assert m["ndcg@10"] == pytest.approx((1 + 1 / math.log2(3)) / 3)
    assert m["mrr"] == pytest.approx((1 + 0.5 + 0.05) / 3)
    with pytest.raises(ValueError):
        rank_metrics([0])


def test_coverage_and_diversity() -> None:
    assert catalogue_coverage([["a", "b"], ["b", "c"]], 10) == pytest.approx(0.3)
    tags = {"a": frozenset({"x"}), "b": frozenset({"x"}), "c": frozenset({"y"})}
    assert intra_list_diversity([["a", "b"]], tags) == 0.0
    assert intra_list_diversity([["a", "c"]], tags) == 1.0


# --- exact full ranking -------------------------------------------------------------


def brute_rank(
    primary: dict[str, float], target: str, history: list[str], pop: PopularityOrder
) -> int:
    seen = set(history) - {target}
    order = sorted(
        (i for i in pop.order if i not in seen),
        key=lambda i: (-primary.get(i, 0.0), pop.position[i]),
    )
    return order.index(target) + 1


def test_counted_rank_equals_brute_force_sort() -> None:
    rng = random.Random(7)
    for _ in range(300):
        universe = [f"FC_{i}" for i in range(rng.randint(2, 40))]
        counts = {i: rng.randint(0, 5) for i in universe}
        pop = PopularityOrder.build(universe, counts)
        primary = {
            i: float(rng.randint(1, 3)) for i in rng.sample(universe, rng.randint(0, len(universe)))
        }
        history = rng.sample(universe, rng.randint(0, min(5, len(universe))))
        target = rng.choice(universe)
        assert full_rank(primary, target, history, pop) == brute_rank(primary, target, history, pop)


def test_top_k_agrees_with_rank() -> None:
    universe = [f"FC_{i}" for i in range(10)]
    pop = PopularityOrder.build(universe, {"FC_9": 5, "FC_8": 4})
    primary = {"FC_3": 1.0}
    top = top_k(primary, ["FC_9"], pop, 3)
    assert top == ["FC_3", "FC_8", "FC_0"]  # FC_9 is in the history
    assert [full_rank(primary, t, ["FC_9"], pop) for t in top] == [1, 2, 3]


def test_unknown_target_is_an_error() -> None:
    pop = PopularityOrder.build(["FC_1"], {})
    with pytest.raises(ValueError):
        full_rank({}, "FC_2", [], pop)


# --- baselines ----------------------------------------------------------------------


def test_popularity_ranks_by_training_count() -> None:
    pop = PopularityOrder.build(["FC_1", "FC_2", "FC_3"], {"FC_2": 9, "FC_3": 4})
    assert full_rank(Popularity().primary_scores(["FC_1"]), "FC_3", ["FC_1"], pop) == 2


def test_markov_follows_the_last_item() -> None:
    markov = Markov([("FC_1", "FC_2"), ("FC_1", "FC_2"), ("FC_1", "FC_3"), ("FC_4", "FC_4")])
    scores = markov.primary_scores(["FC_9", "FC_1"])
    assert scores == {"FC_2": pytest.approx(2 / 3), "FC_3": pytest.approx(1 / 3)}
    assert markov.primary_scores(["FC_4"]) == {}  # self-loops are not transitions
    assert markov.primary_scores([]) == {}


def test_item_knn_scores_co_occurring_items() -> None:
    knn = ItemKNN([("FC_1", "FC_2"), ("FC_1", "FC_2"), ("FC_1", "FC_3"), ("FC_5",)])
    scores = knn.primary_scores(["FC_1"])
    assert scores["FC_2"] > scores["FC_3"] > 0
    assert "FC_5" not in scores
