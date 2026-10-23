"""Onboarding seed dishes (ADR 0005 D1).

Seed picks are stored in pick order without bumping `profile.version` or recalculating
targets: they are ranking history, not an anthropometric or dietary rule change.
"""

from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from savora_ai.core.recommendation.seeds import SeedSuggestions
from savora_backend.ai.gateway import AiGateway
from savora_backend.core.nutrition_profiles import (
    ProfileRepository,
    UserProfileEntity,
    to_planning_profile,
)
from savora_backend.core.onboarding.dto import SeedPicksRequest, SeedPicksResponse
from savora_backend.exceptions import RuntimeException, ValidationException

SOURCE = "onboarding"


class OnboardingSeedService:
    def __init__(self, session: AsyncSession, gateway: AiGateway) -> None:
        self._repo = ProfileRepository(session)
        self._gateway = gateway

    async def _profile(self, user_id: UUID) -> UserProfileEntity:
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise RuntimeException(
                "complete onboarding first", status_code=status.HTTP_409_CONFLICT, source=SOURCE
            )
        return profile

    async def get_suggestions(self, user_id: UUID) -> SeedSuggestions:
        profile = await self._profile(user_id)
        return await self._gateway.seeds(to_planning_profile(profile))

    async def save_picks(self, user_id: UUID, body: SeedPicksRequest) -> SeedPicksResponse:
        profile = await self._repo.lock_by_user_id(user_id)
        if profile is None:
            raise RuntimeException(
                "complete onboarding first", status_code=status.HTTP_409_CONFLICT, source=SOURCE
            )
        try:
            validated = await self._gateway.confirm_seeds(
                to_planning_profile(profile), body.recipe_ids
            )
        except ValueError as exc:
            raise ValidationException(
                {"recipeIds": [str(exc)]}, message=str(exc), source=SOURCE
            ) from exc
        profile.seed_recipe_ids = list(validated)
        await self._repo.save_profile(profile)
        return SeedPicksResponse(seed_recipe_ids=list(validated))
