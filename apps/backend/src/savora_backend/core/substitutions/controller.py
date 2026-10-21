"""Substitution polling route."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from savora_backend.ai.gateway import AiGateway, get_ai_gateway
from savora_backend.auth import CurrentUser
from savora_backend.core.meal_plans.dto import SubstitutionDetailDto
from savora_backend.core.substitutions.service import SubstitutionService
from savora_backend.database import get_session
from savora_backend.decorators import response_message
from savora_backend.interceptors import TransformRoute

substitutions_router = APIRouter(
    prefix="/substitutions", tags=["substitutions"], route_class=TransformRoute
)


@substitutions_router.get("/{substitution_id}")
@response_message("Substitution retrieved")
async def get_substitution(
    substitution_id: UUID,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[AiGateway, Depends(get_ai_gateway)],
) -> SubstitutionDetailDto:
    return await SubstitutionService(session, gateway).get_substitution(user.id, substitution_id)
