# Craving NLU Evaluation Report

## Overview
- **Gold dataset:** `savora_ai/evals/craving_nlu_gold.jsonl` (125 utterances)
- **Prompt version:** `craving-v1` (`savora_ai/prompts/craving_v1.md`)
- **Target contract:** `CravingRequest` (`craving-request.v1`, section 9.1)
- **Runtime platform:** Python 3.14.7 (Windows)

## Template Baseline (`TemplateParser`) — Measured Results

| Metric | Value |
|---|---|
| Samples | 125 |
| Schema Validity Rate | 1.0000 |
| Intent Accuracy | 1.0000 |
| Slot Precision | 1.0000 |
| Slot Recall | 1.0000 |
| Slot Micro-F1 | 1.0000 |
| Clarification Precision | 1.0000 |
| Clarification Recall | 1.0000 |
| Clarification F1 | 1.0000 |
| Latency p50 (ms) | 0.146 |
| Latency p95 (ms) | 0.298 |

## Qwen Structured NLU (`QwenParser`)

- **Status:** `NOT_RUN_NO_API_KEY`
- **Configured Model ID:** `Qwen/Qwen2.5-7B-Instruct`
- **Endpoint Base URL:** `https://api.openai.com/v1`
- **Decoding Settings:** `temperature=0.0`, `response_format=json_object`, `timeout_s=8.0`

> **Note:** `QWEN_API_KEY` was not set in the environment during this run, so live Qwen numbers are intentionally reported as `NOT_RUN_NO_API_KEY` rather than fabricated. The schema-validation and fallback paths (`QWEN_TIMEOUT`, `QWEN_INVALID_SCHEMA`, `QWEN_ERROR`, and allergy guardrails) are verified deterministically in `apps/ai_system/tests/test_craving_nlu.py` using `FakeQwenClient`.
