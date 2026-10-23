"""FastAPI entry point. Run: uvicorn savora_backend.main:app --reload"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from savora_backend.ai.runtime import get_default_ai_runtime
from savora_backend.app_module import api_router
from savora_backend.config import get_settings
from savora_backend.core.meal_plans import mark_stale_generating_jobs_failed
from savora_backend.exceptions import register_exception_handlers

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    # One runtime per process: catalogue, ranker and NLU parser are loaded once.
    application.state.ai_runtime = get_default_ai_runtime()
    try:
        recovered = await mark_stale_generating_jobs_failed()
        if recovered:
            logger.info("Marked %d interrupted job(s) as failed", recovered)
    except Exception as exc:
        logger.warning("Skipping startup job cleanup (database not reachable): %s", exc)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    settings.check_secrets()
    application = FastAPI(title="Savora API", version="0.2.0", lifespan=lifespan)
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
