"""Catalogue routes."""

from fastapi import APIRouter, Query

from savora_backend.auth import CurrentUser
from savora_backend.core.catalogue.dependencies import CatalogueBundleDep
from savora_backend.core.catalogue.dto import (
    CatalogueDishDetailDto,
    CatalogueDishDto,
    CuisineOptionDto,
)
from savora_backend.core.catalogue.service import CatalogueService
from savora_backend.decorators import response_message
from savora_backend.exceptions import RuntimeException
from savora_backend.interceptors import TransformRoute

catalogue_router = APIRouter(prefix="/catalogue", tags=["catalogue"], route_class=TransformRoute)


@catalogue_router.get("/cuisines")
@response_message("Catalogue cuisines retrieved")
async def list_cuisines(_user: CurrentUser, bundle: CatalogueBundleDep) -> list[CuisineOptionDto]:
    return CatalogueService(bundle).cuisines()


@catalogue_router.get("/dishes")
@response_message("Catalogue dishes retrieved")
async def search_dishes(
    _user: CurrentUser,
    bundle: CatalogueBundleDep,
    q: str = Query(default="", max_length=100),
) -> list[CatalogueDishDto]:
    return CatalogueService(bundle).search_dishes(q)


@catalogue_router.get("/dishes/{recipe_id}")
@response_message("Catalogue dish retrieved")
async def get_dish(
    _user: CurrentUser,
    bundle: CatalogueBundleDep,
    recipe_id: str,
) -> CatalogueDishDetailDto:
    dish = CatalogueService(bundle).get_dish(recipe_id)
    if dish is None:
        raise RuntimeException(
            "DISH_NOT_FOUND", f"Dish '{recipe_id}' was not found in the catalogue.", status_code=404
        )
    return dish
