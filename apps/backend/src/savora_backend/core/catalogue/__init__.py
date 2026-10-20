"""Shared catalogue bundle access and catalogue endpoints."""

from functools import lru_cache

from fastapi import APIRouter

from savora_ai.core.pipelines import CatalogueBundle, load_catalogue_export
from savora_backend.auth import CurrentUser
from savora_backend.config import get_settings
from savora_backend.core.common import CamelModel
from savora_backend.decorators import response_message
from savora_backend.interceptors import TransformRoute


@lru_cache(maxsize=1)
def get_catalogue_bundle() -> CatalogueBundle:
    settings = get_settings()
    return load_catalogue_export(settings.catalogue_dir)


class CuisineOptionDto(CamelModel):
    id: str
    name: str


catalogue_router = APIRouter(
    prefix="/catalogue",
    tags=["catalogue"],
    route_class=TransformRoute,
)


@catalogue_router.get("/cuisines")
@response_message("Catalogue cuisines retrieved")
async def list_cuisines(_user: CurrentUser) -> list[CuisineOptionDto]:
    bundle = get_catalogue_bundle()
    return [
        CuisineOptionDto(id=cid, name=name)
        for cid, name in sorted(bundle.cuisine_ids.items(), key=lambda item: item[1])
    ]
