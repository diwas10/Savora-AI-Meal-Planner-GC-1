"""Prospective reservation equations and hostile declaration boundaries, no execution."""

import hashlib
import json
from typing import Any

import pytest
from pydantic import ValidationError
from test_planned_swap_contracts import foundation_case, proposed, rebuild, reference
from test_weekly_contracts import evidence

from savora_ai.schemas import planned_swap as s
from savora_ai.schemas import swap_proof as p
from savora_ai.schemas.candidates import validate_contract_json


@pytest.fixture(scope="module")
def case():
    return foundation_case()


def limits(selection=False, **changes):
    body = dict(
        max_reserved_work=s.SwapWork(**{name: 1_000_000 for name in s.SwapWork.model_fields}),
        max_proof_records=1024,
        max_proof_bytes=1_048_576,
        max_result_bytes=1_048_576,
        max_full_validations=51 if selection else 1,
    )
    if selection:
        body["max_domain_visits"] = 50
    return (s.SwapSelectionLimits if selection else s.SwapValidationLimits).model_validate(
        body | changes
    )


def reservation(operation, items=1, payload_bytes=0) -> dict[str, Any]:
    # Independent explicit cost equation, not the production validator's implementation.
    execution = {name: 0 for name in s.SwapWork.model_fields}
    execution[operation.value] = items
    verification = execution.copy()
    verification["checker_steps"] += int(items > 0)
    total = {name: execution[name] + verification[name] for name in execution}
    return dict(
        operation=operation,
        items=items,
        payload_bytes=payload_bytes,
        execution=s.SwapWork(**execution),
        verification=s.SwapWork(**verification),
        reserved=s.SwapWork(**total),
        proof_records=int(items > 0),
        proof_bytes=payload_bytes + 1024 if items else 0,
    )


def certificate(case, *, selection=False):
    plan = p.SwapReservationPlan(limits=limits(selection), operations=(), result_bytes_reserved=0)
    ordered = {"policy": "synthetic-swap-ordered-events.v1", "events": []}
    digest = hashlib.sha256(
        json.dumps(ordered, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return p.SwapValidationCertificate(
        request=case["request"], events=(), event_digest=digest, reservations=plan
    )


@pytest.mark.parametrize("operation", tuple(p.SwapOperation))
@pytest.mark.parametrize("items", (0, 1, 7))
def test_exact_operation_cost_schedule(operation, items):
    op = p.SwapOperationReservation(**reservation(operation, items))
    assert not op.executed
    assert op.reserved.model_dump() == {
        name: getattr(op.execution, name) + getattr(op.verification, name)
        for name in s.SwapWork.model_fields
    }


@pytest.mark.parametrize(
    "resource", ("work", "records", "bytes", "result", "validations", "domain")
)
def test_exact_and_one_short_reservations(resource):
    operation = (
        p.SwapOperation.FULL_VALIDATION
        if resource == "validations"
        else (p.SwapOperation.DOMAIN_VISIT if resource == "domain" else p.SwapOperation.DAY)
    )
    op = p.SwapOperationReservation(**reservation(operation, payload_bytes=12))
    capacities: dict[str, Any] = dict(
        max_reserved_work=op.reserved,
        max_proof_records=1,
        max_proof_bytes=1036,
        max_result_bytes=25,
        max_full_validations=int(resource == "validations"),
        max_domain_visits=int(resource == "domain"),
    )
    exact = s.SwapSelectionLimits(**capacities)
    p.SwapReservationPlan(limits=exact, operations=(op,), result_bytes_reserved=25)
    if resource == "work":
        work = op.reserved.model_dump()
        work[operation.value] -= 1
        capacities["max_reserved_work"] = s.SwapWork(**work)
    else:
        key = {
            "records": "max_proof_records",
            "bytes": "max_proof_bytes",
            "result": "max_result_bytes",
            "validations": "max_full_validations",
            "domain": "max_domain_visits",
        }[resource]
        capacities[key] -= 1
    with pytest.raises(ValidationError):
        p.SwapReservationPlan(
            limits=s.SwapSelectionLimits(**capacities), operations=(op,), result_bytes_reserved=25
        )


def test_zero_schedule_has_no_claimed_work():
    cap = limits(
        max_reserved_work=s.SwapWork(),
        max_proof_records=0,
        max_proof_bytes=0,
        max_result_bytes=0,
        max_full_validations=0,
    )
    plan = p.SwapReservationPlan(limits=cap, operations=(), result_bytes_reserved=0)
    assert plan.actual_execution == s.SwapWork() and plan.actual_verification == s.SwapWork()
    with pytest.raises(ValidationError):
        p.SwapReservationPlan(
            limits=cap,
            operations=(),
            result_bytes_reserved=0,
            actual_execution=s.SwapWork(checker_steps=1),
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_cache_entries", True),
        ("max_cache_entries", 1),
        ("max_proof_records", 1025),
        ("max_proof_bytes", 1_048_577),
        ("max_full_validations", 2),
        ("deadline", float("nan")),
        ("deadline", float("inf")),
        ("max_result_bytes", True),
    ],
)
def test_strict_capacity_ceiling(field, value):
    with pytest.raises(ValidationError):
        limits(**{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("executed", True),
        ("executed", 0),
        ("proof_records", 0),
        ("proof_bytes", 1023),
        ("verification", s.SwapWork()),
        ("reserved", s.SwapWork()),
    ],
)
def test_forged_or_underreserved_operation(field, value):
    with pytest.raises(ValidationError):
        p.SwapOperationReservation(**(reservation(p.SwapOperation.LOCK_COMPARE) | {field: value}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("outcome", "VALID"),
        ("accepted", True),
        ("accepted", 0),
        ("verification_complete", True),
        ("schema_version", "computed-swap-validation-result.v1"),
        ("failure_scope", "CANDIDATE"),
        ("semantic_assessment", "PASS"),
    ],
)
def test_no_affirmative_computed_declaration(case, field, value):
    with pytest.raises(ValidationError):
        p.SwapValidationDeclaration.model_validate(
            dict(request=case["request"], saved_plan=case["saved_plan"]) | {field: value}
        )


def test_structural_proposed_plan_is_not_success(case):
    declaration = p.SwapValidationDeclaration(
        request=case["request"],
        saved_plan=case["saved_plan"],
        proposed_plan=proposed(case),
        certificate=certificate(case),
    )
    assert declaration.outcome is None and declaration.accepted is False
    assert declaration.verification_complete is False
    assert (
        validate_contract_json(
            p.SwapValidationDeclaration, declaration.model_dump_json(by_alias=True)
        )
        == declaration
    )


def test_domain_and_ranking_declarations(case):
    domain = s.SwapReplacementDomain.build(
        dict(
            record_id="replacement-domain",
            version="1",
            request=case["request"],
            sources=case["sources"],
            options=tuple(o.reference for o in case["sources"].options),
        )
    )
    ranking = s.SyntheticSwapRanking.build(
        dict(
            record_id="rank",
            version="1",
            domain=domain,
            policy="synthetic-fixed-combination-rank.v1",
            eligible=domain.options,
            entries=tuple(
                s.SyntheticRankEntry(option=o, priority=0) for o in reversed(domain.options)
            ),
            ranker_version="fixture-rank.v1",
            evidence=(evidence(),),
        )
    )
    cert = p.SwapSelectionCertificate(
        request=case["request"],
        domain=domain,
        ranking=ranking,
        transcript=certificate(case, selection=True),
    )
    declaration = p.SwapSelectionDeclaration(certificate=cert)
    assert declaration.outcome is None and not declaration.accepted
    with pytest.raises(ValidationError):
        rebuild(ranking, entries=ranking.entries[:-1])
    with pytest.raises(ValidationError):
        rebuild(domain, options=domain.options * 2)


@pytest.mark.parametrize("attack", ("reorder", "duplicate", "gap", "relabel", "outcome"))
def test_ordered_events_and_cross_protocol_attack(case, attack):
    events = tuple(
        p.SwapProofEventDeclaration(
            sequence=i,
            kind=kind,
            input_reference=reference(case["sources"]),
            payload_digest=str(i + 1) * 64,
        )
        for i, kind in enumerate(("SOURCE", "LOCKS"))
    )
    body = {
        "policy": "synthetic-swap-ordered-events.v1",
        "events": [e.model_dump(mode="json", by_alias=True) for e in events],
    }
    digest = hashlib.sha256(
        json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    cert = certificate(case)
    data = cert.model_dump() | dict(events=events, event_digest=digest)
    if attack == "reorder":
        data["events"] = events[::-1]
    elif attack == "duplicate":
        data["events"] = (events[0], events[0])
    elif attack == "gap":
        data["events"] = (events[0], events[1].model_copy(update={"sequence": 3}))
    elif attack == "relabel":
        data["policy"] = "synthetic-weekly-ordered-coverage.v2"
    else:
        data["outcome"] = "REJECTED"
    with pytest.raises(ValidationError):
        p.SwapValidationCertificate.model_validate(data)


def test_computed_apis_absent():
    from savora_ai.core.reasoning import planned_swap

    for name in (
        "validate_swap",
        "verify_swap_validation",
        "select_swap_replacement",
        "verify_swap_selection",
    ):
        assert not hasattr(planned_swap, name)
    for name in ("ComputedSwapValidationResult", "ComputedSwapSelectionResult"):
        assert not hasattr(s, name)
