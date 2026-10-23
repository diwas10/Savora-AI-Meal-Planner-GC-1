"""In-process background jobs for plan generation and substitution (spec section 2 item 3).

No queue or Redis (AGENTS.md): a job is an `asyncio` task running the pure pipeline in a
thread, with its state persisted on the plan/substitution row so clients poll it. Rows
left GENERATING by a restart are marked FAILED at startup. A failure stores a fixed,
user-facing message; the exception itself goes to the logs only.
"""

import asyncio
import json
import logging
from collections.abc import Callable, Coroutine
from datetime import date
from typing import Any, Literal, get_args
from uuid import UUID

from savora_ai.core.pipelines import PlannedMeal, PlanningProfile, PlanStatus, SwapProof
from savora_ai.schemas.craving import CravingRequest
from savora_ai.schemas.nutrients_v2 import Nutrient
from savora_backend.ai.gateway import AiGateway
from savora_backend.core.meal_plans.authority import capture_binding, digest, validate_binding
from savora_backend.core.meal_plans.entity import MealPlanEntity, MealPlanJobStatus
from savora_backend.core.meal_plans.mapper import apply_week_result, copy_slot, slot_entity
from savora_backend.core.meal_plans.repository import MealPlanRepository
from savora_backend.core.nutrition_profiles.mapper import to_planning_profile
from savora_backend.core.nutrition_profiles.repository import ProfileRepository
from savora_backend.database import get_session_factory

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Any]
PLAN_FAILED_MESSAGE = "We could not generate this plan. Please try again."
SWAP_FAILED_MESSAGE = "We could not complete this swap. Your plan is unchanged; please try again."
RESTARTED_MESSAGE = "The server restarted before this finished. Please try again."
VERIFYING_MESSAGE = "Independently verifying the swap against your saved week"
PROFILE_CHANGED_MESSAGE = "Your profile or targets changed while this ran. Generate a new plan."
AUTHORITY_CHANGED_MESSAGE = (
    "Your saved plan or its sources changed. Refresh and generate a new plan."
)
ProofMode = Literal["required", "record", "off"]
# A proof that is not VALID refuses the swap in "required" mode (section 4.4: store a
# substitution only when it is verified); the user-facing reason per decision.
_PROOF_REFUSED = {
    "REJECTED": (
        MealPlanJobStatus.INFEASIBLE,
        "The independent check rejected this swap against your saved week; pick another meal.",
    ),
    "INSUFFICIENT_DATA": (
        MealPlanJobStatus.INSUFFICIENT_DATA,
        "The independent check is missing facts for this meal; pick another meal.",
    ),
    "TIMEOUT": (
        MealPlanJobStatus.TIMEOUT,
        "The independent check ran out of time; please try again.",
    ),
    "ADMISSION_FAILED": (
        MealPlanJobStatus.FAILED,
        "The independent check could not load your saved week; please try again.",
    ),
}

_background_tasks: set[asyncio.Task[None]] = set()


def track_background_task(coro: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def wait_for_background_tasks() -> None:
    if _background_tasks:
        await asyncio.gather(*list(_background_tasks), return_exceptions=True)


async def mark_stale_generating_jobs_failed(session_factory: SessionFactory | None = None) -> int:
    """On startup, mark any plans or substitutions left GENERATING as FAILED."""
    factory = session_factory or get_session_factory()
    async with factory() as session, session.begin():
        repo = MealPlanRepository(session)
        stale = [*await repo.stale_plans(), *await repo.stale_substitutions()]
        for row in stale:
            row.status = MealPlanJobStatus.FAILED.value
            row.message = RESTARTED_MESSAGE
        await session.flush()
        return len(stale)


async def run_plan_week_job(
    *,
    plan_id: UUID,
    user_id: UUID,
    planning_profile: PlanningProfile,
    week_start: date,
    gateway: AiGateway,
    session_factory: SessionFactory,
    target_snapshot: dict[str, Any],
) -> None:
    try:
        week = await gateway.plan_week(
            planning_profile, week_id=str(plan_id), start_date=week_start
        )
        async with session_factory() as session, session.begin():
            repo = MealPlanRepository(session)
            profiles = ProfileRepository(session)
            profile = await profiles.lock_by_user_id(user_id)
            plan = await repo.get_owned_plan(plan_id, user_id, lock=True)
            if plan is None or plan.status != MealPlanJobStatus.GENERATING.value:
                return
            snapshot = (
                None
                if profile is None
                else await profiles.get_latest_nutrition(user_id, profile.version, lock=True)
            )
            if (
                profile is None
                or snapshot is None
                or to_planning_profile(profile, snapshot) != planning_profile
                or digest(snapshot.targets) != digest(target_snapshot)
            ):
                plan.status, plan.message = MealPlanJobStatus.FAILED.value, PROFILE_CHANGED_MESSAGE
                return
            if (
                week.profile_id != str(user_id)
                or week.profile_version != profile.version
                or week.catalogue_version != plan.catalogue_version
                or week.start_date != week_start.isoformat()
            ):
                plan.status, plan.message = (
                    MealPlanJobStatus.FAILED.value,
                    AUTHORITY_CHANGED_MESSAGE,
                )
                return
            apply_week_result(plan, week)
            if week.status is PlanStatus.FEASIBLE:  # only a complete solver-feasible week is stored
                plan.source_binding = capture_binding(
                    plan,
                    week.meals,
                    bundle=gateway.bundle,
                    profile=planning_profile,
                    targets=target_snapshot,
                )
                await repo.clear_current_for_user(user_id)
                plan.is_current = True
                await repo.add_slots([slot_entity(plan.id, m) for m in week.meals])
    except Exception:
        logger.exception("Plan generation job %s failed", plan_id)
        async with session_factory() as session, session.begin():
            plan = await MealPlanRepository(session).get_owned_plan(plan_id, user_id)
            if plan is not None and plan.status == MealPlanJobStatus.GENERATING.value:
                plan.status = MealPlanJobStatus.FAILED.value
                plan.message = PLAN_FAILED_MESSAGE


async def run_substitute_job(
    *,
    substitution_id: UUID,
    from_plan_id: UUID,
    user_id: UUID,
    planning_profile: PlanningProfile,
    current_options: dict[str, str],
    slot_id: str,
    week_start: date,
    exclude_combination_ids: list[str],
    replacement_combination_id: str | None,
    preference: CravingRequest | None,
    gateway: AiGateway,
    session_factory: SessionFactory,
    expected_binding: dict[str, Any],
    from_revision: int = 1,
    proof_mode: ProofMode = "off",
) -> None:
    try:
        swapped = await gateway.substitute(
            planning_profile,
            current=current_options,
            slot=slot_id,
            week_id=f"{from_plan_id}-sub-{substitution_id}",
            start_date=week_start,
            exclude_combination_ids=exclude_combination_ids,
            replacement_combination_id=replacement_combination_id,
            preference=preference,
        )
        new_meal = next((m for m in swapped.meals if m.slot_id == slot_id), None)
        if swapped.status is PlanStatus.FEASIBLE and (
            swapped.profile_id != str(user_id)
            or swapped.profile_version != planning_profile.profile_version
            or swapped.catalogue_version != expected_binding["identity"]["catalogueVersion"]
            or swapped.start_date != week_start.isoformat()
            or len(swapped.meals) != 21
            or {m.slot_id for m in swapped.meals} != set(current_options)
            or any(
                m.option_id != current_options[m.slot_id]
                for m in swapped.meals
                if m.slot_id != slot_id
            )
        ):
            raise ValueError("Swap changed its bound profile, release or locked slots")
        proof: SwapProof | None = None
        if proof_mode != "off" and new_meal is not None and swapped.status is PlanStatus.FEASIBLE:
            async with session_factory() as session, session.begin():
                sub = await MealPlanRepository(session).get_owned_substitution(
                    substitution_id, user_id
                )
                if sub is not None and sub.status == MealPlanJobStatus.GENERATING.value:
                    sub.message = VERIFYING_MESSAGE
            proof = await gateway.prove_swap(
                planning_profile,
                saved=current_options,
                slot=slot_id,
                replacement_option_id=new_meal.option_id,
                plan_id=str(from_plan_id),
                revision=from_revision,
                owner_id=str(user_id),
                start_date=week_start,
                calculator_payload=expected_binding["targetSnapshot"],
            )
        async with session_factory() as session, session.begin():
            repo = MealPlanRepository(session)
            profiles = ProfileRepository(session)
            # All profile writers use this same lock. Never hold it during AI/proof work.
            profile = await profiles.lock_by_user_id(user_id)
            sub = await repo.get_owned_substitution(substitution_id, user_id, lock=True)
            parent = await repo.get_owned_plan(from_plan_id, user_id, lock=True)
            if sub is None or sub.status != MealPlanJobStatus.GENERATING.value:
                return
            snapshot = (
                None
                if profile is None
                else await profiles.get_latest_nutrition(user_id, profile.version, lock=True)
            )
            if (
                profile is None
                or snapshot is None
                or to_planning_profile(profile, snapshot) != planning_profile
            ):
                sub.status, sub.message = MealPlanJobStatus.FAILED.value, PROFILE_CHANGED_MESSAGE
                return
            if (
                parent is None
                or not parent.is_current
                or parent.revision != from_revision
                or parent.status != MealPlanJobStatus.FEASIBLE.value
                or parent.profile_version != profile.version
                or sub.from_plan_id != parent.id
                or sub.slot_id != slot_id
                or parent.source_binding != expected_binding
            ):
                sub.status, sub.message = MealPlanJobStatus.FAILED.value, AUTHORITY_CHANGED_MESSAGE
                return
            parent_slots = await repo.get_slots(parent.id, lock=True)
            try:
                validate_binding(
                    parent,
                    parent_slots,
                    bundle=gateway.bundle,
                    profile=planning_profile,
                    targets=snapshot.targets,
                )
                if {s.slot_id: s.option_id for s in parent_slots} != current_options:
                    raise ValueError("Saved options changed")
                target = next(s for s in parent_slots if s.slot_id == slot_id)
                if digest(sub.before_snapshot) != digest(target.snapshot):
                    raise ValueError("Target permission/payload changed")
            except (ValueError, StopIteration):
                sub.status, sub.message = MealPlanJobStatus.FAILED.value, AUTHORITY_CHANGED_MESSAGE
                return
            sub.status = swapped.status.value
            sub.message = swapped.message
            proof_valid = bool(
                proof
                and proof.status == "VALID"
                and proof.verified
                and proof.certificate_digest
                and len(proof.changed_day_totals) == 7
                and {t.nutrient for t in proof.changed_day_totals} == set(get_args(Nutrient))
                and all(t.complete and t.value is not None for t in proof.changed_day_totals)
            )
            if proof is not None and proof.verified and not proof_valid:
                proof = proof.model_copy(update={"verified": False})
            if proof is not None:
                sub.proof = proof.model_dump(mode="json", by_alias=True)
                sub.proof_certificate_digest = proof.certificate_digest
            if swapped.status is not PlanStatus.FEASIBLE:
                return  # the saved plan is untouched; the message says why
            if new_meal is None:
                sub.status = MealPlanJobStatus.FAILED.value
                sub.message = SWAP_FAILED_MESSAGE
                return
            if not proof_valid and proof_mode == "required":
                refused, message = _PROOF_REFUSED.get(
                    proof.status if proof else "MISSING",
                    (MealPlanJobStatus.FAILED, SWAP_FAILED_MESSAGE),
                )
                sub.status, sub.message = refused.value, message
                return
            if proof_valid:
                sub.message = f"{swapped.message} Swap independently verified (compact B1)."
            # A new revision: the 20 locked slots copied verbatim, the new slot added.
            await repo.clear_current_for_user(user_id)
            revision = max(
                await repo.next_revision_for_week(user_id, parent.week_start), parent.revision + 1
            )
            new_plan = MealPlanEntity(
                user_id=user_id,
                week_start=parent.week_start,
                revision=revision,
                profile_version=parent.profile_version,
                parent_plan_id=parent.id,
                is_current=True,
            )
            apply_week_result(new_plan, swapped)
            await repo.create_plan(new_plan)
            saved_slots = [
                slot_entity(new_plan.id, new_meal)
                if s.slot_id == slot_id
                else copy_slot(new_plan.id, s)
                for s in parent_slots
            ]
            new_plan.source_binding = capture_binding(
                new_plan,
                [PlannedMeal.model_validate_json(json.dumps(s.snapshot)) for s in saved_slots],
                bundle=gateway.bundle,
                profile=planning_profile,
                targets=snapshot.targets,
            )
            await repo.add_slots(saved_slots)
            sub.to_plan_id = new_plan.id
            sub.after_snapshot = new_meal.model_dump(mode="json", by_alias=True)
    except Exception:
        logger.exception("Substitution job %s failed", substitution_id)
        async with session_factory() as session, session.begin():
            sub = await MealPlanRepository(session).get_owned_substitution(substitution_id, user_id)
            if sub is not None and sub.status == MealPlanJobStatus.GENERATING.value:
                sub.status = MealPlanJobStatus.FAILED.value
                sub.message = SWAP_FAILED_MESSAGE
