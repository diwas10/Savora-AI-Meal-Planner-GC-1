"""Tests for S8: meal plan slot substitutions, revision locking, and profile version checks."""

from typing import Any

import httpx
from fastapi import FastAPI

from savora_ai.core.pipelines import PlanStatus
from savora_backend.ai.gateway import get_ai_gateway
from savora_backend.core.meal_plans import wait_for_background_tasks
from tests.fakes import FakeAiGateway


async def _register_and_profile(
    client: httpx.AsyncClient, email: str = "sub@example.com"
) -> dict[str, str]:
    reg = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "strongpassword123",
            "displayName": "Swap Tester",
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


async def test_substitution_creates_revision_and_preserves_locked_slots(
    db_client: httpx.AsyncClient,
) -> None:
    headers = await _register_and_profile(db_client)
    app = _get_app(db_client)
    app.dependency_overrides[get_ai_gateway] = lambda: FakeAiGateway()

    plan_post = await db_client.post(
        "/api/meal-plans",
        headers=headers,
        json={"weekStart": "2026-10-19"},
    )
    assert plan_post.status_code == 202
    plan1_id = plan_post.json()["data"]["planId"]
    await wait_for_background_tasks()

    plan1_resp = await db_client.get(f"/api/meal-plans/{plan1_id}", headers=headers)
    assert plan1_resp.status_code == 200
    plan1 = plan1_resp.json()["data"]
    assert plan1["revision"] == 1
    assert plan1["isCurrent"] is True
    plan1_slots = {s["slotId"]: s for s in plan1["slots"]}

    sub_post = await db_client.post(
        f"/api/meal-plans/{plan1_id}/substitutions",
        headers=headers,
        json={
            "slotId": "D2_LUNCH",
            "expectedRevision": 1,
            "excludeCombinationIds": [],
        },
    )
    assert sub_post.status_code == 202
    sub_id = sub_post.json()["data"]["substitutionId"]
    assert sub_post.json()["data"]["status"] == "GENERATING"

    await wait_for_background_tasks()

    sub_get = await db_client.get(f"/api/substitutions/{sub_id}", headers=headers)
    assert sub_get.status_code == 200
    sub_data = sub_get.json()["data"]
    assert sub_data["status"] == "FEASIBLE"
    assert sub_data["fromPlanId"] == plan1_id
    plan2_id = sub_data["toPlanId"]
    assert plan2_id is not None and plan2_id != plan1_id
    assert sub_data["slotId"] == "D2_LUNCH"
    assert sub_data["beforeSnapshot"]["optionId"] == plan1_slots["D2_LUNCH"]["optionId"]
    assert sub_data["afterSnapshot"]["optionId"] != plan1_slots["D2_LUNCH"]["optionId"]

    # Check old plan is no longer current
    plan1_after = await db_client.get(f"/api/meal-plans/{plan1_id}", headers=headers)
    assert plan1_after.json()["data"]["isCurrent"] is False

    # Check new plan is revision 2, current, and 20 locked slots are identical
    plan2_resp = await db_client.get(f"/api/meal-plans/{plan2_id}", headers=headers)
    assert plan2_resp.status_code == 200
    plan2 = plan2_resp.json()["data"]
    assert plan2["revision"] == 2
    assert plan2["parentPlanId"] == plan1_id
    assert plan2["isCurrent"] is True
    plan2_slots = {s["slotId"]: s for s in plan2["slots"]}

    changed_slots = [
        sid
        for sid in plan1_slots
        if plan1_slots[sid]["optionId"] != plan2_slots[sid]["optionId"]
    ]
    assert changed_slots == ["D2_LUNCH"]
    for sid in plan1_slots:
        if sid != "D2_LUNCH":
            assert plan1_slots[sid]["snapshot"] == plan2_slots[sid]["snapshot"]


async def test_substitution_conflicts_on_revision_and_profile_change(
    db_client: httpx.AsyncClient,
) -> None:
    headers = await _register_and_profile(db_client, email="subconflict@example.com")
    app = _get_app(db_client)
    app.dependency_overrides[get_ai_gateway] = lambda: FakeAiGateway()

    plan_post = await db_client.post(
        "/api/meal-plans",
        headers=headers,
        json={"weekStart": "2026-10-19"},
    )
    plan1_id = plan_post.json()["data"]["planId"]
    await wait_for_background_tasks()

    # Wrong expectedRevision -> 409
    bad_rev = await db_client.post(
        f"/api/meal-plans/{plan1_id}/substitutions",
        headers=headers,
        json={"slotId": "D1_LUNCH", "expectedRevision": 99},
    )
    assert bad_rev.status_code == 409
    assert "revision" in bad_rev.json()["message"].lower()

    # Non-feasible swap outcome leaves original plan current
    app.dependency_overrides[get_ai_gateway] = lambda: FakeAiGateway(
        swap_status=PlanStatus.INSUFFICIENT_DATA
    )
    sub_insuf = await db_client.post(
        f"/api/meal-plans/{plan1_id}/substitutions",
        headers=headers,
        json={"slotId": "D1_LUNCH", "expectedRevision": 1},
    )
    assert sub_insuf.status_code == 202
    sub_insuf_id = sub_insuf.json()["data"]["substitutionId"]
    await wait_for_background_tasks()

    sub_insuf_get = await db_client.get(
        f"/api/substitutions/{sub_insuf_id}", headers=headers
    )
    assert sub_insuf_get.json()["data"]["status"] == "INSUFFICIENT_DATA"
    assert sub_insuf_get.json()["data"]["toPlanId"] is None

    # Update profile -> increments profile.version to 2 -> 409 conflict
    await db_client.put(
        "/api/profile",
        headers=headers,
        json={
            "ageYears": 31,
            "sex": "MALE",
            "heightCm": 175.0,
            "weightKg": 71.0,
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
    prof_changed = await db_client.post(
        f"/api/meal-plans/{plan1_id}/substitutions",
        headers=headers,
        json={"slotId": "D1_LUNCH", "expectedRevision": 1},
    )
    assert prof_changed.status_code == 409
    assert prof_changed.json()["message"] == "profile changed; generate a new plan"
