"""Request-scoped context provider for user and request audit."""

from contextvars import ContextVar
from dataclasses import dataclass, replace
from uuid import UUID, uuid4


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    user_id: UUID | None = None


_request_context: ContextVar[RequestContext | None] = ContextVar(
    "savora_request_context", default=None
)


class RequestContextProvider:
    """Provides access to the current request's user_id and request_id."""

    @staticmethod
    def get() -> RequestContext:
        ctx = _request_context.get()
        if ctx is None:
            return RequestContext(request_id=str(uuid4()), user_id=None)
        return ctx

    @staticmethod
    def set(user_id: UUID | None = None, request_id: str | None = None) -> RequestContext:
        current = _request_context.get()
        req_id = request_id or (current.request_id if current else str(uuid4()))
        ctx = RequestContext(request_id=req_id, user_id=user_id)
        _request_context.set(ctx)
        return ctx

    @staticmethod
    def set_user_id(user_id: UUID | None) -> RequestContext:
        current = RequestContextProvider.get()
        ctx = replace(current, user_id=user_id)
        _request_context.set(ctx)
        return ctx

    @staticmethod
    def clear() -> None:
        _request_context.set(None)
