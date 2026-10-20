"""Shared catalogue bundle access and catalogue endpoints."""

from functools import lru_cache

from fastapi import APIRouter, Query

from savora_ai.core.pipelines import CatalogueBundle, load_catalogue_export
from savora_ai.core.recommendation.seeds import is_seed_eligible
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


class CatalogueDishDto(CamelModel):
    recipe_id: str
    name: str
    cuisines: tuple[str, ...]


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


@catalogue_router.get("/dishes")
@response_message("Catalogue dishes retrieved")
async def search_dishes(
    _user: CurrentUser,
    q: str = Query(default="", max_length=100),
) -> list[CatalogueDishDto]:
    """Return Food.com seed-eligible dishes matching query `q`."""
    bundle = get_catalogue_bundle()
    query = q.strip().lower()
    results: list[CatalogueDishDto] = []
    for dish in sorted(
        bundle.dishes.values(),
        key=lambda d: (-(d.training_interactions or 0), d.recipe_id),
    ):
        if dish.training_interactions is None or not is_seed_eligible(dish):
            continue
        if query and query not in dish.name.lower() and not any(
            query in c.lower() for c in dish.cuisines
        ):
            continue
        results.append(
            CatalogueDishDto(
                recipe_id=dish.recipe_id,
                name=dish.name,
                cuisines=dish.cuisines,
            )
        )
    return results
