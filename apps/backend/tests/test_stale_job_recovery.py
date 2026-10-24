"""Tests for meal plan stuck generation recovery, timeouts, and cancellation."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from fastapi import FastAPI

from savora_ai.core.pipelines import PlanningProfile, WeekPlan
from savora_backend.ai.gateway import get_ai_gateway
from savora_backend.core.meal_plans import (
    MealPlanEntity,
    MealPlanJobStatus,
    wait_for_background_tasks,
)
from savora_backend.core.meal_plans.entity import CANCELLED_MESSAGE, PLAN_TIMEOUT_MESSAGE
from tests.fakes import FakeAiGateway


async def _setup_user_with_profile(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    reg = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "strongpassword123",
            "displayName": "Stale Test User",
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    prof = await client.put(
        "/api/profile",
        headers=headers,
        json={
            "ageYears": 28,
            "sex": "FEMALE",
            "heightCm": 165.0,
            "weightKg": 58.0,
            "activity": "LIGHT",
            "goal": "MAINTAIN",
            "diet": None,
            "cuisines": ["Nepali"],
            "cuisinePolicy": "MIXED",
            "excludedIngredients": [],
            "allergies": [],
            "allergiesConfirmed": False,
            "conditions": [],
        },
    )
    assert prof.status_code == 200, prof.text
    return headers


def _get_app(client: httpx.AsyncClient) -> FastAPI:
    transport: Any = client._transport
    return transport.app


async def test_stale_generating_job_auto_recovered_on_query(db_client: httpx.AsyncClient) -> None:
    """A stuck GENERATING plan older than 180s is reaped as TIMEOUT when queried."""
    headers = await _setup_user_with_profile(db_client, email="stale1@example.com")
    app = _get_app(db_client)
    app.dependency_overrides[get_ai_gateway] = lambda: FakeAiGateway()

    # 1. Start generation
    resp = await db_client.post(
        "/api/meal-plans",
        headers=headers,
        json={"weekStart": "2026-10-19"},
    )
    assert resp.status_code == 202
    plan_id = resp.json()["data"]["planId"]
    await wait_for_background_tasks()

    # 2. Simulate the plan being orphaned in GENERATING state 5 minutes ago
    job_factory = app.state.job_session_factory
    async with job_factory() as session, session.begin():
        plan = await session.get(MealPlanEntity, UUID(plan_id))
        assert plan is not None
        plan.status = MealPlanJobStatus.GENERATING.value
        plan.created_at = datetime.now(UTC) - timedelta(minutes=5)

    # 3. Reading the plan triggers stale job recovery and returns TIMEOUT
    detail = await db_client.get(f"/api/meal-plans/{plan_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == MealPlanJobStatus.TIMEOUT.value
    assert detail.json()["data"]["message"] == PLAN_TIMEOUT_MESSAGE

    # 4. User is no longer blocked by 409 conflict when starting a new plan
    new_plan_resp = await db_client.post(
        "/api/meal-plans",
        headers=headers,
        json={"weekStart": "2026-10-26"},
    )
    assert new_plan_resp.status_code == 202
    await wait_for_background_tasks()


async def test_cancel_generating_meal_plan(db_client: httpx.AsyncClient) -> None:
    """User can explicitly cancel a generating plan."""
    headers1 = await _setup_user_with_profile(db_client, email="cancel1@example.com")
    headers2 = await _setup_user_with_profile(db_client, email="cancel2@example.com")
    app = _get_app(db_client)
    app.dependency_overrides[get_ai_gateway] = lambda: FakeAiGateway()

    # Create plan and put in GENERATING
    resp = await db_client.post(
        "/api/meal-plans",
        headers=headers1,
        json={"weekStart": "2026-10-19"},
    )
    plan_id = resp.json()["data"]["planId"]
    await wait_for_background_tasks()

    job_factory = app.state.job_session_factory
    async with job_factory() as session, session.begin():
        plan = await session.get(MealPlanEntity, UUID(plan_id))
        assert plan is not None
        plan.status = MealPlanJobStatus.GENERATING.value

    # Other user cannot cancel it
    other_cancel = await db_client.post(f"/api/meal-plans/{plan_id}/cancel", headers=headers2)
    assert other_cancel.status_code == 404

    # Owner cancels it
    cancel_resp = await db_client.post(f"/api/meal-plans/{plan_id}/cancel", headers=headers1)
    assert cancel_resp.status_code == 200
    data = cancel_resp.json()["data"]
    assert data["status"] == MealPlanJobStatus.FAILED.value
    assert data["message"] == CANCELLED_MESSAGE

    # Cancelling again returns 409 Conflict
    repeat_cancel = await db_client.post(f"/api/meal-plans/{plan_id}/cancel", headers=headers1)
    assert repeat_cancel.status_code == 409


class TimingOutAiGateway(FakeAiGateway):
    async def plan_week(
        self, profile: PlanningProfile, *, week_id: str, start_date: Any
    ) -> WeekPlan:
        raise TimeoutError("Simulated pipeline timeout")


async def test_plan_week_job_handles_timeout(db_client: httpx.AsyncClient) -> None:
    """A TimeoutError during AI generation transitions the plan to TIMEOUT."""
    headers = await _setup_user_with_profile(db_client, email="timeout@example.com")
    app = _get_app(db_client)
    app.dependency_overrides[get_ai_gateway] = lambda: TimingOutAiGateway()

    resp = await db_client.post(
        "/api/meal-plans",
        headers=headers,
        json={"weekStart": "2026-10-19"},
    )
    assert resp.status_code == 202
    plan_id = resp.json()["data"]["planId"]
    await wait_for_background_tasks()

    detail = await db_client.get(f"/api/meal-plans/{plan_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == MealPlanJobStatus.TIMEOUT.value
    assert detail.json()["data"]["message"] == PLAN_TIMEOUT_MESSAGE
