# Can a small local Qwen do the craving NLU? (21 October 2026)

This is a feasibility study for choosing a model size. It is **not** the section 13 NLU
benchmark, which belongs to Member 3 together with the full gold set and the template
baseline.

- Results: `docs/eval/craving_nlu_feasibility.json`
- Runner: `savora_ai/evals/craving_nlu_feasibility.py`
- Gold set: `savora_ai/evals/data/craving_nlu_feasibility.jsonl`, 58 hand-labelled
  utterances. They cover both intents, cuisines including typos and dish names, flavors,
  negated flavors, exclusions, weekday and "day N" slots, swaps without a slot, allergy
  mentions and off-topic messages.
- Prompt: `prompts/craving_nlu_feasibility_v2.md`
- Setup: Ollama 0.35.1 on an Apple M3 Pro (18 GB), default Q4_K_M quantization,
  temperature 0, seed 7, thinking off, at most 200 tokens, 30 s timeout. Every answer
  must pass strict `CravingRequest` validation; an invalid answer counts as empty.

The three modes:

| Mode | What it does |
|---|---|
| free | JSON mode, no schema |
| schema | decoding constrained to the `CravingRequest` JSON schema |
| grounded | schema mode, then the deterministic `ground()` step before validation. `ground()` drops any cuisine, flavor, exclusion or slot the user's words do not support, recomputes the slot from the words, and forces clarification on an allergy mention or a swap without a slot. It never adds a value |

## Results (grounded mode)

| Model (size) | Valid | Intent | Clarification | Slot P | Slot R | Slot F1 | Exact | p50 / p95 ms |
|---|---|---|---|---|---|---|---|---|
| **qwen3:0.6b** (522 MB) | 1.00 | 0.97 | 0.97 | 0.97 | 0.79 | 0.87 | 0.67 | 303 / 388 |
| qwen3:1.7b (1.4 GB) | 1.00 | 0.79 | 0.78 | 0.95 | 0.90 | 0.93 | 0.66 | 572 / 723 |
| qwen2.5:0.5b (397 MB) | 1.00 | 0.34 | 0.34 | 0.80 | 0.81 | 0.80 | 0.17 | 281 / 340 |
| **qwen2.5:1.5b** (986 MB) | 1.00 | 0.98 | 0.93 | 0.93 | 0.92 | 0.92 | 0.78 | 505 / 668 |

For qwen3:0.6b, each step adds something:

| Mode | Valid | Intent | Slot F1 | Exact |
|---|---|---|---|---|
| free | 0.78 | 0.74 | 0.65 | 0.38 |
| schema | 1.00 | 0.97 | 0.69 | 0.41 |
| grounded | 1.00 | 0.97 | 0.87 | 0.67 |

## Findings

1. **Yes, 0.6B works, but only with schema decoding and grounding.**
   - Without the schema, 22% of its answers are invalid.
   - Without grounding, it adds values the user did not say (with prompt v1 these were
     often the example values, such as `D5_LUNCH`), so slot precision is 0.67.
   - With both, every answer is valid, intent and clarification are 0.97, and precision
     is 0.97. It answers in about 0.3 s and needs about 0.5 GB.
2. **Its weakness is recall (0.79).** It sometimes misses a cuisine named in a dish or an
   exclusion. A miss is the safe kind of error: the request is broader, and the Rule
   Engine still applies every profile restriction. An invented exclusion or cuisine,
   which grounding removes, would be the unsafe kind.
3. **qwen2.5:1.5b is the most accurate** (exact match 0.78, F1 0.92), at about twice the
   latency and size.
   - qwen3:1.7b has good slots, but it misreads intent: it often calls a craving a swap.
   - qwen2.5:0.5b is not usable (intent 0.34).
4. **Safety does not depend on the model.** Allergies are never taken from text, and
   unsupported values are dropped deterministically. Hard restrictions come only from
   the confirmed profile and the Rule Engine (section 9.1).

## Recommendation

- **Default:** `qwen3:0.6b` in Ollama, with schema decoding and grounding, and the
  template parser as fallback.
- **Upgrade, if the machine allows:** `qwen2.5:1.5b`, by changing only
  `QWEN_MODEL_NAME`.

The integration plan is recorded in `docs/member3/IMPLEMENTATION_SPEC.md` section 2
item 4.

Limits:
- 58 utterances is small; the 95% interval on an accuracy near 0.97 is roughly ±0.05.
- The gold set was written by the same team that wrote the prompt.
- The latency figures are for one laptop and are not a server benchmark.
