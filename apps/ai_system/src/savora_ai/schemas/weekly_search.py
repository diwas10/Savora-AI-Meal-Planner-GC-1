"""Strict computed weekly search output and bounded executable coverage certificate."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from savora_ai.schemas.daily import _DailyModel
from savora_ai.schemas.daily_solver import DailyAssignmentEvaluation
from savora_ai.schemas.food_graph import _OpaqueId
from savora_ai.schemas.knowledge_base import _ContentDigest
from savora_ai.schemas.reasoning import RuleStatus, RuleTrace
from savora_ai.schemas.weekly import (
    WeekDayReference,
    WeekFact,
    WeeklyAssignment,
    WeeklyTrial,
)
from savora_ai.schemas.weekly_evaluation import WeekRuleExplanation

_Index = Annotated[int, Field(ge=0, le=49)]
_Path = Annotated[tuple[_Index, ...], Field(max_length=21)]
_Count = Annotated[int, Field(ge=0)]
_Seconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Termination = Literal[
    "NODE_BUDGET",
    "PREPROCESSING_BUDGET",
    "DAY_BUDGET",
    "WEEK_BUDGET",
    "PREDICATE_BUDGET",
    "PROOF_RECORD_BUDGET",
    "PROOF_BYTE_BUDGET",
    "DEADLINE",
]


class WeeklyPreparationProof(_DailyModel):
    option_id: _OpaqueId
    decision_digest: _ContentDigest
    slot_statuses: Annotated[tuple[RuleStatus, ...], Field(min_length=3, max_length=3)]


class WeeklyCoverageRecord(_DailyModel):
    kind: Literal["DAY", "LEAF"]
    path: _Path
    evaluation_digest: _ContentDigest

    @model_validator(mode="after")
    def validate_depth(self) -> Self:
        if not self.path or len(self.path) % 3 or (self.kind == "LEAF" and len(self.path) != 21):
            raise ValueError("coverage records require a completed day or complete leaf")
        return self


class WeeklySearchStatistics(_DailyModel):
    nodes: _Count
    option_evaluations: _Count
    day_evaluations: _Count
    week_evaluations: _Count
    predicate_evaluations: _Count
    phase3_batch_calls: _Count
    phase3_candidate_evaluations: _Count
    cache_entries: _Count
    cache_hits: _Count
    known_failures: _Count
    unknown_hypotheses: _Count
    backtracks: _Count
    pruned_subtrees: _Count
    proof_records: _Count
    proof_bytes: _Count
    checkpoints: _Count
    exhaustive: bool
    termination: Termination | None


class WeeklySearchCertificate(_DailyModel):
    schema_version: Literal["weekly-coverage.v1"] = "weekly-coverage.v1"
    recipe_proof_digest: _ContentDigest | None
    preparation: Annotated[tuple[WeeklyPreparationProof, ...], Field(max_length=150)]
    records: Annotated[tuple[WeeklyCoverageRecord, ...], Field(max_length=8192)]
    # Original sorted-domain indexes. Together with next_indexes these describe the
    # active DFS stack and every unexplored sibling, rather than a sampled frontier.
    frontier: _Path
    next_indexes: Annotated[tuple[Annotated[int, Field(ge=0, le=50)], ...], Field(max_length=21)]
    deadline_checkpoint: Annotated[int, Field(ge=1, le=1_000_000)] | None
    statistics: WeeklySearchStatistics


class WeeklyWitnessDay(_DailyModel):
    day: WeekDayReference
    manifest_digest: _ContentDigest
    evaluation: DailyAssignmentEvaluation


class WeeklyWitness(_DailyModel):
    trial: WeeklyTrial
    assignment: WeeklyAssignment
    days: Annotated[tuple[WeeklyWitnessDay, ...], Field(min_length=7, max_length=7)]
    facts: Annotated[tuple[WeekFact, ...], Field(min_length=3, max_length=3)]
    trace: RuleTrace
    explanations: tuple[WeekRuleExplanation, ...]


class WeeklySolverTiming(_DailyModel):
    preparation_seconds: _Seconds
    search_seconds: _Seconds
    output_validation_seconds: _Seconds
    # Observational wall-clock metadata cannot authenticate an external clock.
    validation_finished_at: Annotated[float, Field(allow_inf_nan=False)] | None = None
    validation_deadline_reached: bool = False
