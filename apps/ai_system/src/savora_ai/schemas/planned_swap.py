"""Synthetic swap declarations and structural bindings, never swap feasibility.

Independent arguments designate a trusted loader boundary, not authentication.
Original WEEKLY_PLAN payloads remain immutable; projections are declarations that
must match separately selected PLANNED_SWAP material. No predicate executes here.
"""

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Any, Literal, Self, get_args, get_origin

from pydantic import Field, TypeAdapter, model_validator

from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.manifest import _KnowledgeContextRequest, _mandatory_checks
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    RuleContext,
    _canonical_content,
    _check_validated_output,
    _content_digest,
)
from savora_ai.schemas.combinations import PortionState, RecipeSnapshotReference
from savora_ai.schemas.daily import (
    DailyMealOption,
    MealOptionReference,
    MealSlot,
    _context_binding,
    _DailyModel,
    _DailySnapshot,
    _evidenced,
    _option_key,
)
from savora_ai.schemas.filtering import _evidence_union
from savora_ai.schemas.food_graph import _OpaqueId
from savora_ai.schemas.knowledge import (
    EvidenceReference,
    RuleDefinition,
    RuleEnvironment,
    _NonBlank,
)
from savora_ai.schemas.knowledge_base import (
    KnowledgeBaseSnapshot,
    KnowledgeWorkflow,
    _ContentDigest,
)
from savora_ai.schemas.weekly import (
    WeekDayReference,
    WeeklyAssignment,
    WeeklyPlanningRequest,
    WeeklySourceSnapshot,
    WeeklyTrial,
    _bind_trial,
    _daily_request,
    _week_days,
)

Revision = Annotated[int, Field(ge=1, le=1_000_000)]
Count = Annotated[int, Field(ge=0, le=1_000_000)]
ByteCount = Annotated[int, Field(ge=0, le=1_048_576)]


class SwapBoundaryError(ValueError):
    """Conflicting independent authority, distinct from a semantic verdict."""

    def __init__(self, code: str, message: str):
        if code not in {
            "PIN_MISMATCH",
            "STALE_PLAN",
            "STALE_LOCKS",
            "UNSUPPORTED_PROTOCOL",
            "INCOMPATIBLE_RELEASE",
            "INVALID_BRIDGE",
        }:
            raise ValueError("unsupported swap boundary code")
        self.code = code
        super().__init__(code + ": " + message)


class _SwapModel(_DailyModel):
    @classmethod
    def _validate_alias_keys(cls, value: object) -> None:
        super()._validate_alias_keys(value)
        _check_validated_output(value)
        if isinstance(value, dict):
            for name, field in cls.model_fields.items():
                if get_origin(field.annotation) is Literal:
                    literals = get_args(field.annotation)
                    for key in (name, field.alias):
                        if key in value and len(literals) == 1:
                            literal = literals[0]
                            if type(literal) in (int, bool) and type(value[key]) is not type(
                                literal
                            ):
                                raise ValueError(
                                    "literal booleans/integers require exact scalar types"
                                )

    @model_validator(mode="after")
    def bounded_synthetic(self) -> Self:
        if any(e.environment is not RuleEnvironment.SYNTHETIC for e in _evidence_union(self)):
            raise ValueError("swap contracts are synthetic only")
        if len(self.model_dump_json(by_alias=True).encode()) > 1_048_576:
            raise ValueError("swap structural envelope exceeds 1 MiB")
        return self


class _SwapSnapshot(_DailySnapshot, _SwapModel):
    """Content digests use the established unordered declaration policy, not event order."""


class SwapReference(_SwapModel):
    record_id: _OpaqueId
    version: _NonBlank
    content_digest: _ContentDigest


class SyntheticTargetReference(_SwapModel):
    schema_version: Literal["synthetic-swap-target-reference.v1"] = (
        "synthetic-swap-target-reference.v1"
    )
    target_id: _OpaqueId
    version: _NonBlank
    content_digest: _ContentDigest
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def evidenced(self) -> Self:
        _evidenced(self.evidence)
        return self


class SwapSlotIdentity(_SwapModel):
    day: WeekDayReference
    slot: MealSlot

    @property
    def canonical_index(self) -> int:
        return 3 * (self.day.day_index - 1) + tuple(MealSlot).index(self.slot)


def _recipe_reference(candidate: CandidateRecipeFacts) -> RecipeSnapshotReference:
    return RecipeSnapshotReference(
        recipe_id=candidate.recipe_id,
        recipe_version=candidate.recipe_version,
        snapshot_id=candidate.snapshot_id,
        snapshot_version=candidate.snapshot_version,
        content_digest=candidate.content_digest,
        catalogue_version=candidate.catalogue_version,
    )


def _fixed_meal_identity(option: DailyMealOption) -> object:
    combo = option.combination
    components = []
    for component in combo.components:
        body = component.model_dump(mode="json")
        # Projected context-bound recipe digests are evaluation metadata, not a new meal.
        body["recipe_snapshot"].pop("content_digest")
        body["preparation"]["recipe_snapshot"].pop("content_digest")
        components.append(body)
    return (
        combo.combination_id,
        combo.portion_configuration_id,
        combo.portion_configuration_version,
        _canonical_content(components),
    )


def _candidate_bindings(
    options: tuple[DailyMealOption, ...], candidates: tuple[CandidateRecipeFacts, ...]
) -> None:
    recipes = {c.recipe_id: c for c in candidates}
    if len(recipes) != len(candidates):
        raise ValueError("duplicate/conflicting candidate recipe identity")
    for option in options:
        for component in option.combination.components:
            candidate = recipes.get(component.recipe_snapshot.recipe_id)
            if candidate is None or component.recipe_snapshot != _recipe_reference(candidate):
                raise ValueError("component differs from complete independent recipe snapshot")


class SavedSlotPayload(_SwapModel):
    identity: SwapSlotIdentity
    source: SwapReference
    option: DailyMealOption
    recipes: Annotated[tuple[CandidateRecipeFacts, ...], Field(min_length=1, max_length=32)]

    @model_validator(mode="after")
    def fixed_payload(self) -> Self:
        if self.option.reference.portion_state is not PortionState.FIXED:
            raise ValueError("saved slots require exact FIXED portions")
        _candidate_bindings((self.option,), self.recipes)
        if {c.recipe_id for c in self.recipes} != {
            p.recipe_snapshot.recipe_id for p in self.option.combination.components
        }:
            raise ValueError("saved slot recipe inventory must be exact")
        return self


class SavedPlanReference(_SwapModel):
    plan_id: _OpaqueId
    effective_revision: Revision
    snapshot_id: _OpaqueId
    snapshot_version: _NonBlank
    snapshot_digest: _ContentDigest


class SavedPlanVerificationRecord(_SwapModel):
    status: Literal["VERIFIED_AT_SAVE", "UNVERIFIED"]
    prior_protocol: (
        Literal["computed-weekly-solve-result.v1", "computed-weekly-solve-result.v2"] | None
    )
    prior_result: SwapReference | None
    verification_policy: _NonBlank
    semantic_assessment: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def historical_only(self) -> Self:
        if (self.prior_protocol is None) != (self.prior_result is None) or (
            (self.status == "VERIFIED_AT_SAVE") != (self.prior_result is not None)
        ):
            raise ValueError("historical verification requires paired native protocol/result pins")
        _evidenced(self.evidence)
        return self


def _canonical_slots(slots: tuple[SavedSlotPayload, ...]) -> None:
    if tuple(s.identity.canonical_index for s in slots) != tuple(range(21)):
        raise ValueError("plan requires exact21 canonical slot identities")
    days = {s.identity.day.day_index: s.identity.day for s in slots}
    if any(days[s.identity.day.day_index] != s.identity.day for s in slots):
        raise ValueError("conflicting day identity")


class _SavedPlanContent(_SwapModel):
    schema_version: Literal["saved-plan-snapshot.v1"] = "saved-plan-snapshot.v1"
    policy_version: Literal["synthetic-saved-plan.v1"] = "synthetic-saved-plan.v1"
    plan_id: _OpaqueId
    snapshot_id: _OpaqueId
    version: _NonBlank
    original_request: WeeklyPlanningRequest
    original_sources: WeeklySourceSnapshot
    original_context: RuleContext
    original_candidates: Annotated[tuple[CandidateRecipeFacts, ...], Field(max_length=150)]
    original_trial: WeeklyTrial
    original_assignment: WeeklyAssignment
    slots: Annotated[tuple[SavedSlotPayload, ...], Field(min_length=21, max_length=21)]
    target: SyntheticTargetReference
    verification: SavedPlanVerificationRecord
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def original_bindings(self) -> Self:
        request, trial, assignment = (
            self.original_request,
            self.original_trial,
            self.original_assignment,
        )
        if request.source != self.original_sources or (
            self.original_sources.daily_source.context != self.original_context
        ):
            raise ValueError("original source/context differs from saved request")
        _bind_trial(request, trial)
        if (
            assignment.request_digest != request.content_digest
            or (assignment.week_id, assignment.week_version, assignment.start_date)
            != (request.week_id, request.week_version, request.start_date)
            or assignment.source != request.expected_source
            or assignment.daily_source != self.original_sources.expected_daily_source
            or assignment.context_digest != self.original_context.content_digest
        ):
            raise ValueError("saved assignment differs from original request/source")
        chosen = {(c.day.day_index, c.slot): c for c in trial.choices}
        assigned = {
            (d.day.day_index, c.slot): (d.day, c.option)
            for d in assignment.days
            for c in d.trial.choices
        }
        if assigned != {key: (c.day, c.option) for key, c in chosen.items()}:
            raise ValueError("saved trial and assignment differ")
        for day in assignment.days:
            domain = next(d for d in request.days if d.day == day.day)
            if day.trial.request_digest != _daily_request(request, domain).content_digest:
                raise ValueError("saved daily assignment differs from original daily request")
        _canonical_slots(self.slots)
        pool = {o.reference.option_id: o for o in self.original_sources.daily_source.options}
        expected_source = SwapReference(
            record_id=self.original_sources.source_id,
            version=self.original_sources.version,
            content_digest=self.original_sources.content_digest,
        )
        _candidate_bindings(tuple(pool.values()), self.original_candidates)
        recipes = {c.recipe_id: c for c in self.original_candidates}
        for payload in self.slots:
            choice = chosen[payload.identity.day.day_index, payload.identity.slot]
            if (
                payload.identity.day != choice.day
                or payload.option.reference != choice.option
                or pool.get(choice.option.option_id) != payload.option
                or payload.source != expected_source
                or any(recipes[c.recipe_id] != c for c in payload.recipes)
            ):
                raise ValueError("saved full slot payload differs from original material")
        _evidenced(self.evidence)
        return self


class SavedPlanSnapshot(_SavedPlanContent, _SwapSnapshot):
    _body_type = _SavedPlanContent


class _SavedMaterialContent(_SwapModel):
    schema_version: Literal["saved-plan-material.v1"] = "saved-plan-material.v1"
    snapshot: SavedPlanSnapshot
    reference: SavedPlanReference

    @model_validator(mode="after")
    def selected_snapshot(self) -> Self:
        if (
            self.reference.plan_id,
            self.reference.snapshot_id,
            self.reference.snapshot_version,
            self.reference.snapshot_digest,
        ) != (
            self.snapshot.plan_id,
            self.snapshot.snapshot_id,
            self.snapshot.version,
            self.snapshot.content_digest,
        ):
            raise ValueError("independent effective reference differs from immutable snapshot")
        return self


class SavedPlanMaterial(_SavedMaterialContent, _SwapSnapshot):
    _body_type = _SavedMaterialContent


class LockKind(StrEnum):
    USER = "USER"
    SYSTEM = "SYSTEM"


class SavedSlotLock(_SwapModel):
    slot: SwapSlotIdentity
    kind: LockKind
    reason: _NonBlank
    authority: EvidenceReference


class _LockContent(_SwapModel):
    schema_version: Literal["saved-plan-lock-inventory.v1"] = "saved-plan-lock-inventory.v1"
    record_id: _OpaqueId
    version: _NonBlank
    revision: Revision
    saved_plan: SavedPlanReference
    entries: Annotated[tuple[SavedSlotLock, ...], Field(max_length=42)]
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def unique_locks(self) -> Self:
        if len({(e.slot, e.kind) for e in self.entries}) != len(self.entries):
            raise ValueError("duplicate user/system lock entry")
        _evidenced(self.evidence)
        return self


class SavedPlanLockInventory(_LockContent, _SwapSnapshot):
    _body_type = _LockContent


class _PermissionContent(_SwapModel):
    schema_version: Literal["swap-target-permission.v1"] = "swap-target-permission.v1"
    record_id: _OpaqueId
    version: _NonBlank
    saved_plan: SavedPlanReference
    locks: SwapReference
    target: SwapSlotIdentity
    context: SwapReference
    profile_id: _OpaqueId
    profile_version: _NonBlank
    operation: Literal["REPLACE_FIXED_MEAL"] = "REPLACE_FIXED_MEAL"
    authority: EvidenceReference


class SwapTargetPermission(_PermissionContent, _SwapSnapshot):
    _body_type = _PermissionContent


class _SwapSourceContent(_SwapModel):
    schema_version: Literal["planned-swap-source.v1"] = "planned-swap-source.v1"
    record_id: _OpaqueId
    version: _NonBlank
    context: RuleContext
    candidates: Annotated[tuple[CandidateRecipeFacts, ...], Field(max_length=150)]
    options: Annotated[tuple[DailyMealOption, ...], Field(max_length=150)]
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def dedicated_source(self) -> Self:
        if self.context.workflow is not KnowledgeWorkflow.PLANNED_SWAP:
            raise ValueError("swap source requires separately selected PLANNED_SWAP context")
        if len({o.reference.option_id for o in self.options}) != len(self.options) or len(
            {_option_key(o.reference) for o in self.options}
        ) != len(self.options):
            raise ValueError("duplicate or aliased swap source option")
        _candidate_bindings(self.options, self.candidates)
        identities: dict[tuple[object, ...], object] = {}
        counts: dict[str, int] = {}

        def consistent(key: tuple[object, ...], value: object) -> None:
            if identities.setdefault(key, value) != value:
                raise ValueError("conflicting source/configuration/preparation identity")

        for option in self.options:
            _context_binding(option.combination, self.context)
            ref, combo = option.reference, option.combination
            if ref.portion_state is not PortionState.FIXED:
                raise ValueError("swap source options must have exact FIXED portions")
            counts[ref.combination_id] = counts.get(ref.combination_id, 0) + 1
            if counts[ref.combination_id] > 50:
                raise ValueError("combination preset ceiling exceeded")
            consistent(("snapshot", combo.snapshot_id, combo.snapshot_version), combo)
            consistent(
                (
                    "config",
                    ref.combination_id,
                    ref.portion_configuration_id,
                    ref.portion_configuration_version,
                ),
                combo,
            )
            for part in combo.components:
                consistent(
                    (
                        "preparation",
                        part.recipe_snapshot,
                        part.preparation.preparation_id,
                        part.preparation.version,
                    ),
                    part.preparation,
                )
            for record in (
                *option.measurements,
                *((option.suitability,) if option.suitability else ()),
            ):
                if (record.source.source_id, record.source.version) == (
                    self.record_id,
                    self.version,
                ):
                    raise ValueError("external origin cannot self-reference swap source")
                consistent(
                    ("external", record.source.source_id, record.source.version), record.source
                )
        _evidenced(self.evidence)
        return self


class PlannedSwapSourceSnapshot(_SwapSourceContent, _SwapSnapshot):
    _body_type = _SwapSourceContent


class SwapOptionProjection(_SwapModel):
    original: MealOptionReference | None
    projected: MealOptionReference
    policy: Literal["CONTEXT_REFERENCES_ONLY"] = "CONTEXT_REFERENCES_ONLY"
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def evidenced(self) -> Self:
        _evidenced(self.evidence)
        return self


class _BridgeContent(_SwapModel):
    schema_version: Literal["planned-swap-workflow-bridge.v1"] = "planned-swap-workflow-bridge.v1"
    policy: Literal["synthetic-planned-swap-bridge.v1"] = "synthetic-planned-swap-bridge.v1"
    record_id: _OpaqueId
    version: _NonBlank
    saved_plan: SavedPlanReference
    original_context: SwapReference
    original_source: SwapReference
    swap_context: SwapReference
    swap_source: SwapReference
    knowledge: SwapReference
    target_release: SyntheticTargetReference
    mappings: Annotated[tuple[SwapOptionProjection, ...], Field(max_length=150)]
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def unique_mapping(self) -> Self:
        old = [m.original.model_dump_json() for m in self.mappings if m.original is not None]
        if len(set(old)) != len(old) or len(
            {m.projected.model_dump_json() for m in self.mappings}
        ) != len(self.mappings):
            raise ValueError("projection map must be one-to-one")
        _evidenced(self.evidence)
        return self


class PlannedSwapWorkflowBridge(_BridgeContent, _SwapSnapshot):
    _body_type = _BridgeContent


class _RequestContent(_SwapModel):
    schema_version: Literal["planned-swap-request.v1"] = "planned-swap-request.v1"
    policy: Literal["synthetic-planned-swap.v1"] = "synthetic-planned-swap.v1"
    record_id: _OpaqueId
    version: _NonBlank
    saved_plan: SavedPlanReference
    locks: SwapReference
    permission: SwapReference
    sources: SwapReference
    bridge: SwapReference
    context: SwapReference
    knowledge: SwapReference
    target_release: SyntheticTargetReference
    target: SwapSlotIdentity
    operation: Literal["REPLACE_FIXED_MEAL"] = "REPLACE_FIXED_MEAL"


class PlannedSwapRequest(_RequestContent, _SwapSnapshot):
    _body_type = _RequestContent


class _DomainContent(_SwapModel):
    schema_version: Literal["swap-replacement-domain.v1"] = "swap-replacement-domain.v1"
    record_id: _OpaqueId
    version: _NonBlank
    request: PlannedSwapRequest
    sources: PlannedSwapSourceSnapshot
    options: Annotated[tuple[MealOptionReference, ...], Field(max_length=50)]

    @model_validator(mode="after")
    def original_domain(self) -> Self:
        source_ref = SwapReference(
            record_id=self.sources.record_id,
            version=self.sources.version,
            content_digest=self.sources.content_digest,
        )
        if self.request.sources != source_ref:
            raise ValueError("domain source differs from request pin")
        pool = {o.reference.option_id: o.reference for o in self.sources.options}
        if tuple(r.option_id for r in self.options) != tuple(
            sorted({r.option_id for r in self.options})
        ):
            raise ValueError("replacement domain must have unique canonical original IDs")
        if any(pool.get(r.option_id) != r for r in self.options):
            raise ValueError("replacement option differs from exact independent source")
        return self


class SwapReplacementDomain(_DomainContent, _SwapSnapshot):
    _body_type = _DomainContent


class SyntheticRankEntry(_SwapModel):
    option: MealOptionReference
    priority: Count


class _RankingContent(_SwapModel):
    schema_version: Literal["synthetic-swap-ranking.v1"] = "synthetic-swap-ranking.v1"
    policy: Literal["synthetic-fixed-combination-rank.v1", "CANONICAL_OPTION_ID"]
    record_id: _OpaqueId
    version: _NonBlank
    domain: SwapReplacementDomain
    eligible: Annotated[tuple[MealOptionReference, ...], Field(max_length=50)]
    entries: Annotated[tuple[SyntheticRankEntry, ...], Field(max_length=50)]
    ranker_version: _NonBlank
    evidence: tuple[EvidenceReference, ...]
    eligibility_assessment: Literal["DECLARED_ONLY"] = "DECLARED_ONLY"
    criterion: Literal["FIRST_VALID_IN_ELIGIBLE_ORDER"] = "FIRST_VALID_IN_ELIGIBLE_ORDER"

    @model_validator(mode="after")
    def complete_declared_ranking(self) -> Self:
        if len({r.option_id for r in self.eligible}) != len(self.eligible) or any(
            r not in self.domain.options for r in self.eligible
        ):
            raise ValueError("declared eligible IDs must be a unique original-domain subset")
        if len({e.option.option_id for e in self.entries}) != len(self.entries) or {
            e.option.model_dump_json() for e in self.entries
        } != {r.model_dump_json() for r in self.eligible}:
            raise ValueError("ranking must cover every declared eligible ID exactly once")
        order = tuple(
            e.option for e in sorted(self.entries, key=lambda e: (e.priority, e.option.option_id))
        )
        if self.policy == "CANONICAL_OPTION_ID" and order != tuple(
            sorted(self.eligible, key=lambda r: r.option_id)
        ):
            raise ValueError("canonical policy cannot declare another ordering")
        _evidenced(self.evidence)
        return self


def _selection_digest(value: object) -> str:
    data = TypeAdapter(Any).dump_python(value, mode="json", by_alias=True)
    raw = json.dumps(
        _canonical_content(data),
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode()).hexdigest()


class SyntheticSwapRanking(_RankingContent, _SwapSnapshot):
    _body_type = _RankingContent

    @property
    def eligibility_digest(self) -> str:
        """Read-only binding; it does not authenticate the declared eligible set.

        A computed property preserves historical v1 declaration wire/digests.
        B2 independently derives the set before comparing this binding.
        """
        return _selection_digest(
            {
                "policy": "synthetic-swap-hard-eligible-set.v1",
                "domain": self.domain.content_digest,
                "eligible": self.eligible,
            }
        )


class _ManifestContent(_SwapModel):
    schema_version: Literal["expected-swap-check-manifest.v1"] = "expected-swap-check-manifest.v1"
    request: PlannedSwapRequest
    knowledge: KnowledgeBaseSnapshot
    context: RuleContext
    locks: SavedPlanLockInventory
    permission: SwapTargetPermission
    original_slots: Annotated[tuple[SwapSlotIdentity, ...], Field(min_length=21, max_length=21)]
    required_checks: tuple[RuleDefinition, ...]
    semantic_assessment: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"

    @model_validator(mode="after")
    def complete_definitions(self) -> Self:
        if self.context.workflow is not KnowledgeWorkflow.PLANNED_SWAP:
            raise ValueError("swap manifest requires exact PLANNED_SWAP workflow")
        accepted = _KnowledgeContextRequest(kb=self.knowledge, context=self.context)
        knowledge = build_knowledge_snapshot(
            accepted.kb, expected_digest=accepted.context.expected_kb_digest
        )
        if tuple(s.canonical_index for s in self.original_slots) != tuple(range(21)) or (
            self.request.target not in self.original_slots
            or any(e.slot not in self.original_slots for e in self.locks.entries)
        ):
            raise ValueError("manifest requires exact original21 slots and lock membership")
        days = tuple(self.original_slots[i].day for i in range(0, 21, 3))
        _week_days(days, days[0].week_id, days[0].week_version, days[0].calendar_date)
        if any(slot.day != days[i // 3] for i, slot in enumerate(self.original_slots)):
            raise ValueError("manifest has conflicting original day identities")
        if (
            self.request.context
            != SwapReference(
                record_id=self.context.context_id,
                version=self.context.version,
                content_digest=self.context.content_digest,
            )
            or self.request.knowledge
            != SwapReference(
                record_id=self.knowledge.kb_id,
                version=self.knowledge.version,
                content_digest=self.knowledge.content_digest,
            )
            or self.request.locks
            != SwapReference(
                record_id=self.locks.record_id,
                version=self.locks.version,
                content_digest=self.locks.content_digest,
            )
            or self.request.permission
            != SwapReference(
                record_id=self.permission.record_id,
                version=self.permission.version,
                content_digest=self.permission.content_digest,
            )
            or self.locks.saved_plan != self.request.saved_plan
            or self.permission.saved_plan != self.request.saved_plan
            or self.permission.target != self.request.target
            or self.permission.locks != self.request.locks
            or self.permission.context != self.request.context
            or (self.permission.profile_id, self.permission.profile_version)
            != (self.context.profile_id, self.context.profile_version)
        ):
            raise ValueError("manifest authority/context/target pin mismatch")
        if self.required_checks != _mandatory_checks(knowledge, accepted.context):
            raise ValueError("swap manifest must contain all exact authoritative definitions")
        return self

    @property
    def locked_slots(self) -> tuple[SwapSlotIdentity, ...]:
        return tuple(s for s in self.original_slots if s != self.request.target)

    @property
    def target_lock_kinds(self) -> tuple[LockKind, ...]:
        return tuple(e.kind for e in self.locks.entries if e.slot == self.request.target)


class ExpectedSwapCheckManifest(_ManifestContent, _SwapSnapshot):
    _body_type = _ManifestContent


class SavedPlanContractCheck(_SwapModel):
    schema_version: Literal["saved-plan-contract-check.v1"] = "saved-plan-contract-check.v1"
    saved_plan: SavedPlanReference
    slot_digests: Annotated[tuple[_ContentDigest, ...], Field(min_length=21, max_length=21)]
    semantic_assessment: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    historical_authentication: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"


class _ResultPlanContent(_SwapModel):
    schema_version: Literal["swap-plan-snapshot.v1"] = "swap-plan-snapshot.v1"
    base: SavedPlanMaterial
    request: PlannedSwapRequest
    sources: PlannedSwapSourceSnapshot
    projected_replacement: MealOptionReference
    slots: Annotated[tuple[SavedSlotPayload, ...], Field(min_length=21, max_length=21)]
    semantic_assessment: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"

    @model_validator(mode="after")
    def exactly_one_target(self) -> Self:
        _canonical_slots(self.slots)
        if self.request.saved_plan != self.base.reference:
            raise ValueError("proposed result differs from expected saved revision")
        if self.request.sources != SwapReference(
            record_id=self.sources.record_id,
            version=self.sources.version,
            content_digest=self.sources.content_digest,
        ):
            raise ValueError("proposed result differs from independently supplied source")
        index = self.request.target.canonical_index
        if self.base.snapshot.slots[index].identity != self.request.target:
            raise ValueError("target differs from original full slot identity")
        for i, (old, new) in enumerate(zip(self.base.snapshot.slots, self.slots, strict=True)):
            if new.identity != old.identity or (i != index and new != old):
                raise ValueError("all20 non-target payloads must remain exactly unchanged")
        new = self.slots[index]
        pool = {o.reference.option_id: o for o in self.sources.options}
        if (
            new.option.reference != self.projected_replacement
            or pool.get(self.projected_replacement.option_id) != new.option
        ):
            raise ValueError("replacement differs from complete source option")
        if new.source != self.request.sources:
            raise ValueError("replacement origin differs from exact swap source")
        recipes = {c.recipe_id: c for c in self.sources.candidates}
        if any(recipes.get(c.recipe_id) != c for c in new.recipes):
            raise ValueError("replacement recipes differ from independent source")
        # Ignore context and integrity metadata: rewrapping the same fixed meal is a no-op.
        if _fixed_meal_identity(self.base.snapshot.slots[index].option) == _fixed_meal_identity(
            new.option
        ):
            raise ValueError("a metadata-only target rewrap is not a replacement")
        return self


class SwapPlanSnapshot(_ResultPlanContent, _SwapSnapshot):
    _body_type = _ResultPlanContent

    @property
    def proposed_snapshot_id(self) -> str:
        """Deterministic proposal identity only; never a persisted revision or credential."""
        return "swap-proposal-" + self.content_digest


class SwapWork(_SwapModel):
    source_items: Count = 0
    bridge_items: Count = 0
    lock_comparisons: Count = 0
    candidate_preparations: Count = 0
    combination_preparations: Count = 0
    predicate_obligations: Count = 0
    day_assessments: Count = 0
    week_assessments: Count = 0
    domain_visits: Count = 0
    ordering_items: Count = 0
    full_validations: Count = 0
    checker_steps: Count = 0


class SwapValidationLimits(_SwapModel):
    schema_version: Literal["swap-validation-limits.v1"] = "swap-validation-limits.v1"
    max_reserved_work: SwapWork
    max_proof_records: Annotated[int, Field(ge=0, le=1024)]
    max_proof_bytes: ByteCount
    max_result_bytes: ByteCount
    max_full_validations: Annotated[int, Field(ge=0, le=1)]
    max_cache_entries: Literal[0] = 0
    deadline: Annotated[float, Field(allow_inf_nan=False)] | None = None


class SwapSelectionLimits(_SwapModel):
    schema_version: Literal["swap-selection-limits.v1"] = "swap-selection-limits.v1"
    max_reserved_work: SwapWork
    max_proof_records: Annotated[int, Field(ge=0, le=1024)]
    max_proof_bytes: ByteCount
    max_result_bytes: ByteCount
    max_full_validations: Annotated[int, Field(ge=0, le=51)]
    max_domain_visits: Annotated[int, Field(ge=0, le=50)]
    max_cache_entries: Literal[0] = 0
    deadline: Annotated[float, Field(allow_inf_nan=False)] | None = None


def _slot_digests(saved: SavedPlanMaterial) -> tuple[str, ...]:
    return tuple(_content_digest(s) for s in saved.snapshot.slots)
