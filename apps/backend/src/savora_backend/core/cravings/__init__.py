"""Craving endpoint (`POST /api/cravings`) orchestrating NLU and standalone recipe discovery."""

import asyncio
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from savora_ai.core.craving_nlu import (
    CravingParser,
    HttpxQwenClient,
    QwenParser,
    TemplateParser,
    parse_craving,
)
from savora_ai.core.pipelines import CravingRecommendation
from savora_ai.schemas.craving import CravingIntent, CravingRequest
from savora_backend.ai.gateway import AiGateway, get_ai_gateway
from savora_backend.auth import CurrentUser
from savora_backend.config import get_settings
from savora_backend.core.common import CamelModel
from savora_backend.core.nutrition_profiles import ProfileRepository, to_planning_profile
from savora_backend.database import get_session
from savora_backend.decorators import response_message
from savora_backend.exceptions import RuntimeException
from savora_backend.interceptors import TransformRoute


class CravingTextRequest(CamelModel):
    text: str = Field(max_length=500)


class CravingParseMeta(CamelModel):
    parser: Literal["TEMPLATE", "QWEN"]
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


def get_craving_parser(
    gateway: Annotated[AiGateway, Depends(get_ai_gateway)],
) -> CravingParser:
    settings = get_settings()
    template = TemplateParser(gateway.bundle.cuisine_ids)
    client = HttpxQwenClient(
        api_key=settings.qwen_api_key,
        base_url=settings.qwen_base_url,
    )
    if client.is_configured:
        return QwenParser(
            client,
            model=settings.qwen_model_name,
            timeout_s=8.0,
            template_fallback=template,
        )
    return template


class CravingService:
    def __init__(
        self,
        session: AsyncSession,
        gateway: AiGateway,
        parser: CravingParser,
    ) -> None:
        self._profile_repo = ProfileRepository(session)
        self._gateway = gateway
        self._parser = parser

    async def handle_craving(
        self, user_id: UUID, body: CravingTextRequest
    ) -> CravingEndpointResponse:
        profile_entity = await self._profile_repo.get_by_user_id(user_id)
        if profile_entity is None:
            raise RuntimeException(
                "complete onboarding first",
                status_code=status.HTTP_409_CONFLICT,
                source="cravings",
            )
        planning_profile = to_planning_profile(profile_entity)

        parsed = await asyncio.to_thread(parse_craving, body.text, parser=self._parser)
        meta = CravingParseMeta(
            parser=parsed.parser,
            prompt_version=parsed.prompt_version,
            fallback_reason=parsed.fallback_reason,
            clarification=parsed.clarification,
        )
        if parsed.request.intent is CravingIntent.SWAP_MEAL:
            return CravingSwapSuggestedResponse(
                parse=meta,
                request=parsed.request,
                clarification=parsed.clarification,
            )

        rec = await self._gateway.craving(parsed.request, planning_profile)
        return CravingRecommendationsResponse(
            parse=meta,
            result=rec,
        )


cravings_router = APIRouter(
    prefix="/cravings",
    tags=["cravings"],
    route_class=TransformRoute,
)


@cravings_router.post("")
@response_message("Craving processed")
async def post_craving(
    body: CravingTextRequest,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[AiGateway, Depends(get_ai_gateway)],
    parser: Annotated[CravingParser, Depends(get_craving_parser)],
) -> CravingEndpointResponse:
    return await CravingService(session, gateway, parser).handle_craving(user.id, body)
