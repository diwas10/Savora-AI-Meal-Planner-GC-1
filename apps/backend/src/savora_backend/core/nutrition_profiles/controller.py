"""Profile routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from savora_backend.auth import CurrentUser
from savora_backend.core.catalogue import CatalogueBundleDep
from savora_backend.core.nutrition_profiles.dto import ProfileEnvelopeData, ProfileUpsertRequest
from savora_backend.core.nutrition_profiles.service import ProfileService
from savora_backend.database import get_session
from savora_backend.decorators import response_message
from savora_backend.interceptors import TransformRoute

profile_router = APIRouter(prefix="/profile", tags=["profile"], route_class=TransformRoute)


@profile_router.get("")
@response_message("Profile retrieved")
async def get_profile(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    bundle: CatalogueBundleDep,
) -> ProfileEnvelopeData:
    return await ProfileService(session, bundle).get_profile(user.id)


@profile_router.put("")
@response_message("Profile saved")
async def put_profile(
    body: ProfileUpsertRequest,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    bundle: CatalogueBundleDep,
) -> ProfileEnvelopeData:
    return await ProfileService(session, bundle).upsert_profile(user.id, body)
