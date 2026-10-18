# pyright: reportMissingImports=false
# torch is the optional `ml` extra; CI type-checks without it, locally with it.
"""T5: model experiments behind the evaluation report (ADR 0004).

    seeds        the main model trained with 3 seeds: mean and spread, not one lucky run
    ablations    without content features / ID embeddings / popularity bias
    hybrid       popularity weight chosen on VALIDATION only, then test scored once
    uncertainty  paired bootstrap 95% intervals for (model - popularity) on test
    catalogue    ranking restricted to the 160 catalogue dishes: what the product does
    meals        anchor vs mean scoring of whole meals (ADR 0004 D6), on catalogue cases

Usage (from apps/ai_system, needs the `ml` extra; about 30 minutes on a laptop CPU):
    uv run --extra ml python -m savora_ai.core.recommendation.experiments \
        --interactions ../../Data/Food.com/RAW_interactions.csv \
        --recipes ../../Data/Food.com/RAW_recipes.csv \
        --catalogue-dir ../../Data/catalogue --output ../../docs/eval/model_experiments.json
"""

import argparse
import json
import math
import random
import statistics
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import torch
from torch import Tensor

from savora_ai.core.recommendation.baselines import PopularityOrder, full_rank
from savora_ai.core.recommendation.metrics import rank_metrics
from savora_ai.core.recommendation.ranking import combination_dishes
from savora_ai.core.recommendation.sequences import EvalCase, SplitData, load_interactions, split
from savora_ai.core.recommendation.torch_model import (
    ItemIndex,
    ModelConfig,
    SASRecContent,
    TrainConfig,
    _left_pad,
    load_features,
    pick_device,
    rank_of,
    save,
    scored_cases,
    train,
)

HYBRID_WEIGHTS = (0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0)
BOOTSTRAP_SAMPLES = 1000
HISTORY_BUCKETS = ((1, 1), (2, 4), (5, 19), (20, 10**9))


@dataclass(frozen=True)
class Run:
    name: str
    seed: int
    model: ModelConfig


RUNS: tuple[Run, ...] = (
    Run("main", 7, ModelConfig()),
    Run("main", 11, ModelConfig()),
    Run("main", 13, ModelConfig()),
    Run("no_content", 7, ModelConfig(use_content=False)),
    Run("no_id", 7, ModelConfig(use_id=False)),
    Run("no_bias", 7, ModelConfig(use_bias=False)),
)


@torch.no_grad()
def case_ranks(
    model: SASRecContent,
    index: ItemIndex,
    cases: Sequence[EvalCase],
    log_popularity: Tensor,
    weights: Sequence[float],
    candidate_rows: Tensor | None = None,
) -> dict[float, list[int]]:
    """Ranks for several hybrid weights (score + w * log(1 + count)) in one scoring pass,
    using the SAME protocol as evaluate.py (`torch_model.scored_cases`)."""
    device = next(model.parameters()).device
    pop = log_popularity.to(device)
    ranks: dict[float, list[int]] = {w: [] for w in weights}
    for _, row, target in scored_cases(model, index, cases, None, candidate_rows):
        for w in weights:
            ranks[w].append(rank_of(row + w * pop, target))
    return ranks


def bootstrap_difference(
    a: Sequence[float], b: Sequence[float], seed: int = 7, samples: int = BOOTSTRAP_SAMPLES
) -> dict[str, float]:
    """Paired bootstrap of mean(a) - mean(b): the same resampled cases for both models."""
    if len(a) != len(b) or not a:
        raise ValueError("paired samples must have the same, non-zero length")
    rng = random.Random(seed)
    n = len(a)
    diffs = []
    for _ in range(samples):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(a[i] - b[i] for i in idx) / n)
    diffs.sort()
    return {
        "difference": sum(x - y for x, y in zip(a, b, strict=True)) / n,
        "ci95Low": diffs[int(0.025 * samples)],
        "ci95High": diffs[int(0.975 * samples) - 1],
        "shareOfResamplesAtOrBelowZero": sum(d <= 0 for d in diffs) / samples,
    }


def per_case(ranks: Sequence[int], k: int = 10) -> dict[str, list[float]]:
    return {
        f"hr@{k}": [float(r <= k) for r in ranks],
        f"ndcg@{k}": [1 / math.log2(r + 1) if r <= k else 0.0 for r in ranks],
        "mrr": [1 / r for r in ranks],
    }


def buckets(cases: Sequence[EvalCase], ranks: Sequence[int]) -> dict[str, object]:
    out: dict[str, object] = {}
    for lo, hi in HISTORY_BUCKETS:
        chosen = [r for c, r in zip(cases, ranks, strict=True) if lo <= len(c.history) <= hi]
        label = f"{lo}" if lo == hi else (f"{lo}+" if hi > 10**8 else f"{lo}-{hi}")
        out[label] = rank_metrics(chosen)
    return out


def _median(values: Sequence[int]) -> float:
    return float(statistics.median(values)) if values else 0.0


@dataclass(frozen=True)
class Catalogue:
    dish_ids: tuple[str, ...]  # Food.com catalogue dishes
    meals: tuple[str, ...]  # combination IDs


def load_catalogue(directory: Path) -> Catalogue:
    path = sorted(directory.glob("*_catalogue.json"))[-1]
    version = path.name.removesuffix("_catalogue.json")
    recipes = json.loads(path.read_text(encoding="utf-8"))["recipes"]
    combos = json.loads((directory / f"{version}_combinations.json").read_text(encoding="utf-8"))
    return Catalogue(
        dish_ids=tuple(sorted(r["recipeId"] for r in recipes if r["recipeId"].startswith("FC_"))),
        meals=tuple(c["combinationId"] for c in combos["combinations"]),
    )


@torch.no_grad()
def meal_ablation(
    model: SASRecContent,
    index: ItemIndex,
    cases: Sequence[EvalCase],
    log_popularity: Tensor,
    weight: float,
    catalogue: Catalogue,
) -> dict[str, object]:
    """Rank of the best meal containing the user's real next recipe, per aggregation.

    No combination-level ground truth exists; this proxy asks which aggregation puts a
    meal with the recipe the user actually chose next near the top of all 446 meals."""
    device = next(model.parameters()).device
    dishes = {cid: combination_dishes(cid) for cid in catalogue.meals}
    scorable = sorted({d for parts in dishes.values() for d in parts if d in index.row})
    rows = torch.tensor([index.row[d] for d in scorable], device=device)
    vectors = model.item_vectors(rows)
    extra = model.item_bias(rows) + weight * log_popularity.to(device)[rows]
    pop = {d: float(log_popularity[index.row[d]]) for d in scorable}  # case-independent
    results: dict[str, list[int]] = {"ANCHOR": [], "MEAN": [], "POPULARITY_ANCHOR": []}
    in_a_meal = {d for parts in dishes.values() for d in parts}
    cases = [c for c in cases if c.target in in_a_meal]  # a dish in no meal cannot be found
    for start in range(0, len(cases), 256):
        batch = cases[start : start + 256]
        seqs = torch.tensor(
            [_left_pad([index.row[r] for r in c.history], model.config.max_len) for c in batch],
            device=device,
        )
        dish_scores = model.encode(seqs)[:, -1] @ vectors.T + extra
        for b, case in enumerate(batch):
            score = dict(zip(scorable, dish_scores[b].tolist(), strict=True))
            relevant = [cid for cid, parts in dishes.items() if case.target in parts]
            for name, table, mean in (
                ("ANCHOR", score, False),
                ("MEAN", score, True),
                ("POPULARITY_ANCHOR", pop, False),
            ):
                meal_score: dict[str, float] = {}
                for cid, parts in dishes.items():
                    known = [table[d] for d in parts if d in table]
                    if mean and known:
                        meal_score[cid] = sum(known) / len(known)
                    elif not mean and parts[0] in table:
                        meal_score[cid] = table[parts[0]]
                best = max(meal_score[c] for c in relevant if c in meal_score)
                results[name].append(sum(v > best for v in meal_score.values()) + 1)
    return {
        "cases": len(cases),
        "meals": len(catalogue.meals),
        "protocol": "rank of the best meal containing the user's next recipe among all meals",
        **{name: rank_metrics(r) for name, r in results.items()},
    }


def run_all(
    interactions: Path,
    recipes: Path,
    catalogue_dir: Path,
    models_dir: Path,
    runs: Sequence[Run] = RUNS,
    train_config: TrainConfig = TrainConfig(),  # noqa: B008 - frozen dataclass
    device: torch.device | None = None,
    log: Callable[[str], None] = print,
) -> dict[str, object]:
    device = device or pick_device("cpu")
    started = time.time()
    data: SplitData = split(load_interactions(interactions))
    features = load_features(recipes)
    universe = sorted(
        set(features)
        | set(data.train_counts)
        | {r for c in (*data.validation, *data.test) for r in (c.target, *c.history)}
    )
    catalogue = load_catalogue(catalogue_dir)
    in_catalogue = set(catalogue.dish_ids)
    cat_test = [c for c in data.test if c.target in in_catalogue]

    pop = PopularityOrder.build(universe, data.train_counts)
    pop_test = [full_rank({}, c.target, c.history, pop) for c in data.test]
    cat_pop = PopularityOrder.build(catalogue.dish_ids, data.train_counts)
    pop_cat = [full_rank({}, c.target, c.history, cat_pop) for c in cat_test]

    results: list[dict[str, object]] = []
    shipped: dict[str, object] | None = None
    for run in runs:
        log(f"--- {run.name} seed {run.seed}")
        model, index, report = train(
            data,
            features,
            universe,
            model_config=run.model,
            train_config=replace(train_config, seed=run.seed),
            device=device,
            log=log,
        )
        save(models_dir / f"{run.name}_seed{run.seed}.pt", model, index, report)
        log_pop = torch.tensor([math.log1p(data.train_counts.get(i, 0)) for i in index.ids])
        valid = case_ranks(model, index, data.validation, log_pop, HYBRID_WEIGHTS)
        best_w = max(HYBRID_WEIGHTS, key=lambda w: (sum(r <= 10 for r in valid[w]), -w))
        test = case_ranks(model, index, data.test, log_pop, (0.0, best_w))
        cat_rows = torch.tensor([index.row[d] for d in catalogue.dish_ids])
        cat = case_ranks(model, index, cat_test, log_pop, (0.0, best_w), cat_rows)
        cold = [i for i, c in enumerate(data.test) if c.target not in data.train_counts]
        entry: dict[str, object] = {
            "run": run.name,
            "seed": run.seed,
            "modelConfig": asdict(run.model),
            "epochs": report["epochs"],
            "bestValidHr@10": report["bestValidHr@10"],
            "hybridWeightChosenOnValidation": best_w,
            "validationByWeight": {str(w): rank_metrics(valid[w]) for w in HYBRID_WEIGHTS},
            "test": rank_metrics(test[0.0]),
            "testHybrid": rank_metrics(test[best_w]),
            "testHistoryBuckets": buckets(data.test, test[0.0]),
            "testHybridHistoryBuckets": buckets(data.test, test[best_w]),
            "coldTargets": {
                "cases": len(cold),
                "medianRankModel": _median([test[0.0][i] for i in cold]),
                "medianRankPopularity": _median([pop_test[i] for i in cold]),
                "hr@10Model": sum(test[0.0][i] <= 10 for i in cold) / max(1, len(cold)),
            },
            "catalogueRestricted": {
                "model": rank_metrics(cat[0.0]),
                "hybrid": rank_metrics(cat[best_w]),
            },
        }
        if run.name == "main" and run.seed == runs[0].seed:
            pairs = per_case(test[best_w]), per_case(pop_test)
            cat_pairs = per_case(cat[best_w]), per_case(pop_cat)
            pure = per_case(test[0.0])
            shipped = {
                "seed": run.seed,
                "hybridVsPopularityTest": {
                    k: bootstrap_difference(pairs[0][k], pairs[1][k]) for k in pairs[0]
                },
                "modelVsPopularityTest": {
                    k: bootstrap_difference(pure[k], pairs[1][k]) for k in pure
                },
                "hybridVsPopularityCatalogue": {
                    k: bootstrap_difference(cat_pairs[0][k], cat_pairs[1][k]) for k in cat_pairs[0]
                },
                "mealAggregation": meal_ablation(
                    model, index, cat_test, log_pop, best_w, catalogue
                ),
            }
        results.append(entry)
        log(f"    test HR@10 {entry['test']}  hybrid(w={best_w}) {entry['testHybrid']}")

    mains = [r for r in results if r["run"] == "main"]

    def spread(key: str, metric: str) -> dict[str, float]:
        values = [float(r[key][metric]) for r in mains]  # type: ignore[index]
        return {
            "mean": statistics.mean(values),
            "sd": statistics.stdev(values) if len(values) > 1 else 0.0,
        }

    return {
        "protocol": {
            "split": data.report(),
            "ranking": "full ranking over every Food.com recipe; history excluded",
            "catalogueRanking": f"{len(catalogue.dish_ids)} catalogue dishes, "
            f"{len(cat_test)} test cases whose target is a catalogue dish",
            "hybridWeights": list(HYBRID_WEIGHTS),
            "hybridSelection": "highest validation HR@10, ties to the smaller weight",
            "bootstrap": f"paired, {BOOTSTRAP_SAMPLES} resamples",
            "trainConfig": asdict(train_config),
            "device": str(device),
            "minutes": round((time.time() - started) / 60, 1),
        },
        "popularity": {
            "test": rank_metrics(pop_test),
            "testHistoryBuckets": buckets(data.test, pop_test),
            "catalogueRestricted": rank_metrics(pop_cat),
        },
        "runs": results,
        "mainAcrossSeeds": {
            f"{key}.{m}": spread(key, m)
            for key in ("test", "testHybrid")
            for m in ("hr@10", "ndcg@10", "mrr")
        },
        "shippedSeedAnalysis": shipped,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data = Path("Data/Food.com")
    parser.add_argument("--interactions", type=Path, default=data / "RAW_interactions.csv")
    parser.add_argument("--recipes", type=Path, default=data / "RAW_recipes.csv")
    parser.add_argument("--catalogue-dir", type=Path, default=Path("Data/catalogue"))
    parser.add_argument("--models-dir", type=Path, default=Path("Data/models/experiments"))
    parser.add_argument("--output", type=Path, default=Path("docs/eval/model_experiments.json"))
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    report = run_all(
        args.interactions,
        args.recipes,
        args.catalogue_dir,
        args.models_dir,
        device=pick_device(args.device),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
