"""Closed profile boundaries, legacy wires and fresh swap authority checks."""

import json

import pytest
from pydantic import ValidationError
from swap_oracle import make_case, repin
from test_planned_swap_contracts import rebuild
from test_swap_proof_contracts import limits

from savora_ai.core.reasoning.planned_swap import validate_swap, verify_swap_validation
from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.planned_swap import SavedPlanMaterial, SwapReference, SwapValidationLimits
from savora_ai.schemas.swap_envelope import (
    LEGACY_SWAP_BYTES,
    REAL_CATALOGUE_SWAP_BYTES,
    REAL_CATALOGUE_SWAP_POLICY,
    real_catalogue_swap_admission,
    swap_structural_bytes,
    validate_real_catalogue_swap_json,
)
from savora_ai.schemas.swap_proof_types import _SwapClaim


def reference_json(size):
    raw = SwapReference(record_id="x", version="v", content_digest="a" * 64).model_dump_json()
    return (raw[:-1] + " " * (size - len(raw)) + "}").encode()


@pytest.mark.parametrize("size", [LEGACY_SWAP_BYTES, 1_992_294, REAL_CATALOGUE_SWAP_BYTES])
def test_exact_raw_byte_boundaries(size):
    raw = reference_json(size)
    assert len(raw) == size
    assert validate_real_catalogue_swap_json(SwapReference, raw).record_id == "x"
    if size > LEGACY_SWAP_BYTES:
        with pytest.raises(ValidationError, match="1 MiB"):
            validate_contract_json(SwapReference, raw)
    else:
        assert validate_contract_json(SwapReference, raw).record_id == "x"


def test_one_byte_over_and_multibyte_are_rejected():
    with pytest.raises(ValidationError, match="4 MiB"):
        validate_real_catalogue_swap_json(
            SwapReference, reference_json(REAL_CATALOGUE_SWAP_BYTES + 1)
        )
    text = reference_json(REAL_CATALOGUE_SWAP_BYTES).decode().replace(chr(118), chr(233), 1)
    with pytest.raises(ValidationError, match="4 MiB"):
        validate_real_catalogue_swap_json(SwapReference, text)


def test_encoded_nested_ceiling_and_restored_legacy():
    with real_catalogue_swap_admission(REAL_CATALOGUE_SWAP_POLICY):
        ref = SwapReference(record_id="x", version="v" * 1_100_000, content_digest="a" * 64)
        assert len(ref.model_dump_json()) > LEGACY_SWAP_BYTES
    with pytest.raises(ValidationError, match="1 MiB"):
        SwapReference.model_validate(ref)
    assert swap_structural_bytes() == LEGACY_SWAP_BYTES
    with pytest.raises(ValueError), real_catalogue_swap_admission("arbitrary-8mib"):  # type: ignore[arg-type]
        pytest.fail("unsupported policy entered")
    assert swap_structural_bytes() == LEGACY_SWAP_BYTES


def test_duplicate_keys_depth_malformed_and_output_caps():
    with pytest.raises(ValidationError, match="duplicate"):
        validate_real_catalogue_swap_json(SwapReference, '{"recordId":"x","recordId":"y"}')
    with pytest.raises(ValidationError, match="64-level"):
        validate_real_catalogue_swap_json(SwapReference, "[" * 65 + "]" * 65)
    with pytest.raises(ValueError, match="swap DTO"):
        validate_real_catalogue_swap_json(str, '"x"')
    with pytest.raises(ValidationError, match="1 MiB"):
        validate_real_catalogue_swap_json(_SwapClaim, reference_json(LEGACY_SWAP_BYTES + 1))
    case = make_case()
    body = case["saved_plan"].model_dump(mode="json", by_alias=True)
    body["snapshot"]["slots"][0]["option"]["reference"]["optionId"] = "tampered"
    with pytest.raises(ValidationError):
        validate_real_catalogue_swap_json(SavedPlanMaterial, json.dumps(body))
    with real_catalogue_swap_admission(REAL_CATALOGUE_SWAP_POLICY), pytest.raises(ValidationError):
        SwapValidationLimits.model_validate(limits().model_dump() | {"max_proof_bytes": 1_048_577})


@pytest.mark.parametrize("history", [False, True])
def test_history_does_not_establish_or_remove_fresh_semantic_authority(history):
    case = make_case(history=history)
    args = case | dict(candidates=case["sources"].candidates, limits=limits())
    result = validate_swap(
        **args, replacement=case["sources"].options[1].reference, clock=lambda: 0.0
    )
    assert result.accepted and result.verification_complete
    assert result.certificate is not None
    assert len(result.certificate.original.days) == 7
    assert len(result.certificate.result.days) == 7
    report = verify_swap_validation(
        result, **args, replacement=case["sources"].options[1].reference, clock=lambda: 0.0
    )
    assert report.accepted


def test_large_saved_input_profile_is_not_semantic_or_result_budget_increase():
    case = make_case()
    ev = (
        case["saved_plan"]
        .snapshot.evidence[0]
        .model_copy(
            update={"evidence_id": "large-independent-evidence", "locator": "x" * 1_100_000}
        )
    )
    with real_catalogue_swap_admission(REAL_CATALOGUE_SWAP_POLICY):
        snapshot = rebuild(case["saved_plan"].snapshot, evidence=(ev,))
        saved = rebuild(
            case["saved_plan"],
            snapshot=snapshot,
            reference=case["saved_plan"].reference.model_copy(
                update={"snapshot_digest": snapshot.content_digest}
            ),
        )
        case = repin(case, saved_plan=saved)
        result = validate_swap(
            **case,
            replacement=case["sources"].options[1].reference,
            candidates=case["sources"].candidates,
            limits=SwapValidationLimits.model_validate(limits()),
            clock=lambda: 0.0,
        )
        # Oversized retained output cannot receive a successful witness.
        assert not result.accepted
    assert swap_structural_bytes() == LEGACY_SWAP_BYTES


def test_profile_context_isolation_and_exception_restoration():
    from contextvars import Context

    independent = Context()
    with pytest.raises(RuntimeError), real_catalogue_swap_admission(REAL_CATALOGUE_SWAP_POLICY):
        assert swap_structural_bytes() == REAL_CATALOGUE_SWAP_BYTES
        assert independent.run(swap_structural_bytes) == LEGACY_SWAP_BYTES
        raise RuntimeError("fixture interruption")
    assert swap_structural_bytes() == LEGACY_SWAP_BYTES
