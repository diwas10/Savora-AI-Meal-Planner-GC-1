"""Literal Cartesian truth, independent interval arithmetic and hostile proof checks."""

import json
from copy import deepcopy
from dataclasses import replace
from itertools import product
from typing import Any

import pytest
from pydantic import ValidationError
from test_member2_phase6_integration import audit_case
from test_weekly_evaluation import rebind, revise
from test_weekly_solver_v2 import limits, strategy

from savora_ai.core.reasoning import weekly_bounds as bounds
from savora_ai.core.reasoning import weekly_proof_v2 as proof
from savora_ai.core.reasoning import weekly_search_v2 as solver
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.week_checks import _compile_week
from savora_ai.evals.synthetic_week_cases import build_week_case, exhaustive_oracle
from savora_ai.schemas import weekly_search_v2 as v2
from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.daily import DailyOutcome
from savora_ai.schemas.knowledge import PredicateOperator, RuleDefinition, RuleScope
from savora_ai.schemas.weekly_solver_v2 import ComputedWeeklySolveResultV2


def forward_strategy():
    return v2.WeeklySearchStrategyV2(
        policy=v2.WeeklyStrategyPolicyV2.FORWARD_CHECKING,
        variable_order="CHRONOLOGICAL",
        value_order="OPTION_ID_ASC",
        propagation="KNOWN_FAILURE_FORWARD_CHECK",
    )


def forward_limits(**changes):
    base = limits()
    work = base.max_reserved_work.model_dump() | dict(heuristic_evaluations=100000)
    return v2.WeeklySearchLimitsV2.model_validate(
        base.model_dump() | dict(max_reserved_work=work) | changes
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


def run(data, **kwargs):
    return solver.solve_weekly_plan_v2(
        **data, strategy=forward_strategy(), limits=kwargs.pop("limits", forward_limits()), **kwargs
    )


def changed_rules(data, transform):
    kb = data["knowledge"]
    kb = build_knowledge_snapshot(
        kb.model_dump(exclude={"content_digest"})
        | dict(rules=tuple(transform(r) for r in kb.rules))
    )
    context = revise(data["context"], expected_kb_digest=kb.content_digest)
    rebound = rebind(
        dict(
            kb=data["knowledge"],
            context=data["context"],
            daily=data["sources"].daily_source,
            source=data["sources"],
            request=data["request"],
        ),
        context=context,
        kb=kb,
    )
    return data | dict(
        knowledge=kb, context=context, sources=rebound["source"], request=rebound["request"]
    )


@pytest.fixture(scope="module")
def runs():
    saved = {}

    def get(name="week-quantity"):
        if name not in saved:
            saved[name] = run(inputs(name), reuse_preparation=True)
        return saved[name]

    return get


@pytest.fixture(scope="module")
def compiled():
    data = inputs("early")
    manifest, pool = proof._admit(
        data["request"], data["candidates"], data["knowledge"], data["context"], data["sources"]
    )
    program = _compile_week(manifest)
    material = proof._material(manifest, pool, forward_strategy(), forward_limits())
    return program, material["original_domains"]


def compare(operator, actual, threshold):
    # Independent literal truth; no production predicate or bound helper.
    return {
        "LT": actual < threshold,
        "LE": actual <= threshold,
        "GT": actual > threshold,
        "GE": actual >= threshold,
        "EQ": actual == threshold,
        "NE": actual != threshold,
    }[operator]


@pytest.mark.parametrize(
    "operator", tuple(PredicateOperator(x) for x in ("LT", "LE", "GT", "GE", "EQ", "NE"))
)
@pytest.mark.parametrize("threshold", (62, 63, 64, 67, 75, 76))
def test_all_operators_boundaries_and_discrete_gaps(compiled, operator, threshold):
    program, domains = compiled
    original = next(a for a in bounds._attempts(program, 0) if a.day_index is None)
    changed = RuleDefinition.model_validate(
        original.rule.model_dump() | dict(operator=operator, value=threshold)
    )
    attempt = bounds._BoundAttempt(changed, original.indexes, None)
    first = bounds._derive_bound(program, domains, (), attempt)
    checked = bounds._check_bound(program, domains, (), attempt)
    assert first == checked
    sums = [
        sum(3 if i == 0 else 7 for i in chosen)
        for chosen in product(*build_week_case("early").spec.domains)
    ]
    assert min(sums) == 63 and max(sums) == 75
    if first is not None:
        assert not any(compare(operator.value, total, threshold) for total in sums)
    if operator is PredicateOperator.EQ and threshold == 64:
        assert first is None  # interval interior, but no discrete solution


@pytest.mark.parametrize("operator", ("LT", "LE", "GT", "GE", "EQ", "NE"))
@pytest.mark.parametrize("scope", ("DAY", "WEEK"))
def test_singleton_exact_equality(compiled, operator, scope):
    program, domains = compiled
    original = next(a for a in bounds._attempts(program, 0) if a.day_index is None)
    day = scope == "DAY"
    attribute = "synthetic_day_quantity_total" if day else "synthetic_week_quantity_total"
    changed = RuleDefinition.model_validate(
        original.rule.model_dump()
        | dict(
            scope=RuleScope(scope),
            attribute=attribute,
            required_facts=(attribute,),
            operator=PredicateOperator(operator),
            value=9 if day else 63,
        )
    )
    attempt = bounds._BoundAttempt(changed, tuple(range(3 if day else 21)), 1 if day else None)
    # Fixed singleton original domains, independently admitted observations.
    singleton = tuple(
        v2.WeeklyOriginalDomainV2(slot=d.slot, options=(d.options[0],)) for d in domains
    )
    value = 9 if day else 63
    expected = None if compare(operator, value, value) else (value, value)
    assert bounds._derive_bound(program, singleton, (), attempt) == expected
    assert bounds._check_bound(program, singleton, (), attempt) == expected


def assert_closures_refute_every_completion(result, spec):
    refs = sorted(
        result.manifest.request.source.daily_source.options, key=lambda o: o.reference.option_id
    )
    names = {o.reference.option_id: i for i, o in enumerate(refs)}
    for event in result.certificate.events:
        if not isinstance(event, v2.WeeklyForwardCheckClosureV2):
            continue
        partial = tuple(names[c.option.option_id] for c in event.scope.path)
        remaining = spec.domains[len(partial) :]
        for tail in product(*remaining):
            selected = partial + tail
            values = [3 + 4 * i for i in selected]
            # Literal whole-assignment truth, including FAIL dominance.
            fails = sum(values) != spec.target
            fails |= spec.day_cap is not None and any(
                sum(values[i : i + 3]) > spec.day_cap for i in range(0, 21, 3)
            )
            assert fails, (event, selected)


@pytest.mark.parametrize(
    "name",
    (
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
    ),
)
def test_independent_cartesian_outcomes_and_each_pruned_subtree(name, runs):
    c = build_week_case(name)
    expected = exhaustive_oracle(c.spec)
    result = runs(name)
    assert result.outcome.value == expected.outcome
    assert result.verification_complete
    assert_closures_refute_every_completion(result, c.spec)
    if expected.first_witness is None:
        assert result.witness is None
    else:
        assert result.witness is not None
        options = sorted(c.sources.daily_source.options, key=lambda o: o.reference.option_id)
        assert tuple(c.option.option_id for c in result.witness.trial.choices) == tuple(
            options[i].reference.option_id for i in expected.first_witness
        )
    a = result.certificate.accounting
    assert a.policy == "synthetic-weekly-forward-work-reservation.v2"
    assert len(result.certificate.model_dump_json(by_alias=True).encode()) <= a.proof_bytes_reserved
    for key in v2.WeeklyWorkV2.model_fields:
        assert getattr(a.execution_work, key) + getattr(result.verification_work, key) == getattr(
            a.reserved_work, key
        )


def test_early_closure_and_unknown_separation(runs):
    closed = runs()
    assert closed.certificate.accounting.logical_nodes == 0
    assert len(closed.certificate.events) == 1
    assert closed.certificate.events[0].kind == "FORWARD_CHECK_CLOSURE"
    assert closed.outcome is DailyOutcome.INFEASIBLE
    for name in ("unknown-day", "unknown-measurement"):
        result = runs(name)
        assert result.outcome is DailyOutcome.INSUFFICIENT_DATA
        assert not any(e.kind == "FORWARD_CHECK_CLOSURE" for e in result.certificate.events)
    assert runs("unknown-refuted").outcome is DailyOutcome.INFEASIBLE


def test_bound_checker_does_not_call_execution_arithmetic(monkeypatch, runs):
    result = runs()
    monkeypatch.setattr(bounds, "_derive_bound", lambda *args: pytest.fail("execution called"))
    assert ComputedWeeklySolveResultV2.model_validate(result).outcome is DailyOutcome.INFEASIBLE


def test_unsound_execution_bound_is_rejected(monkeypatch):
    monkeypatch.setattr(solver, "_derive_bound", lambda *args: (0, 0))
    with pytest.raises(ValueError, match="event differs"):
        run(inputs("single"), reuse_preparation=True)


@pytest.mark.parametrize(
    "change",
    (
        "lower",
        "upper",
        "rule",
        "version",
        "applicability",
        "evidence",
        "required",
        "remaining",
        "indexes",
        "partial",
        "omit",
        "duplicate",
        "frontier",
        "counters",
        "source-measurement",
        "transplant",
    ),
)
def test_rehashed_hostile_certificates_reject(change, runs):
    body = runs().model_dump(mode="json")
    event = body["certificate"]["events"][0]
    bound = event["numeric_bound"]
    if change in ("lower", "upper"):
        bound[change] += 1
    elif change == "rule":
        bound["rule"]["rule_id"] = "bench-week-complete"
    elif change == "version":
        bound["rule"]["version"] = "2"
    elif change == "applicability":
        bound["applicability"] = "UNKNOWN"
    elif change == "evidence":
        bound["applicability_evidence"] = []
    elif change == "required":
        bound["required_observations"] = [
            dict(
                fact_id="synthetic_profile_enabled",
                value=True,
                complete=True,
                evidence=bound["applicability_evidence"],
            )
        ]
    elif change == "remaining":
        event["remaining_domains"] = event["remaining_domains"][:-1]
    elif change == "indexes":
        event["remaining_domains"][0]["original_domain_indexes"] = []
    elif change == "partial":
        event["scope"]["branch_id"] = "another-subtree"
        body["certificate"]["frontier"][0]["scope"]["branch_id"] = "another-subtree"
    elif change == "omit":
        body["certificate"]["events"] = []
    elif change == "duplicate":
        body["certificate"]["events"].append(deepcopy(event))
    elif change == "frontier":
        body["certificate"]["frontier"] = []
    elif change == "counters":
        body["certificate"]["accounting"]["execution_work"]["heuristic_evaluations"] -= 1
    elif change == "source-measurement":
        body["certificate"]["request"]["source"]["daily_source"]["options"][0]["measurements"][0][
            "value"
        ] += 1
    else:
        other = runs("early").model_dump(mode="json")
        other["certificate"]["events"] = [event]
        body = other
    # Repair the failure digest; this is not accepted as evidence of arithmetic.
    if change not in ("omit", "duplicate", "transplant"):
        event["basis"]["evaluation_digest"] = proof._digest(
            v2.WeeklyNumericBoundV2.model_validate_json(json.dumps(bound))
        )
    if change in ("lower", "upper", "applicability", "evidence", "indexes", "partial"):
        assert v2.WeeklySearchCertificateV2.model_validate_json(json.dumps(body["certificate"]))
    with pytest.raises((ValidationError, ValueError)):
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
    ),
)
def test_resource_exhaustion_conservative(resource):
    if resource.startswith("max_"):
        cap = forward_limits(**{resource: 0})
    else:
        base = forward_limits()
        cap = forward_limits(
            max_reserved_work=v2.WeeklyWorkV2.model_validate(
                base.max_reserved_work.model_dump() | {resource: 0}
            )
        )
    result = run(inputs("early"), limits=cap, reuse_preparation=True)
    assert result.outcome is DailyOutcome.TIMEOUT
    assert result.witness is None


def test_deadline_and_verifier_expiration(runs):
    result = run(inputs("single"), limits=forward_limits(deadline=10), clock=lambda: 10)
    assert result.outcome is DailyOutcome.TIMEOUT
    assert result.termination == "DEADLINE"
    # Existing independent deadline withdrawal policy also applies to closures.
    data = inputs("week-quantity")
    result = run(data, limits=forward_limits(deadline=10), clock=lambda: 0, reuse_preparation=True)
    withdrawn = ComputedWeeklySolveResultV2.model_validate(result, context={"v2_clock": lambda: 10})
    assert withdrawn.outcome is DailyOutcome.TIMEOUT
    assert not withdrawn.verification_complete and withdrawn.witness is None


@pytest.mark.parametrize(
    "mode",
    (
        "missing-additional",
        "derived-additional",
        "unknown-app",
        "not-applicable",
        "dependency-unknown",
    ),
)
def test_applicability_and_required_facts(mode):
    data = audit_case(
        target=64, enabled=mode != "not-applicable", unknown_dependency=mode == "dependency-unknown"
    )
    kb = data["knowledge"]
    rules = []
    for rule in kb.rules:
        if rule.attribute == "synthetic_week_quantity_total" and mode.endswith("additional"):
            extra = (
                "synthetic_profile_enabled"
                if mode == "missing-additional"
                else "synthetic_week_complete"
            )
            rule = RuleDefinition.model_validate(
                rule.model_dump() | dict(required_facts=(rule.attribute, extra))
            )
        rules.append(rule)
    context = data["context"]
    if mode == "unknown-app":
        context = revise(
            context,
            facts=tuple(f for f in context.facts if f.fact_id != "synthetic_context_enabled"),
        )
    kb = build_knowledge_snapshot(
        kb.model_dump(exclude={"content_digest"}) | dict(rules=tuple(rules))
    )
    context = revise(context, expected_kb_digest=kb.content_digest)
    # Adapt the established binding helper's fixture vocabulary.
    rebound = rebind(
        dict(
            kb=data["knowledge"],
            context=data["context"],
            daily=data["sources"].daily_source,
            source=data["sources"],
            request=data["request"],
        ),
        context=context,
        kb=kb,
    )
    data.update(
        knowledge=kb, context=context, sources=rebound["source"], request=rebound["request"]
    )
    result = run(data, reuse_preparation=True)
    assert not any(e.kind == "FORWARD_CHECK_CLOSURE" for e in result.certificate.events)
    expected = (
        DailyOutcome.FEASIBLE
        if mode == "not-applicable"
        else DailyOutcome.INFEASIBLE
        if mode == "derived-additional"
        else DailyOutcome.INSUFFICIENT_DATA
    )
    assert result.outcome is expected


@pytest.mark.parametrize("capacity", (0, 1))
def test_reuse_is_fresh_and_equivalent(capacity, runs):
    result = run(
        inputs("week-quantity"), reuse_preparation=True, preparation_cache_entries=capacity
    )
    assert result.certificate == runs().certificate
    assert result.outcome == runs().outcome
    assert result.execution_preparation == result.verification_preparation
    assert result.execution_preparation is not None
    if capacity == 0:
        assert result.execution_preparation.cache_hits == 0


def test_strict_original_json(runs):
    result = runs()
    assert (
        validate_contract_json(ComputedWeeklySolveResultV2, result.model_dump_json(by_alias=True))
        == result
    )


def test_chronological_policy_stays_selectable():
    data = inputs("single")
    baseline = solver.solve_weekly_plan_v2(
        **data, strategy=strategy(), limits=limits(), reuse_preparation=True
    )
    improved = run(data, reuse_preparation=True)
    assert baseline.witness == improved.witness
    assert baseline.certificate.accounting.execution_work.heuristic_evaluations == 0
    assert baseline.certificate.accounting.policy == "synthetic-weekly-work-reservation.v2"
    assert improved.certificate.accounting.execution_work.heuristic_evaluations > 0


@pytest.mark.parametrize("operator", ("LT", "LE", "GT", "GE", "EQ", "NE"))
@pytest.mark.parametrize("scope", ("DAY", "WEEK"))
def test_every_operator_through_complete_public_proof_path(operator, scope):
    data = audit_case(day_cap=9)
    attribute = (
        "synthetic_day_quantity_total" if scope == "DAY" else "synthetic_week_quantity_total"
    )

    def transform(rule):
        return (
            RuleDefinition.model_validate(
                rule.model_dump() | dict(operator=PredicateOperator(operator))
            )
            if rule.attribute == attribute
            else rule
        )

    result = run(changed_rules(data, transform), reuse_preparation=True)
    expected = DailyOutcome.FEASIBLE if operator in ("LE", "GE", "EQ") else DailyOutcome.INFEASIBLE
    assert result.outcome is expected
    if expected is DailyOutcome.INFEASIBLE:
        assert result.certificate.events[0].kind == "FORWARD_CHECK_CLOSURE"
        assert result.certificate.accounting.logical_nodes == 0


def test_partial_measurements_are_not_zero():
    data = audit_case(variable=(20,), target=64)
    options = list(data["sources"].daily_source.options)
    # Exactly one option is incomplete; the other original option remains known.
    options[1] = options[1].model_copy(
        update={
            "measurements": (options[1].measurements[0].model_copy(update={"complete": False}),)
        }
    )
    rebound = rebind(
        dict(
            kb=data["knowledge"],
            context=data["context"],
            daily=data["sources"].daily_source,
            source=data["sources"],
            request=data["request"],
        ),
        options=tuple(options),
    )
    data.update(sources=rebound["source"], request=rebound["request"])
    result = run(data, reuse_preparation=True)
    assert result.outcome is DailyOutcome.INSUFFICIENT_DATA
    assert not any(e.kind == "FORWARD_CHECK_CLOSURE" for e in result.certificate.events)


def test_corrupt_execution_measurement_map_never_authorizes_checker(monkeypatch):
    compile_original = _compile_week

    def corrupt(manifest):
        program = compile_original(manifest)
        options = dict(program.day_program.options)
        for name, option in options.items():
            options[name] = option.model_copy(
                update={"measurements": (option.measurements[0].model_copy(update={"value": 0}),)}
            )
        return replace(program, day_program=replace(program.day_program, options=options))

    monkeypatch.setattr(solver, "_compile_week", corrupt)
    with pytest.raises(ValueError, match="event differs"):
        run(inputs("single"), reuse_preparation=True)


def test_forward_event_order_and_variable_indexes_reject(runs):
    result = runs("late")
    assert len(result.certificate.events) > 1
    for mutation in ("order", "slot", "choice", "remaining-slot"):
        body = result.model_dump(mode="json")
        events = body["certificate"]["events"]
        event = next(e for e in events if e["kind"] == "FORWARD_CHECK_CLOSURE")
        if mutation == "order":
            events[0], events[1] = events[1], events[0]
        elif mutation == "slot":
            event["scope"]["path"][0]["slot"]["canonical_index"] += 1
        elif mutation == "choice":
            event["scope"]["path"][0]["original_domain_index"] += 1
        else:
            event["remaining_domains"][0]["slot"]["canonical_index"] += 1
        with pytest.raises(ValueError):
            validate_contract_json(ComputedWeeklySolveResultV2, json.dumps(body))


def test_exact_bound_reservations_and_one_short(runs):
    result = runs()
    a = result.certificate.accounting
    exact = forward_limits(
        max_nodes=0,
        max_reserved_work=a.reserved_work,
        max_proof_records=1,
        max_proof_bytes=a.proof_bytes_reserved,
    )
    assert (
        run(inputs("week-quantity"), limits=exact, reuse_preparation=True).outcome
        is DailyOutcome.INFEASIBLE
    )
    work = a.reserved_work.model_dump()
    work["heuristic_evaluations"] -= 1
    short = forward_limits(max_nodes=0, max_reserved_work=v2.WeeklyWorkV2(**work))
    timeout = run(inputs("week-quantity"), limits=short, reuse_preparation=True)
    assert timeout.outcome is DailyOutcome.TIMEOUT
    assert timeout.termination == "HEURISTIC_BUDGET"
    assert not timeout.certificate.events


@pytest.mark.parametrize("cutoff", (2, 5, 10, 20))
def test_deadline_at_forward_operations(cutoff):
    calls = 0

    def clock():
        nonlocal calls
        calls += 1
        return 10 if calls >= cutoff else 0

    result = run(
        inputs("early"), limits=forward_limits(deadline=10), clock=clock, reuse_preparation=True
    )
    assert result.outcome is DailyOutcome.TIMEOUT
    assert result.witness is None


def test_policy_relabeling_does_not_enable_unchecked_authority(runs):
    for key in ("root", "account"):
        body = runs().model_dump()
        if key == "root":
            body["search_policy_version"] = "synthetic-chronological-weekly-search.v2"
        else:
            body["certificate"]["accounting"]["policy"] = "synthetic-weekly-work-reservation.v2"
        with pytest.raises(ValueError):
            ComputedWeeklySolveResultV2.model_validate(body)
