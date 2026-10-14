# Member 2 Phase 3: deterministic rule filtering

## Task 3.1 scope and authority

Task 3.1 implements synthetic candidate, fact, ingredient coverage and normalized
context contracts only. Names, fact vocabulary and policies are provisional pending
joint API approval. No clinical thresholds, actual food IDs or production evidence
are supplied. No rule manifest, applicability execution, predicate execution,
graph/taxonomy adapter, filtering, eligibility, ranking, composition, CSP, backend
integration or persistence is implemented.

Reviewed AGENTS.md, ARCHITECTURE.md sections 3-5 and 11, Phase 1/2 decisions,
schemas and tests, and sections 3, 4, 6, 7, 16-18 of the accessible October 2026
`C:/Users/venka/Downloads/Savora_GC1_Architecture_Team_Contract.pdf`. That PDF is a
proposed implementation contract. Its `filter_recipes` and cuisine policy names
differ from repository `filter_candidates` and STRICT/MAJORITY/MIXED vocabulary.
These future interfaces remain pending approval; Task 3.1 does not rename them.

The existing user-selected branch is `feature/member2-rule-filtering`. This task
does not rename the branch or authorize staging, committing, pushing or a PR.

## Public DTOs and imports

Import directly from `savora_ai.schemas.candidates`. Phase 1/2 public contracts
and `schemas/__init__.py` exports are unchanged. Every new DTO inherits the existing
`_ContractModel`: strict Pydantic v2 validation, frozen instances, tuple collections,
forbidden extras, camelCase JSON and recursive instance revalidation. Python inputs
require genuine enum members and tuples; JSON uses tokens and arrays through the
strict `validate_contract_json` ingress documented below. Native Pydantic JSON
methods are only for trusted/generated round trips, not security-sensitive raw input.
FactObservation and FoodEntity are reused, not copied.

| DTO | Exact fields |
|---|---|
| VersionedFact | fact_id, version, subject_kind, subject_id, subject_version, catalogue_version, observation, measurement_basis, basis_reference, context_id, context_version |
| IngredientLine | line_id, version, recipe_id, recipe_version, catalogue_version, mapping_status, ingredient_id, ingredient_version, subingredients_complete, subingredients, gap_reasons, evidence |
| IngredientCoverage | coverage_id, version, recipe_id, recipe_version, catalogue_version, lines, inventory_complete, mapping_complete, subingredients_complete, gap_reasons, evidence |
| CandidateRecipeFacts | schema_version, digest_policy_version, recipe_id, recipe_version, catalogue_version, graph_id, graph_version, graph_recipe_entity_id, graph_recipe_reference, snapshot_id, snapshot_version, context_id, context_version, ingredient_coverage, facts, evidence, content_digest |
| RuleContext | schema_version, digest_policy_version, context_id, version, profile_id, profile_version, workflow, expected_kb_id, expected_kb_version, expected_kb_digest, expected_graph_id, expected_graph_version, expected_taxonomy_version, expected_catalogue_version, expected_check_catalogue_version, workflow_policy_version, evaluator_policy_version, facts, evidence, content_digest |

FactSubjectKind is RECIPE/INGREDIENT/PROFILE/CONTEXT. IngredientMappingStatus is
MAPPED/UNRESOLVED. All new enum fields, reused workflow values and gap code elements
require canonical declared singleton members, including legitimate-looking tokens.

Opaque IDs reuse Phase 2's case-sensitive ASCII ID convention. Record versions are
nonblank opaque release labels, not ordered numbers. Blank versions are rejected;
there is no invented latest-version ordering. Candidate schema is
`candidate-recipe-facts.v1`, context schema is `rule-context.v1`, digest policy is
`candidate-content-digest.v1`, workflow policy is `synthetic-workflow-scopes.v1`
and the reserved evaluator policy is `synthetic-rule-evaluation.v1`. Unknown policy
tokens are rejected. The evaluator token binds a future synthetic policy; no
evaluator exists in Task 3.1.

## Fact ownership and identity binding

VersionedFact.fact_id must equal observation.fact_id. Food subjects require a
catalogue_version; profile/context subjects forbid one. Context ID/version are
either both present or both absent. CONTEXT facts must explicitly bind those fields
to their own subject ID/version.

Candidate recipe facts must match the candidate recipe ID/content version. Ingredient
facts must match a canonical mapped ingredient ID/content version somewhere in its
coverage tree. Profile/context facts are rejected in candidates. Context facts must
match the declared profile or context owner; food facts are rejected in RuleContext.
Context-dependent facts must match the enclosing context binding. An unbound fact
may accompany a bound snapshot without becoming context-dependent automatically.

A fact identity within a snapshot is `(subject_kind, subject_id, fact_id)`. Repeating
it, even identically or at a different fact version, is rejected. The same attribute
may exist for different owners. Ownership validation prevents moving an unchanged
fact between envelopes; rewriting an entire unauthenticated declaration cannot be
detected as source fraud by these schemas.

The candidate embeds an existing FoodEntity. Its kind must be RECIPE_REFERENCE,
entity_id must equal graph_recipe_entity_id, and catalogue_reference must equal
recipe_id. The graph node content version is distinct from recipe_version. Graph
ID/version and catalogue_version bind the declaration and digest. The node alone
cannot prove membership in an actual graph release. No graph lookup or traversal
is performed; accepted-KB membership checking belongs to the next integration.

RuleContext records all expected release bindings, including a mandatory expected
KB digest and explicit nullable taxonomy version. It does not accept/load a KB,
normalize user text, verify a source or compare expectations with an actual release.
Task 3.2 must make those comparisons against an accepted synthetic KB. A changed
expectation changes the context digest; a supplied old digest/pin is rejected.

## Measurement basis policy

Numeric observations retain existing finite/nonnegative/unit validation and percent
range checks. Boolean is not numeric. Every numeric fact also requires a
MeasurementBasis and non-null versioned EvidenceReference in basis_reference.

| Basis | Meaning and restrictions |
|---|---|
| AS_RECORDED | Explicit non-normalized quantity/ratio as declared by its basis evidence; allowed for all subject kinds |
| PER_100_G | Quantity per 100 g of the evidenced food/preparation; food subjects only |
| PER_SERVING | Quantity per the specific evidenced serving/preparation; food subjects only |

Dimensionless and percent observations use AS_RECORDED. PER_100_G/PER_SERVING reject
those units and profile/context owners. A serving has no universal mass: its
basis_reference must identify the declared serving/preparation source. Evidence
metadata is structurally retained; its content is not fetched or authenticated.
Unsupported bases, missing numeric bases/evidence, and numeric bases on boolean,
categorical or null facts are rejected. No unit, serving, mass/volume or nutrition
conversion occurs. Attribute-specific scientific unit/basis compatibility still
requires the jointly approved fact vocabulary and future evaluator policy.

## Ingredient completeness

IngredientLine is a source-line record, not a quantity or absence assertion. MAPPED
requires ingredient_id and ingredient_version. UNRESOLVED requires both to be null
and the UNRESOLVED_MAPPING gap code. An incomplete subingredient declaration
requires INCOMPLETE_SUBINGREDIENTS. A complete parent cannot contain an incomplete
child. Nested lines retain the same recipe/content/catalogue binding.

Line IDs are unique throughout the coverage tree, including across sibling branches.
Repeated canonical ingredients on distinct source lines are allowed, but they must
use one content version in a catalogue release. No quantities or allergen retention
are inferred from ingredient records, classification or DERIVED_FROM ancestry.

Coverage separates three axes:

- inventory_complete: the supplied inventory enumerates the declared source lines.
- mapping_complete: every supplied line/subline has a canonical mapping.
- subingredients_complete: every supplied line declares complete expansion below it.

`lines=None` means missing inventory; all flags must be false and exactly
MISSING_INVENTORY is required. `lines=()` with all flags true is an explicitly complete
empty inventory. `lines=()` with inventory_complete false is a partial empty inventory
and requires INCOMPLETE_INVENTORY. For any supplied tuple, mapping/subingredient
flags must exactly match the records; they are independent of whether additional
top-level lines are missing.

Gap codes exactly describe declarations: MISSING_INVENTORY, INCOMPLETE_INVENTORY,
UNRESOLVED_MAPPING, INCOMPLETE_SUBINGREDIENTS. Missing, extra or duplicate codes
are rejected. Complete source enumeration may still have unresolved mappings;
inventory_complete alone is not complete safety knowledge. Evidence is mandatory
for lines and coverage, including gaps and complete empty inventories.

Presence/absence facts need their own observation evidence and future semantic
checks. Missing records, empty inventories and complete coverage never establish
allergen absence, cross-contact absence or eligibility by themselves.

## Validation, digest construction and trust

All supplied evidence must be SYNTHETIC. Each local evidence tuple rejects duplicate
ID/version pairs. Across an entire snapshot, identical evidence reuse is allowed;
different metadata for the same identity/version is rejected, including basis,
graph-reference, nested-line and observation evidence. Different evidence versions
may coexist. Environment/source/locator labels are not authority credentials.

Use validating constructors/model_validate for Python objects, the strict ingress
below for raw JSON, or these Python factories:

```python
CandidateRecipeFacts.build(content, *, expected_digest=None) -> CandidateRecipeFacts
RuleContext.build(content, *, expected_digest=None) -> RuleContext
```

Content is the respective typed snapshot or a strict Python field dictionary.
Omitting content_digest in a factory requests computation. Supplying any digest
requests verification: null, malformed or stale values are never silently replaced.
Direct constructors/strict JSON ingress require contentDigest. expected_digest is an optional,
independently supplied prior pin; mismatches raise ValidationError.

Digests include every validated field, default, null and policy token except the
snapshot's own content_digest. JSON uses camelCase keys, sorted object keys,
recursively sorted array encodings, compact separators, ASCII escaping and UTF-8;
SHA-256 produces lowercase hex. All present collections are unordered declarations
or categorical sets; these models contain no ordered graph witnesses. Fact/line/
evidence insertion order does not change hashes. Scalar types, including integer
versus float, remain distinguishable. DTOs preserve their original tuple order.
This local format makes no RFC 8785 claim.

The factory revalidates original nested field storage before serialization and never
mutates caller inputs. Inherited guards reject custom dict/list/tuple subclasses
before invoking their methods, counterfeit enums, field/alias/extra collisions,
retained unexpected fields and malformed unchecked copies/constructs. Unchecked
construction is not an authorized pathway; fields already discarded by a caller's
model_construct cannot be reconstructed by later validation.

These Python/decoded-object guards cannot recover repeated identical JSON keys
already discarded by a parser. All security-sensitive raw JSON must enter through
validate_contract_json before native Pydantic decoding.

Facts absent from a snapshot, null incomplete observations, incomplete non-null
collections, numeric zero, False and complete empty collections remain distinct.
No missing value becomes zero or safe. No status or eligibility field exists.
Hashes protect integrity against an independent pin, not source authenticity,
external catalogue completeness, freshness or revocation.

## Planned Task 3.2 and pending agreements

Task 3.2 should accept the synthetic KB through build_knowledge_snapshot, compare
context expectations and candidate release/reference metadata, then construct the
exact workflow/stage manifest from active-rule catalogue and coverage. It must retain
UNKNOWN applicability obligations and record deferred combination/day/week checks.
Manifest construction and any extra approval-admission policy are not implemented
here. Phase 1 aggregate_hard_status does not authenticate manifest completeness.

Member 1 must agree canonical recipe/ingredient IDs, content/preparation versions,
source line identities, fact names, units, basis references, completeness semantics
and graph/catalogue mappings. Members 2/3 must agree normalized profile facts,
context identity/revisions, evaluator dependencies, unknown representations and
release expectations. All members must approve final public API/DTO names, required
hard-rule approval policy and workflow/stage mapping. Member 3 owns future trusted
release selection, authentication, revocation and backend error translation.

## Task 3.1 verification and review boundary

Verified on 14 October 2026 with existing dependencies and UV_NO_SYNC=1. No EDA
notebook execution, dependency installation or lockfile change was performed.

| Check | Result |
|---|---|
| uv run ruff check . | Passed |
| uv run ruff format --check . | Passed; 93 files already formatted |
| uv run pyright | Passed; 0 errors, 0 warnings |
| uv run pytest -q | 2,175 passed, including 305 new Task 3.1 cases |
| AI architecture/import audit | 22 modules; no backend/ORM/database imports or local import cycles |
| Tracked/index and intended untracked-file whitespace | Passed |

Tests include independent digest encoding and hostile container method-call counters,
exact ownership/revision checks, duplicate and contradictory declarations, nested
unresolved ingredients, missing/empty inventories, scalar preservation, genuine and
counterfeit enums, copied/constructed malformed storage, aliases/extras, frozen
instances, strict Python collections, JSON schema/round trips, source conflicts,
production relabelling and tampering against independently supplied digest pins.
All previous 1,870 tests remain passing at that checkpoint. The later independent
review identified one MEDIUM raw-JSON duplicate-key finding; the focused correction
and supported ingress policy are documented below. External release/source
authority, scientific fact vocabulary and later evaluation remain explicit deferred
agreements, not guarantees made by Task 3.1.

Only candidates.py, test_candidate_contracts.py and this document are introduced.
Phase 1/2 contracts, package exports, teammates' files and existing data are unchanged.
HEAD remains 3ef1bbc on feature/member2-rule-filtering; the three task files are
unstaged/untracked. No staging, commit, push, PR or Phase 3.2 implementation is
authorized by this task. Task 3.1 is ready for strict review.

## Focused correction: strict raw-JSON ingress

The independent review reproduced duplicate mappingStatus, contentDigest, subjectId,
complete, profileVersion, workflow and expectedKbVersion acceptance through native
model_validate_json and TypeAdapter.validate_json. Pydantic decodes an object before
the inherited wrap validators receive it. Repeated identical names have already been
overwritten; reserializing that dictionary cannot recover the discarded declarations.
Different snake_case/camelCase alias collisions remain covered by inherited guards.

Selected approach A: a small explicit shared ingress in the authorized candidates.py
module, using supported standard-library/Pydantic APIs. No Phase 1/2 implementation,
DTO field, schema configuration or Python-object validation behavior is changed.
There is no monkey-patching or schema-level claim to intercept arbitrary native
adapter calls. A model_validate_json override alone would leave adapters uncovered.

```python
from savora_ai.schemas.candidates import validate_contract_json

candidate = validate_contract_json(CandidateRecipeFacts, original_raw_json)
context = validate_contract_json(RuleContext, original_raw_json)
# A public TypeAdapter, including a collection of nested DTOs, is also supported:
records = validate_contract_json(TypeAdapter(tuple[CandidateRecipeFacts, ...]), raw_array)
```

The generic signature is `validate_contract_json(target, payload) -> Result`, where
target is a trusted Pydantic model class/schema type or a public TypeAdapter[Result],
subject to the supported validated-output types below. The same function can
validate existing Phase 1/2 DTOs without modifying their definitions.
For a KB this remains schema validation, not build_knowledge_snapshot's synthetic
release acceptance or trusted source selection.

The ingress checks the original raw text with json.loads/object_pairs_hook before
Pydantic runs. Every object rejects duplicate decoded member names, including equal
values, nested duplicates and escaped equivalent names. No first/last value wins.
The parsed Python tree is discarded; the original text then enters the public
TypeAdapter.validate_json(..., strict=True), preserving JSON enum tokens, array-to-
tuple wire semantics, original numeric spelling and existing DTO restrictions.
There is no canonicalization or automatic digest replacement.

Limits and error policy:

- Accept only exact built-in str/bytes/bytearray inputs. Reject input subclasses before
  invoking overridden methods. Byte input must be UTF-8 without BOM.
- Maximum STRICT_JSON_MAX_BYTES is 1,048,576 UTF-8 bytes, including whitespace.
  Character count is bounded first; multibyte text is checked after encoding.
- Maximum STRICT_JSON_MAX_DEPTH is 64 nested object/array containers, including the
  root container. A string/escape-aware scan enforces the bound before decoding.
  Quoted brackets do not contribute. The standard parser validates actual grammar.
- Reject NaN, Infinity, -Infinity and float literals that overflow to nonfinite values.
  Also reject nonfinite floats introduced by Pydantic type conversion or schema
  validators, including integer-to-float overflow, before returning validated output.
  Numeric tokens are still passed unchanged to Pydantic. Legitimate zero, False,
  null, finite values, lists, objects and strings such as "NaN" are preserved.
- Integer parsing also follows the interpreter's integer-string digit safety limit
  (normally 4,300 digits); any resulting ValueError becomes ValidationError.
- Parser/type/encoding/size/depth failures use ValidationError titled StrictJsonIngress
  and omit raw payloads from its input field. Validated-output failures use
  ValidationError titled StrictJsonOutput, also without raw/result input. DTO failures
  retain ordinary Pydantic ValidationError. Invalid schema targets remain caller
  configuration errors.

| Entry point | Raw-input security policy |
|---|---|
| validate_contract_json(ModelClass, original_raw) | Supported and adversarially tested |
| validate_contract_json(TypeAdapter(...), original_raw) | Supported, including nested DTO collections |
| Model.model_validate_json(raw) | Unchanged; unsupported for security-sensitive raw input |
| TypeAdapter(...).validate_json(raw) | Unchanged; unsupported outside strict ingress |
| Native SchemaValidator.validate_json(raw) | Unchanged; unsupported outside strict ingress |
| json.loads(raw) followed by model/build validation | Unsupported raw ingress: duplicates are already lost |
| Python constructors/model_validate/build(validated Python data) | Existing strict Python behavior retained |

The native bypass acceptance is deliberately tested and documented, not represented
as protected. Native methods still support trusted/generated JSON round trips.
Callers must pass original bytes/text through strict ingress, never normalize raw
input first. No application raw-JSON entry point for these new contracts is currently
implemented; future backend integrations must adopt this policy. Relocating/exporting
the utility through a Phase 1 package, or changing native Phase 1 JSON entry points,
would need separate scope approval; neither is needed for this correction.

New regressions cover every reported duplicate field, equal/conflicting values,
escaped names, shared Phase 1/2 DTOs, adapter collections, valid controls, invalid
constants/grammar/encoding, exact size/depth boundaries and documented bypasses.

Focused correction verification on 14 October 2026 used existing dependencies with
UV_NO_SYNC=1. No dependency installation or lockfile update was performed.

| Check | Result |
|---|---|
| uv run ruff check . | Passed |
| uv run ruff format --check . | Passed; 93 files already formatted |
| uv run pyright | Passed; 0 errors, 0 warnings |
| uv run pytest -q | 2,341 passed; 166 new raw-JSON cases, 471 total candidate-contract cases |
| Independent in-memory adversarial JSON probes | 154 rejections passed, plus valid DTO/scalar/limit controls |
| AI architecture and whitespace audits | Passed |

Before correction, conflicting raw duplicates were accepted by native model, adapter
and schema-validator methods for candidate/context, plus inherited Phase 1/2 DTOs.
After correction, strict ingress rejects them for both class and public-adapter
targets. Native bypass acceptance remains explicitly documented and tested. All
previous 2,175 cases still pass. The subsequent generic-output review identified one
MEDIUM integer-to-float overflow defect; its correction is documented below.
No application endpoint was added; adopting strict
ingress on original input is required for future security-sensitive boundaries.

Only candidates.py, test_candidate_contracts.py and this document were changed.
All tracked files, including Phase 1/2 implementations, are unchanged. A separate
Phase 1 PR update is not required for this selected explicit-ingress correction.
HEAD/index remain unchanged; no stage, commit, push, merge, PR or Task 3.2 work.

## Final correction: validated-output numeric overflow

The raw parser correctly rejects nonfinite constants and overflowing float tokens,
but a 400-digit integer token is a legitimate Python integer. Native Pydantic JSON
validation can convert that token to infinity for a float target. Before this fix,
strict ingress returned infinity for TypeAdapter(float), list[float], dict[str, float],
ordinary float-field models and nested models. The same integer remains legitimate
when the validated target is int; rejecting all large integers would change that
contract.

After native strict JSON validation of the original text, ingress checks the actual
validated output before returning it. Every supported float must be finite. This
includes dictionary keys and values, nested containers, model field storage,
RootModel roots, and model extra/private storage. NaN and either infinity raise
StrictJsonOutput ValidationError. There is no clamping, coercion, serialization,
copying or mutation of accepted output.

Supported output data is deliberately bounded:

- Exact built-in None/bool/int/float/str/bytes/bytearray scalars; canonical StrEnum
  string members with the standard EnumType metaclass.
- Exact built-in list/tuple/dict/set/frozenset containers, recursively containing
  supported data. Dictionary keys are inspected as well as values.
- Ordinary BaseModel/RootModel instances without computed fields, whose managed
  field/extra/private storage consists of exact built-in dictionaries containing
  supported data. Fixed BaseModel storage descriptors bypass instance properties,
  overridden __getattribute__ and serializers. Only managed stored data is covered;
  arbitrary properties and future serialization behavior are outside this guarantee.
- Shared acyclic references are allowed and remain shared. Cycles are rejected.
  Iterative traversal is limited to depth 128 from the output root (depth zero),
  including model storage dictionaries, and a 1,048,576 work-item budget for visited
  values plus pending traversal records. These separate output limits also bound
  expansions produced by schema validators. Raw input limits remain 1 MiB UTF-8
  and 64 object/array levels.

Opaque objects, scalar/container subclasses, custom enum metaclasses, computed-field
models, dataclasses, named tuples, Decimal, datetime, UUID and lazy iterators/generators
are unsupported outputs. They are rejected rather than inspected through arbitrary
attributes or custom iteration. Applications needing such targets must first define
and review a safe supported representation; this function makes no universal guarantee
over arbitrary Python objects.

Schema types, TypeAdapters and their validators are trusted application configuration.
The output check cannot sandbox schema code or guard later mutation, computed
properties or serializer code. Untrusted input must be original raw JSON passed to
validate_contract_json. Native model_validate_json, TypeAdapter.validate_json and
SchemaValidator.validate_json remain unsupported security-sensitive entry points,
and previously decoded objects cannot recover lost duplicate keys.

New regressions directly exercise strict ingress for positive/negative 400-digit
integer overflow across scalar/list/tuple/dict/set/frozenset/model/root/nested targets,
nonfinite values produced by validators, dictionary-key overflow, field/extra/private
storage, finite floats and signed zero, large integer preservation, booleans/nulls,
complex typed graphs, identity preservation, unsupported outputs, cycles and output
traversal limits. Existing duplicate-key, invalid-constant/exponent, input size/depth
and Phase 1/2 contract regressions remain in the suite.

Final correction verification on 14 October 2026 used existing dependencies with
UV_NO_SYNC=1:

| Check | Result |
|---|---|
| uv run ruff check . | Passed |
| uv run ruff format --check . | Passed; 93 files already formatted |
| uv run pyright | Passed; 0 errors, 0 warnings |
| uv run pytest -q | 2,411 passed; 70 new regressions, 541 total candidate-contract cases |
| Independent in-memory adversarial probes | 31 rejection cases and 13 valid controls passed |
| AI architecture/import audit | 22 modules; no forbidden backend/ORM/database imports or local cycles |
| Whitespace and scope audit | Passed; all 151 tracked files, HEAD and index unchanged |

Original scalar/list/dict/ordinary-model/nested-model overflow reproductions now raise
ValidationError through supported ingress, for positive and negative integers.
Candidate duplicate mappingStatus rejection also remains verified for class and
adapter targets. No remaining HIGH/MEDIUM defect was identified within the documented
supported boundary. Native bypass routes still require integration discipline.

Only candidates.py, test_candidate_contracts.py and this document are modified.
Phase 1/2 contracts and Python-object behavior remain unchanged. No separate Phase 1
update is required. No application boundary, dependency, export or Git state change
is included; no Task 3.2 implementation begins. Task 3.1 is ready for Task 3.2.

## Tasks 3.2 and 3.3: accepted-KB manifests and deterministic evaluation

Implemented on 14 October 2026 in the user-selected
`feature/member2-rule-filtering` branch. Before implementation, the entire 541-case
Task 3.1 suite passed, including the positive/negative integer-to-float overflow
and validator-produced nonfinite output regressions. The later additions below
supersede the earlier Task 3.1 statements that manifests/evaluators are future work.

Reviewed AGENTS.md, ARCHITECTURE.md sections 3-5 and 11, both Member 2 Phase 1/2
documents, the Task 3.1 documentation, and existing schemas, reasoning modules and
tests. The available Phase 3 review/handoff specifies the module split, catalogue
ownership and fixed recipe stage; it leaves exact evaluator/fact vocabulary pending
joint agreement. This slice makes that vocabulary explicit as a synthetic policy.
It does not establish production or clinical approval. No Task 3.4/3.5 filtering,
graph-derived facts, eligibility API, composition, ranking, CSP or persistence is added.

### Public imports and signatures

```python
from savora_ai.schemas.filtering import ExpectedCheckManifest
from savora_ai.core.reasoning.manifest import build_expected_check_manifest
from savora_ai.core.reasoning.evaluation import evaluate_rule_checks


def build_expected_check_manifest(
    kb: KnowledgeBaseSnapshot,
    candidate: CandidateRecipeFacts,
    context: RuleContext,
) -> ExpectedCheckManifest: ...


def evaluate_rule_checks(
    kb: KnowledgeBaseSnapshot,
    candidate: CandidateRecipeFacts,
    context: RuleContext,
    manifest: ExpectedCheckManifest,
) -> tuple[RuleEvaluation, ...]: ...
```

Existing Phase 1/2 models, acceptance policy and exports are unchanged. These module
imports are provisional Python interfaces; there are no HTTP/OpenAPI/frontend changes.
Use `validate_contract_json` for security-sensitive original raw JSON, including
manifest ingress. Unchecked copies/constructs and native JSON shortcuts do not grant
authority. Every public reasoning entrypoint recursively revalidates original storage
before serialization, preserving aliases/extras/container types and counterfeit enums.
Structural rejection uses `ValidationError`; declaration gaps produce UNKNOWN results.

### Manifest binding and admission

ExpectedCheckManifest is frozen, strict, extra-forbidden, camelCase on the wire and
tuple-based. Fields are:

| Group | Fields |
|---|---|
| Policy | schema_version, stage, workflow_policy_version, admission_policy_version, evaluator_policy_version, attribute_policy_version, identity_policy_version |
| KB/releases | kb_id, kb_version, kb_digest, graph_id, graph_version, taxonomy_version, catalogue_version, check_catalogue_version |
| Candidate | candidate_id (recipe ID), candidate_version (recipe content version), candidate_snapshot_id, candidate_snapshot_version, candidate_digest |
| Context/profile | context_id, context_version, context_digest, profile_id, profile_version, workflow |
| Obligations/identity | required_checks, deferred_checks, manifest_id, manifest_version, content_digest |

The builder accepts a fully validated KnowledgeBaseSnapshot, revalidates it and
calls the existing `build_knowledge_snapshot` acceptance boundary. All exact context
expectations must match, including nullable taxonomy version. Candidate graph and
food-catalogue releases must match. The embedded recipe node must equal the actual
accepted graph entity, including its content version, catalogue reference and evidence.
An explicitly context-bound candidate must match context ID/version. KB, candidate,
context, basis and approval evidence share one conflict-checked synthetic provenance
namespace. No source content is fetched or authenticated.

Checks come exclusively from the accepted KB check catalogue for the exact context
workflow. KB validation enforces every workflow/scope cell and complete coverage,
including empty cells, exact active inventory, lifecycle, hard severity, scope and
full reference/version resolution. Checks resolve full RuleDefinition objects, never
caller-supplied references. PROFILE and RECIPE form the fixed RECIPE_FILTER stage.
COMBINATION, DAY and WEEK are retained in deferred_checks for WEEKLY_PLAN and
PLANNED_SWAP. CRAVING_DISCOVERY has no later-scope obligations. No applicability
outcome changes either obligation set; soft/informational inventory is not mandatory.

`synthetic-hard-rule-admission.v1` additionally requires APPROVED status, approver
and synthetic approval evidence for every mandatory hard rule, including deferred
rules. This is a Phase 3 constraint only: Phase 2 still accepts synthetic PENDING
nonclinical active rules. Unsupported rule attributes, operators/types/units,
applicability identities, required-context descriptors or policy tokens are rejected.
Unsupported unused/archived inventory need not be executed or admitted as a check.

Policies are fixed application configuration; no public scope/check/evaluator override
exists. Current tokens are `expected-check-manifest.v1`, RECIPE_FILTER,
`synthetic-workflow-scopes.v1`, `synthetic-hard-rule-admission.v1`,
`synthetic-rule-evaluation.v1`, `synthetic-attributes.v1`, and
`synthetic-manifest-identity.v1`.

Identity hashes all validated manifest content except its three identity fields,
using the existing candidate unordered canonical JSON/SHA-256 format. Record/null
and policy values are included; collection order is irrelevant to the digest.
`content_digest = sha256(content)`, `manifest_id = "manifest-" + content_digest`,
and `manifest_version = "synthetic-manifest.v1:" + content_digest`. Checks are returned
in rule ID/version order; embedded definitions retain their accepted declaration order.
Versions are exact labels, with no inferred latest-release ordering.

DTO validation alone cannot prove completeness. `evaluate_rule_checks` independently
rebuilds the complete manifest against the supplied accepted KB/candidate/context
and compares its verified content digest. Removing required or deferred checks,
editing a same-ID/version definition, switching workflow or rewriting a binding
fails even if a caller recomputes all manifest identity fields. Integrity hashes
are not signatures; trusted release selection, independent pins, freshness,
authentication, revocation and source truth remain orchestration responsibilities.
An entirely replaced, internally consistent KB and context cannot authenticate each other.

### Explicit synthetic applicability policy

All conditions are evidenced boolean facts with complete=true. Exact registered
ApplicabilityDescriptor reference identities and required-context declarations are:

| Reference ID / version | Exact required_context_facts | Owner |
|---|---|---|
| synthetic-context-enabled / 1 | (synthetic_context_enabled,) | CONTEXT |
| synthetic-context-guard / 1 | (synthetic_context_guard,) | CONTEXT |
| synthetic-profile-enabled / 1 | (synthetic_profile_enabled,) | PROFILE |

The descriptor's hosted rules and dependencies are resolved from the accepted KB.
Unknown IDs/versions, descriptor fact-list mismatches, missing/stale dependencies
and dependency cycles are rejected. Supported dependency topology is KB-declared
configuration under this explicit conservative conjunction policy:

1. Any missing/null/incomplete local condition or dependency makes UNKNOWN.
2. Otherwise any false local condition or NOT_APPLICABLE dependency makes NOT_APPLICABLE.
3. Otherwise every local/dependency condition is true: APPLICABLE.

UNKNOWN therefore dominates false; a false condition cannot conceal an unresolved
dependency. All supplied policy-known condition facts are type/owner validated
before combination, even behind false or unknown siblings. There is no truthiness,
numeric-to-boolean coercion, clinical inference or religion-to-diet inference.
Dependency evaluation is iterative and deterministic, with shared dependencies
computed once. Applicability evidence retains local descriptor, supplied condition
observations and transitive dependency evidence. Missing observations cite the
context snapshot evidence and descriptor; these are gap declarations, not proofs
of a false condition. Deferred descriptors/configuration are validated at admission;
their conditions are not executed unless needed as a recipe-stage dependency.

### Synthetic attribute and predicate policy

RuleDefinition has no measurement-basis field. The named, fixed attribute policy
therefore supplies the exact expected unit, measurement basis and basis evidence
ID/version for its synthetic comparison quantities. It makes no scientific claims
about real nutrition and does not derive thresholds. Threshold values always come
from the admitted RuleDefinition, never from model output or invented defaults.

| Attribute | Kind / owner | Unit | Basis | Exact basis evidence ID / version |
|---|---|---|---|---|
| synthetic_quantity | numeric / RECIPE | mg | PER_100_G | synthetic-per-100-g / 1 |
| synthetic_serving_quantity | numeric / RECIPE | mg | PER_SERVING | synthetic-serving / 1 |
| synthetic_ratio | numeric / RECIPE | dimensionless | AS_RECORDED | synthetic-recorded / 1 |
| synthetic_flag | boolean / RECIPE | null | null | null |
| synthetic_category | scalar categorical string / RECIPE | null | null | null |
| synthetic_profile_flag | boolean / PROFILE | null | null | null |
| three applicability facts above | boolean / their declared owner | null | null | null |

Numeric rules support LT, LE, GT, GE, EQ and NE. Boolean rules support EQ and NE.
Scalar categorical rules support EQ, NE, IN and NOT_IN; membership rule values are
nonempty exact string sets (tuples), while observations remain scalar strings.
Categorical comparisons are case-sensitive. Predicate truth means compliance:
true becomes PASS, false becomes FAIL, with no inversion for exclusion rules.
No case folding, string casting, unit conversion, tolerance, rounding, serving
conversion or implicit int/float conversion is performed. Numeric integers and
finite floats are compatible; bool remains a separate kind. Existing finite,
nonnegative and percent restrictions remain in force. Python exact numeric
comparisons preserve large integers and next-representable-float boundaries.

All required_facts must use the registered vocabulary. PROFILE checks cannot
require recipe facts. Required observations come from their declared owner in
the pinned candidate/context snapshots; there is no ingredient, profile or context
fallback for an absent recipe fact. Missing, null or incomplete required facts
give UNKNOWN. Every supplied policy-known fact is semantically validated before
any result, including unused/incomplete facts and facts behind unknown applicability.
Conflicting owner declarations, booleans-as-numbers, wrong types/units/bases/basis
references and contradictory evidence cause structural rejection. Unknown extra
vocabulary is retained in snapshot digests and schema-validated, but never consulted
as a fallback or assigned unsupported semantics. Ingredient inference awaits Task 3.4.

`evaluate_rule_checks` returns every recipe-stage mandatory check in rule ID order,
including all checks after a known FAIL. It produces validated existing RuleEvaluation
DTOs with full rules, evidenced applicability, present required observations and
numeric basis evidence. Applicability UNKNOWN gives predicate UNKNOWN. Evidenced
NOT_APPLICABLE also gives predicate UNKNOWN; existing Phase 1 aggregation treats
that check as resolved. Deferred obligations remain on the manifest. Empty manifests
produce no evaluations and no PASS claim; existing empty-trace aggregation is UNKNOWN.

Reasons are deterministic versioned strings:
`synthetic-rule-evaluation.v1:APPLICABILITY_UNKNOWN`, `:NOT_APPLICABLE`,
`:REQUIRED_FACT_UNKNOWN`, `:PREDICATE_TRUE` and `:PREDICATE_FALSE`.
RuleEvaluation alone does not authenticate its generating manifest; downstream
orchestration must retain the manifest and candidate/context/KB pins alongside results.

### Integration dependencies and findings

No remaining HIGH/MEDIUM implementation finding is known within this synthetic
boundary. The new policy vocabulary is a deliberate provisional choice, not a
jointly approved production registry. Real clinical activation, preparation/serving
basis source authority and thresholds require reviewed sources and team agreement.
Member 1 supplies agreed canonical food IDs, facts and measurement/preparation
references; Member 3 supplies normalized profile/context revisions and trusted
release loading/revocation. Members 2/3 must jointly approve production applicability
conditions, dependency semantics, workflow scopes and error translation.

Tasks 3.4/3.5 remain integration dependencies for KG-derived facts, complete rule
traces, candidate filtering and eligibility handoff. No backend endpoint, database,
ranking, composer, CSP or frontend check is part of these Python-only tasks. The user
selected the existing `feature/` branch explicitly; it is retained despite the generic
AGENTS.md `feat/` naming convention. No staging, commit, push or PR is performed.

### Tasks 3.2/3.3 final verification

Verified on 14 October 2026 using existing dependencies with UV_NO_SYNC=1. The
sandbox denied access to the installed virtual environment, so verification ran
through the approved escalated `uv run` commands. No dependencies were installed,
lockfiles changed or EDA notebooks executed.

| Check | Result |
|---|---|
| Prerequisite: uv run pytest apps/ai_system/tests/test_candidate_contracts.py -q | 541 passed, including numeric-overflow corrections |
| uv run ruff check . | Passed |
| uv run ruff format --check . | Passed; 98 files already formatted |
| uv run pyright | Passed; 0 errors, 0 warnings |
| uv run pytest -q | 2,712 passed in 123.50 s; 301 added Task 3.2/3.3 cases, all previous 2,411 retained |
| Import/scope review | New modules depend only on stdlib, Pydantic and AI schemas/reasoning; no backend, ORM, database or frontend imports |
| Git/scope review | No tracked/index change; five new task files plus this existing untracked document; Phase 1/2 and Task 3.1 source/tests untouched |

Independent synthetic fixtures/truth tables cover all eight operators, integer/float
boundaries, zero/False, case-sensitive categories, every applicability state,
conservative and transitive/shared dependencies, exact measurement/basis bindings,
unapproved rules including deferred scopes, all release pins, active/catalogue/coverage
corruption, unsupported identities/configuration, omitted mandatory checks, altered
same-ID/version definitions, self-rehashed forged manifests, conflicting fact owners,
counterfeit enums, copied/constructed malformed DTOs and duplicate raw-JSON keys.
Malformed non-null observations are tested behind UNKNOWN applicability, false
applicability, incomplete observations and another missing required fact.

Files created: `schemas/filtering.py`, `core/reasoning/manifest.py`,
`core/reasoning/evaluation.py`, `tests/test_rule_manifest.py`,
`tests/test_rule_evaluation.py` under `apps/ai_system` (source modules under
`src/savora_ai`). File extended: `docs/member2_rule_filtering.md`.
No remaining HIGH/MEDIUM finding was identified within this synthetic policy boundary.
Status: **READY FOR TASKS 3.4 + 3.5**; this status does not authorize their implementation.

## Tasks 3.4 and 3.5: conservative resolution and candidate filtering

Implemented on 14 October 2026 in the explicitly selected
`feature/member2-rule-filtering` branch. Before editing, verified Tasks 3.1/3.2/3.3
were implemented and the complete prerequisite suite passed: 2,712 tests, including
the overflow/strict-ingress corrections, manifest trust checks and every predicate.
Read AGENTS.md, relevant ARCHITECTURE.md sections 3-5 and 11, Member 2 Phase 1/2/3
documentation and applicable rule, graph, taxonomy, KB, candidate, context, manifest
and evaluation contracts and their implementation/tests.

The repository proposed `filter_candidates` but contained neither an implementation
nor a FilterCandidatesResult/RuleExplanation contract. The exact requested signature
is now implemented as a provisional synthetic Python interface. No `filter_recipes`
rename, HTTP/OpenAPI contract, production loader, weekly CSP, ranking, persistence or
UI is introduced. Existing Phase 1/2 schema fields, acceptance and implementations
remain unchanged. Only Phase 3 source modules and filtering DTOs are integrated.

### Public APIs and output contracts

```python
from savora_ai.core.reasoning.facts import resolve_rule_facts
from savora_ai.core.reasoning.filtering import filter_candidates
from savora_ai.schemas.filtering import (
    CandidateFactResolution,
    CandidateFilterDecision,
    FilterCandidatesResult,
    ResolvedRuleFact,
    RuleExplanation,
)


def resolve_rule_facts(
    candidate: CandidateRecipeFacts,
    *,
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
) -> CandidateFactResolution: ...


def filter_candidates(
    candidates: tuple[CandidateRecipeFacts, ...],
    *,
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
) -> FilterCandidatesResult: ...
```

`evaluate_rule_checks` retains its Task 3.3 signature. It now resolves facts internally
and compares the authoritative rebuilt manifest with its argument before evaluating.
No public evaluator accepts caller-supplied resolved facts or graph/taxonomy results.

| DTO | Fields and bindings |
|---|---|
| ResolvedRuleFact | VersionedFact `fact`, optional original `supplied_fact`, source, reason_code, exact RelationResolution records in `relations`, optional TaxonomyResolution in `taxonomy` |
| CandidateFactResolution | schema/adapter policy versions, full authoritative manifest, original ingredient_coverage, inventory_relations, unresolved_line_ids, canonically ordered facts, fixed max_hops=8/max_visited=256 |
| RuleExplanation | schema/policy versions; exact manifest ID/version/digest; candidate ID/content version/digest; context ID/version/digest; KB ID/version/digest; full RuleEvaluation; every required resolved fact or explicit gap; canonical evidence union |
| CandidateFilterDecision | resolution (including manifest/deferred obligations), complete RuleTrace, aggregate RuleStatus, one RuleExplanation per mandatory recipe-stage rule |
| FilterCandidatesResult | schema_version=filter-candidates-result.v1, stage=RECIPE_FILTER, plan_feasibility=NOT_EVALUATED, KB ID/version/digest, full normalized context, canonically ordered decisions, eligible_ids, excluded_ids |

All outputs inherit the existing strict/frozen/extra-forbidden/camelCase contracts.
Output validation checks release/owner/manifest/trace/explanation binding, complete
mandatory evaluation coverage, exact explained observations, evidence consistency,
hard-status aggregation, unique ordering and the eligible/excluded partition.
As with RuleTrace, DTO validation alone does not authenticate supplied source truth
or an externally fabricated predicate result. These are generated outputs; downstream
consumers must call the public pipeline rather than accept externally supplied decisions.
Original raw JSON must use `validate_contract_json`; prior native JSON bypass limits
and trusted schema-code assumptions still apply.

### Explicit synthetic fact-adapter catalogue

The v1 scalar registry and measurement policies are retained. Manifests select
`synthetic-attributes.v2` only when a mandatory required fact uses a new adapter
attribute (including deferred checks); otherwise their v1 policy/identity is retained.
The new resolver is bound to `synthetic-fact-adapters.v1`. Every new attribute is a
scalar boolean on the candidate recipe with no measurement unit/basis. Arbitrary
unregistered evaluator/attribute configurations still fail admission; recognized
unsupported safety semantics below are explicit UNKNOWN adapters.

These adapters are supported for synthetic testing only, without production/team
approval. None contains a clinical threshold or food-name heuristic.

| Attribute | Exact supported semantics |
|---|---|
| synthetic_contains_target | Exact unqualified recipe CONTAINS assertion targeting the INGREDIENT node whose catalogue_reference is synthetic-target. Explicit PRESENT gives true. Explicit ABSENT gives false only with complete inventory/mapping/expansion and no unresolved graph mappings. Missing edge/target mapping gives null/incomplete UNKNOWN. |
| synthetic_origin_target | Existential positive DERIVED_FROM origin path from any supplied, canonically mapped inventory ingredient to synthetic-target. Witness gives true; missing paths, mappings and blocked searches give UNKNOWN. It never gives false, allergen presence/retention or a new CONTAINS assertion. |
| synthetic_dietary_target | Exact DIRECT assignment of the recipe graph subject to synthetic-dietary, whose kind must be DIETARY_CATEGORY. Explicit positive/negative assignments give true/false for that classification only. Missing assignment/wrong target kind gives UNKNOWN; no dietary hierarchy inheritance. |
| synthetic_cuisine_target | Membership in the CUISINE term synthetic-cuisine using the existing bounded CUISINE_PARENTS resolver. Exact or supported child-to-parent membership gives true; exact evidenced negative can give false under that resolver's policy. Missing knowledge/limits give UNKNOWN. It does not establish dietary membership. |
| synthetic_dinner_compatible | Exact directed COMPATIBLE_WITH to RECIPE_REFERENCE catalogue_reference synthetic-companion, with meal_type=DINNER and null cuisine/role qualifiers. Exact positive/negative gives true/false. Other qualifiers, reverse direction or missing mapping/assertion give UNKNOWN. Compatibility never proves nutritional equivalence or safety. |
| synthetic_allergen_absent | Reserved unsupported safety inference: always null/incomplete UNKNOWN, even when the caller supplies true/false or all inventory flags are complete. |
| synthetic_clinically_safe | Reserved unsupported clinical-safety inference: always null/incomplete UNKNOWN; ancestry, cuisine, classifications and compatibility never fill it. |

Supported exact graph/classification adapter facts are rejected as requirements of
CLINICAL-domain rules: their narrow semantics cannot be silently promoted into wider
clinical claims. The two unsupported safety attributes remain unresolved rather
than acquiring a clinical interpretation. Actual clinical evaluators require a
separately reviewed fact vocabulary and sourced rules.

Graph namespace mapping uses exact `FoodEntity.kind` and `catalogue_reference` in
the accepted release. Node ID, canonical_name, aliases and predicted labels are never
fallbacks. Ingredient content versions and graph-node record versions are distinct;
both are preserved, with no unsupported equality assumption. Full IngredientCoverage
retains source-line/content versions and nested records; KB/graph digests bind the
accepted node/relation definitions. Member 1 still must approve the real versioned
catalogue-to-graph mapping and its preparation semantics.

### Conservative resolution and contradictions

The resolver revalidates candidate/context/KB input storage and constructs the full
authoritative manifest through synthetic KB acceptance. It obtains every graph and
taxonomy resolution by calling existing `resolve_food_relations` and
`resolve_taxonomy_assignment` on that KB's embedded graph. No affirmative resolution
argument or candidate extra field is accepted. A supplied graph-backed VersionedFact
is retained as a declaration for diagnostics, but never fills a missing KB assertion.
An independent exact KB assertion can resolve a missing/null/incomplete caller
observation; its evidence supplies the resolved fact's value/completeness.

Every policy-known supplied observation is checked for compatible type, owner,
unit/basis and provenance before any UNKNOWN/NOT_APPLICABLE short circuit. Supplied
non-null graph claims opposing a known exact KB assertion are rejected, including
incomplete claims and negatives whose eventual use is blocked by an ingredient gap.
Mapped inventory presence opposing an exact KB CONTAINS absence is also rejected.
A complete, fully graph-mapped inventory omitting a canonically identifiable ingredient
with a positive recipe CONTAINS assertion is contradictory. Graph/catalogue/source
evidence conflicts reject the entire request.

Positive containment/origin/classification witnesses never change inventory flags.
Missing inventory, partial enumeration, unresolved canonical lines, incomplete
subingredient expansion and absent graph mappings remain distinct diagnostics.
`unresolved_line_ids` reports both source-unresolved and graph-unmapped source lines.
Source `mapping_complete` is preserved even when a canonical-to-graph mapping is
missing; the latter is separately visible and blocks supported containment negatives.
Even fully complete coverage cannot manufacture a negative assertion from a missing
edge, establish allergen absence or establish clinical safety.

Absent scalar recipe/profile/context requirements now have explicit null/incomplete
VersionedFact gap records with owner/revision and snapshot evidence. Supplied scalar
observations retain their original fact versions and completeness. Derived/gap facts
use version `synthetic-fact-resolution.v1`, exact candidate/context owners, context
revision and food-catalogue release. Ingredient ownership is never used as a recipe
attribute fallback. Unregistered extra vocabulary remains schema-validated and bound
in the original digest without invented evaluator semantics.

Direct assertions, ordered relation/term paths, qualifier fields, selected evidence,
coverage, graph/taxonomy policy versions, gap/limit reason codes and limit flags are
retained in full existing resolution DTOs. Traversal uses fixed existing bounds of
8 hops and 256 visited nodes/terms. A limit yields UNKNOWN with no partial affirmative
witness. Evidence unions sort identities; witness paths retain source-to-target or
child-to-parent order. No unordered-content hash is applied to resolution paths.

### Filtering, traces and explanations

Pipeline: strict batch/shared-input validation → exact shared release checks →
synthetic KB acceptance and catalogue/admission/evaluator validation → canonical
candidate order → candidate binding/manifest construction → conservative fact
resolution → every recipe-stage applicability/predicate evaluation → complete
RuleTrace → existing aggregate_hard_status/is_candidate_eligible → bound explanations
and canonical eligible/excluded partition.

Known applicable hard FAIL dominates UNKNOWN. UNKNOWN applicability or an applicable
UNKNOWN predicate excludes the candidate. Evidenced NOT_APPLICABLE retains predicate
UNKNOWN and resolves that mandatory check under existing aggregation. Zero mandatory
recipe-stage checks remain aggregate UNKNOWN, including empty/soft/deferred-only KBs.
No known FAIL stops later evaluation or explanation generation. Numeric/boolean and
all eight predicate semantics from Task 3.3 remain unchanged.

Duplicate recipe IDs, including alternate snapshot revisions, reject the batch.
Every supplied DTO is recursively validated before processing; semantic contradictions
discovered in any candidate also reject the whole call. No partial result is returned
and there are no writes or other externally visible evaluation side effects. Empty
batches validate the shared release, catalogue, approval/evaluator configuration and
supplied normalized context facts before returning empty decisions/ID tuples.

Explanations are deterministic structured records, with full evaluations/reason
codes/rationale, required fact declarations or gaps, evidence, basis references and
exact witnesses. Their direct candidate/context/KB/manifest digest bindings attach
them to the complete versioned release and profile/workflow through the manifest.
Applicability evidence and normalized context are retained alongside the resolution.
Decision validation rejects explanations detached from those facts, evaluations,
evidence or identities. Backend/XAI consumers can format these records; no model
generates safety explanations in this slice.

Weekly planning and planned-swap manifests retain COMBINATION/DAY/WEEK obligations.
Those predicates do not execute in recipe filtering. RECIPE_FILTER PASS means only
the recipe-stage mandatory checks resolved; plan_feasibility remains NOT_EVALUATED.
Actual composition, locked-slot swap checks and weekly feasibility require later
orchestration/composition/CSP integration.

### Scope, blockers and findings

Created `core/reasoning/facts.py`, `core/reasoning/filtering.py`,
`tests/test_rule_fact_resolution.py` and `tests/test_candidate_filtering.py`.
Integrated `schemas/filtering.py`, `core/reasoning/manifest.py` and
`core/reasoning/evaluation.py`; extended this document. All paths are under
`apps/ai_system/src/savora_ai` or `apps/ai_system/tests` as appropriate.
No changes to Phase 1/2 contracts, graph/taxonomy engines, candidates.py, existing
tests, dependencies, exports or other members' implementation were required.

Remaining integration dependencies: jointly agreed real canonical IDs/fact adapters,
content/preparation and catalogue-to-graph revision mapping, reviewed applicability
and clinical source policy, backend error translation, authenticated release loading
and revocation, approved OpenAPI transport contracts, and later composition/CSP/XAI
integration. An internally consistent rewritten KB/context still cannot authenticate
itself; hashes and SYNTHETIC/APPROVED labels do not establish source truth. Resolver
limits bound traversal, while complete snapshot validation still inspects all records;
production loading must bound input and batch sizes.

No remaining HIGH/MEDIUM implementation finding is known within the documented
synthetic boundary. Production readiness and broader medical claims are not implied.
No staging, commit, push or PR is performed. Task 3.6 is not implemented by this slice.

### Tasks 3.4/3.5 final verification

Verified on 14 October 2026 with the existing environment and UV_NO_SYNC=1.
Installed tools were run through approved escalated commands because the sandbox
previously denied virtual-environment access. No dependency installation, lockfile
change or notebook execution occurred.

| Check | Result |
|---|---|
| Prerequisite full pytest | 2,712 passed in 219.09 s before implementation |
| Existing Task 3.2/3.3 focused regressions | 301 passed after evaluator integration |
| New fact-resolution/filtering tests | 156 passed |
| uv run ruff check . | Passed |
| uv run ruff format --check . | Passed; 102 files already formatted |
| uv run pyright | Passed; 0 errors, 0 warnings |
| uv run pytest -q | 2,868 passed in 150.53 s; all 2,712 previous cases retained |
| Import/scope review | New modules import AI reasoning/schemas, stdlib and Pydantic only; no backend, ORM, database or frontend imports |
| Whitespace/Git scope | Tracked diff/index remain unchanged; all eight intended task files have no trailing whitespace; existing untracked data and other files untouched |

New synthetic integration regressions cover PASS/FAIL/UNKNOWN, FAIL dominating
UNKNOWN, evidenced NOT_APPLICABLE, all mandatory evaluations, missing recipe/profile
and condition facts, zero mandatory checks, deferred obligations, exact KB assertions,
complete/partial/missing/nested/unmapped inventories, positive-versus-negative
contradictions even behind gaps, origin witnesses and hop/visited limits, exact dietary
classification and cuisine hierarchy, prediction/ancestry-to-safety misuse, qualified
compatibility, unsupported safety adapters, clinical scope misuse, node/catalogue
namespace separation, release/profile/context pins, unsupported evaluator policy,
missing catalogue obligations, empty batches, duplicate candidates, batch/graph
ordering, malicious copies/constructs and forged enums, complete explanation digest/
identity/evidence/observation binding, duplicate raw JSON and immutable source inputs.

No remaining HIGH/MEDIUM finding was identified within the documented synthetic
boundary. Status: **READY FOR TASK 3.6**. This checkpoint authorizes no Task 3.6 work
and makes no claim of production authentication or weekly-plan feasibility.

## Task 3.6: independent integration and adversarial audit

Audit scope on 14 October 2026: the complete Phase 1/2/3 input-to-eligibility boundary,
not an assumption that earlier tests proved correctness. Reviewed repository
AGENTS.md/ARCHITECTURE.md, Member 2 documents, applicable schemas/reasoning modules
and tests, and all ten pages of
`C:/Users/venka/Downloads/Savora_GC1_Architecture_Team_Contract.pdf`.
The PDF is explicitly proposed for team approval. Repository architecture remains
authoritative. The proposal uses `filter_recipes` and STRICT/DISTRIBUTION/DIVERSE;
the repository uses `filter_candidates` and STRICT/MAJORITY/MIXED. Those aliases and
their final transport shapes remain pending joint agreement. No illustrative clinical
number or broader food/medical claim from the proposal was activated.

### Independent integration coverage

Created `tests/test_member2_phase3_integration.py` with 136 independent cases.
It imports no earlier test fixtures, production comparison helpers or production
canonicalization helpers to calculate expected outcomes. The suite declares its own
synthetic IDs, releases, source/approval metadata, active-rule and workflow catalogue,
ingredient inventory, graph, taxonomy, facts, normalized context and literal operator
truth tables. Independently encoded canonical hashes check KB, candidate, context
and manifest identity against the documented unordered-content format.

The principal three-candidate fixture expects alpha=FAIL, beta=PASS, gamma=UNKNOWN,
eligible=(beta,), excluded=(alpha,gamma), with all mandatory checks present. Other
cases cover all eight operators and numeric boundaries; true/false/unknown
applicability; dependency UNKNOWN dominating false; FAIL dominating missing recipe/
profile facts; missing/null/incomplete observations; mandatory catalogue omissions;
stale/inactive/unapproved rules; rehashed reduced/wrong manifests; incomplete
mapping/expansion; exact graph and taxonomy proofs; unsupported safety inference;
wrong owners/revisions/releases; malformed types/units/bases; counterfeit enums;
unchecked copies/constructs; duplicate candidates and contradictory declarations;
missing/conflicting evidence; empty batches; deferred constraints; deterministic
partitions/digests; complete trace/explanation binding; original raw JSON duplicates,
alias collisions, exponent overflow and positive/negative integer-to-float overflow.
An AST audit checks every local AI module for forbidden imports and import cycles.

### Verified findings and minimal reproductions

No CRITICAL/HIGH bypass of the public filtering/manifest/evaluation boundary was
reproduced. Two MEDIUM findings were confirmed before fixes: the first independent
111-case run produced three failing regressions (one witness case and two inventory
provenance cases), while the other 108 cases passed.

| ID / severity | Minimal reproduction before correction | Correction and scope |
|---|---|---|
| P3-AUDIT-01 / MEDIUM | Filter a valid candidate requiring synthetic_contains_target=False. Copy the resolved fact with relations=(), replace it in both the resolution and explanation, and validate the copied FilterCandidatesResult. Validation succeeded after the exact graph assertion was discarded. | ResolvedRuleFact now validates KB source/adapter/owner/value/completeness against required relation or taxonomy witness shape, kind, traversal, qualifiers, status and selected provenance. Known facts require matching proofs; origin cannot become false; graph-backed facts cannot relabel caller observations as supplied authority. Missing/mismatched proofs and proof-evidence omissions are rejected. All changes are in Phase 3 schemas. |
| P3-AUDIT-02 / MEDIUM | Evaluate an explicit containment negative with complete inventory, or a positive origin path starting from an inventory ingredient. RuleExplanation.evidence contained the graph proof but omitted the inventory and line evidence used by the adapter. | The Phase 3 resolver now adds original IngredientCoverage and nested source-line evidence for containment negatives, mapping gaps and origin queries. Selected RelationResolution evidence/path ordering remains unchanged. Explanations retain the enriched fact evidence automatically. |

The first finding affected output DTO structural guarantees, not the public API's
mandatory-check selection or predicate truth. `filter_candidates` does not accept
copied result/resolution objects. The second affected attribution of the conclusion,
not its calculated status. Neither finding justifies changing Phase 1/2 declarations
or weakening UNKNOWN. Regression coverage additionally probes witness removal,
missing proof evidence, incomplete known KB observations, wrong fact owners and
caller-supplied graph authority for containment, origin, diet and cuisine adapters.

The corrected combined audit and existing fact/filter suite passed 267 cases;
the expanded independent audit subsequently passed all 136 cases. Output facts
still have declared provenance, not cryptographic source authentication. An attacker
who rewrites an entire internally consistent unsigned KB/context/result can fabricate
declarations; consumers must use the public pipeline with independently trusted
release selection rather than authorize externally supplied traces or decisions.
This is an explicit integration limit, not a hidden production authorization claim.

### Public API and policy handoff

All existing Phase 3 public signatures remain unchanged:

- `validate_contract_json(target, payload) -> Result`: original raw JSON ingress for
  trusted schema types/adapters; duplicate member rejection and bounded input/output
  traversal, including post-validation nonfinite checks.
- `CandidateRecipeFacts.build(content, *, expected_digest=None)` and
  `RuleContext.build(content, *, expected_digest=None)`: strict validating factories;
  supplied digests/pins are verified rather than silently replaced.
- `build_expected_check_manifest(kb, candidate, context) -> ExpectedCheckManifest`:
  accepted synthetic KB catalogue controls complete recipe and deferred obligations.
- `resolve_rule_facts(candidate, *, knowledge, context) -> CandidateFactResolution`:
  exact fixed adapters, no external affirmative graph-result arguments.
- `evaluate_rule_checks(kb, candidate, context, manifest) -> tuple[RuleEvaluation, ...]`:
  recomputes trusted resolution/manifest and evaluates every recipe-stage rule.
- `filter_candidates(candidates, *, knowledge, context) -> FilterCandidatesResult`:
  whole-batch validation, complete traces/explanations and PASS-only partition.

Policy versions remain the ones documented above: candidate-recipe-facts.v1,
rule-context.v1, candidate-content-digest.v1, expected-check-manifest.v1,
synthetic-workflow-scopes.v1, synthetic-hard-rule-admission.v1,
synthetic-rule-evaluation.v1, synthetic-attributes.v1/v2,
synthetic-manifest-identity.v1, candidate-fact-resolution.v1,
synthetic-fact-adapters.v1, synthetic-fact-resolution.v1,
rule-explanation.v1, synthetic-rule-explanation.v1 and filter-candidates-result.v1.
The audit corrections restore required proof/provenance semantics without changing
DTO fields, operator truth, manifests, obligation sets or policy selection.

Manifest hashes bind full definitions, approvals, source releases, workflow, context,
profile and candidate revision/digest. PROFILE/RECIPE is fixed; no reduced-scope
caller override exists. UNKNOWN applicability/required safety knowledge excludes;
known hard FAIL dominates; evidenced NOT_APPLICABLE resolves its check without
evaluating its predicate; empty mandatory sets never authorize eligibility.
Graph/taxonomy facts use only accepted KB records; missing knowledge never implies
absence, and origin/cuisine/compatibility never manufactures allergen or clinical
safety. COMBINATION/DAY/WEEK obligations survive weekly-plan and planned-swap
filtering; recipe-stage PASS never means a plan or swap is feasible.

Determinism guarantees are precise: output candidate partitions, checks, facts and
evidence unions have canonical identity ordering; selected graph/taxonomy witness
paths have deterministic semantic order; repeated identical inputs and batch order
permutations produce identical outputs; KB/candidate/context/manifest digests ignore
unordered declaration insertion order while preserving scalar types. Source records
(for example embedded evidence/required-fact/ingredient declaration tuples) retain
their accepted declaration order. Therefore arbitrary reordering of those source
tuples can change their reproduced serialized representation while preserving
semantic decisions and digests. No claim of universal byte-identical serialization,
RFC 8785 compliance, signatures or source authenticity is made.

Member 1 must supply agreed canonical recipe/ingredient IDs, release-bound content
and preparation revisions, authoritative quantities/bases, ingredient enumeration/
mapping/expansion completeness, and approved graph/taxonomy mappings. Member 3 must
supply normalized profile/context owners and revisions, explicit safety unknowns,
workflow selection, independently selected KB/release pins, strict original-JSON
ingress, resource bounds and backend failure translation. Backend owns authenticated
loading and all database I/O; AI owns deterministic symbolic decisions.

Pending joint decisions: production fact/evaluator vocabulary; source, reviewer and
revocation authority; authoritative catalogue/version mapping; real dietary/clinical
rule evidence and exceptions; final workflow/applicability policies and dependency
semantics; public API/DTO naming and OpenAPI transport; cuisine-policy aliases and
composition-level meaning; conversion sources and completeness requirements; later
combination/CSP/swap integration. Production authentication, real clinical clearance,
weekly scheduling/portion optimization, ranking, persistence and UI remain outside
this synthetic commit. No EDA notebook was rerun.

### Audit file and Git scope

Task 3.6 creates only `tests/test_member2_phase3_integration.py` and modifies only
`schemas/filtering.py`, `core/reasoning/facts.py` and this document. The complete
Phase 3 review bundle contains six source modules, six test files and this document
(13 files total). Phase 1/2 schemas/reasoning engines match the pre-audit SHA-256
fingerprints; tracked files, HEAD and Git index are unchanged. The user-selected
branch remains feature/member2-rule-filtering. Existing data and
phase1-security-fix.patch are unrelated pre-existing untracked files.

The proposal PDF was extracted in an isolated `uv run --no-project --with pypdf`
environment because no PDF reader was installed. No repository dependency/lockfile
or project virtual environment was changed. Temporary extraction files were removed.
No staging, commit, push, merge, rebase or PR was performed.

### Task 3.6 final verification and verdict

Verification used the existing project environment with UV_NO_SYNC=1 and approved
escalated commands for its installed tools. Final results on 14 October 2026:

| Required check | Result |
|---|---|
| uv run ruff check . | Passed |
| uv run ruff format --check . | Passed; 103 files already formatted |
| uv run pyright | Passed; 0 errors, 0 warnings |
| uv run pytest -q | 3,004 passed in 175.13 s; all previous 2,868 cases plus 136 independent audit cases |
| Phase 1/2 regression and integrity | Full regressions pass; all seven pre-audit contract/reasoning SHA-256 fingerprints unchanged |
| AI architecture | Independent AST import audit passes: no backend/ORM/database/frontend imports or local import cycles |
| Determinism/provenance | Independent digests, batch permutations, proof consistency and enriched inventory-provenance checks pass; ordered witness paths preserved |
| Whitespace/Git | Tracked/index diffs empty; intended Phase 3 files have no trailing whitespace; HEAD remains 3ef1bbc5bfb487c8ddd0e920a16937e4feceae3f on feature/member2-rule-filtering |

Overall verdict: the entire **synthetic deterministic recipe-filtering system is
READY TO COMMIT** after the two verified MEDIUM fixes. No unresolved CRITICAL/HIGH/
MEDIUM implementation finding remains within the documented boundary. Phase 1/2
contracts were not changed. Source authentication, clinical approval and final team
integration decisions remain explicit external dependencies. This verdict authorizes
no staging, commit, push, merge, rebase or PR; those actions await explicit instruction.
