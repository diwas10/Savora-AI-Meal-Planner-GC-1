# Member 2 Phase 7: contract, proof and swap architecture plan

Status: Phase 7.1a documentation decisions, 19 October 2026. Only this plan and
[ADR: Phase 7 search and swap boundaries](adr_member2_phase7_search_and_swap.md)
are delivered. No Phase 7 runtime capability, benchmark result, DTO, policy token,
heuristic or swap API is implemented. The engineering constraints below are fixed
for this Member 2 work sequence; external team contracts remain **PENDING**.

## Authority and verified baseline

Preflight verified worktree `Savora-Phase7`, branch `feature/member2-phase7`,
HEAD `0ca114c70c1e8f49e24d83d7fed35ec57f98fbe2`, and a clean index/worktree before
editing. Retain the explicitly requested existing branch despite AGENTS.md's
generic `feat/` convention. Do not alter other worktrees, stage, commit or push.

AGENTS.md and ARCHITECTURE.md remain authoritative, especially sections 3-5
(identity, workflow and unknowns), 6-8 (composition, ranking and CSP), 9.3-11
(contracts, persistence and ownership), and 13-15 (evaluation and open decisions).
Read the six Phase 1-6 Member 2 handoffs listed below, including their later
implementation/audit sections. Early declarations of deferred functionality and
historical Git/test results in those documents describe their own checkpoints;
they are not current Phase 7 verification or authority to change the contract.

| Phase and preserved foundation | Documentation | Source anchors under `apps/ai_system/src/savora_ai/` |
|---|---|---|
| 1: declarations, complete hard-check coverage and aggregation | [Contract decisions](member2_contract_decisions.md) | `schemas/knowledge.py`, `schemas/reasoning.py` |
| 2: focused graph/taxonomy and accepted synthetic KB | [Knowledge graph](member2_knowledge_graph.md) | `schemas/knowledge_base.py`, `core/reasoning/kb.py`, `graph.py`, `taxonomy.py` in that core directory |
| 3: authoritative manifests, fact resolution and PASS-only filtering | [Rule filtering](member2_rule_filtering.md) | `schemas/candidates.py`, `schemas/filtering.py`, `core/reasoning/manifest.py`, `filtering.py` in that core directory |
| 4: exact composition/preparation/fixed configuration and deferred DAY/WEEK checks | [Combination constraints](member2_combination_constraints.md) | `schemas/combinations.py`, `schemas/combination_evaluation.py`, `core/reasoning/combinations.py` |
| 5: three-slot DAY derivation and chronological search | [Daily CSP](member2_daily_csp.md) | `schemas/daily.py`, `schemas/daily_solver.py`, `core/reasoning/daily.py`, `day_checks.py` in that core directory |
| 6: seven DAYs/21 slots, WEEK derivation and verified finite search | [Weekly CSP](member2_weekly_csp.md) | `schemas/weekly.py`, `weekly_evaluation.py`, `weekly_search.py`, `weekly_solver.py` in that schema directory; `core/reasoning/weekly.py`, `week_checks.py`, `weekly_search.py` |

Source inspection confirms the actual public weekly entry points are
`build_week_check_manifest`, `evaluate_weekly_trial` and `solve_weekly_plan` in
`savora_ai.core.reasoning.weekly`. The architecture's broad `solve_week` name is
not a reason to rename the implemented API. `WeeklySolveResult` and
`WeeklySearchState` remain unevaluated declarations. Only
`ComputedWeeklySolveResult` provides a verified search outcome. The supplied-trial
`WeeklyTrialEvaluation` also leaves search completeness unevaluated.

## 1. Compatibility and a separate v2 boundary

Preserve every Phase 1-6 public signature, DTO, accepted policy token, policy
selection rule, failure/UNKNOWN semantic, original-JSON ingress and v1 result
verification. Do not broaden an old literal allowlist or retrofit heuristic
behavior into `solve_weekly_plan`. Existing callers continue to get chronological
`FIRST_FEASIBLE` v1 behavior by default. No automatic dispatch or fallback to v2.

The current v1 boundary is explicit:

- `computed-weekly-solve-result.v1` and
  `synthetic-chronological-weekly-search.v1` identify the computed result/search.
- `weekly-coverage.v1` identifies its ordered certificate. Its `DAY`/`LEAF`
  paths index the original canonically sorted domains in chronological order;
  preparation stamps reconstruct unary exclusions, and DAY failures cover suffixes.
- `schemas/weekly_solver.py` replays `core/reasoning/weekly_search.py::_execute`
  from retained validated inputs and compares the full certificate, diagnostics,
  outcome and witness. This is authoritative replay of the same kernel, supported
  by independent test oracles; it is not a separately implemented solver.

Add an explicitly selected v2 weekly search/result/proof boundary. Reuse validated
v1 declarations and rule semantics only where their invariants actually hold.
New execution events must represent arbitrary selected slot identities, rather
than pretending MRV is a chronological prefix. Schema and policy discriminators
must reject cross-version proofs, even after rehashing or changing a version label.
A v2 certificate is never a v1 certificate; a v1 certificate is never v2 evidence.
Any future adapter must recompute and verify the target protocol, with explicit
review, rather than cast, relabel or silently migrate it.

Synthetic attribute policy versions such as `synthetic-attributes.v2` describe
existing fact admission, not the new search protocol. Preserve all earlier
v1/v2/v3-combination/v4-day/v5-week selection semantics and every other Phase 1-6
token. Introducing search v2 does not authorize a fact-policy upgrade.

## 2. Traversal and independently checkable proof obligations

Each new strategy requires an explicit application-owned, versioned allowlist.
Unknown policy/schema tokens reject; caller-defined evaluators, scope subsets,
arbitrary pruning callbacks or claimed eligibility cannot supply authority.
Start with chronological v2 before preparation reuse, forward checking,
incremental derivation or MRV. Keep an unoptimized reference for comparison.

Every removed value or pruned subtree must have independently checkable evidence
that **every completion it removes contains a known failure** under the exact
accepted inputs and mandatory rules. A verified unary failure can refute every
completion containing that value; a completed DAY failure covers only extensions
with that exact day's assignments. A future bound must be conservative over all
remaining original alternatives, registered attributes and exact measurement
bases, with an operator-specific proof of impossibility. Independent lower/upper
bounds are necessary tests, never a proof of joint feasibility. Unsupported
predicates or unavailable bounds do not authorize pruning.

UNKNOWN is not FAIL and cannot authorize pruning. Missing/incomplete values cannot
be zero, guessed extrema, a false applicability condition or an empty domain.
UNKNOWN branches remain in coverage unless another independently established
failure refutes all their completions. Known FAIL still dominates UNKNOWN in the
same hypothesis. Evidenced NOT_APPLICABLE resolves its check while its predicate
status stays UNKNOWN; unknown dependencies still dominate local false conditions.
Empty mandatory inventories never become implicit PASS.

The v2 proof declaration task must specify at least these reconstructible events
and bindings. Names/field shapes are proposals, not existing DTOs:

| Obligation | Required retained or independently reconstructible content |
|---|---|
| Input identity | Exact request; independently selected source/context/profile/candidates/KB; graph, taxonomy, catalogue and check-catalogue pins; complete accepted manifests and rules; preparation/configuration/measurement evidence and policy versions |
| Preparation | Canonical original slot domains, every original option identity/revision/digest, prerequisite evaluations and reuse dependencies; source options outside a domain cannot silently enter it |
| Strategy and selection | Versioned strategy, deterministic tie-breaks, selected `(week, day, date, slot)` identity at every decision, chosen original option, current partial assignment, remaining domains and reproducible ordering basis |
| Pruning | Exact removed values/subspace, applicable rule and known failure, supporting facts/bounds/contributors, dependency state and enough derivation to recompute the entire exclusion |
| Leaves and coverage | Complete trial identities, all recipe/combination/DAY/WEEK obligations, known failures and surviving unknowns; exhaustive partition into evaluated leaves, justified exclusions and unexplored frontier |
| Frontier | Actual selected slot identities, original-domain indices/identities, sibling cursors and remaining options, including interrupted preparation/propagation; no gaps, duplicate coverage or invented exhaustion |
| Accounting | Ordered event sequence, node/propagation/evaluation/cache work, execution and verification charges, proof reservations, checkpoints and exact stop reason, outcome and optional full witness |

The verifier must revalidate original inputs, compare independently selected pins,
rebuild complete manifests, recompute prerequisite/fact/predicate truth and verify
selection/pruning/coverage/accounting against the original domains. It must not
accept caller-supplied hashes, PASS labels, counters, exhaustive flags, sampled
diagnostics or a reduced manifest as proof. Ordered event hashing must retain
order; the existing unordered snapshot digest cannot establish traversal order.
Replay may be used, but acceptance must check every exclusion and frontier
obligation; independent small-domain oracles remain a separate correctness check.
Matching unsigned hashes establish integrity relative to selected inputs, not
source authentication, reviewer authority or entitlement to a saved plan.

Preparation reuse is request-local and keyed by all relevant validated releases,
context, candidates, rules and option/preparation/measurement dependencies. No
caller-prepared PASS or cross-request/global authority cache. Incremental facts
must equal full derivation with identical evidence and support reversible rollback;
completing a DAY means all its three actual slots are assigned, regardless of DFS
depth. MRV operates only on soundly retained domains. Ties and value ordering are
deterministic. Observed history remains separate from provisional assignments;
Transformer ordering needs a separately agreed Member 1 interface and cannot
change eligibility or manufacture options, portions or nutrition.

### Outcomes and resource accounting

Preserve the existing four semantic outcomes in the additive boundary:

| Outcome | Required evidence |
|---|---|
| FEASIBLE | Complete FIXED 21-slot witness, every prerequisite and mandatory DAY/WEEK check resolved successfully, with output proof verification completed |
| INFEASIBLE | Entire supplied finite-domain space covered by known failures or sound exclusions, with no surviving unrefuted unknown |
| INSUFFICIENT_DATA | Complete coverage, no feasible witness, at least one unrefuted unknown hypothesis |
| TIMEOUT | A required preparation, search, propagation, evaluation, proof or verification operation cannot complete within its resource/deadline bound |

INFEASIBLE is relative to supplied finite domains, not all possible catalogue meals.
MRV/value ordering can change the first feasible witness and budget-limited
TIMEOUT behavior. No global optimum or identical first witness is promised for
different strategies. A partial witness or search success lacking required final
verification cannot be returned as FEASIBLE.

Keep v1 accounting unchanged: logical assignment visits count as nodes; option,
DAY, WEEK and semantic predicate capacities reserve execution **and** output
replay. For `m` referenced options, two passes currently perform `2*m` combination
calls and `2*(1+m)` recipe batches. The 150 option-evaluation ceiling permits at
most 75 distinct prepared options under that reservation. FIFO DAY memo eviction
can require more evaluations and cause TIMEOUT without changing logical domains.

V2 must explicitly define execution work, verification work and reservations for
each new event, including propagation, bound computation, incremental updates and
cache validation. Preparation reuse may reduce actual work; it cannot hide it or
provide free verification. Publish counter meanings before comparing strategies;
preserve existing ceilings unless a separately reviewed v2 policy changes them.
Reserve mandatory proof records/bytes before their work. Diagnostics may be sampled;
coverage may not. Proof exhaustion is TIMEOUT, even at a full assignment.

Proof reservation, actual encoded proof size, full result size, cache storage and
process memory are different metrics. V1 `proof_bytes` is conservative certificate
reservation, not RSS or the whole envelope. Preserve strict zero/exact-budget
behavior: consuming the last permitted unit can finish successfully only when no
required work remains. Cache eviction must never discard alternatives. Original
JSON remains bounded at 1 MiB/depth 64 through `validate_contract_json`; no silent
truncation or bypass of strict ingress to fit a proof. Invalid structure remains a
validation error even at zero budget, rather than becoming a search verdict.

Deadlines remain cooperative monotonic checkpoints, not interruption guarantees.
Output verification must be budgeted and timed; exhaustion there yields TIMEOUT
and withholds the witness. Record search-stage termination separately from
verification-stage expiry. Clock observations alone cannot authorize a success.

## 3. Saved-plan substitution security boundary

Member 3 owns authenticated saved-plan access, authorization, revision selection,
freshness/revocation, orchestration and persistence. Member 2 performs pure
validation/selection over independently supplied validated saved-plan material;
it performs no database/HTTP/ORM/authentication/transaction work. A proposal cannot
populate its own independent saved-plan/source/KB/context argument positions.

The future Member 3 handoff must bind the authorized plan ID, exact effective
snapshot ID/revision/digest, original complete 21-slot assignment, original request
and source/context/profile/target/KB releases, and supporting configurations,
preparations, measurements and evidence. A matching digest alone proves neither
plan ownership nor current revision. Member 2 compares the proposal's expected
identity against this independent material; stale, conflicting or malformed
identity is a validation rejection, never permission to load a latest version.
The exact external DTO and revision authority are **PENDING** joint agreement.

Exactly one target `(week, day, calendar date, meal slot)` assignment changes.
The other 20 assignments are locked in their entirety: recipe/component
multiplicity, combination and candidate snapshots/versions/digests, fixed
configuration, quantities/units, preparation and portion/basis references,
measurement values/completeness/evidence, suitability and source bindings. A
different configuration or preparation of the same recipe is still a change.
A no-op target does not satisfy a successful swap. New result/trace identities
may be derived, but must map to the unchanged original locked payloads rather
than rewrite their provenance or silently rebuild them from a current catalogue.

`KnowledgeWorkflow.PLANNED_SWAP` exists and Phase 3/4 retain its later obligations.
However `schemas/daily.py::_DailySourceContent.validate_source` explicitly accepts
only WEEKLY_PLAN; weekly sources wrap that daily source. Existing weekly/daily
requests cannot be relabelled into valid swap requests. Phase 7.3a needs dedicated
swap declarations and a versioned workflow/context bridge. It must retain the
original saved snapshot plus a separately validated PLANNED_SWAP context, select
the complete swap manifests from the accepted KB and verify any context-bound
source mapping without changing v1 workflow acceptance. A copied weekly context
with a new workflow token, recomputed digest or unchecked constructor is not a
bridge and does not establish source authority.

Initial scope requires unchanged profile, nutrition-target and KB versions from
the saved plan, with exact original supporting release bindings retained. Any
change needs an explicitly specified and independently verified compatibility
bridge, including full applicable-rule revalidation of locked slots; no bridge
is currently implemented or approved. Without it, reject an incompatible request
or report unavailable required evidence as insufficient data; never assume that
the old plan's PASS remains valid under a new version.

Member 3's eventual flow follows architecture section 4.4: retrieval → rules →
Member 1 composition → ranking of eligible IDs → Member 2 portion/assignment
feasibility → final validation → Member 3 transactional persistence. Pure swap
validation checks one supplied replacement; bounded selection searches only an
explicit independently supplied replacement domain, with the 20 locks fixed.
Replacement candidates and their exact source/preparation/measurement authority
must also be independently supplied; adding them cannot rewrite locked sources.
No composer/ranker is implemented by Member 2. Standalone craving continues to
bypass composition/CSP and is not a shortcut for planned substitution.

The replacement must pass every applicable PROFILE/RECIPE/COMBINATION prerequisite
and all applicable DAY and WEEK requirements of the resulting full plan, including
hard dietary/allergy/clinical restrictions when supported by approved integration.
Recompute affected aggregates and weekly recipe presence; do not merely subtract
from a scalar target or trust the saved plan's prior PASS. Reuse for unaffected
days requires exact proven dependency equivalence. Locked-slot failures cannot be
repaired by changing another meal. This phase supplies synthetic checks only.
An unsupported applicable obligation blocks VALID; it cannot be omitted to fit
the synthetic registry.

### Proposed swap outcomes (not existing API tokens)

| Outcome | Meaning and consumer obligation |
|---|---|
| VALID | Exactly one changed target and 20 exact locks; independently bound sources/versions; complete resulting-plan obligations and final proof verified. This is validation evidence for Member 3, not authorization or a persistence action. |
| REJECTED | The supplied replacement violates a known requirement or the one-target/lock contract (including no-op), or a fully covered explicit replacement domain contains only known failures. State the reason and precise candidate/domain scope. |
| INSUFFICIENT_DATA | Missing required independent saved material, unsupported version-compatibility evidence or surviving unrefuted UNKNOWN prevents a decision after all required bounded work finishes. Never treat missing authority as PASS. |
| TIMEOUT | Required validation/selection/proof/verification is unfinished due to a declared limit. No partial VALID or exhaustive rejection. |

Malformed DTOs, stale/conflicting independently pinned revisions and unsupported
protocol tokens remain boundary validation errors; they are not global CSP outcomes.
Map these to backend transport errors only after Member 3 agrees the contract.
REJECTED is not global INFEASIBLE: rejecting one replacement says nothing about
another; exhausting a scoped replacement domain says nothing about the full
weekly search space, other catalogue choices or a plan with relaxed locks.
If any replacement remains unrefuted UNKNOWN, exhausted selection yields
INSUFFICIENT_DATA rather than REJECTED. Resource interruption yields TIMEOUT.

Member 3 must recheck authorization and compare the expected revision at write
time to prevent concurrent/stale overwrites, then transactionally retain before/
after snapshots and update the effective plan. Member 2's result must bind the
same expected revision; VALID cannot bypass this final check. The external
compare-and-write/error contract remains **PENDING**, with no persistence changes
authorized here. No ratings, consumption, feedback, craving history or retraining.

## 4. Synthetic scope and excluded integration

Phase 7 operates on application-registered synthetic attributes only, preserving
the recipe/combination/DAY/WEEK ownership registries and admission rules. Existing
DAY facts are `synthetic_day_complete` and `synthetic_day_quantity_total`; WEEK
facts are `synthetic_week_complete`, `synthetic_week_quantity_total` and
`synthetic_week_max_recipe_slot_occurrences`. Integer mg examples and numeric
representation bounds have no clinical/nutritional meaning. Missing measurements
remain UNKNOWN; quantity contributes once per slot and canonical recipe presence
counts once per recipe per slot, even across configurations or duplicate components.

Excluded: real nutrition vectors, clinical thresholds/activation, Food.com/USDA
normalization, recipe-specific conversion integration, generated portions, source
authentication integration, production providers, backend/frontend endpoints,
database work and automatic training. Future ranking integration needs separate
agreement; no learned-ordering capability is implied by this plan. No production
safety, nutrition readiness, medical suitability or performance guarantee is allowed.

## 5. Evaluation protocol

7.1b establishes a repeatable v1 baseline before changes. Compare v2 chronological
against it, then ablate one optimization at a time and compare the final variants.
Use exactly equal independently selected recipes, source snapshots, context,
profile/target/KB and manifests, original slot domains/options, fixed measurements,
rule thresholds, criterion, budget meanings and stopping conditions. Record full
input pins plus policy, implementation revision, Python/platform, benchmark case,
cache mode, repetition count and any ordering seed. Default ordering is deterministic.
Use equal semantic problem data when comparing distinct protocols; do not pretend
their serialized envelopes or certificate formats are identical.

Maintain two comparison tracks: small fully covered problems with sufficient
budgets to test semantic outcomes, and equal-limit bounded workloads that measure
timeouts and useful completed results. Resource-limited differences are observations,
not automatically correctness failures. Never discard TIMEOUT/UNKNOWN runs or count
a partial witness as success. Keep preparation cold by default; any warm/reuse
experiment must use validated dependencies and report its mode separately.

Preserve the independently constructed finite-product checks in
`tests/test_weekly_solver.py::oracle` (literal 2/5 arithmetic) and
`tests/test_member2_phase6_integration.py::literal_oracle` (independent 3/7/11
fixture, daily totals and canonical recipe presence). Future oracles use their
own small-domain enumeration/arithmetic/expected outcomes, not production search,
pruning, predicates, aggregation, ordering or hashing as their truth source.
Cover asymmetric and empty domains, cross-day recovery, all outcomes, known FAIL
with UNKNOWN, missing measurements, repetition/configuration identity, boundaries,
cache eviction and proof interruption. Extend to exhaustive one-target substitutions
with 20 locks. No full 21-slot Cartesian stress materialization is required.

Outcome equivalence means equal semantic verdicts when required work finishes;
witness equivalence means the same complete slot/configuration assignment.
Chronological v2 must match v1's first witness under identical ordering and
sufficient budgets. MRV or a new value order may select a different verified
witness. Compare its constraint satisfaction independently, not its equality to
the v1 first witness. Do not demand matching timeouts or counters across strategies.

| Required measurements | Recording rule |
|---|---|
| Search/outcome | Strategy/criterion; FEASIBLE/INFEASIBLE/INSUFFICIENT_DATA/TIMEOUT and rates; verified witness identity; exhaustive flag, known failures, unknown hypotheses, nodes, backtracks, pruned subtrees/values, completed leaves, propagation/bound/incremental work; hard violations and declared objective (no optimality claim) |
| Evaluation | Option/combination, recipe batches/candidate decisions, DAY, WEEK and semantic predicate work, split into execution and verifier work with total/reservation semantics; preparation/derivation counts and reuse hits/misses |
| Proof/verification | Event/record counts, conservative reserved bytes, actual encoded certificate and whole-result bytes, verifier work/time, accepted/rejected proofs and interruption reason; sampled diagnostics counted separately |
| Memory/cache | Peak Python traced allocation, optional process RSS labelled separately, required working state/frontier size, cache high-water/hits/misses/evictions and configured ceilings; instrumentation mode and overhead |
| Timing/limits | Input/manifest/compilation/option preparation, algorithmic search, output proof verification, serialization and end-to-end time; configured limits, actual use/reservations, checkpoint and stage/reason of timeout |

Use disjoint timing intervals where possible; label inclusive substage times and
never add overlapping categories. Input fixture construction/imports are outside
algorithmic timing and separately disclosed. V1 preparation already includes input
validation/compilation; search includes evaluation/evidence construction. Verification
is always enabled for accepted results. Report repetitions and variability without
replacing actual measurements with historical Phase 6 numbers. Memory profiling runs
are separate from normal timing runs because instrumentation changes latency.
Any required resource exhaustion is TIMEOUT, including proof or verifier capacity.

Adversarial acceptance must reject version relabelling, wrong slot selections,
rehashed omissions/duplicates/reordered events, missing original alternatives,
unsound/UNKNOWN pruning, false counters/exhaustion, stale releases, transplanted
preparation/measurement evidence and changed locked slots. Preserve original-JSON,
hostile-container, unchecked-instance and forged-enum defenses. No speedup claim
is valid if it omits preparation, final verification or required evidence costs.

## 6. Approved work sequence and proposed locations

The sequence below fixes implementation order for future scoped tasks. It does not
authorize their execution in 7.1a or establish team approval of shared contracts.
All new names and paths in this table are **PROPOSED, NOT IMPLEMENTED**. Paths are
relative to `apps/ai_system/` unless prefixed with `docs/`. Existing v1 files remain
the compatibility reference; any later private refactor needs equivalence evidence.

| Task | Future deliverable / gate | Proposed names and paths |
|---|---|---|
| 7.1b — Baseline benchmark harness | Reproducible bounded v1 cases, independent oracles, resource definitions and separate preparation/search/verification/memory measurements; no search change | `src/savora_ai/evals/member2_phase7_baseline.py`, `tests/test_phase7_baseline.py`, `docs/member2_phase7_evaluation.md` |
| 7.1c — Strict v2 proof declarations | Specify strict version-disjoint strategy/event/domain/frontier/accounting declarations and reject forged/malformed evidence; declarations alone authorize no computed outcome | `WeeklySearchCertificateV2`, `WeeklySearchPolicyV2` in `src/savora_ai/schemas/weekly_search_v2.py`; `tests/test_weekly_v2_contracts.py` |
| 7.2a — Independently verified chronological v2 | Retain chronological order, full prerequisites/coverage/replay and resource accounting; verify v1 outcomes/first witnesses and independent small-domain truth before optimizing | `solve_weekly_plan_v2` in `src/savora_ai/core/reasoning/weekly_v2.py`; kernel `weekly_search_v2.py` and verifier `weekly_proof_v2.py` in that directory; `ComputedWeeklySolveResultV2` in `src/savora_ai/schemas/weekly_solver_v2.py`; `verify_weekly_search_v2` in the proposed verifier |
| 7.2b — Preparation reuse | Request-local validated dependency-bound reuse with unchanged decisions/evidence, verifier authority and honest reduced work counts | `src/savora_ai/core/reasoning/weekly_preparation_v2.py`; `tests/test_weekly_preparation_v2.py` |
| 7.2c — Sound forward checking | Registered predicate-specific conservative bounds/exclusions, full subtree evidence and UNKNOWN retention, compared to exhaustive oracles | Proposed v2 kernel/verifier and `tests/test_weekly_forward_checking_v2.py` |
| 7.2d — Incremental derivation | Exact dependency-aware updates/rollback equal full DAY/WEEK facts, statuses and evidence under arbitrary slot order | Proposed v2 kernel/verifier; `tests/test_weekly_incremental_v2.py` |
| 7.2e — Deterministic ordering and MRV | Explicit versioned strategies, stable slot/value tie-breaks, correct selected-slot events/frontier; independently valid possibly different witnesses | `WeeklySearchPolicyV2` and proposed v2 kernel/verifier; `tests/test_weekly_ordering_v2.py` |
| 7.3a — Saved-plan and workflow foundation | Independently pinned saved material, exact lock/revision semantics and dedicated PLANNED_SWAP bridge; external Member 3 handoff remains an agreement gate | `SavedPlanMaterial`, `PlannedSwapRequest` in `src/savora_ai/schemas/planned_swap.py`; bridge in `src/savora_ai/core/reasoning/planned_swap.py`; `tests/test_planned_swap_contracts.py` |
| 7.3b — Pure swap validation | Validate one replacement against exact snapshot, 20 locks and complete resulting-plan obligations; verify all proposed outcomes without I/O | `validate_swap`, `SwapValidationResult` in the proposed swap core/schema modules; `tests/test_swap_validation.py` |
| 7.3c — Bounded replacement selection | Search an explicit finite replacement domain only; proof-backed scoped rejection/UNKNOWN/TIMEOUT and no hidden lock relaxation | `select_swap_replacement` in proposed swap core module; `tests/test_swap_selection.py` |
| 7.4 — Comparative evaluation | Equal-input baseline/ablation/full-strategy and swap comparisons, independently checked correctness, complete costs and negative results | `src/savora_ai/evals/member2_phase7_comparison.py`, proposed evaluation document |
| 7.5 — Full compatibility and security audit | Phase 1-6 preservation, v1/v2 isolation, pruning/frontier/accounting attacks, workflow/version/lock/concurrency handoff audit and relevant full checks | `tests/test_member2_phase7_integration.py`, `docs/member2_phase7_audit.md` |

Candidate future policy/schema spellings, also **PROPOSED, NOT ACCEPTED TOKENS**:
`computed-weekly-solve-result.v2`, `weekly-coverage.v2`,
`synthetic-chronological-weekly-search.v2`,
`synthetic-forward-checking-weekly-search.v2` and
`synthetic-mrv-weekly-search.v2`. Exact feature combinations, version dispatch,
event fields and resource declarations must be specified in 7.1c before use.
`validate_swap` is an architecture deliverable name, not an existing callable.
No OpenAPI/TypeScript contract is introduced by these proposals.

## 7. Pending team decisions and handoffs

| Pending decision | Owners / consequence |
|---|---|
| Saved-plan authority, effective revision/snapshot identity, independent material DTO, write-time concurrency check and error mapping | Members 2/3; required before real saved-plan integration; Member 3 retains authorization/persistence |
| Dedicated PLANNED_SWAP context/source bridge, complete workflow manifests and version compatibility evidence | Members 1/2/3 as their data is involved; no relabelling or version drift by default; initial unchanged-version restriction remains |
| Canonical recipes/compositions, preparation/fixed-configuration/measurement/target authority, release identity and precision | Members 1/2/3; synthetic fixtures do not supply production data or nutrition integration |
| Final public API/DTO names, transport exposure/size and trust/loading/revocation policy | Members 2/3 with Member 1 for consumed ranking/data; no client input becomes an independent source |
| Resource ceilings, supported strategy combinations, first-feasible versus bounded preference objective, ranking integration and observed-history policy | Joint review under architecture section 15; retain first-feasible synthetic baseline until separately decided |
| Clinical sources/applicability/approval, completeness/conversion standards, catalogue, meal templates and cuisine semantics/rounding | Existing architecture section 15 decisions remain pending; no production readiness inferred |

These are dependencies to record, not fictional approvals. Member 2-only baseline
measurement with existing synthetic interfaces can proceed without resolving
production contracts. Swap foundation may be specified/tested synthetically, but
external integration cannot proceed until the relevant contracts are agreed.

## 8. Phase 7.1a completion and Phase 7.1b gate

Validate the new documents against the baseline source and architecture: explicit
v1/v2 isolation, per-subtree known-failure proofs, UNKNOWN retention, independently
selected inputs, exact one-slot swap/20 locks, dedicated workflow bridge, version
restriction, complete accounting and synthetic-only claims. Check relative links,
`git diff --check`, whitespace in both new untracked files, and
`git status --short`. Confirm only the two new Member 2 Markdown files exist in
the change set, the index is unchanged and branch/HEAD remain the preflight values.

No Python, tests, configurations, dependencies, original Phase 1-6 documentation,
Member 1/3 files, shared contracts or other worktrees may change. Tests and runtime
lint/typecheck/build are omitted for this documentation-only slice and must not
be reported as run. This plan records no new benchmark observations.

Readiness: Phase 7.1b is specified and can be the next separately requested task
after this documentation review. It begins with the current v1 baseline; it does
not require a working v2 or swap implementation. Stop after 7.1a validation/report;
do not start the harness, stage, commit, push or open a PR.
