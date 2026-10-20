"""Independent finite-product oracle and adversarial weekly search checks.

Only synthetic input constructors are shared with the supplied-trial tests. The
oracle below uses literal integer arithmetic, never production predicates/search.
"""

import json
from copy import deepcopy
from itertools import product
from typing import Any

import pytest
from pydantic import ValidationError
from test_weekly_evaluation import amounts, case, numeric, rebind, revise, rule

from savora_ai.core.reasoning.weekly import solve_weekly_plan
from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.daily import DailyOutcome, DailySlotDomain, MealSlot
from savora_ai.schemas.knowledge import MeasurementUnit, PredicateOperator, RuleScope
from savora_ai.schemas.reasoning import RuleStatus
from savora_ai.schemas.weekly import WeeklyDayDomain, WeeklySearchLimits
from savora_ai.schemas.weekly_solver import ComputedWeeklySolveResult


def domain_case(data: dict[str, Any], variable: tuple[int, ...] = ()) -> dict[str, Any]:
    request = data["request"]
    days = tuple(
        WeeklyDayDomain(
            day=day.day,
            domains=tuple(
                DailySlotDomain(
                    slot=domain.slot,
                    options=domain.options if i * 3 + j in variable else domain.options[:1],
                )
                for j, domain in enumerate(day.domains)
            ),
        )
        for i, day in enumerate(request.days)
    )
    return data | {"request": revise(request, days=days)}


def solve(data: dict[str, Any], **kwargs: Any):
    return solve_weekly_plan(
        data["request"],
        candidates=(data["candidate"],),
        knowledge=data["kb"],
        context=data["context"],
        sources=data["source"],
        **kwargs,
    )


def test_single_option_witness():
    result = solve(domain_case(case()))
    assert result.outcome is DailyOutcome.FEASIBLE
    assert result.witness is not None
    assert len(result.witness.trial.choices) == 21
    assert result.certificate.statistics.nodes == 21
    assert result.certificate.statistics.day_evaluations == 14
    assert result.certificate.statistics.week_evaluations == 2


def quantity_case(target: int, variable: tuple[int, ...]) -> dict[str, Any]:
    return domain_case(
        case(week_rules=(numeric("weekly-total", "synthetic_week_quantity_total", target),)),
        variable,
    )


def oracle(
    variable: tuple[int, ...], target: int
) -> tuple[DailyOutcome, tuple[int, ...] | None, int]:
    """Literal finite product: each chosen configuration weighs exactly 2 or 5 mg.

    No production evaluation, pruning, aggregation, ordering or hashing is used.
    The fixed slots always weigh 2 mg. All input prerequisites/DAY checks are known.
    """
    count = 0
    for bits in product((0, 1), repeat=len(variable)):
        count += 1
        if 42 + 3 * sum(bits) == target:
            full = [0] * 21
            for index, bit in zip(variable, bits, strict=True):
                full[index] = bit
            return DailyOutcome.FEASIBLE, tuple(full), count
    return DailyOutcome.INFEASIBLE, None, count


@pytest.mark.parametrize(
    "variable,target",
    [
        ((), 42),
        ((0, 1, 2), 45),
        ((0, 1, 2), 51),
        ((0, 1, 2), 43),
        ((0, 1, 2, 3, 4, 5), 60),
        ((0, 1, 2, 3, 4, 5), 43),
    ],
)
def test_independent_cartesian_oracle(variable: tuple[int, ...], target: int):
    data = quantity_case(target, variable)
    expected, chosen, leaves = oracle(variable, target)
    result = solve(data)
    assert result.outcome is expected
    assert result.certificate.statistics.week_evaluations == 2 * leaves
    if chosen is not None:
        assert result.witness is not None
        first, second = (o.reference.option_id for o in data["daily"].options)
        assert tuple(c.option.option_id for c in result.witness.trial.choices) == tuple(
            (first, second)[i] for i in chosen
        )
        assert result.witness.facts[1].observation.value == target
    else:
        assert result.certificate.statistics.exhaustive
    t = result.timing
    stats = result.certificate.statistics
    print(
        f"BENCH variable={len(variable)} target={target} outcome={result.outcome.value} "
        f"prep={t.preparation_seconds:.4f}s search={t.search_seconds:.4f}s "
        f"verify={t.output_validation_seconds:.4f}s nodes={stats.nodes} "
        f"day={stats.day_evaluations} week={stats.week_evaluations} "
        f"options={stats.option_evaluations} batches={stats.phase3_batch_calls} "
        f"proof={stats.proof_bytes}B cache={stats.cache_entries}"
    )


def test_later_daily_alternative_is_retained():
    # D1's first complete day (all 2 mg) fails WEEK. Its next complete day wins.
    result = solve(quantity_case(45, (0, 1, 2)))
    assert result.outcome is DailyOutcome.FEASIBLE
    assert result.certificate.statistics.week_evaluations == 4
    assert result.witness is not None
    assert tuple(c.option.option_id for c in result.witness.trial.choices[:3]) == (
        "week-option-0",
        "week-option-0",
        "week-option-1",
    )


def test_repeated_recipe_multiple_configurations_and_explicit_restriction():
    data = domain_case(
        case(
            week_rules=(
                numeric(
                    "repeat", "synthetic_week_max_recipe_slot_occurrences", 20, PredicateOperator.LE
                ),
            )
        ),
        (0, 1, 2),
    )
    result = solve(data)
    assert result.outcome is DailyOutcome.INFEASIBLE
    assert result.certificate.statistics.week_evaluations == 16
    assert result.certificate.statistics.unknown_hypotheses == 0


def test_day_failure_excludes_entire_subtree():
    day = rule(
        "day-total",
        scope=RuleScope.DAY,
        attribute="synthetic_day_quantity_total",
        required_facts=("synthetic_day_quantity_total",),
        value=7,
        unit=MeasurementUnit.MG,
    )
    result = solve(domain_case(case(day_rules=(day,)), (0, 1, 2)))
    assert result.outcome is DailyOutcome.INFEASIBLE
    assert result.certificate.statistics.nodes == 14
    assert result.certificate.statistics.day_evaluations == 16
    assert result.certificate.statistics.week_evaluations == 0
    assert result.certificate.statistics.pruned_subtrees == 8
    assert all(r.kind == "DAY" and len(r.path) == 3 for r in result.certificate.records)


def test_unknown_day_refuted_by_independent_week_failure():
    day = rule(
        "day-unknown",
        scope=RuleScope.DAY,
        attribute="synthetic_day_complete",
        required_facts=("synthetic_day_complete", "synthetic_profile_flag"),
    )
    data = domain_case(
        case(
            day_rules=(day,),
            week_rules=(numeric("week-impossible", "synthetic_week_quantity_total", 43),),
        )
    )
    result = solve(data)
    assert result.outcome is DailyOutcome.INFEASIBLE
    assert result.certificate.statistics.unknown_hypotheses == 0
    assert result.certificate.statistics.week_evaluations == 2
    assert any(d.stage == "DAY" and d.status is RuleStatus.UNKNOWN for d in result.diagnostics)


@pytest.mark.parametrize("variant", ["day", "week", "suitability", "quantity", "unassigned"])
def test_surviving_unknown_is_insufficient(variant: str):
    if variant == "day":
        data = case(day_rules=())
    elif variant == "week":
        data = case(week_rules=())
    elif variant == "suitability":
        data = case(suitability=False)
    elif variant == "quantity":
        data = amounts(case(), None, complete=False)
    else:
        data = case(fixed=False)
    result = solve(domain_case(data))
    assert result.outcome is DailyOutcome.INSUFFICIENT_DATA
    assert result.certificate.statistics.exhaustive
    assert result.certificate.statistics.unknown_hypotheses == 1
    assert result.witness is None


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("max_nodes", 20, "NODE_BUDGET"),
        ("max_day_evaluations", 13, "DAY_BUDGET"),
        ("max_week_evaluations", 1, "WEEK_BUDGET"),
        ("max_option_evaluations", 1, "PREPROCESSING_BUDGET"),
        ("max_predicate_evaluations", 0, "PREDICATE_BUDGET"),
        ("max_proof_records", 2, "PROOF_RECORD_BUDGET"),
        ("max_proof_bytes", 0, "PROOF_BYTE_BUDGET"),
    ],
)
def test_each_budget_before_work(field: str, value: int, reason: str):
    result = solve(domain_case(case()), limits=WeeklySearchLimits.model_validate({field: value}))
    stats = result.certificate.statistics
    assert result.outcome is DailyOutcome.TIMEOUT
    assert stats.termination == reason
    assert not stats.exhaustive
    assert result.witness is None
    assert (
        getattr(
            stats,
            {
                "max_nodes": "nodes",
                "max_day_evaluations": "day_evaluations",
                "max_week_evaluations": "week_evaluations",
                "max_option_evaluations": "option_evaluations",
                "max_predicate_evaluations": "predicate_evaluations",
                "max_proof_records": "proof_records",
                "max_proof_bytes": "proof_bytes",
            }[field],
        )
        <= value
    )


def test_exact_budget_boundaries_and_certificate_bytes():
    data = domain_case(case())
    baseline = solve(data)
    stats = baseline.certificate.statistics
    limits = WeeklySearchLimits(
        max_nodes=21,
        max_option_evaluations=2,
        max_day_evaluations=14,
        max_week_evaluations=2,
        max_predicate_evaluations=stats.predicate_evaluations,
        max_proof_records=stats.proof_records,
        max_proof_bytes=stats.proof_bytes,
    )
    result = solve(data, limits=limits)
    assert result.outcome is DailyOutcome.FEASIBLE
    assert len(result.certificate.model_dump_json(by_alias=True).encode()) <= stats.proof_bytes
    for field in ("max_predicate_evaluations", "max_proof_records", "max_proof_bytes"):
        limited = limits.model_dump() | {field: getattr(limits, field) - 1}
        assert (
            solve(data, limits=WeeklySearchLimits.model_validate(limited)).outcome
            is DailyOutcome.TIMEOUT
        )


def test_empty_slot_domain_proves_infeasibility():
    data = domain_case(case())
    request = data["request"]
    first = request.days[0]
    empty = WeeklyDayDomain(
        day=first.day,
        domains=(DailySlotDomain(slot=MealSlot.BREAKFAST, options=()), *first.domains[1:]),
    )
    data["request"] = revise(request, days=(empty, *request.days[1:]))
    result = solve(data, limits=WeeklySearchLimits(max_nodes=0))
    assert result.outcome is DailyOutcome.INFEASIBLE
    assert result.certificate.statistics.nodes == 0
    assert result.certificate.statistics.exhaustive


def test_definite_unary_fail_is_sound_exclusion():
    data = case()
    options = tuple(
        o.model_copy(
            update={
                "suitability": o.suitability.model_copy(
                    update={"slots": (MealSlot.LUNCH, MealSlot.DINNER)}
                )
            }
        )
        for o in data["daily"].options
    )
    data = domain_case(rebind(data, options=options))
    result = solve(data)
    assert result.outcome is DailyOutcome.INFEASIBLE
    assert result.certificate.statistics.nodes == 0
    assert result.certificate.statistics.pruned_subtrees == 7


def test_no_implicit_repetition_constraint_and_all_week_obligations():
    result = solve(domain_case(case()))
    assert result.witness is not None
    assert result.witness.facts[2].observation.value == 21
    assert len({c.option.combination_id for c in result.witness.trial.choices}) == 1
    assert (
        tuple(e.rule for e in result.witness.trace.evaluations) == result.manifest.required_checks
    )
    assert all(e.status is RuleStatus.PASS for e in result.witness.trace.evaluations)


@pytest.mark.parametrize("field", ["context", "sources", "configuration"])
def test_foreign_bindings_are_errors(field: str):
    data = domain_case(case())
    if field == "context":
        with pytest.raises(ValidationError):
            solve_weekly_plan(
                data["request"],
                candidates=(data["candidate"],),
                knowledge=data["kb"],
                context=revise(data["context"], version="foreign"),
                sources=data["source"],
            )
    elif field == "sources":
        with pytest.raises(ValidationError):
            solve_weekly_plan(
                data["request"],
                candidates=(data["candidate"],),
                knowledge=data["kb"],
                context=data["context"],
                sources=revise(data["source"], version="foreign"),
            )
    else:
        first = data["request"].days[0]
        ref = first.domains[0].options[0].model_copy(update={"portion_configuration_id": "foreign"})
        changed = first.model_copy(
            update={
                "domains": (
                    first.domains[0].model_copy(update={"options": (ref,)}),
                    *first.domains[1:],
                )
            }
        )
        with pytest.raises(ValidationError):
            solve(
                data
                | {
                    "request": data["request"].model_copy(
                        update={"days": (changed, *data["request"].days[1:])}
                    )
                }
            )


def test_missing_measurement_evidence_rejected():
    data = case()
    options = data["daily"].options
    invalid = options[0].model_copy(
        update={"measurements": (options[0].measurements[0].model_copy(update={"evidence": ()}),)}
    )
    with pytest.raises(ValidationError):
        rebind(data, options=(invalid, options[1]))


def test_cache_zero_and_eviction_preserve_search():
    data = quantity_case(45, (0, 1, 2))
    for capacity in (0, 1):
        result = solve(data, limits=WeeklySearchLimits(max_cache_entries=capacity))
        assert result.outcome is DailyOutcome.FEASIBLE
        assert result.certificate.statistics.cache_entries <= capacity
        assert result.witness is not None
        assert result.witness.facts[1].observation.value == 45


def test_diagnostic_sampling_does_not_limit_proof():
    result = solve(quantity_case(43, (0, 1, 2)), limits=WeeklySearchLimits(max_diagnostics=0))
    assert result.outcome is DailyOutcome.INFEASIBLE
    assert result.diagnostics == ()
    assert sum(r.kind == "LEAF" for r in result.certificate.records) == 8


@pytest.fixture(scope="module")
def computed() -> ComputedWeeklySolveResult:
    return solve(domain_case(case()))


@pytest.mark.parametrize(
    "path,value",
    [
        (("outcome",), "INFEASIBLE"),
        (("timing", "validationDeadlineReached"), True),
        (("witness",), None),
        (("certificate", "statistics", "exhaustive"), True),
        (("certificate", "statistics", "nodes"), 20),
        (("certificate", "statistics", "dayEvaluations"), 0),
        (("certificate", "statistics", "proofBytes"), 0),
        (("certificate", "statistics", "unknownHypotheses"), 1),
        (("certificate", "records"), []),
        (("certificate", "records", 0, "evaluationDigest"), "f" * 64),
        (("certificate", "records", 0, "path"), [0, 0, 1]),
        (("certificate", "frontier"), []),
        (("certificate", "nextIndexes"), []),
        (("certificate", "preparation", 0, "decisionDigest"), "f" * 64),
        (("certificate", "preparation", 0, "slotStatuses"), ["FAIL"] * 3),
        (("witness", "facts", 1, "observation", "value"), 43),
        (("witness", "trace", "evaluations"), []),
        (("witness", "days", 0, "evaluation", "status"), "FAIL"),
    ],
)
def test_forged_computed_output(
    computed: ComputedWeeklySolveResult, path: tuple[Any, ...], value: Any
):
    body = deepcopy(computed.model_dump(mode="json", by_alias=True))
    target = body
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        validate_contract_json(ComputedWeeklySolveResult, json.dumps(body))


def test_original_json_roundtrip_and_duplicates(computed: ComputedWeeklySolveResult):
    raw = computed.model_dump_json(by_alias=True)
    assert len(raw.encode()) < 1_048_576
    assert validate_contract_json(ComputedWeeklySolveResult, raw) == computed
    for before, after in (
        ('"outcome":"FEASIBLE"', '"outcome":"FEASIBLE","outcome":"INFEASIBLE"'),
        ('"dayIndex":1', '"dayIndex":1,"day_index":1'),
    ):
        assert before in raw
        with pytest.raises(ValidationError):
            validate_contract_json(ComputedWeeklySolveResult, raw.replace(before, after, 1))


def test_hostile_containers_and_unchecked_dtos():
    class Hostile(tuple):
        def __iter__(self):
            raise AssertionError("must reject without invoking hostile iteration")

    data = domain_case(case())
    with pytest.raises(ValidationError):
        solve_weekly_plan(
            data["request"],
            candidates=Hostile((data["candidate"],)),
            knowledge=data["kb"],
            context=data["context"],
            sources=data["source"],
        )
    with pytest.raises(ValidationError):
        solve(data | {"request": data["request"].model_copy(update={"surprise": True})})


def test_counterfeit_enum_is_rejected(computed: ComputedWeeklySolveResult):
    forged = str.__new__(DailyOutcome, "FEASIBLE")
    object.__setattr__(forged, "_name_", "FEASIBLE")
    object.__setattr__(forged, "_value_", "FEASIBLE")
    with pytest.raises(ValidationError):
        ComputedWeeklySolveResult.model_validate(computed.model_copy(update={"outcome": forged}))


def test_domain_and_candidate_permutations():
    data = quantity_case(45, (0, 1, 2))
    baseline = solve(data)
    request = data["request"]
    days = tuple(
        WeeklyDayDomain(
            day=d.day,
            domains=tuple(
                DailySlotDomain(slot=x.slot, options=tuple(reversed(x.options)))
                for x in reversed(d.domains)
            ),
        )
        for d in reversed(request.days)
    )
    permuted = solve(data | {"request": revise(request, days=days)})
    assert baseline.certificate == permuted.certificate
    assert baseline.witness == permuted.witness


def test_shared_preparation_counts_do_not_scale_with_leaves(monkeypatch: pytest.MonkeyPatch):
    import savora_ai.core.reasoning.combinations as combinations
    import savora_ai.core.reasoning.week_checks as preparation
    import savora_ai.core.reasoning.weekly_search as search
    from savora_ai.core.reasoning.combinations import evaluate_combination
    from savora_ai.core.reasoning.filtering import filter_candidates

    original_combo = evaluate_combination
    original_filter = filter_candidates
    calls = {"combination": 0, "batch": 0}

    def combo(*args: Any, **kwargs: Any):
        calls["combination"] += 1
        return original_combo(*args, **kwargs)

    def batch(*args: Any, **kwargs: Any):
        calls["batch"] += 1
        return original_filter(*args, **kwargs)

    monkeypatch.setattr(preparation, "evaluate_combination", combo)
    monkeypatch.setattr(search, "filter_candidates", batch)
    monkeypatch.setattr(combinations, "filter_candidates", batch)
    data = quantity_case(43, (0, 1, 2))
    first = solve(data)
    assert calls == {"combination": 4, "batch": 6}
    assert first.certificate.statistics.option_evaluations == 4
    assert first.certificate.statistics.phase3_batch_calls == 6
    solve(data)
    assert calls == {"combination": 8, "batch": 12}


def test_large_search_is_bounded_by_nodes():
    result = solve(
        case(week_rules=(numeric("contradiction", "synthetic_week_quantity_total", 43),)),
        limits=WeeklySearchLimits(max_nodes=80),
    )
    assert result.outcome is DailyOutcome.TIMEOUT
    assert result.certificate.statistics.nodes == 80
    assert result.certificate.statistics.termination == "NODE_BUDGET"
    assert result.certificate.frontier
    print(
        f"BENCH bounded21 prep={result.timing.preparation_seconds:.4f}s "
        f"search={result.timing.search_seconds:.4f}s "
        f"verify={result.timing.output_validation_seconds:.4f}s "
        f"nodes=80 week={result.certificate.statistics.week_evaluations}"
    )


@pytest.mark.parametrize("clock", [lambda: True, lambda: float("nan"), lambda: float("inf")])
def test_bad_clock_rejected(clock: Any):
    with pytest.raises(ValueError):
        solve(domain_case(case()), clock=clock)


def test_cooperative_deadline_before_preparation():
    result = solve(domain_case(case()), limits=WeeklySearchLimits(deadline=10), clock=lambda: 10.0)
    assert result.outcome is DailyOutcome.TIMEOUT
    assert result.certificate.statistics.termination == "DEADLINE"
    assert result.certificate.statistics.option_evaluations == 0
    assert result.certificate.deadline_checkpoint == 1
    assert ComputedWeeklySolveResult.model_validate(result) == result


def test_deadline_after_verification_is_conservative():
    # Without a deadline the clock is sampled at start, prep end, search end,
    # validation start and validation end. A large jump in verification is observed.
    # Choose a clock that expires only at the output verification sample.
    class EndClock:
        def __init__(self):
            self.calls = 0

        def __call__(self):
            self.calls += 1
            return 20.0 if self.calls >= 36 else 0.0

    result = solve(domain_case(case()), limits=WeeklySearchLimits(deadline=10), clock=EndClock())
    assert result.outcome is DailyOutcome.TIMEOUT
    assert result.witness is None
    assert result.timing.validation_deadline_reached
    assert ComputedWeeklySolveResult.model_validate(result) == result


def test_candidate_order_and_unrelated_failed_recipe():
    from savora_ai.core.reasoning.kb import build_knowledge_snapshot
    from savora_ai.schemas.candidates import CandidateRecipeFacts
    from savora_ai.schemas.food_graph import FoodEntity, FoodGraphSnapshot

    data = domain_case(case())
    candidate = data["candidate"]
    node = FoodEntity.model_validate(
        candidate.graph_recipe_reference.model_dump()
        | dict(entity_id="unrelated-node", catalogue_reference="unrelated-recipe")
    )
    graph = FoodGraphSnapshot.model_validate(
        data["kb"].graph.model_dump() | dict(entities=(*data["kb"].graph.entities, node))
    )
    kb = build_knowledge_snapshot(
        data["kb"].model_dump(exclude={"content_digest"}) | dict(graph=graph)
    )
    context = revise(data["context"], expected_kb_digest=kb.content_digest)
    data = domain_case(rebind(data, context=context, kb=kb))
    other = CandidateRecipeFacts.build(
        candidate.model_dump(exclude={"content_digest"})
        | dict(
            recipe_id="unrelated-recipe",
            snapshot_id="unrelated-snapshot",
            graph_recipe_entity_id=node.entity_id,
            graph_recipe_reference=node,
            ingredient_coverage=candidate.ingredient_coverage.model_copy(
                update={"recipe_id": "unrelated-recipe", "coverage_id": "unrelated-inventory"}
            ),
            facts=tuple(
                f.model_copy(
                    update={
                        "subject_id": "unrelated-recipe",
                        "observation": f.observation.model_copy(update={"value": False}),
                    }
                )
                for f in candidate.facts
            ),
        )
    )

    def ordered(pool):
        return solve_weekly_plan(
            data["request"], candidates=pool, knowledge=kb, context=context, sources=data["source"]
        )

    first, second = ordered((candidate, other)), ordered((other, candidate))
    assert first.outcome is DailyOutcome.FEASIBLE
    assert first.certificate == second.certificate
    assert first.witness == second.witness
    assert any(d.stage == "RECIPE" and d.status is RuleStatus.FAIL for d in first.diagnostics)


def test_incomplete_proof_cannot_be_relabelled_infeasible():
    result = solve(quantity_case(43, (0, 1, 2)), limits=WeeklySearchLimits(max_nodes=25))
    assert result.outcome is DailyOutcome.TIMEOUT
    body = result.model_dump(mode="json", by_alias=True)
    body["outcome"] = "INFEASIBLE"
    body["certificate"]["statistics"].update(exhaustive=True, termination=None)
    body["certificate"]["frontier"] = []
    body["certificate"]["nextIndexes"] = []
    with pytest.raises(ValidationError):
        validate_contract_json(ComputedWeeklySolveResult, json.dumps(body))


def test_deadline_mid_search_retains_frontier():
    class Tick:
        def __init__(self):
            self.value = 0.0

        def __call__(self):
            self.value += 1.0
            return self.value

    result = solve(domain_case(case()), limits=WeeklySearchLimits(deadline=12), clock=Tick())
    assert result.outcome is DailyOutcome.TIMEOUT
    assert result.certificate.statistics.termination == "DEADLINE"
    assert 0 < result.certificate.statistics.nodes < 21
    assert result.certificate.frontier
    assert ComputedWeeklySolveResult.model_validate(result) == result


def test_backwards_clock_rejected():
    readings = iter((5.0, 4.0))
    with pytest.raises(ValueError):
        solve(domain_case(case()), clock=lambda: next(readings))
