"""Async SQLAlchemy 2 engine, session factory, and base ORM entities."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Uuid
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from savora_backend.config import get_settings
from savora_backend.contexts import RequestContextProvider


class Base(DeclarativeBase):
    pass


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _current_user_id() -> uuid.UUID | None:
    return RequestContextProvider.get().user_id


class CommonEntity(Base):
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, default=_current_user_id, nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, default=_current_user_id, onupdate=_current_user_id, nullable=True
    )


class PrimaryEntity(CommonEntity):
    __abstract__ = True

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, future=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


def reset_database_state(
    engine: AsyncEngine | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    global _engine, _session_factory
    _engine = engine
    _session_factory = session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session with an explicit transaction per request."""
    factory = get_session_factory()
    async with factory() as session, session.begin():
        yield session
