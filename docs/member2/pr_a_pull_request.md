## Summary & Motivation
Weekly v2 currently orders values by ID and cannot express exact native multi-nutrient
targets. Add explicit priority/native strategies with independent proof replay while
preserving historical protocols, parameters and wire goldens. Ingredient mappings and
clinical declarations remain review-only/inactive. This dependency-aware extraction
excludes the unfinished expanded and compact swap transport.

## Architecture & Ownership
- **Relevant `ARCHITECTURE.md` Section(s):** §§3–5, 8, 9, 11, 13.
- **Touched Workspaces:**
  - [ ] `apps/frontend` (Next.js App Router)
  - [ ] `apps/backend` (FastAPI / SQLAlchemy / Alembic)
  - [x] `apps/ai_system` (Rule/KG, Composer, Ranker, CSP, Qwen, XAI)
  - [ ] `packages/contracts` (OpenAPI / Shared TS Types)
  - [x] Infrastructure / CI / Docs

## Key Changes
- Seven native nutrients, exact decimal DAY/WEEK bands, explicit priorities and independent replay.
- Version-disjoint native result tag; unchanged legacy schemas/default behavior and solver parameters.
- Reviewed mapping provenance/completeness/approval contracts and inactive clinical drafts; no production activation.
- Executable Member 1 examples, real catalogue vectors and preliminary benchmark handoff.
- Preliminary V1 327.044984/404.911207s versus V2 93.639264/89.226649s: two pairs,
  no warmups, identical verified witnesses, no significance claim. Historical measured
  fingerprint differs from final source; no trained Transformer scorer selected the fixture.
  Phase 7.4 remains 624/3007; no campaign restart.

## Savora Invariants Checklist
- [x] Dependency direction respected (`apps/frontend` → `apps/backend` → `apps/ai_system`; no backend/DB imports in `apps/ai_system`)
- [x] Safety invariants preserved (Rule Engine gates eligibility; unknown safety-critical fields do not `PASS`; LLM never invents nutrition)
- [x] Shared contracts in `packages/contracts` updated if backend DTOs changed — N/A; no HTTP DTO changes.
- [x] Alembic migration added if SQLAlchemy entities changed — N/A; no persistence changes.

## Verification Executed
- [ ] `uv run ruff check .` — exact alternative: local venv Ruff check all AI source and new tests passed.
- [x] `uv run pyright` — equivalent local venv invocation, full configured scope, 0 errors/warnings.
- [ ] `uv run pytest -q` — targeted/wider scope: 712 distinct repo tests passed; no skips.
- [ ] `pnpm lint` — not run; frontend unchanged.
- [ ] `pnpm typecheck` — not run; frontend unchanged.
- [ ] `pnpm build` — not run; frontend unchanged.

Additionally 27 actual Member 1 PR #19 pipeline tests and latest-catalogue native
replay passed in an isolated compatibility overlay. Existing
`reuse_preparation=True, preparation_cache_entries=1` call still works. Ruff format,
architecture dependency/cycle gate and four fresh legacy wire hashes passed.

Full scope/files/protocols/evidence: `docs/member2/pr_a_audit.md` and `pr_a_handoff.md`.
Member 1 still owns native/priority application adapters. PR B will target this branch
for native DTO reuse; merge A before B and retarget B to main after A merges.
Production ingredient/clinical approvals remain unavailable and inactive.
