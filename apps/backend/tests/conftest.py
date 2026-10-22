"""Shared pytest fixtures for backend tests."""

from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from savora_backend.database import Base, SyncToAsyncSessionAdapter, get_session
from savora_backend.main import create_app


@pytest.fixture
async def db_client(tmp_path: Path) -> AsyncGenerator[httpx.AsyncClient, None]:
    db_file = tmp_path / "test_savora.db"
    sync_engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(sync_engine)
    sync_maker = sessionmaker(bind=sync_engine, expire_on_commit=False)

    def make_test_session() -> SyncToAsyncSessionAdapter:
        return SyncToAsyncSessionAdapter(sync_maker())

    async def override_get_session() -> AsyncGenerator[SyncToAsyncSessionAdapter, None]:
        async with make_test_session() as session, session.begin():
            yield session

    test_app = create_app()
    test_app.dependency_overrides[get_session] = override_get_session
    test_app.state.job_session_factory = make_test_session
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    sync_engine.dispose()
