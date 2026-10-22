# ADR 0007: Member 2's compact B1 swap proof in the swap job

- **Status:** Proposed (Member 1), needs joint DTO/release approval with Member 2 (PR #21)
- **Date:** 2026-10-23
- **Owner:** Member 1 (resolver, saved-plan authority, persistence, API/UI); Member 2 owns
  `execute_compact_swap` / `verify_compact_swap`
- **Relates to:** ARCHITECTURE.md section 4.4; `docs/member2/compact_swap_handoff.md`;
  `apps/ai_system/src/savora_ai/core/pipelines/swap_proof.py`; migration `0006_swap_proof`

## Context

A saved-slot swap was checked only by re-solving the week with the other 20 slots locked
(WEEKLY_PLAN context), because Member 2's expanded PLANNED_SWAP envelope did not fit 1 MiB
for a real week. Member 2's compact protocol (PR #21, merged into PR #20's branch) moves
the material server-side: the wire input names sources by
`(catalogue_version, combination_id, content_digest)` and a `TrustedSourceResolver`
supplies the bodies and the saved-plan authority.

## Decision

1. `prove_swap` (AI pipeline) builds the compact **B1** input for the saved week and the
   replacement the CSP accepted, plus a `CatalogueResolver`. The resolver is built per
   request from the server's catalogue bundle and the slots the backend loaded for the
   authenticated owner; it rejects any other saved-plan binding or catalogue release and
   never echoes client bodies.
2. The saved-plan authority is honest about history: `UNVERIFIED`, no certificate digest,
   so Member 2's protocol replays both complete weeks freshly. Nothing is labelled
   VERIFIED_AT_SAVE.
3. The target snapshot records the profile's estimated day targets with
   `bandsEnforced: false` and **no nutrient bands**: saved weeks are portion-fitted, not
   band-verified (ADR 0006), so a band would reject swaps over days the user did not touch.
4. `execute_compact_swap` (which already runs its mandatory independent check) is followed
   by `verify_compact_swap`; `verified` is true only when the result is VALID, complete and
   the external check accepts it.
5. The swap job runs the proof after a FEASIBLE CSP result. `SWAP_PROOF_MODE`:
   - `required` (default): the new revision is stored only when the proof is verified;
     REJECTED → INFEASIBLE, INSUFFICIENT_DATA, TIMEOUT and ADMISSION_FAILED → FAILED, each
     with a user-facing reason; the saved plan stays unchanged.
   - `record`: CSP-feasible swaps are stored and the proof is recorded beside them.
   - `off`: no proof (slow machines).
6. Migration 0006 adds `meal_plan_substitutions.proof` (the `SwapProof` JSON: status,
   reason, input digest, certificate digest, exact changed-day native totals, seconds) and
   `proof_certificate_digest`. `GET /api/substitutions/{id}` returns `proof`; the swap
   sheet shows "Swap independently verified" and the job's phase message while it runs.

## Measured (catalogue 20261021T073631Z, Apple M3 Pro)

| Run | Result | Time |
|---|---|---|
| Mixed vegetarian week, milk allergy, swap D2_LUNCH | VALID, verified, 7 exact totals | 226 s for build, execute and verify (another proof was running at the same time) |
| Member 2's fixture, B1 alone | VALID, verified | build 63 s, execute 142 s, verify 74 s (contended) |

A swap therefore takes the CSP time (about 30-50 s) plus a few minutes of proof. The job is
in the background and the sheet says so.

## Consequences

- Swaps now carry a PLANNED_SWAP proof of the synthetic stand-in obligations, bound to the
  saved plan, owner, profile version, KB release and catalogue sources. It is still not a
  clinical or allergy-safety claim (`STAND_IN_UNVERIFIED`).
- B2 (Member 2 selecting among ranked candidates) is not wired: our ranker and the user's
  choice already pick the replacement, and B2 re-checks every candidate in full.
- Plan and lock revisions are both 1-based and taken from the saved row; there is no lock
  inventory yet (no user-pinned meals in GC1).

## Open items needing team approval

1. Joint approval of the DTO/release use above (Member 2's activation checklist).
2. Whether to drop the external `verify_compact_swap` (about a third of the time), since
   execution already performs a mandatory independent check.
3. Storing a VERIFIED_AT_SAVE certificate when a plan is generated, so later swaps need not
   replay the original week.
