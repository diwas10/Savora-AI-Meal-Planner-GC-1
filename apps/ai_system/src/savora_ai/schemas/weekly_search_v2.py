"""Phase 7.1c: synthetic v2 search/proof DECLARATIONS ONLY, never accepted proofs.

All strategies, including chronological DFS, have DECLARED_ONLY support here.
No CSP traversal, ordering selection, bound derivation, predicate, pruning, replay or
coverage verification executes. A failure record claims a complete known-failure
basis; its source truth, applicability and whole-subtree soundness remain DEFERRED.
Hashes/evidence references are integrity declarations, never authentication.

Original domains are numbered by day index, BREAKFAST/LUNCH/DINNER, then unique
option_id ascending (the v1 primary ordering key). Depth counts chosen variables;
canonical_index identifies a slot independently of depth. Tuple order preserves
selection paths and event order. Schema validation checks bindings and shape,
not that the transcript follows a real execution or covers the completion space.

Accounting snapshots distinguish logical visits, execution/verification semantic
work units, combined reservations, optional observed physical calls and sampled
diagnostics. Preparations count semantic option/candidate preparations, predicates
count obligations, DAY/WEEK count assessments, heuristics count scoring/propagation
units and proof verification counts checker steps. None is a physical Python call
count. Reservations precede record-producing work; a snapshot does not prove it
happened. Phase 7.2a must specify/check actual charging and retain v1 accounting.

Deferred to 7.2a: independently selected source/KB/candidate/manifest acceptance,
full mandatory rule coverage, facts/evidence/completeness/applicability truth,
strategy execution/tie-breaks, event transitions/rollback, each pruning theorem,
disjoint and complete frontier coverage, actual counters/byte reservations/clock
readings and all outcome/witness verification. No computed result is exported.
FEASIBLE requires a fully checked witness; INFEASIBLE complete known failure;
INSUFFICIENT_DATA complete coverage with unrefuted UNKNOWN; TIMEOUT unfinished
required work. This declaration's outcome is always None and exhaustive is False.

Untrusted JSON must use validate_contract_json on original text/bytes (1 MiB,
depth 64, duplicate aliases/keys rejected). Native JSON methods are trusted round
trips only. Flat bounded events/frontier avoid recursive branch trees; the complete
declaration also has a 1 MiB encoded structural ceiling. Future execution must
return TIMEOUT on insufficient required proof capacity, never truncate coverage.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Discriminator, Field, Tag, model_validator

from savora_ai.schemas.candidates import STRICT_JSON_MAX_BYTES, _check_validated_output
from savora_ai.schemas.daily import (
    DailySourceReference,
    MealOptionReference,
    MealSlot,
    _DailyModel,
    _evidenced,
)
from savora_ai.schemas.filtering import _evidence_union
from savora_ai.schemas.food_graph import _OpaqueId
from savora_ai.schemas.knowledge import (
    EvidenceReference,
    PredicateOperator,
    RuleEnvironment,
    RuleReference,
    RuleScope,
    _NonBlank,
)
from savora_ai.schemas.knowledge_base import _ContentDigest
from savora_ai.schemas.reasoning import ApplicabilityStatus, FactObservation, RuleStatus
from savora_ai.schemas.weekly import (
    WeekDayReference,
    WeeklyPlanningRequest,
    WeeklySourceReference,
)

_SlotIndex = Annotated[int, Field(ge=0, le=20)]
_OptionIndex = Annotated[int, Field(ge=0, le=49)]
_EventIndex = Annotated[int, Field(ge=0, le=1023)]
_Count = Annotated[int, Field(ge=0, le=1_000_000)]
_Nodes = Annotated[int, Field(ge=0, le=200_000)]
_Records = Annotated[int, Field(ge=0, le=8192)]
_Bytes = Annotated[int, Field(ge=0, le=1_048_576)]
_Checkpoint = Annotated[int, Field(ge=1, le=1_000_000)]
_Cache = Annotated[int, Field(ge=0, le=4096)]


class _V2Model(_DailyModel):
    @classmethod
    def _validate_alias_keys(cls, value: object) -> None:
        # This shared ingress hook runs after hostile-container flattening, before
        # field normalization, in both native JSON and strict Python modes.
        super()._validate_alias_keys(value)
        # Reuse the bounded data-graph/canonical-enum guard. It also rejects
        # custom enum metaclasses before their iteration hooks could execute.
        _check_validated_output(value)
        if isinstance(value, dict):
            if (
                "exhaustive" in cls.model_fields
                and "exhaustive" in value
                and value["exhaustive"] is not False
            ):
                raise ValueError("unverified certificate requires exact boolean False exhaustion")
            if "relevant_basis_complete" in cls.model_fields and any(
                key in value and value[key] is not True
                for key in ("relevant_basis_complete", "relevantBasisComplete")
            ):
                raise ValueError("known-failure basis completeness requires exact boolean True")

    @model_validator(mode="after")
    def validate_synthetic_scope(self) -> Self:
        if any(e.environment is not RuleEnvironment.SYNTHETIC for e in _evidence_union(self)):
            raise ValueError("v2 search declarations are synthetic only")
        return self


class WeeklyStrategyPolicyV2(StrEnum):
    CHRONOLOGICAL = "synthetic-chronological-weekly-search.v2"
    REVERSE_VALUES = "synthetic-reverse-option-weekly-search.v2"
    FORWARD_CHECKING = "synthetic-forward-checking-weekly-search.v2"
    INCREMENTAL = "synthetic-incremental-weekly-search.v2"
    INCREMENTAL_FORWARD_CHECKING = "synthetic-incremental-forward-checking-weekly-search.v2"
    MRV = "synthetic-mrv-weekly-search.v2"
    STATIC_MRV = "synthetic-static-original-mrv-weekly-search.v2"
    STATIC_MRV_FORWARD_CHECKING = "synthetic-static-original-mrv-forward-weekly-search.v2"
    STATIC_MRV_INCREMENTAL = "synthetic-static-original-mrv-incremental-weekly-search.v2"
    STATIC_MRV_INCREMENTAL_FORWARD_CHECKING = (
        "synthetic-static-original-mrv-incremental-forward-weekly-search.v2"
    )


class WeeklySearchStrategyV2(_V2Model):
    schema_version: Literal["weekly-search-strategy.v2"] = "weekly-search-strategy.v2"
    policy: WeeklyStrategyPolicyV2
    support: Literal["DECLARED_ONLY"] = "DECLARED_ONLY"
    criterion: Literal["FIRST_FEASIBLE"] = "FIRST_FEASIBLE"
    variable_order: Literal["CHRONOLOGICAL", "MRV", "STATIC_MRV_ORIGINAL_DOMAINS"]
    value_order: Literal["OPTION_ID_ASC", "OPTION_ID_DESC"]
    propagation: Literal["NONE", "KNOWN_FAILURE_FORWARD_CHECK"]
    variable_tie_break: Literal["CANONICAL_SLOT_INDEX"] = "CANONICAL_SLOT_INDEX"
    original_domain_policy: Literal["synthetic-weekly-original-domains.v2"] = (
        "synthetic-weekly-original-domains.v2"
    )

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        permitted = {
            WeeklyStrategyPolicyV2.CHRONOLOGICAL: ("CHRONOLOGICAL", "OPTION_ID_ASC", "NONE"),
            WeeklyStrategyPolicyV2.REVERSE_VALUES: ("CHRONOLOGICAL", "OPTION_ID_DESC", "NONE"),
            WeeklyStrategyPolicyV2.FORWARD_CHECKING: (
                "CHRONOLOGICAL",
                "OPTION_ID_ASC",
                "KNOWN_FAILURE_FORWARD_CHECK",
            ),
            WeeklyStrategyPolicyV2.INCREMENTAL: ("CHRONOLOGICAL", "OPTION_ID_ASC", "NONE"),
            WeeklyStrategyPolicyV2.INCREMENTAL_FORWARD_CHECKING: (
                "CHRONOLOGICAL",
                "OPTION_ID_ASC",
                "KNOWN_FAILURE_FORWARD_CHECK",
            ),
            WeeklyStrategyPolicyV2.MRV: ("MRV", "OPTION_ID_ASC", "KNOWN_FAILURE_FORWARD_CHECK"),
            WeeklyStrategyPolicyV2.STATIC_MRV: (
                "STATIC_MRV_ORIGINAL_DOMAINS",
                "OPTION_ID_ASC",
                "NONE",
            ),
            WeeklyStrategyPolicyV2.STATIC_MRV_FORWARD_CHECKING: (
                "STATIC_MRV_ORIGINAL_DOMAINS",
                "OPTION_ID_ASC",
                "KNOWN_FAILURE_FORWARD_CHECK",
            ),
            WeeklyStrategyPolicyV2.STATIC_MRV_INCREMENTAL: (
                "STATIC_MRV_ORIGINAL_DOMAINS",
                "OPTION_ID_ASC",
                "NONE",
            ),
            WeeklyStrategyPolicyV2.STATIC_MRV_INCREMENTAL_FORWARD_CHECKING: (
                "STATIC_MRV_ORIGINAL_DOMAINS",
                "OPTION_ID_ASC",
                "KNOWN_FAILURE_FORWARD_CHECK",
            ),
        }
        if (self.variable_order, self.value_order, self.propagation) != permitted[self.policy]:
            raise ValueError("strategy fields must match the exact versioned allowlisted policy")
        return self


class WeeklySearchIdentityV2(_V2Model):
    """Repeated event binding. Manifest/candidate digest authority is DEFERRED.

    Candidate-set digest policy reserves SHA-256 over compact ASCII JSON, sorted
    object keys, with keys ``policy`` (the policy token) and ``candidates`` (sorted
    unique arrays of recipe_id, recipe_version, snapshot_id, snapshot_version,
    content_digest). Source acceptance, pool assembly and hash checking are 7.2a
    work, not implemented by this declaration.
    """

    schema_version: Literal["weekly-search-identity.v2"] = "weekly-search-identity.v2"
    request_id: _OpaqueId
    request_version: _NonBlank
    request_digest: _ContentDigest
    manifest_digest: _ContentDigest
    candidate_set_policy_version: Literal["synthetic-weekly-candidate-set-digest.v2"] = (
        "synthetic-weekly-candidate-set-digest.v2"
    )
    candidate_set_digest: _ContentDigest
    source: WeeklySourceReference
    daily_source: DailySourceReference
    context_id: _OpaqueId
    context_version: _NonBlank
    context_digest: _ContentDigest
    profile_id: _OpaqueId
    profile_version: _NonBlank
    kb_id: _OpaqueId
    kb_version: _NonBlank
    kb_digest: _ContentDigest
    strategy: WeeklySearchStrategyV2


class WeeklySlotIdentityV2(_V2Model):
    canonical_index: _SlotIndex
    day: WeekDayReference
    slot: MealSlot

    @model_validator(mode="after")
    def validate_index(self) -> Self:
        if self.canonical_index != (self.day.day_index - 1) * 3 + tuple(MealSlot).index(self.slot):
            raise ValueError("canonical slot index differs from explicit day/meal identity")
        return self


class WeeklyOriginalDomainV2(_V2Model):
    slot: WeeklySlotIdentityV2
    options: Annotated[tuple[MealOptionReference, ...], Field(max_length=50)]

    @model_validator(mode="after")
    def validate_original_options(self) -> Self:
        ids = tuple(o.option_id for o in self.options)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("original options require unique option IDs in ascending order")
        snapshots = tuple((o.snapshot_id, o.snapshot_version) for o in self.options)
        if len(set(snapshots)) != len(snapshots):
            raise ValueError("aliased original combination snapshots are not distinct options")
        return self


class WeeklySelectedOptionV2(_V2Model):
    depth: _SlotIndex
    slot: WeeklySlotIdentityV2
    original_domain_index: _OptionIndex
    option: MealOptionReference


_Path = Annotated[tuple[WeeklySelectedOptionV2, ...], Field(max_length=21)]


def _validate_path(path: tuple[WeeklySelectedOptionV2, ...]) -> None:
    if tuple(c.depth for c in path) != tuple(range(len(path))):
        raise ValueError("selection path depths must be exactly 0 through length-1")
    if len({c.slot.canonical_index for c in path}) != len(path):
        raise ValueError("selection path cannot assign a slot twice")


class WeeklyBranchScopeV2(_V2Model):
    branch_id: _OpaqueId
    extent: Literal["PREFIX_COMPLETIONS", "SLOT_ALTERNATIVES", "LEAF"]
    path: _Path
    decision_slot: WeeklySlotIdentityV2 | None = None
    original_domain_indexes: Annotated[tuple[_OptionIndex, ...], Field(max_length=50)] = ()

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        _validate_path(self.path)
        if self.extent == "SLOT_ALTERNATIVES":
            if self.decision_slot is None or not self.original_domain_indexes:
                raise ValueError("alternative scope requires an explicit slot and original indexes")
            if self.decision_slot.canonical_index in {c.slot.canonical_index for c in self.path}:
                raise ValueError("alternative scope cannot select an already assigned slot")
            if self.original_domain_indexes != tuple(sorted(set(self.original_domain_indexes))):
                raise ValueError("alternative indexes must be unique and ascending")
        elif self.decision_slot is not None or self.original_domain_indexes:
            raise ValueError("only alternative scopes carry a decision slot/domain slice")
        if (self.extent == "LEAF") != (len(self.path) == 21):
            raise ValueError("only a LEAF scope contains all 21 selected slots")
        return self


class WeeklyRuleObligationV2(_V2Model):
    kind: Literal["RULE"] = "RULE"
    rule: RuleReference
    scope: RuleScope


class WeeklyPrerequisiteObligationV2(_V2Model):
    kind: Literal["PREREQUISITE"] = "PREREQUISITE"
    prerequisite: Literal[
        "CANDIDATE_MEMBERSHIP",
        "COMPOSITION_AUTHORITY",
        "FIXED_CONFIGURATION",
        "SLOT_SUITABILITY",
        "MANDATORY_CHECK_COVERAGE",
    ]
    scope: RuleScope | None = None

    @model_validator(mode="after")
    def validate_coverage_scope(self) -> Self:
        if (self.prerequisite == "MANDATORY_CHECK_COVERAGE") != (self.scope is not None):
            raise ValueError("only mandatory-check coverage names an explicit rule scope")
        return self


def _declared_kind(value: object) -> str | None:
    # Fixed schema dispatch: wrapped _ContractModel variants cannot use Pydantic's
    # field-inferred discriminator. Do not invoke hostile mapping overrides.
    fields = value if type(value) is dict else vars(value) if isinstance(value, _V2Model) else None
    kind = dict.get(fields, "kind") if type(fields) is dict else None
    return kind if type(kind) is str else None


WeeklyObligationV2 = Annotated[
    Annotated[WeeklyRuleObligationV2, Tag("RULE")]
    | Annotated[WeeklyPrerequisiteObligationV2, Tag("PREREQUISITE")],
    Discriminator(_declared_kind),
]
_Obligations = Annotated[tuple[WeeklyObligationV2, ...], Field(min_length=1, max_length=256)]


class WeeklyFailureBasisV2(_V2Model):
    """A declared evaluation reference, never verification of an arbitrary evidence string."""

    obligations: _Obligations
    evaluation_digest: _ContentDigest
    relevant_basis_complete: Literal[True]
    declared_status: Literal["FAIL"] = "FAIL"
    soundness: Literal["DEFERRED"] = "DEFERRED"
    evidence: Annotated[tuple[EvidenceReference, ...], Field(min_length=1, max_length=64)]

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        _evidenced(self.evidence)
        keys = tuple(o.model_dump_json() for o in self.obligations)
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate failure obligations")
        return self


class WeeklyWorkV2(_V2Model):
    """Declared semantic operation units, not inferred physical function calls."""

    candidate_preparations: _Count = 0
    combination_preparations: _Count = 0
    predicate_obligations: _Count = 0
    day_assessments: _Count = 0
    week_assessments: _Count = 0
    heuristic_evaluations: _Count = 0
    proof_verification_steps: _Count = 0


class WeeklyAccountingV2(_V2Model):
    schema_version: Literal["weekly-search-accounting.v2"] = "weekly-search-accounting.v2"
    policy: Literal[
        "synthetic-weekly-work-reservation.v2",
        "synthetic-weekly-forward-work-reservation.v2",
        "synthetic-weekly-incremental-work-reservation.v2",
        "synthetic-weekly-ordered-work-reservation.v2",
    ] = "synthetic-weekly-work-reservation.v2"
    logical_nodes: _Nodes = 0
    backtracks: _Nodes = 0
    execution_work: WeeklyWorkV2 = WeeklyWorkV2()
    verification_work: WeeklyWorkV2 = WeeklyWorkV2()
    reserved_work: WeeklyWorkV2 = WeeklyWorkV2()
    proof_records_reserved: _Records = 0
    proof_records_written: _Records = 0
    proof_bytes_reserved: _Bytes = 0
    proof_bytes_written: _Bytes = 0
    checkpoints: _Count = 0
    cache_capacity: _Cache = 0
    cache_entries: _Cache = 0
    cache_hits: _Count = 0
    cache_evictions: _Count = 0
    physical_evaluator_calls: _Count | Literal["NOT_RECORDED"] = "NOT_RECORDED"
    sampled_diagnostics: Annotated[int, Field(ge=0, le=1000)] = 0

    @model_validator(mode="after")
    def validate_reservations(self) -> Self:
        for field in WeeklyWorkV2.model_fields:
            if getattr(self.execution_work, field) + getattr(
                self.verification_work, field
            ) > getattr(self.reserved_work, field):
                raise ValueError("declared execution and verification work exceeds reservation")
        if (
            self.proof_records_written > self.proof_records_reserved
            or self.proof_bytes_written > self.proof_bytes_reserved
        ):
            raise ValueError("proof-producing operations require reserved record/byte capacity")
        if self.cache_entries > self.cache_capacity:
            raise ValueError("declared cache occupancy exceeds storage capacity")
        return self


class WeeklySearchLimitsV2(_V2Model):
    schema_version: Literal["weekly-search-limits.v2"] = "weekly-search-limits.v2"
    max_nodes: _Nodes
    max_reserved_work: WeeklyWorkV2
    max_proof_records: _Records
    max_proof_bytes: _Bytes
    max_cache_entries: _Cache = 0
    deadline: Annotated[float, Field(allow_inf_nan=False)] | None = None


class _EventV2(_V2Model):
    schema_version: Literal["weekly-proof-event.v2"] = "weekly-proof-event.v2"
    sequence: _EventIndex
    identity: WeeklySearchIdentityV2
    scope: WeeklyBranchScopeV2
    accounting: WeeklyAccountingV2

    @model_validator(mode="after")
    def validate_record_reservation(self) -> Self:
        if self.accounting.proof_records_written != self.sequence + 1:
            raise ValueError("ordered event must declare its own written/reserved proof record")
        if not self.accounting.proof_bytes_reserved or not self.accounting.proof_bytes_written:
            raise ValueError(
                "record-producing event requires positive declared proof byte capacity"
            )
        return self


class WeeklyVariableSelectionV2(_EventV2):
    kind: Literal["VARIABLE_SELECTION"] = "VARIABLE_SELECTION"
    depth: _SlotIndex
    selected_slot: WeeklySlotIdentityV2
    remaining_slots: Annotated[tuple[_SlotIndex, ...], Field(min_length=1, max_length=21)]

    @model_validator(mode="after")
    def validate_selection_shape(self) -> Self:
        assigned = {c.slot.canonical_index for c in self.scope.path}
        if self.scope.extent != "PREFIX_COMPLETIONS" or self.depth != len(self.scope.path):
            raise ValueError("variable selection uses an unfinished prefix and its explicit depth")
        if (
            self.remaining_slots != tuple(i for i in range(21) if i not in assigned)
            or self.selected_slot.canonical_index not in self.remaining_slots
        ):
            raise ValueError("remaining slots must name every unassigned canonical slot once")
        return self


class WeeklyValueSelectionV2(_EventV2):
    kind: Literal["VALUE_SELECTION"] = "VALUE_SELECTION"

    @model_validator(mode="after")
    def validate_value_shape(self) -> Self:
        if not self.scope.path or self.scope.extent == "SLOT_ALTERNATIVES":
            raise ValueError(
                "value selection records the prefix including the exact selected value"
            )
        return self


class WeeklyUnaryFailureV2(_EventV2):
    kind: Literal["UNARY_FAILURE"] = "UNARY_FAILURE"
    basis: WeeklyFailureBasisV2

    @model_validator(mode="after")
    def validate_unary_scope(self) -> Self:
        if self.scope.extent != "SLOT_ALTERNATIVES" or len(self.scope.original_domain_indexes) != 1:
            raise ValueError("unary failure declares one original value at an unassigned slot")
        if any(
            isinstance(o, WeeklyRuleObligationV2)
            and o.scope
            not in (
                RuleScope.PROFILE,
                RuleScope.RECIPE,
                RuleScope.COMBINATION,
            )
            for o in self.basis.obligations
        ):
            raise ValueError("unary failure cannot execute DAY/WEEK obligations")
        return self


class WeeklyDayFailureV2(_EventV2):
    kind: Literal["DAY_FAILURE"] = "DAY_FAILURE"
    day_index: Annotated[int, Field(ge=1, le=7)]
    basis: WeeklyFailureBasisV2

    @model_validator(mode="after")
    def validate_day_scope(self) -> Self:
        if (
            self.scope.extent == "SLOT_ALTERNATIVES"
            or sum(c.slot.day.day_index == self.day_index for c in self.scope.path) != 3
        ):
            raise ValueError("DAY closure needs all three actual day slots, not depth modulo three")
        if any(
            not isinstance(o, WeeklyRuleObligationV2) or o.scope is not RuleScope.DAY
            for o in self.basis.obligations
        ):
            raise ValueError("DAY failure requires DAY rule obligations")
        return self


class WeeklyWeekFailureV2(_EventV2):
    kind: Literal["WEEK_FAILURE"] = "WEEK_FAILURE"
    basis: WeeklyFailureBasisV2

    @model_validator(mode="after")
    def validate_week_scope(self) -> Self:
        if self.scope.extent != "LEAF" or any(
            not isinstance(o, WeeklyRuleObligationV2) or o.scope is not RuleScope.WEEK
            for o in self.basis.obligations
        ):
            raise ValueError("WEEK failure requires a complete trial and WEEK rule obligations")
        return self


class WeeklyDomainSliceV2(_V2Model):
    slot: WeeklySlotIdentityV2
    original_domain_indexes: Annotated[tuple[_OptionIndex, ...], Field(max_length=50)]

    @model_validator(mode="after")
    def validate_indexes(self) -> Self:
        if self.original_domain_indexes != tuple(sorted(set(self.original_domain_indexes))):
            raise ValueError("domain slice indexes must be unique and ascending")
        return self


class WeeklyNumericBoundV2(_V2Model):
    """An asserted interval; only the computed independent checker grants authority."""

    policy: Literal["synthetic-exact-quantity-interval.v2"] = "synthetic-exact-quantity-interval.v2"
    rule: RuleReference
    attribute: Literal["synthetic_day_quantity_total", "synthetic_week_quantity_total"]
    operator: PredicateOperator
    threshold: Annotated[int, Field(ge=0, le=21 * ((2**63 - 1) // 3))]
    day_index: Annotated[int, Field(ge=1, le=7)] | None
    lower: Annotated[int, Field(ge=0, le=21 * ((2**63 - 1) // 3))]
    upper: Annotated[int, Field(ge=0, le=21 * ((2**63 - 1) // 3))]
    applicability: ApplicabilityStatus
    applicability_evidence: Annotated[tuple[EvidenceReference, ...], Field(max_length=64)]
    required_observations: Annotated[tuple[FactObservation, ...], Field(max_length=256)]


class WeeklyForwardCheckClosureV2(_EventV2):
    kind: Literal["FORWARD_CHECK_CLOSURE"] = "FORWARD_CHECK_CLOSURE"
    derivation_policy: Literal["synthetic-forward-check-closure.v2"] = (
        "synthetic-forward-check-closure.v2"
    )
    basis: WeeklyFailureBasisV2
    remaining_domains: Annotated[
        tuple[WeeklyDomainSliceV2, ...], Field(min_length=1, max_length=21)
    ]
    numeric_bound: WeeklyNumericBoundV2 | None = None

    @model_validator(mode="after")
    def validate_forward_shape(self) -> Self:
        if self.scope.extent == "LEAF":
            raise ValueError("forward closure needs an unfinished completion space")
        if self.identity.strategy.propagation != "KNOWN_FAILURE_FORWARD_CHECK":
            raise ValueError("forward closure is not declared by the selected strategy")
        assigned = {c.slot.canonical_index for c in self.scope.path}
        if tuple(d.slot.canonical_index for d in self.remaining_domains) != tuple(
            i for i in range(21) if i not in assigned
        ):
            raise ValueError("forward inputs must explicitly name every remaining slot domain")
        return self


class WeeklyCompletedLeafV2(_EventV2):
    kind: Literal["COMPLETED_LEAF"] = "COMPLETED_LEAF"
    declared_status: RuleStatus
    obligations: _Obligations
    evaluation_digest: _ContentDigest
    semantic_validation: Literal["DEFERRED"] = "DEFERRED"

    @model_validator(mode="after")
    def validate_leaf_shape(self) -> Self:
        if self.scope.extent != "LEAF":
            raise ValueError("completed leaf requires all 21 explicit choices")
        return self


WeeklyInterruptionV2 = Literal[
    "NODE_BUDGET",
    "PREPARATION_BUDGET",
    "PREDICATE_BUDGET",
    "DAY_BUDGET",
    "WEEK_BUDGET",
    "HEURISTIC_BUDGET",
    "VERIFICATION_BUDGET",
    "PROOF_RECORD_BUDGET",
    "PROOF_BYTE_BUDGET",
    "DEADLINE",
]


class WeeklyResourceInterruptionV2(_EventV2):
    kind: Literal["RESOURCE_INTERRUPTION"] = "RESOURCE_INTERRUPTION"
    reason: WeeklyInterruptionV2
    checkpoint: _Checkpoint
    deadline_checkpoint: _Checkpoint | None = None

    @model_validator(mode="after")
    def validate_checkpoint(self) -> Self:
        if self.checkpoint > self.accounting.checkpoints:
            raise ValueError("interruption checkpoint exceeds declared accounting")
        if (self.reason == "DEADLINE") != (self.deadline_checkpoint is not None):
            raise ValueError("deadline interruption requires its explicit checkpoint only")
        if self.deadline_checkpoint is not None and self.deadline_checkpoint != self.checkpoint:
            raise ValueError("deadline checkpoint must identify this interruption checkpoint")
        return self


class WeeklyBranchExhaustionV2(_EventV2):
    kind: Literal["BRANCH_EXHAUSTION"] = "BRANCH_EXHAUSTION"
    child_branch_ids: Annotated[tuple[_OpaqueId, ...], Field(max_length=50)]
    completeness: Literal["NOT_VERIFIED"] = "NOT_VERIFIED"

    @model_validator(mode="after")
    def validate_children(self) -> Self:
        if (
            len(set(self.child_branch_ids)) != len(self.child_branch_ids)
            or self.scope.branch_id in self.child_branch_ids
        ):
            raise ValueError("branch exhaustion requires distinct non-self child references")
        return self


WeeklyProofEventV2 = Annotated[
    Annotated[WeeklyVariableSelectionV2, Tag("VARIABLE_SELECTION")]
    | Annotated[WeeklyValueSelectionV2, Tag("VALUE_SELECTION")]
    | Annotated[WeeklyUnaryFailureV2, Tag("UNARY_FAILURE")]
    | Annotated[WeeklyDayFailureV2, Tag("DAY_FAILURE")]
    | Annotated[WeeklyWeekFailureV2, Tag("WEEK_FAILURE")]
    | Annotated[WeeklyForwardCheckClosureV2, Tag("FORWARD_CHECK_CLOSURE")]
    | Annotated[WeeklyCompletedLeafV2, Tag("COMPLETED_LEAF")]
    | Annotated[WeeklyResourceInterruptionV2, Tag("RESOURCE_INTERRUPTION")]
    | Annotated[WeeklyBranchExhaustionV2, Tag("BRANCH_EXHAUSTION")],
    Discriminator(_declared_kind),
]


class WeeklyFrontierStateV2(StrEnum):
    EXPLORED = "EXPLORED"
    EXCLUSION_DECLARED = "EXCLUSION_DECLARED"
    UNRESOLVED_UNKNOWN = "UNRESOLVED_UNKNOWN"
    UNEXPLORED = "UNEXPLORED"


class WeeklyFrontierBranchV2(_V2Model):
    scope: WeeklyBranchScopeV2
    state: WeeklyFrontierStateV2
    supporting_event: _EventIndex | None = None
    unresolved_obligations: Annotated[tuple[WeeklyObligationV2, ...], Field(max_length=256)] = ()
    semantic_coverage: Literal["NOT_VERIFIED"] = "NOT_VERIFIED"

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if (
            self.state in (WeeklyFrontierStateV2.EXPLORED, WeeklyFrontierStateV2.EXCLUSION_DECLARED)
            and self.supporting_event is None
        ):
            raise ValueError("explored/exclusion declaration requires a supporting event")
        if (self.state is WeeklyFrontierStateV2.UNRESOLVED_UNKNOWN) != bool(
            self.unresolved_obligations
        ):
            raise ValueError("only unresolved UNKNOWN branches carry missing obligations")
        return self


class WeeklySearchCertificateV2(_V2Model):
    """Structural transcript only. Empty frontier/caller hashes cannot authorize a verdict."""

    schema_version: Literal["weekly-coverage.v2"] = "weekly-coverage.v2"
    proof_policy_version: Literal[
        "synthetic-weekly-coverage-declarations.v2", "synthetic-weekly-ordered-coverage.v2"
    ] = "synthetic-weekly-coverage-declarations.v2"
    verification_state: Literal["NOT_VERIFIED"] = "NOT_VERIFIED"
    semantic_validation: Literal["DEFERRED_TO_PHASE_7_2A"] = "DEFERRED_TO_PHASE_7_2A"
    outcome: None = None
    exhaustive: Literal[False] = False
    request: WeeklyPlanningRequest
    identity: WeeklySearchIdentityV2
    rule_obligations: Annotated[tuple[WeeklyRuleObligationV2, ...], Field(max_length=256)]
    original_domains: Annotated[
        tuple[WeeklyOriginalDomainV2, ...], Field(min_length=21, max_length=21)
    ]
    limits: WeeklySearchLimitsV2
    events: Annotated[tuple[WeeklyProofEventV2, ...], Field(max_length=1024)] = ()
    frontier: Annotated[tuple[WeeklyFrontierBranchV2, ...], Field(max_length=512)] = ()
    accounting: WeeklyAccountingV2 = WeeklyAccountingV2()

    @model_validator(mode="after")
    def validate_declaration_bindings(self) -> Self:
        self._validate_identity()
        rule_ids = tuple(o.rule.rule_id for o in self.rule_obligations)
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("duplicate or conflicting declared rule identities/versions/scopes")
        if tuple(d.slot.canonical_index for d in self.original_domains) != tuple(range(21)):
            raise ValueError("original domains must include every canonical slot exactly once")
        for day in self.request.days:
            for domain in day.domains:
                i = (day.day.day_index - 1) * 3 + tuple(MealSlot).index(domain.slot)
                declared = self.original_domains[i]
                if declared.slot.day != day.day or declared.options != tuple(
                    sorted(domain.options, key=lambda option: option.option_id)
                ):
                    raise ValueError(
                        "original domain differs from exact request day/source/options"
                    )
        scopes: dict[str, WeeklyBranchScopeV2] = {}
        for i, event in enumerate(self.events):
            if event.sequence != i or event.identity != self.identity:
                raise ValueError(
                    "event sequence or request/manifest/source/context/strategy binding differs"
                )
            self._validate_scope(event.scope)
            self._record_scope(scopes, event.scope)
            self._validate_accounting(event.accounting)
            if i:
                self._validate_cumulative(self.events[i - 1].accounting, event.accounting)
            if isinstance(event, WeeklyVariableSelectionV2):
                self._validate_slot(event.selected_slot)
                if (
                    self.identity.strategy.variable_order == "CHRONOLOGICAL"
                    and event.selected_slot.canonical_index != event.depth
                ):
                    raise ValueError("chronological selection must name the next canonical slot")
            if isinstance(event, WeeklyForwardCheckClosureV2):
                for domain in event.remaining_domains:
                    self._validate_slot(domain.slot)
                    if any(
                        j >= len(self.original_domains[domain.slot.canonical_index].options)
                        for j in domain.original_domain_indexes
                    ):
                        raise ValueError("forward slice index is outside its original domain")
            if (
                isinstance(event, WeeklyResourceInterruptionV2)
                and event.reason == "DEADLINE"
                and self.limits.deadline is None
            ):
                raise ValueError("deadline interruption requires a declared deadline")
            obligations = (
                event.basis.obligations
                if isinstance(
                    event,
                    (
                        WeeklyUnaryFailureV2,
                        WeeklyDayFailureV2,
                        WeeklyWeekFailureV2,
                        WeeklyForwardCheckClosureV2,
                    ),
                )
                else event.obligations
                if isinstance(event, WeeklyCompletedLeafV2)
                else ()
            )
            self._validate_obligations(obligations)
        branch_keys = set()
        for branch in self.frontier:
            self._validate_scope(branch.scope)
            self._record_scope(scopes, branch.scope)
            key = (
                branch.scope.extent,
                tuple(
                    sorted(
                        (c.slot.canonical_index, c.original_domain_index) for c in branch.scope.path
                    )
                ),
                branch.scope.decision_slot.canonical_index if branch.scope.decision_slot else None,
                branch.scope.original_domain_indexes,
            )
            if key in branch_keys:
                raise ValueError("duplicate frontier completion-space declaration")
            branch_keys.add(key)
            self._validate_obligations(branch.unresolved_obligations)
            if branch.supporting_event is not None:
                if branch.supporting_event >= len(self.events):
                    raise ValueError("frontier points to a missing event")
                supporting = self.events[branch.supporting_event]
                if branch.state is WeeklyFrontierStateV2.EXCLUSION_DECLARED:
                    if not isinstance(
                        supporting,
                        (
                            WeeklyUnaryFailureV2,
                            WeeklyDayFailureV2,
                            WeeklyWeekFailureV2,
                            WeeklyForwardCheckClosureV2,
                        ),
                    ):
                        raise ValueError("exclusion must reference a declared known-failure event")
                elif branch.state is WeeklyFrontierStateV2.EXPLORED:
                    if not isinstance(supporting, WeeklyCompletedLeafV2):
                        raise ValueError(
                            "explored branch must reference a completed-leaf declaration"
                        )
                elif branch.state is WeeklyFrontierStateV2.UNRESOLVED_UNKNOWN:
                    if (
                        not isinstance(supporting, WeeklyCompletedLeafV2)
                        or supporting.declared_status is not RuleStatus.UNKNOWN
                    ):
                        raise ValueError("unknown branch cannot be supported by a resolved leaf")
                elif not isinstance(supporting, WeeklyResourceInterruptionV2):
                    raise ValueError("interrupted unexplored branch must reference interruption")
                if (
                    branch.state is not WeeklyFrontierStateV2.UNEXPLORED
                    and supporting.scope != branch.scope
                ):
                    raise ValueError("frontier branch differs from its supporting event scope")
        for event in self.events:
            if isinstance(event, WeeklyBranchExhaustionV2) and any(
                child not in scopes for child in event.child_branch_ids
            ):
                raise ValueError("branch exhaustion references an undeclared child scope")
        self._validate_branch_graph()
        self._validate_accounting(self.accounting)
        if self.events:
            # Execution can roll back or stop between records. The computed v2
            # checker, not this declaration, establishes exact final charges.
            try:
                self._validate_cumulative(self.events[-1].accounting, self.accounting)
            except ValueError as error:
                raise ValueError(
                    "summary accounting precedes the final event declaration"
                ) from error
        if len(self.model_dump_json(by_alias=True).encode("utf-8")) > STRICT_JSON_MAX_BYTES:
            raise ValueError("v2 declaration exceeds the 1 MiB encoded structural ceiling")
        return self

    def _validate_identity(self) -> None:
        request, identity = self.request, self.identity
        context = request.source.daily_source.context
        if (
            identity.request_id,
            identity.request_version,
            identity.request_digest,
            identity.source,
            identity.daily_source,
            identity.context_id,
            identity.context_version,
            identity.context_digest,
            identity.profile_id,
            identity.profile_version,
            identity.kb_id,
            identity.kb_version,
            identity.kb_digest,
        ) != (
            request.request_id,
            request.version,
            request.content_digest,
            request.expected_source,
            request.source.expected_daily_source,
            context.context_id,
            context.version,
            context.content_digest,
            context.profile_id,
            context.profile_version,
            context.expected_kb_id,
            context.expected_kb_version,
            context.expected_kb_digest,
        ):
            raise ValueError(
                "declaration identity differs from retained request/source/context/KB pins"
            )

    def _validate_slot(self, slot: WeeklySlotIdentityV2) -> None:
        if slot != self.original_domains[slot.canonical_index].slot:
            raise ValueError("event slot is transplanted from another day/week/request")

    def _validate_scope(self, scope: WeeklyBranchScopeV2) -> None:
        for choice in scope.path:
            self._validate_slot(choice.slot)
            domain = self.original_domains[choice.slot.canonical_index]
            if (
                choice.original_domain_index >= len(domain.options)
                or choice.option != domain.options[choice.original_domain_index]
            ):
                raise ValueError(
                    "selected option/index differs from exact original domain/configuration"
                )
        if self.identity.strategy.variable_order == "CHRONOLOGICAL" and tuple(
            c.slot.canonical_index for c in scope.path
        ) != tuple(range(len(scope.path))):
            raise ValueError("chronological path differs from explicit canonical slot order")
        if scope.decision_slot is not None:
            self._validate_slot(scope.decision_slot)
            if any(
                i >= len(self.original_domains[scope.decision_slot.canonical_index].options)
                for i in scope.original_domain_indexes
            ):
                raise ValueError("excluded original-domain position is outside the actual domain")

    def _validate_obligations(self, obligations: tuple[WeeklyObligationV2, ...]) -> None:
        for obligation in obligations:
            if (
                isinstance(obligation, WeeklyRuleObligationV2)
                and obligation not in self.rule_obligations
            ):
                raise ValueError("event names a foreign/rewritten declared rule obligation")

    def _validate_accounting(self, accounting: WeeklyAccountingV2) -> None:
        if (
            accounting.logical_nodes > self.limits.max_nodes
            or accounting.proof_records_reserved > self.limits.max_proof_records
            or accounting.proof_bytes_reserved > self.limits.max_proof_bytes
            or accounting.cache_capacity > self.limits.max_cache_entries
        ):
            raise ValueError("declared accounting exceeds declared resource limits")
        if any(
            getattr(accounting.reserved_work, field) > getattr(self.limits.max_reserved_work, field)
            for field in WeeklyWorkV2.model_fields
        ):
            raise ValueError("declared work reservation exceeds its limit")

    @staticmethod
    def _record_scope(scopes: dict[str, WeeklyBranchScopeV2], scope: WeeklyBranchScopeV2) -> None:
        if scope.branch_id in scopes and scopes[scope.branch_id] != scope:
            raise ValueError("one branch identity has conflicting scope declarations")
        scopes[scope.branch_id] = scope

    def _validate_branch_graph(self) -> None:
        # Reference-graph well-formedness only; this does not verify that children
        # partition their parent or that any branch has actually been exhausted.
        edges: dict[str, tuple[str, ...]] = {}
        for event in self.events:
            if isinstance(event, WeeklyBranchExhaustionV2):
                prior = edges.get(event.scope.branch_id)
                if prior is not None and prior != event.child_branch_ids:
                    raise ValueError("conflicting branch child declarations")
                edges[event.scope.branch_id] = event.child_branch_ids
        incoming = {node: 0 for node in edges}
        for children in edges.values():
            for child in children:
                incoming[child] = incoming.get(child, 0) + 1
        ready = [node for node, count in incoming.items() if not count]
        visited = 0
        while ready:
            node = ready.pop()
            visited += 1
            for child in edges.get(node, ()):
                incoming[child] -= 1
                if not incoming[child]:
                    ready.append(child)
        if visited != len(incoming):
            raise ValueError("cyclic branch reference declaration")

    @staticmethod
    def _validate_cumulative(before: WeeklyAccountingV2, after: WeeklyAccountingV2) -> None:
        counters = (
            "logical_nodes",
            "backtracks",
            "proof_records_reserved",
            "proof_records_written",
            "proof_bytes_reserved",
            "proof_bytes_written",
            "checkpoints",
            "cache_hits",
            "cache_evictions",
        )
        if any(getattr(after, field) < getattr(before, field) for field in counters):
            raise ValueError("cumulative accounting counters cannot decrease")
        for stage in ("execution_work", "verification_work", "reserved_work"):
            if any(
                getattr(getattr(after, stage), field) < getattr(getattr(before, stage), field)
                for field in WeeklyWorkV2.model_fields
            ):
                raise ValueError("cumulative work declarations cannot decrease")
