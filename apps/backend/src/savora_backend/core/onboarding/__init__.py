"""Onboarding seed-dish suggestions and confirmation endpoints (ADR 0005 D1).

Design note: Updating seed picks on an existing profile stores `seed_recipe_ids` in pick
order without bumping `profile.version` or recalculating `NutritionTargets`, because seed
dishes are sequential ranking history rather than anthropometric or dietary rule changes.
"""

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from savora_ai.core.pipelines import CatalogueBundle, confirm_seeds, suggest_seeds
from savora_ai.core.recommendation.seeds import SeedSuggestions
from savora_backend.auth import CurrentUser
from savora_backend.core.catalogue import get_catalogue_bundle
from savora_backend.core.common import CamelModel
from savora_backend.core.nutrition_profiles import ProfileRepository, to_planning_profile
from savora_backend.database import get_session
from savora_backend.decorators import response_message
from savora_backend.exceptions import RuntimeException, ValidationException
from savora_backend.interceptors import TransformRoute


class SeedPicksRequest(CamelModel):
    recipe_ids: list[str] = Field(min_length=1, max_length=10)


class SeedPicksResponse(CamelModel):
    seed_recipe_ids: list[str]


class OnboardingSeedService:
    def __init__(
        self,
        session: AsyncSession,
        bundle: CatalogueBundle | None = None,
    ) -> None:
        self._repo = ProfileRepository(session)
        self._bundle = bundle or get_catalogue_bundle()

    async def get_suggestions(self, user_id: UUID) -> SeedSuggestions:
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise RuntimeException(
                "complete onboarding first",
                status_code=status.HTTP_409_CONFLICT,
                source="onboarding",
            )
        planning_profile = to_planning_profile(profile)
        return await asyncio.to_thread(suggest_seeds, planning_profile, self._bundle)

    async def save_picks(self, user_id: UUID, body: SeedPicksRequest) -> SeedPicksResponse:
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise RuntimeException(
                "complete onboarding first",
                status_code=status.HTTP_409_CONFLICT,
                source="onboarding",
            )
        planning_profile = to_planning_profile(profile)
        try:
            validated = await asyncio.to_thread(
                confirm_seeds, planning_profile, self._bundle, body.recipe_ids
            )
        except ValueError as exc:
            raise ValidationException(
                {"recipeIds": [str(exc)]},
                message=str(exc),
                source="onboarding",
            ) from exc
        profile.seed_recipe_ids = list(validated)
        await self._repo.save_profile(profile)
        return SeedPicksResponse(seed_recipe_ids=list(validated))


onboarding_router = APIRouter(
    prefix="/onboarding",
    tags=["onboarding"],
    route_class=TransformRoute,
)


@onboarding_router.get("/seed-suggestions")
@response_message("Seed suggestions retrieved")
async def get_seed_suggestions(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SeedSuggestions:
    return await OnboardingSeedService(session).get_suggestions(user.id)


@onboarding_router.put("/seed-picks")
@response_message("Seed picks confirmed")
async def put_seed_picks(
    body: SeedPicksRequest,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SeedPicksResponse:
    return await OnboardingSeedService(session).save_picks(user.id, body)
