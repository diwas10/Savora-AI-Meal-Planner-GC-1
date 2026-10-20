"""Tests for onboarding seed suggestions, seed picks, revalidation, and dish search."""

import httpx


async def _setup_user_and_profile(
    client: httpx.AsyncClient,
    email: str = "seeds@example.com",
    diet: str | None = "VEGETARIAN",
) -> dict[str, str]:
    reg = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "securepassword123",
            "displayName": "Seed Tester",
        },
    )
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
            "diet": diet,
            "cuisinePolicy": "MIXED",
            "cuisines": ["Indian"],
            "excludedIngredients": [],
            "allergies": [],
            "allergiesConfirmed": False,
            "conditions": [],
        },
    )
    assert prof.status_code == 200
    return headers


async def test_seed_suggestions_requires_completed_profile(
    db_client: httpx.AsyncClient,
) -> None:
    reg = await db_client.post(
        "/api/auth/register",
        json={
            "email": "noprof@example.com",
            "password": "securepassword123",
            "displayName": "No Prof",
        },
    )
    headers = {"Authorization": f"Bearer {reg.json()['data']['accessToken']}"}
    res = await db_client.get("/api/onboarding/seed-suggestions", headers=headers)
    assert res.status_code == 409


async def test_seed_suggestions_confirm_and_revalidation(
    db_client: httpx.AsyncClient,
) -> None:
    headers = await _setup_user_and_profile(db_client, "flow@example.com", diet=None)

    sug = await db_client.get("/api/onboarding/seed-suggestions", headers=headers)
    assert sug.status_code == 200
    suggestions = sug.json()["data"]["suggestions"]
    assert len(suggestions) == 12
    picks = [s["recipeId"] for s in suggestions[:3]]

    too_few = await db_client.put(
        "/api/onboarding/seed-picks",
        headers=headers,
        json={"recipeIds": picks[:2]},
    )
    assert too_few.status_code == 422

    saved = await db_client.put(
        "/api/onboarding/seed-picks",
        headers=headers,
        json={"recipeIds": picks},
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["seedRecipeIds"] == picks

    prof = await db_client.get("/api/profile", headers=headers)
    assert prof.status_code == 200
    assert prof.json()["data"]["profile"]["seedRecipeIds"] == picks
    assert prof.json()["data"]["profile"]["version"] == 1
    assert prof.json()["data"]["needsSeedPicks"] is False


async def test_catalogue_dish_search(db_client: httpx.AsyncClient) -> None:
    headers = await _setup_user_and_profile(db_client, "search@example.com")
    res = await db_client.get("/api/catalogue/dishes?q=curry", headers=headers)
    assert res.status_code == 200
    dishes = res.json()["data"]
    assert isinstance(dishes, list) and len(dishes) > 0
    assert all(d["recipeId"].startswith("FC_") for d in dishes)
