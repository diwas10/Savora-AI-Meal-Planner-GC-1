"""Version-disjoint swap proof/resource DECLARATIONS ONLY; no checker or execution."""

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

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
