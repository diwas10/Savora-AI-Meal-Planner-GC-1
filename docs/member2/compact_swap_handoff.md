# PR B: compact fixed-meal swap transport

PR B depends on PR A (#20, `feat/member2-native-nutrients-review`, `42cf205`) for
the seven-nutrient DTOs. Branch: `feat/member2-compact-swap`. Merge A before B,
then retarget B to main. PR #19 remains Member 1's application integration work.
This is an explicit AI API; no route, resolver registry, database migration or
application behavior is activated by importing it. The earlier proposed
`compact-swap-transport.v2` document was not an executable protocol. This PR
defines the first executable **compact-planned-swap** family, with explicit v1
tags below; it does not silently activate that proposal.

All reasoning remains **SYNTHETIC**. A VALID fixture result certifies the accepted
synthetic obligations, not clinically validated eligibility. Ingredient mapping
and clinical rule approvals remain inactive as documented in PR A.

## Exact entry points and adapter Protocol

```python
from collections.abc import Callable
from time import monotonic
from typing import Protocol

from savora_ai.schemas.compact_swap import (
    CompactSwapInput, CompactSwapResult, CompactSwapVerification,
    CompactSavedPlanBinding, CompactSwapAuthority, CompactCombinationSource,
)
from savora_ai.core.reasoning.compact_swap_material import AdmittedCompactSwap, admit_compact_swap
from savora_ai.core.reasoning.compact_swap import execute_compact_swap, verify_compact_swap

class TrustedSourceResolver(Protocol):
    def resolve(
        self, catalogue_version: str, ids: tuple[str, ...]
    ) -> tuple[CompactCombinationSource, ...]: ...

    def load_authority(self, binding: CompactSavedPlanBinding) -> CompactSwapAuthority: ...

def admit_compact_swap(
    payload: CompactSwapInput | str | bytes, resolver: TrustedSourceResolver
) -> AdmittedCompactSwap: ...

def execute_compact_swap(
    compact_input: CompactSwapInput | str | bytes, resolver: TrustedSourceResolver,
    *, clock: Callable[[], float] = monotonic,
) -> CompactSwapResult: ...

def verify_compact_swap(
    compact_input: CompactSwapInput | str | bytes,
    compact_result: CompactSwapResult | str | bytes, resolver: TrustedSourceResolver,
    *, clock: Callable[[], float] = monotonic,
) -> CompactSwapVerification: ...
```

The committed Python definitions are authoritative exact signatures. The resolver is
synchronous: Member 1 may preload version-pinned storage with the async backend before
entering this AI API. It must be scoped to the authenticated server request; it must
never echo client source bodies or select ownership/current revision from client claims.
AI imports no backend/ORM/database implementation.

Input/result JSON schemas are provided alongside this document. Source/authority DTOs
are defined in `schemas/compact_swap.py`; inherited historical DTOs keep their own
validation and release semantics. Wire aliases are camelCase, Python names snake_case.

## Input and trusted material

| DTO | Exact significant fields |
|---|---|
| CompactSwapInput | schema_version, policy, mode B1/B2, saved_plan, authority, catalogue_version, sources, slots, target_slot_id, replacement, ranking, candidates |
| CompactSavedPlanBinding | plan_id, revision, owner_id, profile_id, profile_version, snapshot_digest, target_snapshot_digest, kb_id, kb_version, kb_digest, certificate_digest (nullable only for unverified history) |
| AuthorityReference | record_id, version, content_digest |
| CompactSourceReference | catalogue_version, combination_id, content_digest |
| CompactSlot | slot_id, combination_id, portion_preset; exact21 in D1_BREAKFAST through D7_DINNER order |
| CompactReplacement | combination_id, portion_preset; required only in B1 |
| CompactRankEntry | candidate_id, integer priority; B2 wire has only these two candidate fields |
| CompactAuthorizedCandidate | trusted candidate_id, priority, combination_id, portion_preset |
| CompactCombinationSource | schema_version, catalogue_version, combination_id, portions (one per available preset, maximum five) |
| CompactPortionSource | preset, original (nullable for new alternatives), projected, nutrients |
| CompactTargetSnapshot | schema_version, profile_id, profile_version, calculator_payload (full JSON), bands (general DAY/WEEK bands only) |
| CompactSwapAuthority | schema_version, authenticated_user_id, owner_id, current_profile_id/version, saved_plan, target_snapshot, request, locks, permission, knowledge, context, sources, bridge, ranking, candidates, limits |

Authority includes full immutable saved material, original trial/assignment, original
and swap contexts, exact sources/candidates, KB release, full lock inventory and target
permission. Existing `_SwapInputs` admission verifies all revision/reference pins,
the complete context/recipe/option projection whitelist, all saved slots and original
recipe/option coverage. Every B1 attempt also admits its exact independent replacement.
The compact layer does not discard those obligations.

Plan revision and lock-inventory revision are independent counters. Locks remain
bound to the exact saved-plan reference and their complete independently selected
body/digest; the adapter must not conflate the two counters.

After full inventory admission, each compact combination evaluates every recipe in
its exact component references, including ingredient coverage/derivation evidence.
Unrelated recipes in the source pool do not gate that combination; the existing
combination evaluator already has this semantic rule. This avoids repeatedly filtering
all 32 fixture recipes for each two-component meal. All 21 original/result slots and
their actual components are still checked freshly, without a prepared/PASS cache.
The old phase/checker defaults continue to use their full-pool path. Work reservations
remain conservative full-pool upper bounds in the compact path.

Source identity is exactly `(catalogue_version, combination_id, content_digest)`.
Each available preset retains the complete option/configuration IDs and revisions,
component preparations, recipe versions, quantities/units, suitability, source
completeness and native nutrient provenance. Those bindings are not reduced to IDs.
The resolver must construct its available-preset map from the actual combination's
validated configuration inventory. It must not advertise all five presets by default.

Supported identifiers: STANDARD, HIGHER_PROTEIN, LOWER_CARB, LOWER_ENERGY,
HIGHER_ENERGY. Missing presets yield PRESET_UNAVAILABLE. The real example selects
a configuration actually present in Member 1's export.

B2's full authoritative domain and ranking are independently supplied by the resolver.
The input's candidate IDs/priorities and ranking release must match exactly. Priority
is nonnegative, lower first, ties by candidate ID (the existing B2 convention).
PR A's weekly priority strategy uses higher first; do not interchange the conventions.
Every visited candidate receives a full original/result semantic check, including
hard eligibility, slot suitability, all days and week. NO_OP is skipped in B2;
an operation-wide failure such as TARGET_LOCKED stops the operation.

Before selection, B2 independently hard-checks the complete admitted candidate
inventory, derives the exact PASS set and retains FAIL/UNKNOWN/no-op lanes in the
reconstructed certificate. Only PASS candidates enter full replacement selection;
unknown candidates can never be selected and preserve INSUFFICIENT_DATA when no
verified alternative succeeds. A bounded baseline probe is retained when that set
is empty. Candidate aliases of the same combination/preset are rejected. Execution
and verification reserve these prechecks and reconstruct their proof digests freshly.

## Authority and target clarification

A synthetic target ID derived deterministically from `(profile_id, profile_version)`
is acceptable **as a reference only**. It does not authenticate, prove ownership,
establish current revision, verify target content, or authorize clinical rules.

The server adapter must provide the authenticated user and current profile, select
the owned saved revision, and supply the full verified target snapshot. Its content
hash must match the saved target binding; profile identity/version must match both
the current profile and original context. A general band must bind the full calculator
payload hash. An arbitrary synthetic target digest cannot replace that material.
Existing application rows that lack these bindings cannot be admitted by fabricating
them from option IDs. Member 1 must supply a reviewed adapter/persistence migration.

VERIFIED_AT_SAVE uses the actual persisted prior protocol/result reference and digest.
The fixture is UNVERIFIED and has a null certificate_digest. No history is manufactured;
both complete weeks are checked freshly regardless of history. Historical saved DTOs
still accept only their original weekly v1/v2 prior tags. A saved native result with
`computed-weekly-nutrient-solve-result.v1` needs a separately approved saved-history
adapter; do not relabel it as an old protocol or manufacture VERIFIED_AT_SAVE metadata.

## Canonicalization, deduplication and proof artifacts

Canonical compact JSON uses camelCase aliases, ensure_ascii=True, sorted object keys,
compact comma/colon separators, UTF-8 without BOM, no NaN/Infinity, and preserved array
order. Numeric nutrient strings retain their exact declared spelling. SHA-256 values
are lowercase 64-character hexadecimal strings.

`digest(source)` hashes the entire CompactCombinationSource, including its version tag
and each available full portion/native vector; the source does not contain a circular
self-digest field. The authority reference hashes the entire server authority DTO.
Target snapshot digest hashes the entire CompactTargetSnapshot, including profile,
full calculator payload and exact bands. Band source.content_digest hashes the calculator
payload. Legacy KB/source/recipe digests retain their existing canonicalization;
do not reinterpret them under the new JSON codec.

Reconstructed input has root `{input, authority, sources}` with resolved sources sorted
by combination_id. It uses `compact-swap-canonical-dag.v1`:

1. A scalar token is `["value", scalar]`.
2. A composite object node is `["object", [[sorted_key, token], ...]]`.
3. An array node is `["array", [token, ...]]`, preserving order.
4. Each composite node key is SHA-256 of that node's canonical JSON. Equal composite
   bodies appear exactly once; a reference token is `["ref", node_hash]`. Hash equality
   additionally requires exact node equality.
5. The encoded document is `{policy, root, nodes}`. Its **entire encoded byte length**,
   including node hashes, reference tokens, keys and metadata, is the reconstructed
   byte count. It must be at most 4,194,304 bytes. No expanded B2 domain/ranking wrappers
   repeat full sources. Encoding also limits visits to 1,048,576 and depth to 128.

Server reconstruction selects the closed `compact-swap-source-reconstruction.v1`
context. It admits repeated legacy input aggregates by their exact canonical DAG size
when their raw repetition exceeds 4 MiB; it does not raise the 4 MiB ceiling. The complete
authority/native/source root must also pass that same cap. Each output/proof type keeps
its own fixed ceiling. Ordinary legacy and real-catalogue policies retain their raw
1/4 MiB behavior, even when nested inside compact reconstruction. ContextVar tokens
isolate callers and restore the prior policy on exit. There is no wire field that
lets a client choose or raise reconstruction limits.

The real input exposed repeated evidence in the historical expanded phase proof as
well as in the transport. Compact proof phases therefore use the distinct
`compact-swap-phase-assessment.v1` subtype and `compact-swap-canonical-proof.v1` codec,
with an exact **1,048,576-byte** limit. The full two-phase certificate is independently
encoded under that limit too. Historical SwapPhaseAssessment/ComputedSwapCertificate
still retain their original raw 1 MiB ceiling. Only explicit compact execution selects
the new phase factory; no legacy protocol accepts its extra version field.

The proof codec uses the same typed nodes and scalar tokens, but stores nodes in
deterministic postorder in an array. Its reference token is `["ref", zero_based_index]`.
It still interns by SHA-256 plus exact node equality. These short local references
avoid repeating 64-character hash keys throughout large evidence traces. The final
encoded proof, including every node, index/reference and header, must fit 1 MiB;
its artifact digest remains SHA-256 of those exact bytes. This is a distinct proof
codec; input-material/source hashing above continues to use the documented hash refs.

The compact certificate binds the canonical input-material hash and an ordered transcript
of each attempted replacement, the full reconstructed proof's SHA-256, native assessment
digest and computed status. Tags include `compact-swap-phase-certificate.v1` and
`compact-swap-reconstructed-certificate.v1`. A digest is only a binding, never trusted
source evidence or a substitute for evaluating a proof obligation.

No full proof artifact is persisted by Member 2. `verify_compact_swap` loads trusted
authority/sources anew and deterministically reconstructs the complete witness from
them. Its semantic traversal uses the separate historical checker reconstruction,
with the explicit compact phase type and without creating an expanded result plan.
It never calls the executor/phase executor. It compares the complete reconstructed
compact result, including status, replacement, all native totals, byte count and proof
digest. Missing roots/artifacts, stale versions or expired budgets cannot verify.

## Result and verification sequence

CompactSwapResult has schema_version, input_digest, status, reason,
replacement_combination_id, replacement_portion_preset, changed_day_totals,
certificate_digest, reconstructed_bytes and verification_complete. A VALID result
contains seven native-unit totals for the changed day; missing required values remain
UNKNOWN and cannot produce VALID. General native DAY/WEEK bands are checked for both
complete weeks. Failed/unknown decisions contain no replacement delta or fabricated
zero totals. The result is bounded to 1 MiB.

```python
result = execute_compact_swap(compact_json_bytes, authenticated_resolver)
check = verify_compact_swap(compact_json_bytes, result, authenticated_resolver)
if result.status == 'VALID' and result.verification_complete and check.accepted:
    # Member 1 must recheck revision/profile/locks inside its transaction, apply
    # exactly the target delta, and preserve the 20 original saved slot payloads.
    ...
```

Execution already performs a mandatory independent check before exposing a complete
result. An external recheck is useful at the authority/persistence boundary. A verified
REJECTED or INSUFFICIENT_DATA decision is not permission to persist a replacement.

## Errors and resource behavior

| Core status / reason | Meaning | Backend adapter action |
|---|---|---|
| ADMISSION_FAILED / INVALID_INPUT | malformed, oversize, duplicate-key or invalid client JSON | field/contract validation; proposed HTTP 422 |
| ADMISSION_FAILED / STALE_AUTHORITY, AUTHORITY_MISMATCH, TARGET_PROFILE_MISMATCH | owner/current revision/profile/target/KB/history binding differs | refuse stale request; proposed HTTP 409 |
| ADMISSION_FAILED / MISSING_SOURCE, STALE_SOURCE, CONFLICTING_SOURCE, SOURCE_DIGEST_MISMATCH, MALFORMED_SOURCE/AUTHORITY, RESOLVER_UNAVAILABLE | trusted version-pinned material cannot be reconstructed | no persistence; explicit source/adapter failure |
| ADMISSION_FAILED / SLOT_SOURCE_MISMATCH, TARGET_SLOT_MISMATCH, RANKING_MISMATCH, PRESET_UNAVAILABLE | exact slot/domain/preset/ranking binding fails | refuse request; proposed HTTP 422/409 according to stale versus invalid |
| ADMISSION_FAILED / MATERIAL_LIMIT | exact deduplicated canonical input exceeds 4 MiB | refuse; propose a separately reviewed bounded extension if necessary |
| TIMEOUT / RESERVATION or DEADLINE | bounded proof/work/capacity or cooperative deadline stop | incomplete result, no persistence or verification claim |
| REJECTED | full hard/operation/native constraint fails | explicit no-feasible-replacement decision |
| INSUFFICIENT_DATA | unresolved required fact, native value or independent reconstruction | explicit unknown decision; no persistence |
| VALID | complete independently checked synthetic obligations | apply only after server transaction/revision checks and approved application wiring |

HTTP values are adapter proposals; no HTTP contract is changed here. Member 1 must map
them through the existing central success/error envelope and exception handlers.
Resolver exceptions and malformed returns become typed admission failures, not uncaught
resolver exceptions. Diagnostic exception types are sanitized; no resolver exception
message/source contents are returned to clients.

Compact input/output are each at most 1 MiB. Source reconstruction is at most 4 MiB,
with no arbitrary client-selectable extension. Existing atomic proof/result types retain
their ceilings. B2 accepts at most 50 candidates, 71 distinct source combinations and
five available presets per combination, subject also to the historical 150-option source
bound and accepted work/proof-record limits. All candidate traversal, ordering and nested
executor/checker/native work is cumulatively reserved before semantic execution. Sorting
is charged before it runs. B2 conservatively reserves the complete admitted candidate
inventory, even if the first candidate might succeed. The transient canonical proof pool
is reused per candidate; proof-record and work counters are cumulative. Deadlines are
cooperative; structural admission is bounded but is not forcibly preempted. There is no
new process RAM cap or automatic background retry.

## Representative real fixture

`compact_swap_real_example.json` contains full compact B1/B2 JSON, expected results,
independent verification and exact wire/reconstructed byte counts. It is generated from
Member 1 export `20261021T073631Z` (704 dishes / 1692 combinations), with a fictional
owner/profile/target and the stand-in KB. Its file hashes pin the actual catalogue
inputs. Real source values and actual portion configurations are used; no trained
Transformer scorer or production clinical rule base is used.

```powershell
.venv/Scripts/python.exe -m savora_ai.evals.compact_swap_example `
  --catalogue <checkout-of-c5af633>/Data/catalogue `
  --output docs/member2/compact_swap_real_example.json
```

The CLI generator plus pinned source-file hashes defines the representative real-sized
fixture without committing repeated multi-megabyte copies of catalogue/source bodies.
`FixtureResolver` is an in-memory fake. It is not the Member 1 runtime resolver.

## Member 1 activation checklist and deferred features

Required backend fields/artifacts: authenticated owner and current profile identity;
current plan revision and immutable original 21 slot payloads/configuration revisions;
the complete source/recipe/KB/graph/check-policy releases; actual target calculator body
and reviewed target wrapper binding; full locks and target permission; actual prior
saved proof metadata; deterministic original-to-swap projection bridge; available preset
and native-vector provenance/completeness; authoritative B2 domain/ranking release;
accepted limits and the compact decision/certificate digest for successful substitution.
Store before/after snapshots and substitute only the target transactionally. Persist no
craving/history/feedback/retraining events.

Member 1 owns the resolver implementation, database migrations, saved-plan authority,
transaction/revision checks, persistence, API/UI adapters and end-to-end application
tests. Joint DTO/release approval is required before those adapters activate the
protocol. Production ingredient mappings and exact clinical thresholds/applicability
still require source and reviewer approval. PR B is not fully integrated until the
real resolver and backend adapters pass end-to-end validation. No production clinical
rule base or clinically validated label is supplied.
