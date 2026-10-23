"""Tests for profile upsert, target snapshot versioning, allergy confirmation, and cuisines."""

import httpx


async def _register_token(client: httpx.AsyncClient, email: str = "prof@example.com") -> str:
    res = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "securepassword123",
            "displayName": "Profile Tester",
        },
    )
    assert res.status_code == 201
    return str(res.json()["data"]["accessToken"])


def _base_profile(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "ageYears": 28,
        "sex": "FEMALE",
        "heightCm": 165.0,
        "weightKg": 60.0,
        "activity": "MODERATE",
        "goal": "MAINTAIN",
        "diet": "VEGETARIAN",
        "cuisinePolicy": "MIXED",
        "cuisines": ["Indian", "Nepali"],
        "excludedIngredients": ["mushroom"],
        "allergies": [],
        "allergiesConfirmed": False,
        "conditions": ["HYPERTENSION"],
    }
    payload.update(overrides)
    return payload


async def test_profile_create_update_and_versioned_targets(
    db_client: httpx.AsyncClient,
) -> None:
    token = await _register_token(db_client, "v1@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    missing = await db_client.get("/api/profile", headers=headers)
    assert missing.status_code == 404

    put1 = await db_client.put(
        "/api/profile",
        headers=headers,
        json=_base_profile(),
    )
    assert put1.status_code == 200
    data1 = put1.json()["data"]
    assert data1["profile"]["version"] == 1
    assert data1["targets"]["profileVersion"] == 1
    assert data1["targets"]["method"] == "MIFFLIN_ST_JEOR"
    assert data1["needsSeedPicks"] is True
    kcal1 = data1["targets"]["energyKcal"]["target"]
    assert isinstance(kcal1, (int, float)) and kcal1 > 1000

    put2 = await db_client.put(
        "/api/profile",
        headers=headers,
        json=_base_profile(
            weightKg=72.0,
            goal="GAIN",
            allergies=["peanut"],
            allergiesConfirmed=True,
        ),
    )
    assert put2.status_code == 200
    data2 = put2.json()["data"]
    assert data2["profile"]["version"] == 2
    assert data2["profile"]["allergies"] == ["peanut"]
    assert data2["profile"]["allergiesConfirmedAt"] is not None
    assert data2["targets"]["profileVersion"] == 2
    assert data2["targets"]["energyKcal"]["target"] > kcal1

    get_res = await db_client.get("/api/profile", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["profile"]["version"] == 2


async def test_unconfirmed_allergies_return_422(db_client: httpx.AsyncClient) -> None:
    token = await _register_token(db_client, "allergy@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    res = await db_client.put(
        "/api/profile",
        headers=headers,
        json=_base_profile(allergies=["peanut"], allergiesConfirmed=False),
    )
    assert res.status_code == 422
    body = res.json()
    assert body["success"] is False
    assert "allergiesConfirmed" in body["description"]


async def test_catalogue_cuisines_endpoint(db_client: httpx.AsyncClient) -> None:
    token = await _register_token(db_client, "cuisines@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    res = await db_client.get("/api/catalogue/cuisines", headers=headers)
    assert res.status_code == 200
    items = res.json()["data"]
    assert isinstance(items, list) and len(items) > 0
    by_id = {item["id"]: item["name"] for item in items}
    assert by_id["NEPALI"] == "Nepali"
    assert by_id["MIDDLE_EASTERN"] == "Middle Eastern"
