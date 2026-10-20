"""Route decorators for response envelope metadata."""

from collections.abc import Callable
from typing import TypeVar

F = TypeVar("F", bound=Callable[..., object])

RESPONSE_MESSAGE_ATTR = "__savora_response_message__"


def response_message(message: str) -> Callable[[F], F]:
    """Attach a custom response message to a FastAPI endpoint handler."""

    def decorator(func: F) -> F:
        setattr(func, RESPONSE_MESSAGE_ATTR, message)
        return func

    return decorator
