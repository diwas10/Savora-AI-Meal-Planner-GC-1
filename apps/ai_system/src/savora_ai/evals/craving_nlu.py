"""Evaluation runner for Craving NLU (`TemplateParser` vs `QwenParser` when configured).

Run:
    uv run python -m savora_ai.evals.craving_nlu
"""

import json
import os
import platform
import statistics
from pathlib import Path
from typing import Any

from savora_ai.core.craving_nlu import (
    PROMPT_VERSION,
    CravingParser,
    HttpxQwenClient,
    QwenParser,
    TemplateParser,
)
from savora_ai.schemas.craving import CravingRequest

GOLD_PATH = Path(__file__).resolve().parent / "craving_nlu_gold.jsonl"
REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_JSON_OUT = REPO_ROOT / "docs/eval/craving_nlu.json"
DEFAULT_REPORT_OUT = REPO_ROOT / "docs/reports/craving_nlu_report.md"


def load_gold_set(path: Path = GOLD_PATH) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        item["gold"] = CravingRequest.model_validate_json(json.dumps(item["expected"]))
        rows.append(item)
    return rows


def _slot_pairs(req: CravingRequest) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for cid in req.cuisine_ids:
        pairs.add(("cuisine_id", cid))
    for ftag in req.flavor_tags:
        pairs.add(("flavor_tag", ftag.value))
    for ex in req.excluded_ingredient_ids:
        pairs.add(("excluded_ingredient_id", ex))
    if req.meal_slot_id is not None:
        pairs.add(("meal_slot_id", req.meal_slot_id))
    return pairs


def evaluate_parser(
    parser: CravingParser,
    gold_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = gold_rows if gold_rows is not None else load_gold_set()
    n = len(rows)
    intent_correct = 0
    schema_valid = 0
    slot_tp = 0
    slot_fp = 0
    slot_fn = 0
    clar_tp = 0
    clar_fp = 0
    clar_fn = 0
    latencies: list[float] = []

    for row in rows:
        gold: CravingRequest = row["gold"]
        try:
            parsed = parser.parse(row["text"])
            pred = parsed.request
            # Re-verify strict JSON round-trip validity
            CravingRequest.model_validate_json(pred.model_dump_json(by_alias=True))
            schema_valid += 1
            latencies.append(parsed.latency_ms)
        except Exception:
            continue

        if pred.intent is gold.intent:
            intent_correct += 1

        p_slots = _slot_pairs(pred)
        g_slots = _slot_pairs(gold)
        slot_tp += len(p_slots & g_slots)
        slot_fp += len(p_slots - g_slots)
        slot_fn += len(g_slots - p_slots)

        if pred.requires_clarification and gold.requires_clarification:
            clar_tp += 1
        elif pred.requires_clarification and not gold.requires_clarification:
            clar_fp += 1
        elif not pred.requires_clarification and gold.requires_clarification:
            clar_fn += 1

    slot_precision = slot_tp / (slot_tp + slot_fp) if (slot_tp + slot_fp) else 1.0
    slot_recall = slot_tp / (slot_tp + slot_fn) if (slot_tp + slot_fn) else 1.0
    slot_f1 = (
        2 * slot_precision * slot_recall / (slot_precision + slot_recall)
        if (slot_precision + slot_recall)
        else 0.0
    )

    clar_precision = clar_tp / (clar_tp + clar_fp) if (clar_tp + clar_fp) else 1.0
    clar_recall = clar_tp / (clar_tp + clar_fn) if (clar_tp + clar_fn) else 1.0
    clar_f1 = (
        2 * clar_precision * clar_recall / (clar_precision + clar_recall)
        if (clar_precision + clar_recall)
        else 0.0
    )

    sorted_lat = sorted(latencies)
    p50 = round(statistics.median(sorted_lat), 3) if sorted_lat else 0.0
    p95 = (
        round(sorted_lat[min(len(sorted_lat) - 1, int(0.95 * len(sorted_lat)))], 3)
        if sorted_lat
        else 0.0
    )

    return {
        "samples": n,
        "schemaValidityRate": round(schema_valid / n, 4) if n else 0.0,
        "intentAccuracy": round(intent_correct / n, 4) if n else 0.0,
        "slotPrecision": round(slot_precision, 4),
        "slotRecall": round(slot_recall, 4),
        "slotMicroF1": round(slot_f1, 4),
        "clarificationPrecision": round(clar_precision, 4),
        "clarificationRecall": round(clar_recall, 4),
        "clarificationF1": round(clar_f1, 4),
        "latencyP50Ms": p50,
        "latencyP95Ms": p95,
    }


def run_evaluation(
    *,
    json_out: Path = DEFAULT_JSON_OUT,
    report_out: Path = DEFAULT_REPORT_OUT,
) -> dict[str, Any]:
    gold_rows = load_gold_set()
    template_metrics = evaluate_parser(TemplateParser(), gold_rows)

    qwen_key = os.getenv("QWEN_API_KEY", "").strip()
    qwen_model = os.getenv("QWEN_MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct").strip()
    qwen_base = os.getenv("QWEN_BASE_URL", "https://api.openai.com/v1").strip()

    client = HttpxQwenClient(api_key=qwen_key, base_url=qwen_base)
    qwen_metrics: dict[str, Any] | None = None
    if client.is_configured:
        qwen_parser = QwenParser(client, model=qwen_model, timeout_s=8.0)
        qwen_metrics = evaluate_parser(qwen_parser, gold_rows)

    summary: dict[str, Any] = {
        "dataset": {
            "path": "apps/ai_system/src/savora_ai/evals/craving_nlu_gold.jsonl",
            "samples": len(gold_rows),
        },
        "promptVersion": PROMPT_VERSION,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.system(),
        },
        "templateParser": template_metrics,
        "qwenParser": {
            "status": "MEASURED" if qwen_metrics is not None else "NOT_RUN_NO_API_KEY",
            "modelId": qwen_model,
            "baseUrl": qwen_base,
            "decoding": {"temperature": 0.0, "responseFormat": "json_object", "timeoutS": 8.0},
            "metrics": qwen_metrics,
        },
    }

    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    qwen_status = summary["qwenParser"]["status"]
    report_lines = [
        "# Craving NLU Evaluation Report",
        "",
        "## Overview",
        (
            f"- **Gold dataset:** `savora_ai/evals/craving_nlu_gold.jsonl` "
            f"({len(gold_rows)} utterances)"
        ),
        f"- **Prompt version:** `{PROMPT_VERSION}` (`savora_ai/prompts/craving_v1.md`)",
        "- **Target contract:** `CravingRequest` (`craving-request.v1`, section 9.1)",
        f"- **Runtime platform:** Python {platform.python_version()} ({platform.system()})",
        "",
        "## Template Baseline (`TemplateParser`) — Measured Results",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Samples | {template_metrics['samples']} |",
        f"| Schema Validity Rate | {template_metrics['schemaValidityRate']:.4f} |",
        f"| Intent Accuracy | {template_metrics['intentAccuracy']:.4f} |",
        f"| Slot Precision | {template_metrics['slotPrecision']:.4f} |",
        f"| Slot Recall | {template_metrics['slotRecall']:.4f} |",
        f"| Slot Micro-F1 | {template_metrics['slotMicroF1']:.4f} |",
        f"| Clarification Precision | {template_metrics['clarificationPrecision']:.4f} |",
        f"| Clarification Recall | {template_metrics['clarificationRecall']:.4f} |",
        f"| Clarification F1 | {template_metrics['clarificationF1']:.4f} |",
        f"| Latency p50 (ms) | {template_metrics['latencyP50Ms']} |",
        f"| Latency p95 (ms) | {template_metrics['latencyP95Ms']} |",
        "",
        "## Qwen Structured NLU (`QwenParser`)",
        "",
        f"- **Status:** `{qwen_status}`",
        f"- **Configured Model ID:** `{qwen_model}`",
        f"- **Endpoint Base URL:** `{qwen_base}`",
        (
            "- **Decoding Settings:** `temperature=0.0`, "
            "`response_format=json_object`, `timeout_s=8.0`"
        ),
    ]
    if qwen_metrics is None:
        report_lines.extend(
            [
                "",
                "> **Note:** `QWEN_API_KEY` was not set in the environment during this "
                "run, so live Qwen numbers are intentionally reported as "
                "`NOT_RUN_NO_API_KEY` rather than fabricated. The schema-validation and "
                "fallback paths (`QWEN_TIMEOUT`, `QWEN_INVALID_SCHEMA`, `QWEN_ERROR`, and "
                "allergy guardrails) are verified deterministically in "
                "`apps/ai_system/tests/test_craving_nlu.py` using `FakeQwenClient`.",
            ]
        )
    else:
        report_lines.extend(
            [
                "",
                "| Metric | Value |",
                "|---|---|",
                f"| Samples | {qwen_metrics['samples']} |",
                f"| Schema Validity Rate | {qwen_metrics['schemaValidityRate']:.4f} |",
                f"| Intent Accuracy | {qwen_metrics['intentAccuracy']:.4f} |",
                f"| Slot Precision | {qwen_metrics['slotPrecision']:.4f} |",
                f"| Slot Recall | {qwen_metrics['slotRecall']:.4f} |",
                f"| Slot Micro-F1 | {qwen_metrics['slotMicroF1']:.4f} |",
                f"| Clarification Precision | {qwen_metrics['clarificationPrecision']:.4f} |",
                f"| Clarification Recall | {qwen_metrics['clarificationRecall']:.4f} |",
                f"| Latency p50 (ms) | {qwen_metrics['latencyP50Ms']} |",
                f"| Latency p95 (ms) | {qwen_metrics['latencyP95Ms']} |",
            ]
        )

    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    summary = run_evaluation()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
