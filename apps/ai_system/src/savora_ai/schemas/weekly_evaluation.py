"""Computed supplied-trial evidence. No weekly CSP outcome or search proof."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from savora_ai.core.reasoning.week_checks import _assess_week, _compile_week, _prepare_options
from savora_ai.schemas.candidates import CandidateRecipeFacts
from savora_ai.schemas.daily import _DailyModel
from savora_ai.schemas.daily_solver import DailyAssignmentEvaluation, DailyOptionDecision
from savora_ai.schemas.filtering import FilterCandidatesResult, _evidence_union
from savora_ai.schemas.knowledge import EvidenceReference, RuleReference, _NonBlank
from savora_ai.schemas.knowledge_base import _ContentDigest
from savora_ai.schemas.reasoning import RuleStatus, RuleTrace
from savora_ai.schemas.weekly import (
    ExpectedWeekCheckManifest,
    WeekDayReference,
    WeekFact,
    WeeklyTrial,
)


class WeeklyDayEvaluation(_DailyModel):
    day: WeekDayReference
    manifest_digest: _ContentDigest
    evaluation: DailyAssignmentEvaluation


class WeekRuleExplanation(_DailyModel):
    manifest_digest: _ContentDigest
    trial_digest: _ContentDigest
    rule_reference: RuleReference
    status: RuleStatus
    reason: _NonBlank
    evidence: tuple[EvidenceReference, ...]


def _week_explanations(
    manifest: ExpectedWeekCheckManifest, trial: WeeklyTrial, trace: RuleTrace
) -> tuple[WeekRuleExplanation, ...]:
    return tuple(
        WeekRuleExplanation(
            manifest_digest=manifest.content_digest,
            trial_digest=trial.content_digest,
            rule_reference=RuleReference(rule_id=e.rule.rule_id, version=e.rule.version),
            status=e.status,
            reason=e.reason,
            evidence=_evidence_union(e),
        )
        for e in trace.evaluations
    )


class WeeklyTrialEvaluation(_DailyModel):
    schema_version: Literal["weekly-trial-evaluation.v1"] = "weekly-trial-evaluation.v1"
    evaluator_policy_version: Literal["synthetic-week-evaluation.v1"] = (
        "synthetic-week-evaluation.v1"
    )
    derivation_policy_version: Literal["synthetic-week-fact-derivation.v1"] = (
        "synthetic-week-fact-derivation.v1"
    )
    plan_feasibility: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    search_completeness: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    manifest: ExpectedWeekCheckManifest
    candidates: tuple[CandidateRecipeFacts, ...]
    trial: WeeklyTrial
    recipes: FilterCandidatesResult
    options: Annotated[tuple[DailyOptionDecision, ...], Field(max_length=21)]
    days: Annotated[tuple[WeeklyDayEvaluation, ...], Field(min_length=7, max_length=7)]
    facts: Annotated[tuple[WeekFact, ...], Field(min_length=3, max_length=3)]
    trace: RuleTrace
    week_status: RuleStatus
    status: RuleStatus
    explanations: tuple[WeekRuleExplanation, ...]

    @model_validator(mode="after")
    def validate_computation(self) -> Self:
        # Recompute from retained source/candidates, never from caller PASS declarations.
        # This intentionally repeats public preparation at the output trust boundary.
        recipes, options = _prepare_options(self.manifest, self.candidates, self.trial)
        if recipes != self.recipes or options != self.options:
            raise ValueError("weekly prerequisites differ from independently recomputed inputs")
        days, facts, trace, week_status, status = _assess_week(
            _compile_week(self.manifest), self.trial, options
        )
        expected_days = tuple(
            WeeklyDayEvaluation(day=d, manifest_digest=h, evaluation=e) for d, h, e in days
        )
        if self.days != expected_days or self.facts != facts or self.trace != trace:
            raise ValueError(
                "weekly facts/DAY/WEEK evaluations contradict exact bound computations"
            )
        if self.week_status is not week_status or self.status is not status:
            raise ValueError("weekly trial status contradicts complete DAY/WEEK aggregation")
        if self.explanations != _week_explanations(self.manifest, self.trial, trace):
            raise ValueError("weekly explanations differ from exact complete evaluations")
        _evidence_union(self)
        return self
