# Member 2 Phase 2: food graph, taxonomy and versioned Knowledge Base

Status: Phase 2 local integration complete for review, 14 October 2026. All names, fields, enums,
ID syntax and qualifier policies below are provisional proposals pending joint team
approval. This implementation covers Tasks 2.1-2.6. It does not approve a
production KB or rename Phase 1 public contracts. The separately committed Phase 1
enum-validation correction is included; see the final Task 2.6 section.

## Architecture review

Reviewed AGENTS.md, relevant ARCHITECTURE.md sections, Member 2 Phase 1 decisions,
existing schemas/tests, and Sections 3, 4, 6, 16 and 17 of the accessible local
`C:/Users/venka/Downloads/Savora_GC1_Architecture_Team_Contract.pdf`.
The PDF describes an October 2026 proposed implementation contract for team approval.
Its requested sections agree with the five relations, Member 2 graph ownership,
validated inputs and unknown-safety boundary needed here. No blocking conflict affects
this slice. The PDF's cuisine policy vocabulary and future API names differ from
ARCHITECTURE.md; those interfaces are outside this implementation and remain unresolved.

The user explicitly requested keeping `feature/member2-knowledge-graph` despite the
repository's `feat/` prefix convention. No branch rename or Phase 2 commit/push is authorized.

## Implemented models and enums

`schemas/food_graph.py` reuses Phase 1 `EvidenceReference`, `RuleEnvironment` and the
existing strict/frozen contract foundation. Nested collections are tuples; extra
fields are forbidden; Python inputs retain strict enum/container requirements;
JSON uses camelCase aliases, enum tokens and arrays via `model_validate_json`.

- `FoodEntity`: opaque ID, content version, kind, canonical name, aliases, optional
  catalogue reference and nonempty evidence. Reference kinds require a catalogue ID.
- `FoodEntityKind`: INGREDIENT, RECIPE_REFERENCE, CULINARY_ROLE_REFERENCE,
  CUISINE_REFERENCE. Role/cuisine nodes are identity-only catalogue references,
  separate from taxonomy concepts and Member 1 recipe/tagging schemas.
- `FoodRelation`: ID/version, type, source/target IDs, assertion, qualifiers, evidence.
- `RelationQualifiers`: optional cuisine reference, role reference and meal type
  (BREAKFAST/LUNCH/DINNER). These remain exact context keys, not applicability rules.
- `KnowledgeCoverage`: ID/version, graph/catalogue release bindings, subject,
  relation type, qualifiers, explicit completeness, reason and gap/source evidence.
  This initial type describes outgoing relations only, not a rule-check catalogue.
- `FoodGraphSnapshot`: supported schema/policy versions, graph ID/version,
  catalogue version, declared environment, entities, relations, coverage, evidence,
  optional taxonomy release version, taxonomy terms and assignments.
- `RelationResolution`: graph/catalogue/policy versions, environment, exact query,
  traversal, status, full direct relation or ordered origin witness path, optional
  scoped coverage, evidence, reason code and limit flag. It is not eligibility.
- `FoodRelationType`: CONTAINS, DERIVED_FROM, HAS_CULINARY_ROLE, COMPATIBLE_WITH,
  FUNCTIONAL_SUBSTITUTE_FOR.
- `RelationAssertion`: PRESENT / ABSENT.
- `RelationResolutionStatus`: SUPPORTED / VERIFIED_ABSENT / UNKNOWN.
- `TraversalMode`: DIRECT / ORIGIN_PATH. Existing enum meanings are unchanged.

New graph IDs use case-sensitive ASCII strings of 1-128 characters matching
`^[A-Za-z0-9][A-Za-z0-9._:-]*$`. Names/aliases never become IDs or cause entity merging.
Phase 1 identity validation is unchanged. Each snapshot contains one version per
entity/relation/coverage identity. Repeated equivalent assertions must combine
their supporting evidence into one relation rather than introduce duplicate edges.
Graph version, catalogue version and record versions are separate opaque release
identifiers; their values need not equal each other. Coverage must bind exactly to
its graph and catalogue release. Supported schema is `food-graph.v1`; direct
edge-assertion semantics are `food-graph-direct.v1`. This source policy token remains
unchanged because an origin query traverses stored direct assertions rather than
creating a new assertion or changing snapshot content.

## Adversarial validation fixes

Graph enum fields require actual declared enum singleton members. A matching class
or token alone is insufficient: an unchecked Python caller can use `str.__new__`
and assign enum metadata to fabricate an instance that Pydantic's strict enum
validation accepts. Such objects previously bypassed identity-based endpoint and
cycle checks, allowed undeclared relation/traversal tokens, and produced affirmative
results that could fail JSON revalidation.

Graph-scoped `Annotated` enum types now apply an identity-membership validator after
Pydantic's enum parsing. It checks declared members by identity and rejects forged
instances with either unsupported or legitimate-looking tokens. It does not convert
them to canonical members. Entity kinds, relation types, assertions, resolution
statuses, traversal modes and snapshot/result environments use these annotations.
The public query uses the same relation/traversal annotations. Evidence environment
members are also checked within graph validation, without changing Phase 1 schemas.
JSON's valid string tokens still decode to their genuine canonical members.

Public resolution still recursively flattens unchecked nested copies/constructs
before validation, preserving the original enum instances for these checks. No
unchecked object is serialized or normalized to hide invalid enum identities.
The existing identity-based semantic checks remain in place.

Every non-null catalogue binding must be unique within a snapshot by
`(snapshot.catalogue_version, entity.kind, entity.catalogue_reference)`. This covers
recipe, cuisine and role references, plus ingredients with an optional reference.
Different graph IDs or different entity content versions cannot claim the same
catalogue object in the same release. Otherwise opposite assertions could be hidden
under duplicate graph IDs or duplicate qualifier-context IDs. Duplicate bindings
raise a validation error; no merging, alias lookup or canonicalization is introduced.

Kinds provide distinct catalogue identity namespaces. Separate snapshots may reuse
bindings for different catalogue releases. Repeated display names are allowed when
canonical IDs and catalogue identities are distinct. Coverage must still match its
exact graph/catalogue release; these fixes do not relax existing version checks.

These invariants establish structural consistency only. They do not authenticate
sources, prove catalogue membership, verify negative assertions in the real world,
or authorize production use. Production resolution remains deferred to Member 3's
authenticated loading and Member 1's authoritative catalogue alignment.

## Public relation API

```python
resolve_food_relations(
    snapshot: FoodGraphSnapshot,
    *,
    source_id: str,
    target_id: str,
    relation_type: FoodRelationType,
    qualifiers: RelationQualifiers | None = None,
    traversal: TraversalMode = TraversalMode.DIRECT,
    max_hops: int = 8,
    max_visited: int = 256,
) -> RelationResolution
```

The input deliberately uses `FoodGraphSnapshot`, not an incomplete
`KnowledgeBaseSnapshot`. No KB release loader, backend or database access is present.
Omitting qualifiers means an empty qualifier set, not a wildcard. Exact matching
includes direction, type and every qualifier, including explicit absent context.
Both limits must be strictly positive integers; booleans, floats, strings and null
are rejected, including on DIRECT queries. Valid limits affect ORIGIN_PATH only;
DIRECT retains its existing exact-assertion behavior.

The public boundary recursively flattens every nested contract instance using
Phase 1's existing `_validation_payload` helper, then strictly validates the complete
query/snapshot. It preserves unexpected fields in unchecked `model_copy` updates,
strict container/enum types and missing fields from `model_construct`. Cyclic or
excessively deep unchecked payloads produce `ValidationError`, not UNKNOWN.
The reuse of this private shared helper is intentional for this small slice; a
future shared-foundation extraction requires separate review.

Malformed declarations/queries, dangling endpoints, incompatible endpoint kinds,
unsupported qualifiers, duplicate identities/assertions and conflicting evidence
invalidate input. Valid but missing caller IDs or missing exact edges produce
UNKNOWN. Missing IDs never create placeholder entities. A supported assertion
returns its full relation identity/version and original provenance; evidence output
is sorted by identity/version in both top-level output and embedded relation/coverage
records for stable presentation. Entity/edge/evidence order does not affect results.

## Task 2.3: bounded origin traversal

ORIGIN_PATH is supported only for DERIVED_FROM between ingredient entities. It
follows positive directed DERIVED_FROM edges, never negative assertions, reversed
edges, CONTAINS, compatibility or substitution edges. A shortest positive witness
returns SUPPORTED. This is origin reachability, not an independently asserted new
direct relationship, dietary classification, retained allergen content or safety.
Processing can change composition; ancestry alone cannot verify allergen retention.

Breadth-first search uses a FIFO queue. Each adjacency list is sorted by relation
ID. Equal-length witnesses are selected by lexicographic relation-ID sequence,
not by entity names, insertion order or the final edge alone. Entities are marked
visited when discovered, with one parent edge each. Converging paths cannot spend
the budget twice on the same entity. A source-equals-target query is UNKNOWN:
zero-hop identity is not a positive origin witness, and positive cycles are invalid.

`max_hops` is the inclusive maximum witness length. `max_visited` counts distinct
discovered entities, including source and target. Defaults are 8 and 256. The
visited budget is checked before accepting a new target. It measures the whole
search, so earlier sorted sibling discoveries can consume it before a short path
is found. A supported witness does not require exhaustively exploring all paths.

The limit flag is true only when a bound blocks eligible exploration, not simply
because a counter equals its bound. The visited limit stops the search immediately
when another entity cannot be discovered. Hop-limited branches are skipped while
other queued branches are checked; an unresolved search then reports the hop limit.
If visited exhaustion occurs after hop-blocked branches, MAX_VISITED_REACHED records
the immediate stopping cause. Neither limit establishes absence.

The existing result DTO adds immutable `path`, `limit_reached` and `reason_code`
fields. For ORIGIN_PATH, `relation` is always null and `path` contains the selected
FoodRelation records in source-to-target order. Each record preserves relation ID,
version and source evidence. Exact IDs are available as `path[i].relation_id` or
JSON `path[i].relationId`. Top-level evidence is the deduplicated, identity/version
sorted union of that path's evidence only; unused and negative edges are excluded.
Graph, catalogue and source-policy versions remain attached to the result.

Result validation rejects disconnected, cyclic, negative, mixed-type or incorrectly
terminated witnesses, evidence omissions, fabricated direct assertions, unsupported
mode/type pairs and contradictory status/reason/limit metadata. Canonical enum and
full recursive snapshot validation occur before search. Input snapshots are immutable
and are never modified. Unknown results carry no partial witness path.

| Reason code | Status | Limit reached |
|---|---|---|
| DIRECT_SUPPORTED | SUPPORTED | false |
| DIRECT_VERIFIED_ABSENT | VERIFIED_ABSENT | false |
| NO_DIRECT_ASSERTION | UNKNOWN | false |
| MISSING_ENTITY | UNKNOWN | false |
| ORIGIN_PATH_SUPPORTED | SUPPORTED | false |
| NO_ORIGIN_PATH | UNKNOWN | false |
| MAX_HOPS_REACHED | UNKNOWN | true |
| MAX_VISITED_REACHED | UNKNOWN | true |

The public resolver always supplies a reason code. Standalone legacy DIRECT DTO
payloads may omit it; ORIGIN_PATH DTOs require a consistent code. A negative direct
assertion can coexist with an indirect positive path: DIRECT resolves that negative
assertion, while ORIGIN_PATH can return its separate positive witness. A negative
direct assertion alone returns UNKNOWN for origin traversal, never VERIFIED_ABSENT.

For V entities, E relations and P evidence references, complete snapshot validation
is linear in records/references (plus coverage). Building the derivation adjacency
index takes O(E); sorting takes O(sum(d_v log d_v)), at most O(E log E). BFS takes
O(V_reached + E_scanned), with O(min(V, max_visited)) queue/visited/parent storage in
addition to the O(E) index. Witness reconstruction is O(path length); returning its
evidence also sorts the selected references. Limits bound depth and discovery count;
validation and indexing still inspect the complete snapshot. No dependencies, cache,
mutable module-level graph data or generic inference engine are introduced.

## Relationship policy

| Relation | Allowed source -> target | Qualifiers |
|---|---|---|
| CONTAINS | Recipe reference or ingredient -> ingredient | None |
| DERIVED_FROM | Ingredient -> ingredient | None |
| HAS_CULINARY_ROLE | Recipe reference or ingredient -> role reference | Cuisine, meal type |
| COMPATIBLE_WITH | Recipe reference or ingredient -> recipe reference or ingredient | Cuisine, meal type, role |
| FUNCTIONAL_SUBSTITUTE_FOR | Replacement food -> replaced food | Role required; cuisine/meal type optional |

Snapshot qualifier IDs must reference nodes of the correct kind. A caller's
unknown context key cannot match an edge and remains UNKNOWN. Direct queries of
known endpoints with incompatible kinds are validation errors.

DIRECT performs no implicit reverse edge, symmetry, transitive closure, dietary inheritance,
clinical inference or mixed-relation propagation is performed. Self-relations and
positive cycles within CONTAINS or DERIVED_FROM are rejected. Explicit reciprocal
compatibility/substitution assertions may exist, with independent source evidence.
The iterative structural cycle check does not resolve indirect facts.

DERIVED_FROM describes origin only. Processing-specific allergen retention cannot
be established by ancestry alone. Compatibility and functional substitution do not
establish allergy safety, nutrition equivalence or candidate eligibility. These
results do not construct `FactObservation`, `RuleEvaluation` or `RuleTrace` objects.

## UNKNOWN, coverage and verified absence

DIRECT SUPPORTED requires an explicit PRESENT assertion for the exact query.
ORIGIN_PATH SUPPORTED requires its positive derivation witness. VERIFIED_ABSENT is
limited to DIRECT and requires an explicit evidenced ABSENT assertion for that exact
directed qualified query. The term refers to consistency of supplied evidence,
not independently authenticated source truth, allergen absence, cross-contact
absence or medical suitability. UNKNOWN carries no resolved assertion.

Coverage is a scoped declaration, not proof of global knowledge completeness.
No coverage record means coverage is undeclared. Explicit `complete=False` and
its evidence preserve a known gap. Even `complete=True` never generates a negative
assertion from a missing edge. Partial coverage may coexist with a known positive
or negative edge. Relevant coverage is returned separately from the assertion.

## Provenance and environment boundary

Every entity, relation, coverage declaration and snapshot requires nonempty
`EvidenceReference` provenance. Duplicate identities within one evidence tuple are
rejected. Across the complete snapshot, identical `(evidence_id, version)` reuse
is allowed only with identical source, locator and environment. Different evidence
versions can carry revised metadata. All evidence must match snapshot environment.

Schemas can represent structurally consistent SYNTHETIC/PRODUCTION declarations.
This first public resolver deliberately accepts SYNTHETIC snapshots only. Production
resolution awaits authenticated backend loading and approved release/source checks.
Environment labels, source strings and versions are not authority credentials.

All usable test fixtures declare SYNTHETIC provenance. Invalid metadata variants
exercise attempted production relabelling; they are not production examples or
real approvals. No clinical thresholds, nutrition values or dietary advice are supplied.

## Task 2.4: cuisine and dietary taxonomy

The public API is resolve_taxonomy_assignment, following the requested name and
existing resolve_food_relations convention. It lives in core/reasoning/taxonomy.py;
the existing relation resolver is unchanged.

### DTOs, identities and ownership

TaxonomyKind supports CUISINE, DIETARY_PATTERN, DIETARY_CATEGORY and CULINARY_ROLE.
TaxonomyAssignmentAssertion supports PRESENT and ABSENT. TaxonomyTraversalMode adds
DIRECT and CUISINE_PARENTS separately from existing relationship traversal modes.

TaxonomyTerm declares term_id, version, explicit kind, nonblank display_label,
immutable parent_ids and evidence. Its evidence backs its definition and every
declared parent link in that term version. Multiple same-kind parents are allowed.
TaxonomyAssignment declares assignment_id, version, subject_id, term_id, explicit
assertion and evidence. Subjects must be existing ingredients or recipe references.

FoodGraphSnapshot adds taxonomy_version, taxonomy_terms and taxonomy_assignments.
Empty tuples and a null taxonomy version preserve legacy graph inputs. Any taxonomy
records require an explicit nonblank release version. One term/assignment version per
identity is allowed per snapshot. Record versions and the containing graph/catalogue/
taxonomy releases are independent opaque identifiers. Resolution preserves each binding;
these declarations do not authenticate a release or its sources.

TaxonomyResolution carries those versions, taxonomy_policy_version=food-taxonomy.v1,
exact query IDs, the queried term, traversal, RelationResolutionStatus, selected
assignment, term path, negative conflicts, evidence, reason_code, reason and limit_reached.
SUPPORTED/VERIFIED_ABSENT/UNKNOWN are classification statuses, never RuleStatus.PASS/FAIL.

Term IDs and food entity IDs occupy distinct typed namespaces. Repeated labels are
allowed; labels never match subjects or merge terms. Taxonomy concepts do not replace
catalogue cuisine/role reference nodes or become relationship qualifier IDs automatically.
Member 1 must agree explicit taxonomy-to-catalogue mappings, recipe assignments,
cuisine/role vocabulary and source authority. These names remain provisional shared
proposals. The additive local food-graph.v1 schema has no new HTTP/TypeScript contract.

### Validation and evidence

Strict frozen DTOs, tuple collections and forbidden extras apply throughout. Snapshot
validation rejects duplicate term/assignment identities, duplicate/self parents,
dangling parents, mixed-kind parents, hierarchy cycles of every kind, dangling
assignment endpoints and duplicate or opposing exact subject/term assignments.
Equivalent assignments must combine evidence in one record.
Cuisine assignments additionally satisfy the complete ancestor consistency rule below.

Evidence is required for every supplied record. Graph, coverage, terms and assignments
share the same global (evidence_id, version) metadata-consistency check. Revised
evidence versions may coexist. Missing knowledge yields UNKNOWN; a malformed supplied
record missing evidence raises ValidationError, preserving Phase 1's fail-closed input
boundary rather than silently repairing invalid input.

The public resolver recursively revalidates the full snapshot before lookup, including
nested unchecked model_copy/model_construct objects, counterfeit legitimate enum tokens
and retained unexpected fields. Existing relation/origin queries validate the new records
too. Consistent production-labelled schemas are representable, but both resolvers remain
SYNTHETIC-only. No sources are fetched or treated as production authority.

### Classification, traversal and conflict policy

DIRECT resolves exact positive assignments as SUPPORTED and exact negatives as
VERIFIED_ABSENT. Missing assignments remain UNKNOWN. Coverage and missing records
never establish negative classification.

CUISINE_PARENTS first honors exact positive membership. Otherwise CUISINE targets
use bounded multi-source BFS from the food's positive cuisine assignments, child to
parent only. Other kinds honor exact assignments; missing assignments return UNKNOWN /
UNSUPPORTED_HIERARCHY. Non-cuisine parent links may be stored structurally but never
inherit membership. No parent-to-child, food-edge, origin-path or label inference occurs.

Shortest witnesses minimize parent-link count, then assignment_id, then the entire
parent-term-ID sequence. Sorted seeds and parent IDs make insertion order irrelevant.
Visited-on-discovery and predecessor links handle converging paths without duplicate
discovery or whole-path copying. Direct membership needs no path; hierarchy paths contain
the assigned child through the queried ancestor, with at least one parent link.

max_hops defaults to 8 and inclusively counts parent links. max_visited defaults to 256
and counts all distinct discovered terms, including every eligible seed and the target,
excluding the food subject. All seeds spend the shared budget before expansion.
Earlier sorted siblings may consume the budget. Limits require strict positive integers
even for DIRECT queries, but valid bounds affect hierarchy search only. limit_reached
means that exploration was blocked, not that a counter merely equalled its maximum.

For each food subject, snapshot validation groups all explicit PRESENT and ABSENT
cuisine assignments. Starting from every positively assigned cuisine, it computes
the complete upward ancestor closure, including the assigned terms themselves.
If that closure intersects any explicit ABSENT cuisine term for the same subject,
the entire snapshot raises ValidationError before a resolver can return a result.
Exact opposing assignments remain rejected by the existing subject/term uniqueness check.

Every declared cuisine parent route counts, including nonpreferred branches, longer
alternatives and routes from other positive seeds. A clean shortest witness cannot
hide an inconsistent alternative. This rule applies even to unrelated queries, DIRECT
queries and missing caller IDs; query hop/visited bounds cannot truncate validation.
Subject IDs, seed IDs and parent IDs are ordered deterministically, and a per-subject
discovered set visits each reachable term once. Subjects without both positive and
negative cuisine declarations need no closure intersection search. No quadratic table
of every term's ancestor set is stored.

This is a synthetic declaration consistency rule, not proof of real-world cuisine truth.
Evidence strings, hierarchy definitions and labels do not authenticate themselves.
Production use still requires curated sources, authoritative catalogue mappings and
authenticated release loading. The resolver remains SYNTHETIC-only. Missing records
never create negatives. Negatives outside the complete positive closure or belonging
to another subject remain valid. Dietary patterns/categories and culinary roles do not
propagate through their parents or participate in this cuisine-only rule.

If search exhausts without a witness, an exact queried negative may resolve as
DIRECT_VERIFIED_ABSENT. If a bound blocks search, it remains UNKNOWN even with that
negative: bounded exploration never manufactures a new negative classification.
Negative assignments never propagate negative membership to ancestors.

Direct evidence equals the exact assignment evidence. Supported hierarchy evidence is
the identity/version-sorted union of the selected positive assignment and every selected
term definition/link declaration. Queried term definitions are also returned separately.
No evidence is fabricated. Gap/limit UNKNOWN results carry no partial witness. The
existing selected-witness checks and HIERARCHY_CONFLICT DTO diagnostics remain as
defensive/legacy safeguards; accepted snapshots cannot produce those conflicts.

| Reason code | Status | Limit reached |
|---|---|---|
| DIRECT_SUPPORTED / HIERARCHY_SUPPORTED | SUPPORTED | false |
| DIRECT_VERIFIED_ABSENT | VERIFIED_ABSENT | false |
| HIERARCHY_CONFLICT (legacy standalone DTO / defensive safeguard) | UNKNOWN | false |
| MISSING_SUBJECT / MISSING_TERM | UNKNOWN | false |
| NO_ASSIGNMENT / NO_CUISINE_PATH / UNSUPPORTED_HIERARCHY | UNKNOWN | false |
| MAX_HOPS_REACHED / MAX_VISITED_REACHED | UNKNOWN | true |

Plant-derived rice and Animal-flesh chicken fixtures assert individual classifications.
They never establish Vegan, Vegetarian, halal, allergy-safe or clinical eligibility.
Complete authoritative safety facts and future rules remain necessary.

Full validation/indexing inspects food entities, relations, coverage, terms, assignments,
parent links and evidence. Search sorts seeds and parent lists, then scans reachable
terms/links with O(min(T,max_visited)) discovery storage. Limits bound traversal, not
total input-validation resources; authenticated loading must also bound snapshot sizes.
Complete cuisine consistency adds a walk per subject with both positive and negative
cuisine declarations, linear in that subject's reachable terms and parent links, plus
deterministic sorting. Per-subject discovery storage is O(T_reachable); it is independent
of resolver search limits and is discarded between subjects.

## Task 2.5: versioned Knowledge Base declarations

The new schema module is schemas/knowledge_base.py and the builder is
core/reasoning/kb.py. Separation keeps the existing graph, taxonomy and Phase 1
rule contracts unchanged. Names are provisional until joint team approval.
No rule, applicability, clinical or eligibility evaluation is implemented.

### Snapshot, references and release bindings

KnowledgeBaseSnapshot embeds exact existing RuleDefinition and RuleReference DTOs.
Its fields are kb_id, version, environment, graph_id, graph_version, catalogue_version,
taxonomy_version, check_catalogue_version, graph, rules, active_rules,
applicability_descriptors, check_catalogue, rule_catalogue_coverage, evidence and
content_digest. It also records fixed schema_version=knowledge-base.v1,
semantic_policy_version=knowledge-base-integrity.v1 and
workflow_policy_version=synthetic-workflow-scopes.v1.

KB graph ID/version, food catalogue version, optional taxonomy version and environment
must exactly match the embedded FoodGraphSnapshot. Check entries and coverage bind to
kb_id, kb_version and check_catalogue_version. Food catalogue and check-catalogue releases
are distinct. Record versions are independent opaque identifiers, not numerical ordering.

Each (rule_id, version) definition is unique. Archived DRAFT/RETIRED versions may
coexist. Every declared ACTIVE definition must appear in active_rules, and each
reference must resolve to that exact ACTIVE definition. Multiple simultaneously serving
versions of a rule_id are rejected. An ACTIVE clinical rule at any severity requires
explicit APPROVED metadata even in a synthetic KB; existing Phase 1 production
clinical provenance requirements also remain enforced. Synthetic approvals in tests
are fictional declarations and do not authorize production or supply clinical values.

### Synthetic expected-check policy

KnowledgeWorkflow supports WEEKLY_PLAN, CRAVING_DISCOVERY and PLANNED_SWAP.
The precise authoritative workflow/rule mapping is not approved by the team contract.
This implementation therefore fixes a clearly named synthetic policy only:

| Workflow | Required scope cells |
|---|---|
| WEEKLY_PLAN | PROFILE, RECIPE, COMBINATION, DAY, WEEK |
| CRAVING_DISCOVERY | PROFILE, RECIPE |
| PLANNED_SWAP | PROFILE, RECIPE, COMBINATION, DAY, WEEK |

Each required cell must exist, including empty cells. Its CheckCatalogueEntry contains
entry_id, version, KB/check-catalogue release bindings, workflow, scope, rule_references
and evidence. Its exact reference set must equal every ACTIVE ABSOLUTE definition of
that scope in the KB. A missing hard rule, stale reference, wrong scope, extra soft/
informational check or unsupported workflow/scope cell invalidates acceptance.

RuleCatalogueCoverage contains coverage_id, version, identical release/workflow/scope
bindings, explicit complete, reason and evidence. Every required cell needs one complete
coverage declaration. Missing, duplicate, unsupported or incomplete coverage fails
acceptance. Existing KnowledgeCoverage still means outgoing food relationships and
cannot be reused as check-catalogue coverage.

Soft/informational rules can be active inventory members but are never mandatory
hard checks. Applicability metadata cannot remove a required check. The scope matrix
does not execute clinical applicability or mean that daily/weekly limits apply to
standalone cravings. Phase 3 and the team must approve the final workflow policy.

### Applicability metadata

ApplicabilityDescriptor uses reference (the exact versioned applicability identity
named by RuleDefinition.applicability_reference), rule_references (the exact hosted
rule definitions), required_context_facts, dependencies and evidence. Descriptors
may be shared by archived/active rule versions. Dependency-only descriptors may
have no hosted rules. Dependencies reference other exact applicability descriptor
identities; dangling/stale/self/duplicate references and dependency cycles are rejected.
One descriptor version per applicability identity is supported per KB release.

Required context facts must be nonempty, unique names. No facts are observed here,
no predicate is executed and no APPLICABLE/NOT_APPLICABLE outcome is inferred.
Missing future context facts cannot silently remove a catalogue check; the eventual
Phase 3 evaluator must preserve UNKNOWN and the Phase 1 hard-status safeguards.

### Builder and content integrity

build_knowledge_snapshot(content, *, expected_digest=None,
expected_environment=None, expected_kb_id=None, expected_kb_version=None,
expected_graph_id=None, expected_graph_version=None, expected_catalogue_version=None,
expected_taxonomy_version=None, expected_check_catalogue_version=None)
returns an immutable KnowledgeBaseSnapshot.

content is a typed snapshot or strict Python field dictionary. Omit content_digest
only when asking the builder to compute it; supplying a digest requests verification.
A supplied null, malformed or mismatching digest is rejected, not silently repaired.
Native model_validate_json accepts normal camelCase JSON arrays/enum tokens and checks
the digest. JSON schema validation establishes structural consistency only; acceptance
and trusted release checks belong to the builder.

The builder recursively reads every nested DTO field mapping before validation,
retaining unexpected copied fields, container types and actual enum instances.
Canonical membership is checked for Phase 1 rule enums as well as graph/taxonomy/
workflow/environment enums. Copied/constructed malformed records and excessively
deep/cyclic unchecked payloads raise ValidationError. No Phase 1 models are duplicated.

All evidence across the complete KB, graph, taxonomy, outgoing coverage, rule definitions,
approval references, applicability descriptors and catalogue coverage is checked together.
A versioned evidence identity must retain identical source, locator and environment.
Every evidence and rule environment must match the KB. Revisions with distinct evidence
versions are permitted; provenance labels do not authenticate themselves.

The digest uses only the standard library. Every validated field, default, null, schema
and semantic-policy token is included except content_digest itself. Canonical JSON uses
camelCase keys, sorted object keys, recursively sorted collection elements, compact
separators, ASCII JSON escapes and UTF-8 bytes, then SHA-256 lowercase hexadecimal.
All stored collections are unordered declarations (including fact lists and IN/NOT_IN
sets); there are no witness paths in this snapshot. Scalars and their types remain
unchanged. No Unicode normalization, source rewriting or record dropping occurs.
This is a documented local canonical format, not a claim of RFC 8785 compliance.

Tuple/dictionary insertion order does not change the digest. Changing relevant graph,
rule, applicability, coverage or evidence content does. The returned DTO preserves
supplied tuple order; canonicalization applies to hashing rather than semantic field edits.
An independently supplied expected digest and pins are checked after full validation.

### Authority boundary and production gate

The caller must obtain expected digest/environment/version pins from an independently
trusted loader or approved release registry. Copying the supplied digest into the
expected_digest argument proves no source authenticity. Hashes detect changes relative
to an existing trusted release; they are not signatures or evidence-quality reviews.

Internal checks detect omitted inventory references and checks relative to definitions
inside this release. They cannot detect rules omitted from an entirely self-supplied KB
and its inventory/catalogue together. Even an internally complete empty synthetic
inventory produces no PASS/eligibility claim. Trusted external release selection remains
necessary.

Schemas can represent structurally consistent production-labelled declarations.
The builder requires a trusted expected digest, environment, KB ID/version, graph
ID/version and food/check-catalogue version pins for production, plus the taxonomy
version when present. Even matching production pins remain insufficient in this slice:
production serving is rejected pending an approved workflow/scope policy and authenticated
loading. The synthetic workflow policy is never presented as production authority.

Member 1 must align canonical food IDs, catalogue/portion versions, fact names, units
and taxonomy mappings. Member 3 must supply authenticated releases and trusted pins,
translate validation failures and assemble workflow/scope manifests from the accepted
catalogue, not received evaluations. AI core performs no database or backend I/O.
Phase 3 must implement applicability and predicate execution, context completeness,
candidate filtering and reason traces without weakening Phase 1 UNKNOWN handling.

## Remaining team alignment and handoffs

- Member 1: agree canonical IDs/catalogue versions, preparation identity, authoritative
  recipe references, taxonomy-to-catalogue mappings, cuisine/role vocabulary,
  evidenced classification assignments and contextual compatibility sources.
- Member 3: load authoritative records in backend orchestration; agree context IDs,
  source verification, release authentication and error translation. AI never queries
  Supabase/PostgreSQL or owns transactions.
- Members 1/2/3: approve these provisional DTO names, identity rules and semantics.
- Remaining alignment: authoritative graph/taxonomy/KB releases, an approved production
  workflow/scope policy, authenticated release loading, trusted pins and approved
  expected-check catalogue construction. Metadata is implemented; execution is deferred.
- Full predicate execution, candidate filtering, composition, ranking and CSP remain
  outside this implementation. Phase 1 exports and public fields are unchanged.
- No HTTP endpoint or shared TypeScript contract is introduced. If exposed later,
  FastAPI remains the authoritative wire-schema owner and OpenAPI generation applies.

## Task 2.3 verification history

Executed on 13 October 2026 with `UV_NO_SYNC=1` to use existing dependencies without
installing packages or changing the lockfile:

| Check | Result |
|---|---|
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed; 84 files already formatted |
| `uv run pyright` | Passed; 0 errors, 0 warnings |
| `uv run pytest -q` | 582 passed |
| `uv run pytest -q apps/ai_system/tests/test_knowledge_contracts.py` | 255 passed |
| `uv run pytest -q apps/ai_system/tests/test_food_graph.py` | 325 passed |

The graph suite has 83 test functions yielding 325 cases. Task 2.3 adds 25 functions
and 109 cases to the 216-case adversarially hardened baseline. The original 980-line
test prefix is byte-for-byte unchanged. The suite covers
direct relation assertions, direction/context isolation, unknown entities/edges,
coverage, structural integrity, source/environment conflicts, immutable DTOs,
JSON round trips, deterministic output and unchecked-copy/construct exploits,
including canonical enum membership at every graph field/query boundary and
unique catalogue bindings across reference kinds and entity content versions.
Origin tests cover one/two/three-hop paths, negative and mixed edges, deterministic
shortest witnesses, converging paths, exact budget boundaries, false absence claims,
invalid snapshots/limits/modes, counterfeit enums, immutable inputs and versioned
JSON witnesses. An independent path enumerator checks all 64 forward-edge subsets
of a fixed four-node topological order, with 3,072 source/target/hop-limit queries.
Final static checks and all tests pass without warnings. Phase 1's 255 tests pass
and its source files remain unchanged.

The original attacks were rerun before and after the fixes. Fabricated undeclared
relation types and counterfeit DERIVED_FROM members previously returned SUPPORTED,
including an invalid recipe source and a positive cycle. Duplicate recipe references
previously returned opposite positive/negative containment results for one catalogue
object. After the fixes these inputs raise clear ValidationError exceptions. Forged
positive/negative relation assertions and DIRECT/ORIGIN_PATH traversal instances
are rejected; genuine canonical inputs retain SUPPORTED and VERIFIED_ABSENT.

The final Git whitespace checks include `git diff --check` and separate no-index
checks of the four new untracked files. No frontend or HTTP contracts changed,
so frontend checks and contract regeneration were not run for this AI-only slice.

## Task 2.4 initial verification history

Executed locally on 13 October 2026 with existing dependencies (UV_NO_SYNC=1):

| Check | Result |
|---|---|
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed; 86 files already formatted |
| `uv run pyright` | Passed; 0 errors, 0 warnings |
| `uv run pytest -q` | 803 passed |

Task 2.4 adds 59 taxonomy test functions yielding 219 cases, plus two origin-result
regression tests closing the LOW review finding. The graph suite now has 327 cases;
all 255 Phase 1 cases remain passing. No Phase 1 source/export, origin resolver or
dependency/lockfile changes were made. The original graph test cases are preserved.

Synthetic taxonomy tests cover all four kinds, strict DTOs and evidence, release
bindings, duplicate/contradictory identities, parent/reference integrity, every-kind
cycles, environments, direct positive/negative classification, upward cuisine paths,
prohibited reverse/dietary/food-edge inference, conflict witnesses, exact traversal
limits, canonical/fabricated enums, unchecked copies/constructs, forbidden fields,
immutable inputs, witness validation, evidence sorting and JSON round trips.
The suite enumerates every path across all 64 edge subsets of a four-term DAG,
checking 3,072 source/target/hop combinations against cuisine traversal.

A separate in-memory adversarial script, using its own synthetic fixtures and
exhaustive-path reference, checked 6,648 multi-source queries across 100 generated
DAGs, including negative assignments and search bounds. All matched. Another 200
complete-result ordering checks and 11 counterfeit enum checks passed.

Whitespace checks cover tracked changes and all six untracked graph/taxonomy source,
test and documentation files. Existing datasets and EDA notebooks were not modified
or rerun. The branch remains feature/member2-knowledge-graph; no staging, commit,
push or PR is authorized. Production authority and team approval remain deferred.

## Task 2.4 HIGH conflict correction verification

The original review attack was confirmed before editing: a positive seed with two
routes to the target, and a negative on the nonpreferred branch, returned SUPPORTED
with no conflict evidence. After complete snapshot consistency validation was added,
the same declaration raises ValidationError for contradictory cuisine ancestry.

This correction modifies only food_graph.py, taxonomy.py, test_food_taxonomy.py and
this document. No DTO fields or public signatures changed. Resolver witness checks
remain defensive. Previously accepted contradictory fixtures now expect validation
errors; the standalone legacy conflict DTO guards retain their regression coverage.
Phase 1 files, test_food_graph.py, the origin resolver, dependencies and datasets
remain unchanged. No additional packages or Task 2.5 implementation were introduced.

| Check | Result |
|---|---|
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed; 86 files already formatted |
| `uv run pyright` | Passed; 0 errors, 0 warnings |
| `uv run pytest -q` | 827 passed |

There are 24 additional pytest cases: 11 new functions yielding 18 cases, plus six
extra cases from expanded existing regressions. The taxonomy suite now has 70 test
functions / 243 cases. The graph and Phase 1 suites remain 327 and 255 cases.
Coverage includes either diamond branch, longer alternatives, other positive seeds,
opaque-ID renaming, 192 insertion-order combinations with identical conflict errors,
valid multiple parents and outside negatives, subject isolation, non-cuisine exclusion,
query-bound independence, nested unchecked copies/constructs, JSON and a 1,100-term
alternative chain. Existing enum, identity, version and provenance tests remain passing.

Both a repository test and a separate in-memory path enumerator checked all 64
four-term DAG edge subsets and all 81 positive/negative/missing assignment patterns:
5,184 snapshots. All 1,415 contradictions were rejected; all 3,769 consistent snapshots
were accepted. No accepted snapshot had a negative in its positive ancestor closure.
The standalone reference also matched 15,076 accepted-snapshot classification queries
and rejected 12 unchecked public-boundary variants of the original attack.

Tracked and untracked whitespace checks pass. The branch remains
feature/member2-knowledge-graph, with no staging, commit, push or PR.

## Task 2.5 verification

Implemented locally on 13 October 2026 with existing dependencies (UV_NO_SYNC=1).
Created schemas/knowledge_base.py, core/reasoning/kb.py and test_knowledge_base.py;
updated this document. Phase 1 and earlier graph/taxonomy sources, tests, dependency
files and datasets remain unchanged. No Phase 3 execution or backend I/O was added.

| Check | Result |
|---|---|
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed; 89 files already formatted |
| `uv run pyright` | Passed; 0 errors, 0 warnings |
| `uv run pytest -q` | 1,030 passed |

The new suite has 39 test functions / 203 cases. All prior 827 cases remain passing,
including 255 Phase 1, 327 graph and 243 taxonomy cases. New cases cover inventory
omissions, workflow/scope completeness, explicit coverage, exact active/archived
references, clinical approval gates, applicability dependency integrity, forged Phase 1
and Phase 2 enums, recursive copied/constructed defects, unexpected fields, environments,
pins, digest tampering, native JSON round trips and frozen DTOs. Graph origin and cuisine
resolution still work with the accepted graph component.

An independent textual canonical encoder agrees with the production SHA-256 digest.
Record-order permutations, nested collection reversals and fact-set reversals preserve
the digest. Mutations in graph, taxonomy, rules, applicability, catalogue, coverage and
evidence change it; independently pinned old digests reject changed releases.

A separate standalone synthetic audit tested all 8,256 omission subsets across hard
workflow entries, ACTIVE inventory and required coverage. All 8,253 incomplete subsets
were rejected; only the three complete inventories passed. Another 720 rule-order and
catalogue-reversal checks, two trusted-digest tampering checks and JSON round trips passed.
Trusted pins remain external inputs; these tests do not authenticate real sources.

Tracked and untracked whitespace checks pass. Branch feature/member2-knowledge-graph
is unchanged. No staging, commit, push, PR, dataset processing or EDA rerun occurred.
Production serving remains deliberately blocked pending policy approval and authenticated
loading; it is not made ready by successful structural/digest tests.

## Task 2.6: final Phase 2 integration and handoff

Completed locally on 14 October 2026. Tasks 2.1-2.6 provide strict frozen graph,
taxonomy and KB declarations; exact directed/qualified assertions; bounded positive
DERIVED_FROM origin search; conservative cuisine ancestry; direct dietary/role
classification; and versioned active-rule, applicability, catalogue, coverage and
digest validation. Existing Phase 1 types are reused. This is a synthetic integration
handoff, not production or clinical approval.

The Phase 1 counterfeit-enum correction is already committed as f610881 on the
Phase 1 branch and cherry-picked as a58f723 here. The three Phase 1 files have identical
content at those commits. They are excluded from the proposed Phase 2 commit.
The previous LOW approval-integrity coverage gap is closed by seven KB cases for
global approval evidence conflicts, isolated approver/source/version digest changes,
old trusted digest rejection and valid approval metadata.

### Public interfaces

These are the actual module imports. Phase 2 models are imported from
savora_ai.schemas.food_graph and savora_ai.schemas.knowledge_base. They are not
re-exported by the legacy savora_ai.schemas package. Existing Phase 1 exports
remain available. No package export changes or HTTP contracts are needed
for these Python module APIs.

~~~python
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.graph import resolve_food_relations
from savora_ai.core.reasoning.taxonomy import resolve_taxonomy_assignment
from savora_ai.schemas.reasoning import aggregate_hard_status
~~~

Exact source signatures, using their schema type names:

~~~python
def build_knowledge_snapshot(
    content: KnowledgeBaseSnapshot | dict[str, object],
    *,
    expected_digest: str | None = None,
    expected_environment: RuleEnvironment | None = None,
    expected_kb_id: str | None = None,
    expected_kb_version: str | None = None,
    expected_graph_id: str | None = None,
    expected_graph_version: str | None = None,
    expected_catalogue_version: str | None = None,
    expected_taxonomy_version: str | None = None,
    expected_check_catalogue_version: str | None = None,
) -> KnowledgeBaseSnapshot: ...


def resolve_food_relations(
    snapshot: FoodGraphSnapshot,
    *,
    source_id: str,
    target_id: str,
    relation_type: FoodRelationType,
    qualifiers: RelationQualifiers | None = None,
    traversal: TraversalMode = TraversalMode.DIRECT,
    max_hops: int = 8,
    max_visited: int = 256,
) -> RelationResolution: ...


def resolve_taxonomy_assignment(
    snapshot: FoodGraphSnapshot,
    *,
    subject_id: str,
    term_id: str,
    traversal: TaxonomyTraversalMode = TaxonomyTraversalMode.DIRECT,
    max_hops: int = 8,
    max_visited: int = 256,
) -> TaxonomyResolution: ...


def aggregate_hard_status(trace: RuleTrace) -> RuleStatus: ...
~~~

| API / input → output | Supported environment | Validation and failure behavior | Intended consumer / pending dependencies |
|---|---|---|---|
| build_knowledge_snapshot: strict content dictionary or KnowledgeBaseSnapshot → KnowledgeBaseSnapshot | SYNTHETIC acceptance only | Recursively validates records, identities, bindings, provenance, active inventory, descriptors and all required check/coverage cells; computes/verifies digest and supplied pins. Invalid content or mismatched pins raises ValidationError. Production acceptance is blocked even with matching pins. | Member 3 loader/orchestration, then Member 2 reasoning; needs authenticated release selection, revocation and approved production workflow policy. |
| resolve_food_relations: FoodGraphSnapshot plus directed query/context and bounds → RelationResolution | SYNTHETIC only | Revalidates snapshot and query; invalid input raises ValidationError. Missing knowledge and inconclusive bounded search return UNKNOWN. Exact evidenced negatives can return VERIFIED_ABSENT; origin mode never does. | Member 2 future rule evaluator; Member 1 composition/retrieval consumes agreed relation semantics through orchestration. Needs canonical food IDs, preparation identity, qualifier vocabulary and verified graph sources. |
| resolve_taxonomy_assignment: FoodGraphSnapshot plus subject/term/traversal and bounds → TaxonomyResolution | SYNTHETIC only | Revalidates the full snapshot; contradictions and invalid inputs raise ValidationError. Exact assignments resolve directly; only cuisine supports parent traversal. Missing knowledge and blocked searches remain UNKNOWN. | Member 2 future classification/rule evaluation; Member 1 tagging/composition and Member 3 normalized requests. Needs approved taxonomy releases, mapping authority and verified-versus-predicted classification policy. |
| aggregate_hard_status: RuleTrace → RuleStatus | Phase 1 declarations support SYNTHETIC and PRODUCTION labels; no production serving authorization is supplied | Revalidates every nested record and retained extra field. Counterfeit enums and invalid traces raise ValidationError. Applicable hard FAIL dominates; missing checks/evaluations or unknown applicability/outcomes yield UNKNOWN. It aggregates declared outcomes, not predicate truth. | Member 2 Phase 3 evaluator; Member 3 manifest/trace orchestration and Member 1 ranking consume eligible IDs later. Needs trusted complete candidate/context manifests, verified observations and implemented applicability/predicate evaluation. |

### Complete synthetic integration flow

test_member2_phase2_integration.py builds a KB with versioned food references,
direct and multihop derivation, exact negative containment, cuisine and dietary
terms/assignments, active hard and soft rules, archived definitions, applicability
descriptors and every required synthetic workflow/scope catalogue/coverage cell.
The flow selects test release pins, accepts the KB, resolves direct/origin/cuisine/
dietary queries and checks selected evidence, witness record versions and release
bindings. It inspects exact mandatory references, serializes camelCase JSON,
revalidates/reaccepts it using the same selected pins, then repeats all observations.
Nested collection reversals and all 24 relation-order permutations retain the digest
and complete resolution results.

Catalogue references also construct a definition-bound Phase 1 RuleTrace. With no
evaluations its result is UNKNOWN even when graph/classification results are SUPPORTED.
Two additional copy/construct regressions prove that an accepted KB cannot authorize
a later counterfeit-severity trace mutation or hide an extra hard FAIL. Their supplied
PASS/FAIL values are explicit synthetic declarations; no Phase 3 predicate runs.

The integration suite has 39 passing cases: 37 existing cases plus these two focused
security-boundary cases. It distinguishes invalid release structures (ValidationError)
from valid missing/incomplete knowledge (UNKNOWN), and exercises production rejection.

### Safety and production limitations

No edge is inferred absent from missing data or coverage. Direct negative results
are limited to exact evidenced assertions. Origin paths use only positive directed
DERIVED_FROM edges, never reverse, mixed or negative paths. Cuisine propagation is
upward only; dietary/role ancestry and food-edge classification propagation are
unsupported. Complete cuisine ancestor contradictions invalidate the snapshot before
query selection or search limits. Deterministic shortest witnesses and accurate
blocked-search limit flags preserve UNKNOWN semantics.

A KB digest establishes integrity relative to independently trusted pins, not
source authenticity. Internal completeness cannot detect a rule omitted from the
entire untrusted inventory. Evidence/approval/environment labels do not authenticate
sources or reviewers. Production-labelled schemas remain declarations; the Phase 2
builder and both resolvers reject production serving. No clinical thresholds,
applicability execution, recipe filtering, composition, ranking or CSP are added.

### Team agreements and Phase 3 handoff

- Member 1: agree canonical Food.com/USDA ingredient and recipe IDs, preparation and
  catalogue/portion versions, verified ingredient facts/completeness, units, taxonomy
  mappings, culinary roles and qualifier vocabulary. Graph reference DTOs do not take
  ownership of the numeric food catalogue.
- Members 1/2/3: approve cuisine/dietary taxonomy authority and release versions,
  model-predicted versus verified classifications, evidence sufficiency and provenance,
  hard-rule workflow/scope policy and final public API/schema names. Resolve the
  October PDF versus ARCHITECTURE.md cuisine/future API vocabulary differences before
  exposing those future interfaces.
- Members 2/3: agree applicability evaluator ownership, context facts and versions,
  missing-data representation, candidate/context binding and trusted manifest assembly.
  Phase 3 must implement evaluation while preserving hard FAIL/UNKNOWN behavior.
- Member 3: implement authenticated production snapshot loading, independently trusted
  pins, release selection/revocation, backend error translation and orchestration.
  Any HTTP exposure follows jointly approved OpenAPI contracts. AI core performs no
  database/ORM/controller I/O.
- Keep recipe-specific hard dietary/allergy/clinical restrictions in standalone
  craving; daily/weekly constraints belong to their approved planning/swap workflows.
  Subsequent filtering and CSP remain future work; no Phase 3 implementation started.


### Final verification and commit boundary

Final checks on 14 October 2026 used existing dependencies with UV_NO_SYNC=1.
No installation or lockfile update was performed.

| Check | Result |
|---|---|
| uv run ruff check . | Passed |
| uv run ruff format --check . | Passed; 90 files already formatted |
| uv run pyright | Passed; 0 errors, 0 warnings |
| uv run pytest -q | 1,281 passed |
| AI architecture/import audit | 21 modules checked; no backend/HTTP/ORM/DB imports or local import cycles |
| Fresh-process imports | Three module import orders passed |
| Python CI OpenAPI export equivalent | Valid JSON generated in memory; no generated contract file written |
| Tracked/untracked whitespace and intended-file secret scan | Passed |
| Dependency, data/EDA, Phase 1 and teammate file checks | Unchanged |

Test counts are 460 Phase 1, 327 graph/origin, 243 taxonomy, 210 KB,
39 Phase 2 integration and two smoke/health cases. All prior 1,279 cases pass;
only the two focused integration regressions were added during the resumed task.
The seven approval cases and 205 Phase 1 security cases remain passing.

No unresolved CRITICAL/HIGH/MEDIUM implementation findings remain in the reviewed
synthetic scope. Production dependencies listed above are deliberately unresolved.
This handoff is ready for a local Phase 2 commit after user approval; it is not
a production release or authorization to begin Phase 3.

The intended Phase 2 commit contains exactly five source modules, four test files
and this document. Exclude Data/, EDA notebooks, phase1-security-fix.patch, the
already committed Phase 1 files and teammates' work. The current base is a58f723;
HEAD/index remain unchanged and no files were staged. Local/cached main refs do not
confirm that Phase 1 PR #5 has merged. Any later reconciliation must use the approved
main state and transfer only the eventual Phase 2 work, without replaying Phase 1
history; fetching or changing Git history requires a separate instruction.

## Phase 7.3b authorized synthetic workflow-policy extension

The original Phase 2 equality policy remains the unchanged default
`synthetic-workflow-scopes.v1`. Its accepted cases, omissions, complete twelve-cell
coverage and historical hashes remain mandatory compatibility gates.

The separately authorized opt-in
`synthetic-workflow-scopes.v2-registered-swap` adds one closed, code-owned
registration: `synthetic-swap-week-quantity-cap`, version1, WEEK scope,
PLANNED_SWAP only. Its complete approved RuleDefinition digest is
`0b9d9ead8206504f86f2385550184b743fdf398a38e10bb0c7c59a2bdca9de5d`.
The immutable registration includes exact identity/version/scope/workflows and
full definition digest. The fictional integer cap44 mg has no nutrition or
clinical meaning and cannot enable production serving.

V2 independently derives each catalogue cell as all unregistered ACTIVE ABSOLUTE
rules of its scope plus exact registered extensions assigned to that workflow.
Exact equality and every existing release, graph, taxonomy, applicability,
evidence and complete-coverage check remain. Missing or changed registered rules
reject; unregistered names/prefixes remain common mandatory rules. V1 does not
use the registry, even when the same rule identity is present in a v1 release.

Only the existing KB/context/recipe-manifest policy fields accept the new exact
token. Recipe manifests explicitly receive the accepted KB policy. There is no
new public signature, serialized field, arbitrary registry argument, exclusion
callback or default migration. Existing v1 hashes and weekly proof protocols
retain their original bindings. A token or rehashed release is not authority;
trusted release selection remains the loader's responsibility.

See [the policy ADR](adr_member2_workflow_rule_inventory_v2.md) for the exact
decision, security tests, frozen compatibility evidence and final verification.
This extension does not complete the draft swap executor/proof work or authorize
Phase 7.3c.
