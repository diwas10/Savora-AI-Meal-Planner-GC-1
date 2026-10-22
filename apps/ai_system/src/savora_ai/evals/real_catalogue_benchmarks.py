"""Small explicit new-source benchmark; never resumes the historical campaign.

Run --help. Timing includes construction and mandatory independent verification.
Optional tracemalloc measurements are separate instrumented observations.
"""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from savora_ai.core.reasoning.weekly import solve_weekly_plan
from savora_ai.core.reasoning.weekly_search_v2 import solve_weekly_plan_v2, verify_weekly_plan_v2
from savora_ai.schemas.candidates import CandidateRecipeFacts, RuleContext, validate_contract_json
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot
from savora_ai.schemas.weekly import WeeklyPlanningRequest, WeeklySearchLimits, WeeklySourceSnapshot
from savora_ai.schemas.weekly_search_v2 import (
    WeeklySearchLimitsV2,
    WeeklySearchStrategyV2,
    WeeklyStrategyPolicyV2,
    WeeklyWorkV2,
)
from savora_ai.schemas.weekly_solver_v2 import ComputedWeeklySolveResultV2

PROTOCOL = "member2-real-catalogue-comparison.v1"


def read_inputs(directory: Path) -> dict[str, Any]:
    records = dict(
        request=WeeklyPlanningRequest,
        knowledge=KnowledgeBaseSnapshot,
        context=RuleContext,
        sources=WeeklySourceSnapshot,
    )
    args: dict[str, Any] = {
        name: validate_contract_json(model, (directory / (name + ".json")).read_bytes())
        for name, model in records.items()
    }
    args["candidates"] = validate_contract_json(
        TypeAdapter(tuple[CandidateRecipeFacts, ...]), (directory / "candidates.json").read_bytes()
    )
    return args


def source_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((root / "apps/ai_system/src/savora_ai").rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def compare(directory: Path, *, repeats: int = 1, warmups: int = 0, memory: bool = False):
    if type(repeats) is not int or not 1 <= repeats <= 5 or not 0 <= warmups <= 2:
        raise ValueError("focused protocol requires 1..5 repeats and 0..2 warmups")
    inputs = read_inputs(directory)
    root = Path(__file__).resolve().parents[5]
    v1 = WeeklySearchLimits(
        max_nodes=10_000,
        max_option_evaluations=150,
        max_day_evaluations=4096,
        max_week_evaluations=4096,
        max_predicate_evaluations=1_000_000,
        max_proof_records=8192,
        max_proof_bytes=1_048_576,
    )
    v2 = WeeklySearchLimitsV2(
        max_nodes=10_000,
        max_reserved_work=WeeklyWorkV2(**{f: 1_000_000 for f in WeeklyWorkV2.model_fields}),
        max_proof_records=8192,
        max_proof_bytes=1_048_576,
    )
    strategy = WeeklySearchStrategyV2(
        policy=WeeklyStrategyPolicyV2.INCREMENTAL_FORWARD_CHECKING,
        variable_order="CHRONOLOGICAL",
        value_order="OPTION_ID_ASC",
        propagation="KNOWN_FAILURE_FORWARD_CHECK",
    )
    records = []
    for repetition in range(-warmups, repeats):
        # Alternate order; fixed stopping criterion and original domain identity.
        order = ("v1", "v2") if repetition % 2 == 0 else ("v2", "v1")
        witnesses = {}
        outcomes = {}
        for version in order:
            if memory:
                tracemalloc.start()
            start = time.perf_counter()
            result = (
                solve_weekly_plan(**inputs, limits=v1)
                if version == "v1"
                else solve_weekly_plan_v2(
                    **inputs, strategy=strategy, limits=v2, reuse_preparation=True
                )
            )
            elapsed = time.perf_counter() - start
            peak = tracemalloc.get_traced_memory()[1] if memory else None
            if memory:
                tracemalloc.stop()
            outcomes[version] = result.outcome.value
            witnesses[version] = result.witness.trial if result.witness is not None else None
            if isinstance(result, ComputedWeeklySolveResultV2):
                # Fresh source-bound verification is extra, outside paired timing.
                verify_weekly_plan_v2(result, **inputs)
            records.append(
                dict(
                    repetition=repetition,
                    warmup=repetition < 0,
                    version=version,
                    seconds=elapsed,
                    outcome=result.outcome.value,
                    witness_digest=witnesses[version].content_digest
                    if witnesses[version]
                    else None,
                    python_peak_bytes=peak,
                    instrumented=memory,
                )
            )
        equivalent = witnesses["v1"] is not None and witnesses["v1"] == witnesses["v2"]
        if repetition >= 0 and outcomes["v1"] == outcomes["v2"] == "FEASIBLE" and not equivalent:
            raise ValueError(
                "comparable fixed-domain fixture returned different verified witnesses"
            )
        for record in records[-2:]:
            record["paired_witness_equivalent"] = equivalent
    return dict(
        schema_version=PROTOCOL,
        observed_at=datetime.now(UTC).isoformat(),
        base_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        source_fingerprint=source_fingerprint(root),
        python=sys.version,
        platform=platform.platform(),
        processor=platform.processor(),
        logical_cpus=os.cpu_count(),
        input_files={
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.glob("*.json"))
        },
        v1_limits=v1.model_dump(mode="json", by_alias=True),
        v2_limits=v2.model_dump(mode="json", by_alias=True),
        strategy=strategy.model_dump(mode="json", by_alias=True),
        criterion="FIRST_FEASIBLE",
        records=records,
        historical_campaign="PARTIAL - CHECKPOINTED; unchanged 624/3007 cohort",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--warmups", type=int, default=0)
    parser.add_argument("--memory", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; evidence is append-only")
    result = compare(args.input_dir, repeats=args.repeats, warmups=args.warmups, memory=args.memory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(args.output)


if __name__ == "__main__":
    main()
