"""Synthetic KB integrity fixtures; no clinical thresholds, real approvals or serving authority."""

import hashlib
import json
from enum import StrEnum
from itertools import permutations
from typing import Any

import pytest
from pydantic import ValidationError

from savora_ai.core.reasoning.graph import resolve_food_relations
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.taxonomy import resolve_taxonomy_assignment
from savora_ai.schemas.food_graph import (
    FoodEntity,
    FoodEntityKind,
    FoodGraphSnapshot,
    FoodRelation,
    FoodRelationType,
    KnowledgeCoverage,
    RelationAssertion,
    RelationResolutionStatus,
    TaxonomyAssignment,
    TaxonomyAssignmentAssertion,
    TaxonomyKind,
    TaxonomyTerm,
    TaxonomyTraversalMode,
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
    _KnowledgeContent,
)

# Independently declared synthetic fixture policy, not a clinical/workflow authority.
FIXTURE_SCOPES = {
    KnowledgeWorkflow.WEEKLY_PLAN: tuple(RuleScope),
    KnowledgeWorkflow.CRAVING_DISCOVERY: (RuleScope.PROFILE, RuleScope.RECIPE),
    KnowledgeWorkflow.PLANNED_SWAP: tuple(RuleScope),
}


def evidence(
    id_: str = "fixture-shared",
    environment: RuleEnvironment = RuleEnvironment.SYNTHETIC,
    **changes: Any,
) -> EvidenceReference:
    return EvidenceReference.model_validate(
        {
            "evidence_id": id_,
            "version": "source-v1",
            "source": "SYNTHETIC integrity fixture; labels are not real authority or approval",
            "locator": "urn:savora:synthetic:" + id_,
            "environment": environment,
        }
        | changes
    )


def rule(id_: str = "hard-recipe", **changes: Any) -> RuleDefinition:
    return RuleDefinition.model_validate(
        {
            "rule_id": id_,
            "version": "rule-v1",
            "scope": RuleScope.RECIPE,
            "severity": RuleSeverity.ABSOLUTE,
            "domain": RuleDomain.DIETARY,
            "attribute": "fixture_flag",
            "operator": PredicateOperator.EQ,
            "value": False,
            "required_facts": ("fixture_flag",),
            "applicability_reference": RuleReference(rule_id="app-" + id_, version="app-v1"),
            "evidence": (evidence(),),
            "rationale": "SYNTHETIC boolean declaration; no clinical or nutrition values",
            "lifecycle": RuleLifecycle.ACTIVE,
            "approval_status": ApprovalStatus.PENDING,
            "environment": RuleEnvironment.SYNTHETIC,
        }
        | changes
    )


def food_graph(environment: RuleEnvironment = RuleEnvironment.SYNTHETIC) -> FoodGraphSnapshot:
    ref = evidence(environment=environment)
    return FoodGraphSnapshot(
        graph_id="graph",
        version="graph-v1",
        catalogue_version="food-catalogue-v1",
        taxonomy_version="taxonomy-v1",
        environment=environment,
        entities=(
            FoodEntity(
                entity_id="i1",
                version="1",
                kind=FoodEntityKind.INGREDIENT,
                canonical_name="Synthetic origin",
                evidence=(ref,),
            ),
            FoodEntity(
                entity_id="i2",
                version="1",
                kind=FoodEntityKind.INGREDIENT,
                canonical_name="Synthetic derivative",
                evidence=(ref,),
            ),
            FoodEntity(
                entity_id="recipe",
                version="1",
                kind=FoodEntityKind.RECIPE_REFERENCE,
                canonical_name="Synthetic recipe",
                catalogue_reference="m1-recipe",
                evidence=(ref,),
            ),
        ),
        relations=(
            FoodRelation(
                relation_id="derived",
                version="1",
                relation_type=FoodRelationType.DERIVED_FROM,
                source_id="i2",
                target_id="i1",
                assertion=RelationAssertion.PRESENT,
                evidence=(ref,),
            ),
        ),
        coverage=(
            KnowledgeCoverage(
                coverage_id="outgoing",
                version="1",
                graph_id="graph",
                graph_version="graph-v1",
                catalogue_version="food-catalogue-v1",
                subject_id="i2",
                relation_type=FoodRelationType.DERIVED_FROM,
                complete=False,
                reason="SYNTHETIC gap",
                evidence=(ref,),
            ),
        ),
        taxonomy_terms=(
            TaxonomyTerm(
                term_id="indian",
                version="1",
                kind=TaxonomyKind.CUISINE,
                display_label="Synthetic Indian",
                evidence=(ref,),
            ),
            TaxonomyTerm(
                term_id="south",
                version="1",
                kind=TaxonomyKind.CUISINE,
                display_label="Synthetic South Indian",
                parent_ids=("indian",),
                evidence=(ref,),
            ),
        ),
        taxonomy_assignments=(
            TaxonomyAssignment(
                assignment_id="cuisine",
                version="1",
                subject_id="recipe",
                term_id="south",
                assertion=TaxonomyAssignmentAssertion.PRESENT,
                evidence=(ref,),
            ),
        ),
        evidence=(ref,),
    )


def content(
    rules: tuple[RuleDefinition, ...] | None = None,
    environment: RuleEnvironment = RuleEnvironment.SYNTHETIC,
    **changes: Any,
) -> dict[str, Any]:
    ref = evidence(environment=environment)
    definitions = (
        rules
        if rules is not None
        else (
            rule(evidence=(ref,), environment=environment),
            rule("soft", severity=RuleSeverity.SOFT, evidence=(ref,), environment=environment),
            rule(
                "archived",
                version="draft-v0",
                lifecycle=RuleLifecycle.DRAFT,
                evidence=(ref,),
                environment=environment,
            ),
            rule(
                "archived",
                version="retired-v0",
                lifecycle=RuleLifecycle.RETIRED,
                evidence=(ref,),
                environment=environment,
            ),
        )
    )
    graph = food_graph(environment)
    active = tuple(
        RuleReference(rule_id=r.rule_id, version=r.version)
        for r in definitions
        if r.lifecycle is RuleLifecycle.ACTIVE
    )
    keys = sorted(
        {
            (r.applicability_reference.rule_id, r.applicability_reference.version)
            for r in definitions
        }
    )
    descriptors = tuple(
        ApplicabilityDescriptor(
            reference=RuleReference(rule_id=id_, version=version),
            rule_references=tuple(
                RuleReference(rule_id=r.rule_id, version=r.version)
                for r in definitions
                if (r.applicability_reference.rule_id, r.applicability_reference.version)
                == (id_, version)
            ),
            required_context_facts=("fixture_context",),
            evidence=(ref,),
        )
        for id_, version in keys
    )
    bindings = {"kb_id": "kb", "kb_version": "kb-v1", "check_catalogue_version": "checks-v1"}
    catalogue = tuple(
        CheckCatalogueEntry(
            entry_id=f"entry-{workflow.value}-{scope.value}",
            version="1",
            **bindings,
            workflow=workflow,
            scope=scope,
            rule_references=tuple(
                RuleReference(rule_id=r.rule_id, version=r.version)
                for r in definitions
                if r.lifecycle is RuleLifecycle.ACTIVE
                and r.severity is RuleSeverity.ABSOLUTE
                and r.scope is scope
            ),
            evidence=(ref,),
        )
        for workflow, scopes in FIXTURE_SCOPES.items()
        for scope in scopes
    )
    coverage = tuple(
        RuleCatalogueCoverage(
            coverage_id=f"coverage-{entry.workflow.value}-{entry.scope.value}",
            version="1",
            **bindings,
            workflow=entry.workflow,
            scope=entry.scope,
            complete=True,
            reason="SYNTHETIC complete internal catalogue declaration",
            evidence=(ref,),
        )
        for entry in catalogue
    )
    return {
        "kb_id": "kb",
        "version": "kb-v1",
        "environment": environment,
        "graph_id": graph.graph_id,
        "graph_version": graph.version,
        "catalogue_version": graph.catalogue_version,
        "taxonomy_version": graph.taxonomy_version,
        "check_catalogue_version": "checks-v1",
        "graph": graph,
        "rules": definitions,
        "active_rules": active,
        "applicability_descriptors": descriptors,
        "check_catalogue": catalogue,
        "rule_catalogue_coverage": coverage,
        "evidence": (ref,),
    } | changes


def build(data: Any = None, **pins: Any) -> KnowledgeBaseSnapshot:
    return build_knowledge_snapshot(content() if data is None else data, **pins)


def record_ref(r: RuleDefinition) -> RuleReference:
    return RuleReference(rule_id=r.rule_id, version=r.version)


def forged(cls: type[StrEnum], token: str) -> StrEnum:
    instance = str.__new__(cls, token)
    instance._name_ = token
    instance._value_ = token
    return instance


def unchecked(record: Any, changes: dict[str, Any], mode: str) -> Any:
    return (
        record.model_copy(update=changes)
        if mode == "copy"
        else type(record).model_construct(**(vars(record) | changes))
    )


def reverse_collections(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: reverse_collections(item) for key, item in reversed(tuple(value.items()))}
    if isinstance(value, tuple):
        return tuple(reverse_collections(item) for item in reversed(value))
    return value


def independent_digest(data: dict[str, Any]) -> str:
    # Independently encode the JSON tree: object keys sorted and array children
    # encoded individually/sorted. Do not call production canonical helpers.
    def encode(value: Any) -> str:
        if isinstance(value, dict):
            return (
                "{"
                + ",".join(
                    json.dumps(key, ensure_ascii=True) + ":" + encode(value[key])
                    for key in sorted(value)
                )
                + "}"
            )
        if isinstance(value, list):
            return "[" + ",".join(sorted(encode(item) for item in value)) + "]"
        return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))

    return hashlib.sha256(encode(data).encode("utf-8")).hexdigest()


def trusted_pins(snapshot: KnowledgeBaseSnapshot) -> dict[str, Any]:
    return {
        "expected_digest": snapshot.content_digest,
        "expected_environment": snapshot.environment,
        "expected_kb_id": snapshot.kb_id,
        "expected_kb_version": snapshot.version,
        "expected_graph_id": snapshot.graph_id,
        "expected_graph_version": snapshot.graph_version,
        "expected_catalogue_version": snapshot.catalogue_version,
        "expected_taxonomy_version": snapshot.taxonomy_version,
        "expected_check_catalogue_version": snapshot.check_catalogue_version,
    }


def test_valid_release_embeds_exact_phase_one_rules_and_versions() -> None:
    data = content()
    snapshot = build(data)
    assert snapshot.rules == data["rules"]
    assert len(snapshot.content_digest) == 64
    assert snapshot.version == "kb-v1" and snapshot.graph_version == "graph-v1"
    assert (
        snapshot.catalogue_version == "food-catalogue-v1"
        and snapshot.taxonomy_version == "taxonomy-v1"
    )
    assert len(snapshot.check_catalogue) == 12 and len(snapshot.rule_catalogue_coverage) == 12
    assert {ref.rule_id for ref in snapshot.active_rules} == {"hard-recipe", "soft"}
    assert all(
        {ref.rule_id for ref in entry.rule_references} <= {"hard-recipe"}
        for entry in snapshot.check_catalogue
    )


def test_accepted_graph_preserves_direct_origin_and_taxonomy_resolution() -> None:
    graph = build().graph
    for mode in ("direct", "origin"):
        from savora_ai.schemas.food_graph import TraversalMode

        result = resolve_food_relations(
            graph,
            source_id="i2",
            target_id="i1",
            relation_type=FoodRelationType.DERIVED_FROM,
            traversal=TraversalMode.DIRECT if mode == "direct" else TraversalMode.ORIGIN_PATH,
        )
        assert result.status is RelationResolutionStatus.SUPPORTED
    result = resolve_taxonomy_assignment(
        graph,
        subject_id="recipe",
        term_id="indian",
        traversal=TaxonomyTraversalMode.CUISINE_PARENTS,
    )
    assert result.status is RelationResolutionStatus.SUPPORTED


@pytest.mark.parametrize("scope", list(RuleScope))
def test_every_active_hard_rule_is_required_in_each_synthetic_applicable_cell(
    scope: RuleScope,
) -> None:
    snapshot = build(content(rules=(rule(scope=scope),)))
    for entry in snapshot.check_catalogue:
        assert (
            entry.rule_references == (record_ref(snapshot.rules[0]),)
            if entry.scope is scope
            else entry.rule_references == ()
        )


def test_soft_and_informational_rules_never_become_mandatory_hard_checks() -> None:
    snapshot = build(
        content(
            rules=(
                rule(),
                rule("soft", severity=RuleSeverity.SOFT),
                rule("info", severity=RuleSeverity.INFORMATIONAL),
            )
        )
    )
    assert len(snapshot.active_rules) == 3
    assert all(
        all(ref.rule_id == "hard-recipe" for ref in entry.rule_references)
        for entry in snapshot.check_catalogue
    )


@pytest.mark.parametrize(
    "fault",
    [
        "active_omission",
        "definition_omission",
        "stale_active",
        "inactive_active",
        "duplicate_active",
    ],
)
def test_active_inventory_defects_are_rejected(fault: str) -> None:
    data = content()
    hard = data["rules"][0]
    if fault == "active_omission":
        data["active_rules"] = data["active_rules"][1:]
    elif fault == "definition_omission":
        data["rules"] = data["rules"][1:]
    elif fault == "stale_active":
        data["active_rules"] = (
            record_ref(hard).model_copy(update={"version": "stale"}),
            *data["active_rules"][1:],
        )
    elif fault == "inactive_active":
        data["active_rules"] = (*data["active_rules"], record_ref(data["rules"][2]))
    else:
        data["active_rules"] = (*data["active_rules"], data["active_rules"][0])
    with pytest.raises(ValidationError):
        build(data)


def test_simultaneously_active_versions_are_rejected_but_archived_versions_are_kept() -> None:
    with pytest.raises(ValidationError, match="simultaneously serving"):
        build(content(rules=(rule(), rule(version="rule-v2"))))
    assert len([r for r in build().rules if r.rule_id == "archived"]) == 2


def test_duplicate_rule_identity_and_content_is_rejected() -> None:
    data = content()
    data["rules"] = (*data["rules"], data["rules"][0])
    with pytest.raises(ValidationError, match="duplicate rule identity"):
        build(data)


@pytest.mark.parametrize("workflow", list(KnowledgeWorkflow))
def test_a_hard_rule_cannot_be_omitted_from_a_workflow_manifest(
    workflow: KnowledgeWorkflow,
) -> None:
    data = content()
    data["check_catalogue"] = tuple(
        entry.model_copy(update={"rule_references": ()})
        if entry.workflow is workflow and entry.scope is RuleScope.RECIPE
        else entry
        for entry in data["check_catalogue"]
    )
    with pytest.raises(ValidationError, match="omits a mandatory"):
        build(data)


@pytest.mark.parametrize(
    "fault",
    [
        "missing_entry",
        "duplicate_entry_id",
        "duplicate_cell",
        "stale_rule",
        "duplicate_rule_ref",
        "soft_check",
        "scope_mismatch",
        "unsupported_scope",
    ],
)
def test_expected_check_catalogue_defects_are_rejected(fault: str) -> None:
    data = content(
        rules=(
            rule(),
            rule("soft", severity=RuleSeverity.SOFT),
            rule("profile", scope=RuleScope.PROFILE),
        )
    )
    index = next(
        i
        for i, entry in enumerate(data["check_catalogue"])
        if entry.workflow is KnowledgeWorkflow.CRAVING_DISCOVERY and entry.scope is RuleScope.RECIPE
    )
    entry = data["check_catalogue"][index]
    if fault == "missing_entry":
        data["check_catalogue"] = (
            data["check_catalogue"][:index] + data["check_catalogue"][index + 1 :]
        )
    elif fault in ("duplicate_entry_id", "duplicate_cell"):
        data["check_catalogue"] = (
            *data["check_catalogue"],
            entry
            if fault == "duplicate_entry_id"
            else entry.model_copy(update={"entry_id": "other"}),
        )
    else:
        changes = {
            "stale_rule": {
                "rule_references": (RuleReference(rule_id="hard-recipe", version="stale"),)
            },
            "duplicate_rule_ref": {
                "rule_references": (*entry.rule_references, *entry.rule_references)
            },
            "soft_check": {"rule_references": (record_ref(data["rules"][1]),)},
            "scope_mismatch": {"rule_references": (record_ref(data["rules"][2]),)},
            "unsupported_scope": {"scope": RuleScope.DAY},
        }[fault]
        data["check_catalogue"] = tuple(
            entry.model_copy(update=changes) if i == index else old
            for i, old in enumerate(data["check_catalogue"])
        )
    with pytest.raises(ValidationError):
        build(data)


@pytest.mark.parametrize(
    "fault", ["missing", "incomplete", "duplicate_identity", "duplicate_scope", "unsupported_scope"]
)
def test_explicit_catalogue_coverage_is_mandatory(fault: str) -> None:
    data = content()
    coverage = data["rule_catalogue_coverage"][5]
    if fault == "missing":
        data["rule_catalogue_coverage"] = data["rule_catalogue_coverage"][:-1]
    elif fault == "incomplete":
        data["rule_catalogue_coverage"] = (
            coverage.model_copy(update={"complete": False}),
            *data["rule_catalogue_coverage"][:5],
            *data["rule_catalogue_coverage"][6:],
        )
    elif fault in ("duplicate_identity", "duplicate_scope"):
        data["rule_catalogue_coverage"] = (
            *data["rule_catalogue_coverage"],
            coverage
            if fault == "duplicate_identity"
            else coverage.model_copy(update={"coverage_id": "other"}),
        )
    else:
        data["rule_catalogue_coverage"] = tuple(
            c.model_copy(update={"scope": RuleScope.DAY})
            if c.workflow is KnowledgeWorkflow.CRAVING_DISCOVERY and c.scope is RuleScope.RECIPE
            else c
            for c in data["rule_catalogue_coverage"]
        )
    with pytest.raises(ValidationError):
        build(data)


@pytest.mark.parametrize("field", ["kb_id", "kb_version", "check_catalogue_version"])
@pytest.mark.parametrize("location", ["entry", "coverage"])
def test_check_records_bind_to_the_exact_release(field: str, location: str) -> None:
    data = content()
    key = "check_catalogue" if location == "entry" else "rule_catalogue_coverage"
    data[key] = (data[key][0].model_copy(update={field: "stale"}), *data[key][1:])
    with pytest.raises(ValidationError, match="release binding"):
        build(data)


@pytest.mark.parametrize(
    "field", ["graph_id", "graph_version", "catalogue_version", "taxonomy_version", "environment"]
)
def test_graph_release_bindings_cannot_be_relabelled(field: str) -> None:
    data = content()
    data[field] = RuleEnvironment.PRODUCTION if field == "environment" else "stale"
    with pytest.raises(ValidationError, match="binding mismatch"):
        build(data)


@pytest.mark.parametrize(
    "fault",
    [
        "missing_descriptor",
        "stale_rule_reference",
        "empty_facts",
        "duplicate_facts",
        "dangling_dependency",
        "stale_dependency",
        "self_dependency",
        "duplicate_dependency",
        "cycle",
        "multiple_versions",
    ],
)
def test_applicability_metadata_must_resolve_exactly_without_execution(fault: str) -> None:
    data = content()
    descriptors = data["applicability_descriptors"]
    first = descriptors[0]
    if fault == "missing_descriptor":
        data["applicability_descriptors"] = descriptors[1:]
    elif fault == "cycle":
        data["applicability_descriptors"] = (
            first.model_copy(update={"dependencies": (descriptors[1].reference,)}),
            descriptors[1].model_copy(update={"dependencies": (first.reference,)}),
            *descriptors[2:],
        )
    elif fault == "multiple_versions":
        data["applicability_descriptors"] = (
            *descriptors,
            first.model_copy(
                update={"reference": first.reference.model_copy(update={"version": "other"})}
            ),
        )
    else:
        updates = {
            "stale_rule_reference": {
                "rule_references": (RuleReference(rule_id="missing", version="1"),)
            },
            "empty_facts": {"required_context_facts": ()},
            "duplicate_facts": {"required_context_facts": ("context", "context")},
            "dangling_dependency": {
                "dependencies": (RuleReference(rule_id="missing", version="1"),)
            },
            "stale_dependency": {
                "dependencies": (descriptors[1].reference.model_copy(update={"version": "stale"}),)
            },
            "self_dependency": {"dependencies": (first.reference,)},
            "duplicate_dependency": {
                "dependencies": (descriptors[1].reference, descriptors[1].reference)
            },
        }[fault]
        data["applicability_descriptors"] = (first.model_copy(update=updates), *descriptors[1:])
    with pytest.raises(ValidationError):
        build(data)


def test_valid_applicability_dependencies_do_not_remove_required_checks() -> None:
    data = content()
    descriptors = data["applicability_descriptors"]
    data["applicability_descriptors"] = (
        descriptors[0].model_copy(update={"dependencies": (descriptors[1].reference,)}),
        *descriptors[1:],
    )
    snapshot = build(data)
    assert all(
        entry.rule_references
        for entry in snapshot.check_catalogue
        if entry.scope is RuleScope.RECIPE
    )
    assert not hasattr(snapshot.applicability_descriptors[0], "status")
    bad = descriptors[0].model_copy(update={"status": "NOT_APPLICABLE"})
    data["applicability_descriptors"] = (bad, *descriptors[1:])
    with pytest.raises(ValidationError, match="Extra inputs"):
        build(data)


@pytest.mark.parametrize("severity", list(RuleSeverity))
def test_serving_clinical_rules_require_approval_even_in_synthetic_releases(
    severity: RuleSeverity,
) -> None:
    clinical = rule("clinical", domain=RuleDomain.CLINICAL, severity=severity)
    with pytest.raises(ValidationError, match="clinical rules require"):
        build(content(rules=(clinical,)))
    approved = clinical.model_copy(
        update={
            "approval_status": ApprovalStatus.APPROVED,
            "approved_by": "SYNTHETIC reviewer; not a real approval",
            "approval_reference": evidence("synthetic-approval"),
        }
    )
    assert build(content(rules=(approved,))).rules[0].domain is RuleDomain.CLINICAL


@pytest.mark.parametrize("lifecycle", [RuleLifecycle.DRAFT, RuleLifecycle.RETIRED])
def test_inactive_clinical_definitions_cannot_enter_serving_catalogues(
    lifecycle: RuleLifecycle,
) -> None:
    clinical = rule("clinical", domain=RuleDomain.CLINICAL, lifecycle=lifecycle)
    data = content(rules=(rule(), clinical))
    assert build(data).rules[1].lifecycle is lifecycle
    data["active_rules"] = (*data["active_rules"], record_ref(clinical))
    with pytest.raises(ValidationError, match="ACTIVE rule"):
        build(data)


@pytest.mark.parametrize(
    "field,cls",
    [
        ("scope", RuleScope),
        ("severity", RuleSeverity),
        ("domain", RuleDomain),
        ("operator", PredicateOperator),
        ("lifecycle", RuleLifecycle),
        ("approval_status", ApprovalStatus),
        ("environment", RuleEnvironment),
        ("unit", MeasurementUnit),
    ],
)
@pytest.mark.parametrize("valid_token", [True, False])
@pytest.mark.parametrize("mode", ["copy", "construct"])
def test_fabricated_phase_one_rule_enums_are_rejected_before_semantic_checks(
    field: str, cls: type[StrEnum], valid_token: bool, mode: str
) -> None:
    data = content()
    member = next(iter(cls))
    value = forged(cls, member.value if valid_token else "UNDECLARED")
    data["rules"] = (unchecked(data["rules"][0], {field: value}, mode), *data["rules"][1:])
    with pytest.raises(ValidationError, match="canonical declared enum"):
        build(data)


@pytest.mark.parametrize(
    "location",
    [
        "entry_workflow",
        "entry_scope",
        "coverage_workflow",
        "graph_kind",
        "taxonomy_kind",
        "taxonomy_assertion",
        "graph_environment",
        "evidence_environment",
    ],
)
@pytest.mark.parametrize("valid_token", [True, False])
def test_fabricated_phase_two_and_catalogue_enums_are_rejected(
    location: str, valid_token: bool
) -> None:
    data = content()
    graph = data["graph"]
    token = "UNDECLARED"
    if location in ("entry_workflow", "entry_scope", "coverage_workflow"):
        key = "rule_catalogue_coverage" if location == "coverage_workflow" else "check_catalogue"
        field = "scope" if location == "entry_scope" else "workflow"
        genuine = getattr(data[key][0], field)
        data[key] = (
            data[key][0].model_copy(
                update={field: forged(type(genuine), genuine.value if valid_token else token)}
            ),
            *data[key][1:],
        )
    elif location == "graph_kind":
        bad = graph.entities[0].model_copy(
            update={"kind": forged(FoodEntityKind, "INGREDIENT" if valid_token else token)}
        )
        data["graph"] = graph.model_copy(update={"entities": (bad, *graph.entities[1:])})
    elif location == "taxonomy_kind":
        bad = graph.taxonomy_terms[0].model_copy(
            update={"kind": forged(TaxonomyKind, "CUISINE" if valid_token else token)}
        )
        data["graph"] = graph.model_copy(
            update={"taxonomy_terms": (bad, *graph.taxonomy_terms[1:])}
        )
    elif location == "taxonomy_assertion":
        bad = graph.taxonomy_assignments[0].model_copy(
            update={
                "assertion": forged(
                    TaxonomyAssignmentAssertion, "PRESENT" if valid_token else token
                )
            }
        )
        data["graph"] = graph.model_copy(update={"taxonomy_assignments": (bad,)})
    else:
        fake = forged(RuleEnvironment, "SYNTHETIC" if valid_token else token)
        data["graph"] = (
            graph.model_copy(update={"environment": fake})
            if location == "graph_environment"
            else graph.model_copy(
                update={"evidence": (evidence().model_copy(update={"environment": fake}),)}
            )
        )
    with pytest.raises(ValidationError, match="canonical declared enum"):
        build(data)


@pytest.mark.parametrize(
    "location", ["rule", "descriptor", "entry", "coverage", "graph", "taxonomy", "root"]
)
@pytest.mark.parametrize("field", ["source", "locator", "environment"])
def test_evidence_identity_is_consistent_across_the_entire_kb(location: str, field: str) -> None:
    data = content()
    metadata: dict[str, Any] = {
        field: RuleEnvironment.PRODUCTION if field == "environment" else "conflicting metadata"
    }
    ref = evidence(**metadata)
    keys = {
        "rule": "rules",
        "descriptor": "applicability_descriptors",
        "entry": "check_catalogue",
        "coverage": "rule_catalogue_coverage",
    }
    if location in keys:
        key = keys[location]
        data[key] = (data[key][0].model_copy(update={"evidence": (ref,)}), *data[key][1:])
    elif location == "graph":
        data["graph"] = data["graph"].model_copy(update={"evidence": (ref,)})
    elif location == "taxonomy":
        graph = data["graph"]
        data["graph"] = graph.model_copy(
            update={
                "taxonomy_terms": (
                    graph.taxonomy_terms[0].model_copy(update={"evidence": (ref,)}),
                    *graph.taxonomy_terms[1:],
                )
            }
        )
    else:
        data["evidence"] = (ref,)
    with pytest.raises(ValidationError):
        build(data)


@pytest.mark.parametrize(
    "location",
    ["root", "rule", "descriptor", "entry", "coverage", "graph", "reference", "evidence"],
)
def test_unexpected_fields_in_unchecked_copies_are_preserved_and_rejected(location: str) -> None:
    snapshot = build()
    data = snapshot.model_dump(exclude={"content_digest"})
    if location == "root":
        data["unexpected"] = True
    elif location == "reference":
        data["active_rules"] = (
            snapshot.active_rules[0].model_copy(update={"unexpected": True}),
            *snapshot.active_rules[1:],
        )
    elif location == "evidence":
        data["evidence"] = (snapshot.evidence[0].model_copy(update={"unexpected": True}),)
    elif location == "graph":
        data["graph"] = snapshot.graph.model_copy(update={"unexpected": True})
    else:
        key = {
            "rule": "rules",
            "descriptor": "applicability_descriptors",
            "entry": "check_catalogue",
            "coverage": "rule_catalogue_coverage",
        }[location]
        records = getattr(snapshot, key)
        data[key] = (records[0].model_copy(update={"unexpected": True}), *records[1:])
    with pytest.raises(ValidationError, match="Extra inputs"):
        build(data)


@pytest.mark.parametrize("mode", ["copy", "construct"])
@pytest.mark.parametrize(
    "fault",
    [
        "inactive_rule",
        "missing_facts",
        "omitted_manifest",
        "partial_coverage",
        "cuisine_conflict",
        "stale_graph",
    ],
)
def test_unchecked_snapshot_defects_never_bypass_public_build_validation(
    mode: str, fault: str
) -> None:
    snapshot = build()
    if fault in ("inactive_rule", "missing_facts"):
        updates = (
            {"lifecycle": RuleLifecycle.DRAFT}
            if fault == "inactive_rule"
            else {"required_facts": ()}
        )
        changes = {"rules": (unchecked(snapshot.rules[0], updates, mode), *snapshot.rules[1:])}
    elif fault == "omitted_manifest":
        changes = {
            "check_catalogue": tuple(
                entry.model_copy(update={"rule_references": ()})
                for entry in snapshot.check_catalogue
            )
        }
    elif fault == "partial_coverage":
        changes = {"rule_catalogue_coverage": snapshot.rule_catalogue_coverage[:-1]}
    elif fault == "stale_graph":
        changes = {"graph_version": "stale"}
    else:
        negative = TaxonomyAssignment(
            assignment_id="negative",
            version="1",
            subject_id="recipe",
            term_id="indian",
            assertion=TaxonomyAssignmentAssertion.ABSENT,
            evidence=(evidence(),),
        )
        changes = {
            "graph": unchecked(
                snapshot.graph,
                {"taxonomy_assignments": (*snapshot.graph.taxonomy_assignments, negative)},
                mode,
            )
        }
    with pytest.raises(ValidationError):
        build(unchecked(snapshot, changes, mode))


@pytest.mark.parametrize("location", ["root", "descriptor", "entry", "coverage"])
def test_required_evidence_cannot_be_empty(location: str) -> None:
    data = content()
    if location == "root":
        data["evidence"] = ()
    else:
        key = {
            "descriptor": "applicability_descriptors",
            "entry": "check_catalogue",
            "coverage": "rule_catalogue_coverage",
        }[location]
        data[key] = (data[key][0].model_copy(update={"evidence": ()}), *data[key][1:])
    with pytest.raises(ValidationError):
        build(data)


@pytest.mark.parametrize(
    "field",
    [
        "rules",
        "active_rules",
        "applicability_descriptors",
        "check_catalogue",
        "rule_catalogue_coverage",
        "evidence",
    ],
)
def test_python_collections_remain_strict_tuples(field: str) -> None:
    data = content()
    data[field] = list(data[field])
    with pytest.raises(ValidationError):
        build(data)


def test_cyclic_and_missing_constructed_content_are_validation_errors() -> None:
    cyclic: dict[str, Any] = {}
    cyclic["graph"] = cyclic
    with pytest.raises(ValidationError, match="cyclic or excessively deep"):
        build(cyclic)
    snapshot = build()
    values = vars(snapshot).copy()
    del values["graph"]
    with pytest.raises(ValidationError):
        build(KnowledgeBaseSnapshot.model_construct(**values))


def test_canonical_digest_matches_independent_encoder_and_all_order_permutations() -> None:
    snapshot = build()
    data = snapshot.model_dump(mode="json", by_alias=True, exclude={"content_digest"})
    assert snapshot.content_digest == independent_digest(data)
    raw = snapshot.model_dump(exclude={"content_digest"})
    assert build(reverse_collections(raw)).content_digest == snapshot.content_digest
    for ordering in permutations(snapshot.rules):
        assert build(raw | {"rules": ordering}).content_digest == snapshot.content_digest


@pytest.mark.parametrize(
    "group",
    [
        "graph_entity",
        "graph_relation",
        "taxonomy_parent",
        "rule",
        "rule_value",
        "applicability",
        "coverage",
        "entry",
        "evidence",
        "archive",
        "dependency",
    ],
)
def test_every_relevant_content_group_changes_the_digest(group: str) -> None:
    snapshot = build()
    data = snapshot.model_dump(exclude={"content_digest"})
    graph = snapshot.graph
    if group == "graph_entity":
        data["graph"] = graph.model_copy(
            update={
                "entities": (
                    graph.entities[0].model_copy(
                        update={"canonical_name": "Changed synthetic name"}
                    ),
                    *graph.entities[1:],
                )
            }
        )
    elif group == "graph_relation":
        data["graph"] = graph.model_copy(
            update={"relations": (graph.relations[0].model_copy(update={"version": "2"}),)}
        )
    elif group == "taxonomy_parent":
        data["graph"] = graph.model_copy(
            update={
                "taxonomy_terms": (
                    graph.taxonomy_terms[0],
                    graph.taxonomy_terms[1].model_copy(update={"parent_ids": ()}),
                )
            }
        )
    elif group in ("rule", "rule_value"):
        data["rules"] = (
            snapshot.rules[0].model_copy(
                update={"rationale": "Changed synthetic rationale"}
                if group == "rule"
                else {"value": True}
            ),
            *snapshot.rules[1:],
        )
    elif group == "applicability":
        data["applicability_descriptors"] = (
            snapshot.applicability_descriptors[0].model_copy(
                update={"required_context_facts": ("another_context",)}
            ),
            *snapshot.applicability_descriptors[1:],
        )
    elif group == "coverage":
        data["rule_catalogue_coverage"] = (
            snapshot.rule_catalogue_coverage[0].model_copy(
                update={"reason": "Changed declaration"}
            ),
            *snapshot.rule_catalogue_coverage[1:],
        )
    elif group == "entry":
        data["check_catalogue"] = (
            snapshot.check_catalogue[0].model_copy(update={"version": "2"}),
            *snapshot.check_catalogue[1:],
        )
    elif group == "evidence":
        data["evidence"] = (*snapshot.evidence, evidence("new-source"))
    elif group == "archive":
        data["rules"] = (
            *snapshot.rules[:2],
            snapshot.rules[2].model_copy(update={"lifecycle": RuleLifecycle.RETIRED}),
            snapshot.rules[3],
        )
    else:
        desc = snapshot.applicability_descriptors
        data["applicability_descriptors"] = (
            desc[0].model_copy(update={"dependencies": (desc[1].reference,)}),
            *desc[1:],
        )
    assert build(data).content_digest != snapshot.content_digest
    with pytest.raises(ValidationError, match=r"trusted expected.*digest"):
        build(data, expected_digest=snapshot.content_digest)


@pytest.mark.parametrize("invalid", ["0" * 64, "f" * 64, "x" * 64, "A" * 64, "short", None, 1])
def test_supplied_digest_cannot_be_tampered_or_silently_recomputed(invalid: Any) -> None:
    snapshot = build()
    data = snapshot.model_dump()
    data["content_digest"] = invalid
    with pytest.raises(ValidationError):
        build(data)


def test_digest_field_is_excluded_only_from_its_own_hash() -> None:
    snapshot = build()
    assert build(snapshot).content_digest == snapshot.content_digest
    assert (
        KnowledgeBaseSnapshot.model_validate_json(snapshot.model_dump_json(by_alias=True))
        == snapshot
    )
    with pytest.raises(ValidationError, match="digest mismatch"):
        KnowledgeBaseSnapshot.model_validate(snapshot.model_dump() | {"content_digest": "0" * 64})
    with pytest.raises(ValidationError, match="duplicate content digest aliases"):
        build(snapshot.model_dump() | {"contentDigest": snapshot.content_digest})


@pytest.mark.parametrize(
    "field", ["schema_version", "semantic_policy_version", "workflow_policy_version"]
)
def test_unknown_schema_and_policy_versions_are_not_accepted(field: str) -> None:
    data = content()
    data[field] = "unapproved-v2"
    with pytest.raises(ValidationError):
        build(data)


@pytest.mark.parametrize(
    "pin",
    [
        "expected_kb_id",
        "expected_kb_version",
        "expected_graph_id",
        "expected_graph_version",
        "expected_catalogue_version",
        "expected_taxonomy_version",
        "expected_check_catalogue_version",
    ],
)
def test_independently_trusted_release_pins_cannot_mismatch(pin: str) -> None:
    with pytest.raises(ValidationError, match="version pin mismatch"):
        build(**{pin: "stale"})


def test_trusted_digest_and_environment_are_checked() -> None:
    snapshot = build()
    assert build(snapshot, **trusted_pins(snapshot)) == snapshot
    with pytest.raises(ValidationError, match="environment pin mismatch"):
        build(snapshot, expected_environment=RuleEnvironment.PRODUCTION)
    with pytest.raises(ValidationError, match="canonical declared enum"):
        build(snapshot, expected_environment=forged(RuleEnvironment, "SYNTHETIC"))


def test_production_requires_trusted_pins_and_remains_blocked_pending_policy_approval() -> None:
    data = content(environment=RuleEnvironment.PRODUCTION)
    with pytest.raises(ValidationError, match="production requires"):
        build(data)
    validated = _KnowledgeContent.model_validate(data)
    digest = independent_digest(validated.model_dump(mode="json", by_alias=True))
    declaration = KnowledgeBaseSnapshot.model_validate(
        validated.model_dump() | {"content_digest": digest}
    )
    pins = trusted_pins(declaration)
    with pytest.raises(ValidationError, match="deferred pending approved"):
        build(declaration, **pins)
    for key in pins:
        with pytest.raises(ValidationError, match="production requires"):
            build(declaration, **(pins | {key: None}))


def test_synthetic_evidence_cannot_be_used_in_production_labelled_content() -> None:
    data = content(environment=RuleEnvironment.PRODUCTION)
    data["evidence"] = (evidence(),)
    with pytest.raises(ValidationError, match="environment"):
        build(data)


def test_self_supplied_catalogue_completeness_cannot_prove_external_inventory_completeness() -> (
    None
):
    original = build()
    empty = build(content(rules=()))
    assert empty.active_rules == () and all(
        entry.rule_references == () for entry in empty.check_catalogue
    )
    assert empty.content_digest != original.content_digest
    with pytest.raises(ValidationError, match=r"trusted expected.*digest"):
        build(empty, expected_digest=original.content_digest)
    # No eligibility/PASS declaration is produced even for a complete internal empty catalogue.
    assert not hasattr(empty, "status") and not hasattr(empty, "eligible")


@pytest.mark.parametrize(
    "field,token",
    [
        ("workflow", "UNSUPPORTED"),
        ("scope", "UNSUPPORTED"),
    ],
)
def test_unknown_catalogue_tokens_are_rejected_in_json(field: str, token: str) -> None:
    data = build().model_dump(mode="json", by_alias=True)
    data["checkCatalogue"][0][field] = token
    with pytest.raises(ValidationError):
        KnowledgeBaseSnapshot.model_validate_json(json.dumps(data))


def test_json_extra_fields_and_changed_content_cannot_bypass_integrity() -> None:
    data = build().model_dump(mode="json", by_alias=True)
    data["applicabilityDescriptors"][0]["unexpected"] = True
    with pytest.raises(ValidationError, match="Extra inputs"):
        KnowledgeBaseSnapshot.model_validate_json(json.dumps(data))
    del data["applicabilityDescriptors"][0]["unexpected"]
    data["rules"][0]["rationale"] = "Changed synthetic declaration"
    with pytest.raises(ValidationError, match="digest mismatch"):
        KnowledgeBaseSnapshot.model_validate_json(json.dumps(data))


@pytest.mark.parametrize(
    "field,cls",
    [
        ("scope", RuleScope),
        ("severity", RuleSeverity),
        ("domain", RuleDomain),
        ("lifecycle", RuleLifecycle),
        ("approval_status", ApprovalStatus),
        ("environment", RuleEnvironment),
    ],
)
def test_direct_snapshot_schema_also_rejects_fabricated_phase_one_enums(
    field: str,
    cls: type[StrEnum],
) -> None:
    snapshot = build()
    member = getattr(snapshot.rules[0], field)
    bad = snapshot.rules[0].model_copy(update={field: forged(cls, member.value)})
    with pytest.raises(ValidationError):
        KnowledgeBaseSnapshot.model_validate(
            snapshot.model_dump() | {"rules": (bad, *snapshot.rules[1:])}
        )


def test_canonical_digest_covers_unordered_rule_and_descriptor_fact_sets() -> None:
    extra = rule("additional", required_facts=("fixture_flag", "another_fact"))
    data = content(rules=(rule(), extra))
    descriptors = data["applicability_descriptors"]
    data["applicability_descriptors"] = tuple(
        d.model_copy(update={"required_context_facts": ("context_a", "context_b")})
        for d in descriptors
    )
    snapshot = build(data)
    reordered = reverse_collections(snapshot.model_dump(exclude={"content_digest"}))
    assert build(reordered).content_digest == snapshot.content_digest


def test_frozen_snapshot_nested_models_and_input_are_unchanged() -> None:
    data = content()
    before = data["graph"].model_dump_json()
    snapshot = build(data)
    assert data["graph"].model_dump_json() == before
    for model, field, value in (
        (snapshot, "version", "other"),
        (snapshot.rules[0], "value", True),
        (snapshot.applicability_descriptors[0], "required_context_facts", ()),
        (snapshot.check_catalogue[0], "rule_references", ()),
        (snapshot.rule_catalogue_coverage[0], "complete", False),
    ):
        with pytest.raises(ValidationError, match="frozen_instance"):
            setattr(model, field, value)


@pytest.mark.parametrize("field", ["source", "locator", "environment"])
def test_approval_evidence_identity_is_consistent_with_the_entire_kb(field: str) -> None:
    conflicting = evidence().model_copy(
        update={
            field: RuleEnvironment.PRODUCTION if field == "environment" else "conflicting metadata"
        }
    )
    approved = rule(
        domain=RuleDomain.CLINICAL,
        approval_status=ApprovalStatus.APPROVED,
        approved_by="SYNTHETIC reviewer; no real approval",
        approval_reference=conflicting,
    )
    # Phase 1 accepts the declaration; KB validation must compare its approval
    # identity with graph, rule, applicability and coverage evidence together.
    with pytest.raises(ValidationError, match="conflicting evidence metadata across KB"):
        build(content(rules=(approved,)))


@pytest.mark.parametrize("mutation", ["approved_by", "approval_source", "approval_version"])
def test_isolated_approval_mutations_change_digest_and_reject_previous_pin(mutation: str) -> None:
    approved = rule(
        domain=RuleDomain.CLINICAL,
        approval_status=ApprovalStatus.APPROVED,
        approved_by="SYNTHETIC reviewer A; no real approval",
        approval_reference=evidence("fictional-approval"),
    )
    original = build(content(rules=(approved,)))
    if mutation == "approved_by":
        changed = approved.model_copy(update={"approved_by": "SYNTHETIC reviewer B"})
        changed_field = "approved_by"
    else:
        assert approved.approval_reference is not None
        changed = approved.model_copy(
            update={
                "approval_reference": approved.approval_reference.model_copy(
                    update={"source": "Changed SYNTHETIC approval provenance"}
                    if mutation == "approval_source"
                    else {"version": "approval-v2"}
                )
            }
        )
        changed_field = "approval_reference"
    assert changed.model_dump(exclude={changed_field}) == approved.model_dump(
        exclude={changed_field}
    )
    data = content(rules=(changed,))
    rebuilt = build(data)
    assert rebuilt.content_digest != original.content_digest
    assert rebuilt.content_digest == independent_digest(
        rebuilt.model_dump(mode="json", by_alias=True, exclude={"content_digest"})
    )
    with pytest.raises(ValidationError, match="trusted expected KB content digest mismatch"):
        build(data, **trusted_pins(original))


def test_valid_synthetic_approval_metadata_survives_pins_and_json() -> None:
    approved = rule(
        domain=RuleDomain.CLINICAL,
        approval_status=ApprovalStatus.APPROVED,
        approved_by="SYNTHETIC reviewer; no real approval",
        approval_reference=evidence("fictional-approval"),
    )
    snapshot = build(content(rules=(approved,)))
    assert snapshot.rules[0] == approved
    reloaded = KnowledgeBaseSnapshot.model_validate_json(snapshot.model_dump_json(by_alias=True))
    assert build(reloaded, **trusted_pins(snapshot)) == snapshot
