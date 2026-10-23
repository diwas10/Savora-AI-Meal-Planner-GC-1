"""Full Member 3 E2E backend integration test:
register -> profile -> seed suggestions -> confirm seeds -> craving recommend ->
craving swap intent -> generate weekly plan -> poll FEASIBLE -> substitute slot ->
poll FEASIBLE -> list plans.
"""

from typing import Any

import httpx
from fastapi import FastAPI

from savora_backend.ai.gateway import get_ai_gateway
from savora_backend.core.meal_plans import wait_for_background_tasks
from tests.fakes import FakeAiGateway


def _get_app(client: httpx.AsyncClient) -> FastAPI:
    transport: Any = client._transport
    return transport.app


async def test_member3_end_to_end_journey(db_client: httpx.AsyncClient) -> None:
    app = _get_app(db_client)
    app.dependency_overrides[get_ai_gateway] = lambda: FakeAiGateway()

    # 1. Register a new user
    reg = await db_client.post(
        "/api/auth/register",
        json={
            "email": "e2e@example.com",
            "password": "strongpassword123",
            "displayName": "E2E Member 3 User",
        },
    )
    assert reg.status_code == 201
    token = reg.json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Verify /api/auth/me
    me = await db_client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["email"] == "e2e@example.com"

    # 3. Create profile & compute nutrition targets (with confirmed allergy)
    prof = await db_client.put(
        "/api/profile",
        headers=headers,
        json={
            "ageYears": 29,
            "sex": "FEMALE",
            "heightCm": 166.0,
            "weightKg": 61.0,
            "activity": "MODERATE",
            "goal": "MAINTAIN",
            "diet": "VEGETARIAN",
            "cuisinePolicy": "MIXED",
            "cuisines": ["Indian", "Nepali"],
            "excludedIngredients": ["mushroom"],
            "allergies": ["peanut"],
            "allergiesConfirmed": True,
            "conditions": ["HYPERTENSION"],
        },
    )
    assert prof.status_code == 200
    prof_data = prof.json()["data"]
    assert prof_data["profile"]["version"] == 1
    assert prof_data["needsSeedPicks"] is True
    assert prof_data["targets"]["energyKcal"]["target"] > 1200

    # 4. Get onboarding seed suggestions and confirm 3 seed dishes
    sug = await db_client.get("/api/onboarding/seed-suggestions", headers=headers)
    assert sug.status_code == 200
    suggestions = sug.json()["data"]["suggestions"]
    assert len(suggestions) == 12
    picks = [s["recipeId"] for s in suggestions[:3]]

    confirm = await db_client.put(
        "/api/onboarding/seed-picks",
        headers=headers,
        json={"recipeIds": picks},
    )
    assert confirm.status_code == 200
    assert confirm.json()["data"]["seedRecipeIds"] == picks

    prof_after_seeds = await db_client.get("/api/profile", headers=headers)
    assert prof_after_seeds.json()["data"]["needsSeedPicks"] is False

    # 5. Standalone craving recommendation
    crav1 = await db_client.post(
        "/api/cravings",
        headers=headers,
        json={"text": "something spicy Chinese without noodles"},
    )
    assert crav1.status_code == 200
    crav1_data = crav1.json()["data"]
    assert crav1_data["kind"] == "RECOMMENDATIONS"
    assert crav1_data["result"]["request"]["cuisineIds"] == ["CHINESE"]
    assert crav1_data["result"]["request"]["flavorTags"] == ["SPICY"]
    assert crav1_data["result"]["request"]["excludedIngredientIds"] == ["NOODLES"]
    assert crav1_data["result"]["safety"]["status"] == "STAND_IN_UNVERIFIED"
    assert len(crav1_data["result"]["items"]) >= 1

    # 6. Craving swap intent detection
    crav2 = await db_client.post(
        "/api/cravings",
        headers=headers,
        json={"text": "swap Tuesday lunch for something Thai"},
    )
    assert crav2.status_code == 200
    crav2_data = crav2.json()["data"]
    assert crav2_data["kind"] == "SWAP_SUGGESTED"
    assert crav2_data["request"]["intent"] == "SWAP_MEAL"
    assert crav2_data["request"]["mealSlotId"] == "D2_LUNCH"

    # 7. Generate weekly meal plan (background job)
    plan_post = await db_client.post(
        "/api/meal-plans",
        headers=headers,
        json={"weekStart": "2026-10-26"},
    )
    assert plan_post.status_code == 202
    plan1_id = plan_post.json()["data"]["planId"]
    assert plan_post.json()["data"]["status"] == "GENERATING"

    await wait_for_background_tasks()

    plan1_get = await db_client.get(f"/api/meal-plans/{plan1_id}", headers=headers)
    assert plan1_get.status_code == 200
    plan1 = plan1_get.json()["data"]
    assert plan1["status"] == "FEASIBLE"
    assert plan1["isCurrent"] is True
    assert plan1["revision"] == 1
    assert len(plan1["slots"]) == 21
    assert len(plan1["dayTotals"]) == 7

    # 8. Substitute slot D2_LUNCH (background job)
    sub_post = await db_client.post(
        f"/api/meal-plans/{plan1_id}/substitutions",
        headers=headers,
        json={"slotId": "D2_LUNCH", "expectedRevision": 1},
    )
    assert sub_post.status_code == 202
    sub_id = sub_post.json()["data"]["substitutionId"]

    await wait_for_background_tasks()

    sub_get = await db_client.get(f"/api/substitutions/{sub_id}", headers=headers)
    assert sub_get.status_code == 200
    sub_data = sub_get.json()["data"]
    assert sub_data["status"] == "FEASIBLE"
    plan2_id = sub_data["toPlanId"]
    assert plan2_id is not None and plan2_id != plan1_id

    # 9. Verify plan list & current revision
    all_plans = await db_client.get("/api/meal-plans", headers=headers)
    assert all_plans.status_code == 200
    assert len(all_plans.json()["data"]) == 2

    current_plans = await db_client.get("/api/meal-plans?current=true", headers=headers)
    assert current_plans.status_code == 200
    assert len(current_plans.json()["data"]) == 1
    assert current_plans.json()["data"][0]["id"] == plan2_id
    assert current_plans.json()["data"][0]["revision"] == 2
