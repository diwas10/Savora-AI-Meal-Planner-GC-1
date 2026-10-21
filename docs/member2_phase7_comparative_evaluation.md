## M1 corrective verification — 21 October 2026

M1 status: **COMPLETE**. Phase 7.4 benchmark status remains **PARTIAL / CHECKPOINTED**.
The original architecture test is unchanged and passes. Raw proof declarations,
shared admission/cost helpers and the unchanged B1 executor now have dependency-safe
owners; the public facades retain their APIs and mandatory authority-bound replay.
The final import graph is acyclic across 69 AI modules, including deferred imports.

The single fresh regression run collected 780 unique tests and passed all 780,
with zero failures, errors, skips, missing or additional XML test IDs:
140 declaration/contract cases, 71 B1 validation, 87 B1 independent proof,
112 B2 selection, 57 workflow-policy, 136 Phase 3 integration, 150 comparison
harness and 27 focused earlier-phase/reuse/ordering cases. This was not a full
monorepo run. Monitoring ended at 21:29:58 SGT; the original process completed
naturally at approximately 21:30:43 SGT and was discovered during the checkpoint
at 21:30:59. It was neither interrupted nor duplicated.

Ruff passed, formatting checked 126 files, and Pyright analyzed 126 files with no
errors or warnings. All 16 fresh-process import orders passed. Nine public APIs,
21 JSON schemas and two enum classes match the baseline. All four freshly executed
B1 wire/digest goldens match; both stored B2 wire captures reserialize identically.
The frozen v1 KB/wire golden test and registered-v2 policy tests passed in the run.
No unresolved HIGH/MEDIUM finding remains in this corrective scope.

Final verification source: 130 executable/configuration file hashes, dirty source
fingerprint `c67ca90f525cb19377f20d1ef75a842a11cb8310186ff2d57a2ac41792887052`.
The prior 624-job cohort retains fingerprint
`c2454782657369594423dd076b50205c1b6c1c2d67cbb5d6a0050890fd68b3e0`;
all prior 1,155 captured evidence files remain unchanged. Those observations are
not measurements of the M1 refactor. No campaign was resumed.

Detailed A–O report, XML reconciliation, source hashes and the explicit 14-path
submission inventory are preserved in `.delta/m1-cycle/`. The master plan,
datasets and raw `.delta/` evidence are excluded from staging. No commit or push
was performed; those actions require a separate user instruction.

---

> Post-M1 provenance notice: the campaign and verification results below describe
> the preserved pre-refactor Phase 7.4 checkpoint. Its original source hashes
> do not describe the refactored swap modules. The 624 observations and frozen
> source archive remain unchanged. Fresh M1 verification and final source
> fingerprints are recorded separately under `.delta/m1-cycle/`; a benchmark
> on the revised source requires a new cohort or an authorized historical
> environment. No benchmark was resumed by the M1 fix.

# Phase 7.4 — reproducible comparative evaluation

Status: PARTIAL ? CHECKPOINTED FOR SUBMISSION. Exhaustive Phase 7.4 evaluation is unfinished. The user authorized an early deadline checkpoint instead of waiting for 1,504 jobs. No Phase 7.5 implementation is part of this task.

## Scope and preservation

The evaluation owns only `member2_phase7_comparison.py`,
`phase7_comparison_cases.py`, `test_phase7_comparison.py`, and this handoff.
Production solver, proof, KB policy, swap, datasets, and prior evidence remain
unchanged. The starting checkpoint is
`67991cf22c7d80111a08d48ab29df329c07094f3` on
`feature/member2-phase7` in `Savora-Phase7`. The untracked Phase 7.3–7.5 master
plan is excluded from implementation scope. No commit or push is part of this task.

Preservation hashes are in `.delta/phase74/preservation-before.json`: 243 source
and document entries and 213 historical evidence entries. These are checked again
at handoff. Earlier results are historical evidence, not new Phase 7.4 runs.

## Frozen protocol

`member2-phase7-comparison.v1` uses strict versioned configuration, manifest and
run records. The manifest freezes ordered raw workloads, literal oracle truth,
all group/job identities, actual HEAD, full executable source SHA-256 map and a
dirty-source fingerprint. Source changes require a separate complete cohort.
Canonical JSON preserves sequence order and distinguishes missing, zero, false
and empty values. Imports, fixtures, oracle construction and source fingerprint
checks are outside invocation timing.

Fixture construction temporarily supplies the native synthetic case catalogue
only while constructing DTOs; that configuration patch ends before execution.
Relevant lazy engine modules are imported outside timing/tracing without invoking
decisions or warming request-local state. Reporting metrics and result hashes are
extracted after the invocation timer and memory trace stop.

All nine supported v2 strategies run with preparation reuse disabled and enabled.
Original v1 chronological is an additional reference with its own resource units.
No unsupported strategy or native algorithm is enabled or changed. Every semantic
and resource group has a correctness observation; designated latency groups have
two recorded warmups and ten measurements. Case-specific latency groups cover
easy, late, symmetric, DAY bottleneck, WEEK bottleneck, UNKNOWN and many-rule weekly
inputs, plus two single-swap targets and early/late selection. Other workload
groups establish correctness/resource behavior without claiming latency samples.

Execution is sequential with variant rotation within repetition blocks. An
exclusive process lock prevents a second harness from starting concurrently.
Completed atomic records permit resumption without duplicating observations.
Every failure, TIMEOUT and slow observation remains in evidence. No speedup
threshold is required. The user explicitly authorized the full campaign runtime.

Adequate-budget and equal-budget tracks are separate. Native units and ceilings
are recorded per invocation; equal numeric ceilings across v1/v2 do not imply
equal work or proof capacity. Resource observations cover node, work, proof,
encoding, cache and deterministic deadline boundaries. Expected boundary errors
are distinct from completed semantic rejections.

## Independent correctness

The literal weekly oracle streams at most 256 assignments with an explicitly
declared vocabulary of up to 50 fixed options. It uses integer sums, presence,
three-valued logic and recipe-set occurrence counts; it never calls production
predicates or solver decisions. The large sparse case declares a constructed
witness and does not claim exhaustive enumeration. Native proof checking remains
mandatory, and explicit authority verification follows the public invocation.

Swap truth enumerates a bounded declared replacement domain against a fixed
21-slot original. All 21 target positions are represented. Successful proposals
must preserve the exact other 20 payloads, match the supplied opaque replacement
reference and satisfy literal day/week totals. Selection checks visited candidates
and first-VALID ranking semantics. It makes no global preference-optimality claim.
The zero-based rank in the visited eligible order is distinct from the original
domain index; both are recorded for selections.
The 50-option known-invalid fixture uses concise explicit evidence declarations
to fit the unchanged 1 MiB public ingress limit; missing measurements do not become
zero or PASS. Stale references, locks and no-ops remain negative cases.

## Timing, statistics and memory

The actual verified-pipeline total encloses public invocation (including its
mandatory native checking), explicit authority verification and final encoding.
Those three markers are disjoint within the total. Native preparation/search/
checker timings are reported only where exposed by v1; unavailable v2/swap stage
timings and physical-call counts are marked `NOT_AVAILABLE`. Logical work is never
reported as observed physical calls. Setup is separately timed. No stage-median
sum is substituted for total runtime.

Statistics use inclusive linear quartiles, median, IQR, minimum, maximum and all
raw samples. Paired ratios require both complete ten-measurement groups plus
their warmups and correctness gates. Censored groups retain descriptive times and
completion rates but do not yield speedup claims. Cases/protocols are not pooled
into an overall speedup. Ordering may change witnesses; hard feasibility and
chronological first-witness compatibility are checked independently.

Memory is a separate cohort with three fresh processes for each representative
group. Fixtures/imports/oracle are outside tracing. Traced peak Python allocation
and Windows working set/lifetime peak working set are separate metrics; incompatible
baselines are not subtracted. Memory timings never enter latency tables. Less
search and lower memory do not isolate cache/state overhead causally.

Raw atomic records are authoritative; the append journal is retained, including
any partial interrupted tail. Regeneration sorts validated atomic records by
frozen execution order and writes a derived JSONL artifact. Duplicate/missing jobs,
source drift, wrong group identities, oracle contradictions and invalid accepted
proofs are checked before aggregation.

## Findings and final verification

The submission checkpoint contains **624 / 3,007 jobs (20.7516%)**. All are
CORRECTNESS jobs in the weekly ADEQUATE track. All 624 pass their declared
independent correctness assessments: 386 FEASIBLE, 152 INFEASIBLE,
76 INSUFFICIENT_DATA and 10 verified bounded TIMEOUT observations. A verified
TIMEOUT is a valid censored frontier certificate, not completed semantic search.
There are no failed correctness checks or observed invalid accepted proofs.

All 19 variants (nine v2 strategies with reuse off/on plus v1 reference) completed
correctness gates for 32 weekly cases. `fifty-fixed` has 16 of 19 gates; its next
pending job is zero-based order 624, STATIC_MRV_INCREMENTAL_FORWARD_CHECKING,
reuse false. The constructed large weekly case is unstarted. Thus 472 manifest
groups are fully complete, 152 are partial (correctness gates completed but
warmups/measurements pending), and 489 are unstarted. These are protocol groups,
not counts of distinct workloads. Exact group IDs, pending job identities and
case counts are in `.delta/phase74/checkpoint-accounting.json`.

Remaining: **2,383 jobs** = 478 correctness + 312 warmup + 1,560 timing measurement
+ 33 memory probes. No warmup, measurement, swap validation, swap selection or
memory job has completed. All 50 swap correctness jobs, all equal-budget groups
and all repeated timing/memory cohorts remain pending. Passing swap integration
unit tests below do not substitute for those campaign jobs. No statistically
reliable speedup, memory improvement, equal-budget comparison or exhaustive
Phase 7.4 completion is claimed.

Negative findings: REVERSE_VALUES exhausted PROOF_BYTE_BUDGET on product-32,
product-64, product-128, product-256 and fifty-fixed, in both reuse modes (10
records). Each certificate was independently accepted; no witness was claimed.
The proof checker `complete` flag means verification finished, not that search
finished. These observations remain in raw records and descriptive summaries;
they cannot enter successful-completion speedup ratios. Single correctness-job
runtimes include substantial proof costs and are not repeated timing evidence.

### Safe stop and durable evidence

The identity-checked controller (PID 11488), launcher (39992) and actual worker
(74444) have exited. The running controller offered no live pause command; its
job limit was launch-only. Under the user's explicit controlled-interruption
authorization, the controller was stopped and its descendants subsequently
exited; no worker termination command executed. The native benchmark lock was
released. No automatic restart remains. No partial atomic record file exists.
The last durable job is zero-based order 623. The next pending job, order 624,
may have begun computation, but no result exists; replay it rather than inventing
or finalizing an observation. Exact in-flight execution start was not observable.
The progress log ended at 623, whereas authoritative atomic records and the
journal contain 624 complete, unique records. The journal has no partial lines
and agrees with every atomic record. All original observations are preserved.

`.delta/phase74/checkpoint-audit.json` records the successful source, invocation,
oracle, environment, proof/witness, preservation, prior-test and Git-scope audit.
`.delta/phase74/controlled-interruption.json` records the stop; the accounting file
contains per-record SHA-256 hashes and every remaining job. Derived
`summary-checkpoint.json` and `runs-regenerated.jsonl` live in the frozen cohort
directory; the original running `summary.json` is retained and may lag progress.
The original `audit-final.py` remains preserved for eventual full completion.
Internal `.delta/` evidence is excluded from the intended Git submission.

Frozen manifest digest:
`1bb6e7e5badaa75bd92c8e66b311c5b08081e6d7de111db4f90b06e7423e060c`.
Manifest file SHA-256:
`dfbc443a5c722f8ca608ba2680cb01cb5f7cdf0b539710768b2d199e59162a08`.
Current dirty source fingerprint:
`c2454782657369594423dd076b50205c1b6c1c2d67cbb5d6a0050890fd68b3e0`.
All 126 executable source fingerprints match both current source and the archived
source snapshot. All 243 protected files and 213 historical evidence files match
preservation hashes. All 624 invocation fingerprints were independently rebuilt
from frozen raw authorities and actual operational limits; per-group semantic
fingerprints are consistent. Environment information remains in manifest/records.

### Verification reused without expensive repetition

Recorded relevant regressions: **1,705 passed in 8,511.77 seconds**. Final harness:
**150 passed in 201.81 seconds**. Their union is 1,720 unique cases because 135
harness cases overlap. Both XML reports have no failures, errors or skipped cases.
Ruff passed; formatting reports 122 files already formatted. Pyright analyzed
122 files with zero errors, warnings or information diagnostics. These results
apply to the unchanged final Python source. No expensive regression was rerun
for the checkpoint, and no new full monorepo regression is claimed.

The branch/HEAD are unchanged, the index is empty and Git whitespace checks pass.
The only five untracked files are the four intended evaluation submission files
and the preexisting master plan. No production, policy, datasets or Member 1/3
implementation changed. No HIGH/MEDIUM correctness defect was observed in the
completed evidence; missing cohorts remain an explicit evaluation limitation.

### Resumption procedure (future authorization required)

Do not resume automatically or use the old full controller: it repeats checks
and has no submission deadline cap. Preserve at least three hours before the
professor's submission for a separately authorized focused Phase 7.5 audit,
Git review, commit, push and repository verification. An actual submission
clock time was not supplied, so this checkpoint does not assert time remaining.

Before any future campaign launch, inspect controller status and process command
lines, verify no benchmark is active and no lock exists, and revalidate this
manifest, all source fingerprints, raw records and archived source. Stop on any
mismatch. Resume only under the original HEAD and dirty-source fingerprint.
A subsequent Git commit changes the recorded HEAD/dirty state: do not override
provenance checks, reset the submission branch or mix post-commit observations
into this cohort. A separately authorized historical environment or a new cohort
is required if those provenance preconditions can no longer be met.

With the original provenance intact and a newly agreed runtime window, run from
the repository root in PowerShell using the existing interpreter:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = "$PWD/apps/ai_system/src;$PWD/apps/backend/src"
& '..\Savora-AI-Meal-Planner-GC-1\.venv\Scripts\python.exe' -B -m savora_ai.evals.member2_phase7_comparison run .delta/phase74/phase74-full-v1 --cohort phase74-full-v1 --max-jobs 880
```

This skips validated durable observations and processes at most 880 additional
jobs, reaching 1,504 if all complete; it is not a time limit. Choose a smaller
explicit job cap when needed. An intentionally partial capped run returns exit
code 2 with INCOMPLETE status; a correctness failure must still be reviewed as a
blocker. Retain stdout/stderr in a new evidence log rather than overwriting the
original. Reconcile atomic records and regenerate the checkpoint audit after
exit. Full eventual completion must pass the preserved full audit, including
all warmups, ten measurements per timing group and fresh-process memory probes.

The checkpoint is ready for a separately authorized focused Phase 7.5 submission
audit, with incomplete comparative evaluation disclosed. This is not Phase 7.4
COMPLETE or final submission approval. No commit, push or PR occurred.

Threats to validity include synthetic nonclinical attributes, hand-placed
witnesses, small desktop samples, host noise, limited domain/catalogue diversity,
native proof format overhead, common-mode primitive evaluators in native proof
checking, censored limits, different witness quality, runtime/dependency versions,
cache warmup effects, traced-memory overhead and fictional ranking priorities.
No production or medical conclusion follows from these measurements.
