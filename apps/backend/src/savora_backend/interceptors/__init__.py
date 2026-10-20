"""TransformRoute and request context middleware for central envelope wrapping."""

import json
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request, Response, status
from fastapi.routing import APIRoute
from starlette.responses import JSONResponse

from savora_backend.contexts import RequestContextProvider
from savora_backend.decorators import RESPONSE_MESSAGE_ATTR


def _module_source(endpoint: Callable[..., Any]) -> str:
    module_name = getattr(endpoint, "__module__", "")
    parts = [
        p
        for p in module_name.split(".")
        if p not in {"savora_backend", "core", "controller", "controllers", "router", "routes"}
    ]
    if parts:
        return parts[-1].replace("_", "-")
    return "api"


class TransformRoute(APIRoute):
    """Wraps route return values into `{success, source, data, message, status}`."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original_route_handler = super().get_route_handler()
        endpoint = self.endpoint
        source = _module_source(endpoint)
        custom_message = getattr(endpoint, RESPONSE_MESSAGE_ATTR, None)
        default_status = self.status_code or status.HTTP_200_OK

        async def custom_route_handler(request: Request) -> Response:
            RequestContextProvider.set(request_id=request.headers.get("X-Request-ID"))
            try:
                response = await original_route_handler(request)
                if isinstance(response, Response):
                    content_type = response.headers.get("content-type", "")
                    if "application/json" not in content_type or not response.body:
                        return response
                    raw_body = json.loads(bytes(response.body).decode("utf-8"))
                    if (
                        isinstance(raw_body, dict)
                        and "success" in raw_body
                        and "source" in raw_body
                        and "status" in raw_body
                    ):
                        return response
                    status_code = response.status_code or default_status
                    envelope = {
                        "success": True,
                        "source": source,
                        "data": raw_body,
                        "message": custom_message or "OK",
                        "status": status_code,
                    }
                    headers = {
                        k: v
                        for k, v in response.headers.items()
                        if k.lower() != "content-length"
                    }
                    return JSONResponse(
                        content=envelope,
                        status_code=status_code,
                        headers=headers,
                    )
                return response
            finally:
                RequestContextProvider.clear()

        return custom_route_handler
