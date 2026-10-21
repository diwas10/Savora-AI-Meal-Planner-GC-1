"""Saved-plan meal substitution (section 4.4)."""

from savora_backend.core.substitutions.controller import substitutions_router
from savora_backend.core.substitutions.service import SubstitutionService

__all__ = ["SubstitutionService", "substitutions_router"]
