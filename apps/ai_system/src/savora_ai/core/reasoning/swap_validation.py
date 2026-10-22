"""Single fixed-swap execution; mandatory independent replay is unchanged."""

from collections.abc import Callable
from time import monotonic

from pydantic import ValidationError

from savora_ai.core.reasoning.swap_proof import ComputedSwapValidationResult
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    RuleContext,
)
from savora_ai.schemas.daily import MealOptionReference
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot
from savora_ai.schemas.planned_swap import (
    PlannedSwapRequest,
    PlannedSwapSourceSnapshot,
    PlannedSwapWorkflowBridge,
    SavedPlanLockInventory,
    SavedPlanMaterial,
    SwapTargetPermission,
    SwapValidationLimits,
    SwapWork,
)
from savora_ai.schemas.swap_proof_types import (
    ComputedSwapCertificate,
    SwapOutcome,
)


def validate_swap(
    request: PlannedSwapRequest,
    replacement: MealOptionReference,
    *,
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
) -> ComputedSwapValidationResult:
    """Recheck both complete fixed plans; return a witness only after full replay.

    Pydantic admission errors are explicit structural boundary failures. This API
    does not authenticate the loader, persist plans, override locks or search.
    """
    from savora_ai.core.reasoning.swap_checks import (
        _admit,
        _binding_cost,
        _execute_phase,
        _input_digest,
        _Interrupted,
        _Meter,
        _proposed,
        _schedule,
        _verdict,
    )

    authority: dict[str, object] = dict(
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
    )
    inputs = _admit(authority)
    # One shared clock guard spans executor, checker and their boundary.
    guard = _Meter(clock, None, checker=False)

    def guarded_clock() -> float:
        guard.checkpoint()
        assert guard.previous is not None
        return guard.previous

    meter = _Meter(guarded_clock, limits.deadline, checker=False)
    checker_work = SwapWork()
    stage = "RESERVATION"
    try:
        schedule = _schedule(inputs)
        meter.start(_binding_cost(inputs))
        inputs = _admit(authority)
        meter.checkpoint()
        stage = "EXECUTION"
        original = _execute_phase(inputs, "ORIGINAL", meter)
        resulting = _execute_phase(inputs, "RESULT", meter)
        meter.start(SwapWork(full_validations=1))
        outcome, scope, reason = _verdict(inputs, original, resulting)
        certificate = ComputedSwapCertificate(
            input_digest=_input_digest(inputs),
            reservations=schedule.plan,
            original=original,
            result=resulting,
        )
        proof_bytes = len(certificate.model_dump_json(by_alias=True).encode())
        claim = dict(
            request=request,
            replacement=replacement,
            limits=limits,
            stage="COMPLETE",
            outcome=outcome,
            failure_scope=scope,
            reason=reason,
            certificate=certificate,
            resulting_plan=_proposed(inputs) if outcome is SwapOutcome.VALID else None,
            verification_complete=True,
            actual_execution=meter.work,
            actual_verification=schedule.verification,
            proof_bytes=proof_bytes,
        )
        # Check the complete wire envelope before the mandatory checker starts.
        from savora_ai.schemas.swap_proof_types import _SwapClaim

        parsed = _SwapClaim.model_validate(claim)
        if (
            proof_bytes > limits.max_proof_bytes
            or len(parsed.model_dump_json(by_alias=True).encode()) > limits.max_result_bytes
        ):
            raise _Interrupted("RESERVATION")
        meter.checkpoint()
        stage = "VERIFICATION"
        try:
            return ComputedSwapValidationResult.model_validate(
                claim, context={"authority": authority, "clock": guarded_clock}
            )
        except _Interrupted as error:
            checker_work = error.work
            raise
    except _Interrupted as error:
        return ComputedSwapValidationResult(
            request=request,
            replacement=replacement,
            limits=limits,
            stage=stage,
            outcome=SwapOutcome.TIMEOUT,
            reason=error.reason,
            actual_execution=meter.work,
            actual_verification=checker_work,
        )
    except ValidationError as error:
        # Source admission already succeeded. Only the exact bounded computed
        # envelope overflow is a resource stop; policy/binding errors propagate.
        if not all(
            e["msg"] == "Value error, swap structural envelope exceeds 1 MiB"
            for e in error.errors()
        ):
            raise
        return ComputedSwapValidationResult(
            request=request,
            replacement=replacement,
            limits=limits,
            stage=stage,
            outcome=SwapOutcome.TIMEOUT,
            reason="RESERVATION",
            actual_execution=meter.work,
            actual_verification=checker_work,
        )
