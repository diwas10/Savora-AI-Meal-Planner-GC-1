"""Incremental arithmetic is checked against literal truth and full source derivation."""

import json
from dataclasses import FrozenInstanceError, replace

import pytest
from test_member2_phase6_integration import audit_case
from test_weekly_bounds import forward_limits, forward_strategy, inputs
from test_weekly_evaluation import rebind, revise
from test_weekly_solver_v2 import strategy

from savora_ai.core.reasoning import weekly_incremental as inc
from savora_ai.core.reasoning import weekly_proof_v2 as proof
from savora_ai.core.reasoning import weekly_search_v2 as search
from savora_ai.core.reasoning.week_checks import _compile_week, _prepare_option
from savora_ai.core.reasoning.weekly import solve_weekly_plan
from savora_ai.evals.synthetic_week_cases import build_week_case, exhaustive_oracle
from savora_ai.schemas import weekly_search_v2 as v2
from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.daily import DailyOutcome
from savora_ai.schemas.weekly_solver_v2 import ComputedWeeklySolveResultV2


def incremental_strategy(forward=False):
    return v2.WeeklySearchStrategyV2(
        policy=v2.WeeklyStrategyPolicyV2.INCREMENTAL_FORWARD_CHECKING
        if forward
        else v2.WeeklyStrategyPolicyV2.INCREMENTAL,
        variable_order="CHRONOLOGICAL",
        value_order="OPTION_ID_ASC",
        propagation="KNOWN_FAILURE_FORWARD_CHECK" if forward else "NONE",
    )


def solve(data, *, forward=False, **kwargs):
    return search.solve_weekly_plan_v2(
        **data,
        strategy=incremental_strategy(forward),
        limits=kwargs.pop("limits", forward_limits()),
        **kwargs,
    )


@pytest.fixture(scope="module")
def runs():
    saved = {}

    def get(name="single", forward=False):
        key = name, forward
        if key not in saved:
            saved[key] = solve(inputs(name), forward=forward, reuse_preparation=True)
        return saved[key]

    return get


def prepare(data):
    manifest, pool = proof._admit(
        data["request"], data["candidates"], data["knowledge"], data["context"], data["sources"]
    )
    program = _compile_week(manifest)
    domains = proof._material(manifest, pool, incremental_strategy(), forward_limits())[
        "original_domains"
    ]
    refs = {r for domain in domains for r in domain.options}
    decisions = {r.option_id: _prepare_option(manifest, pool, r) for r in refs}
    return program, domains, decisions


@pytest.fixture(scope="module")
def prepared():
    return prepare(audit_case(variable=tuple(range(21)), duplicate_components=True))


def test_exact_add_remove_symmetry_and_repeated_backtracking(prepared):
    state = inc._IncrementalState(*prepared)
    domains = prepared[1]
    root = state.snapshot()
    for repetition in range(5):
        saved = []
        selected = []
        for i in (20, 0, 2, 1, 6, 3, 4, 5):
            before = state.snapshot()
            position = repetition % len(domains[i].options)
            ref = domains[i].options[position]
            frame = state.push(domains[i].slot, ref)
            saved.append((frame, before))
            selected.append((i, position))
            # Independent fixture arithmetic: A=3/7; B=11, one contribution per slot.
            expected = sum((3, 7, 11)[p] for _, p in selected)
            assert state.snapshot().week.known_total == expected
            assert state.snapshot().week.selected == len(selected)
            assert sum(c for _, c in state.snapshot().recipe_counts) == len(selected)
            assert state.week_values()[:2] == (None, False)
            for day in range(7):
                members = [(i, p) for i, p in selected if i // 3 == day]
                known = sum((3, 7, 11)[p] for _, p in members)
                assert state.day_values(day) == (
                    (known, True) if len(members) == 3 else (None, False)
                )
        for frame, before in reversed(saved):
            state.pop(frame)
            assert state.snapshot() is before
        assert state.snapshot() is root
        state.assert_empty()
    with pytest.raises(FrozenInstanceError):
        root.__setattr__("unknown_recipe_slots", 1)


def test_wrong_lifo_fabricated_tokens_and_source_configuration_reject(prepared):
    state = inc._IncrementalState(*prepared)
    domains = prepared[1]
    first = state.push(domains[0].slot, domains[0].options[0])
    second = state.push(domains[1].slot, domains[1].options[0])
    for token in (first, replace(second)):
        with pytest.raises(ValueError, match="rollback"):
            state.pop(token)
    with pytest.raises(ValueError, match="already selected"):
        state.push(domains[0].slot, domains[0].options[0])
    with pytest.raises(ValueError, match="original slot/domain/configuration"):
        state.push(
            domains[2].slot,
            domains[2].options[0].model_copy(update={"portion_configuration_version": "other"}),
        )
    with pytest.raises(ValueError, match="original slot/domain/configuration"):
        state.push(
            domains[2].slot.model_copy(update={"day": domains[3].slot.day}), domains[2].options[0]
        )
    state.pop(second)
    state.pop(first)
    with pytest.raises(ValueError, match="rollback"):
        state.pop(first)
    state.assert_empty()


def rebound(data, **changes):
    revised = rebind(
        dict(
            kb=data["knowledge"],
            context=data["context"],
            daily=data["sources"].daily_source,
            source=data["sources"],
            request=data["request"],
        ),
        **changes,
    )
    return data | dict(
        context=revised["context"], sources=revised["source"], request=revised["request"]
    )


def test_partial_unknown_contributions_and_rollback():
    data = audit_case(variable=tuple(range(21)))
    options = list(data["sources"].daily_source.options)
    options[0] = options[0].model_copy(
        update={
            "measurements": (options[0].measurements[0].model_copy(update={"complete": False}),)
        }
    )
    prepared = prepare(rebound(data, options=tuple(options)))
    state = inc._IncrementalState(*prepared)
    domains = prepared[1]
    first = state.push(domains[0].slot, domains[0].options[0])
    before = state.snapshot()
    second = state.push(domains[1].slot, domains[1].options[1])
    third = state.push(domains[2].slot, domains[2].options[1])
    assert state.snapshot().days[0] == inc._Quantity(14, 1, 3)
    assert state.day_values(0) == (None, False)
    state.pop(third)
    state.pop(second)
    assert state.snapshot() is before
    state.pop(first)
    state.assert_empty()


def test_unknown_recipe_identity_never_becomes_a_complete_count():
    prepared = prepare(audit_case() | dict(candidates=()))
    state = inc._IncrementalState(*prepared)
    frames = [state.push(domain.slot, domain.options[0]) for domain in prepared[1]]
    assert state.week_values() == (63, True, None, False)
    assert state.snapshot().unknown_recipe_slots == 21
    for frame in reversed(frames):
        state.pop(frame)
    state.assert_empty()


def test_multiple_recipes_and_duplicates_within_the_same_slot():
    data = audit_case(duplicate_components=True)
    options = list(data["sources"].daily_source.options)
    original = options[0]
    part_b = options[2].combination.components[0].model_copy(update={"component_id": "part-b"})
    parts = (*original.combination.components, part_b)
    combination = revise(original.combination, components=parts)
    ref = original.reference.model_copy(update={"combination_digest": combination.content_digest})
    options[0] = original.model_copy(
        update=dict(
            reference=ref,
            combination=combination,
            suitability=original.suitability.model_copy(update={"option": ref}),
            measurements=tuple(
                m.model_copy(update={"option": ref, "components": parts})
                for m in original.measurements
            ),
        )
    )
    changed = rebound(data, options=tuple(options))
    result = solve(changed, reuse_preparation=True)
    assert result.outcome is DailyOutcome.FEASIBLE and result.witness is not None
    assert result.witness.facts[1].observation.value == 63
    assert result.witness.facts[2].observation.value == 21
    assert all(
        o.recipe_ids == ("audit-recipe-a", "audit-recipe-b")
        for o in result.witness.facts[2].occurrences
    )


def test_changed_source_is_fresh_and_cannot_enter_old_state(prepared):
    changed = prepare(audit_case(meal=5, target=105))
    fresh = inc._IncrementalState(*changed)
    frame = fresh.push(changed[1][0].slot, changed[1][0].options[0])
    assert fresh.snapshot().week.known_total == 5
    old = inc._IncrementalState(*prepared)
    with pytest.raises(ValueError, match="original slot/domain/configuration"):
        old.push(changed[1][0].slot, changed[1][0].options[0])
    fresh.pop(frame)
    fresh.assert_empty()


CASES = (
    "single",
    "early",
    "late",
    "exhaustive",
    "unknown-day",
    "unknown-measurement",
    "unknown-refuted",
    "day-pruning",
    "week-quantity",
    "week-repetition",
    "repeated-identities",
    "empty-domain",
)


@pytest.mark.parametrize("name", CASES)
@pytest.mark.parametrize("forward", (False, True))
def test_independent_cartesian_and_full_evidence_equivalence(name, forward, runs):
    case = build_week_case(name)
    expected = exhaustive_oracle(case.spec)
    result = runs(name, forward)
    baseline = search.solve_weekly_plan_v2(
        **inputs(name),
        strategy=forward_strategy() if forward else strategy(),
        limits=forward_limits(),
        reuse_preparation=True,
    )
    assert result.outcome.value == expected.outcome == baseline.outcome.value
    assert result.verification_complete and result.witness == baseline.witness
    assert result.search_policy_version == incremental_strategy(forward).policy.value
    a, b = result.certificate.accounting, baseline.certificate.accounting
    assert a.policy == "synthetic-weekly-incremental-work-reservation.v2"
    assert a.logical_nodes == b.logical_nodes and a.backtracks == b.backtracks
    assert a.execution_work.day_assessments == b.execution_work.day_assessments
    assert a.execution_work.week_assessments == b.execution_work.week_assessments
    # Exact facts, traces, explanations, source evidence and terminal digests;
    # only strategy identity and its explicitly versioned work differ.
    assert tuple(
        e.model_dump(exclude={"identity", "accounting"}) for e in result.certificate.events
    ) == tuple(
        e.model_dump(exclude={"identity", "accounting"}) for e in baseline.certificate.events
    )
    for key in v2.WeeklyWorkV2.model_fields:
        assert getattr(a.execution_work, key) + getattr(result.verification_work, key) == getattr(
            a.reserved_work, key
        )
    if expected.first_witness is not None:
        options = sorted(case.sources.daily_source.options, key=lambda o: o.reference.option_id)
        assert result.witness is not None
        assert tuple(c.option for c in result.witness.trial.choices) == tuple(
            options[i].reference for i in expected.first_witness
        )


@pytest.mark.parametrize("meal", (0, 9_007_199_254_740_993, 3_074_457_345_618_258_602))
def test_exact_integer_boundaries(meal):
    result = solve(
        audit_case(meal=meal, target=meal * 21, day_cap=meal * 3), reuse_preparation=True
    )
    assert result.outcome is DailyOutcome.FEASIBLE and result.witness is not None
    assert result.witness.facts[1].observation.value == meal * 21
    assert type(result.witness.facts[1].observation.value) is int
    assert all(day.evaluation.facts[1].observation.value == meal * 3 for day in result.witness.days)


@pytest.mark.parametrize(
    "parameters,expected",
    (
        (dict(day_unknown=True), DailyOutcome.INSUFFICIENT_DATA),
        (dict(day_unknown=True, target=64), DailyOutcome.INFEASIBLE),
        (dict(enabled=False), DailyOutcome.FEASIBLE),
        (dict(enabled=False, unknown_dependency=True), DailyOutcome.INSUFFICIENT_DATA),
        (dict(missing_measurement=True), DailyOutcome.INSUFFICIENT_DATA),
        (dict(repeat_cap=20), DailyOutcome.INFEASIBLE),
        (dict(duplicate_components=True), DailyOutcome.FEASIBLE),
    ),
)
def test_unknown_fail_dominance_na_and_recipe_occurrences(parameters, expected):
    result = solve(audit_case(**parameters), reuse_preparation=True)
    assert result.outcome is expected
    if result.witness:
        assert result.witness.facts[2].observation.value == 21
        assert all(len(o.recipe_ids) == 1 for o in result.witness.facts[2].occurrences)


def test_unknown_applicability_and_incomplete_measurements():
    original = audit_case()
    context = revise(
        original["context"],
        facts=tuple(
            f for f in original["context"].facts if f.fact_id != "synthetic_context_enabled"
        ),
    )
    for mode in ("applicability", "measurement", "absent"):
        options = list(original["sources"].daily_source.options)
        if mode != "applicability":
            options[0] = options[0].model_copy(
                update={
                    "measurements": (
                        options[0].measurements[0].model_copy(update={"complete": False}),
                    )
                    if mode == "measurement"
                    else ()
                }
            )
        rebound = rebind(
            dict(
                kb=original["knowledge"],
                context=original["context"],
                daily=original["sources"].daily_source,
                source=original["sources"],
                request=original["request"],
            ),
            **(dict(context=context) if mode == "applicability" else dict(options=tuple(options))),
        )
        data = original | dict(
            context=rebound["context"], sources=rebound["source"], request=rebound["request"]
        )
        assert solve(data, reuse_preparation=True).outcome is DailyOutcome.INSUFFICIENT_DATA


@pytest.mark.parametrize("reuse,capacity", ((False, 1), (True, 0), (True, 1)))
def test_preparation_options_and_deterministic_repeated_calls(reuse, capacity, runs):
    one = solve(inputs("single"), reuse_preparation=reuse, preparation_cache_entries=capacity)
    two = solve(inputs("single"), reuse_preparation=reuse, preparation_cache_entries=capacity)
    assert one == two
    assert one.certificate == runs().certificate and one.witness == runs().witness


def test_checker_never_constructs_or_reads_incremental_state(monkeypatch, runs):
    result = runs("exhaustive")

    def forbidden(*args, **kwargs):
        pytest.fail("independent checker accessed incremental execution")

    for name in ("__init__", "push", "pop", "day_values", "week_values", "bind_path"):
        monkeypatch.setattr(inc._IncrementalState, name, forbidden)
    assert ComputedWeeklySolveResultV2.model_validate(result) == result
    assert (
        validate_contract_json(ComputedWeeklySolveResultV2, result.model_dump_json(by_alias=True))
        == result
    )


@pytest.mark.parametrize("corruption", ("day", "week", "count", "complete", "snapshot", "rollback"))
def test_corrupt_execution_aggregate_or_rollback_cannot_authorize_result(monkeypatch, corruption):
    if corruption == "day":
        monkeypatch.setattr(inc._IncrementalState, "day_values", lambda *args: (10, True))
    elif corruption in ("week", "count", "complete"):
        values = (
            (64, True, 21, True)
            if corruption == "week"
            else ((63, True, 20, True) if corruption == "count" else (None, False, 21, True))
        )
        monkeypatch.setattr(inc._IncrementalState, "week_values", lambda *args: values)
    elif corruption == "rollback":
        monkeypatch.setattr(inc._IncrementalState, "pop", lambda *args: None)
    else:
        original_push = inc._IncrementalState.push

        def corrupt(self, *args):
            frame = original_push(self, *args)
            self._current = replace(self._current, week=replace(self._current.week, known_total=99))
            return frame

        monkeypatch.setattr(inc._IncrementalState, "push", corrupt)
    with pytest.raises(ValueError):
        solve(inputs("single"), reuse_preparation=True)


@pytest.mark.parametrize("mutation", ("digest", "omit", "frontier", "work", "policy", "state"))
def test_tampering_and_forged_incremental_state_reject(mutation, runs):
    body = runs().model_dump(mode="json")
    certificate = body["certificate"]
    if mutation == "digest":
        certificate["events"][0]["evaluation_digest"] = "0" * 64
        assert v2.WeeklySearchCertificateV2.model_validate_json(json.dumps(certificate))
    elif mutation == "omit":
        certificate["events"] = []
    elif mutation == "frontier":
        certificate["frontier"] = []
    elif mutation == "work":
        certificate["accounting"]["execution_work"]["heuristic_evaluations"] -= 1
    elif mutation == "policy":
        body["search_policy_version"] = "synthetic-chronological-weekly-search.v2"
    else:
        body["incremental_state"] = dict(total=63, complete=True)
    with pytest.raises(ValueError):
        validate_contract_json(ComputedWeeklySolveResultV2, json.dumps(body))


@pytest.mark.parametrize(
    "resource",
    (
        "max_nodes",
        "max_proof_records",
        "max_proof_bytes",
        "heuristic_evaluations",
        "predicate_obligations",
        "proof_verification_steps",
        "day_assessments",
        "week_assessments",
    ),
)
def test_zero_resources(resource):
    cap = forward_limits()
    if resource.startswith("max_"):
        cap = forward_limits(**{resource: 0})
    else:
        cap = forward_limits(
            max_reserved_work=v2.WeeklyWorkV2.model_validate(
                cap.max_reserved_work.model_dump() | {resource: 0}
            )
        )
    result = solve(inputs("single"), limits=cap, reuse_preparation=True)
    assert result.outcome is DailyOutcome.TIMEOUT and result.witness is None


def test_exact_and_one_short_incremental_budget(runs):
    a = runs().certificate.accounting
    exact = forward_limits(
        max_nodes=a.logical_nodes,
        max_reserved_work=a.reserved_work,
        max_proof_records=a.proof_records_reserved,
        max_proof_bytes=a.proof_bytes_reserved,
    )
    assert (
        solve(inputs("single"), limits=exact, reuse_preparation=True).outcome
        is DailyOutcome.FEASIBLE
    )
    short = forward_limits(
        max_reserved_work=v2.WeeklyWorkV2.model_validate(
            a.reserved_work.model_dump()
            | dict(heuristic_evaluations=a.reserved_work.heuristic_evaluations - 1)
        )
    )
    timeout = solve(inputs("single"), limits=short, reuse_preparation=True)
    assert timeout.outcome is DailyOutcome.TIMEOUT and timeout.termination == "HEURISTIC_BUDGET"


@pytest.mark.parametrize("cutoff", (1, 5, 10, 30, 65, 90))
def test_deadlines_always_unwind_and_withhold_witness(cutoff, monkeypatch):
    states = []
    original_init = inc._IncrementalState.__init__

    def observe(self, *args):
        original_init(self, *args)
        states.append(self)

    monkeypatch.setattr(inc._IncrementalState, "__init__", observe)
    calls = 0

    def clock():
        nonlocal calls
        calls += 1
        return 10 if calls >= cutoff else 0

    result = solve(
        inputs("single"), limits=forward_limits(deadline=10), clock=clock, reuse_preparation=True
    )
    assert result.outcome is DailyOutcome.TIMEOUT and result.witness is None
    for state in states:
        state.assert_empty()


@pytest.mark.parametrize("name", ("early", "exhaustive", "unknown-refuted"))
def test_legacy_v1_same_fixture_outcome_and_witness(name, runs):
    case = build_week_case(name)
    old = solve_weekly_plan(**inputs(name), limits=case.spec.limits)
    assert old.outcome == runs(name).outcome
    assert old.witness == runs(name).witness
