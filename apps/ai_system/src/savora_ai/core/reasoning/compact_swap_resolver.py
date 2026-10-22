"""Adapter contract: no database, backend imports or implicit source selection."""

from typing import Protocol

from savora_ai.schemas.compact_swap import (
    CompactCombinationSource,
    CompactSavedPlanBinding,
    CompactSwapAuthority,
)


class TrustedSourceResolver(Protocol):
    def resolve(
        self, catalogue_version: str, ids: tuple[str, ...]
    ) -> tuple[CompactCombinationSource, ...]:
        """Return exactly requested immutable sources from trusted version-pinned storage."""
        ...

    def load_authority(self, binding: CompactSavedPlanBinding) -> CompactSwapAuthority:
        """Select current revision/owner/profile/target/KB under authenticated server identity.

        Treat binding solely as an expected reference, never authorization. All source
        bodies must be independently selected; never echo compact client material.
        VERIFIED_AT_SAVE must retain actual stored proof metadata.
        """
        ...
