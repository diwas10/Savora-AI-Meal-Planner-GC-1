# Member 2 Phase 6, Prompt 1: WEEK admission and strict weekly declarations

Current checkpoint: Phase 6 Prompt 3 weekly search is implemented locally.
The Prompt 3 section records the current API, proof and resource semantics; earlier
sections retain the Prompt 1/2 handoff history.

Status: synthetic implementation, 18 October 2026. The user provisionally approved
WEEK admission and declaration contracts only. This document provides no production,
clinical or authenticated provider approval. No WEEK predicate, weekly aggregation,
search algorithm, ranking, swap, backend endpoint or persistence is implemented.

## Foundation and ownership

Worktree: Savora-Phase6. Branch: feature/member2-weekly-csp. Starting HEAD:
7a00114576d59a4a5e628b37f481bb6565f777e7. The branch and index were clean.
The explicitly selected existing branch is retained despite the generic feat/ rule.
Read AGENTS.md, relevant ARCHITECTURE.md sections 3-6, 8-9, 11 and 13-15,
and the five Member 2 Phase 1-5 handoffs with their implementation/tests.
Architecture remains authoritative; this slice is an intentionally synthetic subset
of its eventual nutrition/portion/search requirements.

Member 2 owns WEEK rule admission, declarations and future derivation/search.
Member 1 supplies exact recipes, composition, preparation, fixed quantities,
measurement evidence and suitability. Member 3 independently selects normalized
profile/context, source and KB releases and later owns transport/persistence.
AI performs no network or database I/O.

Existing interfaces inspected and preserved: aggregate_hard_status,
is_candidate_eligible, build_knowledge_snapshot, resolve_food_relations,
resolve_taxonomy_assignment, build_expected_check_manifest, resolve_rule_facts,
evaluate_rule_checks, filter_candidates, evaluate_combination,
build_day_check_manifest, solve_daily_plan and validate_contract_json.
Existing validating snapshot factories and Phase 5 result semantics are unchanged.

## Original failure and corrected admission

Before modifying production source, the new independent fixture constructed its own
synthetic graph, complete workflow/scope catalogue and coverage, approved ACTIVE
ABSOLUTE CULINARY WEEK rule, recipe and WEEKLY_PLAN context. It imports no earlier
test fixture or production policy/hash helper as its expected-value oracle.
The accepted rule was boolean EQ True on synthetic_week_complete, with
synthetic-context-enabled / 1 applicability. KB construction succeeded.

The unchanged foundation failed test_week_owned_rule_admitted_and_deferred:

```text
build_expected_check_manifest -> _mandatory_checks -> _validate_rule_policy
ValidationError: SyntheticRulePolicy
Value error, unsupported synthetic required attribute
1 failed in 0.77s
```

The same regression passed immediately after the minimal dispatcher/registry
extension: 1 passed in 0.30s. This fixes admission, not WEEK evaluation.

The immutable application-owned registry is separate from recipe, combination and
DAY registries in schemas/filtering.py. Genuine WEEK names never enter VersionedFact
or recipe adapters. All required facts must be registered WEEK facts or existing
PROFILE/CONTEXT prerequisites. Food facts owned by another scope cannot supply them.

| Attribute | Type / representation | Unit | Operators |
|---|---|---|---|
| synthetic_week_complete | exact bool | None | EQ, NE |
| synthetic_week_quantity_total | exact int 0..64,563,604,257,983,430,642 | mg | LT, LE, GT, GE, EQ, NE |
| synthetic_week_max_recipe_slot_occurrences | exact int 0..21 | dimensionless | LT, LE, GT, GE, EQ, NE |

Definitions must be SYNTHETIC, WEEK, CULINARY, ACTIVE, ABSOLUTE and APPROVED,
with the exact synthetic-context-enabled / 1 reference. Approval/definition evidence
remains required and synthetic. Boolean-as-number, float thresholds, unsupported
operators/units, incorrect ownership and unapproved mandatory checks reject.
Archived inactive declarations may remain in inventory but cannot become mandatory.

Upstream attribute policy synthetic-attributes.v5-week is selected iff selected
workflow obligations contain genuine WEEK attributes. It can coexist with earlier
recipe/combination/DAY vocabulary. Earlier v1/v2/v3-combination/v4-day selection
semantics remain unchanged without WEEK names. Rehashed downgrades, false v5 claims
and unknown policy tokens reject. Existing approval/workflow/evaluator/identity
policy tokens are unchanged.

The complete definitions remain deferred through recipe, combination and DAY
results; no upstream WEEK predicate runs. Legacy WEEK checks keep earlier upstream
admission. ExpectedWeekCheckManifest explicitly rejects legacy WEEK predicates
unsupported by the new weekly vocabulary instead of dropping or reinterpreting them.
It also requires supported DAY predicates, as the existing daily evaluator does.

## Policy and future fact semantics

synthetic-week-policy.v1 names the approved synthetic vocabulary. Request contract
policy is synthetic-weekly-contracts.v1; the manifest retains synthetic-day-policy.v1.
Each persisted declaration shape has its own explicit schema_version where shown
by the actual fields below. No weekly evaluator, derivation, measurement or search
policy version is invented before that implementation exists. The numeric basis
label WEEK_FIXED_TOTAL describes a declaration, not an executed algorithm.

Future synthetic_week_complete is True only when all seven days and 21 slots have
established prerequisites and complete DAY validation. Incomplete evidence stays
unknown rather than becoming a fabricated False or True. Exact calendar/slot shape
is already mandatory at the request/trial boundary.

Future quantity derivation sums one complete, verified FIXED whole-meal integer
total for each selected slot. Repeated meals contribute once per occurrence.
Component totals are not added again. Missing/null/incomplete contributions are
not zero and cannot establish a complete weekly quantity. No unit conversion,
rounding, density inference or real nutrition threshold is added.

The maximum is exactly 21 * ((2**63 - 1) // 3), preserving every Phase 5 meal
measurement. It exceeds a signed 64-bit integer. Python exact integers and original
JSON integer tokens are retained; no float or database storage conversion occurs.

Future repetition derivation counts the number of distinct meal slots containing
each canonical recipe_id and returns the maximum. Duplicate occurrences within one
meal count once; different configurations retain the same recipe identity.
The shared daily source already rejects conflicting snapshots under one recipe ID.
There is no automatic repetition or variety restriction. A restriction requires an
explicit admitted rule. Occurrence declarations contain unique recipe IDs per slot.

WeekFact validates declaration shape, complete contributor coverage, bounds and
source/trial bindings. It deliberately does not compute a sum, maximum or predicate.
A correctly bound but numerically inconsistent declaration is not a feasibility
witness; all Prompt 1 results remain NOT_EVALUATED. The future computed contract must
recompute facts independently before allowing any resolved outcome.

Applicability descriptor identities, exact required context declarations and
transitive dependencies are validated through the accepted KB/manifest boundary.
No applicability predicate executes here. Later evaluation must preserve existing
conservative dependency semantics: an unresolved dependency dominates a local False;
evidenced NOT_APPLICABLE resolves coverage while predicate status stays UNKNOWN.
Empty mandatory sets never acquire an implicit PASS.

## Exact DTO fields

Import these directly from savora_ai.schemas.weekly; no package export or HTTP schema
was changed. The table includes inherited fields and fixed schema/policy markers.
All models use the existing strict/frozen/extra-forbidden/camelCase contract base,
recursive storage revalidation, canonical enums and immutable built-in tuples.

| DTO | Exact fields |
|---|---|
| WeeklySourceReference | `source_id`, `version`, `content_digest` |
| WeeklySourceSnapshot | `content_digest`, `schema_version`, `source_id`, `version`, `expected_daily_source`, `daily_source`, `evidence` |
| WeekDayReference | `week_id`, `week_version`, `day_id`, `day_index`, `calendar_date` |
| WeeklyDayDomain | `day`, `domains` |
| WeeklyPlanningRequest | `content_digest`, `schema_version`, `contract_policy_version`, `week_policy_version`, `request_id`, `version`, `week_id`, `week_version`, `start_date`, `context_id`, `context_version`, `context_digest`, `expected_source`, `source`, `days` |
| WeeklyDayAssignment | `day`, `trial`, `assignment` |
| WeeklyAssignment | `content_digest`, `schema_version`, `request_digest`, `week_id`, `week_version`, `start_date`, `source`, `daily_source`, `context_digest`, `days` |
| WeeklyTrialChoice | `day`, `slot`, `option` |
| WeeklyTrial | `content_digest`, `schema_version`, `request_digest`, `week_id`, `week_version`, `start_date`, `choices` |
| WeekMeasurementContribution | `day`, `slot`, `option`, `measurement_source`, `measurement_digest` |
| WeekRecipeOccurrence | `day`, `slot`, `option`, `recipe_ids` |
| WeekFact | `schema_version`, `week_policy_version`, `request_digest`, `trial_digest`, `week_id`, `week_version`, `source`, `context_digest`, `observation`, `measurement_basis`, `basis_reference`, `contributions`, `occurrences` |
| ExpectedWeekCheckManifest | `content_digest`, `schema_version`, `week_policy_version`, `day_policy_version`, `stage`, `request`, `knowledge`, `required_checks`, `day_checks` |
| WeeklySearchLimits | `schema_version`, `max_nodes`, `max_option_evaluations`, `max_day_evaluations`, `max_week_evaluations`, `max_predicate_evaluations`, `max_cache_entries`, `max_diagnostics`, `max_proof_records`, `max_proof_bytes`, `deadline` |
| WeeklyFrontierChoice | `day`, `slot`, `option` |
| WeeklySearchState | `coverage`, `phase`, `exhaustive`, `nodes`, `option_evaluations`, `day_evaluations`, `week_evaluations`, `predicate_evaluations`, `cache_entries`, `proof_records`, `proof_bytes`, `frontier`, `next_option_indexes`, `exhaustion_reason` |
| WeeklyConstraintDiagnostic | `request_digest`, `week_id`, `week_version`, `stage`, `code`, `message`, `status`, `day`, `slot`, `option`, `rule_reference`, `evidence` |
| WeeklySolveResult | `schema_version`, `plan_feasibility`, `weekly_feasibility`, `outcome`, `manifest`, `limits`, `search`, `assignment`, `trial`, `facts`, `diagnostics` |

## Calendar, request and assignment identity

Dates are strict canonical YYYY-MM-DD strings, validated with Python calendar parsing.
Timestamp strings, malformed dates, Python date objects, coercive numeric indexes and
calendar overflow reject. String storage preserves the existing strict JSON output
scalar vocabulary; no upstream ingress guard needed widening.

Exactly seven unique day indexes 1..7 and seven distinct day IDs are required.
Every day pins the same week ID/version and date start_date + day_index - 1.
Week and day IDs must be distinct. Opaque IDs do not determine chronology.
Every day has exactly BREAKFAST/LUNCH/DINNER, hence exactly 21 slot domains.
Different days/slots can have different domains, including empty domains.

Source options and domain references match every option/combination/snapshot/
configuration identity, revision and digest. Shared limits are inherited unchanged:
150 options/source, 50 options/domain, 50 configurations/combination and 32 component
occurrences/meal. Repeated options, recipes and fixed portions across days are allowed.
Duplicate option identities/aliases and conflicting source definitions reject.

WeeklyAssignment contains exactly seven structural daily assignments and their
DailyTrial objects. Existing AssignedMeal enforces FIXED configurations. UNASSIGNED
options can occur in request domains and WeeklyTrial, never in WeeklyAssignment.
Neither structural assignment nor domain membership establishes suitability or safety.

The private _daily_request bridge creates an unchanged DailyPlanningRequest with
request_id = weekly-day-<weekly request digest>-<day index>, the weekly request
version, exact day ID, common context/source and that day's three domains.
WeeklyDayAssignment binds identical daily request digests and slot choices across
the DailyTrial and DailyAssignment. The parent WeeklySolveResult reconstructs the
daily request and verifies that binding and actual weekly domain membership.
DailyTrial.content_digest and DailyAssignment.content_digest are distinct; they are
never substituted. Future DayFacts must retain their original daily trial digest.

WeeklyTrial has exactly 21 day/slot/option choices. WeeklySolveResult binds every
choice to the request, and any supplied structural assignment to those same choices.
Standalone trial/assignment digests provide structural integrity only; containing
request/result checks provide domain/source binding.

## Common source, provenance and manifests

WeeklySourceSnapshot wraps one common DailySourceSnapshot plus an exact independent
expected_daily_source pin. Its own identity is distinct from the daily source.
The daily source contains the normalized context/profile and their full release
expectations. All options retain exact recipe, preparation, quantity, suitability,
measurement and evidence declarations. External declarations cannot self-reference
the enclosing daily or weekly source. Conflicting evidence metadata reject globally.
Missing suitability/measurements are representable unknown declarations; supplied
suitability/source records require evidence and measurement bases remain exact.

Only KnowledgeWorkflow.WEEKLY_PLAN is accepted. The common daily source rejects
CRAVING_DISCOVERY and PLANNED_SWAP. ExpectedWeekCheckManifest uses existing synthetic
KB acceptance and exact context KB/graph/taxonomy/food/check-catalogue expectations.
It selects all canonical DAY/WEEK definitions from that same accepted KB and rejects
reduced or rewritten lists even after rehashing. Catalogue omission, stale references,
incomplete coverage or unsupported applicability dependencies reject.

WeekMeasurementContribution stores an exact option, external measurement source pin
and measurement digest. Parent validation resolves it against the one measurement
in the common source; complete quantity declarations require all 21 measurements
complete. This avoids copying full measurements/components 21 times. Recipe occurrence
records must name exactly the canonical recipe IDs in the selected composition.
Complete occurrence declarations require complete composition for every slot.

These are integrity checks relative to supplied records, not provider authentication.
A declaration constructor cannot discover a wholly replaced, internally consistent
unsigned release. Future public evaluation/search must compare request declarations
to independently selected KB/context/candidates/sources. Never promote client source
records or serialized results into trusted arguments. Authentication, revocation,
source truth and production approval remain external integration responsibilities.

## Digests, serialization and original-JSON ingress

Source, request, assignment, trial and manifest reuse validating build(content,
expected_digest=None) factories. An omitted digest is computed; a supplied null,
malformed or mismatching digest is rejected. The optional independent expected pin
is verified. Direct constructors and JSON require the correct digest.

The existing unordered canonical SHA-256 format includes defaults, policies, exact
scalar types, nulls, occurrence multiplicity and day/slot labels. Dictionary keys and
unordered collection encodings are sorted. Permuting declarations preserves semantic
digests; changing a binding changes its digest. Stored declaration order is retained,
so arbitrary permutations need not have byte-identical model_dump_json output.
Identical accepted input has deterministic serialization. No RFC 8785/signature claim.
Chronological proof order must use explicit indices, never rely on an unordered hash.

Untrusted raw text/bytes must enter through validate_contract_json(Target, original).
The existing 1 MiB, depth-64, duplicate-key/alias, finite-numeric and bounded output
traversal protections remain unchanged. Native JSON validation cannot recover already
overwritten duplicate keys. Hostile containers, counterfeit enums and malformed
unchecked nested Pydantic copies reject before normalization.
Structural Python ceilings do not promise every maximal source/result fits the raw
JSON boundary. Compact source/contribution references reduce duplication; future
transport must preflight the full encoded envelope and reserve space for proof.
Never silently truncate mandatory facts, checks or coverage to fit the limit.

## Resource and proof declaration semantics

| Limit | Default | Hard maximum |
|---|---:|---:|
| nodes | 10,000 | 200,000 |
| option evaluations | 150 | 150 |
| DAY evaluations | 256 | 4,096 |
| WEEK evaluations | 256 | 4,096 |
| predicate evaluations | 100,000 | 1,000,000 |
| cache entries | 256 | 4,096 |
| diagnostics | 100 | 1,000 |
| proof records | 1,024 | 8,192 |
| proof bytes | 524,288 | 1,048,576 |

All capacities accept strict zero. The optional finite absolute deadline refers to a
future injected monotonic clock. Cooperative checks cannot interrupt in-flight
validation or establish an end-to-end latency guarantee. Limits are synthetic
resource declarations, not nutrient restrictions or a benchmark-derived SLO.

WeeklySearchState can describe a chronological frontier prefix, one cursor index per
prefix entry when supplied, counters and an explicit interruption reason. Reasons
cover node/preprocessing/DAY/WEEK/predicate/proof-record/proof-byte budgets and deadline.
Cache capacity is a storage ceiling, not permission to discard search alternatives;
future deterministic eviction may require recomputation. Diagnostics capacity can
limit display records, never mandatory proof coverage.

Coverage is always NOT_VERIFIED, exhaustive must be strict False, and no complete
coverage/pruning certificate is accepted in this prompt. Standalone progress records
are declarations. WeeklySolveResult accepts only NOT_STARTED with zero work/frontier,
outcome=None and both feasibility markers NOT_EVALUATED. All four DailyOutcome
members are rejected as resolved outcomes. No caller hash/counter/exhaustive flag can
authorize INFEASIBLE. A separate future computed result must validate full coverage
or sound subtree pruning. Proof-storage exhaustion before verification must produce
TIMEOUT; exact-budget completion may still succeed when no required work remains.

## Deferred prompts and integration dependencies

Prompt 2 must implement pure WEEK derivation/evaluation, common request-scoped
preparation, exact DAY/WEEK transitions and a computed witness contract with independent
source inputs. Prompt 3 must implement bounded shared 21-slot search and verified
coverage/frontier accounting, then audit outcomes against independent small-domain
Cartesian oracles. Later prompt scope can refine this split without treating these
Prompt 1 declarations as completed execution. Seven first-feasible daily calls cannot
establish a valid week; daily alternatives and UNKNOWN hypotheses must be retained.

Member 1: verified recipe/composition snapshots; canonical recipe identity across
configurations; exact fixed portions/preparations; whole-meal integer measurement and
source evidence; explicit evidenced slot suitability. Real nutrition/targets,
conversions, generated configurations and later ranking require separate agreements.

Member 3: independently selected authenticated context/profile/KB/source releases,
freshness/revocation, original-JSON ingress, resource/transport/error policy and later
FastAPI persistence. Joint production vocabulary, clinical references, approval/reviewer
authority and API/OpenAPI exposure remain pending. No database, frontend, model,
dependency version or lockfile is changed by this slice.

## Verification

The worktree initially lacked an environment. Created its isolated .venv using
uv sync --frozen --link-mode copy, clearing VIRTUAL_ENV only inside that command
process. Existing lockfile versions were used. Windows sandbox access required
approved escalated commands for this sibling worktree and installed native libraries.
No global Git configuration was changed; read-only Git calls used a command-local
safe.directory setting where needed.

The focused suite passed 162 cases before two final bridge/calendar cases were added.
Ruff check and format check passed after formatting; Pyright passed with zero errors,
warnings and informations. The completed final results are recorded below. No EDA notebook, staging, commit, push, merge, rebase,
reset or PR operation is authorized or performed.


### Final verification and scope

All commands ran against the final Python source/tests in the isolated Phase 6
worktree environment. Only this handoff was subsequently updated with results.

| Command/check | Actual result |
|---|---|
| uv run --frozen --no-sync ruff check . | PASS; All checks passed |
| uv run --frozen --no-sync ruff format --check . | PASS; 121 files already formatted |
| uv run --frozen --no-sync python -m pyright | PASS; 0 errors, 0 warnings, 0 informations |
| uv run --frozen --no-sync python -m pytest -q | PASS; 3,771 passed, 1 skipped in 562.62s (0:09:22) |
| New weekly cases | All 164 passed within the full suite; preceding focused run passed 162 before the final two bridge/calendar cases |
| AI import isolation | PASS; the modified/new production modules import no backend, FastAPI or SQLAlchemy code |
| Dependency/lockfile integrity | PASS; uv.lock, root and AI pyproject.toml match HEAD |
| Whitespace/scope | PASS; tracked diff and all three new files checked; five intended files only |

The one skip is the existing optional full Food.com recipe-level verification in
test_foodcom_cuisines.py, requiring FOODCOM_RAW_RECIPES. That dataset is not configured
in this clean worktree. This is not a weekly contract failure. No EDA notebook ran.
Frontend lint/typecheck/build were not run because no frontend or transport changed.

Created: schemas/weekly.py, tests/test_weekly_contracts.py (under apps/ai_system),
and docs/member2_weekly_csp.md. Modified only schemas/filtering.py and
core/reasoning/manifest.py. No Phase 1/2 contract, Phase 5 DTO/solver, public signature,
backend, frontend, package export, dependency or lockfile changed.

No unresolved in-scope HIGH/MEDIUM issue was reproduced. WEEK derivation/predicate
execution, computed proof verification and weekly search remain explicitly deferred,
not silently accepted as finished. Source authentication and production/clinical
approval remain external dependencies, distinct from these synthetic contracts.

Final branch: feature/member2-weekly-csp. HEAD:
7a00114576d59a4a5e628b37f481bb6565f777e7. Index empty. Working tree contains the two
tracked modifications and three new files above; the isolated .venv is ignored.
No staging, commit, push, merge, rebase, reset or PR operation was performed.

Verdict: READY FOR PHASE 6 PROMPT 2 (synthetic scope only). Work stops after Prompt 1.


## Prompt 2: authoritative supplied-trial WEEK evaluation

Implemented 18 October 2026. This section supersedes Prompt 1's statements that
WEEK derivation/evaluation are future work. All Prompt 1 declarations, including
WeeklySolveResult's explicit NOT_EVALUATED contract, remain unchanged. This slice
adds no search, assignment selection, generated portions, backend, persistence,
ranking or production/clinical approval. Phase 1-5 public interfaces are unchanged.

### Actual APIs and independent authority

Import from savora_ai.core.reasoning.weekly:

```python
def build_week_check_manifest(
    request: WeeklyPlanningRequest,
    *,
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: WeeklySourceSnapshot,
) -> ExpectedWeekCheckManifest: ...


def evaluate_weekly_trial(
    request: WeeklyPlanningRequest,
    trial: WeeklyTrial,
    *,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: WeeklySourceSnapshot,
    manifest: ExpectedWeekCheckManifest | None = None,
) -> WeeklyTrialEvaluation: ...
```

The public wrapper recursively revalidates the original request/trial/candidates,
independent KB, normalized context and weekly source. Exact source and context digests
must match the request, and existing KB/release expectations must match the accepted
synthetic KB. Conflicting provenance, including a counterfeit reserved derivation
reference, rejects. Candidate duplicates/malformed records reject atomically.

The manifest is always rebuilt from the complete accepted KB catalogue. Every
mandatory WEEK and DAY definition is selected in canonical identity order; active,
absolute, approved synthetic admission and exact applicability descriptor/dependency
policies are enforced before predicate execution. Optional supplied manifests must
validate and match that authoritative manifest digest; callers cannot reduce checks.
Unsupported legacy WEEK predicates retain their old upstream deferrals but reject
at this weekly boundary. False applicability cannot bypass admission validation.

Each day receives an exact ExpectedDayCheckManifest derived from the same weekly
request/source/context/KB. It must carry the authoritative WEEK definitions unchanged
in deferred_checks. Every selected combination proof is also checked against the
complete DAY/WEEK definition set, retaining the deferred-to-evaluated transition.

Independent argument selection is still a trusted loader responsibility. Matching
unsigned content and synthetic approval metadata do not authenticate a provider.
Do not promote request data into the independent source/KB/context arguments.
Serialized computed results remain evidence records, not external authorization.

### Pure fact and DAY/WEEK computation

core/reasoning/week_checks.py isolates private request-local preparation and pure
trial computation. _compile_week creates seven exact DAY manifests, one shared DAY
program and one WEEK applicability closure. Shared DAY compilation is safe here
because all seven manifests use identical rules, context and common option source;
request/day/trial bindings are still taken from each exact day manifest.
Program observation/applicability lookup maps are immutable MappingProxyType records.
No global cache or caller-prepared PASS input is exposed.

_assess_week evaluates the supplied choices in day-index/BREAKFAST/LUNCH/DINNER order.
It calls the existing _assess_day helper for each exact DailyTrial; it never invokes
solve_daily_plan. All seven DAY evaluations are retained, including FAIL and UNKNOWN.
DayFacts continue to name the DailyTrial digest. No assignment digest substitutes for
that trial identity, and no alternative assignment is selected in this prompt.

The three WEEK facts are always derived, in this order:

1. synthetic_week_complete is evidenced True only when every exact day aggregate is
   PASS. This includes recipe/combination eligibility, FIXED portions, suitability
   and all mandatory DAY coverage. Otherwise value=None, complete=False; no False or
   True is invented from unresolved/failed prerequisites. Structural defects reject.
2. synthetic_week_quantity_total sums one complete FIXED whole-meal measurement per
   selected slot. All 21 contributions must be present and complete. Missing/null or
   incomplete measurements yield value=None, never a partial complete total. Exact
   Python integers retain zero, values above 2**53 and 2**63, and the approved maximum.
   Component and DAY totals are never added again. No conversion/rounding occurs.
3. synthetic_week_max_recipe_slot_occurrences counts canonical recipe IDs once per
   selected slot, using distinct IDs within that slot, then takes the maximum.
   Different configurations retain canonical recipe identity. Count completeness
   requires established candidate membership, composition completeness and upstream
   source authority for every selected option. Missing identity/composition evidence
   yields UNKNOWN. Safety/role UNKNOWN does not erase independently known recipe
   presence; a supplied admitted repetition rule may still refute that hypothesis.

Measurements retain exact source/digest contributions pointing to full common-source
components, preparations, quantities and evidence. Occurrences retain each day/slot/
option and exact unique recipe IDs, with complete composition/prerequisite provenance
in the fact evidence and retained source/proofs. Repetition has no implicit limit.

synthetic-week-derivation / 1, locator urn:savora:synthetic-week-fact-derivation:1,
names the synthetic algorithm; it is not a nutrition source or clinical reference.
The computed result pins synthetic-week-fact-derivation.v1 and
synthetic-week-evaluation.v1. Existing fixed-meal measurement policy is reused.

### Predicates, applicability and aggregation

The existing exact _predicate helper supplies boolean EQ/NE and integer
LT/LE/GT/GE/EQ/NE. Thresholds/units come only from admitted definitions. The complete
existing conservative applicability dependency closure is executed: any unknown
local condition/dependency stays UNKNOWN, even behind a local False. Evidenced
NOT_APPLICABLE resolves mandatory coverage while predicate status remains UNKNOWN.
Every mandatory WEEK rule receives a full evaluation, even after DAY UNKNOWN or
another known FAIL. Empty mandatory WEEK coverage remains UNKNOWN.

The WEEK trace binds candidate_id to the weekly trial digest and uses
week-manifest-<manifest digest> with expected-week-check-manifest.v1:<digest>.
Evaluation reasons are synthetic-week-evaluation.v1:APPLICABILITY_UNKNOWN,
:NOT_APPLICABLE, :REQUIRED_FACT_UNKNOWN, :PREDICATE_TRUE or :PREDICATE_FALSE.
Explanations retain exact rule references, status/reason and evidence unions.

week_status aggregates only the complete WEEK trace. status combines every DAY
aggregate with week_status: any known FAIL dominates UNKNOWN; otherwise any unknown
obligation blocks PASS. A numeric WEEK FAIL can therefore refute a DAY UNKNOWN trial.
PASS describes this supplied trial, not CSP search completeness, preference optimality
or production safety. No FEASIBLE/INFEASIBLE/TIMEOUT outcome is emitted here.

### Computed DTOs and output verification

Import from savora_ai.schemas.weekly_evaluation. Exact fields:

| DTO | Fields |
|---|---|
| WeeklyDayEvaluation | `day`, `manifest_digest`, `evaluation` |
| WeekRuleExplanation | `manifest_digest`, `trial_digest`, `rule_reference`, `status`, `reason`, `evidence` |
| WeeklyTrialEvaluation | `schema_version`, `evaluator_policy_version`, `derivation_policy_version`, `plan_feasibility`, `search_completeness`, `manifest`, `candidates`, `trial`, `recipes`, `options`, `days`, `facts`, `trace`, `week_status`, `status`, `explanations` |

WeeklyTrialEvaluation retains the accepted manifest/common source/KB, exact candidates,
recipe/combination proofs, seven day records, three recomputed facts, complete WEEK
trace, statuses and explanations. plan_feasibility and search_completeness remain
NOT_EVALUATED. There is no search outcome or exhaustion claim field.

All new DTOs preserve strict frozen/extra-forbidden/camelCase behavior, canonical
enums, tuples, recursive storage revalidation and original-JSON protections. The
computed parent rebuilds public prerequisites from retained source/candidate inputs,
recomputes DAY/WEEK facts/applicability/predicates and compares all records, bindings,
statuses and explanations. Mutating a declaration cannot retain an accepted stale
PASS merely by rehashing it. A wholly replaced, internally consistent unsigned
release still cannot authenticate itself; consumers must use independent public inputs.

### Preparation cost and Prompt 3 boundary

Preparation evaluates the full candidate pool and each distinct selected option
once per pass, shared across all 21 occurrences and all WEEK predicates. Unselected
source options remain structurally validated but are not evaluated for this trial.
The inherited Phase 4 call still filters the full recipe pool internally.

For m distinct selected options, one preparation pass makes m public combination
calls and 1+m recipe batches. Initial computation and computed-output verification
each perform a pass: evaluate_weekly_trial therefore makes 2*m combination calls
and 2*(1+m) recipe batches. Deserializing/revalidating a result repeats verification.
This intentional correctness cost is documented, not claimed as single-pass reuse.
No public Phase 3/4 calls occur per DAY or per WEEK predicate. No global PASS cache.

Prompt 3 can reuse the private compiled DAY/WEEK computation with locally validated
preparation and bounded request-local caches. A larger optimization of public
prerequisite validation/output verification requires independent equivalence tests;
no validation bypass, unchecked model construction or public signature change is
introduced here. Node/deadline/proof budgets and finite-domain search remain deferred.
The original 1 MiB raw JSON bound remains unchanged; maximal Python inputs/results
are not promised to fit transport. Full selected provenance can be expensive.

Member 1 still supplies verified fixed source/preparation/measurement/suitability
records. Member 3 owns independently authenticated loading, normalized profile/context,
release freshness/revocation and future transport/resource/persistence policy.
Synthetic unit/threshold tests do not provide medical approval or real nutrition.

### Prompt 2 verification

Final lint, format, typecheck, regression counts and Git scope are recorded below. No dependency/lockfile, Prompt 1 Python file or Phase 1-5
public interface was changed by Prompt 2. No EDA notebook or Git publication ran.


### Prompt 2 final verification and scope

All checks used the existing isolated Windows environment and final Python source/
tests. Only this handoff was subsequently updated with results.

| Check | Actual final result |
|---|---|
| uv run --frozen --no-sync ruff check . | PASS; All checks passed |
| uv run --frozen --no-sync ruff format --check . | PASS; 126 files already formatted |
| uv run --frozen --no-sync python -m pyright | PASS; 0 errors, 0 warnings, 0 informations |
| uv run --frozen --no-sync python -m pytest -q | PASS; 3,833 passed, 1 skipped in 767.48s (0:12:47) |
| New WEEK evaluation cases | 62 passed within the final full run |
| Focused development runs | Initial 27 passed in 144.81s; expanded 58 passed in 221.56s; five final edge/call-count cases passed in 29.70s |
| Public prerequisite counts | Verified 2 combination calls and 4 recipe batches for one selected option across 21 slots and three WEEK predicates; a fresh request repeats all work |
| AI boundary isolation | PASS; new production modules import no backend, FastAPI or SQLAlchemy code |
| Dependency integrity | PASS; uv.lock, root and AI pyproject.toml match HEAD |
| Whitespace/index/scope | PASS; new Python files and handoff checked, index empty, intended files only |

The one skip is the existing optional full Food.com recipe-level verification,
which requires FOODCOM_RAW_RECIPES. It was also skipped in Prompt 1. No EDA notebook
ran. Frontend checks were not run because no frontend, backend transport or generated
OpenAPI/TypeScript contract changed.

Independent literal tests cover boolean and six integer operators, exact 21-slot
aggregation including zero/large integers/representation maximum, duplicate recipe
occurrences, configuration reuse, DAY/WEEK PASS/FAIL/UNKNOWN, unknown dependencies
behind local False, NOT_APPLICABLE, missing composition/identity/measurements,
UNASSIGNED portions, reduced manifests, foreign independent sources/context/releases,
legacy or unapproved rules, counterfeit enums, hostile containers, malformed unchecked
models, original JSON duplicates/aliases and tampered facts/statuses/traces/explanations.
The output round-trip fixture fits the unchanged 1 MiB raw JSON boundary. Test expected
values/statuses are literal; no production WEEK predicate/aggregation helper serves as
an expected-value oracle. Input constructors are independently defined in this test
module and do not import earlier test fixtures.

No in-scope HIGH/MEDIUM defect remains reproduced. Preparation/output verification
cost is explicit; no performance SLO or production/clinical approval is asserted.
Pure WEEK computation and complete DAY/WEEK compatibility are implemented. Full
weekly search, verified search coverage and computed CSP outcomes remain Prompt 3.

Prompt 2 created exactly four files under apps/ai_system:
- src/savora_ai/core/reasoning/week_checks.py
- src/savora_ai/core/reasoning/weekly.py
- src/savora_ai/schemas/weekly_evaluation.py
- tests/test_weekly_evaluation.py

Prompt 2 updated only this existing handoff. All Prompt 1 Python files and earlier
local work remain intact. The cumulative Phase 6 worktree has two tracked modifications
and seven untracked files; all are the intended Prompt 1/2 bundle. Branch remains
feature/member2-weekly-csp at HEAD 7a00114576d59a4a5e628b37f481bb6565f777e7.
Index empty. No staging, commit, push, merge, rebase, reset or PR operation occurred.

Verdict: READY FOR PHASE 6 PROMPT 3 (synthetic scope). Work stops after Prompt 2.


## Phase 6 Prompt 3: bounded chronological weekly search

This section supersedes earlier statements that weekly search is deferred. Scope
remains synthetic only. Reviewed the actual Phase 1-6 handoffs, AGENTS.md, relevant
ARCHITECTURE.md sections 4, 8-9 and ownership/evaluation requirements, weekly and
daily schemas/evaluators/tests, and the existing worktree/index before editing.
The intentionally limited chronological baseline does not implement architecture's
future forward checking, MRV, generated portions or preference optimization.

### Public API and strict computed result

Import `solve_weekly_plan` from `savora_ai.core.reasoning.weekly`:

```python
solve_weekly_plan(
    request: WeeklyPlanningRequest,
    *,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: WeeklySourceSnapshot,
    limits: WeeklySearchLimits | None = None,
    clock: Callable[[], float] = monotonic,
) -> ComputedWeeklySolveResult
```

Import ComputedWeeklySolveResult from `savora_ai.schemas.weekly_solver`; proof,
statistics, timing and witness DTOs live in `savora_ai.schemas.weekly_search` to
keep the evaluator/contract import graph acyclic. Original
WeeklySolveResult and WeeklySearchState remain unevaluated declarations; neither
accepts a computed search outcome. Phase 1-5 public interfaces remain unchanged.

ComputedWeeklySolveResult retains manifest, candidates, limits, certificate,
outcome, optional witness, bounded diagnostics and timing. Its criterion is
FIRST_FEASIBLE; it makes no optimality claim. A witness retains the complete trial,
FIXED WeeklyAssignment, seven WeeklyWitnessDay evaluations, three WEEK facts,
complete WEEK trace and explanations. Access the persisted-plan candidate through
`result.witness.assignment` only when outcome is FEASIBLE. This module performs no
persistence, HTTP, authentication, ranking, composition or model calls.

Strict frozen, extra-forbidden, camelCase, canonical enums, tuple containers,
recursive unchecked-instance revalidation and original-JSON duplicate/alias
protection are inherited. Use validate_contract_json for untrusted original JSON;
native model_validate_json remains a trusted round-trip tool. The existing 1 MiB
JSON limit is unchanged. Large Python results need not fit that transport limit.

### Shared authoritative preparation

The public boundary revalidates all independent inputs, release/context bindings,
candidate identities and fact vocabulary before consulting search budgets. Invalid
structure raises ValidationError, including when a budget or deadline is already
exhausted. It rebuilds the exact complete DAY/WEEK manifest from the accepted KB.

Each pass filters the full candidate pool once and calls the existing public
combination evaluator once per distinct referenced domain option, in canonical
option order. Every combination call still filters the entire pool internally.
Unreferenced source options are structurally validated but are not evaluated.
Preparation checks exact fixed configuration, preparation, trusted composition,
recipe membership, role references, portions and slot suitability. Unrelated
recipe failures do not exclude a combination that does not reference them.

For m referenced options, initial execution makes m combination calls and 1+m
recipe batches. Strict computed-output verification independently repeats that
bounded preparation once: total 2*m combination calls and 2*(1+m) recipe batches.
This cost never scales with the Cartesian number of weekly assignments. No caller
PASS records, unchecked model construction or global caches authorize a witness.
Raw-result revalidation is another independent verification invocation, not part of
the original solve's counters or timing.

### Search, DAY/WEEK interaction and outcomes

Domains are the supplied finite sets, sorted using Phase 5 _option_order. Slots
are D1 BREAKFAST/LUNCH/DINNER through D7 DINNER, regardless of input declaration
order. Chronological DFS materializes one prefix, never the Cartesian product.
Only known unary slot FAIL values are excluded. At each completed day, all DAY
obligations are evaluated; a definite aggregate FAIL excludes that entire subtree.
UNKNOWN continues in exact canonical position. There is no numeric forward pruning.

At every complete trial, all WEEK obligations are evaluated using the existing
pure WEEK derivation and the seven locally evaluated days. The private shared
helper accepts these local assessments to avoid evaluating seven days again at
every leaf. Public supplied-trial evaluation still computes its own days. DAY
facts are keyed to each actual derived daily request/trial, and WEEK quantities,
recipe occurrences and evidence retain the existing exact source bindings.

A bounded request-local FIFO memo stores DAY assessments, keyed by day index and
three exact option IDs within the immutable request/manifest/source. Different
day identities never collide. Cache zero disables reuse; eviction only repeats
work and never excludes branches. The seven active days and prepared option
records are required working state, separate from optional memo capacity.

| Outcome | Verified condition |
|---|---|
| FEASIBLE | First complete FIXED witness whose prerequisites, seven DAY assessments and every WEEK obligation resolve successfully, verified again at output |
| INFEASIBLE | Complete finite-domain coverage by evaluated known failures, unary exclusions or known DAY-failure subtrees, with no surviving unknown leaf |
| INSUFFICIENT_DATA | Complete coverage with at least one unrefuted UNKNOWN leaf and no feasible witness |
| TIMEOUT | Required preparation, node, evaluation, predicate, proof operation or verification exceeds its declared bound/deadline |

Known WEEK FAIL dominates DAY UNKNOWN. Missing measurements remain unknown, never
zero. Empty DAY or WEEK inventories remain conservative through existing empty
hard-status semantics. Repeated recipes/configurations are allowed unless an
explicit admitted authoritative rule restricts them. No default cuisine, nutrition,
distinctness, swap, generated portion or preference policy is introduced.

### Executable coverage certificate and bounded proof storage

WeeklySearchCertificate is an ordered, executable certificate, rather than an
exhaustive flag accepted on trust. It retains a recipe-proof digest, a canonical
preparation prefix (full decision digest and three slot statuses), every completed
DAY assessment and WEEK leaf (original-domain index prefix and complete evaluation
digest), active frontier, next sibling cursors, deadline checkpoint and statistics.
DAY digests bind full facts, rule trace, explanations and status. WEEK leaf digests
bind the exact trial, all seven days, every WEEK fact and complete WEEK trace.
All digests use ordinary ordered canonical JSON/SHA256, not the unordered snapshot
hash used for declarations. The original manifest/source/KB/candidates retain all
inputs and evidence needed to reconstruct full prerequisites and evaluations.

The strict result validator reruns bounded deterministic preparation/search from
those retained inputs, reconstructs unary exclusions and each DAY-failure subtree,
and compares the complete ordered certificate, cursors, counters, diagnostics,
outcome and witness. It does not trust supplied PASS labels, counters, hashes,
exhaustive flags or sampled diagnostics. Rehashing altered outputs cannot make
an incomplete traversal exhaustive. No full Cartesian proof is precomputed.

A DAY event records its entire current prefix even for a memo hit. Completed
leaves are retained separately. Unknown hypotheses count only unrefuted complete
leaves; a known WEEK failure does not leave a DAY unknown hypothesis unresolved.
The active prefix and next sibling indexes identify unexplored suffixes against
the original sorted domains. Preparation interruption is distinguished by its
canonical shorter preparation prefix. Empty or fully unary-excluded domains are
verified directly from the original domains and complete preparation stamps.

Proof limits cover the mandatory compact replay certificate: one recipe record,
one record per prepared option and one per DAY/leaf event. Bytes are charged
before work using a 4096-byte fixed metadata envelope, the 64-byte recipe hash,
compact JSON record lengths plus separators, and worst-case UNKNOWN spelling for
option status stamps. Thus proof_bytes is a conservative reserved size, not a
claim of exact serialized allocation. Zero proof capacity returns TIMEOUT. A small
fixed termination envelope is still returned on zero capacity. Source inputs,
one reconstructed evaluation, required working state, bounded memo, witness and
sample diagnostics have separate structural bounds; proof_bytes is not a cap on
whole-result JSON or process RSS. Full derived traces for failed leaves are
reconstructible by replay, rather than copied into the compact certificate.

Diagnostic sampling is capped independently and never substitutes for mandatory
coverage records. Exhausting proof records/bytes stops before the necessary
record-producing work and returns TIMEOUT, preserving the last verified prefix.
This certificate deliberately trades output size for bounded replay cost.

### Resource semantics, measurements and deadlines

WeeklySearchLimits is reused unchanged. Evaluation capacities reserve **both**
execution and independent output verification before every new operation:
option_evaluations, day_evaluations, week_evaluations and predicate_evaluations
include these two passes. In consequence an odd remaining evaluation allowance
cannot authorize an operation needing two units. For example the single-option
21-slot witness needs option=2, DAY=14, WEEK=2, nodes=21, plus its exact predicates
and proof reservation. The current max_option_evaluations ceiling of 150 allows
at most 75 distinct referenced options when both passes must prepare them. A
larger option set conservatively times out; it cannot produce false infeasibility.

Predicate work charges all mandatory predicate obligations, including unknown or
not-applicable obligations, across recipe batches, combination, DAY and WEEK
assessments. This is a conservative semantic-work counter, not a count of Python
comparison instructions or repeated structural validator internals. Node counts
are chronological assignment visits in the logical search; replay verifies these
visits rather than claiming a second independent candidate search. Memo hits
produce proof events but do not consume new DAY/predicate assessments. Statistics
also retain recipe batches/candidate assessments, cache high-water/hits, known
failures, unknown leaves, backtracks, unary exclusions/DAY prunes, proof reservation,
checkpoints, exhaustive coverage and explicit search termination.

A deadline is an absolute finite monotonic reading supplied by the caller.
Checkpoints precede preparation, nodes and DAY/WEEK work, with a final search
check. The output verifier is already budget-reserved; it completes its current
bounded validation and samples the actual clock at the end. Expiration there
sets TIMEOUT, removes the witness and records timing.validation_deadline_reached
with the observed validation_finished_at. Search termination and this output-stage
expiration are distinguished; an output-stage timeout may retain completed search
coverage without offering a feasible plan. No cooperative deadline interrupts
an already running validation, prerequisite or evaluator call.

Timing records preparation_seconds (including initial structural/release/manifest
validation and compilation), search_seconds and output_validation_seconds
(including nested output validation and proof replay). Clock observations/timing
are observational metadata, not externally authenticated evidence. A claimed
expired timestamp can only downgrade to TIMEOUT, never authorize a plan or prove
infeasibility. Non-finite, boolean and backwards public clocks are rejected.

### Independent verification and integration boundaries

New tests in test_weekly_solver.py share only synthetic input constructors with
the Prompt 2 test module. Literal expected outcomes and the separate itertools
product oracle use exact 2/5 mg arithmetic and no production predicates,
aggregation, pruning, hashing or search helpers. The oracle varies at most six
slots (64 leaves), never the full 21-slot Cartesian space. It checks exact first
witness and exhaustive contradiction for three and six variable slots, in
addition to pruning, UNKNOWN, empty inventories/domains, explicit repetition,
strict ingress, original JSON duplicates, forged certificates, cache eviction,
all resource ceilings, cooperative clocks and declaration-order permutations.

Performance is intentionally bounded, with no production SLO. Public prerequisite
and output validation remain expensive; large exhaustive problems should return
TIMEOUT rather than outrun caps. There is no unbounded stress test or EDA run.
Member 1 must supply verified fixed compositions, recipe/preparation/configuration
identity, measurement evidence and suitability. Member 3 must independently load
and authenticate releases/context/sources and decide future transport limits,
persistence and timeout policy. No medical approval or real nutrition is implied.
No backend, frontend, shared OpenAPI/TypeScript, dependency or lockfile changed.

Final measured performance, check results and local Git scope are recorded below.


### Prompt 3 bounded performance observations

Focused run: seven benchmark cases passed in 69.97s on the existing Windows
CPython 3.14.7 environment. These observations are local synthetic measurements,
not production latency guarantees. All use two exact configurations of the same
canonical recipe (2/5 mg); non-variable slots have one supplied option. Search and
output verification are measured separately. Evaluation counts include both
execution and reserved verification, while nodes describe logical DFS visits.

| Workload | Outcome | Prepare s | Search s | Output verify s | Nodes | DAY / WEEK evals | Combination / recipe batches | Reserved proof B |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| One option per slot, total 42 | FEASIBLE | 1.5304 | 0.7889 | 2.3306 | 21 | 14 / 2 | 2 / 4 | 5411 |
| Two alternatives in 3 slots, total 45, second leaf | FEASIBLE | 1.7464 | 0.8857 | 3.1996 | 40 | 16 / 4 | 4 / 6 | 6662 |
| Two alternatives in 3 slots, total 51, last leaf | FEASIBLE | 2.1130 | 1.4747 | 3.3374 | 158 | 28 / 16 | 4 / 6 | 13208 |
| Two alternatives in 3 slots, impossible total 43 | INFEASIBLE | 1.6496 | 0.9879 | 2.8753 | 158 | 28 / 16 | 4 / 6 | 13208 |
| Two alternatives in 6 slots, total 60, last leaf | FEASIBLE | 1.8951 | 5.9623 | 9.0628 | 1086 | 42 / 128 | 4 / 6 | 67808 |
| Two alternatives in 6 slots, impossible total 43 | INFEASIBLE | 2.1448 | 6.3270 | 7.5914 | 1086 | 42 / 128 | 4 / 6 | 67808 |
| Two alternatives in all 21 slots, node ceiling 80 | TIMEOUT | 2.1558 | 3.0655 | 4.8670 | 80 | bounded / 64 | 4 / 6 | bounded |

The six-variable workloads retain at most 21 memo entries, independent of their
64 evaluated leaves. The one-option witness retains seven memo entries. Zero- and
one-entry eviction tests produce the same witness while doing additional DAY
work. The large-domain benchmark stops at its node ceiling rather than attempting
2**21 assignments. Spy tests independently verify 4 combination calls and 6 recipe
batches for two options across eight failed leaves; a fresh request repeats all
calls, ruling out accidental cross-request reuse.


### Prompt 3 module scope and import audit

New files:
- apps/ai_system/src/savora_ai/core/reasoning/weekly_search.py
- apps/ai_system/src/savora_ai/schemas/weekly_search.py
- apps/ai_system/src/savora_ai/schemas/weekly_solver.py
- apps/ai_system/tests/test_weekly_solver.py

Updated existing Prompt 2 files:
- apps/ai_system/src/savora_ai/core/reasoning/week_checks.py (shared single-option
  preparation and optional locally assessed DAY records for pure WEEK computation)
- apps/ai_system/src/savora_ai/core/reasoning/weekly.py (strict public solver)
- docs/member2_weekly_csp.md (this handoff)

The first full regression attempt exposed an import-cycle audit failure between
the computed result validator and search kernel. That attempt was stopped. Proof,
statistics, witness and timing DTOs were moved into schemas/weekly_search.py, so
the kernel no longer imports its computed-result validator. The existing
architecture audit and the 21-slot witness test then passed (2 cases in 5.71s),
and all required checks/full regression were restarted on the corrected graph.
No audit assertion or earlier test was weakened.


### Prompt 3 final verification and handoff

The final corrected source and tests passed all required checks. Only this Markdown
handoff was subsequently updated with the final measurements and Git state.

| Required check | Actual final result |
|---|---|
| uv run --frozen --no-sync ruff check . | PASS; All checks passed |
| uv run --frozen --no-sync ruff format --check . | PASS; 130 files already formatted |
| uv run --frozen --no-sync python -m pyright | PASS; 0 errors, 0 warnings, 0 informations |
| uv run --frozen --no-sync python -m pytest -q | PASS; 3,899 passed, 1 skipped in 1120.46s (0:18:40) |
| New solver tests | All 66 cases included in the final complete suite |
| Independent Cartesian expectations | All six oracle cases match literal outcomes and exact first witnesses, up to 64 leaves |
| Bounded benchmark run | 7 passed in 69.97s; measurements recorded above |
| Import/dependency audit | PASS in focused reproduction and final full suite; no local import cycles or forbidden backend/DB dependencies |
| Dependency/lockfile integrity | PASS; uv.lock and root/AI/backend pyproject.toml match HEAD |
| Whitespace/index/scope | PASS; intended Phase 6 files only, index empty |

The one skip is the existing optional Food.com full-recipe check requiring
FOODCOM_RAW_RECIPES, also skipped in prior phases. No EDA notebook, frontend build,
database task, dependency change or network operation ran. Python coverage includes
all prior phases, strict original JSON, canonical enums/hostile containers,
independent order permutations, complete provenance, proof/frontier/counter
forgeries, exact budget boundaries, deadline stages and conservative outcomes.

No unresolved in-scope HIGH/MEDIUM defect remains reproduced. Limitations remain
explicit: synthetic-only semantics, repeated authoritative output verification,
cooperative deadlines, effective 75-distinct-option capacity with the existing
150-operation ceiling, bounded proof replay, and separate result/transport size
policy. No production/clinical approval or optimality claim is made.

Final branch: feature/member2-weekly-csp. HEAD:
7a00114576d59a4a5e628b37f481bb6565f777e7. Cumulative Phase 6 Git state is two tracked
modifications and eleven untracked intended files; all previous local work is
preserved. Index empty. No staging, commit, push, merge, rebase, reset or PR action
occurred. Prompt 3 added four files and updated three existing Prompt 2/handoff
files, exactly as listed above. No Phase 1-5 public signature changed.

Verdict: READY FOR PHASE 6 PROMPT 4 (synthetic scope). Work stops after Prompt 3.

## Prompt 4: final independent Phase 1-6 audit (18 October 2026)

This section supersedes the earlier handoff's final counts and Git inventory.
The existing implementation was audited in Savora-Phase6 on the requested
feature/member2-weekly-csp branch at
7a00114576d59a4a5e628b37f481bb6565f777e7. The user explicitly selected that
branch despite the usual feat/ prefix convention. All pre-existing tracked
changes and twelve untracked Phase 6 files were retained. The independent
integration file already existed at audit start; this audit did not create it.

### Compatibility, actual APIs and ownership

The actual public interfaces remain build_week_check_manifest,
evaluate_weekly_trial and solve_weekly_plan in core/reasoning/weekly.py, with
the exact annotated signatures documented above. ComputedWeeklySolveResult is
in schemas/weekly_solver.py; certificate, statistics, witness and timing DTOs
are in schemas/weekly_search.py. All remain strict/frozen/extra-forbidden,
camelCase, canonical-enum and built-in-tuple contracts with recursive original
storage revalidation. No Phase 1-5 public API, backend, frontend, shared wire
contract, dependency or lockfile changed during this audit.

| Phase | Independently checked compatibility |
|---|---|
| 1 | Complete mandatory hard coverage; FAIL dominates UNKNOWN; missing/empty hard sets cannot authorize PASS; rule, applicability and evidence identities remain intact. |
| 2 | Accepted synthetic KB and complete workflow/scope catalogue; exact graph, catalogue, context and KB release pins; provenance consistency and conservative absence semantics. |
| 3 | Authoritative recipe filtering, complete required/deferred manifests, strict original-JSON ingress and no caller-supplied PASS authority. |
| 4 | Exact recipe/component/preparation/fixed-configuration identity; complete prerequisites and preserved DAY/WEEK definitions. |
| 5 | Seven exact derived DAY requests/manifests/trials, fixed measurement/suitability binding, canonical daily decisions, facts and explanations; public APIs remain unchanged. |
| 6 | Application-owned WEEK admission, complete WEEK inventory, seven days/21 slots, authoritative DAY/WEEK computation, evidence/explanation/source binding and verified finite search. |

WEEK admission remains synthetic-attributes.v5-week and
synthetic-week-policy.v1: ACTIVE/ABSOLUTE/APPROVED/SYNTHETIC/CULINARY,
exact scope/unit/applicability, registered prerequisites and supported operators.
No new repetition, nutrition, cuisine or clinical threshold was activated.
The three WEEK predicates preserve complete-day truth, exact fixed-meal integer
summation and canonical recipe presence once per slot. Different configurations
of the same recipe share its occurrence identity; duplicate components within
one slot count once. Missing data remains UNKNOWN and no conversion occurs.
The maximum quantity is exactly 21*((2**63-1)//3) =
64,563,604,257,983,430,642; it is a representation bound, not clinical policy.
Literal boolean EQ/NE and integer LT/LE/GT/GE/EQ/NE boundary tests, including
values beyond 2**53 and 2**63, remain in the complete regression.

### Independent CSP, ingress and proof checks

The retained solver suite has six literal Cartesian oracle cases, up to 64
leaves. The separate integration fixture constructs its own two recipes,
three fixed options (3/7/11 mg), catalogue, context and source evidence; it
imports no earlier fixture or production expected-value helper. It covers the
recipe-to-combination-to-DAY-to-WEEK chain, all four outcomes, DAY pruning,
repetition, cross-day recovery, deterministic selection and exact explanations.

Eight additional in-memory finite-product probes used independently calculated
integer sums, per-day caps, recipe-presence counts and first witnesses.
The overridden slot domains and literal results were:

| Slot overrides (zero-based chronological positions) | WEEK total | DAY maximum | Recipe maximum | Expected outcome |
|---|---:|---:|---:|---|
| 2/5/20: (0,1) | 67 | none | 21 | FEASIBLE; only position 20 uses option 1 |
| 2/5/20: (0,1) | 64 | none | 21 | INFEASIBLE |
| 0: (0,2), 10: (0,1), 20: (1,2) | 79 | none | 20 | FEASIBLE; positions 0/20 use option 2 |
| same asymmetric domains | 76 | none | 20 | INFEASIBLE |
| 0: (0,1,2), 1: (0,1), 3: (0,2) | 75 | 17 | 20 | FEASIBLE; positions 1/3 use options 1/2 |
| same asymmetric domains | 75 | 12 | 20 | INFEASIBLE |
| 0: (1), 9: (2), 20: (0,1) | 75 | none | 20 | FEASIBLE; first value at position 20 |
| 0: empty, 20: (0,1) | 63 | none | 21 | INFEASIBLE; zero nodes |

All other positions use option 0. Options 0/1 contain recipe A; option 2
contains recipe B. Three additional budget probes used two choices at position
20 and an impossible total of 64: node ceilings 20/21/22 produced respectively
0/1/2 complete leaves and TIMEOUT/TIMEOUT/INFEASIBLE. All eleven probes passed.
Expected answers used itertools.product and literal arithmetic only, without
production search, predicate, aggregation, pruning or hashing helpers.

FEASIBLE requires a complete FIXED witness, all seven DAY assessments and every
mandatory WEEK check resolved through PASS or evidenced NOT_APPLICABLE.
INFEASIBLE requires full original-domain coverage by known failures or sound
unary/DAY pruning. Complete coverage with an unrefuted UNKNOWN yields
INSUFFICIENT_DATA. Incomplete required work yields TIMEOUT. A known WEEK failure
can refute DAY UNKNOWN; no unknown hypothesis is pruned solely for being unknown.
Candidate/domain permutations preserve canonical first witnesses.

Computed output replays bounded deterministic preparation/search from the retained
accepted original domains, candidates, source, context and KB. It compares the
entire ordered certificate, preparation stamps, DAY/leaf records, frontier,
cursors, counters, diagnostics, outcome and witness. Rehashed altered proofs,
missing/duplicate/reordered leaves, changed pruned-subtree records, truncated
coverage, false exhaustive flags, erased unknowns, changed witness facts and
omitted mandatory evaluations reject. This is deterministic replay of the same
kernel, supplemented by independent finite-product tests; it is not a separately
implemented solver or a cryptographic authentication scheme.

The existing adversarial coverage checks counterfeit enums, hostile containers,
unchecked copies/constructs, duplicate original JSON keys/aliases, excessive
nesting/size, nonfinite/overflowing numbers, reduced rehashed manifests, missing
catalogue coverage, stale releases, measurement/preparation/configuration
transplants, contradictory evidence, unsupported WEEK predicates and unknown
applicability dependencies. Unknown dependencies still dominate false local
applicability. The supported untrusted wire ingress remains
validate_contract_json on original text/bytes (1 MiB, depth 64); native JSON
methods are trusted round-trip tools and do not recover duplicate keys.

### Confirmed defects and smallest corrections

| ID / severity | Reproduction and root cause | Correction and validation |
|---|---|---|
| P6-AUDIT-01 / LOW | Required Pyright failed at the existing integration test's dictionary-unpacked model_construct call: inferred values could be assigned to Pydantic's special _fields_set parameter. | Explicit dict[str, Any] payload, then the same malformed days=() assignment and original rejection assertion. Focused regression: 1 passed in 10.92s. No production semantics changed. |
| P6-AUDIT-02 / LOW | Solve with deadline=10 and clock=10, remove limits.deadline, and clear the observational output timeout flag. ComputedWeeklySolveResult previously accepted TIMEOUT/DEADLINE/checkpoint=1 with no declared deadline. Replay honored stop_at independently of the deadline configuration. This could fabricate a conservative timeout record, but could not authorize FEASIBLE or INFEASIBLE. | The Phase 6 computed-result validator now rejects a deadline checkpoint without a declared deadline. One focused integration regression was added. New regression plus existing before-preparation, mid-search and post-verification deadline tests: 4 passed in 15.32s. |

No HIGH/MEDIUM implementation defect was reproduced. The first full run was
stopped when the new source correction became necessary; it is NOT counted as
completed verification. The final complete run below used the corrected source
and tests. No Phase 1-5 API or semantic correction, unrelated refactor or
optimization was introduced.

### Bounded performance and resource measurements

Two local Windows/CPython 3.14.7 scenarios were measured after stopping the
superseded full run and completing focused deadline verification. Input fixture
construction and imports were outside measurement. Lightweight wrappers recorded
inclusive stage times; authoritative output verification stayed enabled.
These are synthetic observations, not production latency guarantees.

| Workload | Prepare s | Search s | Output verification s | End-to-end s | Nodes | DAY / WEEK evaluations | Proof reserved / serialized B |
|---|---:|---:|---:|---:|---:|---:|---:|
| Single option, one leaf, total 42 | 1.3858 | 0.7343 | 2.1025 | 4.2231 | 21 | 14 / 2 | 5,411 / 1,896 |
| Two options in first six positions, 64th leaf, total 60 | 1.4891 | 5.8463 | 7.8727 | 15.2097 | 1,086 | 42 / 128 | 67,808 / 64,300 |

For the 64-leaf case, the initial pass measured input validation 0.0636s,
manifest rebuilding 0.1446s, shared seven-DAY compilation 0.6962s, two option
preparations 0.4709s, three recipe batches 0.3082s, 21 fresh DAY assessments
0.4814s, 64 WEEK assessments 3.0402s and proof encoding 0.3223s.
Replay measured compilation 0.8925s, two option preparations 0.5115s,
three recipe batches 0.3375s, 21 DAY assessments 0.5288s, 64 WEEK assessments
2.9479s and proof encoding 0.3633s. These inclusive categories overlap:
combination preparation contains recipe filtering and proof encoding includes
evaluation digests. They must not be added as disjoint stage totals.
The search interval includes DFS and its trial/evaluation/evidence construction;
it is not a measurement of bare recursion instructions.

The reported 1,086 nodes are logical chronological partial-assignment visits:
sum(2**d for d in 1..6) + 15*64 = 126+960. Replay is not added to that node count.
Evaluation counters reserve both execution and replay, explaining 128 WEEK
evaluations for 64 logical leaves. Actual public prerequisite work was four
combination calls and six recipe batches across both passes, independent of
the 64 leaves. The DAY memo peaked at 21 entries with 371 hits per pass.
There is no cross-request cache or Cartesian materialization.

Node/evaluation/predicate/proof budgets are checked before their corresponding
work. Required proof capacity is distinct from diagnostic sampling. Proof
exhaustion stops with TIMEOUT, including at a full assignment; it cannot imply
exhaustive coverage. FIFO cache zero/eviction preserves alternatives and canonical witnesses when budgets permit; extra recomputation may reach an evaluation cap and return TIMEOUT. The 150 option
evaluation ceiling reserves two passes, allowing at most 75 distinct prepared
options. Proof bytes reserve a conservative compact certificate envelope,
not total source/result memory or process RSS. Full Python input validation and
one in-flight evaluation remain non-interruptible; deadlines are cooperative.
Large sources/results may exceed the separate 1 MiB wire limit.

Repeated strict preparation, seven derived DAY manifests, complete evidence and
output replay remain material costs. A substantial improvement needs a separately
reviewed validated-preparation/reuse design. No validation was weakened, no
global PASS cache was added, and no speculative optimization was performed.

### Final verification and exact local scope

| Required check | Actual final result |
|---|---|
| uv run --frozen --no-sync ruff check . | PASS; All checks passed |
| uv run --frozen --no-sync ruff format --check . | PASS; 131 files already formatted |
| uv run --frozen --no-sync python -m pyright | PASS; 0 errors, 0 warnings, 0 informations |
| uv run --frozen --no-sync python -m pytest -q | PASS; 3,920 passed, 1 skipped in 1277.64s (0:21:17), exit 0 |
| Phase 6 integration coverage | 21 cases included in the full run: 20 pre-existing cases and one new deadline-certificate regression |
| Independent CSP checks | All six solver and three integration Cartesian cases passed in the full run; eight extra Cartesian and three budget probes passed in memory |
| Focused corrected behavior | Typing-only malformed-storage case: 1 passed; new/existing deadline behaviors: 4 passed |
| Tracked and untracked whitespace/scope | PASS; git diff --check plus all twelve untracked text-file inspections |
| Imports and preservation | PASS; existing full-suite architecture audit, untracked import checks, nine untouched Phase 6 source/test fingerprints unchanged |
| Dependencies and index | uv.lock and root/AI/backend pyproject.toml unchanged; shared contracts unchanged; index empty |

The final source checks preceded only this Markdown handoff update. No Python
source or test changed after the completed final verification.

The optional Food.com recipe-level test is skipped when FOODCOM_RAW_RECIPES is
unset. No EDA notebook, frontend build, database operation, dependency install,
staging, commit, push, merge, rebase, reset or PR action occurred.

This audit created no repository files. It modified only:

- apps/ai_system/src/savora_ai/schemas/weekly_solver.py
- apps/ai_system/tests/test_member2_phase6_integration.py
- docs/member2_weekly_csp.md

All three were already present as untracked Phase 6 files at audit start.
The cumulative bundle against HEAD remains two tracked modifications:

- apps/ai_system/src/savora_ai/core/reasoning/manifest.py
- apps/ai_system/src/savora_ai/schemas/filtering.py

and twelve untracked files:

- apps/ai_system/src/savora_ai/core/reasoning/week_checks.py
- apps/ai_system/src/savora_ai/core/reasoning/weekly.py
- apps/ai_system/src/savora_ai/core/reasoning/weekly_search.py
- apps/ai_system/src/savora_ai/schemas/weekly.py
- apps/ai_system/src/savora_ai/schemas/weekly_evaluation.py
- apps/ai_system/src/savora_ai/schemas/weekly_search.py
- apps/ai_system/src/savora_ai/schemas/weekly_solver.py
- apps/ai_system/tests/test_member2_phase6_integration.py
- apps/ai_system/tests/test_weekly_contracts.py
- apps/ai_system/tests/test_weekly_evaluation.py
- apps/ai_system/tests/test_weekly_solver.py
- docs/member2_weekly_csp.md

Final branch is feature/member2-weekly-csp and HEAD remains
7a00114576d59a4a5e628b37f481bb6565f777e7. Index empty; working tree intentionally
dirty with the two tracked modifications and twelve untracked files above.
git diff --stat reports only the tracked admission changes (79 insertions,
2 deletions); it does not include the twelve untracked files. Review the entire
fourteen-file bundle rather than only the tracked diff.

### Remaining integration dependencies and verdict

Member 1 must supply independently verified canonical recipes, complete
compositions, exact prepared/fixed configurations, recipe-specific conversion
sources, per-configuration measurement evidence, targets and explicit suitability,
plus the separately agreed ranking integration. Member 3 must supply normalized
profile/context, authenticated independent source/KB/candidate loading, trusted
pins and freshness/revocation, approved transport/resource/error policy, backend
orchestration and persistence. Joint approval remains necessary for real
clinical rule sources/applicability, public DTO naming, numeric transport precision,
cuisine semantics and production provider authority.

The implementation is a synthetic chronological first-feasible FIXED-domain
baseline. It does not implement generated portions, forward checking, MRV,
preference optimization, locked-slot swap validation or clinical/production
clearance. Those architecture requirements remain explicit future work.
Matching unsigned hashes do not authenticate sources or replace independently
trusted release selection.

Verdict: READY TO COMMIT within the documented synthetic scope, after the two LOW corrections. No unresolved HIGH/MEDIUM defect was reproduced. Recommended next action: human review of the complete fourteen-file bundle, then commit only when explicitly instructed. Stop after this audit report.
