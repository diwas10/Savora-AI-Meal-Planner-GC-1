"""Bound synthetic combination decisions; consumers must use the evaluation entrypoint."""

from typing import Literal, Self

from pydantic import model_validator

from savora_ai.schemas.candidates import RuleContext, _content_digest, _require_evidence
from savora_ai.schemas.combinations import CombinationFacts, PortionState
from savora_ai.schemas.filtering import (
    _COMBINATION_ATTRIBUTES,
    FilterCandidatesResult,
    _evidence_union,
    _validate_combination_rule_policy,
)
from savora_ai.schemas.food_graph import FoodEntity
from savora_ai.schemas.knowledge import (
    ApprovalStatus,
    EvidenceReference,
    PredicateOperator,
    RuleDefinition,
    RuleLifecycle,
    RuleScope,
    RuleSeverity,
    _ContractModel,
    _NonBlank,
    _require_canonical_enum,
)
from savora_ai.schemas.knowledge_base import _ContentDigest
from savora_ai.schemas.reasoning import (
    ApplicabilityStatus,
    FactObservation,
    RuleStatus,
    RuleTrace,
    aggregate_hard_status,
)

_PrerequisiteName = Literal[
    "CANDIDATE_MEMBERSHIP",
    "COMPOSITION_COMPLETENESS",
    "PORTION_CONFIGURATION",
    "ROLE_REFERENCES",
    "SOURCE_AUTHORITY",
]
_PREREQUISITES: tuple[_PrerequisiteName, ...] = (
    "CANDIDATE_MEMBERSHIP",
    "COMPOSITION_COMPLETENESS",
    "PORTION_CONFIGURATION",
    "ROLE_REFERENCES",
    "SOURCE_AUTHORITY",
)


def _prerequisite_statuses(
    combination: CombinationFacts,
    source: CombinationFacts | None,
    recipes: FilterCandidatesResult,
    accepted_roles: tuple[FoodEntity, ...],
) -> dict[_PrerequisiteName, RuleStatus | None]:
    """Bind prerequisites to retained records; performs no graph or predicate inference."""
    manifests = {
        item.resolution.manifest.candidate_id: item.resolution.manifest
        for item in recipes.decisions
    }
    ids = {part.recipe_snapshot.recipe_id for part in combination.components}
    if manifests.keys() - ids:
        raise ValueError("combination result contains unrelated recipe decisions")
    membership = RuleStatus.PASS
    for part in combination.components:
        ref = part.recipe_snapshot
        manifest = manifests.get(ref.recipe_id)
        if manifest is None:
            membership = RuleStatus.UNKNOWN
        elif (
            ref.recipe_id,
            ref.recipe_version,
            ref.snapshot_id,
            ref.snapshot_version,
            ref.content_digest,
            ref.catalogue_version,
        ) != (
            manifest.candidate_id,
            manifest.candidate_version,
            manifest.candidate_snapshot_id,
            manifest.candidate_snapshot_version,
            manifest.candidate_digest,
            manifest.catalogue_version,
        ):
            raise ValueError("component reference differs from exact accepted candidate snapshot")
    roles = {role.entity_id: role for role in accepted_roles}
    if tuple(role.entity_id for role in accepted_roles) != tuple(sorted(roles)):
        raise ValueError("accepted role records require unique canonical ordered identities")
    required_roles = {
        role.entity_id: role for part in combination.components for role in part.role_references
    }
    if roles.keys() - required_roles.keys() or any(
        roles[id_] != required_roles[id_] for id_ in roles
    ):
        raise ValueError("component role reference differs from accepted graph entity")
    authority = RuleStatus.PASS if source is not None else RuleStatus.UNKNOWN
    return {
        "CANDIDATE_MEMBERSHIP": membership,
        "SOURCE_AUTHORITY": authority,
        "COMPOSITION_COMPLETENESS": (
            RuleStatus.PASS
            if source is not None and source.composition_complete
            else RuleStatus.UNKNOWN
        ),
        "PORTION_CONFIGURATION": (
            None if combination.portion_state is PortionState.UNASSIGNED else authority
        ),
        "ROLE_REFERENCES": RuleStatus.PASS
        if roles.keys() == required_roles.keys()
        else RuleStatus.UNKNOWN,
    }


def _combine_statuses(statuses: tuple[RuleStatus, ...]) -> RuleStatus:
    if RuleStatus.FAIL in statuses:
        return RuleStatus.FAIL
    if not statuses or RuleStatus.UNKNOWN in statuses:
        return RuleStatus.UNKNOWN
    return RuleStatus.PASS


class CombinationPrerequisite(_ContractModel):
    name: _PrerequisiteName
    status: RuleStatus | None
    reason: _NonBlank
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        if self.status is not None:
            _require_canonical_enum(self.status)
        elif self.name != "PORTION_CONFIGURATION":
            raise ValueError("only unassigned portions can be explicitly unevaluated")
        _require_evidence(self.evidence)
        return self


class _CombinationManifestContent(_ContractModel):
    schema_version: Literal["combination-check-manifest.v1"] = "combination-check-manifest.v1"
    combination: CombinationFacts
    trusted_combination: CombinationFacts | None
    context: RuleContext
    recipe_manifest_digests: tuple[_ContentDigest, ...]
    accepted_role_references: tuple[FoodEntity, ...]
    required_checks: tuple[RuleDefinition, ...]
    deferred_checks: tuple[RuleDefinition, ...]


def _combination_manifest(
    combination: CombinationFacts,
    trusted_combination: CombinationFacts | None,
    recipes: FilterCandidatesResult,
    checks: tuple[RuleDefinition, ...],
    deferred: tuple[RuleDefinition, ...],
    accepted_roles: tuple[FoodEntity, ...],
) -> _CombinationManifestContent:
    # Only unordered declarations and digest references, never ordered graph witnesses.
    return _CombinationManifestContent(
        combination=combination,
        trusted_combination=trusted_combination,
        context=recipes.context,
        recipe_manifest_digests=tuple(
            decision.resolution.manifest.content_digest for decision in recipes.decisions
        ),
        accepted_role_references=accepted_roles,
        required_checks=checks,
        deferred_checks=deferred,
    )


class CombinationEligibilityResult(_ContractModel):
    schema_version: Literal["combination-eligibility-result.v1"] = (
        "combination-eligibility-result.v1"
    )
    stage: Literal["COMBINATION"] = "COMBINATION"
    plan_feasibility: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    combination: CombinationFacts
    trusted_combination: CombinationFacts | None
    recipes: FilterCandidatesResult
    accepted_role_references: tuple[FoodEntity, ...]
    prerequisites: tuple[CombinationPrerequisite, ...]
    trace: RuleTrace
    deferred_checks: tuple[RuleDefinition, ...]
    status: RuleStatus
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        _require_canonical_enum(self.status)
        if tuple(check.name for check in self.prerequisites) != _PREREQUISITES:
            raise ValueError("combination prerequisites must be complete and canonically ordered")
        by_name = {check.name: check for check in self.prerequisites}
        expected_prerequisites = _prerequisite_statuses(
            self.combination, self.trusted_combination, self.recipes, self.accepted_role_references
        )
        if any(
            by_name[name].status is not status for name, status in expected_prerequisites.items()
        ):
            raise ValueError(
                "prerequisite status differs from retained membership/authority records"
            )
        if (by_name["PORTION_CONFIGURATION"].status is None) != (
            self.combination.portion_state is PortionState.UNASSIGNED
        ):
            raise ValueError("only UNASSIGNED portions are unevaluated")
        if self.trusted_combination is None:
            if by_name["SOURCE_AUTHORITY"].status is not RuleStatus.UNKNOWN:
                raise ValueError("missing upstream authority must remain UNKNOWN")
        elif self.trusted_combination.content_digest != self.combination.content_digest:
            raise ValueError("proposal differs from independently selected upstream snapshot")
        combo, context = self.combination, self.recipes.context
        if (combo.context_id, combo.context_version, combo.context_digest) != (
            context.context_id,
            context.version,
            context.content_digest,
        ) or (combo.kb_id, combo.kb_version, combo.kb_digest) != (
            self.recipes.kb_id,
            self.recipes.kb_version,
            self.recipes.kb_digest,
        ):
            raise ValueError("combination result context/KB binding mismatch")
        if (
            combo.graph_id,
            combo.graph_version,
            combo.catalogue_version,
            combo.taxonomy_version,
            combo.check_catalogue_version,
        ) != (
            context.expected_graph_id,
            context.expected_graph_version,
            context.expected_catalogue_version,
            context.expected_taxonomy_version,
            context.expected_check_catalogue_version,
        ):
            raise ValueError("combination result graph/catalogue release mismatch")
        checks = self.trace.required_checks
        for rule in checks:
            _validate_combination_rule_policy(rule)
        if any(
            rule.lifecycle is not RuleLifecycle.ACTIVE
            or rule.severity is not RuleSeverity.ABSOLUTE
            or rule.approval_status is not ApprovalStatus.APPROVED
            for rule in (*checks, *self.deferred_checks)
        ):
            raise ValueError("combination obligations must remain ACTIVE, ABSOLUTE and APPROVED")
        if any(rule.scope is not RuleScope.COMBINATION for rule in checks) or any(
            rule.scope not in (RuleScope.DAY, RuleScope.WEEK) for rule in self.deferred_checks
        ):
            raise ValueError("combination/deferred scope partition mismatch")
        if tuple(rule.rule_id for rule in checks) != tuple(sorted({r.rule_id for r in checks})):
            raise ValueError("combination checks must have unique canonical ordered identities")
        if tuple(rule.rule_id for rule in self.deferred_checks) != tuple(
            sorted({rule.rule_id for rule in self.deferred_checks})
        ):
            raise ValueError("deferred checks must have unique canonical ordered identities")
        if tuple(item.rule for item in self.trace.evaluations) != checks:
            raise ValueError("every mandatory combination check must be evaluated exactly once")
        combination_facts = (
            {}
            if self.trusted_combination is None
            else {
                fact.fact_id: fact.observation
                for fact in self.trusted_combination.observations
                if fact.fact_id in _COMBINATION_ATTRIBUTES
            }
        )
        context_facts = {fact.fact_id: fact.observation for fact in context.facts}
        for evaluation in self.trace.evaluations:
            expected_facts = []
            for name in sorted(evaluation.rule.required_facts):
                namespace = combination_facts if name in _COMBINATION_ATTRIBUTES else context_facts
                observation = namespace.get(name)
                if observation is None:
                    observation = FactObservation(
                        fact_id=name,
                        value=None,
                        complete=False,
                        evidence=_evidence_union((combo.evidence, context.evidence)),
                    )
                expected_facts.append(observation)
            if evaluation.facts != tuple(expected_facts):
                raise ValueError("evaluated facts differ from exact combination/context sources")
            if (
                evaluation.applicability is ApplicabilityStatus.APPLICABLE
                and evaluation.status is not RuleStatus.UNKNOWN
            ):
                # RuleEvaluation validates resolved fact types/completeness. This
                # computed-result contract also rejects relabelled boolean outcomes;
                # Phase 1 declarations and external applicability remain unchanged.
                attribute = next(
                    fact for fact in evaluation.facts if fact.fact_id == evaluation.rule.attribute
                )
                matches = attribute.value == evaluation.rule.value
                satisfied = (
                    matches if evaluation.rule.operator is PredicateOperator.EQ else not matches
                )
                expected_status = RuleStatus.PASS if satisfied else RuleStatus.FAIL
                if evaluation.status is not expected_status:
                    raise ValueError(
                        "resolved outcome contradicts the registered boolean predicate"
                    )
        for decision in self.recipes.decisions:
            expected = tuple(
                sorted(
                    (*checks, *self.deferred_checks), key=lambda rule: (rule.rule_id, rule.version)
                )
            )
            if decision.resolution.manifest.deferred_checks != expected:
                raise ValueError("unresolved combination obligations differ from recipe manifests")
        digest = _content_digest(
            _combination_manifest(
                combo,
                self.trusted_combination,
                self.recipes,
                checks,
                self.deferred_checks,
                self.accepted_role_references,
            )
        )
        if (
            self.trace.candidate_id != combo.combination_id
            or self.trace.context_id != context.context_id
            or self.trace.manifest_id != "combination-manifest-" + digest
            or self.trace.manifest_version != "combination-check-manifest.v1:" + digest
        ):
            raise ValueError("combination trace identity or manifest digest mismatch")
        statuses = (
            aggregate_hard_status(self.trace),
            *(item.status for item in self.recipes.decisions),
            *(item.status for item in self.prerequisites if item.status is not None),
        )
        if self.status is not _combine_statuses(statuses):
            raise ValueError("combination status differs from complete hard aggregation")
        if self.evidence != _evidence_union(
            (
                combo,
                self.trusted_combination,
                self.recipes,
                self.accepted_role_references,
                self.prerequisites,
                self.trace,
                self.deferred_checks,
            )
        ):
            raise ValueError("combination evidence differs from its complete evaluated sources")
        return self
