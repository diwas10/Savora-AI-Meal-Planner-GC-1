"""T4: public ranking API (ARCHITECTURE.md sections 7 and 9.2, ADR 0004 D5-D7).

    rank_recipes(history_recipe_ids, candidate_recipe_ids, user_context)
    rank_combinations(history_recipe_ids, candidate_combination_ids, user_context)

Guarantees:
- Only the SUPPLIED candidate IDs are scored and returned (they are already rule-safe).
- Scores are relative: a softmax within this candidate set, never nutrition, never a
  calibrated or clinical estimate. Raw output carries no portion or nutrition claim.
- No usable history, no trained model, or no torch -> popularity fallback, and the result
  says so in `modelVersion` and `fallbackReason`. Never a silent switch.
- History is the user's onboarding seed dishes (ADR 0004 D7); saved plans are never
  history or positive feedback.
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

POPULARITY_VERSION = "popularity-fallback-v1"


class _RankingModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        allow_inf_nan=False,
    )


class FallbackReason(StrEnum):
    NO_HISTORY = "NO_HISTORY"  # no history item the model knows
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"  # no trained model or no torch installed
    CANDIDATES_UNKNOWN_TO_MODEL = "CANDIDATES_UNKNOWN_TO_MODEL"  # model scores none of them


class Aggregation(StrEnum):
    """How a meal is scored from its dishes (ADR 0004 D6)."""

    ANCHOR = "ANCHOR"  # the main or breakfast base: the default
    MEAN = "MEAN"  # mean over the dishes the model can score: an ablation


class RankingContext(_RankingModel):
    slot_id: str | None = None  # e.g. "D2_LUNCH"; echoed back, not used for scoring


class RankedRecipe(_RankingModel):
    recipe_id: str
    rank: int = Field(ge=1)
    score: float = Field(ge=0, le=1)


class RankedCombination(_RankingModel):
    combination_id: str
    rank: int = Field(ge=1)
    score: float = Field(ge=0, le=1)


class RecipeRanking(_RankingModel):
    slot_id: str | None
    ranked_candidates: tuple[RankedRecipe, ...]
    model_version: str
    fallback_reason: FallbackReason | None = None
    # Candidates the model could not score: ranked after the scored ones, by popularity.
    unscored_candidates: tuple[str, ...] = ()


class CombinationRanking(_RankingModel):
    slot_id: str | None
    ranked_candidates: tuple[RankedCombination, ...]
    model_version: str
    aggregation: Aggregation
    fallback_reason: FallbackReason | None = None
    unscored_candidates: tuple[str, ...] = ()


class SequenceScorer(Protocol):
    """A trained sequential model behind a small, fake-able interface."""

    model_version: str

    def knows(self, recipe_id: str) -> bool: ...

    def score(self, history: Sequence[str], candidates: Sequence[str]) -> Mapping[str, float]:
        """Raw scores for the candidates it knows; history holds only known items."""
        ...


class PopularityScorer:
    """Training-period interaction counts (catalogue `trainingInteractions`)."""

    model_version = POPULARITY_VERSION

    def __init__(self, counts: Mapping[str, int]) -> None:
        self.counts = dict(counts)

    def knows(self, recipe_id: str) -> bool:
        return True

    def score(self, history: Sequence[str], candidates: Sequence[str]) -> Mapping[str, float]:
        del history
        return {c: math.log1p(self.counts.get(c, 0)) for c in candidates}


def popularity_from_catalogue(recipes: Iterable[Mapping[str, object]]) -> PopularityScorer:
    """Fallback built from a catalogue export's `recipes`: training counts, never held-out
    data; USDA staples (null counts) score 0 and are never ranked alone anyway."""
    counts: dict[str, int] = {}
    for recipe in recipes:
        count = recipe.get("trainingInteractions")
        if isinstance(count, int):
            counts[str(recipe["recipeId"])] = count
    return PopularityScorer(counts)


def load_scorer(
    path: Path, popularity_counts: Mapping[str, int] | None = None
) -> SequenceScorer | None:
    """The trained Transformer (the validated hybrid when training counts are given), or
    None if the file or the `ml` extra is missing."""
    if not path.exists():
        return None
    try:
        from savora_ai.core.recommendation.torch_model import TorchScorer
    except ImportError:
        return None
    return TorchScorer(path, popularity_counts)


def _softmax(raw: Mapping[str, float]) -> dict[str, float]:
    if not raw:
        return {}
    top = max(raw.values())
    exp = {k: math.exp(v - top) for k, v in raw.items()}
    total = sum(exp.values())
    return {k: v / total for k, v in exp.items()}


def _unique(ids: Sequence[str], kind: str) -> None:
    if not ids:
        raise ValueError(f"at least one candidate {kind} is required")
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate candidate {kind}s")


def _raw_scores(
    history: Sequence[str],
    dish_ids: Sequence[str],
    scorer: SequenceScorer | None,
    fallback: PopularityScorer,
) -> tuple[dict[str, float], str, FallbackReason | None]:
    if scorer is None:
        return (
            dict(fallback.score(history, dish_ids)),
            fallback.model_version,
            FallbackReason.MODEL_UNAVAILABLE,
        )
    known = [h for h in history if scorer.knows(h)]
    if not known:
        return (
            dict(fallback.score(history, dish_ids)),
            fallback.model_version,
            (FallbackReason.NO_HISTORY),
        )
    known_candidates = [d for d in dish_ids if scorer.knows(d)]
    if not known_candidates:  # never an arbitrary ID order under the model's name
        return (
            dict(fallback.score(history, dish_ids)),
            fallback.model_version,
            FallbackReason.CANDIDATES_UNKNOWN_TO_MODEL,
        )
    return dict(scorer.score(known, known_candidates)), scorer.model_version, None


def _order(
    scores: Mapping[str, float], ids: Sequence[str], popularity: Mapping[str, float]
) -> list[str]:
    """Scored IDs by score; unscored ones after them by popularity; then ID (deterministic)."""
    return sorted(
        ids, key=lambda i: (i not in scores, -scores.get(i, 0.0), -popularity.get(i, 0.0), i)
    )


def rank_recipes(
    history_recipe_ids: Sequence[str],
    candidate_recipe_ids: Sequence[str],
    user_context: RankingContext,
    *,
    scorer: SequenceScorer | None,
    fallback: PopularityScorer,
) -> RecipeRanking:
    """Standalone craving: rank rule-safe recipe IDs (no composer, no CSP)."""
    _unique(candidate_recipe_ids, "recipe")
    raw, version, reason = _raw_scores(history_recipe_ids, candidate_recipe_ids, scorer, fallback)
    scores = _softmax(raw)
    popularity = fallback.score([], candidate_recipe_ids)
    ordered = _order(scores, candidate_recipe_ids, popularity)
    return RecipeRanking(
        slot_id=user_context.slot_id,
        ranked_candidates=tuple(
            RankedRecipe(recipe_id=rid, rank=i + 1, score=round(scores.get(rid, 0.0), 6))
            for i, rid in enumerate(ordered)
        ),
        model_version=version,
        fallback_reason=reason,
        unscored_candidates=tuple(r for r in ordered if r not in scores),
    )


def combination_dishes(combination_id: str) -> tuple[str, ...]:
    """`C_<templateId>__<dishId>__...` -> dish IDs in slot order; the first is the anchor."""
    parts = combination_id.split("__")
    if len(parts) < 2 or not parts[0].startswith("C_"):
        raise ValueError(f"not a combination ID: {combination_id!r}")
    return tuple(parts[1:])


def rank_combinations(
    history_recipe_ids: Sequence[str],
    candidate_combination_ids: Sequence[str],
    user_context: RankingContext,
    *,
    scorer: SequenceScorer | None,
    fallback: PopularityScorer,
    aggregation: Aggregation = Aggregation.ANCHOR,
) -> CombinationRanking:
    """Planning: rank rule-safe combination IDs by their dishes' scores."""
    _unique(candidate_combination_ids, "combination")
    dishes = {cid: combination_dishes(cid) for cid in candidate_combination_ids}
    wanted = sorted({d for parts in dishes.values() for d in parts if d.startswith("FC_")})
    raw_dish, version, reason = _raw_scores(history_recipe_ids, wanted, scorer, fallback)
    raw: dict[str, float] = {}
    for cid, parts in dishes.items():
        if aggregation is Aggregation.ANCHOR:
            if parts[0] in raw_dish:
                raw[cid] = raw_dish[parts[0]]
        else:
            known = [raw_dish[d] for d in parts if d in raw_dish]
            if known:
                raw[cid] = sum(known) / len(known)
    scores = _softmax(raw)
    anchor_popularity = fallback.score([], [parts[0] for parts in dishes.values()])
    popularity = {cid: anchor_popularity.get(parts[0], 0.0) for cid, parts in dishes.items()}
    ordered = _order(scores, candidate_combination_ids, popularity)
    return CombinationRanking(
        slot_id=user_context.slot_id,
        ranked_candidates=tuple(
            RankedCombination(combination_id=cid, rank=i + 1, score=round(scores.get(cid, 0.0), 6))
            for i, cid in enumerate(ordered)
        ),
        model_version=version,
        aggregation=aggregation,
        fallback_reason=reason,
        unscored_candidates=tuple(c for c in ordered if c not in scores),
    )
