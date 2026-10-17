"""Complete synthetic Phase 2 flows; no predicate execution or source authentication."""

import json
from itertools import permutations
from typing import Any

import pytest
from pydantic import ConfigDict, TypeAdapter, ValidationError
from test_knowledge_base import (
    content,
    evidence,
    forged,
    independent_digest,
    reverse_collections,
    rule,
    trusted_pins,
    unchecked,
)
from test_knowledge_contracts import (
    _CUSTOM_DICTS,
    _CUSTOM_SEQUENCES,
    _container_calls,
    _ExtraRuleDefinition,
)

from savora_ai import schemas
from savora_ai.core.reasoning.graph import resolve_food_relations
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.taxonomy import resolve_taxonomy_assignment
from savora_ai.schemas.food_graph import (
    FoodEntity,
    FoodEntityKind,
    FoodGraphSnapshot,
    FoodRelation,
    FoodRelationType,
    RelationAssertion,
    RelationResolution,
    RelationResolutionStatus,
    TaxonomyAssignment,
    TaxonomyAssignmentAssertion,
    TaxonomyKind,
    TaxonomyResolution,
    TaxonomyTerm,
    TaxonomyTraversalMode,
    TraversalMode,
)
from savora_ai.schemas.knowledge import (
    RuleDefinition,
    RuleDomain,
    RuleEnvironment,
    RuleLifecycle,
    RuleReference,
    RuleScope,
    RuleSeverity,
)
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot, KnowledgeWorkflow
from savora_ai.schemas.reasoning import (
    ApplicabilityStatus,
    FactObservation,
    RuleEvaluation,
    RuleStatus,
    RuleTrace,
    aggregate_hard_status,
    is_candidate_eligible,
)


def integrated_content() -> dict[str, Any]:
    # Reuse synthetic declarations/catalogue constructors, then extend their
    # graph with distinct path provenance and conservative dietary assignments.
    base = content()
    data = content(
        rules=(
            *base["rules"],
            rule("hard-recipe-extra"),
            rule("hard-profile", scope=RuleScope.PROFILE),
        )
    )
    graph = data["graph"]
    graph = type(graph).model_validate(
        graph.model_dump()
        | {
            "entities": (
                *graph.entities,
                FoodEntity(
                    entity_id="i3",
                    version="ingredient-v3",
                    kind=FoodEntityKind.INGREDIENT,
                    canonical_name="Synthetic second derivative",
                    evidence=(evidence(),),
                ),
                FoodEntity(
                    entity_id="isolated",
                    version="1",
                    kind=FoodEntityKind.INGREDIENT,
                    canonical_name="Synthetic ingredient with missing knowledge",
                    evidence=(evidence(),),
                ),
            ),
            "relations": (
                graph.relations[0].model_copy(update={"evidence": (evidence("origin-edge"),)}),
                FoodRelation(
                    relation_id="second-derived",
                    version="edge-v2",
                    relation_type=FoodRelationType.DERIVED_FROM,
                    source_id="i3",
                    target_id="i2",
                    assertion=RelationAssertion.PRESENT,
                    evidence=(evidence("derivative-edge"),),
                ),
                FoodRelation(
                    relation_id="contains",
                    version="contains-v1",
                    relation_type=FoodRelationType.CONTAINS,
                    source_id="recipe",
                    target_id="i3",
                    assertion=RelationAssertion.PRESENT,
                    evidence=(evidence("contains-edge"),),
                ),
                FoodRelation(
                    relation_id="negative-contains",
                    version="negative-v1",
                    relation_type=FoodRelationType.CONTAINS,
                    source_id="recipe",
                    target_id="isolated",
                    assertion=RelationAssertion.ABSENT,
                    evidence=(evidence("negative-edge"),),
                ),
            ),
            "taxonomy_terms": (
                *(
                    term.model_copy(update={"evidence": (evidence("term-" + term.term_id),)})
                    for term in graph.taxonomy_terms
                ),
                TaxonomyTerm(
                    term_id="dietary-parent",
                    version="diet-v1",
                    kind=TaxonomyKind.DIETARY_CATEGORY,
                    display_label="Synthetic dietary parent",
                    evidence=(evidence("dietary-parent-term"),),
                ),
                TaxonomyTerm(
                    term_id="dietary-child",
                    version="diet-v2",
                    kind=TaxonomyKind.DIETARY_CATEGORY,
                    display_label="Synthetic dietary child",
                    parent_ids=("dietary-parent",),
                    evidence=(evidence("dietary-child-term"),),
                ),
            ),
            "taxonomy_assignments": (
                graph.taxonomy_assignments[0].model_copy(
                    update={"evidence": (evidence("cuisine-assignment"),)}
                ),
                TaxonomyAssignment(
                    assignment_id="dietary-assignment",
                    version="assignment-v2",
                    subject_id="recipe",
                    term_id="dietary-child",
                    assertion=TaxonomyAssignmentAssertion.PRESENT,
                    evidence=(evidence("dietary-assignment-source"),),
                ),
            ),
        }
    )
    data["graph"] = graph
    return data


def observations(
    snapshot: KnowledgeBaseSnapshot,
) -> tuple[
    RelationResolution,
    RelationResolution,
    RelationResolution,
    TaxonomyResolution,
    TaxonomyResolution,
    tuple[Any, ...],
]:
    graph = snapshot.graph
    direct = resolve_food_relations(
        graph, source_id="i2", target_id="i1", relation_type=FoodRelationType.DERIVED_FROM
    )
    origin = resolve_food_relations(
        graph,
        source_id="i3",
        target_id="i1",
        relation_type=FoodRelationType.DERIVED_FROM,
        traversal=TraversalMode.ORIGIN_PATH,
        max_hops=2,
        max_visited=3,
    )
    absent = resolve_food_relations(
        graph, source_id="recipe", target_id="isolated", relation_type=FoodRelationType.CONTAINS
    )
    cuisine = resolve_taxonomy_assignment(
        graph,
        subject_id="recipe",
        term_id="indian",
        traversal=TaxonomyTraversalMode.CUISINE_PARENTS,
        max_hops=1,
        max_visited=2,
    )
    dietary = resolve_taxonomy_assignment(graph, subject_id="recipe", term_id="dietary-child")
    assert (
        direct.status
        is origin.status
        is cuisine.status
        is dietary.status
        is (RelationResolutionStatus.SUPPORTED)
    )
    assert absent.status is RelationResolutionStatus.VERIFIED_ABSENT
    assert direct.relation is not None
    assert (direct.relation.relation_id, direct.relation.version) == ("derived", "1")
    assert [(edge.relation_id, edge.version) for edge in origin.path] == [
        ("second-derived", "edge-v2"),
        ("derived", "1"),
    ]
    assert origin.reason_code == "ORIGIN_PATH_SUPPORTED" and not origin.limit_reached
    assert {ref.evidence_id for ref in origin.evidence} == {"derivative-edge", "origin-edge"}
    assert [term.term_id for term in cuisine.path] == ["south", "indian"]
    assert {ref.evidence_id for ref in cuisine.evidence} == {
        "cuisine-assignment",
        "term-south",
        "term-indian",
    }
    assert dietary.assignment is not None
    assert (dietary.assignment.assignment_id, dietary.assignment.version) == (
        "dietary-assignment",
        "assignment-v2",
    )
    assert {ref.evidence_id for ref in dietary.evidence} == {"dietary-assignment-source"}

    sources = {
        (ref.evidence_id, ref.version): ref
        for record in (
            graph,
            *graph.entities,
            *graph.relations,
            *graph.taxonomy_terms,
            *graph.taxonomy_assignments,
        )
        for ref in record.evidence
    }
    for result in (direct, origin, absent, cuisine, dietary):
        assert (
            result.graph_id,
            result.graph_version,
            result.catalogue_version,
            result.environment,
        ) == (
            snapshot.graph_id,
            snapshot.graph_version,
            snapshot.catalogue_version,
            RuleEnvironment.SYNTHETIC,
        )
        assert result.semantic_policy_version == graph.semantic_policy_version
        for ref in result.evidence:
            assert sources[(ref.evidence_id, ref.version)] == ref
        # Results also survive their own typed wire round trips.
        assert type(result).model_validate_json(result.model_dump_json(by_alias=True)) == result
    assert cuisine.taxonomy_version == dietary.taxonomy_version == snapshot.taxonomy_version

    checks = []
    for workflow in KnowledgeWorkflow:
        entry = next(
            item
            for item in snapshot.check_catalogue
            if item.workflow is workflow and item.scope is RuleScope.RECIPE
        )
        assert (entry.kb_id, entry.kb_version, entry.check_catalogue_version) == (
            snapshot.kb_id,
            snapshot.version,
            snapshot.check_catalogue_version,
        )
        identities = tuple(sorted((ref.rule_id, ref.version) for ref in entry.rule_references))
        assert identities == (("hard-recipe", "rule-v1"), ("hard-recipe-extra", "rule-v1"))
        assert all(type(ref) is RuleReference for ref in entry.rule_references)
        checks.append((workflow, identities))
    assert all(type(item) is RuleDefinition for item in snapshot.rules)
    assert not hasattr(snapshot, "eligible") and not hasattr(snapshot, "status")
    return direct, origin, absent, cuisine, dietary, tuple(checks)


def test_complete_release_pins_resolution_and_wire_reload() -> None:
    data = integrated_content()
    before = data["graph"].model_dump_json()
    snapshot = build_knowledge_snapshot(data)
    # These pins represent a previously selected synthetic test release.
    # Copying them from a payload would not authenticate a real source.
    pins = trusted_pins(snapshot)
    accepted = build_knowledge_snapshot(data, **pins)
    assert accepted == snapshot
    assert snapshot.content_digest == independent_digest(
        snapshot.model_dump(mode="json", by_alias=True, exclude={"content_digest"})
    )
    expected = observations(accepted)
    decoded = KnowledgeBaseSnapshot.model_validate_json(accepted.model_dump_json(by_alias=True))
    reloaded = build_knowledge_snapshot(decoded, **pins)
    assert reloaded == accepted and observations(reloaded) == expected
    assert data["graph"].model_dump_json() == before
    with pytest.raises(ValidationError, match="frozen_instance"):
        reloaded.graph.entities[0].canonical_name = "mutated"
    with pytest.raises(ValidationError, match="frozen_instance"):
        reloaded.check_catalogue[0].rule_references = ()


def test_record_reordering_preserves_digest_and_complete_resolution_results() -> None:
    original = build_knowledge_snapshot(integrated_content())
    pins = trusted_pins(original)
    expected = observations(original)
    raw = original.model_dump(exclude={"content_digest"})
    reordered = reverse_collections(raw)
    reversed_snapshot = build_knowledge_snapshot(reordered, **pins)
    assert observations(reversed_snapshot) == expected
    for relation_order in permutations(original.graph.relations):
        data = raw.copy()
        data["graph"] = original.graph.model_copy(update={"relations": relation_order})
        rebuilt = build_knowledge_snapshot(data, **pins)
        assert observations(rebuilt) == expected


def test_catalogue_to_phase_one_manifest_keeps_missing_evaluations_unknown() -> None:
    snapshot = build_knowledge_snapshot(integrated_content())
    observations(snapshot)  # Supported graph knowledge does not imply a predicate result.
    entry = next(
        item
        for item in snapshot.check_catalogue
        if item.workflow is KnowledgeWorkflow.CRAVING_DISCOVERY and item.scope is RuleScope.RECIPE
    )
    definitions = {(r.rule_id, r.version): r for r in snapshot.rules}
    trace = RuleTrace(
        candidate_id="m1-recipe",
        context_id="SYNTHETIC-context",
        manifest_id=entry.entry_id,
        manifest_version=snapshot.version + ":" + entry.version,
        required_checks=tuple(
            definitions[(ref.rule_id, ref.version)] for ref in entry.rule_references
        ),
    )
    assert schemas.RuleDefinition is RuleDefinition and schemas.RuleReference is RuleReference
    assert schemas.RuleTrace is RuleTrace and schemas.aggregate_hard_status is aggregate_hard_status
    assert aggregate_hard_status(trace) is RuleStatus.UNKNOWN
    assert not is_candidate_eligible(aggregate_hard_status(trace))


@pytest.mark.parametrize("mode", ["copy", "construct"])
@pytest.mark.parametrize(
    "fault",
    [
        "missing_active_rule",
        "missing_check_entry",
        "missing_mandatory_check",
        "wrong_rule_version",
        "wrong_rule_scope",
        "inactive_reference",
        "evidence_conflict",
        "unapproved_clinical",
        "duplicate_catalogue",
        "invalid_nested_copy",
        "forged_enum",
        "cuisine_contradiction",
        "missing_edge_evidence",
        "tampered_digest",
    ],
)
def test_invalid_releases_fail_before_graph_or_taxonomy_consumption(mode: str, fault: str) -> None:
    snapshot = build_knowledge_snapshot(integrated_content())
    graph = snapshot.graph
    if fault == "missing_active_rule":
        changes = {"active_rules": snapshot.active_rules[1:]}
        match = "every declared ACTIVE"
    elif fault == "missing_check_entry":
        changes = {"check_catalogue": snapshot.check_catalogue[1:]}
        match = "missing required"
    elif fault == "missing_mandatory_check":
        entry = snapshot.check_catalogue[1]
        changes = {
            "check_catalogue": (
                snapshot.check_catalogue[0],
                entry.model_copy(update={"rule_references": entry.rule_references[:1]}),
                *snapshot.check_catalogue[2:],
            )
        }
        match = "omits a mandatory active hard rule"
    elif fault == "wrong_rule_version":
        entry = snapshot.check_catalogue[1]
        wrong = entry.rule_references[0].model_copy(update={"version": "stale"})
        changes = {
            "check_catalogue": (
                snapshot.check_catalogue[0],
                entry.model_copy(update={"rule_references": (wrong, *entry.rule_references[1:])}),
                *snapshot.check_catalogue[2:],
            )
        }
        match = "exact ACTIVE ABSOLUTE"
    elif fault == "wrong_rule_scope":
        changes = {
            "rules": (
                snapshot.rules[0].model_copy(update={"scope": RuleScope.WEEK}),
                *snapshot.rules[1:],
            )
        }
        match = "scope"
    elif fault == "inactive_reference":
        archived = next(r for r in snapshot.rules if r.lifecycle is RuleLifecycle.RETIRED)
        changes = {
            "active_rules": (
                *snapshot.active_rules,
                RuleReference(rule_id=archived.rule_id, version=archived.version),
            )
        }
        match = "ACTIVE rule definitions"
    elif fault == "evidence_conflict":
        changes = {
            "evidence": (snapshot.evidence[0].model_copy(update={"locator": "urn:conflict"}),)
        }
        match = "conflicting evidence metadata"
    elif fault == "unapproved_clinical":
        changes = {
            "rules": (
                snapshot.rules[0].model_copy(update={"domain": RuleDomain.CLINICAL}),
                *snapshot.rules[1:],
            )
        }
        match = "clinical rules require"
    elif fault == "duplicate_catalogue":
        recipe = next(item for item in graph.entities if item.entity_id == "recipe")
        duplicate = recipe.model_copy(update={"entity_id": "recipe-alias", "version": "other"})
        changes = {"graph": graph.model_copy(update={"entities": (*graph.entities, duplicate)})}
        match = "duplicate catalogue binding"
    elif fault == "invalid_nested_copy":
        edge = graph.relations[0].model_copy(
            update={
                "qualifiers": (
                    graph.relations[0].qualifiers.model_copy(update={"unexpected": True})
                )
            }
        )
        changes = {"graph": graph.model_copy(update={"relations": (edge, *graph.relations[1:])})}
        match = "Extra inputs"
    elif fault == "forged_enum":
        edge = graph.relations[0].model_copy(
            update={"relation_type": forged(FoodRelationType, "DERIVED_FROM")}
        )
        changes = {"graph": graph.model_copy(update={"relations": (edge, *graph.relations[1:])})}
        match = "canonical declared enum"
    elif fault == "cuisine_contradiction":
        negative = TaxonomyAssignment(
            assignment_id="contradiction",
            version="1",
            subject_id="recipe",
            term_id="indian",
            assertion=TaxonomyAssignmentAssertion.ABSENT,
            evidence=(evidence(),),
        )
        changes = {
            "graph": graph.model_copy(
                update={"taxonomy_assignments": (*graph.taxonomy_assignments, negative)}
            )
        }
        match = "contradictory cuisine ancestry"
    elif fault == "missing_edge_evidence":
        edge = graph.relations[0].model_copy(update={"evidence": ()})
        changes = {"graph": graph.model_copy(update={"relations": (edge, *graph.relations[1:])})}
        match = "require evidence"
    else:
        changes = {"content_digest": "0" * 64}
        match = "digest mismatch"
    with pytest.raises(ValidationError, match=match):
        accepted = build_knowledge_snapshot(unchecked(snapshot, changes, mode))
        observations(accepted)


@pytest.mark.parametrize(
    "query", ["missing_edge", "missing_entity", "limited_origin", "mixed_path"]
)
def test_valid_incomplete_food_knowledge_remains_unknown(query: str) -> None:
    snapshot = build_knowledge_snapshot(integrated_content())
    inputs: dict[str, Any] = {
        "source_id": "i3",
        "target_id": "i1",
        "relation_type": FoodRelationType.DERIVED_FROM,
    }
    if query == "missing_entity":
        inputs["target_id"] = "unknown-entity"
    elif query == "limited_origin":
        inputs.update(traversal=TraversalMode.ORIGIN_PATH, max_hops=1)
    elif query == "mixed_path":
        inputs.update(source_id="recipe", relation_type=FoodRelationType.CONTAINS, target_id="i1")
    result = resolve_food_relations(snapshot.graph, **inputs)
    assert result.status is RelationResolutionStatus.UNKNOWN
    assert result.relation is None and result.path == ()
    assert result.limit_reached is (query == "limited_origin")
    assert (
        result.reason_code
        == {
            "missing_edge": "NO_DIRECT_ASSERTION",
            "missing_entity": "MISSING_ENTITY",
            "limited_origin": "MAX_HOPS_REACHED",
            "mixed_path": "NO_DIRECT_ASSERTION",
        }[query]
    )


@pytest.mark.parametrize("query", ["missing_subject", "missing_term", "dietary_parent"])
def test_valid_incomplete_taxonomy_knowledge_remains_unknown(query: str) -> None:
    snapshot = build_knowledge_snapshot(integrated_content())
    result = resolve_taxonomy_assignment(
        snapshot.graph,
        subject_id="missing" if query == "missing_subject" else "recipe",
        term_id="missing" if query == "missing_term" else "dietary-parent",
        traversal=TaxonomyTraversalMode.CUISINE_PARENTS,
    )
    assert result.status is RelationResolutionStatus.UNKNOWN
    assert result.assignment is None and result.path == () and not result.limit_reached
    assert (
        result.reason_code
        == {
            "missing_subject": "MISSING_SUBJECT",
            "missing_term": "MISSING_TERM",
            "dietary_parent": "UNSUPPORTED_HIERARCHY",
        }[query]
    )


def test_production_release_cannot_enter_the_integrated_flow() -> None:
    with pytest.raises(ValidationError, match="production requires trusted"):
        accepted = build_knowledge_snapshot(content(environment=RuleEnvironment.PRODUCTION))
        observations(accepted)


@pytest.mark.parametrize("mode", ["copy", "construct"])
def test_accepted_kb_cannot_hide_an_extra_hard_fail_with_counterfeit_severity(mode: str) -> None:
    snapshot = build_knowledge_snapshot(integrated_content())
    entry = next(
        item
        for item in snapshot.check_catalogue
        if item.workflow is KnowledgeWorkflow.CRAVING_DISCOVERY and item.scope is RuleScope.RECIPE
    )
    definitions = {(r.rule_id, r.version): r for r in snapshot.rules}
    required = tuple(definitions[(ref.rule_id, ref.version)] for ref in entry.rule_references)
    # Explicit synthetic declarations exercise aggregation only; no predicate runs.
    results = tuple(
        RuleEvaluation(
            rule=definition,
            applicability=ApplicabilityStatus.APPLICABLE,
            applicability_evidence=definition.evidence,
            facts=(
                FactObservation(
                    fact_id=definition.attribute,
                    value=False,
                    complete=True,
                    evidence=definition.evidence,
                ),
            ),
            status=RuleStatus.PASS,
            reason="SYNTHETIC declared result; no predicate execution",
        )
        for definition in required
    )
    trace = RuleTrace(
        candidate_id="m1-recipe",
        context_id="SYNTHETIC-context",
        manifest_id=entry.entry_id,
        manifest_version=snapshot.version + ":" + entry.version,
        required_checks=required,
        evaluations=results,
    )
    assert aggregate_hard_status(trace) is RuleStatus.PASS
    extra = next(r for r in snapshot.rules if r.rule_id == "hard-profile")
    failed = results[0].model_copy(update={"rule": extra, "status": RuleStatus.FAIL})
    with pytest.raises(ValidationError, match="hard evaluation is absent from required manifest"):
        aggregate_hard_status(trace.model_copy(update={"evaluations": (*results, failed)}))
    fake = forged(type(extra.severity), extra.severity.value)
    invalid_rule = unchecked(extra, {"severity": fake}, mode)
    invalid_evaluation = unchecked(failed, {"rule": invalid_rule}, mode)
    invalid_trace = unchecked(trace, {"evaluations": (*results, invalid_evaluation)}, mode)
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        is_candidate_eligible(aggregate_hard_status(invalid_trace))
    assert invalid_rule.severity is fake
    assert build_knowledge_snapshot(snapshot, **trusted_pins(snapshot)) == snapshot


def _declared_catalogue_trace(
    snapshot: KnowledgeBaseSnapshot,
    *,
    workflow: KnowledgeWorkflow = KnowledgeWorkflow.CRAVING_DISCOVERY,
    scope: RuleScope = RuleScope.RECIPE,
    first_status: RuleStatus = RuleStatus.PASS,
    omit_first: bool = False,
) -> RuleTrace:
    """Test-only composition; no trusted runtime manifest factory or evaluator exists."""
    entry = next(
        item
        for item in snapshot.check_catalogue
        if item.workflow is workflow and item.scope is scope
    )
    definitions = {(r.rule_id, r.version): r for r in snapshot.rules}
    required = tuple(definitions[(ref.rule_id, ref.version)] for ref in entry.rule_references)
    results = []
    for index, definition in enumerate(required):
        status = first_status if index == 0 else RuleStatus.PASS
        results.append(
            RuleEvaluation(
                rule=definition,
                applicability=ApplicabilityStatus.APPLICABLE,
                applicability_evidence=definition.evidence,
                facts=(
                    FactObservation(
                        fact_id=definition.attribute,
                        value=None if status is RuleStatus.UNKNOWN else status is RuleStatus.FAIL,
                        complete=status is not RuleStatus.UNKNOWN,
                        evidence=definition.evidence,
                    ),
                ),
                status=status,
                reason="SYNTHETIC declared outcome; test composition only",
            )
        )
    return RuleTrace(
        candidate_id="m1-recipe",
        context_id="SYNTHETIC test-only context",
        manifest_id=entry.entry_id,
        manifest_version=snapshot.version + ":" + entry.version,
        required_checks=required,
        evaluations=tuple(results[1:] if omit_first else results),
    )


@pytest.mark.parametrize(
    "workflow,scope",
    [
        (workflow, scope)
        for workflow, scopes in (
            (KnowledgeWorkflow.WEEKLY_PLAN, tuple(RuleScope)),
            (KnowledgeWorkflow.CRAVING_DISCOVERY, (RuleScope.PROFILE, RuleScope.RECIPE)),
            (KnowledgeWorkflow.PLANNED_SWAP, tuple(RuleScope)),
        )
        for scope in scopes
    ],
)
@pytest.mark.parametrize("scenario", ["pass", "fail", "unknown", "missing"])
def test_every_catalogue_cell_composes_exact_phase_one_declared_outcomes(
    workflow: KnowledgeWorkflow, scope: RuleScope, scenario: str
) -> None:
    snapshot = build_knowledge_snapshot(integrated_content())
    observations(snapshot)
    status = {
        "pass": RuleStatus.PASS,
        "fail": RuleStatus.FAIL,
        "unknown": RuleStatus.UNKNOWN,
        "missing": RuleStatus.PASS,
    }[scenario]
    trace = _declared_catalogue_trace(
        snapshot,
        workflow=workflow,
        scope=scope,
        first_status=status,
        omit_first=scenario == "missing",
    )
    # Independent expected fixture identities, not a production inventory helper.
    expected_ids = {
        RuleScope.PROFILE: ("hard-profile",),
        RuleScope.RECIPE: ("hard-recipe", "hard-recipe-extra"),
        RuleScope.COMBINATION: (),
        RuleScope.DAY: (),
        RuleScope.WEEK: (),
    }[scope]
    assert sorted((r.rule_id, r.version) for r in trace.required_checks) == [
        (id_, "rule-v1") for id_ in expected_ids
    ]
    assert all(r.scope is scope for r in trace.required_checks)
    expected = (
        RuleStatus.UNKNOWN if not expected_ids or scenario in ("unknown", "missing") else status
    )
    assert aggregate_hard_status(trace) is expected
    assert is_candidate_eligible(expected) is (expected is RuleStatus.PASS)
    reloaded = RuleTrace.model_validate_json(trace.model_dump_json(by_alias=True))
    assert reloaded == trace and aggregate_hard_status(reloaded) is expected


def test_unknown_containment_and_missing_synthetic_fact_never_become_eligible() -> None:
    snapshot = build_knowledge_snapshot(integrated_content())
    gap = resolve_food_relations(
        snapshot.graph, source_id="recipe", target_id="i1", relation_type=FoodRelationType.CONTAINS
    )
    assert gap.status is RelationResolutionStatus.UNKNOWN
    # A future evaluator must propagate the gap. Here the outcome is explicitly
    # declared UNKNOWN to test compatibility; no ingredient/allergen inference runs.
    trace = _declared_catalogue_trace(snapshot, first_status=RuleStatus.UNKNOWN)
    assert trace.evaluations[0].facts[0].value is None
    assert aggregate_hard_status(trace) is RuleStatus.UNKNOWN
    assert not is_candidate_eligible(aggregate_hard_status(trace))
    false_pass = trace.evaluations[0].model_copy(update={"status": RuleStatus.PASS})
    invalid = trace.model_copy(update={"evaluations": (false_pass, *trace.evaluations[1:])})
    with pytest.raises(ValidationError, match="present and complete"):
        is_candidate_eligible(aggregate_hard_status(invalid))


@pytest.mark.parametrize("claim", ["reduced", "wrong_scope", "stale_manifest"])
def test_trace_manifest_authority_is_external_while_kb_catalogue_stays_complete(claim: str) -> None:
    snapshot = build_knowledge_snapshot(integrated_content())
    complete = _declared_catalogue_trace(snapshot)
    if claim == "reduced":
        claimed = complete.model_copy(
            update={
                "required_checks": complete.required_checks[:1],
                "evaluations": complete.evaluations[:1],
            }
        )
    elif claim == "wrong_scope":
        profile = _declared_catalogue_trace(snapshot, scope=RuleScope.PROFILE)
        claimed = profile.model_copy(
            update={
                "manifest_id": complete.manifest_id,
                "manifest_version": complete.manifest_version,
            }
        )
    else:
        stale = complete.required_checks[0].model_copy(update={"version": "stale-rule-version"})
        claimed = complete.model_copy(
            update={
                "required_checks": (stale, *complete.required_checks[1:]),
                "evaluations": (
                    complete.evaluations[0].model_copy(update={"rule": stale}),
                    *complete.evaluations[1:],
                ),
            }
        )
    # The aggregator has no KB/workflow/context authentication input. PASS binds
    # only to this supplied declaration, not to authoritative catalogue completeness.
    assert aggregate_hard_status(claimed) is RuleStatus.PASS
    assert claimed.manifest_id == complete.manifest_id
    assert claimed.required_checks != complete.required_checks
    entry = next(item for item in snapshot.check_catalogue if item.entry_id == complete.manifest_id)
    claimed_refs = tuple(
        RuleReference(rule_id=r.rule_id, version=r.version) for r in claimed.required_checks
    )
    assert claimed_refs != entry.rule_references
    invalid_entry = entry.model_copy(update={"rule_references": claimed_refs})
    data = snapshot.model_dump(exclude={"content_digest"})
    data["check_catalogue"] = tuple(
        invalid_entry if item.entry_id == entry.entry_id else item
        for item in snapshot.check_catalogue
    )
    with pytest.raises(ValidationError, match=r"mandatory active hard rule|stated scope"):
        build_knowledge_snapshot(data)
    assert build_knowledge_snapshot(snapshot, **trusted_pins(snapshot)) == snapshot


def test_active_kb_rule_version_cannot_be_replaced_in_a_phase_one_evaluation() -> None:
    snapshot = build_knowledge_snapshot(integrated_content())
    trace = _declared_catalogue_trace(snapshot)
    original = trace.evaluations[0]
    stale = original.rule.model_copy(update={"version": "stale-rule-version"})
    invalid = trace.model_copy(
        update={
            "evaluations": (original.model_copy(update={"rule": stale}), *trace.evaluations[1:])
        }
    )
    with pytest.raises(ValidationError, match="required rule evaluation version mismatch"):
        is_candidate_eligible(aggregate_hard_status(invalid))


def test_trace_rejects_conflicting_evidence_after_a_valid_kb_was_accepted() -> None:
    snapshot = build_knowledge_snapshot(integrated_content())
    trace = _declared_catalogue_trace(snapshot)
    first = trace.evaluations[0]
    observed = first.facts[0]
    contradictory = observed.evidence[0].model_copy(
        update={"source": "Conflicting SYNTHETIC source"}
    )
    changed = first.model_copy(
        update={"facts": (observed.model_copy(update={"evidence": (contradictory,)}),)}
    )
    invalid = trace.model_copy(update={"evaluations": (changed, *trace.evaluations[1:])})
    with pytest.raises(ValidationError, match="contradictory evidence provenance"):
        is_candidate_eligible(aggregate_hard_status(invalid))


class _ExtraFoodRelation(FoodRelation):
    model_config = ConfigDict(extra="allow", alias_generator=lambda name: "input_" + name)


class _ExtraTaxonomyAssignment(TaxonomyAssignment):
    model_config = ConfigDict(extra="allow", alias_generator=lambda name: "input_" + name)


class _ExtraKnowledgeSnapshot(KnowledgeBaseSnapshot):
    model_config = ConfigDict(extra="allow", alias_generator=lambda name: "input_" + name)


@pytest.mark.parametrize("mode", ["construct", "copy"])
@pytest.mark.parametrize("key_kind", ["field", "subclass_alias"])
@pytest.mark.parametrize("shadow_kind", ["opposite", "identical", "counterfeit"])
@pytest.mark.parametrize("attack", ["graph_supported", "graph_absent", "taxonomy", "kb"])
def test_release_boundaries_reject_colliding_dto_fields(
    mode: str, key_kind: str, shadow_kind: str, attack: str
) -> None:
    snapshot = build_knowledge_snapshot(content())
    if attack.startswith("graph"):
        original: Any = snapshot.graph.relations[0]
        subclass: Any = _ExtraFoodRelation
        field = "assertion"
        declared: Any = (
            RelationAssertion.ABSENT if attack == "graph_supported" else RelationAssertion.PRESENT
        )
        shadow: Any = (
            RelationAssertion.PRESENT if attack == "graph_supported" else RelationAssertion.ABSENT
        )
    elif attack == "taxonomy":
        original = snapshot.graph.taxonomy_assignments[0]
        subclass = _ExtraTaxonomyAssignment
        field = "assertion"
        declared = TaxonomyAssignmentAssertion.ABSENT
        shadow = TaxonomyAssignmentAssertion.PRESENT
    else:
        original = snapshot
        subclass = _ExtraKnowledgeSnapshot
        field = "content_digest"
        declared = "0" * 64
        shadow = snapshot.content_digest
    if shadow_kind == "identical":
        shadow = declared
    elif shadow_kind == "counterfeit":
        # Counterfeit enums hidden in extras must not replace declared assertions.
        shadow = (
            forged(type(declared), declared.value)
            if attack != "kb"
            else forged(RuleEnvironment, "SYNTHETIC")
        )
    data = {"input_" + name: value for name, value in vars(original).items()}
    data["input_" + field] = declared
    key = field if key_kind == "field" else "input_" + field
    if key_kind == "field":
        ambiguous = subclass.model_construct(**(data | {key: shadow}))
    else:
        ambiguous = subclass.model_construct(**data)
        object.__setattr__(ambiguous, "__pydantic_extra__", {key: shadow})
    if mode == "copy":
        ambiguous = ambiguous.model_copy()
    assert getattr(ambiguous, field) == declared
    assert ambiguous.model_extra == {key: shadow}

    # Validate the original DTO before Pydantic can normalize its extra fields.
    for validate in (
        type(original).model_validate,
        TypeAdapter(type(original)).validate_python,
        subclass.model_validate,
    ):
        with pytest.raises(ValidationError, match="colliding DTO"):
            validate(ambiguous)
    if attack.startswith("graph"):
        nested = snapshot.graph.model_copy(update={"relations": (ambiguous,)})
    elif attack == "taxonomy":
        nested = snapshot.graph.model_copy(update={"taxonomy_assignments": (ambiguous,)})
    else:
        nested = ambiguous
    target = FoodGraphSnapshot if attack != "kb" else KnowledgeBaseSnapshot
    for validate in (target.model_validate, TypeAdapter(target).validate_python):
        with pytest.raises(ValidationError, match="colliding DTO"):
            validate(nested)
    if attack != "kb":
        with pytest.raises(ValidationError, match="colliding DTO"):
            FoodGraphSnapshot(**vars(nested))
        bad_release = snapshot.model_copy(update={"graph": nested})
        with pytest.raises(ValidationError, match="colliding DTO"):
            KnowledgeBaseSnapshot.model_validate(bad_release)
        with pytest.raises(ValidationError, match="colliding DTO"):
            TypeAdapter(KnowledgeBaseSnapshot).validate_python(bad_release)
        with pytest.raises(ValidationError, match="colliding DTO"):
            build_knowledge_snapshot(bad_release, **trusted_pins(snapshot))
    with pytest.raises(ValidationError, match="colliding DTO"):
        if attack.startswith("graph"):
            resolve_food_relations(
                snapshot.graph.model_copy(update={"relations": (ambiguous,)}),
                source_id=original.source_id,
                target_id=original.target_id,
                relation_type=original.relation_type,
            )
        elif attack == "taxonomy":
            resolve_taxonomy_assignment(
                snapshot.graph.model_copy(update={"taxonomy_assignments": (ambiguous,)}),
                subject_id=original.subject_id,
                term_id=original.term_id,
            )
        else:
            build_knowledge_snapshot(ambiguous, **trusted_pins(snapshot))
    assert getattr(ambiguous, field) == declared
    assert ambiguous.model_extra == {key: shadow}


@pytest.mark.parametrize("mode", ["construct", "copy"])
def test_kb_inherited_camel_digest_alias_cannot_hide_invalid_digest(mode: str) -> None:
    snapshot = build_knowledge_snapshot(content())
    payload: dict[str, Any] = vars(snapshot) | {
        "content_digest": "0" * 64,
        "contentDigest": snapshot.content_digest,
    }
    ambiguous = _ExtraKnowledgeSnapshot.model_construct(**payload)
    if mode == "copy":
        ambiguous = ambiguous.model_copy()
    assert ambiguous.content_digest == "0" * 64
    with pytest.raises(ValidationError, match="colliding DTO"):
        build_knowledge_snapshot(ambiguous, **trusted_pins(snapshot))
    with pytest.raises(ValidationError, match="colliding DTO"):
        KnowledgeBaseSnapshot.model_validate(ambiguous)
    with pytest.raises(ValidationError, match="colliding DTO"):
        TypeAdapter(KnowledgeBaseSnapshot).validate_python(ambiguous)


@pytest.mark.parametrize("boundary", ["graph", "taxonomy", "kb"])
@pytest.mark.parametrize("unexpected", [False, True])
def test_release_boundaries_preserve_valid_subclasses_and_reject_unexpected_extras(
    boundary: str, unexpected: bool
) -> None:
    snapshot = build_knowledge_snapshot(content())
    if boundary == "graph":
        original: Any = snapshot.graph.relations[0]
        subclass: Any = _ExtraFoodRelation
    elif boundary == "taxonomy":
        original = snapshot.graph.taxonomy_assignments[0]
        subclass = _ExtraTaxonomyAssignment
    else:
        original = snapshot
        subclass = _ExtraKnowledgeSnapshot
    record = subclass.model_construct(
        **(vars(original) | ({"unexpected": "synthetic"} if unexpected else {}))
    )

    def invoke() -> Any:
        if boundary == "graph":
            return resolve_food_relations(
                snapshot.graph.model_copy(update={"relations": (record,)}),
                source_id=original.source_id,
                target_id=original.target_id,
                relation_type=original.relation_type,
            )
        if boundary == "taxonomy":
            return resolve_taxonomy_assignment(
                snapshot.graph.model_copy(update={"taxonomy_assignments": (record,)}),
                subject_id=original.subject_id,
                term_id=original.term_id,
            )
        return build_knowledge_snapshot(record, **trusted_pins(snapshot))

    if unexpected:
        with pytest.raises(ValidationError) as error:
            invoke()
        assert any(item["type"] == "extra_forbidden" for item in error.value.errors())
        with pytest.raises(ValidationError) as direct_error:
            type(original).model_validate(record)
        assert any(item["type"] == "extra_forbidden" for item in direct_error.value.errors())
    elif boundary == "kb":
        assert invoke() == snapshot
        assert KnowledgeBaseSnapshot.model_validate(record) == snapshot
    else:
        assert invoke().status is RelationResolutionStatus.SUPPORTED
        assert type(original).model_validate(record) == original


@pytest.mark.parametrize("location", ["relation", "assignment", "graph", "kb"])
@pytest.mark.parametrize("entry", ["json", "adapter_json"])
@pytest.mark.parametrize("same_value", [False, True])
def test_json_alias_collisions_cannot_be_lost_before_dto_validation(
    location: str, entry: str, same_value: bool
) -> None:
    snapshot = build_knowledge_snapshot(content())
    if location == "relation":
        record: Any = snapshot.graph.relations[0]
        target: Any = FoodRelation
        field = "relation_type"
    elif location == "assignment":
        record = snapshot.graph.taxonomy_assignments[0]
        target = TaxonomyAssignment
        field = "subject_id"
    elif location == "graph":
        record = snapshot.graph
        target = FoodGraphSnapshot
        field = "graph_id"
    else:
        record = snapshot
        target = KnowledgeBaseSnapshot
        field = "content_digest"
    payload = record.model_dump(mode="json", by_alias=True)
    alias = target.model_fields[field].alias
    assert alias != field and alias in payload
    payload[field] = payload[alias] if same_value else "UNDECLARED"
    wire = json.dumps(payload)
    with pytest.raises(ValidationError, match="colliding DTO"):
        if entry == "json":
            target.model_validate_json(wire)
        else:
            TypeAdapter(target).validate_json(wire)


@pytest.mark.parametrize("container", _CUSTOM_DICTS)
@pytest.mark.parametrize("storage", ["fields", "extras"])
@pytest.mark.parametrize("mode", ["construct", "copy"])
@pytest.mark.parametrize("same_value", [False, True])
@pytest.mark.parametrize(
    "attack", ["hard_fail", "graph_supported", "graph_absent", "taxonomy", "kb"]
)
def test_all_five_collision_attacks_reject_custom_storage_before_methods(
    container: Any, storage: str, mode: str, same_value: bool, attack: str
) -> None:
    snapshot = build_knowledge_snapshot(content())
    pins = trusted_pins(snapshot)
    assert len(pins) == 9
    assert build_knowledge_snapshot(snapshot, **pins) == snapshot
    declared_trace = _declared_catalogue_trace(snapshot)
    if attack == "hard_fail":
        original: Any = declared_trace.required_checks[0].model_copy(
            update={"rule_id": "extra-hard"}
        )
        subclass: Any = _ExtraRuleDefinition
        field = "severity"
        declared: Any = RuleSeverity.ABSOLUTE
        shadow: Any = RuleSeverity.SOFT
    elif attack.startswith("graph"):
        original = snapshot.graph.relations[0]
        subclass = _ExtraFoodRelation
        field = "assertion"
        declared = (
            RelationAssertion.ABSENT if attack == "graph_supported" else RelationAssertion.PRESENT
        )
        shadow = (
            RelationAssertion.PRESENT if attack == "graph_supported" else RelationAssertion.ABSENT
        )
    elif attack == "taxonomy":
        original = snapshot.graph.taxonomy_assignments[0]
        subclass = _ExtraTaxonomyAssignment
        field = "assertion"
        declared = TaxonomyAssignmentAssertion.ABSENT
        shadow = TaxonomyAssignmentAssertion.PRESENT
    else:
        original = snapshot
        subclass = _ExtraKnowledgeSnapshot
        field = "content_digest"
        declared = "0" * 64
        shadow = snapshot.content_digest
    malicious = subclass.model_construct(**(vars(original) | {field: declared}))
    if mode == "copy":
        malicious = malicious.model_copy()
    object.__setattr__(malicious, "__pydantic_extra__", {field: declared if same_value else shadow})
    if storage == "fields":
        object.__setattr__(malicious, "__dict__", container(vars(malicious)))
    else:
        object.__setattr__(malicious, "__pydantic_extra__", container(malicious.model_extra))
    _container_calls.clear()
    for validate in (type(original).model_validate, TypeAdapter(type(original)).validate_python):
        with pytest.raises(ValidationError, match="unsupported custom container subclass"):
            validate(malicious)
    if attack == "hard_fail":
        failed = declared_trace.evaluations[0].model_copy(
            update={"rule": malicious, "status": RuleStatus.FAIL}
        )
        nested: Any = declared_trace.model_copy(
            update={"evaluations": (*declared_trace.evaluations, failed)}
        )
        target: Any = RuleTrace
    elif attack.startswith("graph"):
        nested = snapshot.graph.model_copy(update={"relations": (malicious,)})
        target = FoodGraphSnapshot
    elif attack == "taxonomy":
        nested = snapshot.graph.model_copy(update={"taxonomy_assignments": (malicious,)})
        target = FoodGraphSnapshot
    else:
        nested = malicious
        target = KnowledgeBaseSnapshot
    for validate in (target.model_validate, TypeAdapter(target).validate_python):
        with pytest.raises(ValidationError, match="unsupported custom container subclass"):
            validate(nested)
    with pytest.raises(ValidationError, match="unsupported custom container subclass"):
        if attack == "hard_fail":
            aggregate_hard_status(nested)
        elif attack.startswith("graph"):
            resolve_food_relations(
                nested,
                source_id=original.source_id,
                target_id=original.target_id,
                relation_type=original.relation_type,
            )
        elif attack == "taxonomy":
            resolve_taxonomy_assignment(
                nested, subject_id=original.subject_id, term_id=original.term_id
            )
        else:
            build_knowledge_snapshot(nested, **pins)
    if attack in ("graph_supported", "graph_absent", "taxonomy"):
        invalid_release = snapshot.model_copy(update={"graph": nested})
        with pytest.raises(ValidationError, match="unsupported custom container subclass"):
            build_knowledge_snapshot(invalid_release, **pins)
    assert not _container_calls


@pytest.mark.parametrize("container", [*_CUSTOM_DICTS, *_CUSTOM_SEQUENCES])
@pytest.mark.parametrize("boundary", ["graph", "taxonomy", "kb"])
@pytest.mark.parametrize("mode", ["dict", "construct", "copy"])
def test_public_release_boundaries_reject_custom_nested_containers(
    container: Any, boundary: str, mode: str
) -> None:
    snapshot = build_knowledge_snapshot(content())
    graph = snapshot.graph
    data = vars(graph).copy()
    if container in _CUSTOM_DICTS:
        data["entities"] = (container(vars(graph.entities[0])), *graph.entities[1:])
    else:
        data["entities"] = container(graph.entities)
    nested: Any = data
    if mode == "construct":
        nested = FoodGraphSnapshot.model_construct(**data)
    elif mode == "copy":
        nested = graph.model_copy(update={"entities": data["entities"]})
    _container_calls.clear()
    for validate in (
        FoodGraphSnapshot.model_validate,
        TypeAdapter(FoodGraphSnapshot).validate_python,
    ):
        with pytest.raises(ValidationError, match="unsupported custom container subclass"):
            validate(nested)
    with pytest.raises(ValidationError, match="unsupported custom container subclass"):
        if boundary == "graph":
            resolve_food_relations(
                nested, source_id="i2", target_id="i1", relation_type=FoodRelationType.DERIVED_FROM
            )
        elif boundary == "taxonomy":
            resolve_taxonomy_assignment(nested, subject_id="recipe", term_id="south")
        else:
            build_knowledge_snapshot(
                snapshot.model_copy(update={"graph": nested}), **trusted_pins(snapshot)
            )
    assert not _container_calls


@pytest.mark.parametrize("container", _CUSTOM_DICTS)
def test_kb_builder_rejects_custom_content_with_all_nine_pins(container: Any) -> None:
    snapshot = build_knowledge_snapshot(content())
    pins = trusted_pins(snapshot)
    assert len(pins) == 9
    assert build_knowledge_snapshot(snapshot.model_dump(), **pins) == snapshot
    assert build_knowledge_snapshot(snapshot, **pins) == snapshot
    assert (
        build_knowledge_snapshot(
            KnowledgeBaseSnapshot.model_validate_json(snapshot.model_dump_json()), **pins
        )
        == snapshot
    )
    _container_calls.clear()
    with pytest.raises(ValidationError, match="unsupported custom container subclass"):
        build_knowledge_snapshot(container(snapshot.model_dump()), **pins)
    assert not _container_calls
