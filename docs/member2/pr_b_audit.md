# PR B final audit

## A. Base and branch

Base: PR A #20, `feat/member2-native-nutrients-review`,
`42cf205a298bfd132fd2728de470a4c04c4e676b`. Branch: `feat/member2-compact-swap`.
This dependency is genuine: source vectors, native units and general DAY/WEEK bands
import PR A's native nutrient contracts. Merge A before B, retarget B to main after A.
Main remains b96d5a46c757b40a709b87262d09eed027b86cf4. PR #19 remains open at c5af633.

## B. Exact changed files

- `apps/ai_system/src/savora_ai/core/reasoning/compact_swap.py`
- `apps/ai_system/src/savora_ai/core/reasoning/compact_swap_material.py`
- `apps/ai_system/src/savora_ai/core/reasoning/compact_swap_resolver.py`
- `apps/ai_system/src/savora_ai/core/reasoning/swap_checks.py`
- `apps/ai_system/src/savora_ai/core/reasoning/swap_proof.py`
- `apps/ai_system/src/savora_ai/evals/compact_swap_example.py`
- `apps/ai_system/src/savora_ai/evals/saved_plan_fixture.py`
- `apps/ai_system/src/savora_ai/schemas/candidates.py`
- `apps/ai_system/src/savora_ai/schemas/compact_swap.py`
- `apps/ai_system/src/savora_ai/schemas/compact_swap_canonical.py`
- `apps/ai_system/src/savora_ai/schemas/planned_swap.py`
- `apps/ai_system/src/savora_ai/schemas/swap_envelope.py`
- `apps/ai_system/src/savora_ai/schemas/swap_envelope_policy.py`
- `apps/ai_system/src/savora_ai/schemas/swap_proof_types.py`
- `apps/ai_system/tests/compact_swap_fixtures.py`
- `apps/ai_system/tests/test_compact_reconstruction_policy.py`
- `apps/ai_system/tests/test_compact_swap.py`
- `apps/ai_system/tests/test_compact_swap_example.py`
- `apps/ai_system/tests/test_integration_envelope.py`
- `docs/member2/compact_swap_handoff.md`
- `docs/member2/compact_swap_input.schema.json`
- `docs/member2/compact_swap_real_example.json`
- `docs/member2/compact_swap_result.schema.json`
- `docs/member2/pr_b_audit.md`
- `docs/member2/pr_b_pull_request.md`

No frontend/backend/persistence/SQL/Alembic/OpenAPI/generated TS/catalogue files changed.
The eval fixture records compact IDs/references/results and pinned source-file hashes;
it does not duplicate the expanded multi-megabyte catalogue/source bodies.

## C. APIs and protocols

Implemented: CompactSwapInput, CompactSwapResult, CompactSwapVerification,
CompactSwapAuthority, CompactSavedPlanBinding, CompactCombinationSource,
CompactPortionSource, CompactTargetSnapshot and versioned AuthorityReference.
TrustedSourceResolver.resolve(catalogue_version: str, ids: tuple[str, ...]) returns
tuple[CompactCombinationSource, ...]; load_authority(binding) independently supplies
the authenticated/current server authority. Full signatures and JSON schemas are in
`compact_swap_handoff.md`, `compact_swap_input.schema.json`, `compact_swap_result.schema.json`.

`admit_compact_swap`, `execute_compact_swap`, `verify_compact_swap` are executable
explicit entry points. Verification independently reloads complete authority/sources,
reconstructs both full weeks and their proof obligations, and never calls the executor.
The result is one verified substitution delta; Member 1 must preserve the 20 original
saved payloads and provide the complete 21-slot effective application view.

Protocol IDs: compact-planned-swap-input.v1, synthetic-compact-fixed-swap.v1,
compact-planned-swap-result.v1, compact-planned-swap-verification.v1,
compact-combination-source.v1, compact-target-snapshot.v1, compact-swap-authority.v1,
compact-swap-source-reconstruction.v1, compact-swap-canonical-dag.v1,
compact-swap-canonical-proof.v1, compact-swap-phase-assessment.v1,
compact-swap-phase-certificate.v1, compact-swap-reconstructed-certificate.v1,
compact-swap-hard-eligibility.v1. The previously proposed compact-swap-transport.v2
has not been silently activated. No runtime route/registry is installed.

## D. Executed tests and real-sized evidence

**529 distinct tests pass in the final per-case inventory**, with no remaining
failure/error/skip. Exact raw runs (XML/logs retained under ignored `.delta/pr-b/`):

- 214 passed: test_integration_envelope.py, test_member2_phase3_integration.py,
  test_planned_swap_contracts.py.
- 270-test wider sweep: 268 passed, 2 failed. These were unchanged checker
  failure-injection tests. A new private phase-factory default captured the old class
  too early; late binding was restored. The affected complete parameterized test
  (all four variants) then passed. Existing tests were not rewritten.
- 180 passed in an intermediate core/architecture run; its changed compact cases
  are superseded by the final release run below.
- 8 passed: the four corrected failure-injection variants, three canonical policy
  tests and serialized real example validation.
- **46 passed in the final release run**: all 41 compact cases, three canonical
  reconstruction cases, serialized real example and the final dependency/cycle gate.
- Ruff/static and fresh legacy wire comparisons are separate gates below. The final
  test summary deduplicates by (classname, name), preferring the latest report.

The compact tests cover client slot/preset/source-digest/profile/target/KB/history/
owner/ranking tampering, unavailable/missing/stale/malformed/tampered resolver returns,
forged proof and changed-day totals, native UNKNOWN propagation, exact bands, lock
behavior and independent lock revisions, candidate alias rejection, reservation/
deadline stops and exact canonical cap behavior. A 6.4 MiB repeated aggregate fits
through deduplication; genuinely unique material above 4 MiB still fails. Historical
output caps remain 1 MiB. The verifier is tested with the phase executor disabled.

Representative real export: 20261021T073631Z, pinned to Member 1's c5af633 catalogue
(704 dishes / 1692 combinations). This fixture has 21 saved slots and one admitted
replacement at a genuinely available HIGHER_PROTEIN configuration; it is not a
50-candidate stress test or an unrestricted catalogue search.

| Mode | Compact input bytes | Compact result bytes | Exact canonical reconstruction bytes | Result / independent verify |
|---|---:|---:|---:|---|
| B1 | 7161 | 945 | 956568 | VALID / accepted |
| B2 | 7286 | 945 | 956715 | VALID / accepted |

Full JSON and expected outputs are in compact_swap_real_example.json; generator:
`python -m savora_ai.evals.compact_swap_example --catalogue <c5af633>/Data/catalogue --output <file>`.
Final-source B1 independent replay and B2 execution plus independent replay passed.
All seven changed-day totals additionally match independent Decimal sums over M1's
actual portion configurations, without using the native kernel's arithmetic.

This is **real data with fictional owner/profile/target/authority and the stand-in KB**.
It is not authenticated end-to-end application evidence, a trained Transformer fixture,
clinical validation, a latency cohort or a Phase 7.4 continuation. The first expanded
proof attempt exceeded the old 1 MiB phase ceiling; the final explicit compact proof
codec deduplicates proof material under the same 1 MiB cap. No cap was bypassed.

## E. Ruff / Pyright / architecture

Ruff check of all AI source and changed/new tests passed. Ruff format check of all
19 changed/new Python files passed. Full configured Pyright (AI/backend/tests) reports
0 errors, 0 warnings. The unchanged architecture dependency/cycle test passes on the
final tree. `git diff --check` passes. No local frontend or full backend build/test was
run, because those workspaces and HTTP contracts are unchanged.

## F. Member 1 compatibility

PR A's 27 actual PR #19 pipeline tests and latest-catalogue native replay passed in
an isolated overlay. This PR changes no weekly solver/pipeline file relative to A.
`reuse_preparation=True, preparation_cache_entries=1` remains supported with unchanged
defaults. New application integration still requires Member 1's real resolver, current
saved-plan authority, authenticated target binding, migrations, persistence, API/UI and
end-to-end tests. Those features were deliberately not implemented by Member 2.

## G. Historical compatibility

Fresh final-source weekly v1/v2 and B1/B2 serialized SHA-256 values match archived main:

- weekly v1: a4741e103f7f9fed44a7b82f3b95102db85368c642b780dd77c87515528c8985
- weekly v2: 78a5be77d51ee796cdddbb5fddd7ad30b89cfa6249df6565867d1e0f2f49f89a
- B1: 80a0771469661c35e870b484af214e385c8e43df458b48453d308ae1233a28a1
- B2: 993a3a6183f677c13c4f748f0ca818264808278bc3ee371a5bd8450682214061

Legacy default schemas, constructors, byte ceilings and proof behavior remain intact.
Compact reconstruction is server-selected and isolated; ordinary legacy/real policies
retain their own raw byte ceilings. Compact proofs have disjoint version tags and a
separately bounded canonical codec. No caller can use a client digest as source evidence.

## H. Known blockers / scope limits

Core compact execution/reconstruction is implemented. **PR B is not fully application
integrated.** Member 1 must implement and validate the trusted runtime resolver and
backend adapters end to end. Existing saved rows without full authority/target/proof
bindings cannot be admitted by manufacturing metadata. Native weekly prior-history
tags need a separately approved saved-history adapter; do not relabel them as legacy.

Production ingredient mappings and clinical approvals remain absent. Mapping releases
are review-only; hypertension/type 2 diabetes/dyslipidemia declarations remain inactive.
There is no production clinical rule base or clinically validated label. The compact
fixture target enables no nutrient bands; general native bands and UNKNOWN behavior
are exercised independently by the compact tests and PR A's real native target test.

Limits: 1 MiB compact input/output, exact 4 MiB canonical input, 1 MiB canonical proof,
existing atomic historical proof ceilings, bounded work/records/domain and cooperative
deadlines. There is no forced admission/I/O preemption or process RAM cap. Member 1 must
bound storage fetches. Conservative whole-domain reservations can stop a wide B2
request before trying an otherwise promising first candidate. The backend applies only
the target delta, rechecks current revision/profile/locks transactionally and preserves
the 20 saved slot payloads.

## I. Commits and preservation

Contract/resolver commit: 06a33698b7a34adb4b806a45ce88636e63805150. Execution/admission/verification commit: 62832da35a2dc0b33e191c53a142e22abad0f031.
Fixture/handoff/audit commit: 9c0e2a3d5af4526c56c9653b22b7d33a00b63b47.
A following documentation-only commit records publication metadata. No source history was rewritten.
Original six commits 357b172, faa69cc, 11fb5a7, 4110567, ede74ba, ea40e45 remain intact
on feat/member2-real-integration-contracts. Phase 7/reporting worktrees and the untracked
master plan are unchanged. Phase 7.4 remains 624/3007; no campaign jobs were restarted.

## J. Remote publication

PR A: https://github.com/diwas10/Savora-AI-Meal-Planner-GC-1/pull/20, non-draft,
head 42cf205a298bfd132fd2728de470a4c04c4e676b. Remote frontend and architecture/review
checks passed; Python CI was still running at the last read.
PR B: https://github.com/diwas10/Savora-AI-Meal-Planner-GC-1/pull/21, dependent **draft**, target
`feat/member2-native-nutrients-review`, published at `9c0e2a3d5af4526c56c9653b22b7d33a00b63b47`.
Both branch pushes and PR creation succeeded. The completed repository PR template
contains exact source/fixture commits and verification evidence. Nothing is merged.

PR A implementation commit: 2d93f022665406804c18758169798da44d9b24f4.
PR A audit/publication head: 42cf205a298bfd132fd2728de470a4c04c4e676b.
