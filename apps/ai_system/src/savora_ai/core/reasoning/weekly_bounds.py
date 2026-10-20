"""Exact synthetic quantity intervals, with a separate arithmetic verification path.

No prepared measurements or assessments are accepted. Callers provide an admitted
request-local program and ORIGINAL domains. No propagation state survives a call.
Repetition and derived additional requirements deliberately have no bound here.
"""

from dataclasses import dataclass

from savora_ai.core.reasoning.week_checks import _WeekProgram
from savora_ai.schemas.knowledge import (
    MeasurementUnit,
    PredicateOperator,
    RuleDefinition,
    RuleScope,
)
from savora_ai.schemas.reasoning import ApplicabilityStatus


@dataclass(frozen=True)
class _BoundAttempt:
    rule: RuleDefinition
    indexes: tuple[int, ...]
    day_index: int | None


def _attempts(program: _WeekProgram, depth: int) -> tuple[_BoundAttempt, ...]:
    """Fixed DAY-then-WEEK, rule-ID order; no adaptive variable/value ordering."""
    day = depth // 3
    return tuple(
        _BoundAttempt(r, tuple(range(day * 3, day * 3 + 3)), day + 1)
        for r in program.manifest.day_checks
        if r.attribute == "synthetic_day_quantity_total"
    ) + tuple(
        _BoundAttempt(r, tuple(range(21)), None)
        for r in program.manifest.required_checks
        if r.attribute == "synthetic_week_quantity_total"
    )


def _cost(attempt: _BoundAttempt, domains, path: tuple[int, ...]) -> dict[str, int]:
    # One rule visit, one input occurrence scan, and one required-fact check.
    scans = sum(1 if i < len(path) else len(domains[i].options) for i in attempt.indexes)
    return dict(
        heuristic_evaluations=1 + scans + len(attempt.rule.required_facts), predicate_obligations=1
    )


def _metadata(program: _WeekProgram, attempt: _BoundAttempt) -> dict:
    source = program.day_program if attempt.day_index is not None else program
    rule = attempt.rule
    state, evidence = source.applicability[
        (rule.applicability_reference.rule_id, rule.applicability_reference.version)
    ]
    return dict(
        rule=dict(rule_id=rule.rule_id, version=rule.version),
        attribute=rule.attribute,
        operator=rule.operator,
        threshold=rule.value,
        day_index=attempt.day_index,
        applicability=state,
        applicability_evidence=evidence,
        required_observations=tuple(
            source.observations[n]
            for n in sorted(rule.required_facts)
            if n != rule.attribute and n in source.observations
        ),
    )


def _admitted(program: _WeekProgram, attempt: _BoundAttempt) -> bool:
    rule = attempt.rule
    expected = (
        (RuleScope.DAY, "synthetic_day_quantity_total")
        if attempt.day_index
        else (RuleScope.WEEK, "synthetic_week_quantity_total")
    )
    source = program.day_program if attempt.day_index else program
    if (rule.scope, rule.attribute) != expected or rule.unit is not MeasurementUnit.MG:
        return False
    if type(rule.value) is not int or rule.operator not in (
        PredicateOperator.LT,
        PredicateOperator.LE,
        PredicateOperator.GT,
        PredicateOperator.GE,
        PredicateOperator.EQ,
        PredicateOperator.NE,
    ):
        return False
    state, _ = source.applicability[
        (rule.applicability_reference.rule_id, rule.applicability_reference.version)
    ]
    if state is not ApplicabilityStatus.APPLICABLE:
        return False
    # Other derived facts cannot be substituted from context. Full derivation
    # overwrites those names; even a forged known context value supplies no bound.
    for name in rule.required_facts:
        if name == rule.attribute:
            continue
        if name.startswith(("synthetic_day_", "synthetic_week_")):
            return False
        observation = source.observations.get(name)
        if observation is None or observation.value is None or not observation.complete:
            return False
    return True


def _impossible(operator: PredicateOperator, lower: int, upper: int, threshold: int) -> bool:
    return {
        PredicateOperator.LT: lower >= threshold,
        PredicateOperator.LE: lower > threshold,
        PredicateOperator.GT: upper <= threshold,
        PredicateOperator.GE: upper < threshold,
        PredicateOperator.EQ: threshold < lower or threshold > upper,
        PredicateOperator.NE: lower == upper == threshold,
    }.get(operator, False)


def _derive_bound(
    program: _WeekProgram, domains, path: tuple[int, ...], attempt: _BoundAttempt
) -> tuple[int, int] | None:
    if not _admitted(program, attempt):
        return None
    lower = upper = 0
    for i in attempt.indexes:
        refs = (domains[i].options[path[i]],) if i < len(path) else domains[i].options
        values: list[int] = []
        for ref in refs:
            option = program.day_program.options[ref.option_id]
            if not option.measurements:
                return None
            measurement = option.measurements[0]
            if not measurement.complete or measurement.value is None:
                return None
            values.append(measurement.value)
        if not values:
            return None
        lower += min(values)
        upper += max(values)
    threshold = attempt.rule.value
    assert type(threshold) is int
    return (lower, upper) if _impossible(attempt.rule.operator, lower, upper, threshold) else None


def _check_bound(
    program: _WeekProgram, domains, path: tuple[int, ...], attempt: _BoundAttempt
) -> tuple[int, int] | None:
    """Independent interval recomputation, never calls execution's bound/predicate.

    Shared admission describes the existing full-evaluation prerequisites. The
    checker reads retained source records directly, independently of execution's
    compiled option map and any preparation cache.
    """
    if not _admitted(program, attempt):
        return None
    original = {o.reference: o for o in program.manifest.request.source.daily_source.options}
    extrema: list[tuple[int, int]] = []
    for index in attempt.indexes:
        lo: int | None = None
        hi: int | None = None
        for position, ref in enumerate(domains[index].options):
            if index < len(path) and position != path[index]:
                continue
            records = original[ref].measurements
            if len(records) != 1 or records[0].value is None or records[0].complete is not True:
                return None
            value = records[0].value
            lo = value if lo is None or value < lo else lo
            hi = value if hi is None or value > hi else hi
        if lo is None or hi is None:
            return None
        extrema.append((lo, hi))
    low = sum(pair[0] for pair in extrema)
    high = sum(pair[1] for pair in extrema)
    rule = attempt.rule
    t = rule.value
    assert type(t) is int
    # A comparison can hold somewhere in the enclosing interval precisely under
    # these necessary conditions. Discrete gaps deliberately remain open.
    possible = (
        low < t
        if rule.operator is PredicateOperator.LT
        else low <= t
        if rule.operator is PredicateOperator.LE
        else high > t
        if rule.operator is PredicateOperator.GT
        else high >= t
        if rule.operator is PredicateOperator.GE
        else low <= t <= high
        if rule.operator is PredicateOperator.EQ
        else low != t or high != t
    )
    return None if possible else (low, high)
