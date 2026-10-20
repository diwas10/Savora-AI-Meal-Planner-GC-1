"""Verified v1 benchmark runner. Run ``python -m savora_ai.evals.weekly_benchmarks --help``.

JSONL reports are measurements, never accepted solver proofs or authorization.
All counters come from the verified result, except explicitly labelled external
instrumentation. Reserved semantic work is NOT a count of completed physical calls.
No stage timing, full-result byte count or memory sample enters semantic comparison.
"""

import argparse
import hashlib
import platform
import tracemalloc
from importlib.metadata import PackageNotFoundError, version
from time import monotonic, perf_counter
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from savora_ai.core.reasoning.weekly import solve_weekly_plan
from savora_ai.evals.synthetic_week_cases import (
    OptionIndex,
    OracleResult,
    Outcome,
    SyntheticWeekCase,
    build_week_case,
    case_specs,
    exhaustive_oracle,
    literal_trial_status,
)
from savora_ai.schemas.daily import DailyOutcome, MealSlot
from savora_ai.schemas.knowledge import _ContractModel
from savora_ai.schemas.weekly import WeeklySearchLimits
from savora_ai.schemas.weekly_solver import ComputedWeeklySolveResult

Count = Annotated[int, Field(ge=0)]
Seconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Text = Annotated[str, Field(min_length=1)]
Unavailable = Literal["NOT_AVAILABLE"]


class BenchmarkEnvironment(_ContractModel):
    python_version: Text
    python_implementation: Text
    platform: Text
    savora_ai_version: Text
    pydantic_version: Text
    pydantic_core_version: Text


class CorrectnessMetrics(_ContractModel):
    expected_outcome: Outcome
    outcome: Outcome
    expected_outcome_matches: bool
    oracle_scope: Literal["COMPLETE_LITERAL_PROBLEM", "PROBLEM_ONLY_FOR_TIMEOUT"]
    oracle_outcome: Literal["FEASIBLE", "INFEASIBLE", "INSUFFICIENT_DATA"]
    oracle_assignments: Annotated[int, Field(ge=0, le=256)]
    oracle_passed: Count
    oracle_failed: Count
    oracle_unknown: Count
    outcome_matches_oracle: bool | Unavailable
    witness_validation: Literal["INDEPENDENTLY_VALIDATED", "NOT_PRESENT"]
    witness_option_indexes: tuple[OptionIndex, ...]
    first_witness_matches_oracle: bool | Unavailable

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        if self.expected_outcome_matches != (self.expected_outcome == self.outcome):
            raise ValueError("expected outcome comparison is inconsistent")
        if self.oracle_assignments != self.oracle_passed + self.oracle_failed + self.oracle_unknown:
            raise ValueError("oracle truth counts must cover the original Cartesian product")
        truth = (
            "FEASIBLE"
            if self.oracle_passed
            else "INSUFFICIENT_DATA"
            if self.oracle_unknown
            else "INFEASIBLE"
        )
        if self.oracle_outcome != truth:
            raise ValueError("oracle outcome contradicts its literal truth counts")
        if self.outcome == "TIMEOUT":
            if (
                self.oracle_scope != "PROBLEM_ONLY_FOR_TIMEOUT"
                or self.outcome_matches_oracle != "NOT_AVAILABLE"
            ):
                raise ValueError("TIMEOUT cannot be compared to exhaustive problem truth")
        elif self.oracle_scope != "COMPLETE_LITERAL_PROBLEM" or self.outcome_matches_oracle != (
            self.outcome == self.oracle_outcome
        ):
            raise ValueError("completed outcome comparison is inconsistent")
        if self.outcome == "FEASIBLE":
            if (
                len(self.witness_option_indexes) != 21
                or self.witness_validation != "INDEPENDENTLY_VALIDATED"
                or type(self.first_witness_matches_oracle) is not bool
            ):
                raise ValueError("FEASIBLE requires an independently checked full witness")
        elif (
            self.witness_option_indexes
            or self.witness_validation != "NOT_PRESENT"
            or self.first_witness_matches_oracle != "NOT_AVAILABLE"
        ):
            raise ValueError("non-feasible outcome cannot expose a successful witness")
        return self


class SearchEffort(_ContractModel):
    logical_nodes: Count
    completed_assignments: Count  # Actual LEAF records, not week_evaluations / 2.
    backtracks: Count
    pruned_subtrees: Count
    known_failures: Count
    unknown_hypotheses: Count
    cache_entries_high_water: Count
    cache_hits: Count
    cache_misses: Unavailable = "NOT_AVAILABLE"
    cache_evictions: Unavailable = "NOT_AVAILABLE"


class EvaluationWork(_ContractModel):
    accounting: Literal["EXECUTION_AND_OUTPUT_REPLAY_RESERVATIONS"] = (
        "EXECUTION_AND_OUTPUT_REPLAY_RESERVATIONS"
    )
    option_evaluations: Count
    day_evaluations: Count
    week_evaluations: Count
    predicate_evaluations: Count
    recipe_batches: Count
    recipe_candidate_evaluations: Count
    completed_physical_evaluator_calls: Unavailable = "NOT_AVAILABLE"
    execution_verification_split: Unavailable = "NOT_AVAILABLE"


class EvidenceCost(_ContractModel):
    certificate_schema_version: Text
    certificate_digest: Digest
    proof_records: Count
    reserved_proof_bytes: Count
    serialized_certificate_bytes: Count
    serialized_result_bytes: Count
    encoding: Literal["PYDANTIC_CAMELCASE_COMPACT_JSON_UTF8"] = (
        "PYDANTIC_CAMELCASE_COMPACT_JSON_UTF8"
    )


class BenchmarkTimings(_ContractModel):
    stage_clock: Literal["MONOTONIC", "SYNTHETIC_EXPIRED_CONSTANT"]
    preparation_seconds: Seconds
    search_seconds: Seconds
    verification_seconds: Seconds
    total_solver_seconds: Seconds  # External perf_counter; includes all solver validation.
    serialization_seconds: Seconds
    fixture_build_seconds: Seconds
    oracle_seconds: Seconds


class MemoryMeasurements(_ContractModel):
    mode: Literal["DISABLED", "TRACEMALLOC_SOLVER_CALL"]
    python_peak_bytes: Count | Unavailable
    process_rss_bytes: Unavailable = "NOT_AVAILABLE"

    @model_validator(mode="after")
    def validate_mode(self) -> Self:
        if (self.mode == "DISABLED") != (self.python_peak_bytes == "NOT_AVAILABLE"):
            raise ValueError("tracemalloc peak must match the declared instrumentation mode")
        return self


class ResourceOutcome(_ContractModel):
    limits: WeeklySearchLimits
    timeout: bool
    exhaustive_search: bool
    search_termination: Text | None
    checkpoints: Count
    deadline_checkpoint: Annotated[int, Field(ge=1)] | None
    verification_deadline_reached: bool


class WeeklyBenchmarkResult(_ContractModel):
    """Strict additive report envelope; schemas/policies identify the measured solver.

    Compare fixture_digest and limits first. Semantic outcomes and witnesses are
    separate comparisons; never compare times across unlike fixtures/clock modes.
    The full result's timing-dependent byte size is intentionally observational.
    """

    schema_version: Literal["weekly-benchmark-result.v1"] = "weekly-benchmark-result.v1"
    workload_id: Text
    description: Text
    fixture_digest: Digest
    request_digest: Digest
    source_digest: Digest
    context_digest: Digest
    kb_digest: Digest
    solver_schema_version: Text
    search_policy_version: Text
    criterion: Text
    environment: BenchmarkEnvironment
    correctness: CorrectnessMetrics
    effort: SearchEffort
    evaluation_work: EvaluationWork
    evidence: EvidenceCost
    timings: BenchmarkTimings
    memory: MemoryMeasurements
    resources: ResourceOutcome

    @model_validator(mode="after")
    def validate_timeout(self) -> Self:
        if self.resources.timeout != (self.correctness.outcome == "TIMEOUT"):
            raise ValueError("resource timeout flag contradicts the semantic outcome")
        stopped = (
            self.resources.search_termination is not None
            or self.resources.verification_deadline_reached
        )
        if self.resources.timeout != stopped:
            raise ValueError("TIMEOUT must have an explicit search or verification stop")
        return self

    def semantic_projection(self) -> dict[str, object]:
        """No timings, memory, environment, proof layout or serialization lengths.

        Compare outcome alone for outcome equivalence; compare the separate witness
        tuple as well only when evaluating witness equivalence for the same order.
        """
        return dict(
            fixture_digest=self.fixture_digest,
            outcome=self.correctness.outcome,
            oracle_outcome=self.correctness.oracle_outcome,
            witness_validation=self.correctness.witness_validation,
            witness_option_indexes=self.correctness.witness_option_indexes,
        )


def _installed(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "NOT_AVAILABLE"


def validate_witness(case: SyntheticWeekCase, result: ComputedWeeklySolveResult) -> tuple[int, ...]:
    """Independently check exact original domains, trial/assignment equality and truth."""
    witness = result.witness
    if witness is None:
        if result.outcome is DailyOutcome.FEASIBLE:
            raise ValueError("feasible result lacks a witness")
        return ()
    if result.outcome is not DailyOutcome.FEASIBLE:
        raise ValueError("non-feasible result exposed a witness")
    choices = {(c.day.day_index, c.slot): c for c in witness.trial.choices}
    assignments = {
        (d.day.day_index, a.slot): a.option
        for d in witness.assignment.days
        for a in d.assignment.slots
    }
    if len(choices) != 21 or len(assignments) != 21:
        raise ValueError("witness must contain exactly 21 distinct slots")
    indexes = []
    source_refs = tuple(option.reference for option in case.sources.daily_source.options)
    for day in sorted(case.request.days, key=lambda d: d.day.day_index):
        for slot in MealSlot:
            key = (day.day.day_index, slot)
            choice = choices[key]
            domain = next(d for d in day.domains if d.slot is slot)
            if (
                choice.day != day.day
                or choice.option not in domain.options
                or assignments[key] != choice.option
            ):
                raise ValueError("witness differs from exact original day/domain/configuration")
            indexes.append(source_refs.index(choice.option))
    selected = tuple(indexes)
    if literal_trial_status(case.spec, selected) != "PASS":
        raise ValueError("independent literal witness evaluation did not PASS")
    return selected


def _report(
    case: SyntheticWeekCase,
    result: ComputedWeeklySolveResult,
    oracle: OracleResult,
    *,
    total_seconds: float,
    fixture_seconds: float,
    oracle_seconds: float,
    memory_peak: int | None,
) -> WeeklyBenchmarkResult:
    witness = validate_witness(case, result)
    started = perf_counter()
    certificate_bytes = result.certificate.model_dump_json(by_alias=True).encode("utf-8")
    result_bytes = result.model_dump_json(by_alias=True).encode("utf-8")
    serialization_seconds = perf_counter() - started
    stats = result.certificate.statistics
    timeout = result.outcome is DailyOutcome.TIMEOUT
    return WeeklyBenchmarkResult(
        workload_id=case.spec.case_id,
        description=case.spec.description,
        fixture_digest=case.fixture_digest,
        request_digest=case.request.content_digest,
        source_digest=case.sources.content_digest,
        context_digest=case.context.content_digest,
        kb_digest=case.knowledge.content_digest,
        solver_schema_version=result.schema_version,
        search_policy_version=result.search_policy_version,
        criterion=result.criterion,
        environment=BenchmarkEnvironment(
            python_version=platform.python_version(),
            python_implementation=platform.python_implementation(),
            platform=platform.platform(),
            savora_ai_version=_installed("savora-ai"),
            pydantic_version=_installed("pydantic"),
            pydantic_core_version=_installed("pydantic-core"),
        ),
        correctness=CorrectnessMetrics(
            expected_outcome=case.spec.expected_outcome,
            outcome=result.outcome.value,
            expected_outcome_matches=result.outcome.value == case.spec.expected_outcome,
            oracle_scope="PROBLEM_ONLY_FOR_TIMEOUT" if timeout else "COMPLETE_LITERAL_PROBLEM",
            oracle_outcome=oracle.outcome,
            oracle_assignments=oracle.assignments,
            oracle_passed=oracle.passed,
            oracle_failed=oracle.failed,
            oracle_unknown=oracle.unknown,
            outcome_matches_oracle="NOT_AVAILABLE"
            if timeout
            else result.outcome.value == oracle.outcome,
            witness_validation="INDEPENDENTLY_VALIDATED" if witness else "NOT_PRESENT",
            witness_option_indexes=witness,
            first_witness_matches_oracle=witness == oracle.first_witness
            if witness
            else "NOT_AVAILABLE",
        ),
        effort=SearchEffort(
            logical_nodes=stats.nodes,
            completed_assignments=sum(r.kind == "LEAF" for r in result.certificate.records),
            backtracks=stats.backtracks,
            pruned_subtrees=stats.pruned_subtrees,
            known_failures=stats.known_failures,
            unknown_hypotheses=stats.unknown_hypotheses,
            cache_entries_high_water=stats.cache_entries,
            cache_hits=stats.cache_hits,
        ),
        evaluation_work=EvaluationWork(
            option_evaluations=stats.option_evaluations,
            day_evaluations=stats.day_evaluations,
            week_evaluations=stats.week_evaluations,
            predicate_evaluations=stats.predicate_evaluations,
            recipe_batches=stats.phase3_batch_calls,
            recipe_candidate_evaluations=stats.phase3_candidate_evaluations,
        ),
        evidence=EvidenceCost(
            certificate_schema_version=result.certificate.schema_version,
            certificate_digest=hashlib.sha256(certificate_bytes).hexdigest(),
            proof_records=stats.proof_records,
            reserved_proof_bytes=stats.proof_bytes,
            serialized_certificate_bytes=len(certificate_bytes),
            serialized_result_bytes=len(result_bytes),
        ),
        timings=BenchmarkTimings(
            stage_clock="SYNTHETIC_EXPIRED_CONSTANT"
            if case.spec.clock_mode == "EXPIRED_CONSTANT"
            else "MONOTONIC",
            preparation_seconds=result.timing.preparation_seconds,
            search_seconds=result.timing.search_seconds,
            verification_seconds=result.timing.output_validation_seconds,
            total_solver_seconds=total_seconds,
            serialization_seconds=serialization_seconds,
            fixture_build_seconds=fixture_seconds,
            oracle_seconds=oracle_seconds,
        ),
        memory=MemoryMeasurements(
            mode="DISABLED" if memory_peak is None else "TRACEMALLOC_SOLVER_CALL",
            python_peak_bytes="NOT_AVAILABLE" if memory_peak is None else memory_peak,
        ),
        resources=ResourceOutcome(
            limits=case.spec.limits,
            timeout=timeout,
            exhaustive_search=stats.exhaustive,
            search_termination=stats.termination,
            checkpoints=stats.checkpoints,
            deadline_checkpoint=result.certificate.deadline_checkpoint,
            verification_deadline_reached=result.timing.validation_deadline_reached,
        ),
    )


def run_benchmark(workload_id: str, *, measure_memory: bool = False) -> WeeklyBenchmarkResult:
    """One fresh, bounded, verified public solve; no injected solver or proof bypass.

    Fixture construction/oracle/extraction/serialization are outside total_solver_seconds.
    Tracemalloc covers only the public solver call; its overhead affects its timings.
    Stage times for the already-expired synthetic clock are clock metadata, not
    measured algorithmic time. External total_solver_seconds still uses perf_counter.
    """
    if type(measure_memory) is not bool:
        raise ValueError("measure_memory must be a strict boolean")
    if measure_memory and tracemalloc.is_tracing():
        raise ValueError("refusing to reset another caller's active tracemalloc session")
    started = perf_counter()
    case = build_week_case(workload_id)
    fixture_seconds = perf_counter() - started
    started = perf_counter()
    oracle = exhaustive_oracle(case.spec)  # Refuse oversized domains before any solve.
    oracle_seconds = perf_counter() - started
    peak = None
    if measure_memory:
        tracemalloc.start()
    try:
        started = perf_counter()
        result = solve_weekly_plan(
            case.request,
            candidates=case.candidates,
            knowledge=case.knowledge,
            context=case.context,
            sources=case.sources,
            limits=case.spec.limits,
            clock=(lambda: 10.0) if case.spec.clock_mode == "EXPIRED_CONSTANT" else monotonic,
        )
        total_seconds = perf_counter() - started
        if measure_memory:
            peak = tracemalloc.get_traced_memory()[1]
    finally:
        if measure_memory:
            tracemalloc.stop()
    return _report(
        case,
        result,
        oracle,
        total_seconds=total_seconds,
        fixture_seconds=fixture_seconds,
        oracle_seconds=oracle_seconds,
        memory_peak=peak,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case", choices=("all", *(s.case_id for s in case_specs())), required=True
    )
    parser.add_argument(
        "--memory", action="store_true", help="Separate instrumented allocation run"
    )
    args = parser.parse_args()
    cases = tuple(s.case_id for s in case_specs()) if args.case == "all" else (args.case,)
    for case_id in cases:
        report = run_benchmark(case_id, measure_memory=args.memory)
        print(report.model_dump_json(by_alias=True))


if __name__ == "__main__":
    main()
