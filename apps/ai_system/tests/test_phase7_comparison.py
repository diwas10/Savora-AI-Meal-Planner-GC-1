"""Harness-only protocol tests; fake timing records never enter campaign evidence."""

import ast
import json
from math import prod
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from savora_ai.core.reasoning import planned_swap, weekly_search_v2
from savora_ai.evals import member2_phase7_comparison as h
from savora_ai.evals import phase7_comparison_cases as c


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    spec = next(s for s in c.weekly_specs() if s.case_id == "product-1")
    groups = tuple(
        h.Group(family="WEEKLY", case_id=spec.case_id, policy=p, reuse=False, timing=True)
        for p in ("CHRONOLOGICAL", "STATIC_MRV")
    )
    monkeypatch.setattr(h, "weekly_specs", lambda: (spec,))
    monkeypatch.setattr(h, "swap_specs", lambda: ())
    monkeypatch.setattr(h, "groups_for", lambda config: groups)
    monkeypatch.setattr(h, "source_state", lambda: ({"unit-only.py": "a" * 64}, "b" * 64))
    monkeypatch.setattr(h, "git", lambda *args: "unit-head" if args[0] == "rev-parse" else "")
    monkeypatch.setattr(
        h, "build_weekly", lambda spec: SimpleNamespace(authority=lambda: {"unit": "declared"})
    )
    config = h.ComparisonConfig(cohort_id="unit-only")
    manifest = h.freeze(config, tmp_path)
    return tmp_path, manifest


def record(manifest, job, *, seconds=2.0, outcome="FEASIBLE", correct=True, accepted=True):
    group = next(g for g in manifest.groups if g.group_id == job.group_id)
    stamp = manifest.workloads[group.family + ":" + group.case_id]
    return h.RunRecord(
        run_id=job.key(manifest.config.cohort_id),
        cohort_id=manifest.config.cohort_id,
        manifest_digest=manifest.manifest_digest,
        job=job,
        group=group,
        git_head=manifest.git_head,
        source_fingerprints=manifest.source_fingerprints,
        dirty_source_fingerprint=manifest.dirty_source_fingerprint,
        workload_fingerprint=stamp["fingerprint"],
        invocation_fingerprint="unit-only",
        oracle_version=c.ORACLE_VERSION,
        oracle=stamp["oracle"],
        bindings={},
        limits={},
        environment={"pid": 1},
        outcome=outcome,
        native_outcome=outcome,
        expected_outcome="FEASIBLE",
        correctness=correct,
        proof={"accepted": accepted, "complete": accepted},
        witness={"choices": [0] * 21, "digest": "unit-only"} if outcome == "FEASIBLE" else None,
        metrics={"nodes": 21, "proof_bytes": 42},
        timing={"total_seconds": seconds, "traced": False},
        memory={},
    )


def journal(directory, rows):
    (directory / "runs.jsonl").write_text(
        "".join(r.model_dump_json() + "\n" for r in rows), encoding="utf-8"
    )


def test_exact_supported_strategies_and_modes():
    expected = {
        "CHRONOLOGICAL",
        "FORWARD_CHECKING",
        "INCREMENTAL",
        "INCREMENTAL_FORWARD_CHECKING",
        "REVERSE_VALUES",
        "STATIC_MRV",
        "STATIC_MRV_FORWARD_CHECKING",
        "STATIC_MRV_INCREMENTAL",
        "STATIC_MRV_INCREMENTAL_FORWARD_CHECKING",
    }
    assert set(h.STRATEGIES) == expected
    groups = h.groups_for(h.ComparisonConfig(cohort_id="unit"))
    for spec in c.weekly_specs():
        selected = [
            g
            for g in groups
            if g.family == "WEEKLY" and g.case_id == spec.case_id and g.track == "ADEQUATE"
        ]
        assert {(g.policy, g.reuse) for g in selected} == {
            (p, r) for p in expected for r in (False, True)
        } | {("V1", None)}
    assert not any(g.policy in ("MRV", "LCV", "DEGREE") for g in groups)


@pytest.mark.parametrize("policy", ["MRV", "LCV", "DEGREE", "unknown"])
def test_unsupported_strategies_reject(policy):
    with pytest.raises(ValueError):
        h.strategy(policy)
    with pytest.raises(ValidationError):
        h.Group(family="WEEKLY", case_id="x", policy=policy, reuse=False)


@pytest.mark.parametrize("bad", [True, "10", 9, float("inf"), float("nan")])
def test_repetition_floor_and_strictness(bad):
    with pytest.raises(ValidationError):
        h.ComparisonConfig.model_validate({"cohort_id": "unit", "repetitions": bad})


def test_schedule_is_frozen_balanced_and_complete():
    config = h.ComparisonConfig(cohort_id="unit")
    groups = h.groups_for(config)
    jobs = h.jobs_for(config, groups)
    assert jobs == h.jobs_for(config, h.groups_for(config))
    assert len({j.key(config.cohort_id) for j in jobs}) == len(jobs)
    for g in groups:
        selected = [j for j in jobs if j.group_id == g.group_id]
        if g.track == "MEMORY":
            assert [j.phase for j in selected] == ["MEMORY"] * 3
        elif g.timing:
            assert sum(j.phase == "WARMUP" for j in selected) == 2
            assert sum(j.phase == "MEASURE" for j in selected) == 10
            assert selected[0].phase == "CORRECTNESS"
        else:
            assert len(selected) == 1 and selected[0].phase == "CORRECTNESS"


def test_required_case_inventory():
    specs = c.weekly_specs()
    assert {prod(map(len, s.domains)) for s in specs if s.family == "cartesian"} == {
        0,
        1,
        2,
        4,
        8,
        16,
        32,
        64,
        128,
        256,
    }
    assert {s.target for s in c.swap_specs() if s.case_id.startswith("target-")} == set(range(21))
    assert {len(s.values) for s in c.swap_specs() if s.case_id.startswith("select-size-")} == {
        0,
        1,
        2,
        8,
        50,
    }


@pytest.mark.parametrize("spec", c.weekly_specs(), ids=lambda s: s.case_id)
def test_literal_week_oracle_is_bounded(spec):
    truth = c.weekly_oracle(spec)
    assert truth["outcome"] in ("FEASIBLE", "INFEASIBLE", "INSUFFICIENT_DATA")
    if spec.oracle_kind == "EXHAUSTIVE":
        assert truth["enumerated"] <= 256
        assert sum(truth["counts"].values()) == truth["size"]
    else:
        assert truth["truth"] == "CONSTRUCTED_WITNESS" and truth["enumerated"] == 0
    if truth["first_witness"] is not None:
        assert c.literal_week_status(spec, truth["first_witness"]) == "PASS"


@pytest.mark.parametrize("spec", c.swap_specs(), ids=lambda s: s.case_id)
def test_literal_swap_domain_oracle(spec):
    truth = c.swap_oracle(spec)
    assert truth["outcome"] in ("VALID", "REJECTED", "INSUFFICIENT_DATA", "BOUNDARY_ERROR")
    assert (truth["selected"] is not None) == (truth["outcome"] == "VALID")
    if spec.mode == "SELECT" and truth["selected"] is not None:
        assert spec.lanes[truth["selected"]] == "PASS"


def test_oracle_independence_and_explicit_language(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("production decision forbidden")

    monkeypatch.setattr(weekly_search_v2, "solve_weekly_plan_v2", forbidden)
    monkeypatch.setattr(planned_swap, "validate_swap", forbidden)
    monkeypatch.setattr(planned_swap, "select_swap_replacement", forbidden)
    for spec in c.weekly_specs():
        c.weekly_oracle(spec)
    for spec in c.swap_specs():
        c.swap_oracle(spec)
    tree = ast.parse(Path(c.__file__).read_text())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in (
            "weekly_oracle",
            "swap_oracle",
            "literal_week_status",
        ):
            calls = {
                n.func.id
                for n in ast.walk(node)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            }
            assert not calls & {
                "build_weekly",
                "build_swap",
                "strategy",
                "evaluate_combination",
                "_predicate",
            }


def test_zero_is_not_missing_and_boundary_operators():
    truth = {s.case_id: c.weekly_oracle(s)["outcome"] for s in c.weekly_specs()}
    assert truth["zero-measurement"] == "FEASIBLE"
    assert truth["missing-measurement"] == "INSUFFICIENT_DATA"
    assert truth["boundary-le"] == truth["boundary-ge"] == "FEASIBLE"
    assert truth["boundary-lt"] == truth["boundary-gt"] == "INFEASIBLE"
    assert truth["unknown-refuted"] == "INFEASIBLE"
    assert truth["evidenced-na"] == "FEASIBLE"


def test_oversize_oracle_refuses_enumeration():
    base = c.weekly_specs()[1]
    with pytest.raises(ValidationError):
        c.WeeklySpec.model_validate(base.model_dump() | {"domains": ((0, 1),) * 21})
    forged = base.model_copy(update={"domains": ((0, 1),) * 21})
    with pytest.raises(ValueError, match="oversized"):
        c.weekly_oracle(forged)


def test_freeze_reload_and_refuse_overwrite(frozen):
    directory, manifest = frozen
    assert h.load_manifest(directory).model_dump(mode="json") == manifest.model_dump(mode="json")
    with pytest.raises(FileExistsError):
        h.freeze(manifest.config, directory)


@pytest.mark.parametrize("attack", ["source", "head", "workload", "manifest", "case-rehashed"])
def test_fingerprint_drift_rejects(frozen, monkeypatch, attack):
    directory, _manifest = frozen
    if attack == "source":
        monkeypatch.setattr(h, "source_state", lambda: ({"unit-only.py": "f" * 64}, "b" * 64))
    elif attack == "head":
        monkeypatch.setattr(h, "git", lambda *args: "wrong-head")
    elif attack == "workload":
        path = next((directory / "workloads").glob("*.json"))
        path.write_text('{"changed":true}')
    elif attack == "case-rehashed":
        path = directory / "manifest.json"
        body = json.loads(path.read_text())
        body["weekly"][0]["target"] = 64
        body["manifest_digest"] = c.ordered_digest(
            {k: v for k, v in body.items() if k not in ("schema_version", "manifest_digest")}
        )
        path.write_text(json.dumps(body))
    else:
        path = directory / "manifest.json"
        body = json.loads(path.read_text())
        body["manifest_digest"] = "f" * 64
        path.write_text(json.dumps(body))
    with pytest.raises(ValueError, match="mismatch"):
        h.load_manifest(directory)


def test_duplicate_and_missing_observations(frozen):
    directory, manifest = frozen
    row = record(manifest, manifest.jobs[0])
    journal(directory, [row, row])
    with pytest.raises(ValueError, match="duplicate"):
        h.read_records(directory, manifest)
    summary = h.summarize(manifest, [row])
    assert summary["status"] == "INCOMPLETE" and len(summary["missing"]) == len(manifest.jobs) - 1


@pytest.mark.parametrize(
    "attack",
    ["source", "group", "workload", "verdict", "proof", "traced", "witness", "oracle", "bindings"],
)
def test_record_tampering_rejected(frozen, attack):
    directory, manifest = frozen
    row = record(manifest, manifest.jobs[0])
    if attack == "source":
        row = row.model_copy(update={"source_fingerprints": {}})
    elif attack == "group":
        row = row.model_copy(update={"group": manifest.groups[1]})
    elif attack == "workload":
        row = row.model_copy(update={"workload_fingerprint": "f" * 64})
    elif attack == "verdict":
        row = row.model_copy(update={"outcome": "INFEASIBLE"})
    elif attack == "proof":
        row = row.model_copy(update={"proof": {"accepted": False, "complete": False}})
    elif attack == "traced":
        row = row.model_copy(update={"timing": {"traced": True, "total_seconds": 1.0}})
    elif attack == "oracle":
        row = row.model_copy(update={"oracle": {"outcome": "FEASIBLE"}})
    elif attack == "bindings":
        row = row.model_copy(update={"bindings": {"unexpected": True}})
    else:
        row = row.model_copy(update={"witness": None})
    journal(directory, [row])
    with pytest.raises(ValueError):
        h.read_records(directory, manifest)


def test_failed_and_censored_runs_remain_visible(frozen):
    directory, manifest = frozen
    rows = [record(manifest, j, outcome="TIMEOUT", seconds=10.0) for j in manifest.jobs]
    journal(directory, rows)
    loaded = h.read_records(directory, manifest)
    report = h.summarize(manifest, loaded)
    assert report["status"] == "COMPLETE" and report["outcomes"] == {"TIMEOUT": len(rows)}
    assert all(v["status"] == "NOT_AVAILABLE" for v in report["paired_runtime_ratios"].values())
    assert all(v["completion_rate"] == 0 for v in report["runtime_groups"].values())
    failed = rows[0].model_copy(update={"correctness": False, "outcome": "ERROR"})
    assert h.summarize(manifest, [failed])["status"] == "BLOCKED"


def test_statistics_and_paired_ratios(frozen):
    _, manifest = frozen
    stats = h.statistics_for([1.0, 2.0, 3.0, 4.0])
    assert (stats["median"], stats["iqr"], stats["minimum"], stats["maximum"]) == (
        2.5,
        1.5,
        1.0,
        4.0,
    )
    rows = [
        record(manifest, j, seconds=2.0 if j.group_id == manifest.groups[0].group_id else 1.0)
        for j in manifest.jobs
    ]
    result = h.summarize(manifest, rows)
    assert result["status"] == "COMPLETE"
    assert result["paired_runtime_ratios"][manifest.groups[1].group_id]["median"] == 0.5
    assert all(v["all_run_seconds"]["n"] == 10 for v in result["runtime_groups"].values())
    no_warmups = [r for r in rows if r.job.phase != "WARMUP"]
    result = h.summarize(manifest, no_warmups)
    assert all(v["status"] == "NOT_AVAILABLE" for v in result["paired_runtime_ratios"].values())


@pytest.mark.parametrize("value", [True, "1.0", -1.0, float("nan"), float("inf")])
def test_invalid_timing_observations_reject(frozen, value):
    _, manifest = frozen
    with pytest.raises(ValidationError):
        record(manifest, manifest.jobs[0], seconds=value)


def test_raw_record_regeneration_is_ordered_and_repeatable(frozen):
    directory, manifest = frozen
    rows = [record(manifest, j) for j in manifest.jobs]
    journal(directory, list(reversed(rows)))
    first = h.regenerate_records(directory, manifest)
    assert first == h.regenerate_records(directory, manifest)
    assert first.decode().splitlines()[0] == rows[0].model_dump_json()


def test_atomic_records_survive_incomplete_journal(frozen):
    directory, manifest = frozen
    row = record(manifest, manifest.jobs[0])
    folder = directory / "records"
    folder.mkdir()
    (folder / (row.run_id + ".json")).write_text(row.model_dump_json())
    (folder / "interrupted.tmp").write_text('{"incomplete":')
    (directory / "runs.jsonl").write_text('{"partial-journal":')
    assert [r.model_dump(mode="json") for r in h.read_records(directory, manifest)] == [
        row.model_dump(mode="json")
    ]
    assert h.regenerate_records(directory, manifest) == (row.model_dump_json() + "\n").encode()


def test_exclusive_process_lock(tmp_path):
    with (
        h.exclusive_benchmark(tmp_path / "cohort"),
        pytest.raises(RuntimeError, match="lock exists"),
        h.exclusive_benchmark(tmp_path / "other"),
    ):
        pass
    assert not (tmp_path / "active-benchmark.lock").exists()


@pytest.mark.parametrize(
    "case_id",
    [
        "product-1",
        "unknown",
        "week-bottleneck",
        "permuted",
        "zero-measurement",
        "many-rules",
        "fifty-fixed",
    ],
)
def test_real_weekly_fixture_declarations(case_id):
    spec = next(s for s in c.weekly_specs() if s.case_id == case_id)
    built = c.build_weekly(spec)
    assert built.request.source == built.sources
    assert len(built.request.days) == 7
    assert len(built.sources.daily_source.options) == len(spec.weights)


@pytest.mark.parametrize(
    "case_id",
    ["target-00", "target-20", "preparation", "saved-history", "select-size-50", "select-noop"],
)
def test_real_swap_fixture_declarations(case_id):
    spec = next(s for s in c.swap_specs() if s.case_id == case_id)
    built = c.build_swap(spec)
    assert len(built["saved_plan"].snapshot.slots) == 21
    if spec.mode == "SELECT":
        from savora_ai.core.reasoning.swap_selection import _SelectionInputs

        limits = h.operational_limits(h.Group(family="SWAP", case_id=case_id, policy="SELECT"))
        _SelectionInputs.model_validate(built | {"limits": limits})


@pytest.mark.parametrize(
    "family,case_id,policy",
    [
        ("WEEKLY", "product-1", "CHRONOLOGICAL"),
        ("WEEKLY", "product-1", "V1"),
        ("WEEKLY", "unknown-refuted", "STATIC_MRV"),
        ("SWAP", "target-00", "VALIDATE"),
        ("SWAP", "select-early", "SELECT"),
    ],
)
def test_native_pipeline_and_independent_oracle(tmp_path, monkeypatch, family, case_id, policy):
    weekly = tuple(s for s in c.weekly_specs() if family == "WEEKLY" and s.case_id == case_id)
    swaps = tuple(s for s in c.swap_specs() if family == "SWAP" and s.case_id == case_id)
    group = h.Group(
        family=family,
        case_id=case_id,
        policy=policy,
        reuse=False if family == "WEEKLY" and policy != "V1" else None,
    )
    monkeypatch.setattr(h, "weekly_specs", lambda: weekly)
    monkeypatch.setattr(h, "swap_specs", lambda: swaps)
    monkeypatch.setattr(h, "groups_for", lambda config: (group,))
    manifest = h.freeze(h.ComparisonConfig(cohort_id="unit-integration"), tmp_path)
    row = h.measure(manifest, manifest.jobs[0])
    assert row.correctness, row.model_dump_json()
    assert row.outcome == row.expected_outcome
    assert row.proof["accepted"] and row.proof["complete"]
    if family == "SWAP":
        assert row.witness is not None
        assert row.witness["unchanged_payloads"] == 20


def test_invalid_proof_cannot_be_accepted(monkeypatch):
    spec = next(s for s in c.weekly_specs() if s.case_id == "product-1")
    group = h.Group(family="WEEKLY", case_id=spec.case_id, policy="CHRONOLOGICAL", reuse=False)
    result = SimpleNamespace(outcome=SimpleNamespace(value="FEASIBLE"), verification_complete=True)
    oracle = c.weekly_oracle(spec)

    def forbidden(*args, **kwargs):
        raise AssertionError("oracle enumeration belongs outside timed assessment")

    monkeypatch.setattr(h, "weekly_oracle", forbidden)
    assert h.assess_result(
        group, spec, {}, result, SimpleNamespace(accepted=False), oracle=oracle
    ) == (
        False,
        None,
    )


@pytest.mark.parametrize("budget,outcome", [("EXPIRED", "FEASIBLE"), ("LIVE", "TIMEOUT")])
def test_deterministic_deadline_cannot_contradict_clock(budget, outcome):
    spec = next(s for s in c.weekly_specs() if s.case_id == "product-1")
    group = h.Group(
        family="WEEKLY",
        case_id=spec.case_id,
        policy="CHRONOLOGICAL",
        reuse=False,
        track="EQUAL",
        budget=budget,
    )
    result = SimpleNamespace(
        outcome=SimpleNamespace(value=outcome),
        verification_complete=True,
        witness=None,
        resulting_plan=None,
    )
    assert h.assess_result(group, spec, {}, result, SimpleNamespace(accepted=True)) == (False, None)


def test_selected_rank_is_not_original_domain_index():
    spec = next(s for s in c.swap_specs() if s.case_id == "select-priority")
    group = h.Group(family="SWAP", case_id=spec.case_id, policy="SELECT")
    original = tuple(SimpleNamespace(value=i) for i in range(21))
    selected = "second-domain-option"
    plan = SimpleNamespace(
        slots=(SimpleNamespace(option=SimpleNamespace(reference=selected)), *original[1:]),
        content_digest="unit-only",
    )
    authority = {
        "saved_plan": SimpleNamespace(snapshot=SimpleNamespace(slots=original)),
        "domain": SimpleNamespace(options=("first-domain-option", selected)),
    }
    result = SimpleNamespace(
        outcome=SimpleNamespace(value="VALID"),
        verification_complete=True,
        resulting_plan=plan,
        selected=selected,
        exhaustive=False,
        certificate=SimpleNamespace(
            visits=(SimpleNamespace(option=selected, outcome=SimpleNamespace(value="VALID")),)
        ),
    )
    correct, witness = h.assess_result(
        group, spec, authority, result, SimpleNamespace(accepted=True)
    )
    assert correct and witness is not None
    assert witness["selected_domain_index"] == 1 and witness["selected_rank"] == 0


def test_external_deadline_stage_does_not_claim_native_interruption():
    group = h.Group(
        family="SWAP",
        case_id="target-00",
        policy="VALIDATE",
        track="EQUAL",
        budget="VERIFY_DEADLINE",
    )
    result = SimpleNamespace(
        certificate=None,
        stage="COMPLETE",
        actual_execution={},
        actual_verification={},
        proof_bytes=0,
        reason="COMPLETE_PASS",
    )
    data = h.metrics(result, group, external_interrupted=True)
    assert data["native_stage"] == "COMPLETE"
    assert data["exhaustion_stage"] == "EXTERNAL_VERIFICATION"


@pytest.mark.parametrize(
    "termination,reached,stage",
    [("NODES", False, "EXECUTION"), (None, True, "NATIVE_OUTPUT_VERIFICATION")],
)
def test_v1_interruption_stage_uses_native_statistics_or_checker(termination, reached, stage):
    group = h.Group(family="WEEKLY", case_id="product-1", policy="V1")
    stats = SimpleNamespace(
        nodes=0,
        backtracks=0,
        proof_records=0,
        cache_hits=0,
        cache_entries=0,
        termination=termination,
    )
    certificate = SimpleNamespace(
        statistics=stats, records=(), model_dump_json=lambda **kwargs: "{}"
    )
    result = SimpleNamespace(
        certificate=certificate, timing=SimpleNamespace(validation_deadline_reached=reached)
    )
    data = h.metrics(result, group)
    assert data["exhaustion_stage"]["stage"] == stage
    assert data["native_stage"] == data["exhaustion_stage"]
