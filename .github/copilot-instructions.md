# Savora GitHub Code Review Instructions

When reviewing pull requests or generating code in this repository, enforce the rules defined in [`AGENTS.md`](../AGENTS.md) and [`ARCHITECTURE.md`](../ARCHITECTURE.md).

## 1. Architecture & Dependency Direction (Blockers)
- **Dependency Flow:** `apps/frontend` (Next.js App Router) → `apps/backend` (FastAPI) → `apps/ai_system` (Python package).
- **`apps/ai_system` Isolation:** Must **never** import `savora_backend`, FastAPI controllers, SQLAlchemy repositories, database drivers, or frontend modules. Backend owns all database I/O; AI receives Pydantic-validated inputs.
- **Database:** Supabase PostgreSQL (`db.bgrlvhporhrmjsmgexay.supabase.co`) accessed exclusively by `apps/backend` via async SQLAlchemy 2 + Alembic. Do not introduce Redis, Neo4j, Celery, or vector databases in GC1.

## 2. Savora Safety & Domain Invariants (Blockers)
- **Rule Engine Eligibility:** Deterministic Rule Engine decides hard eligibility (`PASS`, `PENALIZE`, `WARN`, `BLOCK`). Unknown safety-critical fields must **never** default to `PASS`.
- **Allergy & Clinical Restrictions:** Hard clinical and allergy restrictions always apply across both weekly meal planning and standalone craving flows.
- **Nutrition Authority:** Nutrition values and unit conversions must come from deterministic calculations over validated ingredient/recipe data—never from LLM/Qwen output.
- **Craving vs. Substitution Flows:**
  - Standalone craving: Qwen NLU → retrieval → Rule Engine → recipe ranking (with cold-start fallback). No Meal Composer or CSP solver.
  - Planned slot substitution: Full composition → ranking → CSP flow with all non-selected slots locked unless the user explicitly permits broader changes.
- **Persistence Scope:** Persist generated meal plans and substitutions only. Do not persist ratings, consumption logs, feedback events, craving history, or automatic retraining loops in GC1.

## 3. Layering & Code Conventions
- **Backend (`apps/backend`):**
  - Thin controllers → domain services → repositories.
  - Use `CamelModel` with camelCase JSON aliases and snake_case Python/SQL names.
  - Use centralized `/api` response envelopes (`TransformRoute` + `@response_message`) and global exception handlers (`RuntimeException`, `ValidationException`); do not manually wrap envelopes inside controllers.
- **Frontend (`apps/frontend`):**
  - Next.js App Router (`src/app` for routes/layouts, `src/core` for feature modules). No React Router or Vite.
  - Strict data access layering: `.api.ts` (declarative endpoints) → `.query.ts` (TanStack React Query hooks) → components. Never call `axios` directly inside components or pages.
  - Default to React Server Components; add `'use client'` only for interactive leaf components.
- **Git & PR Hygiene:**
  - Commits must use bracketed prefixes: `[ADD]:`, `[UPDATE]:`, `[FIX]:`, `[REFACTOR]:`, `[DELETE]:`.
  - Schema changes require Alembic migrations; API DTO changes require updated contracts in `packages/contracts`.
