"""Phase 7.1b: literal correctness, real public solves and honest measurement extraction."""

import hashlib
import inspect
import json
import tracemalloc
from dataclasses import FrozenInstanceError
from math import prod
from typing import Any

import pytest
from pydantic import ValidationError

from savora_ai.core.reasoning import weekly
from savora_ai.evals import synthetic_week_cases as fixtures
from savora_ai.evals import weekly_benchmarks as benchmarks
from savora_ai.evals.synthetic_week_cases import (
    SyntheticWeekCase,
    WeekCaseSpec,
    build_week_case,
    case_specs,
    exhaustive_oracle,
    literal_trial_status,
)
from savora_ai.evals.weekly_benchmarks import WeeklyBenchmarkResult, run_benchmark
from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.daily import DailyOutcome
from savora_ai.schemas.weekly_solver import ComputedWeeklySolveResult

CASE_IDS = tuple(s.case_id for s in case_specs())


@pytest.fixture(scope="module", params=CASE_IDS)
def measurement(
    request: pytest.FixtureRequest,
) -> tuple[SyntheticWeekCase, ComputedWeeklySolveResult, WeeklyBenchmarkResult]:
    """One actual verified solve per fixture; capture the exact result being measured."""
    case = build_week_case(request.param)
    before = case.fixture_digest
    captured: list[ComputedWeeklySolveResult] = []
    original = weekly.solve_weekly_plan

    def observe(*args: Any, **kwargs: Any) -> ComputedWeeklySolveResult:
        result = original(*args, **kwargs)
        captured.append(result)
        return result

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(benchmarks, "build_week_case", lambda _: case)
        patch.setattr(benchmarks, "solve_weekly_plan", observe)
        report = run_benchmark(case.spec.case_id)
    assert len(captured) == 1
    assert case.fixture_digest == before, "benchmark mutated its supplied source material"
    return case, captured[0], report


def test_fixture_inventory_is_bounded_and_deterministic():
    assert case_specs() == case_specs()
    assert len(CASE_IDS) == len(set(CASE_IDS)) == 22
    assert all(s.description and prod(len(d) for d in s.domains) <= 8 for s in case_specs())
    assert all(s.limits.max_nodes <= 10000 for s in case_specs())
    with pytest.raises(ValueError, match="unknown benchmark case"):
        build_week_case("unregistered")


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_fixture_identity_digest_and_source_determinism(case_id: str):
    left, right = build_week_case(case_id), build_week_case(case_id)
    assert left == right
    assert left.fixture_digest == right.fixture_digest
    assert len(left.fixture_digest) == 64
    assert left.request.model_dump_json() == right.request.model_dump_json()
    if case_id == "single":
        assert (
            left.fixture_digest
            == "8a817684f3ffd056327d81a3bed5a400b5901867ac4ee0488982417d68a8b74e"
        )


def test_input_immutability_and_digest_includes_resource_contract():
    case = build_week_case("single")
    with pytest.raises(FrozenInstanceError):
        case.context = case.context  # type: ignore[misc]
    with pytest.raises(ValidationError):
        case.spec.target = 0  # type: ignore[misc]
    assert build_week_case("exact-work").fixture_digest != case.fixture_digest
    assert build_week_case("exact-work").request == case.request


@pytest.mark.parametrize(
    "left,right,expected",
    [
        ("PASS", "PASS", "PASS"),
        ("PASS", "FAIL", "FAIL"),
        ("PASS", "UNKNOWN", "UNKNOWN"),
        ("FAIL", "PASS", "FAIL"),
        ("FAIL", "FAIL", "FAIL"),
        ("FAIL", "UNKNOWN", "FAIL"),
        ("UNKNOWN", "PASS", "UNKNOWN"),
        ("UNKNOWN", "FAIL", "FAIL"),
        ("UNKNOWN", "UNKNOWN", "UNKNOWN"),
    ],
)
def test_independent_hard_truth_table(left, right, expected):
    assert fixtures._TRUTH_TABLE[left, right] == expected


@pytest.mark.parametrize("spec", case_specs(), ids=CASE_IDS)
def test_literal_oracle_outcomes_and_first_witness(spec: WeekCaseSpec):
    result = exhaustive_oracle(spec)
    assert result.assignments == result.passed + result.failed + result.unknown
    assert result.outcome == (
        "FEASIBLE" if spec.expected_outcome == "TIMEOUT" else spec.expected_outcome
    )
    if result.first_witness is not None:
        assert literal_trial_status(spec, result.first_witness) == "PASS"
    if spec.case_id == "late":
        assert result.passed == 1 and result.failed == 7
        assert result.first_witness == tuple(1 if i in (0, 3, 6) else 0 for i in range(21))
    if spec.case_id == "unknown-day":
        assert result.unknown == 1 and result.failed == 0
    if spec.case_id == "unknown-refuted":
        assert result.unknown == 0 and result.failed == 1
    if spec.case_id == "repeated-identities":
        assert result.first_witness is not None
        assert result.first_witness[18] == 1 and result.first_witness[20] == 2


def test_oracle_does_not_call_production_decision_logic(monkeypatch: pytest.MonkeyPatch):
    def forbidden(*args: Any, **kwargs: Any):
        raise AssertionError("production decision helper used as an oracle")

    for target in (
        "savora_ai.core.reasoning.evaluation._predicate",
        "savora_ai.schemas.reasoning.aggregate_hard_status",
        "savora_ai.core.reasoning.weekly_search._execute",
        "savora_ai.core.reasoning.week_checks._assess_week",
        "savora_ai.core.reasoning.day_checks._assess_day",
        "savora_ai.core.reasoning.weekly.solve_weekly_plan",
    ):
        monkeypatch.setattr(target, forbidden)
    assert {exhaustive_oracle(s).outcome for s in case_specs()} == {
        "FEASIBLE",
        "INFEASIBLE",
        "INSUFFICIENT_DATA",
    }


def test_oracle_rejects_large_domains_and_unmodelled_vocabulary():
    data = case_specs()[0].model_dump()
    data["domains"] = tuple((0, 1) if i < 9 else (0,) for i in range(21))
    with pytest.raises(ValueError, match="Cartesian size 512 exceeds bound 256"):
        exhaustive_oracle(WeekCaseSpec.model_validate(data))
    boundary = {**data, "domains": tuple((0, 1) if i < 8 else (0,) for i in range(21))}
    assert exhaustive_oracle(WeekCaseSpec.model_validate(boundary)).assignments == 256
    for bad in (0, True, 257):
        with pytest.raises(ValueError, match="oracle bound"):
            exhaustive_oracle(case_specs()[0], max_assignments=bad)
    with pytest.raises(ValidationError):
        WeekCaseSpec.model_validate({**data, "clinical_rule": "not supported"})
    with pytest.raises(ValueError, match="original 21-slot domains"):
        literal_trial_status(case_specs()[0], (2,) * 21)


def test_reported_outcomes_and_independent_witnesses(measurement):
    case, result, report = measurement
    assert report.correctness.outcome == result.outcome.value == case.spec.expected_outcome
    assert report.correctness.expected_outcome_matches
    assert report.fixture_digest == case.fixture_digest
    if result.outcome is DailyOutcome.TIMEOUT:
        assert report.resources.timeout and result.witness is None
        assert report.correctness.oracle_outcome == "FEASIBLE"
        assert report.correctness.outcome_matches_oracle == "NOT_AVAILABLE"
        assert report.correctness.oracle_scope == "PROBLEM_ONLY_FOR_TIMEOUT"
    else:
        assert report.correctness.outcome_matches_oracle is True
    if result.outcome is DailyOutcome.FEASIBLE:
        assert report.correctness.witness_validation == "INDEPENDENTLY_VALIDATED"
        assert report.correctness.first_witness_matches_oracle is True
    if case.spec.case_id == "day-pruning":
        assert report.effort.pruned_subtrees > 0
        assert report.effort.completed_assignments < report.correctness.oracle_assignments


def test_literal_spec_matches_actual_validated_inputs_and_rejects_spliced_witness(measurement):
    case, result, _ = measurement
    options = case.sources.daily_source.options
    assert tuple(o.measurements[0].value for o in options) == (
        (None,) * 3 if case.spec.missing_measurement else (3, 7, 11)
    )
    recipe_ids = tuple(o.combination.components[0].recipe_snapshot.recipe_id for o in options)
    assert recipe_ids == ("bench-recipe-a", "bench-recipe-a", "bench-recipe-b")
    assert all(
        len(o.combination.components) == (2 if case.spec.duplicate_components else 1)
        for o in options
    )
    for position, domain in enumerate(d for day in case.request.days for d in day.domains):
        assert domain.options == tuple(options[i].reference for i in case.spec.domains[position])
    by_id = {rule.rule_id: rule for rule in case.knowledge.rules}
    assert by_id["bench-week-total"].value == case.spec.target
    assert by_id["bench-week-repeat"].value == case.spec.repeat_cap
    assert (
        "synthetic_profile_enabled" in by_id["bench-day"].required_facts
    ) == case.spec.day_unknown
    if case.spec.day_cap is not None:
        assert by_id["bench-day-cap"].value == case.spec.day_cap
    if result.witness is not None:
        witness = result.witness
        # Hostile unchecked copies are only test inputs to the independent checker;
        # no production validator or certificate verification is bypassed by the runner.
        wrong_choice = witness.trial.choices[0].model_copy(update={"option": options[2].reference})
        wrong_trial = witness.trial.model_copy(
            update={
                "choices": (wrong_choice, *witness.trial.choices[1:]),
            }
        )
        wrong = result.model_copy(
            update={"witness": witness.model_copy(update={"trial": wrong_trial})}
        )
        with pytest.raises(ValueError, match="original day/domain/configuration"):
            benchmarks.validate_witness(case, wrong)


def test_available_counters_and_reservations_are_extracted_without_inference(measurement):
    _, result, report = measurement
    stats = result.certificate.statistics
    assert report.effort.logical_nodes == stats.nodes
    assert report.effort.completed_assignments == sum(
        r.kind == "LEAF" for r in result.certificate.records
    )
    assert report.effort.cache_entries_high_water == stats.cache_entries
    assert report.effort.cache_hits == stats.cache_hits
    assert report.effort.backtracks == stats.backtracks
    assert report.effort.pruned_subtrees == stats.pruned_subtrees
    assert report.effort.known_failures == stats.known_failures
    assert report.effort.unknown_hypotheses == stats.unknown_hypotheses
    work = report.evaluation_work
    assert (
        work.option_evaluations,
        work.day_evaluations,
        work.week_evaluations,
        work.predicate_evaluations,
        work.recipe_batches,
        work.recipe_candidate_evaluations,
    ) == (
        stats.option_evaluations,
        stats.day_evaluations,
        stats.week_evaluations,
        stats.predicate_evaluations,
        stats.phase3_batch_calls,
        stats.phase3_candidate_evaluations,
    )
    assert work.accounting == "EXECUTION_AND_OUTPUT_REPLAY_RESERVATIONS"
    assert work.completed_physical_evaluator_calls == "NOT_AVAILABLE"
    assert work.execution_verification_split == "NOT_AVAILABLE"
    assert report.effort.cache_misses == report.effort.cache_evictions == "NOT_AVAILABLE"
    assert report.memory.python_peak_bytes == report.memory.process_rss_bytes == "NOT_AVAILABLE"
    if report.workload_id == "exact-work":
        assert (
            work.option_evaluations,
            work.day_evaluations,
            work.week_evaluations,
            work.predicate_evaluations,
        ) == (2, 14, 2, 38)
        assert report.effort.logical_nodes == 21 and report.effort.completed_assignments == 1
        assert report.evidence.proof_records == 10


def test_serialization_sizes_and_clocks_match_actual_result(measurement):
    case, result, report = measurement
    encoded = result.certificate.model_dump_json(by_alias=True).encode("utf-8")
    assert report.evidence.serialized_certificate_bytes == len(encoded)
    assert report.evidence.certificate_digest == hashlib.sha256(encoded).hexdigest()
    assert report.evidence.serialized_result_bytes == len(
        result.model_dump_json(by_alias=True).encode("utf-8")
    )
    assert report.evidence.reserved_proof_bytes == result.certificate.statistics.proof_bytes
    assert report.evidence.proof_records == result.certificate.statistics.proof_records
    assert report.timings.preparation_seconds == result.timing.preparation_seconds
    assert report.timings.search_seconds == result.timing.search_seconds
    assert report.timings.verification_seconds == result.timing.output_validation_seconds
    assert report.timings.total_solver_seconds > 0
    assert report.resources.limits == case.spec.limits
    assert report.resources.search_termination == result.certificate.statistics.termination
    if case.spec.clock_mode == "EXPIRED_CONSTANT":
        assert report.timings.stage_clock == "SYNTHETIC_EXPIRED_CONSTANT"
        assert report.timings.search_seconds == report.timings.verification_seconds == 0
        assert report.resources.deadline_checkpoint == 1


def test_report_strict_roundtrip_and_semantics_exclude_observations(measurement):
    _, _, report = measurement
    assert (
        validate_contract_json(WeeklyBenchmarkResult, report.model_dump_json(by_alias=True))
        == report
    )
    data = report.model_dump()
    data["timings"]["total_solver_seconds"] += 50.0
    data["evidence"]["serialized_result_bytes"] += 10
    changed = WeeklyBenchmarkResult.model_validate(data)
    assert changed.semantic_projection() == report.semantic_projection()
    with pytest.raises(ValidationError):
        WeeklyBenchmarkResult.model_validate({**data, "unexpected": True})
    with pytest.raises(ValidationError):
        WeeklyBenchmarkResult.model_validate(report.model_copy(update={"unexpected": True}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("logical_nodes", -1),
        ("logical_nodes", True),
        ("completed_assignments", "1"),
    ],
)
def test_strict_effort_validation(field, value):
    data = dict(
        logical_nodes=1,
        completed_assignments=1,
        backtracks=0,
        pruned_subtrees=0,
        known_failures=0,
        unknown_hypotheses=0,
        cache_entries_high_water=0,
        cache_hits=0,
    )
    with pytest.raises(ValidationError):
        benchmarks.SearchEffort.model_validate({**data, field: value})


def test_strict_metric_relationships_and_original_json():
    report = run_benchmark("deadline-before-preparation")
    data = report.model_dump()
    data["resources"]["timeout"] = False
    with pytest.raises(ValidationError, match="timeout flag"):
        WeeklyBenchmarkResult.model_validate(data)
    for bad in (float("nan"), float("inf"), -1.0):
        data = report.model_dump()
        data["timings"]["total_solver_seconds"] = bad
        with pytest.raises(ValidationError):
            WeeklyBenchmarkResult.model_validate(data)
    data = report.model_dump()
    data["evaluation_work"]["completed_physical_evaluator_calls"] = 1
    with pytest.raises(ValidationError):
        WeeklyBenchmarkResult.model_validate(data)
    text = report.model_dump_json(by_alias=True)
    with pytest.raises(ValidationError):
        validate_contract_json(WeeklyBenchmarkResult, '{"workloadId":"fake",' + text[1:])
    assert json.loads(text)["correctness"]["outcome"] == "TIMEOUT"


def test_repeat_run_has_no_cross_request_cache_or_input_leakage():
    first = run_benchmark("single")
    interrupted = run_benchmark("option-odd")
    second = run_benchmark("single")
    assert interrupted.correctness.outcome == "TIMEOUT"
    assert first.semantic_projection() == second.semantic_projection()
    assert first.effort == second.effort
    assert first.evaluation_work == second.evaluation_work
    assert first.evidence.certificate_digest == second.evidence.certificate_digest
    assert (
        first.evaluation_work.option_evaluations == second.evaluation_work.option_evaluations == 2
    )


def test_memory_is_optional_external_instrumentation_and_restores_state():
    assert not tracemalloc.is_tracing()
    report = run_benchmark("deadline-before-preparation", measure_memory=True)
    assert report.memory.mode == "TRACEMALLOC_SOLVER_CALL"
    assert isinstance(report.memory.python_peak_bytes, int) and report.memory.python_peak_bytes > 0
    assert report.memory.process_rss_bytes == "NOT_AVAILABLE"
    assert not tracemalloc.is_tracing()
    tracemalloc.start()
    try:
        with pytest.raises(ValueError, match="another caller"):
            run_benchmark("single", measure_memory=True)
        assert tracemalloc.is_tracing()
    finally:
        tracemalloc.stop()
    with pytest.raises(ValueError, match="strict boolean"):
        run_benchmark("single", measure_memory=1)  # type: ignore[arg-type]


def test_public_solver_signature_and_v1_tokens_remain_unchanged():
    assert vars(benchmarks)["solve_weekly_plan"] is weekly.solve_weekly_plan
    assert tuple(inspect.signature(weekly.solve_weekly_plan).parameters) == (
        "request",
        "candidates",
        "knowledge",
        "context",
        "sources",
        "limits",
        "clock",
    )
    assert ComputedWeeklySolveResult.model_fields["schema_version"].default == (
        "computed-weekly-solve-result.v1"
    )
    assert ComputedWeeklySolveResult.model_fields["search_policy_version"].default == (
        "synthetic-chronological-weekly-search.v1"
    )


def test_independent_witness_checker_refuses_nonpassing_configuration():
    # Structural oracle input validation is independent of any computed result.
    spec = next(s for s in case_specs() if s.case_id == "late")
    assert literal_trial_status(spec, (0,) * 21) == "FAIL"
    assert (
        literal_trial_status(spec, tuple(1 if i in (0, 3, 6) else 0 for i in range(21))) == "PASS"
    )


def test_no_physical_call_inference_from_reserved_option_units(monkeypatch: pytest.MonkeyPatch):
    from savora_ai.core.reasoning.combinations import evaluate_combination

    calls = 0
    original = evaluate_combination

    def observe(*args: Any, **kwargs: Any):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr("savora_ai.core.reasoning.week_checks.evaluate_combination", observe)
    report = run_benchmark("single")
    assert calls == 2  # Explicit external spy, not derived by dividing a work counter.
    assert report.evaluation_work.option_evaluations == 2
    assert report.evaluation_work.completed_physical_evaluator_calls == "NOT_AVAILABLE"
