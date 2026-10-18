"""T3: SASRec + content smoke tests on tiny synthetic data (skipped without torch)."""

from datetime import date
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from savora_ai.core.recommendation.sequences import Interaction, split  # noqa: E402
from savora_ai.core.recommendation.torch_model import (  # noqa: E402
    PAD,
    ModelConfig,
    TrainConfig,
    dense_ranks,
    load,
    save,
    train,
)

SMALL = ModelConfig(dim=16, layers=1, heads=2, dropout=0.0, max_len=5, top_ingredients=20)
FAST = TrainConfig(epochs=2, batch_size=8, negatives=8, validation_cases=50, patience=5)


def tiny():
    events = []
    order = 0
    for user in range(30):  # every user walks 1 -> 2 -> 3 in training, then 4 later
        for step, (recipe, day) in enumerate(
            [(1, "2010-01-01"), (2, "2010-02-01"), (3, "2011-01-01"), (4, "2013-05-01")]
        ):
            events.append(Interaction(str(user), f"FC_{recipe}", date.fromisoformat(day), order))
            order += 1 + step
    data = split(events)
    features = {
        "FC_1": (["breakfast"], ["oats"]),
        "FC_2": (["main-dish"], ["lentils"]),
        "FC_3": (["main-dish"], ["rice"]),
        "FC_4": (["main-dish"], ["lentils", "rice"]),  # never seen in training
        "FC_5": (["desserts"], ["sugar"]),
    }
    return data, features, sorted(features)


def test_training_runs_and_unseen_items_have_no_id_vector() -> None:
    data, features, universe = tiny()
    model, index, report = train(
        data, features, universe, SMALL, FAST, device=torch.device("cpu"), log=lambda _: None
    )
    assert report["itemsWithIdVector"] == 3  # FC_1..3 only
    assert index.has_id[index.row["FC_4"]] == 0
    # FC_4's vector is pure content: changing its (untrained) ID row changes nothing.
    before = model.item_vectors(torch.tensor([index.row["FC_4"]])).detach().clone()
    with torch.no_grad():
        model.item.weight[index.row["FC_4"]] += 100.0
    after = model.item_vectors(torch.tensor([index.row["FC_4"]]))
    assert torch.allclose(before, after)
    ranks = dense_ranks(model, index, data.test, torch.device("cpu"))
    assert len(ranks) == len(data.test) and all(1 <= r <= len(universe) for r in ranks)


def test_padding_never_produces_nan() -> None:
    data, features, universe = tiny()
    model, index, _ = train(
        data, features, universe, SMALL, FAST, device=torch.device("cpu"), log=lambda _: None
    )
    states = model.encode(torch.tensor([[PAD, PAD, PAD, PAD, index.row["FC_1"]]]))
    assert not torch.isnan(states).any()


def test_save_and_load_give_identical_scores(tmp_path: Path) -> None:
    data, features, universe = tiny()
    model, index, report = train(
        data, features, universe, SMALL, FAST, device=torch.device("cpu"), log=lambda _: None
    )
    path = tmp_path / "m.pt"
    save(path, model, index, report)
    loaded, rows = load(path)
    assert rows == index.row
    model.eval()
    seq = torch.tensor([[PAD, PAD, PAD, index.row["FC_1"], index.row["FC_2"]]])
    with torch.no_grad():
        assert torch.allclose(model.encode(seq), loaded.encode(seq))


def test_torch_scorer_scores_only_known_candidates_and_adds_the_hybrid(tmp_path: Path) -> None:
    from savora_ai.core.recommendation.torch_model import TorchScorer

    data, features, universe = tiny()
    model, index, report = train(
        data, features, universe, SMALL, FAST, device=torch.device("cpu"), log=lambda _: None
    )
    path = tmp_path / "m.pt"
    save(path, model, index, report)
    pure = TorchScorer(path)
    hybrid = TorchScorer(path, {"FC_5": 100}, popularity_weight=2.0)
    assert pure.model_version == "sasrec-content-v1"
    assert hybrid.model_version == "sasrec-content-v1+pop2"
    a = pure.score(["FC_1"], ["FC_5", "FC_X"])
    b = hybrid.score(["FC_1"], ["FC_5", "FC_X"])
    assert set(a) == {"FC_5"}  # an unknown candidate is never invented a score
    assert b["FC_5"] == pytest.approx(a["FC_5"] + 2.0 * __import__("math").log1p(100))


def test_experiments_and_evaluation_share_one_ranking_protocol() -> None:
    # Review: experiments.case_ranks duplicated dense_ranks; both now use scored_cases.
    from savora_ai.core.recommendation.experiments import case_ranks

    data, features, universe = tiny()
    model, index, _ = train(
        data, features, universe, SMALL, FAST, device=torch.device("cpu"), log=lambda _: None
    )
    pop = torch.zeros(len(index.ids))
    assert case_ranks(model, index, data.test, pop, (0.0,))[0.0] == dense_ranks(
        model, index, data.test, torch.device("cpu")
    )
