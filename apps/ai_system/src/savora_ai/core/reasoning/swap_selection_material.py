"""Shared selection admission and source-derived accounting.

This layer imports neither the selector nor verification-backed result models.
"""

from typing import Self, TypedDict

from pydantic import model_validator

from savora_ai.core.reasoning.manifest import _mandatory_checks
from savora_ai.core.reasoning.swap_checks import _admit, _Interrupted, _schedule
from savora_ai.core.reasoning.swap_material import _SwapInputs
from savora_ai.schemas.candidates import CandidateRecipeFacts, RuleContext
from savora_ai.schemas.daily import MealOptionReference
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot
from savora_ai.schemas.planned_swap import (
    PlannedSwapRequest,
    PlannedSwapSourceSnapshot,
    PlannedSwapWorkflowBridge,
    SavedPlanLockInventory,
    SavedPlanMaterial,
    SwapReplacementDomain,
    SwapSelectionLimits,
    SwapTargetPermission,
    SwapValidationLimits,
    SwapWork,
    SyntheticSwapRanking,
    _fixed_meal_identity,
    _selection_digest,
)
from savora_ai.schemas.swap_proof_types import (
    SwapSelectionReservation,
)

_BYTES = 1_048_576


class _SelectionInputs(_SwapInputs):
    domain: SwapReplacementDomain
    ranking: SyntheticSwapRanking
    candidates: tuple[CandidateRecipeFacts, ...]
    limits: SwapSelectionLimits

    @model_validator(mode="after")
    def selection_authority(self) -> Self:
        if (
            self.domain.request != self.request
            or self.domain.sources != self.sources
            or self.ranking.domain != self.domain
            or self.candidates != self.sources.candidates
        ):
            raise ValueError("selection differs from independent domain/ranking/source authority")
        versions = {
            "synthetic-fixed-combination-rank.v1": "synthetic-fixed-combination-rank.v1",
            "CANONICAL_OPTION_ID": "canonical-option-id.v1",
        }
        if self.ranking.ranker_version != versions[self.ranking.policy]:
            raise ValueError("unsupported synthetic ranker/source version binding")
        if self.ranking.policy == "CANONICAL_OPTION_ID" and any(
            e.priority != 0 for e in self.ranking.entries
        ):
            raise ValueError("canonical ranking requires exact zero-priority declaration")
        pool = {o.reference.option_id: o for o in self.sources.options}
        identities = [
            _selection_digest({"fixed": _fixed_meal_identity(pool[r.option_id])})
            for r in self.domain.options
        ]
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate semantic alternatives cannot inflate the original domain")
        return self


def _sum_work(*costs: SwapWork) -> SwapWork:
    values = {n: sum(getattr(c, n) for c in costs) for n in SwapWork.model_fields}
    if any(v > 1_000_000 for v in values.values()):
        raise _Interrupted("RESERVATION")
    return SwapWork(**values)


def _regular(kind, cost: SwapWork, option=None) -> SwapSelectionReservation:
    verification = _sum_work(cost, SwapWork(checker_steps=1))
    return SwapSelectionReservation(
        kind=kind,
        option=option,
        execution=cost,
        verification=verification,
        reserved=_sum_work(cost, verification),
        proof_records=1,
    )


def _header(inputs: _SelectionInputs) -> SwapSelectionReservation:
    return _regular(
        "HEADER",
        SwapWork(
            source_items=23
            + len(inputs.candidates)
            + len(inputs.sources.options)
            + len(inputs.saved_plan.snapshot.original_candidates),
            bridge_items=len(inputs.bridge.mappings),
            lock_comparisons=21 + len(inputs.locks.entries),
        ),
    )


def _hard_cost(inputs: _SelectionInputs, option) -> SwapSelectionReservation:
    rules = _mandatory_checks(inputs.knowledge, inputs.context)
    return _regular(
        "HARD_CHECK",
        SwapWork(
            source_items=len(option.combination.components),
            candidate_preparations=len(inputs.candidates),
            combination_preparations=1,
            predicate_obligations=len(inputs.candidates)
            * sum(r.scope.value in ("PROFILE", "RECIPE") for r in rules)
            + sum(r.scope.value == "COMBINATION" for r in rules),
            domain_visits=1,
        ),
        option.reference,
    )


class _B1Arguments(TypedDict):
    request: PlannedSwapRequest
    replacement: MealOptionReference
    saved_plan: SavedPlanMaterial
    locks: SavedPlanLockInventory
    permission: SwapTargetPermission
    candidates: tuple[CandidateRecipeFacts, ...]
    knowledge: KnowledgeBaseSnapshot
    context: RuleContext
    sources: PlannedSwapSourceSnapshot
    bridge: PlannedSwapWorkflowBridge
    limits: SwapValidationLimits


def _nested(
    inputs: _SelectionInputs, option: MealOptionReference, kind
) -> tuple[SwapSelectionReservation, _B1Arguments]:
    # This is a bounded structural cost derivation, not predicate evaluation.
    limits = SwapValidationLimits(
        max_reserved_work=SwapWork(**{n: 1_000_000 for n in SwapWork.model_fields}),
        max_proof_records=1024,
        max_proof_bytes=_BYTES,
        max_result_bytes=_BYTES,
        max_full_validations=1,
        deadline=inputs.limits.deadline,
    )
    authority = _B1Arguments(
        request=inputs.request,
        replacement=option,
        saved_plan=inputs.saved_plan,
        locks=inputs.locks,
        permission=inputs.permission,
        candidates=inputs.candidates,
        knowledge=inputs.knowledge,
        context=inputs.context,
        sources=inputs.sources,
        bridge=inputs.bridge,
        limits=limits,
    )
    schedule = _schedule(_admit(dict(authority)))
    # The real B1 invocation receives only its allocated share, never a free
    # independent copy of the caller's total outer work capacity.
    limits = limits.model_copy(
        update={
            "max_reserved_work": _sum_work(schedule.execution, schedule.verification),
            "max_proof_records": len(schedule.plan.operations),
        }
    )
    authority["limits"] = limits
    execution = _sum_work(schedule.execution, schedule.verification)
    verification = _sum_work(schedule.verification, SwapWork(checker_steps=1))
    if len(schedule.plan.operations) >= 1024:
        raise _Interrupted("RESERVATION")
    record = SwapSelectionReservation(
        kind=kind,
        option=option,
        execution=execution,
        verification=verification,
        reserved=_sum_work(execution, verification),
        proof_records=1 + len(schedule.plan.operations),
        validation_calls=1,
    )
    return record, authority
