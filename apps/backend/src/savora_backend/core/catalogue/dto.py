"""Catalogue DTOs."""

from savora_backend.core.common import CamelModel


class CuisineOptionDto(CamelModel):
    id: str
    name: str


class CatalogueDishDto(CamelModel):
    recipe_id: str
    name: str
    cuisines: tuple[str, ...]
