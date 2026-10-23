"""The API on real PostgreSQL (JSONB, TEXT[], partial unique indexes, row locks).

Opt-in: set SAVORA_TEST_POSTGRES_URL to an EMPTY throwaway database, e.g.
    postgresql+asyncpg://postgres@/savora_test?host=/tmp/pg
The schema is created by the Alembic migrations (not create_all), so this also proves
the migrations match what the code writes.
"""

import asyncio
import os
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from savora_backend.ai.gateway import get_ai_gateway
from savora_backend.core.meal_plans import wait_for_background_tasks
from savora_backend.database import get_session
from savora_backend.main import create_app

from .fakes import FakeAiGateway

PG_URL = os.getenv("SAVORA_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="SAVORA_TEST_POSTGRES_URL not set")
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

PROFILE = {
    "ageYears": 34,
    "sex": "FEMALE",
    "heightCm": 162.0,
    "weightKg": 58.0,
    "activity": "LIGHT",
    "goal": "MAINTAIN",
    "diet": "VEGETARIAN",
    "cuisinePolicy": "STRICT",
    "cuisines": ["Indian", "Nepali"],
    "excludedIngredients": ["mushroom"],
    "allergies": ["peanut"],
    "allergiesConfirmed": True,
    "conditions": ["HYPERTENSION"],
}


@pytest.fixture
async def pg_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    assert PG_URL is not None
    config = Config(str(ALEMBIC_INI))
    os.environ["DATABASE_URL"] = PG_URL
    await asyncio.to_thread(command.downgrade, config, "base")
    await asyncio.to_thread(command.upgrade, config, "head")
    engine = create_async_engine(PG_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def session() -> AsyncGenerator[object, None]:
        async with factory() as s, s.begin():
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_ai_gateway] = lambda: FakeAiGateway()
    app.state.job_session_factory = factory
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    await engine.dispose()


async def test_full_journey_on_postgres(pg_client: httpx.AsyncClient) -> None:
    reg = await pg_client.post(
        "/api/auth/register",
        json={"email": "pg@example.com", "password": "strongpassword123", "displayName": "Pg"},
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['data']['accessToken']}"}

    prof = await pg_client.put("/api/profile", headers=headers, json=PROFILE)
    assert prof.status_code == 200, prof.text
    stored = prof.json()["data"]["profile"]
    assert stored["cuisines"] == ["Indian", "Nepali"]  # TEXT[] round trip
    assert stored["allergies"] == ["peanut"] and stored["allergiesConfirmedAt"]
    assert prof.json()["data"]["targets"]["energyKcal"]["target"] > 0  # JSONB snapshot

    # Two plan requests at once: the row lock + partial unique index allow exactly one.
    first, second = await asyncio.gather(
        pg_client.post("/api/meal-plans", headers=headers, json={"weekStart": "2026-10-26"}),
        pg_client.post("/api/meal-plans", headers=headers, json={"weekStart": "2026-10-26"}),
    )
    assert sorted([first.status_code, second.status_code]) == [202, 409]
    plan_id = (first if first.status_code == 202 else second).json()["data"]["planId"]
    await wait_for_background_tasks()

    plan = (await pg_client.get(f"/api/meal-plans/{plan_id}", headers=headers)).json()["data"]
    assert plan["status"] == "FEASIBLE" and len(plan["slots"]) == 21
    assert plan["safety"]["status"] == "STAND_IN_UNVERIFIED"
    assert len(plan["dayTotals"]) == 7

    options = await pg_client.post(
        f"/api/meal-plans/{plan_id}/slots/D1_DINNER/replacement-options",
        headers=headers,
        json={"preferenceText": "something creamy"},
    )
    assert options.status_code == 200, options.text

    swap = await pg_client.post(
        f"/api/meal-plans/{plan_id}/substitutions",
        headers=headers,
        json={"slotId": "D1_DINNER", "expectedRevision": 1, "preferenceText": "something creamy"},
    )
    assert swap.status_code == 202, swap.text
    await wait_for_background_tasks()
    sub = await pg_client.get(
        f"/api/substitutions/{swap.json()['data']['substitutionId']}", headers=headers
    )
    body = sub.json()["data"]
    assert body["status"] == "FEASIBLE", body
    assert body["beforeSnapshot"]["slotId"] == "D1_DINNER"
    assert body["preference"]["flavorTags"] == ["CREAMY"]

    plans = (await pg_client.get("/api/meal-plans", headers=headers)).json()["data"]
    assert [p["revision"] for p in plans] == [2, 1]
    assert [p["isCurrent"] for p in plans] == [True, False]
