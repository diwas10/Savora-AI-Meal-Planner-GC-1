"""Frozen public baseline equality and independent cache/proof/oracle checks."""

import inspect
from typing import Any

import pytest
from pydantic import ValidationError
from reference_combination_preparation import evaluate_combination as reference
from test_combination_evaluation import changed, declaration, packet
from test_weekly_solver_v2 import limits, strategy

from savora_ai.core.reasoning import (
    preparation,
)
from savora_ai.core.reasoning import weekly_proof_v2 as proof
from savora_ai.core.reasoning import (
    weekly_search_v2 as solver,
)
from savora_ai.core.reasoning.combinations import (
    _evaluate_prepared_combination,
    evaluate_combination,
)
from savora_ai.core.reasoning.filtering import filter_candidates
from savora_ai.core.reasoning.weekly import solve_weekly_plan
from savora_ai.evals.synthetic_week_cases import build_week_case, exhaustive_oracle
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    FactSubjectKind,
    validate_contract_json,
)
from savora_ai.schemas.knowledge import RuleScope
from savora_ai.schemas.weekly_solver_v2 import ComputedWeeklySolveResultV2


def session(data, capacity=1):
    combo, candidates, kb, context = data
    return preparation._PreparedRecipePool(
        candidates=candidates, knowledge=kb, context=context, sources=(combo,), capacity=capacity
    )


def evaluate(data, prepared=None, **changes):
    combo, candidates, kb, context = data
    kwargs = (
        dict(candidates=candidates, knowledge=kb, context=context, trusted_combination=combo)
        | changes
    )
    return (
        evaluate_combination(combo, **kwargs)
        if prepared is None
        else _evaluate_prepared_combination(combo, **kwargs, prepared=prepared)
    )


@pytest.mark.parametrize(
    "variant",
    (
        "pass",
        "fixed",
        "fail",
        "unknown",
        "not-applicable",
        "missing-applicability",
        "missing-composition",
        "empty",
        "missing-candidate",
        "duplicate",
    ),
)
@pytest.mark.parametrize("capacity", (0, 1))
def test_frozen_full_public_baseline_equivalence(variant, capacity):
    options: dict[str, Any] = (
        {"fixed": True}
        if variant == "fixed"
        else {"compatible": False}
        if variant == "fail"
        else {"compatible": None}
        if variant == "unknown"
        else {"enabled": False}
        if variant == "not-applicable"
        else {"enabled": None}
        if variant == "missing-applicability"
        else {"complete": False}
        if variant == "missing-composition"
        else {"rules": ()}
        if variant == "empty"
        else {}
    )
    combo, candidates, kb, context = packet(**options)
    if variant == "missing-candidate":
        candidates = candidates[:1]
    if variant == "duplicate":
        part = combo.components[0]
        combo = changed(
            combo, components=(part, part.model_copy(update={"component_id": "repeat"}))
        )
    data = combo, candidates, kb, context
    expected = reference(
        combo, candidates=candidates, knowledge=kb, context=context, trusted_combination=combo
    )
    assert evaluate(data).model_dump() == expected.model_dump()
    cached = session(data, capacity)
    cached.assess()
    for _ in range(2):
        assert evaluate(data, cached).model_dump() == expected.model_dump()
    counts = cached.snapshot()
    assert counts["physical_filter_calls"] == (1 if capacity else 3)
    assert counts["cache_hits"] == (2 if capacity else 0)


@pytest.mark.parametrize(
    "change",
    (
        "context",
        "context-version",
        "kb",
        "candidate",
        "candidate-facts",
        "evidence",
        "source",
        "configuration",
    ),
)
def test_exact_dependencies_reject_reuse_across_changes(change):
    original = packet(fixed=True)
    cached = session(original)
    cached.assess()
    combo, candidates, kb, context = original
    if change == "context":
        combo, candidates, kb, context = packet(fixed=True, enabled=False)
    elif change == "kb":
        combo, candidates, kb, context = packet(
            fixed=True, rules=(declaration("different", RuleScope.RECIPE, "synthetic_flag"),)
        )
    elif change == "context-version":
        body: dict[str, Any] = context.model_dump(exclude={"content_digest"})
        body["version"] = "2"
        body["facts"] = tuple(
            f.model_copy(
                update=({"context_version": "2"} if f.context_id is not None else {})
                | ({"subject_version": "2"} if f.subject_kind is FactSubjectKind.CONTEXT else {})
            )
            for f in context.facts
        )
        context = type(context).build(body)
        combo = changed(
            combo, context_version=context.version, context_digest=context.content_digest
        )
    elif change in ("candidate", "candidate-facts", "evidence"):
        first = candidates[0]
        body = first.model_dump(exclude={"content_digest"})
        if change == "candidate":
            body["snapshot_version"] = "new"
        elif change == "candidate-facts":
            body["facts"] = tuple(
                f.model_copy(
                    update={"observation": f.observation.model_copy(update={"value": False})}
                )
                for f in first.facts
            )
        else:
            ev = first.evidence[0].model_copy(update={"source": "Changed provenance"})
            body["evidence"] = (ev,)
        candidates = (CandidateRecipeFacts.build(body), *candidates[1:])
    else:
        combo = changed(
            combo,
            **(
                {"snapshot_version": "new"}
                if change == "source"
                else {"portion_configuration_version": "new"}
            ),
        )
    with pytest.raises(ValueError):
        evaluate((combo, candidates, kb, context), cached)
    assert cached.snapshot()["physical_filter_calls"] == 1


def test_eviction_disabled_and_permutation():
    data = packet(fixed=True)
    cached = session(data)
    first = evaluate(data, cached)
    cached.discard()
    second = evaluate((data[0], tuple(reversed(data[1])), data[2], data[3]), cached)
    assert first == second
    assert cached.snapshot()["cache_evictions"] == 1
    assert cached.snapshot()["physical_filter_calls"] == 2
    snapshot = cached.snapshot()
    snapshot["cache_hits"] = 999
    assert cached.snapshot()["cache_hits"] == 0
    with pytest.raises(TypeError):
        cached.fake_affirmative = True


def test_untrusted_authority_and_fabricated_prepared_records():
    data = packet(fixed=True)
    assert evaluate(data, trusted_combination=None) == reference(
        data[0], candidates=data[1], knowledge=data[2], context=data[3], trusted_combination=None
    )
    untrusted = preparation._PreparedRecipePool(
        candidates=data[1], knowledge=data[2], context=data[3], sources=(), capacity=1
    )
    assert evaluate(data, untrusted, trusted_combination=None) == evaluate(
        data, trusted_combination=None
    )
    affirmative = session(data).assess()
    for forged in (
        affirmative,
        affirmative.model_copy(update={"eligible_ids": ("invented",)}),
        object.__new__(preparation._PreparedRecipePool),
    ):
        with pytest.raises(ValueError, match="locally computed"):
            evaluate(data, forged)
    with pytest.raises(TypeError):
        forged_kwargs: dict[str, Any] = dict(
            candidates=data[1], knowledge=data[2], context=data[3], prepared=affirmative
        )
        evaluate_combination(data[0], **forged_kwargs)
    with pytest.raises(ValidationError):
        evaluate((data[0].model_copy(update={"components": ()}), *data[1:]), session(data))
    assert inspect.signature(evaluate_combination) == inspect.signature(reference)


def test_same_recipe_across_original_fixed_configurations():
    case = build_week_case("early")
    options = case.sources.daily_source.options
    shared = preparation._PreparedRecipePool(
        candidates=case.candidates,
        knowledge=case.knowledge,
        context=case.context,
        sources=tuple(o.combination for o in options),
        capacity=1,
    )
    shared.assess()
    for option in options:
        arguments: dict[str, Any] = dict(
            candidates=case.candidates,
            knowledge=case.knowledge,
            context=case.context,
            trusted_combination=option.combination,
        )
        assert (
            _evaluate_prepared_combination(
                option.combination, **arguments, prepared=shared
            ).model_dump()
            == reference(option.combination, **arguments).model_dump()
        )
    assert shared.snapshot()["physical_filter_calls"] == 1
    assert shared.snapshot()["combination_evaluations"] == 3


@pytest.mark.parametrize(
    "corruption", ("duplicate-component", "conflicting-preparation", "missing-evidence")
)
def test_conflicting_or_unchecked_components_never_reach_cached_assessments(corruption):
    data = packet(fixed=True)
    cached = session(data)
    cached.assess()
    combo = data[0]
    part = combo.components[0]
    if corruption == "duplicate-component":
        bad = combo.model_copy(update={"components": (part, part)})
    elif corruption == "conflicting-preparation":
        bad_part = part.model_copy(
            update={
                "preparation": part.preparation.model_copy(update={"preparation_id": "different"})
            }
        )
        bad = combo.model_copy(update={"components": (bad_part, *combo.components[1:])})
    else:
        bad = combo.model_copy(update={"evidence": ()})
    for worker in (reference, evaluate_combination):
        with pytest.raises(ValidationError):
            worker(
                bad, candidates=data[1], knowledge=data[2], context=data[3], trusted_combination=bad
            )
    with pytest.raises(ValidationError):
        evaluate((bad, *data[1:]), cached)
    assert cached.snapshot()["cache_hits"] == 0


def solve(name="early", **changes):
    c = build_week_case(name)
    args: dict[str, Any] = (
        dict(
            candidates=c.candidates,
            knowledge=c.knowledge,
            context=c.context,
            sources=c.sources,
            strategy=strategy(),
            limits=limits(),
            reuse_preparation=True,
        )
        | changes
    )
    return solver.solve_weekly_plan_v2(c.request, **args)


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
        "repeated-identities",
        "empty-domain",
    ),
)
def test_oracle_full_witness_and_proof_equivalence(name):
    result = solve(name)
    baseline = solve(name, reuse_preparation=False)
    expected = exhaustive_oracle(build_week_case(name).spec)
    assert result.outcome.value == expected.outcome
    assert result.witness == baseline.witness
    assert result.certificate == baseline.certificate
    assert result.verification_work == baseline.verification_work
    assert result.execution_preparation == result.verification_preparation
    stats = result.execution_preparation
    assert stats is not None
    assert stats.physical_filter_calls == 1
    assert (
        stats.logical_candidate_assessments
        == result.certificate.accounting.execution_work.candidate_preparations
    )


@pytest.mark.parametrize("name", ("early", "repeated-identities"))
def test_same_fixture_v1_and_reused_v2_witness_equivalence(name):
    case = build_week_case(name)
    legacy = solve_weekly_plan(
        case.request,
        candidates=case.candidates,
        knowledge=case.knowledge,
        context=case.context,
        sources=case.sources,
        limits=case.spec.limits,
    )
    reused = solve(name)
    assert legacy.outcome == reused.outcome
    assert legacy.witness == reused.witness


@pytest.mark.parametrize("capacity", (0, 1))
def test_fresh_execution_checker_and_consecutive_requests(monkeypatch, capacity):
    actual = []
    original = filter_candidates

    def observe(*args, **kwargs):
        actual.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(preparation, "filter_candidates", observe)
    one = solve(preparation_cache_entries=capacity)
    assert len(actual) == (2 if capacity else 6)
    before = len(actual)
    two = solve(preparation_cache_entries=capacity)
    assert len(actual) - before == before
    assert one == two
    assert one.execution_preparation is not None
    assert one.execution_preparation.physical_filter_calls == (1 if capacity else 3)
    assert ComputedWeeklySolveResultV2.model_validate(one) == one
    assert len(actual) == before * 2 + before // 2  # fresh checker on revalidation


def test_checker_rejects_execution_cache_corruption(monkeypatch):
    original = proof._prepared_option

    def corrupt(*args, **kwargs):
        decision = original(*args, **kwargs)
        from savora_ai.schemas.reasoning import RuleStatus

        return decision.model_copy(
            update={
                "slots": tuple(
                    s.model_copy(update={"status": RuleStatus.FAIL}) for s in decision.slots
                )
            }
        )

    monkeypatch.setattr(solver, "_prepared_option", corrupt)
    with pytest.raises(ValidationError):
        solve()


@pytest.mark.parametrize("mutation", ("proof", "counts", "policy", "unchecked"))
def test_forged_accounting_and_rehashed_proof_rejected(mutation):
    result = solve()
    body = result.model_dump()
    if mutation == "proof":
        body["certificate"]["events"][0]["evaluation_digest"] = "f" * 64
    elif mutation == "counts":
        body["execution_preparation"]["cache_hits"] += 1
    elif mutation == "policy":
        body["execution_preparation"]["policy"] = "untrusted"
    else:
        body["reuse_preparation"] = 1
    with pytest.raises(ValidationError):
        ComputedWeeklySolveResultV2.model_validate(body)
    assert (
        validate_contract_json(ComputedWeeklySolveResultV2, result.model_dump_json(by_alias=True))
        == result
    )


@pytest.mark.parametrize("field", ("max_nodes", "max_proof_records", "max_proof_bytes"))
def test_resource_boundaries_unchanged_with_reuse(field):
    configured = limits(**{field: 0})
    assert solve(limits=configured).outcome.value == "TIMEOUT"
    assert (
        solve(limits=configured).certificate
        == solve(limits=configured, reuse_preparation=False).certificate
    )


@pytest.mark.parametrize("cutoff", (2, 6, 35, 48))
def test_deadline_expiration_withholds_witness(cutoff):
    calls = 0

    def clock():
        nonlocal calls
        calls += 1
        return 10.0 if calls >= cutoff else 0.0

    result = solve(limits=limits(deadline=10.0), clock=clock)
    assert result.outcome.value == "TIMEOUT"
    assert result.witness is None
    assert ComputedWeeklySolveResultV2.model_validate(result) == result
