"""Observational preparation comparison; wrappers never influence eligibility.

Run before editing, then again after, on identical fixture digests. Timings include
input admission/compilation in preparation; search stops before certificate encoding;
verification includes its own admission, preparation and coverage checks. Remaining
serialization/output-admission time is visible in total. Optional traced allocation
is a separate instrumentation mode, not RSS. No benchmark result is proof authority.
"""

import argparse
import importlib
import json
import tracemalloc
from contextlib import ExitStack
from hashlib import sha256
from time import perf_counter
from typing import Any
from unittest.mock import patch

from savora_ai.core.reasoning import combinations, filtering, weekly_proof_v2, weekly_search_v2
from savora_ai.core.reasoning.week_checks import _compile_week
from savora_ai.evals.synthetic_week_cases import build_week_case
from savora_ai.schemas.weekly_search_v2 import (
    WeeklySearchLimitsV2,
    WeeklySearchStrategyV2,
    WeeklyStrategyPolicyV2,
    WeeklyWorkV2,
)


def measure(case_id: str, *, reuse: bool = False, memory: bool = False) -> dict:
    case = build_week_case(case_id)
    policy = WeeklySearchStrategyV2(
        policy=WeeklyStrategyPolicyV2.CHRONOLOGICAL,
        variable_order="CHRONOLOGICAL",
        value_order="OPTION_ID_ASC",
        propagation="NONE",
    )
    limits = WeeklySearchLimitsV2(
        max_nodes=2000,
        max_reserved_work=WeeklyWorkV2(
            candidate_preparations=10000,
            combination_preparations=1000,
            predicate_obligations=100000,
            day_assessments=1000,
            week_assessments=1000,
            proof_verification_steps=10000,
        ),
        max_proof_records=480,
        max_proof_bytes=1048576,
    )
    marks: dict[str, float] = {}
    counts = {"execution_filters": 0, "verification_filters": 0, "combinations": 0}
    phase = "execution"
    original_filter = filtering.filter_candidates
    original_combo = combinations._combination_checks
    original_check = weekly_proof_v2.check_weekly_proof_v2
    original_compile = _compile_week
    original_rest = weekly_proof_v2._rest

    def filtered(*args, **kwargs):
        counts[phase + "_filters"] += 1
        return original_filter(*args, **kwargs)

    def combo(*args, **kwargs):
        counts["combinations"] += 1
        return original_combo(*args, **kwargs)

    def compiled(*args, **kwargs):
        value = original_compile(*args, **kwargs)
        marks["prepared"] = perf_counter()
        return value

    def rest(*args, **kwargs):
        marks.setdefault("searched", perf_counter())
        return original_rest(*args, **kwargs)

    def checked(*args, **kwargs):
        nonlocal phase
        phase = "verification"
        marks["verify_start"] = perf_counter()
        value = original_check(*args, **kwargs)
        marks["verify_end"] = perf_counter()
        return value

    modules = [combinations, weekly_search_v2, weekly_proof_v2]
    try:
        modules.append(importlib.import_module("savora_ai.core.reasoning.preparation"))
    except ModuleNotFoundError as error:
        if error.name != "savora_ai.core.reasoning.preparation":
            raise
    with ExitStack() as stack:
        for module in modules:
            if hasattr(module, "filter_candidates"):
                stack.enter_context(patch.object(module, "filter_candidates", filtered))
        stack.enter_context(patch.object(combinations, "_combination_checks", combo))
        stack.enter_context(patch.object(weekly_search_v2, "_compile_week", compiled))
        stack.enter_context(patch.object(weekly_search_v2, "_rest", rest))
        stack.enter_context(patch.object(weekly_proof_v2, "check_weekly_proof_v2", checked))
        if memory:
            if tracemalloc.is_tracing():
                raise ValueError("measurement requires its own tracing session")
            tracemalloc.start()
            stack.callback(tracemalloc.stop)
        started = perf_counter()
        extra: dict[str, Any] = {"reuse_preparation": True} if reuse else {}
        result = weekly_search_v2.solve_weekly_plan_v2(
            case.request,
            candidates=case.candidates,
            knowledge=case.knowledge,
            context=case.context,
            sources=case.sources,
            strategy=policy,
            limits=limits,
            **extra,
        )
        finished = perf_counter()
        peak = tracemalloc.get_traced_memory()[1] if memory else None
    return dict(
        case=case_id,
        fixture_digest=case.fixture_digest,
        reuse=reuse,
        memory=memory,
        **counts,
        preparation_seconds=marks["prepared"] - started,
        search_seconds=marks["searched"] - marks["prepared"],
        verification_seconds=marks["verify_end"] - marks["verify_start"],
        total_seconds=finished - started,
        outcome=result.outcome.value,
        witness_digest=sha256(result.witness.model_dump_json(by_alias=True).encode()).hexdigest()
        if result.witness
        else None,
        proof_bytes=len(result.certificate.model_dump_json(by_alias=True).encode()),
        peak_traced_bytes=peak,
        logical_accounting=result.certificate.accounting.model_dump(mode="json"),
        preparation_accounting=result.model_dump(mode="json").get("execution_preparation"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse", action="store_true")
    parser.add_argument("--memory", action="store_true")
    parser.add_argument("--repetitions", type=int, default=3, choices=range(1, 6))
    args = parser.parse_args()
    for case_id in ("early", "repeated-identities"):
        for repetition in range(args.repetitions):
            print(
                json.dumps(
                    measure(case_id, reuse=args.reuse, memory=args.memory)
                    | dict(repetition=repetition),
                    sort_keys=True,
                ),
                flush=True,
            )
