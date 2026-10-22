"""Paired synthetic v2 propagation measurements, including independent verification.

Fixture construction/imports are outside timing. Preparation includes input
admission and compilation; checker includes its own admission and preparation.
Trace-memory runs are separate and must not enter ordinary timing medians.
"""

import argparse
import json
import tracemalloc
from contextlib import ExitStack
from hashlib import sha256
from time import perf_counter
from unittest.mock import patch

from savora_ai.core.reasoning import weekly_proof_v2 as proof
from savora_ai.core.reasoning import weekly_search_v2 as search
from savora_ai.core.reasoning.week_checks import _compile_week
from savora_ai.evals.synthetic_week_cases import build_week_case, exhaustive_oracle
from savora_ai.schemas import weekly_search_v2 as v2

CASES = (
    "early",
    "late",
    "day-pruning",
    "week-quantity",
    "unknown-refuted",
    "exhaustive",
    "unknown-measurement",
)


def measure(
    case_id: str,
    *,
    forward: bool,
    budget: str = "adequate",
    memory: bool = False,
    reuse: bool = True,
) -> dict:
    case = build_week_case(case_id)
    expected = exhaustive_oracle(case.spec)
    strategy = v2.WeeklySearchStrategyV2(
        policy=v2.WeeklyStrategyPolicyV2.FORWARD_CHECKING
        if forward
        else v2.WeeklyStrategyPolicyV2.CHRONOLOGICAL,
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
    original_compile, original_rest, original_check = (
        _compile_week,
        proof._rest,
        proof.check_weekly_proof_v2,
    )

    def compile_program(*args, **kwargs):
        result = original_compile(*args, **kwargs)
        marks["prepared"] = perf_counter()
        return result

    def rest(*args, **kwargs):
        marks.setdefault("searched", perf_counter())
        return original_rest(*args, **kwargs)

    def check(*args, **kwargs):
        marks["check_start"] = perf_counter()
        result = original_check(*args, **kwargs)
        marks["check_end"] = perf_counter()
        return result

    with ExitStack() as stack:
        stack.enter_context(patch.object(search, "_compile_week", compile_program))
        stack.enter_context(patch.object(search, "_rest", rest))
        stack.enter_context(patch.object(proof, "check_weekly_proof_v2", check))
        if memory:
            if tracemalloc.is_tracing():
                raise ValueError("memory probe requires its own tracing session")
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
        raise AssertionError("benchmark outcome differs from independent oracle")
    if result.witness is not None:
        refs = sorted(case.sources.daily_source.options, key=lambda o: o.reference.option_id)
        if tuple(c.option for c in result.witness.trial.choices) != tuple(
            refs[i].reference for i in expected.first_witness or ()
        ):
            raise AssertionError("benchmark witness differs from literal oracle")
    account = result.certificate.accounting
    prepared = marks.get("prepared", marks["searched"])
    return dict(
        case=case_id,
        fixture_digest=case.fixture_digest,
        forward=forward,
        reuse=reuse,
        budget=budget,
        limits=limits.model_dump(mode="json"),
        memory=memory,
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
        nodes=account.logical_nodes,
        pruned_subtrees=sum(e.kind == "FORWARD_CHECK_CLOSURE" for e in result.certificate.events),
        completed_leaves=sum(e.kind == "COMPLETED_LEAF" for e in result.certificate.events),
        execution_work=account.execution_work.model_dump(),
        verification_work=result.verification_work.model_dump(),
        proof_records=len(result.certificate.events),
        proof_reserved_records=account.proof_records_reserved,
        proof_bytes=len(result.certificate.model_dump_json(by_alias=True).encode()),
        proof_reserved_bytes=account.proof_bytes_reserved,
        peak_traced_bytes=peak,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--repetitions", type=int, choices=range(1, 6), default=3)
    parser.add_argument(
        "--budget", choices=("adequate", "nodes20", "heuristic0", "expired"), default="adequate"
    )
    parser.add_argument("--memory", action="store_true")
    parser.add_argument("--no-reuse", action="store_true")
    args = parser.parse_args()
    for case_id in args.cases:
        for repetition in range(args.repetitions):
            # Alternate pair order to reduce systematic first-mode timing bias.
            for forward in (False, True) if repetition % 2 == 0 else (True, False):
                print(
                    json.dumps(
                        measure(
                            case_id,
                            forward=forward,
                            budget=args.budget,
                            memory=args.memory,
                            reuse=not args.no_reuse,
                        )
                        | dict(repetition=repetition),
                        sort_keys=True,
                    ),
                    flush=True,
                )
