# ADR: closed synthetic workflow-rule inventory extension

## Decision and scope

The user authorized this narrow shared-policy package following the read-only
Phase 7.3b blocker audit. It is not authorization to finish swap execution,
independent proof/resource testing, replacement selection or Phase 7.3c.
The original blocker was intentional v1 catalogue equality, documented in Phase 2.
Removing that equality check or trusting submitted exclusions would permit missing
hard rules. This decision retains equality under both policies, with independently
reconstructed expected sets.

Two designs were considered: a closed code-owned registration policy, and a new
data-driven KB schema containing a common baseline plus registered additions.
The closed policy is chosen for this synthetic scope. It preserves the existing
payload shape and public signatures. A data-driven schema and production release
registry remain separate design work.

## Exact policies and registration

`knowledge-base.v1` and `knowledge-base-integrity.v1` remain unchanged. Existing
default `synthetic-workflow-scopes.v1` remains unchanged in KB, RuleContext and
recipe manifests. Explicit opt-in adds exactly:

`synthetic-workflow-scopes.v2-registered-swap`

The immutable tuple of frozen registration records in `schemas/workflow_policy.py`
contains one entry:

| Property | Exact value |
|---|---|
| Rule ID | `synthetic-swap-week-quantity-cap` |
| Version | `1` |
| Scope | `WEEK` |
| Permitted workflow | `PLANNED_SWAP` only |
| Full definition SHA-256 | `0b9d9ead8206504f86f2385550184b743fdf398a38e10bb0c7c59a2bdca9de5d` |

The digest covers the full approved RuleDefinition, using the existing unordered
KB canonical JSON encoding: aliases, defaults/nulls, identity, scope, severity,
predicate, required facts, applicability reference, rationale, all evidence and
approval metadata. It excludes no RuleDefinition field. Registry changes require
a new policy version. Registration records are internal policy data; no API accepts
a registry, exclusion list, namespace prefix, wildcard or caller classification.

The registered rule is a fictional CULINARY predicate: synthetic integer WEEK
quantity <=44 mg, with fictional synthetic evidence/approval. It has no nutrition
or clinical authority. The validated definition is independently constructed in
the tests; production code contains its exact registration/digest, not invented
source facts. The new policy rejects nonsynthetic environments. Production serving
remains blocked by the unchanged KB release-acceptance boundary.

## Acceptance and completeness

V1 ignores registrations entirely. For each supported workflow/scope cell it
continues to require all ACTIVE ABSOLUTE definitions of that scope, including a
definition whose ID happens to equal the registered extension's ID.

V2 first requires every registered exact definition to exist and be active, hard,
correctly scoped and digest-identical. Missing, demoted, altered or wrongly
versioned serving definitions reject. Existing definition, active-inventory,
applicability-DAG, evidence and release validators remain in force.

For each cell:

```text
common = all ACTIVE ABSOLUTE definitions except exact registered extensions
expected = common at this scope + exact extensions registered for this workflow/scope
submitted references must equal expected
```

All twelve original cells and complete coverage declarations remain mandatory.
Unknown workflows, unsupported scope cells, duplicate/contradictory entries,
missing common checks, omitted swap checks and extension leakage reject.
Unregistered lookalikes remain common mandatory checks. Expected inventories never
come from submitted catalogue membership or a `complete=True` assertion.

Workflow ownership does not produce a NOT_APPLICABLE evaluation. Selected rules
still use the existing applicability and predicate semantics: UNKNOWN blocks PASS,
evidenced NOT_APPLICABLE resolves a selected obligation, and known FAIL dominates
unrelated UNKNOWN. No evaluator or arithmetic kernel changed.

## Propagation, authority and migration

The only widened policy literals are KB, RuleContext and recipe-manifest policy
fields. `build_expected_check_manifest` now explicitly propagates the validated
KB policy. KB/context mismatches reject; rehashed incoming manifests are compared
with a freshly rebuilt manifest. Existing DAY/WEEK workflow restrictions and public
signatures are unchanged.

Policy/version/digest equality is structural binding, not authentication. As in v1,
a completely self-supplied release cannot establish external rule completeness.
Trusted loaders must independently select approved releases and expected pins.
The tests include an internally valid rehashed common-rule mutation that fails
against the original independent digest.

Older snapshots remain unchanged under v1. There is no automatic upgrade, latest
lookup or cross-policy bridge. The current swap bridge still requires matching
original and swap KB/policy pins. A new-policy fixture therefore builds both source
sets under the same new release, rather than relabelling a rejected v1 catalogue.

The fixture retains the common WEEK limit of45 and separately registers the
swap-only limit44. The original fixed plan totals42 and passes; the replacement
totals45 and fails only the additional registered rule. This is literal synthetic
arithmetic, not a clinical limit. The resulting new obligation adds one execution
and one replay predicate: 41 each, total reservation82, versus40 each for the
matching common-only fixture. Both retain14 DAY and2 WEEK assessments per side.

## Compatibility evidence and completion gate

Before editing, `.delta/phase73b_policy/preservation-before.json` captured327
preexisting file hashes, and `v1-goldens-before.json` retained five complete v1
payload/digest/wire-hash vectors: standalone KB, weekly KB, context, recipe manifest
and WEEK manifest. Frozen expected digest/wire hashes are also literal unit-test
constants. No old default, serialized field, canonical encoder or proof token was
changed. Final test, static and preservation results are recorded in the completion
section below and in the Phase 7.3b handoff.

The exact authorized inventory is five source files, four fixture/test files and
three documentation files. Draft swap executor/proof code, old solvers, teammate
components, datasets, benchmark evidence and the master plan remain unchanged.

| Exact path | Change |
|---|---|
| `apps/ai_system/src/savora_ai/schemas/workflow_policy.py` | New closed registry and policy literals |
| `apps/ai_system/src/savora_ai/schemas/knowledge_base.py` | Version-dispatched exact catalogue admission |
| `apps/ai_system/src/savora_ai/schemas/candidates.py` | Closed context policy token support |
| `apps/ai_system/src/savora_ai/schemas/filtering.py` | Closed recipe-manifest policy token support |
| `apps/ai_system/src/savora_ai/core/reasoning/manifest.py` | Explicit accepted-policy propagation |
| `apps/ai_system/tests/test_workflow_policy.py` | New independent unit/security and v1 golden tests |
| `apps/ai_system/tests/test_workflow_policy_integration.py` | New integration, semantic and literal cost tests |
| `apps/ai_system/tests/swap_oracle.py` | Independently constructed registered-policy fixture |
| `apps/ai_system/tests/test_swap_validation.py` | Two registered-rule manifest expectations |
| `docs/adr_member2_workflow_rule_inventory_v2.md` | This decision and verification record |
| `docs/member2_knowledge_graph.md` | Additive policy handoff |
| `docs/member2_phase73b_swap_validation.md` | Scoped blocker resolution and remaining B1 work |

The shared-policy blocker can be closed only after the new policy tests, relevant
Phase1–7.3a regressions, selected B1 policy-admission case and static/integrity
checks pass. Full B1 completion, its42 proof cases and remaining resource/hostility
work remain a separate next task even after this package passes.

## Final scoped verification — COMPLETE

The authorized workflow-policy package is complete on
`feature/member2-phase7`, unchanged HEAD
`f28c21ef5c5f4f08feace1900b6f560dab262c67`. The original shared-policy
MEDIUM contract/coverage blocker is resolved. No unresolved HIGH or MEDIUM
finding was identified within this package. This is not B1 execution/proof
certification or readiness for Phase 7.3c.

Final evidence is retained under `.delta/phase73b_policy/`:

| Gate | Final result | Evidence |
|---|---|---|
| Independent unit/security and frozen v1 vectors | 45 passed | `final-unit-v2.xml` |
| Policy integration and selected B1 admission | 12 + 1 passed | Only the non-unit cases in `final-policy.xml` |
| KB, graph, taxonomy, context, rules, filtering, combination and DAY regressions | 3,023 passed | `final-foundation-regressions.xml` |
| WEEK, old/v2 solver/proof, bounds, incremental, ordering, benchmark correctness and Phase 7.3a contracts | 1,239 passed | `final-search-contract-regressions.xml` |
| Distinct final cases | **4,320 passed; zero failures, errors or skips** | `verification-summary.json` |
| Ruff and formatting after the final test typing edit | Passed; 117 files already formatted | `final-ruff-recheck.json` |
| Pyright | 117 files; zero errors, warnings or informations | `final-pyright-v2.json` |
| Frozen v1 compatibility | All five content digests and serialized-wire hashes unchanged | `v1-goldens-before.json`, `final-golden-check.json` |
| Source and preservation | Nine authorized Python fingerprints unchanged; only eight authorized existing files changed among 327 captured files | `source-hashes.json`, `final-preservation.json` |
| Git scope and whitespace | Exact twelve-path task scope; expected twenty dirty paths including preserved draft/master-plan files; empty index; no whitespace findings | `final-preservation.json` |

The final 45-unit report supersedes earlier unit runs. Its cases are counted once;
the older combined policy report contributes only its twelve integration cases
and one selected admission case. Development failures and superseded Pyright
outputs remain preserved, with no claim that they passed. All serving source
and reused integration/fixture definitions retain their final fingerprints.
The nine-file Python fingerprint map and final twelve-file hash inventory bind
this record to the final changes. Import origins resolve to this worktree;
the established Python 3.14.7 / Pydantic 2.14.0 environment was used.

The selected B1 case demonstrates that the baseline passes and the resulting
plan is rejected by the additional registered rule. Integration also verifies
UNKNOWN and evidenced NOT_APPLICABLE through the existing public boundary,
independent complete manifests, and the literal additional predicate/reservation
charges. It does not run the remaining B1 hostile-proof/resource suite.

No new full-monorepo, backend or frontend verification is claimed. Historical
benchmark campaigns were not rerun or changed; the benchmark regression file
contains small fixture correctness checks. The draft executor/checker, prior
Phase 7 source/evidence, datasets and untracked master plan remain intact.
No staging, commit, push, PR or other worktree modification occurred.

Ready to resume the separate Phase 7.3b completion/independent validation task.
Its 42 draft proof cases, remaining all-target and resource coverage, checker
overflow path, genuine cross-plan transplant and full B1 audit remain unfinished.
Do not begin selection or Phase 7.3c from this scoped completion.
