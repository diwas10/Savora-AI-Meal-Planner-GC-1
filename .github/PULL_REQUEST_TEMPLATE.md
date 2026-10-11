## Summary
<!-- Concise summary of the vertical slice or change -->

## Architecture & Ownership
- **Relevant `ARCHITECTURE.md` Section(s):** <!-- e.g., §6 API Design, §10 Database Design -->
- **Touched Packages:**
  - [ ] `apps/frontend`
  - [ ] `apps/backend`
  - [ ] `apps/ai_system`
  - [ ] `packages/contracts`
  - [ ] Infrastructure / CI / Docs

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
