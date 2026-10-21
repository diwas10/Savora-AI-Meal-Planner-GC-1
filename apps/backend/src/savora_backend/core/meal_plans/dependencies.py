"""Session factory for background jobs (tests point it at their database)."""

from fastapi import Request

from savora_backend.core.meal_plans.jobs import SessionFactory
from savora_backend.database import get_session_factory


def get_job_session_factory(request: Request) -> SessionFactory:
    override = getattr(request.app.state, "job_session_factory", None)
    if callable(override):
        return override
    return get_session_factory()
