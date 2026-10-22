"""Full, stateless fixed-plan swap primitives. No traversal or affirmative cache.

Structural admission is bounded by the existing synthetic 1 MiB contracts. The
versioned ledger counts logical source/bridge/lock items, candidate preparations,
predicate obligations and full assessments, not Python instructions or RAM.
Each semantic macro reserves its complete executor AND replay cost first.
"""

import hashlib
import json
import math
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Self

from pydantic import ValidationError, model_validator

from savora_ai.core.reasoning.combinations import evaluate_combination
from savora_ai.core.reasoning.day_checks import _slot_status
from savora_ai.core.reasoning.evaluation import _applicability, _observation, _predicate
from savora_ai.core.reasoning.facts import _validated_fact_index
from savora_ai.core.reasoning.manifest import _descriptors_for, _mandatory_checks
from savora_ai.core.reasoning.swap_material import _ref, _SwapInputs
from savora_ai.schemas.candidates import CandidateRecipeFacts, RuleContext, _content_digest
from savora_ai.schemas.combination_evaluation import _combine_statuses
from savora_ai.schemas.daily import DailyMealOption, MealOptionReference
from savora_ai.schemas.filtering import _evidence_union
from savora_ai.schemas.knowledge import MeasurementUnit, RuleScope
from savora_ai.schemas.planned_swap import (
    SavedSlotPayload,
    SwapBoundaryError,
    SwapPlanSnapshot,
    SwapValidationLimits,
    SwapWork,
    _fixed_meal_identity,
)
from savora_ai.schemas.reasoning import (
    ApplicabilityStatus,
    FactObservation,
    RuleEvaluation,
    RuleStatus,
    RuleTrace,
    aggregate_hard_status,
)
from savora_ai.schemas.swap_proof_types import (
    SwapAggregateAssessment,
    SwapOperation,
    SwapOperationReservation,
    SwapOptionAssessment,
    SwapOutcome,
    SwapPhaseAssessment,
    SwapReservationPlan,
)

ENVELOPE_BYTES = 1_048_576


class _Inputs(_SwapInputs):
    replacement: MealOptionReference
    candidates: tuple[CandidateRecipeFacts, ...]
    limits: SwapValidationLimits

    @model_validator(mode="after")
    def full_replacement_source(self) -> Self:
        if self.candidates != self.sources.candidates:
            raise ValueError("independent candidate inventory differs from selected swap source")
        if self.replacement not in tuple(o.reference for o in self.sources.options):
            raise ValueError("replacement is not an exact independently selected source option")
        return self


def _admit(authority: dict[str, object]) -> _Inputs:
    try:
        return _Inputs.model_validate(authority)
    except ValidationError as error:
        roots = [e for e in error.errors() if e["loc"] == ()]
        if roots and "structural envelope" not in str(error):
            message = str(roots[0]["msg"])
            code = (
                "STALE_PLAN"
                if "saved-plan revision" in message
                else (
                    "STALE_LOCKS"
                    if "lock/permission" in message
                    else (
                        "INVALID_BRIDGE"
                        if any(s in message for s in ("bridge", "projection", "whitelist"))
                        else "PIN_MISMATCH"
                    )
                )
            )
            raise SwapBoundaryError(code, message) from error
        raise


class _Interrupted(RuntimeError):
    def __init__(self, reason: Literal["RESERVATION", "DEADLINE"], work: SwapWork | None = None):
        super().__init__(reason)
        self.reason: Literal["RESERVATION", "DEADLINE"] = reason
        self.work = SwapWork() if work is None else work


class _Meter:
    """Cooperative macro checkpoints, including both sides of each primitive call."""

    def __init__(self, clock: Callable[[], float], deadline: float | None, *, checker: bool):
        self.clock, self.deadline, self.checker = clock, deadline, checker
        self.previous: float | None = None
        self.counts = {name: 0 for name in SwapWork.model_fields}

    @property
    def work(self) -> SwapWork:
        return SwapWork(**self.counts)

    def checkpoint(self) -> None:
        now = self.clock()
        if type(now) not in (int, float) or not math.isfinite(now):
            raise ValueError("clock must return a finite real scalar")
        if self.previous is not None and now < self.previous:
            raise ValueError("clock must be monotonic")
        self.previous = now
        if self.deadline is not None and now >= self.deadline:
            raise _Interrupted("DEADLINE", self.work)

    def start(self, cost: SwapWork) -> None:
        self.checkpoint()
        for name, value in cost.model_dump().items():
            self.counts[name] += value
        if self.checker:
            self.counts["checker_steps"] += sum(v > 0 for v in cost.model_dump().values())


def _input_digest(inputs: _Inputs) -> str:
    # A binding only: authority is always reconstructed from independent roots.
    return _content_digest(inputs)


def _selected(inputs: _Inputs, phase: str) -> tuple[DailyMealOption, ...]:
    old = inputs.saved_plan.snapshot.slots
    if phase == "ORIGINAL":
        return tuple(s.option for s in old)
    projected = {m.original.option_id: m.projected for m in inputs.bridge.mappings if m.original}
    source = {o.reference.option_id: o for o in inputs.sources.options}
    return tuple(
        source[
            (
                inputs.replacement
                if s.identity == inputs.request.target
                else projected[s.option.reference.option_id]
            ).option_id
        ]
        for s in old
    )


def _unique(selected: tuple[DailyMealOption, ...]) -> tuple[DailyMealOption, ...]:
    # Request-local proof sharing of identical full options only, never PASS reuse
    # between phases or invocations. All 21 assignments are still assessed.
    return tuple({o.reference.option_id: o for o in selected}.values())


def _phase_context(inputs: _Inputs, phase: str) -> RuleContext:
    return inputs.saved_plan.snapshot.original_context if phase == "ORIGINAL" else inputs.context


def _option_cost(inputs: _Inputs, phase: str, option: DailyMealOption) -> SwapWork:
    context = _phase_context(inputs, phase)
    candidates = (
        inputs.saved_plan.snapshot.original_candidates if phase == "ORIGINAL" else inputs.candidates
    )
    checks = _mandatory_checks(inputs.knowledge, context)
    return SwapWork(
        source_items=len(option.combination.components),
        candidate_preparations=len(candidates),
        combination_preparations=1,
        predicate_obligations=sum(r.scope in (RuleScope.PROFILE, RuleScope.RECIPE) for r in checks)
        * len(candidates)
        + sum(r.scope is RuleScope.COMBINATION for r in checks),
    )


def _aggregate_cost(inputs: _Inputs, phase: str, scope: str) -> SwapWork:
    checks = _mandatory_checks(inputs.knowledge, _phase_context(inputs, phase))
    selected = _selected(inputs, phase)
    # DAY visits exactly three full records; WEEK also scans all component IDs
    # for canonical per-slot recipe presence. Required-fact/rule counts are bounded
    # by the accepted KB; no claim of per-instruction wall-time accounting.
    return SwapWork(
        source_items=3
        if scope == "DAY"
        else 21 + sum(len(o.combination.components) for o in selected),
        predicate_obligations=sum(r.scope.value == scope for r in checks),
        day_assessments=int(scope == "DAY"),
        week_assessments=int(scope == "WEEK"),
    )


def _binding_cost(inputs: _Inputs) -> SwapWork:
    return SwapWork(
        source_items=21
        + len(inputs.candidates)
        + len(inputs.sources.options)
        + len(inputs.saved_plan.snapshot.original_candidates),
        bridge_items=len(inputs.bridge.mappings),
        lock_comparisons=21 + len(inputs.locks.entries),
    )


@dataclass(frozen=True)
class _Schedule:
    plan: SwapReservationPlan
    execution: SwapWork
    verification: SwapWork


def _schedule(inputs: _Inputs) -> _Schedule:
    costs = [_binding_cost(inputs)]
    for phase in ("ORIGINAL", "RESULT"):
        costs.extend(_option_cost(inputs, phase, o) for o in _unique(_selected(inputs, phase)))
        costs.extend(_aggregate_cost(inputs, phase, "DAY") for _ in range(7))
        costs.append(_aggregate_cost(inputs, phase, "WEEK"))
    costs.append(SwapWork(full_validations=1))
    entries = [
        (name, value) for cost in costs for name, value in cost.model_dump().items() if value
    ]
    # Conservative, explicit first policy: reserve the entire bounded proof and
    # result envelope. Smaller byte budgets stop BEFORE semantic work. The flat
    # operation records each receive their specified 1024-byte metadata allowance;
    # the remaining payload pool is attached to the final full-validation record.
    if len(entries) > 1024:
        raise _Interrupted("RESERVATION")
    if any(value * 2 > 1_000_000 for _, value in entries):
        raise _Interrupted("RESERVATION")
    operations = []
    for index, (name, value) in enumerate(entries):
        execution = {key: 0 for key in SwapWork.model_fields}
        execution[name] = value
        verification = execution | {"checker_steps": int(value > 0)}
        reserved = {key: execution[key] + verification[key] for key in execution}
        payload = ENVELOPE_BYTES - 1024 * len(entries) if index == len(entries) - 1 else 0
        operations.append(
            SwapOperationReservation(
                operation=SwapOperation(name),
                items=value,
                payload_bytes=payload,
                execution=SwapWork(**execution),
                verification=SwapWork(**verification),
                reserved=SwapWork(**reserved),
                proof_records=1,
                proof_bytes=payload + 1024,
            )
        )
    # Capacity failures are resource outcomes; structural admission has already
    # succeeded. Do not catch unrelated model/policy errors as TIMEOUT.
    if any(
        sum(getattr(op.reserved, name) for op in operations)
        > getattr(inputs.limits.max_reserved_work, name)
        for name in SwapWork.model_fields
    ) or (
        len(operations) > inputs.limits.max_proof_records
        or inputs.limits.max_proof_bytes < ENVELOPE_BYTES
        or inputs.limits.max_result_bytes < ENVELOPE_BYTES
        or inputs.limits.max_full_validations < 1
    ):
        raise _Interrupted("RESERVATION")
    plan = SwapReservationPlan(
        limits=inputs.limits, operations=tuple(operations), result_bytes_reserved=ENVELOPE_BYTES
    )
    return _Schedule(
        plan,
        SwapWork(
            **{n: sum(getattr(o.execution, n) for o in operations) for n in SwapWork.model_fields}
        ),
        SwapWork(
            **{
                n: sum(getattr(o.verification, n) for o in operations)
                for n in SwapWork.model_fields
            }
        ),
    )


def _assess_option(
    inputs: _Inputs, phase: str, option: DailyMealOption, *, component_recipes_only: bool = False
) -> SwapOptionAssessment:
    candidates = (
        inputs.saved_plan.snapshot.original_candidates if phase == "ORIGINAL" else inputs.candidates
    )
    if component_recipes_only:
        # Compact admission already validates the entire independent inventory.
        # Unrelated recipe decisions never gate a combination (see combinations.py).
        # Retain every referenced component, including hidden ingredient coverage.
        ids = {p.recipe_snapshot.recipe_id for p in option.combination.components}
        candidates = tuple(c for c in candidates if c.recipe_id in ids)
    return SwapOptionAssessment(
        option=option.reference,
        combination=evaluate_combination(
            option.combination,
            candidates=candidates,
            knowledge=inputs.knowledge,
            context=_phase_context(inputs, phase),
            trusted_combination=option.combination,
        ),
    )


def _assess_aggregate(
    inputs: _Inputs,
    phase: str,
    scope: Literal["DAY", "WEEK"],
    day_index: int,
    selected: tuple[DailyMealOption, ...],
    statuses: tuple[RuleStatus, ...],
    options: tuple[SwapOptionAssessment, ...],
) -> SwapAggregateAssessment:
    """Typed full-source swap adapter; shares only primitive rule semantics."""
    context = _phase_context(inputs, phase)
    checks = tuple(
        r for r in _mandatory_checks(inputs.knowledge, context) if r.scope.value == scope
    )
    evidence = _evidence_union((selected, options, context, inputs.knowledge.evidence))
    complete = all(s is RuleStatus.PASS for s in statuses)
    measured = all(
        o.measurements and o.measurements[0].complete and o.measurements[0].value is not None
        for o in selected
    )
    total = (
        sum(
            o.measurements[0].value
            for o in selected
            if o.measurements and o.measurements[0].value is not None
        )
        if measured
        else None
    )
    prefix = "synthetic_" + scope.lower()
    facts = [
        FactObservation(
            fact_id=prefix + "_complete",
            value=True if complete else None,
            complete=complete,
            evidence=evidence,
        ),
        FactObservation(
            fact_id=prefix + "_quantity_total",
            value=total,
            complete=measured,
            unit=MeasurementUnit.MG if measured else None,
            evidence=evidence,
        ),
    ]
    if scope == "WEEK":
        by_id = {o.option.option_id: o.combination for o in options}
        count_complete = all(
            all(
                p.status is RuleStatus.PASS
                for p in by_id[o.reference.option_id].prerequisites
                if p.name
                in ("CANDIDATE_MEMBERSHIP", "COMPOSITION_COMPLETENESS", "SOURCE_AUTHORITY")
            )
            for o in selected
        )
        counts = Counter(
            recipe
            for o in selected
            for recipe in {p.recipe_snapshot.recipe_id for p in o.combination.components}
        )
        facts.append(
            FactObservation(
                fact_id="synthetic_week_max_recipe_slot_occurrences",
                value=max(counts.values(), default=0) if count_complete else None,
                complete=count_complete,
                unit=MeasurementUnit.DIMENSIONLESS if count_complete else None,
                evidence=evidence,
            )
        )
    indexed = _validated_fact_index(context.facts)
    observed = {name: _observation(fact) for name, fact in indexed.items()}
    observed.update({f.fact_id: f for f in facts})
    applicability = _applicability(_descriptors_for(inputs.knowledge, checks), indexed, context)
    evaluations = []
    for rule in checks:
        required = tuple(
            observed.get(name)
            or FactObservation(fact_id=name, value=None, complete=False, evidence=evidence)
            for name in sorted(rule.required_facts)
        )
        state, app_evidence = applicability[
            (rule.applicability_reference.rule_id, rule.applicability_reference.version)
        ]
        status = RuleStatus.UNKNOWN
        if state is ApplicabilityStatus.UNKNOWN:
            reason = "APPLICABILITY_UNKNOWN"
        elif state is ApplicabilityStatus.NOT_APPLICABLE:
            reason = "NOT_APPLICABLE"
        elif any(f.value is None or not f.complete for f in required):
            reason = "REQUIRED_FACT_UNKNOWN"
        else:
            status = (
                RuleStatus.PASS
                if _predicate(rule, next(f for f in required if f.fact_id == rule.attribute))
                else RuleStatus.FAIL
            )
            reason = "PREDICATE_TRUE" if status is RuleStatus.PASS else "PREDICATE_FALSE"
        evaluations.append(
            RuleEvaluation(
                rule=rule,
                applicability=state,
                applicability_evidence=app_evidence,
                facts=required,
                status=status,
                reason="synthetic-swap-aggregate.v1:" + reason,
            )
        )
    contributors = tuple(_content_digest(o) for o in selected)
    identity = hashlib.sha256(
        json.dumps(
            dict(
                inputs=_input_digest(inputs),
                phase=phase,
                scope=scope,
                day=day_index,
                contributors=contributors,
            ),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    trace = RuleTrace(
        candidate_id=identity,
        context_id=context.context_id,
        manifest_id="swap-manifest-" + identity,
        manifest_version="swap-manifest.v1:" + identity,
        required_checks=checks,
        evaluations=tuple(evaluations),
    )
    return SwapAggregateAssessment(
        scope=scope,
        day_index=day_index,
        contributors=contributors,
        observations=tuple(facts),
        trace=trace,
        status=_combine_statuses((*statuses, aggregate_hard_status(trace))),
    )


def _slot_states(
    inputs: _Inputs,
    selected: tuple[DailyMealOption, ...],
    options: tuple[SwapOptionAssessment, ...],
) -> tuple[RuleStatus, ...]:
    decisions = {o.option.option_id: o.combination.status for o in options}
    return tuple(
        _slot_status(o, s.identity.slot, decisions[o.reference.option_id])[0]
        for s, o in zip(inputs.saved_plan.snapshot.slots, selected, strict=True)
    )


def _operation(inputs: _Inputs) -> tuple[bool, str]:
    if any(e.slot == inputs.request.target for e in inputs.locks.entries):
        return False, "TARGET_LOCKED"
    old = inputs.saved_plan.snapshot.slots[inputs.request.target.canonical_index].option
    new = next(o for o in inputs.sources.options if o.reference == inputs.replacement)
    if _fixed_meal_identity(old) == _fixed_meal_identity(new):
        return False, "NO_OP"
    return True, "PERMITTED"


def _verdict(
    inputs: _Inputs, original: SwapPhaseAssessment, result: SwapPhaseAssessment
) -> tuple[SwapOutcome, str | None, str]:
    permitted, reason = _operation(inputs)
    if not permitted:
        return SwapOutcome.REJECTED, "OPERATION", reason
    if original.week.status is RuleStatus.FAIL:
        return SwapOutcome.REJECTED, "OPERATION", "BASELINE_INVALID"
    if result.week.status is RuleStatus.FAIL:
        return SwapOutcome.REJECTED, "CANDIDATE", "RESULT_FAILED"
    if original.week.status is RuleStatus.UNKNOWN or result.week.status is RuleStatus.UNKNOWN:
        return (
            SwapOutcome.INSUFFICIENT_DATA,
            "OPERATION" if original.week.status is RuleStatus.UNKNOWN else "CANDIDATE",
            "REQUIRED_FACT_UNKNOWN",
        )
    return SwapOutcome.VALID, None, "COMPLETE_PASS"


def _proposed(inputs: _Inputs) -> SwapPlanSnapshot:
    slots = list(inputs.saved_plan.snapshot.slots)
    index = inputs.request.target.canonical_index
    option = next(o for o in inputs.sources.options if o.reference == inputs.replacement)
    recipe_ids = {p.recipe_snapshot.recipe_id for p in option.combination.components}
    slots[index] = SavedSlotPayload(
        identity=inputs.request.target,
        source=_ref(inputs.sources),
        option=option,
        recipes=tuple(c for c in inputs.candidates if c.recipe_id in recipe_ids),
    )
    return SwapPlanSnapshot.build(
        dict(
            base=inputs.saved_plan,
            request=inputs.request,
            sources=inputs.sources,
            projected_replacement=inputs.replacement,
            slots=tuple(slots),
        )
    )


def _execute_phase(
    inputs: _Inputs,
    phase: Literal["ORIGINAL", "RESULT"],
    meter: _Meter,
    *,
    phase_type: type[SwapPhaseAssessment] | None = None,
    component_recipes_only: bool = False,
) -> SwapPhaseAssessment:
    phase_type = SwapPhaseAssessment if phase_type is None else phase_type
    selected = _selected(inputs, phase)
    options = []
    for option in _unique(selected):
        meter.start(_option_cost(inputs, phase, option))
        options.append(
            _assess_option(inputs, phase, option, component_recipes_only=component_recipes_only)
        )
        meter.checkpoint()
    assessments = tuple(options)
    slots = _slot_states(inputs, selected, assessments)
    days = []
    for day in range(7):
        meter.start(_aggregate_cost(inputs, phase, "DAY"))
        days.append(
            _assess_aggregate(
                inputs,
                phase,
                "DAY",
                day + 1,
                selected[day * 3 : day * 3 + 3],
                slots[day * 3 : day * 3 + 3],
                assessments,
            )
        )
        meter.checkpoint()
    meter.start(_aggregate_cost(inputs, phase, "WEEK"))
    week = _assess_aggregate(
        inputs, phase, "WEEK", 0, selected, tuple(d.status for d in days), assessments
    )
    meter.checkpoint()
    return phase_type(phase=phase, options=assessments, slots=slots, days=tuple(days), week=week)
