"""End to end under scenario A: the REAL catalogue export through Member 2's daily CSP.

The knowledge base is a fictional, SYNTHETIC stand-in built the same way as Member 2's
own Phase 5 fixture; its rules only use facts this adapter supplies (dish classification
settled, meal roles compatible, day sodium total under a cap). Nothing here
is a clinical rule or a production approval.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.meal_composition.member2_adapter import (
    SCENARIO_A,
    KnowledgeBinding,
    candidate_facts,
    daily_request,
    graph_entities,
    meal_option,
    option_id,
    round_half_up,
)
from savora_ai.core.meal_composition.models import MealCombination
from savora_ai.core.reasoning.daily import solve_daily_plan
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.schemas.candidates import FactSubjectKind, RuleContext, VersionedFact
from savora_ai.schemas.daily import DailyOutcome, DailySourceReference, MealSlot
from savora_ai.schemas.enums import PortionPreset
from savora_ai.schemas.food_graph import FoodGraphSnapshot
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
from savora_ai.schemas.reasoning import FactObservation

EXPORT = Path(__file__).parents[3] / "Data/catalogue"


def load_export() -> tuple[str, dict[str, CatalogueRecipe], list[MealCombination]]:
    catalogue_path = sorted(EXPORT.glob("*_catalogue.json"))[-1]
    version = catalogue_path.name.removesuffix("_catalogue.json")
    catalogue = json.loads(catalogue_path.read_text(encoding="utf-8"))
    combos = json.loads((EXPORT / f"{version}_combinations.json").read_text(encoding="utf-8"))
    dishes = {
        r["recipeId"]: CatalogueRecipe.model_validate_json(json.dumps(r))
        for r in catalogue["recipes"]
    }
    meals = [MealCombination.model_validate_json(json.dumps(c)) for c in combos["combinations"]]
    return version, dishes, meals


def fictional(name: str) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=name,
        version="1",
        source="Fictional scenario-A knowledge base; no clinical meaning",
        locator="urn:savora-test:" + name,
        environment=RuleEnvironment.SYNTHETIC,
    )


def rule(name: str, scope: RuleScope, attribute: str, **predicate: Any) -> RuleDefinition:
    return RuleDefinition.model_validate(
        dict(
            rule_id=name,
            version="1",
            scope=scope,
            severity=RuleSeverity.ABSOLUTE,
            domain=RuleDomain.CULINARY,
            attribute=attribute,
            operator=PredicateOperator.EQ,
            value=True,
            required_facts=(attribute,),
            applicability_reference=RuleReference(rule_id="synthetic-context-enabled", version="1"),
            evidence=(fictional(name),),
            rationale="Fictional scenario-A check; no clinical meaning",
            lifecycle=RuleLifecycle.ACTIVE,
            environment=RuleEnvironment.SYNTHETIC,
            approval_status=ApprovalStatus.APPROVED,
            approved_by="fictional-reviewer",
            approval_reference=fictional("approval-" + name),
        )
        | predicate
    )


def binding(version: str, dishes: list[CatalogueRecipe], day_cap_mg: int) -> KnowledgeBinding:
    ev = (fictional("kb"),)
    graph = FoodGraphSnapshot(
        graph_id="scenario-a-graph",
        version="1",
        catalogue_version=version,
        environment=RuleEnvironment.SYNTHETIC,
        entities=graph_entities(dishes, version),
        relations=(),
        evidence=ev,
    )
    rules = (
        rule("dish-settled", RuleScope.RECIPE, SCENARIO_A.fact_names["classification_settled"]),
        rule("meal-roles", RuleScope.COMBINATION, SCENARIO_A.fact_names["meal_roles_compatible"]),
        rule(
            "day-sodium-cap",
            RuleScope.DAY,
            "synthetic_day_quantity_total",
            operator=PredicateOperator.LE,
            value=day_cap_mg,
            unit=MeasurementUnit.MG,
        ),
        rule("week-deferred", RuleScope.WEEK, "synthetic_flag"),
    )
    refs = tuple(RuleReference(rule_id=r.rule_id, version=r.version) for r in rules)
    cells = tuple(
        CheckCatalogueEntry(
            entry_id=f"cell-{w.value}-{s.value}",
            version="1",
            kb_id="scenario-a-kb",
            kb_version="1",
            check_catalogue_version="scenario-a-checks",
            workflow=w,
            scope=s,
            rule_references=tuple(ref for ref, r in zip(refs, rules, strict=True) if r.scope is s),
            evidence=ev,
        )
        for w in KnowledgeWorkflow
        for s in RuleScope
        if w is not KnowledgeWorkflow.CRAVING_DISCOVERY
        or s in (RuleScope.PROFILE, RuleScope.RECIPE)
    )
    kb = build_knowledge_snapshot(
        dict(
            kb_id="scenario-a-kb",
            version="1",
            environment=RuleEnvironment.SYNTHETIC,
            graph_id=graph.graph_id,
            graph_version=graph.version,
            catalogue_version=version,
            taxonomy_version=None,
            check_catalogue_version="scenario-a-checks",
            graph=graph,
            rules=rules,
            active_rules=refs,
            applicability_descriptors=(
                ApplicabilityDescriptor(
                    reference=RuleReference(rule_id="synthetic-context-enabled", version="1"),
                    rule_references=refs,
                    required_context_facts=("synthetic_context_enabled",),
                    evidence=ev,
                ),
            ),
            check_catalogue=cells,
            rule_catalogue_coverage=tuple(
                RuleCatalogueCoverage(
                    coverage_id="coverage-" + c.entry_id,
                    version="1",
                    kb_id="scenario-a-kb",
                    kb_version="1",
                    check_catalogue_version="scenario-a-checks",
                    workflow=c.workflow,
                    scope=c.scope,
                    complete=True,
                    reason="Fictional complete scenario inventory",
                    evidence=ev,
                )
                for c in cells
            ),
            evidence=ev,
        )
    )
    context = RuleContext.build(
        dict(
            context_id="scenario-a-context",
            version="1",
            profile_id="scenario-a-profile",
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
                    subject_id="scenario-a-context",
                    subject_version="1",
                    context_id="scenario-a-context",
                    context_version="1",
                    observation=FactObservation(
                        fact_id="synthetic_context_enabled", value=True, complete=True, evidence=ev
                    ),
                ),
            ),
            evidence=ev,
        )
    )
    return KnowledgeBinding(knowledge=kb, context=context)


def solve(day_cap_mg: int):
    version, dishes, meals = load_export()

    def standard(meal: str, n: int) -> list[MealCombination]:
        chosen = [
            m
            for m in meals
            if m.meal_types[0].value == meal or meal in {x.value for x in m.meal_types}
        ]
        return sorted(chosen, key=lambda m: m.combination_id)[:n]

    breakfast, mains = standard("BREAKFAST", 3), standard("LUNCH", 4)
    picked = {d.dish_id for m in (*breakfast, *mains) for d in m.components}
    used = [dishes[d] for d in sorted(picked)]
    bound = binding(version, used, day_cap_mg)
    candidates = {
        d.recipe_id: candidate_facts(
            d, version, bound.knowledge.graph_id, bound.knowledge.graph_version
        )
        for d in used
    }
    provider = DailySourceReference(source_id="m1-export", version=version, content_digest="c" * 64)
    configs = {
        m.combination_id: next(c for c in m.configurations if c.preset is PortionPreset.STANDARD)
        for m in (*breakfast, *mains)
    }
    options = [
        meal_option(m, configs[m.combination_id], candidates, dishes, bound, provider)
        for m in (*breakfast, *mains)
    ]
    domains = {
        MealSlot.BREAKFAST: [option_id(configs[m.combination_id]) for m in breakfast],
        MealSlot.LUNCH: [option_id(configs[m.combination_id]) for m in mains],
        MealSlot.DINNER: [option_id(configs[m.combination_id]) for m in mains],
    }
    request, source = daily_request("scenario-a-day", "D1", options, domains, bound)
    result = solve_daily_plan(
        request,
        candidates=tuple(candidates.values()),
        knowledge=bound.knowledge,
        context=bound.context,
        sources=source,
    )
    sodium = {option_id(c): c.nutrition.totals.sodium_mg for c in configs.values() if c.nutrition}
    return result, sodium


def test_real_catalogue_day_is_feasible_under_a_generous_sodium_cap() -> None:
    result, sodium = solve(day_cap_mg=10_000)
    assert result.outcome is DailyOutcome.FEASIBLE
    assert result.assignment is not None
    chosen = [s.option.option_id for s in result.assignment.slots]
    assert len(chosen) == 3
    totals = [sodium[o] for o in chosen]
    assert all(t is not None for t in totals)
    assert sum(round_half_up(t) for t in totals if t is not None) <= 10_000


def test_a_tight_cap_makes_the_solver_backtrack_to_lower_sodium_meals() -> None:
    loose, sodium = solve(day_cap_mg=10_000)
    tight, _ = solve(day_cap_mg=1_500)
    assert loose.assignment is not None and tight.assignment is not None
    total = [sodium[s.option.option_id] for s in tight.assignment.slots]
    assert sum(round_half_up(t) for t in total if t is not None) <= 1_500
    loose_ids = [s.option.option_id for s in loose.assignment.slots]
    assert [s.option.option_id for s in tight.assignment.slots] != loose_ids


def test_real_catalogue_day_is_infeasible_when_no_three_meals_fit() -> None:
    result, _ = solve(day_cap_mg=1)  # below any breakfast + lunch + dinner
    assert result.outcome is DailyOutcome.INFEASIBLE
    assert result.assignment is None


def test_half_up_rounding_is_not_bankers_rounding() -> None:
    assert round_half_up(2.5) == 3 and round_half_up(3.5) == 4 and round_half_up(544.4999) == 544
    with pytest.raises(Exception):  # noqa: B017 - Decimal rejects NaN conversion to int
        round_half_up(float("nan"))
