"""Entity <-> DTO and pipeline-result -> entity conversions."""

import json
from typing import Any
from uuid import UUID

from savora_ai.core.pipelines import PlannedMeal, SafetyVerification, WeekPlan
from savora_ai.core.pipelines.planning import DayTotals, SearchSummary
from savora_ai.schemas.craving import CravingRequest
from savora_backend.core.meal_plans.dto import (
    MealPlanDetailDto,
    MealPlanSlotDto,
    SubstitutionDetailDto,
)
from savora_backend.core.meal_plans.entity import (
    MealPlanEntity,
    MealPlanJobStatus,
    MealPlanSlotEntity,
    MealPlanSubstitutionEntity,
)

_MEAL_ORDER = {"BREAKFAST": 0, "LUNCH": 1, "DINNER": 2}


def _json(value: Any) -> str:
    return json.dumps(value)


def apply_week_result(plan: MealPlanEntity, week: WeekPlan) -> None:
    """Copy a pipeline result's status and provenance onto the plan row."""
    plan.status = week.status.value
    plan.message = week.message
    plan.catalogue_version = week.catalogue_version
    plan.model_version = week.model_version
    plan.fallback_reason = week.fallback_reason.value if week.fallback_reason else None
    plan.kb_id = week.kb_id
    plan.kb_version = week.kb_version
    plan.safety = week.safety.model_dump(mode="json", by_alias=True)
    plan.search = week.search.model_dump(mode="json", by_alias=True) if week.search else None
    plan.day_totals = [d.model_dump(mode="json", by_alias=True) for d in week.day_totals]


def slot_entity(plan_id: UUID, meal: PlannedMeal) -> MealPlanSlotEntity:
    return MealPlanSlotEntity(
        plan_id=plan_id,
        slot_id=meal.slot_id,
        day_index=meal.day_index,
        calendar_date=meal.calendar_date,
        meal_type=meal.meal_type.value,
        option_id=meal.option_id,
        combination_id=meal.combination_id,
        configuration_id=meal.configuration_id,
        preset=meal.preset.value,
        snapshot=meal.model_dump(mode="json", by_alias=True),
    )


def copy_slot(plan_id: UUID, slot: MealPlanSlotEntity) -> MealPlanSlotEntity:
    """A locked slot, copied verbatim into a new revision."""
    return MealPlanSlotEntity(
        plan_id=plan_id,
        slot_id=slot.slot_id,
        day_index=slot.day_index,
        calendar_date=slot.calendar_date,
        meal_type=slot.meal_type,
        option_id=slot.option_id,
        combination_id=slot.combination_id,
        configuration_id=slot.configuration_id,
        preset=slot.preset,
        snapshot=dict(slot.snapshot),
    )


def to_detail_dto(plan: MealPlanEntity, slots: list[MealPlanSlotEntity]) -> MealPlanDetailDto:
    ordered = sorted(slots, key=lambda s: (s.day_index, _MEAL_ORDER.get(s.meal_type, 9)))
    return MealPlanDetailDto(
        id=plan.id,
        user_id=plan.user_id,
        week_start=plan.week_start,
        revision=plan.revision,
        status=MealPlanJobStatus(plan.status),
        message=plan.message,
        profile_version=plan.profile_version,
        catalogue_version=plan.catalogue_version,
        model_version=plan.model_version,
        fallback_reason=plan.fallback_reason,
        kb_id=plan.kb_id,
        kb_version=plan.kb_version,
        parent_plan_id=plan.parent_plan_id,
        is_current=plan.is_current,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        safety=SafetyVerification.model_validate_json(_json(plan.safety)) if plan.safety else None,
        search=SearchSummary.model_validate_json(_json(plan.search)) if plan.search else None,
        day_totals=[DayTotals.model_validate_json(_json(d)) for d in plan.day_totals or []],
        slots=[
            MealPlanSlotDto(
                slot_id=s.slot_id,
                day_index=s.day_index,
                calendar_date=s.calendar_date,
                meal_type=s.meal_type,
                option_id=s.option_id,
                combination_id=s.combination_id,
                configuration_id=s.configuration_id,
                preset=s.preset,
                snapshot=PlannedMeal.model_validate_json(_json(s.snapshot)),
            )
            for s in ordered
        ],
    )


def to_substitution_dto(sub: MealPlanSubstitutionEntity) -> SubstitutionDetailDto:
    def meal(value: dict[str, Any] | None) -> PlannedMeal | None:
        return PlannedMeal.model_validate_json(_json(value)) if value else None

    return SubstitutionDetailDto(
        id=sub.id,
        status=MealPlanJobStatus(sub.status),
        message=sub.message,
        from_plan_id=sub.from_plan_id,
        to_plan_id=sub.to_plan_id,
        slot_id=sub.slot_id,
        replacement_combination_id=sub.replacement_combination_id,
        preference=CravingRequest.model_validate_json(_json(sub.preference))
        if sub.preference
        else None,
        before_snapshot=meal(sub.before_snapshot),
        after_snapshot=meal(sub.after_snapshot),
        created_at=sub.created_at,
        updated_at=sub.updated_at,
    )
