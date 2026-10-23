"""Onboarding routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from savora_ai.core.recommendation.seeds import SeedSuggestions
from savora_backend.ai.gateway import AiGateway, get_ai_gateway
from savora_backend.auth import CurrentUser
from savora_backend.core.onboarding.dto import SeedPicksRequest, SeedPicksResponse
from savora_backend.core.onboarding.service import OnboardingSeedService
from savora_backend.database import get_session
from savora_backend.decorators import response_message
from savora_backend.interceptors import TransformRoute

onboarding_router = APIRouter(prefix="/onboarding", tags=["onboarding"], route_class=TransformRoute)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
GatewayDep = Annotated[AiGateway, Depends(get_ai_gateway)]


@onboarding_router.get("/seed-suggestions")
@response_message("Seed suggestions retrieved")
async def get_seed_suggestions(
    user: CurrentUser, session: SessionDep, gateway: GatewayDep
) -> SeedSuggestions:
    return await OnboardingSeedService(session, gateway).get_suggestions(user.id)


@onboarding_router.put("/seed-picks")
@response_message("Seed picks confirmed")
async def put_seed_picks(
    body: SeedPicksRequest, user: CurrentUser, session: SessionDep, gateway: GatewayDep
) -> SeedPicksResponse:
    return await OnboardingSeedService(session, gateway).save_picks(user.id, body)
