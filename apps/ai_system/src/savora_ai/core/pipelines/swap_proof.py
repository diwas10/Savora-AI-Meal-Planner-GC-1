"""Member 1's runtime adapter for Member 2's compact B1 swap proof (PR #21).

    prove_swap(profile, bundle, saved=..., slot="D2_LUNCH", replacement=..., plan_id=...,
               revision=..., owner_id=..., start_date=...)

After `substitute_slot` has chosen and CSP-checked a replacement, this re-checks the swap
as a real PLANNED_SWAP: Member 2's `execute_compact_swap` replays the original and the
proposed week from trusted material, and `verify_compact_swap` reconstructs the witness
independently. The material comes from the server's own catalogue bundle and the saved
plan the backend loaded for the authenticated owner; nothing comes from the client.

GC1 limits, all visible in the result:
- The KB is the stand-in, so a VALID proof certifies the stand-in's synthetic
  obligations, never clinical or allergy safety.
- The saved plan's history is UNVERIFIED (no VERIFIED_AT_SAVE certificate is stored), so
  both complete weeks are checked freshly, as Member 2's protocol requires.
- The target snapshot carries the profile's estimated day targets for the record, but no
  nutrient bands: the saved weeks are portion-fitted, not band-verified (ADR 0006), so a
  band would reject swaps for days the user never changed.
"""

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from time import monotonic
from typing import Any, Literal

from savora_ai.core.meal_composition.member2_adapter import (
    KnowledgeBinding,
    evidence,
    meal_option,
    option_id,
)
from savora_ai.core.meal_composition.models import MealCombination, PortionConfiguration
from savora_ai.core.pipelines.catalogue import CatalogueBundle
from savora_ai.core.pipelines.planning import _week_inputs, _WeekInputs
from savora_ai.core.pipelines.profile import PlanningProfile, _PipelineModel
from savora_ai.core.reasoning.compact_swap import (
    NUTRIENTS,
    execute_compact_swap,
    verify_compact_swap,
)
from savora_ai.core.reasoning.compact_swap_material import (
    authority_reference,
    digest,
    original_slots,
    saved_binding,
)
from savora_ai.core.reasoning.swap_material import (
    _context_ref,
    _facts_projection,
    _knowledge_ref,
    _ref,
    _source_ref,
)
from savora_ai.schemas import planned_swap as s
from savora_ai.schemas.candidates import RuleContext
from savora_ai.schemas.compact_swap import (
    CompactAuthorizedCandidate,
    CompactCombinationSource,
    CompactNutrientTotal,
    CompactPortionSource,
    CompactReplacement,
    CompactSavedPlanBinding,
    CompactSourceReference,
    CompactSwapAuthority,
    CompactSwapInput,
    CompactTargetSnapshot,
)
from savora_ai.schemas.daily import (
    AssignedMeal,
    DailyAssignment,
    DailyMealOption,
    DailySourceReference,
)
from savora_ai.schemas.daily_solver import DailyTrial, DailyTrialChoice
from savora_ai.schemas.knowledge_base import KnowledgeWorkflow
from savora_ai.schemas.nutrients_v2 import NutrientMeasurementV2, OptionNutrientsV2, native_unit
from savora_ai.schemas.swap_envelope_policy import (
    COMPACT_SWAP_RECONSTRUCTION_POLICY,
    compact_swap_reconstruction,
)
from savora_ai.schemas.weekly import (
    WeeklyAssignment,
    WeeklyDayAssignment,
    WeeklyTrial,
    WeeklyTrialChoice,
    _daily_request,
)

PROTOCOL = "compact-planned-swap-input.v1"
_Status = Literal["VALID", "REJECTED", "INSUFFICIENT_DATA", "TIMEOUT", "ADMISSION_FAILED"]
_Chosen = Mapping[str, tuple[MealCombination, PortionConfiguration]]


class SwapProof(_PipelineModel):
    """What to store on the substitution: the decision and its certificate binding."""

    protocol: str  # the compact input protocol checked
    status: _Status
    verified: bool  # executed VALID AND independently reconstructed and accepted
    reason: str
    certificate_digest: str | None
    input_digest: str
    changed_day_totals: tuple[CompactNutrientTotal, ...]  # exact native totals when VALID
    seconds: float


@dataclass(frozen=True)
class CatalogueResolver:
    """`TrustedSourceResolver` over one server-built authority and the catalogue bundle.

    Built per request from material the backend loaded for the authenticated owner; it
    answers only that binding and that catalogue release, never client-supplied bodies."""

    authority: CompactSwapAuthority
    sources: tuple[CompactCombinationSource, ...]

    def load_authority(self, binding: CompactSavedPlanBinding) -> CompactSwapAuthority:
        if binding != saved_binding(self.authority):
            raise LookupError("saved-plan binding differs from the server's authority")
        return self.authority

    def resolve(
        self, catalogue_version: str, ids: tuple[str, ...]
    ) -> tuple[CompactCombinationSource, ...]:
        if catalogue_version != self.authority.context.expected_catalogue_version:
            raise LookupError("unknown catalogue release")
        wanted = set(ids)
        return tuple(src for src in self.sources if src.combination_id in wanted)


def _saved_material(
    inputs: _WeekInputs, plan_id: str, revision: int, target: s.SyntheticTargetReference
) -> s.SavedPlanMaterial:
    """The saved week as one fixed option per slot, history UNVERIFIED (never invented)."""
    request, source, context = inputs.request, inputs.weekly, inputs.context
    days, choices, slots = [], [], []
    for day in request.days:
        daily = _daily_request(request, day)
        selected = tuple((d.slot, d.options[0]) for d in day.domains)
        trial = DailyTrial.build(
            dict(
                request_digest=daily.content_digest,
                choices=tuple(DailyTrialChoice(slot=sl, option=o) for sl, o in selected),
            )
        )
        assignment = DailyAssignment.build(
            dict(
                request_digest=daily.content_digest,
                day_id=day.day.day_id,
                source=source.expected_daily_source,
                context_digest=context.content_digest,
                slots=tuple(AssignedMeal(slot=sl, option=o) for sl, o in selected),
            )
        )
        days.append(WeeklyDayAssignment(day=day.day, trial=trial, assignment=assignment))
        for slot, ref in selected:
            option = inputs.options[ref.option_id]
            choices.append(WeeklyTrialChoice(day=day.day, slot=slot, option=ref))
            components = option.combination.components
            recipe_ids = sorted({p.recipe_snapshot.recipe_id for p in components})
            slots.append(
                s.SavedSlotPayload(
                    identity=s.SwapSlotIdentity(day=day.day, slot=slot),
                    source=s.SwapReference(
                        record_id=source.source_id,
                        version=source.version,
                        content_digest=source.content_digest,
                    ),
                    option=option,
                    recipes=tuple(inputs.candidates[i] for i in recipe_ids),
                )
            )
    common = dict(
        request_digest=request.content_digest,
        week_id=request.week_id,
        week_version=request.week_version,
        start_date=request.start_date,
    )
    week_trial = WeeklyTrial.build(dict(common, choices=tuple(choices)))
    week_assignment = WeeklyAssignment.build(
        dict(
            common,
            source=request.expected_source,
            daily_source=source.expected_daily_source,
            context_digest=context.content_digest,
            days=tuple(days),
        )
    )
    ev = (evidence(source.version, "m1-saved-plan-unverified-history"),)
    snapshot = s.SavedPlanSnapshot.build(
        dict(
            plan_id=plan_id,
            snapshot_id=f"{plan_id}-r{revision}",
            version=str(revision),
            original_request=request,
            original_sources=source,
            original_context=context,
            original_candidates=tuple(inputs.candidates.values()),
            original_trial=week_trial,
            original_assignment=week_assignment,
            slots=tuple(slots),
            target=target,
            verification=s.SavedPlanVerificationRecord(
                status="UNVERIFIED",
                prior_protocol=None,
                prior_result=None,
                verification_policy="m1-unverified-saved-history.v1",
                evidence=ev,
            ),
            evidence=ev,
        )
    )
    return s.SavedPlanMaterial.build(
        dict(
            snapshot=snapshot,
            reference=s.SavedPlanReference(
                plan_id=plan_id,
                effective_revision=revision,
                snapshot_id=snapshot.snapshot_id,
                snapshot_version=snapshot.version,
                snapshot_digest=snapshot.content_digest,
            ),
        )
    )


def _native(option: DailyMealOption, config: PortionConfiguration, ref, ev) -> OptionNutrientsV2:
    """The configuration's validated totals in native units; a missing value stays unknown."""
    source = DailySourceReference(
        source_id="native-" + hashlib.sha256(option.reference.option_id.encode()).hexdigest()[:32],
        version=option.combination.catalogue_version,
        content_digest=digest(config),
    )
    if config.nutrition is None:
        raise ValueError(f"{config.configuration_id} has no validated nutrition")
    measurements = []
    for name in NUTRIENTS:
        value = getattr(config.nutrition.totals, "carbohydrate_g" if name == "carbs_g" else name)
        measurements.append(
            NutrientMeasurementV2(
                nutrient=name,
                unit=native_unit(name),
                value=None if value is None else str(value),
                complete=value is not None,
                source=source,
                evidence=ev,
            )
        )
    return OptionNutrientsV2(
        option=ref,
        basis="ABSOLUTE_FIXED_PORTION",
        reference_basis="VALIDATED_ABSOLUTE_AGGREGATE",
        mass_g=None,
        measurements=tuple(measurements),
    )


def build_swap(
    profile: PlanningProfile,
    bundle: CatalogueBundle,
    *,
    saved: _Chosen,
    slot: str,
    replacement: tuple[MealCombination, PortionConfiguration],
    plan_id: str,
    revision: int,
    owner_id: str,
    start_date: date,
) -> tuple[CompactSwapInput, CatalogueResolver]:
    """The compact B1 input and its resolver for one saved slot's replacement."""
    combo, config = replacement
    extra = [p.dish_id for p in combo.components]
    inputs = _week_inputs(bundle, profile, f"{plan_id}-r{revision}", start_date, saved, extra)
    ev = (evidence(bundle.version, "m1-runtime-swap-authority"),)
    targets = None if profile.targets is None else profile.targets.model_dump(mode="json")
    target_snapshot = CompactTargetSnapshot(
        profile_id=inputs.context.profile_id,
        profile_version=inputs.context.profile_version,
        calculator_payload={"dayTargets": targets, "bandsEnforced": False},
        bands=(),
    )
    target_ref = s.SyntheticTargetReference(
        target_id=f"target-{inputs.context.profile_id}-{inputs.context.profile_version}",
        version="1",
        content_digest=digest(target_snapshot),
        evidence=ev,
    )
    material = _saved_material(inputs, plan_id, revision, target_ref)

    body: dict[str, Any] = inputs.context.model_dump(exclude={"content_digest"})
    body.update(context_id=f"{plan_id}-swap-{slot}", workflow=KnowledgeWorkflow.PLANNED_SWAP)
    provisional = inputs.context.model_copy(update={"context_id": body["context_id"]})
    _facts_projection(body["facts"], inputs.context, provisional)
    context = RuleContext.build(body)

    options: list[DailyMealOption] = []
    mappings: list[s.SwapOptionProjection] = []
    for old in inputs.weekly.daily_source.options:
        cb = old.combination.model_dump(exclude={"content_digest"})
        cb.update(
            context_id=context.context_id,
            context_version=context.version,
            context_digest=context.content_digest,
        )
        projected_combo = type(old.combination).build(cb)
        digest_update = {"combination_digest": projected_combo.content_digest}
        ref = old.reference.model_copy(update=digest_update)
        options.append(
            DailyMealOption(
                reference=ref,
                combination=projected_combo,
                suitability=None
                if old.suitability is None
                else old.suitability.model_copy(update={"option": ref}),
                measurements=tuple(
                    m.model_copy(update={"option": ref, "components": projected_combo.components})
                    for m in old.measurements
                ),
            )
        )
        mappings.append(s.SwapOptionProjection(original=old.reference, projected=ref, evidence=ev))
    new_id = option_id(config)
    if new_id not in {o.reference.option_id for o in options}:
        binding = KnowledgeBinding(knowledge=inputs.knowledge, context=context)
        new = meal_option(combo, config, inputs.candidates, bundle.dishes, binding, inputs.provider)
        options.append(new)
        mappings.append(s.SwapOptionProjection(original=None, projected=new.reference, evidence=ev))

    sources = s.PlannedSwapSourceSnapshot.build(
        dict(
            record_id=f"{plan_id}-swap-source",
            version="1",
            context=context,
            candidates=tuple(inputs.candidates.values()),
            options=tuple(options),
            evidence=ev,
        )
    )
    locks = s.SavedPlanLockInventory.build(
        dict(
            record_id=f"{plan_id}-locks",
            version="1",
            revision=1,
            saved_plan=material.reference,
            entries=(),
            evidence=ev,
        )
    )
    target = next(
        p.identity
        for p in material.snapshot.slots
        if f"D{p.identity.day.day_index}_{p.identity.slot.value}" == slot
    )
    permission = s.SwapTargetPermission.build(
        dict(
            record_id=f"{plan_id}-permission",
            version="1",
            saved_plan=material.reference,
            locks=_ref(locks),
            target=target,
            context=_context_ref(context),
            profile_id=context.profile_id,
            profile_version=context.profile_version,
            authority=ev[0],
        )
    )
    bridge = s.PlannedSwapWorkflowBridge.build(
        dict(
            record_id=f"{plan_id}-bridge",
            version="1",
            saved_plan=material.reference,
            original_context=_context_ref(inputs.context),
            original_source=_source_ref(inputs.weekly),
            swap_context=_context_ref(context),
            swap_source=_ref(sources),
            knowledge=_knowledge_ref(inputs.knowledge),
            target_release=target_ref,
            mappings=tuple(mappings),
            evidence=ev,
        )
    )
    request = s.PlannedSwapRequest.build(
        dict(
            record_id=f"{plan_id}-swap-request",
            version="1",
            saved_plan=material.reference,
            locks=_ref(locks),
            permission=_ref(permission),
            sources=_ref(sources),
            bridge=_ref(bridge),
            context=_context_ref(context),
            knowledge=_knowledge_ref(inputs.knowledge),
            target_release=target_ref,
            target=target,
        )
    )

    originals = {o.reference.option_id: o for o in inputs.weekly.daily_source.options}
    configs = {option_id(c): c for cb in bundle.combinations.values() for c in cb.configurations}
    grouped: dict[str, list[CompactPortionSource]] = {}
    for option in options:
        cfg = configs[option.reference.option_id]
        original = originals.get(option.reference.option_id)
        ref = option.reference if original is None else original.reference
        grouped.setdefault(option.reference.combination_id, []).append(
            CompactPortionSource(
                preset=cfg.preset.value,
                original=original,
                projected=option,
                nutrients=_native(option, cfg, ref, ev),
            )
        )
    compact_sources = tuple(
        CompactCombinationSource(
            catalogue_version=bundle.version, combination_id=cid, portions=tuple(portions)
        )
        for cid, portions in sorted(grouped.items())
    )
    authority = CompactSwapAuthority(
        authenticated_user_id=owner_id,
        owner_id=owner_id,
        current_profile_id=context.profile_id,
        current_profile_version=context.profile_version,
        saved_plan=material,
        target_snapshot=target_snapshot,
        request=request,
        locks=locks,
        permission=permission,
        knowledge=inputs.knowledge,
        context=context,
        sources=sources,
        bridge=bridge,
        ranking=None,
        candidates=(
            CompactAuthorizedCandidate(
                candidate_id=new_id,
                priority=0,
                combination_id=combo.combination_id,
                portion_preset=config.preset.value,
            ),
        ),
        limits=s.SwapSelectionLimits(
            max_reserved_work=s.SwapWork(**{f: 1_000_000 for f in s.SwapWork.model_fields}),
            max_proof_records=1024,
            max_proof_bytes=1_048_576,
            max_result_bytes=1_048_576,
            max_full_validations=51,
            max_domain_visits=50,
        ),
    )
    compact = CompactSwapInput(
        mode="B1",
        saved_plan=saved_binding(authority),
        authority=authority_reference(authority),
        catalogue_version=bundle.version,
        sources=tuple(
            CompactSourceReference(
                catalogue_version=src.catalogue_version,
                combination_id=src.combination_id,
                content_digest=digest(src),
            )
            for src in compact_sources
        ),
        slots=original_slots(authority, compact_sources),
        target_slot_id=slot,
        replacement=CompactReplacement(
            combination_id=combo.combination_id, portion_preset=config.preset.value
        ),
        ranking=None,
        candidates=(),
    )
    return compact, CatalogueResolver(authority, compact_sources)


def prove_swap(
    profile: PlanningProfile,
    bundle: CatalogueBundle,
    *,
    saved: Mapping[str, str],
    slot: str,
    replacement_option_id: str,
    plan_id: str,
    revision: int,
    owner_id: str,
    start_date: date,
    clock: Callable[[], float] = monotonic,
) -> SwapProof:
    """Execute and independently verify the B1 swap of `slot` to `replacement_option_id`.

    `saved` maps all 21 slot IDs to the saved plan's option IDs. Store the replacement
    only when the swap's own CSP run succeeded; this proof is recorded beside it."""
    started = clock()
    configs = {
        option_id(cfg): (combo, cfg)
        for combo in bundle.combinations.values()
        for cfg in combo.configurations
    }
    with compact_swap_reconstruction(COMPACT_SWAP_RECONSTRUCTION_POLICY):
        compact, resolver = build_swap(
            profile,
            bundle,
            saved={sid: configs[oid] for sid, oid in saved.items()},
            slot=slot,
            replacement=configs[replacement_option_id],
            plan_id=plan_id,
            revision=revision,
            owner_id=owner_id,
            start_date=start_date,
        )
    result = execute_compact_swap(compact, resolver, clock=clock)
    check = verify_compact_swap(compact, result, resolver, clock=clock)
    verified = result.status == "VALID" and result.verification_complete and check.accepted
    return SwapProof(
        protocol=PROTOCOL,
        status=result.status,
        verified=verified,
        reason=result.reason if check.accepted else f"{result.reason}; check: {check.reason}",
        certificate_digest=result.certificate_digest,
        input_digest=result.input_digest,
        changed_day_totals=result.changed_day_totals,
        seconds=round(clock() - started, 3),
    )
