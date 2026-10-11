"""Application router/module assembly (skeleton)."""

from fastapi import APIRouter

api_router = APIRouter(prefix="/api")


@api_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
