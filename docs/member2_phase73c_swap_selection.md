# Phase 7.3c — bounded fixed replacement selection

Status: COMPLETE, 2026-10-21. Ready for a separately authorized Phase 7.4.
Phase 7.4 is not implemented by this package. No unresolved HIGH/MEDIUM findings.

The approved scope is master-plan C8–C10 / Package B2. AI core owns the pure
selection and independent verification boundaries. Backend persistence and
application adapters remain outside this package.

## Public contract

`savora_ai.core.reasoning.planned_swap.select_swap_replacement(request, *,
domain, ranking, saved_plan, locks, permission, candidates, knowledge, context,
sources, bridge, limits, clock=monotonic) -> ComputedSwapSelectionResult`.

`verify_swap_selection(result, *, request, domain, ranking, saved_plan, locks,
permission, candidates, knowledge, context, sources, bridge, limits,
clock=monotonic) -> SwapProofCheck` is available from the same module.

Both use the exact C8 typed authority arguments. Request references, saved PASS
history, declared eligible IDs, priority integers and certificate digests are
claims checked against independently supplied complete material. They are never
credentials. Malformed, stale or conflicting authority is a boundary error even
with zero operational capacity. The strict 1 MiB admission envelope is unchanged.

## Domain, hard checks and ordering

The authoritative domain contains 0–50 canonical unique original FIXED references.
Every reference resolves to its exact source option. Context, saved revision,
target, locks, permission, source and bridge pins must all agree. Duplicate
semantic alternatives cannot inflate coverage. The original fixed target receives
an explicit NO_OP disposition. No portion or option is manufactured by selection.

Every original option receives a fresh full recipe/combination eligibility and
target-slot check. FAIL is an independently justified exclusion. PASS alone enters
preference ordering. UNKNOWN remains in a separate canonical option-ID lane.

The synthetic ranked declaration uses policy and ranker version
`synthetic-fixed-combination-rank.v1`; each independently hard-eligible ID appears
exactly once with a strict finite integer priority in 0–1,000,000. Ordering is
`(priority, option_id)`. The explicit `CANONICAL_OPTION_ID` declaration requires
ranker version `canonical-option-id.v1` and all priorities zero. Missing or invalid
rankings never enable fallback. Unsupported versions/scores/foreign fields reject.

The read-only eligibility digest binds the domain digest and complete PASS set.
It is independently recomputed before use. This additive property leaves the
historical ranking declaration wire/digest unchanged.

The selector uses FIRST_VALID_IN_ELIGIBLE_ORDER. It visits PASS candidates in the
declared order, then retained UNKNOWN candidates in canonical order if needed.
Every visit uses complete B1 semantics. A known downstream DAY/WEEK failure may
refute an UNKNOWN prerequisite. Exhaustion with an unrefuted UNKNOWN returns
INSUFFICIENT_DATA; complete known exclusions/no-ops return DOMAIN REJECTED. The
empty authoritative domain returns EMPTY_DOMAIN. Common lock or observed invalid
baseline failures are OPERATION scoped and do not claim exhaustive domain search.
An early VALID has an explicit unvisited suffix and never claims global optimality
or exhaustive rejection. It does not claim other UNKNOWN options would fail.

## Independent proof and final validation

Computed result/certificate tokens and proof policy are disjoint from declaration,
B1 and weekly certificates: `computed-swap-selection-result.v1`,
`computed-swap-selection-certificate.v1`, and
`synthetic-bounded-swap-selection-full-replay.v1`.

The checker rebuilds hard eligibility, ranking, both lanes, evaluated prefix,
suffix, dispositions, selected reference, termination and costs. Every original
option has exactly one check/disposition; visited and unvisited references form
the exact candidate partition. Typed coverage alone is not semantic proof.
Rehashed, transplanted, missing, duplicated, altered or overlapping evidence is
compared with independent reconstruction.

The independent checker never invokes selection, B1 execution or its phase
executor. It reuses only strict admission, deterministic cost definitions and
stateless predicate primitives. B1's existing independent traversal was extracted
mechanically into a private reconstruction function; its existing public checker
still invokes that traversal at the same point. The selection checker reconstructs
transient B1 visit claims independently and checks their complete ordered wire
digests. It uses the B1 independent checker again on the retained final evidence.

Before selection acceptance, a second fresh B1 validation and its own checker run
against the same complete authority. Capacity for that final call is reserved
before beginning a PASS candidate. The final B1 certificate and outer resulting
plan are retained once; every other visit retains a compact verdict/digest/size
record and is reconstructed during independent verification. No retained PASS or
global cache substitutes for this work. The exact 20 original slot payloads remain
unchanged, including provenance. Expiry or unfinished verification withholds the
selected option and plan.

## Versioned resource policy

`synthetic-bounded-swap-ledger.v1` counts logical work units, not CPU instructions
or measured RAM. Let E/V be B1's independently derivable execution/checking vectors,
R its flat operation-record count, C the swap candidate count, O the swap source
option count, C0 original candidate count, L explicit locks, M bridge mappings,
K an option's component count, and P/Q mandatory PROFILE+RECIPE/COMBINATION rules.

| Outer operation | Execution work | Independent verification work | Record / invocation reservation |
|---|---|---|---|
| HEADER | source items 23+C+O+C0; bridge M; lock comparisons 21+L | same plus one checker step | 1 / 0 |
| HARD_CHECK per original | source K; candidate preparations C; combination preparations 1; predicates C×P+Q; domain visits 1 | same plus one checker step | 1 / 0 |
| ORDER | ordering items = number of PASS alternatives | same plus one checker step | 1 / 0 |
| VISIT / FINAL | E+V, including nested B1 checking | V plus one outer checker step | 1+R / 1 |
| ENCODE | source items 1 | same plus one checker step | 1 / 0 |

Each reserved vector is execution plus verification. All nested predicate,
preparation, original/result 21/7/1 assessment, validation and checker work is
cumulative. Each B1 invocation receives its exact allocated E+V work and R record
share. Selection never resets the caller's global work, record, domain or
invocation counters per alternative. Partial interrupted nested work is reported
as actual work, not its unused reservation. Domain visits count original prechecks;
completed candidate validations and final calls have separate invocation counts.

The hard caps remain 50 original visits, 51 validation invocations, 1,024 logical
flat proof records, 1,000,000 units in each reserved work dimension, and 1 MiB each
for certificate/result encoding. The complete input also remains bounded to 1 MiB.
The record total conservatively includes nested B1 records reconstructed during
replay, even though visit evidence is compact. Therefore admitting 50 alternatives
does not promise that 50 full B1 calls fit a given record/work/encoding capacity.

As in B1, each proof/result pool reserves the full 1 MiB ceiling before producing
evidence; a smaller pool gives conservative TIMEOUT. Sequential transient B1
encoding uses that bounded capacity; bytes describe encoded object capacity,
not cumulative bytes ever serialized or peak Python memory. Work and record counts
remain cumulative. Actual outer certificate bytes are in `proof_bytes`; full
result bytes are `len(result.model_dump_json(by_alias=True).encode())`, and visit
notes report transient B1 sizes. Memory profiling is deferred to Phase 7.4.

Representative complete captures are retained as `sample-valid.json` and
`sample-empty.json`; `sample-sizes-and-work.json` records their SHA-256 hashes,
all work dimensions and sizes:

| Capture | Certificate bytes | Full result bytes | Reserved records | B1 invocations |
|---|---:|---:|---:|---:|
| First VALID, one alternative | 343,323 | 919,614 | 134 | 2 |
| Empty authoritative domain | 3,175 | 6,644 | 3 | 0 |

Both reserve 1,048,576 bytes in each encoding pool. The VALID example charges
execution/verification source work 645/337, predicate work 162/82, DAY work 56/28,
WEEK work 8/4, and checker steps 128/134. Its `full_validations` work vector is
4/2 because nested checkers also perform full validation work; the separate
protocol invocation count is two, not six. These captures are correctness/size
examples, not a comparative benchmark or memory measurement.

Cooperative finite monotonic checkpoints bracket semantic work and final checking;
they are not a wall-clock interruption guarantee. Exact root reconstructed output
overflow becomes incomplete RESERVATION; mixed/unrelated validation errors retain
their original failure. Minimum TIMEOUT control metadata carries no accepted
witness and is not a successful uncharged proof.

## Verification evidence

Evidence is preserved under `.delta/phase73c/` alongside all earlier Phase 7 data.
The final 112 collected selection test IDs reconcile to 112 unique passing cases,
zero missing/extra cases, zero unresolved failures and zero skips. This is a
reconciliation of focused runs, not a claim of one uninterrupted 112-case green run.
`test-reconciliation.json` records the per-case XML source and corrected failures.

| Verification | Actual result | Evidence |
|---|---|---|
| B2 core selection/oracle/security/resource run | 69 passed; one incorrect ranking-transplant fixture corrected and its exact case rerun passed | `selection-core.xml`, `ranking-transplant.xml` |
| Domain/ranking/lock/clock boundaries | 30 passed; oversized 50-option fixture corrected and its exact case rerun passed | `boundaries.xml`, `domain50.xml` |
| Added recipe/combination hard facts and exact quantity | 5 passed | `hard-facts.xml` |
| Complete result envelope at limit−1 / limit / limit+1 | 3 passed | `encoding.xml` |
| Separately coherent foreign authority / rehashed claim | 2 passed | `transplants.xml` |
| Noncanonical explicit priority at the maximum integer bound | 1 passed | `priority.xml` |
| Matching-authority mid-replay deadline | 1 passed, superseding the weaker original same-ID test | `interrupted.xml` |
| B1 execution/proofs, 7.3a contracts, workflow policy | 355 passed | `b1-a-policy.xml` |
| Relevant Phase 1–7.2 regression selection | 1,103 passed | `legacy-regressions.xml` |
| Ruff / formatting | Passed; 101 files already formatted | `ruff-final.txt`, `format-final.txt` |
| Pyright | 119 files analyzed; zero errors/warnings | `pyright-final.json` |

The unique total is 1,570 passing cases (112 new + 1,458 existing); repeated
fixture warmups and targeted reruns are not counted twice. The existing regression
selection is retained at `.delta/phase73b_final/regression-selection.txt`.
No new full monorepo run, frontend campaign or comparative benchmark is claimed.

Observed issues and corrections are retained in the development logs. The first
smoke test exposed a mapping passed to the model-only digest helper; B2 now uses
a dedicated canonical mapping digest while existing model digests remain intact.
New fixture conflicts were rejected by the unchanged source/configuration identity
checks. The 50-option fixture was made structurally smaller, without changing its
expected rejection or raising the envelope limit. The initial ranking transplant
test changed only an independently authoritative declaration version, which is
allowed by the existing contract. It now supplies a ranking for a foreign domain;
the expected boundary rejection is unchanged. The separate unsupported ranker
version tests continue to reject. The deadline test now reaches replay with
matching authority and asserts nonzero charged verification work. No predicate,
source policy, expected semantic outcome or safety validation was relaxed.

The literal test oracle enumerates fixed20 plus each alternative using independent
integer/presence arithmetic, and derives costs from source records without calling
production selection, predicate, ordering or cost helpers. Fixtures explicitly
declare fictional fixed presets; they are not a runtime portion generator.
The 50-option exclusion fixture uses concise declarations within the unchanged
admission bound; missing unrelated observations do not override its known slot FAIL.

`source-fingerprints.json` records the eight final Python files;
`preservation-audit.json` compares the 384 preflight captures. All captured files
remain present and only the six approved pre-existing swap files changed. The B1
executor, approved workflow policy, older search modules and prior evidence remain
unchanged. Final Git/doc metadata is retained in `final-git-audit.json`.

## Compatibility and future integration

Four B1 wire/digest captures taken before extraction match byte for byte afterward:
VALID (909,636 bytes), REJECTED (337,205), INSUFFICIENT_DATA (337,261), TIMEOUT (3,454).
The before/after JSON and SHA metadata remain in `.delta/phase73c/b1-*-*`.
Prior workflow-policy implementation, v1 KB equality/digests and Phase 1–7.2
source/benchmark evidence are preserved. Old declaration APIs remain separate
from executable computed results; the contract test that previously asserted
selection APIs absent now asserts their availability and token separation.

Member 1 option IDs, including `<combinationId>:<PRESET>`, remain opaque external
identities. Full FIXED configuration/preparation/quantity and provenance establish
meaning. No identifier parsing supplies trusted facts. A future versioned adapter
must connect these pure APIs to Member 1's existing `substitute_slot` pipeline,
independently load complete saved/reference/lock/permission/domain/ranking/source/
bridge material, and enforce the exact original20 payloads and resource contract.
This package neither modifies nor duplicates that pipeline. Member 1 already owns
fixed preset generation. Real catalogue nutrient vectors cannot enter as synthetic
measured facts. Ingredient/allergen facts remain UNKNOWN without complete reviewed
canonical mappings. Clinical rules, real nutrition targets and source admission
remain deferred to Phase 8. Backend persistence/transport remains Member 3's future
adapter responsibility; no main-branch merge or cherry-pick occurred.

## Scope and gate

New files: core `swap_selection.py`, `tests/test_swap_selection.py`, this handoff.
Required extensions: core `planned_swap.py` and independent `swap_proof.py`,
schemas `planned_swap.py` / `swap_proof.py`, independent `tests/swap_oracle.py`,
and the additive API availability assertion in `test_swap_proof_contracts.py`.
The approved KB policy, B1 executor, weekly search, Member 1/3 files and datasets
are outside this phase's edit inventory. No commit, push or PR is part of this task.
The final worktree is `Savora-Phase7`, branch `feature/member2-phase7`, HEAD
`f28c21ef5c5f4f08feace1900b6f560dab262c67`. The index remains empty. There are
23 dirty paths: the original 20 preserved Phase 7.3b/policy/planning paths plus
the three new B2 files. The master plan remains untracked. Tracked Git whitespace
and explicit dirty tracked/untracked whitespace checks pass.

Exact B2 edit inventory (six extensions, three new files):

- `apps/ai_system/src/savora_ai/core/reasoning/planned_swap.py`
- `apps/ai_system/src/savora_ai/core/reasoning/swap_proof.py`
- `apps/ai_system/src/savora_ai/core/reasoning/swap_selection.py` (new)
- `apps/ai_system/src/savora_ai/schemas/planned_swap.py`
- `apps/ai_system/src/savora_ai/schemas/swap_proof.py`
- `apps/ai_system/tests/swap_oracle.py`
- `apps/ai_system/tests/test_swap_proof_contracts.py`
- `apps/ai_system/tests/test_swap_selection.py` (new)
- `docs/member2_phase73c_swap_selection.md` (new)

The B2→Phase 7.4 correctness gate passes. Phase 7.4 evaluation and any future
Member 1/3 adapter require their own tasks. No commit, push, PR, history change,
dataset mutation or other-worktree change occurred.
