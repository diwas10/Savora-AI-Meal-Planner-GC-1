# GitHub Copilot Instructions — Savora

Read and enforce [`AGENTS.md`](../AGENTS.md) and relevant sections of [`ARCHITECTURE.md`](../ARCHITECTURE.md) when reviewing Pull Requests or writing code.

## Critical PR Review Checks
- **Architecture Boundaries:** `apps/frontend` (Next.js App Router) → `apps/backend` (FastAPI) → `apps/ai_system` (`savora_ai`). `apps/ai_system` must never import `savora_backend`, FastAPI, SQLAlchemy, or database drivers.
- **Database:** Supabase PostgreSQL accessed exclusively by `apps/backend` via async SQLAlchemy 2 and Alembic migrations. No Redis, Neo4j, Celery, or vector DBs in GC1.
- **Clinical & Allergen Safety:** Rule Engine deterministically gates eligibility (`PASS`, `PENALIZE`, `WARN`, `BLOCK`); unknown safety-critical fields must never default to `PASS`. Nutrition and unit calculations must never come from LLM/Qwen output.
- **Frontend Layering:** `.api.ts` → `.query.ts` (TanStack React Query) → components; no direct `axios` calls in components or `src/app/`.
- **Backend Conventions:** Thin controllers → services → repositories; `CamelModel` DTOs (`camelCase` JSON, `snake_case` Python/SQL); centralized `/api` response envelopes.
