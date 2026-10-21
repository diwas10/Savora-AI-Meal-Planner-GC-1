"""User and authentication DTOs (camelCase on the wire)."""

from uuid import UUID

from pydantic import EmailStr, Field

from savora_backend.core.common import CamelModel


class UserDto(CamelModel):
    id: UUID
    email: EmailStr
    display_name: str
    is_active: bool


class RegisterRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)


class LoginRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthResponse(CamelModel):
    user: UserDto
    access_token: str
