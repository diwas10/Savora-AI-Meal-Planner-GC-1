"""Frozen fictional comparison language and literal oracles, never clinical truth.

Fixture construction reuses native DTO factories, not decisions. Oracles below
use only declared integers, presence and explicit three-valued logic. They never
call production predicates, solvers, cost schedules, ranking or proof helpers.
"""

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from itertools import product
from math import prod
from typing import Any, Literal
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, Field, model_validator

from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.evals import synthetic_week_cases as native
from savora_ai.schemas import planned_swap as swap
from savora_ai.schemas.candidates import VersionedFact
from savora_ai.schemas.daily import (
    AssignedMeal,
    DailyAssignment,
    DailyMealOption,
    DailySlotDomain,
    DailySourceReference,
    MealSlot,
)
from savora_ai.schemas.daily_solver import DailyTrial, DailyTrialChoice
from savora_ai.schemas.knowledge import PredicateOperator, RuleReference, RuleScope
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot, KnowledgeWorkflow
from savora_ai.schemas.weekly import (
    WeeklyAssignment,
    WeeklyDayAssignment,
    WeeklySourceReference,
    WeeklyTrial,
    WeeklyTrialChoice,
    _daily_request,
)

ORACLE_VERSION = "literal-fixed-cartesian-and-swap.v1"
MAX_CARTESIAN = 256


class FrozenModel(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", allow_inf_nan=False, revalidate_instances="always"
    )


def ordered_digest(value: Any) -> str:
    """Ordered workload identity, deliberately distinct from unordered DTO hashes."""
    raw = json.dumps(
        value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    ).encode()
    return hashlib.sha256(raw).hexdigest()


class WeeklySpec(FrozenModel):
    case_id: str
    family: str
    domains: tuple[tuple[int, ...], ...]
    weights: tuple[int | None, ...] = (3, 7, 11)
    target: int = 63
    operator: Literal["EQ", "LE", "LT", "GE", "GT"] = "EQ"
    day_cap: int | None = None
    repeat_cap: int = 21
    day_unknown: bool = False
    recipe: bool | None = True
    combination: bool | None = True
    applicability: bool | None = True
    duplicate_components: bool = False
    extra_rules: int = 0
    permutation: bool = False
    timing: bool = False
    oracle_kind: Literal["EXHAUSTIVE", "CONSTRUCTED"] = "EXHAUSTIVE"

    @model_validator(mode="after")
    def closed_language(self):
        if len(self.domains) != 21 or not 1 <= len(self.weights) <= 50:
            raise ValueError("literal fixture requires 21 domains and 1..50 options")
        if any(
            len(set(d)) != len(d) or any(i < 0 or i >= len(self.weights) for i in d)
            for d in self.domains
        ):
            raise ValueError("domain references outside declared literal vocabulary")
        if not 0 <= self.repeat_cap <= 21 or not 0 <= self.extra_rules <= 8:
            raise ValueError("unsupported repeat/rule fixture size")
        if self.target < 0 or any(w is not None and w < 0 for w in self.weights):
            raise ValueError("fictional measurements are nonnegative integers or missing")
        if self.oracle_kind == "EXHAUSTIVE" and prod(map(len, self.domains)) > MAX_CARTESIAN:
            raise ValueError("literal Cartesian oracle refuses more than 256 assignments")
        return self


class SwapSpec(FrozenModel):
    case_id: str
    mode: Literal["VALIDATE", "SELECT"]
    target: int = Field(default=0, ge=0, le=20)
    values: tuple[int | None, ...] = (7,)
    lanes: tuple[Literal["PASS", "FAIL", "UNKNOWN"], ...] = ("PASS",)
    priorities: tuple[int, ...] = (0,)
    lock: Literal["NONE", "USER", "SYSTEM"] = "NONE"
    stale: Literal["NONE", "REVISION", "PERMISSION", "SOURCE"] = "NONE"
    noop: bool = False
    preparation: bool = False
    history: bool = False
    baseline_unknown: bool = False
    baseline_fail: bool = False
    canonical: bool = False
    timing: bool = False

    @model_validator(mode="after")
    def inventory(self):
        if not len(self.values) == len(self.lanes) == len(self.priorities) or len(self.values) > 50:
            raise ValueError("swap literal alternatives require matching inventories, at most 50")
        if any(p < 0 or p > 1_000_000 for p in self.priorities):
            raise ValueError("unsupported priority")
        if self.mode == "VALIDATE" and len(self.values) != 1:
            raise ValueError("singleton validation requires exactly one fixed proposal")
        return self


def weekly_specs() -> tuple[WeeklySpec, ...]:
    def case(name, family="semantic", variable=(), overrides=None, **changes):
        domains = [(0, 1) if i in variable else (0,) for i in range(21)]
        for i, choices in (overrides or {}).items():
            domains[i] = choices
        return WeeklySpec(case_id=name, family=family, domains=tuple(domains), **changes)

    result = [case("product-0", "cartesian", overrides={0: ()})]
    for power in range(9):
        # Late variables retain opposite early/late witness and MRV interactions.
        result.append(
            case(
                f"product-{2**power}",
                "cartesian",
                variable=tuple(range(21 - power, 21)),
                timing=power in (0, 3),
            )
        )
    result += [
        case("late", "ordering", variable=(0, 3, 6), target=75, timing=True),
        case("symmetric", "ordering", variable=(0, 1, 2), target=67, timing=True),
        case("day-bottleneck", "constraint", variable=(18, 19), target=67, day_cap=9, timing=True),
        case("week-bottleneck", "constraint", variable=(18, 19), target=64, timing=True),
        case("asymmetric", "ordering", overrides={0: (0, 1, 2), 3: (0, 1)}, target=71),
        case("permuted", "ordering", variable=(0, 3, 6), target=75, permutation=True),
        case("all-fail", recipe=False),
        case("unknown", day_unknown=True, timing=True),
        case("unknown-refuted", day_unknown=True, target=64),
        case("missing-fact", recipe=None),
        case("applicability-unknown", applicability=None),
        case("evidenced-na", applicability=False, target=1),
        case("missing-measurement", weights=(None, 7, 11)),
        case("zero-measurement", weights=(0, 7, 11), target=0),
        case("boundary-le", operator="LE", target=63),
        case("boundary-lt", operator="LT", target=63),
        case("boundary-ge", operator="GE", target=63),
        case("boundary-gt", operator="GT", target=63),
        case("repetition-fail", repeat_cap=20),
        case("repetition-distinct", overrides={20: (2,)}, target=71, repeat_cap=20),
        case("duplicate-components", duplicate_components=True),
        case("many-rules", extra_rules=8, timing=True),
        case(
            "fifty-fixed",
            "scaling",
            overrides={0: tuple(range(50))},
            weights=tuple(3 + 4 * i for i in range(50)),
        ),
        case("constructed-large", "scaling", variable=tuple(range(12)), oracle_kind="CONSTRUCTED"),
    ]
    return tuple(result)


def swap_specs() -> tuple[SwapSpec, ...]:
    result = [
        SwapSpec(case_id=f"target-{i:02d}", mode="VALIDATE", target=i, timing=i in (0, 20))
        for i in range(21)
    ]
    for label, changes in (
        ("reject-day-week", dict(values=(8,))),
        ("unknown-measurement", dict(values=(None,))),
        ("unknown-prerequisite", dict(lanes=("UNKNOWN",))),
        ("unknown-refuted", dict(values=(8,), lanes=("UNKNOWN",))),
        ("user-lock", dict(lock="USER")),
        ("system-lock", dict(lock="SYSTEM")),
        ("noop", dict(noop=True)),
        ("preparation", dict(preparation=True)),
        ("saved-history", dict(history=True)),
        ("baseline-unknown", dict(baseline_unknown=True)),
        ("baseline-fail", dict(baseline_fail=True)),
        ("stale-revision", dict(stale="REVISION")),
        ("stale-permission", dict(stale="PERMISSION")),
        ("stale-source", dict(stale="SOURCE")),
    ):
        result.append(SwapSpec.model_validate(dict(case_id=label, mode="VALIDATE") | changes))
    for size in (0, 1, 2, 8, 50):
        result.append(
            SwapSpec(
                case_id=f"select-size-{size}",
                mode="SELECT",
                values=(7,) * size,
                lanes=("FAIL",) * size,
                priorities=(0,) * size,
            )
        )
    for label, values, lanes, priorities in (
        ("early", (7, 6), ("PASS", "PASS"), (0, 0)),
        ("late", (8, 7), ("PASS", "PASS"), (0, 1)),
        ("priority", (6, 7), ("PASS", "PASS"), (1, 0)),
        ("unknown-before", (6, 7), ("UNKNOWN", "PASS"), (0, 0)),
        ("unknown-after", (7, 6), ("PASS", "UNKNOWN"), (0, 0)),
        ("exhaustive-unknown", (8, 7), ("UNKNOWN", "UNKNOWN"), (0, 0)),
        ("unknown-all-refuted", (8, 9), ("UNKNOWN", "UNKNOWN"), (0, 0)),
        ("eight-late", (8,) * 7 + (7,), ("PASS",) * 8, (0,) * 8),
    ):
        result.append(
            SwapSpec.model_validate(
                dict(
                    case_id="select-" + label,
                    mode="SELECT",
                    values=values,
                    lanes=lanes,
                    priorities=priorities,
                    timing=label in ("early", "late"),
                )
            )
        )
    result.append(
        SwapSpec(
            case_id="select-canonical",
            mode="SELECT",
            values=(7, 6),
            lanes=("PASS", "PASS"),
            priorities=(0, 0),
            canonical=True,
        )
    )
    result.append(
        SwapSpec(
            case_id="select-noop",
            mode="SELECT",
            values=(3,),
            lanes=("PASS",),
            priorities=(0,),
            noop=True,
        )
    )
    return tuple(result)


def compare(value: int, target: int, operator: str) -> bool:
    return {
        "EQ": value == target,
        "LE": value <= target,
        "LT": value < target,
        "GE": value >= target,
        "GT": value > target,
    }[operator]


def combine(values) -> str:
    items = tuple(values)
    return "FAIL" if "FAIL" in items else "UNKNOWN" if "UNKNOWN" in items else "PASS"


def literal_week_status(spec: WeeklySpec, choices: tuple[int, ...]) -> str:
    if len(choices) != 21 or any(i not in d for i, d in zip(choices, spec.domains, strict=True)):
        raise ValueError("literal witness is outside original domains")
    if spec.applicability is False:
        return "PASS"
    if spec.applicability is None:
        return "UNKNOWN"
    prerequisite = combine(
        (
            "UNKNOWN" if spec.recipe is None else "PASS" if spec.recipe else "FAIL",
            "UNKNOWN" if spec.combination is None else "PASS" if spec.combination else "FAIL",
        )
    )
    values = [spec.weights[i] for i in choices]
    days = []
    for day in range(7):
        items = values[3 * day : 3 * day + 3]
        numeric = "PASS"
        if spec.day_cap is not None:
            numeric = (
                "UNKNOWN"
                if None in items
                else "PASS"
                if sum(v for v in items if v is not None) <= spec.day_cap
                else "FAIL"
            )
        days.append(
            combine(
                (
                    prerequisite,
                    "UNKNOWN" if spec.day_unknown else "PASS",
                    numeric if spec.day_cap is not None else "PASS",
                )
            )
        )
    total = (
        "UNKNOWN"
        if None in values
        else "PASS"
        if compare(sum(v for v in values if v is not None), spec.target, spec.operator)
        else "FAIL"
    )
    recipes = Counter("B" if i == 2 else "A" for i in choices)
    repeated = "PASS" if max(recipes.values()) <= spec.repeat_cap else "FAIL"
    return combine((*days, total, repeated))


def weekly_oracle(spec: WeeklySpec) -> dict[str, Any]:
    size = prod(map(len, spec.domains))
    if size > MAX_CARTESIAN:
        if spec.oracle_kind != "CONSTRUCTED" or spec.case_id != "constructed-large":
            raise ValueError("oversized literal enumeration refused")
        witness = tuple(d[0] for d in spec.domains)
        if literal_week_status(spec, witness) != "PASS":
            raise ValueError("constructed witness does not establish declared truth")
        return dict(
            outcome="FEASIBLE",
            truth="CONSTRUCTED_WITNESS",
            size=size,
            first_witness=witness,
            enumerated=0,
        )
    counts = Counter()
    first = None
    for choices in product(*spec.domains):
        status = literal_week_status(spec, choices)
        counts[status] += 1
        if status == "PASS" and first is None:
            first = choices
    outcome = (
        "FEASIBLE"
        if first is not None
        else "INSUFFICIENT_DATA"
        if counts["UNKNOWN"]
        else "INFEASIBLE"
    )
    return dict(
        outcome=outcome,
        truth="EXHAUSTIVE_LITERAL",
        size=size,
        enumerated=size,
        first_witness=first,
        counts=dict(counts),
    )


def swap_oracle(spec: SwapSpec) -> dict[str, Any]:
    if spec.stale != "NONE":
        return dict(outcome="BOUNDARY_ERROR", selected=None, visits=())
    if spec.lock != "NONE":
        return dict(outcome="REJECTED", selected=None, visits=())
    if spec.noop:
        return dict(outcome="REJECTED", selected=None, visits=())
    eligible = [i for i, lane in enumerate(spec.lanes) if lane == "PASS"]
    # Literal insertion order, independent from production ranking/sort helpers.
    order = []
    for i in eligible:
        j = 0
        while j < len(order) and (spec.priorities[order[j]], order[j]) <= (spec.priorities[i], i):
            j += 1
        order.insert(j, i)
    if spec.mode == "VALIDATE":
        order = [0]
    else:
        order += [i for i, lane in enumerate(spec.lanes) if lane == "UNKNOWN"]
    visits = []
    unresolved = False
    for i in order:
        amount = spec.values[i]
        # Baseline21 of3; replacement changes exactly one term. Presence first.
        fail = spec.baseline_fail or (amount is not None and (6 + amount > 13 or 60 + amount > 67))
        unknown = spec.baseline_unknown or amount is None or spec.lanes[i] == "UNKNOWN"
        verdict = (
            "REJECTED"
            if fail or spec.lanes[i] == "FAIL"
            else "INSUFFICIENT_DATA"
            if unknown
            else "VALID"
        )
        visits.append((i, verdict))
        unresolved |= verdict == "INSUFFICIENT_DATA"
        if verdict == "VALID":
            return dict(outcome=verdict, selected=i, visits=tuple(visits))
        if spec.baseline_fail:
            return dict(outcome="REJECTED", selected=None, visits=tuple(visits))
    return dict(
        outcome="INSUFFICIENT_DATA" if unresolved else "REJECTED",
        selected=None,
        visits=tuple(visits),
    )


def rebuild(record: Any, **changes: Any) -> Any:
    body = record.model_dump(exclude={"content_digest"}) | changes
    return (
        build_knowledge_snapshot(body)
        if isinstance(record, KnowledgeBaseSnapshot)
        else type(record).build(body)
    )


def reference(record: Any, record_id: str | None = None) -> swap.SwapReference:
    return swap.SwapReference(
        record_id=record_id or record.record_id,
        version=record.version,
        content_digest=record.content_digest,
    )


@dataclass(frozen=True)
class BuiltWeekly:
    spec: WeeklySpec
    request: Any
    candidates: tuple[Any, ...]
    knowledge: Any
    context: Any
    sources: Any

    def authority(self) -> dict[str, Any]:
        return dict(
            request=self.request,
            candidates=self.candidates,
            knowledge=self.knowledge,
            context=self.context,
            sources=self.sources,
        )


def build_weekly(spec: WeeklySpec) -> BuiltWeekly:
    """Native fixture lookup patch is construction-only, never a solver patch."""
    base_spec = native.WeekCaseSpec(
        case_id=spec.case_id,
        description="Phase74 fictional",
        domains=((0,),) * 21,
        target=spec.target,
        day_cap=spec.day_cap,
        day_unknown=spec.day_unknown,
        repeat_cap=spec.repeat_cap,
        duplicate_components=spec.duplicate_components,
    )
    with patch.object(native, "case_specs", return_value=(base_spec,)):
        base = native.build_week_case(spec.case_id)
    rules = tuple(
        r.model_copy(update={"operator": PredicateOperator(spec.operator)})
        if r.rule_id == "bench-week-total"
        else r
        for r in base.knowledge.rules
    )
    rules += tuple(
        native._rule(f"extra-{i}", RuleScope.RECIPE, "synthetic_flag")
        for i in range(spec.extra_rules)
    )
    refs = tuple(RuleReference(rule_id=r.rule_id, version=r.version) for r in rules)
    cells = tuple(
        c.model_copy(
            update={
                "rule_references": tuple(
                    ref for ref, r in zip(refs, rules, strict=True) if r.scope is c.scope
                )
            }
        )
        for c in base.knowledge.check_catalogue
    )
    kb = rebuild(
        base.knowledge,
        rules=rules,
        active_rules=refs,
        check_catalogue=cells,
        applicability_descriptors=tuple(
            d.model_copy(update={"rule_references": refs})
            for d in base.knowledge.applicability_descriptors
        ),
    )
    facts = tuple(
        f.model_copy(
            update={
                "observation": f.observation.model_copy(
                    update={"value": spec.applicability, "complete": spec.applicability is not None}
                )
            }
        )
        if f.fact_id == "synthetic_context_enabled"
        else f
        for f in base.context.facts
    )
    context = rebuild(base.context, expected_kb_digest=kb.content_digest, facts=facts)
    candidates = tuple(
        rebuild(
            c,
            facts=tuple(
                f.model_copy(
                    update={
                        "observation": f.observation.model_copy(
                            update={"value": spec.recipe, "complete": spec.recipe is not None}
                        )
                    }
                )
                for f in c.facts
            ),
        )
        for c in base.candidates
    )
    role = next(e for e in kb.graph.entities if e.entity_id == "bench-role")
    options = []
    for i, weight in enumerate(spec.weights):
        candidate = candidates[1 if i == 2 else 0]
        option = native._option(2 if i == 2 else i % 2, candidate, context, role, base_spec)
        combo = rebuild(
            option.combination,
            snapshot_id=f"p74-s{i}",
            portion_configuration_id=f"p74-c{i}",
            observations=()
            if spec.combination is None
            else tuple(
                o.model_copy(
                    update={
                        "observation": o.observation.model_copy(update={"value": spec.combination})
                    }
                )
                for o in option.combination.observations
            ),
        )
        ref = option.reference.model_copy(
            update={
                "option_id": f"p74:{i:02d}",
                "snapshot_id": combo.snapshot_id,
                "portion_configuration_id": combo.portion_configuration_id,
                "combination_digest": combo.content_digest,
            }
        )
        assert option.suitability is not None
        options.append(
            DailyMealOption(
                reference=ref,
                combination=combo,
                suitability=option.suitability.model_copy(update={"option": ref}),
                measurements=tuple(
                    m.model_copy(
                        update={"option": ref, "value": weight, "complete": weight is not None}
                    )
                    for m in option.measurements
                ),
            )
        )
    sequence = tuple(reversed(options)) if spec.permutation else tuple(options)
    daily = rebuild(base.sources.daily_source, context=context, options=sequence)
    sources = rebuild(
        base.sources,
        daily_source=daily,
        expected_daily_source=DailySourceReference(
            source_id=daily.source_id, version=daily.version, content_digest=daily.content_digest
        ),
    )
    days = tuple(
        day.model_copy(
            update={
                "domains": tuple(
                    DailySlotDomain(
                        slot=slot,
                        options=tuple(options[i].reference for i in spec.domains[3 * d + j]),
                    )
                    for j, slot in enumerate(MealSlot)
                )
            }
        )
        for d, day in enumerate(base.request.days)
    )
    request = rebuild(
        base.request,
        source=sources,
        expected_source=WeeklySourceReference(
            source_id=sources.source_id,
            version=sources.version,
            content_digest=sources.content_digest,
        ),
        context_digest=context.content_digest,
        days=tuple(reversed(days)) if spec.permutation else days,
    )
    return BuiltWeekly(spec, request, candidates, kb, context, sources)


def build_swap(spec: SwapSpec) -> dict[str, Any]:
    base_spec = WeeklySpec(
        case_id="swap-base",
        family="swap",
        domains=((0,),) * 21,
        weights=(None if spec.baseline_unknown else 3, 7),
        target=67,
        operator="LE",
        day_cap=13,
        repeat_cap=20 if spec.baseline_fail else 21,
    )
    base = build_weekly(base_spec)
    request, sources, old_context = base.request, base.sources, base.context
    option = sources.daily_source.options[0]
    evidence = (native._evidence(),)
    choices = tuple(
        WeeklyTrialChoice(day=d.day, slot=slot, option=option.reference)
        for d in request.days
        for slot in MealSlot
    )
    trial = WeeklyTrial.build(
        dict(
            request_digest=request.content_digest,
            week_id=request.week_id,
            week_version=request.week_version,
            start_date=request.start_date,
            choices=choices,
        )
    )
    assigned_days = []
    for day in request.days:
        daily_request = _daily_request(request, day)
        dt = DailyTrial.build(
            dict(
                request_digest=daily_request.content_digest,
                choices=tuple(DailyTrialChoice(slot=s, option=option.reference) for s in MealSlot),
            )
        )
        da = DailyAssignment.build(
            dict(
                request_digest=daily_request.content_digest,
                day_id=day.day.day_id,
                source=sources.expected_daily_source,
                context_digest=old_context.content_digest,
                slots=tuple(AssignedMeal(slot=s, option=option.reference) for s in MealSlot),
            )
        )
        assigned_days.append(WeeklyDayAssignment(day=day.day, trial=dt, assignment=da))
    assignment = WeeklyAssignment.build(
        dict(
            request_digest=request.content_digest,
            week_id=request.week_id,
            week_version=request.week_version,
            start_date=request.start_date,
            source=request.expected_source,
            daily_source=sources.expected_daily_source,
            context_digest=old_context.content_digest,
            days=tuple(assigned_days),
        )
    )
    slots = tuple(
        swap.SavedSlotPayload(
            identity=swap.SwapSlotIdentity(day=c.day, slot=c.slot),
            source=reference(sources, sources.source_id),
            option=option,
            recipes=(base.candidates[0],),
        )
        for c in choices
    )
    target_release = swap.SyntheticTargetReference(
        target_id="p74-target", version="1", content_digest="d" * 64, evidence=evidence
    )
    history = swap.SavedPlanVerificationRecord(
        status="UNVERIFIED",
        prior_protocol=None,
        prior_result=None,
        verification_policy="synthetic-history.v1",
        evidence=evidence,
    )
    if spec.history:
        history = swap.SavedPlanVerificationRecord(
            status="VERIFIED_AT_SAVE",
            prior_protocol="computed-weekly-solve-result.v2",
            prior_result=swap.SwapReference(
                record_id="historical-only", version="1", content_digest="e" * 64
            ),
            verification_policy="fictional-history.v1",
            evidence=evidence,
        )
    snapshot = swap.SavedPlanSnapshot.build(
        dict(
            plan_id="p74-plan",
            snapshot_id="p74-saved",
            version="1",
            original_request=request,
            original_sources=sources,
            original_context=old_context,
            original_candidates=base.candidates,
            original_trial=trial,
            original_assignment=assignment,
            slots=slots,
            target=target_release,
            verification=history,
            evidence=evidence,
        )
    )
    saved_ref = swap.SavedPlanReference(
        plan_id=snapshot.plan_id,
        effective_revision=1,
        snapshot_id=snapshot.snapshot_id,
        snapshot_version=snapshot.version,
        snapshot_digest=snapshot.content_digest,
    )
    saved = swap.SavedPlanMaterial.build(dict(snapshot=snapshot, reference=saved_ref))
    context = rebuild(
        old_context,
        context_id="p74-swap",
        workflow=KnowledgeWorkflow.PLANNED_SWAP,
        facts=tuple(
            VersionedFact.model_validate(
                f.model_dump() | dict(subject_id="p74-swap", context_id="p74-swap")
            )
            if f.subject_kind.value == "CONTEXT"
            else f
            for f in old_context.facts
        ),
    )
    projected = []
    for old in sources.daily_source.options:
        combo = rebuild(
            old.combination,
            context_id=context.context_id,
            context_version=context.version,
            context_digest=context.content_digest,
        )
        ref = old.reference.model_copy(update={"combination_digest": combo.content_digest})
        projected.append(
            DailyMealOption(
                reference=ref,
                combination=combo,
                suitability=old.suitability.model_copy(update={"option": ref}),
                measurements=tuple(m.model_copy(update={"option": ref}) for m in old.measurements),
            )
        )
    alternatives = []
    for i, (value, lane) in enumerate(zip(spec.values, spec.lanes, strict=True)):
        old = projected[1]
        compact = len(spec.values) == 50
        tiny = native._evidence().model_copy(
            update={"evidence_id": "e", "source": "s", "locator": "u"}
        )
        combo = rebuild(
            old.combination,
            combination_id=f"k{i}",
            snapshot_id=f"a{i}",
            portion_configuration_id=f"c{i}",
            observations=()
            if compact
            else tuple(
                o.model_copy(update={"combination_id": f"k{i}"})
                for o in old.combination.observations
            ),
        )
        if compact:
            # Concise explicit declarations fit the unchanged ingress ceiling.
            # Known target-slot FAIL is decisive despite missing measurements.
            tiny = native._evidence().model_copy(
                update={"evidence_id": "e", "source": "s", "locator": "u"}
            )
            parts = []
            for part in combo.components:
                assert part.quantity is not None
                preparation = part.preparation.model_copy(
                    update={
                        "preparation_id": "p",
                        "basis_reference": tiny,
                        "evidence": (tiny,),
                    }
                )
                quantity = part.quantity.model_copy(
                    update={
                        "preparation_id": "p",
                        "basis_reference": tiny,
                        "portion_reference": tiny,
                        "evidence": (tiny,),
                    }
                )
                parts.append(
                    part.model_copy(
                        update={
                            "preparation": preparation,
                            "quantity": quantity,
                            "evidence": (tiny,),
                        }
                    )
                )
            combo = rebuild(combo, components=tuple(parts), evidence=(tiny,))
        if spec.preparation:
            parts = tuple(
                p.model_copy(
                    update={
                        "preparation": p.preparation.model_copy(update={"preparation_id": "other"}),
                        "quantity": p.quantity.model_copy(update={"preparation_id": "other"}),
                    }
                )
                for p in combo.components
            )
            combo = rebuild(combo, components=parts)
        ref = old.reference.model_copy(
            update={
                "option_id": f"a:{i:02d}",
                "combination_id": combo.combination_id,
                "snapshot_id": combo.snapshot_id,
                "portion_configuration_id": combo.portion_configuration_id,
                "combination_digest": combo.content_digest,
            }
        )
        alternatives.append(
            DailyMealOption(
                reference=ref,
                combination=combo,
                suitability=old.suitability.model_copy(
                    update={
                        "option": ref,
                        "slots": old.suitability.slots if lane == "PASS" else (),
                        "complete": lane != "UNKNOWN",
                        **({"evidence": (tiny,)} if compact else {}),
                    }
                ),
                measurements=()
                if compact
                else tuple(
                    m.model_copy(
                        update={
                            "option": ref,
                            "components": combo.components,
                            "value": value,
                            "complete": value is not None,
                        }
                    )
                    for m in old.measurements
                ),
            )
        )
    pool = (*projected, *alternatives)
    swap_sources = swap.PlannedSwapSourceSnapshot.build(
        dict(
            record_id="p74-source",
            version="1",
            context=context,
            candidates=base.candidates,
            options=pool,
            evidence=evidence,
        )
    )
    locks = swap.SavedPlanLockInventory.build(
        dict(
            record_id="p74-locks",
            version="1",
            revision=1,
            saved_plan=saved_ref,
            entries=()
            if spec.lock == "NONE"
            else (
                swap.SavedSlotLock(
                    slot=slots[spec.target].identity,
                    kind=swap.LockKind(spec.lock),
                    reason="Fictional lock",
                    authority=evidence[0],
                ),
            ),
            evidence=evidence,
        )
    )
    permission = swap.SwapTargetPermission.build(
        dict(
            record_id="p74-grant",
            version="1",
            saved_plan=saved_ref,
            locks=reference(locks),
            target=slots[spec.target].identity,
            context=reference(context, context.context_id),
            profile_id=context.profile_id,
            profile_version=context.profile_version,
            authority=evidence[0],
        )
    )
    bridge = swap.PlannedSwapWorkflowBridge.build(
        dict(
            record_id="p74-bridge",
            version="1",
            saved_plan=saved_ref,
            original_context=reference(old_context, old_context.context_id),
            original_source=reference(sources, sources.source_id),
            swap_context=reference(context, context.context_id),
            swap_source=reference(swap_sources),
            knowledge=reference(base.knowledge, base.knowledge.kb_id),
            target_release=target_release,
            mappings=tuple(
                swap.SwapOptionProjection(
                    original=o.reference, projected=p.reference, evidence=evidence
                )
                for o, p in zip(sources.daily_source.options, projected, strict=True)
            )
            + tuple(
                swap.SwapOptionProjection(original=None, projected=o.reference, evidence=evidence)
                for o in alternatives
            ),
            evidence=evidence,
        )
    )
    swap_request = swap.PlannedSwapRequest.build(
        dict(
            record_id="p74-request",
            version="1",
            saved_plan=saved_ref,
            locks=reference(locks),
            permission=reference(permission),
            sources=reference(swap_sources),
            bridge=reference(bridge),
            context=reference(context, context.context_id),
            knowledge=reference(base.knowledge, base.knowledge.kb_id),
            target_release=target_release,
            target=slots[spec.target].identity,
        )
    )
    authority: dict[str, Any] = dict(
        request=swap_request,
        saved_plan=saved,
        locks=locks,
        permission=permission,
        candidates=base.candidates,
        knowledge=base.knowledge,
        context=context,
        sources=swap_sources,
        bridge=bridge,
    )
    if spec.mode == "VALIDATE":
        authority["replacement"] = (
            projected[0].reference if spec.noop else alternatives[0].reference
        )
    else:
        refs = (projected[0].reference,) if spec.noop else tuple(o.reference for o in alternatives)
        domain = swap.SwapReplacementDomain.build(
            dict(
                record_id="p74-domain",
                version="1",
                request=swap_request,
                sources=swap_sources,
                options=refs,
            )
        )
        eligible = tuple(
            r for r, lane in zip(refs, spec.lanes, strict=True) if lane == "PASS" and not spec.noop
        )
        ranking = swap.SyntheticSwapRanking.build(
            dict(
                record_id="p74-rank",
                version="1",
                domain=domain,
                eligible=eligible,
                entries=tuple(
                    swap.SyntheticRankEntry(option=r, priority=p)
                    for r, p, lane in zip(refs, spec.priorities, spec.lanes, strict=True)
                    if lane == "PASS" and not spec.noop
                ),
                policy="CANONICAL_OPTION_ID"
                if spec.canonical
                else "synthetic-fixed-combination-rank.v1",
                ranker_version="canonical-option-id.v1"
                if spec.canonical
                else "synthetic-fixed-combination-rank.v1",
                evidence=evidence,
            )
        )
        authority.update(domain=domain, ranking=ranking)
    if spec.stale == "REVISION":
        authority["saved_plan"] = rebuild(
            saved, reference=saved_ref.model_copy(update={"effective_revision": 2})
        )
    elif spec.stale == "PERMISSION":
        authority["permission"] = rebuild(permission, version="stale")
    elif spec.stale == "SOURCE":
        authority["sources"] = rebuild(swap_sources, version="stale")
    return authority
