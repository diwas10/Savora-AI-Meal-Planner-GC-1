"""Craving route."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from savora_ai.core.craving_nlu import CravingParser
from savora_backend.ai.gateway import AiGateway, get_ai_gateway, get_craving_parser
from savora_backend.auth import CurrentUser
from savora_backend.core.cravings.dto import CravingEndpointResponse, CravingTextRequest
from savora_backend.core.cravings.service import CravingService
from savora_backend.database import get_session
from savora_backend.decorators import response_message
from savora_backend.interceptors import TransformRoute

cravings_router = APIRouter(prefix="/cravings", tags=["cravings"], route_class=TransformRoute)


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
