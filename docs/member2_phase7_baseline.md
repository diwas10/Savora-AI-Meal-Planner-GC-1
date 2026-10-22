# Member 2 Phase 7.1b: synthetic weekly baseline harness

Scope: the existing Phase 6 public `solve_weekly_plan`, with certificate verification
enabled. Existing solver/schema files, production APIs, dependencies, datasets,
teammate files and Phase 7.1a documents are unchanged. Worktree `Savora-Phase7`, branch
`feature/member2-phase7`, baseline HEAD
`0ca114c70c1e8f49e24d83d7fed35ec57f98fbe2`.

Read AGENTS.md, ARCHITECTURE.md's workflow/CSP/ownership/evaluation provisions,
the [Phase 7 plan](member2_phase7_plan.md), [ADR](adr_member2_phase7_search_and_swap.md),
the implemented/audited sections of the [Phase 6 handoff](member2_weekly_csp.md),
and existing independent weekly tests. Retain the explicitly requested branch.
The two untracked 7.1a documents were the only expected preflight changes.

## Implementation and usage

- `apps/ai_system/src/savora_ai/evals/synthetic_week_cases.py`: fresh immutable
  synthetic inputs, stable full-fixture digests and a literal Cartesian oracle.
- `apps/ai_system/src/savora_ai/evals/weekly_benchmarks.py`: public solver runner,
  strict frozen camelCase report models and a JSONL CLI.
- `apps/ai_system/tests/test_weekly_benchmarks.py`: focused fixture, truth,
  measurement, validation, isolation, compatibility and hostile-witness checks.

From a Python environment with the repository's existing dependencies, use the
current worktree's AI source (PowerShell example):

```powershell
$env:PYTHONPATH = (Resolve-Path apps/ai_system/src).Path
python -m savora_ai.evals.weekly_benchmarks --case single
python -m savora_ai.evals.weekly_benchmarks --case all
python -m savora_ai.evals.weekly_benchmarks --case single --memory
```

The CLI writes one `weekly-benchmark-result.v1` JSON object per line to stdout;
it performs no network/model/database access and writes no files itself. Each
run constructs fresh validated candidates, source, context and accepted synthetic
KB material, then invokes the existing public solver once. It does not accept
caller PASS results, disable validation or bypass certificate replay.

## Workload inventory and oracle

| IDs | Purpose |
|---|---|
| `single`, `early`, `late` | One option/slot, first witness, last of eight alternatives |
| `exhaustive`, `week-quantity` | Complete known quantity contradiction |
| `unknown-day`, `unknown-measurement` | Surviving missing prerequisite/measurement evidence |
| `unknown-refuted` | Independently known WEEK failure dominates DAY UNKNOWN |
| `day-pruning` | Known DAY failure covers a subtree |
| `week-repetition`, `repeated-identities` | Canonical recipe presence across configurations and duplicate components |
| `empty-domain` | No original completions |
| `exact-work`, `node-short`, `option-odd` | Exact node/evaluation/predicate/record capacities and insufficient reservations |
| `day-zero`, `week-zero`, `predicate-zero` | Evaluation-cap exhaustion |
| `proof-short`, `proof-bytes-zero` | Mandatory proof record/byte exhaustion |
| `cache-zero` | Eviction/recomputation without changing original alternatives |
| `deadline-before-preparation` | Deterministic already-expired public injected clock |

All 22 workloads use at most eight Cartesian assignments and explicit finite
`WeeklySearchLimits`. The oracle rejects products above its hard ceiling of 256
before enumeration. Tests also check exact admission at 256 and refusal at 512.
Fixture identity hashes the complete ordered spec, expected outcome, budgets,
clock policy, request, candidates, accepted KB, context and source. It excludes
observational timing and environment. Digests identify fictional data, not source
authenticity. Each input graph is rebuilt; no computed decision cache is shared.

The independent oracle models only this fixed literal family: three options with
fictional whole-meal integer quantities 3/7/11; options 0/1 are configurations of
recipe A and option 2 is recipe B; known recipe/composition/suitability prerequisites;
registered DAY completeness/optional quantity cap; WEEK completeness, exact total
and canonical recipe occurrence cap. Duplicate components count once per recipe
per slot. Missing measurements are unknown, not zero. An explicit nine-cell hard
truth table preserves known-FAIL dominance and unrefuted UNKNOWN.

It enumerates original domains with `itertools.product`, performs literal arithmetic
and records every PASS/FAIL/UNKNOWN plus the first feasible witness. It calls no
production predicate, aggregation, pruning or search helper; tests make those
helpers raise while the oracle still works. Feasible results are separately checked
against exact original day/domain/configuration choices, trial/assignment agreement
and literal truth. Unchecked spliced-witness tests demonstrate rejection.

Resource/deadline scenarios have **problem-only oracle support**: their exhaustive
problem is feasible, while the expected bounded v1 execution is TIMEOUT. The oracle
does not simulate scheduling, reservations, cooperative checkpoints or physical
calls. The report marks this distinction explicitly. General KB predicates,
other applicability policies, real nutrition and larger domains are not supported.

## Report and fair comparisons

The strict report has separate `correctness`, `effort`, `evaluationWork`, `evidence`,
`timings`, `memory` and `resources` sections, plus workload/input digests, solver
schema/search policy and Python/runtime dependency/platform metadata. It validates
nonnegative finite metrics, oracle coverage counts, witness/outcome consistency
and timeout/termination relationships. Untrusted raw report JSON can use the existing
`validate_contract_json` duplicate-key ingress. A report is observational data;
validating it does not verify an externally supplied solver certificate or authorize
any plan.

Counter definitions:

- Logical nodes, backtracks, failures, unknowns, cache high-water/hits and pruning
  come directly from verified statistics. Completed assignments count retained
  certificate `LEAF` records; reaching a full prefix without capacity for its WEEK
  evaluation/proof does not count as a completed evaluation.
- Option, DAY, WEEK, predicate, recipe-batch and recipe-candidate counters preserve
  v1's **execution plus output-replay reservations**. They are not divided by two
  or reinterpreted as physical calls. Completed physical calls and the execution/
  verification split are `NOT_AVAILABLE`. A separate test spy counts real public
  combination calls without using reservation arithmetic.
- Proof records and reserved proof bytes come from the certificate; actual compact
  camelCase UTF-8 certificate/result byte lengths are measured separately. Reserved
  bytes do not represent full-result size or process memory. Full-result byte length
  includes variable-length timing metadata and is observational.
- Cache misses/evictions and RSS are `NOT_AVAILABLE`. Optional `tracemalloc` measures
  peak traced Python allocation during the public solver call, excluding prebuilt
  fixture memory; it does not measure process RSS. Existing tracing sessions are
  not reset. Profiling runs must be compared separately because of their overhead.

Preparation/search/output-verification times come from the public result. External
`perf_counter` measures total public solver wall time and separately fixture build,
oracle and serialization intervals. Total solver time includes validation/replay,
but excludes fixture construction, oracle, report extraction and serialization.
Do not add overlapping intervals. The deterministic deadline's constant stage
clock is labelled `SYNTHETIC_EXPIRED_CONSTANT`: its zero stage values are clock
metadata, not measured algorithmic duration; its external wall time is real.

For future comparisons, require equal fixture digests, original semantic inputs,
limits/accounting definitions, stopping criterion and instrumentation mode. Preserve
the v1 expected-outcome label in the fixture rather than changing its digest for a
different strategy. Compare exhaustive oracle truth when work completes; report
bounded outcome differences separately. Never turn TIMEOUT into INFEASIBLE or
compare different workloads' times as if they measured a speedup.
`semantic_projection()` excludes all timing, memory, environment, proof layout and
serialized-size observations, and keeps outcomes and witness choices as separate
values. Different future strategies may agree on outcome with different witnesses.

## Actual baseline observations, 19 October 2026

One sequential measurement per workload, collected separately after tests finished,
with fresh request-local state, imported modules warm and memory tracing disabled.
Environment: CPython 3.14.7, Windows 11 build 26300, savora-ai 0.1.0,
Pydantic 2.14.0 and pydantic-core 2.50.0. These are pilot observations without
repeat statistics or a controlled hardware/SLO claim. Different rows are different
workloads, not evidence of comparative speedup.

All 22 expected bounded outcomes matched: 6 FEASIBLE, 6 INFEASIBLE,
2 INSUFFICIENT_DATA and 8 TIMEOUT. Every completed outcome matched the exhaustive
oracle; all six feasible witnesses independently passed and matched the literal
chronological first witness. TIMEOUT's oracle comparison remains unavailable.

Times below are seconds. `Proof B` means conservative reserved certificate bytes,
not actual serialized bytes. The deadline row's stage times use the labelled
synthetic constant clock; only its total column measures elapsed wall time.

| Workload | Outcome | Nodes / leaves | Prepare | Search | Verify | Total | Proof B |
|---|---|---:|---:|---:|---:|---:|---:|
| single | FEASIBLE | 21 / 1 | 2.2938 | 0.8726 | 3.0914 | 6.2644 | 5412 |
| early | FEASIBLE | 21 / 1 | 3.2302 | 0.8662 | 4.4306 | 8.5277 | 5573 |
| late | FEASIBLE | 138 / 8 | 2.5524 | 0.8420 | 2.6448 | 6.0402 | 12026 |
| exhaustive | INFEASIBLE | 28 / 4 | 1.9272 | 0.4890 | 2.8798 | 5.2966 | 6488 |
| unknown-day | INSUFFICIENT_DATA | 21 / 1 | 1.7874 | 0.2506 | 2.0713 | 4.1099 | 5412 |
| unknown-measurement | INSUFFICIENT_DATA | 21 / 1 | 1.5315 | 0.3312 | 2.8575 | 4.7208 | 5412 |
| unknown-refuted | INFEASIBLE | 21 / 1 | 1.4131 | 0.2220 | 2.1248 | 3.7605 | 5412 |
| day-pruning | INFEASIBLE | 67 / 6 | 2.1655 | 1.1383 | 3.3185 | 6.6228 | 8786 |
| week-quantity | INFEASIBLE | 21 / 1 | 2.8095 | 0.4102 | 1.8822 | 5.1024 | 5412 |
| week-repetition | INFEASIBLE | 22 / 2 | 1.8557 | 0.3929 | 3.0229 | 5.2723 | 5878 |
| repeated-identities | FEASIBLE | 26 / 4 | 2.7555 | 0.8621 | 3.2789 | 6.8971 | 6649 |
| empty-domain | INFEASIBLE | 0 / 0 | 1.3939 | 0.0003 | 1.3280 | 2.7226 | 4321 |
| exact-work | FEASIBLE | 21 / 1 | 1.3675 | 0.4366 | 1.8576 | 3.6621 | 5412 |
| node-short | TIMEOUT | 20 / 0 | 1.4401 | 0.1454 | 1.4520 | 3.0379 | 5107 |
| option-odd | TIMEOUT | 0 / 0 | 0.4555 | 0.0002 | 0.3099 | 0.7659 | 4160 |
| day-zero | TIMEOUT | 3 / 0 | 1.4002 | 0.0003 | 1.3163 | 2.7172 | 4321 |
| week-zero | TIMEOUT | 21 / 0 | 1.4056 | 0.1702 | 1.8266 | 3.4027 | 5259 |
| predicate-zero | TIMEOUT | 0 / 0 | 0.2244 | 0.0002 | 0.1166 | 0.3417 | 0 |
| proof-short | TIMEOUT | 21 / 0 | 1.5435 | 0.1571 | 1.5805 | 3.2814 | 5259 |
| proof-bytes-zero | TIMEOUT | 0 / 0 | 0.2197 | 0.0002 | 0.1216 | 0.3419 | 0 |
| cache-zero | FEASIBLE | 138 / 8 | 2.6212 | 2.8728 | 3.9728 | 9.4676 | 12026 |
| deadline-before-preparation | TIMEOUT | 0 / 0 | synthetic 0 | synthetic 0 | synthetic 0 | 0.3885 | 0 |

The single-option report records 14 DAY and 2 WEEK reserved evaluations, 38 semantic
predicate reservations, 10 proof records, 1,897 actual certificate bytes and 295,854
actual result bytes. `exact-work` finishes at precisely 21 nodes, 2 option units,
14 DAY units, 2 WEEK units, 38 predicate units and 10 records. One fewer node,
an odd single option unit, or a missing final proof record returns TIMEOUT.
`day-pruning` completes six leaves from eight original assignments with a known
DAY exclusion; the exhaustive oracle still checks all eight original assignments.

The complete local JSONL output, including all metrics and fixture/release digests,
is generated at `.delta/member2_phase7_baseline_results.jsonl`. It is an ignored
measurement artifact, not a dependency or an edited solver file. The CLI can
regenerate the format; elapsed times and serialized result sizes need not repeat.

A separate `single --memory` run measured 13,212,938 bytes (12.60 MiB) peak traced
Python allocation during the solver call and took 71.6168 seconds with tracing.
That instrumented time is excluded from the normal baseline table. Fixture build
memory and process RSS are not included. Its JSONL record is in
`.delta/member2_phase7_baseline_memory.jsonl`; all 23 actual normal/profile reports
were strictly validated through `validate_contract_json` on the original JSON lines.

## Verification and compatibility

Executed against the final Python files with the existing installed environment
and explicit current-worktree AI/backend source paths. Python bytecode and pytest
cache writes were disabled; no dependencies were installed and no other worktree
was changed. The sandbox denied the installed environment's Pydantic DLL and Ruff
executable, so the approved commands ran outside the sandbox.

| Check | Actual result |
|---|---|
| Focused benchmark tests plus existing architecture/import-cycle audit | 177 passed in 180.18 seconds (176 focused cases plus 1 existing audit) |
| Existing `test_weekly_solver.py` and `test_member2_phase6_integration.py` | 87 passed in 506.31 seconds |
| `ruff check .` | PASS |
| `ruff format --check .` | PASS; 136 files formatted |
| `python -m pyright --pythonpath <existing interpreter>` | 0 errors, 0 warnings, 0 informations; existing missing-local-venv notice, explicit interpreter used |
| Standalone CLI | 22 bounded workloads; all expected outcomes and supported oracle/witness comparisons passed |
| Measurement artifact ingress | 23 original JSONL records strictly validated; UTF-8 without BOM |

An earlier 154-case focused run also passed; it preceded the additional source/spec
and spliced-witness checks and is not substituted for the final 177-case run.
The complete repository pytest suite was deferred: the required regressions alone
took 8m26s, and the previous Phase 6 full-suite record took about 21 minutes.
No full-suite pass, frontend lint/typecheck/build or clinical evaluation is claimed.

The v1 public signature and literal result/search tokens are checked, and the
existing import audit passes. No HIGH/MEDIUM defect was identified in this bounded
fixture family. Unsupported oracle families, unexposed physical counters/RSS,
limited pilot repetitions and the deferred full-suite run remain explicit gaps.

## Limitations and next task

This is a synthetic baseline and one bounded oracle family, not a production
performance or safety claim. Source authentication, clinical thresholds, real
nutrition, Food.com normalization, v2 search, MRV/forward checking and meal swaps
remain excluded. No HTTP/OpenAPI/TypeScript contract or existing public solver API
is changed. Phase 7.1c strict v2 proof declarations are the next separately scoped
task; they are not implemented here. No commit or push is authorized.
