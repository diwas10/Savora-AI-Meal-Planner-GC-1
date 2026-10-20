"""FastAPI entry point. Run: uvicorn savora_backend.main:app --reload"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from savora_backend.ai.runtime import build_ai_runtime
from savora_backend.app_module import api_router
from savora_backend.config import get_settings
from savora_backend.exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    application.state.ai_runtime = build_ai_runtime()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="Savora API", version="0.1.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(application)
    application.include_router(api_router)
    return application


app = create_app()
