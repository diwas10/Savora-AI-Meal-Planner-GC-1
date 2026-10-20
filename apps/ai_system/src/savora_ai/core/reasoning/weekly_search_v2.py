"""Additive FIRST_FEASIBLE v2: chronological baseline or exact quantity bounds."""

from collections.abc import Callable
from math import isfinite, prod
from time import monotonic
from typing import Any

from savora_ai.core.reasoning.filtering import filter_candidates
from savora_ai.core.reasoning.manifest import _mandatory_checks
from savora_ai.core.reasoning.week_checks import _compile_week, _prepare_option
from savora_ai.core.reasoning.weekly_bounds import _attempts, _cost, _derive_bound
from savora_ai.core.reasoning.weekly_proof_v2 import (
    _admit,
    _charge,
    _day,
    _digest,
    _envelope,
    _forward_payload,
    _leaf,
    _material,
    _payload,
    _preparation_session,
    _prepared_option,
    _rest,
    _scope,
    _seal,
)
from savora_ai.schemas import weekly_search_v2 as v2
from savora_ai.schemas.candidates import CandidateRecipeFacts, RuleContext
from savora_ai.schemas.daily_solver import DailyAssignmentEvaluation, DailyOptionDecision
from savora_ai.schemas.knowledge import RuleScope
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot
from savora_ai.schemas.reasoning import RuleStatus
from savora_ai.schemas.weekly import WeeklyPlanningRequest, WeeklySourceSnapshot
from savora_ai.schemas.weekly_solver_v2 import ComputedWeeklySolveResultV2


def verify_weekly_plan_v2(
    result: ComputedWeeklySolveResultV2,
    *,
    request: WeeklyPlanningRequest,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: WeeklySourceSnapshot,
) -> ComputedWeeklySolveResultV2:
    """Recheck a result against independently selected original input records.

    For untrusted JSON, first use validate_contract_json on the ORIGINAL bytes.
    This exact-material comparison supplements, rather than replaces, backend
    provider authentication/freshness selection.
    """
    manifest, pool = _admit(request, candidates, knowledge, context, sources)
    checked = ComputedWeeklySolveResultV2.model_validate(result)
    if checked.manifest != manifest or checked.candidates != pool:
        raise ValueError("v2 result differs from independently selected original material")
    return checked


def solve_weekly_plan_v2(
    request: WeeklyPlanningRequest,
    *,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: WeeklySourceSnapshot,
    strategy: v2.WeeklySearchStrategyV2,
    limits: v2.WeeklySearchLimitsV2,
    clock: Callable[[], float] = monotonic,
    reuse_preparation: bool = False,
    preparation_cache_entries: int = 1,
) -> ComputedWeeklySolveResultV2:
    """Return only independently checked synthetic v2 outcomes.

    Sources/context/KB/candidate pool must be independently selected by orchestration.
    Only the exact chronological and forward-checking policies execute here.
    max_cache_entries is a capacity, never an instruction to cache.
    See weekly_proof_v2's module contract for semantic work/byte charging. Input
    admission precedes budgets; malformed sources remain errors even at zero work.
    """
    previous: float | None = None

    def now() -> float:
        nonlocal previous
        reading = clock()
        if type(reading) not in (int, float):
            raise ValueError("v2 clock must return finite monotonic numbers")
        try:
            value = float(reading)
        except OverflowError as error:
            raise ValueError("v2 clock must return finite monotonic numbers") from error
        if not isfinite(value) or (previous is not None and value < previous):
            raise ValueError("v2 clock must return finite monotonic numbers")
        previous = value
        return value

    if (
        type(reuse_preparation) is not bool
        or type(preparation_cache_entries) is not int
        or preparation_cache_entries not in (0, 1)
    ):
        raise ValueError("preparation reuse requires exact bool and zero/one capacity")
    now()
    strategy = v2.WeeklySearchStrategyV2.model_validate(strategy)
    limits = v2.WeeklySearchLimitsV2.model_validate(limits)
    manifest, pool = _admit(request, candidates, knowledge, context, sources)
    material = _material(manifest, pool, strategy, limits)
    forward = strategy.policy is v2.WeeklyStrategyPolicyV2.FORWARD_CHECKING
    accounting_policy = (
        "synthetic-weekly-forward-work-reservation.v2"
        if forward
        else "synthetic-weekly-work-reservation.v2"
    )
    domains = material["original_domains"]
    sizes = tuple(len(d.options) for d in domains)
    used = {field: 0 for field in v2.WeeklyWorkV2.model_fields}
    steps = nodes = backtracks = checkpoints = record_reservations = byte_reservations = written = 0
    events: list[v2.WeeklyProofEventV2] = []
    frontier: list[v2.WeeklyFrontierBranchV2] = []
    termination: v2.WeeklyInterruptionV2 | None = None
    deadline_checkpoint = None
    deadline_observation = None
    covered = 0
    found = False

    def snapshot() -> v2.WeeklyAccountingV2:
        reserved = {key: 2 * value for key, value in used.items()}
        reserved["proof_verification_steps"] = steps
        return v2.WeeklyAccountingV2(
            policy=accounting_policy,
            logical_nodes=nodes,
            backtracks=backtracks,
            execution_work=v2.WeeklyWorkV2(**used),
            reserved_work=v2.WeeklyWorkV2(**reserved),
            proof_records_reserved=record_reservations,
            proof_records_written=len(events),
            proof_bytes_reserved=byte_reservations,
            proof_bytes_written=written,
            checkpoints=checkpoints,
        )

    def reserve(
        cost: dict[str, int],
        *,
        node: bool = False,
        payload: dict[str, Any] | None = None,
        envelope: int = 0,
    ) -> bool:
        nonlocal \
            steps, \
            nodes, \
            checkpoints, \
            record_reservations, \
            byte_reservations, \
            termination, \
            deadline_checkpoint, \
            deadline_observation
        checkpoints += 1
        if limits.deadline is not None:
            reading = now()
            if reading >= limits.deadline:
                termination = "DEADLINE"
                deadline_checkpoint, deadline_observation = checkpoints, reading
                return False
        if node and nodes + 1 > limits.max_nodes:
            termination = "NODE_BUDGET"
            return False
        planned = {key: 2 * (used[key] + cost.get(key, 0)) for key in used}
        planned["proof_verification_steps"] = steps + 1
        for key, reason in (
            ("candidate_preparations", "PREPARATION_BUDGET"),
            ("combination_preparations", "PREPARATION_BUDGET"),
            ("predicate_obligations", "PREDICATE_BUDGET"),
            ("day_assessments", "DAY_BUDGET"),
            ("week_assessments", "WEEK_BUDGET"),
            ("heuristic_evaluations", "HEURISTIC_BUDGET"),
            ("proof_verification_steps", "VERIFICATION_BUDGET"),
        ):
            if planned[key] > getattr(limits.max_reserved_work, key):
                termination = reason  # type: ignore[assignment]
                return False
        charge = _charge(payload) if payload is not None else 0
        if payload is not None and (
            record_reservations + 1 > limits.max_proof_records
            or record_reservations >= 480
            or len(payload.get("obligations", ())) > 256
            or len(payload.get("basis", {}).get("evidence", ())) > 64
            or len(payload.get("numeric_bound", {}).get("applicability_evidence", ())) > 64
            or len(payload.get("numeric_bound", {}).get("required_observations", ())) > 256
        ):
            termination = "PROOF_RECORD_BUDGET"
            return False
        if byte_reservations + charge + envelope > limits.max_proof_bytes:
            termination = "PROOF_BYTE_BUDGET"
            return False
        steps += 1
        nodes += int(node)
        record_reservations += int(payload is not None)
        byte_reservations += charge + envelope
        for key, amount in cost.items():
            used[key] += amount
        return True

    def emit(payload: dict[str, Any], missing: tuple[v2.WeeklyObligationV2, ...] = ()) -> None:
        nonlocal written, covered
        event = _seal(payload, len(events), snapshot())
        events.append(event)
        written = event.accounting.proof_bytes_written
        scope = event.scope
        length = len(scope.path) + (scope.extent == "SLOT_ALTERNATIVES")
        covered += prod(sizes[length:])
        state = v2.WeeklyFrontierStateV2.EXCLUSION_DECLARED
        if payload["kind"] == "COMPLETED_LEAF":
            state = (
                v2.WeeklyFrontierStateV2.UNRESOLVED_UNKNOWN
                if payload["declared_status"] is RuleStatus.UNKNOWN
                else v2.WeeklyFrontierStateV2.EXPLORED
            )
        frontier.append(
            v2.WeeklyFrontierBranchV2(
                scope=scope,
                state=state,
                supporting_event=len(events) - 1,
                unresolved_obligations=missing
                if state is v2.WeeklyFrontierStateV2.UNRESOLVED_UNKNOWN
                else (),
            )
        )

    rules = _mandatory_checks(manifest.knowledge, context)
    recipe_cost = len(pool) * sum(r.scope in (RuleScope.PROFILE, RuleScope.RECIPE) for r in rules)
    combination_cost = recipe_cost + sum(r.scope is RuleScope.COMBINATION for r in rules)
    decisions: dict[str, DailyOptionDecision] = {}
    program: Any = None
    preparation = None

    def visit(path: tuple[int, ...], day_records: tuple[DailyAssignmentEvaluation, ...]) -> None:
        nonlocal backtracks, found, record_reservations, byte_reservations
        depth = len(path)
        if forward:
            for attempt in _attempts(program, depth):
                template = _forward_payload(material, domains, path, program, attempt)
                if not reserve(_cost(attempt, domains, path), payload=template):
                    return
                bounds = _derive_bound(program, domains, path, attempt)
                if bounds is not None:
                    emit(_forward_payload(material, domains, path, program, attempt, bounds))
                    return
                record_reservations -= 1
                byte_reservations -= _charge(template)
        for index, ref in enumerate(domains[depth].options):
            chosen = (*path, index)
            decision = decisions[ref.option_id]
            if decision.slots[depth % 3].status is RuleStatus.FAIL:
                scope = _scope(domains, path, (index,))
                template = _payload(material, "UNARY_FAILURE", scope)
                if not reserve({}, payload=template):
                    return
                emit(_payload(material, "UNARY_FAILURE", scope, _digest(decision)))
                continue
            if not reserve({}, node=True):
                return
            assessed = day_records
            if len(chosen) % 3 == 0:
                scope = _scope(domains, chosen)
                if not reserve(
                    dict(day_assessments=1, predicate_obligations=len(manifest.day_checks)),
                ):
                    return
                day = _day(program, domains, chosen, decisions)
                assessed = (*assessed, day)
                if day.status is RuleStatus.FAIL:
                    template = _payload(material, "DAY_FAILURE", scope)
                    if not reserve({}, payload=template):
                        return
                    emit(_payload(material, "DAY_FAILURE", scope, _digest(day)))
                    backtracks += 1
                    continue
            if len(chosen) == 21:
                scope = _scope(domains, chosen)
                template = _payload(material, "COMPLETED_LEAF", scope)
                if not reserve(
                    dict(week_assessments=1, predicate_obligations=len(manifest.required_checks)),
                    payload=template,
                ):
                    return
                status, digest, _, missing = _leaf(program, domains, chosen, decisions, assessed)
                emit(_payload(material, "COMPLETED_LEAF", scope, digest, status), missing)
                found = status is RuleStatus.PASS
            else:
                visit(chosen, assessed)
            if found or termination is not None:
                return
            backtracks += 1

    if reserve(
        dict(candidate_preparations=len(pool), predicate_obligations=recipe_cost),
        envelope=_envelope(material),
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
        required = sorted(
            {r.option_id: r for domain in domains for r in domain.options}.values(),
            key=lambda r: r.option_id,
        )
        for ref in required:
            if not reserve(
                dict(
                    candidate_preparations=len(pool),
                    combination_preparations=1,
                    predicate_obligations=combination_cost,
                )
            ):
                break
            decisions[ref.option_id] = (
                _prepared_option(manifest, pool, ref, preparation)
                if preparation is not None
                else _prepare_option(manifest, pool, ref)
            )
        if termination is None and reserve({}):
            program = _compile_week(manifest)
            if all(sizes):
                visit((), ())
    certificate = v2.WeeklySearchCertificateV2(
        **material,
        events=tuple(events),
        frontier=(*frontier, *_rest(domains, covered)),
        accounting=snapshot(),
    )
    # The schema invokes the independent checker and DERIVES the outcome/witness;
    # execution's local 'found' flag has no result authority.
    preparation_counts = preparation.snapshot() if preparation is not None else None
    preparation = None  # No execution cache is retained during independent verification.
    return ComputedWeeklySolveResultV2.model_validate(
        dict(
            manifest=manifest,
            candidates=pool,
            certificate=certificate,
            termination=termination,
            execution_deadline_checkpoint=deadline_checkpoint,
            execution_deadline_observation=deadline_observation,
            reuse_preparation=reuse_preparation,
            preparation_cache_entries=preparation_cache_entries,
            execution_preparation=preparation_counts,
        ),
        context={"v2_clock": now},
    )
