"""Frozen pre-refactor evaluator from 0ca114c, for full-result equivalence only.

Deliberately preserved independently of the new preparation helper. Shared public
schemas and recipe filtering remain unchanged. Never imported by production code.
"""

from typing import Self

from pydantic import model_validator

from savora_ai.core.reasoning.evaluation import _applicability, _observation, _predicate
from savora_ai.core.reasoning.facts import _validated_fact_index
from savora_ai.core.reasoning.filtering import _FilterRequest, filter_candidates
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.manifest import _descriptors_for, _mandatory_checks, _reject
from savora_ai.schemas.candidates import CandidateRecipeFacts, RuleContext, _content_digest
from savora_ai.schemas.combination_evaluation import (
    CombinationEligibilityResult,
    CombinationPrerequisite,
    _combination_manifest,
    _combine_statuses,
    _prerequisite_statuses,
)
from savora_ai.schemas.combinations import CombinationFacts
from savora_ai.schemas.filtering import (
    _COMBINATION_ATTRIBUTES,
    FilterCandidatesResult,
    _evidence_union,
    _validate_combination_rule_policy,
)
from savora_ai.schemas.food_graph import FoodEntity
from savora_ai.schemas.knowledge import RuleDefinition, RuleScope
from savora_ai.schemas.knowledge_base import (
    KnowledgeBaseSnapshot,
    KnowledgeWorkflow,
    _reference_key,
)
from savora_ai.schemas.reasoning import (
    ApplicabilityStatus,
    FactObservation,
    RuleEvaluation,
    RuleStatus,
    RuleTrace,
    aggregate_hard_status,
)


class _CombinationRequest(_FilterRequest):
    combination: CombinationFacts
    trusted_combination: CombinationFacts | None

    @model_validator(mode="after")
    def validate_combination_bindings(self) -> Self:
        combo, context, kb = self.combination, self.context, self.kb
        if context.workflow is KnowledgeWorkflow.CRAVING_DISCOVERY:
            raise ValueError("standalone craving cannot enter combination evaluation")
        if (
            combo.context_id,
            combo.context_version,
            combo.context_digest,
            combo.kb_id,
            combo.kb_version,
            combo.kb_digest,
            combo.graph_id,
            combo.graph_version,
            combo.catalogue_version,
            combo.taxonomy_version,
            combo.check_catalogue_version,
        ) != (
            context.context_id,
            context.version,
            context.content_digest,
            kb.kb_id,
            kb.version,
            kb.content_digest,
            kb.graph_id,
            kb.graph_version,
            kb.catalogue_version,
            kb.taxonomy_version,
            kb.check_catalogue_version,
        ):
            raise ValueError("exact combination context/KB/release binding mismatch")
        if self.trusted_combination is not None and (
            self.trusted_combination.content_digest != combo.content_digest
        ):
            raise ValueError("proposal differs from independently selected upstream snapshot")
        # Validate registered declarations even when authority/applicability is missing.
        for fact in combo.observations:
            if fact.fact_id in _COMBINATION_ATTRIBUTES and (
                fact.observation.value is not None and type(fact.observation.value) is not bool
            ):
                raise ValueError("combination policy observations require boolean values")
            if (
                fact.fact_id in _COMBINATION_ATTRIBUTES
                and fact.portion_configuration_id is not None
            ):
                raise ValueError("quantity-independent combination facts cannot be portion-bound")
        return self


def _prerequisites(
    request: _CombinationRequest,
    recipes: FilterCandidatesResult,
    accepted_roles: tuple[FoodEntity, ...],
) -> tuple[CombinationPrerequisite, ...]:
    combo, source = request.combination, request.trusted_combination
    try:
        statuses = _prerequisite_statuses(combo, source, recipes, accepted_roles)
    except ValueError as error:
        _reject(str(error))
        raise AssertionError("unreachable") from error
    membership = statuses["CANDIDATE_MEMBERSHIP"]
    authority = statuses["SOURCE_AUTHORITY"]
    composition = statuses["COMPOSITION_COMPLETENESS"]
    portions = statuses["PORTION_CONFIGURATION"]
    roles = statuses["ROLE_REFERENCES"]
    evidence = _evidence_union((combo, source, recipes))
    return (
        CombinationPrerequisite(
            name="CANDIDATE_MEMBERSHIP",
            status=membership,
            reason="EXACT_CANDIDATE_SNAPSHOTS"
            if membership is RuleStatus.PASS
            else "CANDIDATE_MISSING",
            evidence=evidence,
        ),
        CombinationPrerequisite(
            name="COMPOSITION_COMPLETENESS",
            status=composition,
            reason="TRUSTED_COMPLETE_COMPOSITION"
            if composition is RuleStatus.PASS
            else "COMPOSITION_NOT_ESTABLISHED",
            evidence=evidence,
        ),
        CombinationPrerequisite(
            name="PORTION_CONFIGURATION",
            status=portions,
            reason="UNASSIGNED_NO_QUANTITY_EVALUATED"
            if portions is None
            else "EXACT_TRUSTED_FIXED_CONFIGURATION"
            if portions is RuleStatus.PASS
            else "PORTION_AUTHORITY_MISSING",
            evidence=evidence,
        ),
        CombinationPrerequisite(
            name="ROLE_REFERENCES",
            status=roles,
            reason="EXACT_ACCEPTED_ROLE_REFERENCES"
            if roles is RuleStatus.PASS
            else "ROLE_REFERENCE_MISSING",
            evidence=evidence,
        ),
        CombinationPrerequisite(
            name="SOURCE_AUTHORITY",
            status=authority,
            reason="UPSTREAM_TRUSTED_SNAPSHOT"
            if source is not None
            else "UPSTREAM_AUTHORITY_MISSING",
            evidence=evidence,
        ),
    )


def _combination_checks(
    request: _CombinationRequest, rules: tuple[RuleDefinition, ...]
) -> tuple[RuleEvaluation, ...]:
    context = request.context
    indexed = _validated_fact_index(context.facts)
    applicability = _applicability(_descriptors_for(request.kb, rules), indexed, context)
    source = request.trusted_combination
    observed = (
        {}
        if source is None
        else {
            fact.fact_id: fact.observation
            for fact in source.observations
            if fact.fact_id in _COMBINATION_ATTRIBUTES
        }
    )
    facts = {name: _observation(fact) for name, fact in indexed.items()}
    facts.update(observed)
    evaluations = []
    for rule in rules:
        observations = tuple(
            facts.get(name)
            or FactObservation(
                fact_id=name,
                value=None,
                complete=False,
                evidence=_evidence_union((request.combination.evidence, context.evidence)),
            )
            for name in sorted(rule.required_facts)
        )
        state, evidence = applicability[_reference_key(rule.applicability_reference)]
        status = RuleStatus.UNKNOWN
        if state is ApplicabilityStatus.UNKNOWN:
            reason = "APPLICABILITY_UNKNOWN"
        elif state is ApplicabilityStatus.NOT_APPLICABLE:
            reason = "NOT_APPLICABLE"
        elif any(fact.value is None or not fact.complete for fact in observations):
            reason = "REQUIRED_FACT_UNKNOWN"
        else:
            attribute = next(fact for fact in observations if fact.fact_id == rule.attribute)
            status = RuleStatus.PASS if _predicate(rule, attribute) else RuleStatus.FAIL
            reason = "PREDICATE_TRUE" if status is RuleStatus.PASS else "PREDICATE_FALSE"
        evaluations.append(
            RuleEvaluation(
                rule=rule,
                applicability=state,
                applicability_evidence=evidence,
                facts=observations,
                status=status,
                reason=context.evaluator_policy_version + ":" + reason,
            )
        )
    return tuple(evaluations)


def evaluate_combination(
    combination: CombinationFacts,
    *,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    trusted_combination: CombinationFacts | None = None,
) -> CombinationEligibilityResult:
    """Evaluate against independently selected upstream sources, never proposal authority.

    The caller owns source selection/authentication, as for Phase 3 KB/context inputs.
    Omitted upstream combination authority remains UNKNOWN. Structural contradictions
    raise ValidationError. UNASSIGNED quantities are not optimized or asserted valid.
    """
    request = _CombinationRequest.model_validate(
        dict(
            combination=combination,
            candidates=candidates,
            kb=knowledge,
            context=context,
            trusted_combination=trusted_combination,
        )
    )
    knowledge = build_knowledge_snapshot(
        request.kb, expected_digest=request.context.expected_kb_digest
    )
    mandatory = _mandatory_checks(knowledge, request.context)
    checks = tuple(rule for rule in mandatory if rule.scope is RuleScope.COMBINATION)
    for rule in checks:
        try:
            _validate_combination_rule_policy(rule)
        except ValueError as error:
            _reject(str(error))
    deferred = tuple(rule for rule in mandatory if rule.scope in (RuleScope.DAY, RuleScope.WEEK))
    # Validate the entire pool; unrelated recipe decisions do not gate this combination.
    all_recipes = filter_candidates(
        request.candidates, knowledge=knowledge, context=request.context
    )
    ids = {component.recipe_snapshot.recipe_id for component in request.combination.components}
    recipes = FilterCandidatesResult.model_validate(
        all_recipes.model_dump()
        | {
            "decisions": tuple(
                d for d in all_recipes.decisions if d.resolution.manifest.candidate_id in ids
            ),
            "eligible_ids": tuple(id_ for id_ in all_recipes.eligible_ids if id_ in ids),
            "excluded_ids": tuple(id_ for id_ in all_recipes.excluded_ids if id_ in ids),
        }
    )
    role_ids = {
        role.entity_id for part in request.combination.components for role in part.role_references
    }
    accepted_roles = tuple(
        sorted(
            (entity for entity in knowledge.graph.entities if entity.entity_id in role_ids),
            key=lambda entity: entity.entity_id,
        )
    )
    prerequisites = _prerequisites(request, recipes, accepted_roles)
    evaluations = _combination_checks(request, checks)
    digest = _content_digest(
        _combination_manifest(
            request.combination,
            request.trusted_combination,
            recipes,
            checks,
            deferred,
            accepted_roles,
        )
    )
    trace = RuleTrace(
        candidate_id=request.combination.combination_id,
        context_id=request.context.context_id,
        manifest_id="combination-manifest-" + digest,
        manifest_version="combination-check-manifest.v1:" + digest,
        required_checks=checks,
        evaluations=evaluations,
    )
    status = _combine_statuses(
        (
            aggregate_hard_status(trace),
            *(d.status for d in recipes.decisions),
            *(item.status for item in prerequisites if item.status is not None),
        )
    )
    return CombinationEligibilityResult(
        combination=request.combination,
        trusted_combination=request.trusted_combination,
        recipes=recipes,
        accepted_role_references=accepted_roles,
        prerequisites=prerequisites,
        trace=trace,
        deferred_checks=deferred,
        status=status,
        evidence=_evidence_union(
            (
                request.combination,
                request.trusted_combination,
                recipes,
                accepted_roles,
                prerequisites,
                trace,
                deferred,
            )
        ),
    )
