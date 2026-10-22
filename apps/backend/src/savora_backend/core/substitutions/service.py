"""Saved-plan meal substitution (section 4.4).

1. The user's optional words are parsed by the NLU into a validated preference.
2. `replacement_options`: retrieval, the rule screen and the Transformer rank the eligible
   meals for the slot (nothing stored).
3. `start_substitution`: the chosen (or best) meal is validated by the weekly CSP with the
   other 20 slots locked in a background job; only a FEASIBLE week becomes a new revision,
   with before/after snapshots. The saved plan is never modified.
"""

import asyncio
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from savora_ai.core.craving_nlu import CravingParser, parse_craving
from savora_ai.schemas.craving import CravingRequest
from savora_backend.ai.gateway import AiGateway
from savora_backend.config import get_settings
from savora_backend.core.cravings import CravingParseMeta, parse_meta
from savora_backend.core.meal_plans.dto import (
    CreateSubstitutionAcceptedDto,
    CreateSubstitutionRequest,
    ReplacementOptionsDto,
    ReplacementOptionsRequest,
    SubstitutionDetailDto,
)
from savora_backend.core.meal_plans.entity import (
    MealPlanEntity,
    MealPlanJobStatus,
    MealPlanSlotEntity,
    MealPlanSubstitutionEntity,
)
from savora_backend.core.meal_plans.jobs import (
    SessionFactory,
    run_substitute_job,
    track_background_task,
)
from savora_backend.core.meal_plans.mapper import to_substitution_dto
from savora_backend.core.meal_plans.repository import MealPlanRepository
from savora_backend.core.meal_plans.service import JOB_RUNNING, conflict, not_found
from savora_backend.core.nutrition_profiles import (
    ProfileRepository,
    UserProfileEntity,
    to_planning_profile,
)
from savora_backend.database import get_session_factory

SOURCE = "substitutions"


class SubstitutionService:
    def __init__(
        self,
        session: AsyncSession,
        gateway: AiGateway,
        parser: CravingParser | None = None,
        job_session_factory: SessionFactory | None = None,
    ) -> None:
        self._session = session
        self._plans = MealPlanRepository(session)
        self._profiles = ProfileRepository(session)
        self._gateway = gateway
        self._parser = parser
        self._job_session_factory = job_session_factory

    async def _swappable(
        self, user_id: UUID, plan_id: UUID, slot_id: str, *, lock: bool
    ) -> tuple[MealPlanEntity, UserProfileEntity, list[MealPlanSlotEntity]]:
        profile = await (
            self._profiles.lock_by_user_id(user_id)
            if lock
            else self._profiles.get_by_user_id(user_id)
        )
        plan = await self._plans.get_owned_plan(plan_id, user_id)
        if plan is None:
            raise not_found("Meal plan not found", SOURCE)
        if not plan.is_current or plan.status != MealPlanJobStatus.FEASIBLE.value:
            raise conflict("Swaps work only on your current, ready plan.", SOURCE)
        # A swap must not lock meals that no longer fit the profile (section 4.4).
        if profile is None or profile.version != plan.profile_version:
            raise conflict(
                "Your profile changed since this plan was made; generate a new plan.", SOURCE
            )
        slots = await self._plans.get_slots(plan.id)
        if not any(s.slot_id == slot_id for s in slots):
            raise not_found(f"Slot {slot_id} is not on this plan", SOURCE)
        return plan, profile, slots

    async def _preference(
        self, text: str | None
    ) -> tuple[CravingParseMeta | None, CravingRequest | None]:
        """The validated request the words were parsed into; None when they carry nothing."""
        if text is None or not text.strip() or self._parser is None:
            return None, None
        parsed = await asyncio.to_thread(parse_craving, text, parser=self._parser)
        req = parsed.request
        useful = bool(req.cuisine_ids or req.flavor_tags or req.excluded_ingredient_ids)
        return parse_meta(parsed), req if useful else None

    async def replacement_options(
        self, user_id: UUID, plan_id: UUID, slot_id: str, body: ReplacementOptionsRequest
    ) -> ReplacementOptionsDto:
        _, profile, slots = await self._swappable(user_id, plan_id, slot_id, lock=False)
        meta, preference = await self._preference(body.preference_text)
        try:
            result = await self._gateway.replacements(
                to_planning_profile(profile),
                current={s.slot_id: s.option_id for s in slots},
                slot=slot_id,
                preference=preference,
                exclude_combination_ids=body.exclude_combination_ids,
            )
        except ValueError as exc:  # saved meals no longer in the catalogue or profile
            raise conflict(f"{exc}", SOURCE) from exc
        return ReplacementOptionsDto(parse=meta, result=result)

    async def start_substitution(
        self, user_id: UUID, plan_id: UUID, body: CreateSubstitutionRequest
    ) -> CreateSubstitutionAcceptedDto:
        plan, profile, slots = await self._swappable(user_id, plan_id, body.slot_id, lock=True)
        if body.expected_revision != plan.revision:
            raise conflict(
                f"This plan changed (revision {plan.revision}); refresh and try again.", SOURCE
            )
        if await self._plans.has_generating_job(user_id):
            raise conflict(JOB_RUNNING, SOURCE)
        _, preference = (
            (None, None)
            if body.replacement_combination_id
            else await self._preference(body.preference_text)
        )
        target = next(s for s in slots if s.slot_id == body.slot_id)
        sub = MealPlanSubstitutionEntity(
            user_id=user_id,
            from_plan_id=plan.id,
            slot_id=body.slot_id,
            status=MealPlanJobStatus.GENERATING.value,
            message="Checking the week with your other meals locked",
            before_snapshot=dict(target.snapshot),
            excluded_combination_ids=list(body.exclude_combination_ids),
            replacement_combination_id=body.replacement_combination_id,
            preference=preference.model_dump(mode="json", by_alias=True) if preference else None,
        )
        try:
            await self._plans.create_substitution(sub)
        except IntegrityError as exc:
            raise conflict(JOB_RUNNING, SOURCE) from exc
        snapshot = await self._profiles.get_latest_nutrition(user_id, profile.version)
        planning_profile = to_planning_profile(profile, snapshot)
        await self._session.commit()  # the job must see the committed row
        track_background_task(
            run_substitute_job(
                substitution_id=sub.id,
                from_plan_id=plan.id,
                user_id=user_id,
                planning_profile=planning_profile,
                current_options={s.slot_id: s.option_id for s in slots},
                slot_id=body.slot_id,
                week_start=plan.week_start,
                exclude_combination_ids=list(body.exclude_combination_ids),
                replacement_combination_id=body.replacement_combination_id,
                preference=preference,
                gateway=self._gateway,
                session_factory=self._job_session_factory or get_session_factory(),
                from_revision=plan.revision,
                proof_mode=get_settings().swap_proof_mode,
            )
        )
        return CreateSubstitutionAcceptedDto(substitution_id=sub.id)

    async def get_substitution(self, user_id: UUID, substitution_id: UUID) -> SubstitutionDetailDto:
        sub = await self._plans.get_owned_substitution(substitution_id, user_id)
        if sub is None:
            raise not_found("Substitution not found", SOURCE)
        return to_substitution_dto(sub)
