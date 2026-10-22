# Member 3 (Interaction) — GC1 Handoff & Architecture Summary

## 1. Scope Implemented (Slices S0 – S10)

Member 3 owns the user-facing interaction layer, backend persistence and API contracts, onboarding and profile management, Qwen/template Craving NLU, and the end-to-end craving, weekly meal-planning, and slot-substitution flows:

| Slice | Branch | Summary |
|---|---|---|
| **S0** | `feat/m3-backend-foundations` | FastAPI foundations (`Settings`, `CamelModel`, `TransformRoute` central response envelopes, `RuntimeException`/`ValidationException`, `RequestContextProvider`, SQLAlchemy 2 async/sync session adapter, `/api/health`). |
| **S1** | `feat/m3-auth-users` | Argon2 (`pwdlib`) + HS256 JWT (`pyjwt`) authentication (`POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`) and Alembic migration `0001_create_users`. |
| **S2** | `feat/m3-profile-targets` | `user_profiles` and immutable `user_nutrition_profiles` snapshots (`GET /api/profile`, `PUT /api/profile`, `GET /api/catalogue/cuisines`), calling `calculate_nutrition_targets` and `revalidate_seeds`, plus Alembic migration `0002_create_profiles_and_targets`. |
| **S3** | `feat/m3-seed-dishes` | Onboarding seed dish endpoints (`GET /api/onboarding/seed-suggestions`, `PUT /api/onboarding/seed-picks`, `GET /api/catalogue/dishes?q=`) backed by `suggest_seeds` and `confirm_seeds` (ADR 0005). |
| **S4** | `feat/m3-ai-runtime` | Startup `AiRuntime` loader (`load_catalogue_export`, `load_manifest`, `load_scorer` with fail-closed `ModelIntegrityError` handling), `PipelineAiGateway` (`asyncio.to_thread`), and contract-true `FakeAiGateway`. |
| **S5** | `feat/m3-craving-nlu` | `craving_v1.md` prompt, `QwenClient` (`HttpxQwenClient`, `FakeQwenClient`), `TemplateParser` and `QwenParser` with strict `CravingRequest.model_validate_json` validation, alias normalization, allergy guardrails, 125-utterance gold evaluation set (`craving_nlu_gold.jsonl`), and evaluation harness (`savora_ai.evals.craving_nlu`). |
| **S6** | `feat/m3-craving-endpoint` | `POST /api/cravings` returning `RECOMMENDATIONS` (via `recommend_for_craving`) or `SWAP_SUGGESTED` (when `intent == SWAP_MEAL`), with zero craving history persisted. |
| **S7** | `feat/m3-weekly-plans` | `meal_plans` and `meal_plan_slots` tables (`0003_create_meal_plans`), in-process background job runner, startup stale-job recovery (`mark_stale_generating_jobs_failed`), and `POST /api/meal-plans`, `GET /api/meal-plans`, `GET /api/meal-plans/{id}`. |
| **S8** | `feat/m3-substitutions` | `meal_plan_substitutions` table (`0004_create_substitutions`), revision and profile-version concurrency checks, background `substitute_slot` job creating a new `meal_plans` revision with the 20 locked slots copied verbatim, and `POST /api/meal-plans/{id}/substitutions`, `GET /api/substitutions/{id}`. |
| **S9** | `feat/m3-contracts-frontend` | Exported `packages/contracts/openapi.json`, generated TypeScript declarations in `packages/contracts/src/openapi.d.ts`, and built the Next.js App Router frontend (`/login`, `/register`, `/onboarding`, `/profile`, `/dashboard`, `/craving`) with `SafetyNotice`, TanStack Query, React Hook Form + Zod, and central `apiRequest`. |
| **S10** | `feat/m3-e2e-handoff` | Full backend E2E integration test (`apps/backend/tests/test_e2e.py`), updated `README.md`, and this handoff document. |

---

## 2. Key Architectural Decisions (Section 2)

1. **Authentication:** The FastAPI backend owns email/password auth using Argon2 hashing (`pwdlib`) and HS256 access tokens (`pyjwt`), configured via `JWT_SECRET_KEY`, `JWT_ALGORITHM`, and `ACCESS_TOKEN_EXPIRE_MINUTES` in `.env`. No Supabase Auth or refresh tokens are used in GC1.
2. **Catalogue Storage:** The recipe and meal-combination catalogue stays in the versioned JSON export (`Data/catalogue`), loaded once at startup into `CatalogueBundle`. PostgreSQL stores catalogue IDs, versions, and immutable `PlannedMeal` JSONB snapshots rather than duplicating recipe tables.
3. **Asynchronous Background Jobs:** Because Member 2's weekly CSP solver takes ~2–3 minutes per full week, weekly plan generation (`POST /api/meal-plans`) and slot substitution (`POST /api/meal-plans/{id}/substitutions`) run in-process via `asyncio.create_task` + `asyncio.to_thread` with job status persisted on the `meal_plans` / `meal_plan_substitutions` rows (`202 Accepted` + client polling). On server startup, any rows left in `GENERATING` are marked `FAILED` with `"server restarted"`.
4. **Qwen Craving NLU & Deterministic Fallback:** Hosted OpenAI-compatible chat completions are called via `httpx` (`QWEN_API_KEY`, `QWEN_BASE_URL`, `QWEN_MODEL_NAME`, `temperature=0`). When `QWEN_API_KEY` is unset, on timeout (`QWEN_TIMEOUT`), or when model output fails `CravingRequest.model_validate_json` (`QWEN_INVALID_SCHEMA`), `parse_craving` falls back deterministically to `TemplateParser` and records the parser and `fallbackReason` in `CravingParseMeta`.
5. **Onboarding Seed Dishes:** Confirmed seed dishes (3–5 picks) are stored on `user_profiles.seed_recipe_ids` (ADR 0005 D1) and revalidated automatically via `revalidate_seeds` whenever a user updates their profile.

---

## 3. API & Contract Surface

All `/api/*` endpoints are wrapped by `TransformRoute` and central exception handlers into the standard envelope:
- **Success:** `{ "success": true, "source": "...", "data": ..., "message": "...", "status": 200 }`
- **Error:** `{ "success": false, "source": "...", "message": "...", "status": 4xx, "description"?: { "<field>": ["..."] } }`

| Method & Path | Purpose |
|---|---|
| `GET /api/health` | Health probe |
| `POST /api/auth/register` | Register user & return JWT access token |
| `POST /api/auth/login` | Authenticate user & return JWT access token |
| `GET /api/auth/me` | Return authenticated `UserDto` |
| `GET /api/profile` | Return current `UserProfileDto`, latest `NutritionTargets`, and `needsSeedPicks` |
| `PUT /api/profile` | Upsert profile, increment `version`, snapshot `NutritionTargets`, revalidate `seedRecipeIds` |
| `GET /api/catalogue/cuisines` | List canonical `{id, name}` catalogue cuisines |
| `GET /api/catalogue/dishes?q=` | Search seed-eligible catalogue dishes by substring |
| `GET /api/onboarding/seed-suggestions` | Return 12 rule-screened seed dish suggestions for the current profile |
| `PUT /api/onboarding/seed-picks` | Confirm 3–5 seed dish IDs via `confirm_seeds` |
| `POST /api/cravings` | Parse natural-language craving and return `RECOMMENDATIONS` or `SWAP_SUGGESTED` |
| `POST /api/meal-plans` | Start async 21-slot weekly meal plan job (`202 Accepted`) |
| `GET /api/meal-plans` | List user's meal plans (`?current=true` filters to active revision) |
| `GET /api/meal-plans/{plan_id}` | Poll job status or retrieve full 21-slot plan, `dayTotals`, `safety`, and `search` |
| `POST /api/meal-plans/{plan_id}/substitutions` | Start async single-slot substitution job (`202 Accepted`) |
| `GET /api/substitutions/{substitution_id}` | Poll substitution status and inspect `beforeSnapshot` / `afterSnapshot` |

---

## 4. Craving NLU Evaluation Summary

Generated via `uv run python -m savora_ai.evals.craving_nlu` (full artifacts in [`docs/eval/craving_nlu.json`](../eval/craving_nlu.json) and [`docs/reports/craving_nlu_report.md`](../reports/craving_nlu_report.md)):

- **Gold dataset:** `apps/ai_system/src/savora_ai/evals/craving_nlu_gold.jsonl` (125 stratified utterances covering `CRAVING_RECOMMEND`, `SWAP_MEAL`, multi-cuisine/flavor/exclusion combinations, and `requiresClarification` cases).
- **`TemplateParser` (Measured on 125 gold utterances):**
  - Schema Validity Rate: `1.0000` (100%)
  - Intent Accuracy: `1.0000` (100%)
  - Slot Micro-F1: `1.0000` (Precision `1.0000`, Recall `1.0000`)
  - Clarification F1: `1.0000`
  - Latency: `p50 = 0.146 ms`, `p95 = 0.298 ms`
- **`QwenParser`:**
  - Reported as `NOT_RUN_NO_API_KEY` when `QWEN_API_KEY` is not set in `.env`. Run `uv run python -m savora_ai.evals.craving_nlu` with `QWEN_API_KEY` configured to populate live Qwen metrics alongside the template baseline.

> **Recommendation on PR #11:** Earlier exploratory notebook work in PR #11 is superseded by the production `savora_ai.core.craving_nlu` module, prompt `craving_v1.md`, and 125-sample evaluation harness in Slice S5 (`feat/m3-craving-nlu`). We recommend closing PR #11 in favor of S5.

---

## 5. Known GC1 Limitations & Safety Transparency (Section 10)

1. **Stand-in Knowledge Base (`STAND_IN_UNVERIFIED`):** Member 2's production clinical/allergen knowledge base is not yet integrated. Every craving, weekly plan, and substitution response carries `SafetyVerification` (`status: "STAND_IN_UNVERIFIED"`), and the Next.js UI renders `SafetyNotice` prominently on every result view. Results are never described as `"safe for you"`.
2. **Weekly CSP Solve Time:** Full 21-slot weekly CSP verification takes ~2–3 minutes. The backend and frontend handle this asynchronously with non-blocking background jobs and automatic polling.
3. **Standalone Craving Portion & Remaining Targets:** Standalone craving discovery ranks individual recipes at their standard 1-serving portion without running the meal composer or daily CSP, and displays the fixed notice `"Not checked against today's remaining targets"`.
4. **Popularity Fallback Transparency:** When `Data/models/sasrec_content.pt` is absent, pipelines fall back to `popularity-fallback-v1` (`fallbackReason: "MODEL_UNAVAILABLE"`), and the UI surfaces a `"Ranked by popularity"` badge.
