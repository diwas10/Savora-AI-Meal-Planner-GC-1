"""Tests for AiRuntime startup loading, manifest verification, and FakeAiGateway."""

import shutil
from datetime import date
from pathlib import Path

import pytest

from savora_ai.core.pipelines import PlanningProfile, PlanStatus
from savora_ai.schemas.craving import CravingIntent, CravingRequest
from savora_backend.ai.runtime import build_ai_runtime
from savora_backend.config import get_settings

from .fakes import FakeAiGateway


def test_real_runtime_loads_catalogue_export_and_fallback() -> None:
    runtime = build_ai_runtime()
    assert len(runtime.bundle.combinations) == 465
    assert runtime.bundle.version == "20261019T012206Z"
    assert runtime.scorer is None


def test_runtime_refuses_corrupt_model_file(tmp_path: Path) -> None:
    settings = get_settings()
    mod_dir = tmp_path / "models"
    mod_dir.mkdir(parents=True)
    shutil.copy(settings.model_dir / "manifest.json", mod_dir / "manifest.json")
    (mod_dir / "sasrec_content.pt").write_bytes(b"corrupted-checkpoint")

    with pytest.raises(RuntimeError, match="model integrity error"):
        build_ai_runtime(model_dir=mod_dir)


async def test_fake_ai_gateway_returns_contract_valid_models() -> None:
    fake = FakeAiGateway()
    prof = PlanningProfile(profile_id="user-1", profile_version=1)
    req = CravingRequest(intent=CravingIntent.CRAVING_RECOMMEND, cuisine_ids=("INDIAN",))
    crav = await fake.craving(req, prof)
    assert len(crav.items) == 3

    week = await fake.plan_week(prof, week_id="w-1", start_date=date(2026, 10, 26))
    assert week.status is PlanStatus.FEASIBLE
    assert len(week.meals) == 21
