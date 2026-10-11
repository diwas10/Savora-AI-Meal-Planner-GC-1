# AGENTS.md — Savora Engineering Rules

## Authority and reading policy
- Read this file on every task. Read relevant sections of `ARCHITECTURE.md` for domain, API, schema, or cross-module changes; do not load the entire document unnecessarily.
- `ARCHITECTURE.md` defines approved product behavior and ownership. Existing code/tests show implementation details. Surface conflicts instead of silently changing the contract.
- Follow the established monorepo conventions below; the one-time bootstrap prompt is **not** a runtime source of truth.

## Monorepo and runtime
- `apps/frontend`: **Next.js App Router**, TypeScript, Tailwind, TanStack React Query, React Hook Form, Zod. `src/app` owns routes/layouts; `src/core` owns feature implementation. No React Router or Vite.
- `apps/backend`: FastAPI, Pydantic v2, async SQLAlchemy 2, Alembic. Owns HTTP, authentication, persistence, transactions, and application orchestration.
- `apps/ai_system`: importable Python package, same backend runtime for GC1. Owns food preprocessing, nutrition calculation, composition, recommendation, Rule/KG, CSP, Qwen NLU, XAI and evaluations.
- `packages/contracts`: OpenAPI-generated frontend types and example contract fixtures; no direct sharing of Python model source with TypeScript.
- **Dependency direction:** Next.js → FastAPI → typed AI interfaces. AI core must not import backend controllers, ORM repositories or frontend code. Backend owns database I/O; AI receives validated data.
- Supabase PostgreSQL is the sole required data store (accessed exclusively by FastAPI via SQLAlchemy/Alembic). No Redis, Neo4j, vector database, queue, or separate AI microservice for GC1.

## Engineering patterns
- Correctness → clarity → simplicity → safety → testability → maintainability → performance. Inspect neighboring code before editing; avoid speculative frameworks.
- Backend: thin controllers → domain services → repositories; typed DTOs; `CamelModel` with camelCase wire aliases; SQL/Python snake_case. Use migrations, bound SQL parameters and explicit transaction boundaries.
- Standard `/api` envelopes: success `{success, source, data, message, status}`; error `{success:false, source, message, status, description?}`. Validation 422 has field-to-message arrays. Centralize wrapping and exception handling; do not wrap in controllers.
- Retain pragmatic shared foundations: `CommonEntity`/`PrimaryEntity`, `RequestContextProvider` for user/request audit, `RuntimeException`, `ValidationException`, global handlers, `@response_message` + `TransformRoute` where practical. Do **not** copy office/center, device fingerprinting, enterprise RBAC or accounting-specific patterns.
- Frontend: `.api.ts` declarative endpoints → `.query.ts` React Query hooks → feature components; no Axios calls directly in components. Use Zod + React Hook Form. Server Components by default; use `use client` only for interactive features. FastAPI remains the only business backend; Next route handlers are optional thin proxies.
- AI: Pydantic-validated boundaries, versioned prompts, isolated model adapters, deterministic test fakes, explicit timeouts and failures. Never trust Qwen output or model-generated nutrition.
- Naming: Python/SQL snake_case, JSON camelCase, Python/TS classes PascalCase, REST plural kebab-case.

## Git & Pull Request workflow
- Never commit, push, or merge directly to `main`; always work on a `feat/<scope>-<desc>`, `fix/<scope>-<desc>`, `refactor/<scope>-<desc>`, or `chore/<scope>-<desc>` branch.
- Format commit messages with bracketed prefixes: `[ADD]:`, `[UPDATE]:`, `[FIX]:`, `[REFACTOR]:`, or `[DELETE]: <concise imperative summary>`.
- **Do not push or open a Pull Request automatically.** Wait until the user explicitly instructs you to push or create a PR; when instructed, fill out `.github/PULL_REQUEST_TEMPLATE.md` completely and leave merging to human review.

## Savora invariants
- Rule Engine determines eligibility; unknown safety-critical fields do not PASS. Applicable hard clinical and allergy restrictions always apply, including craving.
- Meal Composition constructs sensible combinations; Transformer ranks eligible recipe/combination IDs; CSP chooses feasible portions and 21-slot assignments. Nutrition/units come from validated data.
- Standalone craving: Qwen → retrieval → rules → recipe ranking (content/popularity fallback for cold start); **no** composer/CSP. Planned substitution: full composition/ranking/CSP flow, other slots locked unless user explicitly agrees otherwise.
- Persist generated plans and substitutions only. No ratings, consumption, feedback events, craving history or automatic retraining in GC1.

## Execution checklist
1. Identify owner, relevant `ARCHITECTURE.md` section, consumers, input/output DTOs and failure modes.
2. Implement a small vertical slice on a non-`main` branch; update tests and shared contracts for changes.
3. Run relevant Python (`ruff`, `pyright`, `pytest`) and frontend (`pnpm lint`, `pnpm typecheck`, `pnpm build`) checks; state what actually ran.
4. Report changed contracts, remaining risks and deviations; wait for user instruction before pushing or opening a PR.
