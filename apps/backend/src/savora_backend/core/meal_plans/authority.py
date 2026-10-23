"""Server-owned bindings for unverified saved history; never a proof certificate.

Historical source bodies may be reconstructed only when their complete combination,
configuration and recipe digests still match the release captured at save time.
Otherwise the user must regenerate; current catalogue data cannot rewrite history.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Any

from savora_ai.core.meal_composition.member2_adapter import option_id
from savora_ai.core.pipelines import CatalogueBundle, PlannedMeal, PlanningProfile
from savora_backend.core.meal_plans.entity import MealPlanEntity, MealPlanSlotEntity

SCHEMA = "application-saved-plan-binding.v1"
SLOTS = frozenset(f"D{d}_{m}" for d in range(1, 8) for m in ("BREAKFAST", "LUNCH", "DINNER"))


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def _identity(plan: MealPlanEntity) -> dict[str, Any]:
    return {
        "planId": str(plan.id),
        "ownerId": str(plan.user_id),
        "revision": plan.revision,
        "profileVersion": plan.profile_version,
        "catalogueVersion": plan.catalogue_version,
        "weekStart": plan.week_start.isoformat(),
        "kbId": plan.kb_id,
        "kbVersion": plan.kb_version,
    }


def _sources(bundle: CatalogueBundle, meals: Sequence[PlannedMeal]) -> dict[str, str]:
    sources = {}
    for meal in meals:
        combo = bundle.combinations[meal.combination_id]
        config = next(
            c for c in combo.configurations if c.configuration_id == meal.configuration_id
        )
        if meal.option_id != option_id(config):
            raise ValueError("Saved option/configuration binding differs")
        if meal.preset != config.preset:
            raise ValueError("Saved portion preset differs")
        sources[combo.combination_id] = digest(
            {
                "combination": combo.model_dump(mode="json", by_alias=True),
                "recipes": {
                    p.dish_id: bundle.dishes[p.dish_id].model_dump(mode="json", by_alias=True)
                    for p in combo.components
                },
            }
        )
    return sources


def capture_binding(
    plan: MealPlanEntity,
    meals: Sequence[PlannedMeal],
    *,
    bundle: CatalogueBundle,
    profile: PlanningProfile,
    targets: Mapping[str, Any],
) -> dict[str, Any]:
    if len(meals) != 21 or {m.slot_id for m in meals} != SLOTS:
        raise ValueError("A saved week must contain exactly the 21 canonical slots")
    if plan.catalogue_version != bundle.version or plan.profile_version != profile.profile_version:
        raise ValueError("Saved release/profile differs from the generating authority")
    for meal in meals:
        if (
            meal.slot_id != f"D{meal.day_index}_{meal.meal_type.value}"
            or meal.calendar_date
            != (plan.week_start + timedelta(days=meal.day_index - 1)).isoformat()
        ):
            raise ValueError("Saved slot identity/date differs")
    return {
        "schemaVersion": SCHEMA,
        "identity": _identity(plan),
        "profileDigest": digest(profile.model_dump(mode="json", by_alias=True)),
        "targetSnapshot": dict(targets),
        "targetDigest": digest(targets),
        "slotDigests": {m.slot_id: digest(m.model_dump(mode="json", by_alias=True)) for m in meals},
        "sources": _sources(bundle, meals),
    }


def validate_binding(
    plan: MealPlanEntity,
    slots: Sequence[MealPlanSlotEntity],
    *,
    bundle: CatalogueBundle,
    profile: PlanningProfile,
    targets: Mapping[str, Any],
) -> dict[str, Any]:
    binding = plan.source_binding
    if not binding or binding.get("schemaVersion") != SCHEMA:
        raise ValueError(
            "This saved plan lacks source bindings; generate a new plan before swapping."
        )
    if len(slots) != 21 or {s.slot_id for s in slots} != SLOTS:
        raise ValueError("Saved slot inventory differs; generate a new plan.")
    meals = [PlannedMeal.model_validate_json(json.dumps(s.snapshot)) for s in slots]
    for slot, meal in zip(slots, meals, strict=True):
        if (
            slot.plan_id,
            slot.slot_id,
            slot.day_index,
            slot.calendar_date,
            slot.meal_type,
            slot.option_id,
            slot.combination_id,
            slot.configuration_id,
            slot.preset,
        ) != (
            plan.id,
            meal.slot_id,
            meal.day_index,
            meal.calendar_date,
            meal.meal_type.value,
            meal.option_id,
            meal.combination_id,
            meal.configuration_id,
            meal.preset.value,
        ):
            raise ValueError("Saved slot columns and immutable payload differ.")
    try:
        expected = capture_binding(plan, meals, bundle=bundle, profile=profile, targets=targets)
    except (KeyError, StopIteration) as exc:
        raise ValueError(
            "Original catalogue sources are unavailable; generate a new plan."
        ) from exc
    if binding != expected:
        raise ValueError(
            "Saved source/target digest mismatch; generate a new plan before swapping."
        )
    return binding
