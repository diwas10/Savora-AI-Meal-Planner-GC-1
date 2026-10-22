"""Independent original-domain ordering, coverage and hostile proof checks."""

import json
from itertools import product
from typing import Any

import pytest
from pydantic import ValidationError
from test_weekly_bounds import forward_limits
from test_weekly_search_v2_contracts import declared as original_declaration  # noqa: F401
from test_weekly_search_v2_contracts import strategy

from savora_ai.core.reasoning import weekly_proof_v2 as proof
from savora_ai.core.reasoning import weekly_search_v2 as solver
from savora_ai.evals.synthetic_week_cases import (
    build_week_case,
    exhaustive_oracle,
    literal_trial_status,
)
from savora_ai.schemas import weekly_search_v2 as v2
from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.daily import DailyOutcome
from savora_ai.schemas.weekly_solver_v2 import ComputedWeeklySolveResultV2

ORDERED = (
    v2.WeeklyStrategyPolicyV2.REVERSE_VALUES,
    v2.WeeklyStrategyPolicyV2.STATIC_MRV,
    v2.WeeklyStrategyPolicyV2.STATIC_MRV_FORWARD_CHECKING,
    v2.WeeklyStrategyPolicyV2.STATIC_MRV_INCREMENTAL,
    v2.WeeklyStrategyPolicyV2.STATIC_MRV_INCREMENTAL_FORWARD_CHECKING,
)


@pytest.fixture(scope="module")
def declared(request):
    return request.getfixturevalue("original_declaration")


@pytest.mark.parametrize("policy", ORDERED)
def test_smoke_ordered_execution(policy):
    from savora_ai.core.reasoning.weekly_search_v2 import solve_weekly_plan_v2
    from savora_ai.evals.synthetic_week_cases import build_week_case

    case = build_week_case("early")
    result = solve_weekly_plan_v2(
        case.request,
        candidates=case.candidates,
        knowledge=case.knowledge,
        context=case.context,
        sources=case.sources,
        strategy=strategy(policy),
        limits=forward_limits(),
    )
    assert result.outcome.value == "FEASIBLE"
    assert result.verification_complete


@pytest.mark.parametrize("policy", ORDERED)
def test_ordering_contract_exact_allowlist(policy):
    selected = strategy(policy)
    assert selected == v2.WeeklySearchStrategyV2.model_validate_json(selected.model_dump_json())
    for field, value in (
        ("value_order", "LCV"),
        ("variable_order", "DYNAMIC_MRV"),
        ("variable_tie_break", "DEGREE"),
        ("propagation", "USER_CALLBACK"),
    ):
        with pytest.raises(ValidationError):
            v2.WeeklySearchStrategyV2.model_validate(selected.model_dump() | {field: value})


def test_scope_separates_depth_from_canonical_identity(declared):
    order = (6, 0, 3)
    choices = tuple(
        v2.WeeklySelectedOptionV2(
            depth=depth,
            slot=declared.original_domains[index].slot,
            original_domain_index=0,
            option=declared.original_domains[index].options[0],
        )
        for depth, index in enumerate(order)
    )
    scope = v2.WeeklyBranchScopeV2(branch_id="explicit", extent="PREFIX_COMPLETIONS", path=choices)
    assert tuple(c.slot.canonical_index for c in scope.path) == order
    for path in ((*choices, choices[0]), (choices[1],)):
        with pytest.raises(ValidationError):
            v2.WeeklyBranchScopeV2(branch_id="forged", extent="PREFIX_COMPLETIONS", path=path)


def test_day_failure_requires_actual_three_slots(declared):
    from savora_ai.core.reasoning.weekly_proof_v2 import _payload, _scope

    # Depth three across three different days cannot close any DAY.
    domains = tuple(declared.original_domains[i] for i in (0, 3, 6))
    material = {key: getattr(declared, key) for key in type(declared).model_fields}
    payload = _payload(material, "DAY_FAILURE", _scope(domains, (0, 0, 0)))
    with pytest.raises(ValidationError, match="three actual day slots"):
        v2.WeeklyDayFailureV2.model_validate(
            payload
            | dict(
                sequence=0,
                accounting=v2.WeeklyAccountingV2(
                    proof_records_reserved=1,
                    proof_records_written=1,
                    proof_bytes_reserved=1,
                    proof_bytes_written=1,
                ),
            )
        )


def solve(data, policy=v2.WeeklyStrategyPolicyV2.STATIC_MRV, **kwargs):
    return solver.solve_weekly_plan_v2(
        **data,
        strategy=strategy(policy),
        limits=kwargs.pop("limits", forward_limits()),
        reuse_preparation=kwargs.pop("reuse_preparation", True),
        **kwargs,
    )


def inputs(name) -> dict[str, Any]:
    c = build_week_case(name)
    return dict(
        request=c.request,
        candidates=c.candidates,
        knowledge=c.knowledge,
        context=c.context,
        sources=c.sources,
    )


@pytest.fixture(scope="module")
def ordered_runs():
    cached = {}

    def get(name="early", policy=v2.WeeklyStrategyPolicyV2.STATIC_MRV):
        key = name, policy
        if key not in cached:
            cached[key] = solve(inputs(name), policy)
        return cached[key]

    return get


def literal_first(spec, policy):
    # Literal Cartesian enumeration, no solver/preparation/bound/checker helper.
    order = list(range(21))
    if policy != v2.WeeklyStrategyPolicyV2.REVERSE_VALUES:
        order.sort(key=lambda i: (len(spec.domains[i]), i))
    domains = [spec.domains[i] for i in order]
    if policy == v2.WeeklyStrategyPolicyV2.REVERSE_VALUES:
        domains = [tuple(reversed(d)) for d in domains]
    for assignment in product(*domains):
        canonical = [0] * 21
        for i, value in zip(order, assignment, strict=True):
            canonical[i] = value
        if literal_trial_status(spec, tuple(canonical)) == "PASS":
            return tuple(canonical)
    return None


@pytest.mark.parametrize("policy", ORDERED)
@pytest.mark.parametrize(
    "name",
    (
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
    ),
)
def test_all_strategies_against_literal_product(name, policy, ordered_runs):
    c = build_week_case(name)
    result = ordered_runs(name, policy)
    assert result.outcome.value == exhaustive_oracle(c.spec).outcome
    assert result.verification_complete
    expected = literal_first(c.spec, policy)
    if expected is None:
        assert result.witness is None
    else:
        refs = sorted(c.sources.daily_source.options, key=lambda o: o.reference.option_id)
        assert result.witness is not None
        assert tuple(x.option for x in result.witness.trial.choices) == tuple(
            refs[i].reference for i in expected
        )
    a = result.certificate.accounting
    assert a.policy == "synthetic-weekly-ordered-work-reservation.v2"
    for field in v2.WeeklyWorkV2.model_fields:
        assert getattr(a.execution_work, field) + getattr(
            result.verification_work, field
        ) == getattr(a.reserved_work, field)


def test_static_order_unequal_sizes_ties_and_nonchronological_days(monkeypatch):
    from test_member2_phase6_integration import audit_case

    data = audit_case(domains={0: (0, 1, 2), 2: (0, 1), 3: (0, 1)}, target=63)
    observed = []
    original = proof._day

    def day(program, domains, path, decisions, **kwargs):
        actual = domains[len(path) - 1].slot.canonical_index // 3
        selected = {d.slot.canonical_index for d in domains[: len(path)]}
        assert set(range(actual * 3, actual * 3 + 3)) <= selected
        observed.append((len(path), actual))
        return original(program, domains, path, decisions, **kwargs)

    monkeypatch.setattr(solver, "_day", day)
    result = solve(data)
    expected = (*(i for i in range(21) if i not in (0, 2, 3)), 2, 3, 0)
    assert (
        tuple(c.slot.canonical_index for c in result.certificate.events[-1].scope.path) == expected
    )
    assert observed[0] == (6, 2)  # DAY 3 completes at depth 6, before DAY 1.
    assert (21, 0) in observed and (20, 1) in observed
    assert result.outcome is DailyOutcome.FEASIBLE


@pytest.mark.parametrize("policy", ORDERED)
def test_repeated_execution_and_input_permutations(policy, ordered_runs):
    from savora_ai.schemas.weekly import WeeklyPlanningRequest

    data = inputs("early")
    request = data["request"]
    changed = WeeklyPlanningRequest.build(
        request.model_dump(exclude={"content_digest"})
        | dict(
            days=tuple(
                day.model_copy(
                    update={
                        "domains": tuple(
                            domain.model_copy(update={"options": tuple(reversed(domain.options))})
                            for domain in reversed(day.domains)
                        )
                    }
                )
                for day in reversed(request.days)
            )
        )
    )
    permuted = data | dict(request=changed, candidates=tuple(reversed(data["candidates"])))
    result = solve(permuted, policy)
    original = ordered_runs("early", policy)
    # Retained input tuples preserve their supplied order; canonical decisions,
    # identities, evidence and arithmetic must nevertheless be deterministic.
    assert result.outcome == original.outcome and result.witness == original.witness
    assert result.certificate.events == original.certificate.events
    assert result.certificate.frontier == original.certificate.frontier
    assert result.certificate.accounting == original.certificate.accounting
    assert result.certificate.original_domains == original.certificate.original_domains
    assert solve(inputs("early"), policy) == original


@pytest.mark.parametrize("policy", ORDERED)
@pytest.mark.parametrize("reuse,capacity", ((False, 1), (True, 0), (True, 1)))
def test_preparation_reuse_modes(policy, reuse, capacity, ordered_runs):
    result = solve(
        inputs("early"), policy, reuse_preparation=reuse, preparation_cache_entries=capacity
    )
    assert result.certificate == ordered_runs("early", policy).certificate
    assert result.witness == ordered_runs("early", policy).witness


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
def test_mrv_incremental_unknown_na_and_known_fail(parameters, expected):
    from test_member2_phase6_integration import audit_case

    data = audit_case(domains={0: (0, 1)}, **parameters)
    result = solve(data, v2.WeeklyStrategyPolicyV2.STATIC_MRV_INCREMENTAL_FORWARD_CHECKING)
    assert result.outcome is expected


@pytest.mark.parametrize(
    "attack",
    (
        "slot",
        "depth",
        "option-index",
        "day-index",
        "frontier",
        "duplicate-frontier",
        "omit-event",
        "reorder-events",
        "digest",
        "coverage-policy",
        "strategy",
        "accounting",
        "source",
        "manifest",
        "witness",
        "state",
    ),
)
def test_forged_original_json_rejected(attack, ordered_runs):
    result = ordered_runs("late")
    body = result.model_dump(mode="json")
    cert = body["certificate"]
    event = cert["events"][-1]
    if attack == "slot":
        event["scope"]["path"][0]["slot"] = event["scope"]["path"][-1]["slot"]
    elif attack == "depth":
        event["scope"]["path"][0]["depth"] = 20
    elif attack == "option-index":
        event["scope"]["path"][-1]["original_domain_index"] = 0
    elif attack == "day-index":
        day = next(
            e for e in ordered_runs("day-pruning").certificate.events if e.kind == "DAY_FAILURE"
        )
        cert["events"][0] = day.model_dump(mode="json") | dict(day_index=7)
    elif attack == "frontier":
        cert["frontier"] = cert["frontier"][:-1]
    elif attack == "duplicate-frontier":
        cert["frontier"].append(cert["frontier"][0])
    elif attack == "omit-event":
        cert["events"] = cert["events"][:-1]
    elif attack == "reorder-events":
        cert["events"] = list(reversed(cert["events"]))
    elif attack == "digest":
        event["evaluation_digest"] = "0" * 64
        # Structural acceptance and rebuilt bytes do not establish source truth.
        assert v2.WeeklySearchCertificateV2.model_validate_json(json.dumps(cert))
    elif attack == "coverage-policy":
        cert["proof_policy_version"] = "synthetic-weekly-coverage-declarations.v2"
    elif attack == "strategy":
        replacement = strategy(v2.WeeklyStrategyPolicyV2.REVERSE_VALUES).model_dump(mode="json")
        cert["identity"]["strategy"] = replacement
        for e in cert["events"]:
            e["identity"]["strategy"] = replacement
        body.pop("search_policy_version")
    elif attack == "accounting":
        cert["accounting"]["execution_work"]["heuristic_evaluations"] -= 1
    elif attack == "source":
        cert["identity"]["source"]["snapshot_version"] = "forged"
    elif attack == "manifest":
        body["manifest"]["day_checks"] = []
    elif attack == "witness":
        body["witness"]["facts"][1]["observation"]["value"] += 1
    else:
        body["incremental_state"] = dict(complete=True, total=75)
    with pytest.raises(ValueError):
        validate_contract_json(ComputedWeeklySolveResultV2, json.dumps(body))


@pytest.mark.parametrize("policy", ORDERED)
def test_checker_independent_of_ordering_execution_state(monkeypatch, ordered_runs, policy):
    from savora_ai.core.reasoning import weekly_incremental, weekly_ordering

    result = ordered_runs("early", policy)

    def forbidden(*args, **kwargs):
        pytest.fail("checker called execution or ordering/state helper")

    monkeypatch.setattr(solver, "solve_weekly_plan_v2", forbidden)
    monkeypatch.setattr(solver, "_ordered_domains", forbidden)
    monkeypatch.setattr(weekly_ordering, "_ordered_domains", forbidden)
    monkeypatch.setattr(weekly_incremental._IncrementalState, "__init__", forbidden)
    assert (
        validate_contract_json(ComputedWeeklySolveResultV2, result.model_dump_json(by_alias=True))
        == result
    )


@pytest.mark.parametrize("policy", ORDERED)
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
def test_exact_and_one_short_limits(policy, resource, ordered_runs):
    original = ordered_runs("early", policy)
    a = original.certificate.accounting
    exact = forward_limits(
        max_nodes=a.logical_nodes,
        max_reserved_work=a.reserved_work,
        max_proof_records=a.proof_records_reserved,
        max_proof_bytes=a.proof_bytes_reserved,
    )
    # Only the varied limit is tightened; all other limits stay ample.
    if resource.startswith("max_"):
        value = getattr(exact, resource)
        cap = forward_limits(**{resource: value})
        short = forward_limits(**{resource: value - 1})
    else:
        value = getattr(a.reserved_work, resource)
        cap = forward_limits(
            max_reserved_work=v2.WeeklyWorkV2.model_validate(
                forward_limits().max_reserved_work.model_dump() | {resource: value}
            )
        )
        short = forward_limits(
            max_reserved_work=v2.WeeklyWorkV2.model_validate(
                cap.max_reserved_work.model_dump() | {resource: value - 1}
            )
        )
    assert solve(inputs("early"), policy, limits=cap).outcome is DailyOutcome.FEASIBLE
    limited = solve(inputs("early"), policy, limits=short)
    assert limited.outcome is DailyOutcome.TIMEOUT and limited.witness is None
    assert limited.termination is not None


@pytest.mark.parametrize("cutoff", (1, 6, 12, 30, 65, 90))
def test_mrv_deadline_unwinds_state(cutoff, monkeypatch):
    from savora_ai.core.reasoning.weekly_incremental import _IncrementalState

    states = []
    original = _IncrementalState.__init__

    def observe(self, *args):
        original(self, *args)
        states.append(self)

    monkeypatch.setattr(_IncrementalState, "__init__", observe)
    calls = 0

    def clock():
        nonlocal calls
        calls += 1
        return 10 if calls >= cutoff else 0

    result = solve(
        inputs("late"),
        v2.WeeklyStrategyPolicyV2.STATIC_MRV_INCREMENTAL_FORWARD_CHECKING,
        limits=forward_limits(deadline=10),
        clock=clock,
    )
    assert result.outcome is DailyOutcome.TIMEOUT and result.witness is None
    for state in states:
        state.assert_empty()


@pytest.mark.parametrize("corruption", ("quantity", "count", "rollback"))
def test_mrv_incremental_corruption_rejected(corruption, monkeypatch):
    from savora_ai.core.reasoning.weekly_incremental import _IncrementalState

    if corruption == "quantity":
        monkeypatch.setattr(_IncrementalState, "day_values", lambda *args: (999, True))
    elif corruption == "count":
        original = _IncrementalState.week_values
        monkeypatch.setattr(
            _IncrementalState, "week_values", lambda self: (*original(self)[:2], 0, True)
        )
    else:
        monkeypatch.setattr(_IncrementalState, "pop", lambda *args: None)
    with pytest.raises(ValueError):
        solve(inputs("early"), v2.WeeklyStrategyPolicyV2.STATIC_MRV_INCREMENTAL)


def test_external_source_binding_and_legacy_proofs(ordered_runs):
    from test_weekly_solver_v2 import solve as chronological

    from savora_ai.schemas.weekly_search import WeeklySearchCertificate

    result = ordered_runs()
    with pytest.raises(ValueError):
        solver.verify_weekly_plan_v2(result, **inputs("late"))
    with pytest.raises(ValueError):
        WeeklySearchCertificate.model_validate(result.certificate.model_dump())
    old = chronological("single")
    assert old.certificate.proof_policy_version == "synthetic-weekly-coverage-declarations.v2"
    assert (
        validate_contract_json(ComputedWeeklySolveResultV2, old.model_dump_json(by_alias=True))
        == old
    )
    forged = old.model_dump(mode="json")
    forged["certificate"]["proof_policy_version"] = "synthetic-weekly-ordered-coverage.v2"
    with pytest.raises(ValueError):
        validate_contract_json(ComputedWeeklySolveResultV2, json.dumps(forged))


@pytest.mark.parametrize("policy", ORDERED)
@pytest.mark.parametrize("name", ("early", "late", "exhaustive", "day-pruning", "unknown-day"))
def test_literal_original_space_partition_and_every_prune(policy, name, ordered_runs):
    c = build_week_case(name)
    result = ordered_runs(name, policy)
    refs = sorted(c.sources.daily_source.options, key=lambda o: o.reference.option_id)
    names = {o.reference: i for i, o in enumerate(refs)}
    # Enumerate the ORIGINAL product independently of rank/suffix encoding.
    for assignment in product(*c.spec.domains):
        matches = []
        for branch in result.certificate.frontier:
            scope = branch.scope
            if not all(assignment[x.slot.canonical_index] == names[x.option] for x in scope.path):
                continue
            if scope.decision_slot is not None:
                i = scope.decision_slot.canonical_index
                original = result.certificate.original_domains[i]
                if assignment[i] not in {
                    names[original.options[j]] for j in scope.original_domain_indexes
                }:
                    continue
            matches.append(branch)
        assert len(matches) == 1
        branch = matches[0]
        if branch.state is v2.WeeklyFrontierStateV2.EXCLUSION_DECLARED:
            assert literal_trial_status(c.spec, assignment) == "FAIL"
        elif branch.state is v2.WeeklyFrontierStateV2.UNRESOLVED_UNKNOWN:
            assert literal_trial_status(c.spec, assignment) == "UNKNOWN"


@pytest.mark.parametrize("policy", ORDERED)
@pytest.mark.parametrize("nodes", (0, 3, 19, 21))
def test_interrupted_reordered_frontier_covers_every_original_alternative(policy, nodes):
    c = build_week_case("late")
    result = solve(inputs("late"), policy, limits=forward_limits(max_nodes=nodes))
    # Reverse reaches the only witness in 21 nodes; other cases can time out.
    assert result.outcome in (DailyOutcome.TIMEOUT, DailyOutcome.FEASIBLE)
    refs = sorted(c.sources.daily_source.options, key=lambda o: o.reference.option_id)
    names = {o.reference: i for i, o in enumerate(refs)}
    for assignment in product(*c.spec.domains):
        count = 0
        for b in result.certificate.frontier:
            s = b.scope
            if not all(assignment[x.slot.canonical_index] == names[x.option] for x in s.path):
                continue
            if s.decision_slot:
                i = s.decision_slot.canonical_index
                d = result.certificate.original_domains[i]
                if assignment[i] not in {names[d.options[j]] for j in s.original_domain_indexes}:
                    continue
            count += 1
        assert count == 1
    if result.outcome is DailyOutcome.TIMEOUT:
        assert result.witness is None


@pytest.mark.parametrize("mutation", ("order", "reverse-values", "bound", "suffix"))
def test_execution_order_or_frontier_corruption_cannot_authorize_result(monkeypatch, mutation):
    if mutation == "order":
        monkeypatch.setattr(solver, "_ordered_domains", lambda domains, strategy: domains)
        selected = v2.WeeklyStrategyPolicyV2.STATIC_MRV
    elif mutation == "reverse-values":
        # A reverse policy's chronological suffix is a valid declaration shape
        # with a wrong original-product partition. Recomputed proof rejects it.
        original = proof._rest
        monkeypatch.setattr(
            solver, "_rest", lambda domains, covered, **kwargs: original(domains, covered)
        )
        selected = v2.WeeklyStrategyPolicyV2.REVERSE_VALUES
    elif mutation == "bound":
        monkeypatch.setattr(solver, "_derive_bound", lambda *args: (0, 0))
        selected = v2.WeeklyStrategyPolicyV2.STATIC_MRV_FORWARD_CHECKING
    else:
        monkeypatch.setattr(solver, "_rest", lambda *args, **kwargs: ())
        selected = v2.WeeklyStrategyPolicyV2.STATIC_MRV
    with pytest.raises(ValueError):
        # Reverse exhausts `early` before finding its all-zero witness, leaving
        # no suffix to corrupt. `late` has an immediate reverse witness instead.
        solve(inputs("late" if mutation == "reverse-values" else "early"), selected)


@pytest.mark.parametrize("mode", ("unknown-eligibility", "known-failure"))
def test_static_mrv_uses_original_sizes_even_when_eligibility_changes(mode):
    from test_member2_phase6_integration import audit_case
    from test_weekly_evaluation import rebind

    from savora_ai.schemas.daily import MealSlot

    data = audit_case(domains={i: (2,) for i in range(1, 21)} | {0: (0, 1)}, target=227)
    options = list(data["sources"].daily_source.options)
    options[0] = options[0].model_copy(
        update={
            "suitability": options[0].suitability.model_copy(
                update={
                    "slots": (MealSlot.LUNCH, MealSlot.DINNER),
                    "complete": mode == "known-failure",
                }
            )
        }
    )
    bound = rebind(
        dict(
            kb=data["knowledge"],
            context=data["context"],
            daily=data["sources"].daily_source,
            source=data["sources"],
            request=data["request"],
        ),
        options=tuple(options),
    )
    data = data | dict(request=bound["request"], sources=bound["source"], context=bound["context"])
    result = solve(data)
    assert result.outcome is DailyOutcome.FEASIBLE
    assert len(result.certificate.original_domains[0].options) == 2
    assert all(c.slot.canonical_index != 0 for c in result.certificate.events[-1].scope.path[:-1])
    assert result.certificate.events[-1].scope.path[-1].slot.canonical_index == 0
    unary = [e for e in result.certificate.events if e.kind == "UNARY_FAILURE"]
    assert bool(unary) == (mode == "known-failure")


@pytest.mark.parametrize("mode", ("applicability", "incomplete", "absent"))
def test_unknown_applicability_or_quantity_survives_mrv_forward(mode):
    from test_member2_phase6_integration import audit_case
    from test_weekly_evaluation import rebind, revise

    data = audit_case(domains={0: (0, 1)})
    context = revise(
        data["context"],
        facts=tuple(f for f in data["context"].facts if f.fact_id != "synthetic_context_enabled"),
    )
    options = list(data["sources"].daily_source.options)
    if mode != "applicability":
        options = [
            o.model_copy(
                update={
                    "measurements": ()
                    if mode == "absent"
                    else tuple(m.model_copy(update={"complete": False}) for m in o.measurements)
                }
            )
            for o in options
        ]
    bound = rebind(
        dict(
            kb=data["knowledge"],
            context=data["context"],
            daily=data["sources"].daily_source,
            source=data["sources"],
            request=data["request"],
        ),
        **(dict(context=context) if mode == "applicability" else dict(options=tuple(options))),
    )
    data = data | dict(request=bound["request"], sources=bound["source"], context=bound["context"])
    result = solve(data, v2.WeeklyStrategyPolicyV2.STATIC_MRV_INCREMENTAL_FORWARD_CHECKING)
    assert result.outcome is DailyOutcome.INSUFFICIENT_DATA


@pytest.mark.parametrize("depth", (0, 20))
def test_wide_original_domains_have_lossless_bounded_scope_ids(declared, depth):
    # Declaration/encoder capacity check, never presented as accepted source truth.
    domains = tuple(
        v2.WeeklyOriginalDomainV2(
            slot=d.slot,
            options=tuple(
                d.options[0].model_copy(
                    update={
                        "option_id": f"wide-{i:02}",
                        "snapshot_id": f"wide-snapshot-{i:02}",
                    }
                )
                for i in range(50)
            ),
        )
        for d in declared.original_domains
    )
    selected = (49,) * depth
    scope = proof._scope(domains, selected, tuple(range(50)))
    assert len(scope.branch_id) <= 128
    assert scope.original_domain_indexes == tuple(range(50))
    assert tuple(c.original_domain_index for c in scope.path) == selected
    assert v2.WeeklyBranchScopeV2.model_validate_json(scope.model_dump_json()) == scope
    assert proof._envelope({"original_domains": domains}) > 0


def test_ordering_can_change_first_witness_without_changing_outcome():
    from test_member2_phase6_integration import audit_case

    data = audit_case(domains={0: (0, 1, 2), 3: (0, 1)}, target=67)
    ascending = solve(data, v2.WeeklyStrategyPolicyV2.CHRONOLOGICAL)
    reverse = solve(data, v2.WeeklyStrategyPolicyV2.REVERSE_VALUES)
    mrv = solve(data)
    refs = sorted(data["sources"].daily_source.options, key=lambda o: o.reference.option_id)
    # Two literal feasible assignments, with neither eligibility nor data changed.
    feasible = {
        (a, b)
        for a, b in product((0, 1, 2), (0, 1))
        if 19 * 3 + (3, 7, 11)[a] + (3, 7, 11)[b] == 67
    }
    assert feasible == {(0, 1), (1, 0)}
    chosen = []
    for result in (ascending, reverse, mrv):
        assert result.outcome is DailyOutcome.FEASIBLE and result.witness is not None
        choices = result.witness.trial.choices
        value = tuple(
            next(i for i, ref in enumerate(refs) if ref.reference == choices[j].option)
            for j in (0, 3)
        )
        assert value in feasible
        chosen.append(value)
    assert chosen == [(0, 1), (1, 0), (1, 0)]


@pytest.mark.parametrize("forward", (False, True))
@pytest.mark.parametrize("name", ("late", "exhaustive", "unknown-measurement"))
def test_mrv_incremental_terminal_evidence_equals_full(name, forward, ordered_runs):
    full = ordered_runs(
        name,
        v2.WeeklyStrategyPolicyV2.STATIC_MRV_FORWARD_CHECKING
        if forward
        else v2.WeeklyStrategyPolicyV2.STATIC_MRV,
    )
    incremental = ordered_runs(
        name,
        v2.WeeklyStrategyPolicyV2.STATIC_MRV_INCREMENTAL_FORWARD_CHECKING
        if forward
        else v2.WeeklyStrategyPolicyV2.STATIC_MRV_INCREMENTAL,
    )
    assert full.outcome == incremental.outcome and full.witness == incremental.witness
    assert tuple(
        e.model_dump(exclude={"identity", "accounting"}) for e in full.certificate.events
    ) == tuple(
        e.model_dump(exclude={"identity", "accounting"}) for e in incremental.certificate.events
    )
