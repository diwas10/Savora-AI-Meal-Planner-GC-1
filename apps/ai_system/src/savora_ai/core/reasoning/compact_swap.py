"""Bounded compact B1/B2 with fresh independent full-source proof reconstruction.

No runtime adapter or clinical rule release is installed by importing this module.
"""

import hashlib
from collections.abc import Callable
from time import monotonic
from typing import Any, cast

from pydantic import ValidationError

from savora_ai.core.reasoning.compact_swap_material import (
    WIRE_BYTES,
    AdmittedCompactSwap,
    CompactAdmissionError,
    admit_compact_swap,
    canonical_bytes,
    digest,
    parse_input,
)
from savora_ai.core.reasoning.compact_swap_resolver import TrustedSourceResolver
from savora_ai.core.reasoning.day_checks import _slot_status
from savora_ai.core.reasoning.swap_checks import (
    _admit,
    _assess_option,
    _binding_cost,
    _execute_phase,
    _input_digest,
    _Interrupted,
    _Meter,
    _option_cost,
    _schedule,
    _verdict,
)
from savora_ai.core.reasoning.swap_proof import _reconstruct_swap
from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.compact_swap import (
    CompactAuthorizedCandidate,
    CompactNutrientTotal,
    CompactPortionSource,
    CompactReplacement,
    CompactSwapInput,
    CompactSwapPhaseAssessment,
    CompactSwapResult,
    CompactSwapVerification,
)
from savora_ai.schemas.compact_swap_canonical import CompactCanonicalLimitError, canonical_proof
from savora_ai.schemas.nutrients_v2 import Nutrient, native_unit, scaled_value
from savora_ai.schemas.planned_swap import SwapValidationLimits, SwapWork, _fixed_meal_identity
from savora_ai.schemas.swap_envelope_policy import (
    COMPACT_SWAP_RECONSTRUCTION_POLICY,
    compact_swap_reconstruction,
)
from savora_ai.schemas.swap_proof_types import SwapOutcome

NUTRIENTS: tuple[Nutrient, ...] = (
    "energy_kcal",
    "protein_g",
    "carbs_g",
    "fat_g",
    "saturated_fat_g",
    "sodium_mg",
    "sugars_g",
)


def _proof_capacity_error(error: Exception) -> bool:
    if isinstance(error, CompactCanonicalLimitError):
        return True
    return isinstance(error, ValidationError) and all(
        e["msg"] == "Value error, PROOF_LIMIT" for e in error.errors()
    )


def _portion(admitted: AdmittedCompactSwap, replacement: CompactReplacement):
    for source in admitted.sources:
        if source.combination_id == replacement.combination_id:
            for portion in source.portions:
                if portion.preset == replacement.portion_preset:
                    return portion
    raise CompactAdmissionError("PRESET_UNAVAILABLE")


def _native_value(portion: CompactPortionSource, nutrient: Nutrient) -> int | None:
    vector = portion.nutrients
    if (
        vector.basis != "ABSOLUTE_FIXED_PORTION"
        or vector.reference_basis == "UNKNOWN"
        or (vector.reference_basis == "PER_100_G" and vector.mass_g is None)
    ):
        return None
    observation = next((m for m in vector.measurements if m.nutrient == nutrient), None)
    if observation is None or observation.value is None or not observation.complete:
        return None
    return scaled_value(observation.value)


def _native(admitted: AdmittedCompactSwap, replacement: CompactReplacement):
    """Fresh all21 native evaluation; absent measurements are never zero."""
    originals = [
        _portion(
            admitted,
            CompactReplacement(combination_id=s.combination_id, portion_preset=s.portion_preset),
        )
        for s in admitted.request.slots
    ]
    selected = list(originals)
    target = admitted.authority.request.target.canonical_index
    selected[target] = _portion(admitted, replacement)
    bands = admitted.authority.target_snapshot.bands
    states = []
    observations = []
    for phase, portions in (("ORIGINAL", originals), ("RESULT", selected)):
        for band in bands:
            members = (
                portions
                if band.scope == "WEEK"
                else portions[3 * (cast(int, band.day_index) - 1) : 3 * cast(int, band.day_index)]
            )
            values = [_native_value(p, band.nutrient) for p in members]
            total = None if None in values else sum(cast(list[int], values))
            state = "UNKNOWN"
            if total is not None:
                lower = None if band.lower is None else scaled_value(band.lower)
                upper = None if band.upper is None else scaled_value(band.upper)
                failed = (
                    lower is not None
                    and (total < lower or (total == lower and not band.lower_inclusive))
                ) or (
                    upper is not None
                    and (total > upper or (total == upper and not band.upper_inclusive))
                )
                state = "FAIL" if failed else "PASS"
            states.append(state)
            observations.append((phase, band.band_id, total, state))
    totals = []
    for nutrient in NUTRIENTS:
        values = [
            _native_value(p, nutrient) for p in selected[target // 3 * 3 : target // 3 * 3 + 3]
        ]
        total = None if None in values else sum(cast(list[int], values))
        if total is None:
            states.append("UNKNOWN")
        value = None if total is None else f"{total // 1000}.{total % 1000:03}"
        totals.append(
            CompactNutrientTotal(
                nutrient=nutrient,
                unit=native_unit(nutrient),
                value=value,
                complete=total is not None,
            )
        )
    return (
        "FAIL" if "FAIL" in states else "UNKNOWN" if "UNKNOWN" in states else "PASS",
        tuple(totals),
        digest(
            dict(
                bands=observations,
                totals=[t.model_dump(mode="json", by_alias=True) for t in totals],
            )
        ),
    )


def _compute(admitted: AdmittedCompactSwap, *, checker: bool, clock: Callable[[], float]):
    a, request = admitted.authority, admitted.request
    limits = a.limits
    candidates = (
        (
            CompactAuthorizedCandidate(
                candidate_id="b1-replacement",
                priority=0,
                combination_id=request.replacement.combination_id,
                portion_preset=request.replacement.portion_preset,
            ),
        )
        if request.replacement
        else a.candidates
    )
    guard = _Meter(clock, limits.deadline, checker=checker)
    guard.checkpoint()
    if (
        len(candidates) > limits.max_domain_visits
        or len(candidates) > limits.max_full_validations
        or limits.max_proof_bytes < WIRE_BYTES
        or limits.max_result_bytes < WIRE_BYTES
    ):
        raise _Interrupted("RESERVATION")
    # Reserve traversal, every full B1 executor/checker and native band scan before
    # semantic work. Transient proof byte pool is reused, counters are cumulative.
    work = {name: 0 for name in SwapWork.model_fields}
    work["domain_visits"] = 2 * len(candidates)
    work["ordering_items"] = 2 * len(candidates)
    work["checker_steps"] = 2
    if any(work[n] > getattr(limits.max_reserved_work, n) for n in work):
        raise _Interrupted("RESERVATION")
    candidates = tuple(sorted(candidates, key=lambda e: (e.priority, e.candidate_id)))
    entries = []
    records = len(candidates) + 1
    for candidate in candidates:
        replacement = CompactReplacement(
            combination_id=candidate.combination_id, portion_preset=candidate.portion_preset
        )
        portion = _portion(admitted, replacement)
        b1_limits = SwapValidationLimits(
            max_reserved_work=limits.max_reserved_work,
            max_proof_records=limits.max_proof_records,
            max_proof_bytes=limits.max_proof_bytes,
            max_result_bytes=limits.max_result_bytes,
            max_full_validations=1,
            deadline=limits.deadline,
        )
        inputs = _admit(
            dict(
                request=a.request,
                replacement=portion.projected.reference,
                saved_plan=a.saved_plan,
                locks=a.locks,
                permission=a.permission,
                candidates=a.sources.candidates,
                knowledge=a.knowledge,
                context=a.context,
                sources=a.sources,
                bridge=a.bridge,
                limits=b1_limits,
            )
        )
        schedule = _schedule(inputs)
        records += sum(o.proof_records for o in schedule.plan.operations)
        for op in schedule.plan.operations:
            for name in work:
                work[name] += getattr(op.reserved, name)
        native_visits = (
            2 * sum(21 if b.scope == "WEEK" else 3 for b in a.target_snapshot.bands) + 21
        )
        work["source_items"] += 2 * native_visits
        work["predicate_obligations"] += 4 * len(a.target_snapshot.bands)
        if request.mode == "B2":
            precheck_cost = _option_cost(inputs, "RESULT", portion.projected)
            for name in work:
                work[name] += 2 * getattr(precheck_cost, name)
            work["checker_steps"] += sum(v > 0 for v in precheck_cost.model_dump().values())
        if records > limits.max_proof_records or any(
            work[n] > getattr(limits.max_reserved_work, n) for n in work
        ):
            raise _Interrupted("RESERVATION")
        entries.append((replacement, inputs, schedule))
        guard.checkpoint()
    transcript: list[dict[str, Any]] = []
    seen_unknown = False
    if request.mode == "B2":
        prechecks = []
        eligible = []
        original = a.saved_plan.snapshot.slots[a.request.target.canonical_index].option
        for replacement, inputs, schedule in entries:
            option = _portion(admitted, replacement).projected
            guard.start(_option_cost(inputs, "RESULT", option))
            assessment = _assess_option(inputs, "RESULT", option, component_recipes_only=True)
            status, _ = _slot_status(option, a.request.target.slot, assessment.combination.status)
            lane = (
                "NO_OP"
                if _fixed_meal_identity(original) == _fixed_meal_identity(option)
                else status.value
            )
            prechecks.append(
                dict(
                    optionId=option.reference.option_id,
                    lane=lane,
                    assessment=hashlib.sha256(canonical_proof(assessment)).hexdigest(),
                )
            )
            if lane == "PASS":
                eligible.append((replacement, inputs, schedule))
            seen_unknown |= lane == "UNKNOWN"
            guard.checkpoint()
        transcript.append(
            dict(
                policy="compact-swap-hard-eligibility.v1",
                checks=prechecks,
                eligible=[i.replacement.option_id for _, i, _ in eligible],
            )
        )
        # Always freshly check the original complete week. If there is no hard-
        # eligible candidate, one bounded probe also witnesses the baseline; its
        # failed/unknown/no-op lane cannot become a selectable replacement.
        entries = eligible if eligible else entries[:1]
    final_status = "REJECTED"
    final_reason = "NO_VALID_REPLACEMENT"
    chosen = None
    totals = ()
    for replacement, inputs, schedule in entries:
        guard.start(_binding_cost(inputs))
        if checker:
            original, resulting, outcome, scope, reason, _ = _reconstruct_swap(
                inputs,
                guard,
                include_plan=False,
                phase_type=CompactSwapPhaseAssessment,
                component_recipes_only=True,
            )
        else:
            original = _execute_phase(
                inputs,
                "ORIGINAL",
                guard,
                phase_type=CompactSwapPhaseAssessment,
                component_recipes_only=True,
            )
            resulting = _execute_phase(
                inputs,
                "RESULT",
                guard,
                phase_type=CompactSwapPhaseAssessment,
                component_recipes_only=True,
            )
            guard.start(SwapWork(full_validations=1))
            outcome, scope, reason = _verdict(inputs, original, resulting)
        certificate = dict(
            schemaVersion="compact-swap-phase-certificate.v1",
            input_digest=_input_digest(inputs),
            reservations=schedule.plan.model_dump(mode="json", by_alias=True),
            original=original.model_dump(mode="json", by_alias=True),
            result=resulting.model_dump(mode="json", by_alias=True),
        )
        proof = canonical_proof(certificate)
        native_status, native_totals, native_digest = _native(admitted, replacement)
        guard.checkpoint()
        status = outcome.value
        if outcome is SwapOutcome.VALID:
            status = (
                "REJECTED"
                if native_status == "FAIL"
                else "INSUFFICIENT_DATA"
                if native_status == "UNKNOWN"
                else "VALID"
            )
        transcript.append(
            dict(
                replacement=replacement.model_dump(mode="json", by_alias=True),
                certificate=hashlib.sha256(proof).hexdigest(),
                native=native_digest,
                status=status,
            )
        )
        if len(canonical_bytes(transcript)) > limits.max_proof_bytes:
            raise _Interrupted("RESERVATION")
        if status == "VALID":
            final_status, final_reason, chosen, totals = (
                status,
                "COMPLETE_PASS",
                replacement,
                native_totals,
            )
            break
        seen_unknown |= status == "INSUFFICIENT_DATA"
        if request.mode == "B1" or (scope == "OPERATION" and reason != "NO_OP"):
            final_status, final_reason = (
                status,
                reason
                if outcome is not SwapOutcome.VALID
                else (
                    "NATIVE_REQUIRED_FACT_UNKNOWN"
                    if native_status == "UNKNOWN"
                    else "NATIVE_BAND_FAILED"
                ),
            )
            break
    else:
        if seen_unknown:
            final_status, final_reason = "INSUFFICIENT_DATA", "REQUIRED_FACT_UNKNOWN"
    claim = CompactSwapResult(
        input_digest=digest(request),
        status=final_status,
        reason=final_reason,
        replacement_combination_id=None if chosen is None else chosen.combination_id,
        replacement_portion_preset=None if chosen is None else chosen.portion_preset,
        changed_day_totals=totals,
        certificate_digest=digest(
            dict(
                protocol="compact-swap-reconstructed-certificate.v1",
                material=hashlib.sha256(admitted.material).hexdigest(),
                transcript=transcript,
            )
        ),
        reconstructed_bytes=len(admitted.material),
        verification_complete=True,
    )
    if len(claim.model_dump_json(by_alias=True).encode()) > WIRE_BYTES:
        raise _Interrupted("RESERVATION")
    return claim


def verify_compact_swap(
    compact_input: CompactSwapInput | str | bytes,
    compact_result: CompactSwapResult | str | bytes,
    resolver: TrustedSourceResolver,
    *,
    clock: Callable[[], float] = monotonic,
) -> CompactSwapVerification:
    """Retrieve authority anew, reconstruct full witness, independently replay every phase.

    No call to execute_compact_swap, _execute_phase, stored affirmative status or
    digest-only acceptance. Unavailable material means verification fails closed.
    """
    try:
        raw = (
            compact_result.model_dump_json(by_alias=True)
            if isinstance(compact_result, CompactSwapResult)
            else compact_result
        )
        result = validate_contract_json(CompactSwapResult, raw)
        if not result.verification_complete or result.status in ("TIMEOUT", "ADMISSION_FAILED"):
            return CompactSwapVerification(
                accepted=False, complete=False, reason="UNVERIFIED_RESULT"
            )
        admitted = admit_compact_swap(compact_input, resolver)
        with compact_swap_reconstruction(COMPACT_SWAP_RECONSTRUCTION_POLICY):
            expected = _compute(admitted, checker=True, clock=clock)
        return CompactSwapVerification(
            accepted=expected == result,
            complete=True,
            reason="VERIFIED" if expected == result else "MISMATCH",
        )
    except CompactAdmissionError as error:
        return CompactSwapVerification(accepted=False, complete=False, reason=error.code)
    except _Interrupted as error:
        return CompactSwapVerification(accepted=False, complete=False, reason=error.reason)
    except (ValidationError, ValueError, TypeError) as error:
        return CompactSwapVerification(
            accepted=False,
            complete=False,
            reason="RESERVATION"
            if _proof_capacity_error(error)
            else "INVALID_MATERIAL:" + type(error).__name__,
        )


def execute_compact_swap(
    compact_input: CompactSwapInput | str | bytes,
    resolver: TrustedSourceResolver,
    *,
    clock: Callable[[], float] = monotonic,
) -> CompactSwapResult:
    """Explicit B1/B2 entry point; result is a delta, never a persistence instruction."""
    input_digest = hashlib.sha256(b"invalid-compact-input").hexdigest()
    try:
        request = parse_input(compact_input)
        input_digest = digest(request)
        admitted = admit_compact_swap(request, resolver)
        with compact_swap_reconstruction(COMPACT_SWAP_RECONSTRUCTION_POLICY):
            result = _compute(admitted, checker=False, clock=clock)
        check = verify_compact_swap(request, result, resolver, clock=clock)
        if not check.accepted:
            return CompactSwapResult(
                input_digest=input_digest,
                status="INSUFFICIENT_DATA",
                reason="INDEPENDENT_VERIFICATION:" + check.reason,
            )
        return result
    except CompactAdmissionError as error:
        return CompactSwapResult(
            input_digest=input_digest, status="ADMISSION_FAILED", reason=error.code
        )
    except _Interrupted as error:
        return CompactSwapResult(input_digest=input_digest, status="TIMEOUT", reason=error.reason)
    except (ValidationError, ValueError, TypeError) as error:
        return CompactSwapResult(
            input_digest=input_digest,
            status="TIMEOUT" if _proof_capacity_error(error) else "ADMISSION_FAILED",
            reason="RESERVATION"
            if _proof_capacity_error(error)
            else "INVALID_MATERIAL:" + type(error).__name__,
        )
