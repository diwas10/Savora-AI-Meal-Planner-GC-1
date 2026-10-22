"""Private, operation-local recipe preparation; never accepts affirmative records.

Only original data enters the constructor. The computed pool lives in a closure,
not a transport DTO/cache argument. Every combination revalidates its ordinary
inputs and exact dependency bindings before lookup. Complete recipe assessments
(including FAIL/UNKNOWN and evidence) are retained unchanged. Composition, source,
roles and configuration checks still execute separately for every combination.

One immutable session needs at most one pool entry. Capacity zero disables storage;
discard evicts that entry without changing sources. Execution and checker create
separate sessions. Counters describe this phase only, not physical Python validators.
"""

from collections.abc import Callable
from typing import Any, final

from savora_ai.core.reasoning.filtering import _FilterRequest, filter_candidates
from savora_ai.schemas.candidates import CandidateRecipeFacts, RuleContext
from savora_ai.schemas.combinations import CombinationFacts
from savora_ai.schemas.filtering import FilterCandidatesResult
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot


class _PreparationInputs(_FilterRequest):
    sources: tuple[CombinationFacts, ...]


@final
class _PreparedRecipePool:
    __slots__ = ("__discard", "__fetch", "__seed", "__snapshot")
    __fetch: Callable[..., FilterCandidatesResult]
    __seed: Callable[[], FilterCandidatesResult]
    __discard: Callable[[], None]
    __snapshot: Callable[[], dict[str, Any]]

    def __init__(
        self,
        *,
        candidates: tuple[CandidateRecipeFacts, ...],
        knowledge: KnowledgeBaseSnapshot,
        context: RuleContext,
        sources: tuple[CombinationFacts, ...],
        capacity: int,
    ) -> None:
        if type(capacity) is not int or capacity not in (0, 1):
            raise ValueError("private preparation capacity must be exactly zero or one")
        inputs = _PreparationInputs(
            candidates=candidates, kb=knowledge, context=context, sources=sources
        )
        original_candidates = tuple(sorted(inputs.candidates, key=lambda c: c.recipe_id))
        cached: FilterCandidatesResult | None = None
        counts = dict(
            logical_candidate_assessments=0,
            physical_filter_calls=0,
            physical_candidate_assessments=0,
            reused_candidate_assessments=0,
            combination_evaluations=0,
            cache_validations=0,
            cache_hits=0,
            cache_misses=0,
            cache_evictions=0,
            cache_capacity=capacity,
            cache_entries=0,
        )

        def load() -> FilterCandidatesResult:
            nonlocal cached
            counts["logical_candidate_assessments"] += len(original_candidates)
            if cached is not None:
                counts["cache_hits"] += 1
                counts["reused_candidate_assessments"] += len(original_candidates)
                return cached
            counts["cache_misses"] += 1
            result = filter_candidates(
                original_candidates, knowledge=inputs.kb, context=inputs.context
            )
            counts["physical_filter_calls"] += 1
            counts["physical_candidate_assessments"] += len(original_candidates)
            if capacity:
                cached = result
                counts["cache_entries"] = 1
            return result

        def fetch(
            *,
            candidates: tuple[CandidateRecipeFacts, ...],
            knowledge: KnowledgeBaseSnapshot,
            context: RuleContext,
            source: CombinationFacts | None,
        ) -> FilterCandidatesResult:
            incoming = _FilterRequest(candidates=candidates, kb=knowledge, context=context)
            selected = CombinationFacts.model_validate(source) if source is not None else None
            if (
                incoming.kb != inputs.kb
                or incoming.context != inputs.context
                or tuple(sorted(incoming.candidates, key=lambda c: c.recipe_id))
                != original_candidates
                or (selected not in inputs.sources if inputs.sources else selected is not None)
            ):
                raise ValueError(
                    "prepared pool differs from exact original inputs/source/configuration"
                )
            counts["cache_validations"] += 1
            counts["combination_evaluations"] += 1
            return load()

        def discard() -> None:
            nonlocal cached
            if cached is not None:
                cached = None
                counts["cache_entries"] = 0
                counts["cache_evictions"] += 1

        object.__setattr__(self, "_PreparedRecipePool__fetch", fetch)
        object.__setattr__(self, "_PreparedRecipePool__seed", load)
        object.__setattr__(self, "_PreparedRecipePool__discard", discard)
        object.__setattr__(self, "_PreparedRecipePool__snapshot", lambda: dict(counts))

    def __setattr__(self, name: str, value: object) -> None:
        raise TypeError("prepared state is private and immutable")

    def assess(self) -> FilterCandidatesResult:
        return self.__seed()

    def recipes_for(
        self,
        *,
        candidates: tuple[CandidateRecipeFacts, ...],
        knowledge: KnowledgeBaseSnapshot,
        context: RuleContext,
        source: CombinationFacts | None,
    ) -> FilterCandidatesResult:
        if type(self) is not _PreparedRecipePool or not hasattr(self, "_PreparedRecipePool__fetch"):
            raise ValueError("prepared state must be locally computed from original data")
        return self.__fetch(
            candidates=candidates, knowledge=knowledge, context=context, source=source
        )

    def discard(self) -> None:
        self.__discard()

    def snapshot(self) -> dict[str, Any]:
        return self.__snapshot()
