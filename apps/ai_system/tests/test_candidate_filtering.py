"""Whole-batch fail-closed filtering, explanation binding and hostile DTO regressions."""

from itertools import permutations
from typing import Any

import pytest
from pydantic import ValidationError
from test_rule_evaluation import numeric_fact, numeric_rule
from test_rule_fact_resolution import graph_packet, ingredient_line, replace_graph, selected
from test_rule_manifest import changed_candidate, changed_context, definition, fact, packet, source

from savora_ai.core.reasoning.evaluation import evaluate_rule_checks
from savora_ai.core.reasoning.filtering import filter_candidates
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    FactSubjectKind,
    RuleContext,
    validate_contract_json,
)
from savora_ai.schemas.filtering import FilterCandidatesResult
from savora_ai.schemas.food_graph import (
    FoodEntity,
    FoodEntityKind,
    FoodGraphSnapshot,
    RelationAssertion,
    TaxonomyAssignmentAssertion,
)
from savora_ai.schemas.knowledge import ApprovalStatus, RuleScope, RuleSeverity
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot, KnowledgeWorkflow
from savora_ai.schemas.reasoning import ApplicabilityStatus, RuleStatus


def filtered(
    inputs: tuple[KnowledgeBaseSnapshot, CandidateRecipeFacts, RuleContext],
) -> FilterCandidatesResult:
    return filter_candidates((inputs[1],), knowledge=inputs[0], context=inputs[2])


@pytest.mark.parametrize(
    "value,expected",
    [(False, RuleStatus.PASS), (True, RuleStatus.FAIL), (None, RuleStatus.UNKNOWN)],
)
def test_basic_hard_outcomes(value: bool | None, expected: RuleStatus) -> None:
    inputs = packet(candidate_facts=(fact(value=value, complete=value is not None),))
    result = filtered(inputs)
    assert result.decisions[0].status is expected
    assert result.eligible_ids == (("recipe",) if expected is RuleStatus.PASS else ())
    assert result.excluded_ids == (() if expected is RuleStatus.PASS else ("recipe",))
    assert result.plan_feasibility == "NOT_EVALUATED"
    assert (
        validate_contract_json(FilterCandidatesResult, result.model_dump_json(by_alias=True))
        == result
    )


def test_known_fail_dominates_unknown_and_every_rule_is_evaluated() -> None:
    rules = (
        definition("a-fails", value=True),
        definition(
            "b-unknown",
            attribute="synthetic_profile_flag",
            required_facts=("synthetic_profile_flag",),
        ),
        definition("c-passes"),
    )
    result = filtered(packet(rules))
    decision = result.decisions[0]
    assert decision.status is RuleStatus.FAIL
    assert [item.status for item in decision.trace.evaluations] == [
        RuleStatus.FAIL,
        RuleStatus.UNKNOWN,
        RuleStatus.PASS,
    ]
    assert len(decision.explanations) == 3
    assert decision.explanations[1].facts[0].source == "MISSING"
    assert result.eligible_ids == ()


@pytest.mark.parametrize("missing", ["recipe", "profile", "condition"])
def test_missing_required_facts_are_explained_and_excluded(missing: str) -> None:
    profile = definition(
        attribute="synthetic_profile_flag",
        required_facts=("synthetic_profile_flag",),
        scope=RuleScope.PROFILE,
    )
    inputs = packet(
        (profile,) if missing == "profile" else None,
        candidate_facts=() if missing == "recipe" else None,
        context_facts=() if missing == "condition" else None,
    )
    result = filtered(inputs)
    assert result.decisions[0].status is RuleStatus.UNKNOWN
    assert result.excluded_ids == ("recipe",)
    decision = result.decisions[0]
    names = {item.fact.fact_id for item in decision.resolution.facts}
    assert all(
        name in names for rule in decision.trace.required_checks for name in rule.required_facts
    )
    assert decision.explanations[0].evidence


@pytest.mark.parametrize("condition", [False, None])
def test_not_applicable_resolves_check_unknown_condition_does_not(condition: bool | None) -> None:
    inputs = packet(
        context_facts=(
            fact(
                "synthetic_context_enabled",
                condition,
                complete=condition is not None,
                subject=FactSubjectKind.CONTEXT,
            ),
        ),
        candidate_facts=(),
    )
    result = filtered(inputs)
    evaluation = result.decisions[0].trace.evaluations[0]
    assert evaluation.status is RuleStatus.UNKNOWN
    assert evaluation.applicability is (
        ApplicabilityStatus.NOT_APPLICABLE if condition is False else ApplicabilityStatus.UNKNOWN
    )
    assert result.eligible_ids == (("recipe",) if condition is False else ())
    assert result.decisions[0].explanations[0].evaluation == evaluation


@pytest.mark.parametrize("mode", ["empty", "soft", "deferred_only"])
def test_zero_recipe_stage_mandatory_checks_never_eligible(mode: str) -> None:
    rules = (
        ()
        if mode == "empty"
        else (definition(severity=RuleSeverity.SOFT),)
        if mode == "soft"
        else (definition(scope=RuleScope.DAY),)
    )
    inputs = packet(rules, workflow=KnowledgeWorkflow.WEEKLY_PLAN)
    result = filtered(inputs)
    assert result.eligible_ids == () and result.excluded_ids == ("recipe",)
    assert result.decisions[0].status is RuleStatus.UNKNOWN
    assert result.decisions[0].trace.evaluations == ()
    assert result.decisions[0].explanations == ()
    if mode == "deferred_only":
        assert len(result.decisions[0].resolution.manifest.deferred_checks) == 1


@pytest.mark.parametrize("workflow", list(KnowledgeWorkflow))
def test_recipe_pass_preserves_deferred_obligations(workflow: KnowledgeWorkflow) -> None:
    rules = (
        definition(),
        *(
            definition(scope.value, scope=scope, value=True)
            for scope in (
                RuleScope.COMBINATION,
                RuleScope.DAY,
                RuleScope.WEEK,
            )
        ),
    )
    result = filtered(packet(rules, workflow=workflow))
    assert result.eligible_ids == ("recipe",)
    manifest = result.decisions[0].resolution.manifest
    assert {rule.scope for rule in manifest.deferred_checks} == (
        set()
        if workflow is KnowledgeWorkflow.CRAVING_DISCOVERY
        else {
            RuleScope.COMBINATION,
            RuleScope.DAY,
            RuleScope.WEEK,
        }
    )
    assert result.stage == "RECIPE_FILTER" and result.plan_feasibility == "NOT_EVALUATED"


@pytest.mark.parametrize(
    "assertion,expected",
    [
        (None, RuleStatus.UNKNOWN),
        (RelationAssertion.PRESENT, RuleStatus.PASS),
        (RelationAssertion.ABSENT, RuleStatus.FAIL),
    ],
)
def test_filter_uses_kb_graph_assertions(
    assertion: RelationAssertion | None, expected: RuleStatus
) -> None:
    inputs = graph_packet(contains=assertion)
    result = filtered(inputs)
    decision = result.decisions[0]
    assert decision.status is expected
    assert decision.trace.evaluations == evaluate_rule_checks(*inputs, decision.resolution.manifest)
    assert (
        decision.explanations[0].facts[0].relations
        == selected(decision.resolution, "synthetic_contains_target").relations
    )


@pytest.mark.parametrize("state", ["partial", "missing", "unmapped"])
def test_incomplete_inventory_cannot_authorize_negative_safety(state: str) -> None:
    rule = definition(
        attribute="synthetic_contains_target",
        required_facts=("synthetic_contains_target",),
        value=False,
    )
    inputs = graph_packet(
        rules=(rule,),
        contains=RelationAssertion.ABSENT,
        inventory_state="partial"
        if state == "partial"
        else "missing"
        if state == "missing"
        else "complete",
        inventory_lines=(ingredient_line("unmapped"),) if state == "unmapped" else None,
    )
    result = filtered(inputs)
    assert result.decisions[0].status is RuleStatus.UNKNOWN
    assert result.eligible_ids == ()
    assert result.decisions[0].explanations[0].facts[0].reason_code == "INGREDIENT_MAPPING_GAP"


@pytest.mark.parametrize("name", ["synthetic_dietary_target", "synthetic_cuisine_target"])
def test_taxonomy_support_flows_into_evaluation_and_explanation(name: str) -> None:
    inputs = graph_packet(
        (name,),
        dietary=TaxonomyAssignmentAssertion.PRESENT if name == "synthetic_dietary_target" else None,
        cuisine=TaxonomyAssignmentAssertion.PRESENT if name == "synthetic_cuisine_target" else None,
    )
    result = filtered(inputs)
    assert result.eligible_ids == ("recipe",)
    explanation = result.decisions[0].explanations[0]
    assert explanation.facts[0].taxonomy is not None
    assert explanation.facts[0].taxonomy.status is not None
    assert any(e.evidence_id.endswith("assignment") for e in explanation.evidence)


@pytest.mark.parametrize(
    "name", ["synthetic_allergen_absent", "synthetic_clinically_safe", "synthetic_dietary_target"]
)
def test_origin_or_predicted_cuisine_never_produces_false_safety_eligibility(name: str) -> None:
    inputs = graph_packet(
        (name,),
        origin_length=3,
        cuisine=TaxonomyAssignmentAssertion.PRESENT,
        candidate_facts=(fact(name, True),),
    )
    result = filtered(inputs)
    assert result.decisions[0].status is RuleStatus.UNKNOWN
    assert result.eligible_ids == ()


def test_opposing_graph_claim_rejects_entire_batch() -> None:
    kb, candidate, context = graph_packet(
        contains=RelationAssertion.PRESENT,
        candidate_facts=(fact("synthetic_contains_target", False),),
    )
    with pytest.raises(ValidationError, match="contradicts"):
        filter_candidates((candidate,), knowledge=kb, context=context)


def test_empty_batch_validates_shared_inputs_and_returns_empty_partition() -> None:
    kb, _, context = packet()
    result = filter_candidates((), knowledge=kb, context=context)
    assert result.eligible_ids == result.excluded_ids == result.decisions == ()
    assert result.context == context and result.kb_digest == kb.content_digest


@pytest.mark.parametrize(
    "case",
    [
        "kb_digest",
        "context_digest",
        "release",
        "evaluator",
        "catalogue",
        "coverage",
        "unapproved",
        "condition_type",
    ],
)
def test_empty_batch_does_not_skip_shared_validation(case: str) -> None:
    kb, _, context = packet()
    if case == "kb_digest":
        kb = kb.model_copy(update={"content_digest": "0" * 64})
    elif case == "context_digest":
        context = context.model_copy(update={"content_digest": "0" * 64})
    elif case == "release":
        context = changed_context(context, expected_kb_version="stale")
    elif case == "evaluator":
        context = context.model_copy(update={"evaluator_policy_version": "unsupported"})
    elif case == "catalogue":
        kb = kb.model_copy(update={"check_catalogue": ()})
    elif case == "coverage":
        kb = kb.model_copy(update={"rule_catalogue_coverage": ()})
    elif case == "condition_type":
        context = changed_context(
            context,
            facts=(fact("synthetic_context_enabled", "True", subject=FactSubjectKind.CONTEXT),),
        )
    else:
        pending = definition(
            approval_status=ApprovalStatus.PENDING, approved_by=None, approval_reference=None
        )
        kb, _, context = packet((pending,))
    with pytest.raises(ValidationError):
        filter_candidates((), knowledge=kb, context=context)


@pytest.mark.parametrize(
    "field",
    [
        "expected_kb_id",
        "expected_kb_version",
        "expected_kb_digest",
        "expected_graph_id",
        "expected_graph_version",
        "expected_catalogue_version",
        "expected_check_catalogue_version",
        "expected_taxonomy_version",
    ],
)
def test_wrong_shared_release_pins_reject_batch(field: str) -> None:
    kb, candidate, context = packet()
    context = changed_context(context, **{field: "0" * 64 if field.endswith("digest") else "stale"})
    with pytest.raises(ValidationError):
        filter_candidates((candidate,), knowledge=kb, context=context)


@pytest.mark.parametrize(
    "field", ["context_id", "context_version", "graph_version", "profile_id", "profile_version"]
)
def test_wrong_candidate_or_profile_context_binding_rejected(field: str) -> None:
    kb, candidate, context = packet()
    if field.startswith("profile"):
        profile_fact = fact("synthetic_profile_flag", False, subject=FactSubjectKind.PROFILE)
        context = context.model_copy(
            update={
                "facts": (
                    profile_fact.model_copy(
                        update={
                            "subject_id" if field == "profile_id" else "subject_version": "wrong",
                        }
                    ),
                )
            }
        )
    elif field == "graph_version":
        candidate = changed_candidate(candidate, graph_version="stale")
    else:
        candidate = changed_candidate(candidate, context_id="context", context_version="context-v1")
        candidate = changed_candidate(candidate, **{field: "wrong"})
    with pytest.raises(ValidationError):
        filter_candidates((candidate,), knowledge=kb, context=context)


@pytest.mark.parametrize("revision", [False, True])
def test_duplicate_candidates_rejected(revision: bool) -> None:
    kb, candidate, context = packet()
    duplicate = (
        changed_candidate(candidate, snapshot_version="snapshot-v2") if revision else candidate
    )
    with pytest.raises(ValidationError, match="duplicate candidate"):
        filter_candidates((candidate, duplicate), knowledge=kb, context=context)


def batch_packet() -> tuple[KnowledgeBaseSnapshot, tuple[CandidateRecipeFacts, ...], RuleContext]:
    kb, original, context = packet()
    recipe_ids = ("z-pass", "a-fail", "m-unknown")
    nodes = tuple(
        FoodEntity(
            entity_id="node-" + id_,
            version="graph-entity-v2",
            kind=FoodEntityKind.RECIPE_REFERENCE,
            catalogue_reference=id_,
            canonical_name="Synthetic recipe",
            evidence=(source(),),
        )
        for id_ in recipe_ids
    )
    graph = FoodGraphSnapshot.model_validate(
        kb.graph.model_dump() | {"entities": (*kb.graph.entities, *nodes)}
    )
    body: dict[str, Any] = kb.model_dump(exclude={"content_digest"}) | {"graph": graph}
    kb = build_knowledge_snapshot(body)
    context = changed_context(context, expected_kb_digest=kb.content_digest)
    candidates = []
    for id_, value, node in zip(recipe_ids, (False, True, None), nodes, strict=True):
        observation = fact(value=value, complete=value is not None).model_copy(
            update={"subject_id": id_}
        )
        candidates.append(
            changed_candidate(
                original,
                recipe_id=id_,
                graph_recipe_entity_id=node.entity_id,
                graph_recipe_reference=node,
                facts=(observation,),
                ingredient_coverage=original.ingredient_coverage.model_copy(
                    update={"recipe_id": id_}
                ),
                snapshot_id="snapshot-" + id_,
            )
        )
    return kb, tuple(candidates), context


def test_batch_input_order_does_not_change_outputs() -> None:
    kb, candidates, context = batch_packet()
    expected = filter_candidates(candidates, knowledge=kb, context=context)
    assert expected.eligible_ids == ("z-pass",)
    assert expected.excluded_ids == ("a-fail", "m-unknown")
    assert [item.trace.candidate_id for item in expected.decisions] == [
        "a-fail",
        "m-unknown",
        "z-pass",
    ]
    for permutation in permutations(candidates):
        assert filter_candidates(permutation, knowledge=kb, context=context) == expected


@pytest.mark.parametrize("mode", ["copy", "construct"])
@pytest.mark.parametrize("bad", ["extra", "fact", "enum", "coverage"])
def test_malicious_candidate_rejects_batch_without_partial_success(mode: str, bad: str) -> None:
    kb, candidates, context = batch_packet()
    candidate = candidates[1]
    changes: dict[str, Any] = {
        "extra": {"affirmative_resolution": True},
        "fact": {
            "facts": (
                candidate.facts[0].model_copy(
                    update={
                        "observation": candidate.facts[0].observation.model_copy(
                            update={"value": float("inf")}
                        )
                    }
                ),
            )
        },
        "enum": {
            "graph_recipe_reference": candidate.graph_recipe_reference.model_copy(
                update={"kind": "RECIPE_REFERENCE"}
            )
        },
        "coverage": {
            "ingredient_coverage": candidate.ingredient_coverage.model_copy(
                update={"inventory_complete": 1}
            )
        },
    }[bad]
    corrupted = (
        candidate.model_copy(update=changes)
        if mode == "copy" or bad == "extra"
        else type(candidate).model_construct(**(vars(candidate) | changes))
    )
    with pytest.raises(ValidationError):
        filter_candidates((candidates[0], corrupted, candidates[2]), knowledge=kb, context=context)


@pytest.mark.parametrize("target", ["workflow", "mapping", "rule", "graph"])
def test_forged_enum_members_rejected(target: str) -> None:
    kb, candidate, context = graph_packet()
    if target == "workflow":
        kind, token = KnowledgeWorkflow, "CRAVING_DISCOVERY"
    elif target == "rule":
        kind, token = RuleSeverity, "ABSOLUTE"
    elif target == "mapping":
        from savora_ai.schemas.candidates import IngredientMappingStatus

        kind, token = IngredientMappingStatus, "MAPPED"
    else:
        kind, token = RelationAssertion, "PRESENT"
    forged: Any = str.__new__(kind, token)
    forged._value_ = token
    if target == "workflow":
        context = context.model_copy(update={"workflow": forged})
    elif target == "rule":
        kb = kb.model_copy(update={"rules": (kb.rules[0].model_copy(update={"severity": forged}),)})
    elif target == "mapping":
        assert candidate.ingredient_coverage.lines is not None
        line = candidate.ingredient_coverage.lines[0].model_copy(update={"mapping_status": forged})
        candidate = candidate.model_copy(
            update={
                "ingredient_coverage": candidate.ingredient_coverage.model_copy(
                    update={"lines": (line,)}
                )
            }
        )
    else:
        kb = kb.model_copy(
            update={
                "graph": kb.graph.model_copy(
                    update={
                        "relations": (
                            kb.graph.relations[0].model_copy(update={"assertion": forged}),
                        )
                    }
                )
            }
        )
    with pytest.raises(ValidationError):
        filter_candidates((candidate,), knowledge=kb, context=context)


@pytest.mark.parametrize(
    "field",
    [
        "manifest_id",
        "manifest_version",
        "manifest_digest",
        "candidate_id",
        "candidate_version",
        "candidate_digest",
        "context_id",
        "context_version",
        "context_digest",
        "kb_id",
        "kb_version",
        "kb_digest",
    ],
)
def test_full_explanation_binding_rejects_corrupted_output(field: str) -> None:
    result = filtered(packet())
    decision = result.decisions[0]
    explanation = decision.explanations[0]
    bad = explanation.model_copy(update={field: "0" * 64 if field.endswith("digest") else "wrong"})
    altered = result.model_copy(
        update={"decisions": (decision.model_copy(update={"explanations": (bad,)}),)}
    )
    with pytest.raises(ValidationError):
        FilterCandidatesResult.model_validate(altered)


@pytest.mark.parametrize(
    "case",
    [
        "eligible_partition",
        "status",
        "trace",
        "explanation_missing",
        "explanation_evidence",
        "scope",
    ],
)
def test_output_dto_structural_consistency(case: str) -> None:
    result = filtered(packet())
    decision = result.decisions[0]
    if case == "eligible_partition":
        altered = result.model_copy(update={"eligible_ids": ()})
    elif case == "scope":
        altered = result.model_copy(update={"plan_feasibility": "FEASIBLE"})
    else:
        changes = {
            "status": {"status": RuleStatus.FAIL},
            "trace": {"trace": decision.trace.model_copy(update={"evaluations": ()})},
            "explanation_missing": {"explanations": ()},
            "explanation_evidence": {
                "explanations": (decision.explanations[0].model_copy(update={"evidence": ()}),)
            },
        }[case]
        altered = result.model_copy(update={"decisions": (decision.model_copy(update=changes),)})
    with pytest.raises(ValidationError):
        FilterCandidatesResult.model_validate(altered)


def test_explanation_has_required_rule_approval_applicability_and_fact_evidence() -> None:
    result = filtered(packet())
    explanation = result.decisions[0].explanations[0]
    assert {ref.evidence_id for ref in explanation.evidence} == {
        "test-source",
        "test-approval",
        "app-synthetic-context-enabled",
        "observation-synthetic_context_enabled",
        "observation-synthetic_flag",
    }
    assert explanation.evaluation.reason == "synthetic-rule-evaluation.v1:PREDICATE_TRUE"


def test_json_duplicate_keys_rejected_for_filter_result() -> None:
    result = filtered(packet())
    raw = result.model_dump_json(by_alias=True)[:-1] + ',"eligibleIds":["recipe"]}'
    with pytest.raises(ValidationError, match="duplicate JSON"):
        validate_contract_json(FilterCandidatesResult, raw)


def test_strict_batch_tuple_and_input_immutability() -> None:
    inputs = packet()
    original = tuple(item.model_dump_json() for item in inputs)
    first = filtered(inputs)
    assert first == filtered(inputs)
    assert tuple(item.model_dump_json() for item in inputs) == original
    with pytest.raises(ValidationError):
        filter_candidates([inputs[1]], knowledge=inputs[0], context=inputs[2])  # type: ignore[arg-type]


def test_graph_order_does_not_change_witnesses_evidence_or_filter_results() -> None:
    inputs = graph_packet(
        ("synthetic_contains_target", "synthetic_origin_target", "synthetic_cuisine_target"),
        contains=RelationAssertion.PRESENT,
        origin_length=3,
        cuisine=TaxonomyAssignmentAssertion.PRESENT,
        hierarchy=True,
    )
    graph = inputs[0].graph
    graph = FoodGraphSnapshot.model_validate(
        graph.model_dump()
        | {
            "entities": tuple(reversed(graph.entities)),
            "relations": tuple(reversed(graph.relations)),
            "taxonomy_terms": tuple(reversed(graph.taxonomy_terms)),
            "taxonomy_assignments": tuple(reversed(graph.taxonomy_assignments)),
        }
    )
    assert filtered(replace_graph(inputs, graph)) == filtered(inputs)


def test_explanation_cannot_relabel_resolved_observation() -> None:
    result = filtered(packet())
    explanation = result.decisions[0].explanations[0]
    record = explanation.facts[0]
    assert record.supplied_fact is not None
    changed = record.model_copy(
        update={
            "fact": record.fact.model_copy(
                update={"observation": record.fact.observation.model_copy(update={"value": True})}
            ),
            "supplied_fact": record.supplied_fact.model_copy(
                update={
                    "observation": record.supplied_fact.observation.model_copy(
                        update={"value": True}
                    )
                }
            ),
        }
    )
    with pytest.raises(ValidationError, match="observations differ"):
        type(explanation).model_validate(explanation.model_copy(update={"facts": (changed,)}))


def test_conflicting_evidence_across_batch_rejected() -> None:
    kb, candidates, context = batch_packet()
    contradicted = changed_candidate(
        candidates[0], evidence=(source("test-approval", source="opposing metadata"),)
    )
    with pytest.raises(ValidationError, match="conflicting evidence"):
        filter_candidates((contradicted, *candidates[1:]), knowledge=kb, context=context)


@pytest.mark.parametrize(
    "value,expected", [(0, RuleStatus.PASS), (7, RuleStatus.PASS), (8, RuleStatus.FAIL)]
)
def test_numeric_predicates_and_basis_evidence_flow_through_full_filter(
    value: int, expected: RuleStatus
) -> None:
    result = filtered(packet((numeric_rule(),), candidate_facts=(numeric_fact(value),)))
    assert result.decisions[0].status is expected
    assert result.decisions[0].explanations[0].facts[0].fact.observation.value == value
    assert "synthetic-per-100-g" in {
        ref.evidence_id for ref in result.decisions[0].explanations[0].evidence
    }
