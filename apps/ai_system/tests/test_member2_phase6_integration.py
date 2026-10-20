"""Independent final Phase 1-6 audit. No earlier fixtures or expected-value helpers."""

import hashlib
import json
from copy import deepcopy
from datetime import date, timedelta
from itertools import product
from typing import Any

import pytest
from pydantic import ValidationError

from savora_ai.core.reasoning.combinations import evaluate_combination
from savora_ai.core.reasoning.daily import build_day_check_manifest, solve_daily_plan
from savora_ai.core.reasoning.filtering import filter_candidates
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.weekly import (
    build_week_check_manifest,
    evaluate_weekly_trial,
    solve_weekly_plan,
)
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
    KnowledgeWorkflow,
    RuleCatalogueCoverage,
)
from savora_ai.schemas.reasoning import ApplicabilityStatus, FactObservation, RuleStatus
from savora_ai.schemas.weekly import (
    ExpectedWeekCheckManifest,
    WeekDayReference,
    WeeklyDayDomain,
    WeeklyPlanningRequest,
    WeeklySearchLimits,
    WeeklySourceReference,
    WeeklySourceSnapshot,
)
from savora_ai.schemas.weekly_solver import ComputedWeeklySolveResult


def ev(name: str = "audit-origin") -> EvidenceReference:
    return EvidenceReference(
        evidence_id=name,
        version="audit-1",
        source="Independent fictional final audit",
        locator="urn:phase6-audit:" + name,
        environment=RuleEnvironment.SYNTHETIC,
    )


def requirement(
    name: str,
    scope: RuleScope,
    attr: str,
    value: bool | int = True,
    op: PredicateOperator = PredicateOperator.EQ,
    requires: tuple[str, ...] | None = None,
) -> RuleDefinition:
    unit = (
        MeasurementUnit.MG
        if attr.endswith("quantity_total")
        else MeasurementUnit.DIMENSIONLESS
        if attr.endswith("slot_occurrences")
        else None
    )
    return RuleDefinition(
        rule_id=name,
        version="audit-1",
        scope=scope,
        severity=RuleSeverity.ABSOLUTE,
        domain=RuleDomain.CULINARY,
        attribute=attr,
        operator=op,
        value=value,
        unit=unit,
        required_facts=requires or (attr,),
        applicability_reference=RuleReference(rule_id="synthetic-context-enabled", version="1"),
        evidence=(ev(),),
        rationale="Fictional audit, no medical meaning",
        lifecycle=RuleLifecycle.ACTIVE,
        approval_status=ApprovalStatus.APPROVED,
        approved_by="audit-fiction",
        approval_reference=ev("audit-approval"),
        environment=RuleEnvironment.SYNTHETIC,
    )


def audit_case(
    *,
    variable: tuple[int, ...] = (),
    target: int = 63,
    domains: dict[int, tuple[int, ...]] | None = None,
    day_unknown: bool = False,
    missing_measurement: bool = False,
    day_cap: int | None = None,
    repeat_cap: int = 21,
    duplicate_components: bool = False,
    enabled: bool = True,
    unknown_dependency: bool = False,
    meal: int = 3,
) -> dict[str, Any]:
    """Two recipes, two A configurations and an independent B option. All input-owned."""
    evidence = (ev(),)
    checks = [
        requirement("profile", RuleScope.PROFILE, "synthetic_profile_flag"),
        requirement("recipe", RuleScope.RECIPE, "synthetic_flag"),
        requirement("combination", RuleScope.COMBINATION, "synthetic_combination_roles_compatible"),
        requirement(
            "day",
            RuleScope.DAY,
            "synthetic_day_complete",
            requires=("synthetic_day_complete", "synthetic_profile_enabled")
            if day_unknown
            else None,
        ),
        requirement("week-complete", RuleScope.WEEK, "synthetic_week_complete"),
        requirement("week-total", RuleScope.WEEK, "synthetic_week_quantity_total", target),
        requirement(
            "week-repeat",
            RuleScope.WEEK,
            "synthetic_week_max_recipe_slot_occurrences",
            repeat_cap,
            PredicateOperator.LE,
        ),
    ]
    if day_cap is not None:
        checks.append(
            requirement(
                "day-cap",
                RuleScope.DAY,
                "synthetic_day_quantity_total",
                day_cap,
                PredicateOperator.LE,
            )
        )
    nodes = tuple(
        FoodEntity(
            entity_id="audit-node-" + name,
            version="1",
            kind=FoodEntityKind.RECIPE_REFERENCE,
            canonical_name="Fictional " + name,
            catalogue_reference="audit-recipe-" + name,
            evidence=evidence,
        )
        for name in ("a", "b")
    )
    role = FoodEntity(
        entity_id="audit-role",
        version="1",
        kind=FoodEntityKind.CULINARY_ROLE_REFERENCE,
        canonical_name="Audit role",
        catalogue_reference="audit-role",
        evidence=evidence,
    )
    graph = FoodGraphSnapshot(
        graph_id="audit-graph",
        version="1",
        catalogue_version="audit-foods",
        environment=RuleEnvironment.SYNTHETIC,
        entities=(*nodes, role),
        relations=(),
        evidence=evidence,
    )
    refs = tuple(RuleReference(rule_id=r.rule_id, version=r.version) for r in checks)
    cells = tuple(
        CheckCatalogueEntry(
            entry_id=f"audit-{w.value}-{s.value}",
            version="1",
            kb_id="audit-kb",
            kb_version="1",
            check_catalogue_version="audit-checks",
            workflow=w,
            scope=s,
            rule_references=tuple(
                ref for ref, rule in zip(refs, checks, strict=True) if rule.scope is s
            ),
            evidence=evidence,
        )
        for w in KnowledgeWorkflow
        for s in RuleScope
        if w is not KnowledgeWorkflow.CRAVING_DISCOVERY
        or s in (RuleScope.PROFILE, RuleScope.RECIPE)
    )
    guard = RuleReference(rule_id="synthetic-context-guard", version="1")
    descriptors = (
        ApplicabilityDescriptor(
            reference=RuleReference(rule_id="synthetic-context-enabled", version="1"),
            rule_references=refs,
            required_context_facts=("synthetic_context_enabled",),
            evidence=evidence,
            dependencies=(guard,) if unknown_dependency else (),
        ),
    )
    if unknown_dependency:
        descriptors += (
            ApplicabilityDescriptor(
                reference=guard,
                rule_references=(),
                required_context_facts=("synthetic_context_guard",),
                evidence=evidence,
            ),
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
            rules=tuple(checks),
            active_rules=refs,
            applicability_descriptors=descriptors,
            check_catalogue=cells,
            rule_catalogue_coverage=tuple(
                RuleCatalogueCoverage(
                    coverage_id="coverage-" + c.entry_id,
                    version="1",
                    kb_id=c.kb_id,
                    kb_version=c.kb_version,
                    check_catalogue_version=c.check_catalogue_version,
                    workflow=c.workflow,
                    scope=c.scope,
                    complete=True,
                    reason="Independent exhaustive fictional inventory",
                    evidence=evidence,
                )
                for c in cells
            ),
            evidence=evidence,
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
                        complete=True,
                        evidence=evidence,
                    ),
                ),
                VersionedFact(
                    fact_id="synthetic_profile_flag",
                    version="1",
                    subject_kind=FactSubjectKind.PROFILE,
                    subject_id="audit-profile",
                    subject_version="1",
                    observation=FactObservation(
                        fact_id="synthetic_profile_flag",
                        value=True,
                        complete=True,
                        evidence=evidence,
                    ),
                ),
            ),
            evidence=evidence,
        )
    )
    candidates = tuple(
        CandidateRecipeFacts.build(
            dict(
                recipe_id=recipe_name,
                recipe_version="1",
                catalogue_version=kb.catalogue_version,
                graph_id=kb.graph_id,
                graph_version=kb.graph_version,
                graph_recipe_entity_id=node.entity_id,
                graph_recipe_reference=node,
                snapshot_id="snapshot-" + node.entity_id,
                snapshot_version="1",
                ingredient_coverage=IngredientCoverage(
                    coverage_id="inventory-" + node.entity_id,
                    version="1",
                    recipe_id=recipe_name,
                    recipe_version="1",
                    catalogue_version=kb.catalogue_version,
                    lines=(),
                    inventory_complete=True,
                    mapping_complete=True,
                    subingredients_complete=True,
                    gap_reasons=(),
                    evidence=evidence,
                ),
                facts=(
                    VersionedFact(
                        fact_id="synthetic_flag",
                        version="1",
                        subject_kind=FactSubjectKind.RECIPE,
                        subject_id=recipe_name,
                        subject_version="1",
                        catalogue_version=kb.catalogue_version,
                        observation=FactObservation(
                            fact_id="synthetic_flag", value=True, complete=True, evidence=evidence
                        ),
                    ),
                ),
                evidence=evidence,
            )
        )
        for recipe_name, node in zip(("audit-recipe-a", "audit-recipe-b"), nodes, strict=True)
    )
    options = []
    for index, candidate in enumerate((candidates[0], candidates[0], candidates[1])):
        recipe = RecipeSnapshotReference(
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
            recipe_snapshot=recipe,
            basis_reference=ev("basis-" + candidate.recipe_id),
            evidence=evidence,
        )
        parts = tuple(
            CombinationComponent(
                component_id="part-" + str(i),
                recipe_snapshot=recipe,
                preparation=prep,
                quantity=ComponentQuantity(
                    amount=index + 1,
                    unit=QuantityUnit.G,
                    preparation_id=prep.preparation_id,
                    preparation_version=prep.version,
                    basis_reference=prep.basis_reference,
                    portion_reference=ev("portion-" + str(index)),
                    evidence=evidence,
                ),
                role_references=(role,),
                evidence=evidence,
            )
            for i in range(2 if duplicate_components else 1)
        )
        combo_id = "meal-" + candidate.recipe_id
        combo = CombinationFacts.build(
            dict(
                combination_id=combo_id,
                version="1",
                snapshot_id="audit-combination-" + str(index),
                snapshot_version="1",
                components=parts,
                composition_complete=True,
                composition_gap_reasons=(),
                portion_state=PortionState.FIXED,
                portion_configuration_id="audit-config-" + str(index),
                portion_configuration_version="1",
                observations=(
                    CombinationObservation(
                        fact_id="synthetic_combination_roles_compatible",
                        version="1",
                        combination_id=combo_id,
                        combination_version="1",
                        observation=FactObservation(
                            fact_id="synthetic_combination_roles_compatible",
                            value=True,
                            complete=True,
                            evidence=evidence,
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
                evidence=evidence,
            )
        )
        ref = MealOptionReference(
            option_id="audit-option-" + str(index),
            combination_id=combo.combination_id,
            combination_version=combo.version,
            snapshot_id=combo.snapshot_id,
            snapshot_version=combo.snapshot_version,
            combination_digest=combo.content_digest,
            portion_state=PortionState.FIXED,
            portion_configuration_id=combo.portion_configuration_id,
            portion_configuration_version=combo.portion_configuration_version,
        )
        external = DailySourceReference(
            source_id="audit-provider", version="1", content_digest="a" * 64
        )
        measurement = FixedMealMeasurement(
            option=ref,
            source=external,
            value=None
            if missing_measurement
            else (meal, min(meal + 4, 3_074_457_345_618_258_602), 11)[index],
            complete=not missing_measurement,
            unit=MeasurementUnit.MG,
            measurement_basis=CombinationMeasurementBasis.FIXED_PORTION_TOTAL,
            components=parts,
            basis_reference=ev("measured-" + str(index)),
            evidence=evidence,
        )
        options.append(
            DailyMealOption(
                reference=ref,
                combination=combo,
                suitability=MealSlotSuitability(
                    option=ref,
                    source=external,
                    slots=tuple(MealSlot),
                    complete=True,
                    evidence=evidence,
                ),
                measurements=(measurement,),
            )
        )
    daily = DailySourceSnapshot.build(
        dict(
            source_id="audit-daily-source",
            version="1",
            context=context,
            options=tuple(options),
            evidence=evidence,
        )
    )
    daily_ref = DailySourceReference(
        source_id=daily.source_id, version=daily.version, content_digest=daily.content_digest
    )
    source = WeeklySourceSnapshot.build(
        dict(
            source_id="audit-week-source",
            version="1",
            daily_source=daily,
            expected_daily_source=daily_ref,
            evidence=evidence,
        )
    )
    source_ref = WeeklySourceReference(
        source_id=source.source_id, version=source.version, content_digest=source.content_digest
    )
    start = date(2026, 12, 28)
    days = tuple(
        WeeklyDayDomain(
            day=WeekDayReference(
                week_id="audit-week",
                week_version="1",
                day_id="audit-day-" + str(i + 1),
                day_index=i + 1,
                calendar_date=(start + timedelta(days=i)).isoformat(),
            ),
            domains=tuple(
                DailySlotDomain(
                    slot=slot,
                    options=tuple(
                        options[k].reference
                        for k in (domains or {}).get(
                            3 * i + j, (0, 1) if 3 * i + j in variable else (0,)
                        )
                    ),
                )
                for j, slot in enumerate(MealSlot)
            ),
        )
        for i in range(7)
    )
    request = WeeklyPlanningRequest.build(
        dict(
            request_id="audit-request",
            version="1",
            week_id="audit-week",
            week_version="1",
            start_date=start.isoformat(),
            context_id=context.context_id,
            context_version=context.version,
            context_digest=context.content_digest,
            source=source,
            expected_source=source_ref,
            days=days,
        )
    )
    return dict(
        request=request, candidates=candidates, knowledge=kb, context=context, sources=source
    )


def literal_oracle(
    domains: tuple[tuple[int, ...], ...],
    *,
    target: int,
    repeat_cap: int = 21,
    day_cap: int | None = None,
) -> tuple[DailyOutcome, tuple[int, ...] | None]:
    """Enumerate only explicitly variable positions; no production execution helpers."""
    variable = tuple(i for i, d in enumerate(domains) if len(d) > 1)
    for values in product(*(domains[i] for i in variable)):
        selected = [d[0] for d in domains]
        for i, value in zip(variable, values, strict=True):
            selected[i] = value
        weights = [(3, 7, 11)[i] for i in selected]
        if day_cap is not None and any(sum(weights[d : d + 3]) > day_cap for d in range(0, 21, 3)):
            continue
        if (
            sum(weights) != target
            or max(selected.count(0) + selected.count(1), selected.count(2)) > repeat_cap
        ):
            continue
        return DailyOutcome.FEASIBLE, tuple(selected)
    return DailyOutcome.INFEASIBLE, None


@pytest.mark.parametrize("variable,target", [((0, 3), 67), ((0, 3), 64), ((0, 3, 6, 9), 79)])
def test_literal_cross_day_oracle(variable: tuple[int, ...], target: int):
    data = audit_case(variable=variable, target=target)
    domains = tuple((0, 1) if i in variable else (0,) for i in range(21))
    expected, choices = literal_oracle(domains, target=target)
    result = solve_weekly_plan(**data)
    assert result.outcome is expected
    if choices is not None:
        assert result.witness is not None
        assert tuple(int(c.option.option_id[-1]) for c in result.witness.trial.choices) == choices
    else:
        assert result.certificate.statistics.exhaustive


@pytest.fixture(scope="module")
def accepted() -> ComputedWeeklySolveResult:
    return solve_weekly_plan(**audit_case())


@pytest.fixture(scope="module")
def refuted() -> ComputedWeeklySolveResult:
    return solve_weekly_plan(**audit_case(variable=(0, 3), target=64))


@pytest.fixture(scope="module")
def unresolved() -> ComputedWeeklySolveResult:
    return solve_weekly_plan(**audit_case(day_unknown=True))


@pytest.fixture(scope="module")
def pruned() -> ComputedWeeklySolveResult:
    return solve_weekly_plan(**audit_case(variable=(0, 1), day_cap=8))


@pytest.fixture(scope="module")
def interrupted() -> ComputedWeeklySolveResult:
    return solve_weekly_plan(
        **audit_case(variable=(0, 3), target=64), limits=WeeklySearchLimits(max_nodes=25)
    )


def test_public_phase1_to6_chain_and_complete_bindings(accepted: ComputedWeeklySolveResult):
    data = audit_case()
    recipes = filter_candidates(
        data["candidates"], knowledge=data["knowledge"], context=data["context"]
    )
    assert recipes.eligible_ids == ("audit-recipe-a", "audit-recipe-b")
    assert all(d.status is RuleStatus.PASS for d in recipes.decisions)
    first = data["sources"].daily_source.options[0]
    combo = evaluate_combination(
        first.combination,
        candidates=data["candidates"],
        knowledge=data["knowledge"],
        context=data["context"],
        trusted_combination=first.combination,
    )
    assert combo.status is RuleStatus.PASS
    assert all(p.status is RuleStatus.PASS for p in combo.prerequisites)
    request = data["request"]
    week_manifest = build_week_check_manifest(
        request, knowledge=data["knowledge"], context=data["context"], sources=data["sources"]
    )
    assert week_manifest == accepted.manifest
    daily = DailyPlanningRequest.build(
        dict(
            request_id=f"weekly-day-{request.content_digest}-1",
            version=request.version,
            day_id=request.days[0].day.day_id,
            context_id=request.context_id,
            context_version=request.context_version,
            context_digest=request.context_digest,
            expected_source=request.source.expected_daily_source,
            source=request.source.daily_source,
            domains=request.days[0].domains,
        )
    )
    day_manifest = build_day_check_manifest(
        daily,
        knowledge=data["knowledge"],
        context=data["context"],
        sources=data["sources"].daily_source,
    )
    day = solve_daily_plan(
        daily,
        candidates=data["candidates"],
        knowledge=data["knowledge"],
        context=data["context"],
        sources=data["sources"].daily_source,
    )
    assert day.outcome is DailyOutcome.FEASIBLE
    assert day.weekly_feasibility == "NOT_EVALUATED"
    assert accepted.outcome is DailyOutcome.FEASIBLE and accepted.witness is not None
    witness = accepted.witness
    evaluated = evaluate_weekly_trial(
        request,
        witness.trial,
        candidates=data["candidates"],
        knowledge=data["knowledge"],
        context=data["context"],
        sources=data["sources"],
    )
    assert evaluated.status is RuleStatus.PASS
    assert evaluated.facts == witness.facts
    assert [f.observation.value for f in witness.facts] == [True, 63, 21]
    assert day_manifest.deferred_checks == accepted.manifest.required_checks
    assert len(witness.assignment.days) == 7 and len(witness.trial.choices) == 21
    assert witness.days[0].evaluation.trial == day.evaluations[-1].trial
    for record in witness.days:
        evaluation = record.evaluation
        assert evaluation.status is RuleStatus.PASS
        assert evaluation.trace.required_checks == accepted.manifest.day_checks
        assert all(f.assignment_digest == evaluation.trial.content_digest for f in evaluation.facts)
        assert all(
            e.trial_digest == evaluation.trial.content_digest for e in evaluation.explanations
        )
    assert all(c.option.portion_state is PortionState.FIXED for c in witness.trial.choices)
    assert tuple(e.rule for e in witness.trace.evaluations) == accepted.manifest.required_checks
    assert all(
        e.manifest_digest == accepted.manifest.content_digest
        and e.trial_digest == witness.trial.content_digest
        for e in witness.explanations
    )


def test_four_outcomes_and_sound_day_pruning(
    refuted: ComputedWeeklySolveResult,
    unresolved: ComputedWeeklySolveResult,
    pruned: ComputedWeeklySolveResult,
    interrupted: ComputedWeeklySolveResult,
):
    assert refuted.outcome is DailyOutcome.INFEASIBLE
    assert refuted.certificate.statistics.exhaustive
    assert sum(r.kind == "LEAF" for r in refuted.certificate.records) == 4
    assert unresolved.outcome is DailyOutcome.INSUFFICIENT_DATA
    assert unresolved.certificate.statistics.unknown_hypotheses == 1
    assert pruned.outcome is DailyOutcome.INFEASIBLE
    assert pruned.certificate.statistics.pruned_subtrees == 4
    assert pruned.certificate.statistics.week_evaluations == 0
    assert all(len(r.path) == 3 for r in pruned.certificate.records)
    assert interrupted.outcome is DailyOutcome.TIMEOUT
    assert interrupted.certificate.statistics.nodes == 25
    assert not interrupted.certificate.statistics.exhaustive
    assert interrupted.certificate.frontier and interrupted.certificate.next_indexes


def test_known_week_fail_refutes_day_unknown():
    result = solve_weekly_plan(**audit_case(day_unknown=True, target=64))
    assert result.outcome is DailyOutcome.INFEASIBLE
    assert result.certificate.statistics.unknown_hypotheses == 0
    assert any(d.stage == "DAY" and d.status is RuleStatus.UNKNOWN for d in result.diagnostics)


def test_recipe_presence_duplicate_parts_and_configuration_identity():
    # Both A configurations still contain A. Only a B substitution can reduce A's count.
    domains = {0: (0, 1, 2)}
    result = solve_weekly_plan(
        **audit_case(domains=domains, target=71, repeat_cap=20, duplicate_components=True)
    )
    expected, chosen = literal_oracle(
        tuple(domains.get(i, (0,)) for i in range(21)), target=71, repeat_cap=20
    )
    assert expected is DailyOutcome.FEASIBLE and chosen == (2, *([0] * 20))
    assert result.outcome is expected and result.witness is not None
    assert result.witness.trial.choices[0].option.option_id == "audit-option-2"
    assert result.witness.facts[2].observation.value == 20
    assert all(len(o.recipe_ids) == 1 for o in result.witness.facts[2].occurrences)


@pytest.mark.parametrize(
    "measurement,total",
    [
        (9_007_199_254_740_993, 189_151_184_349_560_853),
        (3_074_457_345_618_258_602, 64_563_604_257_983_430_642),
    ],
)
def test_solver_exact_large_integers_and_weekly_maximum(measurement: int, total: int):
    # Unreferenced alternative measurements must also stay within the meal bound.
    data = audit_case(meal=measurement, target=total)
    result = solve_weekly_plan(**data)
    assert result.outcome is DailyOutcome.FEASIBLE and result.witness is not None
    assert type(result.witness.facts[1].observation.value) is int
    assert result.witness.facts[1].observation.value == total


def test_missing_measurements_remain_unknown():
    result = solve_weekly_plan(**audit_case(missing_measurement=True))
    assert result.outcome is DailyOutcome.INSUFFICIENT_DATA
    assert result.certificate.statistics.unknown_hypotheses == 1


def test_unknown_dependency_dominates_false_and_na_is_evidenced():
    unknown = solve_weekly_plan(**audit_case(enabled=False, unknown_dependency=True, target=64))
    assert unknown.outcome is DailyOutcome.INSUFFICIENT_DATA
    known = solve_weekly_plan(**audit_case(enabled=False, target=64))
    assert known.outcome is DailyOutcome.FEASIBLE and known.witness is not None
    assert all(
        e.applicability is ApplicabilityStatus.NOT_APPLICABLE
        and e.status is RuleStatus.UNKNOWN
        and e.applicability_evidence
        for e in known.witness.trace.evaluations
    )


def reject_computed(body: dict[str, Any], attack: str) -> None:
    try:
        validate_contract_json(ComputedWeeklySolveResult, json.dumps(body))
    except ValidationError:
        return
    pytest.fail("accepted forged proof: " + attack)


def test_spliced_omitted_duplicated_reordered_and_truncated_proofs(
    refuted: ComputedWeeklySolveResult,
):
    original = refuted.model_dump(mode="json", by_alias=True)
    indexes = [i for i, r in enumerate(original["certificate"]["records"]) if r["kind"] == "LEAF"]
    for attack in ("omitted", "duplicate", "reorder", "counter", "bytes", "exhaustive"):
        body = deepcopy(original)
        certificate = body["certificate"]
        if attack == "omitted":
            del certificate["records"][indexes[0]]
            certificate["statistics"]["weekEvaluations"] -= 2
            certificate["statistics"]["proofRecords"] -= 1
            certificate["statistics"]["knownFailures"] -= 1
        elif attack == "duplicate":
            certificate["records"][indexes[1]] = deepcopy(certificate["records"][indexes[0]])
        elif attack == "reorder":
            certificate["records"] = list(reversed(certificate["records"]))
        elif attack == "counter":
            certificate["statistics"]["backtracks"] += 1
        elif attack == "bytes":
            certificate["statistics"]["proofBytes"] -= 1
        else:
            certificate["statistics"]["exhaustive"] = False
        reject_computed(body, attack)


def test_changed_prune_and_unexplored_frontiers(
    pruned: ComputedWeeklySolveResult, interrupted: ComputedWeeklySolveResult
):
    body = pruned.model_dump(mode="json", by_alias=True)
    assert len(body["certificate"]["records"]) == 4
    body["certificate"]["records"][1] = deepcopy(body["certificate"]["records"][0])
    reject_computed(body, "duplicated DAY subtree leaves another subtree uncovered")
    for field in ("frontier", "nextIndexes"):
        body = interrupted.model_dump(mode="json", by_alias=True)
        original = body["certificate"][field]
        body["certificate"][field] = original[1:] + original[:1]
        assert body["certificate"][field] != original
        reject_computed(body, "reordered " + field)
    body = interrupted.model_dump(mode="json", by_alias=True)
    body["outcome"] = "INFEASIBLE"
    body["certificate"]["statistics"].update(exhaustive=True, termination=None)
    body["certificate"]["frontier"] = []
    body["certificate"]["nextIndexes"] = []
    reject_computed(body, "unfinished search relabelled exhaustive")


def test_unknown_cannot_be_erased_to_claim_infeasible(unresolved: ComputedWeeklySolveResult):
    body = unresolved.model_dump(mode="json", by_alias=True)
    body["outcome"] = "INFEASIBLE"
    body["certificate"]["statistics"]["unknownHypotheses"] = 0
    body["certificate"]["statistics"]["knownFailures"] = 1
    reject_computed(body, "erased unrefuted UNKNOWN")


def ordered_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def test_rehashed_witness_and_missing_required_evaluations(accepted: ComputedWeeklySolveResult):
    body = accepted.model_dump(mode="json", by_alias=True)
    witness = body["witness"]
    original_digest = ordered_hash(
        [
            witness["trial"],
            *(r["evaluation"] for r in witness["days"]),
            *witness["facts"],
            witness["trace"],
        ]
    )
    assert original_digest == body["certificate"]["records"][-1]["evaluationDigest"]
    witness["facts"][1]["observation"]["value"] = 64
    for evaluation in witness["trace"]["evaluations"]:
        for fact in evaluation["facts"]:
            if fact["factId"] == "synthetic_week_quantity_total":
                fact["value"] = 64
    body["certificate"]["records"][-1]["evaluationDigest"] = ordered_hash(
        [
            witness["trial"],
            *(r["evaluation"] for r in witness["days"]),
            *witness["facts"],
            witness["trace"],
        ]
    )
    reject_computed(body, "correctly rehashed numeric lie")
    body = accepted.model_dump(mode="json", by_alias=True)
    body["witness"]["trace"]["evaluations"].pop()
    reject_computed(body, "missing mandatory WEEK evaluation")
    for container, field in (("knowledge", "kbId"), ("request", "contextDigest")):
        body = accepted.model_dump(mode="json", by_alias=True)
        body["manifest"][container][field] = "f" * 64
        reject_computed(body, "foreign " + container)


def declaration_hash(body: dict[str, Any]) -> str:
    def canonical(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: canonical(v) for k, v in value.items()}
        if isinstance(value, list):
            return sorted(
                (canonical(v) for v in value),
                key=lambda v: json.dumps(
                    v, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ),
            )
        return value

    return ordered_hash(canonical({k: v for k, v in body.items() if k != "contentDigest"}))


def test_rehashed_reduced_manifests_and_missing_catalogue_coverage(
    accepted: ComputedWeeklySolveResult,
):
    for field in ("requiredChecks", "dayChecks"):
        body = accepted.manifest.model_dump(mode="json", by_alias=True)
        assert declaration_hash(body) == body["contentDigest"]
        body[field] = []
        body["contentDigest"] = declaration_hash(body)
        with pytest.raises(ValidationError):
            validate_contract_json(ExpectedWeekCheckManifest, json.dumps(body))
    body = accepted.manifest.knowledge.model_dump(exclude={"content_digest"})
    body["rule_catalogue_coverage"] = body["rule_catalogue_coverage"][:-1]
    with pytest.raises(ValidationError):
        build_knowledge_snapshot(body)


def test_release_and_measurement_transplants():
    data = audit_case()
    for name in ("context", "sources"):
        body = data[name].model_dump(exclude={"content_digest"}) | dict(version="stale")
        if name == "context":
            body["facts"] = tuple(
                f.model_copy(update={"subject_version": "stale", "context_version": "stale"})
                if f.subject_kind is FactSubjectKind.CONTEXT
                else f
                for f in data[name].facts
            )
        changed = type(data[name]).build(body)
        with pytest.raises(ValidationError):
            solve_weekly_plan(**(data | {name: changed}), limits=WeeklySearchLimits(max_nodes=0))
    kb = data["knowledge"]
    graph = kb.graph.model_copy(
        update={
            "entities": (
                kb.graph.entities[0].model_copy(
                    update={"canonical_name": "Different accepted source declaration"}
                ),
                *kb.graph.entities[1:],
            )
        }
    )
    changed_kb = build_knowledge_snapshot(
        kb.model_dump(exclude={"content_digest"}) | dict(graph=graph)
    )
    with pytest.raises(ValidationError):
        changed_inputs: dict[str, Any] = dict(data)
        changed_inputs["knowledge"] = changed_kb
        solve_weekly_plan(**changed_inputs)
    small, large = data["sources"].daily_source.options[:2]
    transplanted = small.measurements[0].model_copy(
        update={"components": large.combination.components}
    )
    with pytest.raises(ValidationError):
        DailyMealOption.model_validate(small.model_copy(update={"measurements": (transplanted,)}))
    transplanted = small.measurements[0].model_copy(
        update={
            "basis_reference": ev().model_copy(
                update={"source": "Contradictory metadata under the same evidence identity"}
            )
        }
    )
    with pytest.raises(ValidationError):
        DailyMealOption.model_validate(small.model_copy(update={"measurements": (transplanted,)}))


def test_strict_weekly_ingress_and_unchecked_storage(accepted: ComputedWeeklySolveResult):
    raw = accepted.model_dump_json(by_alias=True)
    assert len(raw.encode()) <= 1_048_576
    assert validate_contract_json(ComputedWeeklySolveResult, raw) == accepted
    with pytest.raises(ValidationError):
        validate_contract_json(
            ComputedWeeklySolveResult,
            raw.replace('"outcome":"FEASIBLE"', '"outcome":"FEASIBLE","outcome":"INFEASIBLE"', 1),
        )
    with pytest.raises(ValidationError):
        validate_contract_json(
            ComputedWeeklySolveResult, raw.replace('"dayIndex":1', '"dayIndex":1,"day_index":1', 1)
        )
    for payload in ("[" * 65 + "]" * 65, " " * 1_048_577 + "{}", '{"x":NaN}', '{"x":1e9999}'):
        with pytest.raises(ValidationError):
            validate_contract_json(WeeklyPlanningRequest, payload)

    class Hostile(dict):
        def items(self):
            raise AssertionError("hostile storage must never run")

    forged = accepted.model_copy()
    object.__setattr__(forged, "__pydantic_extra__", Hostile({"outcome": DailyOutcome.FEASIBLE}))
    with pytest.raises(ValidationError):
        ComputedWeeklySolveResult.model_validate(forged)
    forged = str.__new__(DailyOutcome, "FEASIBLE")
    object.__setattr__(forged, "_name_", "FEASIBLE")
    object.__setattr__(forged, "_value_", "FEASIBLE")
    with pytest.raises(ValidationError):
        ComputedWeeklySolveResult.model_validate(accepted.model_copy(update={"outcome": forged}))
    malformed_payload: dict[str, Any] = dict(accepted.manifest.request.__dict__)
    malformed_payload["days"] = ()
    malformed = WeeklyPlanningRequest.model_construct(**malformed_payload)
    with pytest.raises(ValidationError):
        solve_weekly_plan(
            malformed,
            candidates=accepted.candidates,
            knowledge=accepted.manifest.knowledge,
            context=accepted.manifest.request.source.daily_source.context,
            sources=accepted.manifest.request.source,
        )


def test_canonical_input_permutations_and_cache_eviction(accepted: ComputedWeeklySolveResult):
    data = audit_case()
    request = data["request"]
    reversed_days = tuple(
        WeeklyDayDomain(
            day=d.day,
            domains=tuple(
                DailySlotDomain(slot=x.slot, options=tuple(reversed(x.options)))
                for x in reversed(d.domains)
            ),
        )
        for d in reversed(request.days)
    )
    changed = WeeklyPlanningRequest.build(
        request.model_dump(exclude={"content_digest"}) | dict(days=reversed_days)
    )
    permuted_inputs: dict[str, Any] = dict(data)
    permuted_inputs.update(request=changed, candidates=tuple(reversed(data["candidates"])))
    permuted = solve_weekly_plan(**permuted_inputs, limits=WeeklySearchLimits(max_cache_entries=0))
    assert permuted.outcome is DailyOutcome.FEASIBLE
    assert permuted.witness == accepted.witness
    assert permuted.certificate.statistics.cache_entries == 0


def test_proof_exhaustion_at_full_assignment_is_timeout():
    result = solve_weekly_plan(
        **audit_case(variable=(0, 3), target=64),
        limits=WeeklySearchLimits(max_proof_records=10, max_diagnostics=0),
    )
    assert result.outcome is DailyOutcome.TIMEOUT
    assert len(result.certificate.frontier) == 21
    assert result.certificate.statistics.proof_records == 10
    assert result.certificate.statistics.termination == "PROOF_RECORD_BUDGET"
    assert result.certificate.statistics.week_evaluations == 0
    assert result.diagnostics == ()
    body = result.model_dump(mode="json", by_alias=True)
    body["outcome"] = "INFEASIBLE"
    body["certificate"]["statistics"].update(exhaustive=True, termination=None)
    reject_computed(body, "truncated proof at complete assignment")


def test_deadline_certificate_requires_declared_deadline():
    result = solve_weekly_plan(
        **audit_case(), limits=WeeklySearchLimits(deadline=10), clock=lambda: 10.0
    )
    assert result.outcome is DailyOutcome.TIMEOUT
    assert result.certificate.deadline_checkpoint == 1
    body = result.model_dump(mode="json", by_alias=True)
    body["limits"]["deadline"] = None
    body["timing"]["validationDeadlineReached"] = False
    reject_computed(body, "deadline checkpoint without a declared deadline")
