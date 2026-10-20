"""Tests for Craving NLU: TemplateParser gold benchmark, QwenParser, fallbacks, and safety."""

from pathlib import Path

import httpx
import pytest

from savora_ai.core.craving_nlu import (
    PROMPT_VERSION,
    FakeQwenClient,
    QwenParser,
    TemplateParser,
    parse_craving,
)
from savora_ai.evals.craving_nlu import evaluate_parser, load_gold_set, run_evaluation
from savora_ai.schemas.craving import CravingIntent, FlavorTag


def test_template_parser_meets_gold_set_thresholds() -> None:
    gold_rows = load_gold_set()
    assert len(gold_rows) >= 120
    metrics = evaluate_parser(TemplateParser(), gold_rows)
    assert metrics["schemaValidityRate"] == 1.0
    assert metrics["intentAccuracy"] >= 0.98
    assert metrics["slotPrecision"] >= 0.98
    assert metrics["slotRecall"] >= 0.98
    assert metrics["slotMicroF1"] >= 0.98
    assert metrics["clarificationPrecision"] >= 0.98
    assert metrics["clarificationRecall"] >= 0.98


def test_alias_normalization_and_slots() -> None:
    res = parse_craving("Swap Tuesday lunch for spicy Indian curry without brinjal or capsicum")
    assert res.parser == "TEMPLATE"
    assert res.prompt_version == PROMPT_VERSION
    assert res.request.intent is CravingIntent.SWAP_MEAL
    assert res.request.meal_slot_id == "D2_LUNCH"
    assert res.request.cuisine_ids == ("INDIAN",)
    assert res.request.flavor_tags == (FlavorTag.SPICY,)
    assert set(res.request.excluded_ingredient_ids) == {"EGGPLANT", "BELL_PEPPER"}
    assert res.request.requires_clarification is False


def test_allergy_mentions_never_enter_excluded_ingredients() -> None:
    res = parse_craving("I'm allergic to peanuts, show me Thai dishes")
    assert res.request.excluded_ingredient_ids == ()
    assert res.request.requires_clarification is True
    assert res.clarification is not None
    assert "profile" in res.clarification.lower()

    # Even when QwenParser is used, allergy mentions in text must not allow Qwen to smuggle
    # peanuts into excludedIngredientIds
    malicious_allergy_json = (
        '{"intent":"CRAVING_RECOMMEND","cuisineIds":["THAI"],"flavorTags":[],'
        '"excludedIngredientIds":["PEANUT"],"mealSlotId":null,"requiresClarification":false}'
    )
    qwen = QwenParser(FakeQwenClient([malicious_allergy_json]))
    res_qwen = qwen.parse("I am allergic to peanuts, show me Thai food")
    assert res_qwen.request.excluded_ingredient_ids == ()
    assert res_qwen.request.requires_clarification is True


def test_qwen_parser_valid_json_succeeds() -> None:
    valid_json = (
        '{"intent":"CRAVING_RECOMMEND","cuisineIds":["CHINESE"],"flavorTags":["SPICY"],'
        '"excludedIngredientIds":["NOODLES"],"mealSlotId":null,"requiresClarification":false}'
    )
    client = FakeQwenClient([valid_json])
    parser = QwenParser(client, model="Qwen/Qwen2.5-7B-Instruct")
    res = parser.parse("Craving spicy Chinese without noodles")
    assert res.parser == "QWEN"
    assert res.fallback_reason is None
    assert res.request.cuisine_ids == ("CHINESE",)
    assert res.request.flavor_tags == (FlavorTag.SPICY,)
    assert res.request.excluded_ingredient_ids == ("NOODLES",)
    assert len(client.calls) == 1


@pytest.mark.parametrize(
    "malicious_output",
    [
        # Extra key forbidden by strict CravingRequest
        '{"intent":"CRAVING_RECOMMEND","cuisineIds":["INDIAN"],"unsafe":true}',
        # Invalid enum value
        '{"intent":"SEARCH_RECIPES","cuisineIds":["INDIAN"]}',
        # Invalid flavor enum
        '{"intent":"CRAVING_RECOMMEND","flavorTags":["UMAMI"]}',
        # Prose wrapped around JSON (not pure JSON)
        'Sure! Here is your JSON: {"intent":"CRAVING_RECOMMEND","cuisineIds":["INDIAN"]}',
        # Non-canonical lowercase ID
        '{"intent":"CRAVING_RECOMMEND","cuisineIds":["indian"]}',
        # Duplicate items
        '{"intent":"CRAVING_RECOMMEND","cuisineIds":["INDIAN","INDIAN"]}',
        # SWAP_MEAL without slot or clarification
        '{"intent":"SWAP_MEAL","cuisineIds":["INDIAN"],"requiresClarification":false}',
    ],
)
def test_qwen_parser_falls_back_to_template_on_malicious_output(
    malicious_output: str,
) -> None:
    client = FakeQwenClient([malicious_output])
    parser = QwenParser(client)
    res = parser.parse("Spicy Indian dish without onion")
    assert res.parser == "TEMPLATE"
    assert res.fallback_reason == "QWEN_INVALID_SCHEMA"
    assert res.request.cuisine_ids == ("INDIAN",)
    assert res.request.flavor_tags == (FlavorTag.SPICY,)
    assert res.request.excluded_ingredient_ids == ("ONION",)


def test_qwen_parser_falls_back_on_timeout_and_http_error() -> None:
    timeout_parser = QwenParser(FakeQwenClient([TimeoutError("request timed out")]))
    res1 = timeout_parser.parse("Creamy Thai dish")
    assert res1.parser == "TEMPLATE"
    assert res1.fallback_reason == "QWEN_TIMEOUT"
    assert res1.request.cuisine_ids == ("THAI",)

    httpx_timeout_parser = QwenParser(
        FakeQwenClient([httpx.ReadTimeout("read timed out")])
    )
    res2 = httpx_timeout_parser.parse("Swap Monday lunch for Nepali momo")
    assert res2.parser == "TEMPLATE"
    assert res2.fallback_reason == "QWEN_TIMEOUT"
    assert res2.request.intent is CravingIntent.SWAP_MEAL
    assert res2.request.meal_slot_id == "D1_LUNCH"


def test_eval_runner_writes_json_and_report(tmp_path: Path) -> None:
    json_out = tmp_path / "craving_nlu.json"
    report_out = tmp_path / "craving_nlu_report.md"
    summary = run_evaluation(json_out=json_out, report_out=report_out)
    assert json_out.exists()
    assert report_out.exists()
    assert summary["dataset"]["samples"] >= 120
