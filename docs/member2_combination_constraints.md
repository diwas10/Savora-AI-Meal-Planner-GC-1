# Member 2 Phase 4, prompt 1: combination contracts and deferred admission

Status: provisional synthetic implementation, 15 October 2026. These engineering
contracts are authorized for this local slice, not jointly approved production
interfaces. No authenticated source, real clinical rule, threshold, interaction or
medical guidance is activated.

## Scope, architecture and ownership

Member 2 owns these strict symbolic declarations and admission policy. Member 1
supplies verified recipe/preparation/portion data, culinary roles and composed
candidates; Member 3 supplies normalized context, trusted release selection and
orchestration. Future combination evaluation consumes these DTOs before ranking.
The backend continues to own authentication, persistence and database access.

Reviewed AGENTS.md; ARCHITECTURE.md sections 3-6, 8, 11, 13-15; Member 2 contract,
knowledge-graph and filtering documents; relevant Phase 1-3 schemas, reasoning and
tests; and all ten pages of the locally available October 2026 proposed team contract
at `C:/Users/venka/Downloads/Savora_GC1_Architecture_Team_Contract.pdf`.
The proposal's `filter_recipes` and STRICT/DISTRIBUTION/DIVERSE differ from the
repository's `filter_candidates` and STRICT/MAJORITY/MIXED. These existing interface
decisions remain pending; no alias or production semantic change is introduced.
Repository architecture remains authoritative.

Implemented only six DTOs, their local enums, a minimal Phase 3 admission extension,
independent tests and this document. No combination evaluator, nutrition aggregation,
unit conversion, solver, scheduling, endpoint, persistence, ranking or UI is added.
No HTTP/OpenAPI/TypeScript contract or package export changes are required.

## Independently reproduced admission blocker

Before production edits, `test_new_combination_attribute_admitted_and_deferred`
constructed its own synthetic accepted KB with a complete workflow/scope check
catalogue, approved ACTIVE ABSOLUTE CULINARY COMBINATION rule, recipe snapshot and
WEEKLY_PLAN context. Its predicate was the new explicit vocabulary name
`synthetic_combination_roles_compatible`, boolean EQ True, no unit, with
`synthetic-context-enabled / 1` applicability. No prior test fixtures were imported.

On unchanged HEAD `c077b9af3bdd8f7a48322e27833e37c607d115b1`, the two-case reproduction
returned **1 failed, 1 passed**. The admission test raised:

```text
ValidationError: SyntheticRulePolicy
Value error, unsupported synthetic required attribute
```

Exact path: `build_expected_check_manifest()` -> `_mandatory_checks()` ->
`_validate_rule_policy()` -> `_ATTRIBUTES.get(name)` returned None -> `_reject()`.
The original rejection occurred at manifest.py:130; original caller lines were
196 and 258. All catalogue checks, including deferred checks, used the same
recipe-stage attribute registry before scope partitioning. Merely registering a
recipe-owned attribute would give the new fact the wrong ownership semantics.
There was no caller-supported registration mechanism; the independent fixture
declared the proposed name, and this slice registers it explicitly in application
configuration, separately from recipe adapters.

The same reproduction now passes without deleting or weakening any mandatory
obligation. Unknown attributes still reject.

## Versioned scope-aware admission

New manifest `attribute_policy_version`: **synthetic-attributes.v3-combination**.
Its immutable application-owned `_COMBINATION_ATTRIBUTES` registry is separate from
`_ATTRIBUTES`; no caller-defined attribute registration is accepted.

| Exact attribute | Scope / ownership | Domain | Type | Operators | Unit | Applicability |
|---|---|---|---|---|---|---|
| synthetic_combination_roles_compatible | COMBINATION | CULINARY | boolean | EQ, NE | None | synthetic-context-enabled / 1 |
| synthetic_combination_composition_complete | COMBINATION | CULINARY | boolean | EQ, NE | None | synthetic-context-enabled / 1 |

These are fictional quantity-independent declarations. Role compatibility is not
deduced from names, graph ancestry or a complete composition flag. Required facts
may include either registered combination attribute and existing PROFILE/CONTEXT
prerequisites. RECIPE-owned or unregistered prerequisites reject under this new
policy. The accepted descriptor must declare exactly `(synthetic_context_enabled,)`;
its dependencies continue through existing supported descriptor validation.

Every mandatory rule must remain ACTIVE, ABSOLUTE and APPROVED, with exact accepted
versions, declaration evidence and approval metadata. KB acceptance still checks
the complete authoritative catalogue, lifecycle/severity/scope, reference freshness
and coverage. Admission does not execute or remove a check based on applicability.
Wrong scope/domain, type, unit, applicability, unknown attributes and unapproved
mandatory rules reject. Unknown policy tokens reject.

The builder deterministically selects v3 only when selected workflow obligations
contain new combination attributes. A manifest carrying them under v1/v2 rejects,
even if rehashed; v3 with no new combination attributes also rejects. Existing
scalar-only and derived-recipe workflows retain `synthetic-attributes.v1` and
`synthetic-attributes.v2`, respectively, with their existing tokens, semantics and
manifest identity algorithm unchanged. A v3 manifest can also carry v1/v2 recipe
checks without changing their resolution or evaluation policy.

PROFILE/RECIPE checks remain required at RECIPE_FILTER. COMBINATION/DAY/WEEK checks
remain authoritative deferred obligations for WEEKLY_PLAN/PLANNED_SWAP. DAY/WEEK
continue their existing attribute admission behavior, including old recipe-stage
names in deferred rules. New combination names cannot migrate to DAY/WEEK.
Standalone craving still selects PROFILE/RECIPE only. Public signatures for
`filter_candidates`, `build_expected_check_manifest`, fact resolution and evaluation
are unchanged; deferred combination predicates never execute in recipe filtering.
Manifest identity/digest still includes every complete definition and deferred
obligation. Evaluation rebuilds it against accepted inputs to reject reduced or
rewritten manifests. Phase 1/2 public contracts and semantics are unchanged.

## Exact DTOs and public constructors

Import from `savora_ai.schemas.combinations`. Every DTO supports the ordinary
validating constructor `ClassName(**fields)` and `ClassName.model_validate(payload)`.
Python inputs use enum members and tuples; camelCase JSON uses tokens and arrays.
Each DTO has a defaulted, fixed `schema_version`:

| DTO | schema_version | Fields beyond schema_version |
|---|---|---|
| RecipeSnapshotReference | recipe-snapshot-reference.v1 | recipe_id, recipe_version, snapshot_id, snapshot_version, content_digest, catalogue_version |
| PreparationBinding | preparation-binding.v1 | preparation_id, version, recipe_snapshot: RecipeSnapshotReference, basis_reference: EvidenceReference, evidence |
| ComponentQuantity | component-quantity.v1 | amount: positive finite int/float, unit: QuantityUnit, preparation_id, preparation_version, basis_reference: EvidenceReference, portion_reference: EvidenceReference, evidence |
| CombinationComponent | combination-component.v1 | component_id, recipe_snapshot: RecipeSnapshotReference, preparation: PreparationBinding, quantity: ComponentQuantity or None (default None), role_references: tuple[FoodEntity, ...], evidence |
| CombinationObservation | combination-observation.v1 | fact_id, version, combination_id, combination_version, portion_configuration_id/version (default None), observation: FactObservation, measurement_basis: CombinationMeasurementBasis or None (default None), basis_reference: EvidenceReference or None (default None) |
| CombinationFacts | combination-facts.v1 | digest_policy_version=combination-content-digest.v1, combination_id, version, snapshot_id, snapshot_version, components, composition_complete, composition_gap_reasons, portion_state, portion_configuration_id/version (default None), observations, context_id/version/digest, kb_id/version/digest, graph_id/version, catalogue_version, taxonomy_version (required, nullable), check_catalogue_version, evidence, content_digest |

Identity fields use existing opaque-ID constraints; versions use nonblank strings;
digests require exactly 64 lowercase hexadecimal characters. `content_digest` in a
RecipeSnapshotReference is the pinned CandidateRecipeFacts digest, not a hash of
the reference itself. Catalogue identity follows Phase 3's single catalogue release
namespace (`catalogue_version`); no unapproved new catalogue-ID field is invented.
Evidence collections are immutable tuples of existing EvidenceReference records.

Only CombinationFacts adds a validating digest factory:

```python
CombinationFacts.build(content, *, expected_digest=None) -> CombinationFacts
```

`content` is a strict field dictionary or CombinationFacts instance. Omit its digest
to compute it; supply one to verify it. An optional independent expected_digest is
also verified. Null, malformed or incorrect supplied digests never get replaced.
Direct model validation and JSON ingress require an existing correct digest.

Use the existing original-input boundary for security-sensitive JSON:

```python
from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.combinations import CombinationFacts

snapshot = validate_contract_json(CombinationFacts, original_raw_json)
```

Native model_validate_json is useful for trusted/generated round trips but cannot
recover overwritten raw duplicate keys. Do not decode/normalize untrusted JSON
before strict ingress. Existing ingress size, depth, numeric and output bounds apply.
`model_copy(update=...)` and `model_construct` are unchecked Pydantic facilities;
their data must pass recursive validation at constructors/build/ingress boundaries.

## Identity, multiplicity, portions and completeness

Combination identity/version, combination snapshot identity/version and component
occurrence IDs are distinct. At least one occurrence is required; occurrence IDs
are unique. Repeated recipes are valid with distinct occurrence IDs, and remain
distinct records in the digest. No recipe ID or role is inferred from a label.
The same snapshot ID/version cannot declare conflicting recipe references. Within
an exact recipe snapshot, preparation ID/version declarations must agree. Reused
role entity IDs must also agree across components.

PreparationBinding pins the complete recipe reference and versioned basis evidence.
The component's reference must equal the preparation's reference. Quantity pins
preparation ID/version and the exact same basis evidence; raw/cooked preparations
and incompatible bases cannot be exchanged silently. QuantityUnit is exactly g,
mL or serving. All three units conservatively require versioned portion and basis
references plus evidence. Amount is strictly positive and finite; bool, null, zero,
negative, string and nonfinite values reject. No conversion or density is assumed.

PortionState is UNASSIGNED or FIXED. UNASSIGNED requires every quantity absent and
both configuration fields absent. FIXED requires every quantity present and both
nonblank configuration identity/version fields. Any partial assignment rejects.
The configuration's actual quantities are included in the combination digest.

Composition completeness is independent of candidate ingredient coverage. A complete
composition requires no composition gaps. An incomplete one requires at least one
unique CompositionGapReason: INCOMPLETE_COMPOSITION or UNVERIFIED_COMPOSITION.
No ingredient absence, inventory completeness, allergy safety or clinical clearance
is inferred from this declaration. A known embedded synthetic composition-complete
observation must agree with the composition flag; an unknown one remains unknown.

Each component needs nonempty culinary role references and evidence. Roles use
existing FoodEntity CULINARY_ROLE_REFERENCE records with explicit IDs, versions,
catalogue references and evidence. Duplicate roles within a component reject.
Membership in accepted role/catalogue releases requires future cross-validation.

## Observations, evidence and digest guarantees

CombinationObservation has combination ownership only; it does not use or extend
Phase 3's recipe-owned VersionedFact or FactSubjectKind. Its fact ID must equal the
embedded FactObservation ID, and owner/version must equal the enclosing combination.
Duplicate fact IDs reject, including identical, contradictory or alternate revisions.
Configuration pins are paired and, when present, match the enclosing FIXED snapshot.

Numeric observations require units through FactObservation and an explicit
CombinationMeasurementBasis plus versioned basis evidence. AS_RECORDED numeric
facts have no fixed configuration pins. FIXED_PORTION_TOTAL numeric facts require
both exact configuration pins. Boolean/categorical/null facts have no numeric basis;
boolean/categorical declarations may still carry paired configuration pins. Existing
FactObservation distinguishes zero, False, explicit null/incomplete and missing facts.
No default truth, zero filling or model-generated nutrition is introduced.

Every supplied record requires its evidence, including gaps. Identical global
evidence ID/version reuse is allowed only with identical source, locator and
SYNTHETIC metadata. Duplicate evidence within one collection and contradictory
evidence across preparations, quantities, roles and observations reject. Missing
evidence cannot establish compatibility or any eligibility decision.

All DTOs inherit strict, frozen, extra-forbidden, camelCase, recursively revalidated
contracts with immutable tuples and canonical enum-member checks. Invalid unchecked
copies/constructs, alias collisions and hostile custom containers reject before
normalization. Original raw duplicate keys reject via validate_contract_json.

Digest policy uses the existing canonical JSON/SHA-256 algorithm under the explicit
combination-content-digest.v1 token: camelCase fields, sorted dictionary keys,
recursive sorting of unordered arrays by canonical encoding, ASCII escaping, compact
separators and no nonfinite numbers. Only the outer content_digest is excluded;
embedded recipe digests remain included. Arrays retain multiplicity; declaration
permutations preserve digest while serialized source order may differ. There are no
ordered witness paths in these DTOs. No RFC 8785 or byte-identical serialization
claim is made.

Changing a component occurrence, recipe snapshot, preparation, quantity, evidence,
context, KB or other content invalidates the old digest. This is integrity binding,
not a signature or source authentication. A consistently rewritten unsigned snapshot
with a new digest remains only a declaration and grants no eligibility authority.

## Required future cross-validation and prompt 2 boundary

Before any combination evaluation can PASS, the next slice must:

1. Revalidate all original DTOs and accept the independently selected synthetic KB
   and normalized context; compare combination context ID/version/digest exactly and
   KB ID/version/digest, graph, taxonomy, catalogue and check-catalogue releases.
2. Resolve **every** component reference against an independently accepted candidate
   set, comparing recipe ID/content version, snapshot ID/version, candidate content
   digest and catalogue release. Check candidate graph/context pins through existing
   Phase 3 boundaries. Missing/stale/conflicting candidates cannot silently pass.
3. Preserve occurrence multiplicity while evaluating PROFILE/RECIPE prerequisites
   for every pinned candidate under that exact context and accepted KB. A recipe-stage
   failure/unknown cannot be overridden by combination declarations.
4. Validate preparations, portion definitions, basis evidence and culinary role
   references against authoritative Member 1/accepted release records, including
   exact metadata, source relevance, role mapping and permitted quantities/units.
   Verify fixed configuration ID/version resolves to these exact occurrence quantities
   before using a fixed numeric observation. IDs and evidence labels alone are not
   proof that an observation describes the declared preparation/configuration.
5. Derive a complete mandatory COMBINATION manifest from accepted obligations,
   validate applicability/dependencies, registered fact type/unit/basis and source
   evidence, and evaluate deterministic PASS/FAIL/UNKNOWN without recipe ownership
   substitution. A caller's eligibility/status flag never becomes authoritative.
6. Return UNKNOWN for **zero mandatory COMBINATION hard checks**, even if recipe
   prerequisites PASS. Preserve DAY/WEEK obligations as deferred. No daily/weekly
   feasibility, nutrient equivalence, allergy absence or clinical clearance follows
   from graph ancestry, role compatibility or a local composition declaration.

This slice intentionally cannot compare a lone reference to an absent external
candidate set or reject a syntactically valid alternative context/KB pin without
an independently trusted counterpart. It exposes no combination eligibility/status
API. Tests document these limits and prove that such changes invalidate an old pin.
Implementing the above checks belongs to the upcoming full combination evaluation
task; no partial evaluator is hidden in these DTOs.

## Pending Member 1 / Member 3 decisions

Joint approval remains needed for canonical combination/occurrence/snapshot IDs,
catalogue namespace and revision mapping, role references/templates and compatibility
evidence, preparation identity/bases, fixed configuration lifecycle, verified portion
definitions and conversion sources, source authority, production rule vocabulary,
reviewer/revocation policy, resource bounds and final transport/API naming.
Member 1 owns verified numeric data, preparations/portions, composition and ranking;
Member 3 owns normalized context/profile, trusted authenticated release loading,
strict original-JSON ingress and backend failure translation. No production clinical
source or reviewer is authenticated by these fictional tests or APPROVED labels.

## Independent verification and Git scope

The new test module imports no earlier test fixtures or production digest helpers
as oracles. It defines its own accepted synthetic releases, candidates, context,
evidence and rules, and independently encodes canonical hashes. Coverage includes
valid DTOs and wire round trips, multiplicity and empty/duplicate components,
UNASSIGNED/FIXED/partial quantities, preparations/bases/evidence, strict numbers and
units, zero/False/null/missing values, contradictory composition/observations,
digest tampering and independent pins, invalid bindings, counterfeit enums,
unchecked objects, aliases, hostile containers, nested original JSON duplicates,
unsupported attributes/scopes/policies/applicability, stale/inactive/soft/missing
catalogue obligations, old v1 behavior, preserved DAY/WEEK obligations and unchanged
PROFILE/RECIPE PASS and UNKNOWN filtering behavior.

Verification on 15 October 2026 used the existing project environment. Installed
tools ran through approved escalated uv commands because the sandbox could not
initialize the uv cache. The PDF was read in an isolated `--no-project --with pypdf`
environment; no project dependencies or lockfile were changed.

| Check | Result |
|---|---|
| Independent pre-fix reproduction | 1 failed at the original admission blocker, 1 passed |
| New independent contract suite | 194 passed |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed; 105 files already formatted |
| `uv run pyright` | Passed; 0 errors, 0 warnings |
| `uv run pytest -q` | 3,198 passed in 94.27 s; all 3,004 prior cases plus 194 new cases |
| Architecture/import audit | Passed as part of full pytest; all AI modules, including combinations.py, checked for forbidden dependencies and local import cycles |
| Phase 1/2 compatibility | No Phase 1/2 file changes; full existing regression suite passes |
| Git/whitespace scope | Only the five intended files; no whitespace errors or staged changes; branch and HEAD unchanged |

No unresolved HIGH/MEDIUM implementation finding was identified within this first
synthetic slice. External source authentication, team approval and the future
cross-object evaluator remain explicit integration dependencies. Verdict:
**READY FOR PHASE 4 PROMPT 2**. Prompt 2 was not implemented.

Exact authorized file scope:

- Created: `apps/ai_system/src/savora_ai/schemas/combinations.py`
- Created: `apps/ai_system/tests/test_combination_contracts.py`
- Created: `docs/member2_combination_constraints.md`
- Modified: `apps/ai_system/src/savora_ai/schemas/filtering.py`
- Modified: `apps/ai_system/src/savora_ai/core/reasoning/manifest.py`

The explicitly requested branch is `feature/member2-combination-constraints`,
despite the general feat/ prefix convention. HEAD is the exact Phase 3 baseline
`c077b9af3bdd8f7a48322e27833e37c607d115b1`. No stage, commit, push, merge, rebase or PR
is authorized or performed. Existing Food.com/USDA untracked datasets and
`phase1-security-fix.patch` are outside scope and untouched. No EDA notebook runs.

## Prompt 2: deterministic combination eligibility

Implemented 15 October 2026. This section supersedes the first-slice statements
above that describe combination evaluation as future work. All contracts remain
provisional and synthetic. No production rule or external source is activated.

### Explicit upstream authority boundary

The repository has no preparation, portion or whole-composition authority provider.
The user explicitly selected: "Accept separately supplied, upstream-trusted existing
DTOs for synthetic evaluation; missing authority returns UNKNOWN."

The new entrypoint therefore accepts an optional, separately selected
`trusted_combination: CombinationFacts`. Member 1 / the trusted backend loader owns
selection and verification of this complete source snapshot, including preparation,
basis, portion definitions, composition and combination observations. It must describe
the **exact** proposed snapshot: every identity/version, component occurrence, recipe
reference, preparation, quantity, role, evidence, context and release is integrity-bound.
Differences raise ValidationError, including a consistently rehashed proposal that
differs from the independently supplied source. Unordered declaration permutations
remain equivalent under the existing digest contract.

This parameter is a trust boundary, not an authentication service. It must never be
populated by promoting arbitrary request data to authority. Matching digests alone,
object identity, source labels and APPROVED metadata do not authenticate a source.
The synthetic tests explicitly supply independently designated source DTOs. An
omitted trusted source leaves preparation/composition authority UNKNOWN and all
proposal-owned combination facts unresolved. Untrusted negative facts also remain
UNKNOWN rather than manufacturing a known FAIL. Production source loading and
review remain pending. Partial preparation-only authority providers are not added.

### Public interface and result contracts

```python
from savora_ai.core.reasoning.combinations import evaluate_combination


def evaluate_combination(
    combination: CombinationFacts,
    *,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    trusted_combination: CombinationFacts | None = None,
) -> CombinationEligibilityResult: ...
```

The six Prompt 1 DTOs are reused unchanged. Existing Phase 1-3 entrypoints and
policies are unchanged. The new result types live in `schemas/combination_evaluation.py`:

- `CombinationPrerequisite`: name, status (RuleStatus or explicit None only for
  unassigned portions), reason, evidence. Five complete, canonically ordered records:
  CANDIDATE_MEMBERSHIP, COMPOSITION_COMPLETENESS, PORTION_CONFIGURATION,
  ROLE_REFERENCES and SOURCE_AUTHORITY. These are diagnostic prerequisite names,
  not additions to the attribute vocabulary or new rule/application policies.
- `CombinationEligibilityResult`: schema_version=combination-eligibility-result.v1,
  stage=COMBINATION, plan_feasibility=NOT_EVALUATED, combination, trusted_combination,
  recipes (existing FilterCandidatesResult), accepted_role_references (exact FoodEntity
  records), prerequisites, trace (existing RuleTrace), deferred_checks, status, evidence.
  Use existing `is_candidate_eligible(result.status)`; no caller eligibility flag is
  accepted. All records retain strict, frozen, extra-forbidden, camelCase and recursive
  validation conventions; original raw JSON uses validate_contract_json.

The combination trace binds a `combination-check-manifest.v1` content record containing
the full proposal/source snapshots, normalized context, selected recipe manifest
digests, accepted role references and complete COMBINATION/DAY/WEEK definitions.
Its identity is `combination-manifest-<digest>` and version is
`combination-check-manifest.v1:<digest>`. This is a serialization/identity contract,
not a new synthetic evaluation policy. The existing unordered canonical SHA-256
format is reused only over unordered declarations and digest references; ordered
recipe graph witnesses remain in recipe results and are never reordered for hashing.

### Evaluation flow and decisions

1. Recursively revalidate the complete request, including all candidates and the
   optional upstream source. Existing contracts validate quantities, preparations,
   duplicate occurrences/observations, immutable containers and content digests.
   Cross-input provenance is conflict-checked before any decisions are returned.
2. Match the proposal's exact context ID/version/digest and KB, graph, catalogue,
   taxonomy and check-catalogue releases to the independently selected inputs.
   Accept the synthetic KB through the existing builder and complete check catalogue.
   Standalone CRAVING_DISCOVERY cannot enter this path.
3. Select every authoritative COMBINATION check, validate its existing v3 combination
   policy configuration, and retain DAY/WEEK obligations. Legacy recipe-owned
   deferred COMBINATION attributes remain admitted by Phase 3 as before, but are
   unsupported at this evaluator and raise ValidationError. No silent omission or
   recipe-fact reinterpretation is allowed.
4. Run existing filter_candidates over the whole accepted candidate pool. Malformed
   or duplicate candidates anywhere reject atomically. Retain only decisions for
   referenced recipes, then match every occurrence to the exact recipe/content and
   snapshot versions/digest/catalogue in those manifests. A missing candidate yields
   UNKNOWN; a conflicting supplied revision raises ValidationError. Repeated recipe
   occurrences remain distinct while sharing one exact recipe-stage decision.
   Unrelated recipe failures do not exclude a combination using different recipes.
5. Verify every explicit role reference against the exact accepted KB graph entity.
   Missing role records yield UNKNOWN; conflicting entity content raises ValidationError.
   The upstream source supplies the role assignments and whole-composition facts.
   No pairwise, reverse, transitive or ancestry-based compatibility policy is invented.
6. Require upstream preparation/composition authority and positive composition
   completeness. A declared incomplete composition is an unresolved completeness
   prerequisite; an applicable hard completeness rule can independently establish
   FAIL from its trusted False observation. Do not fill an absent observation from
   the flag. FIXED quantities require the exact upstream configuration and quantities.
   UNASSIGNED remains valid at this quantity-independent stage: its portion diagnostic
   is explicitly None/unevaluated, never a claim of approved quantities. No fixed
   assignment requirement or solver policy is introduced.
7. Resolve only the two registered combination attributes from the trusted source.
   They must be boolean/null and quantity-independent (no portion configuration pins).
   PROFILE/CONTEXT prerequisites come exclusively from validated normalized context,
   never same-named CombinationObservations. Missing facts become explicit evidenced
   gaps. Registered malformed declarations reject even behind unknown authority or
   NOT_APPLICABLE conditions. Other generic observation names grant no authority.
8. Reuse existing descriptor resolution, conservative applicability conjunction and
   boolean EQ/NE predicate evaluation. Every mandatory rule executes or records its
   explicit UNKNOWN/NOT_APPLICABLE state; a known FAIL does not stop subsequent checks.
   Existing ACTIVE/ABSOLUTE/APPROVED, type/unit, applicability and policy gates apply.
9. Aggregate recipe prerequisites, structural/source prerequisites and the complete
   COMBINATION RuleTrace. Known hard FAIL dominates UNKNOWN. Otherwise any unresolved
   mandatory fact/applicability/source/membership or recipe-stage UNKNOWN yields
   UNKNOWN. Nonempty checks resolved by PASS or evidenced NOT_APPLICABLE may PASS
   only when all other prerequisites are established. Zero mandatory COMBINATION
   checks remain UNKNOWN; zero recipe-stage checks retain existing Phase 3 UNKNOWN.

Result validation checks exact context/releases, complete prerequisite identities
and statuses against retained source/membership/role records, trace fact ownership
and source binding, complete evaluations, recipe-manifest deferred obligations,
manifest identity, full evidence union and final hard aggregation. Removing recipe
decisions, role records, source authority, required checks or deferred obligations
cannot leave an internally accepted stale PASS. As in Phase 3, serialized decisions
are evidence records, not an authorization API: consumers must call the public
pipeline with independently trusted inputs rather than accept externally rewritten
traces or decisions as source truth.

### Independent testing and final review

`tests/test_combination_evaluation.py` defines independent synthetic KB/check
catalogues, profile/context facts, recipe snapshots, preparation/quantity records,
roles and combination declarations. It imports no earlier test fixtures, production
predicate/comparison helpers or production canonicalization helpers as test oracles.
Literal expected outcomes and an independently encoded manifest hash check behavior.

Coverage includes legitimate UNASSIGNED/FIXED PASS, both boolean operators and
expected values, multiple simultaneous rules, FAIL/UNKNOWN precedence, zero checks,
applicability/dependency UNKNOWN and evidenced NOT_APPLICABLE, missing/duplicate
components, repeated recipes, missing candidates and snapshot conflicts, untrusted
positive/negative observations, incomplete/missing facts, invalid preparation/basis,
partial quantities, missing/conflicting evidence, role lookup gaps/conflicts,
context/KB/digest mismatch, unsupported policies/attributes, unapproved rules,
counterfeit enums, hostile containers, unchecked objects, alias/raw-JSON collisions,
source/context namespace isolation, unrelated candidate behavior, input immutability,
source order determinism, output proof/obligation removal and source-to-trace binding.

The independent review checked public-input false PASS, status precedence, complete
obligations, source authority and context ownership, deterministic output and
complexity. Review-driven hardening retains actual accepted role records and
recomputes prerequisite statuses during result validation; combination observations
cannot fill missing normalized profile facts; traces retain exact source observations.
Existing private helpers are reused to avoid a second evaluator framework. No Phase
1-3 production files or Prompt 1 DTOs/tests were changed for Prompt 2.

Prompt 2 creates only `core/reasoning/combinations.py`,
`schemas/combination_evaluation.py` and `tests/test_combination_evaluation.py`, and
appends this document. All paths are under apps/ai_system/src/savora_ai,
apps/ai_system/tests or docs as appropriate. The earlier five-file Prompt 1 working
tree remains present. Production authentication, Member 1 source-provider integration,
joint public API approval, real clinical policies, nutrition aggregation, ranking,
portion optimization, DAY/WEEK scheduling, persistence and frontend remain deferred.
No external API calls, migrations, dataset changes or notebook execution are added.

### Prompt 2 final verification and verdict

Final checks on 15 October 2026 used the existing project environment through
approved escalated uv commands. No dependencies or lockfiles were changed.

| Check | Result |
|---|---|
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed; 109 files already formatted |
| `uv run pyright` | Passed; 0 errors, 0 warnings |
| `uv run pytest -q` | **3,278 passed in 112.24 s**; all 3,198 Prompt 1 cases plus 80 new independent cases; no skips or failures |
| Architecture/import audit | Passed in full pytest; every local AI module checked for forbidden dependencies and import cycles |
| Phase 1/2 integrity and Phase 3 compatibility | Existing Phase 1/2 files unchanged; full baseline regressions pass; no Prompt 2 changes to Phase 1-3 production files |
| Whitespace and Git | Passed; no staged changes or unexpected files; branch/HEAD unchanged |

No unresolved HIGH/MEDIUM implementation finding remains within this explicit
synthetic/upstream-trusted boundary. Source authentication and actual Member 1
provider integration remain dependencies, not claims made by a content digest.
Verdict: **READY FOR PHASE 4 PROMPT 3**. No production readiness is claimed.

Branch: `feature/member2-combination-constraints`. HEAD:
`c077b9af3bdd8f7a48322e27833e37c607d115b1`. The working tree contains the five
Prompt 1 files plus the three new Prompt 2 files (this existing handoff document
is updated in place), alongside the pre-existing unrelated untracked datasets and
patch. No staging, commit, push, merge, rebase or PR was performed.

## Prompt 3: integration hardening and final handoff

Status: 15 October 2026. The previous prompt sections are historical checkpoints;
this section records the final synthetic foundation review. The upstream-trusted
DTO boundary explicitly selected during Prompt 2 remains in force. No provider,
automatic trust mechanism, production approval, clinical policy or new attribute
policy is introduced.

### Callable surface and input/output ownership

The actual combination entrypoint remains:

```python
from savora_ai.core.reasoning.combinations import evaluate_combination
from savora_ai.schemas.candidates import CandidateRecipeFacts, RuleContext
from savora_ai.schemas.combination_evaluation import CombinationEligibilityResult
from savora_ai.schemas.combinations import CombinationFacts
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot


def evaluate_combination(
    combination: CombinationFacts,
    *,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    trusted_combination: CombinationFacts | None = None,
) -> CombinationEligibilityResult: ...
```

This is a working local Python interface, still provisional for team/public
transport approval. No backend endpoint or provider interface is implied. The
proposal, independently selected candidate pool, accepted KB, normalized context
and optional source DTO are distinct inputs. Only the public evaluator produces
decisions; it accepts no caller-supplied eligibility flag, result or trace override.

Other actual callable boundaries used during integration are:

```python
# savora_ai.schemas.combinations.CombinationFacts
@classmethod
def build(
    cls, content: Self | dict[str, object], *, expected_digest: str | None = None
) -> Self: ...


# savora_ai.schemas.candidates (Result is the existing generic type parameter)
def validate_contract_json(
    target: type[Result] | TypeAdapter[Result], payload: str | bytes | bytearray
) -> Result: ...


# savora_ai.core.reasoning.filtering
def filter_candidates(
    candidates: tuple[CandidateRecipeFacts, ...],
    *,
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
) -> FilterCandidatesResult: ...


# savora_ai.schemas.reasoning
def is_candidate_eligible(status: RuleStatus) -> bool: ...
```

Use the six original combination DTOs and the exact fields documented above;
constructors and signatures are unchanged. CombinationEligibilityResult retains
the proposal and optional source, exact selected recipe decisions, accepted role
records, five prerequisite records, COMBINATION RuleTrace, deferred DAY/WEEK rules,
final status and complete evidence. Its stage is COMBINATION and its
plan_feasibility is always NOT_EVALUATED.

Pass original untrusted JSON through validate_contract_json before using it as
proposal data. This catches duplicate keys and malformed structures, but grants
no authority. The backend must independently select knowledge, context, candidates
and trusted_combination. Do not populate those trusted positions from request
fields merely because their DTO validation or content hashes succeed.

### Trusted-source responsibilities and Member 1 handoff

Member 1 / the independently trusted loader must provide:

1. Exact recipe and candidate snapshot IDs, content versions and digests in the
   agreed catalogue/graph release. Each repeated occurrence references its actual
   accepted snapshot; display labels never select or merge recipes.
2. Preparation identities, versions and basis evidence scoped to each exact
   recipe snapshot. A raw/cooked preparation cannot be transplanted to another
   candidate or silently interchanged with a different basis.
3. Recipe/preparation-specific portion definitions and their source evidence.
   FIXED source snapshots must name the exact configuration and component amounts,
   units, preparations and portion/basis references. The evaluator verifies exact
   declaration binding; it does not fetch portion-definition content, validate
   density, authenticate evidence locators or calculate nutrition.
4. Explicit contextual role assignments with exact accepted graph references and
   evidenced whole-composition observations. Pairwise graph edges or matching
   labels alone do not prove the two registered combination facts.
5. A complete independently selected source CombinationFacts matching the proposal's
   semantic content, including context and KB pins. An unknown, missing or unreviewed
   source must be omitted, not relabeled trusted. Missing source authority yields
   UNKNOWN even when every selected rule is NOT_APPLICABLE.

Member 3 / backend orchestration owns normalized profile/context, authenticated
source selection and release freshness/revocation, original-JSON ingress, resource
bounds, transport errors and persistence. Member 2 owns deterministic rule decisions.
Evidence IDs/versions must retain consistent metadata across every supplied input.
Hashes provide replay/integrity binding within independently selected releases;
they are not signatures or verification that a source's underlying claim is true.

There is no Member 1 production provider in this slice. Final provider contracts,
catalogue/role/template mapping, preparation/portion authority and reviewer/revocation
workflow require team approval. No proposed provider is presented as implemented.

### Worked decision cases

The following cases use fictional rules EQ True for roles/composition and established
recipe/profile prerequisites. They are executable cases in the independent evaluator
tests; no clinical meaning or source approval is implied.

| Case | Exact conditions | Overall result |
|---|---|---|
| Eligible | Exact accepted candidates/releases/source, complete composition, trusted True observations, applicable rules and recipe/profile PASS | PASS |
| Ineligible | Same trusted boundary, but roles observation False against applicable EQ True | FAIL |
| Unknown authority | Positive proposal with matching integrity but trusted_combination omitted | UNKNOWN |
| Unknown fact | Trusted source present but required roles observation missing/null/incomplete | UNKNOWN |
| Missing membership | A referenced recipe snapshot is absent from the accepted pool | UNKNOWN, unless a known hard FAIL dominates |
| Conflicting inputs | Referenced recipe revision, preparation, source snapshot or release conflicts | ValidationError; no partial decision |
| Unassigned | Eligible case with every quantity absent and no configuration | PASS for quantity-independent eligibility; portions explicitly unevaluated |
| Fixed | Eligible case with all quantities and the exact independently trusted configuration | PASS for this stage; nutrition and plan feasibility still unevaluated |
| No mandatory COMBINATION checks | Accepted catalogue selects zero such checks | UNKNOWN |
| All selected checks NOT_APPLICABLE | Nonempty mandatory set, evidenced false applicability, complete authority and all prerequisites established | PASS for resolved coverage; predicate statuses remain UNKNOWN |

The last two cases are deliberately distinct and preserve Phase 1-3 aggregation.
No predicate UNKNOWN is converted to predicate PASS. Known applicable FAIL dominates
other unresolved checks. No known FAIL stops evaluation of remaining mandatory rules.

A production orchestrator's call uses inputs it has already independently selected:

```python
result = evaluate_combination(
    proposal,
    candidates=accepted_candidates,
    knowledge=selected_kb,
    context=normalized_context,
    trusted_combination=selected_source,  # None when authority is unavailable
)
if is_candidate_eligible(result.status):
    safe_combination_id = result.combination.combination_id
else:
    # FAIL and UNKNOWN are both excluded; retain prerequisites/trace for explanation.
    excluded_status = result.status
```

The names above denote existing DTO inputs, not a new provider API. Reproducible
synthetic examples are `test_literal_combination_truth_table`,
`test_self_consistent_hash_and_positive_proposal_never_supply_authority` and
`test_separately_deserialized_upstream_dtos_and_repeated_evaluation`.

### Verified boundary hardening and audit finding

The review confirmed **P4-AUDIT-01 / MEDIUM** in computed-result validation, not in
the public evaluator. A valid trusted False roles observation against applicable
EQ True correctly produced FAIL through evaluate_combination. Editing only the
serialized rule outcome and overall status to PASS was nevertheless accepted by
validate_contract_json(CombinationEligibilityResult, ...). The same issue permitted
incorrect resolved FAIL labels, and also affected NE. Four independent pre-fix
regressions all failed because the corrupted DTO was accepted.

The local result validator now checks that each resolved applicable outcome agrees
with its retained boolean observation and registered EQ/NE predicate. Source binding,
type/completeness and operator policy checks still precede this check. All four
reproductions reject after correction. Phase 1 RuleEvaluation remains a declaration
contract, and Phase 3 semantics and all public signatures remain unchanged. No new
policy or authentication claim is introduced. Serialized results remain evidence
records: consumers must use the evaluator with trusted selections, not authorize an
externally rewritten result merely because it validates.

Twelve targeted cases close actual gaps: four result-label regressions; separate
original-JSON DTO ingress and repeated byte-identical results for UNASSIGNED/FIXED;
cross-candidate preparation and quantity transplants; a rehashed serialized portion
evidence swap whose local quantity bindings are still structurally valid; both
portion states under PLANNED_SWAP with preserved DAY/WEEK obligations; and exact
Phase 3 decision/manifest equality before and after combination evaluation. Existing
coverage already checks other version/digest, missing/conflicting provenance,
multiple-rule ordering, zero-check, NOT_APPLICABLE, hostile input and false-PASS cases;
those tests are retained rather than duplicated.

### Later nutrition/CSP integration: guidance, not implemented functionality

Combination PASS can feed ranking of eligible IDs. It does not establish nutrition
totals, daily/weekly feasibility, a valid swap or production clinical clearance.
Downstream code must retain the exact combination snapshot, occurrence multiplicity,
candidate references, preparations, context/KB pins, evidence and deferred rules.

For future nutrition aggregation, Member 1 must first provide verified per-reference
nutrition, recipe/preparation-specific portion definitions, completeness and conversion
sources. Preserve explicit g/mL/serving units and raw/cooked bases. Never interpret
unknown nutrition as zero or infer allergen absence/nutrient equivalence from ancestry.
Aggregate per occurrence; repeated recipes still contribute repeatedly.

For future CSP, UNASSIGNED PASS is only a portion-independent admission result.
Portion selection creates a new FIXED snapshot/configuration and digest. The current
evaluator requires independently established authority for that exact fixed snapshot;
copying an unassigned proposal and calling it trusted is not an integration path.
The team must approve how verified lower-level portion evidence establishes fixed
snapshot authority for solver-generated configurations. That source adapter is a
pending integration dependency, not implemented or implied by this handoff.

Future stages must enforce every retained DAY/WEEK obligation and applicable numeric
rule with verified nutrition/targets, and distinguish infeasibility from search limits.
Any context, release, component, preparation, quantity or evidence change requires
fresh binding and evaluation. Planned substitution must also preserve other slots
and validate affected daily/weekly constraints before persistence. None of that search,
aggregation, ranking, persistence, frontend or production-provider work is performed
here. Standalone craving continues to bypass composition/CSP.

### Approval requirements and recommended next phase

The synthetic contracts/evaluator are available for local integration. Production
adoption still requires joint approval of IDs/revisions, catalogue/role/template
mapping, preparation/basis and portion semantics, fixed-snapshot derivation authority,
public DTO/API transport, source authentication/revocation, reviewed clinical evidence,
resource limits and backend error handling. These external dependencies do not supply
fictional approvals or medical thresholds to this implementation.

Recommended next phase: agree and verify the Member 1/Member 3 data/source handoff,
then scope nutrition aggregation and a bounded portion/CSP vertical slice separately.
No later phase is implemented or automatically authorized by this recommendation.

### Prompt 3 final verification, scope and verdict

Final verification on 15 October 2026 used the existing project environment through
approved uv commands. No dependency installation or project lockfile change occurred.

| Required check | Final result |
|---|---|
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed; 109 files already formatted, including document Python examples |
| `uv run pyright` | Passed; 0 errors, 0 warnings |
| `uv run pytest -q` | **3,290 passed in 120.15 s**; all 3,278 baseline cases plus 12 targeted cases; no skips or failures |
| Architecture/imports | Full existing AST audit passes; no forbidden dependencies or local import cycles |
| Cross-phase behavior | All Phase 1-3 regressions pass; new integration case preserves exact recipe/profile decisions and deferred obligations |
| Start/end file fingerprints | 170 tracked/existing Phase 4 files compared; only the three authorized files below changed; no files removed or dependencies changed |
| Git/whitespace | Index empty, no whitespace errors, branch/HEAD unchanged; no unexpected files |

Prompt 3 modifies only `schemas/combination_evaluation.py`,
`tests/test_combination_evaluation.py` and this handoff document. It creates no files.
The evaluator implementation, six Prompt 1 DTOs, policy registries, Phase 1-3 files,
other members' code and dependencies are unchanged from the Prompt 2 start state.
The existing Prompt 1/2 working-tree files remain present. Existing datasets and
`phase1-security-fix.patch` were not modified, and no EDA notebook was executed.

The final independent review found one confirmed MEDIUM result-contract defect,
P4-AUDIT-01, now fixed and independently regression-tested. No unresolved in-scope
HIGH/MEDIUM defect or dependency prevents the synthetic foundation's completion
under the explicitly selected upstream-trusted boundary. Missing production
authentication/provider approval still prevents production readiness and must
remain explicit; no DTO or digest creates it automatically.

Verdict: **PHASE 4 SYNTHETIC FOUNDATION COMPLETE**. This verdict covers only the
implemented synthetic contracts, admission, deterministic eligibility and documented
integration boundary. Production providers and the later nutrition/CSP stages are
not completed or approved by this verdict.

Git branch: `feature/member2-combination-constraints`. HEAD remains
`c077b9af3bdd8f7a48322e27833e37c607d115b1`. No staging, commit, push, merge, rebase or
pull request was performed.
