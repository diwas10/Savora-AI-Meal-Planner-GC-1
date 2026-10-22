"""Review-only mapping and inactive clinical contracts, disjoint from KB releases.

APPROVED is a review declaration, never authentication. No production loader or
activation toggle is provided. Existing synthetic KB semantics remain unchanged.
"""

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from savora_ai.schemas.daily import DailySourceReference, _DailyModel
from savora_ai.schemas.food_graph import _OpaqueId
from savora_ai.schemas.knowledge import ApprovalStatus, EvidenceReference, _NonBlank
from savora_ai.schemas.nutrients_v2 import Nutrient

DateToken = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")]


class MappingReviewV1(_DailyModel):
    status: ApprovalStatus
    reviewer: _NonBlank | None
    effective_date: DateToken | None
    evidence: Annotated[tuple[EvidenceReference, ...], Field(max_length=16)]

    @model_validator(mode="after")
    def review_metadata(self) -> Self:
        if self.effective_date is not None:
            date.fromisoformat(self.effective_date)
        if self.status is ApprovalStatus.APPROVED and (
            self.reviewer is None or self.effective_date is None or not self.evidence
        ):
            raise ValueError("approved review requires reviewer, effective date and evidence")
        return self


class IngredientMappingV1(_DailyModel):
    schema_version: Literal["reviewed-ingredient-mapping.v1"] = "reviewed-ingredient-mapping.v1"
    recipe_id: _OpaqueId
    recipe_version: _NonBlank
    source_ingredient_id: _OpaqueId
    source_ingredient_name: _NonBlank
    source: DailySourceReference
    canonical_ingredient_id: _OpaqueId | None
    mapping_status: Literal["RESOLVED", "UNRESOLVED", "CONFLICTING"]
    subingredients_complete: bool
    review: MappingReviewV1

    @model_validator(mode="after")
    def resolved_identity(self) -> Self:
        if (self.mapping_status == "RESOLVED") != (self.canonical_ingredient_id is not None):
            raise ValueError("only resolved mappings identify one canonical ingredient")
        if self.review.status is ApprovalStatus.APPROVED and self.mapping_status != "RESOLVED":
            raise ValueError("unresolved/conflicting mapping cannot be approved")
        return self


class IngredientDerivationV1(_DailyModel):
    parent_id: _OpaqueId
    relationship: Literal["DERIVED_FROM", "CONTAINS"]
    review: MappingReviewV1


class IngredientAllergenEvidenceV1(_DailyModel):
    allergen_id: _OpaqueId
    status: Literal["PRESENT", "VERIFIED_ABSENT", "UNKNOWN"]
    review: MappingReviewV1


class CanonicalIngredientV1(_DailyModel):
    ingredient_id: _OpaqueId
    subingredients_complete: bool
    derived_from: Annotated[tuple[IngredientDerivationV1, ...], Field(max_length=32)]
    allergens: Annotated[tuple[IngredientAllergenEvidenceV1, ...], Field(max_length=32)]

    @model_validator(mode="after")
    def unambiguous_node(self) -> Self:
        if len({a.allergen_id for a in self.allergens}) != len(self.allergens):
            raise ValueError("duplicate/conflicting allergen declarations")
        if len({e.parent_id for e in self.derived_from}) != len(self.derived_from):
            raise ValueError("duplicate/conflicting derivation edges")
        return self


class IngredientMappingReleaseV1(_DailyModel):
    schema_version: Literal["ingredient-mapping-review-release.v1"] = (
        "ingredient-mapping-review-release.v1"
    )
    environment: Literal["REVIEW_ONLY"] = "REVIEW_ONLY"
    release_id: _OpaqueId
    version: _NonBlank
    catalogue_version: _NonBlank
    source: DailySourceReference
    recipe_id: _OpaqueId
    recipe_version: _NonBlank
    source_ingredient_ids: Annotated[tuple[_OpaqueId, ...], Field(max_length=128)]
    ingredient_inventory_complete: bool
    mappings: Annotated[tuple[IngredientMappingV1, ...], Field(max_length=128)]
    canonical_ingredients: Annotated[tuple[CanonicalIngredientV1, ...], Field(max_length=256)]

    @model_validator(mode="after")
    def exact_inventory(self) -> Self:
        ids = self.source_ingredient_ids
        mapped = [m.source_ingredient_id for m in self.mappings]
        nodes = {n.ingredient_id: n for n in self.canonical_ingredients}
        if (
            len(set(ids)) != len(ids)
            or len(set(mapped)) != len(mapped)
            or not set(mapped).issubset(ids)
            or len(nodes) != len(self.canonical_ingredients)
        ):
            raise ValueError("duplicate/conflicting mapping or canonical inventory")
        for mapping in self.mappings:
            if (mapping.recipe_id, mapping.recipe_version, mapping.source) != (
                self.recipe_id,
                self.recipe_version,
                self.source,
            ):
                raise ValueError("mapping differs from exact recipe/source version")
        # Missing parents/nodes are representable gaps; cycles are malformed.
        active: set[str] = set()
        done: set[str] = set()

        def visit(identity: str) -> None:
            if identity in active:
                raise ValueError("cyclic derived ingredient relationship")
            if identity in done or identity not in nodes:
                return
            active.add(identity)
            for edge in nodes[identity].derived_from:
                visit(edge.parent_id)
            active.remove(identity)
            done.add(identity)

        for identity in nodes:
            visit(identity)
        return self


class ClinicalRuleDraftV1(_DailyModel):
    schema_version: Literal["clinical-rule-draft.v1"] = "clinical-rule-draft.v1"
    condition: Literal["HYPERTENSION", "TYPE_2_DIABETES", "DYSLIPIDEMIA"]
    activation: Literal["INACTIVE_NOT_AUTHORIZED"] = "INACTIVE_NOT_AUTHORIZED"
    threshold: None = None
    nutrient: Nutrient | None
    scope: Literal["UNAPPROVED"] = "UNAPPROVED"
    applicability: Literal["REQUIRES_CLINICAL_REVIEW"] = "REQUIRES_CLINICAL_REVIEW"
    candidate_sources: Annotated[tuple[EvidenceReference, ...], Field(max_length=16)]
    approval: Literal["PENDING"] = "PENDING"
