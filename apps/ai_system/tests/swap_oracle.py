"""Fictional input construction and literal oracle, independent of swap execution.

Only DTO fixture construction is reused. Arithmetic, occurrence counting and
expected truth below do not call any production evaluator, digest or predicate.
"""

from typing import Any, TypedDict
from unittest.mock import patch

from test_planned_swap_contracts import foundation_case, projected_option, rebuild, reference
from test_swap_proof_contracts import limits
from test_weekly_contracts import evidence, packet, rule
from test_weekly_evaluation import rebind
from test_workflow_policy import V2, with_registered_extension

from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.schemas import planned_swap as s
from savora_ai.schemas.daily import DailyMealOption
from savora_ai.schemas.knowledge import MeasurementUnit, PredicateOperator, RuleScope


def required[T](value: T | None) -> T:
    assert value is not None
    return value


def literal_fixed_plan(values, recipes):
    days = []
    for day in range(7):
        subtotal = 0
        for slot in range(day * 3, day * 3 + 3):
            if values[slot] is None:
                subtotal = None
                break
            subtotal += values[slot]
        days.append(subtotal)
    total = None if None in values else sum(values)
    counts = {}
    for meal in recipes:
        distinct = []
        for recipe in meal:
            if recipe not in distinct:
                distinct.append(recipe)
        for recipe in distinct:
            counts[recipe] = counts.get(recipe, 0) + 1
    return days, total, max(counts.values(), default=0)


def repin(case: dict[str, Any], **changes: Any) -> dict[str, Any]:
    c = case | changes
    saved, sources = c["saved_plan"], c["sources"]
    locks = rebuild(c["locks"], saved_plan=saved.reference)
    permission = rebuild(c["permission"], saved_plan=saved.reference, locks=reference(locks))
    bridge = rebuild(
        c["bridge"],
        saved_plan=saved.reference,
        swap_source=reference(sources),
        swap_context=reference(c["context"], c["context"].context_id),
    )
    request = rebuild(
        c["request"],
        saved_plan=saved.reference,
        locks=reference(locks),
        permission=reference(permission),
        sources=reference(sources),
        bridge=reference(bridge),
    )
    return c | dict(locks=locks, permission=permission, bridge=bridge, request=request)


def at_target(case, index):
    target = case["saved_plan"].snapshot.slots[index].identity
    permission = rebuild(case["permission"], target=target)
    request = rebuild(case["request"], target=target, permission=reference(permission))
    return case | dict(permission=permission, request=request)


def make_case(
    *,
    recipe=True,
    measurements=(2, 5),
    day_limit=9,
    week_limit=45,
    repetition_limit=21,
    enabled=True,
    history=False,
    context_bound=False,
    copies=1,
    swap_only=False,
    preparation=False,
    opaque_ids=False,
    incomplete=False,
):
    checks = (
        rule(
            "recipe",
            scope=RuleScope.RECIPE,
            attribute="synthetic_flag",
            required_facts=("synthetic_flag",),
        ),
        rule(
            "combination",
            scope=RuleScope.COMBINATION,
            attribute="synthetic_combination_roles_compatible",
            required_facts=("synthetic_combination_roles_compatible",),
        ),
        rule(
            "day-complete",
            scope=RuleScope.DAY,
            attribute="synthetic_day_complete",
            required_facts=("synthetic_day_complete",),
        ),
        rule(
            "day-amount",
            scope=RuleScope.DAY,
            attribute="synthetic_day_quantity_total",
            required_facts=("synthetic_day_quantity_total",),
            operator=PredicateOperator.LE,
            value=day_limit,
            unit=MeasurementUnit.MG,
        ),
        rule("week-complete"),
        rule(
            "week-amount",
            attribute="synthetic_week_quantity_total",
            required_facts=("synthetic_week_quantity_total",),
            operator=PredicateOperator.LE,
            value=max(45, week_limit) if swap_only else week_limit,
            unit=MeasurementUnit.MG,
        ),
        rule(
            "week-repetition",
            attribute="synthetic_week_max_recipe_slot_occurrences",
            required_facts=("synthetic_week_max_recipe_slot_occurrences",),
            operator=PredicateOperator.LE,
            value=repetition_limit,
            unit=MeasurementUnit.DIMENSIONLESS,
        ),
    )
    data = packet(checks=checks, copies=copies)
    if swap_only:
        kb = build_knowledge_snapshot(with_registered_extension(data["kb"]))
        context = rebuild(
            data["context"],
            expected_kb_digest=kb.content_digest,
            expected_kb_version=kb.version,
            workflow_policy_version=V2,
        )
        options = []
        for old in data["daily"].options:
            combo = rebuild(old.combination, kb_version=kb.version)
            ref = old.reference.model_copy(update={"combination_digest": combo.content_digest})
            options.append(
                DailyMealOption(
                    reference=ref,
                    combination=combo,
                    suitability=required(old.suitability).model_copy(update={"option": ref}),
                    measurements=tuple(
                        m.model_copy(update={"option": ref}) for m in old.measurements
                    ),
                )
            )
        data = rebind(data, kb=kb, context=context, options=tuple(options))
    candidate = data["candidate"]
    if recipe is not True:
        candidate = rebuild(
            candidate,
            facts=()
            if recipe is None
            else tuple(
                f.model_copy(
                    update={"observation": f.observation.model_copy(update={"value": False})}
                )
                for f in candidate.facts
            ),
        )
    context = data["context"]
    if enabled is not True:
        context = rebuild(
            context,
            facts=tuple(
                f.model_copy(
                    update={
                        "observation": f.observation.model_copy(
                            update={"value": enabled, "complete": enabled is not None}
                        )
                    }
                )
                for f in context.facts
            ),
        )
    options = []
    for index, old in enumerate(data["daily"].options):
        option = projected_option(old, context, candidate)
        if preparation and index == 1:
            components = tuple(
                p.model_copy(
                    update={
                        "preparation": p.preparation.model_copy(
                            update={"preparation_id": "alternate-preparation"}
                        ),
                        "quantity": required(p.quantity).model_copy(
                            update={"preparation_id": "alternate-preparation"}
                        ),
                    }
                )
                for p in option.combination.components
            )
            combo = rebuild(option.combination, components=components)
            ref = option.reference.model_copy(update={"combination_digest": combo.content_digest})
            option = DailyMealOption(
                reference=ref,
                combination=combo,
                suitability=required(option.suitability).model_copy(update={"option": ref}),
                measurements=tuple(
                    m.model_copy(update={"option": ref, "components": components})
                    for m in option.measurements
                ),
            )
        value = measurements[index]
        option = DailyMealOption.model_validate(
            option.model_dump()
            | {
                "measurements": tuple(
                    m.model_copy(
                        update={"value": value, "complete": value is not None and not incomplete}
                    )
                    for m in option.measurements
                )
            }
        )
        if opaque_ids:
            ref = option.reference.model_copy(
                update={
                    "option_id": option.combination.combination_id + ":" + ("SMALL", "LARGE")[index]
                }
            )
            option = DailyMealOption(
                reference=ref,
                combination=option.combination,
                suitability=required(option.suitability).model_copy(update={"option": ref}),
                measurements=tuple(
                    m.model_copy(update={"option": ref}) for m in option.measurements
                ),
            )
        options.append(option)
    if opaque_ids:
        renamed = {
            old.reference.option_id: new.reference
            for old, new in zip(data["daily"].options, options, strict=True)
        }
        # The existing independent rebind helper looks up by external option ID.
        # Rename its domain references too; rebind validates the entire new source
        # and request together, rather than parsing a preset string for facts.
        request = data["request"].model_copy(
            update={
                "days": tuple(
                    day.model_copy(
                        update={
                            "domains": tuple(
                                domain.model_copy(
                                    update={
                                        "options": tuple(
                                            renamed[ref.option_id] for ref in domain.options
                                        )
                                    }
                                )
                                for domain in day.domains
                            )
                        }
                    )
                    for day in data["request"].days
                )
            }
        )
        data = data | dict(request=request)
    data = rebind(data | dict(candidate=candidate), context=context, options=tuple(options))
    with patch("test_planned_swap_contracts.packet", return_value=data):
        c = foundation_case(context_bound=context_bound)
    if history:
        saved = c["saved_plan"]
        stamp = s.SavedPlanVerificationRecord(
            status="VERIFIED_AT_SAVE",
            prior_protocol="computed-weekly-solve-result.v2",
            prior_result=s.SwapReference(
                record_id="historical-claim", version="1", content_digest="a" * 64
            ),
            verification_policy="fictional-history.v1",
            evidence=(evidence(),),
        )
        snapshot = rebuild(saved.snapshot, verification=stamp)
        saved = rebuild(
            saved,
            snapshot=snapshot,
            reference=saved.reference.model_copy(
                update={"snapshot_digest": snapshot.content_digest}
            ),
        )
        c = repin(c, saved_plan=saved)
    return c


def arguments(case, *, capacity=None, replacement=None):
    return case | dict(
        replacement=replacement or case["sources"].options[1].reference,
        candidates=case["sources"].candidates,
        limits=capacity or limits(),
    )


def replacement_case(values=(5,), lanes=None, *, compact=False, **case_options):
    """Independent declared FIXED catalogue; no runtime selector/generator used.

    Configuration/preparation facts are supplied explicitly by this test fixture.
    FAIL/UNKNOWN lanes use complete/incomplete target-slot declarations.
    """
    c = make_case(**case_options)
    old = c["sources"].options[1]
    alternatives = []
    tiny = evidence().model_copy(update={"evidence_id": "e", "source": "s", "locator": "u"})
    for i, value in enumerate(values):
        config = f"c{i}" if compact else f"fixed-preset-{i:02d}"
        combo = rebuild(
            old.combination,
            combination_id=f"literal-{i:02d}",
            snapshot_id=f"fixed-snapshot-{i:02d}",
            portion_configuration_id=config,
            observations=tuple(
                o.model_copy(
                    update={
                        "portion_configuration_id": config,
                        "combination_id": f"literal-{i:02d}",
                    }
                )
                if o.portion_configuration_id is not None
                else o.model_copy(update={"combination_id": f"literal-{i:02d}"})
                for o in old.combination.observations
            ),
        )
        if compact:
            # Separate concise declarations keep all 50 alternatives within the
            # unchanged ingress envelope. A known slot FAIL remains decisive even
            # with missing combination observations; nothing is promoted to PASS.
            tiny = evidence().model_copy(update={"evidence_id": "e", "source": "s", "locator": "u"})
            parts = []
            for part in combo.components:
                prep = part.preparation.model_copy(
                    update={"preparation_id": "p", "basis_reference": tiny, "evidence": (tiny,)}
                )
                quantity = required(part.quantity).model_copy(
                    update={
                        "preparation_id": "p",
                        "basis_reference": tiny,
                        "portion_reference": tiny,
                        "evidence": (tiny,),
                    }
                )
                parts.append(
                    part.model_copy(
                        update={"preparation": prep, "quantity": quantity, "evidence": (tiny,)}
                    )
                )
            combo = rebuild(
                combo,
                combination_id=f"k{i}",
                snapshot_id=f"s{i}",
                components=tuple(parts),
                observations=(),
                evidence=(tiny,),
            )
        ref = old.reference.model_copy(
            update={
                "option_id": f"o{i:02d}" if compact else f"opaque:{i:02d}",
                "combination_id": combo.combination_id,
                "snapshot_id": combo.snapshot_id,
                "combination_digest": combo.content_digest,
                "portion_configuration_id": config,
            }
        )
        lane = "PASS" if lanes is None else lanes[i]
        suitability = required(old.suitability).model_copy(
            update={
                "option": ref,
                "slots": old.suitability.slots if lane == "PASS" else (),
                "complete": lane != "UNKNOWN",
            }
        )
        if compact:
            suitability = suitability.model_copy(update={"evidence": (tiny,)})
        alternatives.append(
            DailyMealOption(
                reference=ref,
                combination=combo,
                suitability=suitability,
                measurements=()
                if compact
                else tuple(
                    m.model_copy(
                        update={
                            "option": ref,
                            "value": value,
                            "complete": value is not None,
                        }
                    )
                    for m in old.measurements
                ),
            )
        )
    sources = rebuild(c["sources"], options=(*c["sources"].options, *alternatives))
    bridge = rebuild(
        c["bridge"],
        mappings=(
            *c["bridge"].mappings,
            *(
                s.SwapOptionProjection(original=None, projected=o.reference, evidence=(evidence(),))
                for o in alternatives
            ),
        ),
    )
    return repin(c, sources=sources, bridge=bridge), tuple(o.reference for o in alternatives)


def literal_selection(values, lanes, priorities, *, day_limit=9, week_limit=45):
    """Enumerate a fixed20 plus each declared alternative using integer truth.

    No production ordering, predicates, cost helpers or digest functions as oracle.
    Original slots each have value2 and the same recipe, with no restrictive repeat cap.
    """
    eligible = [i for i, lane in enumerate(lanes) if lane == "PASS"]
    # Deliberate literal insertion ordering rather than the production sort helper.
    order = []
    for i in eligible:
        at = 0
        while at < len(order) and (priorities[order[at]], order[at]) <= (priorities[i], i):
            at += 1
        order.insert(at, i)
    unknown = [i for i, lane in enumerate(lanes) if lane == "UNKNOWN"]
    visits = []
    unresolved = False
    for i in order + unknown:
        vector = [2] * 21
        vector[0] = values[i]
        days, total, _ = literal_fixed_plan(vector, [("fixture-recipe",)] * 21)
        known_fail = any(d is not None and d > day_limit for d in days)
        known_fail |= total is not None and total > week_limit
        if known_fail:
            verdict = "REJECTED"
        elif lanes[i] == "UNKNOWN" or total is None:
            verdict = "INSUFFICIENT_DATA"
            unresolved = True
        else:
            verdict = "VALID"
        visits.append((i, verdict))
        if verdict == "VALID":
            return "VALID", i, visits
    return "INSUFFICIENT_DATA" if unresolved else "REJECTED", None, visits


def literal_selection_cost(case, options, eligible_count, visited, final=None) -> dict[str, Any]:
    """B2 source-count oracle independent of production scheduling/ledger code."""
    names = tuple(s.SwapWork.model_fields)
    execution = dict.fromkeys(names, 0)
    verification = dict.fromkeys(names, 0)
    records = calls = 0

    def regular(**cost):
        nonlocal records
        for n, count in cost.items():
            execution[n] += count
            verification[n] += count
        verification["checker_steps"] += 1
        records += 1

    regular(
        source_items=23
        + len(case["sources"].candidates)
        + len(case["sources"].options)
        + len(case["saved_plan"].snapshot.original_candidates),
        bridge_items=len(case["bridge"].mappings),
        lock_comparisons=21 + len(case["locks"].entries),
    )
    active = {(r.rule_id, r.version) for r in case["knowledge"].active_rules}
    rules = [
        r
        for r in case["knowledge"].rules
        if (r.rule_id, r.version) in active and r.severity.value == "ABSOLUTE"
    ]
    for ref in options:
        option = next(o for o in case["sources"].options if o.reference == ref)
        count = len(case["sources"].candidates)
        regular(
            source_items=len(option.combination.components),
            candidate_preparations=count,
            combination_preparations=1,
            domain_visits=1,
            predicate_obligations=count * sum(r.scope.value in ("RECIPE", "PROFILE") for r in rules)
            + sum(r.scope.value == "COMBINATION" for r in rules),
        )
    regular(ordering_items=eligible_count)
    for ref in (*visited, *((final,) if final is not None else ())):
        inner = literal_swap_cost(case, ref)
        for n in names:
            execution[n] += inner["execution"][n] + inner["verification"][n]
            verification[n] += inner["verification"][n]
        verification["checker_steps"] += 1
        records += 1 + inner["records"]
        calls += 1
    regular(source_items=1)
    return dict(
        execution=execution,
        verification=verification,
        reserved={n: execution[n] + verification[n] for n in names},
        records=records,
        calls=calls,
    )


def different_saved_plan(case, *, index=20, revision=1):
    """Choose a genuinely different original meal; preserve superficially equal IDs."""
    saved = case["saved_plan"]
    snap = saved.snapshot
    option = snap.original_sources.daily_source.options[1]
    choices = list(snap.original_trial.choices)
    choices[index] = choices[index].model_copy(update={"option": option.reference})
    trial = rebuild(snap.original_trial, choices=tuple(choices))
    days = list(snap.original_assignment.days)
    day = days[index // 3]
    daily_choices = list(day.trial.choices)
    daily_choices[index % 3] = daily_choices[index % 3].model_copy(
        update={"option": option.reference}
    )
    assigned = list(day.assignment.slots)
    assigned[index % 3] = assigned[index % 3].model_copy(update={"option": option.reference})
    days[index // 3] = day.model_copy(
        update={
            "trial": rebuild(day.trial, choices=tuple(daily_choices)),
            "assignment": rebuild(day.assignment, slots=tuple(assigned)),
        }
    )
    assignment = rebuild(snap.original_assignment, days=tuple(days))
    slots = list(snap.slots)
    slots[index] = slots[index].model_copy(update={"option": option})
    snapshot = rebuild(
        snap, original_trial=trial, original_assignment=assignment, slots=tuple(slots)
    )
    reference = saved.reference.model_copy(
        update={"snapshot_digest": snapshot.content_digest, "effective_revision": revision}
    )
    return repin(case, saved_plan=rebuild(saved, snapshot=snapshot, reference=reference))


class LiteralSwapCosts(TypedDict):
    execution: dict[str, int]
    verification: dict[str, int]
    reserved: dict[str, int]
    records: int
    proof_bytes: int
    result_bytes: int


def literal_swap_cost(case, replacement=None) -> LiteralSwapCosts:
    """Separate C10 oracle: no certificate, production selector, meter or schedule.

    Count full source records and fixed 21/7/1 obligations. The only workflow
    exception is the exact independently approved synthetic registration.
    """
    names = (
        "source_items",
        "bridge_items",
        "lock_comparisons",
        "candidate_preparations",
        "combination_preparations",
        "predicate_obligations",
        "day_assessments",
        "week_assessments",
        "domain_visits",
        "ordering_items",
        "full_validations",
        "checker_steps",
    )
    execution: dict[str, int] = dict.fromkeys(names, 0)
    records = 0

    def charge(**counts):
        nonlocal records
        for name, count in counts.items():
            execution[name] += count
            records += int(count > 0)

    original = case["saved_plan"].snapshot
    sources = case["sources"]
    replacement = replacement or sources.options[1].reference
    charge(
        source_items=21
        + len(original.original_candidates)
        + len(sources.candidates)
        + len(sources.options),
        bridge_items=len(case["bridge"].mappings),
        lock_comparisons=21 + len(case["locks"].entries),
    )
    active = {(r.rule_id, r.version) for r in case["knowledge"].active_rules}
    rules = [
        r
        for r in case["knowledge"].rules
        if (r.rule_id, r.version) in active and r.severity.value == "ABSOLUTE"
    ]
    for phase in ("ORIGINAL", "RESULT"):
        chosen = []
        for slot in original.slots:
            if phase == "ORIGINAL":
                chosen.append(slot.option)
            else:
                reference = (
                    replacement
                    if slot.identity == case["request"].target
                    else next(
                        m.projected
                        for m in case["bridge"].mappings
                        if m.original == slot.option.reference
                    )
                )
                chosen.append(next(o for o in sources.options if o.reference == reference))
        selected_rules = [
            r
            for r in rules
            if not (
                case["knowledge"].workflow_policy_version == V2
                and phase == "ORIGINAL"
                and (r.rule_id, r.version) == ("synthetic-swap-week-quantity-cap", "1")
            )
        ]
        unique = []
        for option in chosen:
            if option not in unique:
                unique.append(option)
        candidate_count = len(
            original.original_candidates if phase == "ORIGINAL" else sources.candidates
        )
        for option in unique:
            charge(
                source_items=len(option.combination.components),
                candidate_preparations=candidate_count,
                combination_preparations=1,
                predicate_obligations=candidate_count
                * sum(r.scope.value in ("PROFILE", "RECIPE") for r in selected_rules)
                + sum(r.scope.value == "COMBINATION" for r in selected_rules),
            )
        for _ in range(7):
            charge(
                source_items=3,
                day_assessments=1,
                predicate_obligations=sum(r.scope.value == "DAY" for r in selected_rules),
            )
        charge(
            source_items=21 + sum(len(o.combination.components) for o in chosen),
            week_assessments=1,
            predicate_obligations=sum(r.scope.value == "WEEK" for r in selected_rules),
        )
    charge(full_validations=1)
    verification = execution | {"checker_steps": records}
    return LiteralSwapCosts(
        execution=execution,
        verification=verification,
        reserved={n: execution[n] + verification[n] for n in names},
        records=records,
        proof_bytes=1_048_576,
        result_bytes=1_048_576,
    )
