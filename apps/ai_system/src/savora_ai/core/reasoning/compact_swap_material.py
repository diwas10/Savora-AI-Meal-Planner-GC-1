"""Trusted compact admission with exact, deduplicated canonical byte accounting."""

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from savora_ai.core.reasoning.compact_swap_resolver import TrustedSourceResolver
from savora_ai.core.reasoning.swap_material import _SwapInputs
from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.compact_swap import (
    AuthorityReference,
    CompactCombinationSource,
    CompactSavedPlanBinding,
    CompactSlot,
    CompactSwapAuthority,
    CompactSwapInput,
)
from savora_ai.schemas.compact_swap_canonical import (
    CompactCanonicalLimitError,
)
from savora_ai.schemas.compact_swap_canonical import (
    canonical_bytes as canonical_bytes,
)
from savora_ai.schemas.compact_swap_canonical import (
    canonical_material as encode_material,
)
from savora_ai.schemas.compact_swap_canonical import (
    digest as digest,
)
from savora_ai.schemas.swap_envelope_policy import (
    COMPACT_SWAP_RECONSTRUCTION_POLICY,
    compact_swap_reconstruction,
)

WIRE_BYTES = 1_048_576
MATERIAL_BYTES = 4_194_304


class CompactAdmissionError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def canonical_material(value: dict[str, Any]) -> bytes:
    try:
        return encode_material(value)
    except CompactCanonicalLimitError as error:
        raise CompactAdmissionError(error.code) from error


def authority_reference(authority: CompactSwapAuthority) -> AuthorityReference:
    return AuthorityReference(
        record_id=authority.request.record_id,
        version=authority.request.version,
        content_digest=digest(authority),
    )


def saved_binding(authority: CompactSwapAuthority) -> CompactSavedPlanBinding:
    saved = authority.saved_plan
    history = saved.snapshot.verification.prior_result
    return CompactSavedPlanBinding(
        plan_id=saved.reference.plan_id,
        revision=saved.reference.effective_revision,
        owner_id=authority.owner_id,
        profile_id=authority.current_profile_id,
        profile_version=authority.current_profile_version,
        snapshot_digest=saved.reference.snapshot_digest,
        target_snapshot_digest=digest(authority.target_snapshot),
        kb_id=authority.knowledge.kb_id,
        kb_version=authority.knowledge.version,
        kb_digest=authority.knowledge.content_digest,
        certificate_digest=None if history is None else history.content_digest,
    )


def original_slots(authority: CompactSwapAuthority, sources: tuple[CompactCombinationSource, ...]):
    by_option = {}
    for source in sources:
        for portion in source.portions:
            if portion.original is not None:
                key = portion.original.reference.model_dump_json()
                if key in by_option:
                    raise CompactAdmissionError("CONFLICTING_SOURCE")
                by_option[key] = (source, portion)
    slots = []
    for slot in authority.saved_plan.snapshot.slots:
        pair = by_option.get(slot.option.reference.model_dump_json())
        if pair is None or pair[1].original != slot.option:
            raise CompactAdmissionError("MISSING_SOURCE")
        source, portion = pair
        slots.append(
            CompactSlot(
                slot_id=f"D{slot.identity.day.day_index}_{slot.identity.slot.value}",
                combination_id=source.combination_id,
                portion_preset=portion.preset,
            )
        )
    return tuple(slots)


@dataclass(frozen=True)
class AdmittedCompactSwap:
    request: CompactSwapInput
    authority: CompactSwapAuthority
    sources: tuple[CompactCombinationSource, ...]
    material: bytes


def parse_input(payload: CompactSwapInput | str | bytes) -> CompactSwapInput:
    if isinstance(payload, CompactSwapInput):
        payload = payload.model_dump_json(by_alias=True)
    try:
        return validate_contract_json(CompactSwapInput, payload)
    except (ValidationError, ValueError, TypeError) as error:
        raise CompactAdmissionError("INVALID_INPUT") from error


def admit_compact_swap(
    payload: CompactSwapInput | str | bytes, resolver: TrustedSourceResolver
) -> AdmittedCompactSwap:
    request = parse_input(payload)
    try:
        # Resolver construction must itself use this bounded server-side policy for
        # historical saved material above 1 MiB. It does not raise output budgets.
        with compact_swap_reconstruction(COMPACT_SWAP_RECONSTRUCTION_POLICY):
            try:
                raw_authority = resolver.load_authority(request.saved_plan)
                raw_sources = resolver.resolve(
                    request.catalogue_version, tuple(s.combination_id for s in request.sources)
                )
            except Exception as error:
                raise CompactAdmissionError("RESOLVER_UNAVAILABLE") from error
            authority = CompactSwapAuthority.model_validate(raw_authority)
            if type(raw_sources) is not tuple:
                raise CompactAdmissionError("MALFORMED_SOURCE")
            sources = tuple(CompactCombinationSource.model_validate(s) for s in raw_sources)
            if (
                authority.authenticated_user_id != authority.owner_id
                or request.saved_plan != saved_binding(authority)
            ):
                raise CompactAdmissionError("STALE_AUTHORITY")
            if request.authority != authority_reference(authority):
                raise CompactAdmissionError("AUTHORITY_MISMATCH")
            saved = authority.saved_plan.snapshot
            if (
                saved.target.content_digest != digest(authority.target_snapshot)
                or authority.target_snapshot.profile_id != authority.current_profile_id
                or authority.target_snapshot.profile_version != authority.current_profile_version
                or saved.original_context.profile_id != authority.current_profile_id
                or saved.original_context.profile_version != authority.current_profile_version
            ):
                raise CompactAdmissionError("TARGET_PROFILE_MISMATCH")
            if any(
                b.source.content_digest != digest(authority.target_snapshot.calculator_payload)
                for b in authority.target_snapshot.bands
            ):
                raise CompactAdmissionError("TARGET_PROFILE_MISMATCH")
            if len({s.combination_id for s in sources}) != len(sources):
                raise CompactAdmissionError("CONFLICTING_SOURCE")
            expected = {s.combination_id: s for s in request.sources}
            if set(expected) != {s.combination_id for s in sources}:
                raise CompactAdmissionError("MISSING_SOURCE")
            pool = {o.reference.model_dump_json(): o for o in authority.sources.options}
            originals = {
                o.reference.model_dump_json(): o
                for o in saved.original_sources.daily_source.options
            }
            covered = set()
            for source in sources:
                pin = expected[source.combination_id]
                if source.catalogue_version != request.catalogue_version:
                    raise CompactAdmissionError("STALE_SOURCE")
                if pin.content_digest != digest(source):
                    raise CompactAdmissionError("SOURCE_DIGEST_MISMATCH")
                for portion in source.portions:
                    key = portion.projected.reference.model_dump_json()
                    if pool.get(key) != portion.projected or key in covered:
                        raise CompactAdmissionError("CONFLICTING_SOURCE")
                    covered.add(key)
                    if (
                        portion.original is not None
                        and originals.get(portion.original.reference.model_dump_json())
                        != portion.original
                    ):
                        raise CompactAdmissionError("CONFLICTING_SOURCE")
            if covered != set(pool) or request.slots != original_slots(authority, sources):
                raise CompactAdmissionError("SLOT_SOURCE_MISMATCH")
            target = authority.request.target
            if request.target_slot_id != f"D{target.day.day_index}_{target.slot.value}":
                raise CompactAdmissionError("TARGET_SLOT_MISMATCH")
            if request.mode == "B2":
                pairs = tuple((e.candidate_id, e.priority) for e in authority.candidates)
                if (
                    len({e[0] for e in pairs}) != len(pairs)
                    or len({(c.combination_id, c.portion_preset) for c in authority.candidates})
                    != len(authority.candidates)
                    or request.ranking != authority.ranking
                    or tuple((e.candidate_id, e.priority) for e in request.candidates) != pairs
                    or authority.ranking is None
                    or authority.ranking.content_digest
                    != digest(
                        [e.model_dump(mode="json", by_alias=True) for e in authority.candidates]
                    )
                ):
                    raise CompactAdmissionError("RANKING_MISMATCH")
            sources = tuple(sorted(sources, key=lambda s: s.combination_id))
            material = canonical_material(dict(input=request, authority=authority, sources=sources))
            _SwapInputs.model_validate(
                dict(
                    request=authority.request,
                    saved_plan=authority.saved_plan,
                    locks=authority.locks,
                    permission=authority.permission,
                    knowledge=authority.knowledge,
                    context=authority.context,
                    sources=authority.sources,
                    bridge=authority.bridge,
                )
            )
            return AdmittedCompactSwap(request, authority, sources, material)
    except CompactAdmissionError:
        raise
    except (ValidationError, ValueError, TypeError, AttributeError, KeyError) as error:
        raise CompactAdmissionError("MALFORMED_AUTHORITY") from error
