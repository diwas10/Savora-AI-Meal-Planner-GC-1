# GC1 submission fixes — 23 October 2026

Base: `origin/main` at `3a09c49746f6a864b0a7ab099fb93f4175de2bf0`.
Work is isolated on `fix/submission-persistence-safety`; existing worktrees are preserved.
This note supplements ADRs 0006 and 0007. It does not approve clinical rules or replace
historical evaluation evidence.

## Running the prototype

The shortest supported application path remains the root README Quick Start:

1. Configure `.env` with a reachable PostgreSQL database and a suitable JWT secret.
2. Run `make setup`, then `make migrate`.
3. In separate terminals run `make dev-backend` and `make dev-frontend`.
4. Register, complete the profile with `MIXED` or `STRICT` cuisine policy, confirm seed
   picks, try Discover, generate a week, poll it to completion, inspect all seven days,
   select a replacement, wait for the B1 check, then reload the saved revision.

For the documented model fallback, set `QWEN_PROVIDER=none`. Without an installed ranking
checkpoint, ranking uses the labelled popularity fallback. PostgreSQL is still required
for the live application; SQLite in tests is not a production database fallback.
Keep `SWAP_PROOF_MODE=required` for the submission demonstration.

Apply migration `0008_saved_plan_source_binding` before starting the updated backend.
It adds one nullable JSONB column, with no backfill. Existing saved plans remain readable;
regenerate them before swapping because their original source binding was not recorded.

## Persistence changes

- Profile updates, seed saves and final job commits use the same profile-row lock. The
  final transaction also locks and refreshes the owned plan, substitution, target and
  saved slot rows before saving a new revision. Generation and B1 execution run outside
  these final-save locks.
- Generation refuses stale profile versions, changed seed selections and changed full
  target snapshots. A refused result cannot replace the prior current plan.
- Substitution rechecks ownership, current-plan status, parent revision, profile,
  job status, requested slot and its original payload at the final transaction boundary.
- Newly saved plans record a server-owned binding of plan/owner/revision/profile/release,
  complete target snapshot, all 21 meal snapshots, and the complete combinations and
  component recipe digests used by the plan. Source or target mismatches refuse a swap
  before proof execution, and are checked again before persistence.
- Reconstruction may use the loaded catalogue only after those saved source digests
  match. Missing legacy bindings and changed sources require regeneration. These
  application bindings are not certificates and never manufacture `VERIFIED_AT_SAVE`.
- B1 receives the original full calculator snapshot in addition to the existing day
  estimates. The optional adapter argument preserves existing callers and protocols.
- Required proof mode refuses incomplete or UNKNOWN proof outcomes. A verified response
  also requires VALID status, a certificate digest and seven complete native totals.
  An inconsistent `verified=true` flag is cleared before returning/storing the proof.

## API and frontend changes

`MAJORITY` was accepted but not enforced. Profile writes now reject it, the generated
OpenAPI/TypeScript input contract includes only `MIXED` and `STRICT`, the UI removes the
option, and legacy profiles must choose a supported policy before generation.

The UI describes the actual stand-in checks and warns that nutrient bands, clinical
rules and allergy safety are not verified. Missing nutrient values remain unknown.
A swap status-fetch failure now displays a retry message instead of an unexplained
indefinite checking screen. No new product flow or interface redesign is introduced.

## Native nutrient enforcement: explicitly deferred

The native seven-nutrient DAY/WEEK contracts and their independent proof tests exist,
but current `planning.py` does not connect them to application planning. ADR 0006's
portion fitting toward energy/protein estimates remains in place. Compact B1 continues
to declare `bandsEnforced: false` with no nutrient bands, as ADR 0007 requires.

Connecting the native strategy would change solver obligations for existing weeks and
swaps and needs separate planning and saved-history compatibility evidence. That change
is deferred for this submission. Solver call arguments, proof protocols and resource
limits are preserved. A FEASIBLE application result or VALID stand-in B1 proof must not
be presented as seven-nutrient, allergy or clinical compliance. Mandatory missing evidence
in the native evaluator remains UNKNOWN, not PASS.

## Verification and environment evidence

The audit machine has Node 24.21.0 and an existing Python project environment. Locked
frontend dependencies installed successfully. No configured application/test PostgreSQL
URL, reachable local PostgreSQL/Qwen service, Docker, Ollama, local ranking checkpoint
or Torch runtime was available. No database or model service was started or provisioned.
There is no claim of a complete browser-to-PostgreSQL journey or a Qwen-backed run.

Backend HTTP journey tests use SQLite and deterministic AI fakes. Real catalogue/CSP/B1 tests exercise
the documented library fallback independently of HTTP and PostgreSQL. Staged concurrency
tests check changes across await boundaries; SQLite does not prove PostgreSQL row-lock
behavior. Migration SQL is compiled for the PostgreSQL dialect without historical backfill.

| Final local check | Result |
| --- | --- |
| Entire `apps/backend/tests` | 63 passed, 1 skipped, 16.68 s |
| Real weekly plan, locked-slot substitution, B1 replay with full calculator snapshot, architecture dependency direction | 4 passed, 366.89 s |
| Native nutrient contracts/search proofs, swap-proof contracts, compact reconstruction policy, compact swap and example | 144 passed, 289.95 s |
| Repository Ruff | Passed |
| Pyright with the installed Python interpreter | 0 errors, 0 warnings |
| Frontend ESLint, TypeScript, production Next.js build | Passed; all 15 pages generated |
| Exact current-app OpenAPI and generated TypeScript export comparison | Passed |
| `git diff --check` | Passed |

Total final focused tests: **211 passed, 1 skipped, 0 failed**. The skipped test is
`test_full_journey_on_postgres` because `SAVORA_TEST_POSTGRES_URL` is unset. The full
repository pytest suite was not rerun locally. Transient implementation errors found
during development were corrected before these final checks.

Checks used the existing Python environment with `PYTHONPATH` set to the backend/AI
source directories and `QWEN_PROVIDER=none`. Frontend checks used
`corepack pnpm --filter @savora/frontend lint`, `typecheck` and `build`; the global pnpm
shim was absent. Installed dependencies and generated build outputs are not committed.

Available main CI at review time: run
[39938687311](https://github.com/diwas10/Savora-AI-Meal-Planner-GC-1/actions/runs/39938687311)
on the base SHA had a successful frontend job and successful Python lint/typecheck and
boundary checks; full pytest was still running. This is not a completed CI pass for
the changes in this branch.

No historical campaign, model training, clinical approval, committed evaluation record
or historical proof was rerun or edited.

## Submission recommendation

Submit as a limited academic prototype with the stated fallback and safety limitations.
Before a live demonstration, migrate the database, regenerate old plans, and run the
documented journey on a configured PostgreSQL instance. Native nutrient enforcement and
clinical/allergy validation remain unresolved and must not be claimed in the report.
Merge remains a human review decision; full CI status must be inspected on the PR.
