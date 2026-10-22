"""Versioned, resumable, sequential Phase 7.4 comparison harness.

No production implementation is changed. Native mandatory checking remains in
the timed call; explicit authority verification and final encoding are included
in the verified-pipeline total. Fixture/oracle/provenance setup is separate.
"""

import argparse
import ctypes
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError, model_validator

from savora_ai.core.reasoning import planned_swap, weekly, weekly_search_v2
from savora_ai.evals.phase7_comparison_cases import (
    ORACLE_VERSION,
    FrozenModel,
    SwapSpec,
    WeeklySpec,
    build_swap,
    build_weekly,
    literal_week_status,
    ordered_digest,
    swap_oracle,
    swap_specs,
    weekly_oracle,
    weekly_specs,
)
from savora_ai.schemas import planned_swap as s
from savora_ai.schemas import weekly_search_v2 as v2
from savora_ai.schemas.weekly import WeeklySearchLimits
from savora_ai.schemas.weekly_solver import ComputedWeeklySolveResult

PROTOCOL = "member2-phase7-comparison.v1"
STRATEGIES = (
    "CHRONOLOGICAL",
    "FORWARD_CHECKING",
    "INCREMENTAL",
    "INCREMENTAL_FORWARD_CHECKING",
    "REVERSE_VALUES",
    "STATIC_MRV",
    "STATIC_MRV_FORWARD_CHECKING",
    "STATIC_MRV_INCREMENTAL",
    "STATIC_MRV_INCREMENTAL_FORWARD_CHECKING",
)
ROOT = Path(__file__).resolve().parents[5]
NA = {"status": "NOT_AVAILABLE", "reason": "native protocol does not expose this metric"}


class ComparisonConfig(FrozenModel):
    schema_version: Literal["phase7-comparison-config.v1"] = "phase7-comparison-config.v1"
    cohort_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    repetitions: int = Field(default=10, ge=10, le=100)
    warmups: Literal[2] = 2
    memory_probes: int = Field(default=3, ge=3, le=10)
    order_policy: Literal["ROTATE_VARIANTS_BY_BLOCK_V1"] = "ROTATE_VARIANTS_BY_BLOCK_V1"
    oracle_version: Literal["literal-fixed-cartesian-and-swap.v1"] = ORACLE_VERSION
    quantile_policy: Literal["INCLUSIVE_LINEAR_QUARTILES"] = "INCLUSIVE_LINEAR_QUARTILES"


class Group(FrozenModel):
    family: Literal["WEEKLY", "SWAP"]
    case_id: str
    policy: str
    reuse: bool | None = None
    preparation_capacity: int = Field(default=1, ge=0, le=1)
    search_cache_capacity: int = Field(default=64, ge=0, le=4096)
    track: Literal["ADEQUATE", "EQUAL", "MEMORY"] = "ADEQUATE"
    budget: str = "ADEQUATE"
    timing: bool = False

    @model_validator(mode="after")
    def executable(self):
        if self.family == "WEEKLY":
            if self.policy not in (*STRATEGIES, "V1"):
                raise ValueError("unsupported weekly comparison policy")
            if (self.policy == "V1") != (self.reuse is None):
                raise ValueError("v1 has no preparation-reuse switch; v2 requires one")
        elif self.policy not in ("VALIDATE", "SELECT") or self.reuse is not None:
            raise ValueError("unsupported swap comparison policy")
        if self.track == "MEMORY" and self.timing:
            raise ValueError("memory timings cannot enter latency groups")
        return self

    @property
    def group_id(self) -> str:
        return ordered_digest(self.model_dump())[:24]


class Job(FrozenModel):
    group_id: str
    phase: Literal["CORRECTNESS", "WARMUP", "MEASURE", "MEMORY"]
    repetition: int = Field(ge=0)
    order: int = Field(ge=0)

    def key(self, cohort_id: str) -> str:
        return ordered_digest([cohort_id, self.group_id, self.phase, self.repetition])


class ComparisonManifest(FrozenModel):
    schema_version: Literal["phase7-comparison-manifest.v1"] = "phase7-comparison-manifest.v1"
    config: ComparisonConfig
    created_utc: str
    git_head: str
    source_fingerprints: dict[str, str]
    dirty_source_fingerprint: str
    source_policy: str
    initial_git_status: str
    environment: dict[str, Any]
    weekly: tuple[WeeklySpec, ...]
    swaps: tuple[SwapSpec, ...]
    workloads: dict[str, dict[str, Any]]
    groups: tuple[Group, ...]
    jobs: tuple[Job, ...]
    manifest_digest: str


class RunRecord(FrozenModel):
    schema_version: Literal["phase7-comparison-run.v1"] = "phase7-comparison-run.v1"
    protocol: Literal["member2-phase7-comparison.v1"] = PROTOCOL
    run_id: str
    cohort_id: str
    manifest_digest: str
    job: Job
    group: Group
    git_head: str
    source_fingerprints: dict[str, str]
    dirty_source_fingerprint: str
    workload_fingerprint: str
    invocation_fingerprint: str
    oracle_version: str
    oracle: dict[str, Any]
    bindings: dict[str, Any]
    limits: dict[str, Any]
    environment: dict[str, Any]
    outcome: str
    native_outcome: str
    expected_outcome: str
    correctness: bool
    proof: dict[str, Any]
    witness: dict[str, Any] | None
    metrics: dict[str, Any]
    timing: dict[str, Any]
    memory: dict[str, Any]
    error: str | None = None

    @model_validator(mode="after")
    def measured_interval(self):
        total = self.timing.get("total_seconds")
        if isinstance(total, bool) or not isinstance(total, (int, float)):
            raise ValueError("total_seconds requires a finite nonnegative observation")
        if not math.isfinite(total) or total < 0:
            raise ValueError("total_seconds requires a finite nonnegative observation")
        if type(self.timing.get("traced")) is not bool:
            raise ValueError("traced requires an explicit boolean")
        return self


def git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()


def source_state() -> tuple[dict[str, str], str]:
    # All relevant executable files, including untracked harness/tests. Generated
    # handoff/evidence are outputs, not source; their hashes are separate artifacts.
    names = {
        p.relative_to(ROOT).as_posix()
        for folder in ("apps/ai_system", "apps/backend")
        for p in (ROOT / folder).rglob("*.py")
        if "__pycache__" not in p.parts
    }
    names.update(
        n
        for n in ("pyproject.toml", "uv.lock", "AGENTS.md", "ARCHITECTURE.md")
        if (ROOT / n).is_file()
    )
    hashes = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in sorted(names)}
    changed = (
        subprocess.check_output(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd=ROOT
        )
        .decode()
        .split("\0")
    )
    dirty = {entry[3:]: hashes[entry[3:]] for entry in changed if entry and entry[3:] in hashes}
    return hashes, ordered_digest(dirty)


def environment() -> dict[str, Any]:
    return dict(
        python=sys.version,
        executable=sys.executable,
        platform=platform.platform(),
        cpu=platform.processor() or "NOT_AVAILABLE",
        logical_cpus=os.cpu_count(),
        physical_memory=physical_memory(),
        pydantic=importlib.metadata.version("pydantic"),
        pid=os.getpid(),
        host_load="NOT_AVAILABLE: no cross-platform host-idleness sensor",
        timer="time.perf_counter; finite monotonic seconds",
    )


def physical_memory() -> dict[str, Any]:
    if os.name != "nt":
        return dict(NA)

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_page", ctypes.c_ulonglong),
            ("available_page", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return dict(NA)
    return dict(
        total_bytes=status.total_physical,
        available_bytes=status.available_physical,
        load_percent=status.load,
        semantics="Windows GlobalMemoryStatusEx at observation",
    )


def wire(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, dict):
        return {k: wire(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [wire(v) for v in value]
    return value


def strategy(name: str) -> v2.WeeklySearchStrategyV2:
    if name not in STRATEGIES:
        raise ValueError("unsupported executable strategy")
    return v2.WeeklySearchStrategyV2(
        policy=v2.WeeklyStrategyPolicyV2[name],
        variable_order="STATIC_MRV_ORIGINAL_DOMAINS"
        if name.startswith("STATIC_MRV")
        else "CHRONOLOGICAL",
        value_order="OPTION_ID_DESC" if name == "REVERSE_VALUES" else "OPTION_ID_ASC",
        propagation="KNOWN_FAILURE_FORWARD_CHECK" if "FORWARD_CHECKING" in name else "NONE",
    )


def groups_for(config: ComparisonConfig) -> tuple[Group, ...]:
    groups = []
    variants = [(p, reuse) for p in STRATEGIES for reuse in (False, True)] + [("V1", None)]
    for spec in weekly_specs():
        groups.extend(
            Group(family="WEEKLY", case_id=spec.case_id, policy=p, reuse=reuse, timing=spec.timing)
            for p, reuse in variants
        )
    # Equal inputs/caps for all v2 strategies; v1's distinct work units are labelled.
    budgets = [
        "NODES0",
        "NODES1",
        "NODES20",
        "NODES21",
        "PROOF0",
        "BYTES0",
        "BYTES_ONE_SHORT",
        "EXPIRED",
        "LIVE",
    ]
    budgets += ["WORK0:" + n for n in v2.WeeklyWorkV2.model_fields]
    for budget in budgets:
        groups.extend(
            Group(
                family="WEEKLY",
                case_id="product-1",
                policy=p,
                reuse=reuse,
                track="EQUAL",
                budget=budget,
            )
            for p, reuse in variants
            if p != "V1" or not budget.startswith("WORK0:")
        )
    for p in STRATEGIES:
        groups.append(
            Group(
                family="WEEKLY",
                case_id="late",
                policy=p,
                reuse=True,
                preparation_capacity=0,
                track="EQUAL",
                budget="CACHE0",
            )
        )
    for capacity in (0, 1, 4096):
        for policy, reuse in variants:
            groups.append(
                Group(
                    family="WEEKLY",
                    case_id="late",
                    policy=policy,
                    reuse=reuse,
                    search_cache_capacity=capacity,
                    track="EQUAL",
                    budget="CACHE",
                )
            )
    for spec in swap_specs():
        groups.append(
            Group(family="SWAP", case_id=spec.case_id, policy=spec.mode, timing=spec.timing)
        )
    for mode, name in (("VALIDATE", "target-00"), ("SELECT", "select-early")):
        for budget in [
            "CALLS0",
            "CALLS_ONE_SHORT",
            "PROOF0",
            "BYTES0",
            "BYTES_ONE_SHORT",
            "RESULT0",
            "EXPIRED",
            "LIVE",
            "VERIFY_DEADLINE",
        ] + ["WORK0:" + n for n in s.SwapWork.model_fields]:
            groups.append(
                Group(family="SWAP", case_id=name, policy=mode, track="EQUAL", budget=budget)
            )
    groups.append(
        Group(
            family="SWAP",
            case_id="select-early",
            policy="SELECT",
            track="EQUAL",
            budget="MALFORMED_RANKING",
        )
    )
    for policy, reuse in (
        ("CHRONOLOGICAL", False),
        ("CHRONOLOGICAL", True),
        ("INCREMENTAL", False),
        ("INCREMENTAL", True),
        ("STATIC_MRV", False),
        ("STATIC_MRV", True),
    ):
        groups.append(
            Group(family="WEEKLY", case_id="product-1", policy=policy, reuse=reuse, track="MEMORY")
        )
    for policy in ("CHRONOLOGICAL", "STATIC_MRV", "STATIC_MRV_FORWARD_CHECKING"):
        groups.append(
            Group(family="WEEKLY", case_id="late", policy=policy, reuse=False, track="MEMORY")
        )
    for policy, name in (("VALIDATE", "target-00"), ("SELECT", "select-early")):
        groups.append(Group(family="SWAP", case_id=name, policy=policy, track="MEMORY"))
    if len({g.group_id for g in groups}) != len(groups):
        raise ValueError("duplicate benchmark groups")
    return tuple(groups)


def jobs_for(config: ComparisonConfig, groups: tuple[Group, ...]) -> tuple[Job, ...]:
    jobs = []

    def add(group, phase, repetition):
        jobs.append(
            Job(group_id=group.group_id, phase=phase, repetition=repetition, order=len(jobs))
        )

    for group in groups:
        if group.track != "MEMORY":
            add(group, "CORRECTNESS", 0)
    # Balanced deterministic blocks over case+track, alternating all variants.
    blocks: dict[tuple[str, str], list[Group]] = {}
    for group in groups:
        if group.timing:
            blocks.setdefault((group.family, group.case_id), []).append(group)
    for block in blocks.values():
        for i in range(config.warmups + config.repetitions):
            rotation = i % len(block)
            for group in block[rotation:] + block[:rotation]:
                add(
                    group,
                    "WARMUP" if i < config.warmups else "MEASURE",
                    i if i < config.warmups else i - config.warmups,
                )
    for group in groups:
        if group.track == "MEMORY":
            for i in range(config.memory_probes):
                add(group, "MEMORY", i)
    return tuple(jobs)


def bindings(authority: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for key in (
        "request",
        "knowledge",
        "context",
        "sources",
        "saved_plan",
        "locks",
        "permission",
        "bridge",
        "domain",
        "ranking",
    ):
        if key in authority:
            item = authority[key]
            result[key] = {
                n: wire(getattr(item, n))
                for n in (
                    "schema_version",
                    "version",
                    "content_digest",
                    "reference",
                    "workflow_policy_version",
                )
                if hasattr(item, n)
            }
    return result


def freeze(config: ComparisonConfig, directory: Path) -> ComparisonManifest:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "manifest.json"
    if target.exists():
        raise FileExistsError("frozen manifest already exists; use resume")
    sources, dirty = source_state()
    env = environment()
    workloads = {}
    folder = directory / "workloads"
    folder.mkdir(exist_ok=True)
    for family, specs in (("WEEKLY", weekly_specs()), ("SWAP", swap_specs())):
        for spec in specs:
            authority = (
                build_weekly(spec).authority() if isinstance(spec, WeeklySpec) else build_swap(spec)
            )
            raw = wire(authority)
            key = family + ":" + spec.case_id
            workloads[key] = dict(
                fingerprint=ordered_digest(raw),
                bindings=bindings(authority),
                oracle=weekly_oracle(spec) if isinstance(spec, WeeklySpec) else swap_oracle(spec),
            )
            (folder / (family.lower() + "-" + spec.case_id + ".json")).write_text(
                json.dumps(raw, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
            )
    groups = groups_for(config)
    body: dict[str, Any] = dict(
        config=config,
        created_utc=datetime.now(UTC).isoformat(),
        git_head=git("rev-parse", "HEAD"),
        source_fingerprints=sources,
        dirty_source_fingerprint=dirty,
        source_policy=(
            "all AI/backend Python + root locks/config/engineering instructions; "
            "generated reports/evidence excluded"
        ),
        initial_git_status=git("status", "--short"),
        environment=env,
        weekly=weekly_specs(),
        swaps=swap_specs(),
        workloads=workloads,
        groups=groups,
        jobs=jobs_for(config, groups),
    )
    digest = ordered_digest(wire(body))
    manifest = ComparisonManifest(**body, manifest_digest=digest)
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def load_manifest(directory: Path, *, check_sources=True) -> ComparisonManifest:
    manifest = ComparisonManifest.model_validate_json(
        (directory / "manifest.json").read_text(encoding="utf-8")
    )
    body = manifest.model_dump(exclude={"schema_version", "manifest_digest"})
    if ordered_digest(body) != manifest.manifest_digest:
        raise ValueError("manifest fingerprint mismatch")
    if manifest.weekly != weekly_specs() or manifest.swaps != swap_specs():
        raise ValueError("frozen case declaration mismatch with code-owned registry")
    expected_workloads = {
        family + ":" + spec.case_id
        for family, specs in (("WEEKLY", manifest.weekly), ("SWAP", manifest.swaps))
        for spec in specs
    }
    if set(manifest.workloads) != expected_workloads:
        raise ValueError("frozen workload inventory mismatch")
    if manifest.groups != groups_for(manifest.config) or manifest.jobs != jobs_for(
        manifest.config, manifest.groups
    ):
        raise ValueError("frozen group/job inventory differs from protocol")
    if check_sources:
        sources, dirty = source_state()
        if (
            sources != manifest.source_fingerprints
            or dirty != manifest.dirty_source_fingerprint
            or git("rev-parse", "HEAD") != manifest.git_head
        ):
            raise ValueError("source/HEAD mismatch; start a separate cohort")
    for key, stamp in manifest.workloads.items():
        family, case = key.split(":", 1)
        raw = json.loads(
            (directory / "workloads" / (family.lower() + "-" + case + ".json")).read_text(
                encoding="utf-8"
            )
        )
        if ordered_digest(raw) != stamp["fingerprint"]:
            raise ValueError("frozen workload fingerprint mismatch")
    return manifest


def operational_limits(group: Group):
    budget = group.budget
    deadline = 1.0 if budget in ("EXPIRED", "LIVE", "VERIFY_DEADLINE") else None
    if group.family == "WEEKLY":
        nodes = int(budget[5:]) if budget.startswith("NODES") else 10000
        proof = 0 if budget == "PROOF0" else 8192
        byte = 0 if budget == "BYTES0" else 1_048_575 if budget == "BYTES_ONE_SHORT" else 1_048_576
        if group.policy == "V1":
            return WeeklySearchLimits(
                max_nodes=nodes,
                max_option_evaluations=150,
                max_day_evaluations=4096,
                max_week_evaluations=4096,
                max_predicate_evaluations=1_000_000,
                max_cache_entries=group.search_cache_capacity,
                max_proof_records=proof,
                max_proof_bytes=byte,
                deadline=deadline,
            )
        work = {n: 1_000_000 for n in v2.WeeklyWorkV2.model_fields}
        if budget.startswith("WORK0:"):
            work[budget.split(":")[1]] = 0
        return v2.WeeklySearchLimitsV2(
            max_nodes=nodes,
            max_reserved_work=v2.WeeklyWorkV2(**work),
            max_proof_records=proof,
            max_proof_bytes=byte,
            max_cache_entries=group.search_cache_capacity,
            deadline=deadline,
        )
    work = {n: 1_000_000 for n in s.SwapWork.model_fields}
    if budget.startswith("WORK0:"):
        work[budget.split(":")[1]] = 0
    body: dict[str, Any] = dict(
        max_reserved_work=s.SwapWork(**work),
        max_proof_records=0 if budget == "PROOF0" else 1024,
        max_proof_bytes=0
        if budget == "BYTES0"
        else 1_048_575
        if budget == "BYTES_ONE_SHORT"
        else 1_048_576,
        max_result_bytes=0 if budget == "RESULT0" else 1_048_576,
        max_full_validations=0
        if budget == "CALLS0"
        else (1 if group.policy == "SELECT" else 0)
        if budget == "CALLS_ONE_SHORT"
        else 51
        if group.policy == "SELECT"
        else 1,
        deadline=deadline,
    )
    return (
        s.SwapSelectionLimits(**body, max_domain_visits=50)
        if group.policy == "SELECT"
        else s.SwapValidationLimits(**body)
    )


def rss() -> dict[str, Any]:
    if os.name != "nt":
        return dict(NA)

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
            (n, ctypes.c_size_t)
            for n in (
                "peak_working_set",
                "working_set",
                "peak_paged",
                "paged",
                "peak_nonpaged",
                "nonpaged",
                "pagefile",
                "peak_pagefile",
            )
        ]

    counter = Counters()
    counter.cb = ctypes.sizeof(counter)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)
    if not psapi.GetProcessMemoryInfo(
        kernel.GetCurrentProcess(), ctypes.byref(counter), counter.cb
    ):
        return dict(NA)
    return dict(
        working_set_bytes=counter.working_set,
        lifetime_peak_working_set_bytes=counter.peak_working_set,
        semantics=(
            "Windows process working set; lifetime peak includes imports/fixtures; no subtraction"
        ),
    )


def assess_result(
    group: Group, spec, authority, result, checked, *, oracle: dict[str, Any] | None = None
) -> tuple[bool, dict[str, Any] | None]:
    if oracle is None:
        oracle = weekly_oracle(spec) if isinstance(spec, WeeklySpec) else swap_oracle(spec)
    outcome = result.outcome.value
    control = outcome == "TIMEOUT"
    complete = bool(getattr(result, "verification_complete", True))
    accepted = checked is not None and (getattr(checked, "accepted", True))
    if (group.budget == "EXPIRED" and not control) or (group.budget == "LIVE" and control):
        return False, None
    if control:
        return getattr(result, "witness", None) is None and getattr(
            result, "resulting_plan", None
        ) is None, None
    if outcome != oracle["outcome"] or not complete or not accepted:
        return False, None
    if group.family == "WEEKLY":
        witness = result.witness
        if witness is None:
            return outcome != "FEASIBLE", None
        choices = tuple(int(c.option.option_id.split(":")[1]) for c in witness.trial.choices)
        # IDs are fixture indexes only here; swap option identities are never parsed.
        if literal_week_status(spec, choices) != "PASS":
            return False, None
        if group.policy in ("V1", "CHRONOLOGICAL") and tuple(oracle["first_witness"]) != choices:
            return False, None
        return True, dict(
            choices=choices, reference=wire(witness.trial), digest=ordered_digest(wire(witness))
        )
    if group.policy == "SELECT":
        visits = result.certificate.visits
        expected_refs = [authority["domain"].options[i] for i, _ in oracle["visits"]]
        if [v.option for v in visits] != expected_refs or [v.outcome.value for v in visits] != [
            v for _, v in oracle["visits"]
        ]:
            return False, None
    plan = result.resulting_plan
    if plan is None:
        return outcome != "VALID", None
    target = spec.target
    if any(
        old != new
        for i, (old, new) in enumerate(
            zip(authority["saved_plan"].snapshot.slots, plan.slots, strict=True)
        )
        if i != target
    ):
        return False, None
    expected = (
        authority["replacement"]
        if group.policy == "VALIDATE"
        else authority["domain"].options[oracle["selected"]]
    )
    if plan.slots[target].option.reference != expected:
        return False, None
    if group.policy == "SELECT":
        if result.selected != expected or result.exhaustive:
            return False, None
        visits = result.certificate.visits
        expected_refs = [authority["domain"].options[i] for i, _ in oracle["visits"]]
        if [v.option for v in visits] != expected_refs:
            return False, None
    return True, dict(
        option=wire(expected),
        plan_digest=plan.content_digest,
        unchanged_payloads=20,
        selected_domain_index=oracle["selected"],
        selected_rank=len(oracle["visits"]) - 1 if group.policy == "SELECT" else None,
        criterion="FIRST_VALID_IN_ELIGIBLE_ORDER"
        if group.policy == "SELECT"
        else "SINGLE_CANDIDATE",
    )


def metrics(result: Any, group: Group, *, external_interrupted=False) -> dict[str, Any]:
    certificate: Any = getattr(result, "certificate", None)
    data: dict[str, Any] = dict(
        nodes=dict(NA),
        backtracks=dict(NA),
        leaves=dict(NA),
        execution_work=dict(NA),
        verification_work=dict(NA),
        search_cache=dict(NA),
        preparation=dict(NA),
        exhaustion_stage=wire(
            getattr(result, "stage", None) or getattr(result, "termination", None)
        ),
        proof_records=dict(NA),
        proof_bytes=0
        if certificate is None
        else len(certificate.model_dump_json(by_alias=True).encode()),
        proof_reservations=dict(NA),
        physical_calls=dict(NA),
    )
    if group.family == "SWAP":
        data.update(
            execution_work=wire(result.actual_execution),
            verification_work=wire(result.actual_verification),
            proof_bytes=result.proof_bytes,
            reason=result.reason,
            operation_scope=wire(getattr(result, "operation_scope", dict(NA))),
            failure_scope=wire(getattr(result, "failure_scope", dict(NA))),
        )
        if certificate is not None:
            if group.policy == "SELECT":
                data.update(
                    reserved_proof_records=sum(r.proof_records for r in certificate.reservations),
                    outer_reservation_records=len(certificate.reservations),
                    proof_reservations=wire(certificate.reservations),
                    hard_filter_counts=dict(Counter(c.lane for c in certificate.prechecks)),
                    visited=len(certificate.visits),
                    unvisited=len(certificate.unvisited),
                    exhaustive=result.exhaustive,
                    reserved_validation_calls=sum(
                        r.validation_calls for r in certificate.reservations
                    ),
                    logical_full_validations=result.actual_execution.full_validations,
                )
            else:
                data.update(
                    proof_records=len(certificate.reservations.operations),
                    proof_reservations=wire(certificate.reservations),
                )
    elif group.policy == "V1":
        assert certificate is not None
        stats = certificate.statistics
        if stats.termination is not None:
            data["exhaustion_stage"] = dict(stage="EXECUTION", reason=wire(stats.termination))
        elif result.timing.validation_deadline_reached:
            data["exhaustion_stage"] = dict(stage="NATIVE_OUTPUT_VERIFICATION", reason="DEADLINE")
        data.update(
            nodes=stats.nodes,
            backtracks=stats.backtracks,
            leaves=sum(r.kind == "LEAF" for r in certificate.records),
            native_statistics=wire(stats),
            proof_records=stats.proof_records,
            search_cache=dict(
                hits=stats.cache_hits, high_water=stats.cache_entries, evictions=dict(NA)
            ),
        )
    else:
        assert certificate is not None
        a = certificate.accounting
        data.update(
            nodes=a.logical_nodes,
            backtracks=a.backtracks,
            completed_leaf_events=sum(e.kind == "COMPLETED_LEAF" for e in certificate.events),
            proof_event_counts=dict(Counter(e.kind for e in certificate.events)),
            execution_work=wire(a.execution_work),
            verification_work=wire(result.verification_work),
            proof_records=len(certificate.events),
            proof_reservations=wire(a),
            preparation=wire(result.execution_preparation)
            if result.execution_preparation is not None
            else dict(NA),
            verification_preparation=wire(result.verification_preparation)
            if result.verification_preparation is not None
            else dict(NA),
            search_cache=dict(
                hits=a.cache_hits,
                evictions=a.cache_evictions,
                entries=a.cache_entries,
                capacity=a.cache_capacity,
            ),
        )
    data["native_stage"] = data["exhaustion_stage"]
    if external_interrupted:
        data["exhaustion_stage"] = "EXTERNAL_VERIFICATION"
    return data


def _measure(manifest: ComparisonManifest, job: Job, *, trace=False) -> RunRecord:
    group = next(g for g in manifest.groups if g.group_id == job.group_id)
    spec = next(
        s
        for s in (manifest.weekly if group.family == "WEEKLY" else manifest.swaps)
        if s.case_id == group.case_id
    )
    setup = time.perf_counter()
    # Public facades import these lazily. Import code without running decisions,
    # before timing/tracing; do not warm a solver or reuse request-local state.
    modules = (
        ("weekly_search", "weekly_proof_v2")
        if group.family == "WEEKLY"
        else ("swap_checks", "swap_selection", "swap_proof")
    )
    for module in modules:
        importlib.import_module("savora_ai.core.reasoning." + module)
    authority = build_weekly(spec).authority() if isinstance(spec, WeeklySpec) else build_swap(spec)
    stamp = manifest.workloads[group.family + ":" + group.case_id]
    if ordered_digest(wire(authority)) != stamp["fingerprint"]:
        raise ValueError("regenerated workload differs from frozen input")
    oracle = weekly_oracle(spec) if isinstance(spec, WeeklySpec) else swap_oracle(spec)
    limits = operational_limits(group)
    authority["limits"] = limits
    if group.budget == "MALFORMED_RANKING":
        authority["ranking"] = authority["ranking"].model_copy(update={"entries": ()})
    clock = (
        (lambda: 1.0)
        if group.budget == "EXPIRED"
        else (lambda: 0.0)
        if group.budget in ("LIVE", "VERIFY_DEADLINE")
        else time.perf_counter
    )
    invocation_fingerprint = ordered_digest(dict(authority=wire(authority), group=wire(group)))
    setup_seconds = time.perf_counter() - setup
    before_rss = rss() if trace else dict(NA)
    if trace:
        if tracemalloc.is_tracing():
            raise ValueError("fresh memory tracing required")
        tracemalloc.start()
    started = time.perf_counter()
    result: Any = None
    checked: Any = None
    error = None
    witness = None
    native_seconds = check_seconds = encoding_seconds = 0.0
    expected = "BOUNDARY_ERROR" if group.budget == "MALFORMED_RANKING" else oracle["outcome"]
    correct = False
    outcome = native_outcome = "ERROR"
    proof = {}
    measured = {}
    raw = None
    native_start = time.perf_counter()
    try:
        if group.family == "WEEKLY":
            if group.policy == "V1":
                result = weekly.solve_weekly_plan(**authority, clock=clock)
            else:
                assert group.reuse is not None
                result = weekly_search_v2.solve_weekly_plan_v2(
                    **authority,
                    strategy=strategy(group.policy),
                    reuse_preparation=group.reuse,
                    preparation_cache_entries=group.preparation_capacity,
                    clock=clock,
                )
        elif group.policy == "VALIDATE":
            result = planned_swap.validate_swap(**authority, clock=clock)
        else:
            result = planned_swap.select_swap_replacement(**authority, clock=clock)
        native_seconds = time.perf_counter() - native_start
        native_outcome = outcome = result.outcome.value
        check_start = time.perf_counter()
        verify_clock = (lambda: 1.0) if group.budget == "VERIFY_DEADLINE" else clock
        if group.family == "WEEKLY":
            if group.policy == "V1":
                checked = ComputedWeeklySolveResult.model_validate(result)
                if (
                    checked.manifest.request != authority["request"]
                    or checked.candidates != authority["candidates"]
                    or checked.manifest.knowledge != authority["knowledge"]
                    or checked.manifest.request.source != authority["sources"]
                    or checked.manifest.request.source.daily_source.context != authority["context"]
                    or checked.limits != limits
                ):
                    raise ValueError("v1 independent authority mismatch")
            else:
                checked = weekly_search_v2.verify_weekly_plan_v2(
                    result, **{k: v for k, v in authority.items() if k != "limits"}
                )
        else:
            verify = (
                planned_swap.verify_swap_validation
                if group.policy == "VALIDATE"
                else planned_swap.verify_swap_selection
            )
            checked = verify(result, **authority, clock=verify_clock)
        correct, witness = assess_result(group, spec, authority, result, checked, oracle=oracle)
        if group.budget == "VERIFY_DEADLINE":
            correct = not checked.accepted and not checked.complete and checked.reason == "DEADLINE"
            outcome = "TIMEOUT"
            witness = None
        check_seconds = time.perf_counter() - check_start
        proof = dict(
            accepted=bool(
                getattr(
                    checked,
                    "accepted",
                    getattr(checked, "verification_complete", outcome != "TIMEOUT"),
                )
            ),
            complete=bool(
                getattr(
                    checked,
                    "complete",
                    getattr(checked, "verification_complete", outcome != "TIMEOUT"),
                )
            ),
            reason=getattr(checked, "reason", "NATIVE_REPLAY"),
            native_mandatory_checker_included=True,
        )
        encode_start = time.perf_counter()
        raw = result.model_dump_json(by_alias=True).encode()
        encoding_seconds = time.perf_counter() - encode_start
    except Exception as failure:
        if result is None:
            native_seconds = time.perf_counter() - native_start
        error = type(failure).__name__ + ": " + str(failure)[:2000]
        if (
            expected == "BOUNDARY_ERROR"
            and result is None
            and isinstance(failure, (ValidationError, ValueError))
        ):
            outcome = native_outcome = "BOUNDARY_ERROR"
            correct = True
        else:
            outcome = native_outcome = "ERROR"
    finally:
        elapsed = time.perf_counter() - started
        memory = dict(NA)
        if trace:
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            memory = dict(
                traced_current_bytes=current,
                traced_peak_bytes=peak,
                rss_before=before_rss,
                rss_after=rss(),
                trace_scope=(
                    "public invocation + mandatory checking + authority verification "
                    "+ final serialization; "
                    "fixtures/imports/oracle excluded"
                ),
            )
    # Reporting/hashing does not inflate invocation latency or traced memory.
    if raw is not None:
        measured = metrics(
            result, group, external_interrupted=group.budget == "VERIFY_DEADLINE" and correct
        )
        measured["result_bytes"] = len(raw)
        measured["result_digest"] = hashlib.sha256(raw).hexdigest()
        semantic = wire(result)
        semantic.pop("timing", None)
        measured["semantic_result_fingerprint"] = ordered_digest(semantic)
    return RunRecord(
        run_id=job.key(manifest.config.cohort_id),
        cohort_id=manifest.config.cohort_id,
        manifest_digest=manifest.manifest_digest,
        job=job,
        group=group,
        git_head=git("rev-parse", "HEAD"),
        source_fingerprints=manifest.source_fingerprints,
        dirty_source_fingerprint=manifest.dirty_source_fingerprint,
        workload_fingerprint=stamp["fingerprint"],
        invocation_fingerprint=invocation_fingerprint,
        oracle_version=ORACLE_VERSION,
        oracle=oracle,
        bindings=stamp["bindings"],
        limits=wire(limits),
        environment=environment(),
        outcome=outcome,
        native_outcome=native_outcome,
        expected_outcome=expected,
        correctness=correct,
        proof=proof,
        witness=witness,
        metrics=measured,
        timing=dict(
            setup_seconds=setup_seconds,
            preparation_seconds=wire(result.timing.preparation_seconds)
            if group.policy == "V1"
            and result is not None
            and group.budget not in ("LIVE", "EXPIRED")
            else dict(NA),
            search_seconds=wire(result.timing.search_seconds)
            if group.policy == "V1"
            and result is not None
            and group.budget not in ("LIVE", "EXPIRED")
            else dict(NA),
            native_invocation_seconds=native_seconds,
            external_checker_seconds=check_seconds,
            native_checker_seconds=wire(result.timing.output_validation_seconds)
            if group.policy == "V1"
            and result is not None
            and group.budget not in ("LIVE", "EXPIRED")
            else dict(NA),
            encoding_seconds=encoding_seconds,
            total_seconds=elapsed,
            traced=trace,
            interval_policy=(
                "disjoint native/external-check/encoding inside total; "
                "native internal checks inclusive; no stage-median summation"
            ),
        ),
        memory=memory,
        error=error,
    )


def measure(manifest: ComparisonManifest, job: Job, *, trace=False) -> RunRecord:
    started = time.perf_counter()
    try:
        return _measure(manifest, job, trace=trace)
    except Exception as error:
        group = next(g for g in manifest.groups if g.group_id == job.group_id)
        stamp = manifest.workloads[group.family + ":" + group.case_id]
        elapsed = time.perf_counter() - started
        return RunRecord(
            run_id=job.key(manifest.config.cohort_id),
            cohort_id=manifest.config.cohort_id,
            manifest_digest=manifest.manifest_digest,
            job=job,
            group=group,
            git_head=git("rev-parse", "HEAD"),
            source_fingerprints=manifest.source_fingerprints,
            dirty_source_fingerprint=manifest.dirty_source_fingerprint,
            workload_fingerprint=stamp["fingerprint"],
            invocation_fingerprint="NOT_AVAILABLE: setup/protocol failed",
            oracle_version=ORACLE_VERSION,
            oracle=stamp["oracle"],
            bindings=stamp["bindings"],
            limits=wire(operational_limits(group)),
            environment=environment(),
            outcome="ERROR",
            native_outcome="NOT_AVAILABLE",
            expected_outcome=stamp["oracle"]["outcome"],
            correctness=False,
            proof={},
            witness=None,
            metrics={},
            timing=dict(
                total_seconds=elapsed,
                traced=trace,
                interval_policy=(
                    "setup/protocol failure; "
                    "elapsed includes attempted fixture setup, not a solver latency"
                ),
            ),
            memory=dict(NA),
            error=type(error).__name__ + ": " + str(error)[:2000],
        )


def read_records(directory: Path, manifest: ComparisonManifest) -> list[RunRecord]:
    folder = directory / "records"
    path = directory / "runs.jsonl"
    if folder.exists():
        lines = [p.read_text(encoding="utf-8") for p in sorted(folder.glob("*.json"))]
    elif path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        return []
    records = []
    seen = set()
    jobs = {j.key(manifest.config.cohort_id): j for j in manifest.jobs}
    for line in lines:
        record = RunRecord.model_validate_json(line)
        if record.run_id in seen:
            raise ValueError("duplicate run record")
        if record.run_id not in jobs or record.job != jobs[record.run_id]:
            raise ValueError("unexpected run identity/order")
        if (
            record.manifest_digest != manifest.manifest_digest
            or record.source_fingerprints != manifest.source_fingerprints
            or record.git_head != manifest.git_head
            or record.dirty_source_fingerprint != manifest.dirty_source_fingerprint
        ):
            raise ValueError("record source/manifest mismatch")
        group = next(g for g in manifest.groups if g.group_id == record.job.group_id)
        if (
            record.group != group
            or record.workload_fingerprint
            != manifest.workloads[group.family + ":" + group.case_id]["fingerprint"]
        ):
            raise ValueError("record grouping/workload mismatch")
        if bool(record.timing["traced"]) != (record.job.phase == "MEMORY"):
            raise ValueError("mixed traced/untraced cohort")
        expected_outcome = (
            "BOUNDARY_ERROR"
            if group.budget == "MALFORMED_RANKING"
            else manifest.workloads[group.family + ":" + group.case_id]["oracle"]["outcome"]
        )
        if record.expected_outcome != expected_outcome:
            raise ValueError("record expected verdict differs from frozen independent truth")
        stamp = manifest.workloads[group.family + ":" + group.case_id]
        if (
            record.oracle_version != manifest.config.oracle_version
            or wire(record.oracle) != wire(stamp["oracle"])
            or wire(record.bindings) != wire(stamp["bindings"])
        ):
            raise ValueError("record oracle/authority bindings mismatch")
        if record.correctness:
            if (group.budget == "EXPIRED" and record.outcome != "TIMEOUT") or (
                group.budget == "LIVE" and record.outcome == "TIMEOUT"
            ):
                raise ValueError("deterministic deadline contradicts declared boundary")
            if record.outcome not in (expected_outcome, "TIMEOUT"):
                raise ValueError("incorrect verdict labelled correct")
            if record.outcome in (
                "VALID",
                "FEASIBLE",
                "REJECTED",
                "INFEASIBLE",
                "INSUFFICIENT_DATA",
            ) and not (record.proof.get("accepted") and record.proof.get("complete")):
                raise ValueError("unverified proof labelled accepted")
            if record.outcome in ("FEASIBLE", "VALID") and record.witness is None:
                raise ValueError("affirmative record lacks a witness")
            if record.outcome == "TIMEOUT" and record.witness is not None:
                raise ValueError("unfinished run retained a witness")
        seen.add(record.run_id)
        records.append(record)
    return sorted(records, key=lambda r: r.job.order)


def regenerate_records(directory: Path, manifest: ComparisonManifest) -> bytes:
    rows = read_records(directory, manifest)
    return ("".join(r.model_dump_json() + "\n" for r in rows)).encode("utf-8")


def statistics_for(values: list[float]) -> dict[str, Any]:
    if not values:
        return dict(status="NOT_AVAILABLE", reason="no observations")
    quartiles = (
        statistics.quantiles(values, n=4, method="inclusive")
        if len(values) > 1
        else [values[0]] * 3
    )
    return dict(
        n=len(values),
        samples=values,
        median=statistics.median(values),
        iqr=quartiles[2] - quartiles[0],
        minimum=min(values),
        maximum=max(values),
    )


def summarize(manifest: ComparisonManifest, records: list[RunRecord]) -> dict[str, Any]:
    ids = [r.run_id for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate record in aggregation")
    expected = {j.key(manifest.config.cohort_id) for j in manifest.jobs}
    observed = set(ids)
    if observed - expected:
        raise ValueError("unregistered record")
    failures = [r.run_id for r in records if not r.correctness]
    grouped = {}
    ratios = {}
    memory = {}
    reuse_ratios = {}
    node_reductions = {}
    by_phase: dict[tuple[str, str], list[RunRecord]] = {}
    for row in records:
        by_phase.setdefault((row.group.group_id, row.job.phase), []).append(row)

    def timing_ready(group):
        warmups = by_phase.get((group.group_id, "WARMUP"), [])
        gate = by_phase.get((group.group_id, "CORRECTNESS"), [])
        rows = by_phase.get((group.group_id, "MEASURE"), [])
        return (
            len(warmups) == manifest.config.warmups
            and len(gate) == 1
            and len(rows) == manifest.config.repetitions
            and all(
                r.correctness
                and r.outcome not in ("TIMEOUT", "ERROR", "BOUNDARY_ERROR")
                and r.proof.get("complete", False)
                for r in (*warmups, *gate, *rows)
            )
        )

    for group in manifest.groups:
        rows = by_phase.get((group.group_id, "MEASURE"), [])
        if group.timing:
            completed = [
                r
                for r in rows
                if r.correctness
                and r.outcome not in ("TIMEOUT", "ERROR", "BOUNDARY_ERROR")
                and r.proof.get("complete", False)
            ]
            grouped[group.group_id] = dict(
                group=wire(group),
                observed=len(rows),
                expected=manifest.config.repetitions,
                outcomes=dict(Counter(r.outcome for r in rows)),
                completion_rate=len(completed) / len(rows) if rows else 0,
                all_run_seconds=statistics_for([r.timing["total_seconds"] for r in rows]),
                completed_pair_eligible=timing_ready(group),
                completed_seconds=statistics_for([r.timing["total_seconds"] for r in completed])
                if timing_ready(group)
                else dict(
                    status="NOT_AVAILABLE",
                    reason="missing/censored group; successful subset not compared",
                ),
                nodes=[r.metrics.get("nodes", dict(NA)) for r in rows],
                proof_bytes=[r.metrics.get("proof_bytes", dict(NA)) for r in rows],
                selected=[
                    {
                        k: v
                        for k, v in (r.witness or {}).items()
                        if k
                        in (
                            "choices",
                            "digest",
                            "option",
                            "selected_rank",
                            "selected_domain_index",
                            "plan_digest",
                        )
                    }
                    for r in rows
                ],
            )
            baseline = next(
                (
                    g
                    for g in manifest.groups
                    if g.family == group.family
                    and g.case_id == group.case_id
                    and g.track == group.track
                    and g.policy == "CHRONOLOGICAL"
                    and g.reuse == group.reuse
                    and g.preparation_capacity == group.preparation_capacity
                    and g.search_cache_capacity == group.search_cache_capacity
                    and g.budget == group.budget
                ),
                None,
            )
            baseline_rows = (
                {r.job.repetition: r for r in by_phase.get((baseline.group_id, "MEASURE"), [])}
                if baseline
                else {}
            )
            if (
                timing_ready(group)
                and baseline is not None
                and timing_ready(baseline)
                and len(baseline_rows) == manifest.config.repetitions
                and all(
                    r.correctness and r.outcome != "TIMEOUT" and r.proof.get("complete")
                    for r in baseline_rows.values()
                )
            ):
                ratios[group.group_id] = statistics_for(
                    [
                        r.timing["total_seconds"]
                        / baseline_rows[r.job.repetition].timing["total_seconds"]
                        for r in completed
                    ]
                )
                if all(
                    type(r.metrics.get("nodes")) is int
                    and type(baseline_rows[r.job.repetition].metrics.get("nodes")) is int
                    and baseline_rows[r.job.repetition].metrics["nodes"] > 0
                    for r in completed
                ):
                    node_reductions[group.group_id] = statistics_for(
                        [
                            1
                            - r.metrics["nodes"] / baseline_rows[r.job.repetition].metrics["nodes"]
                            for r in completed
                        ]
                    )
            else:
                ratios[group.group_id] = dict(
                    status="NOT_AVAILABLE",
                    reason="no complete same-input same-protocol paired chronological population",
                )
            if group.reuse is True:
                off = next(
                    (
                        g
                        for g in manifest.groups
                        if g.family == group.family
                        and g.case_id == group.case_id
                        and g.policy == group.policy
                        and g.track == group.track
                        and g.budget == group.budget
                        and g.reuse is False
                        and g.search_cache_capacity == group.search_cache_capacity
                        and g.preparation_capacity == group.preparation_capacity
                    ),
                    None,
                )
                off_rows = (
                    {r.job.repetition: r for r in by_phase.get((off.group_id, "MEASURE"), [])}
                    if off
                    else {}
                )
                if (
                    timing_ready(group)
                    and off is not None
                    and timing_ready(off)
                    and len(off_rows) == manifest.config.repetitions
                    and all(
                        r.correctness and r.outcome != "TIMEOUT" and r.proof.get("complete")
                        for r in off_rows.values()
                    )
                ):
                    reuse_ratios[group.group_id] = statistics_for(
                        [
                            r.timing["total_seconds"]
                            / off_rows[r.job.repetition].timing["total_seconds"]
                            for r in completed
                        ]
                    )
                else:
                    reuse_ratios[group.group_id] = dict(
                        status="NOT_AVAILABLE", reason="missing/censored reuse pair"
                    )
        if group.track == "MEMORY":
            probes = by_phase.get((group.group_id, "MEMORY"), [])
            if len({r.environment["pid"] for r in probes}) != len(probes):
                raise ValueError("memory probes must use distinct fresh processes")
            memory[group.group_id] = dict(
                observed=len(probes),
                expected=manifest.config.memory_probes,
                peak_traced_bytes=[r.memory.get("traced_peak_bytes") for r in probes],
                rss=[r.memory.get("rss_after") for r in probes],
            )
    return dict(
        schema_version="phase7-comparison-summary.v1",
        manifest_digest=manifest.manifest_digest,
        status="BLOCKED" if failures else "COMPLETE" if observed == expected else "INCOMPLETE",
        expected=len(expected),
        observed=len(observed),
        missing=sorted(expected - observed),
        failed=failures,
        outcomes=dict(Counter(r.outcome for r in records)),
        runtime_groups=grouped,
        paired_runtime_ratios=ratios,
        memory=memory,
        reuse_on_off_runtime_ratios=reuse_ratios,
        node_reduction_ratios=node_reductions,
        known_invalid_accepted=sum(
            r.outcome in ("VALID", "FEASIBLE") and not r.correctness for r in records
        ),
        rule=(
            "no pooling across cases/protocols; "
            "censored populations excluded from speedup ratios, "
            "retained in completion/descriptive tables"
        ),
    )


@contextmanager
def exclusive_benchmark(directory: Path):
    directory.parent.mkdir(parents=True, exist_ok=True)
    path = directory.parent / "active-benchmark.lock"
    try:
        handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError("benchmark lock exists; inspect its PID before any resume") from error
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        json.dump(
            dict(pid=os.getpid(), cohort=str(directory), started=datetime.now(UTC).isoformat()),
            stream,
        )
    try:
        yield
    finally:
        path.unlink()


def run_comparison(
    config: ComparisonConfig, *, directory: Path, max_jobs: int | None = None
) -> dict[str, Any]:
    directory = directory.resolve()
    with exclusive_benchmark(directory):
        manifest = (
            load_manifest(directory)
            if (directory / "manifest.json").exists()
            else freeze(config, directory)
        )
        if manifest.config != config:
            raise ValueError("resume configuration differs from frozen cohort")
        records = read_records(directory, manifest)
        seen = {r.run_id for r in records}
        count = 0
        if any(not r.correctness for r in records):
            raise RuntimeError(
                "cohort contains a correctness failure; preserve and review separately"
            )
        for job in manifest.jobs:
            if job.key(config.cohort_id) in seen:
                continue
            # Source hash check is outside invocation timers; no dirty-code mixing.
            current, dirty = source_state()
            if (
                current != manifest.source_fingerprints
                or dirty != manifest.dirty_source_fingerprint
                or git("rev-parse", "HEAD") != manifest.git_head
            ):
                raise RuntimeError("source changed during cohort")
            if max_jobs is not None and count >= max_jobs:
                break
            if job.phase == "MEMORY":
                target = directory / ("memory-" + job.key(config.cohort_id) + ".json")
                command = [
                    sys.executable,
                    "-m",
                    "savora_ai.evals.member2_phase7_comparison",
                    "memory-child",
                    str(directory),
                    str(job.order),
                    str(target),
                ]
                child = subprocess.run(
                    command,
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    env=os.environ | {"PYTHONDONTWRITEBYTECODE": "1"},
                )
                (directory / ("memory-" + str(job.order) + ".log")).write_text(
                    child.stdout + child.stderr, encoding="utf-8"
                )
                if child.returncode:
                    raise RuntimeError("memory child failed; log retained")
                record = RunRecord.model_validate_json(target.read_text(encoding="utf-8"))
            else:
                record = measure(manifest, job)
            raw_folder = directory / "records"
            raw_folder.mkdir(exist_ok=True)
            target = raw_folder / (record.run_id + ".json")
            if target.exists():
                raise RuntimeError("refuse to overwrite a raw run")
            temporary = target.with_suffix(".tmp")
            with temporary.open("w", encoding="utf-8") as stream:
                stream.write(record.model_dump_json() + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            with (directory / "runs.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(record.model_dump_json() + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            records.append(record)
            count += 1
            if len(records) % 10 == 0 or not record.correctness:
                report = summarize(manifest, records)
                (directory / "summary.json").write_text(
                    json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
                )
            print(
                json.dumps(
                    dict(
                        completed=len(records),
                        expected=len(manifest.jobs),
                        case=record.group.case_id,
                        policy=record.group.policy,
                        phase=job.phase,
                        outcome=record.outcome,
                        correct=record.correctness,
                        seconds=record.timing["total_seconds"],
                    )
                ),
                flush=True,
            )
            if not record.correctness:
                break
        report = summarize(manifest, records)
        (directory / "summary.json").write_text(
            json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        (directory / "runs-regenerated.jsonl").write_bytes(regenerate_records(directory, manifest))
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("directory", type=Path)
    run.add_argument("--cohort", required=True)
    run.add_argument("--max-jobs", type=int)
    summary = sub.add_parser("summarize")
    summary.add_argument("directory", type=Path)
    child = sub.add_parser("memory-child")
    child.add_argument("directory", type=Path)
    child.add_argument("order", type=int)
    child.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "run":
        report = run_comparison(
            ComparisonConfig(cohort_id=args.cohort),
            directory=args.directory,
            max_jobs=args.max_jobs,
        )
        print(
            json.dumps({k: report[k] for k in ("status", "expected", "observed", "failed")}),
            flush=True,
        )
        return 0 if report["status"] == "COMPLETE" else 2
    manifest = load_manifest(args.directory)
    if args.command == "memory-child":
        job = manifest.jobs[args.order]
        if job.phase != "MEMORY":
            raise ValueError("child job is not a memory probe")
        record = measure(manifest, job, trace=True)
        args.output.write_text(record.model_dump_json() + "\n", encoding="utf-8")
    else:
        report = summarize(manifest, read_records(args.directory, manifest))
        print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
