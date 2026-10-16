# Member 2 Phase 1: provisional rule and evidence contracts

Status: implementation for review, 12 October 2026. These DTO details are provisional;
this document does not record joint team approval. Architecture sections 3, 5, 11 and
15 remain authoritative. All test quantities, rules, sources and approvals are synthetic
and have no clinical or nutritional meaning.

## Implemented scope and ownership

Member 2 owns the rule declarations, evidence references, fact observations, declared
evaluations and hard-status aggregation in `savora_ai.schemas`. The package remains
independent of backend, persistence, HTTP, frontend, ranking and model adapters.

`RuleDefinition` binds stable rule ID/version, scope, severity, domain, predicate
attribute/operator/value/unit, explicit required facts, a versioned applicability
reference, evidence, rationale, lifecycle, approval metadata and environment.
`RuleReference` names a versioned rule or applicability definition. `EvidenceReference`
requires identity/version, source, locator and SYNTHETIC/PRODUCTION provenance.
Duplicate evidence ID/version pairs within a reference collection are rejected.
Throughout an eligibility trace, each `(evidence_id, version)` must have consistent
source, locator and environment metadata across manifest/evaluation rule evidence,
approval references, applicability evidence and observed-fact evidence. Identical
reuse is allowed. Different source versions may coexist; no source content is fetched
or verified.

All models use Pydantic v2 strict validation, frozen instances, immutable tuple
collections, forbidden extra fields and camelCase wire aliases. Python inputs use
enum instances and tuples; JSON inputs use enum tokens and arrays via
`model_validate_json`. Callers must use validating constructors; `model_construct`
and unchecked `model_copy(update=...)` are not accepted validation pathways. Instances
are revalidated when nested in another contract model. The public aggregation helper
also recursively copies every DTO field mapping into plain Python dictionaries before
strict `RuleTrace` validation; no nested DTO instance is retained. Tuple/list types,
enum instances and unknown unchecked fields are preserved, so strict validation rejects
invalid copied objects instead of normalizing them. The field mappings are read directly
because serialization may omit unknown copied fields. Structurally invalid inputs raise
`ValidationError`, including the original unchecked copy that removed all required facts;
they are never silently downgraded to UNKNOWN.

Supported provisional operators are LT/LE/GT/GE/EQ/NE/IN/NOT_IN. Numeric values require
an explicit supported unit and must be finite and non-negative; percent is 0–100.
Boolean/categorical values cannot carry measurement units. Ordered predicates cannot
take booleans; membership predicates require non-empty, unique string tuples as the
declared comparison set. IN/NOT_IN observations are temporarily restricted to scalar
strings whenever a non-null value is supplied; collection quantifiers remain unapproved.
Missing/null membership observations may remain UNKNOWN. Empty observed tuples can
represent other categorical facts but count as resolved only when completeness is
explicitly confirmed; incomplete tuples remain unresolved. Missing/null facts are
preserved separately. Supported units are g/mg/ug/mL/kcal/kJ/%
and dimensionless. No clinical thresholds, serving conversions or attribute-to-unit
registry are supplied. These unit restrictions validate value shape, not whether a
particular unit is scientifically appropriate for an attribute.

## Eligibility, applicability and severity

Severity describes policy strength: ABSOLUTE is hard, SOFT and INFORMATIONAL do not
affect hard eligibility. PASS/FAIL/UNKNOWN describe declared predicate outcomes.
Only aggregate PASS is eligible. A PASS here is a statement about declared coverage,
not a guarantee of medical suitability.

An APPLICABLE evaluation may declare PASS or FAIL only with evidenced applicability
and every required fact present, non-null and complete. Predicate fact units and
value kinds must match the definition; unit conversion is never implicit. Missing,
null or incomplete facts can be represented in UNKNOWN evaluations. They cannot
be relabeled as a resolved PASS/FAIL; contradictory declarations are rejected rather
than silently repaired. Zero, False and an empty observed set are real values only
when explicitly provided with completeness and provenance. Tuple observations cannot
serve as IN/NOT_IN predicate attributes under the temporary scalar restriction.

Eligibility manifests require ACTIVE hard rules. Every eligibility evaluation record,
including SOFT/INFORMATIONAL and NOT_APPLICABLE records, also requires an ACTIVE rule.
DRAFT/RETIRED rules can be stored as declarations but cannot participate in this
eligibility interface. Research/preview evaluation would require a separate explicitly
scoped interface. Lifecycle is distinct from evaluation status: ACTIVE does not imply
PASS, and UNKNOWN applicability does not relax the ACTIVE requirement.

UNKNOWN applicability requires predicate status UNKNOWN and blocks hard PASS.
NOT_APPLICABLE also carries predicate status UNKNOWN (the predicate did not run),
but evidenced NOT_APPLICABLE resolves that expected check during aggregation.
APPLICABLE and NOT_APPLICABLE require non-empty applicability evidence. The referenced
applicability definition and source truth are not executed or verified in Phase 1.

Aggregation is deterministic and independent of evaluation/manifest order:

1. Any known applicable required hard FAIL dominates missing checks and UNKNOWN.
2. An empty expected-check manifest returns UNKNOWN, including soft-only traces.
3. Missing required evaluations, unknown applicability or applicable UNKNOWN return UNKNOWN.
4. Every expected hard check resolved as PASS or evidenced NOT_APPLICABLE returns PASS.
5. SOFT/INFORMATIONAL results never alter these outcomes.

Identical duplicate evaluations are idempotent. Conflicting duplicate evaluations,
multiple evaluation versions for one identity, duplicate manifest identities,
unlisted hard evaluations and manifest/evaluation definition differences are rejected.
Full embedded definitions prevent same-ID/version severity or required-fact changes
from bypassing coverage. Rule, applicability, evidence and manifest versions survive
JSON round trips.

## Expected-check manifest trust boundary

`RuleTrace` requires candidate/context IDs and manifest ID/version. `required_checks`
contains full versioned ABSOLUTE rule definitions, including their required facts and
evidence; `evaluations` binds each result to its definition. An omitted expected check
cannot accidentally aggregate to PASS. A hard evaluation outside the manifest is a
contract error; soft/informational evaluations may be carried alongside it.

The caller must build the complete, trusted manifest for the candidate, profile,
workflow, scope and active KB version. This module cannot detect a relevant rule
omitted from the manifest itself, a fabricated manifest or a dishonest PASS/
NOT_APPLICABLE declaration. It does not verify that observations belong to the named
candidate/context. ACTIVE lifecycle is enforced, but selecting the authoritative active
rule set, applicability-definition resolution, evidence verification and provenance
authentication belong to future integration.
Manifest identity/version are trace metadata, not signatures or authority checks.

## Clinical activation safeguards

APPROVED requires both a non-blank approver and approval evidence. PENDING/REJECTED
cannot carry approval metadata; REJECTED rules cannot be ACTIVE. PRODUCTION + ACTIVE
clinical rules, at every severity, require APPROVED status and non-synthetic rule and
approval evidence. Synthetic approval cannot make synthetic clinical sources ready
for production. DRAFT/RETIRED declarations do not constitute production activation.

Environment and approval are declared metadata; schema validation does not authenticate
the reviewer or verify clinical sources. Authorized reviewers, approval workflow,
evidence quality criteria and revocation/versioning policy still require team approval.
There are no real clinical sources, thresholds or approvals in this work. A focused
test uses fictional PRODUCTION-labelled source and approval metadata for a synthetic,
dimensionless predicate solely to reach the approval-reference provenance gate. The
fixture explicitly states that no medical review or approval occurred; these metadata
records must never enter a production KB.

## Required alignment with Members 1 and 3

Member 1 must agree canonical recipe/combination IDs, fact names, nutrition units,
reference preparation/portion, completeness and provenance before these observations
can be connected to normalized data, composition or ranking. Member 3 must agree
canonical profile facts, explicit unknown/null representations, profile/context
versions, request DTOs and error behavior. Required manifests must be assembled from
the agreed profile, workflow and KB, never inferred solely from received evaluations.

Candidate/context and manifest references, applicability definitions, clinical evidence
approval and final public schema naming require joint approval. No HTTP endpoint or
OpenAPI/TypeScript contract changes are introduced. Backend transport adapters and
`packages/contracts` alignment must follow an approved interface; the backend retains
ownership of data access and orchestration. Missing safety data must remain UNKNOWN
through every consumer, including standalone craving.

## Future decisions and limitations

Awaiting approval: final field/enumeration/operator/unit vocabulary, manifest DTO and
trusted construction ownership, rule/applicability identity/version policy, source
locators and reviewer authority, evidence sufficiency, canonical fact types and units,
context binding and resolved NOT_APPLICABLE representation. This slice uses an explicit,
definition-bound expected-check manifest. No earlier review artifact or separate
proposed manifest was present to verify exact DTO equivalence.

Future interfaces include rule loading and activation, predicate execution, focused
KG derivation, `filter_candidates`, combination validation, CSP `solve_week` and
`validate_swap`, evaluation trace/XAI composition and backend error translation.
Their signatures, timeout/failure behavior and contract exposure are not finalized here.

Phase 1 validates declarations and coverage only. It is not a complete working Rule
Engine, does not compare observed values to predicate thresholds, verify external
facts, authenticate evidence, traverse a graph, filter recipes, rank candidates,
solve portions/plans, validate swaps or persist anything. Clinical limits and all
architecture section 15 open decisions remain unresolved.

Definition of done for this slice: the five authorized files are implemented, synthetic
contract/safety-coverage tests and the existing AI smoke test pass, Ruff check/format
and Pyright pass, and the diff contains no unrelated changes. Joint interface approval
and subsequent phases remain separate review gates; no commit or push is authorized.
