"""Feasibility check: can a small, quantized, LOCAL Qwen produce the section 9.1 request?

Runs each model in Ollama (http://localhost:11434) on the gold file
`evals/data/craving_nlu_feasibility.jsonl` (58 utterances) with the versioned prompt
`prompts/craving_nlu_feasibility_v2.md` (v1 kept for comparison), temperature 0, in
three modes:

    schema    Ollama structured output: decoding constrained to the CravingRequest schema
    grounded  schema mode, then `ground()` before validation: a deterministic check that
              drops any flavor, exclusion, cuisine or slot the user's words do not
              support, and forces clarification on an allergy mention or a swap without
              a slot ("never trust Qwen output")
    free      plain JSON mode (no schema), closer to an API without constrained decoding

Every answer must pass `CravingRequest.model_validate_json` (strict); an invalid answer
counts as an empty prediction. Metrics: schema validity, intent accuracy, clarification
accuracy, slot precision/recall/F1 over (field, value) pairs, exact match, latency p50/p95.

This is a feasibility study for choosing a model size, NOT the section 13 benchmark
(Member 3 owns the NLU package, its full gold set and the template baseline).

Usage (from the repo root, Ollama running, models pulled):
    uv run python -m savora_ai.evals.craving_nlu_feasibility \
        --models qwen3:0.6b qwen3:1.7b --output docs/eval/craving_nlu_feasibility.json
"""

import argparse
import json
import statistics
import time
import urllib.request
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from savora_ai.core.craving_nlu.grounding import ground, norm_ingredient
from savora_ai.core.pipelines.catalogue import load_catalogue_export
from savora_ai.schemas.craving import CravingRequest

HERE = Path(__file__).parent
GOLD = HERE / "data/craving_nlu_feasibility.jsonl"
PROMPTS = HERE.parent / "prompts"
OLLAMA = "http://localhost:11434/api/chat"
TIMEOUT_S = 30
MAX_TOKENS = 200  # a valid answer is under 100 tokens; a runaway generation is cut
SLOT_FIELDS = ("cuisineIds", "flavorTags", "excludedIngredientIds", "mealSlotId")


def slots(body: dict[str, Any]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for field in SLOT_FIELDS:
        value = body.get(field)
        values = value if isinstance(value, list) else [] if value is None else [value]
        for v in values:
            pairs.add((field, norm_ingredient(v) if field == "excludedIngredientIds" else v))
    return pairs


def ask(model: str, system: str, text: str, constrained: bool) -> tuple[str, float]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": text}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "seed": 7, "num_predict": MAX_TOKENS},
        "format": CravingRequest.model_json_schema(by_alias=True) if constrained else "json",
    }
    request = urllib.request.Request(
        OLLAMA, json.dumps(payload).encode(), {"Content-Type": "application/json"}
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # local only
        body = json.loads(response.read())
    return body["message"]["content"], (time.perf_counter() - started) * 1000


def evaluate(
    model: str,
    gold: list[dict[str, Any]],
    system: str,
    mode: str,
    cuisines: dict[str, str],
) -> dict[str, Any]:
    constrained = mode != "free"
    ask(model, system, "warm up", constrained)  # load the model before timing
    valid = intent = clarify = exact = 0
    tp = fp = fn = 0
    latencies: list[float] = []
    errors: list[dict[str, str]] = []
    for case in gold:
        expected = CravingRequest.model_validate_json(json.dumps(case["expected"]))
        want = json.loads(expected.model_dump_json(by_alias=True))
        try:
            raw, ms = ask(model, system, case["text"], constrained)
        except TimeoutError:
            raw, ms = "", TIMEOUT_S * 1000.0  # a timeout is an invalid answer
        latencies.append(ms)
        try:
            # Grounding runs before strict validation, so it can repair a SWAP_MEAL
            # without a slot (forced clarification) instead of discarding the answer.
            checked = (
                raw
                if mode != "grounded"
                else json.dumps(ground(case["text"], json.loads(raw), cuisines))
            )
            got = json.loads(
                CravingRequest.model_validate_json(checked).model_dump_json(by_alias=True)
            )
            valid += 1
        except (ValidationError, ValueError, TypeError, AttributeError) as error:
            errors.append({"text": case["text"], "output": raw[:200], "error": str(error)[:160]})
            got = {}
        intent += got.get("intent") == want["intent"]
        clarify += got.get("requiresClarification") == want["requiresClarification"]
        predicted, gold_slots = slots(got), slots(want)
        tp += len(predicted & gold_slots)
        fp += len(predicted - gold_slots)
        fn += len(gold_slots - predicted)
        exact += bool(got) and (
            got["intent"],
            got["requiresClarification"],
            slots(got),
        ) == (want["intent"], want["requiresClarification"], slots(want))
    n = len(gold)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    ordered = sorted(latencies)
    return {
        "model": model,
        "mode": mode,
        "cases": n,
        "schemaValidity": valid / n,
        "intentAccuracy": intent / n,
        "clarificationAccuracy": clarify / n,
        "slotPrecision": precision,
        "slotRecall": recall,
        "slotF1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "exactMatch": exact / n,
        "latencyMsP50": statistics.median(latencies),
        "latencyMsP95": ordered[min(n - 1, int(0.95 * n))],
        "invalidExamples": errors[:5],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--catalogue-dir", type=Path, default=Path("Data/catalogue"))
    parser.add_argument("--prompt", default="craving_nlu_feasibility_v2")
    parser.add_argument("--modes", nargs="+", default=["schema", "grounded", "free"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cuisines = load_catalogue_export(args.catalogue_dir).cuisine_ids
    system = (PROMPTS / f"{args.prompt}.md").read_text(encoding="utf-8")
    system = system.format(cuisine_ids=", ".join(cuisines))
    gold = [json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line]
    results = []
    for model in args.models:
        for mode in args.modes:
            result = evaluate(model, gold, system, mode, cuisines)
            print(json.dumps({k: v for k, v in result.items() if k != "invalidExamples"}))
            results.append(result)
    output = {
        "promptVersion": args.prompt,
        "gold": f"{GOLD.name} ({len(gold)} utterances)",
        "decoding": (
            f"temperature 0, seed 7, thinking off, max {MAX_TOKENS} tokens, "
            f"{TIMEOUT_S} s timeout, Ollama default quantization (Q4_K_M)"
        ),
        "hardware": "Apple M3 Pro, 18 GB, Ollama 0.35.1",
        "results": results,
    }
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
