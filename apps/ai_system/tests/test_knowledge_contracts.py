"""Synthetic contract tests. Fixture quantities have no clinical or nutritional meaning."""

import json
from collections.abc import Iterator
from enum import StrEnum
from itertools import permutations
from typing import Any

import pytest
from pydantic import (
    AliasChoices,
    AliasPath,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
)

from savora_ai.schemas import (
    ApplicabilityStatus,
    ApprovalStatus,
    EvidenceReference,
    FactObservation,
    MeasurementUnit,
    PredicateOperator,
    RuleDefinition,
    RuleDomain,
    RuleEnvironment,
    RuleEvaluation,
    RuleLifecycle,
    RuleReference,
    RuleScope,
    RuleSeverity,
    RuleStatus,
    RuleTrace,
    aggregate_hard_status,
    is_candidate_eligible,
)
from savora_ai.schemas.reasoning import _validation_payload


def evidence(**changes: Any) -> EvidenceReference:
    data: dict[str, Any] = {
        "evidence_id": "synthetic-evidence",
        "version": "fixture-v1",
        "source": "Synthetic unit-test fixture; no medical meaning",
        "locator": "urn:savora:test:fixture",
        "environment": RuleEnvironment.SYNTHETIC,
    }
    return EvidenceReference.model_validate(data | changes)


def rule(**changes: Any) -> RuleDefinition:
    data: dict[str, Any] = {
        "rule_id": "synthetic-rule",
        "version": "fixture-v1",
        "scope": RuleScope.RECIPE,
        "severity": RuleSeverity.ABSOLUTE,
        "domain": RuleDomain.DIETARY,
        "attribute": "fixture_quantity",
        "operator": PredicateOperator.LE,
        "value": 7,
        "unit": MeasurementUnit.DIMENSIONLESS,
        "required_facts": ("fixture_quantity",),
        "applicability_reference": RuleReference(
            rule_id="synthetic-applicability", version="fixture-v1"
        ),
        "evidence": (evidence(),),
        "rationale": "Synthetic predicate; not a nutrition threshold",
        "lifecycle": RuleLifecycle.ACTIVE,
        "approval_status": ApprovalStatus.PENDING,
        "environment": RuleEnvironment.SYNTHETIC,
    }
    return RuleDefinition.model_validate(data | changes)


def fact(**changes: Any) -> FactObservation:
    data: dict[str, Any] = {
        "fact_id": "fixture_quantity",
        "value": 3,
        "unit": MeasurementUnit.DIMENSIONLESS,
        "complete": True,
        "evidence": (evidence(),),
    }
    return FactObservation.model_validate(data | changes)


def evaluation(definition: RuleDefinition | None = None, **changes: Any) -> RuleEvaluation:
    data: dict[str, Any] = {
        "rule": definition if definition is not None else rule(),
        "applicability": ApplicabilityStatus.APPLICABLE,
        "applicability_evidence": (evidence(),),
        "facts": (fact(),),
        "status": RuleStatus.PASS,
        "reason": "Synthetic declared result, not executed by these contracts",
    }
    return RuleEvaluation.model_validate(data | changes)


def trace(
    required: tuple[RuleDefinition, ...] = (),
    results: tuple[RuleEvaluation, ...] = (),
    **changes: Any,
) -> RuleTrace:
    data: dict[str, Any] = {
        "candidate_id": "synthetic-candidate",
        "context_id": "synthetic-context",
        "manifest_id": "synthetic-manifest",
        "manifest_version": "fixture-v1",
        "required_checks": required,
        "evaluations": results,
    }
    return RuleTrace.model_validate(data | changes)


def test_valid_declarations_and_public_references() -> None:
    definition = rule()
    result = evaluation(definition)
    declared_trace = trace((definition,), (result,))
    assert definition.value == 7
    assert definition.evidence[0].environment is RuleEnvironment.SYNTHETIC
    assert result.facts[0].value == 3
    assert aggregate_hard_status(declared_trace) is RuleStatus.PASS


@pytest.mark.parametrize(
    "field",
    ["rule_id", "version", "attribute", "rationale"],
)
@pytest.mark.parametrize("invalid", ["", " \t\n", None, 12])
def test_rule_rejects_blank_or_wrong_type_text(field: str, invalid: Any) -> None:
    with pytest.raises(ValidationError):
        rule(**{field: invalid})


@pytest.mark.parametrize("field", ["rule_id", "version"])
def test_rule_identity_is_required(field: str) -> None:
    data = rule().model_dump()
    del data[field]
    with pytest.raises(ValidationError):
        RuleDefinition.model_validate(data)


@pytest.mark.parametrize("field", ["rule_id", "version"])
def test_rule_reference_rejects_missing_and_blank_identity(field: str) -> None:
    data = {"rule_id": "synthetic", "version": "fixture-v1"}
    del data[field]
    with pytest.raises(ValidationError):
        RuleReference.model_validate(data)
    data[field] = " "
    with pytest.raises(ValidationError):
        RuleReference.model_validate(data)


@pytest.mark.parametrize(
    "field",
    ["scope", "severity", "domain", "operator", "environment", "lifecycle", "approval_status"],
)
def test_unsupported_enum_tokens_rejected_on_json_boundary(field: str) -> None:
    data = rule().model_dump(mode="json")
    data[field] = "UNSUPPORTED"
    with pytest.raises(ValidationError):
        RuleDefinition.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("field", ["evidence_id", "version", "source", "locator"])
@pytest.mark.parametrize("invalid", ["", " \n", None])
def test_evidence_provenance_fields_required(field: str, invalid: Any) -> None:
    with pytest.raises(ValidationError):
        evidence(**{field: invalid})


@pytest.mark.parametrize("field", ["evidence_id", "version", "source", "locator", "environment"])
def test_evidence_provenance_cannot_be_omitted(field: str) -> None:
    data = evidence().model_dump()
    del data[field]
    with pytest.raises(ValidationError):
        EvidenceReference.model_validate(data)


def test_rules_require_evidence_and_reject_duplicate_identity() -> None:
    with pytest.raises(ValidationError, match="source evidence"):
        rule(evidence=())
    with pytest.raises(ValidationError, match="duplicate evidence"):
        rule(evidence=(evidence(), evidence(source="Conflicting synthetic source")))
    assert len(rule(evidence=(evidence(), evidence(version="fixture-v2"))).evidence) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": float("-inf")},
        {"value": -1},
        {"value": True},
        {"value": "7"},
        {"value": None},
        {"value": 3, "unit": None},
        {"value": 101, "unit": MeasurementUnit.PERCENT},
        {"unit": "kg"},
        {"value": ("synthetic-tag",)},
        {"value": [], "operator": PredicateOperator.IN, "unit": None},
        {"value": (), "operator": PredicateOperator.IN, "unit": None},
        {"value": ("tag", "tag"), "operator": PredicateOperator.IN, "unit": None},
        {"value": "tag", "operator": PredicateOperator.IN, "unit": None},
        {"value": False, "operator": PredicateOperator.LT, "unit": None},
    ],
)
def test_invalid_predicate_values_and_units(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        rule(**changes)


@pytest.mark.parametrize("operator", list(PredicateOperator))
def test_supported_operators(operator: PredicateOperator) -> None:
    if operator in (PredicateOperator.IN, PredicateOperator.NOT_IN):
        declaration = rule(operator=operator, value=("synthetic-tag",), unit=None)
    else:
        declaration = rule(operator=operator)
    assert declaration.operator is operator


@pytest.mark.parametrize("unit", list(MeasurementUnit))
def test_supported_measurement_units(unit: MeasurementUnit) -> None:
    assert rule(unit=unit).unit is unit


@pytest.mark.parametrize("value", [False, True, "synthetic-tag"])
def test_boolean_and_categorical_equality(value: bool | str) -> None:
    declaration = rule(operator=PredicateOperator.EQ, value=value, unit=None)
    result = evaluation(declaration, facts=(fact(value=value, unit=None),))
    assert result.status is RuleStatus.PASS


@pytest.mark.parametrize("value", [0, 0.0, 100])
def test_numeric_boundary_values_are_preserved(value: int | float) -> None:
    assert rule(value=value, unit=MeasurementUnit.PERCENT).value == value


@pytest.mark.parametrize("required", [(), ("other",), ("fixture_quantity", "fixture_quantity")])
def test_required_fact_manifest_must_cover_attribute_and_be_unique(
    required: tuple[str, ...],
) -> None:
    with pytest.raises(ValidationError):
        rule(required_facts=required)


@pytest.mark.parametrize(
    "changes",
    [
        {"approved_by": "synthetic-reviewer"},
        {"approval_reference": evidence()},
        {"approval_status": ApprovalStatus.APPROVED},
        {"approval_status": ApprovalStatus.APPROVED, "approved_by": "synthetic-reviewer"},
        {"approval_status": ApprovalStatus.APPROVED, "approval_reference": evidence()},
        {
            "approval_status": ApprovalStatus.APPROVED,
            "approved_by": " ",
            "approval_reference": evidence(),
        },
        {"approval_status": ApprovalStatus.REJECTED},
    ],
)
def test_contradictory_approval_metadata(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        rule(**changes)


def test_approved_synthetic_rule_and_retired_rejected_rule() -> None:
    assert (
        rule(
            approval_status=ApprovalStatus.APPROVED,
            approved_by="synthetic-reviewer",
            approval_reference=evidence(),
        ).approval_status
        is ApprovalStatus.APPROVED
    )
    assert (
        rule(lifecycle=RuleLifecycle.RETIRED, approval_status=ApprovalStatus.REJECTED).lifecycle
        is RuleLifecycle.RETIRED
    )


@pytest.mark.parametrize("severity", list(RuleSeverity))
def test_unapproved_production_active_clinical_rules_rejected(severity: RuleSeverity) -> None:
    with pytest.raises(ValidationError, match="require approval"):
        rule(domain=RuleDomain.CLINICAL, environment=RuleEnvironment.PRODUCTION, severity=severity)


def test_approval_does_not_make_synthetic_evidence_production_ready() -> None:
    with pytest.raises(ValidationError, match="non-synthetic evidence"):
        rule(
            domain=RuleDomain.CLINICAL,
            environment=RuleEnvironment.PRODUCTION,
            approval_status=ApprovalStatus.APPROVED,
            approved_by="synthetic-reviewer",
            approval_reference=evidence(),
        )


def test_synthetic_clinical_declaration_is_not_production_activation() -> None:
    assert rule(domain=RuleDomain.CLINICAL).environment is RuleEnvironment.SYNTHETIC


@pytest.mark.parametrize(
    "changes",
    [
        {"complete": "true"},
        {"complete": 1},
        {"evidence": ()},
        {"value": None},
        {"value": None, "complete": False},
        {"value": True},
        {"value": float("nan")},
        {"value": -2},
        {"value": "3"},
        {"value": 3, "unit": None},
        {"evidence": (evidence(), evidence())},
    ],
)
def test_invalid_fact_observations(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        fact(**changes)


@pytest.mark.parametrize(
    "facts", [(), (fact(value=None, unit=None, complete=False),), (fact(complete=False),)]
)
@pytest.mark.parametrize("status", [RuleStatus.PASS, RuleStatus.FAIL])
def test_missing_null_or_incomplete_facts_cannot_claim_resolved_status(
    facts: tuple[FactObservation, ...], status: RuleStatus
) -> None:
    with pytest.raises(ValidationError, match="present and complete"):
        evaluation(facts=facts, status=status)


@pytest.mark.parametrize(
    "facts", [(), (fact(value=None, unit=None, complete=False),), (fact(complete=False),)]
)
def test_missing_null_and_incomplete_facts_remain_unknown(
    facts: tuple[FactObservation, ...],
) -> None:
    result = evaluation(status=RuleStatus.UNKNOWN, facts=facts)
    assert aggregate_hard_status(trace((rule(),), (result,))) is RuleStatus.UNKNOWN
    if facts:
        assert result.facts[0].value == facts[0].value
        assert result.facts[0].complete is False


def test_every_required_fact_is_needed_and_extra_facts_do_not_fill_gaps() -> None:
    definition = rule(required_facts=("fixture_quantity", "synthetic_context"))
    with pytest.raises(ValidationError, match="present and complete"):
        evaluation(definition, facts=(fact(), fact(fact_id="irrelevant")))
    complete_result = evaluation(
        definition,
        facts=(fact(), fact(fact_id="synthetic_context", value=False, unit=None)),
    )
    assert aggregate_hard_status(trace((definition,), (complete_result,))) is RuleStatus.PASS


def test_duplicate_facts_and_mismatched_units_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate fact"):
        evaluation(facts=(fact(), fact()))
    with pytest.raises(ValidationError, match="units must match"):
        evaluation(facts=(fact(unit=MeasurementUnit.MG),))


def test_declared_fact_type_must_match_predicate_type() -> None:
    definition = rule(value=False, operator=PredicateOperator.EQ, unit=None)
    with pytest.raises(ValidationError, match="type must match"):
        evaluation(definition, facts=(fact(value="false", unit=None),))
    definition = rule(value=("tag",), operator=PredicateOperator.IN, unit=None)
    with pytest.raises(ValidationError, match="scalar strings"):
        evaluation(definition, facts=(fact(value=(), unit=None),))


@pytest.mark.parametrize("status", list(RuleStatus))
def test_pass_fail_unknown_and_eligibility(status: RuleStatus) -> None:
    result = aggregate_hard_status(trace((rule(),), (evaluation(status=status),)))
    assert result is status
    assert is_candidate_eligible(result) is (status is RuleStatus.PASS)


def test_eligibility_does_not_accept_unvalidated_strings() -> None:
    assert not is_candidate_eligible("PASS")  # type: ignore[arg-type]


def test_missing_expected_checks_prevent_false_pass() -> None:
    first, second = rule(), rule(rule_id="second-synthetic-rule")
    assert aggregate_hard_status(trace((first, second), (evaluation(first),))) is RuleStatus.UNKNOWN
    assert aggregate_hard_status(trace((first,))) is RuleStatus.UNKNOWN


def test_empty_manifest_cannot_prove_safety() -> None:
    assert aggregate_hard_status(trace()) is RuleStatus.UNKNOWN


@pytest.mark.parametrize("severity", [RuleSeverity.SOFT, RuleSeverity.INFORMATIONAL])
@pytest.mark.parametrize("status", list(RuleStatus))
def test_nonhard_results_do_not_resolve_missing_hard_checks(
    severity: RuleSeverity, status: RuleStatus
) -> None:
    soft = rule(rule_id="synthetic-advice", severity=severity)
    soft_only = trace((), (evaluation(soft, status=status),))
    missing_hard = trace((rule(),), (evaluation(soft, status=status),))
    assert aggregate_hard_status(soft_only) is RuleStatus.UNKNOWN
    assert aggregate_hard_status(missing_hard) is RuleStatus.UNKNOWN


@pytest.mark.parametrize("severity", [RuleSeverity.SOFT, RuleSeverity.INFORMATIONAL])
@pytest.mark.parametrize("status", list(RuleStatus))
def test_nonhard_results_do_not_override_resolved_hard_pass(
    severity: RuleSeverity, status: RuleStatus
) -> None:
    soft = rule(rule_id="synthetic-advice", severity=severity)
    declared = trace((rule(),), (evaluation(), evaluation(soft, status=status)))
    assert aggregate_hard_status(declared) is RuleStatus.PASS


def test_hard_fail_dominates_missing_checks_and_unknown_results() -> None:
    first, second, third = rule(), rule(rule_id="second"), rule(rule_id="third")
    failed = evaluation(first, status=RuleStatus.FAIL)
    unknown = evaluation(second, status=RuleStatus.UNKNOWN)
    declared = trace((first, second, third), (failed, unknown))
    assert aggregate_hard_status(declared) is RuleStatus.FAIL


def test_hard_fail_dominates_unknown_applicability_in_every_order() -> None:
    first, second = rule(), rule(rule_id="second")
    failed = evaluation(first, status=RuleStatus.FAIL)
    unknown = evaluation(
        second,
        applicability=ApplicabilityStatus.UNKNOWN,
        applicability_evidence=(),
        status=RuleStatus.UNKNOWN,
        facts=(),
    )
    for results in permutations((failed, unknown)):
        assert aggregate_hard_status(trace((first, second), results)) is RuleStatus.FAIL


@pytest.mark.parametrize("severity", [RuleSeverity.SOFT, RuleSeverity.INFORMATIONAL])
def test_nonhard_pass_cannot_override_hard_failure(severity: RuleSeverity) -> None:
    soft = rule(rule_id="synthetic-advice", severity=severity)
    declared = trace((rule(),), (evaluation(status=RuleStatus.FAIL), evaluation(soft)))
    assert aggregate_hard_status(declared) is RuleStatus.FAIL


def test_unknown_applicability_is_not_an_exemption() -> None:
    result = evaluation(
        applicability=ApplicabilityStatus.UNKNOWN,
        applicability_evidence=(),
        status=RuleStatus.UNKNOWN,
        facts=(),
    )
    assert aggregate_hard_status(trace((rule(),), (result,))) is RuleStatus.UNKNOWN


@pytest.mark.parametrize(
    "applicability", [ApplicabilityStatus.UNKNOWN, ApplicabilityStatus.NOT_APPLICABLE]
)
@pytest.mark.parametrize("status", [RuleStatus.PASS, RuleStatus.FAIL])
def test_unevaluated_predicate_cannot_declare_pass_or_fail(
    applicability: ApplicabilityStatus, status: RuleStatus
) -> None:
    with pytest.raises(ValidationError, match="unevaluated predicates"):
        evaluation(applicability=applicability, status=status)


@pytest.mark.parametrize(
    "applicability", [ApplicabilityStatus.APPLICABLE, ApplicabilityStatus.NOT_APPLICABLE]
)
def test_resolved_applicability_requires_evidence(applicability: ApplicabilityStatus) -> None:
    with pytest.raises(ValidationError, match="requires evidence"):
        evaluation(
            applicability=applicability, status=RuleStatus.UNKNOWN, applicability_evidence=()
        )


def test_evidenced_not_applicable_resolves_without_predicate_facts() -> None:
    result = evaluation(
        applicability=ApplicabilityStatus.NOT_APPLICABLE, status=RuleStatus.UNKNOWN, facts=()
    )
    assert aggregate_hard_status(trace((rule(),), (result,))) is RuleStatus.PASS
    second = rule(rule_id="second")
    assert aggregate_hard_status(trace((rule(), second), (result,))) is RuleStatus.UNKNOWN
    resolved = trace((rule(), second), (result, evaluation(second)))
    assert aggregate_hard_status(resolved) is RuleStatus.PASS


def test_duplicate_applicability_evidence_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate evidence"):
        evaluation(applicability_evidence=(evidence(), evidence()))


def test_conflicting_duplicate_evaluations_rejected_but_identical_repeats_are_idempotent() -> None:
    with pytest.raises(ValidationError, match="conflicting duplicate"):
        trace((rule(),), (evaluation(), evaluation(status=RuleStatus.FAIL)))
    repeated = trace((rule(),), (evaluation(), evaluation()))
    assert aggregate_hard_status(repeated) is RuleStatus.PASS


def test_duplicate_manifest_entries_and_multiple_versions_rejected() -> None:
    for second in (rule(), rule(version="fixture-v2")):
        with pytest.raises(ValidationError, match="duplicate rule"):
            trace((rule(), second))


def test_version_mismatches_rejected() -> None:
    with pytest.raises(ValidationError, match="version mismatch"):
        trace((rule(),), (evaluation(rule(version="fixture-v2")),))
    soft = rule(severity=RuleSeverity.SOFT)
    with pytest.raises(ValidationError, match="version mismatch"):
        changed = rule(severity=RuleSeverity.SOFT, version="fixture-v2")
        trace((), (evaluation(soft), evaluation(changed)))


@pytest.mark.parametrize(
    "changes",
    [
        {"severity": RuleSeverity.SOFT},
        {"required_facts": ("fixture_quantity", "omitted_context")},
        {"value": 99},
        {"evidence": (evidence(version="fixture-v2"),)},
    ],
)
def test_same_version_cannot_substitute_a_different_definition(changes: dict[str, Any]) -> None:
    changed = rule(**changes)
    result = evaluation(changed, status=RuleStatus.UNKNOWN)
    with pytest.raises(ValidationError, match="differs from required manifest"):
        trace((rule(),), (result,))


def test_manifest_rejects_nonhard_rules_and_unlisted_hard_evaluations() -> None:
    with pytest.raises(ValidationError, match="only ABSOLUTE"):
        trace((rule(severity=RuleSeverity.SOFT),))
    with pytest.raises(ValidationError, match="absent from required manifest"):
        trace((), (evaluation(),))


@pytest.mark.parametrize("field", ["candidate_id", "context_id", "manifest_id", "manifest_version"])
def test_trace_identity_is_required_and_nonblank(field: str) -> None:
    data = trace().model_dump()
    data[field] = " "
    with pytest.raises(ValidationError):
        RuleTrace.model_validate(data)
    data = trace().model_dump()
    del data[field]
    with pytest.raises(ValidationError):
        RuleTrace.model_validate(data)


def test_serialization_round_trip_retains_versions_evidence_and_nulls() -> None:
    definition = rule()
    gap = fact(value=None, complete=False, unit=None)
    declared = trace((definition,), (evaluation(status=RuleStatus.UNKNOWN, facts=(gap,)),))
    wire = declared.model_dump_json(by_alias=True)
    assert '"requiredChecks"' in wire
    assert '"evidenceId"' in wire
    restored = RuleTrace.model_validate_json(wire)
    assert restored == declared
    assert restored.required_checks[0].version == "fixture-v1"
    assert restored.evaluations[0].facts[0].value is None
    assert aggregate_hard_status(restored) is RuleStatus.UNKNOWN
    rule_wire = definition.model_dump_json(by_alias=True)
    assert RuleDefinition.model_validate_json(rule_wire) == definition
    assert EvidenceReference.model_validate_json(evidence().model_dump_json()) == evidence()
    reference = definition.applicability_reference
    assert RuleReference.model_validate_json(reference.model_dump_json()) == reference


@pytest.mark.parametrize(
    ("value", "unit"),
    [(0, MeasurementUnit.DIMENSIONLESS), (False, None), ((), None)],
)
def test_explicit_zero_false_and_empty_set_are_preserved(
    value: int | bool | tuple[str, ...], unit: MeasurementUnit | None
) -> None:
    observation = fact(value=value, unit=unit)
    restored = FactObservation.model_validate_json(observation.model_dump_json(by_alias=True))
    assert restored == observation
    assert restored.value is not None
    assert type(restored.value) is type(value)
    assert restored.complete is True


def test_nested_models_and_collections_are_immutable() -> None:
    declared = trace((rule(),), (evaluation(),))
    with pytest.raises(ValidationError, match="frozen_instance"):
        declared.manifest_version = "fixture-v2"
    with pytest.raises(ValidationError, match="frozen_instance"):
        declared.required_checks[0].value = 8
    with pytest.raises(ValidationError, match="frozen_instance"):
        declared.evaluations[0].facts[0].complete = False
    with pytest.raises(ValidationError, match="frozen_instance"):
        declared.required_checks[0].evidence[0].source = "changed"
    assert isinstance(declared.required_checks, tuple)
    assert isinstance(declared.required_checks[0].evidence, tuple)
    assert isinstance(declared.evaluations[0].facts, tuple)


@pytest.mark.parametrize(
    "changes",
    [
        {"scope": "RECIPE"},
        {"required_facts": ["fixture_quantity"]},
        {"evidence": [evidence()]},
        {"unrecognized_field": "rejected"},
    ],
)
def test_python_boundary_is_strict_and_forbids_extra_fields(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        rule(**changes)


def test_nested_instances_are_revalidated_instead_of_trusting_unchecked_copies() -> None:
    unchecked = rule().model_copy(update={"value": True})
    with pytest.raises(ValidationError):
        trace((unchecked,))


@pytest.mark.parametrize("field", ["status", "applicability"])
def test_reasoning_rejects_invalid_json_enum_tokens(field: str) -> None:
    data = evaluation().model_dump(mode="json")
    data[field] = "UNSUPPORTED"
    with pytest.raises(ValidationError):
        RuleEvaluation.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("mode", ["pass", "fail", "unknown", "not_applicable"])
def test_evaluation_and_manifest_order_independence(mode: str) -> None:
    first, second, third = rule(), rule(rule_id="second"), rule(rule_id="third")
    if mode == "not_applicable":
        result = evaluation(
            first,
            applicability=ApplicabilityStatus.NOT_APPLICABLE,
            status=RuleStatus.UNKNOWN,
            facts=(),
        )
        expected = RuleStatus.PASS
    else:
        expected = {
            "pass": RuleStatus.PASS,
            "fail": RuleStatus.FAIL,
            "unknown": RuleStatus.UNKNOWN,
        }[mode]
        result = evaluation(first, status=expected)
    results = (result, evaluation(second), evaluation(third))
    for required_order in permutations((first, second, third)):
        for evaluation_order in permutations(results):
            assert aggregate_hard_status(trace(required_order, evaluation_order)) is expected


def test_declared_predicate_truth_is_not_executed_by_phase_one() -> None:
    # Deliberately inconsistent synthetic declaration demonstrates the documented boundary.
    result = evaluation(facts=(fact(value=99),), status=RuleStatus.PASS)
    assert aggregate_hard_status(trace((rule(),), (result,))) is RuleStatus.PASS


def test_aggregation_rejects_original_unchecked_missing_facts_exploit() -> None:
    passing = trace((rule(),), (evaluation(),))
    assert aggregate_hard_status(passing) is RuleStatus.PASS
    unchecked_evaluation = passing.evaluations[0].model_copy(update={"facts": ()})
    unchecked_trace = passing.model_copy(update={"evaluations": (unchecked_evaluation,)})
    with pytest.raises(ValidationError, match="present and complete"):
        aggregate_hard_status(unchecked_trace)


def test_aggregation_validates_plain_data_without_any_nested_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    passing = trace((rule(),), (evaluation(),))
    original_validate = RuleTrace.model_validate

    def assert_no_models(value: object) -> None:
        assert not isinstance(value, BaseModel)
        if isinstance(value, dict):
            for item in value.values():
                assert_no_models(item)
        elif isinstance(value, (tuple, list)):
            for item in value:
                assert_no_models(item)

    def capture_validate(payload: Any, **kwargs: Any) -> RuleTrace:
        assert_no_models(payload)
        assert isinstance(payload["required_checks"], tuple)
        assert kwargs["strict"] is True
        return original_validate(payload, **kwargs)

    monkeypatch.setattr(RuleTrace, "model_validate", capture_validate)
    assert aggregate_hard_status(passing) is RuleStatus.PASS


@pytest.mark.parametrize(
    "changes",
    [
        {"value": True},
        {"required_facts": ()},
        {"version": " "},
        {"lifecycle": RuleLifecycle.DRAFT},
        {"approval_status": ApprovalStatus.APPROVED},
        {"unexpected_rule_field": 1},
    ],
)
def test_aggregation_rejects_unchecked_rule_definitions(changes: dict[str, Any]) -> None:
    passing = trace((rule(),), (evaluation(),))
    unchecked_rule = passing.required_checks[0].model_copy(update=changes)
    unchecked_evaluation = passing.evaluations[0].model_copy(update={"rule": unchecked_rule})
    unchecked_trace = passing.model_copy(
        update={"required_checks": (unchecked_rule,), "evaluations": (unchecked_evaluation,)}
    )
    with pytest.raises(ValidationError):
        aggregate_hard_status(unchecked_trace)


@pytest.mark.parametrize(
    "changes",
    [
        {"locator": " "},
        {"source": None},
        {"environment": "SYNTHETIC"},
        {"evidence_id": ""},
        {"unexpected_evidence_field": 1},
    ],
)
def test_aggregation_rejects_unchecked_nested_evidence(changes: dict[str, Any]) -> None:
    passing = trace((rule(),), (evaluation(),))
    unchecked_evidence = evidence().model_copy(update=changes)
    unchecked_fact = fact().model_copy(update={"evidence": (unchecked_evidence,)})
    unchecked_evaluation = passing.evaluations[0].model_copy(update={"facts": (unchecked_fact,)})
    unchecked_trace = passing.model_copy(update={"evaluations": (unchecked_evaluation,)})
    with pytest.raises(ValidationError) as error:
        aggregate_hard_status(unchecked_trace)
    assert any("evidence" in item["loc"] for item in error.value.errors())


@pytest.mark.parametrize(
    "changes",
    [{"value": None}, {"complete": False}, {"complete": 1}, {"unit": "dimensionless"}],
)
def test_aggregation_rejects_unchecked_invalid_observations(changes: dict[str, Any]) -> None:
    passing = trace((rule(),), (evaluation(),))
    unchecked_fact = fact().model_copy(update=changes)
    unchecked_evaluation = passing.evaluations[0].model_copy(update={"facts": (unchecked_fact,)})
    unchecked_trace = passing.model_copy(update={"evaluations": (unchecked_evaluation,)})
    with pytest.raises(ValidationError):
        aggregate_hard_status(unchecked_trace)


@pytest.mark.parametrize(
    ("required", "message"),
    [
        ([], "valid tuple"),
        ((), "absent from required manifest"),
        ((rule(), rule()), "duplicate rule"),
        ((rule(version="fixture-v2"),), "version mismatch"),
        ((rule(severity=RuleSeverity.SOFT),), "only ABSOLUTE"),
    ],
)
def test_aggregation_rejects_unchecked_manifest_changes(required: Any, message: str) -> None:
    passing = trace((rule(),), (evaluation(),))
    unchecked_trace = passing.model_copy(update={"required_checks": required})
    with pytest.raises(ValidationError, match=message):
        aggregate_hard_status(unchecked_trace)


def test_aggregation_does_not_drop_unknown_unchecked_fields() -> None:
    passing = trace((rule(),), (evaluation(),))
    unchecked_trace = passing.model_copy(update={"unexpected_trace_field": 1})
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        aggregate_hard_status(unchecked_trace)


def test_aggregation_reports_cyclic_unchecked_payload_as_validation_error() -> None:
    passing = trace((rule(),), (evaluation(),))
    cyclic: dict[str, Any] = {}
    cyclic["rule"] = cyclic
    unchecked_trace = passing.model_copy(update={"required_checks": (cyclic,)})
    with pytest.raises(ValidationError, match="cyclic or excessively deep"):
        aggregate_hard_status(unchecked_trace)


@pytest.mark.parametrize("lifecycle", [RuleLifecycle.DRAFT, RuleLifecycle.RETIRED])
def test_eligibility_manifests_reject_inactive_rules(lifecycle: RuleLifecycle) -> None:
    inactive = rule(lifecycle=lifecycle)
    with pytest.raises(ValidationError, match="manifests require ACTIVE"):
        trace((inactive,))


@pytest.mark.parametrize("lifecycle", [RuleLifecycle.DRAFT, RuleLifecycle.RETIRED])
@pytest.mark.parametrize("severity", list(RuleSeverity))
def test_eligibility_evaluations_reject_inactive_rules(
    lifecycle: RuleLifecycle, severity: RuleSeverity
) -> None:
    inactive = rule(lifecycle=lifecycle, severity=severity)
    with pytest.raises(ValidationError, match="evaluations require ACTIVE"):
        evaluation(
            inactive,
            applicability=ApplicabilityStatus.NOT_APPLICABLE,
            status=RuleStatus.UNKNOWN,
            facts=(),
        )


@pytest.mark.parametrize("lifecycle", [RuleLifecycle.DRAFT, RuleLifecycle.RETIRED])
def test_inactive_production_clinical_rules_cannot_bypass_eligibility(
    lifecycle: RuleLifecycle,
) -> None:
    inactive = rule(
        domain=RuleDomain.CLINICAL,
        environment=RuleEnvironment.PRODUCTION,
        lifecycle=lifecycle,
    )
    with pytest.raises(ValidationError, match="manifests require ACTIVE"):
        trace((inactive,))
    with pytest.raises(ValidationError, match="evaluations require ACTIVE"):
        evaluation(inactive)


def test_identical_evidence_reuse_across_every_trace_location_is_valid() -> None:
    first = rule(
        approval_status=ApprovalStatus.APPROVED,
        approved_by="synthetic-reviewer",
        approval_reference=evidence(),
    )
    second = rule(rule_id="second-synthetic-rule")
    declared = trace((first, second), (evaluation(first), evaluation(second)))
    assert aggregate_hard_status(declared) is RuleStatus.PASS


@pytest.mark.parametrize("location", ["rule", "approval", "applicability", "fact"])
@pytest.mark.parametrize(
    "changes",
    [
        {"source": "Contradictory synthetic source"},
        {"locator": "urn:savora:test:contradictory-locator"},
        {"environment": RuleEnvironment.PRODUCTION},
    ],
)
def test_trace_rejects_conflicting_provenance_across_reference_locations(
    location: str, changes: dict[str, Any]
) -> None:
    conflicting = evidence(**changes)
    definition = rule()
    result = evaluation(definition)
    if location == "rule":
        definition = rule(evidence=(conflicting,))
        result = evaluation(definition)
    elif location == "approval":
        definition = rule(
            approval_status=ApprovalStatus.APPROVED,
            approved_by="synthetic-reviewer",
            approval_reference=conflicting,
        )
        result = evaluation(definition)
    elif location == "applicability":
        result = evaluation(definition, applicability_evidence=(conflicting,))
    else:
        result = evaluation(definition, facts=(fact(evidence=(conflicting,)),))
    with pytest.raises(ValidationError, match="contradictory evidence provenance"):
        trace((definition,), (result,))


def test_different_evidence_versions_can_have_different_metadata() -> None:
    revised = evidence(version="fixture-v2", source="Revised synthetic source")
    result = evaluation(facts=(fact(evidence=(revised,)),))
    assert aggregate_hard_status(trace((rule(),), (result,))) is RuleStatus.PASS


def test_aggregation_rejects_unchecked_provenance_conflicts() -> None:
    passing = trace((rule(),), (evaluation(),))
    conflicting = evidence(source="Contradictory synthetic source")
    unchecked_evaluation = passing.evaluations[0].model_copy(
        update={"facts": (fact(evidence=(conflicting,)),)}
    )
    unchecked_trace = passing.model_copy(update={"evaluations": (unchecked_evaluation,)})
    with pytest.raises(ValidationError, match="contradictory evidence provenance"):
        aggregate_hard_status(unchecked_trace)


@pytest.mark.parametrize("severity", list(RuleSeverity))
def test_production_approval_reference_gate_with_otherwise_valid_fictional_records(
    severity: RuleSeverity,
) -> None:
    # PRODUCTION is a test metadata label; these are not real clinical sources/approvals.
    source = evidence(
        evidence_id="fictional-production-source",
        source="Fictional metadata fixture; no medical meaning",
        environment=RuleEnvironment.PRODUCTION,
    )
    approval = evidence(
        evidence_id="fictional-production-approval",
        source="Fictional approval metadata; no medical review or approval",
        environment=RuleEnvironment.PRODUCTION,
    )
    valid = rule(
        domain=RuleDomain.CLINICAL,
        environment=RuleEnvironment.PRODUCTION,
        severity=severity,
        evidence=(source,),
        approval_status=ApprovalStatus.APPROVED,
        approved_by="fictional-test-reviewer-not-medical-approval",
        approval_reference=approval,
    )
    data = valid.model_dump()
    data["approval_reference"] = EvidenceReference.model_validate(
        approval.model_dump() | {"environment": RuleEnvironment.SYNTHETIC}
    )
    with pytest.raises(
        ValidationError, match="production clinical approval evidence must be non-synthetic"
    ):
        RuleDefinition.model_validate(data)


@pytest.mark.parametrize("operator", [PredicateOperator.IN, PredicateOperator.NOT_IN])
def test_membership_scalar_observations_are_valid(operator: PredicateOperator) -> None:
    definition = rule(operator=operator, value=("synthetic-tag",), unit=None)
    result = evaluation(definition, facts=(fact(value="synthetic-tag", unit=None),))
    assert aggregate_hard_status(trace((definition,), (result,))) is RuleStatus.PASS


@pytest.mark.parametrize("operator", [PredicateOperator.IN, PredicateOperator.NOT_IN])
@pytest.mark.parametrize("value", [(), ("synthetic-tag",), ("one", "two")])
@pytest.mark.parametrize("status", [RuleStatus.PASS, RuleStatus.UNKNOWN])
def test_membership_collection_observations_are_rejected(
    operator: PredicateOperator, value: tuple[str, ...], status: RuleStatus
) -> None:
    definition = rule(operator=operator, value=("synthetic-tag",), unit=None)
    observation = fact(value=value, unit=None, complete=status is RuleStatus.PASS)
    with pytest.raises(ValidationError, match="scalar strings"):
        evaluation(definition, facts=(observation,), status=status)


@pytest.mark.parametrize("operator", [PredicateOperator.IN, PredicateOperator.NOT_IN])
@pytest.mark.parametrize("facts", [(), (fact(value=None, unit=None, complete=False),)])
def test_missing_or_null_membership_observations_remain_unknown(
    operator: PredicateOperator, facts: tuple[FactObservation, ...]
) -> None:
    definition = rule(operator=operator, value=("synthetic-tag",), unit=None)
    result = evaluation(definition, facts=facts, status=RuleStatus.UNKNOWN)
    assert aggregate_hard_status(trace((definition,), (result,))) is RuleStatus.UNKNOWN


@pytest.mark.parametrize("complete", [False, True])
def test_empty_auxiliary_set_is_resolved_only_with_explicit_completeness(complete: bool) -> None:
    definition = rule(required_facts=("fixture_quantity", "synthetic_context"))
    observation = fact(fact_id="synthetic_context", value=(), unit=None, complete=complete)
    status = RuleStatus.PASS if complete else RuleStatus.UNKNOWN
    result = evaluation(definition, facts=(fact(), observation), status=status)
    assert aggregate_hard_status(trace((definition,), (result,))) is status
    if not complete:
        with pytest.raises(ValidationError, match="present and complete"):
            evaluation(definition, facts=(fact(), observation), status=RuleStatus.PASS)


# This matrix names every Phase 1 enum field; no Phase 2 helpers are imported.
_RULE_ENUM_FIELDS: tuple[tuple[str, type[StrEnum]], ...] = (
    ("scope", RuleScope),
    ("severity", RuleSeverity),
    ("domain", RuleDomain),
    ("operator", PredicateOperator),
    ("unit", MeasurementUnit),
    ("lifecycle", RuleLifecycle),
    ("approval_status", ApprovalStatus),
    ("environment", RuleEnvironment),
)
_NESTED_ENUM_FIELDS: tuple[tuple[str, type[StrEnum]], ...] = (
    ("rule_evidence", RuleEnvironment),
    ("approval_evidence", RuleEnvironment),
    ("applicability_evidence", RuleEnvironment),
    ("fact_evidence", RuleEnvironment),
    ("fact_unit", MeasurementUnit),
    ("evaluation_status", RuleStatus),
    ("evaluation_applicability", ApplicabilityStatus),
)


def _counterfeit_enum(enum_type: type[StrEnum], token: str) -> StrEnum:
    value = str.__new__(enum_type, token)
    value._name_ = token
    value._value_ = token
    return value


def _unchecked_contract(record: Any, changes: dict[str, Any], mode: str) -> Any:
    if mode == "copy":
        return record.model_copy(update=changes)
    return type(record).model_construct(**(vars(record) | changes))


@pytest.mark.parametrize("mode", ["copy", "construct"])
@pytest.mark.parametrize("token", ["ABSOLUTE", "UNDECLARED"])
def test_original_counterfeit_extra_hard_fail_never_returns_pass(mode: str, token: str) -> None:
    required = rule()
    passing = trace((required,), (evaluation(required),))
    extra = rule(rule_id="extra-hard")
    failed = evaluation(extra, status=RuleStatus.FAIL, facts=(fact(value=9),))
    fake = _counterfeit_enum(RuleSeverity, token)
    invalid_rule = _unchecked_contract(extra, {"severity": fake}, mode)
    invalid_evaluation = _unchecked_contract(failed, {"rule": invalid_rule}, mode)
    invalid_trace = _unchecked_contract(
        passing, {"evaluations": (*passing.evaluations, invalid_evaluation)}, mode
    )
    assert invalid_rule.severity is fake
    assert fake is not RuleSeverity.ABSOLUTE
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        is_candidate_eligible(aggregate_hard_status(invalid_trace))
    # Validation rejects the supplied object rather than replacing its enum.
    assert invalid_rule.severity is fake


@pytest.mark.parametrize("mode", ["copy", "construct"])
@pytest.mark.parametrize(
    "field,enum_type,token",
    [
        (field, enum_type, token)
        for field, enum_type in _RULE_ENUM_FIELDS
        for token in (*[member.value for member in enum_type], "UNDECLARED")
    ],
)
def test_every_rule_enum_rejects_counterfeits_at_schema_and_aggregation_boundaries(
    mode: str, field: str, enum_type: type[StrEnum], token: str
) -> None:
    original = rule()
    passing = trace((original,), (evaluation(original),))
    fake = _counterfeit_enum(enum_type, token)
    invalid_rule = _unchecked_contract(original, {field: fake}, mode)
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        RuleDefinition.model_validate(invalid_rule, strict=True)
    invalid_evaluation = _unchecked_contract(passing.evaluations[0], {"rule": invalid_rule}, mode)
    invalid_trace = _unchecked_contract(
        passing,
        {"required_checks": (invalid_rule,), "evaluations": (invalid_evaluation,)},
        mode,
    )
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        RuleTrace.model_validate(invalid_trace, strict=True)
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        is_candidate_eligible(aggregate_hard_status(invalid_trace))
    assert getattr(invalid_rule, field) is fake


@pytest.mark.parametrize("mode", ["copy", "construct"])
@pytest.mark.parametrize(
    "location,enum_type,token",
    [
        (location, enum_type, token)
        for location, enum_type in _NESTED_ENUM_FIELDS
        for token in (*[member.value for member in enum_type], "UNDECLARED")
    ],
)
def test_nested_evidence_fact_and_evaluation_enums_reject_counterfeits(
    mode: str, location: str, enum_type: type[StrEnum], token: str
) -> None:
    original = rule(
        approval_status=ApprovalStatus.APPROVED,
        approved_by="SYNTHETIC reviewer; no real approval",
        approval_reference=evidence(),
    )
    passing = trace((original,), (evaluation(original),))
    fake = _counterfeit_enum(enum_type, token)
    invalid_rule = original
    invalid_evaluation = passing.evaluations[0]
    if location in ("evaluation_status", "evaluation_applicability"):
        field = "status" if location == "evaluation_status" else "applicability"
        invalid_node = _unchecked_contract(invalid_evaluation, {field: fake}, mode)
        invalid_evaluation = invalid_node
    elif location == "fact_unit":
        invalid_node = _unchecked_contract(fact(), {"unit": fake}, mode)
        invalid_evaluation = _unchecked_contract(
            invalid_evaluation, {"facts": (invalid_node,)}, mode
        )
    else:
        invalid_node = _unchecked_contract(evidence(), {"environment": fake}, mode)
        if location in ("rule_evidence", "approval_evidence"):
            updates = (
                {"evidence": (invalid_node,)}
                if location == "rule_evidence"
                else {"approval_reference": invalid_node}
            )
            invalid_rule = _unchecked_contract(original, updates, mode)
            invalid_evaluation = _unchecked_contract(
                invalid_evaluation, {"rule": invalid_rule}, mode
            )
        elif location == "applicability_evidence":
            invalid_evaluation = _unchecked_contract(
                invalid_evaluation, {"applicability_evidence": (invalid_node,)}, mode
            )
        else:
            invalid_fact = _unchecked_contract(fact(), {"evidence": (invalid_node,)}, mode)
            invalid_evaluation = _unchecked_contract(
                invalid_evaluation, {"facts": (invalid_fact,)}, mode
            )
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        type(invalid_node).model_validate(invalid_node, strict=True)
    invalid_trace = _unchecked_contract(
        passing,
        {"required_checks": (invalid_rule,), "evaluations": (invalid_evaluation,)},
        mode,
    )
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        RuleTrace.model_validate(invalid_trace, strict=True)
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        is_candidate_eligible(aggregate_hard_status(invalid_trace))


@pytest.mark.parametrize(
    "field,member",
    [(field, member) for field, enum_type in _RULE_ENUM_FIELDS for member in enum_type],
)
def test_genuine_rule_enum_members_preserve_identity_and_json(field: str, member: StrEnum) -> None:
    changes: dict[str, Any] = {field: member}
    if member in (PredicateOperator.IN, PredicateOperator.NOT_IN):
        changes.update(value=("synthetic-tag",), unit=None)
    elif member is ApprovalStatus.APPROVED:
        changes.update(
            approved_by="SYNTHETIC reviewer; no real approval", approval_reference=evidence()
        )
    elif member is ApprovalStatus.REJECTED:
        changes["lifecycle"] = RuleLifecycle.DRAFT
    accepted = rule(**changes)
    assert getattr(accepted, field) is member
    reloaded = RuleDefinition.model_validate_json(accepted.model_dump_json(by_alias=True))
    assert reloaded == accepted
    assert getattr(reloaded, field) is member


@pytest.mark.parametrize("unit", [*MeasurementUnit, None])
def test_genuine_fact_unit_members_and_null_preserve_json(unit: MeasurementUnit | None) -> None:
    accepted = fact(unit=unit, value=None, complete=False) if unit is None else fact(unit=unit)
    reloaded = FactObservation.model_validate_json(accepted.model_dump_json(by_alias=True))
    assert reloaded == accepted and reloaded.unit is unit


@pytest.mark.parametrize("environment", list(RuleEnvironment))
def test_genuine_evidence_environment_members_preserve_json(environment: RuleEnvironment) -> None:
    # PRODUCTION here is fictional metadata, not an authenticated source.
    accepted = evidence(environment=environment)
    reloaded = EvidenceReference.model_validate_json(accepted.model_dump_json(by_alias=True))
    assert reloaded == accepted and reloaded.environment is environment


@pytest.mark.parametrize(
    "applicability,status,expected",
    [
        (ApplicabilityStatus.APPLICABLE, RuleStatus.PASS, RuleStatus.PASS),
        (ApplicabilityStatus.APPLICABLE, RuleStatus.FAIL, RuleStatus.FAIL),
        (ApplicabilityStatus.APPLICABLE, RuleStatus.UNKNOWN, RuleStatus.UNKNOWN),
        (ApplicabilityStatus.UNKNOWN, RuleStatus.UNKNOWN, RuleStatus.UNKNOWN),
        (ApplicabilityStatus.NOT_APPLICABLE, RuleStatus.UNKNOWN, RuleStatus.PASS),
    ],
)
def test_genuine_evaluation_enum_members_preserve_aggregation_and_json(
    applicability: ApplicabilityStatus, status: RuleStatus, expected: RuleStatus
) -> None:
    definition = rule()
    result = evaluation(definition, applicability=applicability, status=status)
    reloaded = RuleEvaluation.model_validate_json(result.model_dump_json(by_alias=True))
    assert reloaded.applicability is applicability and reloaded.status is status
    aggregated = aggregate_hard_status(trace((definition,), (reloaded,)))
    assert aggregated is expected
    assert is_candidate_eligible(aggregated) is (expected is RuleStatus.PASS)


def test_canonical_extra_hard_fail_is_rejected_or_dominates_when_required() -> None:
    first = rule()
    second = rule(rule_id="extra-hard")
    results = (
        evaluation(first),
        evaluation(second, status=RuleStatus.FAIL, facts=(fact(value=9),)),
    )
    with pytest.raises(ValidationError, match="hard evaluation is absent from required manifest"):
        trace((first,), results)
    complete = trace((first, second), results)
    assert aggregate_hard_status(complete) is RuleStatus.FAIL
    assert not is_candidate_eligible(aggregate_hard_status(complete))


@pytest.mark.parametrize("token", ["PASS", "UNDECLARED"])
def test_counterfeit_status_cannot_be_directly_eligible(token: str) -> None:
    fake = _counterfeit_enum(RuleStatus, token)
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        is_candidate_eligible(fake)  # type: ignore[arg-type]


class _ExtraRuleDefinition(RuleDefinition):
    model_config = ConfigDict(extra="allow", alias_generator=lambda name: "input_" + name)


class _AliasRuleDefinition(_ExtraRuleDefinition):
    severity: RuleSeverity = Field(
        alias="risk",
        serialization_alias="wireSeverity",
        validation_alias=AliasChoices(
            "risk", AliasPath("nested", 0, "risk"), AliasPath("mapping", "risk")
        ),
    )


@pytest.mark.parametrize("mode", ["construct", "copy"])
@pytest.mark.parametrize("shadow", [RuleSeverity.SOFT, RuleSeverity.ABSOLUTE])
def test_colliding_extra_hard_fail_never_returns_pass(mode: str, shadow: RuleSeverity) -> None:
    required = rule()
    passing = trace((required,), (evaluation(required),))
    extra = rule(rule_id="extra-hard")
    data = {"input_" + name: value for name, value in vars(extra).items()}
    payload: dict[str, Any] = data | {"severity": shadow}
    malicious = _ExtraRuleDefinition.model_construct(**payload)
    if mode == "copy":
        malicious = malicious.model_copy()
    assert malicious.severity is RuleSeverity.ABSOLUTE
    assert malicious.model_extra == {"severity": shadow}
    failed = evaluation(extra, status=RuleStatus.FAIL, facts=(fact(value=9),))
    invalid = passing.model_copy(
        update={
            "evaluations": (*passing.evaluations, failed.model_copy(update={"rule": malicious}))
        }
    )
    with pytest.raises(ValidationError, match="colliding DTO"):
        is_candidate_eligible(aggregate_hard_status(invalid))
    assert malicious.severity is RuleSeverity.ABSOLUTE
    assert malicious.model_extra == {"severity": shadow}
    for validate in (
        RuleDefinition.model_validate,
        TypeAdapter(RuleDefinition).validate_python,
    ):
        with pytest.raises(ValidationError, match="colliding DTO"):
            validate(malicious)
    for validate in (RuleTrace.model_validate, TypeAdapter(RuleTrace).validate_python):
        with pytest.raises(ValidationError, match="colliding DTO"):
            validate(invalid)
    with pytest.raises(ValidationError, match="colliding DTO"):
        RuleEvaluation.model_validate(invalid.evaluations[-1])
    with pytest.raises(ValidationError, match="colliding DTO"):
        RuleTrace(**vars(invalid))


@pytest.mark.parametrize("mode", ["construct", "copy"])
@pytest.mark.parametrize(
    "key",
    [
        "severity",
        "input_severity",
        "risk",
        "wireSeverity",
        "nested",
        "mapping",
        "requiredFacts",
        "input_required_facts",
    ],
)
def test_dto_field_and_inherited_alias_collisions_are_rejected(mode: str, key: str) -> None:
    base = rule()
    malicious = _AliasRuleDefinition.model_construct(**vars(base))
    # Set unchecked storage explicitly when a constructor would consume an alias.
    object.__setattr__(malicious, "__pydantic_extra__", {key: RuleSeverity.ABSOLUTE})
    if mode == "copy":
        malicious = malicious.model_copy()
    invalid = trace((base,), (evaluation(base),)).model_copy(
        update={"required_checks": (malicious,)}
    )
    with pytest.raises(ValidationError, match="colliding DTO"):
        aggregate_hard_status(invalid)
    for validate in (
        RuleDefinition.model_validate,
        _AliasRuleDefinition.model_validate,
        TypeAdapter(RuleDefinition).validate_python,
    ):
        with pytest.raises(ValidationError, match="colliding DTO"):
            validate(malicious)
    with pytest.raises(ValidationError, match="colliding DTO"):
        RuleTrace.model_validate(invalid)


@pytest.mark.parametrize("mode", ["construct", "copy"])
@pytest.mark.parametrize("token", ["ABSOLUTE", "SOFT", "UNDECLARED"])
@pytest.mark.parametrize("location", ["field", "extra"])
def test_collisions_cannot_hide_counterfeit_enums(mode: str, token: str, location: str) -> None:
    base = rule()
    fake = _counterfeit_enum(RuleSeverity, token)
    payload: dict[str, Any] = vars(base) | {
        "severity": fake if location == "field" else RuleSeverity.ABSOLUTE
    }
    malicious = _ExtraRuleDefinition.model_construct(**payload)
    object.__setattr__(
        malicious,
        "__pydantic_extra__",
        {"severity": fake if location == "extra" else RuleSeverity.SOFT},
    )
    if mode == "copy":
        malicious = malicious.model_copy()
    invalid = trace((base,), (evaluation(base),)).model_copy(
        update={"required_checks": (malicious,)}
    )
    with pytest.raises(ValidationError, match="colliding DTO"):
        is_candidate_eligible(aggregate_hard_status(invalid))
    with pytest.raises(ValidationError, match="colliding DTO"):
        RuleDefinition.model_validate(malicious)
    with pytest.raises(ValidationError, match="colliding DTO"):
        RuleTrace.model_validate(invalid)


@pytest.mark.parametrize("extras", [[], "", 0, {1: "unexpected"}])
def test_malformed_extra_storage_is_a_validation_error(extras: Any) -> None:
    base = rule()
    malicious = _ExtraRuleDefinition.model_construct(**vars(base))
    object.__setattr__(malicious, "__pydantic_extra__", extras)
    invalid = trace((base,), (evaluation(base),)).model_copy(
        update={"required_checks": (malicious,)}
    )
    with pytest.raises(ValidationError, match="malformed"):
        aggregate_hard_status(invalid)
    with pytest.raises(ValidationError, match="malformed"):
        RuleDefinition.model_validate(malicious)


def test_alias_shadow_in_field_storage_is_rejected() -> None:
    base = rule()
    malicious = base.model_copy(update={"requiredFacts": base.required_facts})
    invalid = trace((base,), (evaluation(base),)).model_copy(
        update={"required_checks": (malicious,)}
    )
    with pytest.raises(ValidationError, match="colliding DTO"):
        aggregate_hard_status(invalid)


def test_alias_shared_by_two_declared_fields_is_rejected() -> None:
    class AmbiguousRule(_AliasRuleDefinition):
        risk: RuleSeverity

    base = rule()
    payload: dict[str, Any] = vars(base) | {"risk": RuleSeverity.ABSOLUTE}
    malicious = AmbiguousRule.model_construct(**payload)
    invalid = trace((base,), (evaluation(base),)).model_copy(
        update={"required_checks": (malicious,)}
    )
    with pytest.raises(ValidationError, match="colliding DTO"):
        aggregate_hard_status(invalid)


def test_duplicate_unknown_keys_are_rejected_before_merging() -> None:
    base = rule()
    malicious = _ExtraRuleDefinition.model_construct(**vars(base))
    vars(malicious)["unexpected"] = 1
    object.__setattr__(malicious, "__pydantic_extra__", {"unexpected": 1})
    invalid = trace((base,), (evaluation(base),)).model_copy(
        update={"required_checks": (malicious,)}
    )
    with pytest.raises(ValidationError, match="colliding DTO"):
        aggregate_hard_status(invalid)


def test_noncolliding_extras_are_retained_for_strict_validation() -> None:
    base = rule()
    payload: dict[str, Any] = vars(base) | {"unexpected": 1}
    malicious = _ExtraRuleDefinition.model_construct(**payload)
    flattened = _validation_payload(malicious)
    assert isinstance(flattened, dict) and flattened["unexpected"] == 1
    invalid = trace((base,), (evaluation(base),)).model_copy(
        update={"required_checks": (malicious,)}
    )
    with pytest.raises(ValidationError) as error:
        aggregate_hard_status(invalid)
    assert any(item["type"] == "extra_forbidden" for item in error.value.errors())
    with pytest.raises(ValidationError) as direct_error:
        RuleDefinition.model_validate(malicious)
    assert any(item["type"] == "extra_forbidden" for item in direct_error.value.errors())


def test_recursive_payload_preserves_containers_and_declared_types() -> None:
    base = rule()
    value = {"tuple": (base,), "list": [base], "dict": {"rule": base}}
    flattened = _validation_payload(value)
    assert isinstance(flattened, dict)
    assert type(flattened["tuple"]) is tuple
    assert type(flattened["list"]) is list
    assert type(flattened["dict"]) is dict
    for payload in (flattened["tuple"][0], flattened["list"][0], flattened["dict"]["rule"]):
        assert payload["severity"] is RuleSeverity.ABSOLUTE
        assert type(payload["value"]) is int
        assert type(payload["required_facts"]) is tuple
        assert RuleDefinition.model_validate(payload) == base


@pytest.mark.parametrize("subclass", [_ExtraRuleDefinition, _AliasRuleDefinition])
def test_valid_dto_subclasses_keep_normal_aggregation(subclass: type[RuleDefinition]) -> None:
    base = rule()
    valid = subclass.model_construct(**vars(base))
    valid_trace = trace((base,), (evaluation(base),)).model_copy(
        update={"required_checks": (valid,)}
    )
    assert aggregate_hard_status(valid_trace) is RuleStatus.PASS
    assert is_candidate_eligible(aggregate_hard_status(valid_trace))


@pytest.mark.parametrize("entry", ["model", "adapter", "constructor"])
@pytest.mark.parametrize(
    "key", ["input_severity", "risk", "wireSeverity", "nested", "mapping", "requiredFacts"]
)
def test_direct_dictionary_alias_collisions_are_rejected(entry: str, key: str) -> None:
    payload: dict[str, Any] = vars(rule()) | {key: RuleSeverity.ABSOLUTE}
    with pytest.raises(ValidationError, match="colliding DTO"):
        if entry == "model":
            _AliasRuleDefinition.model_validate(payload)
        elif entry == "adapter":
            TypeAdapter(_AliasRuleDefinition).validate_python(payload)
        else:
            _AliasRuleDefinition(**payload)


@pytest.mark.parametrize("kind", ["rule", "trace"])
@pytest.mark.parametrize("entry", ["model", "adapter", "constructor", "json", "adapter_json"])
def test_direct_validation_preserves_valid_dto_and_wire_behavior(kind: str, entry: str) -> None:
    base = rule()
    original: Any = base if kind == "rule" else trace((base,), (evaluation(base),))
    target: Any = type(original)
    if entry == "model":
        result = target.model_validate(original)
    elif entry == "adapter":
        result = TypeAdapter(target).validate_python(original)
    elif entry == "constructor":
        result = target(**original.model_dump(by_alias=True))
    elif entry == "json":
        result = target.model_validate_json(original.model_dump_json(by_alias=True))
    else:
        result = TypeAdapter(target).validate_json(original.model_dump_json(by_alias=True))
    assert result == original
    definition = result if kind == "rule" else result.required_checks[0]
    assert definition.severity is RuleSeverity.ABSOLUTE
    if kind == "trace":
        assert aggregate_hard_status(result) is RuleStatus.PASS


@pytest.mark.parametrize("entry", ["strings", "adapter_strings"])
@pytest.mark.parametrize("key", ["rule_id", "ruleId"])
def test_string_validation_preserves_normal_references(entry: str, key: str) -> None:
    payload = {key: "synthetic-rule", "version": "fixture-v1"}
    result = (
        RuleReference.model_validate_strings(payload)
        if entry == "strings"
        else TypeAdapter(RuleReference).validate_strings(payload)
    )
    assert result == RuleReference(rule_id="synthetic-rule", version="fixture-v1")


@pytest.mark.parametrize(
    "entry", ["model", "adapter", "strings", "adapter_strings", "json", "adapter_json"]
)
def test_reference_alias_collisions_fail_at_real_validation_entry_points(entry: str) -> None:
    payload = {"rule_id": "synthetic-rule", "ruleId": "synthetic-rule", "version": "fixture-v1"}
    with pytest.raises(ValidationError):
        if entry == "model":
            RuleReference.model_validate(payload)
        elif entry == "adapter":
            TypeAdapter(RuleReference).validate_python(payload)
        elif entry == "strings":
            RuleReference.model_validate_strings(payload)
        elif entry == "adapter_strings":
            TypeAdapter(RuleReference).validate_strings(payload)
        elif entry == "json":
            RuleReference.model_validate_json(json.dumps(payload))
        else:
            TypeAdapter(RuleReference).validate_json(json.dumps(payload))


@pytest.mark.parametrize("entry", ["model", "adapter"])
def test_cyclic_unchecked_trace_fails_direct_validation(entry: str) -> None:
    recursive: dict[str, Any] = {}
    recursive["cycle"] = recursive
    invalid = trace().model_copy(update={"required_checks": (recursive,)})
    with pytest.raises(ValidationError, match="cyclic or excessively deep"):
        if entry == "model":
            RuleTrace.model_validate(invalid)
        else:
            TypeAdapter(RuleTrace).validate_python(invalid)


@pytest.mark.parametrize("key", ["risk", "nested", "mapping"])
def test_valid_alias_choices_and_paths_are_preserved(key: str) -> None:
    base = rule()
    payload: dict[str, Any] = vars(base).copy()
    del payload["severity"]
    payload[key] = (
        [{"risk": RuleSeverity.ABSOLUTE}]
        if key == "nested"
        else {"risk": RuleSeverity.ABSOLUTE}
        if key == "mapping"
        else RuleSeverity.ABSOLUTE
    )
    valid = _AliasRuleDefinition.model_validate(payload)
    assert valid.severity is RuleSeverity.ABSOLUTE
    assert RuleDefinition.model_validate(valid) == base


def test_distinct_alias_paths_can_share_a_valid_container_root() -> None:
    class SharedRootReference(RuleReference):
        rule_id: str = Field(validation_alias=AliasPath("binding", "id"))
        version: str = Field(validation_alias=AliasPath("binding", "version"))

    valid = SharedRootReference.model_validate(
        {"binding": {"id": "synthetic-rule", "version": "fixture-v1"}}
    )
    assert RuleReference.model_validate(valid) == RuleReference(
        rule_id="synthetic-rule", version="fixture-v1"
    )


@pytest.mark.parametrize("container", ["tuple", "list", "dict", "foreign_model"])
def test_reused_nested_schemas_cannot_bypass_the_collision_guard(container: str) -> None:
    base = rule()
    payload: dict[str, Any] = {"input_" + name: value for name, value in vars(base).items()}
    payload["severity"] = RuleSeverity.SOFT
    malicious = _ExtraRuleDefinition.model_construct(**payload)
    with pytest.raises(ValidationError, match="colliding DTO"):
        if container == "tuple":
            TypeAdapter(tuple[RuleDefinition, RuleDefinition]).validate_python((base, malicious))
        elif container == "list":
            TypeAdapter(list[RuleDefinition]).validate_python([base, malicious])
        elif container == "dict":
            TypeAdapter(dict[str, RuleDefinition]).validate_python(
                {"valid": base, "invalid": malicious}
            )
        else:

            class Pair(BaseModel):
                left: RuleDefinition
                right: RuleDefinition

            Pair.model_validate({"left": base, "right": malicious})


_container_calls: list[str] = []


class _HiddenKeys(dict[str, Any]):
    def __iter__(self) -> Iterator[str]:
        _container_calls.append("__iter__")
        return iter(())


class _HiddenItems(dict[str, Any]):
    def items(self) -> Any:
        _container_calls.append("items")
        return iter(())


class _LeftUnion(dict[str, Any]):
    def __or__(self, other: Any) -> Any:
        _container_calls.append("__or__")
        return dict(dict.items(self)) | {"severity": RuleSeverity.SOFT}


class _RightUnion(dict[str, Any]):
    def __ror__(self, other: Any) -> Any:
        _container_calls.append("__ror__")
        return dict(other) | {"severity": RuleSeverity.SOFT}


class _HiddenTuple(tuple[Any, ...]):
    def __iter__(self) -> Iterator[Any]:
        _container_calls.append("tuple.__iter__")
        return iter(tuple.__getitem__(self, slice(0, 1)))


class _HiddenList(list[Any]):
    def __iter__(self) -> Iterator[Any]:
        _container_calls.append("list.__iter__")
        return iter(list.__getitem__(self, slice(0, 1)))


_CUSTOM_DICTS = (_HiddenKeys, _HiddenItems, _LeftUnion, _RightUnion)
_CUSTOM_SEQUENCES = (_HiddenTuple, _HiddenList)


@pytest.mark.parametrize("container", _CUSTOM_DICTS)
@pytest.mark.parametrize("entry", ["model", "adapter", "recursive"])
def test_custom_dicts_are_rejected_before_methods(container: Any, entry: str) -> None:
    payload = container(rule().model_dump() | {"unexpected": "must not disappear"})
    _container_calls.clear()
    with pytest.raises(ValidationError, match="unsupported custom container subclass"):
        if entry == "model":
            RuleDefinition.model_validate(payload)
        elif entry == "adapter":
            TypeAdapter(RuleDefinition).validate_python(payload)
        else:
            _validation_payload(payload)
    assert not _container_calls


@pytest.mark.parametrize("container", _CUSTOM_DICTS)
@pytest.mark.parametrize("entry", ["model", "adapter", "strings", "adapter_strings"])
def test_custom_dicts_reach_guards_before_string_normalization(container: Any, entry: str) -> None:
    payload = container(rule_id="synthetic", version="1", unexpected="must not disappear")
    _container_calls.clear()
    with pytest.raises(ValidationError, match="unsupported custom container subclass"):
        if entry == "model":
            RuleReference.model_validate(payload)
        elif entry == "adapter":
            TypeAdapter(RuleReference).validate_python(payload)
        elif entry == "strings":
            RuleReference.model_validate_strings(payload)
        else:
            TypeAdapter(RuleReference).validate_strings(payload)
    assert not _container_calls


@pytest.mark.parametrize("container", _CUSTOM_DICTS)
@pytest.mark.parametrize("storage", ["fields", "extras"])
@pytest.mark.parametrize("mode", ["construct", "copy"])
@pytest.mark.parametrize("key", ["severity", "input_severity", "requiredFacts"])
@pytest.mark.parametrize("same_value", [False, True])
def test_custom_dto_storage_cannot_hide_collisions(
    container: Any, storage: str, mode: str, key: str, same_value: bool
) -> None:
    base = rule()
    malicious = _ExtraRuleDefinition.model_construct(**vars(base))
    if mode == "copy":
        malicious = malicious.model_copy()
    shadow = RuleSeverity.ABSOLUTE if same_value else RuleSeverity.SOFT
    object.__setattr__(malicious, "__pydantic_extra__", {key: shadow})
    if storage == "fields":
        object.__setattr__(malicious, "__dict__", container(vars(malicious)))
    else:
        object.__setattr__(malicious, "__pydantic_extra__", container({key: shadow}))
    nested = trace((base,), (evaluation(base),)).model_copy(
        update={"required_checks": (malicious,)}
    )
    _container_calls.clear()
    validations = (
        (RuleDefinition.model_validate, malicious),
        (TypeAdapter(RuleDefinition).validate_python, malicious),
        (RuleTrace.model_validate, nested),
        (TypeAdapter(RuleTrace).validate_python, nested),
        (_validation_payload, nested),
    )
    for validate, payload in validations:
        with pytest.raises(ValidationError, match="unsupported custom container subclass"):
            validate(payload)
    with pytest.raises(ValidationError, match="unsupported custom container subclass"):
        aggregate_hard_status(nested)
    assert not _container_calls


@pytest.mark.parametrize("container", _CUSTOM_SEQUENCES)
@pytest.mark.parametrize("mode", ["dict", "construct", "copy"])
def test_custom_sequences_cannot_hide_additional_hard_fail(container: Any, mode: str) -> None:
    base = rule()
    extra = rule(rule_id="extra-hard")
    passing = trace((base,), (evaluation(base),))
    failed = evaluation(extra, status=RuleStatus.FAIL, facts=(fact(value=9),))
    # Built-in tuples expose the extra hard FAIL and are already rejected.
    values = (*passing.evaluations, failed)
    with pytest.raises(ValidationError, match="absent from required manifest"):
        RuleTrace.model_validate(vars(passing) | {"evaluations": values})
    payload: Any = vars(passing) | {"evaluations": container(values)}
    if mode == "construct":
        payload = RuleTrace.model_construct(**payload)
    elif mode == "copy":
        payload = passing.model_copy(update={"evaluations": payload["evaluations"]})
    _container_calls.clear()
    for validate in (RuleTrace.model_validate, TypeAdapter(RuleTrace).validate_python):
        with pytest.raises(ValidationError, match="unsupported custom container subclass"):
            validate(payload)
    with pytest.raises(ValidationError, match="unsupported custom container subclass"):
        aggregate_hard_status(payload)
    assert not _container_calls


@pytest.mark.parametrize("container", [*_CUSTOM_DICTS, *_CUSTOM_SEQUENCES])
@pytest.mark.parametrize("entry", ["model", "adapter", "constructor"])
def test_nested_custom_containers_are_checked_before_field_normalization(
    container: Any, entry: str
) -> None:
    base = rule()
    payload = base.model_dump()
    if container in _CUSTOM_DICTS:
        payload["applicability_reference"] = container(payload["applicability_reference"])
    else:
        payload["required_facts"] = container(base.required_facts)
    _container_calls.clear()
    with pytest.raises(ValidationError, match="unsupported custom container subclass"):
        if entry == "model":
            RuleDefinition.model_validate(payload)
        elif entry == "adapter":
            TypeAdapter(RuleDefinition).validate_python(payload)
        else:
            RuleDefinition(**payload)
    assert not _container_calls


def test_builtin_containers_dtos_and_json_preserve_validation() -> None:
    base = rule()
    passing = trace((base,), (evaluation(base),))
    assert RuleTrace.model_validate(passing.model_dump()) == passing
    assert TypeAdapter(RuleTrace).validate_python(passing) == passing
    assert RuleTrace.model_validate_json(passing.model_dump_json()) == passing
    assert TypeAdapter(RuleTrace).validate_json(passing.model_dump_json()) == passing
    assert aggregate_hard_status(passing) is RuleStatus.PASS
    # Lists remain lists in Python (strict tuple fields still reject them); JSON
    # arrays and alias-path lists retain their existing supported behavior.
    tree = {"list": [base], "tuple": (base,), "dict": {"rule": base}}
    flattened: Any = _validation_payload(tree)
    assert type(flattened["list"]) is list
    assert type(flattened["tuple"]) is tuple
    assert type(flattened["dict"]) is dict
    for record in (flattened["list"][0], flattened["tuple"][0], flattened["dict"]["rule"]):
        assert RuleDefinition.model_validate(record) == base


@pytest.mark.parametrize("entry", ["model", "adapter", "recursive"])
def test_custom_tuple_dictionary_keys_are_rejected_before_rehashing(entry: str) -> None:
    class HashTuple(tuple[str, ...]):
        def __hash__(self) -> int:
            _container_calls.append("__hash__")
            return tuple.__hash__(self)

    payload: dict[Any, Any] = rule().model_dump()
    payload[HashTuple(("unexpected",))] = "must not disappear"
    _container_calls.clear()
    with pytest.raises(ValidationError, match="unsupported custom container subclass"):
        if entry == "model":
            RuleDefinition.model_validate(payload)
        elif entry == "adapter":
            TypeAdapter(RuleDefinition).validate_python(payload)
        else:
            _validation_payload(payload)
    assert not _container_calls
