# ADR: Member 2 Phase 7 versioned search proofs and saved-slot substitution

Date: 19 October 2026.
Status: recorded Phase 7.1a Member 2 engineering decisions; external team contracts
**PENDING**. No implementation or joint production approval is implied.

## Context and authority

ARCHITECTURE.md sections 3-4, 8, 11 and 13-15 require conservative eligibility,
21-slot feasibility, search comparisons and saved-slot substitution with the other
20 assignments locked. Phase 6 implements synthetic chronological first-feasible
weekly search with exact preparation and deterministic output replay. Its v1
coverage paths assume chronological slots and cannot represent arbitrary MRV
selection merely by changing the search order. Recipe/combination stages support
PLANNED_SWAP, but the current daily/weekly source boundary accepts WEEKLY_PLAN only.

This focused ADR lives directly in `docs/`: no ADR directory exists at the verified
baseline, and architecture section 15 explicitly says to record short ADRs there.
The companion [Phase 7 plan](member2_phase7_plan.md) supplies source anchors,
proposed names/paths, evaluation protocol, task gates and pending handoffs. Both
documents are subordinate to AGENTS.md and ARCHITECTURE.md. Historical Phase 1-6
handoffs remain unchanged.

## Decision

1. **Add a separate weekly search v2.** Preserve all Phase 1-6 signatures, accepted
   tokens, semantics and v1 verification. Existing `solve_weekly_plan` remains
   chronological v1 by default. V2 requires explicit selection and version-disjoint
   result/certificate validation. Neither version accepts the other's proof; no
   casts, relabelling or implicit migration. Search protocol v2 does not reinterpret
   the existing synthetic attribute-policy version numbers.

2. **Require a checked failure cover for every prune.** A removed subtree is valid
   only when independently recomputed evidence proves every removed completion
   contains a known failure. UNKNOWN alone never authorizes pruning, fabricated
   bounds or zero measurements. Retain complete mandatory checks and conservative
   applicability, known-FAIL dominance and evidenced NOT_APPLICABLE semantics.
   New strategies use explicit allowlisted versioned policies. Verify original
   domains/options, selected slot identities, input/source/context/rule pins,
   preparation, bounds/exclusions, leaves, unknowns, frontier partition and work
   accounting. Rebuild/recompute rather than accepting hashes, counters, PASS
   labels or exhaustive flags. Replay remains supported by independent finite
   correctness oracles; unsigned integrity is not source authentication.

3. **Preserve bounded execution and verification.** Keep v1 accounting unchanged;
   specify and charge v2 preparation, propagation, incremental derivation, proof
   and verifier work explicitly. Reserve mandatory proof capacity before work.
   Cache reuse needs exact validated dependencies; eviction cannot remove options.
   Resource/deadline exhaustion is TIMEOUT, including at proof/output verification;
   no partial successful result. Cooperative deadlines are not interruption
   guarantees. Distinguish proof reservation, encoded size and actual memory.
   Preserve strict original-JSON and unchecked-instance defenses.

4. **Keep swaps pure and externally authorized.** Member 3 owns saved-plan
   authorization, independently selected effective snapshot/revision and persistence.
   Member 2 compares proposals against independently supplied exact saved material.
   Exactly one target assignment changes; all other 20 preserve full original
   recipes/components, configuration/portions, preparation, measurements, suitability,
   source/evidence and version/digest bindings. No-op is not a successful swap.
   A dedicated PLANNED_SWAP workflow/context bridge must validate original-to-swap
   bindings and complete manifests; relabelling a weekly request is forbidden.
   Initial scope keeps profile/target/KB versions unchanged unless an explicit
   independently verified compatibility bridge exists. Validate all applicable
   recipe, combination, DAY and WEEK requirements in the resulting full plan.
   Member 3 must recheck authorization/revision at transactional persistence time.

5. **Use scoped swap verdicts.** Proposed VALID means one verified replacement
   with exact locks and complete obligations, not permission to persist.
   REJECTED means a known violation for the supplied candidate or fully failed
   explicit replacement domain, not global weekly INFEASIBLE. Surviving unrefuted
   unknowns require INSUFFICIENT_DATA; unfinished required work requires TIMEOUT.
   Malformed/stale/conflicting pins remain validation errors. Final shared DTOs,
   tokens and backend mapping are pending team approval.

6. **Limit work and claims to registered synthetic attributes.** Real nutrition
   vectors, clinical thresholds, Food.com normalization, source-authentication
   integration and production safety claims are excluded. Member 1 retains
   composition/ranking/data ownership; Member 3 retains orchestration/persistence.
   Standalone craving bypasses composition/CSP; planned substitution follows the
   full composition/ranking/feasibility workflow. No database or teammate edits.

7. **Establish the baseline before optimization.** Compare equal semantic inputs,
   budgets and stopping criteria. Keep independent small-domain enumeration and
   arithmetic as truth sources. Separate outcome equivalence from first-witness
   equivalence: MRV/value ordering may change the first witness and bounded
   TIMEOUT behavior. Report search/evaluation/propagation/proof/cache/memory costs,
   timeout stages and independently verified results; separate preparation,
   algorithmic search and proof verification timing. Do not claim optimality or
   speedups that exclude required validation.

## Alternatives declined

- Extending v1 policy literals or reusing chronological index paths for MRV would
  reinterpret existing proofs and undermine compatibility.
- Pruning UNKNOWN, trusting claimed hashes/counters, reducing manifests or dropping
  proof events under pressure would permit unjustified infeasibility or success.
- Treating a client-carried saved plan as independent authority, relabelling weekly
  contexts, refreshing locked sources or silently changing another meal would
  violate snapshot and substitution ownership/locking guarantees.
- Implementing heuristics or swap code before baseline/proof declarations would
  bypass the required correctness and evaluation gates.

## Consequences and sequence

Additive schemas and verifiers cost code/verification effort; correctness must be
shown before speed gains. Arbitrary slot ordering needs richer explicit events and
dependency-aware DAY completion/rollback. No universal witness or timeout equality
is promised across strategies. Synthetic success establishes no production safety.

Future sequence is fixed: **7.1b** baseline harness → **7.1c** strict v2 proof
declarations → **7.2a** independently verified chronological v2 → **7.2b** preparation
reuse → **7.2c** sound forward checking → **7.2d** incremental derivation → **7.2e**
deterministic ordering/MRV → **7.3a** saved-plan/workflow foundation → **7.3b** pure
swap validation → **7.3c** bounded replacement selection → **7.4** comparative
evaluation → **7.5** full compatibility/security audit. Proposed APIs and paths in
the plan remain proposals until their future scoped tasks implement them.

Pending joint decisions: saved-plan revision/material and concurrent-write protocol;
workflow/version compatibility bridge; final public DTO/API/transport and resource
policy; ranking and canonical preparation/measurement/target handoffs; source and
revocation authority; all existing architecture section 15 clinical, catalogue,
template/cuisine and objective decisions. These do not block measuring the current
synthetic v1 baseline, but they gate relevant external integration.

Phase 7.1a delivers only the plan and this ADR. Source/proof-boundary review,
documentation link/whitespace checks and final Git scope/identity checks are its
validation. No tests, benchmark execution, implementation, commit or push is part
of this decision record.
