"""Tests for S7: weekly meal plans table, background job runner, and endpoints."""

from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI

from savora_ai.core.pipelines import PlanStatus
from savora_backend.ai.gateway import get_ai_gateway
from savora_backend.core.meal_plans import (
    MealPlanEntity,
    MealPlanJobStatus,
    mark_stale_generating_jobs_failed,
    wait_for_background_tasks,
)
from tests.fakes import FakeAiGateway


async def _register_and_profile(
    client: httpx.AsyncClient, email: str = "planner@example.com"
) -> dict[str, str]:
    reg = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "strongpassword123",
            "displayName": "Test Planner",
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    prof = await client.put(
        "/api/profile",
        headers=headers,
        json={
            "ageYears": 30,
            "sex": "MALE",
            "heightCm": 175.0,
            "weightKg": 70.0,
            "activity": "MODERATE",
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


async def test_meal_plan_requires_profile(db_client: httpx.AsyncClient) -> None:
    reg = await db_client.post(
        "/api/auth/register",
        json={
            "email": "noprof@example.com",
            "password": "strongpassword123",
            "displayName": "No Prof",
        },
    )
    headers = {"Authorization": f"Bearer {reg.json()['data']['accessToken']}"}

    resp = await db_client.post(
        "/api/meal-plans",
        headers=headers,
        json={"weekStart": "2026-10-19"},
    )
    assert resp.status_code == 409
    assert "onboarding" in resp.json()["message"].lower()


async def test_meal_plan_lifecycle_with_fake_gateway(db_client: httpx.AsyncClient) -> None:
    headers = await _register_and_profile(db_client)
    app = _get_app(db_client)
    fake_gw = FakeAiGateway()
    app.dependency_overrides[get_ai_gateway] = lambda: fake_gw

    post_resp = await db_client.post(
        "/api/meal-plans",
        headers=headers,
        json={"weekStart": "2026-10-19"},
    )
    assert post_resp.status_code == 202
    data = post_resp.json()["data"]
    plan_id = data["planId"]
    assert data["status"] == "GENERATING"

    await wait_for_background_tasks()

    get_resp = await db_client.get(f"/api/meal-plans/{plan_id}", headers=headers)
    assert get_resp.status_code == 200
    detail = get_resp.json()["data"]
    assert detail["status"] == "FEASIBLE"
    assert detail["isCurrent"] is True
    assert detail["revision"] == 1
    assert len(detail["slots"]) == 21
    assert len(detail["dayTotals"]) == 7
    assert detail["safety"]["status"] == "STAND_IN_UNVERIFIED"
    assert detail["slots"][0]["slotId"] == "D1_BREAKFAST"

    list_resp = await db_client.get("/api/meal-plans?current=true", headers=headers)
    assert list_resp.status_code == 200
    plans = list_resp.json()["data"]
    assert len(plans) == 1
    assert plans[0]["id"] == plan_id


async def test_meal_plan_failed_job_and_non_feasible_status(
    db_client: httpx.AsyncClient,
) -> None:
    headers = await _register_and_profile(db_client, email="fail@example.com")
    app = _get_app(db_client)

    app.dependency_overrides[get_ai_gateway] = lambda: FakeAiGateway(fail_plan=True)
    resp1 = await db_client.post(
        "/api/meal-plans",
        headers=headers,
        json={"weekStart": "2026-10-19"},
    )
    assert resp1.status_code == 202
    plan1_id = resp1.json()["data"]["planId"]
    await wait_for_background_tasks()

    get1 = await db_client.get(f"/api/meal-plans/{plan1_id}", headers=headers)
    assert get1.status_code == 200
    assert get1.json()["data"]["status"] == "FAILED"
    assert "Simulated solver crash" in get1.json()["data"]["message"]
    assert get1.json()["data"]["slots"] == []

    app.dependency_overrides[get_ai_gateway] = lambda: FakeAiGateway(
        plan_status=PlanStatus.INSUFFICIENT_DATA
    )
    resp2 = await db_client.post(
        "/api/meal-plans",
        headers=headers,
        json={"weekStart": "2026-10-19"},
    )
    assert resp2.status_code == 202
    plan2_id = resp2.json()["data"]["planId"]
    await wait_for_background_tasks()

    get2 = await db_client.get(f"/api/meal-plans/{plan2_id}", headers=headers)
    assert get2.status_code == 200
    assert get2.json()["data"]["status"] == "INSUFFICIENT_DATA"
    assert get2.json()["data"]["slots"] == []
    assert get2.json()["data"]["isCurrent"] is False


async def test_meal_plan_ownership_and_concurrency_and_startup_cleanup(
    db_client: httpx.AsyncClient,
) -> None:
    headers1 = await _register_and_profile(db_client, email="u1@example.com")
    headers2 = await _register_and_profile(db_client, email="u2@example.com")
    app = _get_app(db_client)
    app.dependency_overrides[get_ai_gateway] = lambda: FakeAiGateway()

    post_resp = await db_client.post(
        "/api/meal-plans",
        headers=headers1,
        json={"weekStart": "2026-10-19"},
    )
    plan_id = post_resp.json()["data"]["planId"]
    await wait_for_background_tasks()

    # Ownership check: u2 cannot read u1's plan
    other_get = await db_client.get(f"/api/meal-plans/{plan_id}", headers=headers2)
    assert other_get.status_code == 404

    # Simulate a stale GENERATING row in DB and test concurrency + startup cleanup
    job_factory = app.state.job_session_factory
    async with job_factory() as session, session.begin():
        plan = await session.get(MealPlanEntity, UUID(plan_id))
        assert plan is not None
        plan.status = MealPlanJobStatus.GENERATING.value

    conflict = await db_client.post(
        "/api/meal-plans",
        headers=headers1,
        json={"weekStart": "2026-10-26"},
    )
    assert conflict.status_code == 409

    cleaned = await mark_stale_generating_jobs_failed(job_factory)
    assert cleaned == 1

    after_cleanup = await db_client.get(f"/api/meal-plans/{plan_id}", headers=headers1)
    assert after_cleanup.json()["data"]["status"] == "FAILED"
    assert after_cleanup.json()["data"]["message"] == "server restarted"


@pytest.mark.slow
async def test_meal_plan_real_pipeline_insufficient_data(
    db_client: httpx.AsyncClient,
) -> None:
    """Real PipelineAiGateway integration test (runs without FakeAiGateway)."""
    reg = await db_client.post(
        "/api/auth/register",
        json={
            "email": "realpipe@example.com",
            "password": "strongpassword123",
            "displayName": "Real Pipe",
        },
    )
    headers = {"Authorization": f"Bearer {reg.json()['data']['accessToken']}"}
    # Strict Nepali-only profile has < 4 distinct breakfasts, triggering INSUFFICIENT_DATA
    prof = await db_client.put(
        "/api/profile",
        headers=headers,
        json={
            "ageYears": 30,
            "sex": "MALE",
            "heightCm": 175.0,
            "weightKg": 70.0,
            "activity": "MODERATE",
            "goal": "MAINTAIN",
            "diet": None,
            "cuisines": ["Nepali"],
            "cuisinePolicy": "STRICT",
            "excludedIngredients": [],
            "allergies": [],
            "allergiesConfirmed": False,
            "conditions": [],
        },
    )
    assert prof.status_code == 200, prof.text
    post_resp = await db_client.post(
        "/api/meal-plans",
        headers=headers,
        json={"weekStart": "2026-10-19"},
    )
    assert post_resp.status_code == 202
    plan_id = post_resp.json()["data"]["planId"]
    await wait_for_background_tasks()

    get_resp = await db_client.get(f"/api/meal-plans/{plan_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["status"] == "INSUFFICIENT_DATA"
    assert "breakfast" in get_resp.json()["data"]["message"]
