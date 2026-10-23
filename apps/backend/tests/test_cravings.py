"""Tests for `POST /api/cravings` with FakeAiGateway, FakeQwenClient, and real pipeline."""

from pathlib import Path

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from savora_ai.core.craving_nlu import FakeQwenClient, QwenParser
from savora_backend.ai.gateway import get_ai_gateway
from savora_backend.core.cravings import get_craving_parser
from savora_backend.database import Base, SyncToAsyncSessionAdapter, get_session
from savora_backend.main import create_app

from .fakes import FakeAiGateway


async def _onboard(client: httpx.AsyncClient, email: str = "crave@example.com") -> dict[str, str]:
    reg = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "securepassword123",
            "displayName": "Craving Tester",
        },
    )
    headers = {"Authorization": f"Bearer {reg.json()['data']['accessToken']}"}
    prof = await client.put(
        "/api/profile",
        headers=headers,
        json={
            "ageYears": 26,
            "sex": "FEMALE",
            "heightCm": 162.0,
            "weightKg": 58.0,
            "activity": "MODERATE",
            "goal": "MAINTAIN",
            "diet": "VEGETARIAN",
            "cuisinePolicy": "MIXED",
            "cuisines": ["Chinese", "Indian"],
            "excludedIngredients": [],
            "allergies": ["peanut"],
            "allergiesConfirmed": True,
            "conditions": [],
        },
    )
    assert prof.status_code == 200
    return headers


async def test_cravings_requires_completed_profile(db_client: httpx.AsyncClient) -> None:
    reg = await db_client.post(
        "/api/auth/register",
        json={
            "email": "no-onboard@example.com",
            "password": "securepassword123",
            "displayName": "No Onboard",
        },
    )
    headers = {"Authorization": f"Bearer {reg.json()['data']['accessToken']}"}
    res = await db_client.post(
        "/api/cravings",
        headers=headers,
        json={"text": "Spicy Chinese without noodles"},
    )
    assert res.status_code == 409
    assert "complete onboarding first" in res.json()["message"]


async def test_cravings_with_fake_gateway_and_fake_qwen(tmp_path: Path) -> None:
    db_file = tmp_path / "crave_fake.db"
    sync_engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(sync_engine)
    sync_maker = sessionmaker(bind=sync_engine, expire_on_commit=False)

    async def override_get_session():
        async with SyncToAsyncSessionAdapter(sync_maker()) as session, session.begin():
            yield session

    fake_gateway = FakeAiGateway()
    scripted_json = (
        '{"intent":"CRAVING_RECOMMEND","cuisineIds":["CHINESE"],"flavorTags":["SPICY"],'
        '"excludedIngredientIds":["NOODLES"],"mealSlotId":null,"requiresClarification":false}'
    )
    fake_qwen = QwenParser(FakeQwenClient([scripted_json]))

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_ai_gateway] = lambda: fake_gateway
    app.dependency_overrides[get_craving_parser] = lambda: fake_qwen

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _onboard(client, "fakeqwen@example.com")
        res = await client.post(
            "/api/cravings",
            headers=headers,
            json={"text": "I want spicy Chinese without noodles"},
        )
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["kind"] == "RECOMMENDATIONS"
        assert data["parse"]["parser"] == "HYBRID"
        assert data["result"]["status"] == "OK"
        assert len(data["result"]["items"]) == 3

    sync_engine.dispose()


async def test_cravings_swap_suggested_and_real_pipeline(
    db_client: httpx.AsyncClient,
) -> None:
    headers = await _onboard(db_client, "realcrave@example.com")

    swap_res = await db_client.post(
        "/api/cravings",
        headers=headers,
        json={"text": "Swap Tuesday lunch for spicy Nepali momo"},
    )
    assert swap_res.status_code == 200
    swap_data = swap_res.json()["data"]
    assert swap_data["kind"] == "SWAP_SUGGESTED"
    assert swap_data["request"]["intent"] == "SWAP_MEAL"
    assert swap_data["request"]["mealSlotId"] == "D2_LUNCH"

    real_res = await db_client.post(
        "/api/cravings",
        headers=headers,
        json={"text": "Spicy Chinese dish without noodles"},
    )
    assert real_res.status_code == 200
    real_data = real_res.json()["data"]
    assert real_data["kind"] == "RECOMMENDATIONS"
    assert real_data["parse"]["parser"] == "TEMPLATE"
    assert real_data["result"]["status"] == "OK"
    assert len(real_data["result"]["items"]) > 0
    assert real_data["result"]["safety"]["status"] == "STAND_IN_UNVERIFIED"
