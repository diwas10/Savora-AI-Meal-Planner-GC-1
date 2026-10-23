"""Tests for AiRuntime startup loading, manifest verification, and FakeAiGateway."""

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from savora_ai.core.craving_nlu import QwenParser, TemplateParser
from savora_ai.core.pipelines import PlanningProfile, PlanStatus
from savora_ai.schemas.craving import CravingIntent, CravingRequest
from savora_backend.ai.runtime import build_ai_runtime
from savora_backend.config import DEV_JWT_SECRET, get_settings

from .fakes import FakeAiGateway


def test_real_runtime_loads_the_latest_catalogue_export() -> None:
    settings = get_settings()
    latest = sorted(settings.catalogue_dir.glob("*_combinations.json"))[-1]
    export = json.loads(latest.read_text(encoding="utf-8"))
    runtime = build_ai_runtime()
    assert runtime.bundle.version == export["catalogueVersion"]
    assert len(runtime.bundle.combinations) == len(export["combinations"])
    # The Transformer loads only when the downloaded model file is present (ADR 0005 D2).
    assert (runtime.scorer is None) == (not (settings.model_dir / "sasrec_content.pt").exists())


def test_runtime_builds_the_configured_craving_parser() -> None:
    base = get_settings()
    template_only = build_ai_runtime(settings=base.model_copy(update={"qwen_provider": "none"}))
    assert isinstance(template_only.parser, TemplateParser)
    local = build_ai_runtime(settings=base.model_copy(update={"qwen_provider": "ollama"}))
    assert isinstance(local.parser, QwenParser)


def test_production_refuses_the_development_jwt_secret() -> None:
    base = get_settings()
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        base.model_copy(
            update={"app_env": "production", "jwt_secret_key": DEV_JWT_SECRET}
        ).check_secrets()
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        base.model_copy(update={"app_env": "production", "jwt_secret_key": "short"}).check_secrets()
    strong = base.model_copy(update={"app_env": "production", "jwt_secret_key": "a" * 64})
    strong.check_secrets()  # no error


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
