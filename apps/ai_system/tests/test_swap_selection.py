"""B2 literal-domain, replay and boundary tests on fictional fixed alternatives."""

from functools import lru_cache
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from swap_oracle import (
    different_saved_plan,
    literal_selection,
    literal_selection_cost,
    make_case,
    repin,
    replacement_case,
)
from test_planned_swap_contracts import rebuild
from test_swap_proof_contracts import limits
from test_weekly_contracts import evidence

from savora_ai.core.reasoning.planned_swap import select_swap_replacement, verify_swap_selection
from savora_ai.schemas import planned_swap as s
from savora_ai.schemas import swap_proof as p


def selection(
    case=None, *, options=None, eligible=None, priorities=None, canonical=False, capacity=None
) -> dict[str, Any]:
    c = make_case() if case is None else case
    options = (c["sources"].options[1].reference,) if options is None else options
    eligible = options if eligible is None else eligible
    domain = s.SwapReplacementDomain.build(
        dict(
            record_id="selection-domain",
            version="1",
            request=c["request"],
            sources=c["sources"],
            options=options,
        )
    )
    ranking = s.SyntheticSwapRanking.build(
        dict(
            record_id="selection-ranking",
            version="1",
            domain=domain,
            eligible=eligible,
            entries=tuple(
                s.SyntheticRankEntry(option=r, priority=0 if priorities is None else priorities[i])
                for i, r in enumerate(eligible)
            ),
            policy="CANONICAL_OPTION_ID" if canonical else "synthetic-fixed-combination-rank.v1",
            ranker_version="canonical-option-id.v1"
            if canonical
            else "synthetic-fixed-combination-rank.v1",
            evidence=(evidence("selection"),),
        )
    )
    return c | dict(
        domain=domain,
        ranking=ranking,
        candidates=c["sources"].candidates,
        limits=limits(selection=True) if capacity is None else capacity,
    )


@lru_cache
def valid_case():
    a = selection()
    return a, select_swap_replacement(**a, clock=lambda: 0.0)


def test_first_valid_and_independent_replay():
    a, result = valid_case()
    assert result.outcome.value == "VALID"
    assert result.selected == a["domain"].options[0]
    assert not result.exhaustive
    assert verify_swap_selection(result, **a, clock=lambda: 0.0).accepted
    original = a["saved_plan"].snapshot.slots
    assert result.resulting_plan is not None
    assert result.resulting_plan.slots[1:] == original[1:]


@pytest.mark.parametrize("size", [0, 1, 2, 8, 50])
def test_complete_domain_exclusions(size):
    c, refs = replacement_case((5,) * size, ("FAIL",) * size, compact=size == 50)
    a = selection(c, options=refs, eligible=())
    result = select_swap_replacement(**a, clock=lambda: 0.0)
    assert result.outcome.value == "REJECTED" and result.failure_scope == "DOMAIN"
    assert result.exhaustive and result.verification_complete
    assert result.reason == ("EMPTY_DOMAIN" if size == 0 else "ALL_EXCLUDED")
    cert = result.certificate
    assert cert is not None and cert.original_options == refs
    assert len(cert.dispositions) == size
    assert not cert.visits and not cert.unvisited
    assert all(d.disposition == "HARD_FAIL" for d in cert.dispositions)
    expected = literal_selection_cost(c, refs, 0, ())
    assert result.actual_execution.model_dump() == expected["execution"]
    assert result.actual_verification.model_dump() == expected["verification"]


@pytest.mark.parametrize(
    "values,lanes,priorities",
    [
        ((5, 4), ("PASS", "PASS"), (0, 0)),
        ((7, 4), ("PASS", "PASS"), (0, 1)),
        ((4, 5), ("UNKNOWN", "PASS"), (0, 0)),
        ((5, 4), ("PASS", "UNKNOWN"), (0, 0)),
        ((7, 5), ("UNKNOWN", "UNKNOWN"), (0, 0)),
        ((7, 8), ("UNKNOWN", "UNKNOWN"), (0, 0)),
        ((None,), ("PASS",), (0,)),
        ((7,), ("PASS",), (0,)),
        ((5,), ("UNKNOWN",), (0,)),
        (
            (8, 7, 6, 5, 4, 3, 2, 1),
            ("FAIL", "FAIL", "PASS", "PASS", "PASS", "PASS", "PASS", "PASS"),
            (0,) * 8,
        ),
        ((4, 5), ("PASS", "PASS"), (1_000_000, 0)),
    ],
)
def test_literal_fixed_plan_domain_oracle(values, lanes, priorities):
    c, refs = replacement_case(values, lanes)
    ids = [i for i, lane in enumerate(lanes) if lane == "PASS"]
    a = selection(
        c,
        options=refs,
        eligible=tuple(refs[i] for i in ids),
        priorities=tuple(priorities[i] for i in ids),
    )
    result = select_swap_replacement(**a, clock=lambda: 0.0)
    expected, selected, visits = literal_selection(values, lanes, priorities)
    assert result.outcome.value == expected
    assert result.selected == (None if selected is None else refs[selected])
    cert = result.certificate
    assert cert is not None
    assert [(refs.index(v.option), v.outcome.value) for v in cert.visits] == visits
    assert cert.unvisited == tuple(
        r
        for r in (*cert.eligible_order, *cert.unknown_order)
        if r not in tuple(v.option for v in cert.visits)
    )
    costs = literal_selection_cost(
        c,
        refs,
        len(ids),
        tuple(refs[i] for i, _ in visits),
        None if selected is None else refs[selected],
    )
    assert result.actual_execution.model_dump() == costs["execution"]
    assert result.actual_verification.model_dump() == costs["verification"]
    assert sum(r.proof_records for r in cert.reservations) == costs["records"]
    assert sum(r.validation_calls for r in cert.reservations) == costs["calls"]
    assert result.exhaustive == (expected != "VALID")


def test_noop_original_target_is_accounted():
    c = make_case()
    ref = c["sources"].options[0].reference
    a = selection(c, options=(ref,), eligible=())
    result = select_swap_replacement(**a, clock=lambda: 0.0)
    assert result.outcome.value == "REJECTED" and result.exhaustive
    assert result.certificate is not None
    assert result.certificate.dispositions[0].disposition == "NO_OP"


@pytest.mark.parametrize("lock_type", ["USER", "SYSTEM"])
def test_lock_denial(lock_type):
    c = make_case()
    entry = s.SavedSlotLock(
        slot=c["request"].target,
        kind=s.LockKind(lock_type),
        reason="Explicit lock",
        authority=evidence(),
    )
    c = repin(c, locks=rebuild(c["locks"], entries=(entry,)))
    a = selection(c)
    result = select_swap_replacement(**a, clock=lambda: 0.0)
    assert result.outcome.value == "REJECTED" and result.reason == "TARGET_LOCKED"
    assert result.failure_scope == "OPERATION" and not result.exhaustive
    assert result.certificate is not None
    assert not result.certificate.visits


@pytest.mark.parametrize(
    "field",
    [
        "max_full_validations",
        "max_domain_visits",
        "max_proof_records",
        "max_proof_bytes",
        "max_result_bytes",
    ],
)
def test_zero_capacity_withholds_plan(field):
    a = selection(capacity=limits(selection=True, **{field: 0}))
    result = select_swap_replacement(**a, clock=lambda: 0.0)
    assert result.outcome.value == "TIMEOUT" and result.reason == "RESERVATION"
    assert result.selected is result.resulting_plan is result.certificate is None
    assert not result.verification_complete


@pytest.mark.parametrize("field", list(s.SwapWork.model_fields))
def test_work_one_short_versus_separate_oracle(field):
    a = selection()
    c = literal_selection_cost(
        a, a["domain"].options, 1, a["domain"].options, a["domain"].options[0]
    )
    amount = c["reserved"][field]
    if not amount:
        pytest.skip("zero-cost dimension has no one-short nonnegative budget")
    cap = s.SwapWork(**(c["reserved"] | {field: amount - 1}))
    a["limits"] = limits(selection=True, max_reserved_work=cap)
    result = select_swap_replacement(**a, clock=lambda: 0.0)
    assert result.outcome.value == "TIMEOUT" and result.reason == "RESERVATION"
    assert result.resulting_plan is None


def test_exact_oracle_capacity_and_final_invocation_reserve():
    a = selection()
    cost = literal_selection_cost(
        a, a["domain"].options, 1, a["domain"].options, a["domain"].options[0]
    )
    a["limits"] = limits(
        selection=True,
        max_reserved_work=s.SwapWork(**cost["reserved"]),
        max_proof_records=cost["records"],
        max_full_validations=2,
        max_domain_visits=1,
    )
    result = select_swap_replacement(**a, clock=lambda: 0.0)
    assert result.outcome.value == "VALID"
    with patch(
        "savora_ai.core.reasoning.swap_selection.validate_swap",
        side_effect=AssertionError("no unreserved call"),
    ):
        a["limits"] = a["limits"].model_copy(update={"max_full_validations": 1})
        stopped = select_swap_replacement(**a, clock=lambda: 0.0)
    assert stopped.outcome.value == "TIMEOUT" and stopped.stage == "VALIDATION"


@pytest.mark.parametrize(
    "kind", ["domain", "ranking", "permission", "saved_plan", "sources", "bridge", "request"]
)
def test_authority_transplant_rejected(kind):
    a, result = valid_case()
    altered = dict(a)
    if kind == "saved_plan":
        altered[kind] = different_saved_plan(make_case())[kind]
    elif kind == "ranking":
        # The ranking is independent authority, so its own declaration version
        # can change legitimately. A ranking for a foreign domain must reject.
        foreign = rebuild(a["domain"], version="foreign")
        altered[kind] = rebuild(a[kind], domain=foreign)
    elif kind == "request":
        altered[kind] = rebuild(a[kind], version="foreign")
    else:
        altered[kind] = rebuild(a[kind], version="foreign")
    with pytest.raises((ValidationError, s.SwapBoundaryError)):
        select_swap_replacement(**altered, clock=lambda: 0.0)
    with pytest.raises((ValidationError, s.SwapBoundaryError)):
        verify_swap_selection(result, **altered, clock=lambda: 0.0)


@pytest.mark.parametrize("priority", [-1, 1_000_001, 1.5, True, float("inf"), float("nan"), "1"])
def test_invalid_rank_values(priority):
    a = selection()
    with pytest.raises(ValidationError):
        rebuild(a["ranking"], entries=({"option": a["domain"].options[0], "priority": priority},))


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "extra", "ranker", "canonical", "unknown-promoted"]
)
def test_ranking_boundary(change):
    a = selection()
    r = a["ranking"]
    with pytest.raises((ValidationError, s.SwapBoundaryError)):
        if change == "missing":
            r = rebuild(r, entries=())
        elif change == "duplicate":
            r = rebuild(r, entries=r.entries * 2)
        elif change == "extra":
            r = rebuild(
                r,
                eligible=(a["sources"].options[0].reference,),
                entries=(
                    s.SyntheticRankEntry(option=a["sources"].options[0].reference, priority=0),
                ),
            )
        elif change == "ranker":
            r = rebuild(r, ranker_version="foreign.v2")
        elif change == "canonical":
            r = rebuild(
                r,
                policy="CANONICAL_OPTION_ID",
                ranker_version="canonical-option-id.v1",
                entries=(r.entries[0].model_copy(update={"priority": 1}),),
            )
        else:
            changes: dict[str, Any] = {"recipe": None}
            a = selection(make_case(**changes))
            r = a["ranking"]
        select_swap_replacement(**(a | {"ranking": r}), clock=lambda: 0.0)


@pytest.mark.parametrize(
    "attack",
    [
        "domain-drop",
        "precheck-drop",
        "disposition-drop",
        "duplicate",
        "overlap",
        "order",
        "visit-drop",
        "visit-digest",
        "eligibility",
        "reservation",
        "selected",
        "exhaustive",
        "execution",
        "verification",
        "final",
        "proof-bytes",
    ],
)
def test_independent_checker_rejects_forged_coverage(attack):
    a, result = valid_case()
    cert = result.certificate
    assert cert is not None
    updates = {}
    if attack == "domain-drop":
        cert = cert.model_copy(update={"original_options": ()})
    elif attack == "precheck-drop":
        cert = cert.model_copy(update={"prechecks": ()})
    elif attack == "disposition-drop":
        cert = cert.model_copy(update={"dispositions": ()})
    elif attack == "duplicate":
        cert = cert.model_copy(update={"dispositions": cert.dispositions * 2})
    elif attack == "overlap":
        cert = cert.model_copy(update={"unvisited": a["domain"].options})
    elif attack == "order":
        cert = cert.model_copy(update={"eligible_order": ()})
    elif attack == "visit-drop":
        cert = cert.model_copy(update={"visits": ()})
    elif attack == "visit-digest":
        cert = cert.model_copy(
            update={"visits": (cert.visits[0].model_copy(update={"validation_digest": "a" * 64}),)}
        )
    elif attack == "eligibility":
        cert = cert.model_copy(update={"eligibility_digest": "b" * 64})
    elif attack == "reservation":
        cert = cert.model_copy(update={"reservations": cert.reservations[:-1]})
    elif attack == "selected":
        updates["selected"] = a["sources"].options[0].reference
    elif attack == "exhaustive":
        updates["exhaustive"] = True
    elif attack == "execution":
        updates["actual_execution"] = s.SwapWork()
    elif attack == "verification":
        updates["actual_verification"] = s.SwapWork()
    elif attack == "final":
        cert = cert.model_copy(update={"final_certificate": None})
    elif attack == "proof-bytes":
        updates["proof_bytes"] = 0
    forged = result.model_copy(update={"certificate": cert} | updates)
    check = verify_swap_selection(forged, **a, clock=lambda: 0.0)
    assert not check.accepted


def test_checker_does_not_call_selector_or_executor():
    a, result = valid_case()
    with (
        patch(
            "savora_ai.core.reasoning.swap_selection.select_swap_replacement",
            side_effect=AssertionError("selector forbidden"),
        ),
        patch(
            "savora_ai.core.reasoning.swap_selection.validate_swap",
            side_effect=AssertionError("executor forbidden"),
        ),
        patch(
            "savora_ai.core.reasoning.swap_checks._execute_phase",
            side_effect=AssertionError("executor forbidden"),
            create=True,
        ),
    ):
        assert verify_swap_selection(result, **a, clock=lambda: 0.0).accepted


@pytest.mark.parametrize(
    "clock", [lambda: float("nan"), lambda: float("inf"), lambda: "0", lambda: True]
)
def test_invalid_clocks_reject(clock):
    a = selection()
    with pytest.raises(ValueError):
        select_swap_replacement(**a, clock=clock)


def test_expired_and_interrupted_checker():
    a, _ = valid_case()
    expired = a | {"limits": a["limits"].model_copy(update={"deadline": 0.0})}
    stopped = select_swap_replacement(**expired, clock=lambda: 1.0)
    assert stopped.outcome.value == "TIMEOUT" and stopped.reason == "DEADLINE"
    # Matching live authority is required to reach replay rather than fail pins.
    live = selection(capacity=limits(selection=True, deadline=1.0))
    complete = select_swap_replacement(**live, clock=lambda: 0.0)
    assert complete.outcome.value == "VALID"
    readings = iter([0.0, 0.0, 1.0] + [1.0] * 10000)
    check = verify_swap_selection(complete, **live, clock=lambda: next(readings))
    assert not check.accepted and not check.complete and check.reason == "DEADLINE"
    assert check.actual_verification.source_items > 0


def test_bare_computed_construction_requires_replay():
    _, result = valid_case()
    with pytest.raises(ValidationError):
        p.ComputedSwapSelectionResult.model_validate(result.model_dump())


def test_canonical_order_and_rank_entry_permutations():
    c, refs = replacement_case((4, 5))
    a = selection(c, options=refs, canonical=True)
    first = select_swap_replacement(**a, clock=lambda: 0.0)
    assert first.selected == refs[0] and first.outcome.value == "VALID"
    b = a | {
        "ranking": rebuild(
            a["ranking"],
            eligible=tuple(reversed(refs)),
            entries=tuple(reversed(a["ranking"].entries)),
        )
    }
    second = select_swap_replacement(**b, clock=lambda: 0.0)
    assert second.model_dump_json(by_alias=True) == first.model_dump_json(by_alias=True)


@pytest.mark.parametrize(
    "defect", ["missing", "duplicate", "noncanonical", "altered", "fifty-one", "semantic-alias"]
)
def test_original_domain_boundaries(defect):
    c, refs = replacement_case((4, 5))
    a = selection(c, options=refs)
    with pytest.raises((ValidationError, s.SwapBoundaryError)):
        if defect == "missing":
            malformed: dict[str, Any] = a | {"domain": None}
            select_swap_replacement(**malformed, clock=lambda: 0.0)
        elif defect == "duplicate":
            rebuild(a["domain"], options=(refs[0], refs[0]))
        elif defect == "noncanonical":
            rebuild(a["domain"], options=tuple(reversed(refs)))
        elif defect == "altered":
            rebuild(
                a["domain"], options=(refs[0].model_copy(update={"combination_digest": "a" * 64}),)
            )
        elif defect == "fifty-one":
            rebuild(a["domain"], options=refs * 26)
        else:
            old = c["sources"].options[-1]
            combo = rebuild(old.combination, snapshot_id="aliased-snapshot")
            ref = old.reference.model_copy(
                update={
                    "option_id": "zz-alias",
                    "snapshot_id": combo.snapshot_id,
                    "combination_digest": combo.content_digest,
                }
            )
            alias = old.model_copy(
                update={
                    "reference": ref,
                    "combination": combo,
                    "suitability": old.suitability.model_copy(update={"option": ref}),
                    "measurements": tuple(
                        m.model_copy(update={"option": ref}) for m in old.measurements
                    ),
                }
            )
            sources = rebuild(c["sources"], options=(*c["sources"].options, alias))
            bridge = rebuild(
                c["bridge"],
                mappings=(
                    *c["bridge"].mappings,
                    s.SwapOptionProjection(original=None, projected=ref, evidence=(evidence(),)),
                ),
            )
            c = repin(c, sources=sources, bridge=bridge)
            b = selection(c, options=(*refs, ref))
            select_swap_replacement(**b, clock=lambda: 0.0)


@pytest.mark.parametrize(
    "changes,expected,scope",
    [
        ({"repetition_limit": 20}, "REJECTED", "OPERATION"),
        ({"recipe": None, "day_limit": 8}, "REJECTED", "DOMAIN"),
        ({"recipe": None}, "INSUFFICIENT_DATA", "DOMAIN"),
        ({"measurements": (2, None)}, "INSUFFICIENT_DATA", "DOMAIN"),
        ({"preparation": True, "opaque_ids": True}, "VALID", None),
    ],
)
def test_b1_semantics_are_retained(changes, expected, scope):
    c = make_case(**changes)
    a = selection(c, eligible=() if changes.get("recipe", True) is None else None)
    result = select_swap_replacement(**a, clock=lambda: 0.0)
    assert result.outcome.value == expected and result.failure_scope == scope
    if expected == "VALID":
        assert result.selected is not None and result.resulting_plan is not None
        assert result.selected.option_id.endswith(":LARGE")
        target = c["request"].target.canonical_index
        assert result.resulting_plan.slots[target].option == c["sources"].options[1]
        for i, old in enumerate(c["saved_plan"].snapshot.slots):
            if i != target:
                assert result.resulting_plan.slots[i].model_dump_json() == old.model_dump_json()


@pytest.mark.parametrize("field", ["max_proof_records", "max_proof_bytes", "max_result_bytes"])
def test_one_short_output_reservations(field):
    a = selection()
    cost = literal_selection_cost(
        a, a["domain"].options, 1, a["domain"].options, a["domain"].options[0]
    )
    amount = cost["records"] if field == "max_proof_records" else 1_048_576
    a["limits"] = limits(selection=True, **{field: amount - 1})
    stopped = select_swap_replacement(**a, clock=lambda: 0.0)
    assert stopped.outcome.value == "TIMEOUT" and stopped.selected is None


def test_final_revalidation_expiry_withholds_verified_candidate():
    from savora_ai.core.reasoning import swap_selection

    a = selection(capacity=limits(selection=True, deadline=1.0))
    from savora_ai.core.reasoning.planned_swap import validate_swap as real

    calls = 0
    current = 0.0

    def invoke(**kwargs):
        nonlocal calls, current
        result = real(**kwargs)
        calls += 1
        if calls == 2:
            current = 1.0
        return result

    with patch.object(swap_selection, "validate_swap", side_effect=invoke):
        stopped = select_swap_replacement(**a, clock=lambda: current)
    assert calls == 2
    assert stopped.outcome.value == "TIMEOUT" and stopped.reason == "DEADLINE"
    assert stopped.stage == "FINAL_VALIDATION"
    assert stopped.actual_execution.full_validations == 4
    assert stopped.selected is stopped.resulting_plan is None


@pytest.mark.parametrize("side", ["executor", "checker"])
@pytest.mark.parametrize("mixed", [False, True])
def test_reconstructed_output_overflow_is_resource_only(side, mixed):
    from savora_ai.core.reasoning import swap_proof, swap_selection

    a, result = valid_case()
    errors: Any = [
        {
            "type": "value_error",
            "loc": (),
            "input": None,
            "ctx": {"error": ValueError("swap structural envelope exceeds 1 MiB")},
        }
    ]
    if mixed:
        errors.append(
            {
                "type": "value_error",
                "loc": (),
                "input": None,
                "ctx": {"error": ValueError("unrelated output defect")},
            }
        )

    def fail(*args, **kwargs):
        raise ValidationError.from_exception_data("InjectedOutput", errors)

    owner = swap_selection if side == "executor" else swap_proof
    with patch.object(owner, "ComputedSwapSelectionCertificate", side_effect=fail):
        if mixed:
            with pytest.raises(ValidationError, match="unrelated output defect"):
                if side == "executor":
                    select_swap_replacement(**a, clock=lambda: 0.0)
                else:
                    verify_swap_selection(result, **a, clock=lambda: 0.0)
        elif side == "executor":
            stopped = select_swap_replacement(**a, clock=lambda: 0.0)
            assert stopped.outcome.value == "TIMEOUT" and stopped.reason == "RESERVATION"
            assert stopped.resulting_plan is None
        else:
            stopped = verify_swap_selection(result, **a, clock=lambda: 0.0)
            assert not stopped.accepted and not stopped.complete and stopped.reason == "RESERVATION"


def test_nonmonotonic_clock_rejects():
    a = selection()
    clock = iter([0.5, 0.25])
    with pytest.raises(ValueError, match="monotonic"):
        select_swap_replacement(**a, clock=lambda: next(clock))


def replace_last_option(case, replacement):
    sources = rebuild(case["sources"], options=(*case["sources"].options[:-1], replacement))
    bridge = rebuild(
        case["bridge"],
        mappings=tuple(
            m.model_copy(update={"projected": replacement.reference})
            if m.projected == case["sources"].options[-1].reference
            else m
            for m in case["bridge"].mappings
        ),
    )
    return repin(case, sources=sources, bridge=bridge)


@pytest.mark.parametrize("kind", ["recipe", "combination"])
def test_actual_hard_fail_exclusion(kind):
    if kind == "recipe":
        c = make_case(recipe=False)
        refs = (c["sources"].options[1].reference,)
    else:
        c, refs = replacement_case((5,))
        old = c["sources"].options[-1]
        combo = rebuild(
            old.combination,
            observations=tuple(
                f.model_copy(
                    update={"observation": f.observation.model_copy(update={"value": False})}
                )
                for f in old.combination.observations
            ),
        )
        ref = old.reference.model_copy(update={"combination_digest": combo.content_digest})
        option = old.model_copy(
            update={
                "reference": ref,
                "combination": combo,
                "suitability": old.suitability.model_copy(update={"option": ref}),
                "measurements": tuple(
                    m.model_copy(update={"option": ref}) for m in old.measurements
                ),
            }
        )
        c, refs = replace_last_option(c, option), (ref,)
    result = select_swap_replacement(**selection(c, options=refs, eligible=()), clock=lambda: 0.0)
    assert result.outcome.value == "REJECTED" and result.exhaustive
    assert result.certificate is not None
    assert result.certificate.prechecks[0].status.value == "FAIL"
    assert result.certificate.dispositions[0].disposition == "HARD_FAIL"
    assert not result.certificate.visits


@pytest.mark.parametrize("amount,expected", [(7, "REJECTED"), (5, "INSUFFICIENT_DATA")])
def test_unknown_combination_obligation_is_not_ranked(amount, expected):
    c, _ = replacement_case((amount,))
    old = c["sources"].options[-1]
    combo = rebuild(old.combination, observations=())
    ref = old.reference.model_copy(update={"combination_digest": combo.content_digest})
    option = old.model_copy(
        update={
            "reference": ref,
            "combination": combo,
            "suitability": old.suitability.model_copy(update={"option": ref}),
            "measurements": tuple(m.model_copy(update={"option": ref}) for m in old.measurements),
        }
    )
    c = replace_last_option(c, option)
    result = select_swap_replacement(**selection(c, options=(ref,), eligible=()), clock=lambda: 0.0)
    assert result.outcome.value == expected and result.exhaustive
    assert result.certificate is not None
    assert result.certificate.unknown_order == (ref,) and not result.certificate.eligible_order
    assert result.certificate.visits[0].outcome.value == expected


def test_supplied_fixed_quantity_preserved_without_id_inference():
    c, _ = replacement_case((5,))
    old = c["sources"].options[-1]
    parts = tuple(
        part.model_copy(update={"quantity": part.quantity.model_copy(update={"amount": 3})})
        for part in old.combination.components
    )
    combo = rebuild(old.combination, components=parts)
    ref = old.reference.model_copy(
        update={"option_id": "opaque:XL", "combination_digest": combo.content_digest}
    )
    option = old.model_copy(
        update={
            "reference": ref,
            "combination": combo,
            "suitability": old.suitability.model_copy(update={"option": ref}),
            "measurements": tuple(
                m.model_copy(update={"option": ref, "components": parts}) for m in old.measurements
            ),
        }
    )
    c = replace_last_option(c, option)
    result = select_swap_replacement(**selection(c, options=(ref,)), clock=lambda: 0.0)
    assert result.outcome.value == "VALID" and result.selected == ref
    assert result.resulting_plan is not None
    assert result.resulting_plan.slots[0].option == option
    assert all(
        new == old
        for new, old in zip(
            result.resulting_plan.slots[1:], c["saved_plan"].snapshot.slots[1:], strict=True
        )
    )


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_complete_result_encoding_ceiling(offset):
    _, result = valid_case()
    cert = result.certificate
    assert cert is not None and cert.final_certificate is not None
    b1 = cert.final_certificate
    trace = b1.result.week.trace
    original = trace.evaluations[0]

    def padded(length):
        changed_trace = trace.model_copy(
            update={
                "evaluations": (
                    original.model_copy(update={"reason": "p" * length}),
                    *trace.evaluations[1:],
                )
            }
        )
        week = b1.result.week.model_copy(update={"trace": changed_trace})
        final = b1.model_copy(update={"result": b1.result.model_copy(update={"week": week})})
        certificate = cert.model_copy(update={"final_certificate": final})
        return result.model_copy(update={"certificate": certificate})

    base = len(padded(1).model_dump_json(by_alias=True).encode())
    forged = padded(1_048_576 - base + 1 + offset)
    raw = forged.model_dump_json(by_alias=True)
    assert len(raw.encode()) == 1_048_576 + offset
    if offset > 0:
        with pytest.raises(ValidationError, match="structural envelope"):
            p._SwapSelectionClaim.model_validate_json(raw)
    else:
        declared = p._SwapSelectionClaim.model_validate_json(raw)
        assert declared.schema_version == "computed-swap-selection-result.v1"
        # Parsing a private claim does not run computed-result authority replay.
        assert type(declared) is p._SwapSelectionClaim


@pytest.mark.parametrize("rehash", [False, True])
def test_coherent_authority_transplant_does_not_authenticate_old_proof(rehash):
    _, result = valid_case()
    other = selection(make_case(measurements=(2, 4)))
    claim = result
    if rehash:
        from test_planned_swap_contracts import reference

        from savora_ai.core.reasoning.swap_selection import _SelectionInputs
        from savora_ai.schemas.candidates import _content_digest

        assert result.certificate is not None
        cert = result.certificate.model_copy(
            update={"input_digest": _content_digest(_SelectionInputs.model_validate(other))}
        )
        claim = result.model_copy(
            update={
                "certificate": cert,
                "request": other["request"],
                "domain": reference(other["domain"]),
                "ranking": reference(other["ranking"]),
            }
        )
    check = verify_swap_selection(claim, **other, clock=lambda: 0.0)
    assert not check.accepted and check.complete and check.reason == "MISMATCH"
