"""GC1 STAND-IN knowledge base: lets the real catalogue run through Member 2's Rule Engine
and CSP before the production KB exists. NOT a safety rule set.

Every rule, evidence item and approval here is SYNTHETIC (the only environment Member 2's
contracts admit today) and checks only structural facts Member 1 supplies:

    RECIPE       dish classification settled (a plannable dish)
    COMBINATION  meal roles compatible (built from a curated template)
    DAY          all three slots resolved
    WEEK         all seven days resolved

Diet, allergy and cultural exclusions are applied BEFORE the Rule Engine by the stand-in
profile screen (`profile.py`); clinical rules are not applied at all. Every pipeline result
carries `SafetyVerification(status="STAND_IN_UNVERIFIED")` so no caller can present it as
verified. Replace this module with Member 2's production KB release; the KB and context it
returns are the only things that change.
"""

from collections.abc import Iterable
from typing import Any

from savora_ai.core.meal_composition.member2_adapter import SCENARIO_A, graph_entities
from savora_ai.core.pipelines.catalogue import CatalogueBundle
from savora_ai.core.pipelines.profile import PlanningProfile
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.schemas.candidates import FactSubjectKind, RuleContext, VersionedFact
from savora_ai.schemas.food_graph import FoodGraphSnapshot
from savora_ai.schemas.knowledge import (
    ApprovalStatus,
    EvidenceReference,
    PredicateOperator,
    RuleDefinition,
    RuleDomain,
    RuleEnvironment,
    RuleLifecycle,
    RuleReference,
    RuleScope,
    RuleSeverity,
)
from savora_ai.schemas.knowledge_base import (
    ApplicabilityDescriptor,
    CheckCatalogueEntry,
    KnowledgeBaseSnapshot,
    KnowledgeWorkflow,
    RuleCatalogueCoverage,
)
from savora_ai.schemas.reasoning import FactObservation

STAND_IN_KB_ID = "gc1-stand-in-kb"
STAND_IN_KB_VERSION = "1"
_CHECKS = "gc1-stand-in-checks"
_APPLICABILITY = RuleReference(rule_id="synthetic-context-enabled", version="1")
_CONTEXT_FACT = "synthetic_context_enabled"


def _evidence(name: str) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=name,
        version=STAND_IN_KB_VERSION,
        source="GC1 stand-in knowledge base; structural checks only, no clinical meaning",
        locator="urn:savora:stand-in:" + name,
        environment=RuleEnvironment.SYNTHETIC,
    )


def _rule(name: str, scope: RuleScope, attribute: str) -> RuleDefinition:
    return RuleDefinition.model_validate(
        dict(
            rule_id=name,
            version=STAND_IN_KB_VERSION,
            scope=scope,
            severity=RuleSeverity.ABSOLUTE,
            domain=RuleDomain.CULINARY,
            attribute=attribute,
            operator=PredicateOperator.EQ,
            value=True,
            required_facts=(attribute,),
            applicability_reference=_APPLICABILITY,
            evidence=(_evidence(name),),
            rationale="GC1 stand-in structural check; not a dietary or clinical rule",
            lifecycle=RuleLifecycle.ACTIVE,
            environment=RuleEnvironment.SYNTHETIC,
            approval_status=ApprovalStatus.APPROVED,
            approved_by="gc1-stand-in",
            approval_reference=_evidence("approval-" + name),
        )
    )


def build_stand_in_knowledge(
    bundle: CatalogueBundle, dish_ids: Iterable[str] | None = None
) -> KnowledgeBaseSnapshot:
    """The stand-in KB, its food graph limited to `dish_ids` (all dishes if None).

    Member 2's engine revalidates the whole KB for every candidate, so its cost grows with
    the graph: the pipelines build a KB scoped to the dishes of one request (about 0.1 s)."""
    dishes = (
        bundle.dishes.values()
        if dish_ids is None
        else [bundle.dishes[i] for i in sorted(set(dish_ids))]
    )
    ev = (_evidence("kb"),)
    graph = FoodGraphSnapshot(
        graph_id="gc1-stand-in-graph",
        version=STAND_IN_KB_VERSION,
        catalogue_version=bundle.version,
        environment=RuleEnvironment.SYNTHETIC,
        entities=graph_entities(dishes, bundle.version),
        relations=(),
        evidence=ev,
    )
    names = SCENARIO_A.fact_names
    rules = (
        _rule("dish-settled", RuleScope.RECIPE, names["classification_settled"]),
        _rule("meal-roles", RuleScope.COMBINATION, names["meal_roles_compatible"]),
        _rule("day-complete", RuleScope.DAY, "synthetic_day_complete"),
        _rule("week-complete", RuleScope.WEEK, "synthetic_week_complete"),
    )
    refs = tuple(RuleReference(rule_id=r.rule_id, version=r.version) for r in rules)
    cells = tuple(
        CheckCatalogueEntry(
            entry_id=f"cell-{w.value}-{s.value}",
            version=STAND_IN_KB_VERSION,
            kb_id=STAND_IN_KB_ID,
            kb_version=STAND_IN_KB_VERSION,
            check_catalogue_version=_CHECKS,
            workflow=w,
            scope=s,
            rule_references=tuple(ref for ref, r in zip(refs, rules, strict=True) if r.scope is s),
            evidence=ev,
        )
        for w in KnowledgeWorkflow
        for s in RuleScope
        if w is not KnowledgeWorkflow.CRAVING_DISCOVERY
        or s in (RuleScope.PROFILE, RuleScope.RECIPE)
    )
    body: dict[str, Any] = dict(
        kb_id=STAND_IN_KB_ID,
        version=STAND_IN_KB_VERSION,
        environment=RuleEnvironment.SYNTHETIC,
        graph_id=graph.graph_id,
        graph_version=graph.version,
        catalogue_version=bundle.version,
        taxonomy_version=None,
        check_catalogue_version=_CHECKS,
        graph=graph,
        rules=rules,
        active_rules=refs,
        applicability_descriptors=(
            ApplicabilityDescriptor(
                reference=_APPLICABILITY,
                rule_references=refs,
                required_context_facts=(_CONTEXT_FACT,),
                evidence=ev,
            ),
        ),
        check_catalogue=cells,
        rule_catalogue_coverage=tuple(
            RuleCatalogueCoverage(
                coverage_id="coverage-" + c.entry_id,
                version=STAND_IN_KB_VERSION,
                kb_id=STAND_IN_KB_ID,
                kb_version=STAND_IN_KB_VERSION,
                check_catalogue_version=_CHECKS,
                workflow=c.workflow,
                scope=c.scope,
                complete=True,
                reason="GC1 stand-in inventory (structural checks only)",
                evidence=ev,
            )
            for c in cells
        ),
        evidence=ev,
    )
    return build_knowledge_snapshot(body)


def stand_in_context(
    knowledge: KnowledgeBaseSnapshot, profile: PlanningProfile, workflow: KnowledgeWorkflow
) -> RuleContext:
    """The rule context for one profile version and workflow, pinned to `knowledge`."""
    ev = (_evidence("context"),)
    context_id = f"ctx-{workflow.value.lower()}-{profile.profile_id}"
    version = str(profile.profile_version)
    return RuleContext.build(
        dict(
            context_id=context_id,
            version=version,
            profile_id=profile.profile_id,
            profile_version=version,
            workflow=workflow,
            expected_kb_id=knowledge.kb_id,
            expected_kb_version=knowledge.version,
            expected_kb_digest=knowledge.content_digest,
            expected_graph_id=knowledge.graph_id,
            expected_graph_version=knowledge.graph_version,
            expected_catalogue_version=knowledge.catalogue_version,
            expected_taxonomy_version=knowledge.taxonomy_version,
            expected_check_catalogue_version=knowledge.check_catalogue_version,
            facts=(
                VersionedFact(
                    fact_id=_CONTEXT_FACT,
                    version=version,
                    subject_kind=FactSubjectKind.CONTEXT,
                    subject_id=context_id,
                    subject_version=version,
                    context_id=context_id,
                    context_version=version,
                    observation=FactObservation(
                        fact_id=_CONTEXT_FACT, value=True, complete=True, evidence=ev
                    ),
                ),
            ),
            evidence=ev,
        )
    )
