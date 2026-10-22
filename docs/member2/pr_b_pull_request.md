## Summary & Motivation
Expanded real-catalogue swap authority repeats source material and exceeds transport/
result ceilings. Add an explicit compact B1/B2 protocol with independent trusted-source
reconstruction, full original/result checks and a verified replacement delta. This is
implemented Member 2 core functionality; Member 1's runtime/backend integration remains pending.

Depends on PR #20 for native nutrient DTOs. Merge #20 first, then retarget this PR to main.

## Architecture & Ownership
- **Relevant `ARCHITECTURE.md` Section(s):** §§3–5, 8–11, 13.
- **Touched Workspaces:**
  - [ ] `apps/frontend` (Next.js App Router)
  - [ ] `apps/backend` (FastAPI / SQLAlchemy / Alembic)
  - [x] `apps/ai_system` (Rule/KG, Composer, Ranker, CSP, Qwen, XAI)
  - [ ] `packages/contracts` (OpenAPI / Shared TS Types)
  - [x] Infrastructure / CI / Docs

## Key Changes
- CompactSwapInput/Result and TrustedSourceResolver Protocol, versioned authority/source refs.
- Exact owner/current revision/profile/target/KB/history/locks/configuration bindings; no digest-only trust.
- B1/B2 full-source semantic replay, whole-domain hard eligibility, native totals/bands, exact candidate ranking binding.
- Independent checker reloads authority and reconstructs the full witness; no executor call or manufactured saved proof.
- Fixed caps: 1 MiB wire input/output/proof, 4 MiB deduplicated canonical input. Legacy protocols/default ceilings unchanged.
- Real-sized B1/B2 fixture: 7161/7286 input bytes, 945-byte results, 956568/956715 canonical bytes; VALID with independent replay.
- Exact adapter/persistence/status/canonicalization handoff and JSON schemas/examples.

## Savora Invariants Checklist
- [x] Dependency direction respected (`apps/frontend` → `apps/backend` → `apps/ai_system`; no backend/DB imports in `apps/ai_system`)
- [x] Safety invariants preserved (Rule Engine gates eligibility; unknown safety-critical fields do not `PASS`; LLM never invents nutrition)
- [x] Shared contracts in `packages/contracts` updated if backend DTOs changed — N/A; no HTTP DTO changed.
- [x] Alembic migration added if SQLAlchemy entities changed — N/A; Member 1 owns future runtime migrations.

## Verification Executed
- [ ] `uv run ruff check .` — exact alternative: local venv Ruff on all AI source/changed tests passed; 19-file format check passed.
- [x] `uv run pyright` — equivalent local venv invocation, full configured scope, 0 errors/warnings.
- [ ] `uv run pytest -q` — 529 distinct targeted/wider cases pass in the final per-case inventory.
- [ ] `pnpm lint` — not run locally; frontend unchanged.
- [ ] `pnpm typecheck` — not run locally; frontend unchanged.
- [ ] `pnpm build` — not run locally; frontend unchanged.

46 final release tests passed. Wider legacy sweep initially had 268 passes / 2 failure-
injection regressions; late-binding factory behavior was restored and all four variants
of the affected test passed. Full raw run/dedup details: docs/member2/pr_b_audit.md.
Four fresh legacy wire SHA values match main; final architecture/cycle gate passes.
Real B1/B2 independent replay and a separate Decimal oracle for seven native day totals pass.

## Integration limits
Draft until Member 1's actual resolver/backend adapters pass end-to-end validation.
The real fixture has fictional authority/target and the stand-in KB; no trained scorer
or clinical validation. Clinical declarations and production mapping activation remain
inactive. No Phase 7.4 campaign restart, application wiring, database migration or
persistence change. No merge is requested automatically.
