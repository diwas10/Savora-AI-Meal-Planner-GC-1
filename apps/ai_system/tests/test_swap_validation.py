"""Full-source single-swap behavior and literal fixed-plan expectations."""

import math

import pytest
from pydantic import ValidationError
from swap_oracle import arguments, at_target, literal_fixed_plan, make_case, repin
from test_planned_swap_contracts import rebuild
from test_swap_proof_contracts import limits
from test_weekly_contracts import evidence

from savora_ai.core.reasoning.planned_swap import validate_swap
from savora_ai.schemas import planned_swap as s
from savora_ai.schemas.reasoning import RuleStatus
from savora_ai.schemas.swap_proof import ComputedSwapValidationResult, SwapOutcome


@pytest.fixture(scope="module")
def case():
    return make_case()


@pytest.mark.parametrize("target", range(21))
def test_all_targets_literal_arithmetic_and_twenty_payloads(case, target):
    c = at_target(case, target)
    result = validate_swap(**arguments(c), clock=lambda: 0.0)
    assert result.outcome is SwapOutcome.VALID and result.accepted
    assert result.verification_complete and result.stage == "COMPLETE"
    values = [2] * 21
    values[target] = 5
    days, total, maximum = literal_fixed_plan(values, [["week-recipe"]] * 21)
    proof = result.certificate
    assert proof is not None
    assert result.resulting_plan is not None
    assert [d.observations[1].value for d in proof.result.days] == days
    assert proof.original.week.observations[1].value == 42
    assert proof.result.week.observations[1].value == total == 45
    assert proof.result.week.observations[2].value == maximum == 21
    assert len(proof.original.slots) == len(proof.result.slots) == 21
    for index, old in enumerate(c["saved_plan"].snapshot.slots):
        if index != target:
            assert result.resulting_plan.slots[index].model_dump() == old.model_dump()
        else:
            assert (
                result.resulting_plan.slots[index].option.reference
                == c["sources"].options[1].reference
            )
    assert c["saved_plan"].snapshot.original_context.workflow.value == "WEEKLY_PLAN"
    assert proof.result.options[0].combination.recipes.context.workflow.value == "PLANNED_SWAP"


@pytest.mark.parametrize(
    "kwargs,expected,scope",
    [
        ({"history": True}, "VALID", None),
        ({"recipe": False}, "REJECTED", "OPERATION"),
        ({"recipe": False, "history": True}, "REJECTED", "OPERATION"),
        ({"recipe": None}, "INSUFFICIENT_DATA", "OPERATION"),
        ({"measurements": (2, None)}, "INSUFFICIENT_DATA", "CANDIDATE"),
        ({"measurements": (None, 5)}, "INSUFFICIENT_DATA", "OPERATION"),
        ({"enabled": None}, "INSUFFICIENT_DATA", "OPERATION"),
        ({"enabled": False}, "VALID", None),
        ({"day_limit": 8}, "REJECTED", "CANDIDATE"),
        ({"week_limit": 44}, "REJECTED", "CANDIDATE"),
        ({"recipe": None, "day_limit": 8}, "REJECTED", "CANDIDATE"),
        ({"recipe": None, "week_limit": 44}, "REJECTED", "CANDIDATE"),
        ({"repetition_limit": 20}, "REJECTED", "OPERATION"),
        ({"copies": 2}, "TIMEOUT", None),
        ({"copies": 2, "repetition_limit": 20}, "REJECTED", "OPERATION"),
        ({"preparation": True}, "VALID", None),
        ({"context_bound": True}, "VALID", None),
        ({"swap_only": True, "week_limit": 44}, "REJECTED", "CANDIDATE"),
    ],
)
def test_semantic_matrix(kwargs, expected, scope):
    c = make_case(**kwargs)
    result = validate_swap(**arguments(c), clock=lambda: 0.0)
    assert result.outcome.value == expected and result.failure_scope == scope
    if expected == "TIMEOUT":
        assert result.reason == "RESERVATION" and result.stage == "EXECUTION"
        assert not result.accepted and result.resulting_plan is None
        assert not result.verification_complete and result.certificate is None
        return
    assert result.verification_complete
    assert result.certificate is not None
    assert (result.resulting_plan is not None) == result.accepted
    if kwargs.get("recipe", True) is None and expected == "REJECTED":
        assert RuleStatus.UNKNOWN in result.certificate.result.slots
        assert result.certificate.result.week.status is RuleStatus.FAIL
    if kwargs.get("enabled") is False:
        assert all(
            e.reason.endswith("NOT_APPLICABLE")
            for e in result.certificate.result.week.trace.evaluations
        )
    if kwargs.get("measurements") == (2, None):
        assert result.certificate.result.week.observations[1].value is None
    if kwargs.get("copies") == 2:
        assert result.certificate.result.week.observations[2].value == 21
    if kwargs.get("swap_only"):
        assert "synthetic-swap-week-quantity-cap" not in {
            e.rule.rule_id for e in result.certificate.original.week.trace.evaluations
        }
        assert "synthetic-swap-week-quantity-cap" in {
            e.rule.rule_id for e in result.certificate.result.week.trace.evaluations
        }


@pytest.mark.parametrize("kind", ("USER", "SYSTEM"))
def test_target_lock_denial(case, kind):
    locks = rebuild(
        case["locks"],
        entries=(
            s.SavedSlotLock(
                slot=case["request"].target,
                kind=s.LockKind(kind),
                reason="Explicit lock",
                authority=evidence(),
            ),
        ),
    )
    c = repin(case, locks=locks)
    result = validate_swap(**arguments(c), clock=lambda: 0.0)
    assert result.outcome is SwapOutcome.REJECTED and result.reason == "TARGET_LOCKED"
    assert result.failure_scope == "OPERATION" and result.resulting_plan is None


def test_noop(case):
    result = validate_swap(
        **arguments(case, replacement=case["sources"].options[0].reference), clock=lambda: 0.0
    )
    assert result.outcome is SwapOutcome.REJECTED and result.reason == "NO_OP"


@pytest.mark.parametrize(
    "axis", ("saved", "locks", "permission", "candidates", "bridge", "context")
)
def test_independent_conflicts_are_boundary_errors_even_at_zero(case, axis):
    args = arguments(case, capacity=limits(max_full_validations=0))
    if axis == "saved":
        args["saved_plan"] = rebuild(
            case["saved_plan"],
            reference=case["saved_plan"].reference.model_copy(update={"effective_revision": 2}),
        )
    elif axis == "locks":
        args["locks"] = rebuild(case["locks"], revision=2)
    elif axis == "permission":
        args["permission"] = rebuild(
            case["permission"], target=case["saved_plan"].snapshot.slots[1].identity
        )
    elif axis == "candidates":
        args["candidates"] = ()
    elif axis == "bridge":
        args["bridge"] = rebuild(case["bridge"], version="other")
    else:
        args["context"] = rebuild(case["context"], profile_id="another-profile")
    with pytest.raises((s.SwapBoundaryError, ValidationError)):
        validate_swap(**args, clock=lambda: 0.0)


@pytest.mark.parametrize("value", (0, -1, True, 1.0, "1"))
def test_malformed_revision(case, value):
    payload = case["saved_plan"].model_dump()
    payload["reference"]["effective_revision"] = value
    with pytest.raises(ValidationError):
        validate_swap(**(arguments(case) | {"saved_plan": payload}))


@pytest.mark.parametrize("bad", (math.nan, math.inf, True, "0"))
def test_invalid_clock(case, bad):
    with pytest.raises(ValueError, match="clock"):
        validate_swap(**arguments(case), clock=lambda: bad)


def test_decreasing_clock(case):
    readings = iter([2.0, 1.0])
    with pytest.raises(ValueError, match="monotonic"):
        validate_swap(**arguments(case), clock=lambda: next(readings))


def test_zero_and_initial_deadline(case):
    for capacity in (limits(max_full_validations=0), limits(deadline=0.0)):
        result = validate_swap(**arguments(case, capacity=capacity), clock=lambda: 0.0)
        assert result.outcome is SwapOutcome.TIMEOUT
        assert not result.accepted and not result.verification_complete
        assert result.resulting_plan is None and result.certificate is None
        assert not any(result.actual_execution.model_dump().values())


def test_no_direct_affirmative_constructor(case):
    with pytest.raises(ValidationError):
        ComputedSwapValidationResult.model_validate(
            dict(
                request=case["request"],
                replacement=case["sources"].options[1].reference,
                limits=limits(),
                outcome="VALID",
                stage="COMPLETE",
                reason="COMPLETE_PASS",
                verification_complete=True,
            )
        )


def test_opaque_external_fixed_presets_and_provenance():
    c = make_case(opaque_ids=True, preparation=True)
    original = c["saved_plan"].snapshot.slots
    replacement = c["sources"].options[1]
    result = validate_swap(**arguments(c), clock=lambda: 0.0)
    assert result.accepted
    assert result.resulting_plan is not None
    assert original[0].option.reference.option_id.endswith(":SMALL")
    assert replacement.reference.option_id == replacement.combination.combination_id + ":LARGE"
    target = result.resulting_plan.slots[0]
    assert target.option == replacement
    assert (
        target.option.reference.portion_configuration_id
        == replacement.combination.portion_configuration_id
    )
    assert target.option.reference.portion_state.value == "FIXED"
    assert target.source == c["request"].sources
    assert result.resulting_plan.slots[1:] == original[1:]


@pytest.mark.parametrize(
    "axis",
    (
        "combination_id",
        "combination_version",
        "combination_digest",
        "portion_configuration_id",
        "portion_configuration_version",
    ),
)
def test_same_option_id_cannot_infer_or_override_fixed_identity(case, axis):
    ref = case["sources"].options[1].reference
    altered = ref.model_copy(update={axis: "f" * 64 if axis == "combination_digest" else "foreign"})
    assert altered.option_id == ref.option_id
    with pytest.raises((ValidationError, s.SwapBoundaryError)):
        validate_swap(
            **arguments(case, replacement=altered, capacity=limits(max_full_validations=0))
        )


def test_incomplete_numeric_measurement_is_unknown_not_zero():
    c = make_case(incomplete=True)
    assert c["saved_plan"].snapshot.slots[0].option.measurements[0].value == 2
    result = validate_swap(**arguments(c), clock=lambda: 0.0)
    assert result.outcome is SwapOutcome.INSUFFICIENT_DATA
    assert result.verification_complete and result.resulting_plan is None
    assert result.certificate is not None
    for phase in (result.certificate.original, result.certificate.result):
        assert phase.week.status is RuleStatus.UNKNOWN
        assert phase.week.observations[1].value is None
        assert not phase.week.observations[1].complete
        assert all(day.observations[1].value is None for day in phase.days)


@pytest.mark.parametrize("zero", (False, True))
def test_oversized_authority_is_structural_even_without_operational_budget(case, zero):
    # A valid unbounded evidence string reaches the envelope guard. A huge ID
    # would instead exercise the independent 128-character identity constraint.
    authority = case["permission"].authority.model_copy(update={"source": "x" * 1_048_576})
    permission = case["permission"].model_copy(update={"authority": authority})
    with pytest.raises(ValidationError, match="structural envelope"):
        validate_swap(
            **(
                arguments(case, capacity=limits(max_full_validations=0) if zero else limits())
                | dict(permission=permission)
            )
        )


def test_timeout_wire_has_no_plan_or_completed_claim():
    from savora_ai.core.reasoning.planned_swap import verify_swap_validation
    from savora_ai.schemas.swap_proof import _SwapClaim

    c = make_case(copies=2)
    result = validate_swap(**arguments(c), clock=lambda: 0.0)
    assert result.outcome is SwapOutcome.TIMEOUT and result.stage == "EXECUTION"
    raw = result.model_dump_json(by_alias=True)
    control = _SwapClaim.model_validate_json(raw)
    assert not control.accepted and not control.verification_complete
    assert control.resulting_plan is None and control.certificate is None
    assert len(raw.encode()) < 1_048_576
    report = verify_swap_validation(result, **arguments(c), clock=lambda: 0.0)
    assert not report.accepted and not report.complete and report.reason == "UNVERIFIED_TIMEOUT"


def test_public_request_ingress_and_unchecked_target(case):
    from savora_ai.schemas.candidates import validate_contract_json

    raw = case["request"].model_dump_json(by_alias=True)
    duplicate = raw[:-1] + ',"recordId":"attacker"}'
    with pytest.raises(ValidationError):
        validate_contract_json(s.PlannedSwapRequest, duplicate)
    hostile = case["request"].model_copy(update={"target": None})
    with pytest.raises(ValidationError):
        validate_swap(
            **(arguments(case, capacity=limits(max_full_validations=0)) | dict(request=hostile))
        )
