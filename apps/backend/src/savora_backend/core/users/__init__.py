"""User entity, DTOs, repository, and service."""

from uuid import UUID

from pydantic import EmailStr, Field
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from savora_backend.core.common import CamelModel
from savora_backend.database import PrimaryEntity


class UserEntity(PrimaryEntity):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)


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


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> UserEntity | None:
        stmt = select(UserEntity).where(UserEntity.id == user_id)
        return await self._session.scalar(stmt)

    async def get_by_email(self, email: str) -> UserEntity | None:
        normalized = email.strip().lower()
        stmt = select(UserEntity).where(UserEntity.email == normalized)
        return await self._session.scalar(stmt)

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str,
    ) -> UserEntity:
        user = UserEntity(
            email=email.strip().lower(),
            password_hash=password_hash,
            display_name=display_name.strip(),
        )
        self._session.add(user)
        await self._session.flush()
        return user
