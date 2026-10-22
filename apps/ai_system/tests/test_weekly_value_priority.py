"""Literal priority ordering and independent replay over unchanged original domains."""

from dataclasses import replace
from functools import lru_cache
from typing import Any

import pytest
from pydantic import ValidationError
from test_weekly_bounds import changed_rules, forward_limits

from savora_ai.core.reasoning.weekly_search_v2 import solve_weekly_plan_v2, verify_weekly_plan_v2
from savora_ai.evals.synthetic_week_cases import build_week_case
from savora_ai.schemas import weekly_search_v2 as v2
from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.knowledge import PredicateOperator, RuleDefinition
from savora_ai.schemas.weekly_solver_v2 import ComputedWeeklySolveResultV2


def priority(case, *, high=True):
    slots = []
    for day in case.request.days:
        for i, domain in enumerate(day.domains):
            slots.append(
                v2.WeeklySlotValueOrderV1(
                    canonical_index=3 * (day.day.day_index - 1) + i,
                    entries=tuple(
                        v2.WeeklyOptionPriorityV1(option=o, priority=(j if high else -j))
                        for j, o in enumerate(sorted(domain.options, key=lambda r: r.option_id))
                    ),
                )
            )
    return v2.WeeklyPrioritySearchStrategyV2(
        declaration=v2.WeeklyValueOrderV1(
            request_digest=case.request.content_digest,
            source=case.request.expected_source,
            slots=tuple(slots),
        )
    )


@lru_cache
def run(name="early", high=True):
    c = build_week_case(name)
    if name == "early":
        data: dict[str, Any] = dict(
            request=c.request,
            candidates=c.candidates,
            knowledge=c.knowledge,
            context=c.context,
            sources=c.sources,
        )
        data = changed_rules(
            data,
            lambda r: (
                RuleDefinition.model_validate(r.model_dump() | {"operator": PredicateOperator.GE})
                if r.attribute == "synthetic_week_quantity_total"
                else r
            ),
        )
        c = replace(c, **data)
    args: dict[str, Any] = dict(
        request=c.request,
        candidates=c.candidates,
        knowledge=c.knowledge,
        context=c.context,
        sources=c.sources,
    )
    return args, solve_weekly_plan_v2(
        **args, strategy=priority(c, high=high), limits=forward_limits(), reuse_preparation=True
    )


def test_priority_changes_first_witness_without_renumbering_options():
    args, low = run(high=False)
    _, high = run(high=True)
    assert high.verification_complete and low.verification_complete
    assert high.outcome.value == low.outcome.value == "FEASIBLE"
    assert high.witness is not None and low.witness is not None
    assert high.witness.trial != low.witness.trial
    for result in (low, high):
        assert result.certificate.proof_policy_version == "synthetic-weekly-priority-coverage.v2"
        assert verify_weekly_plan_v2(result, **args) == result
        assert (
            validate_contract_json(
                ComputedWeeklySolveResultV2, result.model_dump_json(by_alias=True)
            )
            == result
        )
    assert high.certificate.original_domains == low.certificate.original_domains


@pytest.mark.parametrize(
    "name", ["exhaustive", "unknown-day", "unknown-measurement", "unknown-refuted"]
)
def test_priority_cannot_promote_fail_or_unknown(name):
    _, result = run(name)
    expected = (
        "INSUFFICIENT_DATA"
        if name.startswith("unknown") and name != "unknown-refuted"
        else "INFEASIBLE"
    )
    assert result.outcome.value == expected
    assert result.witness is None


@pytest.mark.parametrize("attack", ["omit", "extra", "changed_digest", "request", "source"])
def test_exact_domain_binding(attack):
    case = build_week_case("early")
    selected = priority(case)
    body = selected.model_dump()
    declaration = body["declaration"]
    slot = next(s for s in declaration["slots"] if len(s["entries"]) > 1)
    if attack == "omit":
        slot["entries"] = slot["entries"][:-1]
    elif attack == "extra":
        slot["entries"] = (*slot["entries"], slot["entries"][0])
    elif attack == "changed_digest":
        slot["entries"][0]["option"]["combination_digest"] = "f" * 64
    elif attack == "request":
        declaration["request_digest"] = "f" * 64
    else:
        declaration["source"]["version"] = "stale"
    with pytest.raises((ValidationError, ValueError)):
        forged = v2.WeeklyPrioritySearchStrategyV2.model_validate(body)
        forged.declaration.bind(case.request)


def test_checker_rejects_order_transplant_and_does_not_call_executor(monkeypatch):
    args, result = run()
    import savora_ai.core.reasoning.weekly_ordering as ordering

    monkeypatch.setattr(ordering, "_priority_indexes", lambda *_: pytest.fail("executor used"))
    assert verify_weekly_plan_v2(result, **args).verification_complete
    forged = result.model_dump()
    forged["certificate"]["identity"]["strategy"] = priority(
        build_week_case("early"), high=False
    ).model_dump()
    with pytest.raises(ValidationError):
        ComputedWeeklySolveResultV2.model_validate(forged)


@pytest.mark.parametrize(
    "field,value", [("max_nodes", 0), ("max_proof_bytes", 0), ("max_proof_records", 0)]
)
def test_priority_resource_stops_are_verified(field, value):
    case = build_week_case("early")
    result = solve_weekly_plan_v2(
        case.request,
        candidates=case.candidates,
        knowledge=case.knowledge,
        context=case.context,
        sources=case.sources,
        strategy=priority(case),
        limits=forward_limits(**{field: value}),
        reuse_preparation=True,
    )
    assert result.outcome.value == "TIMEOUT" and result.witness is None


def test_zero_ordering_capacity_does_not_execute_priority_work(monkeypatch):
    import savora_ai.core.reasoning.weekly_search_v2 as execution

    case = build_week_case("single")
    work = forward_limits().max_reserved_work.model_dump() | {"heuristic_evaluations": 0}
    limits = forward_limits(max_reserved_work=v2.WeeklyWorkV2.model_validate(work))
    monkeypatch.setattr(
        execution, "_priority_indexes", lambda *_: pytest.fail("unreserved ordering")
    )
    result = execution.solve_weekly_plan_v2(
        case.request,
        candidates=case.candidates,
        knowledge=case.knowledge,
        context=case.context,
        sources=case.sources,
        strategy=priority(case),
        limits=limits,
    )
    assert result.outcome.value == "TIMEOUT"
    assert result.certificate.accounting.execution_work.heuristic_evaluations == 0


def test_nonmonotonic_three_value_permutation_keeps_canonical_frontier():
    from test_planned_swap_contracts import rebuild

    from savora_ai.schemas.daily import DailySlotDomain

    c = build_week_case("repeated-identities")
    args: dict[str, Any] = dict(
        request=c.request,
        candidates=c.candidates,
        knowledge=c.knowledge,
        context=c.context,
        sources=c.sources,
    )
    args = changed_rules(
        args,
        lambda r: (
            RuleDefinition.model_validate(
                r.model_dump() | {"operator": PredicateOperator.GE, "value": 0}
            )
            if r.attribute == "synthetic_week_quantity_total"
            else RuleDefinition.model_validate(r.model_dump() | {"value": 21})
            if r.attribute == "synthetic_week_max_recipe_slot_occurrences"
            else r
        ),
    )
    request = args["request"]
    refs = tuple(
        sorted(
            (o.reference for o in args["sources"].daily_source.options), key=lambda r: r.option_id
        )
    )
    assert len(refs) == 3
    days = tuple(
        d.model_copy(
            update={
                "domains": tuple(
                    DailySlotDomain(
                        slot=domain.slot, options=refs if index == 0 and j == 0 else (refs[0],)
                    )
                    for j, domain in enumerate(d.domains)
                )
            }
        )
        for index, d in enumerate(request.days)
    )
    args["request"] = rebuild(request, days=days)
    fake = replace(c, **args)
    selected = priority(fake)
    declaration = selected.declaration.model_dump()
    declaration["slots"][0]["entries"] = tuple(
        entry.model_copy(update={"priority": (1, 3, 2)[index]})
        for index, entry in enumerate(selected.declaration.slots[0].entries)
    )
    selected = v2.WeeklyPrioritySearchStrategyV2(
        declaration=v2.WeeklyValueOrderV1.model_validate(declaration)
    )
    result = solve_weekly_plan_v2(
        **args, strategy=selected, limits=forward_limits(), reuse_preparation=True
    )
    assert result.outcome.value == "FEASIBLE" and result.witness is not None
    assert result.witness.trial.choices[0].option == refs[1]
    assert verify_weekly_plan_v2(result, **args).verification_complete
    remaining = set()
    for branch in result.certificate.frontier:
        if branch.state.value != "UNEXPLORED":
            continue
        if branch.scope.path:
            remaining.add(branch.scope.path[0].original_domain_index)
        elif branch.scope.decision_slot is not None:
            assert branch.scope.decision_slot.canonical_index == 0
            remaining.update(branch.scope.original_domain_indexes)
    assert remaining == {0, 2}
