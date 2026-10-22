"""Independent structural swap fixtures; never execute a solver or rule predicate."""

import copy
import hashlib
import json
from enum import StrEnum
from typing import Any

import pytest
from pydantic import ValidationError
from test_weekly_contracts import evidence, packet

from savora_ai.core.reasoning.planned_swap import (
    build_swap_check_manifest,
    validate_saved_plan_material,
)
from savora_ai.schemas import planned_swap as s
from savora_ai.schemas.candidates import VersionedFact, validate_contract_json
from savora_ai.schemas.combinations import RecipeSnapshotReference
from savora_ai.schemas.daily import AssignedMeal, DailyAssignment, DailyMealOption, MealSlot
from savora_ai.schemas.daily_solver import DailyTrial, DailyTrialChoice
from savora_ai.schemas.knowledge_base import KnowledgeWorkflow
from savora_ai.schemas.weekly import (
    WeeklyAssignment,
    WeeklyDayAssignment,
    WeeklyTrial,
    WeeklyTrialChoice,
    _daily_request,
)


def reference(record: Any, record_id: str | None = None) -> s.SwapReference:
    return s.SwapReference(
        record_id=record_id or record.record_id,
        version=record.version,
        content_digest=record.content_digest,
    )


def rebuild(record: Any, **changes: Any) -> Any:
    return type(record).build(record.model_dump(exclude={"content_digest"}) | changes)


def projected_option(old: Any, context: Any, candidate: Any) -> DailyMealOption:
    recipe = RecipeSnapshotReference(
        recipe_id=candidate.recipe_id,
        recipe_version=candidate.recipe_version,
        snapshot_id=candidate.snapshot_id,
        snapshot_version=candidate.snapshot_version,
        content_digest=candidate.content_digest,
        catalogue_version=candidate.catalogue_version,
    )
    components = tuple(
        part.model_copy(
            update={
                "recipe_snapshot": recipe,
                "preparation": part.preparation.model_copy(update={"recipe_snapshot": recipe}),
            }
        )
        for part in old.combination.components
    )
    combo = rebuild(
        old.combination,
        context_id=context.context_id,
        context_version=context.version,
        context_digest=context.content_digest,
        components=components,
    )
    ref = old.reference.model_copy(update={"combination_digest": combo.content_digest})
    return DailyMealOption(
        reference=ref,
        combination=combo,
        suitability=old.suitability.model_copy(update={"option": ref}),
        measurements=tuple(
            m.model_copy(update={"option": ref, "components": components}) for m in old.measurements
        ),
    )


def foundation_case(context_bound: bool = False) -> dict[str, Any]:
    data = packet()
    if context_bound:
        ctx = data["context"]
        candidate = data["candidate"]
        candidate = rebuild(
            candidate,
            context_id=ctx.context_id,
            context_version=ctx.version,
            facts=tuple(
                f.model_copy(update={"context_id": ctx.context_id, "context_version": ctx.version})
                for f in candidate.facts
            ),
        )
        old_daily = data["daily"]
        daily = rebuild(
            old_daily, options=tuple(projected_option(o, ctx, candidate) for o in old_daily.options)
        )
        daily_ref = data["source"].expected_daily_source.model_copy(
            update={"content_digest": daily.content_digest}
        )
        source = rebuild(data["source"], daily_source=daily, expected_daily_source=daily_ref)
        # Rebind original domains to their independently built context-bound option references.
        req = data["request"]
        days = tuple(
            d.model_copy(
                update={
                    "domains": tuple(
                        domain.model_copy(
                            update={"options": tuple(o.reference for o in daily.options)}
                        )
                        for domain in d.domains
                    )
                }
            )
            for d in req.days
        )
        req = rebuild(
            req,
            source=source,
            expected_source=req.expected_source.model_copy(
                update={"content_digest": source.content_digest}
            ),
            days=days,
        )
        data = data | dict(candidate=candidate, daily=daily, source=source, request=req)
    request, sources, old_context = data["request"], data["source"], data["context"]
    candidate = data["candidate"]
    option = data["daily"].options[0]
    days = []
    choices = []
    for day in request.days:
        daily = _daily_request(request, day)
        trial = DailyTrial.build(
            dict(
                request_digest=daily.content_digest,
                choices=tuple(
                    DailyTrialChoice(slot=slot, option=option.reference) for slot in MealSlot
                ),
            )
        )
        assignment = DailyAssignment.build(
            dict(
                request_digest=daily.content_digest,
                day_id=day.day.day_id,
                source=sources.expected_daily_source,
                context_digest=old_context.content_digest,
                slots=tuple(AssignedMeal(slot=slot, option=option.reference) for slot in MealSlot),
            )
        )
        days.append(WeeklyDayAssignment(day=day.day, trial=trial, assignment=assignment))
        choices.extend(
            WeeklyTrialChoice(day=day.day, slot=slot, option=option.reference) for slot in MealSlot
        )
    trial = WeeklyTrial.build(
        dict(
            request_digest=request.content_digest,
            week_id=request.week_id,
            week_version=request.week_version,
            start_date=request.start_date,
            choices=tuple(choices),
        )
    )
    assignment = WeeklyAssignment.build(
        dict(
            request_digest=request.content_digest,
            week_id=request.week_id,
            week_version=request.week_version,
            start_date=request.start_date,
            source=request.expected_source,
            daily_source=sources.expected_daily_source,
            context_digest=old_context.content_digest,
            days=tuple(days),
        )
    )
    ev = (evidence(),)
    slots = tuple(
        s.SavedSlotPayload(
            identity=s.SwapSlotIdentity(day=c.day, slot=c.slot),
            source=reference(sources, sources.source_id),
            option=option,
            recipes=(candidate,),
        )
        for c in choices
    )
    target = s.SyntheticTargetReference(
        target_id="synthetic-target", version="1", content_digest="d" * 64, evidence=ev
    )
    snapshot = s.SavedPlanSnapshot.build(
        dict(
            plan_id="saved-plan",
            snapshot_id="saved-snapshot",
            version="1",
            original_request=request,
            original_sources=sources,
            original_context=old_context,
            original_candidates=(candidate,),
            original_trial=trial,
            original_assignment=assignment,
            slots=slots,
            target=target,
            verification=s.SavedPlanVerificationRecord(
                status="UNVERIFIED",
                prior_protocol=None,
                prior_result=None,
                verification_policy="synthetic-history.v1",
                evidence=ev,
            ),
            evidence=ev,
        )
    )
    saved_ref = s.SavedPlanReference(
        plan_id=snapshot.plan_id,
        effective_revision=1,
        snapshot_id=snapshot.snapshot_id,
        snapshot_version=snapshot.version,
        snapshot_digest=snapshot.content_digest,
    )
    saved = s.SavedPlanMaterial.build(dict(snapshot=snapshot, reference=saved_ref))
    facts = tuple(
        VersionedFact.model_validate(
            f.model_dump() | dict(subject_id="swap-context", context_id="swap-context")
        )
        for f in old_context.facts
    )
    context = rebuild(
        old_context, context_id="swap-context", workflow=KnowledgeWorkflow.PLANNED_SWAP, facts=facts
    )
    projected_candidate = candidate
    if context_bound:
        projected_candidate = rebuild(
            candidate,
            context_id=context.context_id,
            context_version=context.version,
            facts=tuple(
                f.model_copy(
                    update={"context_id": context.context_id, "context_version": context.version}
                )
                for f in candidate.facts
            ),
        )
    options = [projected_option(old, context, projected_candidate) for old in data["daily"].options]
    swap_sources = s.PlannedSwapSourceSnapshot.build(
        dict(
            record_id="swap-sources",
            version="1",
            context=context,
            candidates=(projected_candidate,),
            options=tuple(options),
            evidence=ev,
        )
    )
    locks = s.SavedPlanLockInventory.build(
        dict(
            record_id="saved-locks",
            version="1",
            revision=1,
            saved_plan=saved_ref,
            entries=(),
            evidence=ev,
        )
    )
    permission = s.SwapTargetPermission.build(
        dict(
            record_id="target-grant",
            version="1",
            saved_plan=saved_ref,
            locks=reference(locks),
            target=slots[0].identity,
            context=reference(context, context.context_id),
            profile_id=context.profile_id,
            profile_version=context.profile_version,
            authority=evidence(),
        )
    )
    kb_ref = reference(data["kb"], data["kb"].kb_id)
    bridge = s.PlannedSwapWorkflowBridge.build(
        dict(
            record_id="swap-bridge",
            version="1",
            saved_plan=saved_ref,
            original_context=reference(old_context, old_context.context_id),
            original_source=reference(sources, sources.source_id),
            swap_context=reference(context, context.context_id),
            swap_source=reference(swap_sources),
            knowledge=kb_ref,
            target_release=target,
            mappings=tuple(
                s.SwapOptionProjection(original=old.reference, projected=new.reference, evidence=ev)
                for old, new in zip(data["daily"].options, options, strict=True)
            ),
            evidence=ev,
        )
    )
    swap_request = s.PlannedSwapRequest.build(
        dict(
            record_id="swap-request",
            version="1",
            saved_plan=saved_ref,
            locks=reference(locks),
            permission=reference(permission),
            sources=reference(swap_sources),
            bridge=reference(bridge),
            context=reference(context, context.context_id),
            knowledge=kb_ref,
            target_release=target,
            target=slots[0].identity,
        )
    )
    return dict(
        request=swap_request,
        saved_plan=saved,
        locks=locks,
        permission=permission,
        knowledge=data["kb"],
        context=context,
        sources=swap_sources,
        bridge=bridge,
    )


@pytest.fixture(scope="module")
def swap_case() -> dict[str, Any]:
    return foundation_case()


def proposed(case: dict[str, Any]) -> s.SwapPlanSnapshot:
    slots = list(case["saved_plan"].snapshot.slots)
    option = case["sources"].options[1]
    slots[0] = s.SavedSlotPayload(
        identity=slots[0].identity,
        source=reference(case["sources"]),
        option=option,
        recipes=case["sources"].candidates,
    )
    return s.SwapPlanSnapshot.build(
        dict(
            base=case["saved_plan"],
            request=case["request"],
            sources=case["sources"],
            projected_replacement=option.reference,
            slots=tuple(slots),
        )
    )


def test_independent_helpers_never_evaluate(swap_case, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("semantic execution forbidden in Package A")

    from savora_ai.core.reasoning import (
        combinations,
        daily,
        evaluation,
        filtering,
        weekly,
        weekly_search_v2,
    )

    for module, name in (
        (combinations, "evaluate_combination"),
        (daily, "solve_daily_plan"),
        (evaluation, "evaluate_rule_checks"),
        (filtering, "filter_candidates"),
        (weekly, "evaluate_weekly_trial"),
        (weekly, "solve_weekly_plan"),
        (weekly_search_v2, "solve_weekly_plan_v2"),
    ):
        monkeypatch.setattr(module, name, forbidden)
    saved = swap_case["saved_plan"]
    snap = saved.snapshot
    report = validate_saved_plan_material(
        saved,
        knowledge=swap_case["knowledge"],
        original_context=snap.original_context,
        original_sources=snap.original_sources,
        original_candidates=snap.original_candidates,
    )
    assert report.semantic_assessment == report.historical_authentication == "NOT_EVALUATED"
    manifest = build_swap_check_manifest(**swap_case)
    assert len(manifest.locked_slots) == 20 and manifest.target_lock_kinds == ()
    assert set(manifest.required_checks) == set(swap_case["knowledge"].rules)
    assert manifest.semantic_assessment == "NOT_EVALUATED"


def test_non_circular_hashes_are_independently_recomputable(swap_case):
    def encode(value):
        if isinstance(value, dict):
            return {k: encode(v) for k, v in value.items()}
        if isinstance(value, list):
            return sorted(
                (encode(v) for v in value),
                key=lambda v: json.dumps(v, sort_keys=True, separators=(",", ":")),
            )
        return value

    for model in (swap_case["saved_plan"].snapshot, swap_case["saved_plan"]):
        body = encode(model.model_dump(mode="json", by_alias=True, exclude={"content_digest"}))
        expected = hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
        ).hexdigest()
        assert model.content_digest == expected
    assert (
        swap_case["saved_plan"].reference.snapshot_digest
        == swap_case["saved_plan"].snapshot.content_digest
    )


@pytest.mark.parametrize("index", range(1, 21))
def test_each_implicit_lock_rejects_changed_payload(swap_case, index):
    result = proposed(swap_case)
    slots = list(result.slots)
    slots[index] = slots[index].model_copy(update={"option": result.slots[0].option})
    with pytest.raises(ValidationError):
        rebuild(result, slots=tuple(slots))


@pytest.mark.parametrize("kind", tuple(s.LockKind))
def test_target_locks_preserved_without_unlock_or_computed_rejection(swap_case, kind):
    case = swap_case.copy()
    case["locks"] = rebuild(
        case["locks"],
        entries=(
            s.SavedSlotLock(
                slot=case["request"].target,
                kind=kind,
                reason="Synthetic deny",
                authority=evidence(),
            ),
        ),
    )
    case["permission"] = rebuild(case["permission"], locks=reference(case["locks"]))
    case["request"] = rebuild(
        case["request"], locks=reference(case["locks"]), permission=reference(case["permission"])
    )
    manifest = build_swap_check_manifest(**case)
    assert manifest.target_lock_kinds == (kind,) and len(manifest.locked_slots) == 20
    assert not hasattr(manifest, "outcome")


@pytest.mark.parametrize(
    "field",
    (
        "saved_plan",
        "locks",
        "permission",
        "sources",
        "bridge",
        "context",
        "knowledge",
        "target_release",
    ),
)
def test_request_cannot_replace_independent_authority(swap_case, field):
    request = swap_case["request"]
    value = getattr(request, field)
    changed = value.model_copy(
        update={"snapshot_digest": "f" * 64}
        if field == "saved_plan"
        else {"content_digest": "f" * 64}
    )
    with pytest.raises(ValidationError):
        build_swap_check_manifest(**(swap_case | {"request": rebuild(request, **{field: changed})}))


@pytest.mark.parametrize(
    "field,value", [("profile_version", "other"), ("version", "2"), ("effective_revision", True)]
)
def test_stale_or_invalid_original_bindings(swap_case, field, value):
    saved = swap_case["saved_plan"]
    if field == "effective_revision":
        with pytest.raises(ValidationError):
            s.SavedPlanReference.model_validate(saved.reference.model_dump() | {field: value})
    else:
        original = saved.snapshot.original_context
        changes = {field: value}
        if field == "version":
            changes["facts"] = tuple(
                f.model_copy(update={"subject_version": value, "context_version": value})
                for f in original.facts
            )
        context = rebuild(original, **changes)
        with pytest.raises(ValidationError):
            validate_saved_plan_material(
                saved,
                knowledge=swap_case["knowledge"],
                original_context=context,
                original_sources=saved.snapshot.original_sources,
                original_candidates=saved.snapshot.original_candidates,
            )


def test_manifest_omission_and_weekly_relabelling_rejected(swap_case):
    manifest = build_swap_check_manifest(**swap_case)
    with pytest.raises(ValidationError):
        rebuild(manifest, required_checks=manifest.required_checks[:-1])
    original = swap_case["saved_plan"].snapshot.original_sources.daily_source
    with pytest.raises(ValidationError):
        rebuild(original, context=swap_case["context"])


def test_missing_permission_cannot_be_supplied_by_request(swap_case):
    case = swap_case.copy()
    case.pop("permission")
    with pytest.raises(TypeError):
        build_swap_check_manifest(**case)


@pytest.mark.parametrize(
    "attack", ("drop", "duplicate", "foreign-original", "no-origin", "changed-value")
)
def test_rehashed_projection_attack_rejected(swap_case, attack):
    case = swap_case.copy()
    bridge = case["bridge"]
    maps = list(bridge.mappings)
    if attack == "drop":
        maps = maps[1:]
    elif attack == "duplicate":
        maps.append(maps[0])
    elif attack == "foreign-original":
        maps[0] = maps[0].model_copy(
            update={"original": maps[0].original.model_copy(update={"option_id": "foreign"})}
        )
    elif attack == "no-origin":
        maps[0] = maps[0].model_copy(update={"original": None})
    else:
        source = case["sources"]
        options = list(source.options)
        old = options[0]
        options[0] = old.model_copy(
            update={"measurements": (old.measurements[0].model_copy(update={"value": 999}),)}
        )
        case["sources"] = rebuild(source, options=tuple(options))
        bridge = rebuild(bridge, swap_source=reference(case["sources"]))
    with pytest.raises(ValidationError):
        case["bridge"] = rebuild(bridge, mappings=tuple(maps))
        case["request"] = rebuild(
            case["request"], bridge=reference(case["bridge"]), sources=reference(case["sources"])
        )
        build_swap_check_manifest(**case)


@pytest.mark.parametrize("field", ("outcome", "accepted", "unlock", "changed_slots", "assessment"))
def test_request_affirmative_or_unlock_fields_forbidden(swap_case, field):
    with pytest.raises(ValidationError):
        rebuild(swap_case["request"], **{field: "PASS"})


def test_strict_original_json_and_unchecked_instances(swap_case):
    request = swap_case["request"]
    assert (
        validate_contract_json(s.PlannedSwapRequest, request.model_dump_json(by_alias=True))
        == request
    )
    raw = request.model_dump_json(by_alias=True)
    with pytest.raises(ValidationError):
        validate_contract_json(s.PlannedSwapRequest, '{"version":"1",' + raw[1:])
    unchecked = request.model_copy(update={"operation": "UNLOCK"})
    with pytest.raises(ValidationError):
        build_swap_check_manifest(**(swap_case | {"request": unchecked}))

    class Hostile(dict):
        def items(self):
            raise AssertionError("must not invoke hostile methods")

    with pytest.raises(ValidationError):
        s.PlannedSwapRequest.model_validate(Hostile(request.model_dump()))


def test_wrong_enum_rejected(swap_case):
    class Counterfeit(StrEnum):
        USER = "USER"

    with pytest.raises(ValidationError):
        s.SavedSlotLock.model_validate(
            dict(
                slot=swap_case["request"].target,
                kind=Counterfeit.USER,
                reason="x",
                authority=evidence(),
            )
        )


@pytest.mark.parametrize("change", ("duplicate", "reverse", "unfixed", "date"))
def test_original_slot_inventory_tampering(swap_case, change):
    snapshot = swap_case["saved_plan"].snapshot
    slots = list(snapshot.slots)
    if change == "duplicate":
        slots[-1] = slots[0]
    elif change == "reverse":
        slots.reverse()
    elif change == "unfixed":
        slots[0] = slots[0].model_copy(update={"option": packet(fixed=False)["daily"].options[0]})
    else:
        identity = slots[0].identity
        slots[0] = slots[0].model_copy(
            update={
                "identity": identity.model_copy(
                    update={"day": identity.day.model_copy(update={"calendar_date": "2026-10-20"})}
                )
            }
        )
    with pytest.raises(ValidationError):
        rebuild(snapshot, slots=tuple(slots))


def test_structural_result_and_noop(swap_case):
    result = proposed(swap_case)
    assert result.semantic_assessment == "NOT_EVALUATED"
    old = swap_case["sources"].options[0]
    slots = list(result.slots)
    slots[0] = slots[0].model_copy(update={"option": old})
    with pytest.raises(ValidationError):
        rebuild(result, projected_replacement=old.reference, slots=tuple(slots))


@pytest.mark.parametrize("bad", (0, -1, True, 1.0, "1", 1_000_001))
def test_revision_strictness(swap_case, bad):
    with pytest.raises(ValidationError):
        s.SavedPlanReference.model_validate(
            swap_case["saved_plan"].reference.model_dump() | {"effective_revision": bad}
        )


def test_snapshot_digest_forgery_and_native_alias_collision(swap_case):
    snapshot = swap_case["saved_plan"].snapshot
    body = snapshot.model_dump()
    body["content_digest"] = "a" * 64
    with pytest.raises(ValidationError):
        s.SavedPlanSnapshot.model_validate(body)
    body = swap_case["request"].model_dump()
    body["recordId"] = body["record_id"]
    with pytest.raises(ValidationError):
        s.PlannedSwapRequest.model_validate(body)
    payload = copy.deepcopy(swap_case["request"].model_dump())
    payload["unknown"] = "x" * 1_048_576
    with pytest.raises(ValidationError):
        validate_contract_json(s.PlannedSwapRequest, json.dumps(payload))


def test_independent_context_bound_counterparts_and_noop():
    case = foundation_case(context_bound=True)
    manifest = build_swap_check_manifest(**case)
    assert len(manifest.locked_slots) == 20 and manifest.semantic_assessment == "NOT_EVALUATED"
    result = proposed(case)
    option = case["sources"].options[0]
    slots = list(result.slots)
    slots[0] = s.SavedSlotPayload(
        identity=slots[0].identity,
        source=case["request"].sources,
        option=option,
        recipes=case["sources"].candidates,
    )
    with pytest.raises(ValidationError):
        rebuild(result, slots=tuple(slots), projected_replacement=option.reference)


def test_historical_verified_stamp_does_not_authorize_truth(swap_case):
    saved = swap_case["saved_plan"]
    stamp = s.SavedPlanVerificationRecord(
        status="VERIFIED_AT_SAVE",
        prior_protocol="computed-weekly-solve-result.v2",
        prior_result=s.SwapReference(
            record_id="unverified-claim", version="1", content_digest="a" * 64
        ),
        verification_policy="claimed-historical.v1",
        evidence=(evidence(),),
    )
    snapshot = rebuild(saved.snapshot, verification=stamp)
    material = rebuild(
        saved,
        snapshot=snapshot,
        reference=saved.reference.model_copy(update={"snapshot_digest": snapshot.content_digest}),
    )
    report = validate_saved_plan_material(
        material,
        knowledge=swap_case["knowledge"],
        original_context=snapshot.original_context,
        original_sources=snapshot.original_sources,
        original_candidates=snapshot.original_candidates,
    )
    assert report.historical_authentication == report.semantic_assessment == "NOT_EVALUATED"


@pytest.mark.parametrize("attack", ("target", "profile", "lock-revision", "workflow"))
def test_full_authority_body_mismatches(swap_case, attack):
    case = swap_case.copy()
    if attack == "target":
        case["permission"] = rebuild(
            case["permission"], target=case["saved_plan"].snapshot.slots[1].identity
        )
        case["request"] = rebuild(case["request"], permission=reference(case["permission"]))
    elif attack == "profile":
        case["permission"] = rebuild(case["permission"], profile_version="wrong")
        case["request"] = rebuild(case["request"], permission=reference(case["permission"]))
    elif attack == "lock-revision":
        case["locks"] = rebuild(case["locks"], revision=2)
    else:
        case["context"] = case["saved_plan"].snapshot.original_context
    with pytest.raises(ValidationError):
        build_swap_check_manifest(**case)


def test_noop_identity_ignores_component_declaration_order():
    old = packet(copies=2)["daily"].options[0]
    components = old.combination.components[::-1]
    combo = rebuild(old.combination, components=components)
    ref = old.reference.model_copy(update={"combination_digest": combo.content_digest})
    new = DailyMealOption(
        reference=ref,
        combination=combo,
        suitability=old.suitability.model_copy(update={"option": ref}),
        measurements=tuple(
            m.model_copy(update={"option": ref, "components": components}) for m in old.measurements
        ),
    )
    # The same two occurrence IDs, preparations and quantities describe the same meal.
    assert {p.component_id for p in old.combination.components} == {
        p.component_id for p in new.combination.components
    }
    assert s._fixed_meal_identity(old) == s._fixed_meal_identity(new)
