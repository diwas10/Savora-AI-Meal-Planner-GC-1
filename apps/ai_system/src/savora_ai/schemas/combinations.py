"""Provisional synthetic combination snapshots; declarations never grant eligibility.

Accepted candidate/KB membership and source authority require future evaluation.
No ingredient completeness, conversions, nutrition or compatibility is inferred here.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from savora_ai.schemas.candidates import (
    _build_snapshot,
    _content_digest,
    _paired_context,
    _require_evidence,
)
from savora_ai.schemas.filtering import _evidence_union
from savora_ai.schemas.food_graph import FoodEntity, FoodEntityKind, _OpaqueId
from savora_ai.schemas.knowledge import (
    EvidenceReference,
    _ContractModel,
    _NonBlank,
    _require_canonical_enum,
)
from savora_ai.schemas.knowledge_base import _ContentDigest
from savora_ai.schemas.reasoning import FactObservation


class PortionState(StrEnum):
    UNASSIGNED = "UNASSIGNED"
    FIXED = "FIXED"


class QuantityUnit(StrEnum):
    G = "g"
    ML = "mL"
    SERVING = "serving"


class CompositionGapReason(StrEnum):
    INCOMPLETE_COMPOSITION = "INCOMPLETE_COMPOSITION"
    UNVERIFIED_COMPOSITION = "UNVERIFIED_COMPOSITION"


class CombinationMeasurementBasis(StrEnum):
    AS_RECORDED = "AS_RECORDED"
    FIXED_PORTION_TOTAL = "FIXED_PORTION_TOTAL"


class RecipeSnapshotReference(_ContractModel):
    schema_version: Literal["recipe-snapshot-reference.v1"] = "recipe-snapshot-reference.v1"
    recipe_id: _OpaqueId
    recipe_version: _NonBlank
    snapshot_id: _OpaqueId
    snapshot_version: _NonBlank
    content_digest: _ContentDigest
    catalogue_version: _NonBlank


class PreparationBinding(_ContractModel):
    schema_version: Literal["preparation-binding.v1"] = "preparation-binding.v1"
    preparation_id: _OpaqueId
    version: _NonBlank
    recipe_snapshot: RecipeSnapshotReference
    basis_reference: EvidenceReference
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        _require_evidence(self.evidence)
        _evidence_union(self)
        return self


class ComponentQuantity(_ContractModel):
    schema_version: Literal["component-quantity.v1"] = "component-quantity.v1"
    amount: Annotated[int, Field(gt=0)] | Annotated[float, Field(gt=0, allow_inf_nan=False)]
    unit: QuantityUnit
    preparation_id: _OpaqueId
    preparation_version: _NonBlank
    basis_reference: EvidenceReference
    portion_reference: EvidenceReference
    evidence: tuple[EvidenceReference, ...]

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: QuantityUnit) -> QuantityUnit:
        _require_canonical_enum(value)
        return value

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        _require_evidence(self.evidence)
        _evidence_union(self)
        return self


class CombinationComponent(_ContractModel):
    schema_version: Literal["combination-component.v1"] = "combination-component.v1"
    component_id: _OpaqueId
    recipe_snapshot: RecipeSnapshotReference
    preparation: PreparationBinding
    quantity: ComponentQuantity | None = None
    role_references: tuple[FoodEntity, ...]
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_bindings(self) -> Self:
        _require_evidence(self.evidence)
        if self.recipe_snapshot != self.preparation.recipe_snapshot:
            raise ValueError("component preparation must bind the exact recipe snapshot")
        if not self.role_references or any(
            role.kind is not FoodEntityKind.CULINARY_ROLE_REFERENCE for role in self.role_references
        ):
            raise ValueError("components require explicit culinary role references")
        if len({role.entity_id for role in self.role_references}) != len(self.role_references):
            raise ValueError("duplicate component role identity or revision")
        quantity = self.quantity
        if quantity is not None and (
            quantity.preparation_id,
            quantity.preparation_version,
            quantity.basis_reference,
        ) != (
            self.preparation.preparation_id,
            self.preparation.version,
            self.preparation.basis_reference,
        ):
            raise ValueError("quantity preparation/basis differs from component preparation")
        _evidence_union(self)
        return self


class CombinationObservation(_ContractModel):
    schema_version: Literal["combination-observation.v1"] = "combination-observation.v1"
    fact_id: _NonBlank
    version: _NonBlank
    combination_id: _OpaqueId
    combination_version: _NonBlank
    portion_configuration_id: _OpaqueId | None = None
    portion_configuration_version: _NonBlank | None = None
    observation: FactObservation
    measurement_basis: CombinationMeasurementBasis | None = None
    basis_reference: EvidenceReference | None = None

    @field_validator("measurement_basis")
    @classmethod
    def validate_basis(
        cls, value: CombinationMeasurementBasis | None
    ) -> CombinationMeasurementBasis | None:
        if value is not None:
            _require_canonical_enum(value)
        return value

    @model_validator(mode="after")
    def validate_binding(self) -> Self:
        if self.fact_id != self.observation.fact_id:
            raise ValueError("combination fact differs from embedded observation identity")
        _paired_context(self.portion_configuration_id, self.portion_configuration_version)
        numeric = type(self.observation.value) in (int, float)
        if numeric:
            if self.measurement_basis is None or self.basis_reference is None:
                raise ValueError("numeric combination facts require explicit basis and evidence")
            if (self.measurement_basis is CombinationMeasurementBasis.FIXED_PORTION_TOTAL) != (
                self.portion_configuration_id is not None
            ):
                raise ValueError("numeric fixed-portion basis requires exact configuration pins")
        elif self.measurement_basis is not None or self.basis_reference is not None:
            raise ValueError("non-numeric combination facts cannot carry numeric bases")
        _evidence_union(self)
        return self


class _CombinationContent(_ContractModel):
    schema_version: Literal["combination-facts.v1"] = "combination-facts.v1"
    digest_policy_version: Literal["combination-content-digest.v1"] = (
        "combination-content-digest.v1"
    )
    combination_id: _OpaqueId
    version: _NonBlank
    snapshot_id: _OpaqueId
    snapshot_version: _NonBlank
    components: tuple[CombinationComponent, ...]
    composition_complete: bool
    composition_gap_reasons: tuple[CompositionGapReason, ...]
    portion_state: PortionState
    portion_configuration_id: _OpaqueId | None = None
    portion_configuration_version: _NonBlank | None = None
    observations: tuple[CombinationObservation, ...]
    context_id: _OpaqueId
    context_version: _NonBlank
    context_digest: _ContentDigest
    kb_id: _OpaqueId
    kb_version: _NonBlank
    kb_digest: _ContentDigest
    graph_id: _OpaqueId
    graph_version: _NonBlank
    catalogue_version: _NonBlank
    taxonomy_version: _NonBlank | None
    check_catalogue_version: _NonBlank
    evidence: tuple[EvidenceReference, ...]

    @field_validator("portion_state")
    @classmethod
    def validate_state(cls, value: PortionState) -> PortionState:
        _require_canonical_enum(value)
        return value

    @model_validator(mode="after")
    def validate_combination(self) -> Self:
        _require_evidence(self.evidence)
        if not self.components:
            raise ValueError("combinations require at least one component occurrence")
        if len({c.component_id for c in self.components}) != len(self.components):
            raise ValueError("duplicate component occurrence identity")
        gaps = self.composition_gap_reasons
        for reason in gaps:
            _require_canonical_enum(reason)
        if len(set(gaps)) != len(gaps) or self.composition_complete != (not gaps):
            raise ValueError("composition completeness requires exact noncontradictory gaps")
        _paired_context(self.portion_configuration_id, self.portion_configuration_version)
        fixed = self.portion_state is PortionState.FIXED
        if fixed != (self.portion_configuration_id is not None) or any(
            (c.quantity is not None) != fixed for c in self.components
        ):
            raise ValueError("portions must be entirely UNASSIGNED or versioned and entirely FIXED")
        snapshots: dict[tuple[str, str], RecipeSnapshotReference] = {}
        preparations: dict[tuple[RecipeSnapshotReference, str, str], PreparationBinding] = {}
        roles: dict[str, FoodEntity] = {}
        for component in self.components:
            ref = component.recipe_snapshot
            if ref.catalogue_version != self.catalogue_version:
                raise ValueError("component recipe catalogue release mismatch")
            if snapshots.setdefault((ref.snapshot_id, ref.snapshot_version), ref) != ref:
                raise ValueError("conflicting recipe snapshot references")
            prep = component.preparation
            key = ref, prep.preparation_id, prep.version
            if preparations.setdefault(key, prep) != prep:
                raise ValueError("conflicting preparation declarations")
            for role in component.role_references:
                if roles.setdefault(role.entity_id, role) != role:
                    raise ValueError("conflicting role declarations")
        facts: set[str] = set()
        for fact in self.observations:
            if fact.fact_id in facts:
                raise ValueError(
                    "duplicate or conflicting combination observation identity/revision"
                )
            facts.add(fact.fact_id)
            if (fact.combination_id, fact.combination_version) != (
                self.combination_id,
                self.version,
            ):
                raise ValueError("combination observation owner/version mismatch")
            if fact.portion_configuration_id is not None and (
                fact.portion_configuration_id,
                fact.portion_configuration_version,
            ) != (self.portion_configuration_id, self.portion_configuration_version):
                raise ValueError("combination observation portion configuration mismatch")
            if fact.fact_id == "synthetic_combination_composition_complete" and (
                fact.observation.value is not None
                and (
                    type(fact.observation.value) is not bool
                    or fact.observation.value != self.composition_complete
                )
            ):
                raise ValueError("composition observation contradicts composition declaration")
        _evidence_union(self)
        return self


class CombinationFacts(_CombinationContent):
    content_digest: _ContentDigest

    @model_validator(mode="after")
    def validate_digest(self) -> Self:
        if self.content_digest != _content_digest(self):
            raise ValueError("combination snapshot content digest mismatch")
        return self

    @classmethod
    def build(
        cls, content: Self | dict[str, object], *, expected_digest: str | None = None
    ) -> Self:
        """Strictly validate and compute/verify integrity; performs no eligibility checks."""
        return _build_snapshot(cls, _CombinationContent, content, expected_digest)
