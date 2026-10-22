"""Repeated equal-input ordering comparisons, including independent verification.

Fixture construction/imports are excluded. Stage timings are observations, never
authority. Policies, budgets and reuse modes are explicit; no performance fallback.
"""

import argparse
import json
import platform
import sys
from contextlib import ExitStack
from hashlib import sha256
from time import perf_counter
from unittest.mock import patch

from savora_ai.core.reasoning import weekly_proof_v2 as proof
from savora_ai.core.reasoning import weekly_search_v2 as search
from savora_ai.core.reasoning.week_checks import _compile_week
from savora_ai.core.reasoning.weekly_bounds import _derive_bound
from savora_ai.core.reasoning.weekly_ordering import _ordered_domains
from savora_ai.evals.synthetic_week_cases import (
    build_week_case,
    exhaustive_oracle,
    literal_trial_status,
)
from savora_ai.schemas import weekly_search_v2 as v2

Policy = v2.WeeklyStrategyPolicyV2
POLICIES = {
    "chronological": Policy.CHRONOLOGICAL,
    "forward": Policy.FORWARD_CHECKING,
    "incremental": Policy.INCREMENTAL,
    "incremental-forward": Policy.INCREMENTAL_FORWARD_CHECKING,
    "reverse": Policy.REVERSE_VALUES,
    "static-mrv": Policy.STATIC_MRV,
    "static-mrv-forward": Policy.STATIC_MRV_FORWARD_CHECKING,
    "static-mrv-incremental": Policy.STATIC_MRV_INCREMENTAL,
    "static-mrv-incremental-forward": Policy.STATIC_MRV_INCREMENTAL_FORWARD_CHECKING,
}
CASES = ("single", "early", "late", "exhaustive", "day-pruning", "unknown-measurement")


def strategy(label: str) -> v2.WeeklySearchStrategyV2:
    policy = POLICIES[label]  # Unknown labels reject; never default to another policy.
    return v2.WeeklySearchStrategyV2(
        policy=policy,
        variable_order="STATIC_MRV_ORIGINAL_DOMAINS"
        if label.startswith("static-mrv")
        else "CHRONOLOGICAL",
        value_order="OPTION_ID_DESC" if label == "reverse" else "OPTION_ID_ASC",
        propagation="KNOWN_FAILURE_FORWARD_CHECK" if "forward" in label else "NONE",
    )


def measure(case_id: str, label: str, *, reuse: bool, budget: str = "adequate") -> dict:
    if budget not in ("adequate", "nodes20", "heuristic0", "expired"):
        raise ValueError("unknown explicit benchmark budget")
    case = build_week_case(case_id)
    expected = exhaustive_oracle(case.spec)
    selected = strategy(label)
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
    marks = {}
    calls = dict(forward_attempts=0, ordering_preparations=0)
    compile_original = _compile_week
    rest_original = proof._rest
    checker_original = proof.check_weekly_proof_v2
    bound_original = _derive_bound
    order_original = _ordered_domains

    def compile_program(*args, **kwargs):
        result = compile_original(*args, **kwargs)
        marks["prepared"] = perf_counter()
        return result

    def rest(*args, **kwargs):
        marks.setdefault("searched", perf_counter())
        return rest_original(*args, **kwargs)

    def checker(*args, **kwargs):
        marks["check_start"] = perf_counter()
        try:
            return checker_original(*args, **kwargs)
        finally:
            marks["check_end"] = perf_counter()

    def bound(*args, **kwargs):
        calls["forward_attempts"] += 1
        return bound_original(*args, **kwargs)

    def order(*args, **kwargs):
        calls["ordering_preparations"] += 1
        return order_original(*args, **kwargs)

    with ExitStack() as stack:
        for obj, name, replacement in (
            (search, "_compile_week", compile_program),
            (search, "_rest", rest),
            (proof, "check_weekly_proof_v2", checker),
            (search, "_derive_bound", bound),
            (search, "_ordered_domains", order),
        ):
            stack.enter_context(patch.object(obj, name, replacement))
        start = perf_counter()
        result = search.solve_weekly_plan_v2(
            case.request,
            candidates=case.candidates,
            knowledge=case.knowledge,
            context=case.context,
            sources=case.sources,
            strategy=selected,
            limits=limits,
            reuse_preparation=reuse,
            clock=(lambda: 10) if budget == "expired" else perf_counter,
        )
        end = perf_counter()
    if budget == "adequate" and (
        result.outcome.value != expected.outcome or not result.verification_complete
    ):
        raise AssertionError("ordering benchmark differs from independent product oracle")
    if result.witness:
        refs = sorted(case.sources.daily_source.options, key=lambda o: o.reference.option_id)
        chosen = tuple(
            next(i for i, o in enumerate(refs) if o.reference == c.option)
            for c in result.witness.trial.choices
        )
        if literal_trial_status(case.spec, chosen) != "PASS":
            raise AssertionError("ordering benchmark witness fails literal constraints")
    a = result.certificate.accounting
    # Ordering occurs after its reservation and before candidate preparation;
    # its measured time is inside the preparation stage below, not lost.
    prepared = marks.get("prepared", marks["searched"])
    return dict(
        implementation="phase72e-worktree",
        case=case_id,
        label=label,
        fixture_digest=case.fixture_digest,
        reuse=reuse,
        budget=budget,
        limits=limits.model_dump(mode="json"),
        policy=selected.policy.value,
        python=sys.version,
        platform=platform.platform(),
        outcome=result.outcome.value,
        verification_complete=result.verification_complete,
        termination=result.termination,
        witness_digest=sha256(result.witness.model_dump_json(by_alias=True).encode()).hexdigest()
        if result.witness
        else None,
        nodes=a.logical_nodes,
        backtracks=a.backtracks,
        completed_leaves=sum(e.kind == "COMPLETED_LEAF" for e in result.certificate.events),
        day_evaluations=a.execution_work.day_assessments,
        week_evaluations=a.execution_work.week_assessments,
        forward_attempts=calls["forward_attempts"],
        ordering_preparations=calls["ordering_preparations"],
        original_domain_ordering_units=(21 + sum(len(d) for d in case.spec.domains))
        if calls["ordering_preparations"]
        else 0,
        execution_work=a.execution_work.model_dump(),
        verification_work=result.verification_work.model_dump(),
        reserved_work=a.reserved_work.model_dump(),
        proof_records=len(result.certificate.events),
        proof_records_reserved=a.proof_records_reserved,
        proof_bytes=len(result.certificate.model_dump_json(by_alias=True).encode()),
        proof_bytes_reserved=a.proof_bytes_reserved,
        proof_event_bytes_written=a.proof_bytes_written,
        preparation_seconds=prepared - start,
        search_seconds=marks["searched"] - prepared,
        checker_seconds=marks["check_end"] - marks["check_start"],
        total_seconds=end - start,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases", nargs="+", choices=CASES, default=["single", "late", "day-pruning"]
    )
    parser.add_argument("--strategies", nargs="+", choices=tuple(POLICIES), default=list(POLICIES))
    parser.add_argument("--repetitions", type=int, choices=range(1, 6), default=3)
    parser.add_argument(
        "--budget", choices=("adequate", "nodes20", "heuristic0", "expired"), default="adequate"
    )
    parser.add_argument("--reuse", choices=("both", "on", "off"), default="both")
    args = parser.parse_args()
    modes = (True, False) if args.reuse == "both" else (args.reuse == "on",)
    for case_id in args.cases:
        for repetition in range(args.repetitions):
            labels = args.strategies if repetition % 2 == 0 else list(reversed(args.strategies))
            for reuse in modes if repetition % 2 == 0 else tuple(reversed(modes)):
                for label in labels:
                    record = measure(case_id, label, reuse=reuse, budget=args.budget)
                    record["repetition"] = repetition + 1
                    print(json.dumps(record, sort_keys=True), flush=True)
