## Summary & Motivation
<!-- Concise explanation of what this PR changes and why -->

## Architecture & Ownership
- **Relevant `ARCHITECTURE.md` Section(s):** <!-- e.g., §6 API Design, §10 Database Design -->
- **Touched Workspaces:**
  - [ ] `apps/frontend` (Next.js App Router)
  - [ ] `apps/backend` (FastAPI / SQLAlchemy / Alembic)
  - [ ] `apps/ai_system` (Rule/KG, Composer, Ranker, CSP, Qwen, XAI)
  - [ ] `packages/contracts` (OpenAPI / Shared TS Types)
  - [ ] Infrastructure / CI / Docs

## Key Changes
<!-- Bulleted breakdown of key changes by module/file -->
- 

## Savora Invariants Checklist
- [ ] Dependency direction respected (`apps/frontend` → `apps/backend` → `apps/ai_system`; no backend/DB imports in `apps/ai_system`)
- [ ] Safety invariants preserved (Rule Engine gates eligibility; unknown safety-critical fields do not `PASS`; LLM never invents nutrition)
- [ ] Shared contracts in `packages/contracts` updated if backend DTOs changed
- [ ] Alembic migration added if SQLAlchemy entities changed

## Verification Executed
- [ ] `uv run ruff check .`
- [ ] `uv run pyright`
- [ ] `uv run pytest -q`
- [ ] `pnpm lint`
- [ ] `pnpm typecheck`
- [ ] `pnpm build`
