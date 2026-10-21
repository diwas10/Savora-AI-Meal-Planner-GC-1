"""Independent proof attacks, reserved replay and interrupted checker coverage."""

from typing import Any

import pytest
from pydantic import ValidationError
from swap_oracle import arguments, different_saved_plan, literal_swap_cost, make_case, repin
from test_planned_swap_contracts import rebuild
from test_swap_proof_contracts import limits

from savora_ai.core.reasoning import swap_checks
from savora_ai.core.reasoning.planned_swap import validate_swap, verify_swap_validation
from savora_ai.schemas import planned_swap as s
from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.reasoning import RuleStatus
from savora_ai.schemas.swap_proof import ComputedSwapValidationResult, SwapOutcome


@pytest.fixture(scope="module")
def case():
    return make_case()


@pytest.fixture(scope="module")
def verified(case):
    return validate_swap(**arguments(case, capacity=limits(deadline=1.0)), clock=lambda: 0.0)


def check(case, result, **kwargs):
    return verify_swap_validation(
        result, **arguments(case, capacity=limits(deadline=1.0)), **kwargs
    )


def test_fresh_checker_and_no_bare_reconstitution(case, verified):
    assert verified.accepted
    assert check(case, verified, clock=lambda: 0.0).accepted
    with pytest.raises(ValidationError, match="independent authority"):
        ComputedSwapValidationResult.model_validate(verified.model_dump())
    with pytest.raises(ValidationError):
        validate_contract_json(ComputedSwapValidationResult, verified.model_dump_json())


@pytest.mark.parametrize(
    "attack",
    (
        "trace",
        "quantity",
        "omit-day",
        "omit-rule",
        "slots",
        "cost",
        "proof-bytes",
        "plan",
        "outcome",
        "input",
    ),
)
def test_forged_and_rehashed_proofs(case, verified, attack):
    forged = verified
    certificate = verified.certificate
    result = certificate.result
    if attack == "trace":
        trace = result.week.trace
        evaluation = trace.evaluations[0].model_copy(update={"status": RuleStatus.FAIL})
        week = result.week.model_copy(
            update={
                "trace": trace.model_copy(
                    update={"evaluations": (evaluation, *trace.evaluations[1:])}
                )
            }
        )
        result = result.model_copy(update={"week": week})
    elif attack == "quantity":
        observations = result.week.observations
        result = result.model_copy(
            update={
                "week": result.week.model_copy(
                    update={
                        "observations": (
                            observations[0],
                            observations[1].model_copy(update={"value": 44}),
                            observations[2],
                        )
                    }
                )
            }
        )
    elif attack == "omit-day":
        result = result.model_copy(update={"days": result.days[:-1]})
    elif attack == "omit-rule":
        trace = result.week.trace
        result = result.model_copy(
            update={
                "week": result.week.model_copy(
                    update={
                        "trace": trace.model_copy(
                            update={
                                "required_checks": trace.required_checks[:-1],
                                "evaluations": trace.evaluations[:-1],
                            }
                        )
                    }
                )
            }
        )
    elif attack == "slots":
        result = result.model_copy(update={"slots": (RuleStatus.UNKNOWN, *result.slots[1:])})
    elif attack == "cost":
        forged = verified.model_copy(update={"actual_verification": s.SwapWork()})
    elif attack == "proof-bytes":
        forged = verified.model_copy(update={"proof_bytes": 1})
    elif attack == "plan":
        plan = verified.resulting_plan
        slots = list(plan.slots)
        slots[3] = slots[0].model_copy(update={"identity": slots[3].identity})
        forged = verified.model_copy(
            update={"resulting_plan": plan.model_copy(update={"slots": tuple(slots)})}
        )
    elif attack == "outcome":
        forged = verified.model_copy(
            update={"outcome": SwapOutcome.REJECTED, "resulting_plan": None}
        )
    else:
        certificate = certificate.model_copy(update={"input_digest": "f" * 64})
    if attack not in ("cost", "proof-bytes", "plan", "outcome"):
        certificate = certificate.model_copy(update={"result": result})
        # Recompute the byte claim as an attacker can; no digest/size is authority.
        forged = verified.model_copy(
            update={
                "certificate": certificate,
                "proof_bytes": len(certificate.model_dump_json(by_alias=True).encode()),
            }
        )
    report = check(case, forged, clock=lambda: 0.0)
    assert report.complete and not report.accepted and report.reason == "MISMATCH"


@pytest.mark.parametrize("change", ("plan", "revision", "locks", "target"))
def test_transplanted_independent_roots(case, verified, change):
    from swap_oracle import at_target, repin

    if change == "target":
        changed = at_target(case, 20)
    elif change == "locks":
        changed = repin(case, locks=rebuild(case["locks"], revision=2))
    elif change == "revision":
        saved = case["saved_plan"]
        changed = repin(
            case,
            saved_plan=rebuild(
                saved, reference=saved.reference.model_copy(update={"effective_revision": 2})
            ),
        )
    else:
        changed = repin(case, permission=rebuild(case["permission"], record_id="different-grant"))
    assert not check(changed, verified, clock=lambda: 0.0).accepted


@pytest.mark.parametrize(
    "axis", (*s.SwapWork.model_fields, "records", "proof", "result", "validations")
)
def test_exact_and_one_short_reservations(case, verified, axis):
    oracle = literal_swap_cost(case)
    counts = oracle["reserved"].copy()
    if axis in counts and counts[axis] == 0:
        # No search/ranking operations belong to single-candidate validation.
        assert axis in ("domain_visits", "ordering_items")
        return
    base: dict[str, Any] = dict(
        max_reserved_work=s.SwapWork(**counts),
        max_proof_records=oracle["records"],
        max_proof_bytes=1_048_576,
        max_result_bytes=1_048_576,
        max_full_validations=1,
    )
    if axis in counts:
        counts[axis] -= 1
        base["max_reserved_work"] = s.SwapWork(**counts)
    else:
        field = {
            "records": "max_proof_records",
            "proof": "max_proof_bytes",
            "result": "max_result_bytes",
            "validations": "max_full_validations",
        }[axis]
        base[field] -= 1
    result = validate_swap(**arguments(case, capacity=limits(**base)), clock=lambda: 0.0)
    assert result.outcome is SwapOutcome.TIMEOUT and result.reason == "RESERVATION"
    assert not any(result.actual_execution.model_dump().values())
    assert not result.accepted and result.resulting_plan is None


def test_exact_capacity_and_verifier_only_capacity(case, verified):
    oracle = literal_swap_cost(case)
    counts = oracle["reserved"]
    capacity = limits(max_reserved_work=s.SwapWork(**counts), max_proof_records=oracle["records"])
    result = validate_swap(**arguments(case, capacity=capacity), clock=lambda: 0.0)
    assert result.accepted
    # Execution fits every dimension; mandatory replay alone does not fit.
    executor_only = limits(max_reserved_work=s.SwapWork(**oracle["execution"]))
    result = validate_swap(**arguments(case, capacity=executor_only), clock=lambda: 0.0)
    assert result.outcome is SwapOutcome.TIMEOUT and result.stage == "RESERVATION"


@pytest.mark.parametrize("step", (1, 2, 3, 10, 11, 13, 20, 21))
def test_checker_deadline_at_every_stage(case, verified, monkeypatch, step):
    original = swap_checks._Meter.start
    counter = 0
    expired = False

    def start(meter, cost):
        nonlocal counter, expired
        if meter.checker:
            counter += 1
            expired = counter >= step
        return original(meter, cost)

    monkeypatch.setattr(swap_checks._Meter, "start", start)
    report = check(case, verified, clock=lambda: 2.0 if expired else 0.0)
    assert not report.accepted and not report.complete and report.reason == "DEADLINE"
    assert counter == step


def test_validator_withholds_plan_on_checker_interruption(case, monkeypatch):
    original = swap_checks._Meter.start
    expired = False

    def start(meter, cost):
        nonlocal expired
        if meter.checker and cost.day_assessments:
            expired = True
        return original(meter, cost)

    monkeypatch.setattr(swap_checks._Meter, "start", start)
    result = validate_swap(
        **arguments(case, capacity=limits(deadline=1.0)), clock=lambda: 2.0 if expired else 0.0
    )
    assert result.outcome is SwapOutcome.TIMEOUT and result.stage == "VERIFICATION"
    assert result.actual_verification.combination_preparations > 0
    assert not result.accepted and not result.verification_complete
    assert result.certificate is None and result.resulting_plan is None


def test_checker_forbidden_executor_and_optimized_calls(case, verified, monkeypatch):
    from savora_ai.core.reasoning import planned_swap, weekly_incremental, weekly_search_v2

    def forbidden(*args, **kwargs):
        raise AssertionError("checker invoked an execution/optimized entry point")

    monkeypatch.setattr(planned_swap, "validate_swap", forbidden)
    monkeypatch.setattr(swap_checks, "_execute_phase", forbidden)
    for module in (weekly_incremental, weekly_search_v2):
        for name in vars(module):
            if name.startswith(("solve", "_search", "_evaluate")) and callable(
                getattr(module, name)
            ):
                monkeypatch.setattr(module, name, forbidden)
    assert check(case, verified, clock=lambda: 0.0).accepted


def test_checker_reconstruction_envelope_overflow_is_incomplete(verified):
    from savora_ai.core.reasoning.swap_checks import _admit, _input_digest, _schedule

    c = make_case(copies=4)
    inputs = _admit(arguments(c, capacity=limits(deadline=1.0)))
    # Attacker supplies valid structural bindings and recomputes public hashes.
    # The counterfeit negative claim is small; authoritative VALID reconstruction
    # requires an oversized mixed-origin plan. It must never escape as an error
    # or become a completed proof/accepted plan.
    certificate = verified.certificate.model_copy(
        update={
            "input_digest": _input_digest(inputs),
            "reservations": _schedule(inputs).plan,
        }
    )
    forged = verified.model_copy(
        update={
            "request": c["request"],
            "replacement": inputs.replacement,
            "certificate": certificate,
            "resulting_plan": None,
            "outcome": SwapOutcome.REJECTED,
            "reason": "RESULT_FAILED",
            "failure_scope": "CANDIDATE",
        }
    )
    report = check(c, forged, clock=lambda: 0.0)
    assert not report.accepted and not report.complete
    assert report.reason == "RESERVATION" and report.outcome is None
    assert report.actual_verification.full_validations == 1


@pytest.fixture(scope="module")
def distinct_plans():
    first = make_case(day_limit=12, week_limit=48)
    second = different_saved_plan(first)
    a = validate_swap(**arguments(first, capacity=limits(deadline=1.0)), clock=lambda: 0.0)
    b = validate_swap(**arguments(second, capacity=limits(deadline=1.0)), clock=lambda: 0.0)
    assert a.accepted and b.accepted
    assert a.certificate is not None and b.certificate is not None
    assert a.actual_execution.model_dump() == literal_swap_cost(first)["execution"]
    assert b.actual_execution.model_dump() == literal_swap_cost(second)["execution"]
    assert a.certificate.original.week.observations[1].value == 42
    assert b.certificate.original.week.observations[1].value == 45
    assert a.certificate.result.week.observations[1].value == 45
    assert b.certificate.result.week.observations[1].value == 48
    assert first["saved_plan"].reference.plan_id == second["saved_plan"].reference.plan_id
    assert first["saved_plan"].reference.snapshot_id == second["saved_plan"].reference.snapshot_id
    assert (
        first["saved_plan"].reference.snapshot_digest
        != second["saved_plan"].reference.snapshot_digest
    )
    assert first["saved_plan"].snapshot.slots[20] != second["saved_plan"].snapshot.slots[20]
    return first, second, a, b


@pytest.mark.parametrize("direction", (0, 1))
def test_genuine_different_saved_plan_transplants(distinct_plans, direction):
    first, second, a, b = distinct_plans
    authority, claim = (second, a) if direction == 0 else (first, b)
    assert not check(authority, claim, clock=lambda: 0.0).accepted


def test_changed_content_and_revision_transplant(distinct_plans):
    first, second, a, b = distinct_plans
    saved = second["saved_plan"]
    changed = repin(
        second,
        saved_plan=rebuild(
            saved, reference=saved.reference.model_copy(update={"effective_revision": 2})
        ),
    )
    result = validate_swap(**arguments(changed, capacity=limits(deadline=1.0)), clock=lambda: 0.0)
    assert result.accepted and check(changed, result, clock=lambda: 0.0).accepted
    assert not check(changed, a, clock=lambda: 0.0).accepted
    assert not check(first, result, clock=lambda: 0.0).accepted
    assert not check(changed, b, clock=lambda: 0.0).accepted


@pytest.mark.parametrize("axis", ("plan_id", "snapshot_id", "snapshot_version", "snapshot_digest"))
def test_snapshot_identity_and_independent_reference_must_agree(case, verified, axis):
    saved = case["saved_plan"]
    reference = saved.reference.model_copy(
        update={axis: "e" * 64 if axis == "snapshot_digest" else "foreign-identity"}
    )
    unchecked = saved.model_copy(update={"reference": reference})
    zero = limits(
        max_reserved_work=s.SwapWork(),
        max_proof_records=0,
        max_proof_bytes=0,
        max_result_bytes=0,
        max_full_validations=0,
    )
    with pytest.raises(ValidationError):
        validate_swap(**(arguments(case, capacity=zero) | dict(saved_plan=unchecked)))
    with pytest.raises(ValidationError):
        verify_swap_validation(verified, **(arguments(case) | dict(saved_plan=unchecked)))


@pytest.mark.parametrize("axis", ("context", "workflow", "policy"))
def test_context_workflow_and_policy_transplants(case, verified, axis):
    if axis == "workflow":
        with pytest.raises((ValidationError, s.SwapBoundaryError)):
            check(
                case | dict(context=case["saved_plan"].snapshot.original_context),
                verified,
                clock=lambda: 0.0,
            )
        return
    other = make_case(enabled=False) if axis == "context" else make_case(swap_only=True)
    assert other["context"].content_digest != case["context"].content_digest
    result = validate_swap(**arguments(other, capacity=limits(deadline=1.0)), clock=lambda: 0.0)
    assert check(other, result, clock=lambda: 0.0).accepted
    assert not check(other, verified, clock=lambda: 0.0).accepted
    assert not check(case, result, clock=lambda: 0.0).accepted


@pytest.mark.parametrize("variant", ("common", "registered", "duplicate-components"))
def test_independent_literal_resource_oracle(variant):
    c = make_case(
        swap_only=variant == "registered",
        copies=2 if variant == "duplicate-components" else 1,
        repetition_limit=20 if variant == "duplicate-components" else 21,
    )
    expected = literal_swap_cost(c)
    assert expected["execution"]["source_items"] == (
        199 if variant == "duplicate-components" else 154
    )
    assert expected["execution"]["predicate_obligations"] == (41 if variant == "registered" else 40)
    assert expected["execution"]["candidate_preparations"] == 3
    assert expected["execution"]["combination_preparations"] == 3
    assert expected["execution"]["day_assessments"] == 14
    assert expected["execution"]["week_assessments"] == 2
    assert expected["records"] == expected["verification"]["checker_steps"] == 64
    capacity = limits(
        max_reserved_work=s.SwapWork(**expected["reserved"]), max_proof_records=expected["records"]
    )
    result = validate_swap(**arguments(c, capacity=capacity), clock=lambda: 0.0)
    assert result.verification_complete
    assert result.certificate is not None
    assert result.actual_execution.model_dump() == expected["execution"]
    assert result.actual_verification.model_dump() == expected["verification"]
    report = verify_swap_validation(result, **arguments(c, capacity=capacity), clock=lambda: 0.0)
    assert report.accepted and report.actual_verification.model_dump() == expected["verification"]
    operations = result.certificate.reservations.operations
    assert len(operations) == expected["records"]
    assert sum(o.proof_bytes for o in operations) == expected["proof_bytes"]
    assert result.certificate.reservations.result_bytes_reserved == expected["result_bytes"]
    assert {
        n: sum(getattr(o.reserved, n) for o in operations) for n in expected["reserved"]
    } == expected["reserved"]


@pytest.mark.parametrize("axis", tuple(s.SwapWork.model_fields))
def test_independent_verifier_one_short_and_zero_work(case, verified, axis):
    oracle = literal_swap_cost(case)
    counts = oracle["reserved"].copy()
    if counts[axis] == 0:
        # These categories are explicitly unused, not silently deselected cases.
        assert axis in ("domain_visits", "ordering_items")
        assert getattr(verified.actual_execution, axis) == 0
        assert getattr(verified.actual_verification, axis) == 0
        return
    for value in (counts[axis] - 1, 0):
        capacity = limits(max_reserved_work=s.SwapWork(**(counts | {axis: value})), deadline=1.0)
        report = verify_swap_validation(
            verified, **arguments(case, capacity=capacity), clock=lambda: 0.0
        )
        assert not report.accepted and not report.complete and report.reason == "RESERVATION"
        assert not any(report.actual_verification.model_dump().values())


@pytest.mark.parametrize("offset", (-1, 0, 1))
def test_full_result_encoded_byte_boundary_and_certificate_distinction(case, verified, offset):
    from savora_ai.schemas.swap_proof import _SwapClaim

    def padded(length):
        cert = verified.certificate
        week = cert.result.week
        trace = week.trace
        evaluations = (
            trace.evaluations[0].model_copy(update={"reason": "p" * length}),
            *trace.evaluations[1:],
        )
        week = week.model_copy(
            update={"trace": trace.model_copy(update={"evaluations": evaluations})}
        )
        cert = cert.model_copy(update={"result": cert.result.model_copy(update={"week": week})})
        return verified.model_copy(update={"certificate": cert})

    initial = padded(1)
    amount = 1_048_576 - len(initial.model_dump_json(by_alias=True).encode()) + 1 + offset
    hostile = padded(amount)
    raw = hostile.model_dump_json(by_alias=True)
    assert len(raw.encode()) == 1_048_576 + offset
    assert len(hostile.certificate.model_dump_json(by_alias=True).encode()) < 1_048_576
    if offset > 0:
        with pytest.raises(ValidationError, match="structural envelope"):
            _SwapClaim.model_validate_json(raw)
    else:
        assert _SwapClaim.model_validate_json(raw).verification_complete
    # Structural fit never authenticates the padded, internally reserialized proof.
    report = check(case, hostile, clock=lambda: 0.0)
    assert not report.accepted and report.reason == "MISMATCH"


@pytest.mark.parametrize("mixed", (False, True))
@pytest.mark.parametrize("side", ("executor", "checker"))
def test_unrelated_or_mixed_validation_errors_are_not_timeouts(
    case, verified, monkeypatch, mixed, side
):
    from savora_ai.core.reasoning import planned_swap, swap_proof

    errors: Any = [
        {
            "type": "value_error",
            "loc": (),
            "input": None,
            "ctx": {"error": ValueError("unrelated output validation failure")},
        }
    ]
    if mixed:
        errors.insert(
            0,
            {
                "type": "value_error",
                "loc": (),
                "input": None,
                "ctx": {"error": ValueError("swap structural envelope exceeds 1 MiB")},
            },
        )

    def fail(*args, **kwargs):
        raise ValidationError.from_exception_data("InjectedOutputFailure", errors)

    if side == "executor":
        monkeypatch.setattr(planned_swap, "ComputedSwapCertificate", fail)
    else:
        monkeypatch.setattr(swap_proof, "SwapPhaseAssessment", fail)
    with pytest.raises(ValidationError, match="unrelated output validation"):
        if side == "executor":
            validate_swap(**arguments(case), clock=lambda: 0.0)
        else:
            check(case, verified, clock=lambda: 0.0)


@pytest.mark.parametrize("offset", (-1, 0, 1))
def test_certificate_encoded_byte_ceiling(verified, offset):
    from savora_ai.schemas.swap_proof import ComputedSwapCertificate

    cert = verified.certificate
    original = cert.result.week.trace.evaluations[0]

    def padded(length):
        trace = cert.result.week.trace
        trace = trace.model_copy(
            update={
                "evaluations": (
                    original.model_copy(update={"reason": "p" * length}),
                    *trace.evaluations[1:],
                )
            }
        )
        week = cert.result.week.model_copy(update={"trace": trace})
        return cert.model_copy(update={"result": cert.result.model_copy(update={"week": week})})

    initial = padded(1)
    amount = 1_048_576 - len(initial.model_dump_json(by_alias=True).encode()) + 1 + offset
    raw = padded(amount).model_dump_json(by_alias=True)
    assert len(raw.encode()) == 1_048_576 + offset
    if offset > 0:
        with pytest.raises(ValidationError, match="structural envelope"):
            ComputedSwapCertificate.model_validate_json(raw)
    else:
        assert (
            ComputedSwapCertificate.model_validate_json(raw).schema_version
            == "computed-swap-certificate.v1"
        )


@pytest.mark.parametrize(
    "field", ("max_proof_records", "max_proof_bytes", "max_result_bytes", "max_full_validations")
)
def test_zero_output_or_invocation_capacity_withholds_witness(case, verified, field):
    changes: dict[str, Any] = {field: 0}
    capacity = limits(**changes)
    result = validate_swap(**arguments(case, capacity=capacity), clock=lambda: 0.0)
    assert result.outcome is SwapOutcome.TIMEOUT and result.stage == "RESERVATION"
    assert not result.accepted and result.resulting_plan is None and result.certificate is None
    assert not any(result.actual_execution.model_dump().values())
    report = verify_swap_validation(
        verified, **arguments(case, capacity=capacity), clock=lambda: 0.0
    )
    assert not report.accepted and not report.complete and report.reason == "RESERVATION"


@pytest.mark.parametrize("bad", (float("nan"), float("inf"), True, "0"))
def test_checker_invalid_clock(case, verified, bad):
    with pytest.raises(ValueError, match="clock"):
        check(case, verified, clock=lambda: bad)


def test_checker_nonmonotonic_and_initial_expiry(case, verified):
    readings = iter([0.5, 0.25])
    with pytest.raises(ValueError, match="monotonic"):
        check(case, verified, clock=lambda: next(readings))
    report = check(case, verified, clock=lambda: 1.0)
    assert not report.accepted and not report.complete and report.reason == "DEADLINE"
