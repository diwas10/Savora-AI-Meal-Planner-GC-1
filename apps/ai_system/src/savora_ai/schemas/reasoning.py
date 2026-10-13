"""Declared evaluation coverage and deterministic three-state hard aggregation only."""

from enum import StrEnum
from typing import Self

from pydantic import ValidationError, field_validator, model_validator

from savora_ai.schemas.knowledge import (
    EvidenceReference,
    MeasurementUnit,
    PredicateOperator,
    RuleDefinition,
    RuleLifecycle,
    RuleSeverity,
    _ContractModel,
    _FactValue,
    _NonBlank,
    _require_canonical_enum,
    _validate_evidence,
    _validate_value_unit,
)


class RuleStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class ApplicabilityStatus(StrEnum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class FactObservation(_ContractModel):
    fact_id: _NonBlank
    value: _FactValue | None
    complete: bool
    unit: MeasurementUnit | None = None
    evidence: tuple[EvidenceReference, ...]

    @field_validator("unit", mode="after")
    @classmethod
    def validate_unit_member(cls, value: MeasurementUnit | None) -> MeasurementUnit | None:
        if value is not None:
            _require_canonical_enum(value)
        return value

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        if not self.evidence:
            raise ValueError("fact observations require provenance, including declared gaps")
        _validate_evidence(self.evidence)
        if self.value is None:
            if self.complete or self.unit is not None:
                raise ValueError("null facts must be incomplete and carry no measurement unit")
        else:
            _validate_value_unit(self.value, self.unit)
        return self


class RuleEvaluation(_ContractModel):
    rule: RuleDefinition
    applicability: ApplicabilityStatus
    applicability_evidence: tuple[EvidenceReference, ...] = ()
    facts: tuple[FactObservation, ...] = ()
    status: RuleStatus
    reason: _NonBlank

    @field_validator("applicability", "status", mode="after")
    @classmethod
    def validate_enum_members(cls, value: StrEnum) -> StrEnum:
        _require_canonical_enum(value)
        return value

    @model_validator(mode="after")
    def validate_evaluation(self) -> Self:
        if self.rule.lifecycle is not RuleLifecycle.ACTIVE:
            raise ValueError("eligibility evaluations require ACTIVE rules")
        _validate_evidence(self.applicability_evidence)
        fact_ids = [item.fact_id for item in self.facts]
        if len(set(fact_ids)) != len(fact_ids):
            raise ValueError("duplicate fact observations")
        observations = {item.fact_id: item for item in self.facts}
        if self.rule.operator in (PredicateOperator.IN, PredicateOperator.NOT_IN):
            attribute = observations.get(self.rule.attribute)
            if (
                attribute is not None
                and attribute.value is not None
                and not isinstance(attribute.value, str)
            ):
                raise ValueError("IN/NOT_IN observations must be scalar strings")
        if (
            self.applicability is not ApplicabilityStatus.UNKNOWN
            and not self.applicability_evidence
        ):
            raise ValueError("resolved applicability requires evidence")
        if self.applicability is not ApplicabilityStatus.APPLICABLE:
            if self.status is not RuleStatus.UNKNOWN:
                raise ValueError("unevaluated predicates must declare UNKNOWN")
        elif self.status is not RuleStatus.UNKNOWN:
            for fact_id in self.rule.required_facts:
                observation = observations.get(fact_id)
                if observation is None or observation.value is None or not observation.complete:
                    raise ValueError(
                        "PASS/FAIL requires all declared facts to be present and complete"
                    )
            attribute = observations[self.rule.attribute]
            if attribute.unit != self.rule.unit:
                raise ValueError(
                    "predicate observation and rule units must match; no implicit conversion"
                )
            # Validate declared type compatibility, not the truth of the predicate.
            value = attribute.value
            expected = self.rule.value
            if type(expected) in (int, float):
                compatible = type(value) in (int, float)
            elif isinstance(expected, tuple):
                # Collection quantifiers are unapproved; IN/NOT_IN use scalar observations.
                compatible = isinstance(value, str)
            else:
                compatible = type(value) is type(expected)
            if not compatible:
                raise ValueError("predicate observation type must match the rule value kind")
        return self


class RuleTrace(_ContractModel):
    """The caller must supply the complete trusted manifest for this candidate/context.

    Each required check embeds its definition to bind severity, required facts and evidence
    as well as identity/version. Neither completeness nor external facts are verified here.
    """

    candidate_id: _NonBlank
    context_id: _NonBlank
    manifest_id: _NonBlank
    manifest_version: _NonBlank
    required_checks: tuple[RuleDefinition, ...]
    evaluations: tuple[RuleEvaluation, ...] = ()

    @model_validator(mode="after")
    def validate_coverage(self) -> Self:
        required: dict[str, RuleDefinition] = {}
        for rule in self.required_checks:
            if rule.lifecycle is not RuleLifecycle.ACTIVE:
                raise ValueError("eligibility manifests require ACTIVE rules")
            if rule.severity is not RuleSeverity.ABSOLUTE:
                raise ValueError("required hard-check manifest may contain only ABSOLUTE rules")
            if rule.rule_id in required:
                raise ValueError("duplicate rule identities or versions in required manifest")
            required[rule.rule_id] = rule

        seen: dict[str, RuleEvaluation] = {}
        for evaluation in self.evaluations:
            rule_id = evaluation.rule.rule_id
            previous = seen.get(rule_id)
            if previous is not None:
                if previous.rule.version != evaluation.rule.version:
                    raise ValueError("evaluation version mismatch")
                if previous != evaluation:
                    raise ValueError("conflicting duplicate evaluations")
            seen[rule_id] = evaluation
            expected = required.get(rule_id)
            if expected is not None:
                if expected.version != evaluation.rule.version:
                    raise ValueError("required rule evaluation version mismatch")
                if expected != evaluation.rule:
                    raise ValueError("evaluation rule definition differs from required manifest")
            elif evaluation.rule.severity is RuleSeverity.ABSOLUTE:
                raise ValueError("hard evaluation is absent from required manifest")

        # A versioned evidence identity must mean the same thing wherever it is reused.
        provenance: dict[tuple[str, str], EvidenceReference] = {}
        references: list[EvidenceReference] = []
        for rule in (*self.required_checks, *(item.rule for item in self.evaluations)):
            references.extend(rule.evidence)
            if rule.approval_reference is not None:
                references.append(rule.approval_reference)
        for evaluation in self.evaluations:
            references.extend(evaluation.applicability_evidence)
            for observation in evaluation.facts:
                references.extend(observation.evidence)
        for reference in references:
            identity = (reference.evidence_id, reference.version)
            previous = provenance.get(identity)
            if previous is not None and previous != reference:
                raise ValueError(
                    f"contradictory evidence provenance for {identity[0]!r} version {identity[1]!r}"
                )
            provenance[identity] = reference
        return self


def _validation_payload(value: object) -> object:
    """Flatten DTO instances without coercing or dropping unchecked fields.

    Retain container types and enum instances for strict Python validation. Reading the
    field mapping also retains unknown model_copy updates that model_dump can omit.
    No nested DTO instance is passed through to the validating constructor.
    """
    if isinstance(value, _ContractModel):
        value = vars(value) | (value.model_extra or {})
    if isinstance(value, dict):
        return {key: _validation_payload(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_validation_payload(item) for item in value)
    if isinstance(value, list):
        return [_validation_payload(item) for item in value]
    return value


def aggregate_hard_status(trace: RuleTrace) -> RuleStatus:
    """Strictly validate the entire graph, then aggregate declared hard outcomes.

    Invalid structures raise ValidationError; predicates and external evidence are
    not executed or independently verified.
    """
    try:
        payload = _validation_payload(trace)
    except RecursionError as error:
        raise ValidationError.from_exception_data(
            "RuleTrace",
            [
                {
                    "type": "value_error",
                    "loc": (),
                    "input": None,
                    "ctx": {"error": ValueError("cyclic or excessively deep eligibility trace")},
                }
            ],
        ) from error
    trace = RuleTrace.model_validate(payload, strict=True)
    evaluations = {item.rule.rule_id: item for item in trace.evaluations}
    # A known applicable failure dominates missing checks and unknown applicability.
    if any(
        item.rule.severity is RuleSeverity.ABSOLUTE
        and item.applicability is ApplicabilityStatus.APPLICABLE
        and item.status is RuleStatus.FAIL
        for item in trace.evaluations
    ):
        return RuleStatus.FAIL
    if not trace.required_checks:
        return RuleStatus.UNKNOWN
    for rule in trace.required_checks:
        evaluation = evaluations.get(rule.rule_id)
        if evaluation is None or evaluation.applicability is ApplicabilityStatus.UNKNOWN:
            return RuleStatus.UNKNOWN
        if evaluation.applicability is ApplicabilityStatus.NOT_APPLICABLE:
            continue
        if evaluation.status is not RuleStatus.PASS:
            return RuleStatus.UNKNOWN
    return RuleStatus.PASS


def is_candidate_eligible(status: RuleStatus) -> bool:
    """Only canonical PASS is eligible; counterfeit enums raise ValidationError.

    Other unvalidated values retain the existing ineligible boolean behavior.
    """
    if isinstance(status, RuleStatus):
        try:
            _require_canonical_enum(status)
        except ValueError as error:
            raise ValidationError.from_exception_data(
                "RuleStatus",
                [
                    {
                        "type": "value_error",
                        "loc": ("status",),
                        "input": status,
                        "ctx": {"error": error},
                    }
                ],
            ) from error
    return status is RuleStatus.PASS
