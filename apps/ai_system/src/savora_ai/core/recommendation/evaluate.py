"""T5: evaluate rankers on the held-out periods by full ranking (ADR 0004 D4).

Usage (from the repo root):
    uv run python -m savora_ai.core.recommendation.evaluate \
        --interactions Data/Food.com/RAW_interactions.csv --recipes Data/Food.com/RAW_recipes.csv
    # with the trained Transformer (needs the optional `ml` extra; run from apps/ai_system):
    cd apps/ai_system && uv run --extra ml python -m savora_ai.core.recommendation.evaluate \
        --interactions ../../Data/Food.com/RAW_interactions.csv \
        --recipes ../../Data/Food.com/RAW_recipes.csv \
        --model ../../Data/models/sasrec_content.pt --output ../../docs/eval/ranking_evaluation.json

Writes docs/eval/ranking_evaluation.json. Every ranker sees the same cases, the same
universe (every Food.com recipe) and the same tie-break, so the numbers are comparable.
"""

import argparse
import csv
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from savora_ai.core.food_data.foodcom_cuisines import normalize_tags
from savora_ai.core.recommendation.baselines import (
    ItemKNN,
    Markov,
    Popularity,
    PopularityOrder,
    Ranker,
    full_rank,
    top_k,
)
from savora_ai.core.recommendation.metrics import (
    catalogue_coverage,
    intra_list_diversity,
    rank_metrics,
)
from savora_ai.core.recommendation.sequences import EvalCase, load_interactions, split

K = 10
# Top-K lists for coverage/diversity are computed on this many cases (they are costly).
BEYOND_ACCURACY_CASES = 2000


def load_recipe_tags(path: Path) -> dict[str, frozenset[str]]:
    csv.field_size_limit(sys.maxsize)
    tags: dict[str, frozenset[str]] = {}
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["id"].isdecimal():
                tags[f"FC_{int(row['id'])}"] = normalize_tags(row["tags"])
    return tags


def evaluate_sparse(
    ranker: Ranker,
    cases: Sequence[EvalCase],
    pop: PopularityOrder,
    tags: Mapping[str, frozenset[str]],
) -> dict[str, object]:
    ranks: list[int] = []
    tops: list[list[str]] = []
    for index, case in enumerate(cases):
        primary = ranker.primary_scores(case.history)
        ranks.append(full_rank(primary, case.target, case.history, pop))
        if index < BEYOND_ACCURACY_CASES:
            tops.append(top_k(primary, case.history, pop, K))
    return {
        **rank_metrics(ranks, K),
        "catalogueCoverage@10": catalogue_coverage(tops, len(pop.order)),
        "intraListDiversity@10": intra_list_diversity(tops, tags),
    }


def run(
    interactions: Path,
    recipes: Path,
    extra: Mapping[str, Callable[..., dict[str, object]]] | None = None,
) -> dict[str, object]:
    data = split(load_interactions(interactions))
    tags = load_recipe_tags(recipes)
    universe = set(tags) | {
        t for c in (*data.validation, *data.test) for t in (c.target, *c.history)
    }
    pop = PopularityOrder.build(universe, data.train_counts)
    sequences = list(data.train_sequences.values())
    rankers: list[Ranker] = [Popularity(), Markov(sequences), ItemKNN(sequences)]
    results: dict[str, object] = {}
    for period, cases in (("validation", data.validation), ("test", data.test)):
        results[period] = {r.name: evaluate_sparse(r, cases, pop, tags) for r in rankers}
        for name, evaluate in (extra or {}).items():
            results[period][name] = evaluate(cases=cases, pop=pop, tags=tags, data=data)  # type: ignore[index]
    return {
        "protocol": {
            "ranking": "full ranking over every Food.com recipe; history items excluded",
            "tieBreak": "training popularity, then recipe ID",
            "k": K,
            "beyondAccuracyCases": BEYOND_ACCURACY_CASES,
            "universe": len(pop.order),
            **data.report(),
        },
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--interactions", type=Path, default=Path("Data/Food.com/RAW_interactions.csv")
    )
    parser.add_argument("--recipes", type=Path, default=Path("Data/Food.com/RAW_recipes.csv"))
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("docs/eval/ranking_evaluation.json"))
    args = parser.parse_args()
    extra: dict[str, Callable[..., dict[str, object]]] = {}
    if args.model is not None:
        from savora_ai.core.recommendation.torch_model import (  # needs torch
            HYBRID_POPULARITY_WEIGHT,
            evaluator,
        )

        extra["sasrec_content"] = evaluator(args.model)
        extra["sasrec_content+popularity"] = evaluator(args.model, HYBRID_POPULARITY_WEIGHT)
    report = run(args.interactions, args.recipes, extra)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["results"], indent=2))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
