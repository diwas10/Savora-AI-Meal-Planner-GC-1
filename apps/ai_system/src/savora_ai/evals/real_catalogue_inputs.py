"""Real fixture construction, adapted from M1 c5af633 without editing M1 serving code.

The fixture uses M1 ranking/rotation and a SYNTHETIC stand-in KB. This is not
production allergen, clinical or nutritional eligibility evidence.
"""

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from savora_ai.core.meal_composition.member2_adapter import (
    KnowledgeBinding,
    candidate_facts,
    evidence,
    meal_option,
    option_id,
)
from savora_ai.core.meal_composition.models import MealCombination, PortionConfiguration
from savora_ai.core.pipelines.catalogue import CatalogueBundle
from savora_ai.core.pipelines.profile import PlanningProfile
from savora_ai.core.pipelines.stand_in_kb import build_stand_in_knowledge, stand_in_context
from savora_ai.schemas.candidates import CandidateRecipeFacts, RuleContext
from savora_ai.schemas.daily import (
    DailyMealOption,
    DailySlotDomain,
    DailySourceReference,
    DailySourceSnapshot,
    MealSlot,
)
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot, KnowledgeWorkflow
from savora_ai.schemas.weekly import (
    WeekDayReference,
    WeeklyDayDomain,
    WeeklyPlanningRequest,
    WeeklySourceReference,
    WeeklySourceSnapshot,
)

DAYS = 7


@dataclass(frozen=True)
class RealWeekInputs:
    """Everything Member 2's weekly contracts need for one fixed option per slot."""

    dish_ids: list[str]
    knowledge: KnowledgeBaseSnapshot
    context: RuleContext
    candidates: dict[str, CandidateRecipeFacts]
    provider: DailySourceReference
    options: dict[str, DailyMealOption]
    weekly: WeeklySourceSnapshot
    days: tuple[WeekDayReference, ...]
    request: WeeklyPlanningRequest


def build_real_week_inputs(
    bundle: CatalogueBundle,
    profile: PlanningProfile,
    week_id: str,
    start: date,
    chosen: Mapping[str, tuple[MealCombination, PortionConfiguration]],
    extra_dish_ids: Iterable[str] = (),
) -> RealWeekInputs:
    dish_ids = sorted({p.dish_id for c, _ in chosen.values() for p in c.components})
    knowledge = build_stand_in_knowledge(bundle, sorted({*dish_ids, *extra_dish_ids}))
    context = stand_in_context(knowledge, profile, KnowledgeWorkflow.WEEKLY_PLAN)
    binding = KnowledgeBinding(knowledge=knowledge, context=context)
    candidates = {
        i: candidate_facts(
            bundle.dishes[i], bundle.version, knowledge.graph_id, knowledge.graph_version
        )
        for i in sorted({*dish_ids, *extra_dish_ids})
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
    return RealWeekInputs(
        dish_ids=dish_ids,
        knowledge=knowledge,
        context=context,
        candidates=candidates,
        provider=provider,
        options=options,
        weekly=weekly,
        days=days,
        request=request,
    )
