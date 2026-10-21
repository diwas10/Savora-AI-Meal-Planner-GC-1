# Member 3 implementation spec: Savora app integration (paste into your coding agent)

> **How to use.** Pull `main` once the Member 1 integration PR is merged. Open the repository
> root in your coding agent and paste this whole file as the task. The agent works through
> slices S0 to S10 in order, runs every check, commits each slice locally and stops before
> pushing. You review the result and then tell it to push and open PRs.

---

## 0. Role, rules and sources of truth

You are implementing **Member 3 (Interaction)** for Savora GC1: the Next.js app, the
FastAPI integration and persistence, onboarding and profile, Qwen craving NLU, and the
craving, weekly-plan and substitution flows. Everything the AI side must compute already
exists as typed Python calls. Your job is to **wire, persist, expose and present** them.
Do not re-implement ranking, rules, composition, CSP or nutrition.

Read before coding, and re-read the relevant parts per slice:

1. `AGENTS.md` (all of it, every task).
2. `ARCHITECTURE.md` sections 1, 3, 4.1 to 4.4, 9, 10, 11, 12.1, 13 and 14.
3. `docs/adr/0005-onboarding-seed-dishes-and-model-delivery.md` (seed dishes, model file).
4. `apps/ai_system/src/savora_ai/core/pipelines/__init__.py` and its modules (the calls
   you make).
5. `apps/ai_system/src/savora_ai/schemas/craving.py` (the NLU output contract, section 9.1).

Non-negotiables, all from AGENTS.md:

- **Branches.** Work on `feat/m3-<slice>` branches, never `main`. Commit messages use
  `[ADD]: ...`, `[UPDATE]: ...`, `[FIX]: ...` and so on, imperative mood.
- **No push, no PR.** Do not push or open a PR until the human says so. When told, fill
  `.github/PULL_REQUEST_TEMPLATE.md` completely.
- **Dependency direction.** Next.js → FastAPI → `savora_ai`. `apps/ai_system` must never
  import `savora_backend`, `fastapi` or `sqlalchemy`; CI greps for this. Only the backend
  touches the database.
- **Backend pattern.** Thin controllers → services → repositories, with typed DTOs.
  `CamelModel` gives camelCase JSON and snake_case Python/SQL. Use Alembic migrations,
  bound parameters and explicit transactions.
- **Envelopes.** Every `/api` response is wrapped centrally, never in controllers:
  - success: `{success, source, data, message, status}`
  - error: `{success:false, source, message, status, description?}`
  - 422 validation: field → list of messages
- **Frontend pattern.** Next.js App Router. `src/app` holds thin routes and `src/core`
  holds features. Each feature goes `.api.ts` → `.query.ts` (TanStack Query) → components.
  No axios in components or `src/app`. Forms use Zod + React Hook Form. Server Components
  by default; `"use client"` only where interactive.
- **Persistence scope.** Persist **generated plans and substitutions only** (plus users,
  profiles, nutrition target snapshots and seed picks). Never store ratings, consumption,
  feedback events or craving history, and never retrain.
- **Safety.** Never present results as "safe for you". Never invent nutrition. Never trust
  Qwen output beyond the validated `CravingRequest`.
- **Verification.** Run the checks in section 9 for every slice. Report what actually ran
  and what failed; never claim a check you did not run.

## 1. What already exists (call it; do not rebuild it)

All imports below are from `savora_ai`. Every function is pure and synchronous: no I/O
after the catalogue is loaded. Some are slow (see the timing column). Run them with
`await asyncio.to_thread(...)` (craving, seeds) or in a background job (weekly plan, swap)
so the event loop never blocks.

| Call | Purpose | Typical time |
|---|---|---|
| `core.pipelines.load_catalogue_export(Path("Data/catalogue"))` → `CatalogueBundle` | Load once at startup; holds dishes, meal combinations, popularity fallback, `cuisine_ids` | 0.05 s |
| `core.recommendation.model_store.load_manifest()`, then `core.recommendation.ranking.load_scorer(path, bundle.popularity.counts, manifest=manifest)` | Trained Transformer, loaded once at startup. Returns `None` if `Data/models/sasrec_content.pt` or torch is missing; the pipelines then use the popularity fallback and say so. Raises `ModelIntegrityError` if the file does not match the manifest. | 0.5 s |
| `core.nutrition.targets.calculate_nutrition_targets(TargetInput, profile_version=, calculated_at=)` → `NutritionTargets` | Versioned energy and macro targets | instant |
| `core.pipelines.suggest_seeds(profile, bundle, limit=12)` → `SeedSuggestions` | Onboarding liked-dish shortlist, already rule-checked | 1–3 s |
| `core.pipelines.confirm_seeds(profile, bundle, picks)` → `tuple[str, ...]` | Validates 3–5 picks; raises `ValueError` on any unusable pick | ~1 s |
| `core.pipelines.revalidate_seeds(profile, bundle)` → `tuple[str, ...]` | After a profile change: the stored seeds that are still allowed | ~1 s |
| `core.pipelines.recommend_for_craving(request, profile, bundle, scorer=, top_k=10)` → `CravingRecommendation` | Section 4.3: retrieval, then rules, then Transformer. No composer or CSP. | 0.3–3 s |
| `core.pipelines.plan_week(profile, bundle, week_id=, start_date=, scorer=)` → `WeekPlan` | Section 4.2: 21 slots verified by Member 2's weekly CSP | **2–3 min** |
| `core.pipelines.substitute_slot(profile, bundle, current=, slot=, week_id=, start_date=, exclude_combination_ids=, scorer=)` → `WeekPlan` | Section 4.4: one slot replaced, the other 20 locked | **2–3 min** |

Key input and output types (Pydantic v2, strict, camelCase aliases):

- `PlanningProfile`: `profileId`, `profileVersion`, `diet` (`VEGETARIAN`/`VEGAN`/null),
  `cuisinePolicy` (`STRICT`/`MAJORITY`/`MIXED`), `cuisines` (catalogue names such as
  `"Nepali"`), `excludedIngredients`, `allergies` (user-confirmed only), `conditions`
  (`TYPE_2_DIABETES`/`HYPERTENSION`/`DYSLIPIDEMIA`), `seedRecipeIds` (0–5). Build it in
  the backend from the stored profile.
- `CravingRequest` (section 9.1): `intent` (`CRAVING_RECOMMEND`/`SWAP_MEAL`),
  `cuisineIds`, `flavorTags` (`SPICY`/`SWEET`/`SOUR`/`SMOKY`/`CREAMY`),
  `excludedIngredientIds`, `mealSlotId` (`D<1-7>_<BREAKFAST|LUNCH|DINNER>`),
  `requiresClarification`.
  - Strict: validate model output with `CravingRequest.model_validate_json(text)`.
  - Python callers pass enum instances and tuples.
- `CravingRecommendation`: `status` (`OK`/`NEEDS_CLARIFICATION`/`NO_MATCH`), `items[]`
  (`recipeId`, `name`, `rank`, `score`, `cuisines`, `explanation`), `modelVersion`,
  `fallbackReason`, `unknownCuisineIds`, `unmatchedFlavorTags`, `counts`, `kbId`,
  `kbVersion`, `safety`.
- `WeekPlan`:
  - status and identity: `status` (`FEASIBLE`/`INFEASIBLE`/`INSUFFICIENT_DATA`/`TIMEOUT`),
    `workflow`, `weekId`, `startDate`, `profileId`, `profileVersion`, `catalogueVersion`
  - content: `meals[21]` and `dayTotals[7]`
  - provenance: `modelVersion`, `fallbackReason`, `kbId`, `kbVersion`, `search`,
    `message`, `safety`
  - Each meal (`PlannedMeal`) has `slotId`, `dayIndex`, `calendarDate`, `mealType`,
    `optionId` (store it, and lock by it), `combinationId`, `configurationId`, `preset`
    and `explanation` (dishes, portions, totals, unknown nutrients, reasons).
- `SafetyVerification` (on every result): `status: "STAND_IN_UNVERIFIED"`,
  `allergensCheckedBy`, `dietCheckedBy`, `conditionsNotEnforced`, `message`.

**Stand-in knowledge base.** Member 2's production rule KB (real diet, allergen and
clinical rules) does not exist yet. The pipelines therefore use `stand_in_kb.py` plus a
profile screen:
- diet: Food.com tags; a missing tag excludes the dish.
- explicit exclusions and allergies: matched as whole words in ingredient names.
- conditions: not enforced.

Your UI **must** show `safety.message` wherever results appear (craving results, plan,
swap). When Member 2 ships the production KB, only `stand_in_kb.py` and `profile.py`
change; your code does not.

**Weekly time.** Member 2's weekly CSP takes 2–3 minutes per plan today (a known
performance item on Member 2's side). Plan generation and swaps are therefore **background
jobs** with polling (S7, S8). Never run them inside a request handler.

## 2. Decisions this spec takes (state them in your PRs; change only with the team)

1. **Auth.** The backend owns email/password auth: argon2 hashing (`pwdlib`) and an HS256
   access token (`pyjwt`), configured by `JWT_SECRET_KEY`, `JWT_ALGORITHM` and
   `ACCESS_TOKEN_EXPIRE_MINUTES` in `.env`. These dependencies are already in
   `apps/backend/pyproject.toml`. No Supabase Auth and no refresh tokens in GC1.
2. **Catalogue.** It stays in the versioned JSON export, loaded at startup (section 10
   allows simplifying the schema "where a curated catalogue suffices"). The database
   stores catalogue IDs and versions plus immutable meal snapshots, not recipe tables.
3. **Async jobs.** Plan and swap jobs use an in-process worker (`asyncio.create_task`
   plus `asyncio.to_thread`) with job state persisted on the plan row. No queue or Redis
   (AGENTS.md). On startup, mark rows still `GENERATING` as `FAILED` with "server
   restarted".
4. **Qwen (team decision, 21 October 2026): a small quantized Qwen running locally in
   Ollama.** The default is `qwen3:0.6b` (Q4_K_M, 522 MB). `qwen2.5:1.5b` is the
   accuracy upgrade. Evidence: `docs/reports/craving_nlu_feasibility_report.md`.
   - Configure with `QWEN_BASE_URL` (default `http://localhost:11434`) and
     `QWEN_MODEL_NAME` (add both to `.env.example`). Local Ollama needs no
     `QWEN_API_KEY`. Keep the key optional so that a hosted OpenAI-compatible endpoint
     still works.
   - Call `/api/chat` with `httpx` and an explicit timeout, using `"think": false`,
     temperature 0, and `"format"` set to `CravingRequest.model_json_schema(by_alias=True)`
     for constrained decoding.
   - Then apply the deterministic grounding step from
     `savora_ai/evals/craving_nlu_feasibility.py::ground` **before** strict validation.
     Move it into the NLU package.
   - Fall back to the deterministic template parser when Ollama is unreachable, on
     timeout or on invalid output, and record which parser was used.
5. **Seed dishes** are stored on the profile as `seed_recipe_ids` (ADR 0005 D1, accepted
   by the team on 2026-10-20, together with the seed endpoint names in section 4).

## 3. Work plan (one branch per slice, in order; each slice ends green)

### S0 `feat/m3-backend-foundations`

Files go in `apps/backend/src/savora_backend/` under `config/`, `database/`, `core/common/`,
`exceptions/`, `interceptors/`, `contexts/` and `decorators/`. These packages exist and
are empty.

- `config`: `Settings` (pydantic-settings, reads the root `.env`) with
  - `DATABASE_URL`, the `JWT_*` values, `QWEN_*` and `CORS_ORIGINS`
  - `CATALOGUE_DIR` (default `Data/catalogue`) and `MODEL_DIR` (default `Data/models`)
- `database`: async engine and `async_sessionmaker`; a `get_session` dependency that
  yields a session with an explicit transaction per request.
  - `CommonEntity`: `id` UUID primary key, `created_at`, `updated_at`, `created_by`,
    `updated_by`.
  - `PrimaryEntity`: adds `is_active`.
  - Wire the Alembic `target_metadata` to the shared `Base.metadata`.
- `core/common`: `CamelModel(BaseModel)` with alias generator `to_camel`,
  `populate_by_name=True` and `from_attributes=True`.
- `exceptions`: `RuntimeException(message, status, description?)` and
  `ValidationException(errors: dict[str, list[str]])`. Register global handlers for
  these, for `RequestValidationError` (422 field arrays) and for unhandled exceptions (500
  with a generic message; the detail goes to logs only).
- `interceptors`/`decorators`: `@response_message("...")` and a `TransformRoute`
  (`APIRouter(route_class=TransformRoute)`) that wraps return values in the success
  envelope.
  - `source` is the route's module name, for example `"meal-plans"`.
  - Keep `/api/health` unwrapped, or update its test.
- `contexts`: a `RequestContextProvider` contextvar holding the current user ID and
  request ID; the repositories set `created_by`/`updated_by` from it.
- CORS for the frontend origin.
- Tests: envelope shape, 422 shape, `RuntimeException` → envelope, health.

### S1 `feat/m3-auth-users`

- Table `users`: `id`, `email` (unique, lower-cased), `password_hash`, `display_name`,
  `is_active`, timestamps. Add the Alembic migration.
- Endpoints:
  - `POST /api/auth/register` `{email, password, displayName}` → `{user, accessToken}`
  - `POST /api/auth/login` `{email, password}` → `{user, accessToken}`
  - `GET /api/auth/me`
- `current_user` dependency: Bearer token → user, else 401 envelope.
- Password policy: at least 8 characters. Return a generic error on bad credentials.
- Tests: register/login/me, duplicate email 409, bad password 401, expired token 401.

### S2 `feat/m3-profile-targets`

- Tables:
  - `user_profiles`: `user_id` (unique foreign key), `version` (int, starts at 1, +1 on
    every change), `age_years`, `sex`, `height_cm`, `weight_kg`, `activity`, `goal`,
    `diet`, `cuisine_policy`, `cuisines` (text[]), `excluded_ingredients` (text[]),
    `allergies` (text[]), `allergies_confirmed_at`, `conditions` (text[]),
    `seed_recipe_ids` (text[]).
  - `user_nutrition_profiles`: one immutable row per profile version. Fields: `user_id`,
    `profile_version`, `formula_version`, `input_hash`, `targets` (JSONB, the full
    `NutritionTargets`), `calculated_at`.
- Endpoints:
  - `PUT /api/profile` (create or update). Requires an explicit `allergiesConfirmed: true`
    whenever `allergies` is non-empty (section 1: never inferred).
  - `GET /api/profile` returns the profile plus its current targets.
- Service:
  - Map the profile to `TargetInput`, call `calculate_nutrition_targets` and store the
    snapshot.
  - Map the profile to `PlanningProfile`; `profileId` is the user UUID string.
  - On a profile change, call `revalidate_seeds` and store the result. If fewer than 3
    seeds remain, set `needsSeedPicks=true` in the response.
- Cuisine options: `GET /api/catalogue/cuisines` returns `bundle.cuisine_ids` as
  `[{id, name}]`. The frontend uses `name` for the profile and `id` for NLU.
- Tests: targets are stored per version, unconfirmed allergies return 422, and a version
  increment yields a new target snapshot.

### S3 `feat/m3-seed-dishes`

- `GET /api/onboarding/seed-suggestions` → `SeedSuggestions` from
  `suggest_seeds(profile, bundle)`.
- `PUT /api/onboarding/seed-picks` `{recipeIds}` → `confirm_seeds(...)`. A `ValueError`
  maps to 422 with its message. On success, store the picks in order on the profile
  (bumping the version and recalculating targets is not needed for seed-only changes).
  Document this choice.
- Also expose catalogue search for picks beyond the suggestions: `GET /api/catalogue/dishes?q=`
  returns `{recipeId, name, cuisines}`, Food.com dishes only.

### S4 `feat/m3-ai-runtime`

- `savora_backend/ai/runtime.py`: an `AiRuntime` built once in the FastAPI lifespan. It
  holds `bundle` and `scorer`, and logs `modelVersion` or "popularity fallback".
  - With a manifest present and the file absent, use the fallback.
  - On `ModelIntegrityError`, refuse to start with a clear message.
- `savora_backend/ai/gateway.py`: a `Protocol` `AiGateway` with async methods
  `craving(...)`, `plan_week(...)`, `substitute(...)` and `seeds(...)`.
  - The real implementation calls the pipelines through `asyncio.to_thread`.
  - `tests/fakes.py` provides `FakeAiGateway`, returning canned pipeline results built by
    the real Pydantic models so they stay contract-true.
  - Inject the gateway via a dependency.
- Test: the real runtime loads the real export (`len(bundle.combinations) == 465`).

### S5 `feat/m3-craving-nlu` (in `apps/ai_system`, your AI package)

The package is `savora_ai/core/craving_nlu/`; it is currently empty. It must not import
the backend.

- `parse_craving(text, *, parser) -> CravingParse` with fields `request: CravingRequest`,
  `parser: "TEMPLATE" | "QWEN"`, `prompt_version`, `latency_ms` and `clarification`
  (a question for the user when `requiresClarification`).
- `TemplateParser`: the deterministic baseline.
  - Lexicons for intent ("swap", "replace", "change" → `SWAP_MEAL`), cuisines (from
    `bundle.cuisine_ids`, matching case and plurals), flavors (`FlavorTag`), exclusions
    ("no X", "without X", "not X") and slots ("day 2 lunch", "tuesday dinner"; Monday =
    D1 relative to the plan start).
  - Ambiguous or empty input → `requiresClarification=true`.
  - Reuse the PR #11 notebook alias ideas (brinjal → eggplant, capsicum → bell pepper),
    but emit canonical upper-case IDs.
  - **Never** put an allergen into `excludedIngredientIds` because the text mentions
    allergy ("I'm allergic to peanuts" → `requiresClarification`, and the clarification
    asks the user to update their profile). Allergies come only from the confirmed
    profile (section 9.1).
- `QwenParser(client, model, timeout_s=8)`:
  - Versioned prompt at `savora_ai/prompts/craving_v1.md`, with few-shot examples and the
    JSON schema from `CravingRequest.model_json_schema(by_alias=True)`.
  - Use schema-constrained output (Ollama `format`) and `think: false`; start from
    `prompts/craving_nlu_feasibility_v2.md`, which was measured, rather than writing a
    prompt from scratch.
  - Ground the answer (see section 2 item 4), then validate with
    `CravingRequest.model_validate_json`. On invalid JSON, schema
    violations or timeout, fall back to `TemplateParser` and record why.
  - The HTTP adapter lives in `savora_ai/providers/qwen.py` (httpx). Add `httpx` to the
    `savora-ai` dependencies.
- `FakeQwenClient` for tests: returns scripted text, including malicious output (extra
  keys, invalid enums, prose around the JSON).
- Evaluation (section 13):
  - Gold set `savora_ai/evals/craving_nlu_gold.jsonl`: at least 120 utterances covering
    both intents, every cuisine and flavor, exclusions, slots, ambiguity, allergy
    mentions, typos and Nepali/Indian dish words.
  - Runner `python -m savora_ai.evals.craving_nlu` reports intent accuracy, slot
    precision, recall and micro-F1, schema-validity rate, clarification precision and
    recall, and p50/p95 latency for the template parser, and for Qwen when Ollama is
    running. Extend `evals/data/craving_nlu_feasibility.jsonl` (58 cases) rather than
    starting over.
  - Write `docs/eval/craving_nlu.json` and `docs/reports/craving_nlu_report.md` (dataset
    size, model ID, decoding settings, prompt version, hardware/endpoint). **Never report
    Qwen numbers you did not run.**
- Tests: the template parser on the gold set (assert minimum scores you measured), the
  Qwen fallback on every malicious output, and the timeout path.

### S6 `feat/m3-craving-endpoint`

- `POST /api/cravings` `{text}`:
  1. `parse_craving`.
  2. If `SWAP_MEAL`: return `{kind:"SWAP_SUGGESTED", request, clarification?}` so the UI
     routes to the swap flow (S8). Do not swap from free text alone.
  3. Otherwise call `gateway.craving(request, planning_profile)`.
  4. Return `{kind:"RECOMMENDATIONS", parse:{parser, promptVersion}, result:
     CravingRecommendation}`.
- Do **not** store the text, the parse or the results (no craving history in GC1).
- Requires a completed profile; otherwise 409 "complete onboarding first".
- Tests with `FakeAiGateway` and `FakeQwenClient`, plus one real-pipeline test (no Qwen).

### S7 `feat/m3-weekly-plans`

- Tables:
  - `meal_plans`: `id`, `user_id`, `week_start` (date), `revision` (int), `status`
    (`GENERATING`/`FEASIBLE`/`INFEASIBLE`/`INSUFFICIENT_DATA`/`TIMEOUT`/`FAILED`),
    `message`, `profile_version`, `catalogue_version`, `model_version`,
    `fallback_reason`, `kb_id`, `kb_version`, `safety` (JSONB), `search` (JSONB),
    `day_totals` (JSONB), `parent_plan_id` (nullable; the previous revision),
    `is_current`, timestamps.
  - `meal_plan_slots`: `plan_id`, `slot_id` (`D1_BREAKFAST`…), `day_index`,
    `calendar_date`, `meal_type`, `option_id`, `combination_id`, `configuration_id`,
    `preset`, `snapshot` (JSONB: the full `PlannedMeal` incl. explanation, immutable).
    Unique `(plan_id, slot_id)`.
  - Indexes on `(user_id, is_current)` and `(user_id, week_start)`.
- Endpoints:
  - `POST /api/meal-plans` `{weekStart}` → 202 `{planId, status:"GENERATING"}`. A
    background task runs `gateway.plan_week` with `week_id=str(plan_id)` and then, in
    one transaction, writes all 21 slots and the final status. Any exception sets
    `FAILED` and stores the message.
  - `GET /api/meal-plans/{id}` returns the plan plus slots; the frontend polls it while
    `GENERATING`.
  - `GET /api/meal-plans?current=true` lists plans.
- Rules:
  - One `GENERATING` job per user at a time (409 otherwise).
  - Only `FEASIBLE` plans have slots.
  - Ownership is checked on every read (404 for other users' plans).
- Tests: the job lifecycle with the fake gateway (including a failing job), ownership,
  and one slow real-pipeline test marked `@pytest.mark.slow` (register the marker; CI
  still runs it).

### S8 `feat/m3-substitutions`

- Table `meal_plan_substitutions`: `id`, `user_id`, `from_plan_id`, `to_plan_id`
  (nullable until done), `slot_id`, `status`, `message`, `before_snapshot` (JSONB),
  `after_snapshot` (JSONB), `excluded_combination_ids` (text[]), timestamps.
- Endpoint `POST /api/meal-plans/{id}/substitutions` takes `{slotId, expectedRevision,
  excludeCombinationIds?}` and returns 202 `{substitutionId}`.
  - Check that the plan is current, `FEASIBLE`, owned, and that `expectedRevision`
    matches (409 otherwise).
  - The background job calls `gateway.substitute(current={slotId: optionId for 21
    slots}, slot=slotId, ...)`.
  - When it is `FEASIBLE`, create a **new** plan revision (`revision+1`,
    `parent_plan_id`), copy the 20 locked slot snapshots verbatim, add the new slot, flip
    `is_current`, and fill `after_snapshot`. The old plan is never modified.
- `GET /api/substitutions/{id}` returns its status for polling.
- If the profile version changed since the plan was made, return 409 "profile changed;
  generate a new plan". A swap must not lock meals that no longer fit the profile.
- Tests: other slots unchanged, revision conflict, a locked slot is never altered, and the
  before/after snapshots are stored.

### S9 `feat/m3-contracts-frontend`

- Contracts: `make contracts` writes `packages/contracts/openapi.json`. Add
  `openapi-typescript` and a `pnpm --filter @savora/contracts generate` script that
  emits `src/openapi.d.ts`, and re-export it from `src/index.ts`. Commit the generated
  files, and use them for every API type in the frontend.
- Frontend (`apps/frontend/src`):
  - `lib/api-request`: an axios instance with the base URL from `NEXT_PUBLIC_API_URL`, a
    Bearer token from storage and envelope unwrapping. Errors become a typed `ApiError`
    carrying the field errors.
  - `core/public/Auth`: login and register pages and forms.
  - `core/private/UserProfile`:
    - an onboarding wizard: body data → diet/cuisine → allergies with an explicit
      confirmation checkbox → conditions → seed picks (12 suggestions + search, pick 3–5)
    - a profile page showing the targets and their provenance
  - `core/private/MealPlanning`:
    - a 7 × 3 planner grid; each cell shows the dishes, portion, kcal and an
      "explain" drawer with the reasons
    - a "Generate week" button with a progress state while polling
    - a per-slot "Swap" button that polls the swap and then shows the new revision
    - day totals row; unknown nutrients shown as "unknown", never 0
  - `core/private/Craving`:
    - a chat-style input showing the parse ("Chinese · spicy · no noodles") and result
      cards with rank, standard portion, nutrients and an explanation
    - a fixed line on the cards: "Not checked against today's remaining targets"
    - the clarification question when asked
    - a hand-off to swap when the intent is `SWAP_MEAL`
  - A `SafetyNotice` component shows `safety.message` on craving results, the planner and
    the swap result. **Never** write "safe for you" anywhere.
  - Route protection for `(protected)`: redirect to `/login` without a token, and to
    onboarding when the profile is incomplete.
- Checks: `pnpm lint`, `pnpm typecheck`, `pnpm build` and the CI axios guard all pass.

### S10 `feat/m3-e2e-handoff`

- Backend end-to-end test (httpx, real pipelines, fake Qwen): register → profile → seeds →
  craving → plan (job) → swap (job) → plans list. Assert the section 13 end-to-end
  criteria: stored targets; a feasible 21-slot plan; craving results without CSP; a
  substitution with locked slots and before/after snapshots.
- `README.md`: local run steps (db, migrate, backend, frontend, model download via
  `python -m savora_ai.core.recommendation.model_store --download` once the release
  exists).
- `docs/member3/HANDOFF.md`: what was built, the contracts, the decisions from section 2,
  known gaps (section 10) and the measured NLU scores.
- PR #11: move anything useful from its notebooks into S5, then ask the team to close
  PR #11 rather than merge notebooks.

## 4. API summary (all under `/api`, all enveloped, auth required unless noted)

| Method & path | Body | `data` |
|---|---|---|
| `POST /auth/register` (public) | `{email,password,displayName}` | `{user,accessToken}` |
| `POST /auth/login` (public) | `{email,password}` | `{user,accessToken}` |
| `GET /auth/me` | – | `user` |
| `GET /profile` | – | `{profile,targets,needsSeedPicks}` |
| `PUT /profile` | profile fields + `allergiesConfirmed` | `{profile,targets,needsSeedPicks}` |
| `GET /catalogue/cuisines` | – | `[{id,name}]` |
| `GET /catalogue/dishes?q=` | – | `[{recipeId,name,cuisines}]` |
| `GET /onboarding/seed-suggestions` | – | `SeedSuggestions` |
| `PUT /onboarding/seed-picks` | `{recipeIds}` | `{seedRecipeIds}` |
| `POST /cravings` | `{text}` | `{kind,parse,result}` or `{kind:"SWAP_SUGGESTED",request,clarification}` |
| `POST /meal-plans` | `{weekStart}` | `{planId,status}` (202) |
| `GET /meal-plans?current=true` | – | `[planSummary]` |
| `GET /meal-plans/{id}` | – | `plan` with `slots[]` |
| `POST /meal-plans/{id}/substitutions` | `{slotId,expectedRevision,excludeCombinationIds?}` | `{substitutionId}` (202) |
| `GET /substitutions/{id}` | – | `{status,message,toPlanId?}` |

REST paths are plural and kebab-case. JSON is camelCase, and Python and SQL are snake_case.

## 5. Failure modes to handle explicitly

- Model file missing: run with the popularity fallback. The plan and craving responses
  carry `fallbackReason=MODEL_UNAVAILABLE`; show "Ranked by popularity" in the UI.
- Qwen key unset, timeout or invalid output: use the template parser, report
  `parse.parser="TEMPLATE"`, and log the reason.
- `WeekPlan.status` other than `FEASIBLE`: store the status and message and show them.
  Never fabricate slots.
- `CravingStatus.NO_MATCH`: show `unknownCuisineIds` and `unmatchedFlavorTags` and
  suggest relaxing the request.
- Profile not completed: 409 on cravings, plans and seeds.
- Concurrency: one generating job per user, and `expectedRevision` on swaps.

## 6. Definition of done (all slices)

- `uv run ruff check .`, `uv run pyright` and `uv run pytest -q` pass (the full suite
  takes about 15 minutes).
- `pnpm lint`, `pnpm typecheck` and `pnpm build` pass, and so does `make contracts`.
- Every new table has an Alembic migration, `alembic upgrade head` works on an empty
  database, and `downgrade -1` works for each migration.
- `packages/contracts` is regenerated and committed for every DTO change.
- No `.env` is committed, no secrets appear in code or docs, and there is no
  `fastapi`/`sqlalchemy`/`savora_backend` import under `apps/ai_system/src`.
- Each slice is committed with a bracketed message, and **nothing is pushed** until the
  human asks.

## 7. Verification commands

```bash
uv sync && pnpm install
make db && make migrate           # local Postgres via docker compose, or Supabase via .env
uv run ruff check . && uv run pyright && uv run pytest -q
make contracts && pnpm --filter @savora/contracts generate
pnpm lint && pnpm typecheck && pnpm build
make dev-backend   # http://localhost:8000/docs
make dev-frontend  # http://localhost:3000
```

## 8. Out of scope for GC1 (do not build)

- Ratings, likes, consumption tracking, feedback, craving history and retraining.
- Redis, queues, vector databases, Neo4j and separate AI services.
- Re-implementing rules, ranking, composition, CSP or nutrition maths in the backend or
  frontend.
- Inferring diet or allergies from religion or ethnicity.

## 9. Dependencies on others (do not block on them; build against the current behaviour)

| Owner | Item | Effect on your work |
|---|---|---|
| Member 2 (Venkat) | Production rule KB: real diet, allergen and clinical rules, plus ingredient-to-canonical mapping | Until it lands, results stay `STAND_IN_UNVERIFIED`. No code change on your side when it lands. |
| Member 2 (Venkat) | Weekly CSP performance (about 2–3 min per plan; the rule filter reruns per meal option) | That is why plans and swaps are background jobs. Faster solves need no change from you. |
| Member 2 (Venkat) | Search ordering by rank (the solver orders options by ID) and energy/nutrient DAY rules | The pipelines offer one option per slot until this exists. |
| Member 2 (Venkat) | `PLANNED_SWAP` workflow in the daily/weekly CSP contracts (today only `WEEKLY_PLAN` is admitted) | `substitute_slot` solves the swap as a locked week. The result is still labelled `PLANNED_SWAP`, so nothing changes for you. |
| Team / Member 1 (Diwash) | Model hosting for ADR 0005 D2 (deferred by the team on 2026-10-20 until the dataset terms are checked) | Until then, the popularity fallback, labelled. |
| Team | Approval of this spec's section 2 decisions 1 to 4 | Note them in each PR. |

## 10. Known limitations to state in the handoff

- Allergy screening is ingredient-name matching (stand-in). Derived ingredients are not
  detected.
- Health conditions are recorded but not enforced.
- Weekly energy targets are displayed but not optimised. The CSP verifies completeness
  only (stand-in rules).
- Some combinations are culturally odd (for example, a curry as a breakfast base). That
  is a Member 1 catalogue item; report examples rather than filtering in the app.
