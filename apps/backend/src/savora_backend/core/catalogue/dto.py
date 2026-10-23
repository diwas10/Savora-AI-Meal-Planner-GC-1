"""Catalogue DTOs."""

from savora_ai.core.food_data.models import NutrientVector
from savora_backend.core.common import CamelModel


class CuisineOptionDto(CamelModel):
    id: str
    name: str


class CatalogueDishDto(CamelModel):
    recipe_id: str
    name: str
    cuisines: tuple[str, ...]


class CatalogueDishDetailDto(CamelModel):
    recipe_id: str
    name: str
    cuisines: tuple[str, ...]
    roles: tuple[str, ...]
    meal_types: tuple[str, ...]
    ingredients: tuple[str, ...]
    steps: tuple[str, ...]
    standard_portion: str
    standard_nutrients: NutrientVector
