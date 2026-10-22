"""Explicit opt-in compact transport. Synthetic reasoning, never clinical approval."""

from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, model_validator

from savora_ai.schemas.candidates import RuleContext
from savora_ai.schemas.compact_swap_canonical import canonical_proof
from savora_ai.schemas.daily import DailyMealOption, _DailyModel
from savora_ai.schemas.filtering import _evidence_union
from savora_ai.schemas.food_graph import _OpaqueId
from savora_ai.schemas.knowledge import RuleEnvironment
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot, _ContentDigest
from savora_ai.schemas.nutrients_v2 import (
    Nutrient,
    NutrientBandV2,
    OptionNutrientsV2,
    Unit,
)
from savora_ai.schemas.planned_swap import (
    PlannedSwapRequest,
    PlannedSwapSourceSnapshot,
    PlannedSwapWorkflowBridge,
    SavedPlanLockInventory,
    SavedPlanMaterial,
    SwapSelectionLimits,
    SwapTargetPermission,
)
from savora_ai.schemas.swap_proof_types import SwapPhaseAssessment

Preset = Literal["STANDARD", "HIGHER_PROTEIN", "LOWER_CARB", "LOWER_ENERGY", "HIGHER_ENERGY"]
Revision = Annotated[int, Field(ge=1, le=1_000_000_000)]


class CompactSwapPhaseAssessment(SwapPhaseAssessment):
    """New protocol: deduplicated proof bytes, unchanged historical phase models."""

    schema_version: Literal["compact-swap-phase-assessment.v1"] = "compact-swap-phase-assessment.v1"

    @model_validator(mode="after")
    def bounded_synthetic(self) -> Self:
        if any(e.environment is not RuleEnvironment.SYNTHETIC for e in _evidence_union(self)):
            raise ValueError("compact swap contracts are synthetic only")
        canonical_proof(self)
        return self


class AuthorityReference(_DailyModel):
    record_id: _OpaqueId
    version: _OpaqueId
    content_digest: _ContentDigest


class CompactSavedPlanBinding(_DailyModel):
    plan_id: _OpaqueId
    revision: Revision
    owner_id: _OpaqueId
    profile_id: _OpaqueId
    profile_version: _OpaqueId
    snapshot_digest: _ContentDigest
    target_snapshot_digest: _ContentDigest
    kb_id: _OpaqueId
    kb_version: _OpaqueId
    kb_digest: _ContentDigest
    certificate_digest: _ContentDigest | None


class CompactSlot(_DailyModel):
    slot_id: Annotated[str, Field(pattern=r"^D[1-7]_(BREAKFAST|LUNCH|DINNER)$")]
    combination_id: _OpaqueId
    portion_preset: Preset


class CompactSourceReference(_DailyModel):
    catalogue_version: _OpaqueId
    combination_id: _OpaqueId
    content_digest: _ContentDigest


class CompactReplacement(_DailyModel):
    combination_id: _OpaqueId
    portion_preset: Preset


class CompactRankEntry(_DailyModel):
    candidate_id: _OpaqueId
    priority: Annotated[int, Field(ge=0, le=1_000_000)]


class CompactSwapInput(_DailyModel):
    schema_version: Literal["compact-planned-swap-input.v1"] = "compact-planned-swap-input.v1"
    policy: Literal["synthetic-compact-fixed-swap.v1"] = "synthetic-compact-fixed-swap.v1"
    mode: Literal["B1", "B2"]
    saved_plan: CompactSavedPlanBinding
    authority: AuthorityReference
    catalogue_version: _OpaqueId
    sources: Annotated[tuple[CompactSourceReference, ...], Field(min_length=1, max_length=71)]
    slots: Annotated[tuple[CompactSlot, ...], Field(min_length=21, max_length=21)]
    target_slot_id: Annotated[str, Field(pattern=r"^D[1-7]_(BREAKFAST|LUNCH|DINNER)$")]
    replacement: CompactReplacement | None
    ranking: AuthorityReference | None
    candidates: Annotated[tuple[CompactRankEntry, ...], Field(max_length=50)]

    @model_validator(mode="after")
    def closed_inventory(self) -> Self:
        expected = tuple(f"D{d}_{m}" for d in range(1, 8) for m in ("BREAKFAST", "LUNCH", "DINNER"))
        if tuple(s.slot_id for s in self.slots) != expected:
            raise ValueError("requires canonical exact21 saved slots")
        if len({s.combination_id for s in self.sources}) != len(self.sources):
            raise ValueError("duplicate source identity")
        if any(s.catalogue_version != self.catalogue_version for s in self.sources):
            raise ValueError("conflicting catalogue release")
        if len({e.candidate_id for e in self.candidates}) != len(self.candidates):
            raise ValueError("duplicate candidate identity")
        if self.mode == "B1":
            if self.replacement is None or self.ranking is not None or self.candidates:
                raise ValueError("B1 requires one replacement and no ranking")
        elif self.replacement is not None or self.ranking is None or not self.candidates:
            raise ValueError("B2 requires pinned ranking and candidate IDs/priorities only")
        return self


class CompactPortionSource(_DailyModel):
    preset: Preset
    original: DailyMealOption | None
    projected: DailyMealOption
    nutrients: OptionNutrientsV2

    @model_validator(mode="after")
    def exact_nutrients(self) -> Self:
        ref = self.original.reference if self.original is not None else self.projected.reference
        if self.nutrients.option != ref:
            raise ValueError("nutrient vector differs from exact fixed option")
        return self


class CompactCombinationSource(_DailyModel):
    schema_version: Literal["compact-combination-source.v1"] = "compact-combination-source.v1"
    catalogue_version: _OpaqueId
    combination_id: _OpaqueId
    portions: Annotated[tuple[CompactPortionSource, ...], Field(min_length=1, max_length=5)]

    @model_validator(mode="after")
    def actual_configurations(self) -> Self:
        if len({p.preset for p in self.portions}) != len(self.portions):
            raise ValueError("duplicate available preset")
        for p in self.portions:
            for o in (p.original, p.projected):
                if o is not None and (
                    o.reference.combination_id != self.combination_id
                    or o.combination.catalogue_version != self.catalogue_version
                ):
                    raise ValueError("source option differs from combination/catalogue")
        return self


class CompactTargetSnapshot(_DailyModel):
    schema_version: Literal["compact-target-snapshot.v1"] = "compact-target-snapshot.v1"
    profile_id: _OpaqueId
    profile_version: _OpaqueId
    calculator_payload: dict[str, JsonValue]
    bands: Annotated[tuple[NutrientBandV2, ...], Field(max_length=128)]


class CompactAuthorizedCandidate(CompactRankEntry):
    combination_id: _OpaqueId
    portion_preset: Preset


class CompactSwapAuthority(_DailyModel):
    """Server-only material. Resolver must be scoped to the authenticated request."""

    schema_version: Literal["compact-swap-authority.v1"] = "compact-swap-authority.v1"
    authenticated_user_id: _OpaqueId
    owner_id: _OpaqueId
    current_profile_id: _OpaqueId
    current_profile_version: _OpaqueId
    saved_plan: SavedPlanMaterial
    target_snapshot: CompactTargetSnapshot
    request: PlannedSwapRequest
    locks: SavedPlanLockInventory
    permission: SwapTargetPermission
    knowledge: KnowledgeBaseSnapshot
    context: RuleContext
    sources: PlannedSwapSourceSnapshot
    bridge: PlannedSwapWorkflowBridge
    ranking: AuthorityReference | None
    candidates: Annotated[tuple[CompactAuthorizedCandidate, ...], Field(max_length=50)]
    limits: SwapSelectionLimits


class CompactNutrientTotal(_DailyModel):
    nutrient: Nutrient
    unit: Unit
    value: Annotated[str, Field(pattern=r"^(0|[1-9][0-9]{0,11})(\.[0-9]{1,3})?$")] | None
    complete: bool


class CompactSwapResult(_DailyModel):
    schema_version: Literal["compact-planned-swap-result.v1"] = "compact-planned-swap-result.v1"
    input_digest: _ContentDigest
    status: Literal["VALID", "REJECTED", "INSUFFICIENT_DATA", "TIMEOUT", "ADMISSION_FAILED"]
    reason: str
    replacement_combination_id: _OpaqueId | None = None
    replacement_portion_preset: Preset | None = None
    changed_day_totals: Annotated[tuple[CompactNutrientTotal, ...], Field(max_length=7)] = ()
    certificate_digest: _ContentDigest | None = None
    reconstructed_bytes: Annotated[int, Field(ge=0, le=4_194_304)] = 0
    verification_complete: bool = False


class CompactSwapVerification(_DailyModel):
    schema_version: Literal["compact-planned-swap-verification.v1"] = (
        "compact-planned-swap-verification.v1"
    )
    accepted: bool
    complete: bool
    reason: str
