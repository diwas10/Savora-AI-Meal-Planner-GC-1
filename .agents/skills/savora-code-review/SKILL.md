---
name: savora-code-review
description: >-
  Review code changes or Pull Requests against Savora architecture boundaries,
  clinical/allergen safety invariants, and monorepo engineering rules. Use when
  reviewing a PR, auditing a branch diff, or performing pre-PR self-review.
---

# Savora Architecture & Safety Code Review

When reviewing a diff (`git diff main...HEAD`), check every item below and report findings by severity (`BLOCKER`, `WARNING`, `NIT`).

## 1. Monorepo & Layer Boundaries (`BLOCKER`)
- `apps/ai_system` (`savora_ai`) must **never** import `savora_backend`, FastAPI controllers, SQLAlchemy ORM models, or frontend code.
- `apps/frontend` must **never** connect directly to Supabase/PostgreSQL or import Python source files; all business calls go through FastAPI (`/api/*`).
- Frontend components must use `.api.ts` → `.query.ts` hooks, never raw `axios` or `fetch` inside UI components.
- No out-of-scope infrastructure (Redis, Celery, Neo4j, vector DB, separate AI server, Vite, React Router).

## 2. Savora Safety & Domain Invariants (`BLOCKER`)
- **Fail-closed safety:** Rule Engine eligibility uses `PASS | FAIL | UNKNOWN`. `UNKNOWN` or missing safety-critical nutrient/ingredient data must **never** be treated as `PASS` or `0`.
- **Hard rules everywhere:** Diet, allergen, and hard clinical restrictions apply in **all** flows, including standalone craving discovery.
- **Role separation:**
  - Qwen extracts structured intent only and is schema-validated; it never selects safe recipes or invents nutrition/rules.
  - Meal Composition combines complete dishes without setting portion grams.
  - Transformer ranks only rule-`PASS` candidate IDs; never invents dishes or nutrition.
  - CSP alone assigns discrete portions and 21-slot schedules; standalone craving bypasses composer and CSP.
  - Saved-plan substitution locks the other 20 slots unless the user explicitly agrees otherwise.
- **Persistence scope:** Persist generated plans and substitutions only — no ratings, consumption tracking, feedback logs, or craving history tables.

## 3. Backend & Database Standards (`WARNING` / `BLOCKER`)
- Controllers remain thin and never manually build `{success, source, data, message, status}` envelopes.
- Wire DTOs inherit `CamelModel` (`camelCase` JSON, `snake_case` Python/SQL).
- SQL queries use bound parameters and explicit transaction boundaries; schema changes include an Alembic migration.
