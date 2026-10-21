"""Application exceptions and global FastAPI exception handlers."""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic.alias_generators import to_camel

logger = logging.getLogger(__name__)


def infer_source(request: Request) -> str:
    """Derive a kebab-case source token from the route module or path."""
    endpoint = request.scope.get("endpoint")
    if endpoint is not None and hasattr(endpoint, "__module__"):
        module_name = str(endpoint.__module__)
        parts = [
            p
            for p in module_name.split(".")
            if p not in {"savora_backend", "core", "controller", "controllers", "router", "routes"}
        ]
        if parts:
            return parts[-1].replace("_", "-")
    path_parts = [p for p in request.url.path.split("/") if p and p != "api"]
    return path_parts[0] if path_parts else "api"


class RuntimeException(Exception):
    """Domain or HTTP runtime exception mapped to the standard error envelope."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        description: Any | None = None,
        source: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.description = description
        self.source = source


class ValidationException(Exception):
    """Explicit field validation exception mapped to a 422 error envelope."""

    def __init__(
        self,
        errors: dict[str, list[str]],
        message: str = "Validation failed",
        source: str | None = None,
    ) -> None:
        super().__init__(message)
        self.errors = errors
        self.message = message
        self.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        self.source = source


def _error_payload(
    *,
    source: str,
    message: str,
    status_code: int,
    description: Any | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "success": False,
        "source": source,
        "message": message,
        "status": status_code,
    }
    if description is not None:
        payload["description"] = description
    return payload


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RuntimeException)
    async def handle_runtime_exception(request: Request, exc: RuntimeException) -> JSONResponse:
        src = exc.source or infer_source(request)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                source=src,
                message=exc.message,
                status_code=exc.status_code,
                description=exc.description,
            ),
        )

    @app.exception_handler(ValidationException)
    async def handle_validation_exception(
        request: Request, exc: ValidationException
    ) -> JSONResponse:
        src = exc.source or infer_source(request)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                source=src,
                message=exc.message,
                status_code=exc.status_code,
                description=exc.errors,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        field_errors: dict[str, list[str]] = {}
        for err in exc.errors():
            loc = [
                str(part) for part in err.get("loc", ()) if part not in ("body", "query", "path")
            ]
            field_name = to_camel(loc[-1]) if loc else "nonFieldErrors"
            msg = str(err.get("msg", "Invalid value"))
            field_errors.setdefault(field_name, []).append(msg)
        src = infer_source(request)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_payload(
                source=src,
                message="Validation failed",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                description=field_errors,
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc
        )
        src = infer_source(request)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_payload(
                source=src,
                message="Internal server error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ),
        )
