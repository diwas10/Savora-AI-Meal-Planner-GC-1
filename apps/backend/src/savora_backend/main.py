"""FastAPI entry point (skeleton). Run: uvicorn savora_backend.main:app --reload"""

from fastapi import FastAPI

from savora_backend.app_module import api_router


def create_app() -> FastAPI:
    application = FastAPI(title="Savora API", version="0.1.0")
    application.include_router(api_router)
    return application


app = create_app()
