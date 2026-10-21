"""Standalone craving: NLU -> retrieval -> rules -> ranking (section 4.3).

Nothing is stored: not the text, the parse nor the results (no craving history in GC1).
A SWAP_MEAL intent is handed back to the client, which routes it to the swap flow; a
swap is never made from free text alone.
"""

import asyncio
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from savora_ai.core.craving_nlu import CravingParse, CravingParser, parse_craving
from savora_ai.schemas.craving import CravingIntent
from savora_backend.ai.gateway import AiGateway
from savora_backend.core.cravings.dto import (
    CravingEndpointResponse,
    CravingParseMeta,
    CravingRecommendationsResponse,
    CravingSwapSuggestedResponse,
    CravingTextRequest,
)
from savora_backend.core.nutrition_profiles import ProfileRepository, to_planning_profile
from savora_backend.exceptions import RuntimeException


def parse_meta(parsed: CravingParse) -> CravingParseMeta:
    return CravingParseMeta(
        parser=parsed.parser,
        prompt_version=parsed.prompt_version,
        fallback_reason=parsed.fallback_reason,
        clarification=parsed.clarification,
    )


class CravingService:
    def __init__(self, session: AsyncSession, gateway: AiGateway, parser: CravingParser) -> None:
        self._profile_repo = ProfileRepository(session)
        self._gateway = gateway
        self._parser = parser

    async def handle_craving(
        self, user_id: UUID, body: CravingTextRequest
    ) -> CravingEndpointResponse:
        profile = await self._profile_repo.get_by_user_id(user_id)
        if profile is None:
            raise RuntimeException(
                "complete onboarding first", status_code=status.HTTP_409_CONFLICT, source="cravings"
            )
        parsed = await asyncio.to_thread(parse_craving, body.text, parser=self._parser)
        meta = parse_meta(parsed)
        if parsed.request.intent is CravingIntent.SWAP_MEAL:
            return CravingSwapSuggestedResponse(
                parse=meta, request=parsed.request, clarification=parsed.clarification
            )
        result = await self._gateway.craving(parsed.request, to_planning_profile(profile))
        return CravingRecommendationsResponse(parse=meta, result=result)
