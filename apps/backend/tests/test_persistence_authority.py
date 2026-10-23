"""Authority races are tested at await boundaries, without slow AI or a live database."""

import asyncio
import io
from copy import deepcopy
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import httpx
import pytest
from alembic import command
from alembic.config import Config

from savora_ai.core.pipelines import PlanningProfile, SwapProof, WeekPlan
from savora_backend.ai.gateway import get_ai_gateway
from savora_backend.core.meal_plans import wait_for_background_tasks
from savora_backend.core.meal_plans.repository import MealPlanRepository
from savora_backend.core.nutrition_profiles.repository import ProfileRepository

from .fakes import FakeAiGateway
from .test_substitutions import _get_app, _register_and_profile


class GatedGateway(FakeAiGateway):
    def __init__(self, *, stage: Literal["plan", "proof"], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.stage = stage
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def plan_week(
        self,
        profile: PlanningProfile,
        *,
        week_id: str,
        start_date: date,
    ) -> WeekPlan:
        result = await super().plan_week(profile, week_id=week_id, start_date=start_date)
        if self.stage == "plan":
            self.entered.set()
            await self.release.wait()
        return result

    async def prove_swap(self, profile: PlanningProfile, **kwargs: Any) -> SwapProof:
        result = await super().prove_swap(profile, **kwargs)
        if self.stage == "proof":
            self.entered.set()
            await self.release.wait()
        return result


async def ready_plan(
    client: httpx.AsyncClient,
    gateway: FakeAiGateway | None = None,
) -> tuple[dict[str, str], str, FakeAiGateway]:
    headers = await _register_and_profile(client, "authority@example.com")
    gateway = gateway or FakeAiGateway()
    _get_app(client).dependency_overrides[get_ai_gateway] = lambda: gateway
    response = await client.post(
        "/api/meal-plans",
        headers=headers,
        json={"weekStart": "2026-10-26"},
    )
    assert response.status_code == 202, response.text
    await wait_for_background_tasks()
    plan_id = response.json()["data"]["planId"]
    plan = await client.get(f"/api/meal-plans/{plan_id}", headers=headers)
    assert plan.json()["data"]["status"] == "FEASIBLE", plan.text
    return headers, plan_id, gateway


async def update_profile(client: httpx.AsyncClient, headers: dict[str, str]) -> None:
    from .test_profile import _base_profile

    response = await client.put("/api/profile", headers=headers, json=_base_profile(ageYears=42))
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("change", ["profile", "seeds", "targets"])
async def test_profile_change_during_generation_cannot_replace_current_plan(
    db_client: httpx.AsyncClient,
    change: str,
) -> None:
    headers, original_id, _ = await ready_plan(db_client)
    gate = GatedGateway(stage="plan")
    _get_app(db_client).dependency_overrides[get_ai_gateway] = lambda: gate
    response = await db_client.post(
        "/api/meal-plans",
        headers=headers,
        json={"weekStart": "2026-11-02"},
    )
    try:
        await asyncio.wait_for(gate.entered.wait(), 5)
        if change == "profile":
            await update_profile(db_client, headers)
        else:
            factory = _get_app(db_client).state.job_session_factory
            async with factory() as session, session.begin():
                repo = MealPlanRepository(session)
                plan = await repo.get_by_id(UUID(original_id))
                assert plan is not None
                profiles = ProfileRepository(session)
                if change == "seeds":
                    profile = await profiles.lock_by_user_id(plan.user_id)
                    assert profile is not None
                    profile.seed_recipe_ids = ["changed-seed"]
                else:
                    snapshot = await profiles.get_latest_nutrition(plan.user_id, 1)
                    assert snapshot is not None
                    changed = deepcopy(snapshot.targets)
                    changed["provenance"].append("new calculator provenance")
                    snapshot.targets = changed
    finally:
        gate.release.set()
        await asyncio.wait_for(wait_for_background_tasks(), 10)
    result = (
        await db_client.get(
            f"/api/meal-plans/{response.json()['data']['planId']}",
            headers=headers,
        )
    ).json()["data"]
    assert result["status"] == "FAILED" and result["slots"] == []
    assert "profile or targets changed" in result["message"]
    original = (await db_client.get(f"/api/meal-plans/{original_id}", headers=headers)).json()[
        "data"
    ]
    assert original["isCurrent"] is True


@pytest.mark.parametrize(
    "change", ["profile", "revision", "current", "slot", "target", "source", "cancelled"]
)
async def test_authority_change_during_b1_refuses_revision(
    db_client: httpx.AsyncClient,
    change: str,
) -> None:
    initial = FakeAiGateway()
    bundle = replace(initial.bundle, dishes=dict(initial.bundle.dishes))
    gate = GatedGateway(stage="proof", bundle=bundle)
    headers, plan_id, _ = await ready_plan(db_client, gate)
    before = (await db_client.get(f"/api/meal-plans/{plan_id}", headers=headers)).json()["data"]
    response = await db_client.post(
        f"/api/meal-plans/{plan_id}/substitutions",
        headers=headers,
        json={"slotId": "D2_LUNCH", "expectedRevision": 1},
    )
    assert response.status_code == 202, response.text
    try:
        await asyncio.wait_for(gate.entered.wait(), 5)
        # A second concurrent request cannot create a second saved-plan modification.
        other = await db_client.post(
            f"/api/meal-plans/{plan_id}/substitutions",
            headers=headers,
            json={"slotId": "D3_LUNCH", "expectedRevision": 1},
        )
        assert other.status_code == 409
        if change == "profile":
            await update_profile(db_client, headers)
        else:
            factory = _get_app(db_client).state.job_session_factory
            async with factory() as session, session.begin():
                repo = MealPlanRepository(session)
                plan = await repo.get_by_id(UUID(plan_id))
                assert plan is not None
                slots = await repo.get_slots(plan.id)
                if change == "revision":
                    plan.revision += 1
                elif change == "current":
                    plan.is_current = False
                elif change == "slot":
                    slots[0].snapshot = dict(slots[0].snapshot, calendarDate="2027-01-01")
                elif change == "target":
                    target = await ProfileRepository(session).get_latest_nutrition(plan.user_id, 1)
                    assert target is not None
                    changed = deepcopy(target.targets)
                    changed["provenance"].append("changed target source")
                    target.targets = changed
                elif change == "source":
                    meal = bundle.combinations[slots[0].combination_id]
                    dish = bundle.dishes[meal.components[0].dish_id]
                    bundle.dishes[dish.recipe_id] = dish.model_copy(
                        update={"name": "changed source"}
                    )
                elif change == "cancelled":
                    sub = await repo.get_substitution_by_id(
                        UUID(response.json()["data"]["substitutionId"])
                    )
                    assert sub is not None
                    sub.status = "FAILED"
                    sub.message = "Interrupted job"
    finally:
        gate.release.set()
        await asyncio.wait_for(wait_for_background_tasks(), 10)
    sub = (
        await db_client.get(
            f"/api/substitutions/{response.json()['data']['substitutionId']}",
            headers=headers,
        )
    ).json()["data"]
    assert sub["status"] == "FAILED", sub
    assert sub["toPlanId"] is None and sub["afterSnapshot"] is None
    plans = (await db_client.get("/api/meal-plans", headers=headers)).json()["data"]
    assert len(plans) == 1
    if change not in {"slot", "revision", "current"}:
        parent = (await db_client.get(f"/api/meal-plans/{plan_id}", headers=headers)).json()["data"]
        assert parent["slots"] == before["slots"]
        assert parent["isCurrent"] is True


@pytest.mark.parametrize("change", ["legacy", "recipe", "combination", "target", "slot"])
async def test_saved_source_digest_mismatch_is_rejected_before_ai(
    db_client: httpx.AsyncClient,
    change: str,
) -> None:
    fake = FakeAiGateway()
    fake._bundle = replace(
        fake.bundle, dishes=dict(fake.bundle.dishes), combinations=dict(fake.bundle.combinations)
    )
    headers, plan_id, _ = await ready_plan(db_client, fake)
    factory = _get_app(db_client).state.job_session_factory
    async with factory() as session, session.begin():
        repo = MealPlanRepository(session)
        plan = await repo.get_by_id(UUID(plan_id))
        assert plan is not None
        slots = await repo.get_slots(plan.id)
        combo = fake.bundle.combinations[slots[0].combination_id]
        if change == "legacy":
            plan.source_binding = None
        elif change == "recipe":
            dish = fake.bundle.dishes[combo.components[0].dish_id]
            fake.bundle.dishes[dish.recipe_id] = dish.model_copy(
                update={"ingredients": ("changed",)}
            )
        elif change == "combination":
            fake.bundle.combinations[combo.combination_id] = combo.model_copy(
                update={"evidence": ("changed",)}
            )
        elif change == "target":
            binding = deepcopy(plan.source_binding)
            assert binding is not None
            binding["targetDigest"] = "0" * 64
            plan.source_binding = binding
        else:
            slots[0].preset = "HIGHER_ENERGY"
    for suffix, payload in [
        ("slots/D2_LUNCH/replacement-options", {}),
        ("substitutions", {"slotId": "D2_LUNCH", "expectedRevision": 1}),
    ]:
        response = await db_client.post(
            f"/api/meal-plans/{plan_id}/{suffix}", headers=headers, json=payload
        )
        assert response.status_code == 409, response.text
        assert "generate a new plan" in response.json()["message"]
    assert fake.proved == []
    # Refusing reinterpretation does not make the historical snapshot unreadable.
    reloaded = await db_client.get(f"/api/meal-plans/{plan_id}", headers=headers)
    assert reloaded.status_code == 200 and len(reloaded.json()["data"]["slots"]) == 21


async def test_foreign_user_cannot_swap_or_read_substitution(db_client: httpx.AsyncClient) -> None:
    owner, plan_id, _ = await ready_plan(db_client)
    stranger = await _register_and_profile(db_client, "stranger@example.com")
    denied = await db_client.post(
        f"/api/meal-plans/{plan_id}/substitutions",
        headers=stranger,
        json={"slotId": "D2_LUNCH", "expectedRevision": 1},
    )
    assert denied.status_code == 404
    accepted = await db_client.post(
        f"/api/meal-plans/{plan_id}/substitutions",
        headers=owner,
        json={"slotId": "D2_LUNCH", "expectedRevision": 1},
    )
    assert accepted.status_code == 202, accepted.text
    await wait_for_background_tasks()
    response = await db_client.get(
        f"/api/substitutions/{accepted.json()['data']['substitutionId']}",
        headers=stranger,
    )
    assert response.status_code == 404


async def test_b1_receives_full_original_target_snapshot(db_client: httpx.AsyncClient) -> None:
    headers, plan_id, fake = await ready_plan(db_client)
    profile = (await db_client.get("/api/profile", headers=headers)).json()["data"]
    response = await db_client.post(
        f"/api/meal-plans/{plan_id}/substitutions",
        headers=headers,
        json={"slotId": "D2_LUNCH", "expectedRevision": 1},
    )
    assert response.status_code == 202, response.text
    await wait_for_background_tasks()
    assert fake.proved[0]["calculatorPayload"] == profile["targets"]


async def test_majority_policy_is_rejected_in_api_and_openapi(db_client: httpx.AsyncClient) -> None:
    from .test_profile import _base_profile, _register_token

    token = await _register_token(db_client)
    response = await db_client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        json=_base_profile(cuisinePolicy="MAJORITY"),
    )
    assert response.status_code == 422
    assert "cuisinePolicy" in response.json()["description"]
    schema = _get_app(db_client).openapi()["components"]["schemas"]["ProfileUpsertRequest"]
    assert schema["properties"]["cuisinePolicy"]["enum"] == ["MIXED", "STRICT"]


@pytest.mark.parametrize("case", ["unknown_status", "missing_total", "unknown_total"])
async def test_incomplete_or_unknown_proof_never_saves_verified_pass(
    db_client: httpx.AsyncClient,
    case: str,
) -> None:
    class InvalidProofGateway(FakeAiGateway):
        async def prove_swap(self, profile: PlanningProfile, **kwargs: Any) -> SwapProof:
            result = await super().prove_swap(profile, **kwargs)
            if case == "unknown_status":
                return result.model_copy(update={"status": "INSUFFICIENT_DATA", "verified": True})
            totals = result.changed_day_totals
            if case == "missing_total":
                return result.model_copy(update={"changed_day_totals": totals[:-1]})
            unknown = totals[0].model_copy(update={"value": None, "complete": False})
            return result.model_copy(update={"changed_day_totals": (unknown, *totals[1:])})

    headers, plan_id, _ = await ready_plan(db_client, InvalidProofGateway())
    response = await db_client.post(
        f"/api/meal-plans/{plan_id}/substitutions",
        headers=headers,
        json={"slotId": "D2_LUNCH", "expectedRevision": 1},
    )
    assert response.status_code == 202, response.text
    await wait_for_background_tasks()
    sub = (
        await db_client.get(
            f"/api/substitutions/{response.json()['data']['substitutionId']}",
            headers=headers,
        )
    ).json()["data"]
    assert sub["status"] != "FEASIBLE" and sub["toPlanId"] is None
    assert sub["proof"]["verified"] is False
    parent = (await db_client.get(f"/api/meal-plans/{plan_id}", headers=headers)).json()["data"]
    assert parent["isCurrent"] and parent["revision"] == 1


def test_source_binding_migration_compiles_for_postgres_without_backfill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = io.StringIO()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"), output_buffer=output)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://unused:unused@localhost/unused")
    command.upgrade(config, "0007_password_reset:head", sql=True)
    sql = output.getvalue()
    assert "ADD COLUMN source_binding JSONB" in sql
    assert "UPDATE meal_plans" not in sql  # never manufacture history for legacy rows
