"""Independent v2 checker and stateless evaluation/encoding adapters.

The checker never imports the v2 search kernel. It uses an explicit task stack,
recomputes every prerequisite and DAY/WEEK assessment, and additionally checks a
mixed-radix interval partition of the ORIGINAL Cartesian space. Shared helpers
below encode data or evaluate a supplied assignment; none selects a search branch.

Accounting v2: each atomic operation reserves its execution cost plus an equal
verifier cost and one checker step, before work. Candidate costs include the
recipe batches inside combination preparation. DAYs are reassessed on every
visit without a DAY memo. Optional recipe-pool reuse preserves these logical
reservations; versioned preparation accounting separately reports physical work.
Compilation/input admission are bounded contract validation, not predicate units.
They remain cooperative, non-interruptible operations. A checkpoint precedes
each atomic operation. Rollbacks cost no evaluator work. A proof slot is reserved
before each unary exclusion, DAY failure emission, or WEEK assessment.
Written bytes are exact ordered event JSON plus separators. Reserved bytes also
cover the certificate envelope and frontier; they are not process-memory claims.
The runtime reserves at most 480 terminal records, leaving space for the at most
22 unexplored suffix scopes under the declaration's 512-branch structural ceiling.
Larger record declarations do not enlarge that structural execution ceiling.
Certificate snapshots end at execution: their verification_work is zero. The
computed result separately reports actual verifier work against those reservations.
Checker steps count completed atomic operations rechecked; bounded shape, identity,
frontier and failed-reservation checks are metadata validation, not physical-call
or CPU accounting. Revalidation is a fresh check; there is no cross-request credit.
No clock reading authenticates a remote source or a caller's clock observation.
Expired verification can only remove authority and withhold a witness.

Forward policy synthetic-weekly-forward-work-reservation.v2 adds a rule attempt
at each unfinished chronological prefix: one predicate obligation, one heuristic
unit plus one per original measurement occurrence and required fact, mirrored for
verification. These are conservative logical scan obligations, not physical calls.
Each attempt reserves a potential closure record/bytes before arithmetic. Unused
storage is released on a nonclosure; completed work is never refunded. Reported
proof reservations retain committed records plus the envelope, not the sum of
temporary allocations. Snapshot reservations remain cumulative across emitted
events. Failure to reserve potential storage still terminates with TIMEOUT.

Incremental variants use synthetic-weekly-incremental-work-reservation.v2. Only
under that policy, heuristic units additionally reserve source metadata admission,
each selection plus its prepaid rollback, and DAY/WEEK aggregate extraction.
The checker reconstructs those protocol costs but always derives full facts from
original sources, without importing or constructing execution's incremental state.
See the _incremental_*_cost helpers and the Phase 7.2d handoff for exact units.

Ordered variants use synthetic-weekly-ordered-work-reservation.v2: first reserve
21 + total ORIGINAL domain cardinalities for fixed order preparation, mirrored
for verification. Applicable forward/incremental charges above also apply under
this token. Their explicit ordered coverage policy binds the permutation of actual
slot identities and the value-rank bijection; old policies retain old encodings.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from math import prod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from savora_ai.core.reasoning.combinations import _evaluate_prepared_combination
from savora_ai.core.reasoning.day_checks import _assess_day, _evaluate_day, _slot_status
from savora_ai.core.reasoning.facts import _validated_fact_index
from savora_ai.core.reasoning.filtering import filter_candidates
from savora_ai.core.reasoning.manifest import _mandatory_checks, _ManifestRequest
from savora_ai.core.reasoning.preparation import _PreparedRecipePool
from savora_ai.core.reasoning.week_checks import (
    _assess_week,
    _compile_week,
    _evaluate_week,
    _prepare_option,
)
from savora_ai.core.reasoning.weekly import _manifest, _WeekRequest
from savora_ai.core.reasoning.weekly_bounds import _attempts, _check_bound, _cost, _metadata
from savora_ai.schemas import weekly_search_v2 as v2
from savora_ai.schemas.candidates import CandidateRecipeFacts, RuleContext
from savora_ai.schemas.combinations import PortionState
from savora_ai.schemas.daily import DailyOutcome, MealOptionReference, MealSlot
from savora_ai.schemas.daily_solver import (
    DailyAssignmentEvaluation,
    DailyOptionDecision,
    DailySlotDecision,
    DailyTrial,
    DailyTrialChoice,
    _assignment,
    _explanations,
)
from savora_ai.schemas.filtering import _evidence_union
from savora_ai.schemas.knowledge import RuleReference, RuleScope
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot
from savora_ai.schemas.nutrients_v2 import WeeklyNutrientContractV2
from savora_ai.schemas.reasoning import ApplicabilityStatus, RuleStatus
from savora_ai.schemas.weekly import (
    ExpectedWeekCheckManifest,
    WeeklyAssignment,
    WeeklyDayAssignment,
    WeeklyPlanningRequest,
    WeeklySourceSnapshot,
    WeeklyTrial,
    WeeklyTrialChoice,
    _weekly_source_reference,
)
from savora_ai.schemas.weekly_evaluation import _week_explanations
from savora_ai.schemas.weekly_search import WeeklyWitness, WeeklyWitnessDay

if TYPE_CHECKING:
    from savora_ai.core.reasoning.weekly_incremental import _IncrementalState


def _bytes(value: Any) -> bytes:
    def data(item: Any) -> Any:
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json", by_alias=True)
        if type(item) in (tuple, list):
            return [data(x) for x in item]
        if type(item) is dict:
            return {key: data(val) for key, val in item.items()}
        return item

    return json.dumps(
        data(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _preparation_session(
    manifest: ExpectedWeekCheckManifest, candidates: tuple[CandidateRecipeFacts, ...], capacity: int
) -> _PreparedRecipePool:
    return _PreparedRecipePool(
        candidates=candidates,
        knowledge=manifest.knowledge,
        context=manifest.request.source.daily_source.context,
        sources=tuple(o.combination for o in manifest.request.source.daily_source.options),
        capacity=capacity,
    )


def _prepared_option(
    manifest: ExpectedWeekCheckManifest,
    candidates: tuple[CandidateRecipeFacts, ...],
    ref: MealOptionReference,
    session: _PreparedRecipePool,
) -> DailyOptionDecision:
    """Supplied-option evaluation only; no branch selection or cached combination verdict."""
    option = next(o for o in manifest.request.source.daily_source.options if o.reference == ref)
    proof = _evaluate_prepared_combination(
        option.combination,
        candidates=candidates,
        knowledge=manifest.knowledge,
        context=manifest.request.source.daily_source.context,
        trusted_combination=option.combination,
        prepared=session,
    )
    if proof.deferred_checks != tuple(
        sorted(
            (*manifest.day_checks, *manifest.required_checks), key=lambda r: (r.rule_id, r.version)
        )
    ):
        raise ValueError("combination loses authoritative DAY/WEEK definitions")
    return DailyOptionDecision(
        option=ref,
        combination=proof,
        slots=tuple(
            DailySlotDecision(slot=s, status=status, reasons=reasons)
            for s in MealSlot
            for status, reasons in (_slot_status(option, s, proof.status),)
        ),
    )


def _admit(
    request: WeeklyPlanningRequest,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: WeeklySourceSnapshot,
) -> tuple[ExpectedWeekCheckManifest, tuple[CandidateRecipeFacts, ...]]:
    # Revalidate original storage, including unchecked copies; hashes do not admit data.
    from savora_ai.core.reasoning.filtering import _FilterRequest

    accepted = _WeekRequest(request=request, kb=knowledge, context=context, sources=sources)
    pool = _FilterRequest(kb=accepted.kb, context=accepted.context, candidates=candidates)
    for candidate in pool.candidates:
        _ManifestRequest(kb=pool.kb, context=pool.context, candidate=candidate)
        _validated_fact_index(candidate.facts)
    _validated_fact_index(pool.context.facts)
    return _manifest(accepted), tuple(
        sorted(
            pool.candidates,
            key=lambda c: (
                c.recipe_id,
                c.recipe_version,
                c.snapshot_id,
                c.snapshot_version,
                c.content_digest,
            ),
        )
    )


def _material(
    manifest: ExpectedWeekCheckManifest,
    candidates: tuple[CandidateRecipeFacts, ...],
    strategy: v2.WeeklyExecutableStrategyV2,
    limits: v2.WeeklySearchLimitsV2,
) -> dict[str, Any]:
    if strategy.policy not in (
        "synthetic-priority-weekly-search.v2",
        "synthetic-nutrient-priority-weekly-search.v2",
        v2.WeeklyStrategyPolicyV2.CHRONOLOGICAL,
        v2.WeeklyStrategyPolicyV2.FORWARD_CHECKING,
        v2.WeeklyStrategyPolicyV2.INCREMENTAL,
        v2.WeeklyStrategyPolicyV2.INCREMENTAL_FORWARD_CHECKING,
        v2.WeeklyStrategyPolicyV2.REVERSE_VALUES,
        v2.WeeklyStrategyPolicyV2.STATIC_MRV,
        v2.WeeklyStrategyPolicyV2.STATIC_MRV_FORWARD_CHECKING,
        v2.WeeklyStrategyPolicyV2.STATIC_MRV_INCREMENTAL,
        v2.WeeklyStrategyPolicyV2.STATIC_MRV_INCREMENTAL_FORWARD_CHECKING,
    ):
        raise ValueError(
            "only chronological, reverse and static original-domain MRV v2 policies execute"
        )
    request = manifest.request
    if isinstance(strategy, (v2.WeeklyPrioritySearchStrategyV2, v2.WeeklyNutrientSearchStrategyV2)):
        strategy.declaration.bind(request)
    if isinstance(strategy, v2.WeeklyNutrientSearchStrategyV2):
        strategy.nutrient_contract.bind(request)
    context = request.source.daily_source.context
    domains = tuple(
        v2.WeeklyOriginalDomainV2(
            slot=v2.WeeklySlotIdentityV2(
                canonical_index=(day.day.day_index - 1) * 3 + i, day=day.day, slot=slot
            ),
            options=tuple(
                sorted(
                    next(d for d in day.domains if d.slot is slot).options,
                    key=lambda o: o.option_id,
                )
            ),
        )
        for day in sorted(request.days, key=lambda d: d.day.day_index)
        for i, slot in enumerate(MealSlot)
    )
    rules = tuple(
        sorted(_mandatory_checks(manifest.knowledge, context), key=lambda r: (r.rule_id, r.version))
    )
    obligations = tuple(
        v2.WeeklyRuleObligationV2(
            rule=RuleReference(rule_id=r.rule_id, version=r.version), scope=r.scope
        )
        for r in rules
    )
    if len(obligations) > 256:
        raise ValueError("complete inventory exceeds the v2 declaration input capacity")
    identity = v2.WeeklySearchIdentityV2(
        request_id=request.request_id,
        request_version=request.version,
        request_digest=request.content_digest,
        manifest_digest=manifest.content_digest,
        candidate_set_digest=_digest(
            dict(
                policy="synthetic-weekly-candidate-set-digest.v2",
                candidates=sorted(
                    {
                        (
                            c.recipe_id,
                            c.recipe_version,
                            c.snapshot_id,
                            c.snapshot_version,
                            c.content_digest,
                        )
                        for c in candidates
                    }
                ),
            )
        ),
        source=request.expected_source,
        daily_source=request.source.expected_daily_source,
        context_id=context.context_id,
        context_version=context.version,
        context_digest=context.content_digest,
        profile_id=context.profile_id,
        profile_version=context.profile_version,
        kb_id=manifest.knowledge.kb_id,
        kb_version=manifest.knowledge.version,
        kb_digest=manifest.knowledge.content_digest,
        strategy=strategy,
    )
    material: dict[str, Any] = dict(
        request=request,
        identity=identity,
        rule_obligations=obligations,
        original_domains=domains,
        limits=limits,
    )
    if (
        strategy.value_order == "OPTION_ID_DESC"
        or strategy.variable_order == "STATIC_MRV_ORIGINAL_DOMAINS"
    ):
        material["proof_policy_version"] = "synthetic-weekly-ordered-coverage.v2"
    if isinstance(strategy, (v2.WeeklyPrioritySearchStrategyV2, v2.WeeklyNutrientSearchStrategyV2)):
        material["proof_policy_version"] = "synthetic-weekly-priority-coverage.v2"
    if isinstance(strategy, v2.WeeklyNutrientSearchStrategyV2):
        material["proof_policy_version"] = "synthetic-weekly-nutrient-priority-coverage.v2"
    return material


def _scope(
    domains: tuple[v2.WeeklyOriginalDomainV2, ...],
    path: tuple[int, ...],
    alternatives: tuple[int, ...] = (),
) -> v2.WeeklyBranchScopeV2:
    prefix = "p" + ".".join(str(i) for i in path)
    branch_id = prefix + ("a" + ".".join(map(str, alternatives)) if alternatives else "")
    if len(branch_id) > 128:
        # Keep every previously valid ID unchanged. Wide original domains can
        # exceed the opaque-ID ceiling in reservation/suffix scopes. This exact
        # one-character encoding preserves all 0..49 indices without truncation
        # or treating a hash as branch identity authority.
        alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn"
        branch_id = prefix + "a:" + "".join(alphabet[i] for i in alternatives)
    return v2.WeeklyBranchScopeV2(
        branch_id=branch_id,
        extent="SLOT_ALTERNATIVES"
        if alternatives
        else "LEAF"
        if len(path) == 21
        else "PREFIX_COMPLETIONS",
        path=tuple(
            v2.WeeklySelectedOptionV2(
                depth=i, slot=domains[i].slot, original_domain_index=p, option=domains[i].options[p]
            )
            for i, p in enumerate(path)
        ),
        decision_slot=domains[len(path)].slot if alternatives else None,
        original_domain_indexes=alternatives,
    )


def _rest(
    domains: tuple[v2.WeeklyOriginalDomainV2, ...],
    rank: int,
    *,
    reverse: bool = False,
    orders: tuple[tuple[int, ...], ...] | None = None,
) -> tuple[v2.WeeklyFrontierBranchV2, ...]:
    """Compact suffix partition, independent of the executor's mutable DFS cursors."""
    sizes = tuple(len(d.options) for d in domains)
    if rank >= prod(sizes):
        return ()
    if rank == 0:
        scopes = [_scope(domains, ())]
    else:
        ranks = tuple((rank // prod(sizes[i + 1 :])) % sizes[i] for i in range(21))
        digits = tuple(
            orders[i][p] if orders is not None else sizes[i] - 1 - p if reverse else p
            for i, p in enumerate(ranks)
        )
        scopes = [_scope(domains, digits)]
        scopes.extend(
            _scope(
                domains,
                digits[:i],
                tuple(sorted(orders[i][ranks[i] + 1 :]))
                if orders is not None
                else tuple(range(digits[i]))
                if reverse
                else tuple(range(digits[i] + 1, sizes[i])),
            )
            for i in reversed(range(21))
            if ranks[i] + 1 < sizes[i]
        )
    return tuple(
        v2.WeeklyFrontierBranchV2(scope=s, state=v2.WeeklyFrontierStateV2.UNEXPLORED)
        for s in scopes
    )


def _all_obligations(material: dict[str, Any]) -> tuple[v2.WeeklyObligationV2, ...]:
    strategy = material["identity"].strategy
    return (
        *(
            tuple(
                v2.WeeklyNutrientObligationV2(band_id=b.band_id, scope=b.scope)
                for b in strategy.nutrient_contract.bands
            )
            if isinstance(strategy, v2.WeeklyNutrientSearchStrategyV2)
            else ()
        ),
        *material["rule_obligations"],
        *(
            v2.WeeklyPrerequisiteObligationV2(prerequisite=p)
            for p in (
                "CANDIDATE_MEMBERSHIP",
                "COMPOSITION_AUTHORITY",
                "FIXED_CONFIGURATION",
                "SLOT_SUITABILITY",
            )
        ),
        *(
            v2.WeeklyPrerequisiteObligationV2(prerequisite="MANDATORY_CHECK_COVERAGE", scope=s)
            for s in RuleScope
        ),
    )


def _payload(
    material: dict[str, Any],
    kind: str,
    scope: v2.WeeklyBranchScopeV2,
    digest: str = "0" * 64,
    status: RuleStatus = RuleStatus.UNKNOWN,
) -> dict[str, Any]:
    result: dict[str, Any] = dict(kind=kind, identity=material["identity"], scope=scope)
    if kind == "COMPLETED_LEAF":
        return result | dict(
            declared_status=status, obligations=_all_obligations(material), evaluation_digest=digest
        )
    obligations = (
        tuple(o for o in material["rule_obligations"] if o.scope is RuleScope.DAY)
        if kind == "DAY_FAILURE"
        else tuple(
            v2.WeeklyPrerequisiteObligationV2(prerequisite=p)
            for p in (
                "CANDIDATE_MEMBERSHIP",
                "COMPOSITION_AUTHORITY",
                "FIXED_CONFIGURATION",
                "SLOT_SUITABILITY",
            )
        )
    )
    if not obligations:
        # Reservation template only. An empty DAY inventory cannot produce a
        # known DAY failure and is never emitted as a failure event.
        obligations = (
            v2.WeeklyPrerequisiteObligationV2(
                prerequisite="MANDATORY_CHECK_COVERAGE", scope=RuleScope.DAY
            ),
        )
    # Keep a native descriptor until record capacity has been reserved. A legal
    # source can exceed an individual event's evidence ceiling; that is unfinished
    # proof work, not permission to drop evidence or leak an output-validation error.
    result["basis"] = dict(
        obligations=obligations,
        evaluationDigest=digest,
        relevantBasisComplete=True,
        declaredStatus="FAIL",
        soundness="DEFERRED",
        evidence=_evidence_union(
            (
                material["request"].source.evidence,
                material["request"].source.daily_source.context.evidence,
            )
        ),
    )
    if kind == "DAY_FAILURE":
        result["day_index"] = scope.path[-1].slot.day.day_index
    return result


def _charge(payload: dict[str, Any]) -> int:
    # Versioned conservative envelope for one event AND its terminal frontier.
    return len(_bytes(payload)) + 2 * len(_bytes(payload["scope"])) + 4096


def _forward_payload(material, domains, path, program, attempt, bounds=None) -> dict[str, Any]:
    """Reservation descriptor first; actual endpoints only after reserved work."""
    scope = _scope(domains, path)
    result = _payload(material, "UNARY_FAILURE", scope)
    result["kind"] = "FORWARD_CHECK_CLOSURE"
    result["basis"]["obligations"] = (
        v2.WeeklyRuleObligationV2(
            rule=RuleReference(rule_id=attempt.rule.rule_id, version=attempt.rule.version),
            scope=attempt.rule.scope,
        ),
    )
    result["remaining_domains"] = tuple(
        dict(slot=d.slot, original_domain_indexes=tuple(range(len(d.options))))
        for d in sorted(domains[len(path) :], key=lambda d: d.slot.canonical_index)
    )
    maximum = 21 * ((2**63 - 1) // 3)
    lo, hi = bounds if bounds is not None else (maximum, maximum)
    result["numeric_bound"] = _metadata(program, attempt) | dict(lower=lo, upper=hi)
    # Exact original measurements remain in the source-bound request; no asserted
    # digest replaces their independent revalidation and arithmetic.
    result["basis"]["evaluationDigest"] = (
        "0" * 64
        if bounds is None
        else _digest(v2.WeeklyNumericBoundV2.model_validate(result["numeric_bound"]))
    )
    return result


def _envelope(material: dict[str, Any], *, ordered_domains=None) -> int:
    domains = material["original_domains"] if ordered_domains is None else ordered_domains
    # Bound all 22 possible suffix scopes, including the longest option references.
    longest = tuple(
        max(range(len(d.options)), key=lambda j: len(_bytes(d.options[j]))) if d.options else 0
        for d in domains
    )
    suffix = 0
    if all(d.options for d in domains):
        suffix = len(_bytes(_scope(domains, longest))) + 1024
        suffix += sum(
            len(_bytes(_scope(domains, longest[:i], tuple(range(len(domains[i].options)))))) + 1024
            for i in range(21)
        )
    # Fixed limit-metadata allowance avoids circular budget charges depending on
    # the decimal spelling of the very limit being tested.
    return len(_bytes({k: v for k, v in material.items() if k != "limits"})) + suffix + 10240


def _seal(
    payload: dict[str, Any], sequence: int, accounting: v2.WeeklyAccountingV2
) -> v2.WeeklyProofEventV2:
    cls = {
        "UNARY_FAILURE": v2.WeeklyUnaryFailureV2,
        "DAY_FAILURE": v2.WeeklyDayFailureV2,
        "COMPLETED_LEAF": v2.WeeklyCompletedLeafV2,
        "FORWARD_CHECK_CLOSURE": v2.WeeklyForwardCheckClosureV2,
    }[payload["kind"]]
    previous = accounting.proof_bytes_written
    size = 0
    for _ in range(8):
        fields = accounting.model_dump()
        fields["proof_records_written"] = sequence + 1
        fields["proof_bytes_written"] = previous + size
        # Positive bytes are required while solving the decimal-length fixed point.
        fields["proof_bytes_written"] = max(1, fields["proof_bytes_written"])
        event = cls.model_validate(
            payload
            | dict(sequence=sequence, accounting=v2.WeeklyAccountingV2.model_validate(fields))
        )
        actual = len(_bytes(event)) + 1
        if actual == size:
            return event
        size = actual
    raise ValueError("proof encoding did not reach its bounded byte fixed point")


def _incremental_initial_cost(manifest, domains) -> dict[str, int]:
    """Protocol metadata costs only; no aggregate state is used by the checker."""
    required = {ref for domain in domains for ref in domain.options}
    return dict(
        heuristic_evaluations=1
        + sum(
            1 + len(option.combination.components)
            for option in manifest.request.source.daily_source.options
            if option.reference in required
        )
    )


def _incremental_update_cost(manifest, ref) -> dict[str, int]:
    option = next(o for o in manifest.request.source.daily_source.options if o.reference == ref)
    # Prepay publication AND exact rollback, even on success/interruption. Component
    # occurrences conservatively cover deduplicated recipe updates. No refund.
    return dict(heuristic_evaluations=2 * (1 + len(option.combination.components)))


def _incremental_week_cost(manifest, domains, path) -> dict[str, int]:
    original = {o.reference: o for o in manifest.request.source.daily_source.options}
    return dict(
        heuristic_evaluations=1
        + sum(
            len(original[domains[i].options[p]].combination.components) for i, p in enumerate(path)
        )
    )


def _day(
    program: Any,
    domains: tuple[v2.WeeklyOriginalDomainV2, ...],
    path: tuple[int, ...],
    decisions: dict[str, DailyOptionDecision],
    *,
    incremental: "_IncrementalState | None" = None,
) -> DailyAssignmentEvaluation:
    index = domains[len(path) - 1].slot.canonical_index // 3
    daily = program.days[index]
    selected = {domains[i].slot.canonical_index: domains[i].options[p] for i, p in enumerate(path)}
    chosen = tuple(selected[i] for i in range(index * 3, index * 3 + 3))
    trial = DailyTrial.build(
        dict(
            request_digest=daily.request.content_digest,
            choices=tuple(
                DailyTrialChoice(slot=s, option=r) for s, r in zip(MealSlot, chosen, strict=True)
            ),
        )
    )
    arguments = (
        daily,
        tuple(zip(MealSlot, chosen, strict=True)),
        tuple(decisions[r.option_id].slots[i].status for i, r in enumerate(chosen)),
        trial.content_digest,
        program.day_program,
        _evidence_union(tuple(decisions[r.option_id].combination.evidence for r in chosen)),
    )
    if incremental is None:
        facts, trace, status = _assess_day(*arguments)
    else:
        incremental.bind_path(domains, path)
        facts, trace, status = _evaluate_day(*arguments, quantity=incremental.day_values(index))
    return DailyAssignmentEvaluation(
        trial=trial,
        facts=facts,
        trace=trace,
        status=status,
        explanations=_explanations(daily, trial, trace),
    )


def _nutrient_leaf_cost(strategy) -> dict[str, int]:
    if not isinstance(strategy, v2.WeeklyNutrientSearchStrategyV2):
        return {}
    return dict(
        heuristic_evaluations=sum(
            3 if b.scope == "DAY" else 21 for b in strategy.nutrient_contract.bands
        )
    )


def _nutrient_band_count(strategy) -> int:
    return (
        len(strategy.nutrient_contract.bands)
        if isinstance(strategy, v2.WeeklyNutrientSearchStrategyV2)
        else 0
    )


def _leaf(
    program: Any,
    domains: tuple[v2.WeeklyOriginalDomainV2, ...],
    path: tuple[int, ...],
    decisions: dict[str, DailyOptionDecision],
    days: tuple[DailyAssignmentEvaluation, ...],
    *,
    incremental: "_IncrementalState | None" = None,
    nutrient_contract: "WeeklyNutrientContractV2 | None" = None,
) -> tuple[RuleStatus, str, WeeklyWitness | None, tuple[v2.WeeklyObligationV2, ...]]:
    manifest = program.manifest
    request = manifest.request
    trial = WeeklyTrial.build(
        dict(
            request_digest=request.content_digest,
            week_id=request.week_id,
            week_version=request.week_version,
            start_date=request.start_date,
            choices=tuple(
                WeeklyTrialChoice(day=d.slot.day, slot=d.slot.slot, option=d.options[p])
                for d, p in sorted(
                    zip(domains, path, strict=True), key=lambda pair: pair[0].slot.canonical_index
                )
            ),
        )
    )
    selected = {c.option.option_id for c in trial.choices}
    arguments = (program, trial, tuple(decisions[key] for key in sorted(selected)))
    days = tuple(
        sorted(
            days,
            key=lambda e: next(
                i
                for i, daily in enumerate(program.days)
                if daily.request.content_digest == e.trial.request_digest
            ),
        )
    )
    canonical_domains = sorted(domains, key=lambda d: d.slot.canonical_index)
    assessed_days = tuple(
        (canonical_domains[i * 3].slot.day, program.days[i].content_digest, e)
        for i, e in enumerate(days)
    )
    if incremental is None:
        records, facts, trace, _, status = _assess_week(*arguments, assessed_days=assessed_days)
    else:
        incremental.bind_path(domains, path)
        records, facts, trace, _, status = _evaluate_week(
            *arguments, assessed_days=assessed_days, aggregates=incremental.week_values()
        )
    digest = _digest((trial, *(r[2] for r in records), *facts, trace))
    unresolved: list[v2.WeeklyObligationV2] = []
    for scope, evaluations in (
        (RuleScope.DAY, tuple(e.trace for e in days)),
        (RuleScope.WEEK, (trace,)),
    ):
        for t in evaluations:
            if not t.evaluations:
                unresolved.append(
                    v2.WeeklyPrerequisiteObligationV2(
                        prerequisite="MANDATORY_CHECK_COVERAGE", scope=scope
                    )
                )
            for e in t.evaluations:
                if e.applicability is ApplicabilityStatus.UNKNOWN or (
                    e.applicability is ApplicabilityStatus.APPLICABLE
                    and e.status is RuleStatus.UNKNOWN
                ):
                    unresolved.append(
                        v2.WeeklyRuleObligationV2(
                            rule=RuleReference(rule_id=e.rule.rule_id, version=e.rule.version),
                            scope=scope,
                        )
                    )
    for c in trial.choices:
        decision = decisions[c.option.option_id]
        source_option = next(
            o for o in request.source.daily_source.options if o.reference == c.option
        )
        if decision.combination.status is RuleStatus.UNKNOWN:
            unresolved.append(
                v2.WeeklyPrerequisiteObligationV2(prerequisite="COMPOSITION_AUTHORITY")
            )
        if c.option.portion_state is not PortionState.FIXED:
            unresolved.append(v2.WeeklyPrerequisiteObligationV2(prerequisite="FIXED_CONFIGURATION"))
        if source_option.suitability is None or not source_option.suitability.complete:
            unresolved.append(v2.WeeklyPrerequisiteObligationV2(prerequisite="SLOT_SUITABILITY"))
    if nutrient_contract is not None:
        from savora_ai.core.reasoning.nutrients_v2 import evaluate_weekly_nutrients

        nutrient_assessment = evaluate_weekly_nutrients(request, trial, contract=nutrient_contract)
        digest = _digest((digest, nutrient_assessment))
        statuses = (status, nutrient_assessment.status)
        status = (
            RuleStatus.FAIL
            if RuleStatus.FAIL in statuses
            else RuleStatus.UNKNOWN
            if RuleStatus.UNKNOWN in statuses
            else RuleStatus.PASS
        )
        bands = {b.band_id: b for b in nutrient_contract.bands}
        unresolved.extend(
            v2.WeeklyNutrientObligationV2(band_id=a.band_id, scope=bands[a.band_id].scope)
            for a in nutrient_assessment.assessments
            if a.status is RuleStatus.UNKNOWN
        )
    unique = tuple({o.model_dump_json(): o for o in unresolved}.values())
    if status is not RuleStatus.PASS:
        return status, digest, None, unique
    assignment = WeeklyAssignment.build(
        dict(
            request_digest=request.content_digest,
            week_id=request.week_id,
            week_version=request.week_version,
            start_date=request.start_date,
            source=_weekly_source_reference(request.source),
            daily_source=request.source.expected_daily_source,
            context_digest=request.context_digest,
            days=tuple(
                WeeklyDayAssignment(
                    day=d, trial=e.trial, assignment=_assignment(program.days[i], e.trial)
                )
                for i, (d, _, e) in enumerate(records)
            ),
        )
    )
    return (
        status,
        digest,
        WeeklyWitness(
            trial=trial,
            assignment=assignment,
            days=tuple(
                WeeklyWitnessDay(day=d, manifest_digest=h, evaluation=e) for d, h, e in records
            ),
            facts=facts,
            trace=trace,
            explanations=_week_explanations(manifest, trial, trace),
        ),
        unique,
    )


@dataclass(frozen=True)
class ProofCheckV2:
    outcome: DailyOutcome
    witness: WeeklyWitness | None
    work: v2.WeeklyWorkV2
    complete: bool
    deadline_checkpoint: int | None
    deadline_observation: float | None
    preparation: dict[str, Any] | None = None


def check_weekly_proof_v2(
    manifest: ExpectedWeekCheckManifest,
    candidates: tuple[CandidateRecipeFacts, ...],
    certificate: v2.WeeklySearchCertificateV2,
    *,
    termination: v2.WeeklyInterruptionV2 | None,
    execution_deadline_checkpoint: int | None = None,
    execution_deadline_observation: float | None = None,
    verification_deadline_checkpoint: int | None = None,
    verification_deadline_observation: float | None = None,
    clock: Callable[[], float] | None = None,
    reuse_preparation: bool = False,
    preparation_cache_entries: int = 1,
) -> ProofCheckV2:
    """Reconstruct proof independently; never calls the v2 executor or v1 replay.

    External callers must select original source/context/KB/candidates independently.
    The computed DTO verifies internal correctness, not the authenticity of retained
    unsigned material. This function also rebuilds the entire mandatory manifest.
    """
    manifest = ExpectedWeekCheckManifest.model_validate(manifest)
    accepted, pool = _admit(
        manifest.request,
        candidates,
        manifest.knowledge,
        manifest.request.source.daily_source.context,
        manifest.request.source,
    )
    if accepted != manifest:
        raise ValueError("v2 proof manifest differs from complete accepted inventory")
    certificate = v2.WeeklySearchCertificateV2.model_validate(certificate)
    limits = certificate.limits
    material = _material(accepted, pool, certificate.identity.strategy, limits)
    for field, expected in material.items():
        if getattr(certificate, field) != expected:
            raise ValueError("v2 proof differs from independently reconstructed " + field)
    for checkpoint, observed in (
        (execution_deadline_checkpoint, execution_deadline_observation),
        (verification_deadline_checkpoint, verification_deadline_observation),
    ):
        if (checkpoint is None) != (observed is None) or (
            observed is not None and (limits.deadline is None or observed < limits.deadline)
        ):
            raise ValueError("v2 deadline checkpoint requires an expired observation")
    if (termination == "DEADLINE") != (execution_deadline_checkpoint is not None):
        raise ValueError("v2 execution deadline termination binding differs")

    # Independently derive selection order from full original domain cardinalities;
    # never import the executor's ordering helper or trust event selection claims.
    strategy = certificate.identity.strategy
    priority = isinstance(
        strategy, (v2.WeeklyPrioritySearchStrategyV2, v2.WeeklyNutrientSearchStrategyV2)
    )
    ordered = priority or (
        strategy.value_order == "OPTION_ID_DESC"
        or strategy.variable_order == "STATIC_MRV_ORIGINAL_DOMAINS"
    )
    reverse = strategy.value_order == "OPTION_ID_DESC"
    priority_indexes = None

    def value_rank(depth: int, index: int) -> int:
        if priority_indexes is not None:
            return priority_indexes[depth].index(index)
        return sizes[depth] - 1 - index if reverse else index

    expected_proof_policy = (
        "synthetic-weekly-nutrient-priority-coverage.v2"
        if isinstance(strategy, v2.WeeklyNutrientSearchStrategyV2)
        else "synthetic-weekly-priority-coverage.v2"
        if priority
        else "synthetic-weekly-ordered-coverage.v2"
        if ordered
        else "synthetic-weekly-coverage-declarations.v2"
    )
    if certificate.proof_policy_version != expected_proof_policy:
        raise ValueError("v2 coverage policy does not match exact execution strategy")
    canonical = material["original_domains"]
    selection = list(range(21))
    domains = canonical
    sizes = tuple(len(d.options) for d in domains)
    weights = tuple(prod(sizes[i + 1 :]) for i in range(21))
    total = prod(sizes)
    forward = certificate.identity.strategy.policy in (
        v2.WeeklyStrategyPolicyV2.FORWARD_CHECKING,
        v2.WeeklyStrategyPolicyV2.INCREMENTAL_FORWARD_CHECKING,
        v2.WeeklyStrategyPolicyV2.STATIC_MRV_FORWARD_CHECKING,
        v2.WeeklyStrategyPolicyV2.STATIC_MRV_INCREMENTAL_FORWARD_CHECKING,
    )
    incremental = certificate.identity.strategy.policy in (
        v2.WeeklyStrategyPolicyV2.INCREMENTAL,
        v2.WeeklyStrategyPolicyV2.INCREMENTAL_FORWARD_CHECKING,
        v2.WeeklyStrategyPolicyV2.STATIC_MRV_INCREMENTAL,
        v2.WeeklyStrategyPolicyV2.STATIC_MRV_INCREMENTAL_FORWARD_CHECKING,
    )
    accounting_policy = (
        "synthetic-weekly-ordered-work-reservation.v2"
        if ordered
        else "synthetic-weekly-incremental-work-reservation.v2"
        if incremental
        else "synthetic-weekly-forward-work-reservation.v2"
        if forward
        else "synthetic-weekly-work-reservation.v2"
    )
    # Independent accounting arithmetic; no executor meter/reserve implementation.
    used = {field: 0 for field in v2.WeeklyWorkV2.model_fields}
    checked = dict(used)
    operations = nodes = backtracks = checkpoints = slots = byte_reservations = written = 0
    consumed = covered = 0
    branches: list[v2.WeeklyFrontierBranchV2] = []
    unknown = False
    witness = None
    stop = None
    expired_checkpoint = expired_reading = None

    def account() -> v2.WeeklyAccountingV2:
        return v2.WeeklyAccountingV2(
            policy=accounting_policy,
            logical_nodes=nodes,
            backtracks=backtracks,
            execution_work=v2.WeeklyWorkV2(**used),
            reserved_work=v2.WeeklyWorkV2(
                **{
                    key: operations if key == "proof_verification_steps" else 2 * val
                    for key, val in used.items()
                }
            ),
            proof_records_reserved=slots,
            proof_records_written=consumed,
            proof_bytes_reserved=byte_reservations,
            proof_bytes_written=written,
            checkpoints=checkpoints,
        )

    def permit(
        cost: dict[str, int],
        *,
        node: bool = False,
        payload: dict[str, Any] | None = None,
        envelope: int = 0,
    ) -> bool:
        nonlocal \
            operations, \
            nodes, \
            checkpoints, \
            slots, \
            byte_reservations, \
            stop, \
            expired_checkpoint, \
            expired_reading
        checkpoints += 1
        if execution_deadline_checkpoint == checkpoints:
            stop = "DEADLINE"
            return False
        if node and nodes == limits.max_nodes:
            stop = "NODE_BUDGET"
            return False
        reasons = dict(
            candidate_preparations="PREPARATION_BUDGET",
            combination_preparations="PREPARATION_BUDGET",
            predicate_obligations="PREDICATE_BUDGET",
            day_assessments="DAY_BUDGET",
            week_assessments="WEEK_BUDGET",
            heuristic_evaluations="HEURISTIC_BUDGET",
        )
        for key in used:
            needed = (
                operations + 1
                if key == "proof_verification_steps"
                else 2 * (used[key] + cost.get(key, 0))
            )
            if needed > getattr(limits.max_reserved_work, key):
                stop = reasons.get(key, "VERIFICATION_BUDGET")
                return False
        extra = _charge(payload) if payload is not None else 0
        if payload is not None and (
            slots + 1 > limits.max_proof_records
            or slots >= 480
            or len(payload.get("obligations", ())) > 256
            or len(payload.get("basis", {}).get("evidence", ())) > 64
            or len(payload.get("numeric_bound", {}).get("applicability_evidence", ())) > 64
            or len(payload.get("numeric_bound", {}).get("required_observations", ())) > 256
        ):
            stop = "PROOF_RECORD_BUDGET"
            return False
        if byte_reservations + extra + envelope > limits.max_proof_bytes:
            stop = "PROOF_BYTE_BUDGET"
            return False
        # A verifier deadline can ONLY downgrade to an incomplete TIMEOUT. Never
        # inspect a claimed verified flag or return an unchecked successful witness.
        reading = clock() if clock is not None and limits.deadline is not None else None
        if verification_deadline_checkpoint == operations + 1 or (
            reading is not None and limits.deadline is not None and reading >= limits.deadline
        ):
            expired_checkpoint = operations + 1
            expired_reading = reading if reading is not None else verification_deadline_observation
            return False
        operations += 1
        nodes += int(node)
        slots += int(payload is not None)
        byte_reservations += extra + envelope
        for key, value in cost.items():
            used[key] += value
            checked[key] += value
        checked["proof_verification_steps"] += 1
        return True

    def consume(
        payload: dict[str, Any], unresolved: tuple[v2.WeeklyObligationV2, ...] = ()
    ) -> None:
        nonlocal consumed, written, covered
        event = _seal(payload, consumed, account())
        if consumed >= len(certificate.events) or event != certificate.events[consumed]:
            raise ValueError("v2 event differs from independent evaluation/order/accounting")
        scope = event.scope
        path = tuple(c.original_domain_index for c in scope.path)
        if tuple(c.slot.canonical_index for c in scope.path) != tuple(selection[: len(path)]):
            raise ValueError("v2 path differs from independently selected original-domain order")
        start = sum(value_rank(i, p) * weights[i] for i, p in enumerate(path))
        width = prod(sizes[len(path) :])
        if scope.extent == "SLOT_ALTERNATIVES":
            if scope.decision_slot != domains[len(path)].slot:
                raise ValueError("unary exclusion is not at the independently selected decision")
            original_index = scope.original_domain_indexes[0]
            start += (value_rank(len(path), original_index)) * weights[len(path)]
            width = weights[len(path)]
        if start != covered or width <= 0:
            raise ValueError("v2 terminal cover has a gap, overlap or noncanonical interval")
        covered += width
        state = (
            v2.WeeklyFrontierStateV2.EXCLUSION_DECLARED
            if payload["kind"] != "COMPLETED_LEAF"
            else (
                v2.WeeklyFrontierStateV2.UNRESOLVED_UNKNOWN
                if payload["declared_status"] is RuleStatus.UNKNOWN
                else v2.WeeklyFrontierStateV2.EXPLORED
            )
        )
        branches.append(
            v2.WeeklyFrontierBranchV2(
                scope=scope,
                state=state,
                supporting_event=consumed,
                unresolved_obligations=unresolved
                if state is v2.WeeklyFrontierStateV2.UNRESOLVED_UNKNOWN
                else (),
            )
        )
        consumed += 1
        written = event.accounting.proof_bytes_written

    rules = _mandatory_checks(manifest.knowledge, manifest.request.source.daily_source.context)
    recipe_cost = len(pool) * sum(r.scope in (RuleScope.PROFILE, RuleScope.RECIPE) for r in rules)
    option_cost = recipe_cost + sum(r.scope is RuleScope.COMBINATION for r in rules)
    decisions: dict[str, DailyOptionDecision] = {}
    preparation: _PreparedRecipePool | None = None
    ordering_ready = not ordered or permit(dict(heuristic_evaluations=21 + sum(sizes)))
    if priority and ordering_ready:
        priority_indexes = (
            tuple(
                tuple(
                    index
                    for _, _, index in sorted(
                        (-entry.priority, entry.option.option_id, index)
                        for index, entry in enumerate(slot.entries)
                    )
                )
                for slot in strategy.declaration.slots
            )
            if isinstance(
                strategy, (v2.WeeklyPrioritySearchStrategyV2, v2.WeeklyNutrientSearchStrategyV2)
            )
            else None
        )
    if ordering_ready and strategy.variable_order == "STATIC_MRV_ORIGINAL_DOMAINS":
        selection = sorted(selection, key=lambda index: (len(canonical[index].options), index))
        domains = tuple(canonical[index] for index in selection)
        sizes = tuple(len(d.options) for d in domains)
        weights = tuple(prod(sizes[i + 1 :]) for i in range(21))
    if ordering_ready and permit(
        dict(candidate_preparations=len(pool), predicate_obligations=recipe_cost),
        envelope=_envelope(material, ordered_domains=domains) if ordered else _envelope(material),
    ):
        if reuse_preparation:
            preparation = _preparation_session(manifest, pool, preparation_cache_entries)
            preparation.assess()
        else:
            filter_candidates(
                pool,
                knowledge=manifest.knowledge,
                context=manifest.request.source.daily_source.context,
            )
        refs = sorted(
            {o.option_id: o for d in domains for o in d.options}.values(), key=lambda o: o.option_id
        )
        for ref in refs:
            if not permit(
                dict(
                    candidate_preparations=len(pool),
                    combination_preparations=1,
                    predicate_obligations=option_cost,
                )
            ):
                break
            decisions[ref.option_id] = (
                _prepared_option(manifest, pool, ref, preparation)
                if preparation is not None
                else _prepare_option(manifest, pool, ref)
            )
        else:
            if permit({}):
                program = _compile_week(manifest)
                # Task stack is separate from the executor's recursive DFS. Each
                # task includes immutable path/DAY state; rollback tasks enforce
                # counters without trusting any claimed branch-exhaustion marker.
                tasks: list[tuple[str, tuple[int, ...], tuple[DailyAssignmentEvaluation, ...]]] = []
                ready = not incremental or permit(_incremental_initial_cost(manifest, domains))
                if total and ready:
                    tasks = [("expand", (), ())]
                while tasks and stop is None and expired_checkpoint is None and witness is None:
                    action, path, day_records = tasks.pop()
                    if action == "rollback":
                        backtracks += 1
                        continue
                    if action == "expand":
                        closed = False
                        if forward:
                            for attempt in _attempts(
                                program, domains[len(path)].slot.canonical_index
                            ):
                                template = _forward_payload(
                                    material, domains, path, program, attempt
                                )
                                if not permit(_cost(attempt, domains, path), payload=template):
                                    break
                                bounds = _check_bound(program, domains, path, attempt)
                                if bounds is not None:
                                    consume(
                                        _forward_payload(
                                            material, domains, path, program, attempt, bounds
                                        )
                                    )
                                    closed = True
                                    break
                                # Potential proof storage was reserved before work.
                                # No closure: release unused storage, not work units.
                                slots -= 1
                                byte_reservations -= _charge(template)
                            if stop is not None or expired_checkpoint is not None:
                                break
                        if not closed:
                            tasks.extend(
                                ("choose", (*path, i), day_records)
                                for i in (
                                    reversed(priority_indexes[len(path)])
                                    if priority_indexes is not None
                                    else range(sizes[len(path)])
                                    if reverse
                                    else reversed(range(sizes[len(path)]))
                                )
                            )
                        continue
                    depth = len(path) - 1
                    ref = domains[depth].options[path[-1]]
                    decision = decisions[ref.option_id]
                    if (
                        decision.slots[domains[depth].slot.canonical_index % 3].status
                        is RuleStatus.FAIL
                    ):
                        scope = _scope(domains, path[:-1], (path[-1],))
                        payload = _payload(material, "UNARY_FAILURE", scope)
                        if not permit({}, payload=payload):
                            break
                        consume(_payload(material, "UNARY_FAILURE", scope, _digest(decision)))
                        continue
                    if not permit({}, node=True):
                        break
                    if incremental and not permit(_incremental_update_cost(manifest, ref)):
                        break
                    tasks.append(("rollback", path, day_records))
                    actual_day = domains[depth].slot.day.day_index
                    if sum(d.slot.day.day_index == actual_day for d in domains[: len(path)]) == 3:
                        scope = _scope(domains, path)
                        if not permit(
                            dict(
                                day_assessments=1,
                                predicate_obligations=len(manifest.day_checks),
                                **(dict(heuristic_evaluations=1) if incremental else {}),
                            ),
                        ):
                            break
                        evaluation = _day(program, domains, path, decisions)
                        day_records = (*day_records, evaluation)
                        if evaluation.status is RuleStatus.FAIL:
                            template = _payload(material, "DAY_FAILURE", scope)
                            if not permit({}, payload=template):
                                break
                            consume(_payload(material, "DAY_FAILURE", scope, _digest(evaluation)))
                            continue
                    if len(path) == 21:
                        scope = _scope(domains, path)
                        template = _payload(material, "COMPLETED_LEAF", scope)
                        if not permit(
                            dict(
                                week_assessments=1,
                                predicate_obligations=len(manifest.required_checks)
                                + _nutrient_band_count(strategy),
                                **_nutrient_leaf_cost(strategy),
                                **(
                                    _incremental_week_cost(manifest, domains, path)
                                    if incremental
                                    else {}
                                ),
                            ),
                            payload=template,
                        ):
                            break
                        status, digest, witness, missing = _leaf(
                            program,
                            domains,
                            path,
                            decisions,
                            day_records,
                            nutrient_contract=(
                                strategy.nutrient_contract
                                if isinstance(strategy, v2.WeeklyNutrientSearchStrategyV2)
                                else None
                            ),
                        )
                        consume(
                            _payload(material, "COMPLETED_LEAF", scope, digest, status), missing
                        )
                        unknown |= status is RuleStatus.UNKNOWN
                    else:
                        tasks.append(("expand", path, day_records))
    if expired_checkpoint is not None:
        return ProofCheckV2(
            DailyOutcome.TIMEOUT,
            None,
            v2.WeeklyWorkV2(**checked),
            False,
            int(expired_checkpoint),
            expired_reading,
            preparation.snapshot() if preparation is not None else None,
        )
    if (
        verification_deadline_checkpoint is not None
        and verification_deadline_checkpoint != operations + 1
    ):
        raise ValueError("verification deadline checkpoint is not reachable")
    if stop != termination or (
        execution_deadline_checkpoint is not None and checkpoints != execution_deadline_checkpoint
    ):
        raise ValueError("v2 termination differs from independently checked resource boundary")
    if consumed != len(certificate.events) or account() != certificate.accounting:
        raise ValueError("v2 final counters/reservations or event count differ")
    # Independently prove all original completions accounted for, even on timeout
    # and early FEASIBLE: terminal intervals plus a canonical unexplored suffix.
    expected_frontier = (
        *branches,
        *(
            _rest(domains, covered, orders=priority_indexes)
            if priority_indexes is not None
            else _rest(domains, covered, reverse=True)
            if reverse
            else _rest(domains, covered)
        ),
    )
    if certificate.frontier != expected_frontier or covered > total:
        raise ValueError("v2 frontier is not the exact original-domain partition")
    # Independent interval algebra also checks the suffix encoder itself. Merely
    # comparing two invocations of the shared stateless encoder is insufficient.
    cursor = 0
    for branch in certificate.frontier:
        prefix = branch.scope.path
        if tuple(c.slot.canonical_index for c in prefix) != tuple(selection[: len(prefix)]):
            raise ValueError(
                "frontier selected slots differ from independently reconstructed order"
            )
        lower = sum(
            value_rank(i, c.original_domain_index) * weights[i] for i, c in enumerate(prefix)
        )
        width = prod(sizes[len(prefix) :])
        if branch.scope.extent == "SLOT_ALTERNATIVES":
            indexes = branch.scope.original_domain_indexes
            ranks = sorted(value_rank(len(prefix), index) for index in indexes)
            if ranks != list(range(ranks[0], ranks[-1] + 1)):
                raise ValueError("frontier alternative interval contains holes")
            if branch.scope.decision_slot != domains[len(prefix)].slot:
                raise ValueError("frontier decision slot differs from independent selection")
            first_rank = ranks[0]
            lower += first_rank * weights[len(prefix)]
            width = len(indexes) * weights[len(prefix)]
        if lower != cursor or width <= 0:
            raise ValueError("frontier interval has an overlap or coverage gap")
        cursor += width
    if cursor != total:
        raise ValueError("frontier partition does not cover all original completions")
    if stop is None and witness is None and covered != total:
        raise ValueError("v2 claimed exhaustion leaves uncovered completions")
    outcome = (
        DailyOutcome.TIMEOUT
        if stop
        else DailyOutcome.FEASIBLE
        if witness
        else DailyOutcome.INSUFFICIENT_DATA
        if unknown
        else DailyOutcome.INFEASIBLE
    )
    # Check the final in-flight operation/encoding as well as stage entry points.
    reading = (
        clock()
        if clock is not None and limits.deadline is not None
        else verification_deadline_observation
    )
    if reading is not None and limits.deadline is not None and reading >= limits.deadline:
        return ProofCheckV2(
            DailyOutcome.TIMEOUT,
            None,
            v2.WeeklyWorkV2(**checked),
            False,
            operations + 1,
            reading,
            preparation.snapshot() if preparation is not None else None,
        )
    return ProofCheckV2(
        outcome,
        witness if not stop else None,
        v2.WeeklyWorkV2(**checked),
        True,
        None,
        None,
        preparation.snapshot() if preparation is not None else None,
    )
