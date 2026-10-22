"""Canonical caps admit repetition without changing historical byte policies."""

from typing import Any

import pytest
from pydantic import ValidationError

from savora_ai.schemas.planned_swap import _SwapModel
from savora_ai.schemas.swap_envelope_policy import (
    COMPACT_SWAP_RECONSTRUCTION_POLICY,
    REAL_CATALOGUE_SWAP_POLICY,
    compact_swap_reconstruction,
    real_catalogue_swap_admission,
    swap_structural_bytes,
    swap_uses_canonical_material,
)


class RepeatedInput(_SwapModel):
    bodies: tuple[dict[str, str], ...]


class FixedOutput(RepeatedInput):
    _fixed_output_ceiling = True


def test_expanded_repetition_is_counted_once_only_in_closed_compact_policy():
    payload = {"bodies": tuple({"body": "x" * 200_000} for _ in range(32))}
    with (
        real_catalogue_swap_admission(REAL_CATALOGUE_SWAP_POLICY),
        pytest.raises(ValidationError, match="4 MiB"),
    ):
        RepeatedInput.model_validate(payload)
    with compact_swap_reconstruction(COMPACT_SWAP_RECONSTRUCTION_POLICY):
        admitted = RepeatedInput.model_validate(payload)
        assert len(admitted.model_dump_json(by_alias=True).encode()) > 4_194_304
        with pytest.raises(ValidationError, match="1 MiB"):
            FixedOutput.model_validate(payload)
        with real_catalogue_swap_admission(REAL_CATALOGUE_SWAP_POLICY):
            assert not swap_uses_canonical_material()
        assert swap_uses_canonical_material()
    assert swap_structural_bytes() == 1_048_576 and not swap_uses_canonical_material()


def test_genuinely_unique_material_still_cannot_exceed_four_mib():
    payload = {"bodies": tuple({"body": str(i) + "x" * 200_000} for i in range(32))}
    with (
        compact_swap_reconstruction(COMPACT_SWAP_RECONSTRUCTION_POLICY),
        pytest.raises(ValidationError, match="MATERIAL_LIMIT"),
    ):
        RepeatedInput.model_validate(payload)
    assert swap_structural_bytes() == 1_048_576 and not swap_uses_canonical_material()


def test_compact_policy_requires_its_exact_closed_tag():
    invalid_policy: Any = "unreviewed-policy"
    with (
        pytest.raises(ValueError, match="unsupported"),
        compact_swap_reconstruction(invalid_policy),
    ):
        raise AssertionError("must never enter invalid policy")
