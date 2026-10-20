"""Application router/module assembly."""

from fastapi import APIRouter

from savora_backend.auth import auth_router
from savora_backend.core.catalogue import catalogue_router
from savora_backend.core.nutrition_profiles import profile_router
from savora_backend.core.onboarding import onboarding_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(catalogue_router)
api_router.include_router(onboarding_router)


@api_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
