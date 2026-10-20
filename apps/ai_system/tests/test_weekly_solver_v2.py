"""Independent literal oracle, proof forgery, resource and compatibility checks."""

import hashlib
import json
from copy import deepcopy
from enum import StrEnum
from typing import Any

import pytest
from pydantic import ValidationError
from test_member2_phase6_integration import audit_case
from test_weekly_evaluation import case, evidence, rebind, revise, rule

from savora_ai.core.reasoning import weekly_proof_v2 as proof
from savora_ai.core.reasoning import weekly_search_v2 as solver
from savora_ai.evals.synthetic_week_cases import build_week_case, exhaustive_oracle
from savora_ai.schemas import weekly_search_v2 as v2
from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.daily import DailyOutcome, DailySlotDomain, MealSlot
from savora_ai.schemas.reasoning import ApplicabilityStatus, RuleStatus
from savora_ai.schemas.weekly import WeeklyDayDomain, WeeklyPlanningRequest
from savora_ai.schemas.weekly_search import WeeklySearchCertificate
from savora_ai.schemas.weekly_solver import ComputedWeeklySolveResult
from savora_ai.schemas.weekly_solver_v2 import ComputedWeeklySolveResultV2


def strategy() -> v2.WeeklySearchStrategyV2:
    return v2.WeeklySearchStrategyV2(
        policy=v2.WeeklyStrategyPolicyV2.CHRONOLOGICAL,
        variable_order="CHRONOLOGICAL",
        value_order="OPTION_ID_ASC",
        propagation="NONE",
    )


def limits(**changes: Any) -> v2.WeeklySearchLimitsV2:
    return v2.WeeklySearchLimitsV2.model_validate(
        dict(
            max_nodes=2000,
            max_reserved_work=v2.WeeklyWorkV2(
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
        | changes
    )


def solve(name: str = "single", **kwargs: Any) -> ComputedWeeklySolveResultV2:
    c = build_week_case(name)
    return solver.solve_weekly_plan_v2(
        c.request,
        candidates=c.candidates,
        knowledge=c.knowledge,
        context=c.context,
        sources=c.sources,
        strategy=strategy(),
        limits=kwargs.pop("limits", limits()),
        **kwargs,
    )


@pytest.fixture(scope="module")
def runs():
    cached: dict[str, ComputedWeeklySolveResultV2] = {}

    def get(name="single"):
        if name not in cached:
            cached[name] = solve(name)
        return cached[name]

    return get


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
def test_independent_literal_oracle(name, runs):
    c = build_week_case(name)
    expected = exhaustive_oracle(c.spec)
    result = runs(name)
    assert result.outcome.value == expected.outcome
    assert result.verification_complete
    assert result.certificate.outcome is None
    assert not result.certificate.exhaustive
    assert result.certificate.verification_state == "NOT_VERIFIED"
    if expected.first_witness is None:
        assert result.witness is None
    else:
        assert result.witness is not None
        refs = sorted(c.sources.daily_source.options, key=lambda o: o.reference.option_id)
        assert tuple(choice.option.option_id for choice in result.witness.trial.choices) == tuple(
            refs[i].reference.option_id for i in expected.first_witness
        )
    account = result.certificate.accounting
    assert (
        len(result.certificate.model_dump_json(by_alias=True).encode())
        <= account.proof_bytes_reserved
    )
    for key in v2.WeeklyWorkV2.model_fields:
        assert getattr(account.execution_work, key) + getattr(
            result.verification_work, key
        ) == getattr(account.reserved_work, key)


def test_single_exact_units(runs):
    result = runs()
    a = result.certificate.accounting
    assert a.logical_nodes == 21
    assert a.backtracks == 0
    assert a.execution_work.combination_preparations == 1
    assert a.execution_work.candidate_preparations == 4  # two candidates in each of two batches
    assert a.execution_work.day_assessments == 7
    assert a.execution_work.week_assessments == 1
    assert a.proof_records_reserved == a.proof_records_written == 1
    assert a.proof_bytes_written == sum(len(proof._bytes(e)) + 1 for e in result.certificate.events)
    assert result.witness is not None
    assert len(result.witness.assignment.days) == 7


def test_fail_dominance_day_prune_and_week_repetition(runs):
    assert runs("unknown-day").outcome is DailyOutcome.INSUFFICIENT_DATA
    assert runs("unknown-refuted").outcome is DailyOutcome.INFEASIBLE
    assert any(e.kind == "DAY_FAILURE" for e in runs("day-pruning").certificate.events)
    assert all(e.kind == "COMPLETED_LEAF" for e in runs("week-quantity").certificate.events)
    assert runs("week-repetition").outcome is DailyOutcome.INFEASIBLE
    assert runs("repeated-identities").outcome is DailyOutcome.FEASIBLE
    unknown = runs("unknown-day").certificate.frontier
    assert any(b.unresolved_obligations for b in unknown)
    assert not any(
        b.state is v2.WeeklyFrontierStateV2.UNRESOLVED_UNKNOWN
        for b in runs("unknown-refuted").certificate.frontier
    )


@pytest.mark.parametrize(
    "unknown_dependency,expected",
    ((False, DailyOutcome.FEASIBLE), (True, DailyOutcome.INSUFFICIENT_DATA)),
)
def test_evidenced_not_applicable_and_unknown_dependency(unknown_dependency, expected):
    data = audit_case(enabled=False, day_unknown=True, unknown_dependency=unknown_dependency)
    result = solver.solve_weekly_plan_v2(
        data["request"],
        candidates=data["candidates"],
        knowledge=data["knowledge"],
        context=data["context"],
        sources=data["sources"],
        strategy=strategy(),
        limits=limits(),
    )
    assert result.outcome is expected
    if not unknown_dependency:
        assert result.witness is not None
        evaluations = result.witness.days[0].evaluation.trace.evaluations
        assert any(
            e.applicability is ApplicabilityStatus.NOT_APPLICABLE and e.status is RuleStatus.UNKNOWN
            for e in evaluations
        )


def test_canonical_permutations_and_no_state_leakage(runs):
    c = build_week_case("early")
    request = WeeklyPlanningRequest.build(
        dict(
            c.request.model_dump(exclude={"content_digest"}),
            days=tuple(
                WeeklyDayDomain(
                    day=d.day,
                    domains=tuple(
                        DailySlotDomain(slot=slot.slot, options=tuple(reversed(slot.options)))
                        for slot in reversed(d.domains)
                    ),
                )
                for d in reversed(c.request.days)
            ),
        )
    )
    result = solver.solve_weekly_plan_v2(
        request,
        candidates=tuple(reversed(c.candidates)),
        knowledge=c.knowledge,
        context=c.context,
        sources=c.sources,
        strategy=strategy(),
        limits=limits(max_cache_entries=4),
    )
    baseline = runs("early")
    assert result.witness == baseline.witness
    assert result.certificate.events == baseline.certificate.events
    assert (
        result.certificate.accounting.cache_entries == result.certificate.accounting.cache_hits == 0
    )
    again = solve("early")
    assert again == baseline
    assert again is not baseline
    assert runs("unknown-day").outcome is DailyOutcome.INSUFFICIENT_DATA


@pytest.mark.parametrize(
    "field,reason",
    (
        ("candidate_preparations", "PREPARATION_BUDGET"),
        ("combination_preparations", "PREPARATION_BUDGET"),
        ("predicate_obligations", "PREDICATE_BUDGET"),
        ("day_assessments", "DAY_BUDGET"),
        ("week_assessments", "WEEK_BUDGET"),
        ("proof_verification_steps", "VERIFICATION_BUDGET"),
    ),
)
def test_zero_work_cap(field, reason):
    work = limits().max_reserved_work.model_dump() | {field: 0}
    result = solve(limits=limits(max_reserved_work=v2.WeeklyWorkV2.model_validate(work)))
    assert result.outcome is DailyOutcome.TIMEOUT
    assert result.termination == reason
    assert result.witness is None
    assert result.verification_complete


@pytest.mark.parametrize(
    "field,reason",
    (
        ("max_nodes", "NODE_BUDGET"),
        ("max_proof_records", "PROOF_RECORD_BUDGET"),
        ("max_proof_bytes", "PROOF_BYTE_BUDGET"),
    ),
)
def test_zero_other_cap(field, reason):
    result = solve(limits=limits(**{field: 0}))
    assert result.outcome is DailyOutcome.TIMEOUT
    assert result.termination == reason
    assert result.witness is None


def exact_limits(result):
    a = result.certificate.accounting
    return limits(
        max_nodes=a.logical_nodes,
        max_reserved_work=a.reserved_work,
        max_proof_records=a.proof_records_reserved,
        max_proof_bytes=a.proof_bytes_reserved,
    )


def test_all_exact_boundaries(runs):
    result = solve(limits=exact_limits(runs()))
    assert result.outcome is DailyOutcome.FEASIBLE
    assert result.witness == runs().witness
    assert result.certificate.accounting == runs().certificate.accounting


@pytest.mark.parametrize(
    "field",
    (
        "candidate_preparations",
        "combination_preparations",
        "predicate_obligations",
        "day_assessments",
        "week_assessments",
        "proof_verification_steps",
        "max_nodes",
        "max_proof_records",
        "max_proof_bytes",
    ),
)
def test_one_below_exact_boundary(field, runs):
    exact = exact_limits(runs()).model_dump()
    if field.startswith("max_"):
        exact[field] -= 1
    else:
        exact["max_reserved_work"][field] -= 1
    result = solve(limits=v2.WeeklySearchLimitsV2.model_validate(exact))
    assert result.outcome is DailyOutcome.TIMEOUT
    assert result.witness is None
    assert result.termination is not None
    assert any(b.state is v2.WeeklyFrontierStateV2.UNEXPLORED for b in result.certificate.frontier)


@pytest.mark.parametrize("cutoff", (2, 3, 5, 10, 34, 45, 66))
def test_preparation_search_and_verification_deadlines(cutoff):
    calls = 0

    def clock():
        nonlocal calls
        calls += 1
        return 10.0 if calls >= cutoff else 0.0

    result = solve(limits=limits(deadline=10.0), clock=clock)
    assert result.outcome is DailyOutcome.TIMEOUT
    assert result.witness is None
    assert not result.verification_complete
    if cutoff >= 34:
        assert result.termination is None
        assert result.verification_deadline_checkpoint is not None
    else:
        assert result.termination == "DEADLINE"
        assert result.execution_deadline_observation == 10.0
    # The retained bounded verifier transcript rechecks without a live clock.
    assert ComputedWeeklySolveResultV2.model_validate(result) == result


@pytest.mark.parametrize(
    "reading",
    (True, float("nan"), float("inf"), "0", 10**10000),
    ids=("bool", "nan", "inf", "string", "overflow"),
)
def test_invalid_clock(reading):
    with pytest.raises(ValueError, match="clock"):
        solve(clock=lambda: reading)


def test_backwards_clock():
    readings = iter((2.0, 1.0))
    with pytest.raises(ValueError, match="clock"):
        solve(limits=limits(deadline=10.0), clock=lambda: next(readings))


@pytest.mark.parametrize(
    "policy,variable,value,propagation",
    (
        (v2.WeeklyStrategyPolicyV2.REVERSE_VALUES, "CHRONOLOGICAL", "OPTION_ID_DESC", "NONE"),
        (v2.WeeklyStrategyPolicyV2.MRV, "MRV", "OPTION_ID_ASC", "KNOWN_FAILURE_FORWARD_CHECK"),
    ),
)
def test_future_declarations_not_executable(policy, variable, value, propagation):
    c = build_week_case("single")
    declaration = v2.WeeklySearchStrategyV2(
        policy=policy, variable_order=variable, value_order=value, propagation=propagation
    )
    with pytest.raises(ValueError, match="only chronological"):
        solver.solve_weekly_plan_v2(
            c.request,
            candidates=c.candidates,
            knowledge=c.knowledge,
            context=c.context,
            sources=c.sources,
            strategy=declaration,
            limits=limits(),
        )


def test_checker_does_not_call_solver_or_v1_replay(monkeypatch, runs):
    result = runs("exhaustive")

    def forbidden(*args, **kwargs):
        raise AssertionError("checker called search kernel")

    monkeypatch.setattr(solver, "solve_weekly_plan_v2", forbidden)
    monkeypatch.setattr("savora_ai.core.reasoning.weekly_search._execute", forbidden)
    assert ComputedWeeklySolveResultV2.model_validate(result) == result


@pytest.mark.parametrize(
    "mutation",
    (
        "event-omit",
        "event-duplicate",
        "event-reorder",
        "event-status",
        "event-digest-rehashed",
        "frontier-omit",
        "frontier-state",
        "frontier-unknown-erase",
        "nodes",
        "backtracks",
        "predicates",
        "verification-work",
        "reservations",
        "written-bytes",
        "proof-records",
        "candidate-digest",
        "manifest-digest",
        "obligations",
        "outcome",
        "verified-flag",
    ),
)
def test_forged_proof_rejected(mutation, runs):
    result = (
        runs("exhaustive")
        if mutation in ("event-omit", "event-duplicate", "event-reorder")
        else runs("unknown-day")
        if mutation == "frontier-unknown-erase"
        else runs()
    )
    payload = result.model_dump()
    cert = payload["certificate"]
    events = list(cert["events"])
    if mutation == "event-omit":
        cert["events"] = tuple(events[:-1])
    elif mutation == "event-duplicate":
        cert["events"] = tuple([events[0], *events])
    elif mutation == "event-reorder":
        cert["events"] = tuple(reversed(events))
    elif mutation == "event-status":
        events[0]["declared_status"] = RuleStatus.FAIL
    elif mutation == "event-digest-rehashed":
        # An attacker can hash any invented fact. It is not an evaluation proof.
        events[0]["evaluation_digest"] = hashlib.sha256(b'{"inventedFact":true}').hexdigest()
    elif mutation == "frontier-omit":
        cert["frontier"] = ()
    elif mutation == "frontier-state":
        cert["frontier"][0]["state"] = v2.WeeklyFrontierStateV2.UNEXPLORED
        cert["frontier"][0]["supporting_event"] = None
    elif mutation == "frontier-unknown-erase":
        cert["frontier"][0]["state"] = v2.WeeklyFrontierStateV2.EXPLORED
        cert["frontier"][0]["unresolved_obligations"] = ()
    elif mutation in ("nodes", "backtracks", "written-bytes", "proof-records"):
        key = dict(
            nodes="logical_nodes",
            backtracks="backtracks",
            **{"written-bytes": "proof_bytes_written", "proof-records": "proof_records_reserved"},
        )[mutation]
        cert["accounting"][key] += 1
    elif mutation in ("predicates", "reservations"):
        cert["accounting"]["reserved_work" if mutation == "reservations" else "execution_work"][
            "predicate_obligations"
        ] += 1
    elif mutation == "verification-work":
        payload["verification_work"]["week_assessments"] += 1
    elif mutation in ("candidate-digest", "manifest-digest"):
        key = "candidate_set_digest" if mutation == "candidate-digest" else "manifest_digest"
        cert["identity"][key] = "f" * 64
        for event in events:
            event["identity"][key] = "f" * 64
    elif mutation == "obligations":
        cert["rule_obligations"] = cert["rule_obligations"][:-1]
    elif mutation == "outcome":
        payload["outcome"] = DailyOutcome.INFEASIBLE
    else:
        payload["verification_complete"] = False
    if mutation in ("event-status", "event-digest-rehashed", "candidate-digest"):
        assert v2.WeeklySearchCertificateV2.model_validate(cert)
    with pytest.raises(ValidationError):
        ComputedWeeklySolveResultV2.model_validate(payload)


def test_forged_witness_and_source_transplant(runs):
    baseline = runs()
    payload = baseline.model_dump()
    assert payload["witness"] is not None
    payload["witness"]["facts"][1]["observation"]["value"] += 1
    with pytest.raises(ValidationError):
        ComputedWeeklySolveResultV2.model_validate(payload)
    c = build_week_case("late")
    with pytest.raises(ValueError, match="independently selected"):
        solver.verify_weekly_plan_v2(
            baseline,
            request=c.request,
            candidates=c.candidates,
            knowledge=c.knowledge,
            context=c.context,
            sources=c.sources,
        )
    with pytest.raises(ValidationError):
        ComputedWeeklySolveResultV2.model_validate(
            baseline.model_copy(update={"certificate": runs("late").certificate})
        )


@pytest.mark.parametrize("nested", (False, True))
def test_unchecked_objects_revalidated(nested, runs):
    baseline = runs()
    bad = (
        baseline.model_copy(
            update={"manifest": baseline.manifest.model_copy(update={"day_checks": ()})}
        )
        if nested
        else baseline.model_copy(update={"extraAuthority": True})
    )
    with pytest.raises(ValidationError):
        ComputedWeeklySolveResultV2.model_validate(bad)
    invalid = ComputedWeeklySolveResultV2.model_construct(
        **(baseline.model_dump() | {"verification_complete": 1})
    )
    with pytest.raises(ValidationError):
        ComputedWeeklySolveResultV2.model_validate(invalid)


def test_original_json_strict_roundtrip_and_duplicate_keys(runs):
    result = runs()
    raw = result.model_dump_json(by_alias=True)
    assert validate_contract_json(ComputedWeeklySolveResultV2, raw) == result
    with pytest.raises(ValueError):
        validate_contract_json(ComputedWeeklySolveResultV2, '{"outcome":"FEASIBLE",' + raw[1:])
    payload = json.loads(raw)
    payload["verificationComplete"] = 1
    with pytest.raises(ValueError):
        validate_contract_json(ComputedWeeklySolveResultV2, json.dumps(payload))


def test_cross_version_certificates_and_fake_enum(runs):
    result = runs()
    with pytest.raises(ValidationError):
        WeeklySearchCertificate.model_validate(result.certificate.model_dump())
    with pytest.raises(ValidationError):
        ComputedWeeklySolveResult.model_validate(result.model_dump())
    forged = result.certificate.model_dump() | {"schema_version": "weekly-coverage.v1"}
    with pytest.raises(ValidationError):
        v2.WeeklySearchCertificateV2.model_validate(forged)

    class ForeignOutcome(StrEnum):
        FEASIBLE = "FEASIBLE"

    with pytest.raises(ValidationError):
        ComputedWeeklySolveResultV2.model_validate(
            result.model_copy(update={"outcome": ForeignOutcome.FEASIBLE})
        )


def test_hostile_containers_callbacks_and_malformed_inputs_before_zero_budget(runs):
    class HostileTuple(tuple):
        def __iter__(self):
            raise AssertionError("hostile iterator executed")

    result = runs()
    for bad in (
        result.model_copy(update={"candidates": HostileTuple()}),
        result.model_copy(update={"certificate": lambda: True}),
    ):
        with pytest.raises(ValidationError):
            ComputedWeeklySolveResultV2.model_validate(bad)
    c = build_week_case("single")
    with pytest.raises(ValidationError):
        solver.solve_weekly_plan_v2(
            c.request.model_copy(update={"days": ()}),
            candidates=c.candidates,
            knowledge=c.knowledge,
            context=c.context,
            sources=c.sources,
            strategy=strategy(),
            limits=limits(max_nodes=0),
        )


def test_rehashed_missing_known_failure_cannot_close_space(runs):
    # Replace a known-failure transcript with an internally consistent carrier
    # that claims no events or work. Structural declarations deliberately allow
    # this; only the computed boundary can refuse its invented exhaustion.
    payload = deepcopy(runs("exhaustive").model_dump())
    cert = payload["certificate"]
    cert.update(events=(), frontier=(), accounting=v2.WeeklyAccountingV2().model_dump())
    assert v2.WeeklySearchCertificateV2.model_validate(cert)
    with pytest.raises(ValidationError):
        ComputedWeeklySolveResultV2.model_validate(payload)


def legacy_fixture_solve(data):
    request = revise(
        data["request"],
        days=tuple(
            WeeklyDayDomain(
                day=d.day,
                domains=tuple(
                    DailySlotDomain(slot=domain.slot, options=domain.options[:1])
                    for domain in d.domains
                ),
            )
            for d in data["request"].days
        ),
    )
    return solver.solve_weekly_plan_v2(
        request,
        candidates=(data["candidate"],),
        knowledge=data["kb"],
        context=data["context"],
        sources=data["source"],
        strategy=strategy(),
        limits=limits(),
    )


@pytest.mark.parametrize("scope", ("day", "week", "both"))
def test_empty_mandatory_inventory_is_unknown(scope):
    data = case(
        **(
            {"day_rules": ()}
            if scope == "day"
            else {"week_rules": ()}
            if scope == "week"
            else {"day_rules": (), "week_rules": ()}
        )
    )
    result = legacy_fixture_solve(data)
    assert result.outcome is DailyOutcome.INSUFFICIENT_DATA
    assert result.witness is None
    assert any(
        isinstance(o, v2.WeeklyPrerequisiteObligationV2)
        and o.prerequisite == "MANDATORY_CHECK_COVERAGE"
        for b in result.certificate.frontier
        for o in b.unresolved_obligations
    )


@pytest.mark.parametrize("missing", ("suitability", "fixed"))
def test_missing_prerequisites_cannot_authorize_pass(missing):
    parameters: dict[str, Any] = {missing: False}
    result = legacy_fixture_solve(case(**parameters))
    assert result.outcome is DailyOutcome.INSUFFICIENT_DATA
    assert result.witness is None
    expected = "SLOT_SUITABILITY" if missing == "suitability" else "FIXED_CONFIGURATION"
    assert any(
        isinstance(o, v2.WeeklyPrerequisiteObligationV2) and o.prerequisite == expected
        for b in result.certificate.frontier
        for o in b.unresolved_obligations
    )


def test_known_unary_exclusion_is_verified_without_nodes():
    data = case()
    changed = tuple(
        o.model_copy(
            update={
                "suitability": o.suitability.model_copy(
                    update={"slots": (MealSlot.LUNCH, MealSlot.DINNER)}
                )
            }
        )
        for o in data["daily"].options
    )
    result = legacy_fixture_solve(rebind(data, options=changed))
    assert result.outcome is DailyOutcome.INFEASIBLE
    assert result.certificate.accounting.logical_nodes == 0
    assert len(result.certificate.events) == 1
    assert result.certificate.events[0].kind == "UNARY_FAILURE"


def test_known_combination_failure_is_a_verified_exclusion():
    data = case()
    changed = tuple(
        o.model_copy(
            update={
                "combination": revise(
                    o.combination,
                    observations=tuple(
                        ob.model_copy(
                            update={
                                "observation": ob.observation.model_copy(update={"value": False})
                            }
                        )
                        for ob in o.combination.observations
                    ),
                )
            }
        )
        for o in data["daily"].options
    )
    result = legacy_fixture_solve(rebind(data, options=changed))
    assert result.outcome is DailyOutcome.INFEASIBLE
    assert result.certificate.accounting.logical_nodes == 0
    assert result.certificate.events[0].kind == "UNARY_FAILURE"


def test_missing_recipe_pool_is_not_a_pass():
    c = build_week_case("single")
    result = solver.solve_weekly_plan_v2(
        c.request,
        candidates=(),
        knowledge=c.knowledge,
        context=c.context,
        sources=c.sources,
        strategy=strategy(),
        limits=limits(),
    )
    assert result.outcome is DailyOutcome.INSUFFICIENT_DATA
    assert result.witness is None


def test_frontier_encoder_bug_is_detected_by_independent_interval_check(monkeypatch):
    # Both executor and checker's expected-frontier encoder are deliberately
    # replaced. The separately implemented interval partition must still refuse.
    original = proof._rest

    def broken(domains, rank):
        return original(domains, rank)[1:]

    monkeypatch.setattr(proof, "_rest", broken)
    monkeypatch.setattr(solver, "_rest", broken)
    with pytest.raises(ValidationError, match=r"interval|partition"):
        solve("early")


def test_leaf_obligation_capacity_stops_before_week_assessment():
    data = case(week_rules=tuple(rule("many-week-" + str(i)) for i in range(248)))
    result = legacy_fixture_solve(data)
    assert len(result.certificate.rule_obligations) == 251
    assert result.outcome is DailyOutcome.TIMEOUT
    assert result.termination == "PROOF_RECORD_BUDGET"
    assert result.verification_complete
    assert result.certificate.accounting.execution_work.week_assessments == 0
    assert result.witness is None


@pytest.mark.parametrize("failure", (False, True))
def test_large_source_evidence_is_never_silently_truncated(failure):
    data = case()
    context = revise(
        data["context"], evidence=tuple(evidence("many-origin-" + str(i)) for i in range(65))
    )
    options = data["daily"].options
    if failure:
        options = tuple(
            o.model_copy(
                update={
                    "suitability": o.suitability.model_copy(
                        update={"slots": (MealSlot.LUNCH, MealSlot.DINNER)}
                    )
                }
            )
            for o in options
        )
    result = legacy_fixture_solve(rebind(data, context=context, options=options))
    assert result.outcome is (DailyOutcome.TIMEOUT if failure else DailyOutcome.FEASIBLE)
    assert len(result.manifest.request.source.daily_source.context.evidence) == 65
    if failure:
        assert result.termination == "PROOF_RECORD_BUDGET"
        assert result.certificate.events == ()
        assert result.witness is None
