"""Reproducible real-sized transport fixture with explicitly fictional server authority.

Uses real portion configurations and native vectors, the stand-in KB and fictional
owner/profile/target data. It supplies no clinical or production authorization.
"""

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from savora_ai.core.meal_composition.member2_adapter import (
    KnowledgeBinding,
    evidence,
    meal_option,
    option_id,
)
from savora_ai.core.pipelines.catalogue import load_catalogue_export
from savora_ai.core.pipelines.planning import _ranked_meals, _rotation, _standard
from savora_ai.core.pipelines.profile import DietPattern, PlanningProfile
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
from savora_ai.evals.real_catalogue_inputs import build_real_week_inputs
from savora_ai.evals.saved_plan_fixture import saved_fixture
from savora_ai.schemas import planned_swap as s
from savora_ai.schemas.candidates import RuleContext
from savora_ai.schemas.compact_swap import (
    AuthorityReference,
    CompactAuthorizedCandidate,
    CompactCombinationSource,
    CompactPortionSource,
    CompactRankEntry,
    CompactReplacement,
    CompactSavedPlanBinding,
    CompactSourceReference,
    CompactSwapAuthority,
    CompactSwapInput,
    CompactSwapResult,
    CompactTargetSnapshot,
)
from savora_ai.schemas.daily import DailyMealOption, DailySourceReference
from savora_ai.schemas.enums import CuisinePolicy
from savora_ai.schemas.knowledge_base import KnowledgeWorkflow
from savora_ai.schemas.nutrients_v2 import NutrientMeasurementV2, OptionNutrientsV2, native_unit
from savora_ai.schemas.swap_envelope_policy import (
    COMPACT_SWAP_RECONSTRUCTION_POLICY,
    compact_swap_reconstruction,
)


@dataclass(frozen=True)
class FixtureResolver:
    """In-memory fake. Runtime resolver, authentication and persistence belong to M1."""

    authority: CompactSwapAuthority
    sources: tuple[CompactCombinationSource, ...]

    def load_authority(self, binding: CompactSavedPlanBinding) -> CompactSwapAuthority:
        return self.authority

    def resolve(
        self, catalogue_version: str, ids: tuple[str, ...]
    ) -> tuple[CompactCombinationSource, ...]:
        if catalogue_version != self.authority.context.expected_catalogue_version:
            raise LookupError("unknown fixture release")
        return tuple(s for s in self.sources if s.combination_id in ids)


def build_fixture(directory: Path) -> tuple[CompactSwapInput, CompactSwapInput, FixtureResolver]:
    bundle = load_catalogue_export(directory)
    profile = PlanningProfile(
        profile_id="compact-real-fixture-profile",
        profile_version=1,
        diet=DietPattern.VEGETARIAN,
        cuisine_policy=CuisinePolicy.STRICT,
        cuisines=("Indian",),
    )
    _, by_meal = _ranked_meals(bundle, profile, None)
    chosen = {}
    for slot, combo in _rotation(by_meal).items():
        config = _standard(combo)
        if config is None:
            raise ValueError("missing real STANDARD configuration")
        chosen[slot] = (combo, config)
    inputs = build_real_week_inputs(
        bundle, profile, "compact-real-week", date(2026, 10, 26), chosen
    )
    with compact_swap_reconstruction(COMPACT_SWAP_RECONSTRUCTION_POLICY):
        saved = saved_fixture(inputs)
        target_snapshot = CompactTargetSnapshot(
            profile_id=inputs.context.profile_id,
            profile_version=inputs.context.profile_version,
            calculator_payload={"fixture": "fictional target; no enabled nutrient bands"},
            bands=(),
        )
        target_ref = saved.snapshot.target.model_copy(
            update={"content_digest": digest(target_snapshot)}
        )
        snapshot_body: dict[str, object] = saved.snapshot.model_dump(exclude={"content_digest"})
        snapshot_body["target"] = target_ref
        snapshot = s.SavedPlanSnapshot.build(snapshot_body)
        saved = s.SavedPlanMaterial.build(
            dict(
                snapshot=snapshot,
                reference=saved.reference.model_copy(
                    update={"snapshot_digest": snapshot.content_digest}
                ),
            )
        )
        body = inputs.context.model_dump(exclude={"content_digest"})
        body.update(context_id="compact-real-swap-context", workflow=KnowledgeWorkflow.PLANNED_SWAP)
        provisional = inputs.context.model_copy(update={"context_id": body["context_id"]})
        _facts_projection(body["facts"], inputs.context, provisional)
        context = RuleContext.build(body)
        options = []
        mappings = []
        for old in inputs.weekly.daily_source.options:
            cb = old.combination.model_dump(exclude={"content_digest"})
            cb.update(
                context_id=context.context_id,
                context_version=context.version,
                context_digest=context.content_digest,
            )
            combo = type(old.combination).build(cb)
            ref = old.reference.model_copy(update={"combination_digest": combo.content_digest})
            projected = DailyMealOption(
                reference=ref,
                combination=combo,
                suitability=None
                if old.suitability is None
                else old.suitability.model_copy(update={"option": ref}),
                measurements=tuple(
                    m.model_copy(update={"option": ref, "components": combo.components})
                    for m in old.measurements
                ),
            )
            options.append(projected)
            mappings.append(
                s.SwapOptionProjection(
                    original=old.reference,
                    projected=ref,
                    evidence=(evidence(bundle.version, "fixture"),),
                )
            )
        # Change a real available portion of the target's combination. No preset is
        # invented and component occurrences remain unchanged by this portion swap.
        first = saved.snapshot.slots[0].option
        combination = bundle.combinations[first.reference.combination_id]
        config = next(
            c
            for c in combination.configurations
            if option_id(c) != first.reference.option_id
            and c.nutrition is not None
            and all(
                getattr(c.nutrition.totals, "carbohydrate_g" if n == "carbs_g" else n) is not None
                for n in NUTRIENTS
            )
        )
        replacement = meal_option(
            combination,
            config,
            inputs.candidates,
            bundle.dishes,
            KnowledgeBinding(knowledge=inputs.knowledge, context=context),
            inputs.provider,
        )
        options.append(replacement)
        ev = (evidence(bundle.version, "fictional-compact-authority"),)
        mappings.append(
            s.SwapOptionProjection(original=None, projected=replacement.reference, evidence=ev)
        )
        sources = s.PlannedSwapSourceSnapshot.build(
            dict(
                record_id="compact-real-source",
                version="1",
                context=context,
                candidates=tuple(inputs.candidates.values()),
                options=tuple(options),
                evidence=ev,
            )
        )
        locks = s.SavedPlanLockInventory.build(
            dict(
                record_id="compact-real-locks",
                version="1",
                revision=1,
                saved_plan=saved.reference,
                entries=(),
                evidence=ev,
            )
        )
        target = saved.snapshot.slots[0].identity
        permission = s.SwapTargetPermission.build(
            dict(
                record_id="compact-real-permission",
                version="1",
                saved_plan=saved.reference,
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
                record_id="compact-real-bridge",
                version="1",
                saved_plan=saved.reference,
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
                record_id="compact-real-request",
                version="1",
                saved_plan=saved.reference,
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
        grouped = {}
        for option in options:
            cid = option.reference.combination_id
            cfg = next(
                c
                for c in bundle.combinations[cid].configurations
                if option_id(c) == option.reference.option_id
            )
            original = originals.get(option.reference.option_id)
            native_source = DailySourceReference(
                source_id="native-"
                + hashlib.sha256(option.reference.option_id.encode()).hexdigest()[:32],
                version=bundle.version,
                content_digest=digest(cfg),
            )
            measurements = []
            if cfg.nutrition is None:
                raise ValueError("fixture configuration has no validated nutrition")
            for name in NUTRIENTS:
                value = getattr(
                    cfg.nutrition.totals, "carbohydrate_g" if name == "carbs_g" else name
                )
                measurements.append(
                    NutrientMeasurementV2(
                        nutrient=name,
                        unit=native_unit(name),
                        value=None if value is None else str(value),
                        complete=value is not None,
                        source=native_source,
                        evidence=ev,
                    )
                )
            vector = OptionNutrientsV2(
                option=option.reference if original is None else original.reference,
                basis="ABSOLUTE_FIXED_PORTION",
                reference_basis="VALIDATED_ABSOLUTE_AGGREGATE",
                mass_g=None,
                measurements=tuple(measurements),
            )
            grouped.setdefault(cid, []).append(
                CompactPortionSource(
                    preset=cfg.preset.value, original=original, projected=option, nutrients=vector
                )
            )
        compact_sources = tuple(
            CompactCombinationSource(
                catalogue_version=bundle.version, combination_id=cid, portions=tuple(portions)
            )
            for cid, portions in sorted(grouped.items())
        )
        candidates = (
            CompactAuthorizedCandidate(
                candidate_id=replacement.reference.option_id,
                priority=0,
                combination_id=combination.combination_id,
                portion_preset=config.preset.value,
            ),
        )
        ranking = AuthorityReference(
            record_id="compact-real-ranking",
            version="1",
            content_digest=digest([c.model_dump(mode="json", by_alias=True) for c in candidates]),
        )
        authority = CompactSwapAuthority(
            authenticated_user_id="fictional-owner",
            owner_id="fictional-owner",
            current_profile_id=context.profile_id,
            current_profile_version=context.profile_version,
            saved_plan=saved,
            target_snapshot=target_snapshot,
            request=request,
            locks=locks,
            permission=permission,
            knowledge=inputs.knowledge,
            context=context,
            sources=sources,
            bridge=bridge,
            ranking=ranking,
            candidates=candidates,
            limits=s.SwapSelectionLimits(
                max_reserved_work=s.SwapWork(**{f: 1_000_000 for f in s.SwapWork.model_fields}),
                max_proof_records=1024,
                max_proof_bytes=1_048_576,
                max_result_bytes=1_048_576,
                max_full_validations=51,
                max_domain_visits=50,
            ),
        )
        common: dict[str, Any] = dict(
            saved_plan=saved_binding(authority),
            authority=authority_reference(authority),
            catalogue_version=bundle.version,
            sources=tuple(
                CompactSourceReference(
                    catalogue_version=s.catalogue_version,
                    combination_id=s.combination_id,
                    content_digest=digest(s),
                )
                for s in compact_sources
            ),
            slots=original_slots(authority, compact_sources),
            target_slot_id="D1_BREAKFAST",
        )
        b1 = CompactSwapInput(
            mode="B1",
            replacement=CompactReplacement(
                combination_id=combination.combination_id, portion_preset=config.preset.value
            ),
            ranking=None,
            candidates=(),
            **common,
        )
        b2 = CompactSwapInput(
            mode="B2",
            replacement=None,
            ranking=ranking,
            candidates=(CompactRankEntry(candidate_id=candidates[0].candidate_id, priority=0),),
            **common,
        )
    return b1, b2, FixtureResolver(authority, compact_sources)


def assert_literal_changed_day(
    bundle, request: CompactSwapInput, result: CompactSwapResult
) -> None:
    """Independent Decimal arithmetic over M1 configurations, no native kernel calls."""
    start = 3 * (int(request.target_slot_id.split("_")[0][1:]) - 1)
    vectors = []
    for slot in request.slots[start : start + 3]:
        cid = slot.combination_id
        preset = slot.portion_preset
        if slot.slot_id == request.target_slot_id:
            cid = result.replacement_combination_id
            preset = result.replacement_portion_preset
        config = next(
            c for c in bundle.combinations[cid].configurations if c.preset.value == preset
        )
        assert config.nutrition is not None
        vectors.append(config.nutrition.totals)
    for total in result.changed_day_totals:
        name = "carbohydrate_g" if total.nutrient == "carbs_g" else total.nutrient
        values = [getattr(v, name) for v in vectors]
        expected = None if None in values else sum(Decimal(str(v)) for v in values)
        assert (None if total.value is None else Decimal(total.value)) == expected
        assert total.complete == (expected is not None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    b1, b2, resolver = build_fixture(args.catalogue)
    literal_bundle = load_catalogue_export(args.catalogue)
    results = {}
    for name, request in (("b1", b1), ("b2", b2)):
        result = execute_compact_swap(request, resolver, clock=lambda: 0.0)
        check = verify_compact_swap(request, result, resolver, clock=lambda: 0.0)
        if result.status != "VALID" or not result.verification_complete or not check.accepted:
            raise RuntimeError(
                f"{name} fixture failed: {result.status}/{result.reason}/{check.reason}"
            )
        assert_literal_changed_day(literal_bundle, request, result)
        results[name] = dict(
            input=request.model_dump(mode="json", by_alias=True),
            expectedResult=result.model_dump(mode="json", by_alias=True),
            independentVerification=check.model_dump(mode="json", by_alias=True),
            inputBytes=len(request.model_dump_json(by_alias=True).encode()),
            outputBytes=len(result.model_dump_json(by_alias=True).encode()),
        )
    record = dict(
        status="REAL_SOURCES_FICTIONAL_AUTHORITY_STAND_IN_KB_ONLY",
        catalogueVersion=b1.catalogue_version,
        sourceFiles={
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(args.catalogue.glob(b1.catalogue_version + "*.json"))
        },
        examples=results,
    )
    args.output.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                k: dict(
                    status=v["expectedResult"]["status"],
                    verified=v["independentVerification"]["accepted"],
                    inputBytes=v["inputBytes"],
                    outputBytes=v["outputBytes"],
                    reconstructedBytes=v["expectedResult"]["reconstructedBytes"],
                )
                for k, v in results.items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
