"""Independent Phase 1-3 fixtures, literal truth tables and adversarial boundary probes.

No prior test fixtures, comparator, adapter or production canonicalization helper
calculates the expected eligibility, identities, witness or evidence assertions.
"""

import ast
import hashlib
import json
import math
from enum import StrEnum
from itertools import permutations
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from savora_ai.core.reasoning.evaluation import evaluate_rule_checks
from savora_ai.core.reasoning.facts import resolve_rule_facts
from savora_ai.core.reasoning.filtering import filter_candidates
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.manifest import build_expected_check_manifest
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    FactSubjectKind,
    IngredientCoverage,
    IngredientGapReason,
    IngredientLine,
    IngredientMappingStatus,
    MeasurementBasis,
    RuleContext,
    VersionedFact,
    validate_contract_json,
)
from savora_ai.schemas.filtering import ExpectedCheckManifest, FilterCandidatesResult
from savora_ai.schemas.food_graph import (
    FoodEntity,
    FoodEntityKind,
    FoodGraphSnapshot,
    FoodRelation,
    FoodRelationType,
    RelationAssertion,
    RelationResolutionStatus,
    TaxonomyAssignment,
    TaxonomyAssignmentAssertion,
    TaxonomyKind,
    TaxonomyTerm,
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
from savora_ai.schemas.reasoning import (
    ApplicabilityStatus,
    FactObservation,
    RuleStatus,
    aggregate_hard_status,
    is_candidate_eligible,
)


def proof(id_: str, **changes: Any) -> EvidenceReference:
    return EvidenceReference.model_validate(
        {
            "evidence_id": id_,
            "version": "1",
            "source": "Independent synthetic audit fixture, no medical meaning",
            "locator": "urn:phase3-independent-audit:" + id_,
            "environment": RuleEnvironment.SYNTHETIC,
        }
        | changes
    )


def audit_rule(id_: str = "quantity", **changes: Any) -> RuleDefinition:
    return RuleDefinition.model_validate(
        {
            "rule_id": id_,
            "version": "rule-v5",
            "scope": RuleScope.RECIPE,
            "severity": RuleSeverity.ABSOLUTE,
            "domain": RuleDomain.DIETARY,
            "attribute": "synthetic_quantity",
            "operator": PredicateOperator.LE,
            "value": 13,
            "unit": MeasurementUnit.MG,
            "required_facts": ("synthetic_quantity",),
            "applicability_reference": RuleReference(
                rule_id="synthetic-context-enabled", version="1"
            ),
            "evidence": (proof("rule-" + id_),),
            "rationale": "Fictional exact comparison, no clinical threshold",
            "lifecycle": RuleLifecycle.ACTIVE,
            "approval_status": ApprovalStatus.APPROVED,
            "approved_by": "fictional-reviewer",
            "approval_reference": proof("approval-" + id_),
            "environment": RuleEnvironment.SYNTHETIC,
        }
        | changes
    )


def boolean_rule(id_: str, name: str, value: bool = False, **changes: Any) -> RuleDefinition:
    return audit_rule(
        id_,
        attribute=name,
        required_facts=(name,),
        operator=PredicateOperator.EQ,
        value=value,
        unit=None,
        **changes,
    )


def observation(
    recipe: str,
    name: str,
    value: Any,
    *,
    subject: FactSubjectKind = FactSubjectKind.RECIPE,
    complete: bool = True,
    unit: MeasurementUnit | None = None,
) -> VersionedFact:
    owner, revision = {
        FactSubjectKind.RECIPE: (recipe, "recipe-v11"),
        FactSubjectKind.PROFILE: ("audit-profile", "profile-v12"),
        FactSubjectKind.CONTEXT: ("audit-context", "context-v13"),
    }[subject]
    numeric = type(value) in (int, float)
    return VersionedFact(
        fact_id=name,
        version="fact-v14",
        subject_kind=subject,
        subject_id=owner,
        subject_version=revision,
        catalogue_version="food-v4" if subject is FactSubjectKind.RECIPE else None,
        context_id="audit-context" if subject is FactSubjectKind.CONTEXT else None,
        context_version="context-v13" if subject is FactSubjectKind.CONTEXT else None,
        observation=FactObservation(
            fact_id=name,
            value=value,
            complete=complete,
            unit=unit,
            evidence=(proof("observed-" + recipe + "-" + name),),
        ),
        measurement_basis=MeasurementBasis.PER_100_G if numeric else None,
        basis_reference=proof("synthetic-per-100-g") if numeric else None,
    )


def audit_line(recipe: str, canonical: str, **changes: Any) -> IngredientLine:
    return IngredientLine.model_validate(
        {
            "line_id": recipe + "-line-" + canonical,
            "version": "line-v15",
            "recipe_id": recipe,
            "recipe_version": "recipe-v11",
            "catalogue_version": "food-v4",
            "mapping_status": IngredientMappingStatus.MAPPED,
            "ingredient_id": canonical,
            "ingredient_version": "ingredient-v16",
            "subingredients_complete": True,
            "gap_reasons": (),
            "evidence": (proof(recipe + "-line-source-" + canonical),),
        }
        | changes
    )


def fixture(
    rules: tuple[RuleDefinition, ...] | None = None,
    *,
    condition: bool | None = True,
    workflow: KnowledgeWorkflow = KnowledgeWorkflow.CRAVING_DISCOVERY,
    dependency: bool | str | None = "unused",
) -> tuple[KnowledgeBaseSnapshot, tuple[CandidateRecipeFacts, ...], RuleContext]:
    definitions = (
        rules
        if rules is not None
        else (
            audit_rule(),
            boolean_rule("profile", "synthetic_profile_flag", scope=RuleScope.PROFILE),
            boolean_rule("containment", "synthetic_contains_target"),
        )
    )
    recipes = ("alpha", "beta", "gamma")
    nodes = tuple(
        FoodEntity(
            entity_id="node-" + id_,
            version="node-v9",
            kind=FoodEntityKind.RECIPE_REFERENCE,
            canonical_name="Independent synthetic recipe " + id_,
            catalogue_reference=id_,
            evidence=(proof("node-" + id_),),
        )
        for id_ in recipes
    )
    source = FoodEntity(
        entity_id="source-node",
        version="node-v9",
        kind=FoodEntityKind.INGREDIENT,
        canonical_name="Independent source",
        catalogue_reference="synthetic-source",
        evidence=(proof("source-node"),),
    )
    target = FoodEntity(
        entity_id="target-node",
        version="node-v9",
        kind=FoodEntityKind.INGREDIENT,
        canonical_name="Independent target",
        catalogue_reference="synthetic-target",
        evidence=(proof("target-node"),),
    )
    middle = FoodEntity(
        entity_id="middle-node",
        version="node-v9",
        kind=FoodEntityKind.INGREDIENT,
        canonical_name="Independent intermediate",
        evidence=(proof("middle-node"),),
    )
    relations = [
        FoodRelation(
            relation_id=id_ + "-source",
            version="edge-v10",
            relation_type=FoodRelationType.CONTAINS,
            source_id="node-" + id_,
            target_id="source-node",
            assertion=RelationAssertion.PRESENT,
            evidence=(proof(id_ + "-source-edge"),),
        )
        for id_ in recipes
    ]
    for id_, assertion in (
        ("alpha", RelationAssertion.PRESENT),
        ("beta", RelationAssertion.ABSENT),
    ):
        relations.append(
            FoodRelation(
                relation_id=id_ + "-target",
                version="edge-v10",
                relation_type=FoodRelationType.CONTAINS,
                source_id="node-" + id_,
                target_id="target-node",
                assertion=assertion,
                evidence=(proof(id_ + "-target-edge"),),
            )
        )
    relations.extend(
        (
            FoodRelation(
                relation_id="origin-first",
                version="edge-v10",
                relation_type=FoodRelationType.DERIVED_FROM,
                source_id="source-node",
                target_id="middle-node",
                assertion=RelationAssertion.PRESENT,
                evidence=(proof("origin-first"),),
            ),
            FoodRelation(
                relation_id="origin-second",
                version="edge-v10",
                relation_type=FoodRelationType.DERIVED_FROM,
                source_id="middle-node",
                target_id="target-node",
                assertion=RelationAssertion.PRESENT,
                evidence=(proof("origin-second"),),
            ),
        )
    )
    terms = (
        TaxonomyTerm(
            term_id="synthetic-dietary",
            version="term-v17",
            kind=TaxonomyKind.DIETARY_CATEGORY,
            display_label="Audit diet",
            evidence=(proof("diet-term"),),
        ),
        TaxonomyTerm(
            term_id="synthetic-cuisine",
            version="term-v17",
            kind=TaxonomyKind.CUISINE,
            display_label="Audit cuisine parent",
            evidence=(proof("cuisine-parent"),),
        ),
        TaxonomyTerm(
            term_id="audit-cuisine-child",
            version="term-v17",
            kind=TaxonomyKind.CUISINE,
            display_label="Audit cuisine child",
            parent_ids=("synthetic-cuisine",),
            evidence=(proof("cuisine-child"),),
        ),
    )
    assignments = tuple(
        TaxonomyAssignment(
            assignment_id="beta-" + term,
            version="assignment-v18",
            subject_id="node-beta",
            term_id=term,
            assertion=TaxonomyAssignmentAssertion.PRESENT,
            evidence=(proof("assignment-" + term),),
        )
        for term in ("synthetic-dietary", "audit-cuisine-child")
    )
    graph = FoodGraphSnapshot(
        graph_id="audit-graph",
        version="graph-v2",
        catalogue_version="food-v4",
        environment=RuleEnvironment.SYNTHETIC,
        entities=(*nodes, source, target, middle),
        relations=tuple(relations),
        taxonomy_version="taxonomy-v6",
        taxonomy_terms=terms,
        taxonomy_assignments=assignments,
        evidence=(proof("audit-graph-source"),),
    )
    active = tuple(
        RuleReference(rule_id=rule.rule_id, version=rule.version)
        for rule in definitions
        if rule.lifecycle is RuleLifecycle.ACTIVE
    )
    descriptors = []
    for id_, name in (
        ("synthetic-context-enabled", "synthetic_context_enabled"),
        ("synthetic-profile-enabled", "synthetic_profile_enabled"),
    ):
        if id_ == "synthetic-profile-enabled" and dependency == "unused":
            continue
        descriptors.append(
            ApplicabilityDescriptor(
                reference=RuleReference(rule_id=id_, version="1"),
                rule_references=tuple(
                    RuleReference(rule_id=rule.rule_id, version=rule.version)
                    for rule in definitions
                    if rule.applicability_reference.rule_id == id_
                ),
                required_context_facts=(name,),
                dependencies=(RuleReference(rule_id="synthetic-profile-enabled", version="1"),)
                if id_ == "synthetic-context-enabled" and dependency != "unused"
                else (),
                evidence=(proof("descriptor-" + id_),),
            )
        )
    cells = tuple(
        (flow, scope)
        for flow in KnowledgeWorkflow
        for scope in (
            (RuleScope.PROFILE, RuleScope.RECIPE)
            if flow is KnowledgeWorkflow.CRAVING_DISCOVERY
            else (
                RuleScope.PROFILE,
                RuleScope.RECIPE,
                RuleScope.COMBINATION,
                RuleScope.DAY,
                RuleScope.WEEK,
            )
        )
    )
    entries = tuple(
        CheckCatalogueEntry(
            entry_id=flow.value + "-" + scope.value,
            version="entry-v19",
            kb_id="audit-kb",
            kb_version="kb-v7",
            check_catalogue_version="checks-v3",
            workflow=flow,
            scope=scope,
            rule_references=tuple(
                RuleReference(rule_id=rule.rule_id, version=rule.version)
                for rule in definitions
                if rule.scope is scope
                and rule.lifecycle is RuleLifecycle.ACTIVE
                and rule.severity is RuleSeverity.ABSOLUTE
            ),
            evidence=(proof("catalogue-source"),),
        )
        for flow, scope in cells
    )
    coverage = tuple(
        RuleCatalogueCoverage(
            coverage_id="coverage-" + entry.entry_id,
            version="coverage-v20",
            kb_id="audit-kb",
            kb_version="kb-v7",
            check_catalogue_version="checks-v3",
            workflow=entry.workflow,
            scope=entry.scope,
            complete=True,
            reason="Independent synthetic inventory coverage",
            evidence=(proof("coverage-source"),),
        )
        for entry in entries
    )
    kb = build_knowledge_snapshot(
        {
            "kb_id": "audit-kb",
            "version": "kb-v7",
            "environment": RuleEnvironment.SYNTHETIC,
            "graph_id": "audit-graph",
            "graph_version": "graph-v2",
            "catalogue_version": "food-v4",
            "taxonomy_version": "taxonomy-v6",
            "check_catalogue_version": "checks-v3",
            "graph": graph,
            "rules": definitions,
            "active_rules": active,
            "applicability_descriptors": tuple(descriptors),
            "check_catalogue": entries,
            "rule_catalogue_coverage": coverage,
            "evidence": (proof("kb-source"),),
        }
    )
    candidates = []
    for id_, node in zip(recipes, nodes, strict=True):
        lines = (audit_line(id_, "synthetic-source"),)
        if id_ == "alpha":
            lines = (*lines, audit_line(id_, "synthetic-target"))
        inventory = IngredientCoverage(
            coverage_id=id_ + "-coverage",
            version="inventory-v21",
            recipe_id=id_,
            recipe_version="recipe-v11",
            catalogue_version="food-v4",
            lines=lines,
            inventory_complete=True,
            mapping_complete=True,
            subingredients_complete=True,
            gap_reasons=(),
            evidence=(proof(id_ + "-inventory-source"),),
        )
        candidates.append(
            CandidateRecipeFacts.build(
                {
                    "recipe_id": id_,
                    "recipe_version": "recipe-v11",
                    "catalogue_version": "food-v4",
                    "graph_id": "audit-graph",
                    "graph_version": "graph-v2",
                    "graph_recipe_entity_id": node.entity_id,
                    "graph_recipe_reference": node,
                    "snapshot_id": id_ + "-snapshot",
                    "snapshot_version": "snapshot-v22",
                    "ingredient_coverage": inventory,
                    "facts": (
                        observation(id_, "synthetic_quantity", 13, unit=MeasurementUnit.MG),
                        observation(id_, "synthetic_flag", False),
                    ),
                    "evidence": (proof(id_ + "-recipe-source"),),
                }
            )
        )
    facts = (
        observation(
            "shared",
            "synthetic_context_enabled",
            condition,
            complete=condition is not None,
            subject=FactSubjectKind.CONTEXT,
        ),
        observation("shared", "synthetic_profile_flag", False, subject=FactSubjectKind.PROFILE),
    )
    if dependency != "unused":
        facts = (
            *facts,
            observation(
                "shared",
                "synthetic_profile_enabled",
                dependency,
                complete=dependency is not None,
                subject=FactSubjectKind.PROFILE,
            ),
        )
    context = RuleContext.build(
        {
            "context_id": "audit-context",
            "version": "context-v13",
            "profile_id": "audit-profile",
            "profile_version": "profile-v12",
            "workflow": workflow,
            "expected_kb_id": "audit-kb",
            "expected_kb_version": "kb-v7",
            "expected_kb_digest": kb.content_digest,
            "expected_graph_id": "audit-graph",
            "expected_graph_version": "graph-v2",
            "expected_catalogue_version": "food-v4",
            "expected_taxonomy_version": "taxonomy-v6",
            "expected_check_catalogue_version": "checks-v3",
            "facts": facts,
            "evidence": (proof("context-source"),),
        }
    )
    return kb, tuple(candidates), context


def revise_candidate(candidate: CandidateRecipeFacts, **changes: Any) -> CandidateRecipeFacts:
    data: dict[str, Any] = candidate.model_dump(exclude={"content_digest"}) | changes
    return CandidateRecipeFacts.build(data)


def revise_context(context: RuleContext, **changes: Any) -> RuleContext:
    data: dict[str, Any] = context.model_dump(exclude={"content_digest"}) | changes
    return RuleContext.build(data)


def unordered_digest(data: Any) -> str:
    # Independent recursive encoder; no production digest/model validators consulted.
    def encode(value: Any) -> str:
        if isinstance(value, dict):
            return (
                "{"
                + ",".join(json.dumps(key) + ":" + encode(value[key]) for key in sorted(value))
                + "}"
            )
        if isinstance(value, list):
            return "[" + ",".join(sorted(encode(item) for item in value)) + "]"
        return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))

    return hashlib.sha256(encode(data).encode("utf-8")).hexdigest()


def rehash_manifest(manifest: ExpectedCheckManifest, **changes: Any) -> ExpectedCheckManifest:
    body = manifest.model_dump(
        mode="json", by_alias=True, exclude={"manifest_id", "manifest_version", "content_digest"}
    )
    body.update(changes)
    digest = unordered_digest(body)
    return validate_contract_json(
        ExpectedCheckManifest,
        json.dumps(
            body
            | {
                "contentDigest": digest,
                "manifestId": "manifest-" + digest,
                "manifestVersion": "synthetic-manifest.v1:" + digest,
            }
        ),
    )


def test_complete_three_candidate_partition_and_trace_explanation_binding() -> None:
    kb, candidates, context = fixture()
    result = filter_candidates(candidates, knowledge=kb, context=context)
    assert result.eligible_ids == ("beta",)
    assert result.excluded_ids == ("alpha", "gamma")
    assert tuple(item.status for item in result.decisions) == (
        RuleStatus.FAIL,
        RuleStatus.PASS,
        RuleStatus.UNKNOWN,
    )
    for decision in result.decisions:
        manifest = decision.resolution.manifest
        assert tuple(rule.rule_id for rule in manifest.required_checks) == (
            "containment",
            "profile",
            "quantity",
        )
        assert tuple(item.rule.rule_id for item in decision.trace.evaluations) == (
            "containment",
            "profile",
            "quantity",
        )
        assert aggregate_hard_status(decision.trace) is decision.status
        assert is_candidate_eligible(decision.status) is (decision.trace.candidate_id == "beta")
        assert decision.trace.manifest_id == manifest.manifest_id
        assert decision.trace.manifest_version == manifest.manifest_version
        for explanation, evaluation in zip(
            decision.explanations, decision.trace.evaluations, strict=True
        ):
            assert explanation.evaluation == evaluation
            assert explanation.candidate_id == decision.trace.candidate_id
            assert explanation.candidate_version == "recipe-v11"
            assert explanation.context_version == "context-v13"
            assert explanation.kb_version == "kb-v7"
            assert explanation.manifest_digest == manifest.content_digest
            assert explanation.evidence
        assert (
            evaluate_rule_checks(
                kb,
                candidates[("alpha", "beta", "gamma").index(decision.trace.candidate_id)],
                context,
                manifest,
            )
            == decision.trace.evaluations
        )
    assert (
        validate_contract_json(FilterCandidatesResult, result.model_dump_json(by_alias=True))
        == result
    )


@pytest.mark.parametrize(
    "operator,values,truth",
    [
        (PredicateOperator.LT, (12, 13, 14), (True, False, False)),
        (PredicateOperator.LE, (12, 13, 14), (True, True, False)),
        (PredicateOperator.GT, (12, 13, 14), (False, False, True)),
        (PredicateOperator.GE, (12, 13, 14), (False, True, True)),
        (PredicateOperator.EQ, (12, 13, 14), (False, True, False)),
        (PredicateOperator.NE, (12, 13, 14), (True, False, True)),
        (PredicateOperator.IN, ("A", "B", "a"), (True, True, False)),
        (PredicateOperator.NOT_IN, ("A", "B", "a"), (False, False, True)),
    ],
)
def test_all_operators_against_literal_independent_truth_table(
    operator: PredicateOperator, values: tuple[Any, ...], truth: tuple[bool, ...]
) -> None:
    membership = operator in (PredicateOperator.IN, PredicateOperator.NOT_IN)
    name = "synthetic_category" if membership else "synthetic_quantity"
    rule = audit_rule(
        operator=operator,
        attribute=name,
        required_facts=(name,),
        value=("A", "B") if membership else 13,
        unit=None if membership else MeasurementUnit.MG,
    )
    kb, candidates, context = fixture((rule,))
    batch = tuple(
        revise_candidate(
            candidate,
            facts=(
                observation(
                    candidate.recipe_id,
                    name,
                    value,
                    unit=None if membership else MeasurementUnit.MG,
                ),
            ),
        )
        for candidate, value in zip(candidates, values, strict=True)
    )
    result = filter_candidates(batch, knowledge=kb, context=context)
    expected = tuple(RuleStatus.PASS if item else RuleStatus.FAIL for item in truth)
    assert tuple(item.status for item in result.decisions) == expected


@pytest.mark.parametrize(
    "condition,status,app,eligible",
    [
        (True, RuleStatus.UNKNOWN, ApplicabilityStatus.APPLICABLE, ()),
        (False, RuleStatus.PASS, ApplicabilityStatus.NOT_APPLICABLE, ("beta",)),
        (None, RuleStatus.UNKNOWN, ApplicabilityStatus.UNKNOWN, ()),
    ],
)
def test_applicability_states_keep_missing_requirement_and_check(
    condition: bool | None, status: RuleStatus, app: ApplicabilityStatus, eligible: tuple[str, ...]
) -> None:
    kb, candidates, context = fixture((audit_rule(),), condition=condition)
    candidate = revise_candidate(candidates[1], facts=())
    result = filter_candidates((candidate,), knowledge=kb, context=context)
    assert result.eligible_ids == eligible and result.decisions[0].status is status
    assert len(result.decisions[0].trace.evaluations) == 1
    assert result.decisions[0].trace.evaluations[0].applicability is app
    assert result.decisions[0].trace.evaluations[0].status is RuleStatus.UNKNOWN


@pytest.mark.parametrize(
    "own,dependency,expected",
    [
        (False, None, RuleStatus.UNKNOWN),
        (None, False, RuleStatus.UNKNOWN),
        (True, False, RuleStatus.PASS),
        (True, True, RuleStatus.PASS),
    ],
)
def test_conservative_dependency_unknown_dominates_false(
    own: bool | None, dependency: bool | None, expected: RuleStatus
) -> None:
    kb, candidates, context = fixture((audit_rule(),), condition=own, dependency=dependency)
    result = filter_candidates((candidates[1],), knowledge=kb, context=context)
    assert result.decisions[0].status is expected


def test_known_fail_dominates_missing_recipe_and_profile_requirements() -> None:
    rules = (
        audit_rule(),
        boolean_rule("profile", "synthetic_profile_flag"),
        boolean_rule("recipe", "synthetic_category"),
    )
    # Correct scalar categorical declaration, not a boolean cast.
    rules = (
        *rules[:2],
        audit_rule(
            "recipe",
            attribute="synthetic_category",
            required_facts=("synthetic_category",),
            operator=PredicateOperator.EQ,
            value="A",
            unit=None,
        ),
    )
    kb, candidates, context = fixture(rules)
    context = revise_context(context, facts=context.facts[:1])
    candidate = revise_candidate(
        candidates[1],
        facts=(observation("beta", "synthetic_quantity", 14, unit=MeasurementUnit.MG),),
    )
    result = filter_candidates((candidate,), knowledge=kb, context=context)
    assert result.decisions[0].status is RuleStatus.FAIL
    assert tuple(item.status for item in result.decisions[0].trace.evaluations) == (
        RuleStatus.UNKNOWN,
        RuleStatus.FAIL,
        RuleStatus.UNKNOWN,
    )
    assert len(result.decisions[0].explanations) == 3
    assert result.eligible_ids == ()


@pytest.mark.parametrize("gap", ["missing", "null", "incomplete"])
def test_required_fact_completeness_cannot_yield_pass(gap: str) -> None:
    kb, candidates, context = fixture((audit_rule(),))
    facts = (
        ()
        if gap == "missing"
        else (
            observation("beta", "synthetic_quantity", None, complete=False)
            if gap == "null"
            else observation(
                "beta", "synthetic_quantity", 0, complete=False, unit=MeasurementUnit.MG
            ),
        )
    )
    result = filter_candidates(
        (revise_candidate(candidates[1], facts=facts),), knowledge=kb, context=context
    )
    assert result.decisions[0].status is RuleStatus.UNKNOWN
    assert result.eligible_ids == ()


@pytest.mark.parametrize(
    "case",
    [
        "missing_entry",
        "missing_rule",
        "stale_rule",
        "inactive",
        "wrong_scope",
        "missing_coverage",
        "incomplete_coverage",
    ],
)
def test_mandatory_catalogue_adversarial_edits_are_rejected(case: str) -> None:
    kb, candidates, context = fixture()
    entries = kb.check_catalogue
    index = next(
        i
        for i, entry in enumerate(entries)
        if entry.workflow is KnowledgeWorkflow.CRAVING_DISCOVERY and entry.scope is RuleScope.RECIPE
    )
    changes: dict[str, Any] = {}
    if case == "missing_entry":
        changes["check_catalogue"] = entries[:index] + entries[index + 1 :]
    elif case in ("missing_rule", "stale_rule", "wrong_scope"):
        entry = entries[index]
        update = (
            {"rule_references": entry.rule_references[:1]}
            if case == "missing_rule"
            else {
                "rule_references": (RuleReference(rule_id="quantity", version="stale"),),
            }
            if case == "stale_rule"
            else {"scope": RuleScope.PROFILE}
        )
        changes["check_catalogue"] = (
            *entries[:index],
            entry.model_copy(update=update),
            *entries[index + 1 :],
        )
    elif case == "inactive":
        changes["rules"] = (
            kb.rules[0].model_copy(update={"lifecycle": RuleLifecycle.RETIRED}),
            *kb.rules[1:],
        )
    elif case == "missing_coverage":
        changes["rule_catalogue_coverage"] = kb.rule_catalogue_coverage[:-1]
    else:
        changes["rule_catalogue_coverage"] = (
            kb.rule_catalogue_coverage[0].model_copy(update={"complete": False}),
            *kb.rule_catalogue_coverage[1:],
        )
    with pytest.raises(ValidationError):
        filter_candidates(candidates, knowledge=kb.model_copy(update=changes), context=context)


@pytest.mark.parametrize("scope", list(RuleScope))
def test_phase3_approval_gate_including_deferred_checks(scope: RuleScope) -> None:
    name = "synthetic_profile_flag" if scope is RuleScope.PROFILE else "synthetic_flag"
    rule = boolean_rule(
        "unapproved",
        name,
        scope=scope,
        approval_status=ApprovalStatus.PENDING,
        approved_by=None,
        approval_reference=None,
    )
    kb, candidates, context = fixture((rule,), workflow=KnowledgeWorkflow.WEEKLY_PLAN)
    assert build_knowledge_snapshot(kb) == kb  # The Phase 2 policy is deliberately unchanged.
    with pytest.raises(ValidationError, match="unapproved"):
        filter_candidates(candidates, knowledge=kb, context=context)


@pytest.mark.parametrize(
    "edit", ["remove", "substitute", "context", "candidate", "workflow", "deferred"]
)
def test_rehashed_wrong_manifest_selection_cannot_override_authoritative_builder(edit: str) -> None:
    rules = (audit_rule(), boolean_rule("day", "synthetic_flag", True, scope=RuleScope.DAY))
    kb, candidates, context = fixture(rules, workflow=KnowledgeWorkflow.WEEKLY_PLAN)
    manifest = build_expected_check_manifest(kb, candidates[1], context)
    changes: dict[str, Any] = {
        "remove": {"requiredChecks": []},
        "substitute": {
            "requiredChecks": [audit_rule(value=99).model_dump(mode="json", by_alias=True)]
        },
        "context": {"contextVersion": "stale"},
        "candidate": {"candidateId": "alpha"},
        "workflow": {"workflow": "PLANNED_SWAP"},
        "deferred": {"deferredChecks": []},
    }[edit]
    wrong = rehash_manifest(manifest, **changes)
    with pytest.raises(ValidationError, match="manifest differs"):
        evaluate_rule_checks(kb, candidates[1], context, wrong)


@pytest.mark.parametrize("case", ["inventory", "mapping", "subingredients", "graph_mapping"])
def test_complete_negative_requires_complete_supported_inventory(case: str) -> None:
    kb, candidates, context = fixture((boolean_rule("absence", "synthetic_contains_target"),))
    candidate = candidates[1]
    line = audit_line("beta", "synthetic-source")
    if case == "inventory":
        updates = {
            "inventory_complete": False,
            "gap_reasons": (IngredientGapReason.INCOMPLETE_INVENTORY,),
        }
    elif case == "mapping":
        line = audit_line(
            "beta",
            "missing",
            mapping_status=IngredientMappingStatus.UNRESOLVED,
            ingredient_id=None,
            ingredient_version=None,
            gap_reasons=(IngredientGapReason.UNRESOLVED_MAPPING,),
        )
        updates = {
            "lines": (line,),
            "mapping_complete": False,
            "gap_reasons": (IngredientGapReason.UNRESOLVED_MAPPING,),
        }
    elif case == "subingredients":
        line = audit_line(
            "beta",
            "synthetic-source",
            subingredients_complete=False,
            gap_reasons=(IngredientGapReason.INCOMPLETE_SUBINGREDIENTS,),
        )
        updates = {
            "lines": (line,),
            "subingredients_complete": False,
            "gap_reasons": (IngredientGapReason.INCOMPLETE_SUBINGREDIENTS,),
        }
    else:
        updates = {"lines": (audit_line("beta", "no-graph-mapping"),)}
    inventory = IngredientCoverage.model_validate(
        candidate.ingredient_coverage.model_dump() | updates
    )
    result = filter_candidates(
        (revise_candidate(candidate, ingredient_coverage=inventory),), knowledge=kb, context=context
    )
    assert result.eligible_ids == () and result.decisions[0].status is RuleStatus.UNKNOWN
    record = next(
        item
        for item in result.decisions[0].resolution.facts
        if item.fact.fact_id == "synthetic_contains_target"
    )
    assert record.relations[0].status is RelationResolutionStatus.VERIFIED_ABSENT
    assert record.reason_code == "INGREDIENT_MAPPING_GAP"


def test_origin_and_taxonomy_witnesses_preserved_without_safety_generalization() -> None:
    rules = tuple(
        boolean_rule(name, name, True)
        for name in (
            "synthetic_origin_target",
            "synthetic_dietary_target",
            "synthetic_cuisine_target",
            "synthetic_allergen_absent",
        )
    )
    kb, candidates, context = fixture(rules)
    result = filter_candidates((candidates[1],), knowledge=kb, context=context)
    assert result.decisions[0].status is RuleStatus.UNKNOWN and result.eligible_ids == ()
    records = {item.fact.fact_id: item for item in result.decisions[0].resolution.facts}
    assert [edge.relation_id for edge in records["synthetic_origin_target"].relations[0].path] == [
        "origin-first",
        "origin-second",
    ]
    cuisine = records["synthetic_cuisine_target"].taxonomy
    assert cuisine is not None
    assert [term.term_id for term in cuisine.path] == [
        "audit-cuisine-child",
        "synthetic-cuisine",
    ]
    assert records["synthetic_dietary_target"].fact.observation.value is True
    assert records["synthetic_allergen_absent"].fact.observation.value is None
    assert result.decisions[0].resolution.manifest.taxonomy_version == "taxonomy-v6"


@pytest.mark.parametrize(
    "field",
    [
        "expected_kb_id",
        "expected_kb_version",
        "expected_kb_digest",
        "expected_graph_id",
        "expected_graph_version",
        "expected_catalogue_version",
        "expected_taxonomy_version",
        "expected_check_catalogue_version",
    ],
)
def test_release_pin_mismatch_is_structural_rejection(field: str) -> None:
    kb, candidates, context = fixture()
    changed = revise_context(context, **{field: "0" * 64 if field.endswith("digest") else "stale"})
    with pytest.raises(ValidationError):
        filter_candidates(candidates, knowledge=kb, context=changed)


@pytest.mark.parametrize("owner", ["profile", "context", "recipe"])
@pytest.mark.parametrize("field", ["subject_id", "subject_version"])
def test_wrong_fact_owner_or_revision_rejected(owner: str, field: str) -> None:
    kb, candidates, context = fixture()
    if owner == "recipe":
        bad = candidates[1].facts[0].model_copy(update={field: "wrong"})
        candidates = (candidates[1].model_copy(update={"facts": (bad,)}),)
    else:
        index = 1 if owner == "profile" else 0
        bad = context.facts[index].model_copy(update={field: "wrong"})
        context = context.model_copy(update={"facts": (bad,)})
    with pytest.raises(ValidationError):
        filter_candidates(candidates, knowledge=kb, context=context)


@pytest.mark.parametrize("condition", [False, None, True])
@pytest.mark.parametrize("value", [True, "13", ("13",), float("inf"), float("nan")])
def test_type_and_finiteness_corruption_cannot_hide_behind_applicability(
    condition: bool | None, value: Any
) -> None:
    kb, candidates, context = fixture((audit_rule(),), condition=condition)
    original = candidates[1].facts[0]
    bad = original.model_copy(
        update={
            "observation": original.observation.model_copy(
                update={"value": value, "complete": False}
            )
        }
    )
    with pytest.raises(ValidationError):
        filter_candidates(
            (candidates[1].model_copy(update={"facts": (bad,)}),), knowledge=kb, context=context
        )


@pytest.mark.parametrize("target", ["workflow", "severity", "operator", "environment", "mapping"])
def test_counterfeit_declared_enum_tokens_rejected(target: str) -> None:
    kb, candidates, context = fixture()
    classes: dict[str, type[StrEnum]] = {
        "workflow": KnowledgeWorkflow,
        "severity": RuleSeverity,
        "operator": PredicateOperator,
        "environment": RuleEnvironment,
        "mapping": IngredientMappingStatus,
    }
    tokens = {
        "workflow": "CRAVING_DISCOVERY",
        "severity": "ABSOLUTE",
        "operator": "LE",
        "environment": "SYNTHETIC",
        "mapping": "MAPPED",
    }
    fake: Any = str.__new__(classes[target], tokens[target])
    fake._value_ = tokens[target]
    if target == "workflow":
        context = context.model_copy(update={"workflow": fake})
    elif target in ("severity", "operator", "environment"):
        kb = kb.model_copy(
            update={"rules": (kb.rules[0].model_copy(update={target: fake}), *kb.rules[1:])}
        )
    else:
        candidate = candidates[1]
        bad_line = audit_line("beta", "synthetic-source").model_copy(
            update={"mapping_status": fake}
        )
        candidates = (
            candidate.model_copy(
                update={
                    "ingredient_coverage": candidate.ingredient_coverage.model_copy(
                        update={"lines": (bad_line,)}
                    )
                }
            ),
        )
    with pytest.raises(ValidationError):
        filter_candidates(candidates, knowledge=kb, context=context)


@pytest.mark.parametrize("mode", ["copy", "construct"])
@pytest.mark.parametrize("target", ["candidate", "context", "knowledge"])
def test_unchecked_dtos_revalidated_at_public_filter_boundary(mode: str, target: str) -> None:
    kb, candidates, context = fixture()
    model: Any = {"candidate": candidates[1], "context": context, "knowledge": kb}[target]
    malformed = (
        model.model_copy(update={"content_digest": "0" * 64})
        if mode == "copy"
        else type(model).model_construct(**(vars(model) | {"content_digest": "0" * 64}))
    )
    with pytest.raises(ValidationError):
        filter_candidates(
            (malformed,) if target == "candidate" else candidates,
            knowledge=malformed if target == "knowledge" else kb,
            context=malformed if target == "context" else context,
        )


def test_duplicate_candidate_and_opposing_fact_declarations_rejected() -> None:
    kb, candidates, context = fixture()
    with pytest.raises(ValidationError, match="duplicate candidate"):
        filter_candidates(
            (candidates[1], revise_candidate(candidates[1], snapshot_version="new")),
            knowledge=kb,
            context=context,
        )
    opposing = revise_candidate(
        candidates[1],
        facts=(*candidates[1].facts, observation("beta", "synthetic_contains_target", True)),
    )
    with pytest.raises(ValidationError, match="contradicts"):
        filter_candidates((opposing,), knowledge=kb, context=context)


@pytest.mark.parametrize("empty", [False, True])
def test_evidence_requirement_and_cross_source_conflicts_are_not_ignored(empty: bool) -> None:
    kb, candidates, context = fixture()
    evidence = () if empty else (proof("kb-source", source="opposing source metadata"),)
    bad = candidates[1].model_copy(update={"evidence": evidence})
    with pytest.raises(ValidationError):
        filter_candidates((bad,), knowledge=kb, context=context)


@pytest.mark.parametrize(
    "workflow", [KnowledgeWorkflow.WEEKLY_PLAN, KnowledgeWorkflow.PLANNED_SWAP]
)
def test_deferred_hard_fail_does_not_become_recipe_stage_feasibility(
    workflow: KnowledgeWorkflow,
) -> None:
    rules = (
        audit_rule(),
        *(
            boolean_rule(scope.value, "synthetic_flag", True, scope=scope)
            for scope in (RuleScope.COMBINATION, RuleScope.DAY, RuleScope.WEEK)
        ),
    )
    kb, candidates, context = fixture(rules, workflow=workflow)
    result = filter_candidates((candidates[1],), knowledge=kb, context=context)
    assert result.eligible_ids == ("beta",)
    assert tuple(
        item.rule_id for item in result.decisions[0].resolution.manifest.deferred_checks
    ) == ("COMBINATION", "DAY", "WEEK")
    assert tuple(item.rule.rule_id for item in result.decisions[0].trace.evaluations) == (
        "quantity",
    )
    assert result.plan_feasibility == "NOT_EVALUATED"


@pytest.mark.parametrize(
    "rules", [(), (boolean_rule("soft", "synthetic_flag", severity=RuleSeverity.SOFT),)]
)
def test_zero_mandatory_checks_cannot_produce_eligibility(
    rules: tuple[RuleDefinition, ...],
) -> None:
    kb, candidates, context = fixture(rules)
    result = filter_candidates(candidates, knowledge=kb, context=context)
    assert result.eligible_ids == () and result.excluded_ids == ("alpha", "beta", "gamma")
    assert all(item.status is RuleStatus.UNKNOWN for item in result.decisions)


def test_empty_batch_still_checks_release_and_evaluator_policy() -> None:
    kb, _, context = fixture()
    result = filter_candidates((), knowledge=kb, context=context)
    assert result.eligible_ids == result.excluded_ids == result.decisions == ()
    with pytest.raises(ValidationError):
        filter_candidates(
            (),
            knowledge=kb,
            context=context.model_copy(update={"evaluator_policy_version": "unsupported"}),
        )
    with pytest.raises(ValidationError):
        filter_candidates(
            (), knowledge=kb, context=revise_context(context, expected_kb_version="stale")
        )


def test_independent_digest_and_canonical_batch_order() -> None:
    kb, candidates, context = fixture()
    result = filter_candidates(candidates, knowledge=kb, context=context)
    assert kb.content_digest == unordered_digest(
        kb.model_dump(mode="json", by_alias=True, exclude={"content_digest"})
    )
    assert context.content_digest == unordered_digest(
        context.model_dump(mode="json", by_alias=True, exclude={"content_digest"})
    )
    for candidate, decision in zip(candidates, result.decisions, strict=True):
        assert candidate.content_digest == unordered_digest(
            candidate.model_dump(mode="json", by_alias=True, exclude={"content_digest"})
        )
        manifest = decision.resolution.manifest
        digest = unordered_digest(
            manifest.model_dump(
                mode="json",
                by_alias=True,
                exclude={"content_digest", "manifest_id", "manifest_version"},
            )
        )
        assert manifest.manifest_id == "manifest-" + digest
        assert manifest.manifest_version == "synthetic-manifest.v1:" + digest
    for permutation in permutations(candidates):
        assert filter_candidates(permutation, knowledge=kb, context=context) == result


@pytest.mark.parametrize("where", ["candidate", "context", "knowledge", "result"])
def test_strict_raw_json_ingress_and_nested_duplicate_member_rejection(where: str) -> None:
    kb, candidates, context = fixture()
    result = filter_candidates(candidates, knowledge=kb, context=context)
    model: Any = {
        "candidate": candidates[1],
        "context": context,
        "knowledge": kb,
        "result": result,
    }[where]
    raw = model.model_dump_json(by_alias=True)
    assert validate_contract_json(type(model), raw) == model
    assert validate_contract_json(TypeAdapter(type(model)), raw) == model
    key = "contentDigest" if where != "result" else "eligibleIds"
    value = model.model_dump(mode="json", by_alias=True)[key]
    duplicate = raw[:-1] + "," + json.dumps(key) + ":" + json.dumps(value) + "}"
    for target in (type(model), TypeAdapter(type(model))):
        with pytest.raises(ValidationError, match="duplicate JSON"):
            validate_contract_json(target, duplicate)


class AuditFloat(BaseModel):
    value: float


@pytest.mark.parametrize("sign", ["", "-"])
@pytest.mark.parametrize("target", [float, TypeAdapter(float), AuditFloat])
def test_strict_ingress_integer_to_float_overflow_rejected(sign: str, target: Any) -> None:
    raw = sign + "9" * 400
    payload = '{"value":' + raw + "}" if target is AuditFloat else raw
    with pytest.raises(ValidationError, match="nonfinite float"):
        validate_contract_json(target, payload)
    assert validate_contract_json(int, raw) == int(raw)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "1e9999"])
def test_nonfinite_raw_json_never_reaches_predicate(value: str) -> None:
    with pytest.raises(ValidationError):
        validate_contract_json(TypeAdapter(float), value)
    assert validate_contract_json(float, "0.0") == 0.0


def test_numeric_boundary_no_boolean_cast_or_tolerance() -> None:
    kb, candidates, context = fixture((audit_rule(value=0.3, operator=PredicateOperator.EQ),))
    candidate = revise_candidate(
        candidates[1],
        facts=(observation("beta", "synthetic_quantity", 0.1 + 0.2, unit=MeasurementUnit.MG),),
    )
    result = filter_candidates((candidate,), knowledge=kb, context=context)
    assert result.decisions[0].status is RuleStatus.FAIL
    measured = candidate.facts[0].observation.value
    assert isinstance(measured, float) and math.isfinite(measured)


def test_proof_records_cannot_be_removed_from_valid_graph_explanations() -> None:
    kb, candidates, context = fixture()
    result = filter_candidates((candidates[1],), knowledge=kb, context=context)
    decision = result.decisions[0]
    resolved = next(
        item
        for item in decision.resolution.facts
        if item.fact.fact_id == "synthetic_contains_target"
    )
    stripped = resolved.model_copy(update={"relations": ()})
    facts = tuple(
        stripped if item.fact.fact_id == "synthetic_contains_target" else item
        for item in decision.resolution.facts
    )
    explanations = tuple(
        item.model_copy(update={"facts": (stripped,)})
        if item.evaluation.rule.rule_id == "containment"
        else item
        for item in decision.explanations
    )
    forged = result.model_copy(
        update={
            "decisions": (
                decision.model_copy(
                    update={
                        "resolution": decision.resolution.model_copy(update={"facts": facts}),
                        "explanations": explanations,
                    }
                ),
            )
        }
    )
    with pytest.raises(ValidationError):
        FilterCandidatesResult.model_validate(forged)


@pytest.mark.parametrize("attribute", ["synthetic_contains_target", "synthetic_origin_target"])
def test_inventory_evidence_included_when_adapter_relies_on_inventory(attribute: str) -> None:
    rule = boolean_rule("proof", attribute, attribute == "synthetic_origin_target")
    kb, candidates, context = fixture((rule,))
    result = filter_candidates((candidates[1],), knowledge=kb, context=context)
    assert result.eligible_ids == ("beta",)
    proof_ids = {item.evidence_id for item in result.decisions[0].explanations[0].evidence}
    assert "beta-inventory-source" in proof_ids
    assert "beta-line-source-synthetic-source" in proof_ids


@pytest.mark.parametrize(
    "attribute",
    [
        "synthetic_contains_target",
        "synthetic_origin_target",
        "synthetic_dietary_target",
        "synthetic_cuisine_target",
    ],
)
@pytest.mark.parametrize(
    "corruption", ["omit_proof", "omit_evidence", "incomplete", "supplied_authority", "wrong_owner"]
)
def test_resolved_fact_proof_shape_cannot_be_corrupted(attribute: str, corruption: str) -> None:
    rule = boolean_rule("proof", attribute, attribute != "synthetic_contains_target")
    kb, candidates, context = fixture((rule,))
    resolution = resolve_rule_facts(candidates[1], knowledge=kb, context=context)
    record = next(item for item in resolution.facts if item.fact.fact_id == attribute)
    changes: dict[str, Any] = {}
    if corruption == "omit_proof":
        changes = {"relations": (), "taxonomy": None}
    elif corruption == "omit_evidence":
        changes = {
            "fact": record.fact.model_copy(
                update={
                    "observation": record.fact.observation.model_copy(
                        update={"evidence": (proof("unrelated-proof"),)}
                    )
                }
            )
        }
    elif corruption == "incomplete":
        changes = {
            "fact": record.fact.model_copy(
                update={
                    "observation": record.fact.observation.model_copy(update={"complete": False})
                }
            )
        }
    elif corruption == "wrong_owner":
        changes = {
            "fact": record.fact.model_copy(
                update={
                    "subject_kind": FactSubjectKind.PROFILE,
                    "subject_id": "audit-profile",
                    "subject_version": "profile-v12",
                    "catalogue_version": None,
                }
            )
        }
    else:
        changes = {
            "source": "SUPPLIED",
            "supplied_fact": record.fact,
            "relations": (),
            "taxonomy": None,
        }
    with pytest.raises(ValidationError):
        type(record).model_validate(record.model_copy(update=changes))


@pytest.mark.parametrize("attribute", ["synthetic_allergen_absent", "synthetic_clinically_safe"])
def test_supplied_safety_claims_cannot_fill_unsupported_adapters(attribute: str) -> None:
    kb, candidates, context = fixture((boolean_rule("safety", attribute, True),))
    candidate = revise_candidate(candidates[1], facts=(observation("beta", attribute, True),))
    result = filter_candidates((candidate,), knowledge=kb, context=context)
    assert result.decisions[0].status is RuleStatus.UNKNOWN and result.eligible_ids == ()


def test_empty_batch_and_failing_batch_do_not_hide_malformed_extra_fields() -> None:
    kb, candidates, context = fixture()
    with pytest.raises(ValidationError):
        filter_candidates(
            (), knowledge=kb, context=context.model_copy(update={"clientOverride": "safe"})
        )
    with pytest.raises(ValidationError):
        filter_candidates(
            (candidates[0], candidates[1].model_copy(update={"affirmative_resolution": True})),
            knowledge=kb,
            context=context,
        )


def test_malformed_units_and_basis_cannot_hide_behind_missing_condition() -> None:
    kb, candidates, context = fixture((audit_rule(),), condition=None)
    original = candidates[1].facts[0]
    for malformed in (
        original.model_copy(update={"measurement_basis": MeasurementBasis.PER_SERVING}),
        original.model_copy(update={"basis_reference": proof("unapproved-basis")}),
        original.model_copy(
            update={
                "observation": original.observation.model_copy(update={"unit": MeasurementUnit.G})
            }
        ),
    ):
        with pytest.raises(ValidationError):
            filter_candidates(
                (candidates[1].model_copy(update={"facts": (malformed,)}),),
                knowledge=kb,
                context=context,
            )


def test_raw_nested_alias_collision_duplicate_and_overflow_are_rejected() -> None:
    _, candidates, _ = fixture((audit_rule(),))
    raw = candidates[1].model_dump_json(by_alias=True)
    for corrupted in (
        raw.replace('"complete":true', '"complete":true,"complete":false', 1),
        raw.replace('"subjectId":"beta"', '"subjectId":"beta","subject_id":"beta"', 1),
        raw.replace('"value":13', '"value":1e9999', 1),
    ):
        assert corrupted != raw
        with pytest.raises(ValidationError):
            validate_contract_json(CandidateRecipeFacts, corrupted)


def test_architecture_dependency_direction_and_no_local_import_cycles() -> None:
    root = Path(__file__).parents[1] / "src" / "savora_ai"
    modules: dict[str, set[str]] = {}
    forbidden = ("savora_backend", "sqlalchemy", "fastapi", "psycopg", "asyncpg", "supabase")
    for path in root.rglob("*.py"):
        parts = path.relative_to(root.parent).with_suffix("").parts
        name = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        imported: set[str] = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported.update(item.name for item in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0, "Relative imports require explicit audit resolution"
                if node.module:
                    imported.add(node.module)
        assert not any(
            item == prefix or item.startswith(prefix + ".")
            for prefix in forbidden
            for item in imported
        )
        modules[name] = imported
    visited: set[str] = set()
    active: set[str] = set()

    def visit(name: str) -> None:
        assert name not in active, "Local AI module import cycle"
        if name in visited:
            return
        active.add(name)
        for dependency in modules[name]:
            if dependency in modules:
                visit(dependency)
        active.remove(name)
        visited.add(name)

    for name in modules:
        visit(name)
