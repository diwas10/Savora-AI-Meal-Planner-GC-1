"""The code that produces the reported numbers is itself tested, end to end, on tiny data."""

import csv
import json
from pathlib import Path

import pytest

from savora_ai.core.recommendation import evaluate

USERS = 40


def write_data(tmp: Path) -> tuple[Path, Path]:
    """Every user walks FC_1 -> FC_2 -> FC_3 before 2012, then FC_4 in 2012 and 2013+."""
    interactions = tmp / "RAW_interactions.csv"
    with interactions.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["user_id", "recipe_id", "date", "rating", "review"])
        for user in range(USERS):
            for recipe, day in ((1, "2010-01-01"), (2, "2010-06-01"), (3, "2011-01-01")):
                writer.writerow([user, recipe, day, 5, "ok"])
            writer.writerow([user, 4 if user % 2 else 5, "2012-05-01", 5, "ok"])
            writer.writerow([user, 4, "2014-05-01", 5, "ok"])
    recipes = tmp / "RAW_recipes.csv"
    with recipes.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["name", "id", "tags", "nutrition", "ingredients"])
        for recipe, tags, ingredients in (
            (1, ["breakfast"], ["oats"]),
            (2, ["main-dish"], ["lentils"]),
            (3, ["main-dish"], ["rice"]),
            (4, ["main-dish"], ["lentils", "rice"]),
            (5, ["desserts"], ["sugar"]),
        ):
            writer.writerow(
                [f"dish {recipe}", recipe, str(tags), "[1,2,3,4,5,6,7]", str(ingredients)]
            )
    return interactions, recipes


def test_baseline_evaluation_runs_end_to_end(tmp_path: Path) -> None:
    interactions, recipes = write_data(tmp_path)
    report = evaluate.run(interactions, recipes)
    protocol = report["protocol"]
    assert isinstance(protocol, dict)
    assert protocol["testCases"] == USERS and protocol["validationCases"] == USERS
    results = report["results"]
    assert isinstance(results, dict)
    test = results["test"]
    assert set(test) == {"popularity", "markov", "item_knn"}
    # FC_4 is never trained on and the universe is tiny: every metric is a valid rate.
    for metrics in test.values():
        assert 0.0 <= metrics["hr@10"] <= 1.0 and metrics["cases"] == USERS


def test_baseline_cli_writes_the_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    interactions, recipes = write_data(tmp_path)
    out = tmp_path / "eval.json"
    argv = ["evaluate", "--interactions", str(interactions), "--recipes", str(recipes)]
    monkeypatch.setattr("sys.argv", [*argv, "--output", str(out)])
    evaluate.main()
    assert json.loads(out.read_text(encoding="utf-8"))["protocol"]["k"] == 10


# --- experiments (torch) -------------------------------------------------------------


def test_bootstrap_difference_brackets_the_truth() -> None:
    pytest.importorskip("torch")
    from savora_ai.core.recommendation.experiments import bootstrap_difference

    same = bootstrap_difference([1.0, 0.0] * 50, [1.0, 0.0] * 50)
    assert same["difference"] == 0.0 and same["ci95Low"] <= 0.0 <= same["ci95High"]
    better = bootstrap_difference([1.0] * 80 + [0.0] * 20, [0.0] * 80 + [1.0] * 20)
    assert better["ci95Low"] > 0 and better["shareOfResamplesAtOrBelowZero"] == 0.0
    with pytest.raises(ValueError):
        bootstrap_difference([1.0], [1.0, 0.0])


def test_experiment_suite_runs_end_to_end_on_tiny_data(tmp_path: Path) -> None:
    pytest.importorskip("torch")
    from savora_ai.core.recommendation import experiments
    from savora_ai.core.recommendation.torch_model import ModelConfig, TrainConfig

    interactions, recipes = write_data(tmp_path)
    catalogue = tmp_path / "catalogue"
    catalogue.mkdir()
    version = "20261019T000000Z"
    (catalogue / f"{version}_catalogue.json").write_text(
        json.dumps({"recipes": [{"recipeId": f"FC_{i}"} for i in (2, 3, 4)]}), encoding="utf-8"
    )
    (catalogue / f"{version}_combinations.json").write_text(
        json.dumps(
            {
                "combinations": [
                    {"combinationId": "C_ONE_DISH__FC_4"},
                    {"combinationId": "C_MAIN_STAPLE__FC_2__USDA_1"},
                    {"combinationId": "C_MAIN_STAPLE_VEGETABLE__FC_3__USDA_1__FC_4"},
                ]
            }
        ),
        encoding="utf-8",
    )
    small = ModelConfig(dim=16, layers=1, heads=2, dropout=0.0, max_len=5, top_ingredients=20)
    report = experiments.run_all(
        interactions,
        recipes,
        catalogue,
        tmp_path / "models",
        runs=(
            experiments.Run("main", 7, small),
            experiments.Run("main", 11, small),
            experiments.Run(
                "no_content", 7, ModelConfig(**{**small.__dict__, "use_content": False})
            ),
        ),
        train_config=TrainConfig(epochs=2, batch_size=8, negatives=8, validation_cases=20),
        log=lambda _: None,
    )
    runs = report["runs"]
    assert isinstance(runs, list) and [r["run"] for r in runs] == ["main", "main", "no_content"]
    spread = report["mainAcrossSeeds"]
    assert isinstance(spread, dict) and set(spread["test.hr@10"]) == {"mean", "sd"}
    shipped = report["shippedSeedAnalysis"]
    assert isinstance(shipped, dict)
    meals = shipped["mealAggregation"]
    assert meals["cases"] == USERS  # every test target (FC_4) is in a meal
    assert set(meals) >= {"ANCHOR", "MEAN", "POPULARITY_ANCHOR"}
    assert (tmp_path / "models" / "main_seed7.pt").exists()
    for run in runs:
        assert run["hybridWeightChosenOnValidation"] in experiments.HYBRID_WEIGHTS
        assert run["catalogueRestricted"]["model"]["cases"] == USERS


def test_repeated_weights_do_not_duplicate_ranks() -> None:
    # Found by the end-to-end test: weights (0.0, best) with best == 0.0 doubled ranks.
    torch = pytest.importorskip("torch")
    from datetime import date

    from savora_ai.core.recommendation.experiments import case_ranks
    from savora_ai.core.recommendation.sequences import Interaction, split
    from savora_ai.core.recommendation.torch_model import ModelConfig, TrainConfig, train

    events = [
        Interaction(str(u), f"FC_{r}", date.fromisoformat(d), i)
        for u in range(10)
        for i, (r, d) in enumerate(((1, "2010-01-01"), (2, "2011-01-01"), (3, "2014-01-01")))
    ]
    data = split(events)
    features = {f"FC_{i}": (["main-dish"], ["x"]) for i in (1, 2, 3)}
    model, index, _ = train(
        data, features, sorted(features),
        ModelConfig(dim=8, layers=1, heads=2, dropout=0.0, max_len=3, top_ingredients=5),
        TrainConfig(epochs=1, batch_size=4, negatives=2, validation_cases=5),
        device=torch.device("cpu"), log=lambda _: None,
    )  # fmt: skip
    ranks = case_ranks(model, index, data.test, torch.zeros(len(index.ids)), (0.0, 0.0))
    assert list(ranks) == [0.0] and len(ranks[0.0]) == len(data.test)
