"""Authoritative synthetic WEEK manifest and complete supplied-trial evaluation."""

from collections.abc import Callable
from math import isfinite
from time import monotonic
from typing import Self

from pydantic import model_validator

from savora_ai.core.reasoning.filtering import _FilterRequest
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.manifest import _KnowledgeContextRequest, _mandatory_checks, _reject
from savora_ai.core.reasoning.week_checks import (
    _assess_week,
    _compile_week,
    _prepare_options,
    _week_derivation_evidence,
)
from savora_ai.schemas.candidates import CandidateRecipeFacts, RuleContext
from savora_ai.schemas.filtering import _evidence_union
from savora_ai.schemas.knowledge import RuleScope
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot
from savora_ai.schemas.weekly import (
    ExpectedWeekCheckManifest,
    WeeklyPlanningRequest,
    WeeklySearchLimits,
    WeeklySourceSnapshot,
    WeeklyTrial,
    _bind_trial,
)
from savora_ai.schemas.weekly_evaluation import (
    WeeklyDayEvaluation,
    WeeklyTrialEvaluation,
    _week_explanations,
)
from savora_ai.schemas.weekly_search import WeeklySolverTiming
from savora_ai.schemas.weekly_solver import ComputedWeeklySolveResult


class _WeekRequest(_KnowledgeContextRequest):
    request: WeeklyPlanningRequest
    sources: WeeklySourceSnapshot

    @model_validator(mode="after")
    def validate_independent_sources(self) -> Self:
        if self.request.source.content_digest != self.sources.content_digest or (
            self.sources.daily_source.context.content_digest != self.context.content_digest
        ):
            raise ValueError("weekly request differs from independently selected source/context")
        _evidence_union((self, _week_derivation_evidence()))
        return self


class _WeekEvaluationRequest(_WeekRequest, _FilterRequest):
    trial: WeeklyTrial
    manifest: ExpectedWeekCheckManifest | None

    @model_validator(mode="after")
    def validate_trial(self) -> Self:
        _bind_trial(self.request, self.trial)
        return self


def _manifest(validated: _WeekRequest) -> ExpectedWeekCheckManifest:
    kb = build_knowledge_snapshot(
        validated.kb, expected_digest=validated.context.expected_kb_digest
    )
    rules = _mandatory_checks(kb, validated.context)
    return ExpectedWeekCheckManifest.build(
        dict(
            request=validated.request,
            knowledge=kb,
            required_checks=tuple(r for r in rules if r.scope is RuleScope.WEEK),
            day_checks=tuple(r for r in rules if r.scope is RuleScope.DAY),
        )
    )


def build_week_check_manifest(
    request: WeeklyPlanningRequest,
    *,
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: WeeklySourceSnapshot,
) -> ExpectedWeekCheckManifest:
    """Accept independent inputs and select the complete supported DAY/WEEK definitions."""
    return _manifest(
        _WeekRequest.model_validate(
            dict(request=request, kb=knowledge, context=context, sources=sources)
        )
    )


def evaluate_weekly_trial(
    request: WeeklyPlanningRequest,
    trial: WeeklyTrial,
    *,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: WeeklySourceSnapshot,
    manifest: ExpectedWeekCheckManifest | None = None,
) -> WeeklyTrialEvaluation:
    """Evaluate exactly the supplied 21 choices. No selection, search or feasibility claim."""
    validated = _WeekEvaluationRequest.model_validate(
        dict(
            request=request,
            trial=trial,
            candidates=candidates,
            kb=knowledge,
            context=context,
            sources=sources,
            manifest=manifest,
        )
    )
    accepted = _manifest(validated)
    if (
        validated.manifest is not None
        and validated.manifest.content_digest != accepted.content_digest
    ):
        _reject("supplied manifest differs from authoritative complete weekly manifest")
    recipes, options = _prepare_options(accepted, validated.candidates, validated.trial)
    days, facts, trace, week_status, status = _assess_week(
        _compile_week(accepted), validated.trial, options
    )
    return WeeklyTrialEvaluation(
        manifest=accepted,
        candidates=validated.candidates,
        trial=validated.trial,
        recipes=recipes,
        options=options,
        days=tuple(WeeklyDayEvaluation(day=d, manifest_digest=h, evaluation=e) for d, h, e in days),
        facts=facts,
        trace=trace,
        week_status=week_status,
        status=status,
        explanations=_week_explanations(accepted, validated.trial, trace),
    )


class _WeekSolveRequest(_WeekRequest, _FilterRequest):
    limits: WeeklySearchLimits


def solve_weekly_plan(
    request: WeeklyPlanningRequest,
    *,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: WeeklySourceSnapshot,
    limits: WeeklySearchLimits | None = None,
    clock: Callable[[], float] = monotonic,
) -> ComputedWeeklySolveResult:
    """First verified FIXED 21-slot witness, or conservative bounded-search outcome.

    Synthetic only. Deadlines are absolute cooperative clock readings. Validation
    and prerequisites already in flight cannot be interrupted by this interface.
    """
    from savora_ai.core.reasoning.facts import _validated_fact_index
    from savora_ai.core.reasoning.manifest import _ManifestRequest
    from savora_ai.core.reasoning.weekly_search import _execute

    last: float | None = None

    def now() -> float:
        nonlocal last
        reading = clock()
        if type(reading) not in (int, float):
            raise ValueError("weekly clock must return finite monotonic numbers")
        try:
            value = float(reading)
        except OverflowError as error:
            raise ValueError("weekly clock must return finite monotonic numbers") from error
        if not isfinite(value) or (last is not None and value < last):
            raise ValueError("weekly clock must return finite monotonic numbers")
        last = value
        return value

    started = now()
    validated = _WeekSolveRequest.model_validate(
        dict(
            request=request,
            candidates=candidates,
            kb=knowledge,
            context=context,
            sources=sources,
            limits=WeeklySearchLimits() if limits is None else limits,
        )
    )
    # Structural/release errors remain errors even with zero evaluation budgets.
    for candidate in validated.candidates:
        _ManifestRequest(kb=validated.kb, context=validated.context, candidate=candidate)
        _validated_fact_index(candidate.facts)
    _validated_fact_index(validated.context.facts)
    manifest = _manifest(validated)
    run = _execute(manifest, validated.candidates, validated.limits, clock=now)
    return ComputedWeeklySolveResult.model_validate(
        dict(
            manifest=manifest,
            candidates=validated.candidates,
            limits=validated.limits,
            certificate=run.certificate,
            outcome=run.outcome,
            witness=run.witness,
            diagnostics=run.diagnostics,
            timing=WeeklySolverTiming(
                preparation_seconds=run.prepared_at - started,
                search_seconds=run.finished_at - run.prepared_at,
                output_validation_seconds=0.0,
            ),
        ),
        context={"weekly_clock": now, "validation_started": now()},
    )
