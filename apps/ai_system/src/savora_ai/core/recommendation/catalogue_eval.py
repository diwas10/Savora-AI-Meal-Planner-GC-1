# pyright: reportMissingImports=false
# torch is the optional `ml` extra; CI type-checks without it, locally with it.
"""Evaluate the SHIPPED Transformer on a catalogue export, without retraining.

What the product does is rank catalogue dishes and meals, not all 231k Food.com recipes.
For the held-out TEST cases whose next recipe is a catalogue dish, this reports:

    dishes   rank of that dish among the catalogue's Food.com dishes: the model alone,
             the shipped hybrid (model + validated popularity weight), and popularity,
             with paired bootstrap 95% intervals (hybrid - popularity) and by cuisine
    within   the same, but ranked only among dishes of the target's cuisine, as a strict
             single-cuisine profile sees them (the product filters before it ranks)
    meals    rank of the best meal containing it among all meals (ANCHOR vs MEAN
             aggregation vs popularity; experiments.meal_ablation)

Same split, protocol and metrics as experiments.py. A larger catalogue means more
candidates, so absolute HR@10 is not comparable across catalogues of different size;
compare each ranker with popularity on the SAME catalogue.

Usage (from apps/ai_system, needs the `ml` extra and the trained model):
    uv run --extra ml python -m savora_ai.core.recommendation.catalogue_eval \
        --interactions ../../Data/Food.com/RAW_interactions.csv \
        --catalogue-dir ../../Data/catalogue --model ../../Data/models/sasrec_content.pt \
        --output ../../docs/eval/v2/catalogue_evaluation.json
"""

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

import torch

from savora_ai.core.recommendation.baselines import PopularityOrder, full_rank
from savora_ai.core.recommendation.experiments import (
    bootstrap_difference,
    load_catalogue,
    meal_ablation,
    per_case,
)
from savora_ai.core.recommendation.metrics import rank_metrics
from savora_ai.core.recommendation.sequences import EvalCase, load_interactions, split
from savora_ai.core.recommendation.torch_model import (
    _RowsOnly,
    load,
    log_popularity,
    pick_device,
    weighted_ranks,
)


def by_cuisine_cases(cases: list[EvalCase], cuisine: dict[str, str]) -> dict[str, list[EvalCase]]:
    groups: dict[str, list[EvalCase]] = defaultdict(list)
    for case in cases:
        groups[cuisine.get(case.target, "(none)")].append(case)
    return groups


def run(
    interactions: Path, catalogue_dir: Path, model_path: Path, device: torch.device
) -> dict[str, object]:
    started = time.time()
    data = split(load_interactions(interactions))
    model, rows = load(model_path, device)
    index = _RowsOnly(rows)
    catalogue = load_catalogue(catalogue_dir)
    dishes = [d for d in catalogue.dish_ids if d in rows]
    in_catalogue = set(dishes)
    cases = [c for c in data.test if c.target in in_catalogue]
    weight = model.hybrid_weight
    log_pop = log_popularity(index.ids, data.train_counts)
    candidate_rows = torch.tensor([rows[d] for d in dishes])
    ranks = weighted_ranks(model, index, cases, log_pop, (0.0, weight), candidate_rows)  # type: ignore[arg-type]
    popularity = PopularityOrder.build(dishes, data.train_counts)
    pop_ranks = [full_rank({}, c.target, c.history, popularity) for c in cases]

    recipes = json.loads(
        sorted(catalogue_dir.glob("*_catalogue.json"))[-1].read_text(encoding="utf-8")
    )["recipes"]
    cuisine = {r["recipeId"]: (r["cuisines"] or ["(none)"])[0] for r in recipes}
    by_cuisine: dict[str, dict[str, list[int]]] = defaultdict(lambda: {"hybrid": [], "pop": []})
    for case, hybrid, pop in zip(cases, ranks[weight], pop_ranks, strict=True):
        by_cuisine[cuisine.get(case.target, "(none)")]["hybrid"].append(hybrid)
        by_cuisine[cuisine.get(case.target, "(none)")]["pop"].append(pop)

    within: dict[str, list[int]] = {"model": [], "hybrid": [], "popularity": []}
    for name, group in sorted(by_cuisine_cases(cases, cuisine).items()):
        pool = [d for d in dishes if cuisine.get(d) == name]
        pool_rows = torch.tensor([rows[d] for d in pool])
        group_ranks = weighted_ranks(model, index, group, log_pop, (0.0, weight), pool_rows)  # type: ignore[arg-type]
        order = PopularityOrder.build(pool, data.train_counts)
        within["model"] += group_ranks[0.0]
        within["hybrid"] += group_ranks[weight]
        within["popularity"] += [full_rank({}, c.target, c.history, order) for c in group]

    hybrid_cases, pop_cases = per_case(ranks[weight]), per_case(pop_ranks)
    within_hybrid, within_pop = per_case(within["hybrid"]), per_case(within["popularity"])
    return {
        "catalogue": {
            "directory": str(catalogue_dir),
            "foodcomDishes": len(catalogue.dish_ids),
            "dishesKnownToModel": len(dishes),
            "meals": len(catalogue.meals),
        },
        "protocol": {
            "split": data.report(),
            "cases": f"{len(cases)} test cases whose next recipe is a catalogue dish",
            "ranking": "among the catalogue's Food.com dishes; the user's history excluded",
            "hybridWeight": weight,
            "modelFile": model_path.name,
            "device": str(device),
            "minutes": round((time.time() - started) / 60, 1),
        },
        "dishes": {
            "model": rank_metrics(ranks[0.0]),
            "hybrid": rank_metrics(ranks[weight]),
            "popularity": rank_metrics(pop_ranks),
            "hybridVsPopularity": {
                k: bootstrap_difference(hybrid_cases[k], pop_cases[k]) for k in hybrid_cases
            },
            "byTargetCuisine": {
                c: {
                    "cases": len(v["hybrid"]),
                    "hybrid": rank_metrics(v["hybrid"]),
                    "popularity": rank_metrics(v["pop"]),
                }
                for c, v in sorted(by_cuisine.items())
            },
        },
        "withinCuisine": {
            **{k: rank_metrics(v) for k, v in within.items()},
            "hybridVsPopularity": {
                k: bootstrap_difference(within_hybrid[k], within_pop[k]) for k in within_hybrid
            },
        },
        "meals": meal_ablation(model, index, cases, log_pop, weight, catalogue),  # type: ignore[arg-type]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interactions", type=Path, required=True)
    parser.add_argument("--catalogue-dir", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    result = run(args.interactions, args.catalogue_dir, args.model, pick_device(args.device))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("catalogue", "withinCuisine")}, indent=2)[:3000])


if __name__ == "__main__":
    main()
