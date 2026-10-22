# Phase 7.2d: incremental synthetic DAY/WEEK evaluation

Owner: Member 2 reasoning. Synthetic scope only. Preflight: clean `Savora-Phase7`,
branch `feature/member2-phase7`, HEAD `09b7dd19e1e698e723f9cce012712483842ef70b`.
The existing user-selected branch is retained. No Git history/branch/worktree
mutation, commit, push, dependency change or teammate edit is authorized here.

## Derivation analysis and boundary

The existing full evaluators distinguish quantity completeness from eligibility:
one whole-meal measurement contributes once per slot, even when eligibility is
UNKNOWN. Quantity exists only when every selected measurement is present, complete
and non-null. DAY has three actual slots; WEEK has 21. Recipe presence counts each
canonical ID once per slot, including across configurations, with duplicates
inside a slot deduplicated. Occurrence completeness requires the original known
candidate-membership, composition-completeness and source-authority prerequisites.
Unrelated safety UNKNOWN does not erase independently known recipe presence.

These arithmetic/completeness calculations are incremental. Required facts,
applicability dependency closure, all mandatory rule evaluations, evidence unions,
measurement contributions, exact source/configuration references, facts, traces
and explanations remain mandatory. Immutable context/profile observations and
applicability information already belong to the admitted request-local programs;
this phase does not introduce a second authority cache or cached rule PASS.

## Explicit policies and compatibility

Two new allowlisted `WeeklyStrategyPolicyV2` policies select chronological,
`OPTION_ID_ASC`, `FIRST_FEASIBLE` execution:

- `synthetic-incremental-weekly-search.v2`: propagation `NONE`.
- `synthetic-incremental-forward-checking-weekly-search.v2`: propagation
  `KNOWN_FAILURE_FORWARD_CHECK`.

The earlier chronological/forward policies retain their fields, default behavior,
serialization and accounting meanings. No default dispatch selects incremental
execution. MRV and reverse ordering remain declaration-only and nonexecutable.
Preparation reuse retains its independent existing optional arguments and fresh
checker session. No public function signature, v1 schema, HTTP or shared team
contract changes. The private DAY/WEEK entry points retain their signatures and
full source derivation; new private evaluation helpers share evidence/rule assembly
with the incremental execution adapters.

## State and rollback

`core/reasoning/weekly_incremental.py::_IncrementalState` is an internal execution
object, not a wire model or public solver argument. It is constructed only after
ordinary source/KB/context/candidate/domain admission and option preparation.
Metadata binds exact original option references, measurements and configuration
identities. A slot accepts only a reference in its exact original domain.

Each frozen snapshot contains canonical selected slot/reference pairs, seven DAY
quantity accumulators, a WEEK accumulator, per-recipe slot counts and a count of
slots with unknown occurrence identity. Each quantity accumulator separately keeps
known subtotal, number of unknown contributions and selected-slot count. A partial
or incomplete observation is `(None, False)`, never a fabricated zero total. Python
integers stay exact; meal, DAY, WEEK and per-recipe representation limits apply.

Push computes a complete new immutable snapshot before publication. An internal
LIFO token retains the exact prior and new objects. Pop accepts only the active
token and current snapshot identity, then restores the prior object. There is no
subtractive rollback or mutable aggregate shared between snapshots. Every search
selection has a `finally` rollback, including known failure, early FEASIBLE,
resource/deadline interruption and exceptions. Before proof verification, execution
must have restored the exact root object and empty token stack, then discards state.

The stack has at most 21 frames. Each snapshot holds at most 21 choices, seven DAY
accumulators and the bounded selected recipe inventory. State uses actual canonical
slot identities; unit checks exercise nonchronological additions solely to establish
correct scope completion. No nonchronological search policy is implemented.

## Proof authority and forward checking

Execution supplies only scalar aggregate observations to private evidence/rule
assembly. Every DAY/WEEK evaluation still builds the original facts, contributors,
source references, traces and explanations. Terminal digests include all facts,
including facts not used by a particular predicate.

The independent checker constructs no incremental state, reads no snapshots and
calls no incremental mutation/extraction method. Its task stack continues to call
the full authoritative DAY/WEEK paths and compares complete terminal evidence,
ordered events, accounting and the exact original Cartesian frontier partition.
Incorrect execution arithmetic cannot supply a checked outcome. There is no
incremental-state field, cached-total override, evaluator callback or PASS claim
accepted at the public boundary.

Forward checking retains the complete Phase 7.2c bounds and independent arithmetic
checker. Bounds still scan original domains and source measurements; incremental
partial totals do not supply pruning authority or alter applicability/required-fact
admission. UNKNOWN is not FAIL. Known independent FAIL still dominates unrelated
UNKNOWN. Evidenced NOT_APPLICABLE and unknown dependency behavior remain unchanged.

## Versioned accounting and interruption

New policies require `synthetic-weekly-incremental-work-reservation.v2`. Existing
work fields remain semantic units, not physical call or CPU counters. Only under
this new accounting policy, `heuristic_evaluations` additionally charges:

| Operation | Additional execution units |
|---|---:|
| State initialization | 1 + sum(1 + component occurrences) over distinct referenced options |
| Selection and prepaid rollback | 2 * (1 + selected option component occurrences) |
| DAY aggregate extraction | 1 |
| WEEK aggregate extraction | 1 + component occurrences across all 21 selected slots |

Every new operation also reserves matching independent-verification units and a
checker step before work. The checker derives protocol costs from original source
metadata, never from execution state. The selection reservation prepays rollback
even on success or interruption; it is not refunded. This ensures restoration
does not need new capacity after exhaustion. Mandatory DAY/WEEK/predicate and
preparation charges remain intact. Forward attempts retain their previous costs
in addition to incremental work.

No new work field/default is added to old certificates, so their byte accounting
is preserved. New strategy/accounting tokens bind the new charges. Existing proof
record/byte reservations, complete frontier coverage and zero/exact-budget behavior
remain mandatory. `HEURISTIC_BUDGET` can now stop the new policy's state work.
Incomplete proof or independent verification is TIMEOUT and withholds a witness.
Deadline checkpoints are cooperative, not preemptive interruption guarantees.

## Files and validation plan

Created, relative to `apps/ai_system/` unless `docs/` is specified:

- `src/savora_ai/core/reasoning/weekly_incremental.py`
- `src/savora_ai/evals/incremental_benchmarks.py`
- `tests/test_weekly_incremental.py`
- `docs/member2_phase72d_incremental_evaluation.md` (repository root)

Modified:

- `src/savora_ai/core/reasoning/day_checks.py`
- `src/savora_ai/core/reasoning/week_checks.py`
- `src/savora_ai/core/reasoning/weekly_search_v2.py`
- `src/savora_ai/core/reasoning/weekly_proof_v2.py`
- `src/savora_ai/schemas/weekly_search_v2.py`
- `src/savora_ai/schemas/weekly_solver_v2.py`
- `tests/test_weekly_search_v2_contracts.py` (extend the enumerated policy fixture;
  all existing assertions remain intact)

The new suite checks literal Cartesian outcomes and first witnesses, exact full
terminal evidence equivalence, arbitrary-slot state arithmetic, duplicate/multiple
recipes, complete/incomplete/absent measurements, identity changes, unknown
applicability/requirements, FAIL dominance, evidenced N/A, all preparation modes,
corrupt aggregates/tokens/rollback, hostile wire proof data, resource boundaries,
deadline unwind, deterministic execution and original v1 compatibility. Required
earlier Phase 7 and DAY/WEEK suites are rerun. Actual results follow after execution.

`evals/incremental_benchmarks.py` compares equal problems/limits with paired order
alternation. It reports nodes/leaves, DAY/WEEK calls, full/incremental derivations,
state initialization/push/pop counts, preparation/search/checker/total timing,
proof sizes and optional separate Python traced peaks. Fixture construction and
imports are excluded from timing; state initialization is search work. Independent
verification remains enabled and uses full derivation. No speedup is assumed.

## Verification results

Status: **COMPLETE**. Implementation, regression, proof/security review and paired
runtime verification are complete within the registered synthetic scope.

- Initial focused arithmetic/corruption checks: 12 passed in 89.74s. These are a
  subset of the final new suite, not additional distinct coverage.
- Complete new suite: **75 passed in 694.94s**, exit 0, no skips/failures/errors.
  Evidence: `.delta/phase72d/incremental-tests.xml`. Tests ran concurrently with
  earlier-phase regressions; these durations are not comparative benchmarks.
- Ruff lint and formatting passed; **156 files already formatted**. Pyright:
  **0 errors, 0 warnings, 0 informations**, with explicit existing interpreter
  and this worktree's AI/backend source paths. The absent configured local `.venv`
  notice is informational. No dependencies were installed. Initial development
  lint/type diagnostics were fixed before these passing final checks.
- AST comparison against HEAD confirms unchanged signatures for the two original
  private DAY/WEEK entry points, public proof checker and public v2 solve/verify
  functions. Evidence: `.delta/phase72d/api-signatures.json`. Original v1 solver/
  schema files, backend/frontend, shared contracts and dependency files are unedited.
- All 11 created/modified paths match the inventory. Tracked/untracked whitespace
  checks (accepting Windows CRLF), branch/HEAD and empty-index checks pass.
- Earlier Phase 7, baseline benchmark/oracle and DAY/WEEK regressions:
  **1,168 passed in 2,155.54s**, exit 0, no failures/errors/skips. Evidence:
  `.delta/phase72d/regressions.xml`. This includes the complete forward-checking,
  preparation-reuse, original v2 solver/proof, v2 declarations, baseline benchmark,
  weekly solver/evaluation/contracts, Phase 6 integration, daily solver/contracts
  and Phase 5 integration suites. It is a fresh combined regression run, not a
  sum of historical results.
- Remaining monorepo tests: **3,312 passed, 1 skipped in 191.74s**, exit 0, in a
  disjoint batch excluding the new suite and every required-regression suite.
  The existing Food.com recipe-level export check is skipped because
  `FOODCOM_RAW_RECIPES` is unset. No dataset or dependency was changed to bypass
  that gate. Evidence: `.delta/phase72d/remaining-monorepo.xml`.
- Root collection/JUnit partition verification passed: all **4,556 collected
  cases** are covered exactly once across the three batches: **4,555 passed,
  1 existing dataset-gated skip**, no overlaps/missing cases/failures/errors.
  Evidence: `.delta/phase72d/collection.txt` and `coverage-summary.json`.
  This covers the collected Python monorepo suite in three disjoint invocations;
  it is not claimed to be one monolithic run. Frontend checks were not run because
  no frontend, shared TypeScript or HTTP contract changed.
- Tested implementation fingerprints for all 10 changed/new Python files are
  retained in `.delta/phase72d/source-hashes.json` and match the benchmark source.

## Resource and memory observations

Equal-budget comparisons are saved in `.delta/phase72d/equal-heuristic0.jsonl`,
`equal-nodes20.jsonl` and `equal-expired.jsonl`. Timings from these concurrent
resource runs are excluded from performance claims:

- With zero heuristic capacity, old chronological `early` is FEASIBLE and
  `week-quantity` INFEASIBLE; incremental execution returns HEURISTIC_BUDGET
  TIMEOUT before state initialization/assignment visits.
- With 20 nodes and ample other work capacity, both modes return NODE_BUDGET
  TIMEOUT at 20 nodes for `early`.
- An expired deadline returns DEADLINE TIMEOUT with no witness and incomplete
  verification in both modes. New tests separately cover exact reservation,
  one-short capacity and interruption during live state/verification.

Separate one-pair `late` tracemalloc probe (`.delta/phase72d/memory.jsonl`):
full peak 17,493,052 bytes; incremental peak 17,376,622 bytes. These are full timed-
invocation Python traced peaks after fixture/import construction, not isolated
state allocations or RSS. One probe does not establish a memory improvement;
immutable snapshots add retained execution state despite the slightly lower
observed overall peak. Traced timings are excluded from normal timing medians.

Both memory runs return the same FEASIBLE witness and 138 nodes/8 leaves. Full
execution performs 46 full DAY and 8 full WEEK derivations. Incremental execution
performs 46 incremental DAY and 8 incremental WEEK extractions, one initialization
and 138 pushes/138 pops. Both independent checkers perform all 46 full DAY and 8
full WEEK derivations and construct no incremental state. Proof bytes are
282,919 -> 283,052. Operation counts are named derivation/extraction operations,
not physical integer-addition or CPU-instruction counts.

## Repeated paired runtime findings

Executed after all test/memory processes finished: **36 untraced runs**, three
repetitions per mode for each of six case/forward-policy pairs. Pair order
alternates. Both sides use the same fixtures, adequate limits and fresh request-
local preparation reuse. Every record has complete independent verification, no
termination, and identical paired fixture/outcome/first-witness digests, nodes,
backtracks, leaves and DAY/WEEK evaluation counts. No runs/outliers were discarded.

Environment recorded in raw artifacts: Python 3.14.7, Windows 11 build 26300.
Base HEAD and exact working implementation fingerprints are recorded above.
Artifacts: `.delta/phase72d/adequate.jsonl`, `adequate-forward.jsonl`, `summary.json`.
Full in the tables means nonincremental execution under the SAME forward policy.

| Case | Forward | Nodes / leaves (both) | DAY / WEEK evaluations (both) | Median total seconds, full -> incremental | Encoded proof bytes, full -> incremental |
|---|---|---:|---:|---:|---:|
| early | No | 21 / 1 | 7 / 1 | 4.3081 -> 4.2975 | 99,096 -> 99,124 |
| late | No | 138 / 8 | 46 / 8 | 8.1823 -> 8.1623 | 282,919 -> 283,052 |
| exhaustive | No | 28 / 4 | 10 / 4 | 4.7413 -> 4.7998 | 168,672 -> 168,742 |
| late | Yes | 24 / 1 | 7 / 1 | 4.7391 -> 4.7478 | 119,017 -> 119,097 |
| day-pruning | Yes | 4 / 0 | 0 / 0 | 3.4493 -> 3.5204 | 83,917 -> 83,983 |
| unknown-measurement | Yes | 21 / 1 | 7 / 1 | 3.8231 -> 3.8364 | 82,265 -> 82,299 |

| Case / forward | Median preparation, full -> incremental | Median search, full -> incremental | Median checker, full -> incremental | Total range, full / incremental |
|---|---:|---:|---:|---|
| early / No | 1.4567 -> 1.4190 | 0.5012 -> 0.5006 | 2.1036 -> 2.0991 | 4.2899-4.4177 / 4.2859-4.3301 |
| late / No | 1.4260 -> 1.4250 | 2.2211 -> 2.2218 | 3.9626 -> 3.9344 | 8.1728-8.2319 / 8.1567-8.1700 |
| exhaustive / No | 1.4669 -> 1.4793 | 0.6286 -> 0.6426 | 2.2759 -> 2.2804 | 4.7234-4.7880 / 4.7084-4.8097 |
| late / Yes | 1.4281 -> 1.4374 | 0.7069 -> 0.6935 | 2.3157 -> 2.2857 | 4.6917-4.8479 / 4.7322-4.7484 |
| day-pruning / Yes | 1.4789 -> 1.5062 | 0.0646 -> 0.0634 | 1.6727 -> 1.7013 | 3.4322-3.5062 / 3.4596-3.5722 |
| unknown-measurement / Yes | 1.3338 -> 1.3398 | 0.4089 -> 0.4119 | 1.8515 -> 1.8526 | 3.8130-3.8928 / 3.8070-3.8702 |

Times are seconds. Total also includes certificate/envelope construction and
validation outside the named stage markers. Stage medians are reported separately
and must not be added as though they were the median of a sum.

For each row, incremental execution replaces the listed full DAY/WEEK arithmetic
operations with the same number of incremental aggregate extractions, plus one
state initialization and paired push/pop operations equal to the node count.
Independent verification continues to perform the listed full derivations in
every mode and never initializes incremental state. All rule obligations,
contributors, evidence and explanations remain present. Proof reservations and
execution/verification work counters are retained separately in the raw records.

There is **no established meaningful end-to-end speedup** on this small local
pilot. Total median changes range from approximately 0.25% faster to 2.06% slower;
four of six pairs are slower with incremental execution. Arithmetic savings are
small relative to mandatory evidence/validation/checker work, and state/accounting
overhead remains. There is no node-reduction or memory-improvement claim for this
optimization. This does not establish a general latency guarantee or statistical
advantage. The new policies remain explicit opt-ins.

## Completion audit and next gate

**A. COMPLETE.** No unresolved HIGH/MEDIUM correctness or security defect remains
identified within the supported synthetic scope. Expected rejection of injected
bad state/rollback is a tested defense, not an accepted partial result.

**B-C. Git and scope.** Branch `feature/member2-phase7`, HEAD
`09b7dd19e1e698e723f9cce012712483842ef70b`; seven tracked modifications and four
new files exactly match the inventory above. The index remains empty. Source
fingerprints are unchanged across final tests and benchmarks. No commit, push,
branch/history mutation, other-worktree source change or unrelated edit occurred.

**D-H. State, facts and proof.** Immutable bounded snapshots and active LIFO tokens
restore exact prior state. Supported incremental attributes are
`synthetic_day_quantity_total`, `synthetic_week_quantity_total` and
`synthetic_week_max_recipe_slot_occurrences`, including partial bookkeeping and
numeric/occurrence completeness. Eligibility completeness and all required facts,
applicability, rules and evidence remain fully evaluated. Unknown values remain
unknown. Original source/configuration bindings and known FAIL dominance are
preserved. Independent verification always recomputes authoritative values and
retains the original proof/frontier/resource guarantees. Both preparation modes
and optional forward checking are covered by the completed suites.

**I-K. Verification and measurement.** All 4,556 collected Python cases are covered
exactly once: 4,555 passed and one existing raw-dataset check skipped. New suite:
75 passed; required earlier suites: 1,168 passed; remaining repository: 3,312
passed/one skipped. Ruff lint/format and Pyright pass. Resource outcomes, traced
memory, repeated end-to-end timing, physical derivation/extraction counts and
proof sizes are reported above, with no performance benefit overstated.

**L-N. Compatibility and readiness.** No unresolved HIGH/MEDIUM defect was found.
Legacy public APIs, default behavior and original v1 solver/schema source remain
unchanged. Internal v2 additions are the two explicit strategy tokens, computed
policy acceptance and the versioned incremental accounting semantics. Phase 7.2e
can begin as a separate task using the retained full derivation/oracle baseline;
arbitrary-order search and proof coverage still need their own implementation and
verification. No MRV, LCV, degree heuristic, meal swap, clinical/real-nutrition,
backend/frontend/database, Member 1/3 or dataset change is included here.
