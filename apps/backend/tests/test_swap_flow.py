"""Swap flow (section 4.4 / SCREENS.md): options, chosen replacement, preference, guards."""

from typing import Any

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from savora_ai.core.craving_nlu import TemplateParser
from savora_backend.ai.gateway import get_ai_gateway, get_craving_parser
from savora_backend.core.catalogue import get_catalogue_bundle
from savora_backend.core.meal_plans import (
    MealPlanEntity,
    MealPlanJobStatus,
    wait_for_background_tasks,
)
from savora_backend.database import Base

from .fakes import FakeAiGateway

PROFILE: dict[str, Any] = {
    "ageYears": 30,
    "sex": "FEMALE",
    "heightCm": 165.0,
    "weightKg": 60.0,
    "activity": "MODERATE",
    "goal": "MAINTAIN",
    "diet": None,
    "cuisinePolicy": "MIXED",
    "cuisines": [],
    "excludedIngredients": [],
    "allergies": [],
    "allergiesConfirmed": False,
    "conditions": [],
}


async def _ready_plan(client: httpx.AsyncClient, email: str) -> tuple[dict[str, str], str]:
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "strongpassword123", "displayName": "Swap"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['data']['accessToken']}"}
    assert (await client.put("/api/profile", headers=headers, json=PROFILE)).status_code == 200
    res = await client.post("/api/meal-plans", headers=headers, json={"weekStart": "2026-10-26"})
    plan_id = res.json()["data"]["planId"]
    await wait_for_background_tasks()
    return headers, plan_id


@pytest.fixture
def app_with_fakes(db_client: httpx.AsyncClient) -> FakeAiGateway:
    fake = FakeAiGateway()
    app = db_client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[get_ai_gateway] = lambda: fake
    template = TemplateParser(get_catalogue_bundle().cuisine_ids)
    app.dependency_overrides[get_craving_parser] = lambda: template
    return fake


async def test_replacement_options_are_ranked_and_parsed(
    db_client: httpx.AsyncClient, app_with_fakes: FakeAiGateway
) -> None:
    headers, plan_id = await _ready_plan(db_client, "options@example.com")
    url = f"/api/meal-plans/{plan_id}/slots/D2_LUNCH/replacement-options"
    plain = await db_client.post(url, headers=headers, json={})
    assert plain.status_code == 200, plain.text
    data = plain.json()["data"]
    assert data["parse"] is None
    options = data["result"]["options"]
    assert options and [o["rank"] for o in options] == list(range(1, len(options) + 1))
    assert all(o["combinationId"] != data["result"]["currentCombinationId"] for o in options)
    assert data["result"]["safety"]["status"] == "STAND_IN_UNVERIFIED"

    worded = await db_client.post(
        url, headers=headers, json={"preferenceText": "something without potato"}
    )
    parsed = worded.json()["data"]
    assert parsed["parse"]["parser"] == "TEMPLATE"
    assert parsed["result"]["preference"]["excludedIngredientIds"] == ["POTATO"]

    bad_slot = await db_client.post(
        f"/api/meal-plans/{plan_id}/slots/D9_LUNCH/replacement-options", headers=headers, json={}
    )
    assert bad_slot.status_code == 422


async def test_substitution_uses_the_chosen_option_and_stores_the_preference(
    db_client: httpx.AsyncClient, app_with_fakes: FakeAiGateway
) -> None:
    headers, plan_id = await _ready_plan(db_client, "chosen@example.com")
    url = f"/api/meal-plans/{plan_id}/slots/D3_DINNER/replacement-options"
    options = (await db_client.post(url, headers=headers, json={})).json()["data"]["result"]
    choice = options["options"][-1]["combinationId"]

    res = await db_client.post(
        f"/api/meal-plans/{plan_id}/substitutions",
        headers=headers,
        json={"slotId": "D3_DINNER", "expectedRevision": 1, "replacementCombinationId": choice},
    )
    assert res.status_code == 202, res.text
    await wait_for_background_tasks()
    sub = await db_client.get(
        f"/api/substitutions/{res.json()['data']['substitutionId']}", headers=headers
    )
    body = sub.json()["data"]
    assert body["status"] == "FEASIBLE"
    assert body["replacementCombinationId"] == choice
    assert body["afterSnapshot"]["combinationId"] == choice
    assert app_with_fakes.last_swap["replacement"] == choice

    # A second swap on the new revision with words instead of a choice.
    new_plan = body["toPlanId"]
    res2 = await db_client.post(
        f"/api/meal-plans/{new_plan}/substitutions",
        headers=headers,
        json={"slotId": "D1_LUNCH", "expectedRevision": 2, "preferenceText": "spicy, no rice"},
    )
    assert res2.status_code == 202, res2.text
    await wait_for_background_tasks()
    sub2 = await db_client.get(
        f"/api/substitutions/{res2.json()['data']['substitutionId']}", headers=headers
    )
    preference = sub2.json()["data"]["preference"]
    assert preference["flavorTags"] == ["SPICY"] and preference["excludedIngredientIds"] == ["RICE"]


async def test_unchanged_profile_keeps_its_version(db_client: httpx.AsyncClient) -> None:
    reg = await db_client.post(
        "/api/auth/register",
        json={"email": "same@example.com", "password": "strongpassword123", "displayName": "S"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['data']['accessToken']}"}
    first = await db_client.put("/api/profile", headers=headers, json=PROFILE)
    again = await db_client.put("/api/profile", headers=headers, json=PROFILE)
    changed = await db_client.put("/api/profile", headers=headers, json=PROFILE | {"weightKg": 61})
    versions = [r.json()["data"]["profile"]["version"] for r in (first, again, changed)]
    assert versions == [1, 1, 2]


async def test_cuisine_options_are_the_target_cuisines_only(db_client: httpx.AsyncClient) -> None:
    reg = await db_client.post(
        "/api/auth/register",
        json={"email": "cuis@example.com", "password": "strongpassword123", "displayName": "C"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['data']['accessToken']}"}
    names = [
        c["name"]
        for c in (await db_client.get("/api/catalogue/cuisines", headers=headers)).json()["data"]
    ]
    assert "Nepali" in names and "Korean" in names and "British" not in names
    assert len(names) == 19


def test_database_allows_one_generating_plan_per_user(tmp_path: Any) -> None:
    """The partial unique index backs the service's row lock (migration 0005)."""
    import uuid
    from datetime import date

    from savora_backend.core.users import UserEntity

    engine = create_engine(f"sqlite:///{tmp_path / 'guard.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        user = UserEntity(email="g@example.com", password_hash="x", display_name="G")
        session.add(user)
        session.flush()

        def plan(status: MealPlanJobStatus) -> MealPlanEntity:
            return MealPlanEntity(
                id=uuid.uuid4(),
                user_id=user.id,
                week_start=date(2026, 10, 26),
                status=status.value,
                profile_version=1,
            )

        session.add_all([plan(MealPlanJobStatus.FEASIBLE), plan(MealPlanJobStatus.GENERATING)])
        session.flush()  # finished plans never conflict
        session.add(plan(MealPlanJobStatus.GENERATING))
        with pytest.raises(IntegrityError):
            session.flush()
