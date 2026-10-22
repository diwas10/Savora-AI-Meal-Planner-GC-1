"""Fictional server authority and trusted resolver, never application adapters."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from swap_oracle import make_case, repin
from test_planned_swap_contracts import rebuild
from test_swap_proof_contracts import limits
from test_weekly_contracts import evidence

from savora_ai.core.reasoning.compact_swap_material import (
    authority_reference,
    digest,
    original_slots,
    saved_binding,
)
from savora_ai.schemas.compact_swap import (
    AuthorityReference,
    CompactAuthorizedCandidate,
    CompactCombinationSource,
    CompactPortionSource,
    CompactRankEntry,
    CompactReplacement,
    CompactSourceReference,
    CompactSwapAuthority,
    CompactSwapInput,
    CompactTargetSnapshot,
    Preset,
)
from savora_ai.schemas.daily import DailySourceReference
from savora_ai.schemas.nutrients_v2 import NutrientMeasurementV2, OptionNutrientsV2, native_unit
from savora_ai.schemas.planned_swap import SwapSelectionLimits


@dataclass
class FakeResolver:
    authority: Any
    sources: Any
    fail: bool = False

    def load_authority(self, binding):
        if self.fail:
            raise LookupError("fictional unavailable authority")
        return self.authority

    def resolve(self, catalogue_version, ids):
        if self.fail:
            raise LookupError("fictional unavailable release")
        return self.sources


def package_case(case, bands=()):
    """Install a fictional full target snapshot; never invent saved proof metadata."""
    ctx = case["context"]
    target = CompactTargetSnapshot(
        profile_id=ctx.profile_id,
        profile_version=ctx.profile_version,
        calculator_payload={"fixture": "fictional-general-target"},
        bands=bands,
    )
    target_ref = case["saved_plan"].snapshot.target.model_copy(
        update={"content_digest": digest(target)}
    )
    snapshot = rebuild(case["saved_plan"].snapshot, target=target_ref)
    saved = rebuild(
        case["saved_plan"],
        snapshot=snapshot,
        reference=case["saved_plan"].reference.model_copy(
            update={"snapshot_digest": snapshot.content_digest}
        ),
    )
    bridge = rebuild(case["bridge"], target_release=target_ref)
    request = rebuild(case["request"], target_release=target_ref)
    case = repin(case, saved_plan=saved, bridge=bridge, request=request)
    by_combination = {}
    originals = {
        o.reference.model_dump_json(): o for o in snapshot.original_sources.daily_source.options
    }
    for option in case["sources"].options:
        mapping = next(m for m in case["bridge"].mappings if m.projected == option.reference)
        original = (
            None if mapping.original is None else originals[mapping.original.model_dump_json()]
        )
        portions = by_combination.setdefault(option.reference.combination_id, [])
        presets: tuple[Preset, ...] = (
            "STANDARD",
            "HIGHER_PROTEIN",
            "LOWER_CARB",
            "LOWER_ENERGY",
            "HIGHER_ENERGY",
        )
        reference = option.reference if original is None else original.reference
        source = DailySourceReference(
            source_id="fictional-native", version="1", content_digest="a" * 64
        )
        names = (
            "energy_kcal",
            "protein_g",
            "carbs_g",
            "fat_g",
            "saturated_fat_g",
            "sodium_mg",
            "sugars_g",
        )
        vector = OptionNutrientsV2(
            option=reference,
            basis="ABSOLUTE_FIXED_PORTION",
            reference_basis="VALIDATED_ABSOLUTE_AGGREGATE",
            mass_g=None,
            measurements=tuple(
                NutrientMeasurementV2.model_validate(
                    dict(
                        nutrient=n,
                        unit=native_unit(n),
                        value="10",
                        complete=True,
                        source=source,
                        evidence=(evidence(),),
                    )
                )
                for n in names
            ),
        )
        portions.append(
            CompactPortionSource(
                preset=presets[len(portions)], original=original, projected=option, nutrients=vector
            )
        )
    sources = tuple(
        CompactCombinationSource(
            catalogue_version=ctx.expected_catalogue_version,
            combination_id=cid,
            portions=tuple(portions),
        )
        for cid, portions in sorted(by_combination.items())
    )
    candidates = tuple(
        CompactAuthorizedCandidate(
            candidate_id=p.projected.reference.option_id,
            priority=i,
            combination_id=s.combination_id,
            portion_preset=p.preset,
        )
        for s in sources
        for i, p in enumerate(s.portions)
    )
    ranking = AuthorityReference(
        record_id="fictional-ranking",
        version="1",
        content_digest=digest([e.model_dump(mode="json", by_alias=True) for e in candidates]),
    )
    authority = CompactSwapAuthority(
        authenticated_user_id="fictional-owner",
        owner_id="fictional-owner",
        current_profile_id=ctx.profile_id,
        current_profile_version=ctx.profile_version,
        target_snapshot=target,
        ranking=ranking,
        candidates=candidates,
        limits=SwapSelectionLimits.model_validate(limits(selection=True)),
        **case,
    )
    return authority, sources


@lru_cache
def fixture():
    return package_case(make_case())


def compact_input(authority, sources, mode: Literal["B1", "B2"] = "B1"):
    target = authority.request.target
    candidate = authority.candidates[-1]
    return CompactSwapInput(
        mode=mode,
        saved_plan=saved_binding(authority),
        authority=authority_reference(authority),
        catalogue_version=authority.context.expected_catalogue_version,
        sources=tuple(
            CompactSourceReference(
                catalogue_version=s.catalogue_version,
                combination_id=s.combination_id,
                content_digest=digest(s),
            )
            for s in sources
        ),
        slots=original_slots(authority, sources),
        target_slot_id=f"D{target.day.day_index}_{target.slot.value}",
        replacement=CompactReplacement(
            combination_id=candidate.combination_id, portion_preset=candidate.portion_preset
        )
        if mode == "B1"
        else None,
        ranking=authority.ranking if mode == "B2" else None,
        candidates=tuple(
            CompactRankEntry(candidate_id=e.candidate_id, priority=e.priority)
            for e in authority.candidates
        )
        if mode == "B2"
        else (),
    )
