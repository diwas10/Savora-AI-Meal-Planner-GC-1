"""Independent synthetic end-to-end fixtures; no production decision/digest oracles."""

import hashlib
import json
from enum import StrEnum
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from savora_ai.core.reasoning.combinations import evaluate_combination
from savora_ai.core.reasoning.filtering import filter_candidates
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    FactSubjectKind,
    IngredientCoverage,
    IngredientGapReason,
    RuleContext,
    VersionedFact,
    validate_contract_json,
)
from savora_ai.schemas.combination_evaluation import CombinationEligibilityResult
from savora_ai.schemas.combinations import (
    CombinationComponent,
    CombinationFacts,
    CombinationMeasurementBasis,
    CombinationObservation,
    ComponentQuantity,
    CompositionGapReason,
    PortionState,
    PreparationBinding,
    QuantityUnit,
    RecipeSnapshotReference,
)
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
from savora_ai.schemas.reasoning import ApplicabilityStatus, FactObservation, RuleStatus

ROLES = "synthetic_combination_roles_compatible"
COMPOSITION = "synthetic_combination_composition_complete"


def proof(id_: str = "source", **changes: Any) -> EvidenceReference:
    return EvidenceReference.model_validate(
        dict(
            evidence_id=id_,
            version="source-v1",
            source="Independent fictional evaluator test",
            locator="urn:independent-combination:" + id_,
            environment=RuleEnvironment.SYNTHETIC,
        )
        | changes
    )


def declaration(id_: str, scope: RuleScope, attribute: str, **changes: Any) -> RuleDefinition:
    return RuleDefinition.model_validate(
        dict(
            rule_id=id_,
            version="rule-v1",
            scope=scope,
            severity=RuleSeverity.ABSOLUTE,
            domain=RuleDomain.CULINARY,
            attribute=attribute,
            operator=PredicateOperator.EQ,
            value=True,
            required_facts=(attribute,),
            applicability_reference=RuleReference(rule_id="synthetic-context-enabled", version="1"),
            evidence=(proof("rule-" + id_),),
            rationale="Fictional boolean requirement",
            lifecycle=RuleLifecycle.ACTIVE,
            environment=RuleEnvironment.SYNTHETIC,
            approval_status=ApprovalStatus.APPROVED,
            approved_by="fictional-reviewer",
            approval_reference=proof("approval-" + id_),
        )
        | changes
    )


def fact(
    name: str, owner: FactSubjectKind, id_: str, value: Any = True, *, complete: bool = True
) -> VersionedFact:
    return VersionedFact(
        fact_id=name,
        version="fact-v1",
        subject_kind=owner,
        subject_id=id_,
        subject_version="1",
        catalogue_version="catalogue-1" if owner is FactSubjectKind.RECIPE else None,
        context_id="context" if owner is FactSubjectKind.CONTEXT else None,
        context_version="1" if owner is FactSubjectKind.CONTEXT else None,
        observation=FactObservation(
            fact_id=name,
            value=value,
            complete=complete,
            evidence=(proof("fact-" + name + "-" + id_),),
        ),
    )


def packet(
    *,
    rules: tuple[RuleDefinition, ...] | None = None,
    fixed: bool = False,
    compatible: bool | None = True,
    complete: bool = True,
    enabled: bool | None = True,
) -> tuple[CombinationFacts, tuple[CandidateRecipeFacts, ...], KnowledgeBaseSnapshot, RuleContext]:
    if rules is None:
        rules = (
            declaration("recipe", RuleScope.RECIPE, "synthetic_flag"),
            declaration("profile", RuleScope.PROFILE, "synthetic_profile_flag"),
            declaration("roles", RuleScope.COMBINATION, ROLES),
            declaration("composition", RuleScope.COMBINATION, COMPOSITION),
            declaration("day", RuleScope.DAY, "synthetic_flag"),
            declaration("week", RuleScope.WEEK, "synthetic_flag"),
        )
    nodes = tuple(
        FoodEntity(
            entity_id="node-" + id_,
            version="1",
            kind=FoodEntityKind.RECIPE_REFERENCE,
            canonical_name="Same display label",
            catalogue_reference=id_,
            evidence=(proof("node-" + id_),),
        )
        for id_ in ("alpha", "beta")
    )
    role = FoodEntity(
        entity_id="role-node",
        version="1",
        kind=FoodEntityKind.CULINARY_ROLE_REFERENCE,
        canonical_name="Same display label",
        catalogue_reference="role",
        evidence=(proof("role"),),
    )
    graph = FoodGraphSnapshot(
        graph_id="graph",
        version="1",
        catalogue_version="catalogue-1",
        environment=RuleEnvironment.SYNTHETIC,
        entities=(*nodes, role),
        relations=(),
        evidence=(proof(),),
    )
    cells = tuple(
        CheckCatalogueEntry(
            entry_id=f"{workflow.value}-{scope.value}",
            version="1",
            kb_id="kb",
            kb_version="1",
            check_catalogue_version="checks-1",
            workflow=workflow,
            scope=scope,
            rule_references=tuple(
                RuleReference(rule_id=r.rule_id, version=r.version)
                for r in rules
                if r.scope is scope
            ),
            evidence=(proof(),),
        )
        for workflow in KnowledgeWorkflow
        for scope in RuleScope
        if workflow is not KnowledgeWorkflow.CRAVING_DISCOVERY
        or scope in (RuleScope.PROFILE, RuleScope.RECIPE)
    )
    kb = build_knowledge_snapshot(
        dict(
            kb_id="kb",
            version="1",
            environment=RuleEnvironment.SYNTHETIC,
            graph_id="graph",
            graph_version="1",
            catalogue_version="catalogue-1",
            taxonomy_version=None,
            check_catalogue_version="checks-1",
            graph=graph,
            rules=rules,
            active_rules=tuple(RuleReference(rule_id=r.rule_id, version=r.version) for r in rules),
            applicability_descriptors=(
                ApplicabilityDescriptor(
                    reference=RuleReference(rule_id="synthetic-context-enabled", version="1"),
                    rule_references=tuple(
                        RuleReference(rule_id=r.rule_id, version=r.version) for r in rules
                    ),
                    required_context_facts=("synthetic_context_enabled",),
                    evidence=(proof("applicability"),),
                ),
            ),
            check_catalogue=cells,
            rule_catalogue_coverage=tuple(
                RuleCatalogueCoverage(
                    coverage_id="coverage-" + cell.entry_id,
                    version="1",
                    kb_id="kb",
                    kb_version="1",
                    check_catalogue_version="checks-1",
                    workflow=cell.workflow,
                    scope=cell.scope,
                    complete=True,
                    reason="Independent complete check inventory",
                    evidence=(proof(),),
                )
                for cell in cells
            ),
            evidence=(proof(),),
        )
    )
    candidates = tuple(
        CandidateRecipeFacts.build(
            dict(
                recipe_id=node.catalogue_reference,
                recipe_version="1",
                catalogue_version="catalogue-1",
                graph_id="graph",
                graph_version="1",
                graph_recipe_entity_id=node.entity_id,
                graph_recipe_reference=node,
                snapshot_id="snapshot-" + str(node.catalogue_reference),
                snapshot_version="1",
                ingredient_coverage=IngredientCoverage(
                    coverage_id="coverage-" + node.entity_id,
                    version="1",
                    recipe_id=str(node.catalogue_reference),
                    recipe_version="1",
                    catalogue_version="catalogue-1",
                    lines=None,
                    inventory_complete=False,
                    mapping_complete=False,
                    subingredients_complete=False,
                    gap_reasons=(IngredientGapReason.MISSING_INVENTORY,),
                    evidence=(proof("inventory"),),
                ),
                facts=(
                    fact("synthetic_flag", FactSubjectKind.RECIPE, str(node.catalogue_reference)),
                ),
                evidence=(proof("candidate"),),
            )
        )
        for node in nodes
    )
    context = RuleContext.build(
        dict(
            context_id="context",
            version="1",
            profile_id="profile",
            profile_version="1",
            workflow=KnowledgeWorkflow.WEEKLY_PLAN,
            expected_kb_id=kb.kb_id,
            expected_kb_version=kb.version,
            expected_kb_digest=kb.content_digest,
            expected_graph_id=kb.graph_id,
            expected_graph_version=kb.graph_version,
            expected_taxonomy_version=kb.taxonomy_version,
            expected_catalogue_version=kb.catalogue_version,
            expected_check_catalogue_version=kb.check_catalogue_version,
            facts=(
                fact(
                    "synthetic_context_enabled",
                    FactSubjectKind.CONTEXT,
                    "context",
                    enabled,
                    complete=enabled is not None,
                ),
                fact("synthetic_profile_flag", FactSubjectKind.PROFILE, "profile"),
            ),
            evidence=(proof("context"),),
        )
    )
    components = []
    for position, candidate in enumerate(candidates):
        ref = RecipeSnapshotReference(
            recipe_id=candidate.recipe_id,
            recipe_version=candidate.recipe_version,
            snapshot_id=candidate.snapshot_id,
            snapshot_version=candidate.snapshot_version,
            content_digest=candidate.content_digest,
            catalogue_version=candidate.catalogue_version,
        )
        prep = PreparationBinding(
            preparation_id="cooked-" + candidate.recipe_id,
            version="1",
            recipe_snapshot=ref,
            basis_reference=proof("cooked-basis-" + candidate.recipe_id),
            evidence=(proof("preparation"),),
        )
        components.append(
            CombinationComponent(
                component_id="occurrence-" + str(position),
                recipe_snapshot=ref,
                preparation=prep,
                quantity=ComponentQuantity(
                    amount=10 + position,
                    unit=QuantityUnit.G,
                    preparation_id=prep.preparation_id,
                    preparation_version=prep.version,
                    basis_reference=prep.basis_reference,
                    portion_reference=proof("portion-definition"),
                    evidence=(proof("quantity"),),
                )
                if fixed
                else None,
                role_references=(role,),
                evidence=(proof("component"),),
            )
        )
    combo = CombinationFacts.build(
        dict(
            combination_id="combination",
            version="1",
            snapshot_id="combination-snapshot",
            snapshot_version="1",
            components=tuple(components),
            composition_complete=complete,
            composition_gap_reasons=()
            if complete
            else (CompositionGapReason.INCOMPLETE_COMPOSITION,),
            portion_state=PortionState.FIXED if fixed else PortionState.UNASSIGNED,
            portion_configuration_id="configuration" if fixed else None,
            portion_configuration_version="1" if fixed else None,
            observations=tuple(
                CombinationObservation(
                    fact_id=name,
                    version="1",
                    combination_id="combination",
                    combination_version="1",
                    observation=FactObservation(
                        fact_id=name,
                        value=value,
                        complete=value is not None,
                        evidence=(proof("observation-" + name),),
                    ),
                )
                for name, value in ((ROLES, compatible), (COMPOSITION, complete))
            ),
            context_id=context.context_id,
            context_version=context.version,
            context_digest=context.content_digest,
            kb_id=kb.kb_id,
            kb_version=kb.version,
            kb_digest=kb.content_digest,
            graph_id=kb.graph_id,
            graph_version=kb.graph_version,
            catalogue_version=kb.catalogue_version,
            taxonomy_version=kb.taxonomy_version,
            check_catalogue_version=kb.check_catalogue_version,
            evidence=(proof("composition-source"),),
        )
    )
    return combo, candidates, kb, context


def evaluate(
    packet_: tuple[Any, ...], *, trusted: bool = True, **changes: Any
) -> CombinationEligibilityResult:
    combo, candidates, kb, context = packet_
    return evaluate_combination(
        combo,
        **(
            dict(
                candidates=candidates,
                knowledge=kb,
                context=context,
                trusted_combination=combo if trusted else None,
            )
            | changes
        ),
    )


def changed(combo: CombinationFacts, **changes: Any) -> CombinationFacts:
    return CombinationFacts.build(combo.model_dump(exclude={"content_digest"}) | changes)


@pytest.mark.parametrize("fixed", [False, True])
def test_fully_valid_combination_and_exact_recipe_prerequisites(fixed: bool) -> None:
    result = evaluate(packet(fixed=fixed))
    assert result.status is RuleStatus.PASS
    assert result.recipes.eligible_ids == ("alpha", "beta")
    assert tuple(item.rule.rule_id for item in result.trace.evaluations) == ("composition", "roles")
    assert all(item.status is RuleStatus.PASS for item in result.trace.evaluations)
    assert tuple(rule.rule_id for rule in result.deferred_checks) == ("day", "week")
    portions = next(item for item in result.prerequisites if item.name == "PORTION_CONFIGURATION")
    assert portions.status is (RuleStatus.PASS if fixed else None)
    assert result.plan_feasibility == "NOT_EVALUATED"
    assert (
        validate_contract_json(CombinationEligibilityResult, result.model_dump_json(by_alias=True))
        == result
    )


@pytest.mark.parametrize("trusted", [False, True])
@pytest.mark.parametrize("count", [0, 1])
def test_missing_candidate_membership_unknown(count: int, trusted: bool) -> None:
    data = packet()
    result = evaluate(data, candidates=data[1][:count], trusted=trusted)
    assert result.status is RuleStatus.UNKNOWN
    assert (
        next(p for p in result.prerequisites if p.name == "CANDIDATE_MEMBERSHIP").status
        is RuleStatus.UNKNOWN
    )


@pytest.mark.parametrize("fixed", [False, True])
def test_self_consistent_hash_and_positive_proposal_never_supply_authority(fixed: bool) -> None:
    result = evaluate(packet(fixed=fixed), trusted=False)
    assert result.status is RuleStatus.UNKNOWN
    assert all(item.status is RuleStatus.UNKNOWN for item in result.trace.evaluations)
    assert all(fact.value is None for item in result.trace.evaluations for fact in item.facts)


@pytest.mark.parametrize(
    "compatible,complete,expected",
    [
        (True, True, RuleStatus.PASS),
        (False, True, RuleStatus.FAIL),
        (None, True, RuleStatus.UNKNOWN),
        (True, False, RuleStatus.FAIL),
        (False, False, RuleStatus.FAIL),
        (None, False, RuleStatus.FAIL),
    ],
)
def test_literal_combination_truth_table(
    compatible: bool | None, complete: bool, expected: RuleStatus
) -> None:
    result = evaluate(packet(compatible=compatible, complete=complete))
    assert result.status is expected


@pytest.mark.parametrize(
    "enabled,expected",
    [(True, RuleStatus.PASS), (False, RuleStatus.PASS), (None, RuleStatus.UNKNOWN)],
)
def test_applicability_preserves_existing_semantics(
    enabled: bool | None, expected: RuleStatus
) -> None:
    result = evaluate(packet(enabled=enabled))
    assert result.status is expected
    if enabled is False:
        assert all(
            e.applicability is ApplicabilityStatus.NOT_APPLICABLE for e in result.trace.evaluations
        )
        assert all(e.status is RuleStatus.UNKNOWN for e in result.trace.evaluations)


@pytest.mark.parametrize(
    "field",
    [
        "context_id",
        "context_version",
        "kb_id",
        "kb_version",
        "graph_id",
        "graph_version",
        "catalogue_version",
        "check_catalogue_version",
    ],
)
def test_wrong_release_or_context_binding_rejected(field: str) -> None:
    combo, candidates, kb, context = packet()
    body = combo.model_dump(exclude={"content_digest"})
    body[field] = "wrong"
    with pytest.raises(ValidationError):
        evaluate((CombinationFacts.build(body), candidates, kb, context))


@pytest.mark.parametrize("field", ["context_digest", "kb_digest", "content_digest"])
def test_digest_tampering_rejected(field: str) -> None:
    combo, candidates, kb, context = packet()
    bad = combo.model_copy(update={field: "a" * 64})
    with pytest.raises(ValidationError):
        evaluate((bad, candidates, kb, context))


def test_candidate_snapshot_revision_conflict_rejected() -> None:
    data = packet()
    candidate = data[1][0]
    body = candidate.model_dump(exclude={"content_digest"})
    body["snapshot_version"] = "2"
    revised = CandidateRecipeFacts.build(body)
    with pytest.raises(ValidationError, match="exact accepted candidate"):
        evaluate(data, candidates=(revised, data[1][1]))


def test_duplicate_occurrence_and_missing_component_rejected() -> None:
    data = packet()
    combo = data[0]
    for components in ((), (combo.components[0], combo.components[0])):
        with pytest.raises(ValidationError):
            evaluate((combo.model_copy(update={"components": components}), *data[1:]))


def test_repeated_recipe_occurrences_preserved() -> None:
    data = packet()
    a = data[0].components[0]
    combo = changed(data[0], components=(a, a.model_copy(update={"component_id": "repeat"})))
    result = evaluate((combo, *data[1:]))
    assert result.status is RuleStatus.PASS
    assert len(result.combination.components) == 2
    assert result.recipes.eligible_ids == ("alpha",)


def test_wrong_preparation_and_fixed_configuration_sources_rejected() -> None:
    data = packet(fixed=True)
    original = data[0]
    for field, value in (
        ("preparation_id", "raw"),
        ("preparation_version", "2"),
        ("basis_reference", proof("raw-basis")),
    ):
        part = original.components[0]
        bad_quantity = part.quantity.model_copy(update={field: value}) if part.quantity else None
        bad = original.model_copy(
            update={
                "components": (
                    part.model_copy(update={"quantity": bad_quantity}),
                    original.components[1],
                )
            }
        )
        with pytest.raises(ValidationError):
            evaluate((bad, *data[1:]))
    revised = changed(original, portion_configuration_version="2")
    with pytest.raises(ValidationError, match="upstream snapshot"):
        evaluate((revised, *data[1:]), trusted_combination=original)


def test_partial_fixed_assignment_and_missing_evidence_rejected() -> None:
    data = packet(fixed=True)
    original = data[0]
    for update in (
        {
            "components": (
                original.components[0].model_copy(update={"quantity": None}),
                original.components[1],
            )
        },
        {"evidence": ()},
        {
            "components": (
                original.components[0].model_copy(
                    update={
                        "preparation": original.components[0].preparation.model_copy(
                            update={"evidence": ()}
                        )
                    }
                ),
                original.components[1],
            )
        },
    ):
        with pytest.raises(ValidationError):
            evaluate((original.model_copy(update=update), *data[1:]))


def test_conflicting_cross_input_evidence_rejected() -> None:
    data = packet()
    candidate = data[1][0]
    body = candidate.model_dump(exclude={"content_digest"})
    body["evidence"] = (proof("composition-source", locator="urn:contradictory"),)
    conflicting = CandidateRecipeFacts.build(body)
    with pytest.raises(ValidationError, match="conflicting evidence"):
        evaluate(data, candidates=(conflicting, data[1][1]))


def test_no_combination_rules_and_no_recipe_rules_both_remain_unknown() -> None:
    for rules in (
        (declaration("recipe", RuleScope.RECIPE, "synthetic_flag"),),
        (declaration("roles", RuleScope.COMBINATION, ROLES),),
    ):
        assert evaluate(packet(rules=rules)).status is RuleStatus.UNKNOWN


@pytest.mark.parametrize(
    "operator,value,observed,expected",
    [
        (PredicateOperator.EQ, True, True, RuleStatus.PASS),
        (PredicateOperator.EQ, True, False, RuleStatus.FAIL),
        (PredicateOperator.EQ, False, False, RuleStatus.PASS),
        (PredicateOperator.NE, True, False, RuleStatus.PASS),
        (PredicateOperator.NE, False, True, RuleStatus.PASS),
        (PredicateOperator.NE, False, False, RuleStatus.FAIL),
    ],
)
def test_exact_registered_boolean_comparisons(
    operator: PredicateOperator, value: bool, observed: bool, expected: RuleStatus
) -> None:
    rules = (
        declaration("recipe", RuleScope.RECIPE, "synthetic_flag"),
        declaration("roles", RuleScope.COMBINATION, ROLES, operator=operator, value=value),
    )
    assert evaluate(packet(rules=rules, compatible=observed)).status is expected


def test_unsupported_old_recipe_attribute_on_combination_rejected_only_at_combination_stage() -> (
    None
):
    rules = (declaration("legacy", RuleScope.COMBINATION, "synthetic_flag"),)
    with pytest.raises(ValidationError, match="combination predicate"):
        evaluate(packet(rules=rules))


def test_rule_and_candidate_order_do_not_change_output() -> None:
    data = packet()
    first = evaluate(data)
    second = evaluate(data, candidates=tuple(reversed(data[1])))
    assert first == second
    combo, candidates, kb, context = data
    body = kb.model_dump(exclude={"content_digest"})
    body["rules"] = tuple(reversed(kb.rules))
    reordered = build_knowledge_snapshot(body)
    assert reordered.content_digest == kb.content_digest
    third = evaluate((combo, candidates, reordered, context))
    assert third == first


def test_unchecked_objects_hostile_containers_aliases_and_counterfeit_statuses() -> None:
    data = packet()

    class HostileTuple(tuple):
        def __iter__(self) -> Any:
            raise AssertionError("custom iteration must not execute")

    bad_inputs: tuple[dict[str, Any], ...] = (
        {"candidates": HostileTuple(data[1])},
        {"context": data[3].model_copy(update={"eligible": True})},
        {"trusted_combination": CombinationFacts.model_construct()},
    )
    for changes in bad_inputs:
        with pytest.raises(ValidationError):
            evaluate(data, **changes)

    class FakeStatus(StrEnum):
        PASS = "PASS"

    result = evaluate(data)
    with pytest.raises(ValidationError):
        CombinationEligibilityResult.model_validate(
            result.model_copy(update={"status": FakeStatus.PASS})
        )
    payload = result.model_dump()
    payload["trustedCombination"] = result.trusted_combination
    with pytest.raises(ValidationError, match="alias"):
        CombinationEligibilityResult.model_validate(payload)
    raw = result.model_dump_json(by_alias=True)
    with pytest.raises(ValidationError, match="duplicate JSON"):
        validate_contract_json(
            TypeAdapter(CombinationEligibilityResult),
            raw.replace('"status":"PASS"', '"status":"PASS","status":"PASS"', 1),
        )


def repin(
    data: tuple[Any, ...],
    *,
    kb: KnowledgeBaseSnapshot | None = None,
    context: RuleContext | None = None,
) -> tuple[Any, ...]:
    combo, candidates, old_kb, old_context = data
    selected_kb: KnowledgeBaseSnapshot = old_kb if kb is None else kb
    if context is None:
        body = old_context.model_dump(exclude={"content_digest"})
        body.update(
            expected_kb_digest=selected_kb.content_digest,
            expected_graph_version=selected_kb.graph_version,
            expected_taxonomy_version=selected_kb.taxonomy_version,
        )
        context = RuleContext.build(body)
    return (
        changed(
            combo,
            kb_digest=selected_kb.content_digest,
            context_digest=context.content_digest,
            context_id=context.context_id,
            context_version=context.version,
            graph_version=selected_kb.graph_version,
            taxonomy_version=selected_kb.taxonomy_version,
        ),
        candidates,
        selected_kb,
        context,
    )


def test_missing_or_incomplete_observations_remain_unknown() -> None:
    data = packet()
    combo = data[0]
    for observations in (
        (),
        tuple(o for o in combo.observations if o.fact_id != ROLES),
        tuple(
            o.model_copy(
                update={"observation": o.observation.model_copy(update={"complete": False})}
            )
            if o.fact_id == ROLES
            else o
            for o in combo.observations
        ),
    ):
        revised = changed(combo, observations=observations)
        assert evaluate((revised, *data[1:])).status is RuleStatus.UNKNOWN


def test_untrusted_negative_is_not_a_known_failure() -> None:
    assert evaluate(packet(compatible=False), trusted=False).status is RuleStatus.UNKNOWN


def test_known_failure_dominates_missing_candidate_without_skipping_checks() -> None:
    result = evaluate(packet(compatible=False), candidates=())
    assert result.status is RuleStatus.FAIL
    assert len(result.trace.evaluations) == 2
    assert {item.status for item in result.trace.evaluations} == {RuleStatus.PASS, RuleStatus.FAIL}


def test_accepted_role_membership_unknown_and_conflicting_role_records_rejected() -> None:
    data = packet()
    for missing in (True, False):
        body = data[2].model_dump(exclude={"content_digest"})
        graph = body["graph"]
        if missing:
            graph["entities"] = tuple(
                node for node in graph["entities"] if node["entity_id"] != "role-node"
            )
        else:
            for node in graph["entities"]:
                if node["entity_id"] == "role-node":
                    node["canonical_name"] = "Conflicting content under the same identity/version"
        revised = repin(data, kb=build_knowledge_snapshot(body))
        if missing:
            result = evaluate(revised)
            assert result.status is RuleStatus.UNKNOWN
            assert (
                next(p for p in result.prerequisites if p.name == "ROLE_REFERENCES").status
                is RuleStatus.UNKNOWN
            )
        else:
            with pytest.raises(ValidationError, match="role reference"):
                evaluate(revised)


def test_combination_owned_observations_cannot_supply_normalized_profile_facts() -> None:
    rules = (
        declaration("recipe", RuleScope.RECIPE, "synthetic_flag"),
        declaration(
            "roles", RuleScope.COMBINATION, ROLES, required_facts=(ROLES, "synthetic_profile_flag")
        ),
    )
    data = packet(rules=rules)
    context_body = data[3].model_dump(exclude={"content_digest"})
    context_body["facts"] = tuple(f for f in data[3].facts if f.fact_id != "synthetic_profile_flag")
    data = repin(data, context=RuleContext.build(context_body))
    spoof = CombinationObservation(
        fact_id="synthetic_profile_flag",
        version="1",
        combination_id="combination",
        combination_version="1",
        observation=FactObservation(
            fact_id="synthetic_profile_flag",
            value=True,
            complete=True,
            evidence=(proof("spoofed-profile-fact"),),
        ),
    )
    combo = changed(data[0], observations=(*data[0].observations, spoof))
    result = evaluate((combo, *data[1:]))
    assert result.status is RuleStatus.UNKNOWN
    profile = next(
        f for f in result.trace.evaluations[0].facts if f.fact_id == "synthetic_profile_flag"
    )
    assert profile.value is None


@pytest.mark.parametrize("value,expected", [(False, RuleStatus.FAIL), (None, RuleStatus.UNKNOWN)])
def test_recipe_fail_or_unknown_cannot_be_overridden_by_combination_pass(
    value: bool | None, expected: RuleStatus
) -> None:
    data = packet()
    combo, candidates, kb, context = data
    candidate_body = candidates[0].model_dump(exclude={"content_digest"})
    candidate_body["facts"] = (
        fact("synthetic_flag", FactSubjectKind.RECIPE, "alpha", value, complete=value is not None),
    )
    revised = CandidateRecipeFacts.build(candidate_body)
    part = combo.components[0]
    ref = part.recipe_snapshot.model_copy(update={"content_digest": revised.content_digest})
    part = part.model_copy(
        update={
            "recipe_snapshot": ref,
            "preparation": part.preparation.model_copy(update={"recipe_snapshot": ref}),
        }
    )
    combo = changed(combo, components=(part, combo.components[1]))
    result = evaluate((combo, (revised, candidates[1]), kb, context))
    assert result.status is expected
    assert all(e.status is RuleStatus.PASS for e in result.trace.evaluations)


def test_independent_manifest_digest_includes_source_context_obligations_and_roles() -> None:
    result = evaluate(packet())
    wire = dict(
        schemaVersion="combination-check-manifest.v1",
        combination=result.combination.model_dump(mode="json", by_alias=True),
        trustedCombination=result.trusted_combination.model_dump(mode="json", by_alias=True)
        if result.trusted_combination
        else None,
        context=result.recipes.context.model_dump(mode="json", by_alias=True),
        recipeManifestDigests=[
            d.resolution.manifest.content_digest for d in result.recipes.decisions
        ],
        acceptedRoleReferences=[
            r.model_dump(mode="json", by_alias=True) for r in result.accepted_role_references
        ],
        requiredChecks=[
            r.model_dump(mode="json", by_alias=True) for r in result.trace.required_checks
        ],
        deferredChecks=[r.model_dump(mode="json", by_alias=True) for r in result.deferred_checks],
    )

    def encode(value: Any) -> str:
        if isinstance(value, dict):
            return (
                "{" + ",".join(json.dumps(k) + ":" + encode(value[k]) for k in sorted(value)) + "}"
            )
        if isinstance(value, list):
            return "[" + ",".join(sorted(encode(v) for v in value)) + "]"
        return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))

    digest = hashlib.sha256(encode(wire).encode()).hexdigest()
    assert result.trace.manifest_id == "combination-manifest-" + digest
    assert result.trace.manifest_version == "combination-check-manifest.v1:" + digest


@pytest.mark.parametrize(
    "mutation", ["prerequisites", "roles", "recipes", "trace", "status", "source", "deferred"]
)
def test_output_cannot_drop_mandatory_obligations_or_source_proofs(mutation: str) -> None:
    result = evaluate(packet())
    updates: dict[str, Any]
    if mutation == "prerequisites":
        updates = {"prerequisites": result.prerequisites[:-1]}
    elif mutation == "roles":
        updates = {"accepted_role_references": ()}
    elif mutation == "recipes":
        updates = {
            "recipes": result.recipes.model_copy(
                update={"decisions": (), "eligible_ids": (), "excluded_ids": ()}
            )
        }
    elif mutation == "trace":
        updates = {
            "trace": result.trace.model_copy(update={"required_checks": (), "evaluations": ()})
        }
    elif mutation == "status":
        updates = {"status": RuleStatus.UNKNOWN}
    elif mutation == "source":
        updates = {"trusted_combination": None}
    else:
        updates = {"deferred_checks": ()}
    with pytest.raises(ValidationError):
        CombinationEligibilityResult.model_validate(result.model_copy(update=updates))


def test_missing_authority_cannot_be_hidden_by_all_not_applicable_rules() -> None:
    assert evaluate(packet(enabled=False), trusted=False).status is RuleStatus.UNKNOWN


def test_standalone_craving_cannot_enter_combination_path() -> None:
    data = packet()
    body = data[3].model_dump(exclude={"content_digest"})
    body["workflow"] = KnowledgeWorkflow.CRAVING_DISCOVERY
    revised = repin(data, context=RuleContext.build(body))
    with pytest.raises(ValidationError, match="standalone craving"):
        evaluate(revised)


@pytest.mark.parametrize("bad_value", [0, 1, "true", ()])
def test_malformed_registered_observation_cannot_hide_behind_unknown_authority(
    bad_value: Any,
) -> None:
    data = packet()
    obs = data[0].observations[0]
    # Use unchecked storage to test the public boundary, preserving malformed units too.
    forged = obs.model_copy(
        update={"observation": obs.observation.model_copy(update={"value": bad_value})}
    )
    combo = data[0].model_copy(update={"observations": (forged, *data[0].observations[1:])})
    with pytest.raises(ValidationError):
        evaluate((combo, *data[1:]), trusted=False)


def test_unrelated_failing_candidate_does_not_exclude_referenced_recipes() -> None:
    data = packet()
    combo = changed(data[0], components=(data[0].components[0],))
    body = data[1][1].model_dump(exclude={"content_digest"})
    body["facts"] = (fact("synthetic_flag", FactSubjectKind.RECIPE, "beta", False),)
    bad_beta = CandidateRecipeFacts.build(body)
    result = evaluate((combo, (data[1][0], bad_beta), *data[2:]))
    assert result.status is RuleStatus.PASS
    assert result.recipes.eligible_ids == ("alpha",)
    assert len(result.recipes.decisions) == 1
    with pytest.raises(ValidationError):
        evaluate(data, candidates=(*data[1], data[1][0]))
    with pytest.raises(ValidationError):
        evaluate(
            (combo, *data[1:]),
            candidates=(data[1][0], bad_beta.model_copy(update={"eligibility": True})),
        )


def test_multiple_same_attribute_obligations_all_evaluate() -> None:
    rules = (
        declaration("recipe", RuleScope.RECIPE, "synthetic_flag"),
        declaration("allow", RuleScope.COMBINATION, ROLES),
        declaration("deny", RuleScope.COMBINATION, ROLES, operator=PredicateOperator.NE),
    )
    result = evaluate(packet(rules=rules))
    assert result.status is RuleStatus.FAIL
    assert tuple((e.rule.rule_id, e.status) for e in result.trace.evaluations) == (
        ("allow", RuleStatus.PASS),
        ("deny", RuleStatus.FAIL),
    )


@pytest.mark.parametrize("token", ["unknown", "synthetic-rule-evaluation.v2", False, None])
def test_unsupported_context_policy_tokens_reject(token: Any) -> None:
    data = packet()
    with pytest.raises(ValidationError):
        evaluate(data, context=data[3].model_copy(update={"evaluator_policy_version": token}))


def test_unapproved_mandatory_rule_cannot_enter_new_evaluator() -> None:
    rules = (
        declaration("recipe", RuleScope.RECIPE, "synthetic_flag"),
        declaration(
            "roles",
            RuleScope.COMBINATION,
            ROLES,
            approval_status=ApprovalStatus.PENDING,
            approved_by=None,
            approval_reference=None,
        ),
    )
    with pytest.raises(ValidationError, match="unapproved"):
        evaluate(packet(rules=rules))


@pytest.mark.parametrize("enabled", [True, False])
def test_unknown_dependency_dominates_false_local_applicability(enabled: bool) -> None:
    data = packet(enabled=enabled)
    body = data[2].model_dump(exclude={"content_digest"})
    descriptor = data[2].applicability_descriptors[0]
    ref = RuleReference(rule_id="synthetic-context-guard", version="1")
    body["applicability_descriptors"] = (
        descriptor.model_copy(update={"dependencies": (ref,)}),
        ApplicabilityDescriptor(
            reference=ref,
            rule_references=(),
            required_context_facts=("synthetic_context_guard",),
            evidence=(proof("guard"),),
        ),
    )
    revised = repin(data, kb=build_knowledge_snapshot(body))
    result = evaluate(revised)
    assert result.status is RuleStatus.UNKNOWN
    assert all(e.applicability is ApplicabilityStatus.UNKNOWN for e in result.trace.evaluations)
    assert proof("guard") in result.evidence


@pytest.mark.parametrize("fixed", [False, True])
def test_exact_independent_source_snapshot_mismatch_is_invalid(fixed: bool) -> None:
    data = packet(fixed=fixed)
    original = data[0]
    for changes in (
        {"snapshot_version": "2"},
        {"evidence": (proof("different-source"),)},
    ):
        revised = changed(original, **changes)
        with pytest.raises(ValidationError, match="upstream snapshot"):
            evaluate(data, trusted_combination=revised)


def test_well_shaped_numeric_fact_under_boolean_attribute_is_invalid() -> None:
    data = packet()
    obs = data[0].observations[0]
    revised_observation = obs.model_copy(
        update={
            "observation": FactObservation(
                fact_id=ROLES,
                value=0,
                complete=True,
                unit=MeasurementUnit.MG,
                evidence=(proof("numeric-observation"),),
            )
        }
    )
    # The generic DTO can carry numeric declarations; the registered policy cannot.
    revised_observation = revised_observation.model_copy(
        update={
            "measurement_basis": CombinationMeasurementBasis.AS_RECORDED,
            "basis_reference": proof("recorded-numeric-basis"),
        }
    )
    combo = changed(data[0], observations=(revised_observation, data[0].observations[1]))
    with pytest.raises(ValidationError, match="boolean"):
        evaluate((combo, *data[1:]), trusted=False)


def test_full_candidate_validation_is_atomic_and_preserves_input_objects() -> None:
    data = packet()
    before = [obj.model_dump_json() for obj in (data[0], *data[1], data[2], data[3])]
    evaluate(data)
    assert before == [obj.model_dump_json() for obj in (data[0], *data[1], data[2], data[3])]


def test_unchanged_recipe_prerequisites_with_multiple_component_orders() -> None:
    data = packet()
    first = evaluate(data)
    reordered = changed(
        data[0],
        components=tuple(reversed(data[0].components)),
        observations=tuple(reversed(data[0].observations)),
    )
    second = evaluate((reordered, *data[1:]))
    assert first.status is second.status is RuleStatus.PASS
    assert first.trace == second.trace
    assert first.recipes == second.recipes
    assert first.prerequisites == second.prerequisites


def test_trace_observations_cannot_detach_from_trusted_source() -> None:
    result = evaluate(packet())
    evaluation = result.trace.evaluations[0]
    replacement = evaluation.facts[0].model_copy(update={"value": False})
    bad_evaluation = evaluation.model_copy(
        update={"facts": (replacement,), "status": RuleStatus.FAIL}
    )
    trace = result.trace.model_copy(
        update={"evaluations": (bad_evaluation, *result.trace.evaluations[1:])}
    )
    with pytest.raises(ValidationError, match="exact combination/context"):
        CombinationEligibilityResult.model_validate(
            result.model_copy(update={"trace": trace, "status": RuleStatus.FAIL})
        )


@pytest.mark.parametrize(
    "operator,observed,expected,forged",
    [
        (PredicateOperator.EQ, False, RuleStatus.FAIL, RuleStatus.PASS),
        (PredicateOperator.NE, True, RuleStatus.FAIL, RuleStatus.PASS),
        (PredicateOperator.EQ, True, RuleStatus.PASS, RuleStatus.FAIL),
        (PredicateOperator.NE, False, RuleStatus.PASS, RuleStatus.FAIL),
    ],
)
def test_serialized_result_rejects_relabelled_boolean_outcome(
    operator: PredicateOperator, observed: bool, expected: RuleStatus, forged: RuleStatus
) -> None:
    rules = (
        declaration("recipe", RuleScope.RECIPE, "synthetic_flag"),
        declaration("roles", RuleScope.COMBINATION, ROLES, operator=operator),
    )
    result = evaluate(packet(rules=rules, compatible=observed))
    assert result.status is expected
    wire = result.model_dump(mode="json", by_alias=True)
    wire["trace"]["evaluations"][0]["status"] = forged.value
    wire["status"] = forged.value
    with pytest.raises(ValidationError, match="boolean predicate"):
        validate_contract_json(CombinationEligibilityResult, json.dumps(wire))


@pytest.mark.parametrize("fixed", [False, True])
def test_separately_deserialized_upstream_dtos_and_repeated_evaluation(fixed: bool) -> None:
    combo, candidates, kb, context = packet(fixed=fixed)
    proposal_wire = combo.model_dump_json(by_alias=True)
    proposal = validate_contract_json(CombinationFacts, proposal_wire)
    source = validate_contract_json(CombinationFacts, proposal_wire)
    accepted = tuple(
        validate_contract_json(CandidateRecipeFacts, c.model_dump_json(by_alias=True))
        for c in candidates
    )
    selected_kb = validate_contract_json(KnowledgeBaseSnapshot, kb.model_dump_json(by_alias=True))
    selected_context = validate_contract_json(RuleContext, context.model_dump_json(by_alias=True))
    assert source is not proposal
    # The test deliberately designates a separate fictional source; parsing does
    # not authenticate either copy. Exercise exactly the public integration call.
    outputs = [
        evaluate_combination(
            proposal,
            candidates=accepted,
            knowledge=selected_kb,
            context=selected_context,
            trusted_combination=source,
        )
        for _ in range(3)
    ]
    assert all(result.status is RuleStatus.PASS for result in outputs)
    assert len({result.model_dump_json(by_alias=True) for result in outputs}) == 1
    assert source.model_dump_json(by_alias=True) == proposal_wire


def test_preparation_cannot_be_transplanted_between_candidates_with_equal_labels() -> None:
    data = packet()
    combo = data[0]
    assert (
        data[1][0].graph_recipe_reference.canonical_name
        == data[1][1].graph_recipe_reference.canonical_name
    )
    parts = (
        combo.components[0].model_copy(update={"preparation": combo.components[1].preparation}),
        combo.components[1],
    )
    with pytest.raises(ValidationError, match="exact recipe snapshot"):
        evaluate(
            (combo.model_copy(update={"components": parts}), *data[1:]), trusted_combination=combo
        )


def test_quantity_cannot_be_transplanted_between_candidates() -> None:
    data = packet(fixed=True)
    combo = data[0]
    parts = (
        combo.components[0].model_copy(update={"quantity": combo.components[1].quantity}),
        combo.components[1],
    )
    with pytest.raises(ValidationError, match="quantity preparation/basis"):
        evaluate(
            (combo.model_copy(update={"components": parts}), *data[1:]), trusted_combination=combo
        )


def test_portion_evidence_swap_cannot_hide_behind_valid_local_quantity_bindings() -> None:
    data = packet(fixed=True)
    parts = []
    for component in data[0].components:
        assert component.quantity is not None
        parts.append(
            component.model_copy(
                update={
                    "quantity": component.quantity.model_copy(
                        update={
                            "portion_reference": proof(
                                "portion-for-" + component.recipe_snapshot.recipe_id
                            ),
                        }
                    )
                }
            )
        )
    source = changed(data[0], components=tuple(parts))
    assert evaluate((source, *data[1:])).status is RuleStatus.PASS
    # An untrusted producer can recompute integrity; the independent source pin
    # must still reject the cross-candidate evidence swap.
    body = source.model_dump(exclude={"content_digest"})
    body["components"][0]["quantity"]["portion_reference"] = body["components"][1]["quantity"][
        "portion_reference"
    ]
    tampered = CombinationFacts.build(body)
    received = validate_contract_json(CombinationFacts, tampered.model_dump_json(by_alias=True))
    with pytest.raises(ValidationError, match="upstream snapshot"):
        evaluate((received, *data[1:]), trusted_combination=source)


@pytest.mark.parametrize("fixed", [False, True])
def test_planned_swap_retains_day_week_obligations_without_feasibility_claim(fixed: bool) -> None:
    data = packet(fixed=fixed)
    body = data[3].model_dump(exclude={"content_digest"})
    body["workflow"] = KnowledgeWorkflow.PLANNED_SWAP
    selected = repin(data, context=RuleContext.build(body))
    result = evaluate(selected)
    assert result.status is RuleStatus.PASS
    assert result.plan_feasibility == "NOT_EVALUATED"
    assert tuple(r.rule_id for r in result.deferred_checks) == ("day", "week")
    assert all(e.rule.scope is RuleScope.COMBINATION for e in result.trace.evaluations)


def test_combination_stage_preserves_exact_phase3_decisions_and_obligations() -> None:
    data = packet()
    before = filter_candidates(data[1], knowledge=data[2], context=data[3])
    result = evaluate(data)
    after = filter_candidates(data[1], knowledge=data[2], context=data[3])
    assert result.recipes == before == after
    for decision in before.decisions:
        deferred = decision.resolution.manifest.deferred_checks
        assert (
            tuple(r for r in deferred if r.scope is RuleScope.COMBINATION)
            == result.trace.required_checks
        )
        assert (
            tuple(r for r in deferred if r.scope in (RuleScope.DAY, RuleScope.WEEK))
            == result.deferred_checks
        )
