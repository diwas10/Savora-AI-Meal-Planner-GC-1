"""Closed structural admission policies; no increase to proof or result budgets.

The opt-in is selected by a server-side adapter, never inferred from JSON fields.
ContextVar tokens isolate concurrent requests and restore legacy limits on errors.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal

LEGACY_SWAP_BYTES = 1_048_576
REAL_CATALOGUE_SWAP_BYTES = 4 * LEGACY_SWAP_BYTES
REAL_CATALOGUE_SWAP_POLICY = "swap-structural-envelope.v2-real-catalogue-4mib"
COMPACT_SWAP_RECONSTRUCTION_POLICY = "compact-swap-source-reconstruction.v1"
_swap_input_bytes: ContextVar[int] = ContextVar("swap_input_bytes", default=LEGACY_SWAP_BYTES)
_canonical_input: ContextVar[bool] = ContextVar("swap_canonical_input", default=False)


def swap_structural_bytes() -> int:
    return _swap_input_bytes.get()


def swap_uses_canonical_material() -> bool:
    return _canonical_input.get()


@contextmanager
def real_catalogue_swap_admission(
    policy: Literal["swap-structural-envelope.v2-real-catalogue-4mib"],
) -> Iterator[None]:
    """Use around construction, B1/B2 execution AND authority-bound proof replay.

    This changes size admission only. All evidence stays under the existing
    synthetic reasoning protocol; it does not authorize real food safety claims.
    """
    if type(policy) is not str or policy != REAL_CATALOGUE_SWAP_POLICY:
        raise ValueError("unsupported swap structural admission policy")
    token = _swap_input_bytes.set(REAL_CATALOGUE_SWAP_BYTES)
    canonical_token = _canonical_input.set(False)
    try:
        yield
    finally:
        _canonical_input.reset(canonical_token)
        _swap_input_bytes.reset(token)


@contextmanager
def compact_swap_reconstruction(
    policy: Literal["compact-swap-source-reconstruction.v1"],
) -> Iterator[None]:
    """Server-only reconstruction: exact deduplicated input cap stays 4 MiB.

    Raw legacy aggregate repetition may exceed that count; the compact codec must
    admit it under the same 4 MiB ceiling. Historical proof/output types stay 1 MiB.
    The complete authority/native/source root is checked again by compact admission.
    """
    if type(policy) is not str or policy != COMPACT_SWAP_RECONSTRUCTION_POLICY:
        raise ValueError("unsupported compact reconstruction policy")
    token = _swap_input_bytes.set(REAL_CATALOGUE_SWAP_BYTES)
    canonical_token = _canonical_input.set(True)
    try:
        yield
    finally:
        _canonical_input.reset(canonical_token)
        _swap_input_bytes.reset(token)
