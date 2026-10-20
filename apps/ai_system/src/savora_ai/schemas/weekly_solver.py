"""Strict computed weekly CSP result; verify using the acyclic bounded replay kernel."""

from collections.abc import Callable
from typing import Annotated, Literal, Self, cast

from pydantic import Field, ValidationInfo, model_validator

from savora_ai.schemas.candidates import CandidateRecipeFacts
from savora_ai.schemas.daily import DailyOutcome, _DailyModel
from savora_ai.schemas.weekly import (
    ExpectedWeekCheckManifest,
    WeeklyConstraintDiagnostic,
    WeeklySearchLimits,
)
from savora_ai.schemas.weekly_search import (
    WeeklySearchCertificate,
    WeeklySolverTiming,
    WeeklyWitness,
)


class ComputedWeeklySolveResult(_DailyModel):
    schema_version: Literal["computed-weekly-solve-result.v1"] = "computed-weekly-solve-result.v1"
    search_policy_version: Literal["synthetic-chronological-weekly-search.v1"] = (
        "synthetic-chronological-weekly-search.v1"
    )
    criterion: Literal["FIRST_FEASIBLE"] = "FIRST_FEASIBLE"
    manifest: ExpectedWeekCheckManifest
    candidates: tuple[CandidateRecipeFacts, ...]
    limits: WeeklySearchLimits
    certificate: WeeklySearchCertificate
    outcome: DailyOutcome
    witness: WeeklyWitness | None
    diagnostics: Annotated[tuple[WeeklyConstraintDiagnostic, ...], Field(max_length=1000)]
    timing: WeeklySolverTiming

    @model_validator(mode="after")
    def verify_coverage(self, info: ValidationInfo) -> Self:
        from savora_ai.core.reasoning.facts import _validated_fact_index
        from savora_ai.core.reasoning.filtering import _FilterRequest
        from savora_ai.core.reasoning.manifest import _ManifestRequest
        from savora_ai.core.reasoning.weekly_search import _execute

        if self.certificate.deadline_checkpoint is not None and self.limits.deadline is None:
            raise ValueError("weekly deadline certificate requires a declared deadline")

        request = _FilterRequest(
            kb=self.manifest.knowledge,
            context=self.manifest.request.source.daily_source.context,
            candidates=self.candidates,
        )
        for candidate in request.candidates:
            _ManifestRequest(kb=request.kb, context=request.context, candidate=candidate)
            _validated_fact_index(candidate.facts)
        _validated_fact_index(request.context.facts)

        clock = info.context.get("weekly_clock") if isinstance(info.context, dict) else None
        clock = cast(Callable[[], float] | None, clock)
        started = (
            cast(float, info.context["validation_started"])
            if callable(clock)
            and isinstance(info.context, dict)
            and "validation_started" in info.context
            else clock()
            if callable(clock)
            else None
        )
        replay = _execute(
            self.manifest,
            self.candidates,
            self.limits,
            stop_at=self.certificate.deadline_checkpoint,
        )
        if replay.certificate != self.certificate:
            raise ValueError("weekly coverage/frontier/counters differ from authoritative replay")
        if replay.diagnostics != self.diagnostics:
            raise ValueError("weekly diagnostics differ from bounded authoritative evaluations")
        observed_timeout = self.timing.validation_deadline_reached
        expired_observation = (
            self.limits.deadline is not None
            and self.timing.validation_finished_at is not None
            and self.timing.validation_finished_at >= self.limits.deadline
        )
        if observed_timeout != expired_observation:
            raise ValueError("validation deadline claim requires an expired clock observation")
        expected = DailyOutcome.TIMEOUT if observed_timeout else replay.outcome
        witness = None if observed_timeout else replay.witness
        if self.outcome is not expected or self.witness != witness:
            raise ValueError("weekly outcome/witness contradict exact verified search coverage")
        if callable(clock) and started is not None:
            finished = clock()
            expired = self.limits.deadline is not None and finished >= self.limits.deadline
            timing = WeeklySolverTiming(
                preparation_seconds=self.timing.preparation_seconds,
                search_seconds=self.timing.search_seconds,
                output_validation_seconds=finished - started,
                validation_finished_at=finished,
                validation_deadline_reached=expired,
            )
            # Derived values are strictly constructed after full replay. This never
            # accepts caller PASS records, unchecked models or a validation shortcut.
            object.__setattr__(self, "timing", timing)
            if expired:
                object.__setattr__(self, "outcome", DailyOutcome.TIMEOUT)
                object.__setattr__(self, "witness", None)
        return self
