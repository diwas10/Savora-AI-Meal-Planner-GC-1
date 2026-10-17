"""Independent synthetic catalogue and manifest trust-boundary fixtures/tests."""

import hashlib
import json
from typing import Any

import pytest
from pydantic import ValidationError

from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.manifest import build_expected_check_manifest
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    FactSubjectKind,
    IngredientCoverage,
    MeasurementBasis,
    RuleContext,
    VersionedFact,
    validate_contract_json,
)
from savora_ai.schemas.filtering import ExpectedCheckManifest
from savora_ai.schemas.food_graph import FoodEntity, FoodEntityKind, FoodGraphSnapshot
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
from savora_ai.schemas.reasoning import FactObservation


def source(id_: str = "test-source", **changes: Any) -> EvidenceReference:
    return EvidenceReference.model_validate(
        {
            "evidence_id": id_,
            "version": "1",
            "source": "SYNTHETIC only; no clinical meaning",
            "locator": "urn:synthetic:" + id_,
            "environment": RuleEnvironment.SYNTHETIC,
        }
        | changes
    )


def definition(id_: str = "recipe-check", **changes: Any) -> RuleDefinition:
    return RuleDefinition.model_validate(
        {
            "rule_id": id_,
            "version": "1",
            "scope": RuleScope.RECIPE,
            "severity": RuleSeverity.ABSOLUTE,
            "domain": RuleDomain.DIETARY,
            "attribute": "synthetic_flag",
            "operator": PredicateOperator.EQ,
            "value": False,
            "required_facts": ("synthetic_flag",),
            "applicability_reference": RuleReference(
                rule_id="synthetic-context-enabled", version="1"
            ),
            "evidence": (source(),),
            "rationale": "Synthetic compliance fixture",
            "lifecycle": RuleLifecycle.ACTIVE,
            "approval_status": ApprovalStatus.APPROVED,
            "approved_by": "synthetic-reviewer",
            "approval_reference": source("test-approval"),
            "environment": RuleEnvironment.SYNTHETIC,
        }
        | changes
    )


def descriptor(
    id_: str = "synthetic-context-enabled",
    rules: tuple[RuleDefinition, ...] = (),
    **changes: Any,
) -> ApplicabilityDescriptor:
    name = {
        "synthetic-context-enabled": "synthetic_context_enabled",
        "synthetic-context-guard": "synthetic_context_guard",
        "synthetic-profile-enabled": "synthetic_profile_enabled",
    }.get(id_, "synthetic_context_enabled")
    return ApplicabilityDescriptor.model_validate(
        {
            "reference": RuleReference(rule_id=id_, version="1"),
            "rule_references": tuple(
                RuleReference(rule_id=r.rule_id, version=r.version)
                for r in rules
                if r.applicability_reference.rule_id == id_
            ),
            "required_context_facts": (name,),
            "evidence": (source("app-" + id_),),
        }
        | changes
    )


def release_content(
    rules: tuple[RuleDefinition, ...] | None = None,
    descriptors: tuple[ApplicabilityDescriptor, ...] | None = None,
) -> dict[str, Any]:
    rules = (definition(),) if rules is None else rules
    entity = FoodEntity(
        entity_id="graph-recipe",
        version="graph-entity-v2",
        kind=FoodEntityKind.RECIPE_REFERENCE,
        canonical_name="Synthetic",
        catalogue_reference="recipe",
        evidence=(source(),),
    )
    graph = FoodGraphSnapshot(
        graph_id="graph",
        version="graph-v1",
        catalogue_version="catalogue-v1",
        environment=RuleEnvironment.SYNTHETIC,
        entities=(entity,),
        relations=(),
        evidence=(source(),),
    )
    if descriptors is None:
        descriptors = tuple(
            descriptor(id_, rules)
            for id_ in sorted({r.applicability_reference.rule_id for r in rules})
        )
    entries = tuple(
        CheckCatalogueEntry(
            entry_id=f"entry-{workflow.value}-{scope.value}",
            version="cell-v1",
            kb_id="kb",
            kb_version="kb-v1",
            check_catalogue_version="checks-v1",
            workflow=workflow,
            scope=scope,
            rule_references=tuple(
                RuleReference(rule_id=r.rule_id, version=r.version)
                for r in rules
                if r.scope is scope
                and r.lifecycle is RuleLifecycle.ACTIVE
                and r.severity is RuleSeverity.ABSOLUTE
            ),
            evidence=(source(),),
        )
        for workflow in KnowledgeWorkflow
        for scope in (
            (RuleScope.PROFILE, RuleScope.RECIPE)
            if workflow is KnowledgeWorkflow.CRAVING_DISCOVERY
            else (
                RuleScope.PROFILE,
                RuleScope.RECIPE,
                RuleScope.COMBINATION,
                RuleScope.DAY,
                RuleScope.WEEK,
            )
        )
    )
    coverage = tuple(
        RuleCatalogueCoverage(
            coverage_id="coverage-" + e.entry_id,
            version="coverage-v1",
            kb_id="kb",
            kb_version="kb-v1",
            check_catalogue_version="checks-v1",
            workflow=e.workflow,
            scope=e.scope,
            complete=True,
            reason="Synthetic complete internal catalogue",
            evidence=(source(),),
        )
        for e in entries
    )
    return {
        "kb_id": "kb",
        "version": "kb-v1",
        "environment": RuleEnvironment.SYNTHETIC,
        "graph_id": "graph",
        "graph_version": "graph-v1",
        "catalogue_version": "catalogue-v1",
        "taxonomy_version": None,
        "check_catalogue_version": "checks-v1",
        "graph": graph,
        "rules": rules,
        "active_rules": tuple(
            RuleReference(rule_id=r.rule_id, version=r.version)
            for r in rules
            if r.lifecycle is RuleLifecycle.ACTIVE
        ),
        "applicability_descriptors": descriptors,
        "check_catalogue": entries,
        "rule_catalogue_coverage": coverage,
        "evidence": (source(),),
    }


def fact(
    name: str = "synthetic_flag",
    value: Any = False,
    *,
    complete: bool = True,
    subject: FactSubjectKind = FactSubjectKind.RECIPE,
    unit: MeasurementUnit | None = None,
    basis: MeasurementBasis | None = None,
    basis_source: EvidenceReference | None = None,
) -> VersionedFact:
    owner, version = {
        FactSubjectKind.RECIPE: ("recipe", "recipe-v1"),
        FactSubjectKind.PROFILE: ("profile", "profile-v1"),
        FactSubjectKind.CONTEXT: ("context", "context-v1"),
        FactSubjectKind.INGREDIENT: ("ingredient", "ingredient-v1"),
    }[subject]
    return VersionedFact(
        fact_id=name,
        version="fact-v1",
        subject_kind=subject,
        subject_id=owner,
        subject_version=version,
        catalogue_version="catalogue-v1"
        if subject in (FactSubjectKind.RECIPE, FactSubjectKind.INGREDIENT)
        else None,
        observation=FactObservation(
            fact_id=name,
            value=value,
            complete=complete,
            unit=unit,
            evidence=(source("observation-" + name),),
        ),
        measurement_basis=basis,
        basis_reference=basis_source,
        context_id="context" if subject is FactSubjectKind.CONTEXT else None,
        context_version="context-v1" if subject is FactSubjectKind.CONTEXT else None,
    )


def packet(
    rules: tuple[RuleDefinition, ...] | None = None,
    *,
    descriptors: tuple[ApplicabilityDescriptor, ...] | None = None,
    candidate_facts: tuple[VersionedFact, ...] | None = None,
    context_facts: tuple[VersionedFact, ...] | None = None,
    workflow: KnowledgeWorkflow = KnowledgeWorkflow.CRAVING_DISCOVERY,
) -> tuple[KnowledgeBaseSnapshot, CandidateRecipeFacts, RuleContext]:
    kb = build_knowledge_snapshot(release_content(rules, descriptors))
    candidate = CandidateRecipeFacts.build(
        {
            "recipe_id": "recipe",
            "recipe_version": "recipe-v1",
            "catalogue_version": "catalogue-v1",
            "graph_id": "graph",
            "graph_version": "graph-v1",
            "graph_recipe_entity_id": "graph-recipe",
            "graph_recipe_reference": kb.graph.entities[0],
            "snapshot_id": "candidate-snapshot",
            "snapshot_version": "snapshot-v1",
            "facts": (fact(),) if candidate_facts is None else candidate_facts,
            "ingredient_coverage": IngredientCoverage(
                coverage_id="ingredients",
                version="1",
                recipe_id="recipe",
                recipe_version="recipe-v1",
                catalogue_version="catalogue-v1",
                lines=(),
                inventory_complete=True,
                mapping_complete=True,
                subingredients_complete=True,
                gap_reasons=(),
                evidence=(source(),),
            ),
            "evidence": (source(),),
        }
    )
    context = RuleContext.build(
        {
            "context_id": "context",
            "version": "context-v1",
            "profile_id": "profile",
            "profile_version": "profile-v1",
            "workflow": workflow,
            "expected_kb_id": kb.kb_id,
            "expected_kb_version": kb.version,
            "expected_kb_digest": kb.content_digest,
            "expected_graph_id": kb.graph_id,
            "expected_graph_version": kb.graph_version,
            "expected_taxonomy_version": kb.taxonomy_version,
            "expected_catalogue_version": kb.catalogue_version,
            "expected_check_catalogue_version": kb.check_catalogue_version,
            "facts": (fact("synthetic_context_enabled", True, subject=FactSubjectKind.CONTEXT),)
            if context_facts is None
            else context_facts,
            "evidence": (source(),),
        }
    )
    return kb, candidate, context


def independent_hash(data: dict[str, Any]) -> str:
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

    return hashlib.sha256(encode(data).encode()).hexdigest()


def rehash_manifest(manifest: ExpectedCheckManifest, **changes: Any) -> ExpectedCheckManifest:
    wire = manifest.model_dump(mode="json", by_alias=True)
    for key in ("manifestId", "manifestVersion", "contentDigest"):
        del wire[key]
    wire.update(changes)
    digest = independent_hash(wire)
    return validate_contract_json(
        ExpectedCheckManifest,
        json.dumps(
            wire
            | {
                "manifestId": "manifest-" + digest,
                "manifestVersion": "synthetic-manifest.v1:" + digest,
                "contentDigest": digest,
            }
        ),
    )


def changed_candidate(candidate: CandidateRecipeFacts, **changes: Any) -> CandidateRecipeFacts:
    body: dict[str, Any] = candidate.model_dump(exclude={"content_digest"}) | changes
    return CandidateRecipeFacts.build(body)


def changed_context(context: RuleContext, **changes: Any) -> RuleContext:
    body: dict[str, Any] = context.model_dump(exclude={"content_digest"}) | changes
    return RuleContext.build(body)


@pytest.mark.parametrize("workflow", list(KnowledgeWorkflow))
def test_fixed_stage_retains_full_definitions_and_deferred_obligations(
    workflow: KnowledgeWorkflow,
) -> None:
    rules = tuple(
        definition(
            scope.value,
            scope=scope,
            attribute="synthetic_profile_flag" if scope is RuleScope.PROFILE else "synthetic_flag",
            required_facts=("synthetic_profile_flag",)
            if scope is RuleScope.PROFILE
            else ("synthetic_flag",),
        )
        for scope in RuleScope
    )
    kb, candidate, context = packet(rules, workflow=workflow)
    manifest = build_expected_check_manifest(kb, candidate, context)
    assert {r.scope for r in manifest.required_checks} == {RuleScope.PROFILE, RuleScope.RECIPE}
    expected = (
        set()
        if workflow is KnowledgeWorkflow.CRAVING_DISCOVERY
        else {RuleScope.COMBINATION, RuleScope.DAY, RuleScope.WEEK}
    )
    assert {r.scope for r in manifest.deferred_checks} == expected
    for rule in (*manifest.required_checks, *manifest.deferred_checks):
        assert rule == next(r for r in kb.rules if r.rule_id == rule.rule_id)
    assert manifest.kb_digest == kb.content_digest
    assert manifest.candidate_digest == candidate.content_digest
    assert manifest.context_digest == context.content_digest


def test_manifest_identity_independent_encoding_order_and_wire_roundtrip() -> None:
    kb, candidate, context = packet((definition("z"), definition("a")))
    manifest = build_expected_check_manifest(kb, candidate, context)
    wire = manifest.model_dump(mode="json", by_alias=True)
    body = {
        k: v for k, v in wire.items() if k not in ("contentDigest", "manifestId", "manifestVersion")
    }
    assert manifest.content_digest == independent_hash(body)
    assert rehash_manifest(manifest) == manifest
    assert (
        validate_contract_json(ExpectedCheckManifest, manifest.model_dump_json(by_alias=True))
        == manifest
    )
    reverse = build_knowledge_snapshot(
        kb.model_dump(exclude={"content_digest"})
        | {
            "rules": tuple(reversed(kb.rules)),
            "active_rules": tuple(reversed(kb.active_rules)),
            "check_catalogue": tuple(reversed(kb.check_catalogue)),
        }
    )
    assert build_expected_check_manifest(reverse, candidate, context) == manifest


@pytest.mark.parametrize(
    "field",
    [
        "expected_kb_id",
        "expected_kb_version",
        "expected_kb_digest",
        "expected_graph_id",
        "expected_graph_version",
        "expected_taxonomy_version",
        "expected_catalogue_version",
        "expected_check_catalogue_version",
    ],
)
def test_stale_context_release_expectations_rejected(field: str) -> None:
    kb, candidate, context = packet()
    changed = changed_context(
        context,
        **{
            field: "0" * 64 if field == "expected_kb_digest" else "stale",
        },
    )
    with pytest.raises(ValidationError):
        build_expected_check_manifest(kb, candidate, changed)


@pytest.mark.parametrize("field", ["graph_id", "graph_version", "catalogue_version"])
def test_candidate_release_mismatch(field: str) -> None:
    kb, candidate, context = packet()
    values = candidate.model_dump(exclude={"content_digest"})
    values[field] = "stale"
    if field == "catalogue_version":
        values["facts"] = ()
        values["ingredient_coverage"][field] = "stale"
    changed = CandidateRecipeFacts.build(values)
    with pytest.raises(ValidationError):
        build_expected_check_manifest(kb, changed, context)


@pytest.mark.parametrize("status", [ApprovalStatus.PENDING, ApprovalStatus.REJECTED])
def test_phase3_approval_does_not_change_phase2_acceptance(status: ApprovalStatus) -> None:
    pending = definition(
        approval_status=ApprovalStatus.PENDING, approved_by=None, approval_reference=None
    )
    kb, candidate, context = packet((pending,))
    assert (
        build_knowledge_snapshot(kb) == kb
    )  # Existing synthetic dietary acceptance remains valid.
    if status is ApprovalStatus.REJECTED:
        kb = kb.model_copy(
            update={"rules": (pending.model_copy(update={"approval_status": status}),)}
        )
    with pytest.raises(ValidationError):
        build_expected_check_manifest(kb, candidate, context)


@pytest.mark.parametrize("scope", list(RuleScope))
def test_unapproved_mandatory_rules_including_deferred_rejected(scope: RuleScope) -> None:
    rule = definition(
        scope=scope,
        approval_status=ApprovalStatus.PENDING,
        approved_by=None,
        approval_reference=None,
        attribute="synthetic_profile_flag" if scope is RuleScope.PROFILE else "synthetic_flag",
        required_facts=("synthetic_profile_flag",)
        if scope is RuleScope.PROFILE
        else ("synthetic_flag",),
    )
    kb, candidate, context = packet((rule,), workflow=KnowledgeWorkflow.WEEKLY_PLAN)
    with pytest.raises(ValidationError, match="unapproved"):
        build_expected_check_manifest(kb, candidate, context)


@pytest.mark.parametrize(
    "case",
    [
        "missing_check",
        "absent_rule",
        "stale_rule",
        "inactive_rule",
        "wrong_scope",
        "wrong_workflow",
        "stale_catalogue",
        "missing_cell",
        "missing_coverage",
        "incomplete_coverage",
        "duplicate_coverage",
        "wrong_coverage_scope",
        "stale_coverage",
        "duplicate_cell",
    ],
)
def test_corrupted_catalogue_cannot_enter_manifest(case: str) -> None:
    kb, candidate, context = packet()
    entry = next(
        e
        for e in kb.check_catalogue
        if e.workflow is KnowledgeWorkflow.CRAVING_DISCOVERY and e.scope is RuleScope.RECIPE
    )
    coverage = next(
        c
        for c in kb.rule_catalogue_coverage
        if c.workflow is entry.workflow and c.scope is entry.scope
    )
    changes: dict[str, Any] = {}
    modifications: dict[str, Any] = {
        "missing_check": {"rule_references": ()},
        "absent_rule": {"rule_references": (RuleReference(rule_id="absent", version="1"),)},
        "stale_rule": {
            "rule_references": (RuleReference(rule_id="recipe-check", version="stale"),)
        },
        "wrong_scope": {"scope": RuleScope.PROFILE},
        "wrong_workflow": {"workflow": KnowledgeWorkflow.WEEKLY_PLAN},
        "stale_catalogue": {"check_catalogue_version": "stale"},
    }
    if case in modifications:
        changes["check_catalogue"] = tuple(
            e.model_copy(update=modifications[case]) if e is entry else e
            for e in kb.check_catalogue
        )
    elif case == "inactive_rule":
        changes["rules"] = (kb.rules[0].model_copy(update={"lifecycle": RuleLifecycle.RETIRED}),)
    elif case == "missing_cell":
        changes["check_catalogue"] = tuple(e for e in kb.check_catalogue if e is not entry)
    elif case == "duplicate_cell":
        changes["check_catalogue"] = (*kb.check_catalogue, entry)
    elif case == "missing_coverage":
        changes["rule_catalogue_coverage"] = tuple(
            c for c in kb.rule_catalogue_coverage if c is not coverage
        )
    elif case == "duplicate_coverage":
        changes["rule_catalogue_coverage"] = (*kb.rule_catalogue_coverage, coverage)
    else:
        modification = {
            "incomplete_coverage": {"complete": False},
            "wrong_coverage_scope": {"scope": RuleScope.WEEK},
            "stale_coverage": {"kb_version": "stale"},
        }[case]
        changes["rule_catalogue_coverage"] = tuple(
            c.model_copy(update=modification) if c is coverage else c
            for c in kb.rule_catalogue_coverage
        )
    with pytest.raises(ValidationError):
        build_expected_check_manifest(kb.model_copy(update=changes), candidate, context)


@pytest.mark.parametrize(
    "changes",
    [
        {"attribute": "unregistered", "required_facts": ("unregistered",)},
        {"required_facts": ("synthetic_flag", "unregistered")},
        {
            "attribute": "synthetic_quantity",
            "required_facts": ("synthetic_quantity",),
            "value": 1,
            "unit": MeasurementUnit.G,
        },
        {"value": "False"},
        {"scope": RuleScope.PROFILE},
    ],
)
def test_unsupported_attribute_policy_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        build_expected_check_manifest(*packet((definition(**changes),)))


@pytest.mark.parametrize("case", ["identity", "version", "required_fact", "dependency"])
def test_unsupported_applicability_and_descriptor_mismatches(case: str) -> None:
    rule = definition()
    item = descriptor(rules=(rule,))
    if case in ("identity", "version"):
        ref = RuleReference(
            rule_id="unsupported" if case == "identity" else "synthetic-context-enabled",
            version="stale" if case == "version" else "1",
        )
        rule = rule.model_copy(update={"applicability_reference": ref})
        item = item.model_copy(update={"reference": ref})
    elif case == "required_fact":
        item = item.model_copy(update={"required_context_facts": ("synthetic_profile_enabled",)})
    else:
        other = descriptor("unsupported")
        item = item.model_copy(update={"dependencies": (other.reference,)})
        with pytest.raises(ValidationError, match="unsupported applicability"):
            build_expected_check_manifest(*packet((rule,), descriptors=(item, other)))
        return
    with pytest.raises(ValidationError, match="unsupported applicability"):
        build_expected_check_manifest(*packet((rule,), descriptors=(item,)))


@pytest.mark.parametrize("target", ["kb", "candidate", "context"])
@pytest.mark.parametrize("case", ["extra", "missing", "counterfeit", "digest"])
def test_corrupted_dtos_revalidated(target: str, case: str) -> None:
    inputs: list[Any] = list(packet())
    index = {"kb": 0, "candidate": 1, "context": 2}[target]
    model = inputs[index]
    data = dict(vars(model))
    if case == "extra":
        data["unexpected"] = True
    elif case == "missing":
        del data["evidence"]
    elif case == "digest":
        data["content_digest"] = "0" * 64
    else:
        data["evidence"] = (source().model_copy(update={"environment": "SYNTHETIC"}),)
    inputs[index] = type(model).model_construct(**data)
    if case == "extra":
        inputs[index] = model.model_copy(update={"unexpected": True})
    with pytest.raises(ValidationError):
        build_expected_check_manifest(inputs[0], inputs[1], inputs[2])


def test_empty_and_soft_only_catalogues_do_not_invent_checks() -> None:
    for rules in ((), (definition(severity=RuleSeverity.SOFT),)):
        manifest = build_expected_check_manifest(*packet(rules))
        assert manifest.required_checks == manifest.deferred_checks == ()


@pytest.mark.parametrize(
    "field",
    [
        "stage",
        "admissionPolicyVersion",
        "attributePolicyVersion",
        "evaluatorPolicyVersion",
        "identityPolicyVersion",
    ],
)
def test_manifest_rejects_unsupported_configuration(field: str) -> None:
    manifest = build_expected_check_manifest(*packet())
    with pytest.raises(ValidationError):
        rehash_manifest(manifest, **{field: "unsupported"})


def test_graph_reference_context_and_provenance_bindings() -> None:
    kb, candidate, context = packet()
    variants = [
        changed_candidate(
            candidate,
            graph_recipe_reference=candidate.graph_recipe_reference.model_copy(
                update={"version": "stale"}
            ),
        ),
        changed_candidate(
            candidate,
            context_id="different",
            context_version="1",
        ),
        changed_candidate(
            candidate,
            evidence=(source("test-approval", source="contradictory metadata"),),
        ),
    ]
    for changed in variants:
        with pytest.raises(ValidationError):
            build_expected_check_manifest(kb, changed, context)


@pytest.mark.parametrize(
    "field", ["candidate", "context", "profile_version", "workflow", "snapshot_version"]
)
def test_manifest_identity_changes_with_bound_inputs(field: str) -> None:
    kb, candidate, context = packet()
    original = build_expected_check_manifest(kb, candidate, context)
    if field == "candidate":
        candidate = changed_candidate(candidate, facts=(fact(value=True),))
    elif field == "snapshot_version":
        candidate = changed_candidate(candidate, snapshot_version="snapshot-v2")
    elif field == "context":
        context = changed_context(context, facts=())
    elif field == "profile_version":
        context = changed_context(context, profile_version="profile-v2")
    else:
        context = changed_context(context, workflow=KnowledgeWorkflow.PLANNED_SWAP)
    revised = build_expected_check_manifest(kb, candidate, context)
    assert revised.manifest_id != original.manifest_id
    assert revised.manifest_version != original.manifest_version
    assert revised.content_digest != original.content_digest


@pytest.mark.parametrize(
    "case", ["scope_override", "checks_override", "wrong_partition", "duplicate", "alias", "list"]
)
def test_no_reduced_scope_override_or_malformed_manifest_contract(case: str) -> None:
    inputs = packet()
    manifest = build_expected_check_manifest(*inputs)
    if case in ("scope_override", "checks_override"):
        override = (
            {"scopes": (RuleScope.RECIPE,)} if case == "scope_override" else {"required_checks": ()}
        )
        with pytest.raises(TypeError):
            build_expected_check_manifest(*inputs, **override)  # type: ignore[call-arg]
    elif case == "wrong_partition":
        with pytest.raises(ValidationError):
            rehash_manifest(
                manifest,
                requiredChecks=[],
                deferredChecks=[
                    manifest.required_checks[0].model_dump(mode="json", by_alias=True),
                ],
            )
    else:
        body = manifest.model_dump()
        if case == "duplicate":
            body["required_checks"] = (*manifest.required_checks, *manifest.required_checks)
        elif case == "alias":
            body["manifestId"] = body["manifest_id"]
        else:
            body["required_checks"] = list(manifest.required_checks)
        with pytest.raises(ValidationError):
            ExpectedCheckManifest.model_validate(body)


@pytest.mark.parametrize("field", ["workflow", "rule_scope", "rule_severity"])
def test_counterfeit_enum_instances_rejected(field: str) -> None:
    kb, candidate, context = packet()
    if field == "workflow":
        fake = str.__new__(KnowledgeWorkflow, "CRAVING_DISCOVERY")
        fake._value_ = "CRAVING_DISCOVERY"
        context = context.model_copy(update={"workflow": fake})
    else:
        kind = RuleScope if field == "rule_scope" else RuleSeverity
        token = "RECIPE" if field == "rule_scope" else "ABSOLUTE"
        fake = str.__new__(kind, token)
        fake._value_ = token
        kb = kb.model_copy(
            update={
                "rules": (
                    kb.rules[0].model_copy(
                        update={
                            "scope" if field == "rule_scope" else "severity": fake,
                        }
                    ),
                )
            }
        )
    with pytest.raises(ValidationError):
        build_expected_check_manifest(kb, candidate, context)


@pytest.mark.parametrize("key", ["workflow", "manifestId", "contentDigest", "requiredChecks"])
def test_strict_manifest_json_rejects_duplicate_keys(key: str) -> None:
    manifest = build_expected_check_manifest(*packet())
    body = manifest.model_dump(mode="json", by_alias=True)
    value = json.dumps(body[key])
    raw = json.dumps(body)[:-1] + "," + json.dumps(key) + ":" + value + "}"
    with pytest.raises(ValidationError, match="duplicate JSON"):
        validate_contract_json(ExpectedCheckManifest, raw)
