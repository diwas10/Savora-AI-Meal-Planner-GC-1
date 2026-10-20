"""Shared base models and envelope DTOs."""

from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class SuccessEnvelope[T](CamelModel):
    success: bool = True
    source: str
    data: T
    message: str
    status: int


class ErrorEnvelope(CamelModel):
    success: bool = False
    source: str
    message: str
    status: int
    description: Any | None = None
