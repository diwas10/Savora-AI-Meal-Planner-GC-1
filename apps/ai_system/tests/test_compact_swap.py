"""Trust boundaries and fresh independent compact proof reconstruction."""

import json
from unittest.mock import patch

import pytest
from compact_swap_fixtures import FakeResolver, compact_input, fixture, package_case
from swap_oracle import make_case
from test_weekly_contracts import evidence

from savora_ai.core.reasoning.compact_swap import execute_compact_swap, verify_compact_swap
from savora_ai.core.reasoning.compact_swap_material import canonical_material, digest
from savora_ai.schemas.daily import DailySourceReference
from savora_ai.schemas.nutrients_v2 import NutrientBandV2


@pytest.mark.parametrize("mode", ["B1", "B2"])
def test_good_compact_full_replay(mode):
    authority, sources = fixture()
    request = compact_input(authority, sources, mode)
    resolver = FakeResolver(authority, sources)
    result = execute_compact_swap(request, resolver, clock=lambda: 0.0)
    assert result.status == "VALID", result
    assert result.verification_complete
    assert result.replacement_portion_preset == "HIGHER_PROTEIN"
    assert all(t.value == "30.000" and t.complete for t in result.changed_day_totals)
    assert result.reconstructed_bytes <= 4_194_304
    assert len(request.model_dump_json(by_alias=True).encode()) <= 1_048_576
    assert len(result.model_dump_json(by_alias=True).encode()) <= 1_048_576
    with patch("savora_ai.core.reasoning.compact_swap._execute_phase", side_effect=AssertionError):
        assert verify_compact_swap(request, result, resolver, clock=lambda: 0.0).accepted
    assert authority.saved_plan.snapshot.verification.status == "UNVERIFIED"


@pytest.mark.parametrize(
    "mutation",
    [
        "slot",
        "preset",
        "digest",
        "profile",
        "target",
        "kb",
        "certificate",
        "owner",
        "authority",
        "rank",
    ],
)
def test_client_tampering_fails_admission(mutation):
    authority, sources = fixture()
    request = compact_input(authority, sources, "B2" if mutation == "rank" else "B1")
    body = request.model_dump(mode="json", by_alias=True)
    if mutation == "slot":
        body["slots"][1]["combinationId"] = "foreign"
    elif mutation == "preset":
        body["slots"][1]["portionPreset"] = "LOWER_CARB"
    elif mutation == "digest":
        body["sources"][0]["contentDigest"] = "f" * 64
    elif mutation == "authority":
        body["authority"]["contentDigest"] = "f" * 64
    elif mutation == "rank":
        body["candidates"][0]["priority"] += 1
    else:
        field = {
            "profile": "profileVersion",
            "target": "targetSnapshotDigest",
            "kb": "kbVersion",
            "certificate": "certificateDigest",
            "owner": "ownerId",
        }[mutation]
        body["savedPlan"][field] = "f" * 64 if mutation in ("target", "certificate") else "stale"
    result = execute_compact_swap(
        json.dumps(body), FakeResolver(authority, sources), clock=lambda: 0.0
    )
    assert result.status == "ADMISSION_FAILED", result
    assert not result.verification_complete


@pytest.mark.parametrize("mode", ["missing", "stale", "tampered", "malformed", "unavailable"])
def test_resolver_failure_is_typed(mode):
    authority, sources = fixture()
    request = compact_input(authority, sources)
    bad = sources
    if mode == "missing":
        bad = ()
    elif mode == "stale":
        bad = (sources[0].model_copy(update={"catalogue_version": "stale"}),)
    elif mode == "tampered":
        p = sources[0].portions[0]
        m = p.nutrients.measurements[0].model_copy(update={"value": "999"})
        vector = p.nutrients.model_copy(update={"measurements": (m, *p.nutrients.measurements[1:])})
        bad = (
            sources[0].model_copy(
                update={
                    "portions": (
                        p.model_copy(update={"nutrients": vector}),
                        *sources[0].portions[1:],
                    )
                }
            ),
        )
    elif mode == "malformed":
        bad = [{"unexpected": "body"}]
    result = execute_compact_swap(
        request, FakeResolver(authority, bad, mode == "unavailable"), clock=lambda: 0.0
    )
    assert result.status == "ADMISSION_FAILED", result
    assert not result.verification_complete


def test_result_tampering_and_source_unavailability_never_verify():
    authority, sources = fixture()
    request = compact_input(authority, sources)
    resolver = FakeResolver(authority, sources)
    result = execute_compact_swap(request, resolver, clock=lambda: 0.0)
    assert result.status == "VALID"
    for change in (
        {"certificate_digest": "f" * 64},
        {"replacement_portion_preset": "LOWER_CARB"},
        {
            "changed_day_totals": (
                result.changed_day_totals[0].model_copy(update={"value": "31"}),
                *result.changed_day_totals[1:],
            )
        },
    ):
        assert not verify_compact_swap(
            request, result.model_copy(update=change), resolver, clock=lambda: 0.0
        ).accepted
    assert not verify_compact_swap(
        request, result, FakeResolver(authority, (), True), clock=lambda: 0.0
    ).accepted


def test_deduplication_is_exact_and_retains_changes():
    repeated = {"source": {"a": "x" * 10000}, "slots": [{"a": "x" * 10000}] * 21}
    compact = canonical_material(repeated)
    assert len(compact) < 20000
    assert compact == canonical_material(repeated)
    assert digest(compact.decode()) != digest(canonical_material(repeated | {"other": 1}).decode())


@pytest.mark.parametrize(
    "payload",
    [
        b" " * 1_048_577,
        b'{"mode":"B1","mode":"B2"}',
        b"{}",
        b"null",
    ],
    ids=["oversize", "duplicate-key", "missing-fields", "null"],
)
def test_strict_wire_admission(payload):
    authority, sources = fixture()
    result = execute_compact_swap(payload, FakeResolver(authority, sources), clock=lambda: 0.0)
    assert result.status == "ADMISSION_FAILED"


def test_native_unknown_never_becomes_zero_or_valid():
    authority, sources = fixture()
    source = sources[0]
    portion = source.portions[-1]
    unknown = portion.nutrients.measurements[0].model_copy(
        update={"value": None, "complete": False}
    )
    vector = portion.nutrients.model_copy(
        update={"measurements": (unknown, *portion.nutrients.measurements[1:])}
    )
    changed = source.model_copy(
        update={
            "portions": (*source.portions[:-1], portion.model_copy(update={"nutrients": vector}))
        }
    )
    changed_sources = (changed,)
    request = compact_input(authority, changed_sources)
    result = execute_compact_swap(
        request, FakeResolver(authority, changed_sources), clock=lambda: 0.0
    )
    assert result.status == "INSUFFICIENT_DATA", result
    assert result.reason == "NATIVE_REQUIRED_FACT_UNKNOWN"
    assert result.verification_complete


@pytest.mark.parametrize("upper,status", [("30", "VALID"), ("29.999", "REJECTED")])
def test_full_target_snapshot_native_band_is_hard(upper, status):
    source = DailySourceReference(
        source_id="fictional-target",
        version="1",
        content_digest=digest({"fixture": "fictional-general-target"}),
    )
    band = NutrientBandV2(
        band_id="fixture-day-one",
        scope="DAY",
        day_index=1,
        nutrient="energy_kcal",
        unit="kcal",
        lower=None,
        upper=upper,
        source=source,
        evidence=(evidence(),),
    )
    authority, sources = package_case(make_case(), bands=(band,))
    result = execute_compact_swap(
        compact_input(authority, sources), FakeResolver(authority, sources), clock=lambda: 0.0
    )
    assert result.status == status, result
    assert result.verification_complete


@pytest.mark.parametrize(
    "capacity", ["work", "records", "bytes", "visits", "validations", "deadline"]
)
def test_budget_reserves_before_semantic_execution(capacity):
    authority, sources = fixture()
    limits = authority.limits
    changes = {
        "work": {
            "max_reserved_work": limits.max_reserved_work.model_copy(update={"ordering_items": 0})
        },
        "records": {"max_proof_records": 0},
        "bytes": {"max_proof_bytes": 1},
        "visits": {"max_domain_visits": 0},
        "validations": {"max_full_validations": 0},
        "deadline": {"deadline": 0.0},
    }[capacity]
    limited = authority.model_copy(update={"limits": limits.model_copy(update=changes)})
    with patch("savora_ai.core.reasoning.compact_swap._execute_phase", side_effect=AssertionError):
        result = execute_compact_swap(
            compact_input(limited, sources), FakeResolver(limited, sources), clock=lambda: 0.0
        )
    assert result.status == "TIMEOUT", result
    assert not result.verification_complete


def test_canonical_material_overflow_is_typed():
    from savora_ai.core.reasoning.compact_swap_material import CompactAdmissionError

    with pytest.raises(CompactAdmissionError, match="MATERIAL_LIMIT"):
        canonical_material({"unique": "x" * 4_194_304})


def test_compact_proof_has_its_own_exact_one_mib_ceiling():
    from savora_ai.schemas.compact_swap_canonical import CompactCanonicalLimitError, canonical_proof

    with pytest.raises(CompactCanonicalLimitError, match="PROOF_LIMIT"):
        canonical_proof({"unique": "x" * 1_048_576})


@pytest.mark.parametrize(
    "change",
    [
        {"authenticated_user_id": "another-user"},
        {"current_profile_version": "stale"},
    ],
)
def test_changed_server_authority_cannot_be_repaired_by_rehashing_client_pins(change):
    authority, sources = fixture()
    changed = authority.model_copy(update=change)
    request = compact_input(changed, sources)
    result = execute_compact_swap(request, FakeResolver(changed, sources), clock=lambda: 0.0)
    assert result.status == "ADMISSION_FAILED"
    assert not result.verification_complete


@pytest.mark.parametrize(
    "case_args,expected",
    [
        ({"recipe": False}, "REJECTED"),
        ({"incomplete": True}, "INSUFFICIENT_DATA"),
    ],
)
def test_compact_component_recipe_checks_preserve_literal_hard_truth(case_args, expected):
    authority, sources = package_case(make_case(**case_args))
    result = execute_compact_swap(
        compact_input(authority, sources), FakeResolver(authority, sources), clock=lambda: 0.0
    )
    assert result.status == expected, result
    assert result.verification_complete


def test_b2_rejects_aliases_of_the_same_fixed_candidate_even_with_rehashed_pins():
    authority, sources = fixture()
    assert authority.ranking is not None
    duplicate = authority.candidates[-1].model_copy(update={"candidate_id": "foreign-alias"})
    candidates = (*authority.candidates, duplicate)
    ranking = authority.ranking.model_copy(
        update={
            "content_digest": digest([c.model_dump(mode="json", by_alias=True) for c in candidates])
        }
    )
    changed = authority.model_copy(update={"candidates": candidates, "ranking": ranking})
    result = execute_compact_swap(
        compact_input(changed, sources, "B2"), FakeResolver(changed, sources), clock=lambda: 0.0
    )
    assert result.status == "ADMISSION_FAILED" and result.reason == "RANKING_MISMATCH"


def test_lock_inventory_revision_is_independent_but_its_full_body_remains_pinned():
    from test_planned_swap_contracts import rebuild, reference

    authority, sources = fixture()
    locks = rebuild(authority.locks, revision=2)
    permission = rebuild(authority.permission, locks=reference(locks))
    request = rebuild(authority.request, locks=reference(locks), permission=reference(permission))
    changed = authority.model_copy(
        update={"locks": locks, "permission": permission, "request": request}
    )
    compact = compact_input(changed, sources)
    result = execute_compact_swap(compact, FakeResolver(changed, sources), clock=lambda: 0.0)
    assert result.status == "VALID" and result.verification_complete, result
    assert compact.saved_plan.revision == 1 and locks.revision == 2


def test_locked_target_is_rejected_and_no_slot_is_changed():
    from test_planned_swap_contracts import rebuild, reference

    from savora_ai.schemas.planned_swap import LockKind, SavedSlotLock

    authority, sources = fixture()
    locks = rebuild(
        authority.locks,
        entries=(
            SavedSlotLock(
                slot=authority.request.target,
                kind=LockKind.USER,
                reason="fictional locked target",
                authority=evidence(),
            ),
        ),
    )
    permission = rebuild(authority.permission, locks=reference(locks))
    request = rebuild(authority.request, locks=reference(locks), permission=reference(permission))
    authority = authority.model_copy(
        update={"locks": locks, "permission": permission, "request": request}
    )
    compact = compact_input(authority, sources)
    before = authority.saved_plan.model_dump_json(by_alias=True)
    result = execute_compact_swap(compact, FakeResolver(authority, sources), clock=lambda: 0.0)
    assert result.status == "REJECTED" and result.reason == "TARGET_LOCKED", result
    assert authority.saved_plan.model_dump_json(by_alias=True) == before
    assert not result.changed_day_totals and result.replacement_combination_id is None
