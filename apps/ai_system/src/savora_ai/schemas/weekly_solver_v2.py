"""Computed v2 boundary. Declaration certificates alone still authorize nothing.

Outcome, witness and verification work are derived by the independent checker on
every construction, Python revalidation and strict original-JSON ingress. A wire
round trip must match these computed fields exactly. No caller-supplied flag can
skip verification. Internal retained-source correctness is distinct from backend
authentication/independent source selection.
"""

from collections.abc import Callable
from typing import Annotated, Any, Literal, Self, cast

from pydantic import Field, ValidationInfo, model_validator

from savora_ai.schemas.candidates import CandidateRecipeFacts
from savora_ai.schemas.daily import DailyOutcome
from savora_ai.schemas.weekly import ExpectedWeekCheckManifest
from savora_ai.schemas.weekly_search import WeeklyWitness
from savora_ai.schemas.weekly_search_v2 import (
    WeeklyInterruptionV2,
    WeeklySearchCertificateV2,
    WeeklyWorkV2,
    _V2Model,
)


class WeeklyPreparationAccountingV2(_V2Model):
    """Physical work of one fresh session; logical reservations remain unchanged.

    Binding validation is charged inside each already reserved combination operation.
    Counts exclude repeated structural Pydantic validators. Existing certificate
    cache counters continue to describe search caches, not this preparation pool.
    """

    policy: Literal["synthetic-weekly-preparation-reuse.v2"] = (
        "synthetic-weekly-preparation-reuse.v2"
    )
    logical_candidate_assessments: Annotated[int, Field(ge=0, le=1_000_000)]
    physical_filter_calls: Annotated[int, Field(ge=0, le=1_000_000)]
    physical_candidate_assessments: Annotated[int, Field(ge=0, le=1_000_000)]
    reused_candidate_assessments: Annotated[int, Field(ge=0, le=1_000_000)]
    combination_evaluations: Annotated[int, Field(ge=0, le=1_000_000)]
    cache_validations: Annotated[int, Field(ge=0, le=1_000_000)]
    cache_hits: Annotated[int, Field(ge=0, le=1_000_000)]
    cache_misses: Annotated[int, Field(ge=0, le=1_000_000)]
    cache_evictions: Annotated[int, Field(ge=0, le=1_000_000)]
    cache_capacity: Annotated[int, Field(ge=0, le=1)]
    cache_entries: Annotated[int, Field(ge=0, le=1)]


class ComputedWeeklySolveResultV2(_V2Model):
    schema_version: Literal[
        "computed-weekly-solve-result.v2", "computed-weekly-nutrient-solve-result.v1"
    ] = "computed-weekly-solve-result.v2"
    search_policy_version: Literal[
        "synthetic-chronological-weekly-search.v2",
        "synthetic-priority-weekly-search.v2",
        "synthetic-nutrient-priority-weekly-search.v2",
        "synthetic-forward-checking-weekly-search.v2",
        "synthetic-incremental-weekly-search.v2",
        "synthetic-incremental-forward-checking-weekly-search.v2",
        "synthetic-reverse-option-weekly-search.v2",
        "synthetic-static-original-mrv-weekly-search.v2",
        "synthetic-static-original-mrv-forward-weekly-search.v2",
        "synthetic-static-original-mrv-incremental-weekly-search.v2",
        "synthetic-static-original-mrv-incremental-forward-weekly-search.v2",
    ] = "synthetic-chronological-weekly-search.v2"
    verification_policy_version: Literal["synthetic-independent-weekly-cover.v2"] = (
        "synthetic-independent-weekly-cover.v2"
    )
    criterion: Literal["FIRST_FEASIBLE"] = "FIRST_FEASIBLE"
    manifest: ExpectedWeekCheckManifest
    candidates: tuple[CandidateRecipeFacts, ...]
    certificate: WeeklySearchCertificateV2
    termination: WeeklyInterruptionV2 | None = None
    execution_deadline_checkpoint: Annotated[int, Field(ge=1, le=1_000_000)] | None = None
    execution_deadline_observation: Annotated[float, Field(allow_inf_nan=False)] | None = None
    verification_deadline_checkpoint: Annotated[int, Field(ge=1, le=1_000_000)] | None = None
    verification_deadline_observation: Annotated[float, Field(allow_inf_nan=False)] | None = None
    outcome: DailyOutcome = DailyOutcome.TIMEOUT
    witness: WeeklyWitness | None = None
    verification_complete: bool = False
    verification_work: WeeklyWorkV2 = WeeklyWorkV2()
    reuse_preparation: bool = False
    preparation_cache_entries: Annotated[int, Field(ge=0, le=1)] = 1
    execution_preparation: WeeklyPreparationAccountingV2 | None = None
    verification_preparation: WeeklyPreparationAccountingV2 | None = None

    @model_validator(mode="after")
    def independently_check(self, info: ValidationInfo) -> Self:
        from savora_ai.core.reasoning.weekly_proof_v2 import check_weekly_proof_v2
        from savora_ai.schemas.weekly_search_v2 import WeeklyNutrientSearchStrategyV2

        expected_schema = (
            "computed-weekly-nutrient-solve-result.v1"
            if isinstance(self.certificate.identity.strategy, WeeklyNutrientSearchStrategyV2)
            else "computed-weekly-solve-result.v2"
        )
        if self.schema_version != expected_schema:
            raise ValueError("weekly result protocol does not match native constraint inventory")
        clock = info.context.get("v2_clock") if type(info.context) is dict else None
        checked = check_weekly_proof_v2(
            self.manifest,
            self.candidates,
            self.certificate,
            termination=self.termination,
            execution_deadline_checkpoint=self.execution_deadline_checkpoint,
            execution_deadline_observation=self.execution_deadline_observation,
            verification_deadline_checkpoint=self.verification_deadline_checkpoint,
            verification_deadline_observation=self.verification_deadline_observation,
            clock=cast(Callable[[], float] | None, clock),
            reuse_preparation=self.reuse_preparation,
            preparation_cache_entries=self.preparation_cache_entries,
        )
        expected: dict[str, Any] = dict(
            search_policy_version=(
                self.certificate.identity.strategy.policy
                if isinstance(self.certificate.identity.strategy.policy, str)
                else self.certificate.identity.strategy.policy.value
            ),
            outcome=checked.outcome,
            witness=checked.witness,
            verification_complete=checked.complete,
            verification_work=checked.work,
            verification_deadline_checkpoint=checked.deadline_checkpoint,
            verification_deadline_observation=checked.deadline_observation,
            execution_preparation=WeeklyPreparationAccountingV2.model_validate(checked.preparation)
            if checked.complete and checked.preparation is not None
            else None,
            verification_preparation=WeeklyPreparationAccountingV2.model_validate(
                checked.preparation
            )
            if checked.preparation is not None
            else None,
        )
        for field, value in expected.items():
            # A newly observed verifier deadline can only withdraw authority.
            if (
                field in self.model_fields_set
                and getattr(self, field) != value
                and (clock is None or checked.complete)
            ):
                raise ValueError("v2 computed " + field + " contradicts independent verification")
            object.__setattr__(self, field, value)
        return self
