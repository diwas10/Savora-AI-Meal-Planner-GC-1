"""Independent fictional registrations and adversarial catalogue expectations."""

import copy
import hashlib
import json
from dataclasses import FrozenInstanceError
from typing import Any

import pytest
from pydantic import ValidationError
from test_knowledge_base import build as legacy_kb
from test_knowledge_base import independent_digest
from test_weekly_contracts import foundation

from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.manifest import build_expected_check_manifest
from savora_ai.core.reasoning.weekly import build_week_check_manifest
from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.knowledge import RuleDefinition, RuleScope
from savora_ai.schemas.knowledge_base import (
    ApplicabilityDescriptor,
    CheckCatalogueEntry,
    KnowledgeBaseSnapshot,
    KnowledgeWorkflow,
    RuleCatalogueCoverage,
)
from savora_ai.schemas.workflow_policy import REGISTERED_SWAP_EXTENSIONS

V2 = "synthetic-workflow-scopes.v2-registered-swap"
EXTENSION = "synthetic-swap-week-quantity-cap"


def approved_extension() -> RuleDefinition:
    # Literal independently constructed definition. Do not obtain it from the
    # registry, whose full-definition digest is what these tests verify.
    evidence = dict(
        evidenceId="synthetic-registered-swap-policy",
        version="1",
        source="Fictional closed swap-policy fixture; no nutrition authority",
        locator="urn:savora:synthetic-registered-swap-policy:1",
        environment="SYNTHETIC",
    )
    return RuleDefinition.model_validate_json(
        json.dumps(
            dict(
                ruleId=EXTENSION,
                version="1",
                scope="WEEK",
                severity="ABSOLUTE",
                domain="CULINARY",
                attribute="synthetic_week_quantity_total",
                operator="LE",
                value=44,
                unit="mg",
                requiredFacts=["synthetic_week_quantity_total"],
                applicabilityReference=dict(ruleId="synthetic-context-enabled", version="1"),
                evidence=[evidence],
                rationale=(
                    "Fictional swap-only integer cap for policy evaluation, not clinical guidance"
                ),
                lifecycle="ACTIVE",
                approvalStatus="APPROVED",
                approvedBy="synthetic-policy-reviewer",
                approvalReference=evidence,
                environment="SYNTHETIC",
            )
        )
    )


def v2_content() -> dict[str, Any]:
    base, _, _ = foundation()
    return with_registered_extension(base)


def with_registered_extension(base: KnowledgeBaseSnapshot) -> dict[str, Any]:
    extension = approved_extension()
    ref = dict(rule_id=EXTENSION, version="1")
    # Build complete cells independently of the production policy selector.
    cells = []
    for cell in base.check_catalogue:
        refs = tuple(r.model_dump() for r in cell.rule_references)
        if cell.workflow is KnowledgeWorkflow.PLANNED_SWAP and cell.scope is RuleScope.WEEK:
            refs += (ref,)
        cells.append(
            CheckCatalogueEntry.model_validate(
                cell.model_dump() | dict(kb_version="policy-v2", rule_references=refs)
            )
        )
    return base.model_dump(exclude={"content_digest"}) | dict(
        version="policy-v2",
        workflow_policy_version=V2,
        rules=(*base.rules, extension),
        active_rules=(*base.active_rules, ref),
        applicability_descriptors=tuple(
            ApplicabilityDescriptor.model_validate(
                d.model_dump() | dict(rule_references=(*d.rule_references, ref))
            )
            for d in base.applicability_descriptors
        ),
        check_catalogue=tuple(cells),
        rule_catalogue_coverage=tuple(
            RuleCatalogueCoverage.model_validate(c.model_dump() | dict(kb_version="policy-v2"))
            for c in base.rule_catalogue_coverage
        ),
    )


def edit_cell(data, workflow, scope, **changes):
    data["check_catalogue"] = tuple(
        CheckCatalogueEntry.model_validate(c) for c in data["check_catalogue"]
    )
    data["check_catalogue"] = tuple(
        CheckCatalogueEntry.model_validate(c.model_dump() | changes)
        if (c.workflow.value, c.scope.value) == (workflow, scope)
        else c
        for c in data["check_catalogue"]
    )


def test_registry_is_closed_and_full_definition_bound():
    assert len(REGISTERED_SWAP_EXTENSIONS) == 1
    registration = REGISTERED_SWAP_EXTENSIONS[0]
    assert (
        registration.rule_id,
        registration.version,
        registration.scope.value,
        registration.workflows,
    ) == (EXTENSION, "1", "WEEK", ("PLANNED_SWAP",))
    assert (
        independent_digest(approved_extension().model_dump(mode="json", by_alias=True))
        == registration.definition_digest
    )
    with pytest.raises(FrozenInstanceError):
        target: Any = registration
        target.workflows = ("WEEKLY_PLAN",)


def test_v1_frozen_hash_and_wire_goldens():
    from test_weekly_contracts import packet

    data = packet()
    models = dict(
        kb=legacy_kb(),
        weekly_kb=data["kb"],
        context=data["context"],
        recipe_manifest=build_expected_check_manifest(
            data["kb"], data["candidate"], data["context"]
        ),
        week_manifest=build_week_check_manifest(
            data["request"], knowledge=data["kb"], context=data["context"], sources=data["source"]
        ),
    )
    # Frozen before any implementation edit, not recalculated expected values.
    goldens = {
        "kb": (
            "816771c2e27c1ec0dfbaa597080fe866be72d71a2ce51957da5fbb3ddec3bdbe",
            "ec7955539c2dd752e23b2207d89234383c87d50b892048b3acceb76269b43679",
        ),
        "weekly_kb": (
            "844b78522bc8a958c91009739126a63e93f8be7a981aca47d9dbd9d26a853d23",
            "104aae24e037af0a0f58fb8e58dfee005fe132da5846daaf95de6be679747874",
        ),
        "context": (
            "c8ef5f5836c3423d80e32238c15dc75188d68119ffa4c3652a0e8451a23d5f5b",
            "ec645a614f2d4c71d0a27a6cdbe2afc88252152e900edf311534d64531568588",
        ),
        "recipe_manifest": (
            "28a33a256351c1f47c8a89ea67771f10f865f5dd687019d353f888f3ac205455",
            "b8ace251092d1d7e9ac9dbc53147e802a2017c55c5bc1634b69d05e2dff78680",
        ),
        "week_manifest": (
            "6ae6c732d2b55fe905ae87af3ed59bedfc173b6dd124793988131153b98f3711",
            "611783440769b15514317dea583b86433cabe21be6bc9a86e6307227069b9e54",
        ),
    }
    for name, model in models.items():
        assert (
            model.content_digest,
            hashlib.sha256(model.model_dump_json(by_alias=True).encode()).hexdigest(),
        ) == goldens[name]


@pytest.mark.parametrize("workflow", ("WEEKLY_PLAN", "PLANNED_SWAP"))
def test_v1_registered_name_is_still_common(workflow):
    kb, _, _ = foundation((approved_extension(),))
    assert kb.workflow_policy_version == "synthetic-workflow-scopes.v1"
    body = kb.model_dump(exclude={"content_digest"})
    edit_cell(body, workflow, "WEEK", rule_references=())
    with pytest.raises(ValidationError, match="omits a mandatory"):
        build_knowledge_snapshot(body)


def test_v2_complete_cells_and_no_leakage():
    kb = build_knowledge_snapshot(v2_content())
    assert kb.workflow_policy_version == V2
    assert len(kb.check_catalogue) == len(kb.rule_catalogue_coverage) == 12
    for cell in kb.check_catalogue:
        assert (EXTENSION in {r.rule_id for r in cell.rule_references}) == (
            cell.workflow is KnowledgeWorkflow.PLANNED_SWAP and cell.scope is RuleScope.WEEK
        )
    assert KnowledgeBaseSnapshot.model_validate_json(kb.model_dump_json()) == kb


@pytest.mark.parametrize("policy", ("synthetic-workflow-scopes.v2", "unknown", "", None, True))
def test_unknown_policy_versions(policy):
    data = v2_content() | {"workflow_policy_version": policy}
    with pytest.raises(ValidationError):
        build_knowledge_snapshot(data)


@pytest.mark.parametrize("workflow", ("WEEKLY_PLAN", "CRAVING_DISCOVERY", "PLANNED_SWAP"))
def test_missing_common_rule(workflow):
    data = v2_content()
    edit_cell(data, workflow, "RECIPE", rule_references=())
    with pytest.raises(ValidationError):
        build_knowledge_snapshot(data)


@pytest.mark.parametrize(
    "fault",
    (
        "absent",
        "inactive",
        "soft",
        "version",
        "scope",
        "value",
        "evidence",
        "rationale",
        "approval",
    ),
)
def test_required_extension_cannot_be_removed_or_changed(fault):
    data = v2_content()
    rules = [r.model_dump(mode="json", by_alias=True) for r in data["rules"]]
    extra = rules[-1]
    if fault == "absent":
        rules.pop()
    elif fault == "evidence":
        extra["evidence"][0]["source"] = "Altered fictional source"
        extra["approvalReference"]["source"] = "Altered fictional source"
    else:
        field, value = {
            "inactive": ("lifecycle", "DRAFT"),
            "soft": ("severity", "SOFT"),
            "version": ("version", "2"),
            "scope": ("scope", "DAY"),
            "value": ("value", 45),
            "rationale": ("rationale", "Forged rationale"),
            "approval": ("approvedBy", "forged"),
        }[fault]
        extra[field] = value
    data["rules"] = tuple(RuleDefinition.model_validate_json(json.dumps(r)) for r in rules)
    # Consistently rewrite the submitted active/host/cell inventories. Rehashing
    # an internally self-consistent forgery must still fail registry validation.
    refs = tuple(
        dict(rule_id=r.rule_id, version=r.version)
        for r in data["rules"]
        if r.lifecycle.value == "ACTIVE"
    )
    data["active_rules"] = refs
    data["applicability_descriptors"] = tuple(
        ApplicabilityDescriptor.model_validate(
            d.model_dump()
            | dict(
                rule_references=tuple(
                    dict(rule_id=r.rule_id, version=r.version) for r in data["rules"]
                )
            )
        )
        for d in data["applicability_descriptors"]
    )
    data["check_catalogue"] = tuple(
        CheckCatalogueEntry.model_validate(
            c.model_dump()
            | dict(
                rule_references=tuple(
                    ref
                    for ref in refs
                    if next(r for r in data["rules"] if r.rule_id == ref["rule_id"]).scope
                    is c.scope
                    and next(r for r in data["rules"] if r.rule_id == ref["rule_id"]).severity.value
                    == "ABSOLUTE"
                    and (ref["rule_id"] != EXTENSION or c.workflow.value == "PLANNED_SWAP")
                )
            )
        )
        for c in data["check_catalogue"]
    )
    with pytest.raises(ValidationError):
        build_knowledge_snapshot(data)


@pytest.mark.parametrize(
    "fault",
    (
        "missing-extension-cell",
        "leak",
        "duplicate",
        "contradictory",
        "unsupported",
        "wrong-source",
        "coverage",
    ),
)
def test_forged_catalogue(fault):
    data = v2_content()
    cell = next(
        c
        for c in data["check_catalogue"]
        if c.workflow.value == "PLANNED_SWAP" and c.scope.value == "WEEK"
    )
    if fault == "missing-extension-cell":
        edit_cell(data, "PLANNED_SWAP", "WEEK", rule_references=cell.rule_references[:-1])
    elif fault == "leak":
        edit_cell(data, "WEEKLY_PLAN", "WEEK", rule_references=cell.rule_references)
    elif fault in ("duplicate", "contradictory"):
        data["check_catalogue"] += (
            CheckCatalogueEntry.model_validate(
                cell.model_dump()
                | dict(
                    entry_id="duplicate",
                    rule_references=() if fault == "contradictory" else cell.rule_references,
                )
            ),
        )
    elif fault == "unsupported":
        data["check_catalogue"] += (
            CheckCatalogueEntry.model_validate(
                cell.model_dump()
                | dict(entry_id="unsupported", workflow=KnowledgeWorkflow.CRAVING_DISCOVERY)
            ),
        )
    elif fault == "wrong-source":
        edit_cell(data, "PLANNED_SWAP", "WEEK", kb_version="other")
    else:
        data["rule_catalogue_coverage"] = data["rule_catalogue_coverage"][:-1]
    with pytest.raises(ValidationError):
        build_knowledge_snapshot(data)


@pytest.mark.parametrize("index", range(12))
def test_every_cell_is_mandatory(index):
    data = v2_content()
    data["check_catalogue"] = data["check_catalogue"][:index] + data["check_catalogue"][index + 1 :]
    with pytest.raises(ValidationError):
        build_knowledge_snapshot(data)


def test_unregistered_prefix_is_common_and_registry_is_not_an_input():
    data = v2_content()
    extra = approved_extension().model_dump(mode="json", by_alias=True) | {
        "ruleId": EXTENSION + "-lookalike"
    }
    rule = RuleDefinition.model_validate_json(json.dumps(extra))
    ref = dict(rule_id=rule.rule_id, version=rule.version)
    data["rules"] += (rule,)
    data["active_rules"] += (ref,)
    data["applicability_descriptors"] = tuple(
        ApplicabilityDescriptor.model_validate(
            d.model_dump() | dict(rule_references=(*d.rule_references, ref))
        )
        for d in data["applicability_descriptors"]
    )
    data["check_catalogue"] = tuple(
        CheckCatalogueEntry.model_validate(
            c.model_dump() | dict(rule_references=(*c.rule_references, ref))
        )
        if c.scope is RuleScope.WEEK
        else c
        for c in data["check_catalogue"]
    )
    kb = build_knowledge_snapshot(data)
    assert any(
        r.rule_id == rule.rule_id
        for c in kb.check_catalogue
        if c.workflow is KnowledgeWorkflow.WEEKLY_PLAN
        for r in c.rule_references
    )
    edit_cell(
        data,
        "WEEKLY_PLAN",
        "WEEK",
        rule_references=tuple(
            r
            for r in next(
                c
                for c in data["check_catalogue"]
                if c.workflow is KnowledgeWorkflow.WEEKLY_PLAN and c.scope is RuleScope.WEEK
            ).rule_references
            if r.rule_id != rule.rule_id
        ),
    )
    with pytest.raises(ValidationError):
        build_knowledge_snapshot(data)
    with pytest.raises(ValidationError):
        forged: dict[str, object] = v2_content()
        forged["registry"] = ()
        build_knowledge_snapshot(forged)


def test_rehash_is_not_independent_release_authority():
    kb = build_knowledge_snapshot(v2_content())
    changed = copy.deepcopy(v2_content())
    original = changed["rules"][0]
    changed["rules"] = (
        RuleDefinition.model_validate(
            original.model_dump()
            | dict(rationale="Changed common rule with a self-computed digest")
        ),
        *changed["rules"][1:],
    )
    rehashed = build_knowledge_snapshot(changed)
    assert rehashed.content_digest != kb.content_digest
    with pytest.raises(ValidationError, match="trusted expected KB content digest mismatch"):
        build_knowledge_snapshot(changed, expected_digest=kb.content_digest)
    with pytest.raises(ValidationError):
        validate_contract_json(
            KnowledgeBaseSnapshot, kb.model_dump_json()[:-1] + ',"workflowPolicyVersion":"unknown"}'
        )


@pytest.mark.parametrize("direction", ("v1-to-v2", "v2-to-v1"))
def test_policy_relabelling_alone_never_supplies_inventory(direction):
    body: dict[str, object]
    if direction == "v1-to-v2":
        base, _, _ = foundation()
        body = base.model_dump(exclude={"content_digest"})
        body["workflow_policy_version"] = V2
    else:
        body = v2_content()
        body["workflow_policy_version"] = "synthetic-workflow-scopes.v1"
    with pytest.raises(ValidationError):
        build_knowledge_snapshot(body)
