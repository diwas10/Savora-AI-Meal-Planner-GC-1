# Phase 7.3b — independent single-swap validation

## Current status

**COMPLETE within the approved synthetic Package B1 scope.** Final correctness,
proof, resource, compatibility and preservation evidence is recorded in
**Final B1 correctness and proof verification** below. Phase 7.3c can begin as a
separate task; no selection implementation or production integration is included.
The completed shared KB workflow-policy implementation remains unchanged.

## Historical draft status and stopping point

The following stopped-draft and policy-only checkpoint sections retain the
original evidence and limitations. Their unfinished-gate statements describe
those earlier checkpoints; the final B1 section below supersedes them.
No commit, staging, push, PR or next-phase implementation occurred.

Worktree: `Savora-Phase7`; branch: `feature/member2-phase7`.
Starting and unchanged HEAD: `f28c21ef5c5f4f08feace1900b6f560dab262c67`.
The Phase 7.3a checkpoint and initially empty index were verified. The only
preexisting untracked file was `docs/member2_phase73_75_master_plan.md`.

## Historical authority/compatibility stop

This section records the original stop before the separately authorized policy
extension described below. V1 still intentionally rejects that original fixture;
the new opt-in policy has its own exact registered definition and fixture.

The requested new-workflow-only mandatory-check gate cannot be constructed under
the current accepted KB contract. In `schemas/knowledge_base.py`,
`_KnowledgeContent` derives the expected rules for **each** workflow/scope cell
from all active ABSOLUTE rules of that scope, without a workflow-specific rule
membership policy. It rejects any different set with:

> expected-check entry omits a mandatory active hard rule

WEEKLY_PLAN and PLANNED_SWAP currently support the same scopes. Consequently,
their mandatory rule sets are necessarily equal under this version of the KB
contract. The new validator independently selects both manifests; that does not
make a workflow-only obligation representable. The workflow bridge also forbids
changing context facts, predicates, applicability evidence or KB release merely
to manufacture a different assessment. An unchecked fixture or a monkeypatched
accepted catalogue would not establish independently validated authority.

The fixture-only probe attempted to retain `week-amount` in PLANNED_SWAP while
removing it from the other workflow cells. Accepted KB construction rejected it
before any swap predicate ran. This exposes an existing contract/specification
conflict, not an observed accepted unsafe swap. At that stop, the required test
remained an unfinished gate. The original `swap_only` fixture and its semantic
matrix case exposed this incompatibility. The separately authorized package
below replaces that fixture with a fully validated registered-policy release;
it retains the original v1 rejection.

The user requires stopping before a shared compatibility change and reporting
BLOCKED when an original/resulting mandatory rule cannot be established under
the intended policy. No existing KB, RuleContext, DAY or WEEK API was broadened.

Smallest proposed next decision: explicitly authorize a separately versioned KB
workflow-membership policy, with a release-bound, independently validated rule
inventory for each workflow. Preserve the current v1 behavior and rejection
tests exactly. Assess matching context policy pins and all catalogue consumers
before choosing its additive schema representation. This must be approved and
specified before modifying shared KB/context contracts; silently weakening the
current catalogue equality check is not acceptable. Alternatively, an explicit
specification amendment could defer workflow-specific inventories and their
required B1 coverage. Neither change is assumed authorized here.

This was the **MEDIUM contract/coverage blocker** reported by the original stop.
The separately authorized policy package addresses it below. No completed B1
security review or absence of additional draft defects is claimed.

## Exact draft file inventory

New files:

- `apps/ai_system/src/savora_ai/core/reasoning/swap_checks.py`
- `apps/ai_system/src/savora_ai/core/reasoning/swap_proof.py`
- `apps/ai_system/tests/test_swap_validation.py`
- `apps/ai_system/tests/test_swap_proof.py`
- `apps/ai_system/tests/swap_oracle.py`
- `docs/member2_phase73b_swap_validation.md`

Modified Phase 7.3a files:

- `apps/ai_system/src/savora_ai/core/reasoning/planned_swap.py`
- `apps/ai_system/src/savora_ai/schemas/planned_swap.py`
- `apps/ai_system/src/savora_ai/schemas/swap_proof.py`
- `apps/ai_system/tests/test_swap_proof_contracts.py`

The last file only replaces the old assertion that validation APIs are absent
with declaration/computed-token separation and continued absence of selection
APIs. Historical declaration meanings remain unchanged.

## Implemented draft behavior, pending final verification

The public functions in `core/reasoning/planned_swap.py` have the C6 signatures:

```python
validate_swap(request, replacement, *, saved_plan, locks, permission,
              candidates, knowledge, context, sources, bridge, limits,
              clock=monotonic) -> ComputedSwapValidationResult

verify_swap_validation(result, *, request, replacement, saved_plan, locks,
                       permission, candidates, knowledge, context, sources,
                       bridge, limits, clock=monotonic) -> SwapProofCheck
```

Computed schemas are separate from Package A declaration types:
`computed-swap-validation-result.v1`, `computed-swap-certificate.v1` and
`swap-proof-check.v1`. The computed certificate uses
`synthetic-fixed-swap-full-replay.v1`. `SwapBoundaryError` distinguishes
independent authority conflicts from semantic verdicts.

The draft rechecks both complete fixed plans, disregards historical affirmative
stamps, evaluates selected recipe/combination obligations, all 21 slot states,
seven DAY assessments and the WEEK assessment in each phase. PLANNED_SWAP uses
new typed aggregate records and the audited predicate/applicability primitives;
old WEEKLY_PLAN sources retain their original workflow. Complete source roots
and the strict bridge are revalidated at admission and in operational replay.

The executor constructs the proposed plan from the original 20 full payloads
plus the independently supplied replacement. Target USER/SYSTEM locks and no-op
changes yield OPERATION rejection. Known baseline failure prevents repair or
VALID; known resulting failure dominates unrelated UNKNOWN. Missing measured
values remain unknown rather than zero. Evidenced NOT_APPLICABLE retains the
existing aggregation semantics. The four scoped outcomes are implemented in
draft, with no resulting plan on TIMEOUT or an unverified verdict.

The dedicated checker independently traverses supplied roots, selects options,
rebuilds assessments, reconstructs the proposed plan and verdict, and compares
full evidence and cost claims. It does not call `validate_swap`, its phase
executor, optimized weekly traversal or a prepared affirmative cache. Stateless
full combination/aggregate primitives are shared; literal arithmetic/occurrence
oracles were written separately. Affirmative model construction invokes fresh
checking against external roots rather than accepting a cached PASS token.
These security properties still require the authored hostile-proof suite to run.

Reservations use the exact existing Package A execution-plus-checker equations.
Logical macro costs cover source/bridge/lock records, candidate/combination
preparations, predicate obligations, DAY/WEEK assessments and final validation.
They do not measure Python instructions, actual memory or wall-clock performance.
Bounded structural admission precedes operational reservation. All operational
execution and replay capacity is reserved before semantic work. Identical full
options share records only within one phase of one invocation; both phases and
all assignments are assessed separately.

The initial conservative byte policy reserves the full 1 MiB proof and result
envelopes. Smaller byte limits stop before semantic work. Actual oversized
computed output returns nonaffirmative TIMEOUT; limits are never raised. A
development repeated-component case exposed this guard and the draft now
explicitly handles that output-envelope exception. Clock checks are cooperative
at macro boundaries; the draft does not claim preemptive interruption of a
primitive call or production latency readiness.

## Actual evidence and remaining verification

All evidence is local under `.delta/phase73b/`, excluded from Git staging:

| Evidence | Actual result and limitation |
|---|---|
| First simple end-to-end smoke | VALID after replay; 14 DAY and 2 WEEK assessments; proof 261,550 bytes. Development source only. |
| `development-semantics.xml` | 13 passed, 1 failed, 41 deselected; stopped at the repeated-component result-envelope overflow. Source changed during this development process, so this is not final-fingerprint evidence. |
| `development-profile.bin`, `development-profile.txt` | One seven-rule fixture returned VALID; proof 333,720 bytes, full result 927,182 bytes. Profiling diagnostic only, not a benchmark or correctness suite. |
| Fixture-only probe | Preparation and context-bound fixtures constructed; workflow-only KB fixture rejected as described above. |
| `development-pyright-3.json` | 0 errors, 0 warnings, 0 informations, 114 files analyzed at that development checkpoint. Later scoped edits require a final recheck. |
| `stopped-ruff.txt`, `stopped-format.txt` | Read-only checks of the stopped draft: Ruff passed; all 114 Python files under `apps` already formatted. |
| `stopped-pyright.json` | Stopped draft: 0 errors, 0 warnings, 0 informations, 114 files analyzed. This is a static gate, not semantic/security certification. |
| `stopped-preservation.json`, `stopped-source-hashes.json` | Expected branch/HEAD; empty index; no unexpected preexisting file changes; no whitespace findings. Master plan and all captured prior evidence preserved. Exact ten-path draft inventory and hashes retained. |

The initial 13 semantic passes covered verified/unverified baseline handling,
known baseline failure, missing recipe/measurement facts, unknown/false
applicability, DAY and WEEK refutations despite unrelated UNKNOWN, and repetition
failure. They do not establish all-target, hostile-proof, exact-capacity,
interrupted-checker or final compatibility coverage.

Authored but not finally run: all 21 target locations and 20 unchanged payloads,
USER/SYSTEM target denial, no-op, stale independent pins, malformed revisions,
clock failures, zero/exact/one-short resource axes, replay-only capacity,
checker-stage deadlines, rehashed/omitted/altered/transplanted certificates and
forbidden executor/optimized entry points. At the original stop, the required
new-workflow-only gate was blocked by the accepted v1 KB contract. That checkpoint
claimed no final focused or legacy regression pass. The separate policy results
below supersede only its policy gate, not the remaining B1 validation work.
A full monorepo run was not performed.

Prior Phase 7.3a evidence (140 new and 1,435 relevant cases, Ruff/Pyright) and
Phase 7.2 benchmark evidence remain historical evidence for their fingerprints.
They are not substitute verification of these draft changes. No benchmark was
rerun. `preservation-before.json` captures 308 preexisting file hashes, including
the master plan, tracked source and prior evidence. The final static/preservation
record is retained separately. PowerShell-redirection logs/JSON use the local
PowerShell text encoding; Python-written audit JSON is UTF-8.

## Resumption requirements

The workflow-policy decision is now separately authorized; its verification is
recorded below. After that package passes, audit the draft proof/resource design,
run the remaining full B1 focused
gates, all relevant legacy contract/combination/DAY/WEEK/v2 regressions and final
Ruff/format/Pyright/Git checks against one source fingerprint. Review byte-bound
interruption behavior and independent resource oracles as unfinished work.

Member1 production identities, preparation/portion semantics, complete nutrient
measurements and ranking contracts remain pending. Member3 authenticated loading,
current immutable revisions/locks/grants, revocation and atomic compare-and-write
remain pending. Clinical activation, persistence, HTTP, frontend and selection
execution were not implemented. Phase 7.3c must not begin from this draft handoff.

## Authorized workflow-policy extension

The narrow shared-policy package adds explicit opt-in
`synthetic-workflow-scopes.v2-registered-swap`; v1 remains the unchanged default
with complete hard-rule equality. See the [policy ADR](adr_member2_workflow_rule_inventory_v2.md).
The exact code-owned registration binds `synthetic-swap-week-quantity-cap`,
version1, WEEK, PLANNED_SWAP only, to full definition digest
`0b9d9ead8206504f86f2385550184b743fdf398a38e10bb0c7c59a2bdca9de5d`.
Unregistered rules remain common mandatory checks. No missing obligation becomes
NOT_APPLICABLE and no evaluator truth semantics changed.

The migrated fixture independently validates the registered definition, builds
complete v2 cells and matching original/swap contexts and source bindings, and
retains the common WEEK cap45. The baseline totals42, the replacement totals45,
and only the additional swap cap44 refutes it. It does not just relabel the
rejected v1 `week-amount` catalogue. Original and swap releases still match;
automatic migration of saved v1 material remains unsupported.

The package changes exactly the twelve authorized source/test/document paths.
The draft executor, dedicated checker and declaration/proof implementation files
are preserved byte-for-byte from the policy task's starting state. No remaining
B1 hostile-proof/resource suite is run as part of this package. The new policy
integration tests cover only policy obligations, UNKNOWN/NOT_APPLICABLE,
independent manifests and literal additional logical work.

Final policy verification is **COMPLETE**. The original shared-policy MEDIUM
blocker is resolved; no unresolved HIGH/MEDIUM finding was identified in this
package. Evidence is retained under `.delta/phase73b_policy/`:

| Gate | Actual final result |
|---|---|
| Policy unit/security tests | 45 passed in `final-unit-v2.xml` |
| Policy integration and selected registered-rule semantic case | 12 + 1 passed; only non-unit cases counted from `final-policy.xml` |
| Foundation regressions through DAY | 3,023 passed in `final-foundation-regressions.xml` |
| WEEK, search/proof, Phase 7.2 strategy and Phase 7.3a declaration regressions | 1,239 passed in `final-search-contract-regressions.xml` |
| Distinct final cases | **4,320 passed; zero failures, errors or skips**; `verification-summary.json` |
| Ruff / formatting | Passed; all 117 Python files already formatted; `final-ruff-recheck.json` |
| Pyright | 117 files, zero errors/warnings/informations; `final-pyright-v2.json` |
| Frozen v1 compatibility | Five saved full payloads retain their content digests and wire hashes; `final-golden-check.json` |
| Integrity and scope | Final nine Python fingerprints match; all protected initial files/evidence preserved; exact twelve-path task scope, empty index, unchanged branch/HEAD and no whitespace issues; `source-hashes.json`, `final-preservation.json` |

The final unit report supersedes earlier unit runs without double counting.
Earlier development failures and superseded static reports remain preserved.
Python 3.14.7 / Pydantic 2.14.0 imports resolved to this worktree. No new full
monorepo, backend or frontend run is claimed. Historical benchmark campaigns
and their records were preserved; only small benchmark correctness regressions
ran. No staging, commit, push, PR or other worktree changes occurred.

At that narrower policy-only checkpoint, general Phase 7.3b remained incomplete:
the42 draft proof cases, remaining all-target/hostile-input/resource coverage,
checker overflow path, genuine cross-plan transplant and final full B1 audit
remain separate work. This handoff does not authorize replacement selection.
The final B1 verification below records completion of those remaining gates.

## Member 1/3 future integration requirements

Member 1 reports that the catalogue already supplies fixed portion presets and
that `substitute_slot` exists in the main-branch planning pipeline. These are
integration inputs, not authorization to expand B1. Read-only inspection of the
locally available `main` (`54bb9f5d1824b1d6cc23a6254c61fb8fa1e9e514`) and
`origin/main` (`aead5767fc2485c64e378bb2bdb9dbf213fdf107`) snapshots did not find
that symbol under `apps`. No fetch, merge, cherry-pick or other worktree modification
was performed. Compatibility with the reported current pipeline is a future
adapter requirement, not a completed integration claim.

| Boundary | Required future agreement and behavior |
|---|---|
| External option identity | Preserve `<combinationId>:<PRESET>` byte-for-byte as an opaque ID. Resolve its full independently accepted record; never split it to infer recipe, portion, configuration, quantity or provenance. |
| Fixed presets | Member 1 supplies the presets. No portion generator belongs in this validator. Bind exact combination/configuration IDs and versions, FIXED state, component occurrence/role, full recipe snapshot, preparation, quantity/unit/basis, conversion evidence and source provenance. |
| Saved and replacement material | Jointly version the adapter's complete snapshot/projection mapping. Preserve all twenty original payloads and origins; admit the proposed target against its exact independent source body. A matching option ID cannot replace full identity/evidence comparisons. |
| Existing `substitute_slot` | Connect the existing orchestrator through a future approved adapter to the pure `validate_swap` and independent verifier. Do not copy or replace the pipeline, add a parallel substitution service, or merge main to obtain it in this worktree. Preserve the product's composition/ranking/CSP ownership and fixed-proposal boundary. |
| Real nutrient vectors | A separately approved versioned adapter must define component/configuration identity, complete nutrient fields, dimensions, units, basis, conversions, provenance and reviewed source admission. Never relabel real catalogue vectors as synthetic measured mg facts or fill missing quantities with zero. |
| Ingredient/allergen mapping | Require complete, reviewed canonical ingredient/allergen identities and completeness/coverage evidence. Until then, relevant facts remain UNKNOWN; labels, recipe names, missing mappings and rankings cannot establish safety. |
| Targets and clinical rules | Real nutrition targets, source-admission decisions and clinical activation remain Phase 8 work. The synthetic target pin and fictional integer rules provide no nutritional or clinical authority. |
| Member 3 authority | Independently load approved immutable source/KB/context releases, saved effective revision, complete locks, profile/target pins and the full current permission body. Hashes and caller-supplied references are bindings, not authentication or permission. |
| Persistence and races | Authenticate and recheck ownership, revision, locks, permission/revocation and target at one atomic compare-and-write boundary; persist immutable before/after provenance only after verification. B1 performs no persistence, transaction or revision increment. |
| Outcomes and failures | Preserve boundary errors separately from verified candidate/operation REJECTED, INSUFFICIENT_DATA and nonaffirmative TIMEOUT. Single-candidate rejection is not a global no-feasible-replacement proof. No interrupted/unchecked result may update a plan. |

The B1 tests exercise opaque preset IDs with independent FIXED configuration and
preparation payloads, exact provenance, unchanged slots and same-ID/different-body
rejection. They do not establish a production catalogue adapter or end-to-end
compatibility with Member 1's reported `substitute_slot` implementation. No
ranking invocation, real nutrition, clinical activation, database/backend/frontend
integration or replacement selection is introduced here.

## Final B1 correctness and proof verification

**COMPLETE.** Final focused results, exact-ID fixture reconciliation, relevant
legacy regressions, static checks and protected-source verification have resolved.
Authority is the separately authorized final B1 task and the additional Member 1
integration constraints, with master-plan C6/C7/C9/C10 and Package B1 as the scope.

### Concrete production correction

A new ordinary regression reproduced a MEDIUM resource-result defect: a valid
750,307-byte combined admission with four component occurrences could require a
mixed-origin plan larger than 1 MiB. The independent checker raised ValidationError
instead of returning an incomplete resource report. The preserved probe and
`reproduced-overflow.xml` record that failure. No unsafe affirmative acceptance
was observed in that reproduction.

The sole production correction catches only a nonempty set of exact root
`value_error` envelope-overflow diagnostics during reconstruction and returns
`accepted=False`, `complete=False`, `reason=RESERVATION`, retaining actual verifier
work. Initial authority admission remains outside the handler. Mixed or unrelated
validation failures retain their original exception. No ceiling is raised, proof
is truncated, or output witness is accepted after incomplete reconstruction.
`production-change-audit.json` proves that removing this handler reproduces the
starting checker's full byte fingerprint. Every other production file is unchanged.

### Independent correctness and identity coverage

The retained APIs preserve the exact C6 signatures and independently supplied
authority. Protocols remain `computed-swap-validation-result.v1`,
`computed-swap-certificate.v1`, `synthetic-fixed-swap-full-replay.v1` and
`swap-proof-check.v1`; Package A declarations stay separate. No selection API is
added. Runtime/signature and source-origin evidence is retained separately.

Both fixed plans are freshly checked: complete recipe/combination prerequisites,
21 slot states, seven DAY assessments and one WEEK assessment per phase. All
twenty non-target payloads retain exact original content and source provenance.
The target is independently resolved against a FIXED source option; locks, no-op,
preparation/configuration, quantities and permission remain authoritative checks.
Historical saved PASS labels and rehashed pins never replace this work.

New genuine cross-plan tests construct a second valid original assignment by
changing the last saved slot, rebuilding its daily/weekly trials, assignment,
snapshot and all independent pins. The plans deliberately retain matching plan
and snapshot IDs while their saved content/digests differ. Original totals are42
and45; resulting totals45 and48 under independently valid synthetic limits.
Transplants are checked in both directions and with a changed effective revision.
Separate cases cover each snapshot/reference identity field, locks, contexts,
workflows and policy releases. The original grant-only `plan`-labelled case is
retained as historical coverage rather than misrepresented as the new plan test.

Known FAIL dominates unrelated UNKNOWN. Required incomplete measurements retain
unknown totals even when their numeric value is present. Missing values are never
zero. Evidenced NOT_APPLICABLE retains its existing trace/aggregation meaning.
All four outcomes remain scoped to one proposal; only completely verified VALID
retains a plan. Invalid authoritative structure is a boundary error, including
when all operational budgets are zero.

### Resource oracle and output boundaries

`swap_oracle.literal_swap_cost` independently counts source inventories, complete
definitions, distinct full phase-local options and fixed 21/7/1 assessments. It
does not read certificates or call production schedule, meter, cost, rule-selector
or predicate helpers. The original one-short/exact tests now use this oracle.
It is also checked against literal constants and distinct original assignments,
the registered rule and repeated component occurrences.

| Category per execution / replay | Common fixture | Registered swap-only fixture |
|---|---:|---:|
| Source items | 154 / 154 | 154 / 154 |
| Bridge items | 2 / 2 | 2 / 2 |
| Locked payload comparisons | 21 / 21 | 21 / 21 |
| Candidate / combination preparations | 3 / 3 each | 3 / 3 each |
| Mandatory predicates | 40 / 40 | 41 / 41 |
| DAY / WEEK assessments | 14 / 2 each | 14 / 2 each |
| Full validation work | 1 / 1 | 1 / 1 |
| Checker steps | 0 / 64 | 0 / 64 |
| Domain visits / ordering items | 0 / 0 | 0 / 0 |

Two component occurrences increase source visits to199 per side; per-slot recipe
presence still counts the duplicated recipe once. Each positive operation
category contributes one flat reservation record; these fixtures have64 records.
Reservation is the exact executor-plus-replay vector. Checker-step work is charged
separately, and verifier-only exhaustion cannot authorize a witness. Zero-use
domain/ordering axes are explicitly asserted zero, not skipped.

The accepted initial byte policy conservatively reserves the entire 1 MiB proof
and result capacities. Smaller operational capacities stop before semantic work,
even if a particular smaller output might fit. Exact work/record capacities,
one-short and zero capacities, checker-only exhaustion and execution/checker
deadlines are tested. Units are logical macro obligations, not Python instructions,
actual RAM or a production latency guarantee.

Separate certificate and full-result envelope tests construct below/exact/one-byte
over boundary encodings. Padding is deliberately forged evidence: structural fit
does not make it proof-valid, and the public verifier rejects it. A two-component
case demonstrates a certificate and tentative plan fitting individually while
their full result does not; validation withholds the witness as TIMEOUT. The
four-component case exercises oversized independent plan reconstruction. Oversized
authoritative evidence is rejected structurally before zero-budget operation.
TIMEOUT JSON has no resulting plan or completed-verification claim. Unrelated or
mixed validation errors are not converted into a resource outcome.

### Verification evidence and reconciliation

All new evidence is under `.delta/phase73b_final/`; older `.delta/phase73b/`, policy
and benchmark records remain preserved. The initial draft run passed102 cases,
including all42 original proof IDs collected before edits. Those IDs are retained
in `original-proof-ids.json`; all42 final individual passing results are recorded
in `original-proof-results.json` against the corrected production fingerprint.

The targeted new-gate run recorded9 passes and a fixture-only opaque-ID rename
KeyError, stopping before its last case. The fixture was corrected by binding
renamed domain references together with the complete validated source, without
parsing IDs or changing expected outcomes. The genuine checker-overflow failure
was reproduced separately before its production fix.

Two further new test setups were corrected while the broad run retained its
already-loaded earlier code: backwards-clock readings must remain below the
deadline, and oversized admission must use an unbounded evidence field rather
than a length-limited ID. All three corrected parameter cases passed in
`final-corrected-fixtures.xml`. These change no validation outcomes or production
contracts. `test-fixture-reconciliation.json` reconstructs the earlier file bytes
and verifies their captured hashes; all other test functions and production files
are identical. The broad run's earlier failures remain reported, with final
case results reconciled by exact test ID rather than double-counting reruns.

Ruff, formatting and Pyright v2 checks pass:117 formatted/analyzed files, zero
Pyright errors/warnings/informations. Early type-check outputs retain the incorrect
sibling import-path diagnostics and subsequent new-test annotation fixes. Final
checks explicitly use this worktree's AI/backend source paths and the established
Python3.14.7 / Pydantic2.14.0 environment. The missing local `.venv` configuration
notice is retained; the explicit interpreter and verified import origins are used.

| Run / coverage | Actual result and qualification |
|---|---|
| Initial draft, `draft-focused.xml` | 102 passed:42 proof +60 validation; no failures/skips. Initial fingerprint; overlapping cases are not added to final totals. |
| `reproduced-overflow.xml` | 1 reproduced production failure before correction; its final regression passed. |
| `development-new-gates.xml` | 11 collected;9 passed,1 opaque-ID fixture failure,1 not executed after `-x`; no skips. All IDs occur in final coverage. |
| Broad `final-focused.xml` | 355 collected;352 passed,3 failures from earlier loaded clock/oversized-ID test setups; zero skips/deselections. All42 original proof IDs passed. |
| `final-corrected-fixtures.xml` | All3 exact failed IDs passed with corrected setups and unchanged expected validation outcomes. |
| `final-regressions.xml` | 1,103 passed; zero failures/errors/skips/deselections. Node inventory and collection IDs retained in `regression-selection.txt` and `regression-collection.txt`. |
| Reconciled focused coverage | 355 distinct passing IDs:87 proof +71 validation +68 saved contracts +72 proof contracts +45 policy units +12 policy integrations. Includes56 new B1 cases beyond the original102. |
| Distinct final focused + legacy coverage | **1,458 passing IDs, no unresolved failures**; `verification-summary.json`. Overlapping runs and corrected reruns are counted once per ID. |

The three broad-run failures exactly equal the corrected-rerun ID set. No
unrelated failing case is removed or reclassified, and no security expectation
is weakened. Reconciliation uses the captured byte fingerprints and identical
unaffected function bodies, not a historical PASS. The serving production
fingerprint is identical across the broad and corrected runs. The final128-file
Python map is `final-source-hashes-v2.json`; the earlier map remains preserved.
Full collection IDs are retained, including all original42.

Selected regressions cover KB/catalogue equality, graph authority, recipe
manifests, filtering, rule/combination primitives, literal DAY truth/unknown cases,
v1/v2 WEEK proof APIs, forward checking, incremental checking and MRV. Only the
independent swap checker's resource-error handling changed in production; earlier
shared schema/KB/manifest/evaluation/solver source is unchanged. This selection
avoids blindly repeating the previous4,320 policy cases. Their XML, v1 full-payload
and wire goldens, and benchmark evidence remain intact; the45 policy unit cases
and12 integrations ran again here. The full Python monorepo suite is explicitly
deferred to Phase 7.5. No new full backend/frontend run, historical benchmark
campaign or production latency certification is claimed.

### Final scope, Git integrity and readiness

Worktree `Savora-Phase7`, branch `feature/member2-phase7`, unchanged HEAD
`f28c21ef5c5f4f08feace1900b6f560dab262c67`. Index empty. Tracked diff and all
untracked-file whitespace checks pass. The351-file starting preservation capture
changes only in these five authorized resumption paths:

```text
apps/ai_system/src/savora_ai/core/reasoning/swap_proof.py
apps/ai_system/tests/swap_oracle.py
apps/ai_system/tests/test_swap_proof.py
apps/ai_system/tests/test_swap_validation.py
docs/member2_phase73b_swap_validation.md
```

The final dirty inventory remains exactly20 paths (9 modified,11 untracked):

```text
 M apps/ai_system/src/savora_ai/core/reasoning/manifest.py
 M apps/ai_system/src/savora_ai/core/reasoning/planned_swap.py
 M apps/ai_system/src/savora_ai/schemas/candidates.py
 M apps/ai_system/src/savora_ai/schemas/filtering.py
 M apps/ai_system/src/savora_ai/schemas/knowledge_base.py
 M apps/ai_system/src/savora_ai/schemas/planned_swap.py
 M apps/ai_system/src/savora_ai/schemas/swap_proof.py
 M apps/ai_system/tests/test_swap_proof_contracts.py
 M docs/member2_knowledge_graph.md
?? apps/ai_system/src/savora_ai/core/reasoning/swap_checks.py
?? apps/ai_system/src/savora_ai/core/reasoning/swap_proof.py
?? apps/ai_system/src/savora_ai/schemas/workflow_policy.py
?? apps/ai_system/tests/swap_oracle.py
?? apps/ai_system/tests/test_swap_proof.py
?? apps/ai_system/tests/test_swap_validation.py
?? apps/ai_system/tests/test_workflow_policy.py
?? apps/ai_system/tests/test_workflow_policy_integration.py
?? docs/adr_member2_workflow_rule_inventory_v2.md
?? docs/member2_phase73_75_master_plan.md
?? docs/member2_phase73b_swap_validation.md
```

`final-preservation.json` records exact inventory, branch/HEAD, final hashes,
empty index and whitespace checks. All other captured files, approved policy
implementation and historical raw evidence are unchanged. The master plan remains
untracked and byte-identical. No commit, push, PR, reset, clean, rebase, merge,
cherry-pick, other-worktree modification, dataset/dependency/backend/frontend or
Member1/3 implementation change occurred.

No unresolved HIGH/MEDIUM correctness or security finding remains in the approved
synthetic B1 scope. The reproduced MEDIUM checker overflow defect is corrected and
covered by ordinary regression tests. Production source/clinical/auth decisions
remain deferred integration boundaries. All20 unchanged-slot, authority,
workflow-only obligation, independent proof, resource and output gates are covered
as described above.

**Ready for a separately authorized Phase 7.3c synthetic selection task.** No
selection/ranking generation, portion generator, production adapter, persistence,
real nutrition or clinical activation is implemented here. Member1/3 Phase 8
dependencies and reported `substitute_slot` compatibility remain exactly as
recorded in the future integration requirements above.
