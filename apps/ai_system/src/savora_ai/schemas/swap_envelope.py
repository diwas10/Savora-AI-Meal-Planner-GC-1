"""Explicit real-catalogue swap ingress. Policy state has no DTO dependencies."""

from savora_ai.schemas.swap_envelope_policy import (
    LEGACY_SWAP_BYTES as LEGACY_SWAP_BYTES,
)
from savora_ai.schemas.swap_envelope_policy import (
    REAL_CATALOGUE_SWAP_BYTES as REAL_CATALOGUE_SWAP_BYTES,
)
from savora_ai.schemas.swap_envelope_policy import (
    REAL_CATALOGUE_SWAP_POLICY as REAL_CATALOGUE_SWAP_POLICY,
)
from savora_ai.schemas.swap_envelope_policy import (
    real_catalogue_swap_admission as real_catalogue_swap_admission,
)
from savora_ai.schemas.swap_envelope_policy import (
    swap_structural_bytes as swap_structural_bytes,
)


def validate_real_catalogue_swap_json[Result](
    target: type[Result], payload: str | bytes | bytearray
) -> Result:
    """Strict original-JSON ingress, limited to swap DTOs and the closed profile.

    Proof and result DTOs retain their historical 1 MiB raw/encoded ceiling.
    The profile is selected outside the payload by authenticated orchestration.
    """
    from savora_ai.schemas.candidates import _validate_contract_json
    from savora_ai.schemas.planned_swap import _SwapModel

    if not isinstance(target, type) or not issubclass(target, _SwapModel):
        raise ValueError("real-catalogue admission requires a swap DTO class")
    ceiling = LEGACY_SWAP_BYTES if target._fixed_output_ceiling else REAL_CATALOGUE_SWAP_BYTES
    with real_catalogue_swap_admission(REAL_CATALOGUE_SWAP_POLICY):
        return _validate_contract_json(target, payload, max_bytes=ceiling)
