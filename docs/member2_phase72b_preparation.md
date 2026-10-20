# Member 2 Phase 7.2b: private prepared recipe pools

Scope: registered synthetic rules only. Worktree `Savora-Phase7`, branch
`feature/member2-phase7`, HEAD `0ca114c`. This resolves the preparation-boundary
blocker with the explicitly authorized private refactoring. No clinical, ranking,
forward-checking, MRV, incremental derivation or substitution feature is enabled.

## Boundary and compatibility

`filter_candidates` is unchanged. The public `evaluate_combination` signature and
ordinary-input validation remain unchanged. It delegates to the shared private
`_evaluate_prepared_combination` worker, which still builds `_CombinationRequest`,
accepts the pinned KB, admits all mandatory checks, validates registered policies,
and performs the original component membership, composition, role, source,
preparation/configuration, applicability, predicate, evidence and result checks.
Its ordinary path calls the original full-pool public recipe filter directly.
There is no public parameter accepting a prepared pool or an affirmative result.

The private `_PreparedRecipePool` constructor accepts original inputs only. A
validated full pool is computed by the unchanged public recipe filter and stored
inside an operation-local closure. Exact validated KB (including graph/catalogue),
context/workflow/policy, complete candidate facts/evidence and permitted source/
configuration records bind each lookup. They are compared as complete records,
not accepted on caller-supplied hashes. No cache transport DTO, global registry,
cross-request pool, caller predicate or caller affirmative assessment is admitted.
Normal mutation is disabled; arbitrary trusted Python code execution is outside
the data-boundary threat model, as for the other private evaluator primitives.

All PASS, FAIL and UNKNOWN recipe assessments and explanations are retained.
Each combination is still evaluated separately, including different fixed
configurations of the same combination. An unreferenced failing recipe does not
exclude a combination. Empty hard inventories and unavailable evidence retain
the existing conservative semantics. No validator is disabled and no unchecked
Pydantic construction is used for accepted data.

## Opt-in v2 API and session scope

`solve_weekly_plan_v2(..., reuse_preparation=True, preparation_cache_entries=1)`
enables reuse. Existing defaults preserve the Phase 7.2a unshared execution path.
Capacity is exactly zero or one; zero performs fresh filtering on every logical
pool assessment. One immutable invocation has one complete pool key, so one entry
is sufficient. Private `discard()` evicts it; the next access recomputes the same
assessment. Production traversal needs no eviction between immutable bindings.

The initial reserved recipe operation seeds execution's pool; subsequent reserved
combination operations independently check their inputs before accessing it.
Execution releases the session before computed-result verification. The checker
constructs its own fresh session from retained, revalidated original inputs and
recomputes recipe assessments. It neither reads execution's cache nor accepts its
claimed counters. Search selection, pruning, terminal events and the independent
interval/frontier coverage check remain unchanged.

## Accounting

The existing `synthetic-weekly-work-reservation.v2` policy is unchanged. Recipe
preparations and predicates remain logical semantic obligations, including reused
assessments, reserved for execution and verification before work. Consequently the
same original limits produce the same logical certificate and stopping boundary,
except for genuinely different cooperative wall-clock deadline observations.
Binding validation is part of the already-reserved combination operation.

New optional computed fields `execution_preparation` and
`verification_preparation` use `synthetic-weekly-preparation-reuse.v2` and report:

- Logical candidate assessments, physical public filtering calls and candidate
  assessments, reused candidate assessments, and combination preparations.
- Successful cache binding checks, hits, misses, evictions and pool capacity/use.

These count named operations, not every structural Pydantic validator or physical
predicate invocation. Existing certificate cache fields continue to concern search
caches; comprehensive `physical_evaluator_calls` remains `NOT_RECORDED`. Preparation
instrumentation never supplies eligibility or proof authority. The checker derives
the new counts independently and rejects modified claims. If verification expires,
the result withholds execution preparation claims along with the successful witness;
only the checker's completed preparation work may remain reported.

For `n` candidates and `m` distinct referenced options, a completed phase retains
`n*(1+m)` logical candidate assessments. Disabled reuse executes `1+m` filters.
Enabled reuse executes one filter and reuses `n*m` candidate assessments. A complete
solve has separate execution and verification phases, each paying its own costs.

## Verification and measurement protocol

`tests/reference_combination_preparation.py` preserves the original evaluator from
HEAD `0ca114c` independently of the new worker. Equivalence tests compare its full
results, traces, explanations, manifests and evidence with public and prepared
evaluations. Original Phase 3/4 tests and Phase 6/v2 proof regressions remain intact.
Additional tests cover changed bindings, eviction, disabled storage, fabricated
records, input attacks, separate checker sessions, proof/count mutations, resource
boundaries, deadline withdrawal and the literal Phase 7.1b Cartesian oracle.

`python -m savora_ai.evals.preparation_benchmarks` measures two existing bounded
fixtures; `--reuse` enables sharing, `--memory` separately enables tracemalloc.
Instrumentation wraps original functions and never changes returned decisions.
Preparation includes input admission and compilation. Search ends before certificate
encoding. Verification includes its own admission, preparation and coverage work.
Total also includes certificate encoding and output admission; these overlapping
categories must not be added indiscriminately. Traced allocation is not RSS.

Actual pre-edit observations are preserved under ignored `.delta/phase72b` with
fixture, witness and logical-accounting identities. Final measurements and check
results are recorded below after verification; historical results are not new runs.

## Measurements: 20 October 2026

Existing Windows Python tooling, Pydantic 2.14.0, fresh invocation-local state and
no concurrent tests. Three untraced repetitions per case before edits; then three
disabled/enabled pairs per case after the refactor, always disabled first. Medians
in seconds follow. Fixture construction/imports are outside the timed interval;
required input admission, full validation and independent checking remain inside.

| Case / path | Preparation | Search | Independent verification | Total |
|---|---:|---:|---:|---:|
| early / pre-edit | 3.2217 | 0.9872 | 4.6858 | 9.3574 |
| early / refactored disabled | 3.5772 | 1.0478 | 4.7218 | 9.9303 |
| early / refactored enabled | 3.0220 | 1.0690 | 3.7647 | 8.1900 |
| repeated-identities / pre-edit | 4.7053 | 2.1358 | 7.1818 | 15.0655 |
| repeated-identities / refactored disabled | 4.2602 | 1.7919 | 6.4065 | 13.6520 |
| repeated-identities / refactored enabled | 3.9924 | 1.9932 | 5.6068 | 12.0491 |

The two-option early fixture reduced full-pool filters from 3 to 1 **per phase**
(6 to 2 total); the three-option repeated-identities fixture reduced 4 to 1
(8 to 2 total). Physical combination assessments remained 4/6 total respectively.
Each enabled phase had 2/3 successful reuse hits and binding checks, one miss,
one cached pool entry and zero operational evictions. Both have two candidates.
No logical reservation, node count, predicate obligation, frontier or proof record
changed. Cache validation is not free: its time is included in preparation and
verification, inside the original reserved combination operations.

All six timing pairs favored reuse. Observed paired-control median total reductions
were 17.5% and 11.7%; preparation medians fell 15.5% and 6.3%, and verification
medians fell 20.3% and 12.5%. Search timing varies and no search speedup is claimed.
Disabled/enabled total ranges were 8.7865–10.4040 / 8.1734–8.4642 seconds for early,
and 13.0053–14.7230 / 11.7021–12.7660 for repeated-identities. This is a small local,
fixed-order pilot, not a statistically established or general latency guarantee.
Pre-edit versus refactored-disabled ranges overlap; no default-path timing
regression or improvement is established from those observations.

Every measured run returned FEASIBLE with identical witness digests, fixture
digests and complete logical accounting. Compact certificate sizes stayed exactly
99,091 and 182,742 bytes. Enabled per-phase physical candidate assessments fell
6→2 / 8→2, with 4/6 reused candidate assessments; logical counts stayed 6/8.

Separate single-run tracemalloc probes (not included in the timing medians) found:

| Case | Disabled peak bytes | Enabled peak bytes | Difference |
|---|---:|---:|---:|
| early | 11,973,326 | 12,384,088 | +410,762 (3.4%) |
| repeated-identities | 17,518,532 | 17,919,124 | +400,592 (2.3%) |

These are full-invocation Python traced peaks, not isolated cache allocation or
RSS. The enabled path retains a full pool during each phase and adds preparation
metadata; its execution pool is released before the independent checker starts.
End-of-phase cache-entry counts describe the session before teardown. Teardown
does not count as an operational eviction. Tracing materially slows execution;
its timings are deliberately excluded from the untraced comparison.

Raw artifacts: `.delta/phase72b/before.jsonl`, `after-paired.jsonl`, `memory.jsonl`.
They are observational local artifacts and remain ignored, not trusted inputs.

## Actual checks and remaining scope

- Preparation suite: 55 passed in 406.78s, including the literal oracle, complete
  public/reference equality, changed bindings, cache-disabled/eviction behavior,
  consecutive fresh requests, cache corruption, count/proof forgeries and deadlines.
- Additional component/preparation/evidence rejection cases: 3 passed in 2.11s.
- Final same-fixture v1/v2 witness checks, absent-authority prepared evaluation,
  coherent context-version binding and dependency audit: 5 passed in 48.60s.
- Original v2 solver/proof, 7.1c declarations and architecture audit: 208 passed
  in 483.70s. Existing tests were not weakened or edited.
- Phase 3 filtering, Phase 4 evaluator, Phase 6 solver/integration group: 269 passed;
  one legacy filtering-spy test failed against an earlier module import layout.
  The original public filtering alias/path was restored; that unchanged test and
  two final execution/checker isolation cases then passed (3 cases in 47.01s).
  The expensive combined group was not repeatedly rerun.
- Final Ruff lint and formatting passed; Pyright reported 0 errors, 0 warnings,
  0 informations using the explicit existing interpreter. The missing local
  `.venv` notice does not change the selected interpreter or import paths.

Full monorepo pytest was deferred. No backend/frontend, dependency/lockfile, team
ownership, nutrition, nonchronological strategy or swap change occurred. The public
Phase 1–6 functions and schemas retain their signatures and behavior. Original
Phase 7 files outside the three necessary v2 implementation/result changes remain
byte-identical to preflight. No unresolved HIGH/MEDIUM defect is reproduced within
the registered synthetic scope. Reuse remains opt-in; safe preparation is ready
as the foundation for Phase 7.2c. No commit or push was performed.

Files created in this task:

- `apps/ai_system/src/savora_ai/core/reasoning/preparation.py`
- `apps/ai_system/src/savora_ai/evals/preparation_benchmarks.py`
- `apps/ai_system/tests/reference_combination_preparation.py`
- `apps/ai_system/tests/test_preparation_reuse.py`
- `docs/member2_phase72b_preparation.md`

Files modified in this task:

- `apps/ai_system/src/savora_ai/core/reasoning/combinations.py`
- `apps/ai_system/src/savora_ai/core/reasoning/weekly_search_v2.py`
- `apps/ai_system/src/savora_ai/core/reasoning/weekly_proof_v2.py`
- `apps/ai_system/src/savora_ai/schemas/weekly_solver_v2.py`
