"""Application router/module assembly."""

from fastapi import APIRouter

from savora_backend.auth import auth_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)


@api_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
