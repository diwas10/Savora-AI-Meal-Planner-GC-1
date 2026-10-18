"""Independent literal WEEK evaluation expectations; synthetic sources only."""

import hashlib
import json
from copy import deepcopy
from datetime import date, timedelta
from enum import StrEnum
from typing import Any

import pytest
from pydantic import ValidationError

from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.weekly import build_week_check_manifest, evaluate_weekly_trial
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
    CompositionGapReason,
    PortionState,
    PreparationBinding,
    QuantityUnit,
    RecipeSnapshotReference,
)
from savora_ai.schemas.daily import (
    DailyMealOption,
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
from savora_ai.schemas.reasoning import FactObservation, RuleStatus
from savora_ai.schemas.weekly import (
    ExpectedWeekCheckManifest,
    WeekDayReference,
    WeeklyDayDomain,
    WeeklyPlanningRequest,
    WeeklySourceReference,
    WeeklySourceSnapshot,
    WeeklyTrial,
    WeeklyTrialChoice,
)
from savora_ai.schemas.weekly_evaluation import WeeklyTrialEvaluation


def evidence(name: str = "week-fiction", **changes: Any) -> EvidenceReference:
    return EvidenceReference.model_validate(
        dict(
            evidence_id=name,
            version="1",
            source="Independent fictional weekly contract fixture",
            locator="urn:weekly-fiction:" + name,
            environment=RuleEnvironment.SYNTHETIC,
        )
        | changes
    )


def rule(name: str = "week", **changes: Any) -> RuleDefinition:
    return RuleDefinition.model_validate(
        dict(
            rule_id=name,
            version="1",
            scope=RuleScope.WEEK,
            severity=RuleSeverity.ABSOLUTE,
            domain=RuleDomain.CULINARY,
            attribute="synthetic_week_complete",
            operator=PredicateOperator.EQ,
            value=True,
            required_facts=("synthetic_week_complete",),
            applicability_reference=RuleReference(rule_id="synthetic-context-enabled", version="1"),
            evidence=(evidence(),),
            rationale="Fictional weekly requirement, no medical meaning",
            lifecycle=RuleLifecycle.ACTIVE,
            approval_status=ApprovalStatus.APPROVED,
            approved_by="fictional-reviewer",
            approval_reference=evidence("fictional-approval"),
            environment=RuleEnvironment.SYNTHETIC,
        )
        | changes
    )


def foundation(checks: tuple[RuleDefinition, ...] | None = None) -> tuple[Any, Any, Any]:
    if checks is None:
        checks = (
            rule(
                "recipe",
                scope=RuleScope.RECIPE,
                attribute="synthetic_flag",
                required_facts=("synthetic_flag",),
            ),
            rule(
                "combination",
                scope=RuleScope.COMBINATION,
                attribute="synthetic_combination_roles_compatible",
                required_facts=("synthetic_combination_roles_compatible",),
            ),
            rule(
                "day",
                scope=RuleScope.DAY,
                attribute="synthetic_day_complete",
                required_facts=("synthetic_day_complete",),
            ),
            rule(),
        )
    ev = (evidence(),)
    node = FoodEntity(
        entity_id="week-recipe-node",
        version="1",
        kind=FoodEntityKind.RECIPE_REFERENCE,
        canonical_name="Fictional dish",
        catalogue_reference="week-recipe",
        evidence=ev,
    )
    role = FoodEntity(
        entity_id="week-role",
        version="1",
        kind=FoodEntityKind.CULINARY_ROLE_REFERENCE,
        canonical_name="Fictional role",
        catalogue_reference="role",
        evidence=ev,
    )
    graph = FoodGraphSnapshot(
        graph_id="week-graph",
        version="1",
        catalogue_version="foods-1",
        environment=RuleEnvironment.SYNTHETIC,
        entities=(node, role),
        relations=(),
        evidence=ev,
    )
    refs = tuple(RuleReference(rule_id=r.rule_id, version=r.version) for r in checks)
    cells = tuple(
        CheckCatalogueEntry(
            entry_id=f"cell-{workflow.value}-{scope.value}",
            version="1",
            kb_id="week-kb",
            kb_version="1",
            check_catalogue_version="checks-1",
            workflow=workflow,
            scope=scope,
            rule_references=tuple(
                ref
                for ref, r in zip(refs, checks, strict=True)
                if r.scope is scope
                and r.lifecycle is RuleLifecycle.ACTIVE
                and r.severity is RuleSeverity.ABSOLUTE
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
            kb_id="week-kb",
            version="1",
            environment=RuleEnvironment.SYNTHETIC,
            graph_id=graph.graph_id,
            graph_version=graph.version,
            catalogue_version=graph.catalogue_version,
            taxonomy_version=None,
            check_catalogue_version="checks-1",
            graph=graph,
            rules=checks,
            active_rules=tuple(
                ref
                for ref, r in zip(refs, checks, strict=True)
                if r.lifecycle is RuleLifecycle.ACTIVE
            ),
            applicability_descriptors=(
                ApplicabilityDescriptor(
                    reference=RuleReference(rule_id="synthetic-context-enabled", version="1"),
                    rule_references=refs,
                    required_context_facts=("synthetic_context_enabled",),
                    evidence=ev,
                ),
            )
            if checks
            else (),
            check_catalogue=cells,
            rule_catalogue_coverage=tuple(
                RuleCatalogueCoverage(
                    coverage_id="coverage-" + c.entry_id,
                    version="1",
                    kb_id="week-kb",
                    kb_version="1",
                    check_catalogue_version="checks-1",
                    workflow=c.workflow,
                    scope=c.scope,
                    complete=True,
                    reason="Fictional exhaustive inventory",
                    evidence=ev,
                )
                for c in cells
            ),
            evidence=ev,
        )
    )
    candidate = CandidateRecipeFacts.build(
        dict(
            recipe_id="week-recipe",
            recipe_version="1",
            catalogue_version=graph.catalogue_version,
            graph_id=graph.graph_id,
            graph_version=graph.version,
            graph_recipe_entity_id=node.entity_id,
            graph_recipe_reference=node,
            snapshot_id="week-recipe-snapshot",
            snapshot_version="1",
            ingredient_coverage=IngredientCoverage(
                coverage_id="week-inventory",
                version="1",
                recipe_id="week-recipe",
                recipe_version="1",
                catalogue_version=graph.catalogue_version,
                lines=(),
                inventory_complete=True,
                mapping_complete=True,
                subingredients_complete=True,
                gap_reasons=(),
                evidence=ev,
            ),
            facts=(),
            evidence=ev,
        )
    )
    context = RuleContext.build(
        dict(
            context_id="week-context",
            version="1",
            profile_id="week-profile",
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
            facts=(),
            evidence=ev,
        )
    )
    return kb, candidate, context


def digest(model: Any, *, excludes: set[str] | None = None) -> str:
    """Independent documented unordered-declaration encoding; no production hash helper."""

    def encode(value: Any) -> str:
        if isinstance(value, dict):
            return (
                "{" + ",".join(json.dumps(k) + ":" + encode(value[k]) for k in sorted(value)) + "}"
            )
        if isinstance(value, list):
            return "[" + ",".join(sorted(encode(v) for v in value)) + "]"
        return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))

    data = model.model_dump(
        mode="json", by_alias=True, exclude={"content_digest"} if excludes is None else excludes
    )
    return hashlib.sha256(encode(data).encode()).hexdigest()


def revise(model: Any, **changes: Any) -> Any:
    return type(model).build(model.model_dump(exclude={"content_digest"}) | changes)


def packet(
    *,
    checks: tuple[RuleDefinition, ...] | None = None,
    fixed: bool = True,
    suitability: bool = True,
    copies: int = 1,
) -> dict[str, Any]:
    kb, candidate, context = foundation(checks)
    ev = (evidence(),)
    context = revise(
        context,
        facts=(
            VersionedFact(
                fact_id="synthetic_context_enabled",
                version="1",
                subject_kind=FactSubjectKind.CONTEXT,
                subject_id=context.context_id,
                subject_version=context.version,
                context_id=context.context_id,
                context_version=context.version,
                observation=FactObservation(
                    fact_id="synthetic_context_enabled", value=True, complete=True, evidence=ev
                ),
            ),
        ),
    )
    candidate = revise(
        candidate,
        facts=(
            VersionedFact(
                fact_id="synthetic_flag",
                version="1",
                subject_kind=FactSubjectKind.RECIPE,
                subject_id=candidate.recipe_id,
                subject_version=candidate.recipe_version,
                catalogue_version=kb.catalogue_version,
                observation=FactObservation(
                    fact_id="synthetic_flag", value=True, complete=True, evidence=ev
                ),
            ),
        ),
    )
    recipe = RecipeSnapshotReference(
        recipe_id=candidate.recipe_id,
        recipe_version=candidate.recipe_version,
        snapshot_id=candidate.snapshot_id,
        snapshot_version=candidate.snapshot_version,
        content_digest=candidate.content_digest,
        catalogue_version=candidate.catalogue_version,
    )
    prep = PreparationBinding(
        preparation_id="week-cooked",
        version="1",
        recipe_snapshot=recipe,
        basis_reference=evidence("cooked-basis"),
        evidence=ev,
    )
    options = []
    for index in range(2):
        components = tuple(
            CombinationComponent(
                component_id=f"occurrence-{i}",
                recipe_snapshot=recipe,
                preparation=prep,
                quantity=ComponentQuantity(
                    amount=index + 1,
                    unit=QuantityUnit.G,
                    preparation_id=prep.preparation_id,
                    preparation_version=prep.version,
                    basis_reference=prep.basis_reference,
                    portion_reference=evidence(f"portion-{index}"),
                    evidence=ev,
                )
                if fixed
                else None,
                role_references=(kb.graph.entities[1],),
                evidence=ev,
            )
            for i in range(copies)
        )
        combo = CombinationFacts.build(
            dict(
                combination_id="week-meal",
                version="1",
                snapshot_id=f"week-meal-snapshot-{index}",
                snapshot_version="1",
                components=components,
                composition_complete=True,
                composition_gap_reasons=(),
                portion_state=PortionState.FIXED if fixed else PortionState.UNASSIGNED,
                portion_configuration_id=f"config-{index}" if fixed else None,
                portion_configuration_version="1" if fixed else None,
                observations=(
                    CombinationObservation(
                        fact_id="synthetic_combination_roles_compatible",
                        version="1",
                        combination_id="week-meal",
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
            option_id=f"week-option-{index}",
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
            source_id="week-provider", version="1", content_digest="b" * 64
        )
        options.append(
            DailyMealOption(
                reference=ref,
                combination=combo,
                suitability=MealSlotSuitability(
                    option=ref, source=external, slots=tuple(MealSlot), complete=True, evidence=ev
                )
                if suitability
                else None,
                measurements=(
                    FixedMealMeasurement(
                        option=ref,
                        source=external,
                        value=(2, 5)[index],
                        complete=True,
                        unit=MeasurementUnit.MG,
                        measurement_basis=CombinationMeasurementBasis.FIXED_PORTION_TOTAL,
                        components=components,
                        basis_reference=evidence(f"measure-{index}"),
                        evidence=ev,
                    ),
                )
                if fixed
                else (),
            )
        )
    daily = DailySourceSnapshot.build(
        dict(
            source_id="week-common-source",
            version="1",
            context=context,
            options=tuple(options),
            evidence=ev,
        )
    )
    daily_ref = DailySourceReference(
        source_id=daily.source_id, version=daily.version, content_digest=daily.content_digest
    )
    source = WeeklySourceSnapshot.build(
        dict(
            source_id="weekly-source",
            version="1",
            expected_daily_source=daily_ref,
            daily_source=daily,
            evidence=ev,
        )
    )
    source_ref = WeeklySourceReference(
        source_id=source.source_id, version=source.version, content_digest=source.content_digest
    )
    start = date(2026, 10, 19)
    days = tuple(
        WeeklyDayDomain(
            day=WeekDayReference(
                week_id="week-1",
                week_version="1",
                day_id=f"independent-day-{i}",
                day_index=i,
                calendar_date=(start + timedelta(days=i - 1)).isoformat(),
            ),
            domains=tuple(
                DailySlotDomain(slot=slot, options=tuple(o.reference for o in options))
                for slot in MealSlot
            ),
        )
        for i in range(1, 8)
    )
    request = WeeklyPlanningRequest.build(
        dict(
            request_id="weekly-request",
            version="1",
            week_id="week-1",
            week_version="1",
            start_date=start.isoformat(),
            context_id=context.context_id,
            context_version=context.version,
            context_digest=context.content_digest,
            expected_source=source_ref,
            source=source,
            days=days,
        )
    )
    manifest = ExpectedWeekCheckManifest.build(
        dict(
            request=request,
            knowledge=kb,
            required_checks=tuple(
                sorted(
                    (r for r in kb.rules if r.scope is RuleScope.WEEK),
                    key=lambda r: (r.rule_id, r.version),
                )
            ),
            day_checks=tuple(
                sorted(
                    (r for r in kb.rules if r.scope is RuleScope.DAY),
                    key=lambda r: (r.rule_id, r.version),
                )
            ),
        )
    )
    return dict(
        kb=kb,
        candidate=candidate,
        context=context,
        daily=daily,
        source=source,
        request=request,
        manifest=manifest,
    )


def trial(request: WeeklyPlanningRequest) -> WeeklyTrial:
    return WeeklyTrial.build(
        dict(
            request_digest=request.content_digest,
            week_id=request.week_id,
            week_version=request.week_version,
            start_date=request.start_date,
            choices=tuple(
                WeeklyTrialChoice(day=d.day, slot=domain.slot, option=domain.options[0])
                for d in request.days
                for domain in d.domains
            ),
        )
    )


def numeric(
    name: str, attribute: str, value: int, operator: PredicateOperator = PredicateOperator.EQ
) -> RuleDefinition:
    return rule(
        name,
        attribute=attribute,
        required_facts=(attribute,),
        value=value,
        operator=operator,
        unit=MeasurementUnit.MG
        if attribute == "synthetic_week_quantity_total"
        else MeasurementUnit.DIMENSIONLESS,
    )


def case(
    *,
    week_rules: tuple[RuleDefinition, ...] | None = None,
    day_rules: tuple[RuleDefinition, ...] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    checks = (
        rule(
            "recipe",
            scope=RuleScope.RECIPE,
            attribute="synthetic_flag",
            required_facts=("synthetic_flag",),
        ),
        rule(
            "combination",
            scope=RuleScope.COMBINATION,
            attribute="synthetic_combination_roles_compatible",
            required_facts=("synthetic_combination_roles_compatible",),
        ),
        *(
            day_rules
            if day_rules is not None
            else (
                rule(
                    "day",
                    scope=RuleScope.DAY,
                    attribute="synthetic_day_complete",
                    required_facts=("synthetic_day_complete",),
                ),
            )
        ),
        *(
            week_rules
            if week_rules is not None
            else (
                rule("week-complete"),
                numeric("week-quantity", "synthetic_week_quantity_total", 42),
                numeric("week-repetition", "synthetic_week_max_recipe_slot_occurrences", 21),
            )
        ),
    )
    return packet(checks=checks, **kwargs)


def solve(data: dict[str, Any], **kwargs: Any) -> WeeklyTrialEvaluation:
    args = dict(
        request=data["request"],
        trial=trial(data["request"]),
        candidates=(data["candidate"],),
        knowledge=data["kb"],
        context=data["context"],
        sources=data["source"],
    )
    args.update(kwargs)
    return evaluate_weekly_trial(**args)


def rebind(
    data: dict[str, Any], *, context: Any = None, kb: Any = None, options: Any = None
) -> dict[str, Any]:
    changed = dict(data)
    context = data["context"] if context is None else context
    kb = data["kb"] if kb is None else kb
    source_options = []
    for option in data["daily"].options if options is None else options:
        combo = revise(
            option.combination, context_digest=context.content_digest, kb_digest=kb.content_digest
        )
        ref = option.reference.model_copy(update={"combination_digest": combo.content_digest})
        suitability = (
            None
            if option.suitability is None
            else option.suitability.model_copy(update={"option": ref})
        )
        measurements = tuple(m.model_copy(update={"option": ref}) for m in option.measurements)
        source_options.append(
            DailyMealOption(
                reference=ref, combination=combo, suitability=suitability, measurements=measurements
            )
        )
    daily = revise(data["daily"], context=context, options=tuple(source_options))
    daily_ref = DailySourceReference(
        source_id=daily.source_id, version=daily.version, content_digest=daily.content_digest
    )
    source = revise(data["source"], daily_source=daily, expected_daily_source=daily_ref)
    source_ref = WeeklySourceReference(
        source_id=source.source_id, version=source.version, content_digest=source.content_digest
    )
    refs = {o.reference.option_id: o.reference for o in daily.options}
    days = tuple(
        WeeklyDayDomain(
            day=d.day,
            domains=tuple(
                DailySlotDomain(
                    slot=domain.slot, options=tuple(refs[r.option_id] for r in domain.options)
                )
                for domain in d.domains
            ),
        )
        for d in data["request"].days
    )
    request = revise(
        data["request"],
        context_digest=context.content_digest,
        source=source,
        expected_source=source_ref,
        days=days,
    )
    changed.update(kb=kb, context=context, daily=daily, source=source, request=request)
    return changed


def amounts(data: dict[str, Any], value: int | None, *, complete: bool = True) -> dict[str, Any]:
    options = tuple(
        o.model_copy(
            update={
                "measurements": tuple(
                    m.model_copy(
                        update={"value": value, "complete": complete and value is not None}
                    )
                    for m in o.measurements
                )
            }
        )
        for o in data["daily"].options
    )
    return rebind(data, options=options)


def test_complete_trial_quantity_occurrences_and_daily_trial_bindings() -> None:
    result = solve(case(copies=2))
    assert result.status is RuleStatus.PASS and result.week_status is RuleStatus.PASS
    assert [f.observation.value for f in result.facts] == [True, 42, 21]
    assert len(result.days) == 7 and len(result.facts[1].contributions) == 21
    assert all(d.evaluation.status is RuleStatus.PASS for d in result.days)
    assert all(
        d.evaluation.facts[0].assignment_digest == d.evaluation.trial.content_digest
        for d in result.days
    )
    assert (
        result.plan_feasibility == "NOT_EVALUATED" and result.search_completeness == "NOT_EVALUATED"
    )
    assert [e.rule.rule_id for e in result.trace.evaluations] == [
        "week-complete",
        "week-quantity",
        "week-repetition",
    ]
    assert all(r.recipe_ids == ("week-recipe",) for r in result.facts[2].occurrences)
    ids = {e.evidence_id for e in result.facts[1].observation.evidence}
    assert {
        "synthetic-week-derivation",
        "synthetic-day-derivation",
        "measure-0",
        "portion-0",
    } <= ids


@pytest.mark.parametrize(
    "operator,expected",
    [
        (PredicateOperator.LT, False),
        (PredicateOperator.LE, True),
        (PredicateOperator.GT, False),
        (PredicateOperator.GE, True),
        (PredicateOperator.EQ, True),
        (PredicateOperator.NE, False),
    ],
)
@pytest.mark.parametrize(
    "attribute,value",
    [("synthetic_week_quantity_total", 42), ("synthetic_week_max_recipe_slot_occurrences", 21)],
)
def test_literal_integer_comparison_boundaries(
    operator: PredicateOperator, expected: bool, attribute: str, value: int
) -> None:
    result = solve(case(week_rules=(numeric("numeric", attribute, value, operator),)))
    assert result.trace.evaluations[0].status is (RuleStatus.PASS if expected else RuleStatus.FAIL)
    assert result.week_status is (RuleStatus.PASS if expected else RuleStatus.FAIL)


@pytest.mark.parametrize(
    "operator,value,expected",
    [
        (PredicateOperator.EQ, True, "PASS"),
        (PredicateOperator.EQ, False, "FAIL"),
        (PredicateOperator.NE, False, "PASS"),
        (PredicateOperator.NE, True, "FAIL"),
    ],
)
def test_literal_boolean_comparisons(
    operator: PredicateOperator, value: bool, expected: str
) -> None:
    result = solve(case(week_rules=(rule(operator=operator, value=value),)))
    assert result.week_status.value == expected


@pytest.mark.parametrize(
    "measurement,total",
    [
        (0, 0),
        (2**53 + 1, 189151184349560853),
        (1_000_000_000_000_000_000, 21_000_000_000_000_000_000),
        (3_074_457_345_618_258_602, 64_563_604_257_983_430_642),
    ],
)
def test_exact_integer_totals(measurement: int, total: int) -> None:
    result = solve(
        amounts(
            case(week_rules=(numeric("quantity", "synthetic_week_quantity_total", total),)),
            measurement,
        )
    )
    assert (
        result.facts[1].observation.value == total
        and type(result.facts[1].observation.value) is int
    )
    assert result.status is RuleStatus.PASS


@pytest.mark.parametrize("value,complete", [(None, False), (2, False)])
def test_missing_and_incomplete_quantity(value: int | None, complete: bool) -> None:
    result = solve(amounts(case(), value, complete=complete))
    assert result.facts[1].observation.value is None
    assert result.facts[1].observation.complete is False
    assert result.week_status is RuleStatus.UNKNOWN and result.status is RuleStatus.UNKNOWN


@pytest.mark.parametrize("unknown_day_rule", [False, True])
def test_week_failure_refutes_day_unknown_and_all_rules_execute(unknown_day_rule: bool) -> None:
    days = (
        rule(
            "day",
            scope=RuleScope.DAY,
            attribute="synthetic_day_complete",
            required_facts=("synthetic_day_complete", "synthetic_profile_flag"),
        ),
    )
    data = case(
        suitability=unknown_day_rule,
        day_rules=days if unknown_day_rule else None,
        week_rules=(rule("a-complete"), numeric("b-quantity", "synthetic_week_quantity_total", 0)),
    )
    result = solve(data)
    assert all(d.evaluation.status is RuleStatus.UNKNOWN for d in result.days)
    assert [e.status for e in result.trace.evaluations] == [RuleStatus.UNKNOWN, RuleStatus.FAIL]
    assert result.status is RuleStatus.FAIL and result.facts[0].observation.value is None
    assert len(result.explanations) == 2


def test_day_fail_and_unknown_and_empty_week_coverage() -> None:
    failed = solve(
        case(
            day_rules=(
                rule(
                    "day",
                    scope=RuleScope.DAY,
                    attribute="synthetic_day_complete",
                    required_facts=("synthetic_day_complete",),
                    value=False,
                ),
            )
        )
    )
    assert all(d.evaluation.status is RuleStatus.FAIL for d in failed.days)
    assert failed.status is RuleStatus.FAIL and failed.facts[0].observation.value is None
    unknown = solve(case(day_rules=()))
    assert all(d.evaluation.status is RuleStatus.UNKNOWN for d in unknown.days)
    assert unknown.status is RuleStatus.UNKNOWN
    empty = solve(case(week_rules=()))
    assert empty.trace.evaluations == () and empty.week_status is RuleStatus.UNKNOWN
    assert empty.status is RuleStatus.UNKNOWN


def test_missing_candidate_identity_makes_occurrences_unknown() -> None:
    result = solve(case(), candidates=())
    assert result.facts[2].observation.value is None
    assert result.facts[1].observation.value == 42
    assert result.status is RuleStatus.UNKNOWN


def test_fixed_configuration_repetition_counts_same_recipe() -> None:
    data = case()
    t = trial(data["request"])
    choices = tuple(
        c.model_copy(update={"option": data["daily"].options[1].reference})
        if c.day.day_index == 7 and c.slot is MealSlot.DINNER
        else c
        for c in t.choices
    )
    t = revise(t, choices=choices)
    result = solve(data, trial=t)
    assert result.facts[1].observation.value == 45
    assert result.facts[2].observation.value == 21
    assert result.week_status is RuleStatus.FAIL


@pytest.fixture(scope="module")
def evaluated() -> WeeklyTrialEvaluation:
    return solve(case())


@pytest.mark.parametrize("enabled,expected", [(False, "PASS"), (None, "UNKNOWN")])
def test_evidenced_not_applicable_and_unknown(enabled: bool | None, expected: str) -> None:
    data = case()
    original = data["context"].facts[0]
    context = revise(
        data["context"],
        facts=(
            original.model_copy(
                update={
                    "observation": original.observation.model_copy(
                        update={"value": enabled, "complete": enabled is not None}
                    )
                }
            ),
        ),
    )
    result = solve(rebind(data, context=context))
    assert result.week_status.value == expected and result.status.value == expected
    assert all(e.status is RuleStatus.UNKNOWN for e in result.trace.evaluations)
    assert all(
        e.applicability.value == ("NOT_APPLICABLE" if enabled is False else "UNKNOWN")
        for e in result.trace.evaluations
    )


@pytest.mark.parametrize("guard", [None, True, False])
def test_unknown_dependency_dominates_false_local_applicability(guard: bool | None) -> None:
    data = case()
    kb = data["kb"]
    own = kb.applicability_descriptors[0]
    dependency = RuleReference(rule_id="synthetic-context-guard", version="1")
    dep = ApplicabilityDescriptor(
        reference=dependency,
        rule_references=(),
        required_context_facts=("synthetic_context_guard",),
        evidence=(evidence("dependency"),),
    )
    kb = build_knowledge_snapshot(
        kb.model_dump(exclude={"content_digest"})
        | {
            "applicability_descriptors": (
                own.model_copy(update={"dependencies": (dependency,)}),
                dep,
            )
        }
    )
    context = data["context"]
    original = context.facts[0]
    false = original.model_copy(
        update={"observation": original.observation.model_copy(update={"value": False})}
    )
    guard_fact = VersionedFact(
        fact_id="synthetic_context_guard",
        version="1",
        subject_kind=FactSubjectKind.CONTEXT,
        subject_id=context.context_id,
        subject_version=context.version,
        context_id=context.context_id,
        context_version=context.version,
        observation=FactObservation(
            fact_id="synthetic_context_guard",
            value=guard,
            complete=guard is not None,
            evidence=(evidence("guard"),),
        ),
    )
    context = revise(context, expected_kb_digest=kb.content_digest, facts=(false, guard_fact))
    result = solve(rebind(data, kb=kb, context=context))
    assert result.week_status is (RuleStatus.UNKNOWN if guard is None else RuleStatus.PASS)
    assert all(
        e.applicability.value == ("UNKNOWN" if guard is None else "NOT_APPLICABLE")
        for e in result.trace.evaluations
    )


def test_authoritative_manifest_and_deferred_transition(evaluated: WeeklyTrialEvaluation) -> None:
    data = case()
    manifest = build_week_check_manifest(
        data["request"], knowledge=data["kb"], context=data["context"], sources=data["source"]
    )
    assert manifest.required_checks == evaluated.trace.required_checks
    assert all(
        tuple(r for r in o.combination.deferred_checks if r.scope is RuleScope.WEEK)
        == manifest.required_checks
        for o in evaluated.options
    )
    assert tuple(e.rule for e in evaluated.trace.evaluations) == manifest.required_checks
    assert all(d.evaluation.trace.required_checks == manifest.day_checks for d in evaluated.days)
    assert len(evaluated.explanations) == 3
    for field in ("required_checks", "day_checks"):
        with pytest.raises(ValidationError):
            forged = manifest.model_copy(update={field: ()})
            evaluate_weekly_trial(
                data["request"],
                trial(data["request"]),
                candidates=(data["candidate"],),
                knowledge=data["kb"],
                context=data["context"],
                sources=data["source"],
                manifest=forged,
            )


@pytest.mark.parametrize("field", ["knowledge", "context", "sources"])
def test_independent_authority_transplants(field: str) -> None:
    data = case()
    foreign = case(week_rules=(rule("foreign-week"),))
    aliases = {"knowledge": "kb", "context": "context", "sources": "source"}
    with pytest.raises(ValidationError):
        solve(data, **{field: foreign[aliases[field]]})


def test_legacy_week_and_unapproved_even_behind_false_applicability() -> None:
    with pytest.raises(ValidationError):
        case(week_rules=(rule(attribute="synthetic_flag", required_facts=("synthetic_flag",)),))
    data = case()
    checks = tuple(
        r.model_copy(
            update={
                "approval_status": ApprovalStatus.PENDING,
                "approved_by": None,
                "approval_reference": None,
            }
        )
        if r.scope is RuleScope.WEEK
        else r
        for r in data["kb"].rules
    )
    kb = build_knowledge_snapshot(
        data["kb"].model_dump(exclude={"content_digest"}) | {"rules": checks}
    )
    original = data["context"].facts[0]
    context = revise(
        data["context"],
        expected_kb_digest=kb.content_digest,
        facts=(
            original.model_copy(
                update={"observation": original.observation.model_copy(update={"value": False})}
            ),
        ),
    )
    with pytest.raises(ValidationError):
        solve(rebind(data, kb=kb, context=context))


@pytest.mark.parametrize(
    "path,value",
    [
        (("status",), "FAIL"),
        (("weekStatus",), "UNKNOWN"),
        (("facts", 1, "observation", "value"), 43),
        (("facts", 2, "observation", "value"), 20),
        (("facts", 0, "observation", "value"), False),
        (("facts", 1, "trialDigest"), "f" * 64),
        (("days", 0, "evaluation", "status"), "FAIL"),
        (("days", 0, "evaluation", "facts", 0, "assignmentDigest"), "f" * 64),
        (("trace", "evaluations", 0, "status"), "FAIL"),
        (("explanations", 0, "trialDigest"), "f" * 64),
        (("trace", "evaluations"), []),
        (("days",), []),
        (("options",), []),
        (("planFeasibility",), "FEASIBLE"),
        (("searchCompleteness",), "EXHAUSTIVE"),
    ],
)
def test_tampered_computed_proofs(
    evaluated: WeeklyTrialEvaluation, path: tuple[Any, ...], value: Any
) -> None:
    payload = deepcopy(evaluated.model_dump(mode="json", by_alias=True))
    parent = payload
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    with pytest.raises(ValidationError):
        validate_contract_json(WeeklyTrialEvaluation, json.dumps(payload))


def test_original_json_roundtrip_and_nested_duplicates(evaluated: WeeklyTrialEvaluation) -> None:
    raw = evaluated.model_dump_json(by_alias=True)
    assert len(raw.encode()) < 1_048_576
    assert validate_contract_json(WeeklyTrialEvaluation, raw) == evaluated
    for old, new in [
        ('"dayIndex":1', '"dayIndex":1,"dayIndex":2'),
        ('"weekStatus":"PASS"', '"weekStatus":"PASS","week_status":"PASS"'),
    ]:
        assert old in raw
        with pytest.raises(ValidationError):
            validate_contract_json(WeeklyTrialEvaluation, raw.replace(old, new, 1))


@pytest.mark.parametrize("enum_type", [RuleStatus, MealSlot, RuleScope])
def test_counterfeit_and_unchecked_inputs(enum_type: type[StrEnum]) -> None:
    data = case()
    value = next(iter(enum_type))
    forged = str.__new__(enum_type, value.value)
    object.__setattr__(forged, "_name_", value.name)
    object.__setattr__(forged, "_value_", value.value)
    if enum_type is MealSlot:
        t = trial(data["request"])
        with pytest.raises(ValidationError):
            solve(
                data,
                trial=t.model_copy(
                    update={
                        "choices": (
                            t.choices[0].model_copy(update={"slot": forged}),
                            *t.choices[1:],
                        )
                    }
                ),
            )
    elif enum_type is RuleScope:
        with pytest.raises(ValidationError):
            case(week_rules=(rule().model_copy(update={"scope": forged}),))
    else:
        result = solve(data)
        with pytest.raises(ValidationError):
            WeeklyTrialEvaluation.model_validate(result.model_copy(update={"status": forged}))


def test_hostile_containers_and_malformed_models(evaluated: WeeklyTrialEvaluation) -> None:
    class HostileTuple(tuple):
        def __iter__(self):
            raise AssertionError("must not iterate hostile tuple")

    class HostileDict(dict):
        def items(self):
            raise AssertionError("must not inspect hostile mapping")

    data = case()
    with pytest.raises(ValidationError):
        solve(data, candidates=HostileTuple((data["candidate"],)))
    with pytest.raises(ValidationError):
        WeeklyTrialEvaluation.model_validate(HostileDict(evaluated.model_dump()))
    for changes in (
        {"extra": True},
        {"candidates": list(evaluated.candidates)},
        {"trial": WeeklyTrial.model_construct(request_digest="bad")},
        {"days": HostileTuple(evaluated.days)},
    ):
        with pytest.raises(ValidationError):
            WeeklyTrialEvaluation.model_validate(evaluated.model_copy(update=changes))


def test_contradictory_evidence_and_wrong_configuration() -> None:
    data = case()
    with pytest.raises(ValidationError):
        bad = revise(data["source"], evidence=(evidence(source="Conflicting same-version source"),))
        solve(data, sources=bad)
    t = trial(data["request"])
    ref = t.choices[0].option.model_copy(update={"portion_configuration_id": "foreign"})
    with pytest.raises(ValidationError):
        solve(
            data,
            trial=revise(
                t, choices=(t.choices[0].model_copy(update={"option": ref}), *t.choices[1:])
            ),
        )


def test_public_preparation_counts_and_no_global_pass_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import savora_ai.core.reasoning.combinations as combo_module
    import savora_ai.core.reasoning.week_checks as week_module

    counts = {"recipe": 0, "combination": 0}
    from savora_ai.core.reasoning.combinations import evaluate_combination as original_combo
    from savora_ai.core.reasoning.filtering import filter_candidates as original_filter

    def recipe(*args: Any, **kwargs: Any) -> Any:
        counts["recipe"] += 1
        return original_filter(*args, **kwargs)

    def combination(*args: Any, **kwargs: Any) -> Any:
        counts["combination"] += 1
        return original_combo(*args, **kwargs)

    monkeypatch.setattr(week_module, "filter_candidates", recipe)
    monkeypatch.setattr(combo_module, "filter_candidates", recipe)
    monkeypatch.setattr(week_module, "evaluate_combination", combination)
    data = case()
    solve(data)
    # One distinct selected option across 21 slots and three WEEK predicates.
    # Initial preparation and computed-output verification each make one pass.
    assert counts == {"recipe": 4, "combination": 2}
    solve(data)
    assert counts == {"recipe": 8, "combination": 4}


def test_incomplete_composition_keeps_recipe_presence_unknown() -> None:
    data = case()
    options = tuple(
        o.model_copy(
            update={
                "combination": revise(
                    o.combination,
                    composition_complete=False,
                    composition_gap_reasons=(CompositionGapReason.INCOMPLETE_COMPOSITION,),
                )
            }
        )
        for o in data["daily"].options
    )
    result = solve(rebind(data, options=options))
    assert result.facts[2].observation.value is None
    assert result.facts[1].observation.value == 42
    assert result.status is RuleStatus.UNKNOWN


def test_unassigned_trial_never_manufactures_portions_or_complete_week() -> None:
    result = solve(case(fixed=False))
    assert result.facts[0].observation.value is None
    assert result.facts[1].observation.value is None
    assert result.status is RuleStatus.UNKNOWN
    assert result.plan_feasibility == "NOT_EVALUATED"
