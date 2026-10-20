"""Structural v2 declarations only: these tests do not execute or fake a v2 checker."""

import inspect
import json
from enum import EnumType, StrEnum
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from savora_ai.core.reasoning import weekly
from savora_ai.evals.synthetic_week_cases import build_week_case
from savora_ai.evals.weekly_benchmarks import CorrectnessMetrics, WeeklyBenchmarkResult
from savora_ai.schemas import weekly_search_v2 as v2
from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.daily import DailyOutcome, MealSlot
from savora_ai.schemas.knowledge import EvidenceReference, RuleEnvironment, RuleReference, RuleScope
from savora_ai.schemas.reasoning import RuleStatus
from savora_ai.schemas.weekly_search import WeeklySearchCertificate, WeeklySearchStatistics
from savora_ai.schemas.weekly_solver import ComputedWeeklySolveResult


def strategy(policy=v2.WeeklyStrategyPolicyV2.CHRONOLOGICAL) -> v2.WeeklySearchStrategyV2:
    variable, value, propagation = {
        v2.WeeklyStrategyPolicyV2.CHRONOLOGICAL: ("CHRONOLOGICAL", "OPTION_ID_ASC", "NONE"),
        v2.WeeklyStrategyPolicyV2.REVERSE_VALUES: ("CHRONOLOGICAL", "OPTION_ID_DESC", "NONE"),
        v2.WeeklyStrategyPolicyV2.FORWARD_CHECKING: (
            "CHRONOLOGICAL",
            "OPTION_ID_ASC",
            "KNOWN_FAILURE_FORWARD_CHECK",
        ),
        v2.WeeklyStrategyPolicyV2.MRV: ("MRV", "OPTION_ID_ASC", "KNOWN_FAILURE_FORWARD_CHECK"),
    }[policy]
    return v2.WeeklySearchStrategyV2.model_validate(
        dict(
            policy=policy,
            variable_order=variable,
            value_order=value,
            propagation=propagation,
        )
    )


@pytest.fixture(scope="module")
def declared() -> v2.WeeklySearchCertificateV2:
    case = build_week_case("early")
    request, context = case.request, case.context
    identity = v2.WeeklySearchIdentityV2(
        request_id=request.request_id,
        request_version=request.version,
        request_digest=request.content_digest,
        # Deliberately declarations, not authenticated/rebuilt manifests or proofs.
        manifest_digest="b" * 64,
        candidate_set_digest="c" * 64,
        source=request.expected_source,
        daily_source=request.source.expected_daily_source,
        context_id=context.context_id,
        context_version=context.version,
        context_digest=context.content_digest,
        profile_id=context.profile_id,
        profile_version=context.profile_version,
        kb_id=context.expected_kb_id,
        kb_version=context.expected_kb_version,
        kb_digest=context.expected_kb_digest,
        strategy=strategy(),
    )
    domains = tuple(
        v2.WeeklyOriginalDomainV2(
            slot=v2.WeeklySlotIdentityV2(
                canonical_index=(day.day.day_index - 1) * 3 + j, day=day.day, slot=slot
            ),
            options=tuple(
                sorted(
                    next(d.options for d in day.domains if d.slot is slot),
                    key=lambda option: option.option_id,
                )
            ),
        )
        for day in sorted(request.days, key=lambda d: d.day.day_index)
        for j, slot in enumerate(MealSlot)
    )
    return v2.WeeklySearchCertificateV2(
        request=request,
        identity=identity,
        original_domains=domains,
        rule_obligations=tuple(
            v2.WeeklyRuleObligationV2(
                rule=RuleReference(rule_id=rule.rule_id, version=rule.version),
                scope=rule.scope,
            )
            for rule in case.knowledge.rules
        ),
        limits=v2.WeeklySearchLimitsV2(
            max_nodes=1000,
            max_reserved_work=v2.WeeklyWorkV2(
                candidate_preparations=100,
                combination_preparations=100,
                predicate_obligations=1000,
                day_assessments=100,
                week_assessments=100,
                heuristic_evaluations=1000,
                proof_verification_steps=1000,
            ),
            max_proof_records=1024,
            max_proof_bytes=1_048_576,
            max_cache_entries=64,
        ),
    )


def revise(model, **changes):
    return type(model).model_validate({**model.model_dump(), **changes})


def with_strategy(declared, policy):
    return revise(declared, identity=revise(declared.identity, strategy=strategy(policy)))


def choice(declared, slot: int, depth: int = 0, option: int = 0):
    domain = declared.original_domains[slot]
    return v2.WeeklySelectedOptionV2(
        depth=depth,
        slot=domain.slot,
        original_domain_index=option,
        option=domain.options[option],
    )


def scope(declared, slots=(), *, branch_id="branch", alternative=None):
    path = tuple(choice(declared, slot, depth) for depth, slot in enumerate(slots))
    return v2.WeeklyBranchScopeV2(
        branch_id=branch_id,
        extent="SLOT_ALTERNATIVES"
        if alternative is not None
        else "LEAF"
        if len(slots) == 21
        else "PREFIX_COMPLETIONS",
        path=path,
        decision_slot=declared.original_domains[alternative].slot
        if alternative is not None
        else None,
        original_domain_indexes=(0,) if alternative is not None else (),
    )


def accounting(sequence=0, **changes):
    return v2.WeeklyAccountingV2.model_validate(
        dict(
            logical_nodes=sequence,
            proof_records_written=sequence + 1,
            proof_records_reserved=sequence + 1,
            proof_bytes_reserved=(sequence + 1) * 4096,
            proof_bytes_written=(sequence + 1) * 4096,
            checkpoints=sequence + 1,
            **changes,
        )
    )


def basis(declared, rule_scope=RuleScope.DAY, **changes):
    obligation = next(o for o in declared.rule_obligations if o.scope is rule_scope)
    return v2.WeeklyFailureBasisV2.model_validate(
        dict(
            obligations=(obligation,),
            evaluation_digest="e" * 64,
            relevant_basis_complete=True,
            evidence=(
                EvidenceReference(
                    evidence_id="v2-fictional-evaluation",
                    version="1",
                    source="Fictional declaration",
                    locator="urn:synthetic:v2:declared-evaluation",
                    environment=RuleEnvironment.SYNTHETIC,
                ),
            ),
            **changes,
        )
    )


def event(declared, kind, *, sequence=0, **changes):
    payload = dict(
        kind=kind,
        sequence=sequence,
        identity=declared.identity,
        scope=scope(declared),
        accounting=accounting(sequence),
    )
    payload.update(changes)
    return TypeAdapter(v2.WeeklyProofEventV2).validate_python(payload)


def certificate(declared, events=(), frontier=(), **changes):
    return revise(
        declared,
        events=events,
        frontier=frontier,
        accounting=events[-1].accounting if events else declared.accounting,
        **changes,
    )


def sample_event(declared, kind):
    if kind == "VARIABLE_SELECTION":
        return event(
            declared,
            kind,
            depth=0,
            selected_slot=declared.original_domains[0].slot,
            remaining_slots=tuple(range(21)),
        )
    if kind == "VALUE_SELECTION":
        return event(declared, kind, scope=scope(declared, (0,)))
    if kind == "UNARY_FAILURE":
        return event(
            declared,
            kind,
            scope=scope(declared, alternative=0),
            basis=basis(declared, RuleScope.RECIPE),
        )
    if kind == "DAY_FAILURE":
        return event(
            declared, kind, scope=scope(declared, (0, 1, 2)), day_index=1, basis=basis(declared)
        )
    if kind == "WEEK_FAILURE":
        return event(
            declared,
            kind,
            scope=scope(declared, tuple(range(21))),
            basis=basis(declared, RuleScope.WEEK),
        )
    if kind == "FORWARD_CHECK_CLOSURE":
        return event(
            declared,
            kind,
            basis=basis(declared),
            remaining_domains=tuple(
                v2.WeeklyDomainSliceV2(
                    slot=d.slot,
                    original_domain_indexes=tuple(range(len(d.options))),
                )
                for d in declared.original_domains
            ),
        )
    if kind == "COMPLETED_LEAF":
        return event(
            declared,
            kind,
            scope=scope(declared, tuple(range(21))),
            declared_status=RuleStatus.UNKNOWN,
            obligations=declared.rule_obligations,
            evaluation_digest="d" * 64,
        )
    if kind == "RESOURCE_INTERRUPTION":
        return event(declared, kind, reason="NODE_BUDGET", checkpoint=1)
    return event(declared, kind, child_branch_ids=())


EVENT_KINDS = (
    "VARIABLE_SELECTION",
    "VALUE_SELECTION",
    "UNARY_FAILURE",
    "DAY_FAILURE",
    "WEEK_FAILURE",
    "FORWARD_CHECK_CLOSURE",
    "COMPLETED_LEAF",
    "RESOURCE_INTERRUPTION",
    "BRANCH_EXHAUSTION",
)


def test_declarations_do_not_authorize_results_even_with_empty_frontier(declared):
    assert declared.outcome is None and declared.exhaustive is False
    assert declared.verification_state == "NOT_VERIFIED"
    assert declared.semantic_validation == "DEFERRED_TO_PHASE_7_2A"
    assert declared.frontier == declared.events == ()
    assert not any(name.startswith("Computed") for name in vars(v2))
    # An exhaustion declaration over a nonempty original domain remains unverified.
    closed = certificate(declared, (sample_event(declared, "BRANCH_EXHAUSTION"),))
    assert closed.outcome is None and closed.exhaustive is False


@pytest.mark.parametrize("outcome", [*DailyOutcome, "FEASIBLE", "INFEASIBLE", "TIMEOUT"])
def test_no_unverified_outcome_authorization(declared, outcome):
    with pytest.raises(ValidationError):
        revise(declared, outcome=outcome)
    with pytest.raises(ValidationError):
        v2.WeeklySearchCertificateV2.model_validate(
            declared.model_copy(update={"outcome": outcome})
        )


@pytest.mark.parametrize("flag", [True, 0, 1, 0.0, "false", None])
def test_no_exhaustive_claim_or_boolean_coercion(declared, flag):
    with pytest.raises(ValidationError):
        revise(declared, exhaustive=flag)


@pytest.mark.parametrize("policy", list(v2.WeeklyStrategyPolicyV2))
def test_all_strategy_policies_are_frozen_declared_only(policy):
    item = strategy(policy)
    assert item.support == "DECLARED_ONLY"
    assert item.criterion == "FIRST_FEASIBLE"
    assert (
        validate_contract_json(v2.WeeklySearchStrategyV2, item.model_dump_json(by_alias=True))
        == item
    )
    with pytest.raises(ValidationError):
        item.value_order = "OPTION_ID_DESC"
    with pytest.raises(ValidationError):
        revise(item, support="IMPLEMENTED")
    with pytest.raises(ValidationError):
        revise(item, criterion="GLOBAL_OPTIMAL")


@pytest.mark.parametrize(
    "change",
    [
        {"policy": "synthetic-chronological-weekly-search.v1"},
        {"policy": "unknown.v2"},
        {"variable_order": "MRV"},
        {"value_order": "OPTION_ID_DESC"},
        {"propagation": "KNOWN_FAILURE_FORWARD_CHECK"},
        {"callback": lambda: True},
        {"variable_order": lambda: 0},
        {"rule_expression": "True"},
        {"original_domain_policy": "caller-domain-order"},
    ],
)
def test_no_undocumented_policies_combinations_or_callbacks(change):
    with pytest.raises(ValidationError):
        revise(strategy(), **change)


@pytest.mark.parametrize("kind", EVENT_KINDS)
def test_every_event_shape_roundtrips_but_is_not_semantically_verified(declared, kind):
    if kind == "FORWARD_CHECK_CLOSURE":
        declared = with_strategy(declared, v2.WeeklyStrategyPolicyV2.FORWARD_CHECKING)
    item = sample_event(declared, kind)
    document = certificate(declared, (item,))
    assert document.outcome is None
    assert (
        validate_contract_json(
            v2.WeeklySearchCertificateV2, document.model_dump_json(by_alias=True)
        )
        == document
    )
    assert (
        validate_contract_json(
            TypeAdapter(v2.WeeklyProofEventV2), item.model_dump_json(by_alias=True)
        )
        == item
    )


def test_mrv_depth_is_not_slot_identity_and_day_closure_uses_actual_slots(declared):
    mrv = with_strategy(declared, v2.WeeklyStrategyPolicyV2.MRV)
    selected = event(
        mrv,
        "VARIABLE_SELECTION",
        depth=0,
        selected_slot=mrv.original_domains[20].slot,
        remaining_slots=tuple(range(21)),
    )
    assert certificate(mrv, (selected,)).events[0].selected_slot.canonical_index == 20
    path = scope(mrv, (20, 0, 3, 1, 2))
    day = event(mrv, "DAY_FAILURE", scope=path, day_index=1, basis=basis(mrv))
    assert len(certificate(mrv, (day,)).events[0].scope.path) == 5
    wrong_day = scope(mrv, (0, 3, 6))
    with pytest.raises(ValidationError, match="actual day slots"):
        event(mrv, "DAY_FAILURE", scope=wrong_day, day_index=1, basis=basis(mrv))
    with pytest.raises(ValidationError, match="chronological selection"):
        certificate(declared, (revise(selected, identity=declared.identity),))


@pytest.mark.parametrize(
    "field,value",
    [
        ("depth", -1),
        ("depth", 21),
        ("depth", True),
        ("original_domain_index", -1),
        ("original_domain_index", 50),
        ("original_domain_index", True),
        ("original_domain_index", 1.0),
    ],
)
def test_position_scalar_boundaries(declared, field, value):
    with pytest.raises(ValidationError):
        revise(choice(declared, 0), **{field: value})


def test_original_positions_and_exact_configuration_binding(declared):
    selected = choice(declared, 1)
    bad_index = revise(selected, original_domain_index=1)
    bad_option = revise(
        selected, option=revise(selected.option, portion_configuration_id="foreign")
    )
    for wrong in (bad_index, bad_option):
        bad_scope = revise(
            scope(declared, (0, 1)), path=(choice(declared, 0), revise(wrong, depth=1))
        )
        with pytest.raises(ValidationError, match="exact original domain"):
            certificate(declared, (event(declared, "VALUE_SELECTION", scope=bad_scope),))
    with pytest.raises(ValidationError):
        revise(declared.original_domains[0].slot, canonical_index=1)
    with pytest.raises(ValidationError, match="assign a slot twice"):
        v2.WeeklyBranchScopeV2(
            branch_id="dup",
            extent="PREFIX_COMPLETIONS",
            path=(choice(declared, 0), choice(declared, 0, 1)),
        )
    with pytest.raises(ValidationError, match="depths"):
        revise(scope(declared, (0,)), path=(choice(declared, 0, 1),))


def test_duplicate_domains_options_and_branches_rejected(declared):
    with pytest.raises(ValidationError):
        revise(declared, original_domains=(declared.original_domains[0],) * 21)
    domain = declared.original_domains[0]
    with pytest.raises(ValidationError):
        revise(domain, options=(domain.options[0], domain.options[0]))
    with pytest.raises(ValidationError):
        revise(domain, options=tuple(reversed(domain.options)))
    branch = v2.WeeklyFrontierBranchV2(
        scope=scope(declared), state=v2.WeeklyFrontierStateV2.UNEXPLORED
    )
    for duplicate in (branch, revise(branch, scope=revise(branch.scope, branch_id="different-id"))):
        with pytest.raises(ValidationError, match="duplicate frontier"):
            certificate(declared, frontier=(branch, duplicate))
    value = event(declared, "VALUE_SELECTION", scope=scope(declared, (0,)))
    with pytest.raises(ValidationError, match="conflicting scope"):
        certificate(declared, (value,), (branch,))


@pytest.mark.parametrize(
    "field",
    [
        "request_digest",
        "manifest_digest",
        "candidate_set_digest",
        "context_digest",
        "kb_digest",
    ],
)
@pytest.mark.parametrize("value", ["", "A" * 64, "x" * 64, "a" * 63, "a" * 65, None])
def test_identity_digest_syntax(declared, field, value):
    with pytest.raises(ValidationError):
        revise(declared.identity, **{field: value})


@pytest.mark.parametrize("field", ["request_digest", "context_digest", "kb_digest"])
def test_valid_digest_format_does_not_permit_pin_conflicts(declared, field):
    with pytest.raises(ValidationError, match="retained request"):
        revise(declared, identity=revise(declared.identity, **{field: "f" * 64}))


def test_unresolved_manifest_authority_and_failure_truth_stay_deferred(declared):
    # Structurally self-consistent unsigned manifest claims are representable,
    # but cannot authorize any verdict or authenticate their named evidence.
    changed = revise(declared, identity=revise(declared.identity, manifest_digest="f" * 64))
    claimed = certificate(changed, (sample_event(changed, "UNARY_FAILURE"),))
    assert claimed.verification_state == "NOT_VERIFIED" and claimed.outcome is None
    assert claimed.events[0].basis.soundness == "DEFERRED"
    with pytest.raises(ValidationError):
        basis(declared, declared_status="UNKNOWN")
    for incomplete in (False, None, 1, "true"):
        data = basis(declared).model_dump()
        data["relevant_basis_complete"] = incomplete
        with pytest.raises(ValidationError):
            v2.WeeklyFailureBasisV2.model_validate(data)
    with pytest.raises(ValidationError):
        basis(declared, soundness="VERIFIED")


def test_cross_request_event_manifest_context_and_option_transplants_rejected(declared):
    valid = sample_event(declared, "VALUE_SELECTION")
    for changes in (
        {"request_digest": "f" * 64},
        {"manifest_digest": "f" * 64},
        {"candidate_set_digest": "f" * 64},
        {"context_version": "foreign"},
        {"source": revise(declared.identity.source, content_digest="f" * 64)},
        {"strategy": strategy(v2.WeeklyStrategyPolicyV2.REVERSE_VALUES)},
    ):
        other = revise(valid, identity=revise(valid.identity, **changes))
        with pytest.raises(ValidationError, match="binding differs"):
            certificate(declared, (other,))
    with pytest.raises(ValidationError, match="retained request"):
        revise(declared, request=build_week_case("late").request)
    foreign_slot = revise(
        declared.original_domains[0].slot,
        day=revise(declared.original_domains[0].slot.day, day_id="foreign-day"),
    )
    wrong = revise(
        valid, scope=revise(valid.scope, path=(revise(choice(declared, 0), slot=foreign_slot),))
    )
    with pytest.raises(ValidationError, match="transplanted"):
        certificate(declared, (wrong,))


@pytest.mark.parametrize(
    "field,max_value",
    [
        ("logical_nodes", 200000),
        ("backtracks", 200000),
        ("proof_records_reserved", 8192),
        ("proof_bytes_reserved", 1048576),
        ("checkpoints", 1000000),
        ("cache_capacity", 4096),
        ("cache_hits", 1000000),
    ],
)
def test_accounting_strict_boundaries(field, max_value):
    for bad in (-1, max_value + 1, True, "1", 1.5):
        with pytest.raises(ValidationError):
            v2.WeeklyAccountingV2.model_validate({field: bad})
    assert getattr(v2.WeeklyAccountingV2.model_validate({field: max_value}), field) == max_value


@pytest.mark.parametrize("field", list(v2.WeeklyWorkV2.model_fields))
def test_execution_verification_reservations_are_separate_and_bounded(field):
    work = v2.WeeklyWorkV2.model_validate({field: 1})
    with pytest.raises(ValidationError, match="exceeds reservation"):
        v2.WeeklyAccountingV2(execution_work=work, verification_work=work, reserved_work=work)
    item = v2.WeeklyAccountingV2(
        execution_work=work,
        verification_work=work,
        reserved_work=v2.WeeklyWorkV2.model_validate({field: 2}),
    )
    assert item.physical_evaluator_calls == "NOT_RECORDED"
    for bad in (-1, 1000001, True):
        with pytest.raises(ValidationError):
            v2.WeeklyWorkV2.model_validate({field: bad})


def test_record_reservation_summary_limits_and_monotonic_declarations(declared):
    item = sample_event(declared, "VALUE_SELECTION")
    for bad in (
        {"proof_records_reserved": 0},
        {"proof_bytes_reserved": 0},
        {"proof_bytes_written": 0},
        {"proof_records_written": 0},
    ):
        with pytest.raises(ValidationError):
            event(
                declared,
                "VALUE_SELECTION",
                scope=item.scope,
                accounting=revise(item.accounting, **bad),
            )
    with pytest.raises(ValidationError, match="resource limits"):
        certificate(declared, (item,), limits=revise(declared.limits, max_proof_records=0))
    with pytest.raises(ValidationError, match="work reservation"):
        certificate(
            declared,
            (
                revise(
                    item,
                    accounting=revise(
                        item.accounting, reserved_work=v2.WeeklyWorkV2(candidate_preparations=101)
                    ),
                ),
            ),
        )
    with pytest.raises(ValidationError, match="summary accounting"):
        revise(certificate(declared, (item,)), accounting=v2.WeeklyAccountingV2())
    first = revise(item, accounting=revise(item.accounting, logical_nodes=10))
    second = event(
        declared, "VALUE_SELECTION", sequence=1, scope=scope(declared, (0, 1), branch_id="b2")
    )
    with pytest.raises(ValidationError, match="cannot decrease"):
        certificate(declared, (first, second))
    with pytest.raises(ValidationError):
        v2.WeeklyAccountingV2(cache_capacity=0, cache_entries=1)


def test_frontier_states_and_support_are_typed_but_not_verified(declared):
    leaf = sample_event(declared, "COMPLETED_LEAF")
    branch = v2.WeeklyFrontierBranchV2(
        scope=leaf.scope,
        state=v2.WeeklyFrontierStateV2.UNRESOLVED_UNKNOWN,
        supporting_event=0,
        unresolved_obligations=(declared.rule_obligations[0],),
    )
    assert certificate(declared, (leaf,), (branch,)).outcome is None
    explored = revise(branch, state=v2.WeeklyFrontierStateV2.EXPLORED, unresolved_obligations=())
    assert certificate(declared, (leaf,), (explored,)).exhaustive is False
    exclusion = sample_event(declared, "UNARY_FAILURE")
    excluded = v2.WeeklyFrontierBranchV2(
        scope=exclusion.scope, state=v2.WeeklyFrontierStateV2.EXCLUSION_DECLARED, supporting_event=0
    )
    assert certificate(declared, (exclusion,), (excluded,)).verification_state == "NOT_VERIFIED"
    with pytest.raises(ValidationError, match="known-failure event"):
        certificate(declared, (leaf,), (revise(excluded, scope=leaf.scope),))
    with pytest.raises(ValidationError, match="missing event"):
        certificate(declared, (leaf,), (revise(branch, supporting_event=1),))
    with pytest.raises(ValidationError):
        revise(branch, unresolved_obligations=())


def test_empty_mandatory_inventory_unknown_has_an_explicit_scoped_obligation(declared):
    gap = v2.WeeklyPrerequisiteObligationV2(
        prerequisite="MANDATORY_CHECK_COVERAGE",
        scope=RuleScope.WEEK,
    )
    missing = v2.WeeklyFrontierBranchV2(
        scope=scope(declared),
        state=v2.WeeklyFrontierStateV2.UNRESOLVED_UNKNOWN,
        unresolved_obligations=(gap,),
    )
    document = certificate(declared, frontier=(missing,), rule_obligations=())
    assert document.outcome is None and document.exhaustive is False
    assert (
        validate_contract_json(v2.WeeklySearchCertificateV2, document.model_dump_json()) == document
    )
    with pytest.raises(ValidationError):
        v2.WeeklyPrerequisiteObligationV2(prerequisite="MANDATORY_CHECK_COVERAGE")
    with pytest.raises(ValidationError):
        v2.WeeklyPrerequisiteObligationV2(prerequisite="SLOT_SUITABILITY", scope=RuleScope.DAY)


def test_scope_and_event_malformed_shapes(declared):
    for change in ({"sequence": 1}, {"kind": "CALLER_PRUNE"}, {"verified": True}, {"scope": {}}):
        payload = sample_event(declared, "VALUE_SELECTION").model_dump()
        payload.update(change)
        with pytest.raises(ValidationError):
            certificate(declared, (TypeAdapter(v2.WeeklyProofEventV2).validate_python(payload),))
    with pytest.raises(ValidationError):
        event(declared, "WEEK_FAILURE", basis=basis(declared, RuleScope.WEEK))
    with pytest.raises(ValidationError):
        sample_event(declared, "FORWARD_CHECK_CLOSURE")
    with pytest.raises(ValidationError):
        event(
            declared,
            "VARIABLE_SELECTION",
            depth=0,
            selected_slot=declared.original_domains[0].slot,
            remaining_slots=(0, 0),
        )
    with pytest.raises(ValidationError):
        event(
            declared, "UNARY_FAILURE", scope=scope(declared, alternative=0), basis=basis(declared)
        )
    with pytest.raises(ValidationError):
        revise(scope(declared, alternative=0), original_domain_indexes=(0, 0))


def test_interruption_not_a_timeout_result_or_clock_authentication(declared):
    stopped = sample_event(declared, "RESOURCE_INTERRUPTION")
    assert certificate(declared, (stopped,)).outcome is None
    deadline = revise(stopped, reason="DEADLINE", deadline_checkpoint=1)
    with pytest.raises(ValidationError, match="declared deadline"):
        certificate(declared, (deadline,))
    timed = certificate(declared, (deadline,), limits=revise(declared.limits, deadline=10.0))
    assert timed.verification_state == "NOT_VERIFIED"
    for bad in (float("nan"), float("inf"), True, "10"):
        with pytest.raises(ValidationError):
            revise(declared.limits, deadline=bad)
    with pytest.raises(ValidationError):
        revise(stopped, checkpoint=2)


def test_original_json_aliases_extra_fields_and_bounds(declared):
    raw = declared.model_dump_json(by_alias=True)
    for text in (
        raw.replace('"requestId":', '"requestId":"duplicate","requestId":', 1),
        raw.replace('"requestId":', '"request_id":"duplicate","requestId":', 1),
        raw.replace('"schemaVersion":', '"schema_version":"foreign","schemaVersion":', 1),
        '{"callback":"x",' + raw[1:],
        "{",
        "[" * 65 + "0" + "]" * 65,
        " " * 1_048_577,
    ):
        with pytest.raises(ValidationError):
            validate_contract_json(v2.WeeklySearchCertificateV2, text)
    data = declared.model_dump()
    data["original_domains"] = list(data["original_domains"])
    with pytest.raises(ValidationError):
        v2.WeeklySearchCertificateV2.model_validate(data)
    with pytest.raises(ValidationError):
        declared.identity.context_digest = "f" * 64
    assert "weekly-coverage.v2" in json.dumps(v2.WeeklySearchCertificateV2.model_json_schema())


def test_hostile_container_rejection_before_custom_methods(declared):
    class HostileDict(dict):
        def items(self):
            raise AssertionError("hostile mapping executed")

    class HostileTuple(tuple):
        def __iter__(self):
            raise AssertionError("hostile tuple executed")

    class HostileList(list):
        def __iter__(self):
            raise AssertionError("hostile list executed")

    with pytest.raises(ValidationError):
        v2.WeeklySearchCertificateV2.model_validate(HostileDict(declared.model_dump()))
    for hostile in (HostileList(), HostileTuple(), []):
        with pytest.raises(ValidationError):
            v2.WeeklySearchCertificateV2.model_validate(
                declared.model_copy(update={"events": hostile})
            )
    bad = declared.model_copy()
    object.__setattr__(bad, "__dict__", HostileDict(vars(bad)))
    with pytest.raises(ValidationError):
        v2.WeeklySearchCertificateV2.model_validate(bad)
    with pytest.raises(ValidationError):
        TypeAdapter(v2.WeeklyProofEventV2).validate_python(HostileDict(kind="VALUE_SELECTION"))


@pytest.mark.parametrize("extra", [{"unexpected": True}, {"verification_state": "VERIFIED"}])
def test_unchecked_copies_and_nested_constructs_are_revalidated(declared, extra):
    with pytest.raises(ValidationError):
        v2.WeeklySearchCertificateV2.model_validate(declared.model_copy(update=extra))
    malformed = v2.WeeklySelectedOptionV2.model_construct(
        depth="0",
        slot=declared.original_domains[0].slot,
        original_domain_index=0,
        option=declared.original_domains[0].options[0],
    )
    copied = scope(declared, (0,)).model_copy(update={"path": (malformed,)})
    with pytest.raises(ValidationError):
        v2.WeeklyBranchScopeV2.model_validate(copied)


@pytest.mark.parametrize(
    "enum_type",
    [
        v2.WeeklyStrategyPolicyV2,
        v2.WeeklyFrontierStateV2,
        RuleScope,
        MealSlot,
        RuleStatus,
    ],
)
def test_fabricated_canonical_looking_enums_are_rejected(declared, enum_type):
    original = next(iter(enum_type))
    fake = str.__new__(enum_type, original.value)
    object.__setattr__(fake, "_name_", original.name)
    object.__setattr__(fake, "_value_", original.value)
    if enum_type is v2.WeeklyStrategyPolicyV2:
        target, model = strategy().model_copy(update={"policy": fake}), v2.WeeklySearchStrategyV2
    elif enum_type is v2.WeeklyFrontierStateV2:
        target = v2.WeeklyFrontierBranchV2.model_construct(scope=scope(declared), state=fake)
        model = v2.WeeklyFrontierBranchV2
    elif enum_type is RuleScope:
        target, model = (
            declared.rule_obligations[0].model_copy(update={"scope": fake}),
            v2.WeeklyRuleObligationV2,
        )
    elif enum_type is MealSlot:
        target, model = (
            declared.original_domains[0].slot.model_copy(update={"slot": fake}),
            v2.WeeklySlotIdentityV2,
        )
    else:
        target, model = (
            sample_event(declared, "COMPLETED_LEAF").model_copy(update={"declared_status": fake}),
            v2.WeeklyCompletedLeafV2,
        )
    with pytest.raises(ValidationError):
        model.model_validate(target)


def test_foreign_enum_types_and_production_labels_cannot_enter(declared):
    class ForeignPolicy(StrEnum):
        SAME_TOKEN = "synthetic-chronological-weekly-search.v2"

    with pytest.raises(ValidationError):
        revise(strategy(), policy=ForeignPolicy.SAME_TOKEN)
    record = basis(declared).evidence[0]
    with pytest.raises(ValidationError):
        revise(basis(declared), evidence=(revise(record, environment=RuleEnvironment.PRODUCTION),))
    with pytest.raises(ValidationError):
        revise(basis(declared), evidence=(record, record))


def test_hostile_enum_metaclass_is_rejected_before_iteration():
    class HostileMeta(EnumType):
        def __iter__(cls):
            raise AssertionError("hostile enum metaclass executed")

    class HostileEnum(StrEnum, metaclass=HostileMeta):
        SAME_TOKEN = "synthetic-chronological-weekly-search.v2"

    with pytest.raises(ValidationError):
        revise(strategy(), policy=HostileEnum.SAME_TOKEN)


def test_branch_child_references_must_be_known_unique_and_acyclic(declared):
    parent_scope = scope(declared, branch_id="parent")
    child_scope = scope(declared, (0,), branch_id="child")
    parent = event(declared, "BRANCH_EXHAUSTION", scope=parent_scope, child_branch_ids=("child",))
    child = event(declared, "BRANCH_EXHAUSTION", sequence=1, scope=child_scope, child_branch_ids=())
    assert certificate(declared, (parent, child)).exhaustive is False
    with pytest.raises(ValidationError, match="undeclared child"):
        certificate(declared, (parent,))
    with pytest.raises(ValidationError):
        revise(parent, child_branch_ids=("child", "child"))
    with pytest.raises(ValidationError):
        revise(parent, child_branch_ids=("parent",))
    with pytest.raises(ValidationError, match="cyclic branch"):
        certificate(declared, (parent, revise(child, child_branch_ids=("parent",))))


def test_nested_proof_cardinality_and_encoded_size_are_bounded(declared):
    item = sample_event(declared, "VALUE_SELECTION")
    with pytest.raises(ValidationError):
        certificate(declared, (item,) * 1025)
    with pytest.raises(ValidationError):
        revise(scope(declared, (0,)), path=(choice(declared, 0),) * 22)
    huge = revise(basis(declared, RuleScope.RECIPE).evidence[0], locator="x" * 1_048_576)
    large_basis = revise(basis(declared, RuleScope.RECIPE), evidence=(huge,))
    with pytest.raises(ValidationError, match="encoded structural ceiling"):
        certificate(
            declared,
            (
                event(
                    declared,
                    "UNARY_FAILURE",
                    scope=scope(declared, alternative=0),
                    basis=large_basis,
                ),
            ),
        )


def test_v1_v2_schema_separation_even_after_relabelling(declared):
    stats: dict[str, Any] = {field: 0 for field in WeeklySearchStatistics.model_fields}
    stats.update(exhaustive=False, termination=None)
    v1 = WeeklySearchCertificate(
        recipe_proof_digest=None,
        preparation=(),
        records=(),
        frontier=(),
        next_indexes=(),
        deadline_checkpoint=None,
        statistics=WeeklySearchStatistics.model_validate(stats),
    )
    for data in (v1, v1.model_copy(update={"schema_version": "weekly-coverage.v2"})):
        with pytest.raises(ValidationError):
            v2.WeeklySearchCertificateV2.model_validate(data)
    for data in (declared, declared.model_copy(update={"schema_version": "weekly-coverage.v1"})):
        with pytest.raises(ValidationError):
            WeeklySearchCertificate.model_validate(data)
        annotation = ComputedWeeklySolveResult.model_fields["certificate"].annotation
        assert annotation is not None
        with pytest.raises(ValidationError):
            TypeAdapter(annotation).validate_python(data)
    assert tuple(inspect.signature(weekly.solve_weekly_plan).parameters) == (
        "request",
        "candidates",
        "knowledge",
        "context",
        "sources",
        "limits",
        "clock",
    )
    assert ComputedWeeklySolveResult.model_fields["search_policy_version"].default == (
        "synthetic-chronological-weekly-search.v1"
    )


def test_future_benchmark_metadata_does_not_make_declarations_computed_outcomes(declared):
    for field, token in (
        ("solver_schema_version", declared.schema_version),
        ("search_policy_version", declared.identity.strategy.policy.value),
    ):
        annotation = WeeklyBenchmarkResult.model_fields[field].annotation
        assert annotation is not None
        assert TypeAdapter(annotation).validate_python(token) == token
    with pytest.raises(ValidationError):
        CorrectnessMetrics.model_validate(
            dict(
                expected_outcome="FEASIBLE",
                outcome=declared.outcome,
                expected_outcome_matches=False,
                oracle_scope="COMPLETE_LITERAL_PROBLEM",
                oracle_outcome="FEASIBLE",
                oracle_assignments=1,
                oracle_passed=1,
                oracle_failed=0,
                oracle_unknown=0,
                outcome_matches_oracle=False,
                witness_validation="NOT_PRESENT",
                witness_option_indexes=(),
                first_witness_matches_oracle="NOT_AVAILABLE",
            )
        )
