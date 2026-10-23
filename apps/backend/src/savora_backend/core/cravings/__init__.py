"""Standalone craving discovery (section 4.3); nothing is persisted."""

from savora_backend.ai.gateway import get_craving_parser
from savora_backend.core.cravings.controller import cravings_router
from savora_backend.core.cravings.dto import (
    CravingEndpointResponse,
    CravingParseMeta,
    CravingRecommendationsResponse,
    CravingSwapSuggestedResponse,
    CravingTextRequest,
)
from savora_backend.core.cravings.service import CravingService, parse_meta

__all__ = [
    "CravingEndpointResponse",
    "CravingParseMeta",
    "CravingRecommendationsResponse",
    "CravingService",
    "CravingSwapSuggestedResponse",
    "CravingTextRequest",
    "cravings_router",
    "get_craving_parser",
    "parse_meta",
]
