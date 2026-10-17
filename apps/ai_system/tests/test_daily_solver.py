"""Independent fictional solver inputs, literal truth tables and Cartesian oracle."""

import itertools
import json
from enum import StrEnum
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
    FixedMealMeasurement,
    MealOptionReference,
    MealSlot,
    MealSlotSuitability,
)
from savora_ai.schemas.daily_solver import DailySearchLimits, DailySolveResult
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
from savora_ai.schemas.reasoning import FactObservation, RuleStatus


def evidence(id_: str = "solver-fiction", **changes: Any) -> EvidenceReference:
    return EvidenceReference.model_validate(
        dict(
            evidence_id=id_,
            version="1",
            source="Independent fictional daily solver test",
            locator="urn:solver:" + id_,
            environment=RuleEnvironment.SYNTHETIC,
        )
        | changes
    )


def rule(id_: str, scope: RuleScope, attribute: str, **changes: Any) -> RuleDefinition:
    return RuleDefinition.model_validate(
        dict(
            rule_id=id_,
            version="1",
            scope=scope,
            severity=RuleSeverity.ABSOLUTE,
            domain=RuleDomain.CULINARY,
            attribute=attribute,
            operator=PredicateOperator.EQ,
            value=True,
            required_facts=(attribute,),
            applicability_reference=RuleReference(rule_id="synthetic-context-enabled", version="1"),
            evidence=(evidence("rule-" + id_),),
            rationale="Fictional test requirement",
            lifecycle=RuleLifecycle.ACTIVE,
            environment=RuleEnvironment.SYNTHETIC,
            approval_status=ApprovalStatus.APPROVED,
            approved_by="fictional-reviewer",
            approval_reference=evidence("approval-" + id_),
        )
        | changes
    )


def numeric_rule(
    operator: PredicateOperator = PredicateOperator.EQ, value: int = 60
) -> RuleDefinition:
    return rule(
        "day-number",
        RuleScope.DAY,
        "synthetic_day_quantity_total",
        operator=operator,
        value=value,
        unit=MeasurementUnit.MG,
    )


def fact(name: str, owner: FactSubjectKind, id_: str, value: bool | None) -> VersionedFact:
    return VersionedFact(
        fact_id=name,
        version="1",
        subject_kind=owner,
        subject_id=id_,
        subject_version="1",
        catalogue_version="solver-catalogue" if owner is FactSubjectKind.RECIPE else None,
        context_id="solver-context" if owner is FactSubjectKind.CONTEXT else None,
        context_version="1" if owner is FactSubjectKind.CONTEXT else None,
        observation=FactObservation(
            fact_id=name,
            value=value,
            complete=value is not None,
            evidence=(evidence("fact-" + id_),),
        ),
    )


def scenario(
    values: tuple[int | None, ...] = (10, 20, 30),
    *,
    domains: tuple[tuple[int, ...], ...] = ((0,), (1,), (2,)),
    day_rules: tuple[RuleDefinition, ...] | None = None,
    recipe_values: tuple[bool | None, ...] | None = None,
    combination_values: tuple[bool | None, ...] | None = None,
    enabled: bool | None = True,
    missing_suitability: tuple[int, ...] = (),
    unsuitable: tuple[int, ...] = (),
    unassigned: tuple[int, ...] = (),
) -> dict[str, Any]:
    rules = (
        rule("recipe", RuleScope.RECIPE, "synthetic_flag"),
        rule("combination", RuleScope.COMBINATION, "synthetic_combination_roles_compatible"),
        *(day_rules if day_rules is not None else (numeric_rule(),)),
        rule("week", RuleScope.WEEK, "synthetic_flag"),
    )
    nodes = tuple(
        FoodEntity(
            entity_id=f"node-{i}",
            version="1",
            kind=FoodEntityKind.RECIPE_REFERENCE,
            canonical_name="Same fictional label",
            catalogue_reference=f"recipe-{i}",
            evidence=(evidence(),),
        )
        for i in range(len(values))
    )
    role = FoodEntity(
        entity_id="role",
        version="1",
        kind=FoodEntityKind.CULINARY_ROLE_REFERENCE,
        canonical_name="Same fictional label",
        catalogue_reference="role-id",
        evidence=(evidence(),),
    )
    graph = FoodGraphSnapshot(
        graph_id="solver-graph",
        version="1",
        catalogue_version="solver-catalogue",
        environment=RuleEnvironment.SYNTHETIC,
        entities=(*nodes, role),
        relations=(),
        evidence=(evidence(),),
    )
    cells = tuple(
        CheckCatalogueEntry(
            entry_id=f"{workflow.value}-{scope.value}",
            version="1",
            kb_id="solver-kb",
            kb_version="1",
            check_catalogue_version="solver-checks",
            workflow=workflow,
            scope=scope,
            rule_references=tuple(
                RuleReference(rule_id=r.rule_id, version=r.version)
                for r in rules
                if r.scope is scope
            ),
            evidence=(evidence(),),
        )
        for workflow in KnowledgeWorkflow
        for scope in RuleScope
        if workflow is not KnowledgeWorkflow.CRAVING_DISCOVERY
        or scope in (RuleScope.PROFILE, RuleScope.RECIPE)
    )
    kb_body: dict[str, object] = dict(
        kb_id="solver-kb",
        version="1",
        environment=RuleEnvironment.SYNTHETIC,
        graph_id=graph.graph_id,
        graph_version=graph.version,
        catalogue_version=graph.catalogue_version,
        taxonomy_version=None,
        check_catalogue_version="solver-checks",
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
                evidence=(evidence(),),
            ),
        ),
        check_catalogue=cells,
        rule_catalogue_coverage=tuple(
            RuleCatalogueCoverage(
                coverage_id="coverage-" + cell.entry_id,
                version="1",
                kb_id="solver-kb",
                kb_version="1",
                check_catalogue_version="solver-checks",
                workflow=cell.workflow,
                scope=cell.scope,
                complete=True,
                reason="Independent fictional complete catalogue",
                evidence=(evidence(),),
            )
            for cell in cells
        ),
        evidence=(evidence(),),
    )

    # Independent canonical encoder, not a production digest factory.
    def digest(data: dict[str, Any]) -> str:
        import hashlib

        def canonical(value: Any) -> Any:
            if isinstance(value, dict):
                return {
                    key.split("_")[0]
                    + "".join(
                        part[:1].upper() + part[1:] for part in key.split("_")[1:]
                    ): canonical(item)
                    for key, item in value.items()
                }
            if isinstance(value, list):
                return sorted(
                    (canonical(item) for item in value),
                    key=lambda item: json.dumps(
                        item,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                    ),
                )
            return value

        from pydantic import TypeAdapter

        plain = TypeAdapter(dict[str, Any]).dump_python(data, mode="json", by_alias=True)
        return hashlib.sha256(
            json.dumps(
                canonical(plain), sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode()
        ).hexdigest()

    # Include default tokens in the independent KB hash.
    kb_body.update(
        schema_version="knowledge-base.v1",
        semantic_policy_version="knowledge-base-integrity.v1",
        workflow_policy_version="synthetic-workflow-scopes.v1",
    )
    kb = KnowledgeBaseSnapshot.model_validate(kb_body | {"content_digest": digest(kb_body)})
    context = RuleContext.build(
        dict(
            context_id="solver-context",
            version="1",
            profile_id="solver-profile",
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
                fact(
                    "synthetic_context_enabled", FactSubjectKind.CONTEXT, "solver-context", enabled
                ),
            ),
            evidence=(evidence(),),
        )
    )
    candidates = []
    options = []
    for i, (node, value) in enumerate(zip(nodes, values, strict=True)):
        candidate = CandidateRecipeFacts.build(
            dict(
                recipe_id=f"recipe-{i}",
                recipe_version="1",
                catalogue_version=kb.catalogue_version,
                graph_id=kb.graph_id,
                graph_version=kb.graph_version,
                graph_recipe_entity_id=node.entity_id,
                graph_recipe_reference=node,
                snapshot_id=f"recipe-snapshot-{i}",
                snapshot_version="1",
                ingredient_coverage=IngredientCoverage(
                    coverage_id=f"inventory-{i}",
                    version="1",
                    recipe_id=f"recipe-{i}",
                    recipe_version="1",
                    catalogue_version=kb.catalogue_version,
                    lines=(),
                    inventory_complete=True,
                    mapping_complete=True,
                    subingredients_complete=True,
                    gap_reasons=(),
                    evidence=(evidence(),),
                ),
                facts=(
                    fact(
                        "synthetic_flag",
                        FactSubjectKind.RECIPE,
                        f"recipe-{i}",
                        recipe_values[i] if recipe_values is not None else True,
                    ),
                ),
                evidence=(evidence(),),
            )
        )
        candidates.append(candidate)
        ref = RecipeSnapshotReference(
            recipe_id=candidate.recipe_id,
            recipe_version="1",
            snapshot_id=candidate.snapshot_id,
            snapshot_version="1",
            content_digest=candidate.content_digest,
            catalogue_version=kb.catalogue_version,
        )
        prep = PreparationBinding(
            preparation_id=f"cooked-{i}",
            version="1",
            recipe_snapshot=ref,
            basis_reference=evidence(f"basis-{i}"),
            evidence=(evidence(),),
        )
        part = CombinationComponent(
            component_id="occurrence",
            recipe_snapshot=ref,
            preparation=prep,
            quantity=ComponentQuantity(
                amount=10,
                unit=QuantityUnit.G,
                preparation_id=prep.preparation_id,
                preparation_version="1",
                basis_reference=prep.basis_reference,
                portion_reference=evidence(f"portion-{i}"),
                evidence=(evidence(),),
            )
            if i not in unassigned
            else None,
            role_references=(role,),
            evidence=(evidence(),),
        )
        compatible = combination_values[i] if combination_values is not None else True
        combo = CombinationFacts.build(
            dict(
                combination_id=f"meal-{i}",
                version="1",
                snapshot_id=f"meal-snapshot-{i}",
                snapshot_version="1",
                components=(part,),
                composition_complete=True,
                composition_gap_reasons=(),
                portion_state=PortionState.UNASSIGNED if i in unassigned else PortionState.FIXED,
                portion_configuration_id=None if i in unassigned else f"config-{i}",
                portion_configuration_version=None if i in unassigned else "1",
                observations=(
                    CombinationObservation(
                        fact_id="synthetic_combination_roles_compatible",
                        version="1",
                        combination_id=f"meal-{i}",
                        combination_version="1",
                        observation=FactObservation(
                            fact_id="synthetic_combination_roles_compatible",
                            value=compatible,
                            complete=compatible is not None,
                            evidence=(evidence(),),
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
                evidence=(evidence(),),
            )
        )
        option = MealOptionReference(
            option_id=f"option-{i:02}",
            combination_id=combo.combination_id,
            combination_version="1",
            snapshot_id=combo.snapshot_id,
            snapshot_version="1",
            combination_digest=combo.content_digest,
            portion_state=combo.portion_state,
            portion_configuration_id=combo.portion_configuration_id,
            portion_configuration_version=combo.portion_configuration_version,
        )
        external = DailySourceReference(
            source_id=f"external-{i}", version="1", content_digest="a" * 64
        )
        suitability = (
            None
            if i in missing_suitability
            else MealSlotSuitability(
                option=option,
                source=external,
                slots=() if i in unsuitable else tuple(MealSlot),
                complete=True,
                evidence=(evidence(),),
            )
        )
        measurements = (
            ()
            if i in unassigned
            else (
                FixedMealMeasurement(
                    option=option,
                    source=external,
                    value=value,
                    complete=value is not None,
                    unit=MeasurementUnit.MG,
                    measurement_basis=CombinationMeasurementBasis.FIXED_PORTION_TOTAL,
                    components=combo.components,
                    basis_reference=evidence(f"meal-basis-{i}"),
                    evidence=(evidence(),),
                ),
            )
        )
        options.append(
            DailyMealOption(
                reference=option,
                combination=combo,
                suitability=suitability,
                measurements=measurements,
            )
        )
    sources = DailySourceSnapshot.build(
        dict(
            source_id="solver-source",
            version="1",
            context=context,
            options=tuple(options),
            evidence=(evidence(),),
        )
    )
    request = DailyPlanningRequest.build(
        dict(
            request_id="solver-request",
            version="1",
            day_id="fictional-day",
            context_id=context.context_id,
            context_version=context.version,
            context_digest=context.content_digest,
            expected_source=DailySourceReference(
                source_id=sources.source_id,
                version=sources.version,
                content_digest=sources.content_digest,
            ),
            source=sources,
            domains=tuple(
                DailySlotDomain(slot=slot, options=tuple(options[i].reference for i in indices))
                for slot, indices in zip(MealSlot, domains, strict=True)
            ),
        )
    )
    return dict(
        request=request,
        candidates=tuple(candidates),
        knowledge=kb,
        context=context,
        sources=sources,
    )


def solve(data: dict[str, Any], **changes: Any) -> DailySolveResult:
    return solve_daily_plan(**(data | changes))


def test_exact_three_slot_feasible_and_literal_integer_total() -> None:
    result = solve(scenario())
    assert result.outcome is DailyOutcome.FEASIBLE and result.assignment is not None
    assert tuple(item.slot for item in result.assignment.slots) == tuple(MealSlot)
    assert result.evaluations[0].facts[1].observation.value == 60
    assert type(result.evaluations[0].facts[1].observation.value) is int
    assert tuple(
        item.measurement.value for item in result.evaluations[0].facts[1].contributions
    ) == (10, 20, 30)
    assert tuple(rule.rule_id for rule in result.manifest.deferred_checks) == ("week",)
    assert result.statistics.option_evaluations == 3
    assert result.statistics.phase3_batch_calls == 4
    assert result.statistics.nodes == 3 and result.statistics.completed_assignments == 1
    assert result.statistics.backtracks == 0 and not result.statistics.exhaustive


@pytest.mark.parametrize(
    "operator,threshold,expected",
    [
        (PredicateOperator.LT, 59, False),
        (PredicateOperator.LT, 60, False),
        (PredicateOperator.LT, 61, True),
        (PredicateOperator.LE, 59, False),
        (PredicateOperator.LE, 60, True),
        (PredicateOperator.LE, 61, True),
        (PredicateOperator.GT, 59, True),
        (PredicateOperator.GT, 60, False),
        (PredicateOperator.GT, 61, False),
        (PredicateOperator.GE, 59, True),
        (PredicateOperator.GE, 60, True),
        (PredicateOperator.GE, 61, False),
        (PredicateOperator.EQ, 59, False),
        (PredicateOperator.EQ, 60, True),
        (PredicateOperator.EQ, 61, False),
        (PredicateOperator.NE, 59, True),
        (PredicateOperator.NE, 60, False),
        (PredicateOperator.NE, 61, True),
    ],
)
def test_literal_numeric_truth_table(
    operator: PredicateOperator, threshold: int, expected: bool
) -> None:
    result = solve(scenario(day_rules=(numeric_rule(operator, threshold),)))
    assert result.outcome is (DailyOutcome.FEASIBLE if expected else DailyOutcome.INFEASIBLE)


@pytest.mark.parametrize(
    "operator,value,expected",
    [
        (PredicateOperator.EQ, True, DailyOutcome.FEASIBLE),
        (PredicateOperator.EQ, False, DailyOutcome.INFEASIBLE),
        (PredicateOperator.NE, True, DailyOutcome.INFEASIBLE),
        (PredicateOperator.NE, False, DailyOutcome.FEASIBLE),
    ],
)
def test_boolean_day_predicates(
    operator: PredicateOperator, value: bool, expected: DailyOutcome
) -> None:
    result = solve(
        scenario(
            day_rules=(
                rule(
                    "day", RuleScope.DAY, "synthetic_day_complete", operator=operator, value=value
                ),
            )
        )
    )
    assert result.outcome is expected


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"recipe_values": (False, True, True)}, DailyOutcome.INFEASIBLE),
        ({"recipe_values": (None, True, True)}, DailyOutcome.INSUFFICIENT_DATA),
        ({"combination_values": (False, None, True)}, DailyOutcome.INFEASIBLE),
        ({"combination_values": (None, None, None)}, DailyOutcome.INSUFFICIENT_DATA),
        ({"values": (10, None, 30)}, DailyOutcome.INSUFFICIENT_DATA),
        ({"missing_suitability": (1,)}, DailyOutcome.INSUFFICIENT_DATA),
        ({"unsuitable": (1,)}, DailyOutcome.INFEASIBLE),
        ({"unassigned": (1,)}, DailyOutcome.INSUFFICIENT_DATA),
        ({"enabled": None}, DailyOutcome.INSUFFICIENT_DATA),
        ({"enabled": False}, DailyOutcome.FEASIBLE),
        ({"domains": ((), (1,), (2,))}, DailyOutcome.INFEASIBLE),
        ({"day_rules": ()}, DailyOutcome.INSUFFICIENT_DATA),
    ],
)
def test_known_fail_unknown_empty_and_not_applicable(
    changes: dict[str, Any], expected: DailyOutcome
) -> None:
    result = solve(scenario(**changes))
    assert result.outcome is expected
    assert result.statistics.exhaustive == (expected is not DailyOutcome.FEASIBLE)


def test_known_numeric_failure_dominates_unknown_eligibility() -> None:
    result = solve(scenario(recipe_values=(None, True, True), day_rules=(numeric_rule(value=61),)))
    assert result.outcome is DailyOutcome.INFEASIBLE
    assert result.evaluations[0].facts[0].observation.value is None
    assert result.evaluations[0].trace.evaluations[0].status is RuleStatus.FAIL


def test_every_day_check_runs_after_failure_and_unknown() -> None:
    rules = (
        numeric_rule(value=61),
        rule(
            "day-other",
            RuleScope.DAY,
            "synthetic_day_complete",
            required_facts=("synthetic_day_complete", "synthetic_profile_flag"),
        ),
    )
    result = solve(scenario(day_rules=rules))
    assert result.outcome is DailyOutcome.INFEASIBLE
    assert tuple(item.status for item in result.evaluations[0].trace.evaluations) == (
        RuleStatus.FAIL,
        RuleStatus.UNKNOWN,
    )
    assert len(result.evaluations[0].explanations) == 2


@pytest.mark.parametrize(
    "limits,reason",
    [
        (DailySearchLimits(max_nodes=0), "NODE_BUDGET"),
        (DailySearchLimits(max_nodes=2), "NODE_BUDGET"),
        (DailySearchLimits(max_completed_assignments=0), "ASSIGNMENT_BUDGET"),
        (DailySearchLimits(max_option_evaluations=0), "PREPROCESSING_BUDGET"),
    ],
)
def test_budgets_are_timeouts(limits: DailySearchLimits, reason: str) -> None:
    result = solve(scenario(), limits=limits)
    assert result.outcome is DailyOutcome.TIMEOUT and result.assignment is None
    assert result.statistics.budget_exhaustion == reason and not result.statistics.search_completed


def test_repeated_occurrences_counted_once_per_meal_slot() -> None:
    result = solve(scenario(values=(20,), domains=((0,), (0,), (0,))))
    assert result.outcome is DailyOutcome.FEASIBLE
    assert result.statistics.option_evaluations == 1
    assert result.evaluations[0].facts[1].observation.value == 60
    assert len(result.evaluations[0].facts[1].contributions) == 3


def test_authoritative_manifest_no_caller_reduction_and_exact_week() -> None:
    data = scenario()
    manifest = build_day_check_manifest(
        data["request"],
        knowledge=data["knowledge"],
        context=data["context"],
        sources=data["sources"],
    )
    assert tuple(r.rule_id for r in manifest.required_checks) == ("day-number",)
    assert tuple(r.rule_id for r in manifest.deferred_checks) == ("week",)
    for changes in (
        {"required_checks": ()},
        {"deferred_checks": ()},
        {"day_policy_version": "unknown"},
    ):
        with pytest.raises(ValidationError):
            payload: dict[str, object] = manifest.model_dump(exclude={"content_digest"})
            payload.update(changes)
            type(manifest).build(payload)


@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("target", [30, 50, 60, 91])
def test_independent_cartesian_oracle(n: int, target: int) -> None:
    values = (10, 20, 30)[:n]
    choices = tuple(range(n))
    data = scenario(
        values=values, domains=(choices, choices, choices), day_rules=(numeric_rule(value=target),)
    )
    expected = next(
        (
            assignment
            for assignment in itertools.product(choices, repeat=3)
            if sum(values[index] for index in assignment) == target
        ),
        None,
    )
    result = solve(data)
    assert result.outcome is (
        DailyOutcome.FEASIBLE if expected is not None else DailyOutcome.INFEASIBLE
    )
    if expected is not None:
        assert result.assignment is not None
        assert tuple(item.option.option_id for item in result.assignment.slots) == tuple(
            f"option-{i:02}" for i in expected
        )
    else:
        assert result.statistics.completed_assignments == n**3
        assert result.statistics.exhaustive


@pytest.mark.parametrize(
    "values,target,expected",
    [
        ((None, 20), 60, DailyOutcome.FEASIBLE),
        ((None, 20), 61, DailyOutcome.INSUFFICIENT_DATA),
        ((10, 20), 61, DailyOutcome.INFEASIBLE),
    ],
)
def test_optimistic_unknown_branches_compared_with_independent_oracle(
    values: tuple[int | None, ...],
    target: int,
    expected: DailyOutcome,
) -> None:
    unknown = False
    answer = None
    for assignment in itertools.product(range(2), repeat=3):
        amounts = tuple(values[index] for index in assignment)
        if None in amounts:
            unknown = True
        elif sum(value for value in amounts if value is not None) == target:
            answer = assignment
            break
    literal = (
        DailyOutcome.FEASIBLE
        if answer is not None
        else (DailyOutcome.INSUFFICIENT_DATA if unknown else DailyOutcome.INFEASIBLE)
    )
    assert literal is expected
    result = solve(
        scenario(values=values, domains=((0, 1),) * 3, day_rules=(numeric_rule(value=target),))
    )
    assert result.outcome is expected


def test_domain_source_candidate_permutations_preserve_search_and_semantics() -> None:
    data = scenario(values=(10, 20), domains=((0, 1),) * 3, day_rules=(numeric_rule(value=50),))
    first = solve(data, clock=lambda: 0.0)
    request = data["request"]
    changed_request = DailyPlanningRequest.build(
        request.model_dump(exclude={"content_digest"})
        | {
            "domains": tuple(
                domain.model_copy(update={"options": tuple(reversed(domain.options))})
                for domain in reversed(request.domains)
            ),
        }
    )
    sources = data["sources"]
    changed_source = DailySourceSnapshot.build(
        sources.model_dump(exclude={"content_digest"})
        | {
            "options": tuple(reversed(sources.options)),
        }
    )
    second = solve(
        data,
        request=changed_request,
        sources=changed_source,
        candidates=tuple(reversed(data["candidates"])),
        clock=lambda: 0.0,
    )
    assert first.assignment == second.assignment
    assert first.evaluations == second.evaluations and first.statistics == second.statistics


@pytest.mark.parametrize(
    "cap,expected",
    [(0, DailyOutcome.TIMEOUT), (7, DailyOutcome.TIMEOUT), (8, DailyOutcome.INFEASIBLE)],
)
def test_completed_budget_exact_boundary(cap: int, expected: DailyOutcome) -> None:
    result = solve(
        scenario(values=(10, 20), domains=((0, 1),) * 3, day_rules=(numeric_rule(value=100),)),
        limits=DailySearchLimits(max_completed_assignments=cap),
    )
    assert result.outcome is expected
    assert result.statistics.completed_assignments == cap


def test_deadline_during_preparation_and_search_is_cooperative_and_testable() -> None:
    data = scenario()
    early = solve(data, limits=DailySearchLimits(deadline=0.0), clock=lambda: 0.0)
    assert early.outcome is DailyOutcome.TIMEOUT and early.statistics.option_evaluations == 0
    assert early.statistics.phase3_batch_calls == 1
    # start; three preprocessing checks; end preparation; first search check.
    ticks = iter((0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 2.0))
    late = solve(data, limits=DailySearchLimits(deadline=1.0), clock=lambda: next(ticks))
    assert late.outcome is DailyOutcome.TIMEOUT and late.statistics.option_evaluations == 3
    assert late.statistics.nodes == 0 and late.statistics.budget_exhaustion == "DEADLINE"


@pytest.mark.parametrize("reading", [float("nan"), float("inf"), True, "0", 10**1000])
def test_clock_rejects_invalid_readings(reading: Any) -> None:
    with pytest.raises(ValueError, match="finite monotonic"):
        solve(scenario(), clock=lambda: reading)


def test_clock_cannot_move_backwards() -> None:
    ticks = iter((1.0, 0.0))
    with pytest.raises(ValueError, match="backwards"):
        solve(scenario(), limits=DailySearchLimits(deadline=3.0), clock=lambda: next(ticks))


@pytest.mark.parametrize("field", ["knowledge", "context", "sources", "request", "candidates"])
def test_recursive_malformed_inputs_never_authorize_a_plan(field: str) -> None:
    data = scenario()
    original = data[field][0] if field == "candidates" else data[field]
    corrupt = original.model_copy(update={"affirmative_override": True})
    with pytest.raises(ValidationError):
        solve(data, **{field: (corrupt, *data[field][1:]) if field == "candidates" else corrupt})


def test_independently_deserialized_source_and_original_json() -> None:
    data = scenario()
    source = validate_contract_json(
        DailySourceSnapshot, data["sources"].model_dump_json(by_alias=True)
    )
    request = validate_contract_json(
        DailyPlanningRequest, data["request"].model_dump_json(by_alias=True)
    )
    assert source is not data["sources"]
    result = solve(data, sources=source, request=request)
    raw = result.model_dump_json(by_alias=True)
    assert validate_contract_json(DailySolveResult, raw) == result
    for token, replacement in (
        ('"outcome":"FEASIBLE"', '"outcome":"FEASIBLE","outcome":"INFEASIBLE"'),
        ('"requestDigest":', '"request_digest":"wrong","requestDigest":'),
        ('"value":60', '"value":1e9999'),
    ):
        changed = raw.replace(token, replacement, 1)
        assert changed != raw
        with pytest.raises(ValidationError):
            validate_contract_json(DailySolveResult, changed)


@pytest.fixture(scope="module")
def solved() -> DailySolveResult:
    return solve(scenario(), clock=lambda: 0.0)


@pytest.mark.parametrize(
    "mutation",
    [
        "outcome",
        "assignment",
        "facts",
        "trace",
        "explanation",
        "week",
        "options",
        "option_status",
        "statistics",
        "recipe_status",
    ],
)
def test_forged_computed_outputs_rejected(solved: DailySolveResult, mutation: str) -> None:
    attempt = solved.evaluations[0]
    if mutation == "outcome":
        modified = solved.model_copy(update={"outcome": DailyOutcome.INFEASIBLE})
    elif mutation == "assignment":
        assert solved.assignment is not None
        modified = solved.model_copy(
            update={"assignment": solved.assignment.model_copy(update={"day_id": "wrong"})}
        )
    elif mutation == "facts":
        observed = attempt.facts[1].observation.model_copy(update={"value": 61})
        modified = solved.model_copy(
            update={
                "evaluations": (
                    attempt.model_copy(
                        update={
                            "facts": (
                                attempt.facts[0],
                                attempt.facts[1].model_copy(update={"observation": observed}),
                            ),
                        }
                    ),
                )
            }
        )
    elif mutation == "trace":
        trace = attempt.trace.model_copy(
            update={
                "evaluations": (
                    attempt.trace.evaluations[0].model_copy(
                        update={
                            "status": RuleStatus.FAIL,
                        }
                    ),
                )
            }
        )
        modified = solved.model_copy(
            update={"evaluations": (attempt.model_copy(update={"trace": trace}),)}
        )
    elif mutation == "explanation":
        modified = solved.model_copy(
            update={"evaluations": (attempt.model_copy(update={"explanations": ()}),)}
        )
    elif mutation == "week":
        modified = solved.model_copy(
            update={"manifest": solved.manifest.model_copy(update={"deferred_checks": ()})}
        )
    elif mutation == "options":
        modified = solved.model_copy(update={"options": solved.options[:-1]})
    elif mutation == "option_status":
        option = solved.options[0]
        modified = solved.model_copy(
            update={
                "options": (
                    option.model_copy(
                        update={
                            "slots": (
                                option.slots[0].model_copy(update={"status": RuleStatus.UNKNOWN}),
                                *option.slots[1:],
                            ),
                        }
                    ),
                    *solved.options[1:],
                )
            }
        )
    elif mutation == "recipe_status":
        decision = solved.recipes.decisions[0]
        trace = decision.trace.model_copy(
            update={
                "evaluations": (
                    decision.trace.evaluations[0].model_copy(update={"status": RuleStatus.FAIL}),
                )
            }
        )
        modified = solved.model_copy(
            update={
                "recipes": solved.recipes.model_copy(
                    update={
                        "decisions": (
                            decision.model_copy(update={"trace": trace}),
                            *solved.recipes.decisions[1:],
                        ),
                    }
                )
            }
        )
    else:
        modified = solved.model_copy(
            update={"statistics": solved.statistics.model_copy(update={"nodes": 0})}
        )
    with pytest.raises(ValidationError):
        DailySolveResult.model_validate(modified)


@pytest.mark.parametrize("enum_type,field", [(DailyOutcome, "outcome"), (RuleStatus, "status")])
def test_counterfeit_result_enums(
    solved: DailySolveResult, enum_type: type[StrEnum], field: str
) -> None:
    member = next(iter(enum_type))
    counterfeit = str.__new__(enum_type, member.value)
    counterfeit._name_, counterfeit._value_ = member.name, member.value
    modified = (
        solved.model_copy(update={field: counterfeit})
        if field == "outcome"
        else solved.model_copy(
            update={
                "evaluations": (solved.evaluations[0].model_copy(update={"status": counterfeit}),),
            }
        )
    )
    with pytest.raises(ValidationError):
        DailySolveResult.model_validate(modified)


def test_no_global_cache_and_public_phase_counts_do_not_scale_with_assignments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import savora_ai.core.reasoning.combinations as combination_module
    import savora_ai.core.reasoning.daily as daily_module

    calls = {"recipe": 0, "combination": 0}
    from savora_ai.core.reasoning.combinations import evaluate_combination as original_combination
    from savora_ai.core.reasoning.filtering import filter_candidates as original_filter

    def counted_filter(*args: Any, **kwargs: Any) -> Any:
        calls["recipe"] += 1
        return original_filter(*args, **kwargs)

    def counted_combination(*args: Any, **kwargs: Any) -> Any:
        calls["combination"] += 1
        return original_combination(*args, **kwargs)

    monkeypatch.setattr(daily_module, "filter_candidates", counted_filter)
    monkeypatch.setattr(combination_module, "filter_candidates", counted_filter)
    monkeypatch.setattr(daily_module, "evaluate_combination", counted_combination)
    data = scenario(values=(10, 20), domains=((0, 1),) * 3, day_rules=(numeric_rule(value=100),))
    first = solve(data)
    assert first.statistics.completed_assignments == 8
    assert calls == {"recipe": 3, "combination": 2}
    assert first.statistics.phase3_candidate_evaluations == 6
    second = solve(data)
    assert second.outcome is first.outcome
    assert calls == {"recipe": 6, "combination": 4}  # Independent request, no retained PASS cache.


def rebind_release(
    data: dict[str, Any],
    *,
    knowledge: KnowledgeBaseSnapshot | None = None,
    context_changes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a separately designated fictional release, not an expected-outcome oracle."""
    kb = knowledge if knowledge is not None else data["knowledge"]
    context = RuleContext.build(
        data["context"].model_dump(exclude={"content_digest"})
        | {
            "expected_kb_digest": kb.content_digest,
        }
        | (context_changes or {})
    )
    options = []
    for original in data["sources"].options:
        combo = CombinationFacts.build(
            original.combination.model_dump(exclude={"content_digest"})
            | {
                "kb_digest": kb.content_digest,
                "context_digest": context.content_digest,
            }
        )
        reference = original.reference.model_copy(
            update={"combination_digest": combo.content_digest}
        )
        suitability = (
            None
            if original.suitability is None
            else original.suitability.model_copy(
                update={
                    "option": reference,
                }
            )
        )
        measurements = tuple(
            m.model_copy(update={"option": reference}) for m in original.measurements
        )
        options.append(
            DailyMealOption(
                reference=reference,
                combination=combo,
                suitability=suitability,
                measurements=measurements,
            )
        )
    sources = DailySourceSnapshot.build(
        data["sources"].model_dump(exclude={"content_digest"})
        | {
            "context": context,
            "options": tuple(options),
        }
    )
    refs = {option.reference.option_id: option.reference for option in options}
    request = DailyPlanningRequest.build(
        data["request"].model_dump(exclude={"content_digest"})
        | {
            "context_digest": context.content_digest,
            "source": sources,
            "expected_source": DailySourceReference(
                source_id=sources.source_id,
                version=sources.version,
                content_digest=sources.content_digest,
            ),
            "domains": tuple(
                DailySlotDomain(
                    slot=domain.slot, options=tuple(refs[ref.option_id] for ref in domain.options)
                )
                for domain in data["request"].domains
            ),
        }
    )
    return data | dict(knowledge=kb, context=context, sources=sources, request=request)


@pytest.mark.parametrize(
    "local,dependency,expected",
    [
        (False, None, DailyOutcome.INSUFFICIENT_DATA),
        (True, None, DailyOutcome.INSUFFICIENT_DATA),
        (True, False, DailyOutcome.FEASIBLE),
    ],
)
def test_dependency_unknown_dominates_false_local_condition(
    local: bool,
    dependency: bool | None,
    expected: DailyOutcome,
) -> None:
    data = scenario(enabled=local)
    kb = data["knowledge"]
    guard = RuleReference(rule_id="synthetic-context-guard", version="1")
    descriptor = kb.applicability_descriptors[0].model_copy(update={"dependencies": (guard,)})
    descriptors = (
        descriptor,
        ApplicabilityDescriptor(
            reference=guard,
            rule_references=(),
            required_context_facts=("synthetic_context_guard",),
            evidence=(evidence("dependency"),),
        ),
    )
    knowledge = build_knowledge_snapshot(
        kb.model_dump(exclude={"content_digest"})
        | {
            "applicability_descriptors": descriptors,
        }
    )
    facts = (
        *data["context"].facts,
        fact("synthetic_context_guard", FactSubjectKind.CONTEXT, "solver-context", dependency),
    )
    rebound = rebind_release(data, knowledge=knowledge, context_changes={"facts": facts})
    result = solve(rebound)
    assert result.outcome is expected


@pytest.mark.parametrize("mutation", ["unapproved", "unsupported", "retired", "missing_catalogue"])
def test_malformed_or_unapproved_day_release_cannot_hide_behind_fresh_digests(
    mutation: str,
) -> None:
    data = scenario()
    kb = data["knowledge"]
    original = next(r for r in kb.rules if r.scope is RuleScope.DAY)
    changed = original.model_dump()
    if mutation == "unapproved":
        changed.update(
            approval_status=ApprovalStatus.PENDING, approved_by=None, approval_reference=None
        )
    elif mutation == "unsupported":
        changed.update(attribute="unregistered_day", required_facts=("unregistered_day",))
    elif mutation == "retired":
        changed.update(lifecycle=RuleLifecycle.RETIRED)
    replacement = RuleDefinition.model_validate(changed)
    body = kb.model_dump(exclude={"content_digest"})
    body["rules"] = tuple(replacement if r.rule_id == original.rule_id else r for r in kb.rules)
    if mutation == "missing_catalogue":
        body["check_catalogue"] = tuple(
            entry.model_copy(update={"rule_references": ()})
            if entry.scope is RuleScope.DAY
            else entry
            for entry in kb.check_catalogue
        )
    with pytest.raises(ValidationError):
        rebound = rebind_release(data, knowledge=build_knowledge_snapshot(body))
        solve(rebound)


def test_request_rehash_does_not_supply_independent_source_authority() -> None:
    data = scenario()
    changed_source = DailySourceSnapshot.build(
        data["sources"].model_dump(exclude={"content_digest"})
        | {
            "version": "untrusted-new-version",
        }
    )
    changed_request = DailyPlanningRequest.build(
        data["request"].model_dump(exclude={"content_digest"})
        | {
            "source": changed_source,
            "expected_source": DailySourceReference(
                source_id=changed_source.source_id,
                version=changed_source.version,
                content_digest=changed_source.content_digest,
            ),
        }
    )
    with pytest.raises(ValidationError, match="independently selected"):
        solve(data, request=changed_request)
    changed_context = RuleContext.build(
        data["context"].model_dump(exclude={"content_digest"})
        | {
            "profile_version": "different-profile-version",
        }
    )
    with pytest.raises(ValidationError, match="independently selected"):
        solve(data, context=changed_context)


@pytest.mark.parametrize("mutation", ["configuration", "evidence", "measurement_unit"])
def test_structural_contradictions_reject_even_before_expired_budget(mutation: str) -> None:
    data = scenario()
    source = data["sources"]
    option = source.options[0]
    if mutation == "configuration":
        option = option.model_copy(
            update={
                "reference": option.reference.model_copy(
                    update={
                        "portion_configuration_id": "other",
                    }
                )
            }
        )
    elif mutation == "evidence":
        assert option.suitability is not None
        option = option.model_copy(
            update={"suitability": option.suitability.model_copy(update={"evidence": ()})}
        )
    else:
        option = option.model_copy(
            update={
                "measurements": (
                    option.measurements[0].model_copy(
                        update={
                            "unit": MeasurementUnit.G,
                        }
                    ),
                )
            }
        )
    corrupt = source.model_copy(update={"options": (option, *source.options[1:])})
    with pytest.raises(ValidationError):
        solve(data, sources=corrupt, limits=DailySearchLimits(deadline=0.0), clock=lambda: 0.0)


def test_unknown_branches_cannot_be_removed_to_forge_unsatisfiability() -> None:
    result = solve(
        scenario(values=(None, 20), domains=((0, 1),) * 3, day_rules=(numeric_rule(value=61),))
    )
    assert result.outcome is DailyOutcome.INSUFFICIENT_DATA
    modified = result.model_copy(
        update={
            "evaluations": (result.evaluations[-1],),
            "outcome": DailyOutcome.INFEASIBLE,
            "statistics": result.statistics.model_copy(
                update={"completed_assignments": 1, "unknown_branches": 0}
            ),
        }
    )
    with pytest.raises(ValidationError):
        DailySolveResult.model_validate(modified)


@pytest.mark.parametrize("amounts", [(0, 0, 0), (2**53, 1, 1), ((2**63 - 1) // 3,) * 3])
def test_exact_integer_totals_zero_and_above_float_precision(amounts: tuple[int, ...]) -> None:
    expected = sum(amounts)
    result = solve(scenario(values=amounts, day_rules=(numeric_rule(value=expected),)))
    assert result.outcome is DailyOutcome.FEASIBLE
    actual = result.evaluations[0].facts[1].observation.value
    assert type(actual) is int and actual == expected


def large_shared_recipe_scenario(size: int = 50) -> dict[str, Any]:
    data = scenario(values=(20,), domains=((0,),) * 3)
    base = data["sources"].options[0]
    options = []
    for index in range(size):
        combo = CombinationFacts.build(
            base.combination.model_dump(exclude={"content_digest"})
            | {
                "snapshot_id": f"large-snapshot-{index}",
                "portion_configuration_id": f"large-config-{index}",
            }
        )
        reference = base.reference.model_copy(
            update={
                "option_id": f"large-{index:02}",
                "snapshot_id": combo.snapshot_id,
                "combination_digest": combo.content_digest,
                "portion_configuration_id": combo.portion_configuration_id,
            }
        )
        assert base.suitability is not None
        options.append(
            DailyMealOption(
                reference=reference,
                combination=combo,
                suitability=base.suitability.model_copy(update={"option": reference}),
                measurements=(base.measurements[0].model_copy(update={"option": reference}),),
            )
        )
    source = DailySourceSnapshot.build(
        data["sources"].model_dump(exclude={"content_digest"})
        | {
            "options": tuple(options),
        }
    )
    request = DailyPlanningRequest.build(
        data["request"].model_dump(exclude={"content_digest"})
        | {
            "source": source,
            "expected_source": DailySourceReference(
                source_id=source.source_id,
                version=source.version,
                content_digest=source.content_digest,
            ),
            "domains": tuple(
                DailySlotDomain(slot=slot, options=tuple(o.reference for o in options))
                for slot in MealSlot
            ),
        }
    )
    return data | dict(request=request, sources=source)


def test_large_domains_do_not_materialize_cartesian_product() -> None:
    result = solve(large_shared_recipe_scenario())
    assert result.outcome is DailyOutcome.FEASIBLE
    assert result.statistics.option_evaluations == 50
    assert result.statistics.phase3_candidate_evaluations == 51
    assert result.statistics.nodes == 3 and result.statistics.completed_assignments == 1


def test_new_result_models_reject_hostile_containers_and_unchecked_limits(
    solved: DailySolveResult,
) -> None:
    class HostileTuple(tuple):
        def __iter__(self) -> Any:
            raise AssertionError("hostile iterator executed")

    with pytest.raises(ValidationError):
        DailySolveResult.model_validate(
            solved.model_copy(update={"evaluations": HostileTuple(solved.evaluations)})
        )
    for malformed in (True, -1, 200_001, "3"):
        with pytest.raises(ValidationError):
            DailySearchLimits.model_validate(
                DailySearchLimits().model_copy(update={"max_nodes": malformed})
            )


def test_derivation_provenance_conflict_is_a_validation_error() -> None:
    data = scenario()
    source = DailySourceSnapshot.build(
        data["sources"].model_dump(exclude={"content_digest"})
        | {
            "evidence": (evidence("synthetic-day-derivation"),),
        }
    )
    request = DailyPlanningRequest.build(
        data["request"].model_dump(exclude={"content_digest"})
        | {
            "source": source,
            "expected_source": DailySourceReference(
                source_id=source.source_id,
                version=source.version,
                content_digest=source.content_digest,
            ),
        }
    )
    with pytest.raises(ValidationError):
        solve(data, request=request, sources=source)
