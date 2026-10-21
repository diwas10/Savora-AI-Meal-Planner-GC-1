"""Bounded fixed-alternative selection. No portion generation, ranker or cache.

All work reservations include nested B1 execution/checking and outer proof replay.
Encoded proof/result pools are each 1 MiB, reused only for transient B1 material;
work and nested proof-record counters are cumulative and never reset per visit.
"""

import hashlib
from collections.abc import Callable
from time import monotonic
from typing import Any, Self, TypedDict

from pydantic import ValidationError, model_validator

from savora_ai.core.reasoning.combinations import evaluate_combination
from savora_ai.core.reasoning.day_checks import _slot_status
from savora_ai.core.reasoning.manifest import _mandatory_checks
from savora_ai.core.reasoning.planned_swap import _ref, _SwapInputs, validate_swap
from savora_ai.core.reasoning.swap_checks import _admit, _Interrupted, _Meter, _schedule
from savora_ai.schemas.candidates import CandidateRecipeFacts, RuleContext, _content_digest
from savora_ai.schemas.daily import MealOptionReference
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot
from savora_ai.schemas.planned_swap import (
    PlannedSwapRequest,
    PlannedSwapSourceSnapshot,
    PlannedSwapWorkflowBridge,
    SavedPlanLockInventory,
    SavedPlanMaterial,
    SwapBoundaryError,
    SwapReplacementDomain,
    SwapSelectionLimits,
    SwapTargetPermission,
    SwapValidationLimits,
    SwapWork,
    SyntheticSwapRanking,
    _fixed_meal_identity,
    _selection_digest,
)
from savora_ai.schemas.swap_proof import (
    ComputedSwapSelectionCertificate,
    ComputedSwapSelectionResult,
    SwapOutcome,
    SwapSelectionDisposition,
    SwapSelectionPrecheck,
    SwapSelectionReservation,
    SwapSelectionVisit,
    _SwapClaim,
    _SwapSelectionClaim,
)

_BYTES = 1_048_576
_B1_KEYS = (
    "request",
    "saved_plan",
    "locks",
    "permission",
    "candidates",
    "knowledge",
    "context",
    "sources",
    "bridge",
)


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


def _precheck(inputs: _SelectionInputs, option) -> SwapSelectionPrecheck:
    assessment = evaluate_combination(
        option.combination,
        candidates=inputs.candidates,
        knowledge=inputs.knowledge,
        context=inputs.context,
        trusted_combination=option.combination,
    )
    status, reason = _slot_status(option, inputs.request.target.slot, assessment.status)
    original = inputs.saved_plan.snapshot.slots[inputs.request.target.canonical_index].option
    lane = (
        "NO_OP" if _fixed_meal_identity(original) == _fixed_meal_identity(option) else status.value
    )
    return SwapSelectionPrecheck(
        option=option.reference,
        status=status,
        lane=lane,
        assessment_digest=_selection_digest(
            {
                "option": option,
                "assessment": assessment,
                "slot_status": status,
                "reason": reason,
            }
        ),
    )


def _ranked(inputs: _SelectionInputs, checks: tuple[SwapSelectionPrecheck, ...]):
    eligible = tuple(c.option for c in checks if c.lane == "PASS")
    digest = _selection_digest(
        {
            "policy": "synthetic-swap-hard-eligible-set.v1",
            "domain": inputs.domain.content_digest,
            "eligible": eligible,
        }
    )
    if digest != inputs.ranking.eligibility_digest or set(eligible) != set(inputs.ranking.eligible):
        raise SwapBoundaryError(
            "PIN_MISMATCH", "ranking differs from independently hard-eligible set"
        )
    order = tuple(
        e.option
        for e in sorted(inputs.ranking.entries, key=lambda e: (e.priority, e.option.option_id))
    )
    return digest, order, tuple(c.option for c in checks if c.lane == "UNKNOWN")


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


class _Ledger:
    def __init__(self, inputs: _SelectionInputs, guard: _Meter):
        self.inputs, self.guard = inputs, guard
        self.operations: list[SwapSelectionReservation] = []
        self.actual = SwapWork()
        self.finish = _regular("ENCODE", SwapWork(source_items=1))

    def reserve(self, record: SwapSelectionReservation, *, extra=None) -> None:
        self.guard.checkpoint()
        proposed = (*self.operations, record)
        held = (() if record.kind == "ENCODE" else (self.finish,)) + (
            () if extra is None else (extra,)
        )
        limits = self.inputs.limits
        all_records = proposed + held
        if (
            limits.max_proof_bytes < _BYTES
            or limits.max_result_bytes < _BYTES
            or sum(r.proof_records for r in all_records) > limits.max_proof_records
            or sum(r.validation_calls for r in all_records) > limits.max_full_validations
            or sum(r.execution.domain_visits for r in all_records) > limits.max_domain_visits
            or any(
                sum(getattr(r.reserved, n) for r in all_records)
                > getattr(limits.max_reserved_work, n)
                for n in SwapWork.model_fields
            )
        ):
            raise _Interrupted("RESERVATION")
        self.operations.append(record)

    def regular(self, record: SwapSelectionReservation) -> None:
        self.reserve(record)
        self.actual = _sum_work(self.actual, record.execution)

    def nested_actual(self, result: _SwapClaim) -> None:
        self.actual = _sum_work(self.actual, result.actual_execution, result.actual_verification)


def _note(result: _SwapClaim) -> SwapSelectionVisit:
    raw = result.model_dump_json(by_alias=True).encode()
    if result.outcome is SwapOutcome.TIMEOUT:
        raise _Interrupted("DEADLINE" if result.reason == "DEADLINE" else "RESERVATION")
    reason = result.reason
    if reason in ("RESERVATION", "DEADLINE"):
        raise ValueError("completed B1 visit cannot declare an interruption")
    return SwapSelectionVisit(
        option=result.replacement,
        outcome=result.outcome,
        failure_scope=result.failure_scope,
        reason=reason,
        validation_digest=hashlib.sha256(raw).hexdigest(),
        proof_bytes=result.proof_bytes,
        result_bytes=len(raw),
    )


def _dispositions(checks, visits):
    by_id = {v.option.option_id: v for v in visits}
    records = []
    for check in checks:
        if check.lane in ("FAIL", "NO_OP"):
            disposition = "HARD_FAIL" if check.lane == "FAIL" else "NO_OP"
        elif check.option.option_id not in by_id:
            disposition = "UNVISITED"
        else:
            outcome = by_id[check.option.option_id].outcome
            disposition = "SELECTED" if outcome is SwapOutcome.VALID else outcome.value
        records.append(SwapSelectionDisposition(option=check.option, disposition=disposition))
    return tuple(records)


def select_swap_replacement(
    request: PlannedSwapRequest,
    *,
    domain: SwapReplacementDomain,
    ranking: SyntheticSwapRanking,
    saved_plan: SavedPlanMaterial,
    locks: SavedPlanLockInventory,
    permission: SwapTargetPermission,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: PlannedSwapSourceSnapshot,
    bridge: PlannedSwapWorkflowBridge,
    limits: SwapSelectionLimits,
    clock: Callable[[], float] = monotonic,
) -> ComputedSwapSelectionResult:
    authority: dict[str, object] = dict(
        request=request,
        domain=domain,
        ranking=ranking,
        saved_plan=saved_plan,
        locks=locks,
        permission=permission,
        candidates=candidates,
        knowledge=knowledge,
        context=context,
        sources=sources,
        bridge=bridge,
        limits=limits,
    )
    inputs = _SelectionInputs.model_validate(authority)
    guard = _Meter(clock, limits.deadline, checker=False)

    def observed_clock() -> float:
        guard.checkpoint()
        assert guard.previous is not None
        return guard.previous

    ledger = _Ledger(inputs, guard)
    stage = "RESERVATION"
    checker_work = SwapWork()
    try:
        ledger.regular(_header(inputs))
        stage = "PRECHECK"
        pool = {o.reference.option_id: o for o in inputs.sources.options}
        checks = []
        for reference in inputs.domain.options:
            option = pool[reference.option_id]
            ledger.regular(_hard_cost(inputs, option))
            checks.append(_precheck(inputs, option))
            guard.checkpoint()
        checks = tuple(checks)
        stage = "RANKING"
        ledger.regular(
            _regular("ORDER", SwapWork(ordering_items=sum(c.lane == "PASS" for c in checks)))
        )
        eligible_digest, order, unknown = _ranked(inputs, checks)
        guard.checkpoint()
        visits = []
        final_note = final_certificate = selected = plan = None
        outcome, scope, reason = SwapOutcome.REJECTED, "DOMAIN", "ALL_EXCLUDED"
        locked = any(e.slot == request.target for e in inputs.locks.entries)
        if locked:
            scope, reason = "OPERATION", "TARGET_LOCKED"
        else:
            for reference in order + unknown:
                stage = "VALIDATION"
                record, inner = _nested(inputs, reference, "VISIT")
                final_record, final_inner = _nested(inputs, reference, "FINAL")
                ranked = reference in order
                ledger.reserve(record, extra=final_record if ranked else None)
                result = validate_swap(**inner, clock=observed_clock)
                ledger.nested_actual(result)
                note = _note(result)
                visits.append(note)
                guard.checkpoint()
                if result.reason == "BASELINE_INVALID":
                    outcome, scope, reason = SwapOutcome.REJECTED, "OPERATION", "BASELINE_INVALID"
                    break
                if result.outcome is SwapOutcome.VALID:
                    if not ranked:
                        raise ValueError("prerequisite UNKNOWN cannot become an eligible VALID")
                    stage = "FINAL_VALIDATION"
                    ledger.reserve(final_record)
                    final = validate_swap(**final_inner, clock=observed_clock)
                    ledger.nested_actual(final)
                    guard.checkpoint()
                    final_note = _note(final)
                    if final.outcome is not SwapOutcome.VALID:
                        raise ValueError(
                            "fresh final validation conflicts with the selected witness"
                        )
                    selected, plan, final_certificate = (
                        reference,
                        final.resulting_plan,
                        final.certificate,
                    )
                    outcome, scope, reason = SwapOutcome.VALID, None, "FIRST_VALID"
                    break
            else:
                if any(v.outcome is SwapOutcome.INSUFFICIENT_DATA for v in visits):
                    outcome, reason = SwapOutcome.INSUFFICIENT_DATA, "REQUIRED_FACT_UNKNOWN"
                elif not inputs.domain.options:
                    reason = "EMPTY_DOMAIN"
        stage = "ENCODING"
        ledger.regular(ledger.finish)
        visited = {v.option.option_id for v in visits}
        certificate = ComputedSwapSelectionCertificate(
            input_digest=_content_digest(inputs),
            eligibility_digest=eligible_digest,
            original_options=inputs.domain.options,
            prechecks=checks,
            eligible_order=order,
            unknown_order=unknown,
            dispositions=_dispositions(checks, visits),
            visits=tuple(visits),
            unvisited=tuple(r for r in order + unknown if r.option_id not in visited),
            reservations=tuple(ledger.operations),
            final_visit=final_note,
            final_certificate=final_certificate,
        )
        claim: dict[str, Any] = dict(
            request=request,
            domain=_ref(inputs.domain),
            ranking=_ref(inputs.ranking),
            limits=limits,
            outcome=outcome,
            failure_scope=scope,
            reason=reason,
            stage="COMPLETE",
            certificate=certificate,
            selected=selected,
            resulting_plan=plan,
            verification_complete=True,
            exhaustive=scope == "DOMAIN",
            actual_execution=ledger.actual,
            actual_verification=_sum_work(*(r.verification for r in ledger.operations)),
            proof_bytes=len(certificate.model_dump_json(by_alias=True).encode()),
        )
        parsed = _SwapSelectionClaim.model_validate(claim)
        if (
            parsed.proof_bytes > limits.max_proof_bytes
            or len(parsed.model_dump_json(by_alias=True).encode()) > limits.max_result_bytes
        ):
            raise _Interrupted("RESERVATION")
        guard.checkpoint()
        stage = "VERIFICATION"
        try:
            return ComputedSwapSelectionResult.model_validate(
                claim, context={"authority": authority, "clock": observed_clock}
            )
        except _Interrupted as error:
            checker_work = error.work
            raise
    except _Interrupted as error:
        return ComputedSwapSelectionResult(
            request=request,
            domain=_ref(inputs.domain),
            ranking=_ref(inputs.ranking),
            limits=limits,
            outcome=SwapOutcome.TIMEOUT,
            reason=error.reason,
            stage=stage,
            actual_execution=ledger.actual,
            actual_verification=checker_work,
        )
    except ValidationError as error:
        errors = error.errors()
        if not errors or not all(
            e["type"] == "value_error"
            and e["loc"] == ()
            and e["msg"] == "Value error, swap structural envelope exceeds 1 MiB"
            for e in errors
        ):
            raise
        return ComputedSwapSelectionResult(
            request=request,
            domain=_ref(inputs.domain),
            ranking=_ref(inputs.ranking),
            limits=limits,
            outcome=SwapOutcome.TIMEOUT,
            reason="RESERVATION",
            stage=stage,
            actual_execution=ledger.actual,
            actual_verification=checker_work,
        )
