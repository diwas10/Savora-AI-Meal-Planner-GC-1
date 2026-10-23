"""Craving NLU evaluation (ARCHITECTURE section 13): template baseline and local Qwen.

Two gold sets are scored:

- `craving_nlu_gold.jsonl` (125 utterances), written together with the template parser
- `data/craving_nlu_feasibility.jsonl` (58 utterances), written independently of it for
  the model-size study; the template parser's score here is the fairer estimate

Qwen runs through the production path (`QwenParser`: schema-constrained decoding, then
`ground()`, then strict validation, template fallback), alone ("qwen") and merged with the
template parse ("hybrid", the production default). Fallbacks count as the template answer
they produced, and the fallback rate is reported beside them. Qwen numbers
are written only when the endpoint answered; otherwise the status says why.

`mealSlotId` is scored only on SWAP_MEAL: on a standalone craving the slot has no effect
(the craving pipeline ignores it), and the two gold sets label it differently there.

Run (from the repo root, Ollama running, model pulled):
    uv run python -m savora_ai.evals.craving_nlu --model qwen3:0.6b
"""

import argparse
import json
import platform
import statistics
import sys
from pathlib import Path
from typing import Any

import httpx

from savora_ai.core.craving_nlu import (
    PROMPT_VERSION,
    CravingParser,
    QwenParser,
    TemplateParser,
    build_qwen_client,
)
from savora_ai.core.pipelines.catalogue import load_catalogue_export
from savora_ai.schemas.craving import CravingIntent, CravingRequest

HERE = Path(__file__).resolve().parent
GOLD_PATH = HERE / "craving_nlu_gold.jsonl"
INDEPENDENT_PATH = HERE / "data/craving_nlu_feasibility.jsonl"
REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_JSON_OUT = REPO_ROOT / "docs/eval/craving_nlu.json"
DEFAULT_REPORT_OUT = REPO_ROOT / "docs/reports/craving_nlu_report.md"
TIMEOUT_S = 8.0
EVALS_DIR = "apps/ai_system/src/savora_ai/evals"


def load_gold_set(path: Path = GOLD_PATH) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        item["gold"] = CravingRequest.model_validate_json(json.dumps(item["expected"]))
        rows.append(item)
    return rows


def _slot_pairs(req: CravingRequest) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    pairs.update(("cuisine_id", c) for c in req.cuisine_ids)
    pairs.update(("flavor_tag", f.value) for f in req.flavor_tags)
    pairs.update(
        ("excluded_ingredient_id", x.removesuffix("S")) for x in req.excluded_ingredient_ids
    )
    if req.intent is CravingIntent.SWAP_MEAL and req.meal_slot_id is not None:
        pairs.add(("meal_slot_id", req.meal_slot_id))
    return pairs


def _ratio(num: int, den: int) -> float:
    return round(num / den, 4) if den else 1.0


def evaluate_parser(
    parser: CravingParser,
    gold_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = gold_rows if gold_rows is not None else load_gold_set()
    n = len(rows)
    valid = intent = exact = fallbacks = 0
    slot_tp = slot_fp = slot_fn = clar_tp = clar_fp = clar_fn = 0
    latencies: list[float] = []
    fallback_reasons: dict[str, int] = {}
    for row in rows:
        gold: CravingRequest = row["gold"]
        try:
            parsed = parser.parse(row["text"])
            pred = CravingRequest.model_validate_json(parsed.request.model_dump_json(by_alias=True))
        except Exception:
            continue
        valid += 1
        latencies.append(parsed.latency_ms)
        if parsed.fallback_reason:
            fallbacks += 1
            fallback_reasons[parsed.fallback_reason] = (
                fallback_reasons.get(parsed.fallback_reason, 0) + 1
            )
        intent += pred.intent is gold.intent
        predicted, expected = _slot_pairs(pred), _slot_pairs(gold)
        slot_tp += len(predicted & expected)
        slot_fp += len(predicted - expected)
        slot_fn += len(expected - predicted)
        clar_tp += pred.requires_clarification and gold.requires_clarification
        clar_fp += pred.requires_clarification and not gold.requires_clarification
        clar_fn += gold.requires_clarification and not pred.requires_clarification
        exact += (
            pred.intent is gold.intent
            and pred.requires_clarification == gold.requires_clarification
            and predicted == expected
        )
    precision, recall = _ratio(slot_tp, slot_tp + slot_fp), _ratio(slot_tp, slot_tp + slot_fn)
    clar_p, clar_r = _ratio(clar_tp, clar_tp + clar_fp), _ratio(clar_tp, clar_tp + clar_fn)
    ordered = sorted(latencies)
    return {
        "samples": n,
        "schemaValidityRate": _ratio(valid, n),
        "intentAccuracy": _ratio(intent, n),
        "slotPrecision": precision,
        "slotRecall": recall,
        "slotMicroF1": round(2 * precision * recall / (precision + recall), 4)
        if precision + recall
        else 0.0,
        "clarificationPrecision": clar_p,
        "clarificationRecall": clar_r,
        "clarificationF1": round(2 * clar_p * clar_r / (clar_p + clar_r), 4)
        if clar_p + clar_r
        else 0.0,
        "exactMatch": _ratio(exact, n),
        "fallbackRate": _ratio(fallbacks, n),
        "fallbackReasons": fallback_reasons,
        "latencyP50Ms": round(statistics.median(ordered), 3) if ordered else 0.0,
        "latencyP95Ms": round(ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))], 3)
        if ordered
        else 0.0,
    }


def _endpoint_status(provider: str, base_url: str) -> str:
    if provider != "ollama":
        return "MEASURED"
    try:
        httpx.get(f"{base_url.rstrip('/')}/api/version", timeout=3.0).raise_for_status()
    except httpx.HTTPError:
        return "NOT_RUN_OLLAMA_UNREACHABLE"
    return "MEASURED"


def _table(metrics: dict[str, Any]) -> list[str]:
    keys = (
        ("schemaValidityRate", "Schema validity"),
        ("intentAccuracy", "Intent accuracy"),
        ("slotPrecision", "Slot precision"),
        ("slotRecall", "Slot recall"),
        ("slotMicroF1", "Slot micro-F1"),
        ("clarificationPrecision", "Clarification precision"),
        ("clarificationRecall", "Clarification recall"),
        ("exactMatch", "Exact match"),
        ("fallbackRate", "Fallback to template"),
        ("latencyP50Ms", "Latency p50 (ms)"),
        ("latencyP95Ms", "Latency p95 (ms)"),
    )
    return [f"| {label} | {metrics[key]} |" for key, label in keys]


def run_evaluation(
    *,
    json_out: Path = DEFAULT_JSON_OUT,
    report_out: Path = DEFAULT_REPORT_OUT,
    model: str = "qwen3:0.6b",
    provider: str = "ollama",
    base_url: str = "http://localhost:11434",
    api_key: str = "",
    run_qwen: bool = True,
    catalogue_dir: Path = REPO_ROOT / "Data/catalogue",
) -> dict[str, Any]:
    cuisines = load_catalogue_export(catalogue_dir).cuisine_ids
    datasets = {
        "gold": load_gold_set(GOLD_PATH),
        "independent": load_gold_set(INDEPENDENT_PATH),
    }
    template = TemplateParser(cuisines)
    status = _endpoint_status(provider, base_url) if run_qwen else "NOT_RUN_DISABLED"
    qwen: QwenParser | None = None
    hybrid: QwenParser | None = None
    if status == "MEASURED":
        client = build_qwen_client(
            provider="openai" if provider == "openai" else "ollama",
            base_url=base_url,
            api_key=api_key,
        )
        settings: dict[str, Any] = dict(
            model=model, timeout_s=TIMEOUT_S, cuisine_ids=cuisines, template_fallback=template
        )
        qwen = QwenParser(client, merge_with_template=False, **settings)
        hybrid = QwenParser(client, **settings)
        qwen.parse("warm up")  # load the model before timing
    results: dict[str, Any] = {}
    for name, rows in datasets.items():
        results[name] = {
            "samples": len(rows),
            "template": evaluate_parser(template, rows),
            "qwen": evaluate_parser(qwen, rows) if qwen is not None else None,
            "hybrid": evaluate_parser(hybrid, rows) if hybrid is not None else None,
        }
    summary: dict[str, Any] = {
        "dataset": {
            "path": f"{EVALS_DIR}/craving_nlu_gold.jsonl",
            "samples": len(datasets["gold"]),
            "independentPath": f"{EVALS_DIR}/data/craving_nlu_feasibility.jsonl",
            "independentSamples": len(datasets["independent"]),
        },
        "promptVersion": PROMPT_VERSION,
        "qwen": {
            "status": status,
            "provider": provider,
            "modelId": model,
            "endpoint": base_url,
            "decoding": "schema-constrained (CravingRequest), think off, temperature 0, "
            f"seed 7, max 200 tokens, {TIMEOUT_S:g} s timeout; ground() before validation",
        },
        "environment": {
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.machine()}",
        },
        "results": results,
    }
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(_report(summary), encoding="utf-8")
    return summary


def _report(summary: dict[str, Any]) -> str:
    q = summary["qwen"]
    lines = [
        "# Craving NLU evaluation (ARCHITECTURE section 13)",
        "",
        "Generated by `uv run python -m savora_ai.evals.craving_nlu`; raw numbers in "
        "`docs/eval/craving_nlu.json`.",
        "",
        f"- Prompt: `{summary['promptVersion']}` (`savora_ai/prompts/craving_v2.md`)",
        f"- Qwen: `{q['modelId']}` via {q['provider']} at `{q['endpoint']}`, status "
        f"`{q['status']}`",
        f"- Decoding: {q['decoding']}",
        f"- Runtime: Python {summary['environment']['python']} on "
        f"{summary['environment']['platform']}",
        "- `mealSlotId` is scored on SWAP_MEAL only; excluded-ingredient IDs are compared "
        "singular/plural-insensitively.",
        "",
    ]
    titles = {
        "gold": "Gold set (written together with the template parser)",
        "independent": "Independent set (written for the model-size study)",
    }
    for name, block in summary["results"].items():
        lines += [f"## {titles[name]}: {block['samples']} utterances", ""]
        columns = [("Template", block["template"])] + [
            (label, block[key])
            for key, label in (("qwen", "Qwen (grounded)"), ("hybrid", "Hybrid (production)"))
            if block.get(key)
        ]
        lines += ["| Metric | " + " | ".join(c for c, _ in columns) + " |"]
        lines += ["|---|" + "---|" * len(columns)]
        tables = [_table(m) for _, m in columns]
        for row in zip(*tables, strict=True):
            label = row[0].split("|")[1]
            lines.append("|" + label + "|" + "|".join(r.split("|")[2] for r in row) + "|")
        lines.append("")
    if q["status"] != "MEASURED":
        lines += [
            "Qwen was not measured in this run, so no Qwen numbers are reported. The "
            "fallback paths are covered by `apps/ai_system/tests/test_craving_nlu.py`.",
            "",
        ]
    lines += [
        "Limits: the gold sets were written by the team that wrote the parsers; the "
        "template parser's perfect score on its own gold set is an upper bound, and the "
        "independent set is the fairer estimate. The hybrid merge rule was chosen after "
        "comparing three clarification variants on these sets, so its lead is slightly "
        "optimistic. Latency is for one laptop.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3:0.6b")
    parser.add_argument("--provider", choices=("ollama", "openai"), default="ollama")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--no-qwen", action="store_true")
    args = parser.parse_args()
    summary = run_evaluation(
        model=args.model,
        provider=args.provider,
        base_url=args.base_url,
        run_qwen=not args.no_qwen,
    )
    sys.stdout.write(json.dumps(summary["results"], indent=2) + "\n")


if __name__ == "__main__":
    main()
