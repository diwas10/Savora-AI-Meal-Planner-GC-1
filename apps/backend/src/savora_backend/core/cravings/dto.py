"""Craving DTOs (section 4.3)."""

from typing import Literal

from pydantic import Field

from savora_ai.core.pipelines import CravingRecommendation
from savora_ai.schemas.craving import CravingRequest
from savora_backend.core.common import CamelModel


class CravingTextRequest(CamelModel):
    text: str = Field(min_length=1, max_length=500)


class CravingParseMeta(CamelModel):
    parser: Literal["TEMPLATE", "QWEN", "HYBRID"]
    prompt_version: str
    fallback_reason: str | None = None
    clarification: str | None = None


class CravingRecommendationsResponse(CamelModel):
    kind: Literal["RECOMMENDATIONS"] = "RECOMMENDATIONS"
    parse: CravingParseMeta
    result: CravingRecommendation


class CravingSwapSuggestedResponse(CamelModel):
    kind: Literal["SWAP_SUGGESTED"] = "SWAP_SUGGESTED"
    parse: CravingParseMeta
    request: CravingRequest
    clarification: str | None = None


CravingEndpointResponse = CravingRecommendationsResponse | CravingSwapSuggestedResponse
