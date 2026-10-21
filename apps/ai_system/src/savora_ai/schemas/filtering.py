"""Phase 3 synthetic policy and manifest declarations; no production authority."""

from types import MappingProxyType
from typing import Literal, NamedTuple, Self

from pydantic import model_validator

from savora_ai.schemas.candidates import (
    FactSubjectKind,
    IngredientCoverage,
    MeasurementBasis,
    RuleContext,
    VersionedFact,
    _content_digest,
    _require_evidence,
    _validate_provenance,
)
from savora_ai.schemas.food_graph import (
    FoodRelationType,
    RelationQualifiers,
    RelationResolution,
    RelationResolutionStatus,
    TaxonomyKind,
    TaxonomyResolution,
    TaxonomyTraversalMode,
    TraversalMode,
    _OpaqueId,
)
from savora_ai.schemas.knowledge import (
    ApprovalStatus,
    EvidenceReference,
    MeasurementUnit,
    PredicateOperator,
    RuleDefinition,
    RuleDomain,
    RuleEnvironment,
    RuleLifecycle,
    RuleScope,
    RuleSeverity,
    _ContractModel,
    _NonBlank,
    _require_canonical_enum,
)
from savora_ai.schemas.knowledge_base import KnowledgeWorkflow, _ContentDigest
from savora_ai.schemas.reasoning import (
    FactObservation,
    RuleEvaluation,
    RuleStatus,
    RuleTrace,
    aggregate_hard_status,
    is_candidate_eligible,
)
from savora_ai.schemas.workflow_policy import WorkflowPolicyVersion


class _AttributePolicy(NamedTuple):
    kind: Literal["numeric", "boolean", "categorical"]
    subject: FactSubjectKind
    unit: MeasurementUnit | None = None
    basis: MeasurementBasis | None = None
    basis_identity: tuple[str, str] | None = None


# Application configuration, never supplied by callers or inferred from food names.
_SCALAR_ATTRIBUTES = MappingProxyType(
    {
        "synthetic_quantity": _AttributePolicy(
            "numeric",
            FactSubjectKind.RECIPE,
            MeasurementUnit.MG,
            MeasurementBasis.PER_100_G,
            ("synthetic-per-100-g", "1"),
        ),
        "synthetic_serving_quantity": _AttributePolicy(
            "numeric",
            FactSubjectKind.RECIPE,
            MeasurementUnit.MG,
            MeasurementBasis.PER_SERVING,
            ("synthetic-serving", "1"),
        ),
        "synthetic_ratio": _AttributePolicy(
            "numeric",
            FactSubjectKind.RECIPE,
            MeasurementUnit.DIMENSIONLESS,
            MeasurementBasis.AS_RECORDED,
            ("synthetic-recorded", "1"),
        ),
        "synthetic_flag": _AttributePolicy("boolean", FactSubjectKind.RECIPE),
        "synthetic_category": _AttributePolicy("categorical", FactSubjectKind.RECIPE),
        "synthetic_profile_flag": _AttributePolicy("boolean", FactSubjectKind.PROFILE),
        "synthetic_context_enabled": _AttributePolicy("boolean", FactSubjectKind.CONTEXT),
        "synthetic_context_guard": _AttributePolicy("boolean", FactSubjectKind.CONTEXT),
        "synthetic_profile_enabled": _AttributePolicy("boolean", FactSubjectKind.PROFILE),
    }
)
# v1 scalar semantics are retained. These v2 additions are resolved internally,
# never taken as authoritative caller observations.
_DERIVED_ATTRIBUTES = frozenset(
    {
        "synthetic_contains_target",
        "synthetic_origin_target",
        "synthetic_dietary_target",
        "synthetic_cuisine_target",
        "synthetic_dinner_compatible",
        "synthetic_allergen_absent",
        "synthetic_clinically_safe",
    }
)
_ATTRIBUTES = MappingProxyType(
    dict(_SCALAR_ATTRIBUTES)
    | {name: _AttributePolicy("boolean", FactSubjectKind.RECIPE) for name in _DERIVED_ATTRIBUTES}
)
_APPLICABILITY = MappingProxyType(
    {
        ("synthetic-context-enabled", "1"): "synthetic_context_enabled",
        ("synthetic-context-guard", "1"): "synthetic_context_guard",
        ("synthetic-profile-enabled", "1"): "synthetic_profile_enabled",
    }
)


class _CombinationAttributePolicy(NamedTuple):
    scope: RuleScope
    domain: RuleDomain
    kind: Literal["boolean"]
    operators: tuple[PredicateOperator, ...]
    unit: None
    applicability: tuple[str, str]


# Separate ownership: never insert these names into the recipe fact adapters.
_COMBINATION_ATTRIBUTES = MappingProxyType(
    {
        name: _CombinationAttributePolicy(
            RuleScope.COMBINATION,
            RuleDomain.CULINARY,
            "boolean",
            (PredicateOperator.EQ, PredicateOperator.NE),
            None,
            ("synthetic-context-enabled", "1"),
        )
        for name in (
            "synthetic_combination_roles_compatible",
            "synthetic_combination_composition_complete",
        )
    }
)


def _validate_combination_rule_policy(rule: RuleDefinition) -> None:
    policy = _COMBINATION_ATTRIBUTES.get(rule.attribute)
    if policy is None:
        raise ValueError("combination-owned prerequisites require a combination predicate")
    if (
        rule.scope is not policy.scope
        or rule.domain is not policy.domain
        or type(rule.value) is not bool
        or rule.operator not in policy.operators
        or rule.unit is not policy.unit
        or (rule.applicability_reference.rule_id, rule.applicability_reference.version)
        != policy.applicability
    ):
        raise ValueError("unsupported combination scope/domain/predicate/unit/applicability")
    for name in rule.required_facts:
        if name in _COMBINATION_ATTRIBUTES:
            continue
        prerequisite = _ATTRIBUTES.get(name)
        if prerequisite is None or prerequisite.subject not in (
            FactSubjectKind.PROFILE,
            FactSubjectKind.CONTEXT,
        ):
            raise ValueError("unsupported combination required attribute or recipe-owned fact")


_DAY_MAX_TOTAL = 2**63 - 1  # Representation/resource bound, never a nutritional threshold.
_DAY_ATTRIBUTES = MappingProxyType(
    {"synthetic_day_complete": None, "synthetic_day_quantity_total": MeasurementUnit.MG}
)


def _validate_day_rule_policy(rule: RuleDefinition) -> None:
    """Admit only the two application-owned, synthetic DAY predicates; execute neither."""
    if (
        rule.attribute not in _DAY_ATTRIBUTES
        or rule.scope is not RuleScope.DAY
        or rule.domain is not RuleDomain.CULINARY
        or rule.environment is not RuleEnvironment.SYNTHETIC
        or rule.lifecycle is not RuleLifecycle.ACTIVE
        or rule.severity is not RuleSeverity.ABSOLUTE
        or rule.approval_status is not ApprovalStatus.APPROVED
        or rule.unit is not _DAY_ATTRIBUTES.get(rule.attribute)
        or (rule.applicability_reference.rule_id, rule.applicability_reference.version)
        != ("synthetic-context-enabled", "1")
    ):
        raise ValueError("unsupported DAY scope/domain/unit/applicability or admission metadata")
    numeric = rule.attribute == "synthetic_day_quantity_total"
    operators = (
        (
            PredicateOperator.LT,
            PredicateOperator.LE,
            PredicateOperator.GT,
            PredicateOperator.GE,
            PredicateOperator.EQ,
            PredicateOperator.NE,
        )
        if numeric
        else (PredicateOperator.EQ, PredicateOperator.NE)
    )
    valid_value = (
        type(rule.value) is int and 0 <= rule.value <= _DAY_MAX_TOTAL
        if numeric
        else type(rule.value) is bool
    )
    if rule.operator not in operators or not valid_value:
        raise ValueError("unsupported DAY predicate/value")
    for name in rule.required_facts:
        if name in _DAY_ATTRIBUTES:
            continue
        policy = _ATTRIBUTES.get(name)
        if policy is None or policy.subject not in (
            FactSubjectKind.PROFILE,
            FactSubjectKind.CONTEXT,
        ):
            raise ValueError("unsupported DAY prerequisite or non-DAY food ownership")


_WEEK_MAX_TOTAL = 64_563_604_257_983_430_642
_WEEK_ATTRIBUTES = MappingProxyType(
    {
        "synthetic_week_complete": None,
        "synthetic_week_quantity_total": MeasurementUnit.MG,
        "synthetic_week_max_recipe_slot_occurrences": MeasurementUnit.DIMENSIONLESS,
    }
)


def _validate_week_rule_policy(rule: RuleDefinition) -> None:
    """Admit synthetic WEEK ownership only; never derive facts or execute predicates."""
    if (
        rule.attribute not in _WEEK_ATTRIBUTES
        or rule.scope is not RuleScope.WEEK
        or rule.domain is not RuleDomain.CULINARY
        or rule.environment is not RuleEnvironment.SYNTHETIC
        or rule.lifecycle is not RuleLifecycle.ACTIVE
        or rule.severity is not RuleSeverity.ABSOLUTE
        or rule.approval_status is not ApprovalStatus.APPROVED
        or rule.unit is not _WEEK_ATTRIBUTES.get(rule.attribute)
        or (rule.applicability_reference.rule_id, rule.applicability_reference.version)
        != ("synthetic-context-enabled", "1")
    ):
        raise ValueError("unsupported WEEK scope/domain/unit/applicability or admission metadata")
    numeric = rule.attribute != "synthetic_week_complete"
    operators = (
        (
            PredicateOperator.LT,
            PredicateOperator.LE,
            PredicateOperator.GT,
            PredicateOperator.GE,
            PredicateOperator.EQ,
            PredicateOperator.NE,
        )
        if numeric
        else (PredicateOperator.EQ, PredicateOperator.NE)
    )
    maximum = _WEEK_MAX_TOTAL if rule.attribute == "synthetic_week_quantity_total" else 21
    valid_value = (
        type(rule.value) is int and 0 <= rule.value <= maximum
        if numeric
        else type(rule.value) is bool
    )
    if rule.operator not in operators or not valid_value:
        raise ValueError("unsupported WEEK predicate/value")
    for name in rule.required_facts:
        if name in _WEEK_ATTRIBUTES:
            continue
        policy = _ATTRIBUTES.get(name)
        if policy is None or policy.subject not in (
            FactSubjectKind.PROFILE,
            FactSubjectKind.CONTEXT,
        ):
            raise ValueError("unsupported WEEK prerequisite or non-WEEK food ownership")


class _ManifestContent(_ContractModel):
    schema_version: Literal["expected-check-manifest.v1"] = "expected-check-manifest.v1"
    stage: Literal["RECIPE_FILTER"] = "RECIPE_FILTER"
    workflow_policy_version: WorkflowPolicyVersion = "synthetic-workflow-scopes.v1"
    admission_policy_version: Literal["synthetic-hard-rule-admission.v1"] = (
        "synthetic-hard-rule-admission.v1"
    )
    evaluator_policy_version: Literal["synthetic-rule-evaluation.v1"] = (
        "synthetic-rule-evaluation.v1"
    )
    attribute_policy_version: Literal[
        "synthetic-attributes.v1",
        "synthetic-attributes.v2",
        "synthetic-attributes.v3-combination",
        "synthetic-attributes.v4-day",
        "synthetic-attributes.v5-week",
    ] = "synthetic-attributes.v1"
    identity_policy_version: Literal["synthetic-manifest-identity.v1"] = (
        "synthetic-manifest-identity.v1"
    )
    kb_id: _OpaqueId
    kb_version: _NonBlank
    kb_digest: _ContentDigest
    graph_id: _OpaqueId
    graph_version: _NonBlank
    taxonomy_version: _NonBlank | None
    catalogue_version: _NonBlank
    check_catalogue_version: _NonBlank
    workflow: KnowledgeWorkflow
    candidate_id: _OpaqueId
    candidate_version: _NonBlank
    candidate_snapshot_id: _OpaqueId
    candidate_snapshot_version: _NonBlank
    candidate_digest: _ContentDigest
    context_id: _OpaqueId
    context_version: _NonBlank
    context_digest: _ContentDigest
    profile_id: _OpaqueId
    profile_version: _NonBlank
    required_checks: tuple[RuleDefinition, ...]
    deferred_checks: tuple[RuleDefinition, ...]

    @model_validator(mode="after")
    def validate_checks(self) -> Self:
        _require_canonical_enum(self.workflow)
        seen: set[str] = set()
        has_combination_attributes = False
        has_day_attributes = False
        has_week_attributes = False
        for deferred, checks in ((False, self.required_checks), (True, self.deferred_checks)):
            for rule in checks:
                if rule.rule_id in seen:
                    raise ValueError("duplicate manifest rule identity")
                seen.add(rule.rule_id)
                if (
                    rule.lifecycle is not RuleLifecycle.ACTIVE
                    or rule.severity is not RuleSeverity.ABSOLUTE
                    or rule.approval_status is not ApprovalStatus.APPROVED
                ):
                    raise ValueError("Phase 3 mandatory hard rules must be ACTIVE and APPROVED")
                if deferred != (rule.scope not in (RuleScope.PROFILE, RuleScope.RECIPE)):
                    raise ValueError("fixed recipe-filter scope partition mismatch")
                if any(name in _COMBINATION_ATTRIBUTES for name in rule.required_facts):
                    has_combination_attributes = True
                    _validate_combination_rule_policy(rule)
                if any(name in _DAY_ATTRIBUTES for name in rule.required_facts):
                    has_day_attributes = True
                    _validate_day_rule_policy(rule)
                if any(name in _WEEK_ATTRIBUTES for name in rule.required_facts):
                    has_week_attributes = True
                    _validate_week_rule_policy(rule)
        if has_week_attributes:
            if self.attribute_policy_version != "synthetic-attributes.v5-week":
                raise ValueError("WEEK attributes require their exact scope-aware policy version")
        elif self.attribute_policy_version == "synthetic-attributes.v5-week":
            raise ValueError("WEEK policy version requires WEEK-owned attributes")
        elif has_day_attributes:
            if self.attribute_policy_version != "synthetic-attributes.v4-day":
                raise ValueError("DAY attributes require their exact scope-aware policy version")
        elif self.attribute_policy_version == "synthetic-attributes.v4-day":
            raise ValueError("DAY policy version requires DAY-owned attributes")
        elif has_combination_attributes != (
            self.attribute_policy_version == "synthetic-attributes.v3-combination"
        ):
            raise ValueError(
                "combination attributes require their exact scope-aware policy version"
            )
        if self.workflow is KnowledgeWorkflow.CRAVING_DISCOVERY and self.deferred_checks:
            raise ValueError("standalone craving cannot carry later-scope obligations")
        return self


class ExpectedCheckManifest(_ManifestContent):
    """Integrity-bound declaration; consumers must rebuild against the accepted KB."""

    manifest_id: _NonBlank
    manifest_version: _NonBlank
    content_digest: _ContentDigest

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        body = _ManifestContent.model_validate(
            {
                key: value
                for key, value in vars(self).items()
                if key not in ("manifest_id", "manifest_version", "content_digest")
            }
        )
        digest = _content_digest(body)
        if (
            self.content_digest != digest
            or self.manifest_id != "manifest-" + digest
            or self.manifest_version != "synthetic-manifest.v1:" + digest
        ):
            raise ValueError("manifest identity/version/digest mismatch")
        return self


def _record_evidence(value: object) -> tuple[EvidenceReference, ...]:
    """Inspect already validated records without sorting their ordered witness paths."""
    if isinstance(value, EvidenceReference):
        return (value,)
    if isinstance(value, _ContractModel):
        return tuple(ref for item in vars(value).values() for ref in _record_evidence(item))
    if isinstance(value, tuple):
        return tuple(ref for item in value for ref in _record_evidence(item))
    return ()


def _evidence_union(value: object) -> tuple[EvidenceReference, ...]:
    references = _record_evidence(value)
    _validate_provenance(references)
    indexed = {(ref.evidence_id, ref.version): ref for ref in references}
    return tuple(indexed[key] for key in sorted(indexed))


class ResolvedRuleFact(_ContractModel):
    fact: VersionedFact
    supplied_fact: VersionedFact | None = None
    source: Literal["SUPPLIED", "MISSING", "KB_RELATION", "KB_TAXONOMY", "UNSUPPORTED"]
    reason_code: _NonBlank
    relations: tuple[RelationResolution, ...] = ()
    taxonomy: TaxonomyResolution | None = None

    @model_validator(mode="after")
    def validate_fact(self) -> Self:
        if self.supplied_fact is not None and (
            self.supplied_fact.fact_id,
            self.supplied_fact.subject_kind,
            self.supplied_fact.subject_id,
            self.supplied_fact.subject_version,
        ) != (
            self.fact.fact_id,
            self.fact.subject_kind,
            self.fact.subject_id,
            self.fact.subject_version,
        ):
            raise ValueError("supplied/resolved fact identity mismatch")
        if self.source == "SUPPLIED" and self.fact != self.supplied_fact:
            raise ValueError("supplied fact must retain the exact declaration")
        if self.source in ("MISSING", "UNSUPPORTED") and self.fact.observation.value is not None:
            raise ValueError("missing/unsupported facts cannot declare a known value")
        self._validate_witness()
        _evidence_union(self)
        return self

    def _validate_witness(self) -> None:
        """Proof shape/meaning only; matching the records to an accepted KB is still external."""
        name = self.fact.fact_id
        value = self.fact.observation.value
        if self.source in ("SUPPLIED", "MISSING", "UNSUPPORTED"):
            if self.relations or self.taxonomy is not None:
                raise ValueError("non-KB fact sources cannot carry graph/taxonomy witnesses")
            if self.source == "SUPPLIED" and name in _DERIVED_ATTRIBUTES:
                raise ValueError("graph-backed facts cannot use caller-supplied authority")
            return
        if self.fact.subject_kind is not FactSubjectKind.RECIPE:
            raise ValueError("synthetic KB adapters require recipe-owned facts")
        if value is not None and (type(value) is not bool or not self.fact.observation.complete):
            raise ValueError("known KB facts require complete boolean observations")
        expected = (
            RelationResolutionStatus.SUPPORTED
            if value is True
            else RelationResolutionStatus.VERIFIED_ABSENT
        )
        if self.source == "KB_RELATION":
            configuration = {
                "synthetic_contains_target": (
                    FoodRelationType.CONTAINS,
                    TraversalMode.DIRECT,
                    RelationQualifiers(),
                ),
                "synthetic_origin_target": (
                    FoodRelationType.DERIVED_FROM,
                    TraversalMode.ORIGIN_PATH,
                    RelationQualifiers(),
                ),
                "synthetic_dinner_compatible": (
                    FoodRelationType.COMPATIBLE_WITH,
                    TraversalMode.DIRECT,
                    RelationQualifiers(meal_type="DINNER"),
                ),
            }.get(name)
            if configuration is None or self.taxonomy is not None:
                raise ValueError("unsupported relation fact/source configuration")
            if any(
                (record.relation_type, record.traversal, record.qualifiers) != configuration
                for record in self.relations
            ):
                raise ValueError("relation witness semantics differ from synthetic fact adapter")
            if value is not None and (
                not any(record.status is expected for record in self.relations)
                or (name == "synthetic_origin_target" and value is False)
            ):
                raise ValueError(
                    "known relation facts require matching exact assertions or origin witnesses"
                )
            if name != "synthetic_origin_target" and len(self.relations) > 1:
                raise ValueError("direct facts require a single exact query")
        else:
            configuration = {
                "synthetic_dietary_target": (
                    "synthetic-dietary",
                    TaxonomyKind.DIETARY_CATEGORY,
                    TaxonomyTraversalMode.DIRECT,
                ),
                "synthetic_cuisine_target": (
                    "synthetic-cuisine",
                    TaxonomyKind.CUISINE,
                    TaxonomyTraversalMode.CUISINE_PARENTS,
                ),
            }.get(name)
            taxonomy = self.taxonomy
            if configuration is None or self.relations:
                raise ValueError("unsupported taxonomy fact/source configuration")
            if taxonomy is not None and (taxonomy.term_id, taxonomy.traversal) != (
                configuration[0],
                configuration[2],
            ):
                raise ValueError("taxonomy query differs from synthetic fact adapter")
            if value is not None and (
                taxonomy is None
                or taxonomy.status is not expected
                or taxonomy.term is None
                or taxonomy.term.kind is not configuration[1]
            ):
                raise ValueError("known taxonomy facts require matching classification witnesses")
        witness_evidence = _evidence_union((self.relations, self.taxonomy))
        if not set(witness_evidence).issubset(self.fact.observation.evidence):
            raise ValueError("resolved fact evidence omits its graph/taxonomy provenance")


class CandidateFactResolution(_ContractModel):
    schema_version: Literal["candidate-fact-resolution.v1"] = "candidate-fact-resolution.v1"
    adapter_policy_version: Literal["synthetic-fact-adapters.v1"] = "synthetic-fact-adapters.v1"
    manifest: ExpectedCheckManifest
    ingredient_coverage: IngredientCoverage
    inventory_relations: tuple[RelationResolution, ...] = ()
    unresolved_line_ids: tuple[_OpaqueId, ...]
    facts: tuple[ResolvedRuleFact, ...]
    max_hops: Literal[8] = 8
    max_visited: Literal[256] = 256

    @model_validator(mode="after")
    def validate_binding(self) -> Self:
        manifest = self.manifest
        if (
            self.ingredient_coverage.recipe_id,
            self.ingredient_coverage.recipe_version,
            self.ingredient_coverage.catalogue_version,
        ) != (
            manifest.candidate_id,
            manifest.candidate_version,
            manifest.catalogue_version,
        ):
            raise ValueError("fact resolution ingredient release mismatch")
        names = tuple(item.fact.fact_id for item in self.facts)
        if names != tuple(sorted(set(names))):
            raise ValueError("resolved facts must have unique canonical ordered identities")
        if self.unresolved_line_ids != tuple(sorted(set(self.unresolved_line_ids))):
            raise ValueError("unresolved lines must be unique and ordered")
        for relation in self.inventory_relations:
            if (relation.graph_id, relation.graph_version, relation.catalogue_version) != (
                manifest.graph_id,
                manifest.graph_version,
                manifest.catalogue_version,
            ):
                raise ValueError("inventory relation release mismatch")
        for item in self.facts:
            fact = item.fact
            owner = {
                FactSubjectKind.RECIPE: (manifest.candidate_id, manifest.candidate_version),
                FactSubjectKind.PROFILE: (manifest.profile_id, manifest.profile_version),
                FactSubjectKind.CONTEXT: (manifest.context_id, manifest.context_version),
            }.get(fact.subject_kind)
            if owner != (fact.subject_id, fact.subject_version):
                raise ValueError("resolved fact owner/revision mismatch")
            food = fact.subject_kind is FactSubjectKind.RECIPE
            if fact.catalogue_version != (manifest.catalogue_version if food else None):
                raise ValueError("resolved fact catalogue mismatch")
            if fact.context_id is not None and (fact.context_id, fact.context_version) != (
                manifest.context_id,
                manifest.context_version,
            ):
                raise ValueError("resolved fact context mismatch")
            for relation in item.relations:
                if (relation.graph_id, relation.graph_version, relation.catalogue_version) != (
                    manifest.graph_id,
                    manifest.graph_version,
                    manifest.catalogue_version,
                ):
                    raise ValueError("resolved relation release mismatch")
            taxonomy = item.taxonomy
            if taxonomy is not None and (
                taxonomy.graph_id,
                taxonomy.graph_version,
                taxonomy.catalogue_version,
                taxonomy.taxonomy_version,
            ) != (
                manifest.graph_id,
                manifest.graph_version,
                manifest.catalogue_version,
                manifest.taxonomy_version,
            ):
                raise ValueError("resolved taxonomy release mismatch")
        _evidence_union(self)
        return self


class RuleExplanation(_ContractModel):
    schema_version: Literal["rule-explanation.v1"] = "rule-explanation.v1"
    policy_version: Literal["synthetic-rule-explanation.v1"] = "synthetic-rule-explanation.v1"
    manifest_id: _NonBlank
    manifest_version: _NonBlank
    manifest_digest: _ContentDigest
    candidate_id: _OpaqueId
    candidate_version: _NonBlank
    candidate_digest: _ContentDigest
    context_id: _OpaqueId
    context_version: _NonBlank
    context_digest: _ContentDigest
    kb_id: _OpaqueId
    kb_version: _NonBlank
    kb_digest: _ContentDigest
    evaluation: RuleEvaluation
    facts: tuple[ResolvedRuleFact, ...]
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_explanation(self) -> Self:
        _require_evidence(self.evidence)
        if tuple(item.fact.fact_id for item in self.facts) != tuple(
            sorted(self.evaluation.rule.required_facts)
        ):
            raise ValueError("explanation must include every required fact and gap")
        observations = tuple(
            FactObservation.model_validate(
                item.fact.observation.model_dump()
                | {
                    "evidence": _evidence_union(
                        (item.fact.observation.evidence, item.fact.basis_reference)
                    ),
                }
            )
            for item in self.facts
        )
        if self.evaluation.facts != observations:
            raise ValueError("explanation observations differ from evaluated facts")
        if self.evidence != _evidence_union((self.evaluation, self.facts)):
            raise ValueError("explanation evidence differs from evaluated facts and rule")
        return self


class CandidateFilterDecision(_ContractModel):
    resolution: CandidateFactResolution
    trace: RuleTrace
    status: RuleStatus
    explanations: tuple[RuleExplanation, ...]

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        _require_canonical_enum(self.status)
        manifest = self.resolution.manifest
        if (
            self.trace.candidate_id,
            self.trace.context_id,
            self.trace.manifest_id,
            self.trace.manifest_version,
            self.trace.required_checks,
        ) != (
            manifest.candidate_id,
            manifest.context_id,
            manifest.manifest_id,
            manifest.manifest_version,
            manifest.required_checks,
        ):
            raise ValueError("trace differs from bound manifest")
        if tuple(item.rule for item in self.trace.evaluations) != manifest.required_checks:
            raise ValueError("trace must evaluate every mandatory check exactly once in order")
        if self.status is not aggregate_hard_status(self.trace):
            raise ValueError("decision status differs from hard aggregation")
        if tuple(item.evaluation for item in self.explanations) != self.trace.evaluations:
            raise ValueError("explanations differ from complete evaluations")
        resolved = {item.fact.fact_id: item for item in self.resolution.facts}
        for explanation in self.explanations:
            for field in (
                "manifest_id",
                "manifest_version",
                "candidate_id",
                "candidate_version",
                "candidate_digest",
                "context_id",
                "context_version",
                "context_digest",
                "kb_id",
                "kb_version",
                "kb_digest",
            ):
                if getattr(explanation, field) != getattr(manifest, field):
                    raise ValueError("explanation binding differs from manifest")
            if explanation.manifest_digest != manifest.content_digest:
                raise ValueError("explanation manifest digest mismatch")
            if any(resolved.get(item.fact.fact_id) != item for item in explanation.facts):
                raise ValueError("explanation facts differ from resolution")
        _evidence_union(self)
        return self


class FilterCandidatesResult(_ContractModel):
    schema_version: Literal["filter-candidates-result.v1"] = "filter-candidates-result.v1"
    stage: Literal["RECIPE_FILTER"] = "RECIPE_FILTER"
    plan_feasibility: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    kb_id: _OpaqueId
    kb_version: _NonBlank
    kb_digest: _ContentDigest
    context: RuleContext
    decisions: tuple[CandidateFilterDecision, ...]
    eligible_ids: tuple[_OpaqueId, ...]
    excluded_ids: tuple[_OpaqueId, ...]

    @model_validator(mode="after")
    def validate_partition(self) -> Self:
        if (self.kb_id, self.kb_version, self.kb_digest) != (
            self.context.expected_kb_id,
            self.context.expected_kb_version,
            self.context.expected_kb_digest,
        ):
            raise ValueError("filter result shared KB/context binding mismatch")
        ids = tuple(item.resolution.manifest.candidate_id for item in self.decisions)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("candidate decisions must have unique canonical ordered IDs")
        for decision in self.decisions:
            manifest = decision.resolution.manifest
            if (
                manifest.kb_id,
                manifest.kb_version,
                manifest.kb_digest,
                manifest.context_id,
                manifest.context_version,
                manifest.context_digest,
                manifest.profile_id,
                manifest.profile_version,
                manifest.workflow,
            ) != (
                self.kb_id,
                self.kb_version,
                self.kb_digest,
                self.context.context_id,
                self.context.version,
                self.context.content_digest,
                self.context.profile_id,
                self.context.profile_version,
                self.context.workflow,
            ):
                raise ValueError("decision differs from shared filter context/release")
        expected_eligible = tuple(
            item.resolution.manifest.candidate_id
            for item in self.decisions
            if is_candidate_eligible(item.status)
        )
        expected_excluded = tuple(
            item.resolution.manifest.candidate_id
            for item in self.decisions
            if not is_candidate_eligible(item.status)
        )
        if self.eligible_ids != expected_eligible or self.excluded_ids != expected_excluded:
            raise ValueError("eligible/excluded partition differs from hard statuses")
        _evidence_union(self)
        return self
