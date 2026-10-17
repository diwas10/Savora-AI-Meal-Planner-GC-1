# Member 2 Phase 5, Prompt 1: DAY admission and daily contracts

Status: 15 October 2026, provisional local synthetic contracts. The user approved
exactly three slots, complete combinations, supplied FIXED configurations,
evidence-bound integer totals, permissive repetition unless an authoritative rule
restricts it, and deferred WEEK obligations. These are not production/team or
clinical approvals. This prompt implements declarations and admission only.

## Authority, scope and baseline

Reviewed AGENTS.md, the Member 2 Phase 1-4 handoffs and relevant implementation/tests,
and ARCHITECTURE.md sections 3-6, 8-9, 11, 13-15. Repository architecture remains
authoritative. The previously reviewed October PDF is a proposed team contract;
its future API/cuisine terminology does not rename repository interfaces.

Member 2 owns symbolic admission/contracts. Member 1 supplies composed candidates,
verified preparations/portions, measurement sources and explicit slot suitability.
Member 3 owns normalized context/profile, independent source/release selection and
future backend transport. AI contracts perform no database or network I/O.

Start checkpoint: branch `feature/member2-daily-csp`, HEAD
`63720ff540f65dd887897af1fca178f590547933`, no tracked or staged changes. The explicit
user-selected branch is retained despite the generic feat/ naming convention.
Existing Food.com/USDA untracked data and `phase1-security-fix.patch` are outside
scope. No EDA notebook is executed.

Baseline with existing dependencies (`uv run --frozen --no-sync`): Ruff lint and
format passed (109 formatted files), Pyright had zero errors/warnings, and all
3,290 pytest cases passed in 116.28 seconds. The sandbox could not access the uv
cache; approved escalated commands were used. No dependencies/lockfiles changed.

## Independently reproduced blocker and correction

Before production edits, the newly declared `test_day_owned_rule_admitted_and_deferred`
constructed its own graph, full workflow/scope catalogue and coverage, approved
ACTIVE ABSOLUTE CULINARY DAY rule, candidate and WEEKLY_PLAN context. It imports no
earlier test fixture or production hash/comparison helper as an expected-outcome oracle.
The rule was boolean EQ True on `synthetic_day_complete` with
`synthetic-context-enabled / 1` applicability. KB construction succeeded.

The unchanged Phase 4 baseline rejected manifest admission:

```text
test_day_owned_rule_admitted_and_deferred: FAILED
build_expected_check_manifest -> _mandatory_checks -> _validate_rule_policy
ValidationError: SyntheticRulePolicy
Value error, unsupported synthetic required attribute
1 failed in 0.23s
```

Before correction, `_validate_rule_policy` consulted the recipe registry for this
new attribute before scope partitioning. The extension now admits the complete
DAY definition as deferred, with no recipe-fact ownership substitution. The same
test passed immediately after the change (1 passed in 0.17s). Full upstream tests
also verify that recipe and combination decisions remain quantity-independent,
DAY checks do not execute upstream, and WEEK definitions survive unchanged.

## Versioned admission policy

New upstream manifest attribute policy: `synthetic-attributes.v4-day`. It is
selected iff the workflow's mandatory obligations contain registered DAY facts.
It can coexist with existing recipe and combination obligations. Rehashed
manifests carrying DAY names under older tokens, or v4 without DAY names, reject.
Existing v1 scalar, v2 derived-recipe and v3 combination selection/meaning remain
unchanged when no new DAY facts occur. Approval admission remains
`synthetic-hard-rule-admission.v1`; workflow/evaluator/identity policies are unchanged.

The fixed application-owned registry lives in schemas/filtering.py, separately
from `_ATTRIBUTES` and `_COMBINATION_ATTRIBUTES`:

| Attribute | Scope/domain | Value | Operators | Unit |
|---|---|---|---|---|
| synthetic_day_complete | DAY / CULINARY | exact bool | EQ, NE | None |
| synthetic_day_quantity_total | DAY / CULINARY | integer 0 through 2**63-1 | LT, LE, GT, GE, EQ, NE | mg |

Both require SYNTHETIC, ACTIVE, ABSOLUTE, APPROVED definitions and exact
`synthetic-context-enabled / 1` applicability. Required facts may include the
two DAY attributes and existing registered PROFILE/CONTEXT prerequisites. RECIPE,
ingredient, combination-owned and arbitrary names cannot supply DAY requirements.
The existing descriptor validator retains exact condition/dependency admission.
Unknown attributes, wrong scope/domain/operator/unit/applicability, float/bool
numeric thresholds and unapproved mandatory rules reject. Inactive inventory may
remain archived but cannot appear as a mandatory check. No default threshold exists.

The integer maximum is a representational/resource bound, not a nutrient limit.
No clinical domain predicate is added. No Phase 1/2 file or Phase 3/4 public
function signature changes. Existing old-vocabulary DAY/WEEK deferred declarations
retain their earlier upstream behavior; the new daily manifest only admits its
explicit DAY vocabulary and rejects unsupported legacy DAY predicates.

## Exact DTO surface

Import directly from `savora_ai.schemas.daily`. All models inherit strict,
frozen, recursively revalidated, extra-forbidden, camelCase `_ContractModel`
semantics. Nested collections are tuples. Canonical enum identity and synthetic
evidence consistency are checked throughout new records. Local evidence collections
reject duplicates; identical references may be reused across different records.

The following are actual fields, beyond the named default schema/policy tokens.
Versions are opaque nonblank strings; IDs use existing opaque-ID syntax; digests
are 64 lowercase hexadecimal characters.

| DTO | Fields |
|---|---|
| MealSlot | BREAKFAST, LUNCH, DINNER |
| DailyOutcome | FEASIBLE, INFEASIBLE, INSUFFICIENT_DATA, TIMEOUT; reserved vocabulary, no outcomes computed here |
| DailySourceReference | source_id, version, content_digest |
| MealOptionReference | schema_version=meal-option-reference.v1; option_id, combination_id, combination_version, snapshot_id, snapshot_version, combination_digest, portion_state, nullable portion_configuration_id/version |
| MealSlotSuitability | schema_version=meal-slot-suitability.v1; option, source, slots, complete, evidence |
| FixedMealMeasurement | schema_version=fixed-meal-measurement.v1; measurement_policy_version=synthetic-fixed-meal-measurements.v1; option, source, attribute=synthetic_meal_quantity_total, value, complete, unit, measurement_basis, aggregation_level=MEAL_TOTAL, components, basis_reference, evidence |
| DailyMealOption | reference, combination: CombinationFacts, nullable suitability, measurements |
| DailySourceSnapshot | schema_version=daily-source-snapshot.v1; source_id, version, context: RuleContext, options, evidence, content_digest |
| DailySlotDomain | slot, options |
| DailyPlanningRequest | schema_version=daily-planning-request.v1; policy_version=synthetic-daily-contracts.v1; request_id, version, day_id, context_id/version/digest, expected_source, source: DailySourceSnapshot, domains, content_digest |
| AssignedMeal | slot, option |
| DailyAssignment | schema_version=daily-assignment.v1; request_digest, day_id, source, context_digest, slots, content_digest |
| DayMeasurementContribution | slot, measurement: FixedMealMeasurement |
| DayFact | schema_version=day-fact.v1; request_digest, assignment_digest, day_id, source, context_digest, observation: FactObservation, nullable measurement_basis/basis_reference, contributions |
| ExpectedDayCheckManifest | schema_version=expected-day-check-manifest.v1; day_policy_version=synthetic-day-policy.v1; stage=DAY; request, knowledge: KnowledgeBaseSnapshot, required_checks, deferred_checks, content_digest |
| ConstraintDiagnostic | request_digest, stage (CONTRACT/RECIPE/COMBINATION/DAY/SEARCH), code, message, status: RuleStatus, nullable slot/option/rule_reference, evidence |
| DailyPlanningResult | schema_version=daily-planning-result.v1; plan_feasibility=NOT_EVALUATED, weekly_feasibility=NOT_EVALUATED; nullable outcome, manifest, nullable assignment, facts, diagnostics |

Supporting DTOs isolate option/source/domain/occurrence references without changing
existing enums or duplicating recipe, preparation, quantity or evidence models.
No new package-level export or HTTP/OpenAPI/TypeScript contract is introduced.

## Identity, slot and portion binding

Every request and structural assignment contains each of the three slots exactly
once. Domain order is declarative; slot-to-option association remains part of the
digest. Each domain has 0-50 options; a source contains 0-150 options; at most 50
options/configurations are declared for one combination ID; at most 32 component
occurrences are admitted per meal. These are explicit synthetic resource limits.
Representational limits do not imply that a large request fits the separate raw
JSON ingress byte/depth bounds or satisfies a production latency requirement.

Option IDs are unique in a source and within a domain. Different option IDs cannot
alias the same exact combination snapshot. Reusing an option across slots is
permitted. Domain references must equal actual source option references, including
combination/content/snapshot/configuration revisions and digest. A source verifies
each combination against its complete normalized context and KB/graph/catalogue/
taxonomy/check-catalogue pins. Its context includes profile ID/version and workflow;
only WEEKLY_PLAN enters these daily contracts. No craving or swap behavior is added.

Repeated recipe occurrences remain valid and retain distinct component IDs.
Conflicting recipe snapshots, combination snapshots, fixed configurations or
preparation definitions under reused exact identities reject across the source.
Display names/cuisine labels grant no slot suitability or identity fallback.

UNASSIGNED options require both configuration pins absent; FIXED options require
both present and equality with the complete CombinationFacts. UNASSIGNED options
may appear in domains but cannot enter AssignedMeal/DailyAssignment. No quantities
are generated, filled with defaults or partially assigned.

DailyAssignment is a complete structural hypothesis. DailyPlanningResult checks
its exact request/source/context/day and domain membership. Neither establishes
recipe/combination eligibility, suitability, DAY truth or feasibility in Prompt 1.
No implicit repetition prohibition or cuisine policy is supplied.

## Measurements and suitability

The only measurement is a whole-meal `synthetic_meal_quantity_total` in mg on
`FIXED_PORTION_TOTAL`. Values are strict integers from zero through
`(2**63-1)//3`, or None. Three maximum admitted meal totals therefore fit the
declared daily integer representation. True/False, floats (including 0.0), strings,
negative and overflowing values reject. Complete requires a non-null value;
incomplete non-null values remain incomplete; zero is a real value.

Every measurement pins the exact option, full component occurrences, recipe
snapshots, preparation and quantity/basis/portion evidence. Its components must
match the source combination. It also carries an independent external source
ID/version/digest, total-basis reference and nonempty source/gap evidence. Reused
external source ID/version pairs must agree on digest. Declarations cannot name
the enclosing daily source as their own external source.

At most one such total is allowed per option. Ingredient totals cannot be supplied
as another aggregation level; no component/ingredient and meal totals are added
together. GI, ratios, percentages and classification labels are unsupported.
There is no raw/cooked, serving/grams, volume/mass, density or unit conversion.
An evidenced per-fixed-configuration integer total is supplied by upstream, not
derived by this module. Its evidence metadata is retained, not fetched/authenticated.

Suitability names exact supported MealSlot members for that exact option, plus
completeness, external source pin and nonempty evidence. Missing suitability,
incomplete empty slots and complete empty slots remain distinct. A source can
retain an unsuitable/unknown option for diagnostics; request validation never
claims domain membership proves suitability. Prompt 2 must exclude unresolved
or incompatible options before any feasible result.

DayFact wraps existing FactObservation with daily ownership. The numeric fact
requires DAY_FIXED_TOTAL and basis evidence; a complete declaration requires
one complete FixedMealMeasurement contribution for each slot. The result envelope
matches every contributor to the selected option's exact source measurement.
Boolean completeness facts have no numeric basis or contributors. Missing numeric
facts have value=None/complete=False/unit=None; no zero is manufactured. This
prompt validates declaration shape/bindings only: it does not sum contributions,
compare a predicate or authenticate a declared day observation.

## Manifest, digests and trust

ExpectedDayCheckManifest embeds the supplied KB and request. It verifies SYNTHETIC
KB acceptance fields against the normalized context, selects full exact DAY/WEEK
definitions from that KB's authoritative workflow cells and compares both complete
sets in canonical rule order. Existing KB validation enforces active inventory and
complete catalogue coverage. DAY rules use the new registry; applicability descriptor
conditions and dependency identities are admitted without executing them. Reduced,
substituted, unapproved or wrong-scope obligations reject even when rehashed.

WEEK definitions remain `deferred_checks`; no weekly predicate runs. Empty DAY
manifests are representable but never establish PASS. A missing mandatory catalogue
entry/coverage is invalid, distinct from a valid empty mandatory set.

DailySourceSnapshot, DailyPlanningRequest, DailyAssignment and
ExpectedDayCheckManifest share the validating factory:

```python
Snapshot.build(content, *, expected_digest=None) -> Snapshot
```

The inherited factory strictly revalidates original nested field storage, verifies
any supplied digest (including rejecting null), computes only an omitted digest,
and verifies an optional independent expected pin. Direct constructors/JSON require
the correct content_digest. The existing unordered canonical JSON/SHA-256 policy is
reused: camelCase keys, sorted mapping keys/unordered array encodings, ASCII escapes,
compact separators, scalar types and occurrence multiplicity retained. All present
snapshot collections are unordered declarations; no ordered graph witness paths
are hashed using this policy. Only the outer content_digest is excluded.

Hashes ignore declaration order but bind slot labels to their values. Moving a
different meal between slots changes the assignment digest. Embedded accepted
records retain source declaration order; semantic/digest determinism is not a
claim of universally byte-identical serialization or RFC 8785 compliance.

Matching hashes, self-consistent pins and SYNTHETIC/APPROVED labels are not
authentication. A caller can fabricate a completely rewritten unsigned release.
The request's embedded source is a declaration; future orchestration must compare
it with independently selected source/context/KB records, not promote request data
into trusted arguments. No production provider, source-content verification,
reviewer authentication or revocation service is implemented.

Original untrusted JSON must enter via
`validate_contract_json(Target, original_raw_json)`, including TypeAdapter collections.
Native model_validate_json/TypeAdapter round trips do not recover duplicate keys
already overwritten by a parser and remain unsupported for security-sensitive raw
ingress. Hostile containers, counterfeit enums, aliases/extras and malformed
unchecked model_copy/model_construct trees are revalidated before normalization.

## Prompt 2 handoff and limits

DailyPlanningResult is deliberately unevaluated: outcome must be None and both
feasibility markers remain NOT_EVALUATED. A non-null DailyOutcome is rejected,
including INFEASIBLE/TIMEOUT; no search has run. The enum reserves the agreed four
future outcomes. Prompt 2 must add a computed-result contract backed by actual
recipe/combination prerequisites, complete DAY evaluations and search diagnostics
before producing any of them. This is an explicit incomplete-stage boundary,
not a declaration that any structural assignment is feasible.

Prompt 2 still needs request-scoped validated preparation, real Phase 3/4 decision
reuse, independent upstream selections, slot admission, integer DAY aggregation,
supported applicability/predicate execution, complete traces and bounded daily
search. It must distinguish exhaustive infeasibility from insufficient evidence
and budget/deadline exhaustion; UNKNOWN cannot authorize a plan. Preserve WEEK
obligations and revalidate the computed result. Do not silently remove old-vocabulary
unsupported DAY checks or relax rules. Ranking, weekly search, swaps, solver-generated
portions, persistence, endpoints and UI remain separate later work.

Pending production integration: Member 1 canonical combination/portion IDs,
verified integer measurement provider and source/preparation semantics, explicit
slot metadata, approved conversion/precision policies and numeric targets;
Member 3 independently authenticated context/KB/source loading, freshness/revocation,
resource policy and backend error contracts; joint public interface and reviewed
clinical rule approval. No synthetic test quantity has clinical meaning.

## Verification and findings

The independent suite covers exact three-slot construction, empty and UNASSIGNED
domains, fixed-only assignments, source/context/release and configuration pins,
measurement/preparation/quantity transplants, units/bases, evidence duplicates and
conflicts, missing versus zero/False/empty observations, integer bounds, source/domain/
configuration limits, inactive/unapproved/unsupported rules, policy downgrade,
upstream Phase 3/4 compatibility, WEEK preservation, independent canonical hashes,
slot permutation versus reassignment, frozen DTOs, recursive unchecked/hostile input,
counterfeit enums and original JSON duplicate/alias/overflow/collection ingress.

The first expanded run found local duplicate evidence references were accepted by
the new nonempty-only check (1 failed, 116 passed). The new records now call existing
evidence validation as well as cross-record provenance validation. The independently
declared duplicate-evidence regression rejects after correction. Source/preparation
conflict and self-reference checks were added during local hardening. No pre-existing
Phase 1-4 public false-PASS defect is claimed by these contract findings.

Final verification on 15 October 2026 used the existing environment with
`uv run --frozen --no-sync`; no dependencies or lockfiles changed.

| Check | Result |
|---|---|
| Ruff check . | Passed |
| Ruff format --check . | Passed; 112 files already formatted |
| Pyright | Passed; zero errors/warnings |
| pytest -q | **3,440 passed in 121.87 seconds**; all 3,290 baseline cases plus 150 new independent cases |
| Architecture/import audit | Passed in full pytest, including every new local module; no forbidden dependencies/import cycles |
| Phase 1/2 and public compatibility | Phase 1/2 files, Phase 3/4 public signatures, combination evaluator/results and dependencies unchanged |
| Git/whitespace | No staged changes or whitespace errors; branch/HEAD unchanged; only five task files added/modified |

The duplicate-local-evidence issue is a corrected MEDIUM contract-validation finding;
it did not produce an evaluated PASS or feasible result. No unresolved in-scope
HIGH/MEDIUM finding is known after the regression suite and local review. External
source/provider authentication and clinical approval remain explicit integration
dependencies, not guarantees supplied by these contracts.

Created: schemas/daily.py, tests/test_daily_contracts.py (both under apps/ai_system
with the existing src/savora_ai layout), and this document. Modified only
schemas/filtering.py and core/reasoning/manifest.py for the scoped admission
extension. Existing untracked data and backup patch were left untouched.

Final branch: `feature/member2-daily-csp`. HEAD remains
`63720ff540f65dd887897af1fca178f590547933`. No staging, commit, push, merge, rebase,
reset, PR or branch change was performed. No solver, DAY predicate/numeric
evaluation, weekly planning, swap, ranking integration, endpoint or production
authentication was implemented.

Verdict: **READY FOR PHASE 5 PROMPT 2**, for the explicitly authorized synthetic
boundary only. Prompt 2 has not been implemented.

## Prompt 2: authoritative DAY evaluation and deterministic daily search

This section supersedes Prompt 1's statements that DAY evaluation/search are
future work. Prompt 1 DTOs and all Phase 1-4 public APIs remain unchanged. The
existing `DailyPlanningResult` is still an unevaluated handoff; computed outcomes
use the new `DailySolveResult` contract in schemas/daily_solver.py. This preserves
Prompt 1 callers rather than changing an unevaluated record into an authorization.

Verified start baseline: branch `feature/member2-daily-csp`, HEAD `63720ff`, all
five local Prompt 1 files present, Ruff/format clean, Pyright zero errors/warnings,
and **3,440 tests passed in 119.94 seconds**. Existing datasets/backup patch remain
outside scope. All quantities, source records and approvals below are fictional.

### Actual APIs and ownership

```python
from collections.abc import Callable
from time import monotonic

from savora_ai.core.reasoning.daily import build_day_check_manifest, solve_daily_plan
from savora_ai.schemas.daily_solver import DailySearchLimits, DailySolveResult


def build_day_check_manifest(
    request: DailyPlanningRequest,
    *,
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: DailySourceSnapshot,
) -> ExpectedDayCheckManifest: ...


def solve_daily_plan(
    request: DailyPlanningRequest,
    *,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: DailySourceSnapshot,
    limits: DailySearchLimits | None = None,
    clock: Callable[[], float] = monotonic,
) -> DailySolveResult: ...
```

These are local synchronous Python interfaces. No backend endpoint, persistence,
ranking, weekly schedule or substitution interface is added. Member 1 and the trusted
loader designate complete source DTOs; Member 3 independently selects normalized
context, candidates and KB. Source authentication/freshness/revocation is not supplied
by hashes. Do not copy client request records into trusted argument positions merely
because parsing succeeds. Serialized results are evidence records, never accepted
eligibility overrides or inputs to solve_daily_plan.

### Authoritative manifest and preprocessing

Every public call recursively validates original nested DTO storage and exact
independent source/context/KB pins. Sources must match the request's source digest;
context must match its exact source/context digest. Existing context validation
compares KB, graph, food/check-catalogue, taxonomy and workflow expectations.

The manifest builder accepts the KB through build_knowledge_snapshot, selects all
workflow obligations through the existing mandatory-check admission boundary and
constructs the exact DAY manifest with full WEEK deferrals. Complete catalogue
coverage, active/absolute/approved definitions, evidence and applicability references
are mandatory. Unsupported DAY vocabulary (including unsupported old recipe-owned
DAY predicates) rejects instead of being omitted. No reduced manifest, caller list,
policy override or eligibility flag is accepted by the public API.

The solver compiles the DAY applicability dependency closure once after accepted
manifest construction. Existing _validated_fact_index, _descriptors_for and
_applicability semantics validate ownership/type and compute conservative dependency
states. Missing dependencies dominate an evidenced false local condition; missing
applicability never becomes NOT_APPLICABLE.

One public filter_candidates call validates/evaluates the entire candidate pool,
including empty-domain and already-expired requests. Each distinct domain option
then receives one public evaluate_combination call, using the independently supplied
exact source combination. Each existing combination call itself runs public recipe
filtering over the candidate pool. These calls retain all Phase 3/4 prerequisites,
full traces, accepted role records and exact deferred definitions.

Consequently, for m evaluated distinct options and r supplied recipes, actual public
calls are m combination evaluations and 1+m recipe-filter batches; recipe decisions
are evaluated (1+m)*r times. This inherited repeated preprocessing is reported
honestly. There is no unsupported cached-result argument or bypass of public
validation. Results are memoized once per exact validated option within this request,
shared across its slot occurrences and never cached across requests. No public
eligibility API runs in assignment search or final output verification.

Per-slot admission combines combination/recipe status, FIXED configuration and
explicit suitability. Complete suitability excluding a slot is known FAIL; absent
or incomplete suitability is UNKNOWN. UNASSIGNED is UNKNOWN. Known FAIL dominates
other unresolved prerequisites. Each option retains statuses/reasons for all three
slots, plus its complete Phase 4 proof; domain membership remains independently
specified by the validated request. Measurement records retain exact identity,
unit/basis/completeness validation, without becoming eligibility flags.

### DAY facts, predicates and explanations

`core/reasoning/day_checks.py` contains private request-local computations shared by
search and computed-output verification, avoiding a second numeric/applicability
implementation or a circular dependency on the solver. It performs no source
loading, search or global caching. The new computed schemas may call these pure
checks after recursively validating their retained records.

`synthetic_day_complete` derives True only from three exact, eligible, suitable,
FIXED slot choices whose accepted combinations are complete. An unresolved
prerequisite yields value=None/complete=False, never an invented False or True.
Trial identity binds every exact slot/option reference; the parent result retains
all upstream proof records and the fact retains derivation/source evidence.

`synthetic_day_quantity_total` sums exactly one complete, independently supplied
integer MEAL_TOTAL per selected slot. Repeated meals contribute once for each slot
occurrence. A missing/null/incomplete contribution makes the total UNKNOWN; partial
totals are not substituted. Original contributions and preparation/configuration
bindings survive in DayFact. A numeric total may be independently known even if
recipe eligibility is unresolved, allowing a known numeric violation to rule out
that hypothesis. No ingredient totals, conversions, floats, rounding, clinical
defaults or invented thresholds are introduced.

The derivation reference `synthetic-day-derivation / 1` names the synthetic
three-slot/exact-integer algorithm, not a nutrition source or clinical approval.
Its metadata conflicts with a supplied same-ID/version reference reject through
existing provenance checks. Source and prerequisite evidence is retained alongside
this algorithm reference.

Boolean EQ/NE and integer LT/LE/GT/GE/EQ/NE use the existing exact predicate helper.
Thresholds are exclusively the accepted RuleDefinition values. Each mandatory DAY
rule receives a complete evaluation after a completed hypothesis, even after a FAIL.
Missing required PROFILE/CONTEXT prerequisites remain explicit evidenced gaps.
Evidenced NOT_APPLICABLE keeps predicate UNKNOWN and resolves coverage; UNKNOWN
applicability/required facts blocks PASS. A nonempty set is required for DAY PASS.

The DAY aggregate combines all slot prerequisites with aggregate_hard_status of the
complete DAY RuleTrace: known FAIL dominates UNKNOWN. No mandatory DAY checks yields
UNKNOWN. Measurements not required by an applicable predicate can remain UNKNOWN
without being silently filled, including an evidenced NOT_APPLICABLE numeric rule.
Every trial retains DayFacts, full RuleTrace and one bound, evidenced explanation per
rule. Rule rationale, exact observations, applicability evidence and comparison reason
are retained; no model generates safety explanations.

### Search and four outcomes

Variable order is BREAKFAST, LUNCH, DINNER. Value ordering is the full tuple:
option_id, combination_id/version, snapshot_id/version, configuration_id/version
(empty only for UNASSIGNED), combination_digest. Source/domain insertion order does
not change traversal. First verified feasibility stops search; no preference or
optimality claim is made. Repetition remains allowed by this two-attribute policy.

The implementation uses chronological depth-first backtracking and only sound unary
pruning: remove options with a definite per-slot FAIL. UNKNOWN choices remain in
hypothetical domains. There is no nutrient-bound pruning or forward checking in this
baseline; no unknown quantity is replaced by zero or an invented bound. Search uses
a depth-three stack, never a prebuilt Cartesian product.

| Outcome | Meaning |
|---|---|
| FEASIBLE | First complete trial has all prerequisites and mandatory DAY checks resolved; expose its exact FIXED DailyAssignment |
| INFEASIBLE | Complete preparation and exhaustive remaining-domain coverage prove every hypothesis FAIL, or a slot has no non-FAIL option |
| INSUFFICIENT_DATA | Exhausted finite domains have at least one UNKNOWN hypothesis and no verified feasible trial |
| TIMEOUT | Preprocessing, node, completed-assignment or deadline boundary stops work before proof |

Known FAIL plus UNKNOWN within one hypothesis remains FAIL. An UNKNOWN elsewhere
does not erase a proven failure, but an unrefuted UNKNOWN hypothesis prevents an
INFEASIBLE verdict. Proofs concern the supplied finite domains, not all catalogue
meals. Weekly feasibility always remains NOT_EVALUATED with full WEEK definitions
on the manifest. No weekly predicate runs and no persisted plan is created.

DailyTrial is a digest-bound structural hypothesis that can include UNASSIGNED
references; it is necessary to explain unresolved branches. Its DayFacts bind the
trial digest. Only a verified feasible trial is converted to the existing FIXED-only
DailyAssignment, and the computed result verifies their exact correspondence.

### Bounded search and computed DTOs

DailySearchLimits defaults: max_nodes=10,000, max_completed_assignments=256,
max_option_evaluations=150, deadline=None. Fixed hard maxima are 200,000 nodes,
4,096 retained completed evaluations and 150 options; zero work budgets are supported.
These explicit synthetic resource limits are not clinical limits or production SLOs.
The completed-assignment cap bounds full diagnostic retention.

Deadline is an optional finite absolute reading of the injected monotonic clock.
Clock readings must be finite numbers and never move backwards. Deadlines are
checked between option evaluations and search nodes; in-flight public validation
finishes and is never bypassed. Boundary expiry does not interrupt a public evaluator
halfway or claim that partial validation establishes feasibility. Exact budget use
that finishes the problem succeeds; a limit becomes TIMEOUT only if more work remains.

New strict/frozen/camelCase DTOs in schemas/daily_solver.py:

| DTO | Fields beyond fixed schema/policy tokens |
|---|---|
| DailySearchLimits | max_nodes, max_completed_assignments, max_option_evaluations, deadline |
| DailySlotDecision | slot, status, reasons |
| DailyOptionDecision | option, complete CombinationEligibilityResult, three slot decisions |
| DailyTrialChoice | slot, option |
| DailyTrial | request_digest, canonical three choices, content_digest; validating build factory |
| DayRuleExplanation | manifest_digest, trial_digest, rule_reference, status, reason, evidence |
| DailyAssignmentEvaluation | trial, two facts, trace, status, explanations |
| DailySearchStatistics | nodes, completed_assignments, backtracks, known_rejections, unknown_branches, option_evaluations, phase3_batch_calls, phase3_candidate_evaluations, search_completed, exhaustive, budget_exhaustion, preprocessing_seconds, search_seconds |
| DailySolveResult | manifest, limits, recipes, options, evaluations, nullable assignment, outcome, statistics; criterion=FIRST_FEASIBLE and weekly_feasibility=NOT_EVALUATED |

New fixed tokens are daily-trial.v1, daily-solve-result.v1,
synthetic-day-evaluation.v1, synthetic-chronological-daily-search.v1 and
synthetic-daily-search-limits.v1. Prompt 1's attribute/measurement/admission tokens
remain unchanged. New records use existing strict raw JSON ingress; no native JSON
bypass or public result-input override is introduced.

DailySolveResult recursively validates every retained proof. It checks source,
recipe/combination and deferred-obligation bindings, recomputes slot states, exact
DAY facts/predicates/applicability and explanations, and verifies canonical trial
prefix/complete finite coverage. It rejects result-label changes, altered totals,
missing contributors/explanations/proofs, fabricated exhaustion and inconsistent
work counts. Recipe predicate/applicability labels are checked from retained resolved
facts without rerunning public graph/KB pipelines. A fully rewritten internally
consistent unsigned source/result still does not authenticate itself.

### Performance and remaining integration

Preparation cost includes existing public KB/recipe/combination validation and can
dominate small searches. Search is O(|B|*|L|*|D|) in the exhaustive case, bounded by
limits. Stored evidence is O(evaluated options + completed-assignment cap), with
bounded three-slot contributions per evaluation. The depth-first stack is O(3).
Final result validation rechecks retained computations; it does not invoke public
Phase 3/4 evaluation. Statistics separate preprocessing and search time; wall-clock
benchmarks additionally include output validation. Timing fields are measurements,
not part of semantic determinism or assignment hashes.

An isolated benchmark on this environment used the independent synthetic fixture,
constant 20 mg measurements and an approved fictional EQ 0 rule, forcing exhaustive
FAIL. Input construction was outside the measurements. Python tracemalloc was
enabled throughout each solve; its instrumentation materially increases runtime.
Peak is tracked Python allocation during solving, not process RSS or total input
dataset memory. These are observations, not production latency targets.

| Options per slot | Preparation s | Search s | Total s including output verification | Peak Python MiB | Public recipe batches | Public recipe decisions | Combination calls | Nodes / completed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 3.0584 | 0.2717 | 4.3807 | 2.175 | 2 | 2 | 1 | 3 / 1 |
| 2 | 7.4457 | 3.0113 | 14.4879 | 5.538 | 3 | 6 | 2 | 14 / 8 |
| 4 | 20.3165 | 24.6026 | 73.2519 | 27.485 | 5 | 20 | 4 | 84 / 64 |

Public eligibility calls depend on distinct options/recipes, not explored
assignments. Predicate consistency checks during output verification are separate
from the reported public-pipeline counts. Full evidence retention and output
revalidation have measurable time/memory cost; the completed-assignment cap must
remain explicit. No claim of production performance readiness is made. Separate
instrumented tests verify exact public call counts, repetition reuse and absence
of cross-request caches. A 50-option-per-slot first-feasible case visits only three
nodes and one complete assignment instead of materializing 125,000 tuples.

Member 1 still supplies actual trusted composition/suitability/fixed measurement
providers and approved nutrition semantics. Member 3 supplies authenticated source,
context/profile and release loading, freshness/revocation, transport/resource policy
and later persistence. Joint public/clinical approval remains separate. This slice
does not add production authentication, generated portions, ranking, weekly CSP,
substitutions, backend endpoints or data migrations.

### Prompt 2 adversarial finding

An independent `test_derivation_provenance_conflict_is_a_validation_error` supplied
a structurally consistent source containing conflicting metadata for the reserved
`synthetic-day-derivation / 1` identity. Before correction, search rejected it with
an unwrapped ValueError from evidence union (1 failed, 105 deselected, 2.96 seconds).
No feasible result or false PASS was produced, but the failure escaped the expected
ValidationError contract.

The public request validator now conflict-checks the complete independently bound
input tree together with the exact derivation policy reference before evaluation.
The shared reference factory prevents drift between boundary admission and fact
derivation. The regression passes after correction, including the final targeted
18-case release/precision/large-domain run (18 passed, 88 deselected, 48.35 seconds).
This MEDIUM error-contract finding is fixed within new Prompt 2 files; no Phase 1-4
contract or predicate behavior was changed.

### Prompt 2 final verification and scope

Final checks on 15 October 2026 used `uv run --frozen --no-sync` with the existing
environment and approved cache access. No dependency or lockfile changed.

| Check | Result |
|---|---|
| Ruff check . | Passed |
| Ruff format --check . | Passed; 116 files already formatted |
| Pyright | Passed; zero errors/warnings |
| pytest -q | **3,546 passed in 436.98 seconds**; all 3,440 baseline cases plus 106 new independent solver cases |
| Architecture/import audit | Passed in full pytest; no forbidden imports or local cycles, including the new shared checks/computed-schema dependencies |
| Oracle | Literal boolean/numeric tables and independent Cartesian products agree for the tested complete and unknown domains; no false-feasible discrepancy found |
| Public evaluation counts | Instrumented 2-option/8-assignment failure uses 2 combination calls and 3 recipe batches; a repeated request repeats these calls |
| Scope/Git | Five Prompt 2 files only; no staged changes, branch/HEAD unchanged, existing datasets/patch untouched |

`known_rejections` counts completed FAIL trials; per-slot known exclusions and
their reasons remain in option decisions. `unknown_branches` counts completed
UNKNOWN trials, not an estimate of unvisited possibilities. Incomplete work is
explicitly marked TIMEOUT rather than using zero counters to claim proof.

Created: core/reasoning/daily.py, core/reasoning/day_checks.py,
schemas/daily_solver.py (under apps/ai_system/src/savora_ai), and
apps/ai_system/tests/test_daily_solver.py. Updated only this existing handoff.
The five local Prompt 1 files remain present; their production/test code and all
Phase 1-4 public interfaces are unchanged by Prompt 2. No EDA notebook was run.

No unresolved in-scope HIGH/MEDIUM defect is known after the independent cases,
output/provenance hardening, measured experiments and full regressions. This is a
synthetic implementation verdict, not production/clinical approval or a performance
SLO. Trace retention/output validation cost and external authority integration
remain explicit limitations described above.

Final branch: `feature/member2-daily-csp`. HEAD remains
`63720ff540f65dd887897af1fca178f590547933`. No staging, commit, push, merge, rebase,
reset, PR or branch change was performed. Work stops after Prompt 2.

Verdict: **READY FOR PHASE 5 PROMPT 3**.

## Prompt 3: final independent Phase 1-5 audit

Audit date: 17 October 2026. This section records the recovered existing synthetic
daily implementation; it does not rebuild it or approve production/clinical use.
The earlier 3,585-case recovery result is historical evidence, not a substitute
for this audit's final run. Completed final verification is recorded below.

Reviewed AGENTS.md, ARCHITECTURE.md, all five Member 2 handoffs, actual Phase 1-5
validation/evaluation boundaries and the three daily test modules. The accessible
ten-page October proposed team contract was supplementary. Repository contracts
retain authority over its proposed API/cuisine vocabulary. Existing Python APIs
and the four DailyOutcome values are preserved.

### Audited interfaces, policies and compatibility

The exact annotated signatures and imports remain those in Prompt 2 above:
build_day_check_manifest(request, *, knowledge, context, sources) returns
ExpectedDayCheckManifest; solve_daily_plan(request, *, candidates, knowledge,
context, sources, limits=None, clock=monotonic) returns DailySolveResult.
There is no new endpoint, export or public Phase 1-4 interface.

| Phase | Guarantee checked through the daily chain |
|---|---|
| 1 | Strict/frozen/extra-forbidden recursively revalidated DTOs, exact rule/evidence identities, complete mandatory coverage, known FAIL dominance, evidenced NOT_APPLICABLE and empty-check UNKNOWN |
| 2 | Accepted synthetic KB, complete catalogue/coverage cells, ACTIVE/ABSOLUTE/APPROVED obligations, exact release pins, retained graph/taxonomy evidence and no negative inference from missing edges |
| 3 | Independent candidate/context/KB selection, exact recipe/graph bindings, source-aware resolution, full authoritative manifests, original-JSON ingress and PASS-only recipe eligibility |
| 4 | Public recipe prerequisites, exact combination/component/preparation/configuration binding, FIXED/UNASSIGNED isolation, explicit upstream authority and complete DAY/WEEK deferrals |
| 5 | Exact source/context/KB/domain/assignment pins, full DAY definitions, integer contribution evidence, deterministic bounded search and unevaluated WEEK obligations |

The extension remains synthetic-attributes.v4-day, with DAY policy
synthetic-day-policy.v1, evaluator synthetic-day-evaluation.v1 and search policy
synthetic-chronological-daily-search.v1. Application-owned DAY/CULINARY facts are:

- synthetic_day_complete: boolean EQ/NE; known True requires three eligible,
  suitable, FIXED choices. Unresolved prerequisites produce unknown, not an
  invented False or verified True.
- synthetic_day_quantity_total: bounded integer mg with LT/LE/GT/GE/EQ/NE.
  Each selected slot contributes one complete fixed whole-meal total. Repetition
  contributes per slot; ingredient totals are not added again. Missing,
  incomplete or null measurements do not become zero. No conversion occurs.

Representation/resource bounds remain (2**63-1)//3 per meal and 2**63-1 per DAY;
these are not clinical thresholds. Fixed configurations and explicit suitability
match independently selected source records and evidence. Schema validation and
matching hashes do not authenticate external providers.

Order remains BREAKFAST/LUNCH/DINNER with the canonical option ordering above.
Only known per-slot FAIL options are pruned; UNKNOWN hypotheses remain. The
independent product enumeration confirms that removed assignments contain a known
slot failure and that no valid witness is lost. No forward checking, MRV, ranking,
preference optimization or generated portions were added.

FEASIBLE requires a verified three-slot FIXED witness. INFEASIBLE requires complete
preprocessing and exhaustive failure or a sound empty-slot proof. INSUFFICIENT_DATA
retains unrefuted unknown hypotheses after complete finite coverage. TIMEOUT means
a node, assignment, preprocessing or deadline boundary prevented completion.
A known numeric violation can refute an otherwise unknown hypothesis; an
unrefuted unknown cannot establish infeasibility. Full WEEK definitions remain
deferred_checks and weekly_feasibility remains NOT_EVALUATED.

Budgets are unchanged: defaults 10,000 nodes, 256 completed assignments, 150 option
evaluations and no deadline; hard maxima 200,000/4,096/150. Deadline checks are
cooperative boundaries, not interruption of in-flight validation. Input/source/
domain/component limits and original-JSON limits are separate.

### Independent oracle, security and provenance evidence

The existing 150 contract, 106 solver and 39 integration cases are retained.
Their independently defined fixtures, literal truth tables and Cartesian
expectations do not use production predicate, aggregation or hash helpers as
expected-value oracles. All six numeric predicates, both boolean operators, zero,
large integers, unknown applicability and zero mandatory checks remain covered.

Additional probes ran in memory without adding redundant permanent tests:

- Ten product cases used (2,5), (None,5) and (0,1,3) measurements, reachable and
  unreachable equalities, unknown eligibility, known unsuitable options, empty/
  asymmetric domains and repeated occurrences. Literal statuses, complete
  evaluated prefixes and first witnesses matched every result.
- Thirteen budget cases independently checked a two-by-two-by-two domain.
  Node budgets 0/1/2/3/4/7/14 produced 0/0/0/1/2/4/8 completed trials.
  Assignment caps 0/1/2/8 stopped at 3/4/6/14 nodes. Only complete exhaustion
  returned INFEASIBLE; incomplete work, zero preprocessing and expired deadlines
  returned TIMEOUT.
- Forty-two adversarial cases raised ValidationError: malformed copied/constructed
  records, caller PASS extras, foreign KB/context/source releases, rehashed reduced
  or wrong-policy manifests, unapproved rules, omitted catalogue cells, altered
  outcomes/arithmetic/contributors/explanations/slot states/counters/WEEK checks,
  duplicate original JSON/aliases, nonfinite/overflowing values, hostile containers,
  counterfeit enums, wrong units, missing measurement/suitability evidence, wrong
  configurations and measurement/preparation transplants.
- Two graph cases distinguished an exact evidenced negative from a missing edge.
  The latter remained INSUFFICIENT_DATA despite complete inventory and a
  caller-declared False. The verified case retained inventory, exact absence and
  derivation evidence through the entire result.
- Three independently rebound applicability cases returned (local False,
  dependency unknown) -> INSUFFICIENT_DATA, (True, unknown) -> INSUFFICIENT_DATA
  and (True, evidenced False) -> FEASIBLE with predicate UNKNOWN/NOT_APPLICABLE.
  Unknown dependencies were never hidden by false local applicability.

Thus 23 oracle/budget scenarios, 42 adversarial rejections and five graph/dependency
scenarios passed. Public DTO builders and existing independent fixture constructors
formed legal inputs; expected statuses used literal arithmetic and explicit
three-valued tables, not production comparison/aggregation helpers.

No new HIGH/MEDIUM/LOW implementation defect was reproduced. The interrupted
integration file's four E501 findings were already fixed by the separately
authorized formatting recovery with its AST unchanged. No source optimization,
test rewrite or public contract correction was needed in this final audit.

Supported raw ingress is validate_contract_json on original bytes/text. Native
model_validate_json cannot recover overwritten duplicate keys and remains
unsupported for security-sensitive raw ingress. Unsupported solver keyword
arguments are ordinary invalid Python API usage, not an eligibility override.
A wholly rewritten internally consistent unsigned release/result does not
authenticate itself. Request data or serialized decisions must not be promoted
to independent source/KB/context authority.

### Measured performance and resource limits

Four small benchmarks used CPython 3.14.7 and existing dependencies, one recipe
and 1/2/3 distinct fixed configurations available in every slot. Input construction,
imports and wrapper setup were outside measurement. Every row enabled tracemalloc
throughout solving. Peak is traced Python allocation, not RSS or total input
memory. Instrumentation affects runtime; these observations are not SLOs.

| Options/slot | Possible assignments | Outcome | Nodes | Completed | Preprocessing s | Search s | Output s | Total s | Peak Python MiB |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | INFEASIBLE | 3 | 1 | 3.312116 | 0.288491 | 1.057259 | 4.658645 | 2.137973 |
| 2 | 8 | INFEASIBLE | 14 | 8 | 6.385518 | 3.314026 | 4.548525 | 14.249640 | 5.147930 |
| 2 | 8 | FEASIBLE | 3 | 1 | 5.968876 | 0.389240 | 2.124607 | 8.497807 | 2.809818 |
| 3 | 27 | FEASIBLE | 3 | 1 | 9.967924 | 0.395677 | 2.609669 | 12.988175 | 3.491825 |

Preprocessing/search are actual DailySearchStatistics measurements. The search
interval includes domain preparation, DAY-program compilation and trial/trace/
explanation creation, not just DFS instructions. Output is a separate wall-clock
wrapper around DailySolveResult construction, including recursive proof validation
and recomputation. Total also includes small statistics/return-argument overhead.

In the two-option exhaustive case, inclusive timers measured strict top-level
request validation 0.389909 s; accepted KB/DAY-manifest building 0.635716 s; public
recipe batches 2.620418 s; combination evaluations 3.571816 s; two DAY-program
compilations 0.001293 s; and result creation/validation 4.548525 s. These overlap:
combination calls include recipe filtering, and output verification includes the
second compilation. Do not add them as disjoint categories.

Actual public calls were respectively 2/3/3/4 recipe batches and 1/2/2/3 combination
evaluations. For m distinct referenced options and r supplied recipes the inherited
path makes m combination calls, 1+m recipe batches and (1+m)*r recipe decisions.
The two-option feasible/infeasible rows have identical prerequisite counts despite
one versus eight completed assignments. No public Phase 3/4 evaluation runs inside
DFS or output validation. There is no cross-request cache. Full input validation
still inspects the entire supplied KB, candidate pool and source, including unused
source options.

Strict prerequisites and retained evidence/output verification are material costs;
DAY-program compilation is small here. A full-suite runtime is not a measurement
of Cartesian search alone. Search caps bound nodes/retained trials, not in-flight
validation latency or serialized size for every structurally admissible source.
A larger optimization would require a separately reviewed request-local validated
preparation/reuse design across Phase 3/4 boundaries and independent equivalence
tests. No validation bypass, global cache or speculative refactor was introduced.

Reproduce the small-domain timing method from the repository root in PowerShell.
The detailed run additionally wrapped prerequisite/program functions to count
calls and measure the inclusive categories above.

```powershell
$env:UV_NO_SYNC = "1"
$env:UV_FROZEN = "1"
@'
import gc
import runpy
import time
import tracemalloc
from unittest.mock import patch

import savora_ai.core.reasoning.daily as daily

case = runpy.run_path("apps/ai_system/tests/test_member2_phase5_integration.py")["audit_case"]
for amounts, target in [((2,), 8), ((2, 5), 8), ((2, 5), 6), ((2, 5, 8), 6)]:
    data = case(amounts, target=target)
    original = daily.DailySolveResult
    output = {}

    def measured_output(*args, **kwargs):
        began = time.perf_counter()
        result = original(*args, **kwargs)
        output["seconds"] = time.perf_counter() - began
        return result

    with patch.object(daily, "DailySolveResult", measured_output):
        gc.collect()
        tracemalloc.start()
        began = time.perf_counter()
        result = daily.solve_daily_plan(**data)
        total = time.perf_counter() - began
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    stats = result.statistics
    print(len(amounts), len(amounts) ** 3, result.outcome.value,
          stats.nodes, stats.completed_assignments,
          stats.preprocessing_seconds, stats.search_seconds,
          output["seconds"], total, peak / 1024 ** 2)
'@ | uv run python -
```

The existing test_no_global_cache_and_public_phase_counts_do_not_scale_with_assignments
in tests/test_daily_solver.py independently spies on public calls and repeats a
request. Keep it and the finite-domain oracles when reviewing future optimizations.
No large Cartesian stress case or repeated full suite was launched for profiling.

### Integration dependencies, scope and file set

Member 1 supplies verified complete combinations, exact prepared/fixed configurations,
per-configuration integer measurement semantics and explicit evidenced suitability.
Real nutrition, recipe-specific conversions, validated targets and production fact
vocabulary need separate source review. Member 3 owns authenticated independent
candidate/context/KB/source loading, release freshness/revocation, original-JSON
ingress, backend resource/error policy and eventual persistence. Joint agreement on
API/transport, clinical rules, precision and source/reviewer authority is pending.

This is a synthetic daily finite-domain witness, not a verified production nutrition
plan or medical-safety decision. Weekly CSP/WEEK evaluation, locked-slot swaps,
ranking, generated portions, production providers and clinical activation are not
completed or approved here.

The complete Phase 5 bundle is exactly ten files relative to the repository:

- Modified: apps/ai_system/src/savora_ai/schemas/filtering.py
- Modified: apps/ai_system/src/savora_ai/core/reasoning/manifest.py
- Created: apps/ai_system/src/savora_ai/schemas/daily.py
- Created: apps/ai_system/src/savora_ai/schemas/daily_solver.py
- Created: apps/ai_system/src/savora_ai/core/reasoning/daily.py
- Created: apps/ai_system/src/savora_ai/core/reasoning/day_checks.py
- Created: apps/ai_system/tests/test_daily_contracts.py
- Created: apps/ai_system/tests/test_daily_solver.py
- Created: apps/ai_system/tests/test_member2_phase5_integration.py
- Created: docs/member2_daily_csp.md

Eight files remain untracked; the two tracked changes are the documented DAY
admission extension. This final audit changes only this handoff. Formatting
recovery preceded audit start. No new tests were added without a concrete gap or
defect. No Phase 1-4 public interface/semantics, dependency, lockfile, provider,
backend or frontend change was made.

Branch/HEAD remain feature/member2-daily-csp at
63720ff540f65dd887897af1fca178f590547933; the index is empty. Existing Data files,
EDA notebooks and phase1-security-fix.patch are outside the bundle. No EDA notebook,
Git history operation, staging or publication was performed.

### Final independent verification

Use existing dependencies with UV_NO_SYNC=1 and UV_FROZEN=1. Python module entry
points avoid the previously blocked Windows launchers; no failing launcher retry,
package installation or synchronization is required.

| Check | Final audit result |
|---|---|
| uv run ruff check . | PASS; exit 0; All checks passed |
| uv run ruff format --check . | PASS; exit 0; 117 files already formatted |
| uv run python -m pyright | PASS; exit 0; 0 errors, 0 warnings, 0 informations |
| uv run python -m pytest -q | PASS; exit 0; 3585 passed in 496.76s (0:08:16) |
| git diff --check and intended-file/data integrity | PASS; only this document changed during audit; 179 file hashes compared and 41 Data file size/mtime records unchanged |

The full suite ran once after the independent probes and profiling. Exact output
and all four exit codes are retained in the ignored local verification log
.delta/phase5-final-audit-2026-10-17.log. The final results were then recorded here;
no source or test changed after verification. Git HEAD, index and status are
unchanged from audit start; lockfiles and phase1-security-fix.patch match their
recorded hashes. The whitespace check also covers the eight untracked Phase 5
files, which are absent from git diff.

Final verdict: READY TO COMMIT for the synthetic Phase 5 bundle. A successful
synthetic audit is not production/
clinical approval and authorizes no staging, commit, push or PR.
