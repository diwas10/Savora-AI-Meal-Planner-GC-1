"""Equal-input incremental/full v2 comparisons with independent checking included.

Fixtures/imports are outside timing. State initialization is search work. Memory
probes are separate from untraced timing runs; their peak is not an RSS estimate.
Operation instrumentation is observational and never supplies result authority.
"""

import argparse
import json
import platform
import sys
import tracemalloc
from contextlib import ExitStack
from hashlib import sha256
from time import perf_counter
from unittest.mock import patch

from savora_ai.core.reasoning import day_checks, week_checks
from savora_ai.core.reasoning import weekly_incremental as incremental_state
from savora_ai.core.reasoning import weekly_proof_v2 as proof
from savora_ai.core.reasoning import weekly_search_v2 as search
from savora_ai.core.reasoning.week_checks import _compile_week
from savora_ai.evals.synthetic_week_cases import build_week_case, exhaustive_oracle
from savora_ai.schemas import weekly_search_v2 as v2

CASES = (
    "early",
    "late",
    "exhaustive",
    "day-pruning",
    "week-quantity",
    "week-repetition",
    "unknown-measurement",
    "repeated-identities",
)


def measure(
    case_id: str,
    *,
    incremental: bool,
    forward: bool = False,
    budget: str = "adequate",
    memory: bool = False,
    reuse: bool = True,
) -> dict:
    case = build_week_case(case_id)
    expected = exhaustive_oracle(case.spec)
    policies = {
        (False, False): v2.WeeklyStrategyPolicyV2.CHRONOLOGICAL,
        (False, True): v2.WeeklyStrategyPolicyV2.FORWARD_CHECKING,
        (True, False): v2.WeeklyStrategyPolicyV2.INCREMENTAL,
        (True, True): v2.WeeklyStrategyPolicyV2.INCREMENTAL_FORWARD_CHECKING,
    }
    strategy = v2.WeeklySearchStrategyV2(
        policy=policies[incremental, forward],
        variable_order="CHRONOLOGICAL",
        value_order="OPTION_ID_ASC",
        propagation="KNOWN_FAILURE_FORWARD_CHECK" if forward else "NONE",
    )
    limits = v2.WeeklySearchLimitsV2(
        max_nodes=20 if budget == "nodes20" else 2000,
        max_reserved_work=v2.WeeklyWorkV2(
            candidate_preparations=10000,
            combination_preparations=1000,
            predicate_obligations=100000,
            day_assessments=1000,
            week_assessments=1000,
            heuristic_evaluations=0 if budget == "heuristic0" else 100000,
            proof_verification_steps=10000,
        ),
        max_proof_records=480,
        max_proof_bytes=1048576,
        deadline=10 if budget == "expired" else None,
    )
    marks: dict[str, float] = {}
    phase = "execution"
    keys = (
        "full_day",
        "incremental_day",
        "full_week",
        "incremental_week",
        "state_initializations",
        "state_pushes",
        "state_pops",
    )
    operations = {stage: dict.fromkeys(keys, 0) for stage in ("execution", "verification")}
    original_compile, original_rest, original_check = (
        _compile_week,
        proof._rest,
        proof.check_weekly_proof_v2,
    )
    original_day, original_week = day_checks._evaluate_day, week_checks._evaluate_week
    original_init = incremental_state._IncrementalState.__init__
    original_push = incremental_state._IncrementalState.push
    original_pop = incremental_state._IncrementalState.pop

    def compile_program(*args, **kwargs):
        result = original_compile(*args, **kwargs)
        marks["prepared"] = perf_counter()
        return result

    def rest(*args, **kwargs):
        marks.setdefault("searched", perf_counter())
        return original_rest(*args, **kwargs)

    def check(*args, **kwargs):
        nonlocal phase
        phase = "verification"
        marks["check_start"] = perf_counter()
        try:
            return original_check(*args, **kwargs)
        finally:
            marks["check_end"] = perf_counter()
            phase = "execution"

    def day(*args, **kwargs):
        operations[phase]["full_day" if kwargs.get("quantity") is None else "incremental_day"] += 1
        return original_day(*args, **kwargs)

    def week(*args, **kwargs):
        operations[phase][
            "full_week" if kwargs.get("aggregates") is None else "incremental_week"
        ] += 1
        return original_week(*args, **kwargs)

    def initialize(*args, **kwargs):
        original_init(*args, **kwargs)
        operations[phase]["state_initializations"] += 1

    def push(*args, **kwargs):
        result = original_push(*args, **kwargs)
        operations[phase]["state_pushes"] += 1
        return result

    def pop(*args, **kwargs):
        original_pop(*args, **kwargs)
        operations[phase]["state_pops"] += 1

    with ExitStack() as stack:
        for obj, name, replacement in (
            (search, "_compile_week", compile_program),
            (search, "_rest", rest),
            (proof, "check_weekly_proof_v2", check),
            (proof, "_evaluate_day", day),
            (day_checks, "_evaluate_day", day),
            (proof, "_evaluate_week", week),
            (week_checks, "_evaluate_week", week),
            (incremental_state._IncrementalState, "__init__", initialize),
            (incremental_state._IncrementalState, "push", push),
            (incremental_state._IncrementalState, "pop", pop),
        ):
            stack.enter_context(patch.object(obj, name, replacement))
        if memory:
            if tracemalloc.is_tracing():
                raise ValueError("memory probe requires a separate tracing session")
            tracemalloc.start()
            stack.callback(tracemalloc.stop)
        start = perf_counter()
        result = search.solve_weekly_plan_v2(
            case.request,
            candidates=case.candidates,
            knowledge=case.knowledge,
            context=case.context,
            sources=case.sources,
            strategy=strategy,
            limits=limits,
            reuse_preparation=reuse,
            clock=(lambda: 10) if budget == "expired" else perf_counter,
        )
        end = perf_counter()
        peak = tracemalloc.get_traced_memory()[1] if memory else None
    if budget == "adequate" and result.outcome.value != expected.outcome:
        raise AssertionError("incremental benchmark differs from independent literal oracle")
    if result.witness:
        refs = sorted(case.sources.daily_source.options, key=lambda o: o.reference.option_id)
        if tuple(c.option for c in result.witness.trial.choices) != tuple(
            refs[i].reference for i in expected.first_witness or ()
        ):
            raise AssertionError("incremental benchmark first witness differs from literal oracle")
    if operations["verification"]["state_initializations"]:
        raise AssertionError("checker used incremental execution state")
    if operations["execution"]["state_pushes"] != operations["execution"]["state_pops"]:
        raise AssertionError("incremental benchmark did not unwind all frames")
    a = result.certificate.accounting
    prepared = marks.get("prepared", marks["searched"])
    return dict(
        case=case_id,
        fixture_digest=case.fixture_digest,
        incremental=incremental,
        forward=forward,
        reuse=reuse,
        budget=budget,
        memory=memory,
        policy=strategy.policy.value,
        limits=limits.model_dump(mode="json"),
        implementation="phase72d-worktree",
        python=sys.version,
        platform=platform.platform(),
        outcome=result.outcome.value,
        verification_complete=result.verification_complete,
        termination=result.termination,
        witness_digest=sha256(result.witness.model_dump_json(by_alias=True).encode()).hexdigest()
        if result.witness
        else None,
        preparation_seconds=prepared - start,
        search_seconds=marks["searched"] - prepared,
        checker_seconds=marks["check_end"] - marks["check_start"],
        total_seconds=end - start,
        nodes=a.logical_nodes,
        backtracks=a.backtracks,
        completed_leaves=sum(e.kind == "COMPLETED_LEAF" for e in result.certificate.events),
        day_evaluations=a.execution_work.day_assessments,
        week_evaluations=a.execution_work.week_assessments,
        derivation_operations=operations,
        execution_work=a.execution_work.model_dump(),
        verification_work=result.verification_work.model_dump(),
        proof_bytes=len(result.certificate.model_dump_json(by_alias=True).encode()),
        proof_reserved_bytes=a.proof_bytes_reserved,
        proof_records=len(result.certificate.events),
        peak_traced_bytes=peak,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases", nargs="+", choices=CASES, default=["early", "late", "exhaustive"]
    )
    parser.add_argument("--repetitions", type=int, choices=range(1, 6), default=3)
    parser.add_argument(
        "--budget", choices=("adequate", "nodes20", "heuristic0", "expired"), default="adequate"
    )
    parser.add_argument("--memory", action="store_true")
    parser.add_argument("--forward", action="store_true")
    parser.add_argument("--no-reuse", action="store_true")
    args = parser.parse_args()
    for case_id in args.cases:
        for repetition in range(args.repetitions):
            for incremental in (False, True) if repetition % 2 == 0 else (True, False):
                print(
                    json.dumps(
                        measure(
                            case_id,
                            incremental=incremental,
                            forward=args.forward,
                            budget=args.budget,
                            memory=args.memory,
                            reuse=not args.no_reuse,
                        )
                        | dict(repetition=repetition),
                        sort_keys=True,
                    ),
                    flush=True,
                )
