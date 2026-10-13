"""Provisional, versioned rule declarations; no predicate execution or clinical limits."""

from enum import StrEnum
from math import isfinite
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator
from pydantic.alias_generators import to_camel

_NonBlank = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
_FactValue = bool | int | float | _NonBlank | tuple[_NonBlank, ...]


class _ContractModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        revalidate_instances="always",
        allow_inf_nan=False,
    )


class RuleSeverity(StrEnum):
    ABSOLUTE = "ABSOLUTE"
    SOFT = "SOFT"
    INFORMATIONAL = "INFORMATIONAL"


class RuleScope(StrEnum):
    PROFILE = "PROFILE"
    RECIPE = "RECIPE"
    COMBINATION = "COMBINATION"
    DAY = "DAY"
    WEEK = "WEEK"


class RuleDomain(StrEnum):
    DIETARY = "DIETARY"
    CULTURAL = "CULTURAL"
    CLINICAL = "CLINICAL"
    CULINARY = "CULINARY"


class RuleEnvironment(StrEnum):
    SYNTHETIC = "SYNTHETIC"
    PRODUCTION = "PRODUCTION"


class RuleLifecycle(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PredicateOperator(StrEnum):
    LT = "LT"
    LE = "LE"
    GT = "GT"
    GE = "GE"
    EQ = "EQ"
    NE = "NE"
    IN = "IN"
    NOT_IN = "NOT_IN"


class MeasurementUnit(StrEnum):
    G = "g"
    MG = "mg"
    UG = "ug"
    ML = "mL"
    KCAL = "kcal"
    KJ = "kJ"
    PERCENT = "%"
    DIMENSIONLESS = "dimensionless"


def _require_canonical_enum(value: StrEnum) -> None:
    """Require the declared singleton, not merely an enum instance or equal text."""
    if not any(value is member for member in type(value)):
        raise ValueError(f"{type(value).__name__} requires a canonical declared enum member")


class RuleReference(_ContractModel):
    rule_id: _NonBlank
    version: _NonBlank


class EvidenceReference(_ContractModel):
    """Declared provenance, not proof that a source was independently verified."""

    evidence_id: _NonBlank
    version: _NonBlank
    source: _NonBlank
    locator: _NonBlank
    environment: RuleEnvironment

    @field_validator("environment", mode="after")
    @classmethod
    def validate_environment_member(cls, value: RuleEnvironment) -> RuleEnvironment:
        _require_canonical_enum(value)
        return value


def _validate_evidence(evidence: tuple[EvidenceReference, ...]) -> None:
    identities = [(item.evidence_id, item.version) for item in evidence]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate evidence identity/version")


def _validate_value_unit(value: _FactValue, unit: MeasurementUnit | None) -> None:
    # bool is a subclass of int; it must never be interpreted as a numeric measurement.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not isfinite(value):
            raise ValueError("numeric values must be finite")
        if unit is None:
            raise ValueError("numeric measurements require an explicit unit")
        if value < 0:
            raise ValueError("measurement values must be non-negative")
        if unit is MeasurementUnit.PERCENT and value > 100:
            raise ValueError("percent values must be between 0 and 100")
    elif unit is not None:
        raise ValueError("boolean and categorical values cannot carry measurement units")
    if isinstance(value, tuple) and len(set(value)) != len(value):
        raise ValueError("categorical sets cannot contain duplicates")


class RuleDefinition(_ContractModel):
    rule_id: _NonBlank
    version: _NonBlank
    scope: RuleScope
    severity: RuleSeverity
    domain: RuleDomain
    attribute: _NonBlank
    operator: PredicateOperator
    value: _FactValue
    unit: MeasurementUnit | None = None
    required_facts: tuple[_NonBlank, ...]
    applicability_reference: RuleReference
    evidence: tuple[EvidenceReference, ...]
    rationale: _NonBlank
    lifecycle: RuleLifecycle
    approval_status: ApprovalStatus
    approved_by: _NonBlank | None = None
    approval_reference: EvidenceReference | None = None
    environment: RuleEnvironment

    @field_validator(
        "scope",
        "severity",
        "domain",
        "operator",
        "unit",
        "lifecycle",
        "approval_status",
        "environment",
        mode="after",
    )
    @classmethod
    def validate_enum_members(cls, value: StrEnum | None) -> StrEnum | None:
        if value is not None:
            _require_canonical_enum(value)
        return value

    @model_validator(mode="after")
    def validate_declaration(self) -> Self:
        if not self.required_facts or len(set(self.required_facts)) != len(self.required_facts):
            raise ValueError("required facts must be non-empty and unique")
        if self.attribute not in self.required_facts:
            raise ValueError("predicate attribute must be listed among required facts")
        if not self.evidence:
            raise ValueError("rules require source evidence")
        _validate_evidence(self.evidence)
        _validate_value_unit(self.value, self.unit)

        if self.operator in (PredicateOperator.IN, PredicateOperator.NOT_IN):
            if not isinstance(self.value, tuple) or not self.value:
                raise ValueError("membership predicates require a non-empty categorical tuple")
        elif isinstance(self.value, tuple):
            raise ValueError("categorical tuples require a membership operator")
        elif self.operator in (
            PredicateOperator.LT,
            PredicateOperator.LE,
            PredicateOperator.GT,
            PredicateOperator.GE,
        ) and type(self.value) not in (int, float):
            raise ValueError("ordered comparisons require numeric measurements, never booleans")

        approved = self.approval_status is ApprovalStatus.APPROVED
        metadata_present = self.approved_by is not None or self.approval_reference is not None
        if approved and (self.approved_by is None or self.approval_reference is None):
            raise ValueError("approval requires both approver and approval evidence")
        if not approved and metadata_present:
            raise ValueError("unapproved rules cannot carry approval metadata")
        if (
            self.lifecycle is RuleLifecycle.ACTIVE
            and self.approval_status is ApprovalStatus.REJECTED
        ):
            raise ValueError("rejected rules cannot be active")
        if (
            self.environment is RuleEnvironment.PRODUCTION
            and self.lifecycle is RuleLifecycle.ACTIVE
            and self.domain is RuleDomain.CLINICAL
        ):
            if not approved:
                raise ValueError("production-active clinical rules require approval")
            if any(item.environment is RuleEnvironment.SYNTHETIC for item in self.evidence):
                raise ValueError("production-active clinical rules require non-synthetic evidence")
            if (
                self.approval_reference is None
                or self.approval_reference.environment is not RuleEnvironment.PRODUCTION
            ):
                raise ValueError("production clinical approval evidence must be non-synthetic")
        return self
