"""UNVERIFIED real-data envelope fixture; not a production saved-plan authority adapter."""

from savora_ai.core.meal_composition.member2_adapter import evidence
from savora_ai.evals.real_catalogue_inputs import RealWeekInputs


def saved_fixture(inputs: RealWeekInputs):
    """Materialize fixed one-option domains as UNVERIFIED, never VERIFIED_AT_SAVE.

    This is an envelope fixture, not permission to persist a plan. Original and
    proposed complete weeks still need fresh independent B1 semantic checking.
    """
    from savora_ai.schemas.daily import AssignedMeal, DailyAssignment
    from savora_ai.schemas.daily_solver import DailyTrial, DailyTrialChoice
    from savora_ai.schemas.planned_swap import (
        SavedPlanMaterial,
        SavedPlanReference,
        SavedPlanSnapshot,
        SavedPlanVerificationRecord,
        SavedSlotPayload,
        SwapReference,
        SwapSlotIdentity,
        SyntheticTargetReference,
    )
    from savora_ai.schemas.weekly import (
        WeeklyAssignment,
        WeeklyDayAssignment,
        WeeklyTrial,
        WeeklyTrialChoice,
        _daily_request,
    )

    request, source, context = inputs.request, inputs.weekly, inputs.context
    days = []
    choices = []
    slots = []
    for day in request.days:
        if any(len(d.options) != 1 for d in day.domains):
            raise ValueError("envelope fixture requires exactly one fixed option per slot")
        daily = _daily_request(request, day)
        selected = tuple((d.slot, d.options[0]) for d in day.domains)
        trial = DailyTrial.build(
            dict(
                request_digest=daily.content_digest,
                choices=tuple(DailyTrialChoice(slot=s, option=o) for s, o in selected),
            )
        )
        assignment = DailyAssignment.build(
            dict(
                request_digest=daily.content_digest,
                day_id=day.day.day_id,
                source=source.expected_daily_source,
                context_digest=context.content_digest,
                slots=tuple(AssignedMeal(slot=s, option=o) for s, o in selected),
            )
        )
        days.append(WeeklyDayAssignment(day=day.day, trial=trial, assignment=assignment))
        for slot, ref in selected:
            option = inputs.options[ref.option_id]
            choices.append(WeeklyTrialChoice(day=day.day, slot=slot, option=ref))
            recipes = tuple(
                inputs.candidates[i]
                for i in sorted(
                    {p.recipe_snapshot.recipe_id for p in option.combination.components}
                )
            )
            slots.append(
                SavedSlotPayload(
                    identity=SwapSlotIdentity(day=day.day, slot=slot),
                    source=SwapReference(
                        record_id=source.source_id,
                        version=source.version,
                        content_digest=source.content_digest,
                    ),
                    option=option,
                    recipes=recipes,
                )
            )
    trial = WeeklyTrial.build(
        dict(
            request_digest=request.content_digest,
            week_id=request.week_id,
            week_version=request.week_version,
            start_date=request.start_date,
            choices=tuple(choices),
        )
    )
    assignment = WeeklyAssignment.build(
        dict(
            request_digest=request.content_digest,
            week_id=request.week_id,
            week_version=request.week_version,
            start_date=request.start_date,
            source=request.expected_source,
            daily_source=source.expected_daily_source,
            context_digest=context.content_digest,
            days=tuple(days),
        )
    )
    ev = (evidence(inputs.weekly.version, "unverified-envelope-fixture"),)
    snapshot = SavedPlanSnapshot.build(
        dict(
            plan_id="real-envelope-plan",
            snapshot_id="real-envelope-snapshot",
            version="1",
            original_request=request,
            original_sources=source,
            original_context=context,
            original_candidates=tuple(inputs.candidates.values()),
            original_trial=trial,
            original_assignment=assignment,
            slots=tuple(slots),
            target=SyntheticTargetReference(
                target_id="stand-in-no-nutrient-target",
                version="1",
                content_digest="e" * 64,
                evidence=ev,
            ),
            verification=SavedPlanVerificationRecord(
                status="UNVERIFIED",
                prior_protocol=None,
                prior_result=None,
                verification_policy="unverified-envelope-fixture.v1",
                evidence=ev,
            ),
            evidence=ev,
        )
    )
    return SavedPlanMaterial.build(
        dict(
            snapshot=snapshot,
            reference=SavedPlanReference(
                plan_id=snapshot.plan_id,
                effective_revision=1,
                snapshot_id=snapshot.snapshot_id,
                snapshot_version=snapshot.version,
                snapshot_digest=snapshot.content_digest,
            ),
        )
    )
