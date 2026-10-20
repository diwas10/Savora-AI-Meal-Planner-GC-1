# Phase 7.2e: deterministic ordering and static original-domain MRV

Owner: Member 2 reasoning; synthetic Python only. Branch
`feature/member2-phase7`, HEAD `09b7dd19e1e698e723f9cce012712483842ef70b`.
The existing seven tracked modifications and four untracked Phase 7.2d files were
retained. Their initial Python hashes match `.delta/phase72d/source-hashes.json`;
the preflight status and hashes are saved in `.delta/phase72e/initial-*`.
No branch/worktree/history/index change, dependency, dataset, teammate, backend,
frontend, database or swap work belongs to this phase.

## Proof feasibility established before traversal changes

The existing v2 declaration schema already separates `depth` from explicit
canonical slot/day/meal identity and preserves original option references and
indices. It rejects duplicate selected slots, false depths, invalid domain indices,
and a DAY failure lacking its three actual slots. This representation is adequate
for arbitrary static variable order. Its chronological execution/checker coverage
arithmetic was not adequate: it inferred slot identities and mixed-radix positions
from depth, and generated only an ascending chronological suffix.

The additive contract first introduces distinct static-original-domain strategy
tokens, a `STATIC_MRV_ORIGINAL_DOMAINS` variable-order literal, ordered proof and
accounting policy tokens, and computed-result allowlisting. Seven contract checks
passed before any traversal changes (`contract-first.xml`). No new default field
is introduced into old events or counters. Existing serialization and default
chronological/incremental/forward accounting remain intact. The earlier ambiguous
`synthetic-mrv-weekly-search.v2` declaration remains nonexecutable.

## Explicit executable combinations

| Policy enum | Variables | Values | Forward | Incremental |
|---|---|---|---|---|
| CHRONOLOGICAL (existing) | Canonical | Ascending option ID | No | No |
| FORWARD_CHECKING (existing) | Canonical | Ascending option ID | Yes | No |
| INCREMENTAL (existing) | Canonical | Ascending option ID | No | Yes |
| INCREMENTAL_FORWARD_CHECKING (existing) | Canonical | Ascending option ID | Yes | Yes |
| REVERSE_VALUES | Canonical | Descending option ID | No | No |
| STATIC_MRV | Original domain size, canonical tie | Ascending option ID | No | No |
| STATIC_MRV_FORWARD_CHECKING | Same static MRV | Ascending option ID | Yes | No |
| STATIC_MRV_INCREMENTAL | Same static MRV | Ascending option ID | No | Yes |
| STATIC_MRV_INCREMENTAL_FORWARD_CHECKING | Same static MRV | Ascending option ID | Yes | Yes |

Policies and their exact literal combinations are allowlisted. Preparation reuse
is independently enabled/disabled, including zero/one request-local cache capacity.
There is no silent strategy fallback. Reverse+MRV, reverse+forward/incremental,
dynamic MRV, degree, LCV and Transformer ordering are unsupported.

Static MRV uses complete ORIGINAL validated domain cardinalities, before eligibility
assessment can remove anything. Sorting `(cardinality, canonical_index)` once is
equivalent to selecting the smallest original domain among the unassigned slots
at each decision. Empty original domains retain their original meaning. Forward
checking only closes a whole partial-assignment subtree; it produces no reduced
per-variable domains. Therefore it supplies no safe dynamic-MRV input. Dynamic
MRV is deliberately deferred rather than manufacturing reductions.

## Independent proof and complete frontier

New execution requires `synthetic-weekly-ordered-coverage.v2`; old execution requires
its existing declaration coverage policy. The checker rejects mismatched tokens.
Each path still carries explicit actual slots and unchanged original option indices.
The retained original domain inventory stays canonical and complete. Only the
private traversal view is permuted.

For ordered proofs, a deterministic permutation of variables and a bijection of
value indices define traversal coordinates over the same original Cartesian
product. Reverse maps original index `p` to rank `size-1-p`; ascending uses `p`.
Each terminal prefix denotes an interval in those traversal coordinates. Terminal
intervals followed by the unexplored suffix must have exactly adjacent endpoints,
positive widths, and cover the entire product once. Alternative slices retain
ascending ORIGINAL indices even when the traversal rank is reversed. Their rank
intervals are independently reconstructed with the correct endpoints.

Maximum-domain review found that an existing dotted branch ID could exceed the
128-character field ceiling while reserving a scope with 50 alternatives. Only
IDs that previously overflowed now use an exact one-character-per-index suffix
with a distinct `a:` marker. No alternative is truncated, no hash replaces its
identity, and every previously valid ID/wire representation remains unchanged.
Maximum 50-option/depth-20 declaration/envelope probes verify this correction.

The checker derives variable order separately from retained original cardinalities
and canonical ties. It imports no execution ordering helper, calls no optimized
solver and constructs no incremental state. Its separate task stack reconstructs
option order, actual selected-slot identities, known unary/DAY failures, full leaves,
all mandatory DAY/WEEK obligations, unknowns, pruning, budgets and interruption.
It compares complete events/accounting with independently recomputed expectations.
It checks the suffix encoder again using independent interval algebra; tests also
enumerate the original Cartesian product and count every frontier membership.
Wrong selection, omitted/duplicated coverage, rehashed false digests, cross-strategy
relabeling, and source or manifest changes cannot gain authority.

Source/request/context/profile/KB/configuration/measurement pins and full manifests
are rebuilt as before. External verification compares independently selected
material. Unsigned hashes bind integrity relative to that material; they do not
authenticate source providers.

## Actual DAY completion and incremental compatibility

A selection triggers a DAY assessment exactly when it completes that actual day's
three canonical slots. It need not occur at a multiple of three traversal depth.
The DAY trial is reconstructed in canonical meal order; DAY records are retained
across later selections and restored with the existing immutable recursive state.
At 21 assigned slots, WEEK receives canonical trial choices and canonically ordered
DAY records, including days completed in another order. Earlier DAY assessments
are neither omitted nor spuriously repeated. WEEK is never assessed on a partial
assignment.

Incremental state continues to bind canonical ORIGINAL domains. Its private path
binding now accepts a permutation of those exact original domain objects, verifies
all 21 identities, and compares sorted actual selected slot/reference pairs. Push
already used actual slot identities and immutable actual-day/WEEK accumulators.
Existing LIFO tokens, prepaid rollback, `finally` restoration and exact empty-root
check remain mandatory. The checker always uses full source arithmetic/evidence.
Known FAIL dominates unrelated UNKNOWN. Missing/incomplete observations are never
zero, and unknown applicability/required facts cannot prune. Evidenced N/A retains
the established semantics. No clinical or production nutrition claim is added.

## Work, resources and reproducibility

New policies require `synthetic-weekly-ordered-work-reservation.v2`. Before ordering,
execution reserves `21 + sum(original domain cardinalities)` heuristic units, plus
matching verification units and one checker step. This is a fixed semantic input
visit charge, not a claim about comparison counts or CPU instructions. Static
ordering is prepared once; there is no dynamic domain scoring work. Existing
preparation, nodes, predicates, DAY/WEEK, forward attempts and incremental state/
extraction charges are additionally preserved. Existing policies keep their old
accounting tokens and operations unchanged.

Proof storage is reserved before record-producing work, including unsuccessful
forward attempts. Exhaustion of any required work/proof/node capacity returns
TIMEOUT; an unfinished checker withdraws the witness. Exact limits, one-short
limits and cooperative execution/verification deadlines are checked independently.
Input validation still precedes budgets. A first witness can differ across
strategies, and equal resource limits can produce different TIMEOUT behavior.

`evals/ordering_benchmarks.py` compares all nine explicit strategies on the same
fixtures and limits. It validates outcomes and witnesses using the independent
literal oracle. It records outcome/witness digest, nodes/backtracks/leaves, DAY/
WEEK work, forward attempts, original-domain ordering work, execution/verification/
reserved work, encoded/reserved proof bytes and records, preparation/search/checker/
total times, resources and runtime environment. Ordering time is included in the
preparation stage because it precedes ordinary preparation. Imports/fixture
construction are excluded. Preparation reuse modes are explicit. Trial order
alternates across repetitions. A separate traced memory probe is excluded from ordinary timing medians.

## Final verification and handoff

Exact workspace inventory (nine tracked modifications and eight untracked files):

| Path | Workspace status | Phase 7.2e action |
|---|---|---|
| `apps/ai_system/src/savora_ai/core/reasoning/day_checks.py` | Modified | Preserve 7.2d bytes |
| `apps/ai_system/src/savora_ai/core/reasoning/week_checks.py` | Modified | Preserve 7.2d bytes |
| `apps/ai_system/src/savora_ai/core/reasoning/weekly_bounds.py` | Modified | Bind bounds/scans to actual canonical slots |
| `apps/ai_system/src/savora_ai/core/reasoning/weekly_proof_v2.py` | Modified | Ordered coverage/checker, actual DAY/WEEK adapters, bounded scope IDs |
| `apps/ai_system/src/savora_ai/core/reasoning/weekly_search_v2.py` | Modified | Explicit ordering execution and reservations |
| `apps/ai_system/src/savora_ai/schemas/weekly_search_v2.py` | Modified | Additive strategy/proof/accounting literals |
| `apps/ai_system/src/savora_ai/schemas/weekly_solver_v2.py` | Modified | Add executable result policy allowlist |
| `apps/ai_system/tests/test_weekly_search_v2_contracts.py` | Modified | Extend all-policy declaration fixture |
| `apps/ai_system/tests/test_weekly_solver_v2.py` | Modified | Reverse is executable; retain unsupported MRV rejection |
| `apps/ai_system/src/savora_ai/core/reasoning/weekly_incremental.py` | Untracked from 7.2d | Bind reordered paths to exact original objects |
| `apps/ai_system/src/savora_ai/core/reasoning/weekly_ordering.py` | New | Execution ordering and semantic cost |
| `apps/ai_system/src/savora_ai/evals/incremental_benchmarks.py` | Untracked from 7.2d | Preserve 7.2d bytes |
| `apps/ai_system/src/savora_ai/evals/ordering_benchmarks.py` | New | Nine-strategy same-input benchmark |
| `apps/ai_system/tests/test_weekly_incremental.py` | Untracked from 7.2d | Preserve 7.2d bytes |
| `apps/ai_system/tests/test_weekly_ordering.py` | New | Ordering/oracle/resource/adversarial tests |
| `docs/member2_phase72d_incremental_evaluation.md` | Untracked from 7.2d | Preserve 7.2d bytes |
| `docs/member2_phase72e_ordering_and_mrv.md` | New | This analysis and final handoff |

### Passing final verification evidence

**229 new ordering cases pass**, with no failures/errors/skips in the final
evidence: 222 cases in 1,204.93s (`final-ordering.xml`) plus seven disjoint final
multi-witness/evidence-equivalence cases in 86.37s
(`final-additional-ordering.xml`). Collection confirms all 229 current cases
appear exactly once across those two batches. Durations include concurrent test
workloads and are not benchmark timings.

**1,246 relevant earlier-phase regression cases have passing final evidence.**
The initial combined regression run had 1,245 passes and one failure in 1,940.86s:
an existing two-argument chronological suffix test double rejected the newly
supplied keyword. The original call form was restored without changing that
test's assertion. The complete 90-case v2 proof suite then passed afresh in
313.12s (`final-proof-regressions.xml`). It fully supersedes all 90 initial v2
proof cases. The other 1,156 passing combined cases are retained; the batches are
not added together as if the repeated 90 cases were distinct. No unresolved test
failure is accepted.

| Required suite | Distinct passing cases in final evidence |
|---|---:|
| Phase 7.2d incremental | 75 |
| Phase 7.2c bounds/forward checking | 116 |
| Preparation reuse | 60 |
| Original v2 solver/proof (fresh complete rerun) | 90 |
| v2 declaration contracts, including additive policies | 121 |
| Phase 7.1 benchmarks/oracles | 176 |
| Weekly v1 solver | 66 |
| Weekly evaluation | 62 |
| Weekly contracts | 164 |
| Phase 6 integration | 21 |
| Daily solver | 106 |
| Daily contracts | 150 |
| Phase 5 integration | 39 |

Total final distinct coverage is **1,475 passing cases**, without failures,
errors or skips in the selected final batches. The machine audit script
`.delta/phase72e/summarize_verification.py` checks the full replacement suite's
case identities, disjoint new batches and exact current collection.
`verification-summary.json` records the accounting; `regressions.xml` deliberately
retains the initial failed development evidence. Early fixture-development and
subset runs are excluded from the final distinct count. The permutation test was
corrected to compare canonical decisions/evidence while preserving supplied input
tuple order; the reverse-suffix attack uses a fixture that actually leaves a suffix.

Ruff lint passes for `apps`; formatting passes for all 104 Python files there.
Pyright passes with **0 errors, 0 warnings, 0 informations**, using the existing
shared Python environment and this worktree's AI/backend source paths. The absent
configured local `.venv` message is informational. No dependencies were installed.
Tracked and all eight untracked Git whitespace checks pass. AST comparison against
HEAD confirms the two original DAY/WEEK entry points and three public v2 functions
retain their signatures (`api-signatures.json`). Four preserved Phase 7.2d Python
files retain their exact initial hashes. All 15 changed/new Python paths have
fingerprints in `.delta/phase72e/source-hashes.json`.

The complete Python monorepo rerun is **deferred to the Phase 7.2 release checkpoint
or Phase 7.5**, as explicitly authorized in this task. The Phase 7.2d full-suite
result remains historical evidence, not a fresh 7.2e claim. Frontend checks were
not run because no frontend, shared TypeScript or HTTP contract changed.

## Repeated benchmark findings

Executed **270 untraced runs**: five fixtures, nine strategies, two preparation
reuse modes and three repetitions per group (90 groups). The initial 216 runs
cover `single`, `late`, `day-pruning` and `unknown-measurement`. A separate 54-run
`early` batch checks the opposite value-order direction after the resource/memory
probes finished. All ordinary runs are sequential, after agent-started tests have
finished; traced probes never overlap them. Strategy and reuse order alternate
between repetitions. No repetitions or outliers are discarded.

Runtime: Python 3.14.7, Windows 11 build 26300. Tested implementation fingerprints
are unchanged across measurement. Raw records: `.delta/phase72e/adequate.jsonl`
and `early.jsonl`; complete grouped medians/ranges, work, proof reservations and
limits: `benchmark-summary.json`. The audit asserts identical fixture digests and
limits, three records per strategy/reuse group, stable deterministic counters,
outcomes/witnesses/proof sizes, and complete independent checking in every run.
These five fixtures have unique feasible witnesses where feasible; the separate
multiple-witness test establishes permitted first-witness changes.

Imports, fixture construction, the comparison oracle and after-return reporting
are outside the solver timer. Source admission, certificate construction/validation
and mandatory independent proof checking are inside it. Preparation includes fixed
ordering setup; incremental state initialization remains search work. Total includes
validation/encoding between the named stage markers. Stage medians are separate
statistics and must not be added as if they were the median of a sum. Timings are
seconds and describe a small local pilot, subject to ordinary desktop variability.

With reuse enabled:

- On `late`, static MRV reduces nodes **138 -> 32** and DAY evaluations **46 -> 18**;
  leaves/WEEK evaluations remain eight. Median total changes
  **9.2238s -> 7.4889s**
  (18.8% lower).
  This is an observed fixture-specific reduction, not a universal latency guarantee.
- On `day-pruning`, static MRV reduces nodes **67 -> 30**, but proof bytes grow
  **233,426 -> 253,265**. Median total is
  **6.5707s -> 6.0598s**.
- Combining MRV with forward checking is slower than chronological forward checking
  here: `late` **5.3207s -> 5.9129s**,
  and `day-pruning` **3.5066s -> 4.7802s**.
  In `late`, both visit 24 nodes, but MRV performs two WEEK leaves/10 DAY evaluations
  instead of one/seven, with larger proof records. In `day-pruning`, postponing the
  larger domains delays conflicting DAY choices: 22 nodes/44 forward attempts
  replace four nodes/nine attempts. Equal node counts alone do not establish a win.
- Reverse demonstrates the expected directional tradeoff: `late` visits 21 nodes
  instead of 138 (median **9.2238s -> 4.8270s**),
  while `early` visits 138 instead of 21
  (median **4.2996s -> 8.2791s**).
  These fixtures place their unique feasible assignment at opposite ends of value order.
- On `early`, static MRV also visits 21 nodes, but its median total is
  **4.4992s**, compared with **4.2996s** chronologically. Ordering adds work even
  when it cannot reduce the search; the measured benefit is workload-dependent.
- Symmetric fixed/unknown-measurement domains give no MRV node reduction. Small timing
  differences there do not establish a heuristic advantage. Incremental variants
  preserve the paired terminal evidence and node counts; they establish no consistent
  additional total-runtime benefit on this pilot. All policies remain explicit opt-ins.

In the tables, `on / off` means preparation reuse enabled / disabled. Ordering
units are the new fixed original-domain preparation charge, not dynamic scoring or
physical CPU comparisons. Full execution/verification work and proof reservations
are retained in raw/grouped JSON for every row.

### single

| Strategy | Nodes / leaves | DAY / WEEK | FC attempts | Ordering units | Proof bytes | Median total on / off |
|---|---:|---:|---:|---:|---:|---:|
| chronological | 21 / 1 | 7 / 1 | 0 | 0 | 82,083 | 4.4642 / 4.7889 |
| forward | 21 / 1 | 7 / 1 | 21 | 0 | 82,159 | 4.7405 / 5.0540 |
| incremental | 21 / 1 | 7 / 1 | 0 | 0 | 82,111 | 4.4562 / 4.8370 |
| incremental-forward | 21 / 1 | 7 / 1 | 21 | 0 | 82,193 | 4.6467 / 5.1893 |
| reverse | 21 / 1 | 7 / 1 | 0 | 42 | 82,102 | 4.4112 / 4.9047 |
| static-mrv | 21 / 1 | 7 / 1 | 0 | 42 | 82,138 | 4.3594 / 4.8015 |
| static-mrv-forward | 21 / 1 | 7 / 1 | 21 | 42 | 82,206 | 4.6895 / 5.0952 |
| static-mrv-incremental | 21 / 1 | 7 / 1 | 0 | 42 | 82,166 | 4.4537 / 4.7765 |
| static-mrv-incremental-forward | 21 / 1 | 7 / 1 | 21 | 42 | 82,230 | 4.6614 / 5.1044 |

### late

| Strategy | Nodes / leaves | DAY / WEEK | FC attempts | Ordering units | Proof bytes | Median total on / off |
|---|---:|---:|---:|---:|---:|---:|
| chronological | 138 / 8 | 46 / 8 | 0 | 0 | 282,919 | 9.2238 / 10.1957 |
| forward | 24 / 1 | 7 / 1 | 24 | 0 | 119,017 | 5.3207 / 6.0145 |
| incremental | 138 / 8 | 46 / 8 | 0 | 0 | 283,052 | 9.2619 / 10.2462 |
| incremental-forward | 24 / 1 | 7 / 1 | 24 | 0 | 119,097 | 5.2366 / 6.1063 |
| reverse | 21 / 1 | 7 / 1 | 0 | 45 | 99,115 | 4.8270 / 5.7529 |
| static-mrv | 32 / 8 | 18 / 8 | 0 | 45 | 283,157 | 7.4889 / 8.4048 |
| static-mrv-forward | 24 / 2 | 10 / 2 | 23 | 45 | 166,000 | 5.9129 / 6.6067 |
| static-mrv-incremental | 32 / 8 | 18 / 8 | 0 | 45 | 283,283 | 7.5248 / 8.1070 |
| static-mrv-incremental-forward | 24 / 2 | 10 / 2 | 23 | 45 | 166,060 | 5.9370 / 6.5565 |

### day-pruning

| Strategy | Nodes / leaves | DAY / WEEK | FC attempts | Ordering units | Proof bytes | Median total on / off |
|---|---:|---:|---:|---:|---:|---:|
| chronological | 67 / 6 | 25 / 6 | 0 | 0 | 233,426 | 6.5707 / 7.1913 |
| forward | 4 / 0 | 0 / 0 | 9 | 0 | 83,917 | 3.5066 / 4.2012 |
| incremental | 67 / 6 | 25 / 6 | 0 | 0 | 233,546 | 6.5047 / 7.2175 |
| incremental-forward | 4 / 0 | 0 / 0 | 9 | 0 | 83,983 | 3.4922 / 4.1627 |
| reverse | 67 / 6 | 25 / 6 | 0 | 45 | 233,512 | 6.5403 / 7.2131 |
| static-mrv | 30 / 6 | 15 / 6 | 0 | 45 | 253,265 | 6.0598 / 6.6667 |
| static-mrv-forward | 22 / 0 | 7 / 0 | 44 | 45 | 135,618 | 4.7802 / 5.4466 |
| static-mrv-incremental | 30 / 6 | 15 / 6 | 0 | 45 | 253,377 | 6.0174 / 6.6887 |
| static-mrv-incremental-forward | 22 / 0 | 7 / 0 | 44 | 45 | 135,670 | 4.7491 / 5.4245 |

### unknown-measurement

| Strategy | Nodes / leaves | DAY / WEEK | FC attempts | Ordering units | Proof bytes | Median total on / off |
|---|---:|---:|---:|---:|---:|---:|
| chronological | 21 / 1 | 7 / 1 | 0 | 0 | 82,189 | 3.6470 / 3.9256 |
| forward | 21 / 1 | 7 / 1 | 21 | 0 | 82,265 | 3.9154 / 4.1719 |
| incremental | 21 / 1 | 7 / 1 | 0 | 0 | 82,217 | 3.6217 / 3.9352 |
| incremental-forward | 21 / 1 | 7 / 1 | 21 | 0 | 82,299 | 3.8526 / 4.3261 |
| reverse | 21 / 1 | 7 / 1 | 0 | 42 | 82,208 | 3.6080 / 3.9622 |
| static-mrv | 21 / 1 | 7 / 1 | 0 | 42 | 82,244 | 3.6392 / 3.9360 |
| static-mrv-forward | 21 / 1 | 7 / 1 | 21 | 42 | 82,312 | 3.8556 / 4.1809 |
| static-mrv-incremental | 21 / 1 | 7 / 1 | 0 | 42 | 82,272 | 3.6509 / 3.9164 |
| static-mrv-incremental-forward | 21 / 1 | 7 / 1 | 21 | 42 | 82,336 | 3.8470 / 4.1799 |

### early

| Strategy | Nodes / leaves | DAY / WEEK | FC attempts | Ordering units | Proof bytes | Median total on / off |
|---|---:|---:|---:|---:|---:|---:|
| chronological | 21 / 1 | 7 / 1 | 0 | 0 | 99,096 | 4.2996 / 5.1576 |
| forward | 21 / 1 | 7 / 1 | 21 | 0 | 99,172 | 4.5861 / 5.2686 |
| incremental | 21 / 1 | 7 / 1 | 0 | 0 | 99,124 | 4.2956 / 4.9490 |
| incremental-forward | 21 / 1 | 7 / 1 | 21 | 0 | 99,206 | 4.5522 / 5.6623 |
| reverse | 138 / 8 | 46 / 8 | 0 | 45 | 283,022 | 8.2791 / 9.4471 |
| static-mrv | 21 / 1 | 7 / 1 | 0 | 45 | 118,749 | 4.4992 / 5.5022 |
| static-mrv-forward | 21 / 1 | 7 / 1 | 21 | 45 | 118,817 | 4.7223 / 5.7800 |
| static-mrv-incremental | 21 / 1 | 7 / 1 | 0 | 45 | 118,777 | 5.1563 / 6.3765 |
| static-mrv-incremental-forward | 21 / 1 | 7 / 1 | 21 | 45 | 118,841 | 6.4593 / 6.4839 |

### Late-case stage medians with preparation reuse

| Strategy | Preparation | Search | Checker | Total range |
|---|---:|---:|---:|---:|
| chronological | 1.5990 | 2.4756 | 4.4727 | 9.1430–9.2868 |
| forward | 1.6211 | 0.7734 | 2.5985 | 5.2292–5.3838 |
| incremental | 1.6289 | 2.5214 | 4.4333 | 9.2476–9.2646 |
| incremental-forward | 1.6095 | 0.7769 | 2.5140 | 5.2211–5.3002 |
| reverse | 1.6123 | 0.5602 | 2.3707 | 4.7734–4.8658 |
| static-mrv | 1.6306 | 1.6631 | 3.5911 | 7.4559–7.5399 |
| static-mrv-forward | 1.5900 | 1.0180 | 2.8349 | 5.8527–5.9142 |
| static-mrv-incremental | 1.6274 | 1.6194 | 3.6002 | 7.4905–7.6645 |
| static-mrv-incremental-forward | 1.6174 | 1.0502 | 2.8687 | 5.8445–6.0729 |


## Equal-resource and memory observations

Separate nine-strategy `late` comparisons (`equal-nodes20.jsonl`,
`equal-heuristic0.jsonl`, `equal-expired.jsonl`; `resource-summary.json`):

- A 20-node cap gives NODE_BUDGET TIMEOUT at exactly 20 nodes in all nine modes,
  with independently verified timeout coverage and no witness.
- Zero heuristic capacity leaves the chronological baseline FEASIBLE at 138 nodes.
  All eight optimization policies return HEURISTIC_BUDGET TIMEOUT with zero nodes;
  new ordered policies stop before ordering/preparation. There is no silent fallback.
- An expired deadline gives DEADLINE TIMEOUT, zero nodes, no witness and incomplete
  verification in every mode. The new suite additionally checks live rollback and
  execution/verifier deadline boundaries, proof/work limits and one-short capacities.

Separate one-call-per-policy `late` traced probe (`memory.jsonl`):

| Strategy | Nodes | Peak Python traced bytes |
|---|---:|---:|
| chronological | 138 | 17,504,064 |
| static-mrv | 32 | 17,352,530 |
| static-mrv-incremental | 32 | 17,317,842 |

The immutable fixture is built before tracing. Peaks include full invocation and
oracle/limit/internal instrumentation setup, including mandatory verification;
they are not RSS or isolated state allocations. Traced timings are excluded from
ordinary comparisons. One small probe cannot establish a memory improvement or
measure the isolated overhead of ordered views/immutable snapshots. Static MRV
performs less work on this fixture; incremental state still adds bounded retained
execution metadata. No memory-saving claim is made.

## A–O completion audit

Resume verification on 2026-10-20 found no active benchmark process and all 54
supplementary records complete. No measurements or expensive tests were repeated.
The local audit (`.delta/phase72e/resume-audit.json`) binds SHA-256 hashes of all
six final raw measurement files (300 records) to the retained 15-file source
snapshot. Every current source hash matches; source modification times precede
that snapshot, and all final measurement files follow it. Four prior Python files
and the Phase 7.2d handoff retain their original bytes. Raw records identify
`phase72e-worktree` but do not embed source hashes; this sidecar establishes local
provenance, not authenticated historical execution. Test XML/collection audits,
five API signatures and Ruff/format/Pyright checks were refreshed without changing
implementation files. All earlier raw and development evidence is preserved.

**A. COMPLETE.** Phase 7.2e implementation, independent proof review, relevant
regressions and repeated measurements are complete within the synthetic scope.

**B. Git and exact inventory.** Branch `feature/member2-phase7`, HEAD
`09b7dd19e1e698e723f9cce012712483842ef70b`; nine tracked modifications and eight
untracked files exactly match the inventory above. The index is empty. Prior
7.2d work is retained. Supporting ignored evidence is inventoried separately in
`.delta/phase72e/artifact-inventory.txt`. No commit, push or branch/worktree/history
mutation occurred.

**C. Implemented.** Reverse chronological value ordering and four explicit static
original-domain MRV variants: full, full+forward, incremental, incremental+forward.
All four earlier policies and defaults remain selectable with unchanged valid wire
encodings/accounting. Preparation reuse and zero/one capacity remain independent.

**D. Deferred/unsupported.** Dynamic MRV has no reduced-domain input from this
whole-subtree forward checker. The legacy ambiguous MRV declaration remains
nonexecutable. Reverse combined with MRV/forward/incremental, degree, LCV and
Transformer ordering are rejected; no fallback is inferred.

**E. Proof/frontier.** Explicit actual slots and original indices are retained.
New ordered coverage binds a variable permutation/value-rank bijection over the
complete original product, including interruption and early success. Independent
interval algebra and literal membership counts verify no gaps/overlaps. The
maximum-domain branch-ID overflow is corrected without changing previously valid IDs.

**F. Checker.** Separately reconstructs order from original sizes/ties, source
material, all mandatory facts/rules, exclusions, coverage, resources and witness.
It calls no optimized traversal/ordering helper and accesses no incremental state.
Hashes do not authenticate sources; external selected-material comparison remains.

**G. DAY/WEEK.** Complete each actual DAY once its three actual slots are assigned;
assemble canonical DAY trials/records and the 21-slot WEEK witness. No obligation
is skipped because traversal depth differs from canonical index.

**H. UNKNOWN/applicability.** Unknown alternatives remain in original domains.
Missing/incomplete facts are never fabricated zero. Known independent FAIL can
dominate unrelated UNKNOWN; unknown dependencies/applicability cannot prune and
evidenced N/A retains the existing rule semantics.

**I. Accounting.** Ordered setup reserves its 21+cardinality-sum heuristic units,
equal checker work and a step before work. Existing preparation, forward,
incremental/push/prepaid rollback, DAY/WEEK, proof bytes/records, node and verifier
charges remain mandatory. Exhaustion/unfinished verification gives TIMEOUT and
withholds the witness; deadlines remain cooperative.

**J. Compatibility.** Exact original-object state binding supports permutations;
immutable LIFO rollback is checked on every exit. Incremental/full terminal
facts/evidence agree under MRV. Forward bounds use full original measurements;
preparation sessions and independent checks stay request-local. v1 APIs/contracts,
HTTP/shared team boundaries and dependency files are unchanged.

**K. Tests.** 229 new plus 1,246 relevant prior cases = **1,475 distinct passes**
with no accepted unresolved failures/skips. Collection/replacement audit and
commands/batch provenance are recorded above and in `verification-summary.json`.
Full monorepo verification is scheduled for the Phase 7.2 release checkpoint or
Phase 7.5; frontend checks are outside the unchanged frontend/HTTP scope.

**L. Benchmarks.** 270 repeated untraced runs, 27 equal-resource observations and
three separate traced probes, with no discarded ordinary runs. Results support
fixture-specific MRV gains and clear combinations/value-order tradeoffs, not a
general speedup or an automatic policy switch. Full data/stage ranges are retained.

**M. Static/Git checks.** Ruff lint/format checks pass (104 Python files under
`apps`); Pyright has zero errors/warnings/informations with the existing explicit
environment/source paths. Tracked/untracked whitespace, empty-index, branch/HEAD,
five retained API signatures and tested/benchmarked source fingerprint checks pass.

**N. Unresolved HIGH/MEDIUM findings: none identified** in the supported scope.
The suffix-call compatibility and maximum-domain ID issues are fixed; development
fixture mistakes are corrected and excluded from final passing counts. Real
clinical/data/provider integration remains an explicit exclusion, not a safety claim.

**O. Ready for Phase 7.3a — Saved-Plan and Swap Contracts.** That next contract
foundation must resolve Member 3 selected saved-plan authority/revision and workflow
bindings, locked slots and transactional/concurrent-write handoff with the team.
This result authorizes no persistence or swap and implements none. Stop here;
no commit, push or PR is created.
