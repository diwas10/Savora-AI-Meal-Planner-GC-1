"""Onboarding seed-dish DTOs (ADR 0005 D1)."""

from pydantic import Field

from savora_backend.core.common import CamelModel


class SeedPicksRequest(CamelModel):
    recipe_ids: list[str] = Field(min_length=1, max_length=10)


class SeedPicksResponse(CamelModel):
    seed_recipe_ids: list[str]
