"""Catalogue routes."""

from fastapi import APIRouter, Query

from savora_backend.auth import CurrentUser
from savora_backend.core.catalogue.dependencies import CatalogueBundleDep
from savora_backend.core.catalogue.dto import CatalogueDishDto, CuisineOptionDto
from savora_backend.core.catalogue.service import CatalogueService
from savora_backend.decorators import response_message
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
