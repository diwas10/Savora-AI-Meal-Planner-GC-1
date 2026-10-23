# Savora GC1 app: handoff (22 October 2026)

The GC1 app is complete end to end: onboarding, versioned targets, a verified 7-day plan,
saved-plan swaps with the other 20 meals locked, standalone craving discovery with local
Qwen, and an installable PWA. This document replaces the Member 3 slice handoff of PR #17;
it covers that work, the completion on `feat/m1-app-completion`, and the integration of
Member 2's Phase 7 (PR #18).

## 1. What is built

| Area | Where | Notes |
|---|---|---|
| Backend foundations | `apps/backend/src/savora_backend/{config,database,exceptions,interceptors,contexts,decorators}` | envelopes via `TransformRoute`, global handlers, `CamelModel`, request context |
| Layered modules | `core/<module>/{entity,dto,repository,service,controller}.py` | users, auth, nutrition_profiles, catalogue, onboarding, cravings, meal_plans, substitutions |
| Migrations | `apps/backend/alembic/versions/0001`–`0005` | up/down verified on PostgreSQL 16; `alembic check` reports no drift |
| AI runtime | `savora_backend/ai/{runtime,gateway}.py` | catalogue, Transformer (or labelled popularity fallback) and NLU parser built once |
| Craving NLU | `savora_ai/core/craving_nlu/`, `providers/qwen.py`, `prompts/craving_v2.md` | local Ollama Qwen, schema-constrained, grounded, merged with the template parse |
| Swap options | `savora_ai/core/pipelines/planning.py::suggest_replacements` | ranked, rule-screened alternatives for one slot, optional preference words |
| Weekly CSP | `planning.py::_solve` | Member 2's `solve_weekly_plan_v2` (Phase 7) |
| Frontend PWA | `apps/frontend` | built to `.agents/designs/DESIGN_SYSTEM.md` and `SCREENS.md` |
| Contracts | `packages/contracts` | regenerated with `make contracts` |

## 2. API (all under `/api`, enveloped, auth required except register/login)

| Method and path | Purpose |
|---|---|
| `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` | argon2 passwords; HS256 token in an httpOnly cookie (or Bearer) |
| `GET /profile`, `PUT /profile` | profile and versioned target snapshot; an unchanged save keeps its version |
| `GET /catalogue/cuisines` | the 19 target cuisines (incidental tags such as British are hidden) |
| `GET /catalogue/dishes?q=` | seed-eligible dish search (top 50) |
| `GET /onboarding/seed-suggestions`, `PUT /onboarding/seed-picks` | ADR 0005 seed dishes (3–5) |
| `POST /cravings` | NLU, then retrieval → rules → ranking; nothing stored |
| `POST /meal-plans` (202), `GET /meal-plans`, `GET /meal-plans/{id}` | background generation with polling; every plan kept |
| `POST /meal-plans/{id}/slots/{slotId}/replacement-options` | ranked eligible meals for one slot; optional `preferenceText` |
| `POST /meal-plans/{id}/substitutions` (202) | the chosen option (`replacementCombinationId`) or words; locked-week validation in the background |
| `GET /substitutions/{id}` | swap status, before/after snapshots, parsed preference |

## 3. Decisions (spec section 2, as implemented)

1. **Auth**: backend-owned email/password; argon2 and HS256. `APP_ENV=production`
   refuses the development secret or one shorter than 32 characters. The browser session
   is the token in an httpOnly, SameSite=Lax cookie (`savora_session`, path `/api`,
   Secure in production) that scripts cannot read. Next.js rewrites `/api` to FastAPI
   (`BACKEND_URL`), so the cookie is first-party. Cookie-authenticated writes must send
   `X-Savora-Client` (CSRF); `POST /auth/logout` clears the cookie. Bearer tokens still
   work for API clients and tests. No refresh tokens in GC1 (60-minute sessions).
2. **Catalogue**: the versioned JSON export, loaded once into the shared AI runtime.
3. **Jobs**: in-process tasks, state on the row, stale jobs failed at startup. A job start
   locks the profile row, and migration 0005's partial unique indexes allow one generating
   plan and one generating swap per user. A failure shows a fixed message; details are logged.
4. **Qwen**: local Ollama `qwen3:0.6b`, `format` = the `CravingRequest` schema, thinking
   off, temperature 0. Steps: strict schema check → `ground()` → strict validation → merge
   with the template parse (`HYBRID`). Any failure falls back to the template parser with a
   recorded reason (`QWEN_UNAVAILABLE`, `QWEN_TIMEOUT`, `QWEN_INVALID_SCHEMA`, ...).
   `QWEN_PROVIDER=openai` supports a hosted endpoint; `none` disables the model.
5. **Swaps** (section 4.4, SCREENS.md): words → validated preference → ranked eligible
   options → the user picks one → the week is re-solved by Member 2's CSP with the other 20
   options locked → a new plan revision with before/after snapshots. The parsed preference
   is stored on the substitution; the raw text never is.
6. **Password reset**: `POST /auth/forgot-password` always answers the same, so it cannot
   show who has an account; it mails a single-use link (SHA-256 stored, 60 minutes, one per
   account per minute, a newer link ends older ones). `POST /auth/reset-password` sets the
   password and `users.password_changed_at`, which ends every session issued earlier.
   Pages `/forgot-password` and `/reset-password`; migration `0007`. Mail goes through SMTP
   (`SMTP_*`, `FRONTEND_URL` in `.env.example`); without `SMTP_HOST` the link is logged
   outside production and nothing is sent in production, so **set SMTP before deploying**.
7. **No craving history**: Discover's chat lives only in the screen's memory.

## 4. Craving NLU evaluation (`docs/reports/craving_nlu_report.md`)

Measured with qwen3:0.6b on an Apple M3 Pro. The independent set (58 utterances, written
for the model-size study) is the fairer estimate; the template parser was written together
with the 125-utterance gold set.

| Independent set | Template | Qwen (grounded) | Hybrid (production) |
|---|---|---|---|
| Exact match | 0.845 | 0.638 | **0.931** |
| Slot micro-F1 | 0.938 | 0.889 | **0.964** |
| Clarification precision | 0.538 | 0.500 | **0.875** |
| Latency p50 | 0.2 ms | 368 ms | about 370 ms |

## 5. Member 2 Phase 7 integration (PR #18)

- **Weekly search v2 is in use.** `solve_weekly_plan_v2` with incremental forward
  checking and preparation reuse returns the same verified witness as v1 on a strict Indian
  vegetarian week in **50 s instead of 175 s**: the rule filter runs once per week rather
  than once per option. Each result is rechecked by Member 2's independent verifier.
- **PLANNED_SWAP proof is integrated (compact B1, PR #21; ADR 0007).** After the CSP
  accepts a swap, `pipelines/swap_proof.py::prove_swap` builds Member 2's compact B1 input
  and a server-side `CatalogueResolver`; `execute_compact_swap` and `verify_compact_swap`
  replay both complete weeks and reconstruct the witness independently. With
  `SWAP_PROOF_MODE=required` (default) only a verified swap becomes a new revision; the
  proof (status, certificate digest, exact changed-day totals) is stored on the
  substitution (migration 0006) and shown in the swap sheet. A proof takes a few minutes on
  a real week (226 s measured).
- **Native nutrients (PR #20) are merged but not yet driving portions.** Its nutrient
  search checks bands only at complete weeks (no pruning yet) and a contract holds at most
  75 options, so offering every preset per slot (up to 105) is not possible yet; portions
  stay fitted before the CSP (ADR 0006).

## 6. Verification performed

- Python: ruff, ruff format, pyright and the full pytest suite (results in the PR).
- PostgreSQL 16: migrations up, down and up; `alembic check` clean; the opt-in journey test
  `apps/backend/tests/test_postgres.py` (JSONB, `TEXT[]`, two concurrent plan requests →
  exactly one 202 and one 409, options, swap, revisions).
- Frontend: `pnpm lint`, `pnpm typecheck`, `pnpm build`.
- Browser (Microsoft Edge via Playwright, 390×844, real backend, real pipelines, local
  Qwen): register → onboarding → targets → seed dishes → plan generated (52 s) → Home →
  meal detail → My Plan → swap with words and a chosen option (50 s) → Discover chat →
  swap hand-off → Profile; desktop and dark mode. PWA: manifest, icons and service worker
  active; offline, visited pages show saved plans and unvisited pages show `/offline`.

## 7. Known limits and open team decisions

1. **Stand-in KB** (`STAND_IN_UNVERIFIED`): allergies are matched on the dish name and
   ingredient names, including common derived ingredients for the nine major allergen
   groups plus gluten and seafood (`pipelines/allergens.py`, reviewed by Member 1; for example milk
   blocks ghee and paneer, wheat blocks soy sauce, shellfish blocks Thai curry paste).
   Conditions are recorded but not enforced; every result shows the safety notice.
   Excluded ingredients (preferences) block only as a main ingredient; a minor one is
   listed on the meal to leave out or swap (ADR 0008). Allergies block in any amount.
2. **Energy is fitted, not verified** (ADR 0006): each day's portion presets are chosen
   toward the energy band and protein minimum before the CSP, which still checks
   completeness only. Fitted days are mostly in band (for example 6 of 7 instead of 0 for
   a strict Indian vegetarian week); the plan message reports the count.
3. **Ranking** (decided 2026-10-23): keep the shipped hybrid and ANCHOR aggregation; it
   ties popularity on the catalogue (`docs/reports/catalogue_ranking_evaluation.md`). The
   model is not published for GC1 (ADR 0005): the demo machine holds the verified file,
   others run the labelled popularity fallback.
4. **Strict single-cuisine weeks**: every target cuisine works; Nepali has exactly the 4
   breakfasts a week needs (no spare), so strict vegan Nepali returns INSUFFICIENT_DATA.
5. **Curation** marked `ai-review:claude` in `Data/curated/` awaits a person's review.
6. **Swap proof time**: the compact B1 proof adds a few minutes per swap (ADR 0007);
   `SWAP_PROOF_MODE=record` or `off` trades that for speed.
