"""Independent full-source reconstruction of a single-swap claim.

Never calls validate_swap, its phase executor, a weekly solver, an incremental
kernel or a prepared recipe cache. Stateless combination and aggregate primitive
assessments are shared; traversal, source selection, verdict and plan assembly
are reconstructed here from separately supplied roots.
"""

import hashlib
from collections.abc import Callable
from time import monotonic
from typing import Literal

from pydantic import ValidationError

from savora_ai.core.reasoning.day_checks import _slot_status
from savora_ai.core.reasoning.planned_swap import _ref
from savora_ai.core.reasoning.swap_checks import (
    _admit,
    _aggregate_cost,
    _assess_aggregate,
    _assess_option,
    _binding_cost,
    _input_digest,
    _Inputs,
    _Interrupted,
    _Meter,
    _option_cost,
    _schedule,
)
from savora_ai.schemas.candidates import CandidateRecipeFacts, RuleContext, _content_digest
from savora_ai.schemas.daily import MealOptionReference
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot
from savora_ai.schemas.planned_swap import (
    PlannedSwapRequest,
    PlannedSwapSourceSnapshot,
    PlannedSwapWorkflowBridge,
    SavedPlanLockInventory,
    SavedPlanMaterial,
    SavedSlotPayload,
    SwapPlanSnapshot,
    SwapReplacementDomain,
    SwapSelectionLimits,
    SwapTargetPermission,
    SwapValidationLimits,
    SwapWork,
    SyntheticSwapRanking,
    _fixed_meal_identity,
    _selection_digest,
)
from savora_ai.schemas.reasoning import RuleStatus
from savora_ai.schemas.swap_proof import (
    ComputedSwapCertificate,
    ComputedSwapSelectionCertificate,
    ComputedSwapSelectionResult,
    ComputedSwapValidationResult,
    SwapOutcome,
    SwapPhaseAssessment,
    SwapProofCheck,
    SwapSelectionDisposition,
    SwapSelectionPrecheck,
    SwapSelectionVisit,
    _SwapClaim,
    _SwapSelectionClaim,
)


def _replay_validation_claim(
    authority: dict[str, object], clock: Callable[[], float]
) -> tuple[_SwapClaim, SwapWork]:
    """Rebuild a compact selection visit using the independent B1 traversal.

    No execution API or cached affirmative verdict is used. The complete claim
    exists only transiently and is compared by ordered wire digest by B2.
    """
    inputs = _admit(authority)
    meter = _Meter(clock, inputs.limits.deadline, checker=True)
    try:
        schedule = _schedule(inputs)
        meter.start(_binding_cost(inputs))
        inputs = _admit(authority)
        meter.checkpoint()
        original, resulting, outcome, scope, reason, plan = _reconstruct_swap(inputs, meter)
        certificate = ComputedSwapCertificate(
            input_digest=_input_digest(inputs),
            reservations=schedule.plan,
            original=original,
            result=resulting,
        )
        claim = _SwapClaim(
            request=inputs.request,
            replacement=inputs.replacement,
            limits=inputs.limits,
            stage="COMPLETE",
            outcome=outcome,
            failure_scope=scope,
            reason=reason,
            certificate=certificate,
            resulting_plan=plan,
            verification_complete=True,
            actual_execution=schedule.execution,
            actual_verification=schedule.verification,
            proof_bytes=len(certificate.model_dump_json(by_alias=True).encode()),
        )
        if (
            claim.proof_bytes > inputs.limits.max_proof_bytes
            or len(claim.model_dump_json(by_alias=True).encode()) > inputs.limits.max_result_bytes
        ):
            raise _Interrupted("RESERVATION", meter.work)
        meter.checkpoint()
        return claim, meter.work
    except ValidationError as error:
        errors = error.errors()
        if not errors or not all(
            e["type"] == "value_error"
            and e["loc"] == ()
            and e["msg"] == "Value error, swap structural envelope exceeds 1 MiB"
            for e in errors
        ):
            raise
        raise _Interrupted("RESERVATION", meter.work) from error


def _reconstruct_swap(
    inputs: _Inputs, meter: _Meter
) -> tuple[
    SwapPhaseAssessment,
    SwapPhaseAssessment,
    SwapOutcome,
    Literal["OPERATION", "CANDIDATE"] | None,
    Literal[
        "TARGET_LOCKED",
        "NO_OP",
        "BASELINE_INVALID",
        "RESULT_FAILED",
        "REQUIRED_FACT_UNKNOWN",
        "COMPLETE_PASS",
    ],
    SwapPlanSnapshot | None,
]:
    """Independent B1 reconstruction; shared only by independent proof checkers."""
    records = []
    for phase in ("ORIGINAL", "RESULT"):
        chosen = []
        for old in inputs.saved_plan.snapshot.slots:
            if phase == "ORIGINAL":
                chosen.append(old.option)
            else:
                if old.identity == inputs.request.target:
                    reference = inputs.replacement
                else:
                    reference = next(
                        m.projected
                        for m in inputs.bridge.mappings
                        if m.original == old.option.reference
                    )
                chosen.append(next(o for o in inputs.sources.options if o.reference == reference))
        decisions = []
        seen = set()
        for option in chosen:
            if option.reference.option_id in seen:
                continue
            seen.add(option.reference.option_id)
            meter.start(_option_cost(inputs, phase, option))
            decisions.append(_assess_option(inputs, phase, option))
            meter.checkpoint()
        options = tuple(decisions)
        by_id = {d.option.option_id: d.combination.status for d in decisions}
        states = tuple(
            _slot_status(option, old.identity.slot, by_id[option.reference.option_id])[0]
            for old, option in zip(inputs.saved_plan.snapshot.slots, chosen, strict=True)
        )
        days = []
        for index in range(7):
            meter.start(_aggregate_cost(inputs, phase, "DAY"))
            days.append(
                _assess_aggregate(
                    inputs,
                    phase,
                    "DAY",
                    index + 1,
                    tuple(chosen[index * 3 : index * 3 + 3]),
                    states[index * 3 : index * 3 + 3],
                    options,
                )
            )
            meter.checkpoint()
        meter.start(_aggregate_cost(inputs, phase, "WEEK"))
        week = _assess_aggregate(
            inputs, phase, "WEEK", 0, tuple(chosen), tuple(d.status for d in days), options
        )
        meter.checkpoint()
        records.append(
            SwapPhaseAssessment(
                phase=phase, options=options, slots=states, days=tuple(days), week=week
            )
        )
    meter.start(SwapWork(full_validations=1))
    original, resulting = records
    target = inputs.request.target.canonical_index
    old = inputs.saved_plan.snapshot.slots[target]
    replacement = next(o for o in inputs.sources.options if o.reference == inputs.replacement)
    plan = None
    if any(lock.slot == old.identity for lock in inputs.locks.entries):
        outcome, scope, reason = SwapOutcome.REJECTED, "OPERATION", "TARGET_LOCKED"
    elif _fixed_meal_identity(old.option) == _fixed_meal_identity(replacement):
        outcome, scope, reason = SwapOutcome.REJECTED, "OPERATION", "NO_OP"
    elif original.week.status is RuleStatus.FAIL:
        outcome, scope, reason = SwapOutcome.REJECTED, "OPERATION", "BASELINE_INVALID"
    elif resulting.week.status is RuleStatus.FAIL:
        outcome, scope, reason = SwapOutcome.REJECTED, "CANDIDATE", "RESULT_FAILED"
    elif RuleStatus.UNKNOWN in (original.week.status, resulting.week.status):
        outcome, scope, reason = (
            SwapOutcome.INSUFFICIENT_DATA,
            "OPERATION" if original.week.status is RuleStatus.UNKNOWN else "CANDIDATE",
            "REQUIRED_FACT_UNKNOWN",
        )
    else:
        outcome, scope, reason = SwapOutcome.VALID, None, "COMPLETE_PASS"
        # Independently assemble exactly one payload; no executor plan used.
        slots = tuple(
            SavedSlotPayload(
                identity=slot.identity,
                source=_ref(inputs.sources),
                option=replacement,
                recipes=tuple(
                    c
                    for c in inputs.candidates
                    if c.recipe_id
                    in {p.recipe_snapshot.recipe_id for p in replacement.combination.components}
                ),
            )
            if index == target
            else slot
            for index, slot in enumerate(inputs.saved_plan.snapshot.slots)
        )
        plan = SwapPlanSnapshot.build(
            dict(
                base=inputs.saved_plan,
                request=inputs.request,
                sources=inputs.sources,
                projected_replacement=inputs.replacement,
                slots=slots,
            )
        )
    return original, resulting, outcome, scope, reason, plan


def _check_claim(
    claim: _SwapClaim, *, clock: Callable[[], float], **authority: object
) -> SwapProofCheck:
    # Admission errors describe caller/root conflicts, never semantic REJECTED.
    inputs = _admit(authority)
    meter = _Meter(clock, inputs.limits.deadline, checker=True)
    try:
        schedule = _schedule(inputs)
        meter.start(_binding_cost(inputs))
        # Revalidate every original/bridge/authority payload, not a retained
        # certificate's roots or its self-computed hash.
        inputs = _admit(authority)
        meter.checkpoint()
        try:
            if type(claim) not in (_SwapClaim, ComputedSwapValidationResult):
                raise ValueError("proof requires an ordinary computed claim")
            parsed = _SwapClaim.model_validate(dict(vars(claim)))
        except (ValidationError, ValueError):
            return SwapProofCheck(
                accepted=False, complete=True, reason="MISMATCH", actual_verification=meter.work
            )
        certificate = parsed.certificate
        if parsed.outcome is SwapOutcome.TIMEOUT:
            return SwapProofCheck(
                accepted=False,
                complete=False,
                reason="UNVERIFIED_TIMEOUT",
                actual_verification=meter.work,
            )
        if (
            certificate is None
            or certificate.input_digest != _input_digest(inputs)
            or certificate.reservations != schedule.plan
        ):
            return SwapProofCheck(
                accepted=False, complete=True, reason="MISMATCH", actual_verification=meter.work
            )
        original, resulting, outcome, scope, reason, plan = _reconstruct_swap(inputs, meter)
        proof_bytes = len(certificate.model_dump_json(by_alias=True).encode())
        matches = (
            original == certificate.original
            and resulting == certificate.result
            and (parsed.outcome, parsed.failure_scope, parsed.reason) == (outcome, scope, reason)
            and parsed.resulting_plan == plan
            and parsed.request == inputs.request
            and parsed.replacement == inputs.replacement
            and parsed.limits == inputs.limits
            and parsed.stage == "COMPLETE"
            and parsed.actual_execution == schedule.execution
            and parsed.actual_verification == schedule.verification
            and parsed.actual_verification == meter.work
            and parsed.proof_bytes == proof_bytes
            and proof_bytes <= inputs.limits.max_proof_bytes
            and len(parsed.model_dump_json(by_alias=True).encode())
            <= inputs.limits.max_result_bytes
        )
        meter.checkpoint()
        return SwapProofCheck(
            accepted=matches,
            complete=True,
            reason="VERIFIED" if matches else "MISMATCH",
            outcome=outcome,
            actual_verification=meter.work,
        )
    except _Interrupted as error:
        return SwapProofCheck(
            accepted=False, complete=False, reason=error.reason, actual_verification=meter.work
        )
    except ValidationError as error:
        # Initial authoritative admission is outside this resource handler.
        # A bounded reconstructed output may not fit even though its inputs do.
        # Only that exact root overflow is incomplete verification; unrelated
        # or mixed structural/policy errors must retain their original failure.
        errors = error.errors()
        if not errors or not all(
            e["type"] == "value_error"
            and e["loc"] == ()
            and e["msg"] == "Value error, swap structural envelope exceeds 1 MiB"
            for e in errors
        ):
            raise
        return SwapProofCheck(
            accepted=False, complete=False, reason="RESERVATION", actual_verification=meter.work
        )


def verify_swap_validation(
    result: ComputedSwapValidationResult,
    *,
    request: PlannedSwapRequest,
    replacement: MealOptionReference,
    saved_plan: SavedPlanMaterial,
    locks: SavedPlanLockInventory,
    permission: SwapTargetPermission,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: PlannedSwapSourceSnapshot,
    bridge: PlannedSwapWorkflowBridge,
    limits: SwapValidationLimits,
    clock: Callable[[], float] = monotonic,
) -> SwapProofCheck:
    """Check a hostile claim against independent roots; accepted means proof-valid.

    A verified REJECTED/INSUFFICIENT_DATA certificate may be proof-valid while
    never authorizing a plan. External root conflicts raise boundary validation.
    """
    return _check_claim(
        result,
        request=request,
        replacement=replacement,
        saved_plan=saved_plan,
        locks=locks,
        permission=permission,
        candidates=candidates,
        knowledge=knowledge,
        context=context,
        sources=sources,
        bridge=bridge,
        limits=limits,
        clock=clock,
    )


def _check_selection_claim(
    claim: _SwapSelectionClaim, *, clock: Callable[[], float], **authority: object
) -> SwapProofCheck:
    """Independent domain/eligibility/prefix reconstruction; never the selector.

    Shared helpers below describe typed admission and source-derived cost units.
    Hard classification, ranking, traversal, coverage and verdict are rebuilt here.
    Nested visits use the independent B1 replay, not validate_swap or its executor.
    """
    from savora_ai.core.reasoning.combinations import evaluate_combination
    from savora_ai.core.reasoning.swap_selection import (
        _hard_cost,
        _header,
        _nested,
        _regular,
        _SelectionInputs,
        _sum_work,
    )

    inputs = _SelectionInputs.model_validate(authority)
    guard = _Meter(clock, inputs.limits.deadline, checker=True)
    actual = SwapWork()
    operations = []
    finish = _regular("ENCODE", SwapWork(source_items=1))

    def observed_clock() -> float:
        guard.checkpoint()
        assert guard.previous is not None
        return guard.previous

    def reserve(record, extra=None):
        guard.checkpoint()
        prospective = [*operations, record]
        if record.kind != "ENCODE":
            prospective.append(finish)
        if extra is not None:
            prospective.append(extra)
        limits = inputs.limits
        if (
            limits.max_proof_bytes != 1_048_576
            or limits.max_result_bytes != 1_048_576
            or sum(r.proof_records for r in prospective) > limits.max_proof_records
            or sum(r.validation_calls for r in prospective) > limits.max_full_validations
            or sum(r.execution.domain_visits for r in prospective) > limits.max_domain_visits
            or any(
                sum(getattr(r.reserved, key) for r in prospective)
                > getattr(limits.max_reserved_work, key)
                for key in SwapWork.model_fields
            )
        ):
            raise _Interrupted("RESERVATION")
        operations.append(record)

    def regular(record):
        nonlocal actual
        reserve(record)
        actual = _sum_work(actual, record.verification)

    def note_for(result):
        raw = result.model_dump_json(by_alias=True).encode()
        return SwapSelectionVisit(
            option=result.replacement,
            outcome=result.outcome,
            failure_scope=result.failure_scope,
            reason=result.reason,
            validation_digest=hashlib.sha256(raw).hexdigest(),
            proof_bytes=result.proof_bytes,
            result_bytes=len(raw),
        )

    try:
        regular(_header(inputs))
        try:
            if type(claim) not in (_SwapSelectionClaim, ComputedSwapSelectionResult):
                raise ValueError("selection proof requires an ordinary computed claim")
            parsed = _SwapSelectionClaim.model_validate(dict(vars(claim)))
        except (ValidationError, ValueError):
            return SwapProofCheck(
                accepted=False, complete=True, reason="MISMATCH", actual_verification=actual
            )
        if parsed.outcome is SwapOutcome.TIMEOUT:
            return SwapProofCheck(
                accepted=False,
                complete=False,
                reason="UNVERIFIED_TIMEOUT",
                actual_verification=actual,
            )
        supplied = parsed.certificate
        if supplied is None or supplied.input_digest != _content_digest(inputs):
            return SwapProofCheck(
                accepted=False, complete=True, reason="MISMATCH", actual_verification=actual
            )
        checks = []
        for reference in inputs.domain.options:
            option = next(o for o in inputs.sources.options if o.reference == reference)
            regular(_hard_cost(inputs, option))
            decision = evaluate_combination(
                option.combination,
                candidates=inputs.candidates,
                knowledge=inputs.knowledge,
                context=inputs.context,
                trusted_combination=option.combination,
            )
            status, why = _slot_status(option, inputs.request.target.slot, decision.status)
            old = inputs.saved_plan.snapshot.slots[inputs.request.target.canonical_index].option
            if _fixed_meal_identity(old) == _fixed_meal_identity(option):
                lane = "NO_OP"
            elif status is RuleStatus.FAIL:
                lane = "FAIL"
            elif status is RuleStatus.UNKNOWN:
                lane = "UNKNOWN"
            else:
                lane = "PASS"
            checks.append(
                SwapSelectionPrecheck(
                    option=reference,
                    status=status,
                    lane=lane,
                    assessment_digest=_selection_digest(
                        {
                            "option": option,
                            "assessment": decision,
                            "slot_status": status,
                            "reason": why,
                        }
                    ),
                )
            )
            guard.checkpoint()
        eligible = tuple(c.option for c in checks if c.lane == "PASS")
        unknown = tuple(c.option for c in checks if c.lane == "UNKNOWN")
        regular(_regular("ORDER", SwapWork(ordering_items=len(eligible))))
        eligible_digest = _selection_digest(
            {
                "policy": "synthetic-swap-hard-eligible-set.v1",
                "domain": inputs.domain.content_digest,
                "eligible": eligible,
            }
        )
        if eligible_digest != inputs.ranking.eligibility_digest or set(eligible) != set(
            inputs.ranking.eligible
        ):
            raise ValueError("ranking differs from independently hard-eligible set")
        ranked = tuple(
            e.option
            for e in sorted(inputs.ranking.entries, key=lambda e: (e.priority, e.option.option_id))
        )
        visits = []
        selected = plan = final_visit = final_certificate = None
        outcome, scope, reason = SwapOutcome.REJECTED, "DOMAIN", "ALL_EXCLUDED"
        if any(lock.slot == inputs.request.target for lock in inputs.locks.entries):
            scope, reason = "OPERATION", "TARGET_LOCKED"
        else:
            for reference in (*ranked, *unknown):
                frame, inner = _nested(inputs, reference, "VISIT")
                final_frame, final_inner = _nested(inputs, reference, "FINAL")
                is_ranked = reference in ranked
                reserve(frame, extra=final_frame if is_ranked else None)
                actual = _sum_work(actual, SwapWork(checker_steps=1))
                try:
                    reconstructed, work = _replay_validation_claim(dict(inner), observed_clock)
                except _Interrupted as error:
                    actual = _sum_work(actual, error.work)
                    raise
                actual = _sum_work(actual, work)
                visits.append(note_for(reconstructed))
                guard.checkpoint()
                if reconstructed.reason == "BASELINE_INVALID":
                    outcome, scope, reason = SwapOutcome.REJECTED, "OPERATION", "BASELINE_INVALID"
                    break
                if reconstructed.outcome is SwapOutcome.VALID:
                    if not is_ranked:
                        raise ValueError("UNKNOWN prerequisite cannot authorize selected VALID")
                    selected = reference
                    reserve(final_frame)
                    actual = _sum_work(actual, SwapWork(checker_steps=1))
                    # A fresh public B1 checker independently verifies the retained
                    # final evidence against the same separately supplied roots.
                    final_certificate = supplied.final_certificate
                    if final_certificate is None:
                        return SwapProofCheck(
                            accepted=False,
                            complete=True,
                            reason="MISMATCH",
                            actual_verification=actual,
                        )
                    allocation = _schedule(_admit(dict(final_inner)))
                    final_claim = _SwapClaim(
                        request=inputs.request,
                        replacement=reference,
                        limits=final_inner["limits"],
                        stage="COMPLETE",
                        outcome=SwapOutcome.VALID,
                        reason="COMPLETE_PASS",
                        certificate=final_certificate,
                        resulting_plan=parsed.resulting_plan,
                        verification_complete=True,
                        actual_execution=allocation.execution,
                        actual_verification=allocation.verification,
                        proof_bytes=len(final_certificate.model_dump_json(by_alias=True).encode()),
                    )
                    report = _check_claim(final_claim, **final_inner, clock=observed_clock)
                    actual = _sum_work(actual, report.actual_verification)
                    if not report.accepted:
                        if not report.complete and report.reason in ("DEADLINE", "RESERVATION"):
                            raise _Interrupted(report.reason)
                        return SwapProofCheck(
                            accepted=False,
                            complete=True,
                            reason="MISMATCH",
                            actual_verification=actual,
                        )
                    final_visit, plan = note_for(final_claim), parsed.resulting_plan
                    outcome, scope, reason = SwapOutcome.VALID, None, "FIRST_VALID"
                    break
            else:
                if any(v.outcome is SwapOutcome.INSUFFICIENT_DATA for v in visits):
                    outcome, reason = SwapOutcome.INSUFFICIENT_DATA, "REQUIRED_FACT_UNKNOWN"
                elif not inputs.domain.options:
                    reason = "EMPTY_DOMAIN"
        regular(finish)
        by_id = {v.option.option_id: v for v in visits}
        dispositions = []
        for check in checks:
            if check.lane == "FAIL":
                disposition = "HARD_FAIL"
            elif check.lane == "NO_OP":
                disposition = "NO_OP"
            elif check.option.option_id not in by_id:
                disposition = "UNVISITED"
            elif by_id[check.option.option_id].outcome is SwapOutcome.VALID:
                disposition = "SELECTED"
            else:
                disposition = by_id[check.option.option_id].outcome.value
            dispositions.append(
                SwapSelectionDisposition(option=check.option, disposition=disposition)
            )
        expected = ComputedSwapSelectionCertificate(
            input_digest=_content_digest(inputs),
            eligibility_digest=eligible_digest,
            original_options=inputs.domain.options,
            prechecks=tuple(checks),
            eligible_order=ranked,
            unknown_order=unknown,
            dispositions=tuple(dispositions),
            visits=tuple(visits),
            unvisited=tuple(r for r in ranked + unknown if r.option_id not in by_id),
            reservations=tuple(operations),
            final_visit=final_visit,
            final_certificate=final_certificate,
        )
        expected_execution = _sum_work(*(op.execution for op in operations))
        expected_verification = _sum_work(*(op.verification for op in operations))
        matches = (
            supplied == expected
            and parsed.request == inputs.request
            and parsed.domain == _ref(inputs.domain)
            and parsed.ranking == _ref(inputs.ranking)
            and parsed.limits == inputs.limits
            and parsed.stage == "COMPLETE"
            and (parsed.outcome, parsed.failure_scope, parsed.reason) == (outcome, scope, reason)
            and parsed.selected == selected
            and parsed.resulting_plan == plan
            and parsed.exhaustive == (scope == "DOMAIN")
            and parsed.actual_execution == expected_execution
            and parsed.actual_verification == expected_verification == actual
            and parsed.proof_bytes == len(expected.model_dump_json(by_alias=True).encode())
            and parsed.proof_bytes <= inputs.limits.max_proof_bytes
            and len(parsed.model_dump_json(by_alias=True).encode())
            <= inputs.limits.max_result_bytes
        )
        guard.checkpoint()
        return SwapProofCheck(
            accepted=matches,
            complete=True,
            reason="VERIFIED" if matches else "MISMATCH",
            outcome=outcome,
            actual_verification=actual,
        )
    except _Interrupted as error:
        return SwapProofCheck(
            accepted=False, complete=False, reason=error.reason, actual_verification=actual
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
        return SwapProofCheck(
            accepted=False, complete=False, reason="RESERVATION", actual_verification=actual
        )


def verify_swap_selection(
    result: ComputedSwapSelectionResult,
    *,
    request: PlannedSwapRequest,
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
) -> SwapProofCheck:
    return _check_selection_claim(
        result,
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
        clock=clock,
    )
