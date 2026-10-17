"""Independent cross-phase fixtures, finite-domain oracle and hostile-boundary audit.

No earlier test fixtures, production predicate, aggregation or digest helpers are
used as expected-value oracles. All sources and quantities are fictional.
"""

import itertools
import json
from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from savora_ai.core.reasoning.daily import build_day_check_manifest, solve_daily_plan
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    FactSubjectKind,
    IngredientCoverage,
    RuleContext,
    VersionedFact,
    validate_contract_json,
)
from savora_ai.schemas.combinations import (
    CombinationComponent,
    CombinationFacts,
    CombinationMeasurementBasis,
    CombinationObservation,
    ComponentQuantity,
    PortionState,
    PreparationBinding,
    QuantityUnit,
    RecipeSnapshotReference,
)
from savora_ai.schemas.daily import (
    DailyMealOption,
    DailyOutcome,
    DailyPlanningRequest,
    DailySlotDomain,
    DailySourceReference,
    DailySourceSnapshot,
    ExpectedDayCheckManifest,
    FixedMealMeasurement,
    MealOptionReference,
    MealSlot,
    MealSlotSuitability,
)
from savora_ai.schemas.daily_solver import DailySearchLimits, DailySolveResult
from savora_ai.schemas.food_graph import (
    FoodEntity,
    FoodEntityKind,
    FoodGraphSnapshot,
    FoodRelation,
    FoodRelationType,
    RelationAssertion,
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
    KnowledgeWorkflow,
    RuleCatalogueCoverage,
)
from savora_ai.schemas.reasoning import ApplicabilityStatus, FactObservation, RuleStatus


def audit_evidence(name: str) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=name,
        version="audit-1",
        source="Independent Phase 5 fictional audit",
        locator="urn:phase5-audit:" + name,
        environment=RuleEnvironment.SYNTHETIC,
    )


def audit_rule(name: str, scope: RuleScope, attribute: str, **predicate: Any) -> RuleDefinition:
    return RuleDefinition.model_validate(
        dict(
            rule_id=name,
            version="audit-1",
            scope=scope,
            severity=RuleSeverity.ABSOLUTE,
            domain=RuleDomain.CULINARY,
            attribute=attribute,
            operator=PredicateOperator.EQ,
            value=True,
            required_facts=(attribute,),
            applicability_reference=RuleReference(rule_id="synthetic-context-enabled", version="1"),
            evidence=(audit_evidence(name),),
            rationale="Fictional audit requirement; no clinical meaning",
            lifecycle=RuleLifecycle.ACTIVE,
            environment=RuleEnvironment.SYNTHETIC,
            approval_status=ApprovalStatus.APPROVED,
            approved_by="fictional-auditor",
            approval_reference=audit_evidence("approval-" + name),
        )
        | predicate
    )


def numeric_check(operator: PredicateOperator, value: int) -> RuleDefinition:
    return audit_rule(
        "day-total",
        RuleScope.DAY,
        "synthetic_day_quantity_total",
        operator=operator,
        value=value,
        unit=MeasurementUnit.MG,
    )


def audit_case(
    amounts: tuple[int | None, ...] = (7, 11),
    *,
    target: int = 25,
    checks: tuple[RuleDefinition, ...] | None = None,
    domains: tuple[tuple[int, ...], ...] | None = None,
    unknown: tuple[int, ...] = (),
    rejected: tuple[int, ...] = (),
    enabled: bool | None = True,
    graph_backed: bool = False,
    graph_witness: bool = True,
) -> dict[str, Any]:
    """A single real recipe, several independently fixed meal configurations.

    Sharing a recipe intentionally checks configuration identity and repeated meal
    arithmetic, while keeping prerequisites independent of the search product.
    """
    ev = (audit_evidence("catalogue"),)
    recipe_node = FoodEntity(
        entity_id="audit-recipe-node",
        version="1",
        kind=FoodEntityKind.RECIPE_REFERENCE,
        canonical_name="Fictional dish",
        catalogue_reference="audit-recipe",
        evidence=ev,
    )
    role_node = FoodEntity(
        entity_id="audit-role",
        version="1",
        kind=FoodEntityKind.CULINARY_ROLE_REFERENCE,
        canonical_name="Fictional role",
        catalogue_reference="audit-role-ref",
        evidence=ev,
    )
    target_node = FoodEntity(
        entity_id="audit-target",
        version="1",
        kind=FoodEntityKind.INGREDIENT,
        canonical_name="Fictional ingredient",
        catalogue_reference="synthetic-target",
        evidence=ev,
    )
    graph = FoodGraphSnapshot(
        graph_id="audit-graph",
        version="1",
        catalogue_version="audit-foods",
        environment=RuleEnvironment.SYNTHETIC,
        entities=(role_node, recipe_node, *((target_node,) if graph_backed else ())),
        relations=(
            FoodRelation(
                relation_id="audit-exact-absence",
                version="1",
                source_id=recipe_node.entity_id,
                target_id=target_node.entity_id,
                relation_type=FoodRelationType.CONTAINS,
                assertion=RelationAssertion.ABSENT,
                evidence=(audit_evidence("absence-proof"),),
            ),
        )
        if graph_backed and graph_witness
        else (),
        evidence=ev,
    )
    rules = (
        audit_rule(
            "recipe-required",
            RuleScope.RECIPE,
            "synthetic_contains_target" if graph_backed else "synthetic_flag",
            value=not graph_backed,
        ),
        audit_rule(
            "meal-required", RuleScope.COMBINATION, "synthetic_combination_roles_compatible"
        ),
        *(checks if checks is not None else (numeric_check(PredicateOperator.EQ, target),)),
        audit_rule("week-deferred", RuleScope.WEEK, "synthetic_flag"),
    )
    references = tuple(RuleReference(rule_id=r.rule_id, version=r.version) for r in rules)
    cells = tuple(
        CheckCatalogueEntry(
            entry_id=f"audit-{workflow.value}-{scope.value}",
            version="1",
            kb_id="audit-kb",
            kb_version="1",
            check_catalogue_version="audit-checks",
            workflow=workflow,
            scope=scope,
            rule_references=tuple(
                ref for ref, r in zip(references, rules, strict=True) if r.scope is scope
            ),
            evidence=ev,
        )
        for workflow in KnowledgeWorkflow
        for scope in RuleScope
        if workflow is not KnowledgeWorkflow.CRAVING_DISCOVERY
        or scope in (RuleScope.PROFILE, RuleScope.RECIPE)
    )
    kb = build_knowledge_snapshot(
        dict(
            kb_id="audit-kb",
            version="1",
            environment=RuleEnvironment.SYNTHETIC,
            graph_id=graph.graph_id,
            graph_version=graph.version,
            catalogue_version=graph.catalogue_version,
            taxonomy_version=None,
            check_catalogue_version="audit-checks",
            graph=graph,
            rules=rules,
            active_rules=references,
            applicability_descriptors=(
                ApplicabilityDescriptor(
                    reference=RuleReference(rule_id="synthetic-context-enabled", version="1"),
                    rule_references=references,
                    required_context_facts=("synthetic_context_enabled",),
                    evidence=ev,
                ),
            ),
            check_catalogue=cells,
            rule_catalogue_coverage=tuple(
                RuleCatalogueCoverage(
                    coverage_id="coverage-" + cell.entry_id,
                    version="1",
                    kb_id="audit-kb",
                    kb_version="1",
                    check_catalogue_version="audit-checks",
                    workflow=cell.workflow,
                    scope=cell.scope,
                    complete=True,
                    reason="Fictional complete audit inventory",
                    evidence=ev,
                )
                for cell in cells
            ),
            evidence=ev,
        )
    )
    context = RuleContext.build(
        dict(
            context_id="audit-context",
            version="1",
            profile_id="audit-profile",
            profile_version="1",
            workflow=KnowledgeWorkflow.WEEKLY_PLAN,
            expected_kb_id=kb.kb_id,
            expected_kb_version=kb.version,
            expected_kb_digest=kb.content_digest,
            expected_graph_id=kb.graph_id,
            expected_graph_version=kb.graph_version,
            expected_catalogue_version=kb.catalogue_version,
            expected_taxonomy_version=kb.taxonomy_version,
            expected_check_catalogue_version=kb.check_catalogue_version,
            facts=(
                VersionedFact(
                    fact_id="synthetic_context_enabled",
                    version="1",
                    subject_kind=FactSubjectKind.CONTEXT,
                    subject_id="audit-context",
                    subject_version="1",
                    context_id="audit-context",
                    context_version="1",
                    observation=FactObservation(
                        fact_id="synthetic_context_enabled",
                        value=enabled,
                        complete=enabled is not None,
                        evidence=ev,
                    ),
                ),
            ),
            evidence=ev,
        )
    )
    candidate = CandidateRecipeFacts.build(
        dict(
            recipe_id="audit-recipe",
            recipe_version="1",
            catalogue_version=kb.catalogue_version,
            graph_id=kb.graph_id,
            graph_version=kb.graph_version,
            graph_recipe_entity_id=recipe_node.entity_id,
            graph_recipe_reference=recipe_node,
            snapshot_id="audit-recipe-snapshot",
            snapshot_version="1",
            ingredient_coverage=IngredientCoverage(
                coverage_id="audit-inventory",
                version="1",
                recipe_id="audit-recipe",
                recipe_version="1",
                catalogue_version=kb.catalogue_version,
                lines=(),
                inventory_complete=True,
                mapping_complete=True,
                subingredients_complete=True,
                gap_reasons=(),
                evidence=(audit_evidence("inventory-proof"),),
            ),
            facts=(
                VersionedFact(
                    fact_id="synthetic_contains_target" if graph_backed else "synthetic_flag",
                    version="1",
                    subject_kind=FactSubjectKind.RECIPE,
                    subject_id="audit-recipe",
                    subject_version="1",
                    catalogue_version=kb.catalogue_version,
                    observation=FactObservation(
                        fact_id="synthetic_contains_target" if graph_backed else "synthetic_flag",
                        value=not graph_backed,
                        complete=True,
                        evidence=ev,
                    ),
                ),
            ),
            evidence=ev,
        )
    )
    recipe_ref = RecipeSnapshotReference(
        recipe_id=candidate.recipe_id,
        recipe_version=candidate.recipe_version,
        snapshot_id=candidate.snapshot_id,
        snapshot_version=candidate.snapshot_version,
        content_digest=candidate.content_digest,
        catalogue_version=candidate.catalogue_version,
    )
    preparation = PreparationBinding(
        preparation_id="audit-cooked",
        version="1",
        recipe_snapshot=recipe_ref,
        basis_reference=audit_evidence("cooked-basis"),
        evidence=ev,
    )
    options = []
    for index, amount in enumerate(amounts):
        part = CombinationComponent(
            component_id="audit-occurrence",
            recipe_snapshot=recipe_ref,
            preparation=preparation,
            quantity=ComponentQuantity(
                amount=index + 1,
                unit=QuantityUnit.G,
                preparation_id=preparation.preparation_id,
                preparation_version=preparation.version,
                basis_reference=preparation.basis_reference,
                portion_reference=audit_evidence(f"portion-{index}"),
                evidence=ev,
            ),
            role_references=(role_node,),
            evidence=ev,
        )
        combo = CombinationFacts.build(
            dict(
                combination_id="audit-meal",
                version="1",
                snapshot_id=f"audit-meal-{index}",
                snapshot_version="1",
                components=(part,),
                composition_complete=True,
                composition_gap_reasons=(),
                portion_state=PortionState.FIXED,
                portion_configuration_id=f"audit-config-{index}",
                portion_configuration_version="1",
                observations=(
                    CombinationObservation(
                        fact_id="synthetic_combination_roles_compatible",
                        version="1",
                        combination_id="audit-meal",
                        combination_version="1",
                        observation=FactObservation(
                            fact_id="synthetic_combination_roles_compatible",
                            value=True,
                            complete=True,
                            evidence=ev,
                        ),
                    ),
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
                evidence=ev,
            )
        )
        ref = MealOptionReference(
            option_id=f"audit-option-{index:02}",
            combination_id=combo.combination_id,
            combination_version=combo.version,
            snapshot_id=combo.snapshot_id,
            snapshot_version=combo.snapshot_version,
            combination_digest=combo.content_digest,
            portion_state=combo.portion_state,
            portion_configuration_id=combo.portion_configuration_id,
            portion_configuration_version=combo.portion_configuration_version,
        )
        external = DailySourceReference(
            source_id="audit-provider", version="1", content_digest="b" * 64
        )
        options.append(
            DailyMealOption(
                reference=ref,
                combination=combo,
                suitability=None
                if index in unknown
                else MealSlotSuitability(
                    option=ref,
                    source=external,
                    slots=() if index in rejected else tuple(MealSlot),
                    complete=True,
                    evidence=ev,
                ),
                measurements=(
                    FixedMealMeasurement(
                        option=ref,
                        source=external,
                        value=amount,
                        complete=amount is not None,
                        unit=MeasurementUnit.MG,
                        measurement_basis=CombinationMeasurementBasis.FIXED_PORTION_TOTAL,
                        components=(part,),
                        basis_reference=audit_evidence(f"fixed-total-{index}"),
                        evidence=ev,
                    ),
                ),
            )
        )
    source = DailySourceSnapshot.build(
        dict(
            source_id="audit-source",
            version="1",
            context=context,
            options=tuple(options),
            evidence=ev,
        )
    )
    if domains is None:
        domains = (tuple(range(len(options))),) * 3
    request = DailyPlanningRequest.build(
        dict(
            request_id="audit-request",
            version="1",
            day_id="audit-day",
            context_id=context.context_id,
            context_version=context.version,
            context_digest=context.content_digest,
            expected_source=DailySourceReference(
                source_id=source.source_id,
                version=source.version,
                content_digest=source.content_digest,
            ),
            source=source,
            domains=tuple(
                DailySlotDomain(slot=slot, options=tuple(options[i].reference for i in indices))
                for slot, indices in zip(MealSlot, domains, strict=True)
            ),
        )
    )
    return dict(
        request=request, candidates=(candidate,), knowledge=kb, context=context, sources=source
    )


def oracle(
    amounts: tuple[int | None, ...],
    domains: tuple[tuple[int, ...], ...],
    target: int,
    unknown: tuple[int, ...],
    rejected: tuple[int, ...],
) -> tuple[str, tuple[str, ...] | None, list[str]]:
    """Standalone three-valued exhaustive oracle; no production reasoning calls."""
    statuses = []
    for choice in itertools.product(*(sorted(d) for d in domains)):
        if any(i in rejected for i in choice):
            continue
        values = [amounts[i] for i in choice]
        if None not in values and sum(v for v in values if v is not None) != target:
            status = "FAIL"
        elif None in values or any(i in unknown for i in choice):
            status = "UNKNOWN"
        else:
            status = "PASS"
        statuses.append(status)
        if status == "PASS":
            return "FEASIBLE", tuple(f"audit-option-{i:02}" for i in choice), statuses
    return ("INSUFFICIENT_DATA" if "UNKNOWN" in statuses else "INFEASIBLE"), None, statuses


@pytest.mark.parametrize(
    ("amounts", "domains", "target", "unknown", "rejected"),
    [
        ((7, 11), ((1, 0),) * 3, 25, (), ()),
        ((7, 11), ((0, 1),) * 3, 26, (), ()),
        ((7, 11), ((0, 1),) * 3, 25, (0,), ()),
        ((None, 11), ((0, 1),) * 3, 25, (), ()),
        ((7, 11), ((), (0, 1), (0,)), 25, (), ()),
        ((7, 11), ((0, 1),) * 3, 25, (), (0,)),
        ((0,), ((0,),) * 3, 0, (), ()),
        (((2**63 - 1) // 3,), ((0,),) * 3, 2**63 - 2, (), ()),
        ((3, 6, 9), ((2, 1), (0, 2), (1, 0)), 18, (), ()),
    ],
)
def test_separate_cartesian_oracle(
    amounts: tuple[int | None, ...],
    domains: tuple[tuple[int, ...], ...],
    target: int,
    unknown: tuple[int, ...],
    rejected: tuple[int, ...],
) -> None:
    expected, witness, statuses = oracle(amounts, domains, target, unknown, rejected)
    result = solve_daily_plan(
        **audit_case(amounts, domains=domains, target=target, unknown=unknown, rejected=rejected),
        clock=lambda: 0.0,
    )
    assert result.outcome.value == expected
    assert [e.status.value for e in result.evaluations] == statuses
    assert result.statistics.exhaustive == (witness is None)
    actual = (
        tuple(item.option.option_id for item in result.assignment.slots)
        if result.assignment
        else None
    )
    assert actual == witness
    assert result.statistics.phase3_batch_calls == 1 + len(amounts)


@pytest.mark.parametrize(
    ("operator", "truth"),
    [
        (PredicateOperator.LT, (False, False, True)),
        (PredicateOperator.LE, (False, True, True)),
        (PredicateOperator.GT, (True, False, False)),
        (PredicateOperator.GE, (True, True, False)),
        (PredicateOperator.EQ, (False, True, False)),
        (PredicateOperator.NE, (True, False, True)),
    ],
)
def test_numeric_truth_tables(operator: PredicateOperator, truth: tuple[bool, ...]) -> None:
    # A repeated fixed meal of 4 mg yields exactly 12 mg. Thresholds straddle it.
    for threshold, satisfied in zip((11, 12, 13), truth, strict=True):
        result = solve_daily_plan(**audit_case((4,), checks=(numeric_check(operator, threshold),)))
        assert result.outcome is (DailyOutcome.FEASIBLE if satisfied else DailyOutcome.INFEASIBLE)
        assert result.evaluations[0].facts[1].observation.value == 12


@pytest.mark.parametrize(
    ("operator", "value", "expected"),
    [
        (PredicateOperator.EQ, True, "FEASIBLE"),
        (PredicateOperator.EQ, False, "INFEASIBLE"),
        (PredicateOperator.NE, True, "INFEASIBLE"),
        (PredicateOperator.NE, False, "FEASIBLE"),
    ],
)
def test_boolean_truth_table(operator: PredicateOperator, value: bool, expected: str) -> None:
    check = audit_rule(
        "day-complete", RuleScope.DAY, "synthetic_day_complete", operator=operator, value=value
    )
    assert solve_daily_plan(**audit_case((4,), checks=(check,))).outcome.value == expected


def test_full_cross_phase_provenance_and_strict_roundtrip() -> None:
    result = solve_daily_plan(**audit_case(), clock=lambda: 0.0)
    assert result.assignment is not None
    assert result.recipes.eligible_ids == ("audit-recipe",)
    assert all(option.combination.status is RuleStatus.PASS for option in result.options)
    assert [r.rule_id for r in result.manifest.required_checks] == ["day-total"]
    assert [r.rule_id for r in result.manifest.deferred_checks] == ["week-deferred"]
    evaluation = result.evaluations[-1]
    assert [c.measurement.value for c in evaluation.facts[1].contributions] == [7, 7, 11]
    explanation = evaluation.explanations[0]
    assert explanation.manifest_digest == result.manifest.content_digest
    assert explanation.trial_digest == evaluation.trial.content_digest
    ids = {e.evidence_id for e in evaluation.facts[1].observation.evidence}
    assert {
        "recipe-required",
        "meal-required",
        "fixed-total-0",
        "fixed-total-1",
        "synthetic-day-derivation",
    } <= ids
    assert explanation.status is RuleStatus.PASS and explanation.evidence
    assert validate_contract_json(DailySolveResult, result.model_dump_json()) == result


@pytest.mark.parametrize("enabled", [False, None])
def test_applicability_and_zero_check_coverage(enabled: bool | None) -> None:
    result = solve_daily_plan(**audit_case((None,), enabled=enabled))
    evaluation = result.evaluations[0].trace.evaluations[0]
    assert evaluation.status is RuleStatus.UNKNOWN
    assert evaluation.applicability is (
        ApplicabilityStatus.NOT_APPLICABLE if enabled is False else ApplicabilityStatus.UNKNOWN
    )
    assert result.outcome is (
        DailyOutcome.FEASIBLE if enabled is False else DailyOutcome.INSUFFICIENT_DATA
    )
    assert solve_daily_plan(**audit_case((4,), checks=())).outcome is DailyOutcome.INSUFFICIENT_DATA


def test_all_mandatory_checks_run_and_fail_dominates_unknown() -> None:
    checks = (
        numeric_check(PredicateOperator.EQ, 0),
        audit_rule("day-complete", RuleScope.DAY, "synthetic_day_complete"),
    )
    result = solve_daily_plan(**audit_case((4,), checks=checks, unknown=(0,)))
    assert result.outcome is DailyOutcome.INFEASIBLE
    assert [e.status for e in result.evaluations[0].trace.evaluations] == [
        RuleStatus.UNKNOWN,
        RuleStatus.FAIL,
    ]
    assert len(result.evaluations[0].explanations) == 2


@pytest.mark.parametrize(
    "limits",
    [
        DailySearchLimits(max_nodes=2),
        DailySearchLimits(max_completed_assignments=0),
        DailySearchLimits(max_option_evaluations=0),
        DailySearchLimits(deadline=0),
    ],
)
def test_budget_exhaustion_has_no_infeasibility_claim(limits: DailySearchLimits) -> None:
    result = solve_daily_plan(**audit_case((4,), target=0), limits=limits, clock=lambda: 0.0)
    assert result.outcome is DailyOutcome.TIMEOUT
    assert result.assignment is None
    assert not result.statistics.exhaustive and not result.statistics.search_completed


def test_rehashed_reduced_manifest_and_unapproved_policy_rejected() -> None:
    case = audit_case((4,))
    manifest = build_day_check_manifest(**{k: v for k, v in case.items() if k != "candidates"})
    payload: dict[str, Any] = manifest.model_dump(exclude={"content_digest"})
    payload["required_checks"] = ()
    with pytest.raises(ValidationError):
        ExpectedDayCheckManifest.build(payload)
    pending = numeric_check(PredicateOperator.EQ, 12).model_copy(
        update={
            "approval_status": ApprovalStatus.PENDING,
            "approval_reference": None,
            "approved_by": None,
        }
    )
    with pytest.raises(ValidationError):
        solve_daily_plan(**audit_case((4,), checks=(pending,)))


def test_wrong_independent_release_and_stale_preparation_rejected() -> None:
    case = audit_case((4,))
    foreign = audit_case((4,), target=1)
    with pytest.raises(ValidationError):
        solve_daily_plan(**(case | {"knowledge": foreign["knowledge"]}))
    with pytest.raises(ValidationError):
        solve_daily_plan(**(case | {"sources": foreign["sources"]}))
    option = case["sources"].options[0]
    measurement = option.measurements[0]
    stale = measurement.components[0].model_copy(
        update={
            "preparation": measurement.components[0].preparation.model_copy(
                update={"version": "stale"}
            )
        }
    )
    with pytest.raises(ValidationError):
        DailyMealOption.model_validate(
            option.model_copy(
                update={"measurements": (measurement.model_copy(update={"components": (stale,)}),)}
            )
        )


def test_output_tampering_is_rejected() -> None:
    result = solve_daily_plan(**audit_case((4,), target=12), clock=lambda: 0.0)
    payload = result.model_dump(mode="json", by_alias=True)
    for path, value in [
        (("outcome",), "INFEASIBLE"),
        (("evaluations", 0, "facts", 1, "observation", "value"), 13),
        (("evaluations", 0, "explanations", 0, "trialDigest"), "0" * 64),
        (("statistics", "exhaustive"), True),
        (("manifest", "deferredChecks"), []),
    ]:
        forged = deepcopy(payload)
        parent = forged
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = value
        with pytest.raises(ValidationError):
            validate_contract_json(DailySolveResult, json.dumps(forged))


def test_supported_raw_json_ingress_rejects_ambiguous_and_unbounded_input() -> None:
    for raw in (
        '{"maxNodes":1,"maxNodes":2}',
        '{"maxNodes":1,"max_nodes":2}',
        '{"deadline":1e999}',
        '{"deadline":NaN}',
        "[" * 65 + "0" + "]" * 65,
        " " * 1_048_577,
    ):
        with pytest.raises(ValidationError):
            validate_contract_json(DailySearchLimits, raw)


def test_hostile_unchecked_inputs_and_counterfeit_enum_rejected() -> None:
    class HostileTuple(tuple):
        def __iter__(self):
            raise AssertionError("hostile tuple must never be iterated")

    case = audit_case((4,))
    hostile: dict[str, Any] = case | {"candidates": HostileTuple(case["candidates"])}
    with pytest.raises(ValidationError):
        solve_daily_plan(**hostile)
    unchecked: dict[str, Any] = case | {"limits": DailySearchLimits.model_construct(max_nodes=-1)}
    with pytest.raises(ValidationError):
        solve_daily_plan(**unchecked)
    forged = str.__new__(DailyOutcome, "FEASIBLE")
    object.__setattr__(forged, "_name_", "FEASIBLE")
    object.__setattr__(forged, "_value_", "FEASIBLE")
    result = solve_daily_plan(**case)
    with pytest.raises(ValidationError):
        DailySolveResult.model_validate(result.model_copy(update={"outcome": forged}))


def test_domain_permutations_preserve_first_canonical_witness() -> None:
    results = []
    for order in ((1, 0), (0, 1)):
        results.append(solve_daily_plan(**audit_case(domains=(order,) * 3), clock=lambda: 0.0))
    assert results[0].assignment == results[1].assignment
    assert results[0].evaluations == results[1].evaluations
    assert results[0].statistics == results[1].statistics


def test_timeout_proof_cannot_claim_search_before_preprocessing() -> None:
    result = solve_daily_plan(
        **audit_case((4,)),
        limits=DailySearchLimits(max_option_evaluations=0, max_nodes=0),
        clock=lambda: 0.0,
    )
    stats = result.statistics.model_copy(update={"budget_exhaustion": "NODE_BUDGET"})
    with pytest.raises(ValidationError):
        DailySolveResult.model_validate(result.model_copy(update={"statistics": stats}))


def test_combination_applicability_cannot_be_relabelled_in_daily_proof() -> None:
    result = solve_daily_plan(**audit_case((4,), target=12), clock=lambda: 0.0)
    payload = result.model_dump(mode="json", by_alias=True)
    evaluation = payload["options"][0]["combination"]["trace"]["evaluations"][0]
    evaluation.update(applicability="NOT_APPLICABLE", status="UNKNOWN")
    with pytest.raises(ValidationError):
        validate_contract_json(DailySolveResult, json.dumps(payload))


def test_timeout_partial_counters_must_describe_real_chronological_prefix() -> None:
    result = solve_daily_plan(
        **audit_case((4,), target=0), limits=DailySearchLimits(max_nodes=2), clock=lambda: 0.0
    )
    assert result.statistics.nodes == 2 and result.statistics.backtracks == 0
    stats = result.statistics.model_copy(update={"backtracks": 1})
    with pytest.raises(ValidationError):
        DailySolveResult.model_validate(result.model_copy(update={"statistics": stats}))


def test_graph_witness_and_inventory_provenance_survive_all_stages() -> None:
    case = audit_case((4,), target=12, graph_backed=True)
    result = solve_daily_plan(**case)
    assert result.outcome is DailyOutcome.FEASIBLE
    resolved = next(
        f
        for f in result.recipes.decisions[0].resolution.facts
        if f.fact.fact_id == "synthetic_contains_target"
    )
    assert resolved.fact.observation.value is False
    assert resolved.relations[0].relation is not None
    assert resolved.relations[0].relation.relation_id == "audit-exact-absence"
    assert {"absence-proof", "inventory-proof"} <= {
        e.evidence_id for e in result.evaluations[0].facts[1].observation.evidence
    }
    with pytest.raises(ValidationError):
        type(resolved).model_validate(resolved.model_copy(update={"relations": ()}))
    # A caller's False declaration and complete inventory cannot replace a missing edge.
    missing = solve_daily_plan(
        **audit_case((4,), target=12, graph_backed=True, graph_witness=False)
    )
    assert missing.outcome is DailyOutcome.INSUFFICIENT_DATA
    transplanted = (
        case["candidates"][0]
        .facts[0]
        .model_copy(
            update={"subject_kind": FactSubjectKind.INGREDIENT, "subject_id": "foreign-ingredient"}
        )
    )
    wrong: dict[str, Any] = case | {
        "candidates": (case["candidates"][0].model_copy(update={"facts": (transplanted,)}),)
    }
    with pytest.raises(ValidationError):
        solve_daily_plan(**wrong)


def test_literal_chronological_budget_edges() -> None:
    case = audit_case((4, 4), target=0)
    # Hand-enumerated two-by-two-by-two DFS: (budget, completed leaves, backtracks).
    for budget, leaves, backtracks in ((0, 0, 0), (4, 2, 3), (7, 4, 7), (11, 6, 10), (14, 8, 14)):
        result = solve_daily_plan(
            **case, limits=DailySearchLimits(max_nodes=budget), clock=lambda: 0.0
        )
        assert result.statistics.nodes == budget
        assert result.statistics.completed_assignments == leaves
        assert result.statistics.backtracks == backtracks
        assert result.outcome is (DailyOutcome.INFEASIBLE if budget == 14 else DailyOutcome.TIMEOUT)
    for budget, nodes, backtracks in ((0, 3, 0), (2, 6, 3), (4, 10, 7), (8, 14, 14)):
        result = solve_daily_plan(
            **case, limits=DailySearchLimits(max_completed_assignments=budget), clock=lambda: 0.0
        )
        assert result.statistics.nodes == nodes and result.statistics.backtracks == backtracks
        assert result.statistics.completed_assignments == budget
        assert result.outcome is (DailyOutcome.INFEASIBLE if budget == 8 else DailyOutcome.TIMEOUT)


def test_catalogue_omission_and_hostile_mapping_and_list_rejected() -> None:
    case = audit_case((4,))
    kb = case["knowledge"]
    body: dict[str, object] = kb.model_dump(exclude={"content_digest"})
    body["check_catalogue"] = tuple(
        c
        for c in kb.check_catalogue
        if not (c.workflow is KnowledgeWorkflow.WEEKLY_PLAN and c.scope is RuleScope.DAY)
    )
    with pytest.raises(ValidationError):
        build_knowledge_snapshot(body)

    class HostileDict(dict):
        def items(self):
            raise AssertionError("hostile mapping must never be inspected")

    class HostileList(list):
        def __iter__(self):
            raise AssertionError("hostile list must never be iterated")

    with pytest.raises(ValidationError):
        DailySearchLimits.model_validate(HostileDict(max_nodes=1))
    wrong: dict[str, Any] = case | {
        "request": case["request"].model_copy(
            update={"domains": HostileList(case["request"].domains)}
        )
    }
    with pytest.raises(ValidationError):
        solve_daily_plan(**wrong)
