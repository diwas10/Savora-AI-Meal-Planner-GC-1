# Phase 7.3a: saved-plan, lock and swap contract foundation

Member 2, synthetic contracts only. Checkpoint HEAD
`ecc74a74959f0c521d400c6228d644bf505e80f2`, branch
`feature/member2-phase7`, worktree `Savora-Phase7`. Authority:
[master plan](member2_phase73_75_master_plan.md), sections C/F/G/H/I/K,
[Phase 7 ADR](adr_member2_phase7_search_and_swap.md), AGENTS.md and relevant
ARCHITECTURE.md workflow/ownership sections. Shared production decisions remain
pending; implementing this foundation does not approve those interfaces.

## Scope and exact inventory

Only the following six files are created:

| Path under repository root | Responsibility |
|---|---|
| `apps/ai_system/src/savora_ai/schemas/planned_swap.py` | Strict saved/slot/lock/permission/source/bridge/request/domain/ranking/manifest/result-plan and limit declarations |
| `apps/ai_system/src/savora_ai/schemas/swap_proof.py` | Declaration-only results, ordered event declarations and prospective cost/reservation equations |
| `apps/ai_system/src/savora_ai/core/reasoning/planned_swap.py` | Independent structural bindings and complete manifest selection |
| `apps/ai_system/tests/test_planned_swap_contracts.py` | Independent structural fixtures, authority/lock/projection/ingress attacks |
| `apps/ai_system/tests/test_swap_proof_contracts.py` | Cost/boundary/ranking/proof hostility and absent-execution tests |
| `docs/member2_phase73a_saved_plan_contracts.md` | This contract and verification handoff |

The preexisting untracked master plan is retained unchanged. Prior code/tests,
Phase 7.2 handoffs and `.delta/phase72d`/`phase72e` records remain intact. New local
test/static evidence belongs to `.delta/phase73a` and is not a shared contract.
There is no `validate_swap`, `verify_swap_validation`, replacement selector,
computed swap result, semantic proof checker or CSP change. No new package export,
dependency, HTTP/TypeScript, teammate, production source, clinical or database work.

## DTO and protocol inventory

All models inherit frozen, strict, extra-forbidden, recursively revalidated
contract behavior. CamelCase wire aliases, original-JSON duplicate-key/alias
defenses, canonical enum identity and unchecked-instance rejection are retained.
New roots additionally bound their encoded structural envelope to 1 MiB and reject
nonsynthetic evidence. Numeric/boolean literals require exact scalar types.

| Type(s) | Schema token / purpose |
|---|---|
| `SwapReference` | ID/version/content-digest pin, not a credential |
| `SyntheticTargetReference` | `synthetic-swap-target-reference.v1`; mandatory evidenced synthetic identity only, no target calculation or nutrients |
| `SwapSlotIdentity`, `SavedSlotPayload` | Exact day/week/date/meal and complete FIXED option, recipe snapshots and original source |
| `SavedPlanReference`, `SavedPlanVerificationRecord` | Effective revision and immutable snapshot pin; historical UNVERIFIED/VERIFIED_AT_SAVE claims, never current PASS |
| `SavedPlanSnapshot` | `saved-plan-snapshot.v1`, policy `synthetic-saved-plan.v1`; immutable original request/source/context/candidates/trial/assignment/21 payloads/target/provenance |
| `SavedPlanMaterial` | `saved-plan-material.v1`; full snapshot plus independently selected effective reference |
| `LockKind`, `SavedSlotLock`, `SavedPlanLockInventory` | USER/SYSTEM restrictions; `saved-plan-lock-inventory.v1`, own strict revision and digest |
| `SwapTargetPermission` | `swap-target-permission.v1`; full independently selected grant body, exact saved/lock/target/profile/context pins and issuer evidence |
| `PlannedSwapSourceSnapshot` | `planned-swap-source.v1`; independently selected PLANNED_SWAP context, candidates and fixed option pool |
| `SwapOptionProjection`, `PlannedSwapWorkflowBridge` | `planned-swap-workflow-bridge.v1`, policy `synthetic-planned-swap-bridge.v1`; complete one-to-one original/projection origin mapping |
| `PlannedSwapRequest` | `planned-swap-request.v1`, policy `synthetic-planned-swap.v1`; one target and exact expected authority pins; operation REPLACE_FIXED_MEAL |
| `SwapReplacementDomain` | `swap-replacement-domain.v1`; canonical original 0–50 references resolving to exact source payloads |
| `SyntheticRankEntry`, `SyntheticSwapRanking` | `synthetic-swap-ranking.v1`; synthetic-fixed-combination-rank.v1 or explicit CANONICAL_OPTION_ID; complete declared eligible subset, integer priority/option-ID tie; no evaluated eligibility |
| `ExpectedSwapCheckManifest` | `expected-swap-check-manifest.v1`; complete accepted PLANNED_SWAP definitions, permission, locks and original slot inventory, NOT_EVALUATED |
| `SavedPlanContractCheck` | `saved-plan-contract-check.v1`; canonical slot digests and independently checked structural references; semantics/history authentication NOT_EVALUATED |
| `SwapPlanSnapshot` | `swap-plan-snapshot.v1`; mixed-origin tentative21-slot payload, exact20 unchanged and one non-no-op target; NOT_EVALUATED, not a verified plan |
| `SwapWork`, `SwapValidationLimits`, `SwapSelectionLimits` | Named bounded semantic work categories and `swap-validation-limits.v1` / `swap-selection-limits.v1`; explicit prospective ceilings |
| `SwapOperation`, `SwapOperationReservation`, `SwapReservationPlan` | `swap-operation-reservation.v1`, `swap-reservation-plan.v1`, policy `synthetic-swap-work-reservation.v1`; no operation executed |
| `SwapProofEventDeclaration` | Flat numbered typed source/bridge/lock/baseline/candidate/DAY/WEEK/frontier claims; assessment NOT_EVALUATED |
| `SwapValidationCertificate`, `SwapSelectionCertificate` | `swap-validation-certificate-declaration.v1`, `swap-selection-certificate-declaration.v1`; distinct synthetic-swap-validation-proof.v1 / synthetic-swap-selection-proof.v1 policies; never accepted proofs |
| `SwapValidationDeclaration`, `SwapSelectionDeclaration` | `swap-validation-result-declaration.v1`, `swap-selection-result-declaration.v1`; outcome=None, accepted=False, verification_complete=False, semantics NOT_EVALUATED |

Every digested content type has strict `build(content, expected_digest=None)`
using the existing unordered declaration-content encoding. A supplied wrong/null
digest is rejected rather than replaced. Snapshot digest excludes its own digest
and contains no mutable effective revision or reference back to itself. Material
digest covers the full snapshot and effective reference; its reference must match
the inner snapshot's actual digest/identity. No circular digest or latest lookup.
Ordered events use a separate SHA-256 of compact sorted-key JSON with
`policy=synthetic-swap-ordered-events.v1` and the event list in supplied order;
sequence must be exactly 0..n-1. Declaration hashing is not proof verification.

## Saved-plan and lock invariants

Canonical slot index is `3*(day_index-1)+meal_index`, with breakfast/lunch/dinner
0/1/2. Exactly seven original consecutive days and 21 unique FIXED choices must
agree with the original request/domains, trial, structural assignment, original
sources, daily request digests and complete recipe snapshots. Saved slot payloads
retain configuration/portion, preparation, component multiplicity, measurement
value/completeness/unit/basis, suitability, source and evidence. No scalar nutrient
subtraction, portion calculation or recipe catalogue refresh occurs.

`SwapPlanSnapshot` is a tentative shape: its target must be an actual original
identity, its other20 full payloads must equal the originals, and its target must
resolve exactly to independent source data. A metadata-only context/digest rewrap
of the same fixed combination/configuration/components is rejected as no-op,
including context-bound recipe projection digests. It is not an old
`WeeklyAssignment` relabelled into mixed sources.

All non-target slots are implicit locks regardless of the explicit inventory.
Explicit USER and SYSTEM locks may both exist on a slot; duplicate kind/slot
entries and foreign slot identities reject. No unlock/override field exists.
The manifest's `locked_slots` property derives all20 rather than trusting a
caller list; `target_lock_kinds` retains authoritative target restrictions.
Package A may represent a locked-target request for future rejection; it does
not compute REJECTED or authorize changing that target. B1 must give target lock
denial precedence and may never treat manifest construction as permission to swap.

Historical VERIFIED_AT_SAVE requires paired native v1/v2 result/protocol references
but remains a claim only. Both structural helper reports stay NOT_EVALUATED even
for a well-formed fabricated historical stamp. B1 must fully revalidate original
and resulting fixed plans; no repair workflow or cached historical PASS is enabled.
Required baseline UNKNOWN must survive to downstream checking, where independent
known FAIL may dominate; none of that predicate execution happens here.

## Authority and complete workflow projection

The source/context/KB/saved/lock/permission/bridge arguments must be selected by a
trusted loader independently of the proposal. A Python argument position or digest
cannot authenticate them. A caller controlling every root can fabricate a
self-consistent dataset; Member3 remains responsible for authentication, current
revision selection, revocation/freshness and authorization before invocation and
again at write time. Matching pins never grant a transaction lease.

The permission **body** is mandatory independently of its request reference.
Its plan revision, lock reference, one target, operation and profile/context must
match. Stale/mismatched pins raise Pydantic validation errors; no automatic refresh.
No semantic eligibility result or backend error mapping is introduced.

The bridge retains exact original material and separately supplied PLANNED_SWAP
counterparts. It compares all context content, allowing only context ID/version,
workflow and exact context-owner/reference fields in VersionedFact records to
change. Profile, target, KB/graph/taxonomy/catalogue/check-catalogue, policy,
observation value/completeness and evidence remain bound. Original candidate
counterparts must preserve all content except those context references and their
derived content digests. Recipe IDs/versions/snapshot IDs/versions remain fixed.

Mapped option counterparts may differ only in combination context ID/version/
digest, derived combination/reference digests, context-projected recipe reference
digests (also in preparation/measurement contributors), and dependent option
references in suitability/measurement records. All quantities, units, component
occurrences, roles, preparations, configuration identities, observations, external
source pins, completeness and evidence are compared in full. Declaration record
order is normalized by the established unordered policy, not confused with event
sequence. Evaluation projections do not overwrite original persisted payloads.

Every projected source option appears exactly once in the mapping. Every selected
original option, including the target, has an exact original-to-projection mapping.
A new independent replacement origin uses `original=None` with nonempty evidence
and cannot shadow an original option ID. Future B1 must still revalidate it; its
presence does not confer eligibility. Projection content is compared to independent
counterparts; the helper does not manufacture a rehashed source as authority.

Original WEEKLY_PLAN source restrictions are unchanged. New swap sources enforce
PLANNED_SWAP and full source/candidate/preparation/configuration consistency.
Complete workflow definitions are selected from the independently accepted KB,
not copied from the weekly manifest. Empty or unknown predicate inventories never
become PASS because there is no semantic assessment. Missing/conflicting required
structural bindings reject rather than being filled with fabricated values.

## Exact structural helpers

```python
validate_saved_plan_material(
    saved_plan, *, knowledge, original_context, original_sources, original_candidates
) -> SavedPlanContractCheck

build_swap_check_manifest(
    request, *, saved_plan, locks, permission, knowledge, context, sources, bridge
) -> ExpectedSwapCheckManifest
```

These implement the master plan's authority arguments unchanged. Inputs are
recursively revalidated before comparison. KB acceptance and complete mandatory
definition selection are allowed structural work. No rule fact resolver,
predicate evaluator, filter eligibility call, combination evaluator, DAY/WEEK
assessment, weekly solver or proof checker is invoked. Tests forbid those calls.
The complete admission envelope is bounded to 1 MiB. Both helpers preserve their
inputs and produce only structural reports/manifests.

## Resource and proof declarations

Representation ceilings: 21 slots, 150 options per source, 50 fixed replacement
alternatives, 32 component occurrences, 1,024 flat proof operations/events, 1 MiB
per structural envelope/declared proof/result, original JSON depth64, and no cache.
Revisions are strict integers1..1,000,000; work integers0..1,000,000. Validation
invocation cap0..1; selection cap0..51 (up to50 candidates plus one final check),
domain visits0..50. Finite optional absolute deadlines are declarations only;
there is no clock observation, checkpoint execution or hard interruption claim.

For a declared operation with `n` items in category `k`:

- prospective execution has `k=n` and all other categories0;
- prospective verification has `k=n`, plus one checker step if `n>0` (add to that
  same category if the operation itself is CHECK_STEP);
- reservation is the exact category-wise sum;
- for `n>0`, reserve one record and `payload_bytes+1024` bytes; for zero items,
  payload/record/byte reservation must all be zero;
- declarations' actual execution/verification remain exactly zero.

Operations enumerate source-item/bridge-item visits, locked-payload comparisons,
candidate/combination preparations, predicate obligations, original/result DAY/WEEK
assessments, domain/ordering visits, full validation invocations and checker steps.
The unit is a semantic named item, not a CPU call/instruction. Manifest/KB/source
admission records and output encoding must be represented in source/checker visits
and complete payload bounds, including envelope headers; they are not free.
Repeated baseline/final/nested checker passes need separate operations. B1 must
derive item counts and encoded payload bounds from independent material and verify
every transition. Package A validates cost equations, not that declared counts
actually describe a performed computation. No executable cost policy is enabled.

`SwapReservationPlan` sums operations under every work/proof/result/validation/
domain cap and rejects one-short capacities; no silent fallback or budget increase.
It does not turn that structural fit into a success/timeout verdict. Result
declarations may omit a certificate, but never attach computed TIMEOUT/VALID or
nonzero actual work. A future certificate-free TIMEOUT control envelope, complete
output-byte reservation and cooperative execution/checker accounting belong to B1.
Proof record reservations, encoded declaration size and future process memory are
different metrics. Resource declaration tests cannot establish future execution.

## Verification and completion

**COMPLETE** within the Package A synthetic structural/declaration scope.

Verified interpreter:
`../Savora-AI-Meal-Planner-GC-1/.venv/Scripts/python.exe`, with
`PYTHONDONTWRITEBYTECODE=1` and
`PYTHONPATH=<this worktree>/apps/ai_system/src;<this worktree>/apps/backend/src`.
Import-origin inspection confirms both packages resolve here, not to the sibling
checkout. Pydantic 2.14.0 was inspected in the existing environment. No dependency
installation or other-worktree modification occurred.

| Actual final check | Result / retained evidence |
|---|---|
| `python -m pytest -q apps/ai_system/tests/test_planned_swap_contracts.py apps/ai_system/tests/test_swap_proof_contracts.py -p no:cacheprovider --junitxml=.delta/phase73a/final-contracts-v2.xml` | **140 passed**, 217.44s; no failures/errors/skips |
| Required eight existing suites listed below, one combined `pytest -q ... -p no:cacheprovider --junitxml=.delta/phase73a/regressions.xml` invocation | **1,435 passed**, 106.04s; no failures/errors/skips |
| `python -m ruff check apps` | All checks passed |
| `python -m ruff format --check apps` | 109 Python files already formatted |
| `python -m pyright --pythonpath <verified interpreter>` | 0 errors, 0 warnings, 0 informations; absent configured local `.venv` notice is informational |
| Tracked and six new-file whitespace, scope, branch/HEAD and empty-index checks | PASS; no tracked files changed; exactly six task paths plus the preexisting master plan untracked |
| Final Python source/test SHA-256 snapshot | Five exact paths match `.delta/phase73a/source-hashes.json`; no subsequent Python edits |
| Prior source/evidence preservation | Tracked Phase1–7.2 source/tests remain equal to checkpoint; all55 captured prior master-plan and Phase7.2d/e evidence file hashes unchanged |

The eight existing test files, all under `apps/ai_system/tests/`, were:

| File | Passing cases |
|---|---:|
| `test_candidate_contracts.py` | 541 |
| `test_candidate_filtering.py` | 91 |
| `test_rule_manifest.py` | 82 |
| `test_combination_contracts.py` | 194 |
| `test_combination_evaluation.py` | 92 |
| `test_daily_contracts.py` | 150 |
| `test_weekly_contracts.py` | 164 |
| `test_weekly_search_v2_contracts.py` | 121 |

Final distinct passing coverage is **1,575 cases** (140+1,435). XML identities are
checked for uniqueness/disjointness. These are relevant contract regressions,
**not a new full Python monorepo run**. The complete suite remains due at the
previously recorded release checkpoint/final audit. No frontend/shared HTTP change
was made, so frontend checks were not run. No Phase7.2 benchmark was rerun.

New cases cover independent permission/source/revision pins, exact canonical
original inventory, mutation of each of the20 implicit locks, USER/SYSTEM target
restriction retention, complete manifest selection, context-bound counterparts,
rehashed projection changes, source/workflow relabel attempts, historical stamp
non-authority, no-op/configuration separation, original JSON/alias/enum/container/
unchecked-instance defenses, all12 operation-cost categories, zero/exact/one-short
reservations, strict numeric ceilings, ordering/transplant attacks and forbidden
affirmative/computed/actually-executed claims. Semantic entry points are monkeypatched
to fail if the helpers invoke them. Computed swap/selection APIs are asserted absent.

Development evidence is retained but excluded from the final distinct count:
`development.xml` initially had33 passes and one fixture setup failure (a changed
context version still carried old fact owner/version pins). The fixture now builds
a valid independently mismatched context before testing rejection. Initial lint/
type diagnostics were corrected. A59-case targeted run and a139-pass preliminary
full run are superseded by the final140-case run. Final review additionally made
no-op identity independent of component declaration order; its regression is in
the final run. No initial failure is accepted as unresolved or silently counted
as passing evidence. Durations are test execution, not performance benchmarks.

`verification-summary.json` and `preservation-check.json` retain final case/hash
accounting. Git checks accept ordinary Windows CRLF while rejecting trailing-space,
EOF and space-before-tab diagnostics. No staging, commit, push or PR occurred.
No unresolved HIGH/MEDIUM correctness/security defect is identified in this
declaration-only scope; independent semantic verification remains deliberately
unimplemented rather than claimed complete.

## Remaining integration decisions and next gate

Member1 must approve real recipe/component/preparation/portion identities,
conversions, full required nutrient measurements/completeness, target versions and
eligible-ID ranking/fallback contracts. Member3 must approve current immutable
saved material/revision and lock authority, grant issuance, authenticated loading,
revocation, HTTP/error/size/resource policies and atomic compare-and-write. Clinical
source/applicability activation remains outside this synthetic scope.

B1 must implement independent semantic validation/checking with full original and
resulting21/7/1 obligations, complete FAIL/UNKNOWN/N/A semantics, actual cost and
output reservation enforcement, proof coverage and final witness withholding.
Initial policy allows structurally valid unverified history only into that full
recheck path; historical stamp and structural helper output are never authority.
Target lock denial, stale write comparison and unknown-lane selection rules remain
mandatory next-stage obligations, not capabilities implemented here. No Phase7.3b
or Phase8 execution is authorized by this handoff.
