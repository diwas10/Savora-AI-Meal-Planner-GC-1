"""Independent fictional WEEK contracts; no clinical or provider approval."""

import hashlib
import json
from datetime import date, timedelta
from enum import StrEnum
from typing import Any

import pytest
from pydantic import ValidationError

from savora_ai.core.reasoning.combinations import evaluate_combination
from savora_ai.core.reasoning.daily import build_day_check_manifest, solve_daily_plan
from savora_ai.core.reasoning.filtering import filter_candidates
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.manifest import build_expected_check_manifest
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
    AssignedMeal,
    DailyAssignment,
    DailyMealOption,
    DailyOutcome,
    DailySlotDomain,
    DailySourceReference,
    DailySourceSnapshot,
    FixedMealMeasurement,
    MealOptionReference,
    MealSlot,
    MealSlotSuitability,
)
from savora_ai.schemas.daily_solver import DailyTrial, DailyTrialChoice
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
    KnowledgeWorkflow,
    RuleCatalogueCoverage,
)
from savora_ai.schemas.reasoning import FactObservation, RuleStatus
from savora_ai.schemas.weekly import (
    ExpectedWeekCheckManifest,
    WeekDayReference,
    WeekFact,
    WeeklyAssignment,
    WeeklyConstraintDiagnostic,
    WeeklyDayAssignment,
    WeeklyDayDomain,
    WeeklyFrontierChoice,
    WeeklyPlanningRequest,
    WeeklySearchLimits,
    WeeklySearchState,
    WeeklySolveResult,
    WeeklySourceReference,
    WeeklySourceSnapshot,
    WeeklyTrial,
    WeeklyTrialChoice,
    WeekMeasurementContribution,
    WeekRecipeOccurrence,
    _daily_request,
)


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


def test_week_owned_rule_admitted_and_deferred() -> None:
    kb, candidate, context = foundation((rule(),))
    assert kb.rules[0].scope is RuleScope.WEEK
    manifest = build_expected_check_manifest(kb, candidate, context)
    assert manifest.attribute_policy_version == "synthetic-attributes.v5-week"
    assert manifest.required_checks == ()
    assert manifest.deferred_checks == kb.rules


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


@pytest.fixture(scope="module")
def frame() -> dict[str, Any]:
    return packet()


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


def assignment(request: WeeklyPlanningRequest) -> WeeklyAssignment:
    days = []
    for d in request.days:
        daily = _daily_request(request, d)
        choices = tuple(
            DailyTrialChoice(
                slot=slot,
                option=next(domain.options[0] for domain in d.domains if domain.slot is slot),
            )
            for slot in MealSlot
        )
        t = DailyTrial.build(dict(request_digest=daily.content_digest, choices=choices))
        a = DailyAssignment.build(
            dict(
                request_digest=daily.content_digest,
                day_id=d.day.day_id,
                source=request.source.expected_daily_source,
                context_digest=request.context_digest,
                slots=tuple(AssignedMeal(slot=c.slot, option=c.option) for c in choices),
            )
        )
        days.append(WeeklyDayAssignment(day=d.day, trial=t, assignment=a))
    return WeeklyAssignment.build(
        dict(
            request_digest=request.content_digest,
            week_id=request.week_id,
            week_version=request.week_version,
            start_date=request.start_date,
            source=request.expected_source,
            daily_source=request.source.expected_daily_source,
            context_digest=request.context_digest,
            days=tuple(days),
        )
    )


def fact(frame: dict[str, Any], name: str = "synthetic_week_complete") -> WeekFact:
    request = frame["request"]
    t = trial(request)
    options = {o.reference.option_id: o for o in frame["daily"].options}
    numeric = name != "synthetic_week_complete"
    quantity = name == "synthetic_week_quantity_total"
    return WeekFact(
        request_digest=request.content_digest,
        trial_digest=t.content_digest,
        week_id=request.week_id,
        week_version=request.week_version,
        source=request.expected_source,
        context_digest=request.context_digest,
        observation=FactObservation(
            fact_id=name,
            value=42 if quantity else 21 if numeric else True,
            complete=True,
            unit=MeasurementUnit.MG
            if quantity
            else MeasurementUnit.DIMENSIONLESS
            if numeric
            else None,
            evidence=(evidence(),),
        ),
        measurement_basis="WEEK_FIXED_TOTAL" if quantity else None,
        basis_reference=evidence("week-basis") if numeric else None,
        contributions=tuple(
            WeekMeasurementContribution(
                day=c.day,
                slot=c.slot,
                option=c.option,
                measurement_source=options[c.option.option_id].measurements[0].source,
                measurement_digest=digest(options[c.option.option_id].measurements[0]),
            )
            for c in t.choices
        )
        if quantity
        else (),
        occurrences=tuple(
            WeekRecipeOccurrence(
                day=c.day, slot=c.slot, option=c.option, recipe_ids=("week-recipe",)
            )
            for c in t.choices
        )
        if numeric and not quantity
        else (),
    )


def test_valid_weekly_request_and_unevaluated_result(frame: dict[str, Any]) -> None:
    request = frame["request"]
    assert [d.day.day_index for d in request.days] == list(range(1, 8))
    assert [d.day.calendar_date for d in request.days] == [f"2026-10-{i}" for i in range(19, 26)]
    assert sum(len(d.domains) for d in request.days) == 21
    result = WeeklySolveResult(
        manifest=frame["manifest"],
        assignment=assignment(request),
        trial=trial(request),
        facts=tuple(
            fact(frame, n)
            for n in (
                "synthetic_week_complete",
                "synthetic_week_quantity_total",
                "synthetic_week_max_recipe_slot_occurrences",
            )
        ),
    )
    assert result.outcome is None and result.weekly_feasibility == "NOT_EVALUATED"
    assert validate_contract_json(WeeklySolveResult, result.model_dump_json()) == result


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "extra", "gap", "index", "foreign", "day-id"]
)
def test_invalid_days(frame: dict[str, Any], change: str) -> None:
    request = frame["request"]
    days = list(request.days)
    if change == "missing":
        days.pop()
    elif change == "extra":
        days.append(days[-1])
    elif change == "duplicate":
        days[-1] = days[0]
    else:
        changes = {
            "gap": {"calendar_date": "2026-10-27"},
            "index": {"day_index": 6},
            "foreign": {"week_id": "foreign"},
            "day-id": {"day_id": days[0].day.day_id},
        }[change]
        days[-1] = days[-1].model_copy(update={"day": days[-1].day.model_copy(update=changes)})
    with pytest.raises(ValidationError):
        revise(request, days=tuple(days))


@pytest.mark.parametrize("change", ["missing", "duplicate", "extra"])
def test_invalid_slots(frame: dict[str, Any], change: str) -> None:
    day = frame["request"].days[0]
    domains = (
        day.domains[:-1]
        if change == "missing"
        else (*day.domains, day.domains[0])
        if change == "extra"
        else (day.domains[0],) * 3
    )
    with pytest.raises(ValidationError):
        WeeklyDayDomain(day=day.day, domains=domains)


@pytest.mark.parametrize(
    "field,value",
    [
        ("day_index", 0),
        ("day_index", 8),
        ("day_index", True),
        ("day_index", 1.0),
        ("calendar_date", "2026-02-30"),
        ("calendar_date", "2026-1-01"),
        ("calendar_date", "2026-10-19T00:00:00"),
        ("calendar_date", date(2026, 10, 19)),
    ],
)
def test_strict_calendar(frame: dict[str, Any], field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        WeekDayReference.model_validate(
            frame["request"].days[0].day.model_copy(update={field: value})
        )


@pytest.mark.parametrize(
    "name,unit,maximum",
    [
        ("synthetic_week_quantity_total", MeasurementUnit.MG, 64_563_604_257_983_430_642),
        ("synthetic_week_max_recipe_slot_occurrences", MeasurementUnit.DIMENSIONLESS, 21),
    ],
)
@pytest.mark.parametrize(
    "operator",
    [
        PredicateOperator.LT,
        PredicateOperator.LE,
        PredicateOperator.GT,
        PredicateOperator.GE,
        PredicateOperator.EQ,
        PredicateOperator.NE,
    ],
)
@pytest.mark.parametrize("upper", [False, True])
def test_numeric_week_admission(
    name: str, unit: MeasurementUnit, maximum: int, operator: PredicateOperator, upper: bool
) -> None:
    r = rule(
        attribute=name,
        required_facts=(name,),
        unit=unit,
        operator=operator,
        value=maximum if upper else 0,
    )
    kb, candidate, context = foundation((r,))
    assert build_expected_check_manifest(kb, candidate, context).deferred_checks == (r,)


@pytest.mark.parametrize(
    "changes",
    [
        {"scope": RuleScope.RECIPE},
        {"scope": RuleScope.COMBINATION},
        {"scope": RuleScope.DAY},
        {"domain": RuleDomain.CLINICAL},
        {"unit": MeasurementUnit.DIMENSIONLESS},
        {"operator": PredicateOperator.GT},
        {"value": 1},
        {"required_facts": ("synthetic_week_complete", "synthetic_flag")},
        {"required_facts": ("synthetic_week_complete", "synthetic_day_complete")},
        {"required_facts": ("synthetic_week_complete", "synthetic_combination_roles_compatible")},
        {"required_facts": ("synthetic_week_complete", "unknown")},
        {
            "approval_status": ApprovalStatus.PENDING,
            "approved_by": None,
            "approval_reference": None,
        },
    ],
)
def test_invalid_week_admission(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        kb, candidate, context = foundation((rule(**changes),))
        build_expected_check_manifest(kb, candidate, context)


@pytest.mark.parametrize(
    "value", [-1, 64_563_604_257_983_430_643, True, False, 0.0, "0", float("inf"), 10**100]
)
def test_invalid_numeric_threshold(value: Any) -> None:
    with pytest.raises(ValidationError):
        kb, candidate, context = foundation(
            (
                rule(
                    attribute="synthetic_week_quantity_total",
                    required_facts=("synthetic_week_quantity_total",),
                    unit=MeasurementUnit.MG,
                    value=value,
                ),
            )
        )
        build_expected_check_manifest(kb, candidate, context)


@pytest.mark.parametrize("lifecycle", [RuleLifecycle.DRAFT, RuleLifecycle.RETIRED])
def test_inactive_week_not_mandatory(lifecycle: RuleLifecycle) -> None:
    kb, candidate, context = foundation((rule(lifecycle=lifecycle),))
    assert build_expected_check_manifest(kb, candidate, context).deferred_checks == ()
    cells = tuple(
        c.model_copy(update={"rule_references": (RuleReference(rule_id="week", version="1"),)})
        if c.scope is RuleScope.WEEK
        else c
        for c in kb.check_catalogue
    )
    with pytest.raises(ValidationError):
        build_knowledge_snapshot(
            kb.model_dump(exclude={"content_digest"}) | {"check_catalogue": cells}
        )


@pytest.mark.parametrize(
    "token",
    [
        "synthetic-attributes.v1",
        "synthetic-attributes.v2",
        "synthetic-attributes.v3-combination",
        "synthetic-attributes.v4-day",
        "unknown",
    ],
)
def test_upstream_policy_downgrade_rejected(frame: dict[str, Any], token: str) -> None:
    m = build_expected_check_manifest(frame["kb"], frame["candidate"], frame["context"])
    data = m.model_copy(update={"attribute_policy_version": token})
    h = digest(data, excludes={"manifest_id", "manifest_version", "content_digest"})
    with pytest.raises(ValidationError):
        ExpectedCheckManifest.model_validate(
            data.model_dump()
            | {
                "content_digest": h,
                "manifest_id": "manifest-" + h,
                "manifest_version": "synthetic-manifest.v1:" + h,
            }
        )


@pytest.mark.parametrize("field", ["required_checks", "day_checks"])
def test_reduced_week_manifest(frame: dict[str, Any], field: str) -> None:
    with pytest.raises(ValidationError):
        revise(frame["manifest"], **{field: ()})


@pytest.mark.parametrize("token", [None, False, "unknown", "synthetic-week-policy.v2"])
def test_week_policy_version(frame: dict[str, Any], token: Any) -> None:
    with pytest.raises(ValidationError):
        revise(frame["request"], week_policy_version=token)
    with pytest.raises(ValidationError):
        revise(frame["manifest"], week_policy_version=token)


@pytest.mark.parametrize("field", ["context_id", "context_version", "context_digest"])
def test_wrong_context_pin(frame: dict[str, Any], field: str) -> None:
    with pytest.raises(ValidationError):
        revise(frame["request"], **{field: "f" * 64})


@pytest.mark.parametrize("field", ["source_id", "version", "content_digest"])
def test_wrong_source_pin(frame: dict[str, Any], field: str) -> None:
    source = frame["request"].expected_source.model_copy(update={field: "f" * 64})
    with pytest.raises(ValidationError):
        revise(frame["request"], expected_source=source)


@pytest.mark.parametrize(
    "field",
    [
        "kb_id",
        "version",
        "graph_version",
        "catalogue_version",
        "check_catalogue_version",
        "taxonomy_version",
        "content_digest",
    ],
)
def test_wrong_kb_pin(frame: dict[str, Any], field: str) -> None:
    with pytest.raises(ValidationError):
        revise(frame["manifest"], knowledge=frame["kb"].model_copy(update={field: "f" * 64}))


@pytest.mark.parametrize(
    "field",
    [
        "combination_digest",
        "snapshot_id",
        "portion_configuration_id",
        "portion_configuration_version",
    ],
)
def test_domain_option_identity(frame: dict[str, Any], field: str) -> None:
    request = frame["request"]
    day = request.days[0]
    domain = day.domains[0]
    wrong = domain.options[0].model_copy(update={field: "f" * 64})
    changed = day.model_copy(
        update={"domains": (domain.model_copy(update={"options": (wrong,)}), *day.domains[1:])}
    )
    with pytest.raises(ValidationError):
        revise(request, days=(changed, *request.days[1:]))


def test_unassigned_and_missing_suitability_remain_unevaluated() -> None:
    data = packet(fixed=False, suitability=False)
    result = WeeklySolveResult(manifest=data["manifest"], trial=trial(data["request"]))
    assert result.outcome is None
    with pytest.raises(ValidationError):
        assignment(data["request"])


def test_missing_suitability_evidence_and_wrong_measurement_basis(frame: dict[str, Any]) -> None:
    option = frame["daily"].options[0]
    for changes in (
        {"suitability": option.suitability.model_copy(update={"evidence": ()})},
        {
            "measurements": (
                option.measurements[0].model_copy(
                    update={"measurement_basis": CombinationMeasurementBasis.AS_RECORDED}
                ),
            )
        },
    ):
        daily = frame["daily"].model_copy(update={"options": (option.model_copy(update=changes),)})
        with pytest.raises(ValidationError):
            revise(frame["source"], daily_source=daily)
    with pytest.raises(ValidationError):
        revise(frame["source"], evidence=())


def test_cross_day_repeated_recipe_and_component_occurrences() -> None:
    data = packet(copies=2)
    result = WeeklySolveResult(
        manifest=data["manifest"],
        trial=trial(data["request"]),
        facts=(fact(data, "synthetic_week_max_recipe_slot_occurrences"),),
    )
    assert len(result.facts[0].occurrences) == 21
    assert all(r.recipe_ids == ("week-recipe",) for r in result.facts[0].occurrences)
    assert (
        data["daily"].options[0].combination.components[0].recipe_snapshot
        == data["daily"].options[1].combination.components[0].recipe_snapshot
    )
    occurrence = result.facts[0].occurrences[0]
    with pytest.raises(ValidationError):
        WeekRecipeOccurrence.model_validate(
            occurrence.model_copy(update={"recipe_ids": ("week-recipe",) * 2})
        )


@pytest.mark.parametrize("outcome", list(DailyOutcome))
def test_prompt_one_never_authorizes_outcomes(frame: dict[str, Any], outcome: DailyOutcome) -> None:
    with pytest.raises(ValidationError):
        WeeklySolveResult(manifest=frame["manifest"], outcome=outcome)


def test_daily_trial_digest_is_not_assignment_digest(frame: dict[str, Any]) -> None:
    a = assignment(frame["request"])
    day = a.days[0]
    assert day.trial.content_digest != day.assignment.content_digest
    forged = revise(day.trial, request_digest=day.assignment.content_digest)
    with pytest.raises(ValidationError):
        WeeklyDayAssignment(day=day.day, trial=forged, assignment=day.assignment)
    forged_day = WeeklyDayAssignment(
        day=day.day,
        trial=forged,
        assignment=revise(day.assignment, request_digest=day.assignment.content_digest),
    )
    with pytest.raises(ValidationError):
        WeeklySolveResult(
            manifest=frame["manifest"], assignment=revise(a, days=(forged_day, *a.days[1:]))
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"exhaustive": True},
        {"exhaustive": 1},
        {"phase": "NOT_STARTED", "nodes": 1},
        {"phase": "INTERRUPTED"},
        {"phase": "SEARCHING", "exhaustion_reason": "NODE_BUDGET"},
    ],
)
def test_unverified_search_never_proves_exhaustion(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        WeeklySearchState(**changes)


@pytest.mark.parametrize(
    "field",
    [
        "max_nodes",
        "max_option_evaluations",
        "max_day_evaluations",
        "max_week_evaluations",
        "max_predicate_evaluations",
        "max_cache_entries",
        "max_diagnostics",
        "max_proof_records",
        "max_proof_bytes",
    ],
)
def test_resource_limits_strict_and_zero(field: str) -> None:
    assert getattr(WeeklySearchLimits.model_validate({field: 0}), field) == 0
    for value in (-1, True, 1.0, 10**100):
        with pytest.raises(ValidationError):
            WeeklySearchLimits.model_validate({field: value})


def test_frontier_and_progress_declarations(frame: dict[str, Any]) -> None:
    first = trial(frame["request"]).choices[0]
    choice = WeeklyFrontierChoice.model_validate(first.model_dump())
    state = WeeklySearchState(
        phase="INTERRUPTED",
        frontier=(choice,),
        next_option_indexes=(1,),
        exhaustion_reason="PROOF_BYTE_BUDGET",
    )
    assert state.coverage == "NOT_VERIFIED" and not state.exhaustive
    with pytest.raises(ValidationError):
        WeeklySolveResult(manifest=frame["manifest"], search=state)
    with pytest.raises(ValidationError):
        WeeklySearchState(
            phase="SEARCHING", frontier=(choice.model_copy(update={"slot": MealSlot.DINNER}),)
        )


@pytest.mark.parametrize("field", ["request_digest", "trial_digest", "context_digest"])
def test_fact_binding_transplants(frame: dict[str, Any], field: str) -> None:
    f = fact(frame)
    with pytest.raises(ValidationError):
        WeeklySolveResult(
            manifest=frame["manifest"],
            trial=trial(frame["request"]),
            facts=(f.model_copy(update={field: "f" * 64}),),
        )


def test_measurement_and_recipe_evidence_transplants(frame: dict[str, Any]) -> None:
    f = fact(frame, "synthetic_week_quantity_total")
    for update in (
        {"measurement_digest": "f" * 64},
        {
            "measurement_source": f.contributions[0].measurement_source.model_copy(
                update={"version": "foreign"}
            )
        },
    ):
        wrong = f.contributions[0].model_copy(update=update)
        with pytest.raises(ValidationError):
            WeeklySolveResult(
                manifest=frame["manifest"],
                trial=trial(frame["request"]),
                facts=(f.model_copy(update={"contributions": (wrong, *f.contributions[1:])}),),
            )
    f = fact(frame, "synthetic_week_max_recipe_slot_occurrences")
    wrong = f.occurrences[0].model_copy(update={"recipe_ids": ("foreign-recipe",)})
    with pytest.raises(ValidationError):
        WeeklySolveResult(
            manifest=frame["manifest"],
            trial=trial(frame["request"]),
            facts=(f.model_copy(update={"occurrences": (wrong, *f.occurrences[1:])}),),
        )


@pytest.mark.parametrize("value", [-1, True, 0.0, "0", 64_563_604_257_983_430_643])
def test_week_fact_numeric_boundaries_reject(frame: dict[str, Any], value: Any) -> None:
    f = fact(frame, "synthetic_week_quantity_total")
    with pytest.raises(ValidationError):
        WeekFact.model_validate(
            f.model_copy(update={"observation": f.observation.model_copy(update={"value": value})})
        )


def test_week_fact_maximum_is_exact_declaration_not_computation(frame: dict[str, Any]) -> None:
    f = fact(frame, "synthetic_week_quantity_total")
    f = WeekFact.model_validate(
        f.model_copy(
            update={
                "observation": f.observation.model_copy(
                    update={"value": 64_563_604_257_983_430_642}
                )
            }
        )
    )
    # Representation/bindings only; Prompt 1 deliberately does not sum or claim PASS.
    r = WeeklySolveResult(manifest=frame["manifest"], trial=trial(frame["request"]), facts=(f,))
    assert r.outcome is None
    assert (
        validate_contract_json(WeekFact, f.model_dump_json()).observation.value
        == 64_563_604_257_983_430_642
    )


def test_original_json_and_unchecked_nested_containers(frame: dict[str, Any]) -> None:
    request = frame["request"]
    raw = request.model_dump_json(by_alias=True)
    for bad in (
        raw.replace('"dayIndex":1', '"dayIndex":1,"dayIndex":2', 1),
        raw.replace('"dayIndex":1', '"dayIndex":1,"day_index":1', 1),
    ):
        with pytest.raises(ValidationError):
            validate_contract_json(WeeklyPlanningRequest, bad)
    for bad in (
        '{"deadline":1e999}',
        '{"deadline":NaN}',
        "[" * 65 + "0" + "]" * 65,
        " " * 1_048_577,
    ):
        with pytest.raises(ValidationError):
            validate_contract_json(WeeklySearchLimits, bad)

    class HostileTuple(tuple):
        def __iter__(self):
            raise AssertionError("hostile tuple executed")

    class HostileDict(dict):
        def items(self):
            raise AssertionError("hostile mapping executed")

    class HostileList(list):
        def __iter__(self):
            raise AssertionError("hostile list executed")

    for days in (HostileTuple(request.days), HostileList(request.days), list(request.days)):
        with pytest.raises(ValidationError):
            revise(request, days=days)
    with pytest.raises(ValidationError):
        WeeklyPlanningRequest.model_validate(HostileDict(request.model_dump()))
    for changes in ({"extra": True}, {"days": ()}, {"content_digest": "f" * 64}):
        with pytest.raises(ValidationError):
            WeeklyPlanningRequest.model_validate(request.model_copy(update=changes))


@pytest.mark.parametrize("enum_type", [MealSlot, PortionState, RuleScope, RuleStatus, DailyOutcome])
def test_counterfeit_enums(frame: dict[str, Any], enum_type: type[StrEnum]) -> None:
    original = next(iter(enum_type))
    forged = str.__new__(enum_type, original.value)
    object.__setattr__(forged, "_name_", original.name)
    object.__setattr__(forged, "_value_", original.value)
    if enum_type is DailyOutcome:
        target = WeeklySolveResult.model_construct(manifest=frame["manifest"], outcome=forged)
        cls = WeeklySolveResult
    elif enum_type is RuleStatus:
        target = WeeklyConstraintDiagnostic.model_construct(
            request_digest=frame["request"].content_digest,
            week_id="week-1",
            week_version="1",
            stage="WEEK",
            code="x",
            message="x",
            status=forged,
            evidence=(evidence(),),
        )
        cls = WeeklyConstraintDiagnostic
    elif enum_type is RuleScope:
        target = rule().model_copy(update={"scope": forged})
        with pytest.raises(ValidationError):
            kb, candidate, context = foundation((target,))
            build_expected_check_manifest(kb, candidate, context)
        return
    else:
        choice = trial(frame["request"]).choices[0]
        target = choice.model_copy(
            update={"slot": forged}
            if enum_type is MealSlot
            else {"option": choice.option.model_copy(update={"portion_state": forged})}
        )
        cls = WeeklyTrialChoice
    with pytest.raises(ValidationError):
        cls.model_validate(target)


def test_digests_roundtrip_and_unordered_declarations(frame: dict[str, Any]) -> None:
    request = frame["request"]
    for model in (frame["source"], request, frame["manifest"], trial(request), assignment(request)):
        assert model.content_digest == digest(model)
        assert validate_contract_json(type(model), model.model_dump_json()) == model
        assert model.model_dump_json() == model.model_dump_json()
    changed = revise(request, days=tuple(reversed(request.days)))
    assert changed.content_digest == request.content_digest
    assert sorted(d.day.day_index for d in changed.days) == list(range(1, 8))
    with pytest.raises(ValidationError):
        type(request).build(request.model_dump(), expected_digest="f" * 64)


def test_complete_upstream_week_deferral(frame: dict[str, Any]) -> None:
    candidate, kb, context = frame["candidate"], frame["kb"], frame["context"]
    expected = tuple(r for r in kb.rules if r.scope is RuleScope.WEEK)
    recipe = filter_candidates((candidate,), knowledge=kb, context=context)
    assert recipe.eligible_ids == ("week-recipe",)
    assert (
        tuple(
            r
            for r in recipe.decisions[0].resolution.manifest.deferred_checks
            if r.scope is RuleScope.WEEK
        )
        == expected
    )
    combo = frame["daily"].options[0].combination
    result = evaluate_combination(
        combo, candidates=(candidate,), knowledge=kb, context=context, trusted_combination=combo
    )
    assert result.status is RuleStatus.PASS
    assert tuple(r for r in result.deferred_checks if r.scope is RuleScope.WEEK) == expected
    daily = _daily_request(frame["request"], frame["request"].days[0])
    manifest = build_day_check_manifest(
        daily, knowledge=kb, context=context, sources=frame["daily"]
    )
    assert manifest.deferred_checks == expected
    solved = solve_daily_plan(
        daily, candidates=(candidate,), knowledge=kb, context=context, sources=frame["daily"]
    )
    assert solved.outcome is DailyOutcome.FEASIBLE
    assert solved.weekly_feasibility == "NOT_EVALUATED"
    assert solved.manifest.deferred_checks == expected


@pytest.mark.parametrize(
    "scope,attribute,version",
    [
        (RuleScope.RECIPE, "synthetic_flag", "synthetic-attributes.v1"),
        (
            RuleScope.COMBINATION,
            "synthetic_combination_roles_compatible",
            "synthetic-attributes.v3-combination",
        ),
        (RuleScope.DAY, "synthetic_day_complete", "synthetic-attributes.v4-day"),
        (RuleScope.WEEK, "synthetic_flag", "synthetic-attributes.v1"),
    ],
)
def test_old_policy_versions_and_legacy_week(
    scope: RuleScope, attribute: str, version: str
) -> None:
    kb, candidate, context = foundation(
        (rule(scope=scope, attribute=attribute, required_facts=(attribute,)),)
    )
    assert build_expected_check_manifest(kb, candidate, context).attribute_policy_version == version
    if scope is RuleScope.WEEK:
        with pytest.raises(ValidationError, match="WEEK"):
            packet(checks=(rule(attribute=attribute, required_facts=(attribute,)),))


@pytest.mark.parametrize(
    "workflow", [KnowledgeWorkflow.CRAVING_DISCOVERY, KnowledgeWorkflow.PLANNED_SWAP]
)
def test_nonweekly_workflow_rejected(frame: dict[str, Any], workflow: KnowledgeWorkflow) -> None:
    changed = revise(frame["context"], workflow=workflow)
    with pytest.raises(ValidationError):
        revise(frame["daily"], context=changed)


@pytest.mark.parametrize("value", [False, True])
@pytest.mark.parametrize("operator", [PredicateOperator.EQ, PredicateOperator.NE])
def test_boolean_week_admission(value: bool, operator: PredicateOperator) -> None:
    kb, candidate, context = foundation((rule(value=value, operator=operator),))
    manifest = build_expected_check_manifest(kb, candidate, context)
    assert manifest.deferred_checks[0].value is value
    assert manifest.deferred_checks[0].operator is operator


@pytest.mark.parametrize(
    "name,unit,value,operator",
    [
        (
            "synthetic_week_max_recipe_slot_occurrences",
            MeasurementUnit.DIMENSIONLESS,
            22,
            PredicateOperator.EQ,
        ),
        ("synthetic_week_max_recipe_slot_occurrences", MeasurementUnit.MG, 1, PredicateOperator.EQ),
        ("synthetic_week_quantity_total", MeasurementUnit.MG, ("a",), PredicateOperator.IN),
        ("unknown_week_fact", None, True, PredicateOperator.EQ),
    ],
)
def test_additional_admission_restrictions(
    name: str, unit: MeasurementUnit | None, value: Any, operator: PredicateOperator
) -> None:
    with pytest.raises(ValidationError):
        kb, candidate, context = foundation(
            (
                rule(
                    attribute=name,
                    required_facts=(name,),
                    unit=unit,
                    value=value,
                    operator=operator,
                ),
            )
        )
        build_expected_check_manifest(kb, candidate, context)


@pytest.mark.parametrize("case", ["wrong-version", "descriptor-fact", "dependency", "unknown-id"])
def test_exact_applicability_and_dependencies(case: str) -> None:
    kb, candidate, context = foundation((rule(),))
    body = kb.model_dump(exclude={"content_digest"})
    descriptor = kb.applicability_descriptors[0]
    if case == "descriptor-fact":
        body["applicability_descriptors"] = (
            descriptor.model_copy(update={"required_context_facts": ("wrong",)}),
        )
    elif case == "dependency":
        body["applicability_descriptors"] = (
            descriptor.model_copy(
                update={
                    "dependencies": (RuleReference(rule_id="unresolved-dependency", version="1"),)
                }
            ),
        )
    else:
        ref = RuleReference(
            rule_id="unsupported" if case == "unknown-id" else "synthetic-context-enabled",
            version="1" if case == "unknown-id" else "99",
        )
        body["rules"] = (kb.rules[0].model_copy(update={"applicability_reference": ref}),)
        body["applicability_descriptors"] = (descriptor.model_copy(update={"reference": ref}),)
    with pytest.raises(ValidationError):
        changed = build_knowledge_snapshot(body)
        changed_context = revise(context, expected_kb_digest=changed.content_digest)
        build_expected_check_manifest(changed, candidate, changed_context)


def test_false_v5_policy_without_week_attributes_rejected() -> None:
    kb, candidate, context = foundation(
        (
            rule(
                scope=RuleScope.DAY,
                attribute="synthetic_day_complete",
                required_facts=("synthetic_day_complete",),
            ),
        )
    )
    manifest = build_expected_check_manifest(kb, candidate, context)
    data = manifest.model_copy(update={"attribute_policy_version": "synthetic-attributes.v5-week"})
    h = digest(data, excludes={"manifest_id", "manifest_version", "content_digest"})
    with pytest.raises(ValidationError):
        ExpectedCheckManifest.model_validate(
            data.model_dump()
            | {
                "manifest_id": "manifest-" + h,
                "manifest_version": "synthetic-manifest.v1:" + h,
                "content_digest": h,
            }
        )


def test_source_cardinality_and_conflicting_evidence(frame: dict[str, Any]) -> None:
    daily = frame["daily"]
    with pytest.raises(ValidationError):
        revise(daily, options=(daily.options[0],) * 151)
    with pytest.raises(ValidationError):
        DailySlotDomain(slot=MealSlot.BREAKFAST, options=(daily.options[0].reference,) * 51)
    conflicting = evidence(source="Conflicting source under the same evidence identity")
    with pytest.raises(ValidationError):
        revise(frame["source"], evidence=(conflicting,))
    for field in ("source_id", "version", "content_digest"):
        with pytest.raises(ValidationError):
            revise(
                frame["source"],
                expected_daily_source=frame["source"].expected_daily_source.model_copy(
                    update={field: "f" * 64}
                ),
            )


def test_distinct_empty_domains_and_missing_measurements_are_declarations(
    frame: dict[str, Any],
) -> None:
    request = frame["request"]
    day = request.days[0]
    modified = WeeklyDayDomain(
        day=day.day, domains=tuple(DailySlotDomain(slot=d.slot, options=()) for d in day.domains)
    )
    changed = revise(request, days=(modified, *request.days[1:]))
    assert changed.days[0].domains[0].options == ()
    data = packet(suitability=False)
    result = WeeklySolveResult(manifest=data["manifest"])
    assert result.outcome is None


def test_diagnostic_bindings_capacity_and_evidence(frame: dict[str, Any]) -> None:
    request = frame["request"]
    diagnostic = WeeklyConstraintDiagnostic(
        request_digest=request.content_digest,
        week_id=request.week_id,
        week_version=request.week_version,
        stage="WEEK",
        code="NOT_EVALUATED",
        message="Synthetic declaration only",
        status=RuleStatus.UNKNOWN,
        evidence=(evidence(),),
    )
    assert WeeklySolveResult(manifest=frame["manifest"], diagnostics=(diagnostic,)).outcome is None
    for change in (
        {"request_digest": "f" * 64},
        {"week_id": "foreign"},
        {"evidence": ()},
        {"day": request.days[0].day.model_copy(update={"day_id": "foreign-day"})},
        {"rule_reference": RuleReference(rule_id="foreign-rule", version="1")},
    ):
        with pytest.raises(ValidationError):
            WeeklySolveResult(
                manifest=frame["manifest"], diagnostics=(diagnostic.model_copy(update=change),)
            )
    with pytest.raises(ValidationError):
        WeeklySolveResult(
            manifest=frame["manifest"],
            limits=WeeklySearchLimits(max_diagnostics=0),
            diagnostics=(diagnostic,),
        )


def test_all_new_records_revalidate_unchecked_fields(frame: dict[str, Any]) -> None:
    request = frame["request"]
    t = trial(request)
    a = assignment(request)
    quantity = fact(frame, "synthetic_week_quantity_total")
    occurrences = fact(frame, "synthetic_week_max_recipe_slot_occurrences")
    records = (
        frame["source"],
        request.expected_source,
        request,
        request.days[0],
        request.days[0].day,
        frame["manifest"],
        t,
        t.choices[0],
        a,
        a.days[0],
        quantity,
        quantity.contributions[0],
        occurrences.occurrences[0],
        WeeklySearchLimits(),
        WeeklySearchState(),
        WeeklyFrontierChoice.model_validate(t.choices[0].model_dump()),
        WeeklySolveResult(manifest=frame["manifest"]),
    )
    for record in records:
        with pytest.raises(ValidationError):
            type(record).model_validate(record.model_copy(update={"unexpected": 1}))
        required = [
            name for name, field in type(record).model_fields.items() if field.is_required()
        ]
        if required:
            unchecked: Any = record.model_copy()
            del unchecked.__dict__[required[0]]
            with pytest.raises(ValidationError):
                type(record).model_validate(unchecked)


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), "0"])
def test_deadline_strict_finite(value: Any) -> None:
    with pytest.raises(ValidationError):
        WeeklySearchLimits(deadline=value)


def test_daily_bridge_literal_identity(frame: dict[str, Any]) -> None:
    request = frame["request"]
    daily = _daily_request(request, request.days[0])
    assert daily.request_id == "weekly-day-" + digest(request) + "-1"
    assert daily.day_id == "independent-day-1"
    assert daily.source == frame["daily"]
    assert daily.content_digest == digest(daily)


def test_calendar_year_boundary_and_overflow(frame: dict[str, Any]) -> None:
    request = frame["request"]
    start = date(2026, 12, 29)
    days = tuple(
        d.model_copy(
            update={
                "day": d.day.model_copy(
                    update={
                        "calendar_date": (start + timedelta(days=d.day.day_index - 1)).isoformat()
                    }
                )
            }
        )
        for d in request.days
    )
    changed = revise(request, start_date=start.isoformat(), days=days)
    assert changed.days[-1].day.calendar_date == "2027-01-04"
    with pytest.raises(ValidationError):
        revise(request, start_date="9999-12-31")
