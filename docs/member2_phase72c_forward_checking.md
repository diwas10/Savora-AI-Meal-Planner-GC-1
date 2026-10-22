# Phase 7.2c: sound synthetic forward checking

## Design recorded before implementation

Owner: Member 2 AI reasoning. The selected v2 policy is
`synthetic-forward-checking-weekly-search.v2`; chronological v2 and Phase 6 v1
remain selectable without propagation. No ordering, incremental facts or swaps.

The first and only supported family is exact integer summation for
`synthetic_day_quantity_total` (three slots, mg) and
`synthetic_week_quantity_total` (21 slots, mg). These share the same theorem.
Repetition and boolean completeness predicates remain full-evaluation-only.

For each selected slot use its exact admitted fixed-meal measurement. For each
unassigned slot use the minimum and maximum over its entire ORIGINAL domain,
including options with unknown or failing eligibility. All contributions in the
relevant scope must exist, be complete and non-null. Sum minima into L and maxima
into U. Integer arithmetic is exact. Every completion's total lies in [L,U], even
though not every integer inside the interval need be attainable.

An applicable rule with threshold t is necessarily false only when:
LT: L >= t; LE: L > t; GT: U <= t; GE: U < t;
EQ: t < L or t > U; NE: L == U == t.
An interior discrete gap is not a pruning proof.

Admission must establish the exact registered attribute, scope, operator, integer
threshold and mg unit. Applicability must be APPLICABLE with its dependency
evidence. Every additional required fact must be a complete, non-null original
context/profile observation; derived completeness dependencies are unsupported.
No missing measurement becomes zero. Unknown eligibility does not prevent a
separately known numeric FAIL from dominating UNKNOWN, matching full derivation.
UNKNOWN applicability or required facts prevent this bound from closing a branch.

Each closure binds the rule, applicability evidence, required observations,
partial assignment, bound endpoints and all original remaining domain indexes.
Original request/source/KB/context/candidate bindings stay in the certificate.
The independent checker reconstructs prerequisites and interval arithmetic from
its own admitted inputs, not execution preparation or asserted bounds, then
checks the original Cartesian-space interval partition.

Each attempted rule bound reserves one potential proof record and conservative
bytes BEFORE scanning measurements, plus predicate/heuristic units and equal
checker work. Unused tentative record/byte capacity is released on a nonclosure;
completed semantic work is never refunded. Proof capacity exhaustion is TIMEOUT,
including for a potentially nonpruning attempt. Cooperative deadline checkpoints
precede each operation. This policy's effort is explicitly charged; it is not
the zero-heuristic chronological baseline.

## Execution and verification contract

Select `WeeklySearchStrategyV2` with policy
`synthetic-forward-checking-weekly-search.v2`, variable order `CHRONOLOGICAL`,
value order `OPTION_ID_ASC` and propagation `KNOWN_FAILURE_FORWARD_CHECK`.
The strategy DTO remains a declaration; only `ComputedWeeklySolveResultV2` grants
checked outcome authority. MRV and reverse ordering are still rejected by runtime.

At each unfinished prefix (including the root), attempt the current DAY's numeric
rules, then WEEK numeric rules, in manifest order. All original alternatives stay
in each interval; no domain filtering, variable/value ordering, incremental totals,
memoization or rollback-derived facts are introduced. DAY completion and full
21-slot witness verification still use the existing complete evaluators.

The forward accounting policy is
`synthetic-weekly-forward-work-reservation.v2`. A rule attempt costs one predicate
obligation and `1 + measurement_occurrences + required_facts` heuristic units.
Selected scope slots contribute one occurrence; unassigned scope slots contribute
their full original-domain lengths. These are conservative logical scan
obligations even if missing information stops arithmetic early. Execution reserves
the same cost for the independent checker, plus a checker operation step.

Before scanning, a temporary closure slot and conservative byte charge must fit.
On nonclosure only unused storage is released. Final proof reservation counters
describe committed records plus the certificate/frontier envelope, not cumulative
temporary allocations or RSS. The independent checker repeats these capacity
decisions and releases; snapshots across emitted records remain cumulative.
No bound attempt is free because it failed to prune. Zero/exhausted heuristic,
predicate, proof, node or verifier capacity preserves conservative TIMEOUT.

`WeeklyNumericBoundV2` uses `synthetic-exact-quantity-interval.v2`; closure events
retain the existing `synthetic-forward-check-closure.v2` declaration token.
The bound digest encodes the typed bound's canonical JSON, including its policy.
Neither that digest nor the asserted endpoints are trusted. `_check_bound` reads
original retained measurements and computes extrema and possible-comparison
conditions separately from execution's `_derive_bound` / `_impossible` helpers.
It does not call the recursive executor. The checker retains its explicit task
stack and independently verifies disjoint mixed-radix coverage against all original
domains, including unexplored suffixes on TIMEOUT or first FEASIBLE.

Preparation reuse is optional and independent of propagation. The checker creates
its own fresh recipe session; bounds take no caller-prepared assessment or
measurement cache. Changed execution measurement maps are rejected by verification.
Strict original-JSON ingress, complete manifests and source/context/KB/candidate
binding remain mandatory. Unsigned self-consistency does not authenticate sources;
orchestration must independently select original source records, as before.

## Task file inventory and compatibility

Created (code paths relative to `apps/ai_system`):

- `src/savora_ai/core/reasoning/weekly_bounds.py`
- `src/savora_ai/evals/forward_benchmarks.py`
- `tests/test_weekly_bounds.py`
- `docs/member2_phase72c_forward_checking.md` (repository root)

Modified:

- `src/savora_ai/core/reasoning/weekly_search_v2.py`
- `src/savora_ai/core/reasoning/weekly_proof_v2.py`
- `src/savora_ai/schemas/weekly_search_v2.py`
- `src/savora_ai/schemas/weekly_solver_v2.py`
- `tests/test_weekly_solver_v2.py`

The existing unsupported-strategy test now covers the two still-future policies;
forward checking is tested as executable by the new independent suite. No other
existing test was changed. Thirteen other preexisting Phase 7/preparation files,
including the public combination refactor, match preflight SHA-256 fingerprints.
All Phase 1-6 source files remain unchanged in this task. No backend/frontend,
dependencies, shared contracts or Member 1/3 changes. No Git mutation or commit.

## Verification and measurement results

Fresh combined Phase 3 filtering, Phase 4 combination evaluation, Phase 6 weekly
solver and integration run: **270 passed in 306.58s**. This explicitly includes
`test_weekly_solver.py::test_shared_preparation_counts_do_not_scale_with_leaves`.
It is a single fresh combined run, not a union of prior isolated passes.

Clean final forward-checking suite: **116 passed in 226.32s**. Includes all six
numeric operators for DAY/WEEK through full public/proof admission; literal
interval and discrete-gap tables; per-prune Cartesian completion enumeration;
complete oracle outcomes/first witnesses; partial and missing measurements;
unknown applicability/dependencies/additional prerequisites; evidenced N/A;
known failure dominating UNKNOWN; repetition/configuration identity regressions;
fresh zero/one-capacity preparation; exact/one-short reservations; execution and
verification deadlines; forged endpoints/rules/evidence/domains/indices/frontier/
work; event ordering/omission; rehashed certificates and transplantation;
corrupted execution arithmetic and measurement maps; strict original-JSON ingress.

During development several new test fixture constructors were corrected, and
adversarial tests were strengthened to use original JSON rather than fail at
Python-mode string-enum admission. Selected altered certificates must first pass
declaration validation; their typed bound digest is recomputed before the
independent computed boundary rejects them. Existing validators were not relaxed.

Existing Phase 7.2a solver/proof, Phase 7.2b preparation reuse, Phase 7.1c strict
declarations and Phase 7.1b benchmark/oracle tests: **442 passed in 670.68s** in
one combined run. Together with 116 new and 270 shared regressions, the required
verification groups pass; the existing baseline benchmark tests are included.

Final Ruff lint/format passed (152 Python files already formatted); Pyright:
0 errors, 0 warnings, 0 informations. Tooling uses the preexisting shared virtual
environment with PYTHONPATH bound to this worktree; no packages installed or
other-worktree sources changed. Root `.venv` absence is an informational notice.
Scoped whitespace checks and empty-index checks passed. Full monorepo pytest is
deferred in favor of the required focused/shared regressions.

Equal-budget observations (timings excluded because tests ran concurrently):

- With heuristic capacity zero, chronological `early` is FEASIBLE and
  `week-quantity` INFEASIBLE; forward checking returns HEURISTIC_BUDGET TIMEOUT
  for both. Propagation has an explicit cost.
- With 20 nodes and adequate other resources, both strategies TIMEOUT for
  `early`; for `week-quantity`, baseline TIMEOUT versus verified forward INFEASIBLE
  at zero nodes.
- An already expired deadline returns DEADLINE TIMEOUT for both cases/modes.

Artifacts: `.delta/phase72c/equal-heuristic0.jsonl`, `equal-nodes20.jsonl`,
`equal-expired.jsonl`. Adequacy-budget repeated measurements follow separately.

## Resumed independent completion audit - 20 October 2026

### A-B. Verdict and repository identity

**COMPLETE** for Phase 7.2c's registered synthetic scope. No implementation or
test fix was required. This resumed task changes only this handoff document;
ignored local verification artifacts are retained under `.delta/phase72c/`.

Verified worktree: `C:/Users/venka/OneDrive/Desktop/AIS/GC1/Savora/Savora-Phase7`.
Branch: `feature/member2-phase7`. HEAD:
`0ca114c70c1e8f49e24d83d7fed35ec57f98fbe2`. The explicitly requested existing
branch is retained. The index is empty; the worktree retains one tracked
modification (`combinations.py`, from 7.2b) and 21 untracked Phase 7 files.
No unrelated changes, Git history changes, commit, push or PR occurred.

The saved pre-7.2c fingerprints match all 13 earlier files outside the five
documented 7.2c edits. All 22 preexisting changed/untracked files were also
fingerprinted during this audit and remained byte-identical until this report
was appended. The earlier 7.2b combination refactor is preserved.

### C. Exact Phase 7.2c file scope

The four created files and five modified files are exactly those in the task
inventory above. Paths below are relative to `apps/ai_system/`, except `docs/`:

| Change in 7.2c | File |
|---|---|
| Created | `src/savora_ai/core/reasoning/weekly_bounds.py` |
| Created | `src/savora_ai/evals/forward_benchmarks.py` |
| Created | `tests/test_weekly_bounds.py` |
| Created; report appended in this resume | `docs/member2_phase72c_forward_checking.md` |
| Modified | `src/savora_ai/core/reasoning/weekly_search_v2.py` |
| Modified | `src/savora_ai/core/reasoning/weekly_proof_v2.py` |
| Modified | `src/savora_ai/schemas/weekly_search_v2.py` |
| Modified | `src/savora_ai/schemas/weekly_solver_v2.py` |
| Modified | `tests/test_weekly_solver_v2.py` |

The modified files were already untracked Phase 7 work at this task's baseline;
Git status alone therefore cannot distinguish the earlier phases from 7.2c.
The handoff inventory and saved fingerprints provide that distinction.

### D-F. Correctness and security findings

Forward checking requires explicit `synthetic-forward-checking-weekly-search.v2`
selection with chronological variables, ascending original option IDs and
`KNOWN_FAILURE_FORWARD_CHECK`. The default v1 API does not dispatch to it.
Reverse ordering and MRV declarations remain nonexecutable.

Only the two registered numeric DAY/WEEK quantity sums are bounded. At every
unfinished prefix, the current DAY is checked before WEEK rules. Selected slots
contribute their exact value; every unassigned slot contributes extrema over its
entire original domain, including options with unknown or failing eligibility.
All contributing measurements must be present, complete, non-null, admitted fixed
whole-meal integer mg measurements. Integer arithmetic does not round through
floating point. With endpoints L/U and threshold t, closure requires:

| Operator | Proven impossibility |
|---|---|
| LT | L >= t |
| LE | L > t |
| GT | U <= t |
| GE | U < t |
| EQ | t < L or t > U |
| NE | L == U == t |

These enclosing intervals are necessary conditions, not claims of joint
feasibility or of attainable interior integers. Discrete gaps stay open.
Boolean completeness and repetition remain full-evaluation-only. Complete DAY
and WEEK evaluation and prerequisite checks are retained for surviving branches.

The verifier rebuilds the mandatory manifest and original domains, revalidates
source/context/profile/KB/candidate/configuration/measurement bindings, and
creates its own fresh preparation session. `_check_bound` reads retained source
measurements and independently computes extrema and comparison possibility;
it calls neither execution's bound helpers nor the search kernel. Shared
admission/encoding helpers do not establish arithmetic truth. Independent literal
Cartesian oracles separately check outcomes, first witnesses and every completion
excluded by the tested closures.

The checker reconstructs ordered events and accounting with its own task stack,
then checks the mixed-radix partition of original completions, including exact
unexplored suffixes after TIMEOUT or first FEASIBLE. Rehashed bounds, altered
evidence/rules/domains/indexes, omitted/reordered/duplicated events, changed
frontiers and counters cannot obtain a successful checked outcome in the
exercised attacks. Corrupted execution arithmetic and compiled measurement maps
are rejected. Hash agreement alone remains neither source authentication nor
permission to persist; the external verification entry point requires separately
selected authoritative inputs.

UNKNOWN applicability, missing/incomplete measurements and additional required
facts cannot authorize a bound closure. Additional facts must be known original
context/profile observations; other derived prerequisites disable the bound.
Evidenced NOT_APPLICABLE resolves its own obligation without asserting predicate
PASS; unknown dependencies dominate a local false applicability condition.
A separately established numeric FAIL can still refute a hypothesis containing
unrelated UNKNOWN, consistently with full evaluation.

Before arithmetic, each bound attempt reserves a potential proof record/bytes,
predicate and heuristic work, matching verifier work and a verifier step. Only
unused storage is refunded on nonclosure. Exact-budget completion and one-short
interruption are checked. Any unfinished required proof/verification work yields
TIMEOUT and withholds the witness; verifier expiry cannot promote authority.
Deadlines remain cooperative checkpoints, not preemptive CPU or RSS limits.

### G-H. Historical evidence and newly executed checks

The earlier handoff records 116 forward tests in 226.32s, 270 shared regressions
in 306.58s, and one combined 442-test earlier-v2/preparation/declaration/benchmark
run in 670.68s. Those are historical reported results, not reruns in this audit.
No retained raw runner log or JUnit report for those three runs was found among
the local handoff artifacts inspected. Source and test coverage were reviewed;
the historical counts are not presented as newly reproduced evidence.

Fresh focused final verification:

- **86 passed, 30 deselected in 282.80s**, exit 0, from `test_weekly_bounds.py`.
  Selection covers all six operator boundary/discrete-gap tables, all 12 literal
  Cartesian cases and per-prune enumeration, independent checker isolation,
  rehashed hostile certificates, source-map/arithmetic corruption, UNKNOWN and
  required facts, strict JSON, preparation capacities, resource exhaustion,
  verifier expiry, event order, exact reservations and policy relabelling.
- JUnit evidence: `.delta/phase72c/resume-focused.xml`. Pytest cache and bytecode
  writes were disabled. No package installation or other-worktree source edit.
- Fresh `ruff check .`: passed.
- Fresh `ruff format --check .`: passed, 152 files already formatted.
- Fresh Pyright using the existing shared interpreter and this worktree's AI and
  backend source paths: **0 errors, 0 warnings, 0 informations**. The configured
  local `.venv` absence produced an informational tool notice; the interpreter
  was explicitly supplied.
- `git diff --check`, all untracked-file whitespace checks with Windows CRLF
  accepted, empty-index checks, branch/HEAD and ownership/scope checks: passed.

Sandbox package access initially failed. The required tooling/tests then ran
with approved access to the preexisting shared environment, with this worktree's
sources selected. Full monorepo tests, frontend checks and new benchmark timing
runs were not executed. No Phase 7.2d, MRV or substitution work was started.

### I. Retained performance evidence

Validated all 42 records in `.delta/phase72c/adequate-paired.jsonl`: seven cases,
three repetitions per strategy, equal paired limits/fixture digests/outcomes/
first-witness digests, completed verification and no termination. These are saved
measurements from the interrupted task, not newly timed runs. Medians include
preparation and independent checking; fixture construction/imports are outside
timing. Preparation reuse was enabled for both strategies.

| Case | Baseline -> forward nodes | Median total seconds, baseline -> forward |
|---|---:|---:|
| early | 21 -> 21 | 4.350 -> 4.606 |
| late | 138 -> 24 | 8.253 -> 4.765 |
| day-pruning | 67 -> 4 | 6.377 -> 3.439 |
| week-quantity | 21 -> 0 | 3.515 -> 2.935 |
| unknown-refuted | 21 -> 0 | 3.527 -> 2.901 |
| exhaustive | 28 -> 22 | 4.677 -> 4.192 |
| unknown-measurement | 21 -> 21 | 3.540 -> 3.777 |

Late and DAY bottlenecks reduce nodes by approximately 82.6% and 94.0%; WEEK
root closures eliminate assignment visits. Nonpruning early/unknown-measurement
cases add approximately 5.9%/6.7% total-time overhead. Those two forward runs
charge 495/483 heuristic units per execution, mirrored by verification, versus
zero baseline heuristic work. Their certificates grow by 76 bytes each.
No new memory probe was run, and these small local measurements establish no
general latency or memory guarantee. The saved equal-budget observations above
also show that forward work can exhaust a budget where baseline completes.

### J-M. Remaining defects, compatibility and next gate

No unresolved HIGH or MEDIUM correctness/security defect was identified within
the supported synthetic scope. The final review covers pruning, required facts,
source bindings, proof/frontier/accounting forgeries and resource exhaustion;
it is not the future whole-Phase-7 integration audit or production certification.

Phase 1-6 public APIs and original solver/schema files remain unchanged by 7.2c.
The existing 7.2b private combination refactor remains preserved. V2 additions
are restricted to the explicit forward strategy, numeric bound declaration,
versioned accounting and computed result's forward-policy acceptance. No HTTP,
OpenAPI, TypeScript, backend/frontend, dataset or teammate contract changes.
Chronological v2 remains selectable; preparation reuse remains independent and
request-local, with a separate checker session. Phase 7.2a/7.2b compatibility is
supported by source/fingerprint review, the historical regression reports and
fresh selected forward/reuse tests, without claiming the full old suites reran.

A scoped checkpoint commit is safe after normal human review of the complete
uncommitted Phase 7 inventory. Nothing was staged or committed. Phase 7.2d is
ready to begin as a separately authorized task; it must retain exact full-fact/
evidence equivalence and reversible rollback against the current evaluators and
independent oracles. It is not implemented by this completion audit.
