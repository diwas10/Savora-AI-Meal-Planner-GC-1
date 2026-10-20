"""Tests for backend foundations: envelopes, 422 shape, exceptions, and health."""

import httpx
from fastapi import APIRouter, FastAPI, status

from savora_backend.contexts import RequestContextProvider
from savora_backend.core.common import CamelModel
from savora_backend.decorators import response_message
from savora_backend.exceptions import (
    RuntimeException,
    ValidationException,
    register_exception_handlers,
)
from savora_backend.interceptors import TransformRoute
from savora_backend.main import app


class SamplePayload(CamelModel):
    first_name: str
    item_count: int


def _build_test_app() -> FastAPI:
    test_app = FastAPI()
    register_exception_handlers(test_app)
    router = APIRouter(prefix="/api/sample-items", route_class=TransformRoute)

    @router.post("", status_code=status.HTTP_201_CREATED)
    @response_message("Sample created")
    async def create_sample(body: SamplePayload) -> SamplePayload:
        return body

    @router.get("/runtime-error")
    async def trigger_runtime_error() -> dict[str, str]:
        raise RuntimeException(
            "Resource conflict",
            status_code=status.HTTP_409_CONFLICT,
            description="Already exists",
        )

    @router.get("/validation-error")
    async def trigger_validation_error() -> dict[str, str]:
        raise ValidationException({"allergies": ["Confirmation required"]})

    @router.get("/unhandled-error")
    async def trigger_unhandled_error() -> dict[str, str]:
        raise ValueError("secret database detail")

    @router.get("/context")
    async def read_context() -> dict[str, str]:
        ctx = RequestContextProvider.get()
        return {"requestId": ctx.request_id}

    test_app.include_router(router)
    return test_app


async def test_health() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_success_envelope_and_camel_case() -> None:
    test_app = _build_test_app()
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/sample-items",
            json={"firstName": "Asha", "itemCount": 3},
            headers={"X-Request-ID": "req-123"},
        )
    assert response.status_code == 201
    body = response.json()
    assert body == {
        "success": True,
        "source": "test-health",
        "data": {"firstName": "Asha", "itemCount": 3},
        "message": "Sample created",
        "status": 201,
    }


async def test_request_validation_422_shape() -> None:
    test_app = _build_test_app()
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/sample-items", json={"firstName": "Asha"})
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["status"] == 422
    assert body["message"] == "Validation failed"
    assert "itemCount" in body["description"]
    assert isinstance(body["description"]["itemCount"], list)


async def test_runtime_and_validation_exceptions() -> None:
    test_app = _build_test_app()
    transport = httpx.ASGITransport(app=test_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        conflict = await client.get("/api/sample-items/runtime-error")
        val_err = await client.get("/api/sample-items/validation-error")
        unhandled = await client.get(
            "/api/sample-items/unhandled-error",
        )
    assert conflict.status_code == 409
    assert conflict.json() == {
        "success": False,
        "source": "test-health",
        "message": "Resource conflict",
        "status": 409,
        "description": "Already exists",
    }
    assert val_err.status_code == 422
    assert val_err.json()["description"] == {"allergies": ["Confirmation required"]}
    assert unhandled.status_code == 500
    assert unhandled.json() == {
        "success": False,
        "source": "test-health",
        "message": "Internal server error",
        "status": 500,
    }
