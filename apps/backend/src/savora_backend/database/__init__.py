"""Async SQLAlchemy 2 engine, session factory, and base ORM entities."""

import sqlite3
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, String, Uuid, create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

from savora_backend.config import get_settings
from savora_backend.contexts import RequestContextProvider

sqlite3.register_adapter(uuid.UUID, str)


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


class StringArrayType(TypeDecorator[list[str]]):
    """Uses PostgreSQL TEXT[] in Postgres and JSON array in SQLite."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(String))
        return dialect.type_descriptor(JSON())


JsonbType = JSON().with_variant(JSONB(), "postgresql")


class SyncToAsyncSessionAdapter:
    """Wraps a sync SQLAlchemy Session with an AsyncSession-compatible interface."""

    def __init__(self, sync_session: Session) -> None:
        self._session = sync_session

    async def __aenter__(self) -> "SyncToAsyncSessionAdapter":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self._session.close()

    @asynccontextmanager
    async def begin(self) -> AsyncGenerator["SyncToAsyncSessionAdapter", None]:
        if self._session.in_transaction():
            yield self
            return
        with self._session.begin():
            yield self

    def add(self, instance: object) -> None:
        self._session.add(instance)

    def add_all(self, instances: Any) -> None:
        self._session.add_all(instances)

    async def delete(self, instance: object) -> None:
        self._session.delete(instance)

    async def flush(self) -> None:
        self._session.flush()

    async def commit(self) -> None:
        self._session.commit()

    async def rollback(self) -> None:
        self._session.rollback()

    async def refresh(self, instance: object) -> None:
        self._session.refresh(instance)

    async def execute(self, statement: Any, params: Any | None = None) -> Any:
        return self._session.execute(statement, params)

    async def scalar(self, statement: Any, params: Any | None = None) -> Any:
        return self._session.scalar(statement, params)

    async def scalars(self, statement: Any, params: Any | None = None) -> Any:
        return self._session.scalars(statement, params)

    async def get(self, entity: Any, ident: Any) -> Any:
        return self._session.get(entity, ident)

    async def close(self) -> None:
        self._session.close()


_engine: AsyncEngine | None = None
_session_factory: Any = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, future=True)
    return _engine


def get_session_factory() -> Any:
    global _session_factory
    if _session_factory is None:
        settings = get_settings()
        if settings.database_url.startswith("sqlite://"):
            is_memory = ":memory:" in settings.database_url
            sync_engine = create_engine(
                settings.database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool if is_memory else None,
                future=True,
            )
            sync_maker = sessionmaker(bind=sync_engine, expire_on_commit=False)

            def _make_adapter() -> SyncToAsyncSessionAdapter:
                return SyncToAsyncSessionAdapter(sync_maker())

            _session_factory = _make_adapter
        else:
            _session_factory = async_sessionmaker(
                bind=get_engine(),
                class_=AsyncSession,
                expire_on_commit=False,
            )
    return _session_factory


def reset_database_state(
    engine: AsyncEngine | None = None,
    session_factory: Any = None,
) -> None:
    global _engine, _session_factory
    _engine = engine
    _session_factory = session_factory


async def get_session() -> AsyncGenerator[Any, None]:
    """Yield an async session with an explicit transaction per request."""
    factory = get_session_factory()
    async with factory() as session, session.begin():
        yield session
