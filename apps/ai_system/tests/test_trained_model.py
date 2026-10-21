"""Behavioural tests of the SHIPPED trained model (skipped without torch or the file).

The model file is git-ignored (rebuilt by one command), so CI skips these; run locally
after training. They check properties a user would notice, not exact numbers.
"""

import csv
import json
import random
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

REPO = Path(__file__).parents[3]
MODEL = REPO / "Data/models/sasrec_content.pt"
RECIPES = REPO / "Data/Food.com/RAW_recipes.csv"
pytestmark = pytest.mark.skipif(
    not MODEL.exists() or not RECIPES.exists(), reason="trained model or raw data not present"
)

from savora_ai.core.food_data.foodcom_cuisines import normalize_tags  # noqa: E402
from savora_ai.core.recommendation.ranking import (  # noqa: E402
    PopularityScorer,
    RankingContext,
    load_scorer,
    rank_recipes,
)
from savora_ai.core.recommendation.torch_model import MODEL_VERSION, load  # noqa: E402


def catalogue_dishes() -> list[dict[str, object]]:
    path = sorted((REPO / "Data/catalogue").glob("*_catalogue.json"))[-1]
    return json.loads(path.read_text(encoding="utf-8"))["recipes"]


def tags_of(ids: set[str]) -> dict[str, frozenset[str]]:
    csv.field_size_limit(sys.maxsize)
    out: dict[str, frozenset[str]] = {}
    with RECIPES.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            rid = f"FC_{row['id']}"
            if rid in ids:
                out[rid] = normalize_tags(row["tags"])
    return out


def test_checkpoint_loads_safely_and_scores_deterministically() -> None:
    model, rows = load(MODEL)  # weights_only=True: tensors and plain containers only
    dishes = [str(d["recipeId"]) for d in catalogue_dishes() if str(d["recipeId"]) in rows]
    scorer = load_scorer(MODEL, {d: 10 for d in dishes})
    assert scorer is not None
    assert scorer.model_version == f"{MODEL_VERSION}+pop{model.hybrid_weight:g}"
    history, candidates = dishes[:2], dishes[2:30]
    first = scorer.score(history, candidates)
    assert first == scorer.score(history, candidates)
    assert set(first) == set(candidates)  # only the supplied IDs
    assert model.config.use_content and model.config.use_id


def test_ranking_api_with_the_real_model_returns_every_candidate_once() -> None:
    dishes = catalogue_dishes()
    counts = {str(d["recipeId"]): d["trainingInteractions"] or 0 for d in dishes}
    scorer = load_scorer(MODEL, counts)  # type: ignore[arg-type]
    fc = [str(d["recipeId"]) for d in dishes if str(d["recipeId"]).startswith("FC_")]
    result = rank_recipes(
        fc[:3],
        fc[3:],
        RankingContext(),
        scorer=scorer,
        fallback=PopularityScorer(counts),  # type: ignore[arg-type]
    )
    assert result.fallback_reason is None and result.model_version.startswith("sasrec")
    assert sorted(c.recipe_id for c in result.ranked_candidates) == sorted(fc[3:])
    assert [c.rank for c in result.ranked_candidates] == list(range(1, len(fc) - 2))


def test_content_vectors_place_indian_dishes_near_indian_dishes() -> None:
    """Nearest neighbours of Indian catalogue dishes are far more often Indian than chance."""
    model, rows = load(MODEL)
    sample = random.Random(7).sample(sorted(rows)[1:], 4000)
    dishes = [d for d in catalogue_dishes() if "Indian" in d["cuisines"]]  # type: ignore[operator]
    query = [str(d["recipeId"]) for d in dishes if str(d["recipeId"]) in rows][:10]
    tags = tags_of(set(sample) | set(query))
    pool = [r for r in sample if r in tags]
    base_rate = sum("indian" in tags[r] for r in pool) / len(pool)
    with torch.no_grad():
        vectors = model.item_vectors(torch.tensor([rows[r] for r in pool]))
        vectors = torch.nn.functional.normalize(vectors, dim=-1)
        hits = []
        for q in query:
            v = torch.nn.functional.normalize(model.item_vectors(torch.tensor([rows[q]])), dim=-1)
            nearest = torch.topk((vectors @ v.T).squeeze(-1), 20).indices.tolist()
            hits.append(sum("indian" in tags[pool[i]] for i in nearest) / 20)
    assert sum(hits) / len(hits) > 5 * base_rate  # Indian is ~2% of recipes
