"""Weekly plan and saved-slot substitution (ARCHITECTURE.md sections 4.2 and 4.4).

    plan_week(profile, bundle, start_date=..., scorer=...)
    substitute_slot(profile, bundle, current=<saved WeekPlan>, slot_id="D2_LUNCH", ...)

    allowed meal combinations (stand-in profile screen, profile.py)
      -> Transformer: rank_combinations, history = the profile's seed dishes
      -> one meal per slot: best-ranked anchors rotated over the week, so an anchor dish
         repeats at most twice (MAX_REPEATS_PER_WEEK)
      -> Rule Engine + weekly CSP: Member 2's solve_weekly_plan over the 21 slots
      -> explanation per meal; per-day nutrient totals

GC1 limits, all visible in the result:
- The KB is the stand-in (stand_in_kb.py): structural DAY/WEEK checks only, no nutrient
  or clinical constraints, so the CSP verifies a complete week rather than trading
  portions against targets. Each slot therefore offers ONE option (the ranked meal at its
  STANDARD portion): Member 2's solver orders a slot's options by ID, not by rank, so
  offering more would let ID order, not the ranker, decide.
- Energy is not a CSP constraint yet (member2_adapter assumption 3): day totals are
  reported, never claimed to fit the targets.

Substitution re-solves the week with every other slot LOCKED to its saved option and the
target slot offered the next-ranked meal the week does not already repeat (section 4.4).
It runs as a WEEKLY_PLAN context (Member 2's CSP does not admit PLANNED_SWAP yet); the
result is still labelled PLANNED_SWAP.
"""

import hashlib
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from time import monotonic
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from savora_ai.core.explainability.explanation import (
    MealExplanation,
    PlanningOutcome,
    RuleOutcome,
    explain_meal,
)
from savora_ai.core.food_data.classification import is_plannable
from savora_ai.core.food_data.models import NutrientVector
from savora_ai.core.meal_composition.coverage import MAX_REPEATS_PER_WEEK
from savora_ai.core.meal_composition.member2_adapter import (
    KnowledgeBinding,
    candidate_facts,
    evidence,
    meal_option,
    option_id,
)
from savora_ai.core.meal_composition.models import MealCombination, PortionConfiguration
from savora_ai.core.pipelines.catalogue import CatalogueBundle
from savora_ai.core.pipelines.profile import (
    PlanningProfile,
    SafetyVerification,
    _PipelineModel,
    combination_allowed,
    safety_verification,
)
from savora_ai.core.pipelines.stand_in_kb import build_stand_in_knowledge, stand_in_context
from savora_ai.core.reasoning.weekly import solve_weekly_plan
from savora_ai.core.recommendation.ranking import (
    CombinationRanking,
    FallbackReason,
    RankingContext,
    SequenceScorer,
    rank_combinations,
)
from savora_ai.schemas.daily import (
    DailyOutcome,
    DailySlotDomain,
    DailySourceReference,
    DailySourceSnapshot,
    MealSlot,
)
from savora_ai.schemas.enums import MealType, PortionPreset
from savora_ai.schemas.knowledge_base import KnowledgeWorkflow
from savora_ai.schemas.weekly import (
    WeekDayReference,
    WeeklyDayDomain,
    WeeklyPlanningRequest,
    WeeklySearchLimits,
    WeeklySourceReference,
    WeeklySourceSnapshot,
)

DAYS = 7
SLOT_ID = r"^D[1-7]_(BREAKFAST|LUNCH|DINNER)$"
_SlotId = Annotated[str, StringConstraints(pattern=SLOT_ID)]
_NUTRIENTS = tuple(NutrientVector.model_fields)
_Workflow = Literal["WEEKLY_PLAN", "PLANNED_SWAP"]


class PlanStatus(StrEnum):
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # unknown facts, or too few allowed meals
    TIMEOUT = "TIMEOUT"


class PlannedMeal(_PipelineModel):
    slot_id: _SlotId  # "D2_LUNCH"
    day_index: int = Field(ge=1, le=DAYS)
    calendar_date: str
    meal_type: MealType
    option_id: str  # "<combinationId>:<PRESET>": what to store and lock
    combination_id: str
    configuration_id: str
    preset: PortionPreset
    explanation: MealExplanation  # dishes, portions, totals, reasons


class DayTotals(_PipelineModel):
    day_index: int = Field(ge=1, le=DAYS)
    calendar_date: str
    totals: NutrientVector  # sum of the three meals; any unknown meal value -> unknown


class SearchSummary(_PipelineModel):
    outcome: DailyOutcome
    nodes: int
    exhaustive: bool
    diagnostics: tuple[str, ...]  # "<stage>:<code>: <message>", bounded by the solver
    seconds: float


class WeekPlan(_PipelineModel):
    status: PlanStatus
    workflow: _Workflow
    week_id: str
    start_date: str
    profile_id: str
    profile_version: int
    catalogue_version: str
    meals: tuple[PlannedMeal, ...]  # 21 when FEASIBLE, else empty
    day_totals: tuple[DayTotals, ...]
    model_version: str | None
    fallback_reason: FallbackReason | None
    kb_id: str | None
    kb_version: str | None
    search: SearchSummary | None
    message: str
    safety: SafetyVerification


def slot_id(day_index: int, meal: MealType) -> str:
    return f"D{day_index}_{meal.value}"


def _standard(combination: MealCombination) -> PortionConfiguration | None:
    """The STANDARD configuration, if validated with a known sodium total (the one meal
    measurement the CSP carries; unknown would make the day UNKNOWN)."""
    for config in combination.configurations:
        if (
            config.preset is PortionPreset.STANDARD
            and config.nutrition is not None
            and config.nutrition.totals.sodium_mg is not None
        ):
            return config
    return None


def _ranked_meals(
    bundle: CatalogueBundle,
    profile: PlanningProfile,
    scorer: SequenceScorer | None,
) -> tuple[CombinationRanking, dict[MealType, list[MealCombination]]]:
    """Allowed, plannable, measurable meals in rank order; the best meal per anchor dish."""
    allowed = [
        c
        for c in sorted(bundle.combinations.values(), key=lambda c: c.combination_id)
        if combination_allowed(c, bundle.dishes, profile)
        and all(is_plannable(bundle.dishes[p.dish_id]) for p in c.components)
        and _standard(c) is not None
    ]
    ranking = rank_combinations(
        profile.seed_recipe_ids,
        [c.combination_id for c in allowed],
        RankingContext(),
        scorer=scorer,
        fallback=bundle.popularity,
    )
    by_meal: dict[MealType, list[MealCombination]] = {MealType.BREAKFAST: [], MealType.LUNCH: []}
    seen: dict[MealType, set[str]] = {MealType.BREAKFAST: set(), MealType.LUNCH: set()}
    for entry in ranking.ranked_candidates:
        combo = bundle.combinations[entry.combination_id]
        kind = MealType.BREAKFAST if MealType.BREAKFAST in combo.meal_types else MealType.LUNCH
        if kind is MealType.LUNCH and MealType.DINNER not in combo.meal_types:
            continue
        anchor = combo.components[0].dish_id
        if anchor not in seen[kind]:
            seen[kind].add(anchor)
            by_meal[kind].append(combo)
    # A dish that anchors both a breakfast and a main is kept as a breakfast, so the week
    # does not serve it at both (unless mains would run short without it).
    breakfast_anchors = {c.components[0].dish_id for c in by_meal[MealType.BREAKFAST][:DAYS]}
    mains = [c for c in by_meal[MealType.LUNCH] if c.components[0].dish_id not in breakfast_anchors]
    if len(mains) >= _needed(MealType.LUNCH):
        by_meal[MealType.LUNCH] = mains
    return ranking, by_meal


def _rotation(by_meal: Mapping[MealType, Sequence[MealCombination]]) -> dict[str, MealCombination]:
    """Breakfast d uses anchor d; lunch/dinner d use mains 2d and 2d+1 (cycled)."""
    breakfasts, mains = by_meal[MealType.BREAKFAST], by_meal[MealType.LUNCH]
    week: dict[str, MealCombination] = {}
    for d in range(DAYS):
        week[slot_id(d + 1, MealType.BREAKFAST)] = breakfasts[d % len(breakfasts)]
        week[slot_id(d + 1, MealType.LUNCH)] = mains[(2 * d) % len(mains)]
        week[slot_id(d + 1, MealType.DINNER)] = mains[(2 * d + 1) % len(mains)]
    return week


def _needed(meal: MealType) -> int:
    slots = DAYS if meal is MealType.BREAKFAST else 2 * DAYS
    return -(-slots // MAX_REPEATS_PER_WEEK)


def _sum(values: Iterable[NutrientVector]) -> NutrientVector:
    items = list(values)
    totals: dict[str, float | None] = {}
    for name in _NUTRIENTS:
        parts = [getattr(v, name) for v in items]
        totals[name] = None if any(p is None for p in parts) else round(sum(parts), 2)
    return NutrientVector(**totals)


def _solve(
    bundle: CatalogueBundle,
    profile: PlanningProfile,
    workflow: _Workflow,
    week_id: str,
    start: date,
    chosen: Mapping[str, tuple[MealCombination, PortionConfiguration]],
    ranking: CombinationRanking,
    limits: WeeklySearchLimits | None,
    clock: Callable[[], float],
) -> WeekPlan:
    """Member 2's weekly CSP over one option per slot; maps the witness to `PlannedMeal`s."""
    started = clock()
    dish_ids = sorted({p.dish_id for c, _ in chosen.values() for p in c.components})
    knowledge = build_stand_in_knowledge(bundle, dish_ids)
    # Member 2's daily/weekly contracts admit only WEEKLY_PLAN contexts (no PLANNED_SWAP
    # yet), so a swap is solved as a week whose other 20 slots are locked.
    context = stand_in_context(knowledge, profile, KnowledgeWorkflow.WEEKLY_PLAN)
    binding = KnowledgeBinding(knowledge=knowledge, context=context)
    candidates = {
        i: candidate_facts(
            bundle.dishes[i], bundle.version, knowledge.graph_id, knowledge.graph_version
        )
        for i in dish_ids
    }
    provider = DailySourceReference(  # who declared suitability/measurements: the export
        source_id="m1-catalogue-export",
        version=bundle.version,
        content_digest=hashlib.sha256(bundle.version.encode()).hexdigest(),
    )
    options = {}
    for combo, config in chosen.values():
        oid = option_id(config)
        if oid not in options:
            options[oid] = meal_option(combo, config, candidates, bundle.dishes, binding, provider)
    v = bundle.version
    daily = DailySourceSnapshot.build(
        dict(
            source_id="m1-catalogue-meals",
            version=v,
            context=context,
            options=tuple(options[k] for k in sorted(options)),
            evidence=(evidence(v, "meal-options"),),
        )
    )
    weekly = WeeklySourceSnapshot.build(
        dict(
            source_id="m1-catalogue-week",
            version=v,
            expected_daily_source=DailySourceReference(
                source_id=daily.source_id,
                version=daily.version,
                content_digest=daily.content_digest,
            ),
            daily_source=daily,
            evidence=(evidence(v, "week-options"),),
        )
    )
    days = tuple(
        WeekDayReference(
            week_id=week_id,
            week_version="1",
            day_id=f"{week_id}-d{d}",
            day_index=d,
            calendar_date=(start + timedelta(days=d - 1)).isoformat(),
        )
        for d in range(1, DAYS + 1)
    )
    request = WeeklyPlanningRequest.build(
        dict(
            request_id=f"{week_id}-request",
            version="1",
            week_id=week_id,
            week_version="1",
            start_date=start.isoformat(),
            context_id=context.context_id,
            context_version=context.version,
            context_digest=context.content_digest,
            expected_source=WeeklySourceReference(
                source_id=weekly.source_id,
                version=weekly.version,
                content_digest=weekly.content_digest,
            ),
            source=weekly,
            days=tuple(
                WeeklyDayDomain(
                    day=day,
                    domains=tuple(
                        DailySlotDomain(
                            slot=slot,
                            options=(
                                options[
                                    option_id(chosen[f"D{day.day_index}_{slot.value}"][1])
                                ].reference,
                            ),
                        )
                        for slot in MealSlot
                    ),
                )
                for day in days
            ),
        )
    )
    result = solve_weekly_plan(
        request,
        candidates=tuple(candidates[i] for i in dish_ids),
        knowledge=knowledge,
        context=context,
        sources=weekly,
        limits=limits,
        clock=clock,
    )
    stats = result.certificate.statistics
    search = SearchSummary(
        outcome=result.outcome,
        nodes=stats.nodes,
        exhaustive=stats.exhaustive,
        diagnostics=tuple(f"{d.stage}:{d.code}: {d.message}" for d in result.diagnostics),
        seconds=round(clock() - started, 3),
    )
    job = _Job(bundle, profile, workflow, week_id, start, ranking)
    kb = (knowledge.kb_id, knowledge.version)
    if result.outcome is not DailyOutcome.FEASIBLE or result.witness is None:
        return _week_plan(
            job,
            PlanStatus(result.outcome.value),
            f"Weekly CSP outcome {result.outcome.value}; no plan to save.",
            kb=kb,
            search=search,
        )
    by_option = {option_id(config): (combo, config) for combo, config in chosen.values()}
    meals: list[PlannedMeal] = []
    for day in result.witness.assignment.days:
        for assigned in day.assignment.slots:
            combo, config = by_option[assigned.option.option_id]
            sid = f"D{day.day.day_index}_{assigned.slot.value}"
            rules = RuleOutcome(
                status="PASS",
                checked_rules=tuple(r.rule_id for r in knowledge.rules),
                trace_id=result.witness.trace.manifest_id,
            )
            planning = PlanningOutcome(
                outcome="FEASIBLE",
                slot_id=sid,
                search_nodes=stats.nodes,
                constraints=("stand-in: every slot resolved; all seven days resolved",),
            )
            meals.append(
                PlannedMeal(
                    slot_id=sid,
                    day_index=day.day.day_index,
                    calendar_date=day.day.calendar_date,
                    meal_type=MealType(assigned.slot.value),
                    option_id=assigned.option.option_id,
                    combination_id=combo.combination_id,
                    configuration_id=config.configuration_id,
                    preset=config.preset,
                    explanation=explain_meal(
                        combo,
                        config,
                        bundle.dishes,
                        slot_id=sid,
                        ranking=ranking,
                        rules=rules,
                        planning=planning,
                    ),
                )
            )
    meals.sort(key=lambda m: (m.day_index, list(MealType).index(m.meal_type)))
    totals = tuple(
        DayTotals(
            day_index=d,
            calendar_date=(start + timedelta(days=d - 1)).isoformat(),
            totals=_sum(m.explanation.totals for m in meals if m.day_index == d),
        )
        for d in range(1, DAYS + 1)
    )
    return _week_plan(
        job,
        PlanStatus.FEASIBLE,
        "21 meals verified by the weekly CSP against the stand-in rule set.",
        meals=meals,
        day_totals=totals,
        kb=kb,
        search=search,
    )


@dataclass(frozen=True)
class _Job:
    bundle: CatalogueBundle
    profile: PlanningProfile
    workflow: _Workflow
    week_id: str
    start: date
    ranking: CombinationRanking


def _week_plan(
    job: _Job,
    status: PlanStatus,
    message: str,
    *,
    meals: Sequence[PlannedMeal] = (),
    day_totals: Sequence[DayTotals] = (),
    kb: tuple[str, str] | None = None,
    search: SearchSummary | None = None,
) -> WeekPlan:
    return WeekPlan(
        status=status,
        workflow=job.workflow,
        week_id=job.week_id,
        start_date=job.start.isoformat(),
        profile_id=job.profile.profile_id,
        profile_version=job.profile.profile_version,
        catalogue_version=job.bundle.version,
        meals=tuple(meals),
        day_totals=tuple(day_totals),
        model_version=job.ranking.model_version,
        fallback_reason=job.ranking.fallback_reason,
        kb_id=None if kb is None else kb[0],
        kb_version=None if kb is None else kb[1],
        search=search,
        message=message,
        safety=safety_verification(job.profile),
    )


def plan_week(
    profile: PlanningProfile,
    bundle: CatalogueBundle,
    *,
    week_id: str,
    start_date: date,
    scorer: SequenceScorer | None = None,
    limits: WeeklySearchLimits | None = None,
    clock: Callable[[], float] = monotonic,
) -> WeekPlan:
    """A new 21-slot plan for the profile; store it only when `status` is FEASIBLE."""
    workflow: _Workflow = "WEEKLY_PLAN"
    ranking, by_meal = _ranked_meals(bundle, profile, scorer)
    short = [
        f"{len(by_meal[m])} distinct {m.value.lower()} dishes allowed, {_needed(m)} needed"
        for m in by_meal
        if len(by_meal[m]) < _needed(m)
    ]
    if short:
        return _week_plan(
            _Job(bundle, profile, workflow, week_id, start_date, ranking),
            PlanStatus.INSUFFICIENT_DATA,
            "Not enough allowed meals for a week without repeating a dish more than "
            f"{MAX_REPEATS_PER_WEEK} times: " + "; ".join(short) + ".",
        )
    chosen = {}
    for sid, combo in _rotation(by_meal).items():
        config = _standard(combo)
        assert config is not None  # _ranked_meals keeps only measurable meals
        chosen[sid] = (combo, config)
    return _solve(bundle, profile, workflow, week_id, start_date, chosen, ranking, limits, clock)


def substitute_slot(
    profile: PlanningProfile,
    bundle: CatalogueBundle,
    *,
    current: Mapping[str, str],
    slot: str,
    week_id: str,
    start_date: date,
    exclude_combination_ids: Iterable[str] = (),
    scorer: SequenceScorer | None = None,
    limits: WeeklySearchLimits | None = None,
    clock: Callable[[], float] = monotonic,
) -> WeekPlan:
    """Replace one saved slot; every other slot stays LOCKED to its saved option.

    `current` maps all 21 slot IDs to their saved option IDs (`PlannedMeal.option_id`).
    The new meal is the best-ranked allowed meal for that meal type, not in
    `exclude_combination_ids` (e.g. earlier replacements the user rejected), whose anchor
    dish is not yet in the week, else used fewer than MAX_REPEATS_PER_WEEK times. The
    result is a full revision to store as new."""
    workflow: _Workflow = "PLANNED_SWAP"
    expected = {slot_id(d, m) for d in range(1, DAYS + 1) for m in MealType}
    if set(current) != expected:
        raise ValueError("current must map all 21 slot IDs (D1_BREAKFAST..D7_DINNER)")
    if slot not in expected:
        raise ValueError(f"unknown slot {slot!r}")
    configs = {
        option_id(cfg): (combo, cfg)
        for combo in bundle.combinations.values()
        for cfg in combo.configurations
    }
    missing = sorted(o for o in current.values() if o not in configs)
    if missing:
        raise ValueError(f"saved options not in catalogue {bundle.version}: {missing[:3]}")
    chosen = {sid: configs[oid] for sid, oid in current.items()}
    # Locking must never keep a meal the current profile no longer allows (new allergy,
    # diet or cuisine policy): the caller generates a new plan instead.
    stale = sorted(
        sid
        for sid, (combo, _) in chosen.items()
        if sid != slot and not combination_allowed(combo, bundle.dishes, profile)
    )
    if stale:
        raise ValueError(f"saved meals no longer fit the profile: {stale[:3]}; plan a new week")
    ranking, by_meal = _ranked_meals(bundle, profile, scorer)
    meal = MealType(slot.split("_", 1)[1])
    kind = MealType.BREAKFAST if meal is MealType.BREAKFAST else MealType.LUNCH
    used = Counter(c.components[0].dish_id for sid, (c, _) in chosen.items() if sid != slot)
    old_combo = chosen[slot][0]
    excluded = {*exclude_combination_ids, old_combo.combination_id}
    # Prefer a dish not yet in the week, then one used fewer than MAX_REPEATS_PER_WEEK times.
    replacement = next(
        (
            c
            for repeats in range(MAX_REPEATS_PER_WEEK)
            for c in by_meal[kind]
            if c.combination_id not in excluded and used[c.components[0].dish_id] == repeats
        ),
        None,
    )
    if replacement is None:
        return _week_plan(
            _Job(bundle, profile, workflow, week_id, start_date, ranking),
            PlanStatus.INSUFFICIENT_DATA,
            f"No allowed {meal.value.lower()} meal left that the week does not already "
            f"serve {MAX_REPEATS_PER_WEEK} times.",
        )
    config = _standard(replacement)
    assert config is not None
    chosen[slot] = (replacement, config)
    return _solve(bundle, profile, workflow, week_id, start_date, chosen, ranking, limits, clock)
