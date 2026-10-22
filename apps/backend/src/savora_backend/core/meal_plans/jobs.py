"""In-process background jobs for plan generation and substitution (spec section 2 item 3).

No queue or Redis (AGENTS.md): a job is an `asyncio` task running the pure pipeline in a
thread, with its state persisted on the plan/substitution row so clients poll it. Rows
left GENERATING by a restart are marked FAILED at startup. A failure stores a fixed,
user-facing message; the exception itself goes to the logs only.
"""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from datetime import date
from typing import Any, Literal
from uuid import UUID

from savora_ai.core.pipelines import PlanningProfile, PlanStatus, SwapProof
from savora_ai.schemas.craving import CravingRequest
from savora_backend.ai.gateway import AiGateway
from savora_backend.core.meal_plans.entity import MealPlanEntity, MealPlanJobStatus
from savora_backend.core.meal_plans.mapper import apply_week_result, copy_slot, slot_entity
from savora_backend.core.meal_plans.repository import MealPlanRepository
from savora_backend.database import get_session_factory

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Any]
PLAN_FAILED_MESSAGE = "We could not generate this plan. Please try again."
SWAP_FAILED_MESSAGE = "We could not complete this swap. Your plan is unchanged; please try again."
RESTARTED_MESSAGE = "The server restarted before this finished. Please try again."
VERIFYING_MESSAGE = "Independently verifying the swap against your saved week"
ProofMode = Literal["required", "record", "off"]
# A proof that is not VALID refuses the swap in "required" mode (section 4.4: store a
# substitution only when it is verified); the user-facing reason per decision.
_PROOF_REFUSED = {
    "REJECTED": (
        MealPlanJobStatus.INFEASIBLE,
        "The independent check rejected this swap against your saved week; "
        "pick another meal.",
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
) -> None:
    try:
        week = await gateway.plan_week(
            planning_profile, week_id=str(plan_id), start_date=week_start
        )
        async with session_factory() as session, session.begin():
            repo = MealPlanRepository(session)
            plan = await repo.get_by_id(plan_id)
            if plan is None:
                return
            apply_week_result(plan, week)
            if week.status is PlanStatus.FEASIBLE:  # only a fully verified week is stored
                await repo.clear_current_for_user(user_id)
                plan.is_current = True
                await repo.add_slots([slot_entity(plan.id, m) for m in week.meals])
    except Exception:
        logger.exception("Plan generation job %s failed", plan_id)
        async with session_factory() as session, session.begin():
            plan = await MealPlanRepository(session).get_by_id(plan_id)
            if plan is not None:
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
        proof: SwapProof | None = None
        if proof_mode != "off" and new_meal is not None and swapped.status is PlanStatus.FEASIBLE:
            async with session_factory() as session, session.begin():
                sub = await MealPlanRepository(session).get_substitution_by_id(substitution_id)
                if sub is not None:
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
            )
        async with session_factory() as session, session.begin():
            repo = MealPlanRepository(session)
            sub = await repo.get_substitution_by_id(substitution_id)
            parent = await repo.get_by_id(from_plan_id)
            if sub is None or parent is None:
                return
            sub.status = swapped.status.value
            sub.message = swapped.message
            if proof is not None:
                sub.proof = proof.model_dump(mode="json", by_alias=True)
                sub.proof_certificate_digest = proof.certificate_digest
            if swapped.status is not PlanStatus.FEASIBLE:
                return  # the saved plan is untouched; the message says why
            if new_meal is None:
                sub.status = MealPlanJobStatus.FAILED.value
                sub.message = SWAP_FAILED_MESSAGE
                return
            if proof is not None and not proof.verified and proof_mode == "required":
                refused, message = _PROOF_REFUSED.get(
                    proof.status, (MealPlanJobStatus.FAILED, SWAP_FAILED_MESSAGE)
                )
                sub.status, sub.message = refused.value, message
                return
            if proof is not None and proof.verified:
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
            parent_slots = await repo.get_slots(parent.id)
            await repo.add_slots(
                [
                    slot_entity(new_plan.id, new_meal)
                    if s.slot_id == slot_id
                    else copy_slot(new_plan.id, s)
                    for s in parent_slots
                ]
            )
            sub.to_plan_id = new_plan.id
            sub.after_snapshot = new_meal.model_dump(mode="json", by_alias=True)
    except Exception:
        logger.exception("Substitution job %s failed", substitution_id)
        async with session_factory() as session, session.begin():
            sub = await MealPlanRepository(session).get_substitution_by_id(substitution_id)
            if sub is not None:
                sub.status = MealPlanJobStatus.FAILED.value
                sub.message = SWAP_FAILED_MESSAGE
