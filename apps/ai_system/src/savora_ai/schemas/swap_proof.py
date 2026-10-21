"""Version-disjoint swap proof/resource DECLARATIONS ONLY; no checker or execution."""

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, ValidationInfo, model_validator

from savora_ai.schemas.combination_evaluation import CombinationEligibilityResult
from savora_ai.schemas.daily import MealOptionReference
from savora_ai.schemas.knowledge_base import _ContentDigest
from savora_ai.schemas.planned_swap import (
    ByteCount,
    Count,
    PlannedSwapRequest,
    SavedPlanMaterial,
    SwapPlanSnapshot,
    SwapReference,
    SwapReplacementDomain,
    SwapSelectionLimits,
    SwapValidationLimits,
    SwapWork,
    SyntheticSwapRanking,
    _SwapModel,
)
from savora_ai.schemas.reasoning import FactObservation, RuleStatus, RuleTrace


class SwapOperation(StrEnum):
    SOURCE_ITEM = "source_items"
    BRIDGE_ITEM = "bridge_items"
    LOCK_COMPARE = "lock_comparisons"
    CANDIDATE_PREPARATION = "candidate_preparations"
    COMBINATION_PREPARATION = "combination_preparations"
    PREDICATE = "predicate_obligations"
    DAY = "day_assessments"
    WEEK = "week_assessments"
    DOMAIN_VISIT = "domain_visits"
    ORDER_ITEM = "ordering_items"
    FULL_VALIDATION = "full_validations"
    CHECK_STEP = "checker_steps"


class SwapOperationReservation(_SwapModel):
    """Prospective unit-cost equation, not evidence that any operation happened.

    For n items: executor n in the named category; checker n in that
    category plus one step if n>0. Reserve their sum. A nonempty operation
    reserves one flat record, payload bytes plus a 1024-byte metadata allowance.
    Item counts/payload bounds must be independently derived by a future checker.
    """

    schema_version: Literal["swap-operation-reservation.v1"] = "swap-operation-reservation.v1"
    policy: Literal["synthetic-swap-work-reservation.v1"] = "synthetic-swap-work-reservation.v1"
    operation: SwapOperation
    items: Count
    payload_bytes: ByteCount
    execution: SwapWork
    verification: SwapWork
    reserved: SwapWork
    proof_records: Annotated[int, Field(ge=0, le=1)]
    proof_bytes: ByteCount
    executed: Literal[False] = False

    @model_validator(mode="after")
    def exact_cost_equations(self) -> Self:
        execution = {name: 0 for name in SwapWork.model_fields}
        verification = execution.copy()
        execution[self.operation.value] = self.items
        verification[self.operation.value] = self.items
        verification["checker_steps"] += int(self.items > 0)
        reserved = {name: execution[name] + verification[name] for name in execution}
        records = int(self.items > 0)
        if (
            self.execution.model_dump() != execution
            or self.verification.model_dump() != verification
            or self.reserved.model_dump() != reserved
            or self.proof_records != records
            or self.proof_bytes != (self.payload_bytes + 1024 if records else 0)
            or (not records and self.payload_bytes != 0)
        ):
            raise ValueError("reservation differs from versioned exact operation-cost equations")
        return self


class SwapReservationPlan(_SwapModel):
    schema_version: Literal["swap-reservation-plan.v1"] = "swap-reservation-plan.v1"
    limits: SwapValidationLimits | SwapSelectionLimits
    operations: Annotated[tuple[SwapOperationReservation, ...], Field(max_length=1024)]
    result_bytes_reserved: ByteCount
    actual_execution: SwapWork = SwapWork()
    actual_verification: SwapWork = SwapWork()
    execution_status: Literal["NOT_EXECUTED"] = "NOT_EXECUTED"

    @model_validator(mode="after")
    def bounded_prospective_reservations(self) -> Self:
        if any(self.actual_execution.model_dump().values()) or any(
            self.actual_verification.model_dump().values()
        ):
            raise ValueError("declarations cannot claim execution or verification work")
        for name in SwapWork.model_fields:
            if sum(getattr(op.reserved, name) for op in self.operations) > getattr(
                self.limits.max_reserved_work, name
            ):
                raise ValueError("prospective work exceeds declared limit")
        if (
            sum(op.proof_records for op in self.operations) > self.limits.max_proof_records
            or sum(op.proof_bytes for op in self.operations) > self.limits.max_proof_bytes
            or self.result_bytes_reserved > self.limits.max_result_bytes
            or sum(op.execution.full_validations for op in self.operations)
            > self.limits.max_full_validations
        ):
            raise ValueError("prospective proof/result/validation capacity is insufficient")
        visits = sum(op.execution.domain_visits for op in self.operations)
        if visits > (
            self.limits.max_domain_visits if isinstance(self.limits, SwapSelectionLimits) else 0
        ):
            raise ValueError("prospective original-domain visits exceed selection capacity")
        return self


class SwapProofEventDeclaration(_SwapModel):
    sequence: Annotated[int, Field(ge=0, le=1023)]
    kind: Literal["SOURCE", "BRIDGE", "LOCKS", "BASELINE", "CANDIDATE", "DAY", "WEEK", "FRONTIER"]
    input_reference: SwapReference
    payload_digest: _ContentDigest
    semantic_assessment: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"


def _ordered_events_digest(events: tuple[SwapProofEventDeclaration, ...]) -> str:
    body = {
        "policy": "synthetic-swap-ordered-events.v1",
        "events": [e.model_dump(mode="json", by_alias=True) for e in events],
    }
    return hashlib.sha256(
        json.dumps(
            body, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


class SwapValidationCertificate(_SwapModel):
    schema_version: Literal["swap-validation-certificate-declaration.v1"] = (
        "swap-validation-certificate-declaration.v1"
    )
    policy: Literal["synthetic-swap-validation-proof.v1"] = "synthetic-swap-validation-proof.v1"
    request: PlannedSwapRequest
    events: Annotated[tuple[SwapProofEventDeclaration, ...], Field(max_length=1024)]
    event_digest: _ContentDigest
    reservations: SwapReservationPlan
    exhaustive: Literal[False] = False
    verification_complete: Literal[False] = False
    outcome: None = None

    @model_validator(mode="after")
    def ordered_declaration(self) -> Self:
        if tuple(e.sequence for e in self.events) != tuple(range(len(self.events))):
            raise ValueError("declaration event sequence must be contiguous and unique")
        if self.event_digest != _ordered_events_digest(self.events):
            raise ValueError("ordered event digest mismatch")
        return self


class SwapSelectionCertificate(_SwapModel):
    schema_version: Literal["swap-selection-certificate-declaration.v1"] = (
        "swap-selection-certificate-declaration.v1"
    )
    policy: Literal["synthetic-swap-selection-proof.v1"] = "synthetic-swap-selection-proof.v1"
    request: PlannedSwapRequest
    domain: SwapReplacementDomain
    ranking: SyntheticSwapRanking
    transcript: SwapValidationCertificate
    failure_scope: None = None
    exhaustive: Literal[False] = False
    outcome: None = None
    verification_complete: Literal[False] = False

    @model_validator(mode="after")
    def scoped_declarations(self) -> Self:
        if (
            self.domain.request != self.request
            or self.ranking.domain != self.domain
            or (self.transcript.request != self.request)
        ):
            raise ValueError(
                "selection declaration cannot transplant another request/domain/ranking"
            )
        if not isinstance(self.transcript.reservations.limits, SwapSelectionLimits):
            raise ValueError("selection proof requires shared outer selection limits")
        return self


class SwapValidationDeclaration(_SwapModel):
    schema_version: Literal["swap-validation-result-declaration.v1"] = (
        "swap-validation-result-declaration.v1"
    )
    request: PlannedSwapRequest
    saved_plan: SavedPlanMaterial
    proposed_plan: SwapPlanSnapshot | None = None
    certificate: SwapValidationCertificate | None = None
    operation_scope: Literal["SINGLE_CANDIDATE"] = "SINGLE_CANDIDATE"
    failure_scope: None = None
    outcome: None = None
    accepted: Literal[False] = False
    verification_complete: Literal[False] = False
    semantic_assessment: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"

    @model_validator(mode="after")
    def original_binding(self) -> Self:
        if (
            self.request.saved_plan != self.saved_plan.reference
            or (
                self.proposed_plan is not None
                and (
                    self.proposed_plan.base != self.saved_plan
                    or self.proposed_plan.request != self.request
                )
            )
            or (self.certificate is not None and self.certificate.request != self.request)
        ):
            raise ValueError("validation declaration differs from exact original request/material")
        return self


class SwapSelectionDeclaration(_SwapModel):
    schema_version: Literal["swap-selection-result-declaration.v1"] = (
        "swap-selection-result-declaration.v1"
    )
    certificate: SwapSelectionCertificate
    operation_scope: Literal["EXPLICIT_REPLACEMENT_DOMAIN"] = "EXPLICIT_REPLACEMENT_DOMAIN"
    outcome: None = None
    accepted: Literal[False] = False
    verification_complete: Literal[False] = False
    semantic_assessment: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"


class SwapOutcome(StrEnum):
    VALID = "VALID"
    REJECTED = "REJECTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    TIMEOUT = "TIMEOUT"


class SwapOptionAssessment(_SwapModel):
    option: MealOptionReference
    combination: CombinationEligibilityResult


class SwapAggregateAssessment(_SwapModel):
    scope: Literal["DAY", "WEEK"]
    day_index: Annotated[int, Field(ge=0, le=7)]
    # Ordered full-option digests bind every contributing fixed meal, including
    # preparation, units, missing measurements, provenance and component order.
    contributors: Annotated[tuple[_ContentDigest, ...], Field(max_length=21)]
    observations: tuple[FactObservation, ...]
    trace: RuleTrace
    status: RuleStatus


class SwapPhaseAssessment(_SwapModel):
    phase: Literal["ORIGINAL", "RESULT"]
    options: Annotated[tuple[SwapOptionAssessment, ...], Field(max_length=21)]
    slots: Annotated[tuple[RuleStatus, ...], Field(min_length=21, max_length=21)]
    days: Annotated[tuple[SwapAggregateAssessment, ...], Field(min_length=7, max_length=7)]
    week: SwapAggregateAssessment


class ComputedSwapCertificate(_SwapModel):
    schema_version: Literal["computed-swap-certificate.v1"] = "computed-swap-certificate.v1"
    policy: Literal["synthetic-fixed-swap-full-replay.v1"] = "synthetic-fixed-swap-full-replay.v1"
    input_digest: _ContentDigest
    reservations: SwapReservationPlan
    original: SwapPhaseAssessment
    result: SwapPhaseAssessment


class SwapProofCheck(_SwapModel):
    schema_version: Literal["swap-proof-check.v1"] = "swap-proof-check.v1"
    accepted: bool
    complete: bool
    reason: Literal["VERIFIED", "MISMATCH", "RESERVATION", "DEADLINE", "UNVERIFIED_TIMEOUT"]
    outcome: SwapOutcome | None = None
    actual_verification: SwapWork = SwapWork()


class _SwapClaim(_SwapModel):
    """Untrusted computed claim. Parsing this class does not authorize a plan."""

    schema_version: Literal["computed-swap-validation-result.v1"] = (
        "computed-swap-validation-result.v1"
    )
    request: PlannedSwapRequest
    replacement: MealOptionReference
    limits: SwapValidationLimits
    operation_scope: Literal["SINGLE_CANDIDATE"] = "SINGLE_CANDIDATE"
    outcome: SwapOutcome
    failure_scope: Literal["OPERATION", "CANDIDATE"] | None = None
    reason: Literal[
        "TARGET_LOCKED",
        "NO_OP",
        "BASELINE_INVALID",
        "RESULT_FAILED",
        "REQUIRED_FACT_UNKNOWN",
        "COMPLETE_PASS",
        "RESERVATION",
        "DEADLINE",
    ]
    stage: Literal["RESERVATION", "EXECUTION", "VERIFICATION", "COMPLETE"]
    certificate: ComputedSwapCertificate | None = None
    resulting_plan: SwapPlanSnapshot | None = None
    verification_complete: bool = False
    actual_execution: SwapWork = SwapWork()
    actual_verification: SwapWork = SwapWork()
    proof_bytes: ByteCount = 0

    @property
    def accepted(self) -> bool:
        return self.outcome is SwapOutcome.VALID and self.verification_complete

    @model_validator(mode="after")
    def scoped_claim(self) -> Self:
        if self.outcome is SwapOutcome.TIMEOUT:
            if self.resulting_plan is not None or self.verification_complete:
                raise ValueError("TIMEOUT cannot retain an accepted plan or checked verdict")
        elif self.certificate is None or not self.verification_complete:
            raise ValueError("non-TIMEOUT verdict requires a complete certificate/check")
        if (self.resulting_plan is not None) != (self.outcome is SwapOutcome.VALID):
            raise ValueError("only VALID retains a proposed plan")
        return self

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return (self.reason,)


class ComputedSwapValidationResult(_SwapClaim):
    """Affirmative construction requires fresh replay against supplied authority.

    Wire claims must be checked with verify_swap_validation and independently
    loaded roots. A digest, model_copy, historical stamp or caller boolean is
    never authority. Context carries roots, not a precomputed PASS token.
    """

    @model_validator(mode="after")
    def independently_checked(self, info: ValidationInfo) -> Self:
        if self.outcome is SwapOutcome.TIMEOUT:
            return self
        if not info.context or "authority" not in info.context:
            raise ValueError("computed swap verdict requires independent authority replay")
        from savora_ai.core.reasoning.swap_proof import _check_claim

        check = _check_claim(self, **info.context["authority"], clock=info.context["clock"])
        if not check.accepted:
            if not check.complete:
                from savora_ai.core.reasoning.swap_checks import _Interrupted

                if check.reason not in ("RESERVATION", "DEADLINE"):
                    raise ValueError("unexpected incomplete checker result")
                raise _Interrupted(check.reason, check.actual_verification)
            raise ValueError("independent swap proof reconstruction failed")
        return self


class SwapSelectionPrecheck(_SwapModel):
    option: MealOptionReference
    status: RuleStatus
    lane: Literal["PASS", "FAIL", "UNKNOWN", "NO_OP"]
    assessment_digest: _ContentDigest


class SwapSelectionVisit(_SwapModel):
    option: MealOptionReference
    outcome: SwapOutcome
    failure_scope: Literal["OPERATION", "CANDIDATE"] | None
    reason: Literal[
        "TARGET_LOCKED",
        "NO_OP",
        "BASELINE_INVALID",
        "RESULT_FAILED",
        "REQUIRED_FACT_UNKNOWN",
        "COMPLETE_PASS",
    ]
    validation_digest: _ContentDigest
    proof_bytes: ByteCount
    result_bytes: ByteCount

    @model_validator(mode="after")
    def complete_visit(self) -> Self:
        if self.outcome is SwapOutcome.TIMEOUT:
            raise ValueError("unfinished validation is not a completed selection visit")
        return self


class SwapSelectionDisposition(_SwapModel):
    option: MealOptionReference
    disposition: Literal[
        "NO_OP", "HARD_FAIL", "UNVISITED", "REJECTED", "INSUFFICIENT_DATA", "SELECTED"
    ]


class SwapSelectionReservation(_SwapModel):
    policy: Literal["synthetic-bounded-swap-ledger.v1"] = "synthetic-bounded-swap-ledger.v1"
    kind: Literal["HEADER", "HARD_CHECK", "ORDER", "VISIT", "FINAL", "ENCODE"]
    option: MealOptionReference | None = None
    execution: SwapWork
    verification: SwapWork
    reserved: SwapWork
    # Includes each nested B1 reservation record, not just compact outer notes.
    proof_records: Annotated[int, Field(ge=1, le=1024)]
    validation_calls: Annotated[int, Field(ge=0, le=1)] = 0

    @model_validator(mode="after")
    def exact_sum(self) -> Self:
        if self.reserved.model_dump() != {
            n: getattr(self.execution, n) + getattr(self.verification, n)
            for n in SwapWork.model_fields
        }:
            raise ValueError("selection reservation must include execution and independent replay")
        if (self.option is not None) != (self.kind in ("HARD_CHECK", "VISIT", "FINAL")):
            raise ValueError("selection reservation option differs from operation kind")
        if self.validation_calls != int(self.kind in ("VISIT", "FINAL")):
            raise ValueError("selection invocation count differs from operation kind")
        return self


class ComputedSwapSelectionCertificate(_SwapModel):
    schema_version: Literal["computed-swap-selection-certificate.v1"] = (
        "computed-swap-selection-certificate.v1"
    )
    policy: Literal["synthetic-bounded-swap-selection-full-replay.v1"] = (
        "synthetic-bounded-swap-selection-full-replay.v1"
    )
    input_digest: _ContentDigest
    eligibility_digest: _ContentDigest
    original_options: Annotated[tuple[MealOptionReference, ...], Field(max_length=50)]
    prechecks: Annotated[tuple[SwapSelectionPrecheck, ...], Field(max_length=50)]
    eligible_order: Annotated[tuple[MealOptionReference, ...], Field(max_length=50)]
    unknown_order: Annotated[tuple[MealOptionReference, ...], Field(max_length=50)]
    dispositions: Annotated[tuple[SwapSelectionDisposition, ...], Field(max_length=50)]
    visits: Annotated[tuple[SwapSelectionVisit, ...], Field(max_length=50)]
    unvisited: Annotated[tuple[MealOptionReference, ...], Field(max_length=50)]
    reservations: Annotated[tuple[SwapSelectionReservation, ...], Field(max_length=1024)]
    final_visit: SwapSelectionVisit | None = None
    final_certificate: ComputedSwapCertificate | None = None
    proof_bytes_reserved: ByteCount = 1_048_576
    result_bytes_reserved: ByteCount = 1_048_576

    @model_validator(mode="after")
    def complete_partition_shape(self) -> Self:
        originals = self.original_options
        if tuple(o.option_id for o in originals) != tuple(sorted({o.option_id for o in originals})):
            raise ValueError("selection requires the canonical complete original inventory")
        if tuple(p.option for p in self.prechecks) != originals or (
            tuple(d.option for d in self.dispositions) != originals
        ):
            raise ValueError("each original option requires exactly one check and disposition")
        candidates = self.eligible_order + self.unknown_order
        covered = tuple(v.option for v in self.visits) + self.unvisited
        if len({o.option_id for o in candidates}) != len(candidates) or (
            len({o.option_id for o in covered}) != len(covered) or set(covered) != set(candidates)
        ):
            raise ValueError("selection visit prefix and suffix must partition candidate lanes")
        if (self.final_visit is None) != (self.final_certificate is None):
            raise ValueError("final validation requires paired note and B1 certificate")
        return self


class _SwapSelectionClaim(_SwapModel):
    schema_version: Literal["computed-swap-selection-result.v1"] = (
        "computed-swap-selection-result.v1"
    )
    request: PlannedSwapRequest
    domain: SwapReference
    ranking: SwapReference
    limits: SwapSelectionLimits
    criterion: Literal["FIRST_VALID_IN_ELIGIBLE_ORDER"] = "FIRST_VALID_IN_ELIGIBLE_ORDER"
    operation_scope: Literal["EXPLICIT_REPLACEMENT_DOMAIN"] = "EXPLICIT_REPLACEMENT_DOMAIN"
    outcome: SwapOutcome
    failure_scope: Literal["OPERATION", "DOMAIN"] | None = None
    reason: Literal[
        "FIRST_VALID",
        "TARGET_LOCKED",
        "BASELINE_INVALID",
        "ALL_EXCLUDED",
        "EMPTY_DOMAIN",
        "REQUIRED_FACT_UNKNOWN",
        "RESERVATION",
        "DEADLINE",
    ]
    stage: Literal[
        "RESERVATION",
        "PRECHECK",
        "RANKING",
        "VALIDATION",
        "FINAL_VALIDATION",
        "ENCODING",
        "VERIFICATION",
        "COMPLETE",
    ]
    certificate: ComputedSwapSelectionCertificate | None = None
    selected: MealOptionReference | None = None
    resulting_plan: SwapPlanSnapshot | None = None
    verification_complete: bool = False
    exhaustive: bool = False
    actual_execution: SwapWork = SwapWork()
    actual_verification: SwapWork = SwapWork()
    proof_bytes: ByteCount = 0

    @property
    def accepted(self) -> bool:
        return self.outcome is SwapOutcome.VALID and self.verification_complete

    @model_validator(mode="after")
    def selected_shape(self) -> Self:
        if self.outcome is SwapOutcome.TIMEOUT:
            if (
                self.selected is not None
                or self.resulting_plan is not None
                or self.certificate is not None
                or self.verification_complete
                or self.exhaustive
            ):
                raise ValueError("unfinished selection cannot retain a checked witness")
        else:
            if self.certificate is None or not self.verification_complete:
                raise ValueError("complete selection requires independently checked coverage")
            if (self.outcome is SwapOutcome.VALID) != (self.selected is not None):
                raise ValueError("only VALID selects a replacement")
            if (self.resulting_plan is not None) != (self.selected is not None):
                raise ValueError("selected replacement requires its complete plan")
            if self.outcome is SwapOutcome.VALID and self.exhaustive:
                raise ValueError("FIRST_VALID does not claim exhaustive domain rejection")
        return self


class ComputedSwapSelectionResult(_SwapSelectionClaim):
    @model_validator(mode="after")
    def independently_checked_selection(self, info: ValidationInfo) -> Self:
        if self.outcome is SwapOutcome.TIMEOUT:
            return self
        if not info.context or "authority" not in info.context:
            raise ValueError("computed selection requires independent authority replay")
        from savora_ai.core.reasoning.swap_proof import _check_selection_claim

        report = _check_selection_claim(
            self, **info.context["authority"], clock=info.context["clock"]
        )
        if not report.accepted:
            if not report.complete and report.reason in ("RESERVATION", "DEADLINE"):
                from savora_ai.core.reasoning.swap_checks import _Interrupted

                raise _Interrupted(report.reason, report.actual_verification)
            raise ValueError("independent selection proof reconstruction failed")
        return self
