"""Authoritative synthetic DAY evaluation and bounded three-slot backtracking."""

from collections.abc import Callable
from math import isfinite
from time import monotonic
from typing import Self

from pydantic import model_validator

from savora_ai.core.reasoning.combinations import evaluate_combination
from savora_ai.core.reasoning.day_checks import (
    _assess_day,
    _compile_day,
    _derivation_evidence,
    _option_order,
    _slot_status,
)
from savora_ai.core.reasoning.filtering import _FilterRequest, filter_candidates
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.manifest import _KnowledgeContextRequest, _mandatory_checks
from savora_ai.schemas.candidates import CandidateRecipeFacts, RuleContext
from savora_ai.schemas.daily import (
    DailyOutcome,
    DailyPlanningRequest,
    DailySourceSnapshot,
    ExpectedDayCheckManifest,
    MealOptionReference,
    MealSlot,
)
from savora_ai.schemas.daily_solver import (
    DailyAssignmentEvaluation,
    DailyOptionDecision,
    DailySearchLimits,
    DailySearchStatistics,
    DailySlotDecision,
    DailySolveResult,
    DailyTrial,
    DailyTrialChoice,
    _assignment,
    _explanations,
)
from savora_ai.schemas.filtering import _evidence_union
from savora_ai.schemas.knowledge import RuleScope
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot
from savora_ai.schemas.reasoning import RuleStatus


class _DayRequest(_KnowledgeContextRequest):
    request: DailyPlanningRequest
    sources: DailySourceSnapshot

    @model_validator(mode="after")
    def validate_independent_sources(self) -> Self:
        if self.request.source.content_digest != self.sources.content_digest or (
            self.sources.context.content_digest != self.context.content_digest
        ):
            raise ValueError("daily request differs from independently selected source/context")
        _evidence_union((self, _derivation_evidence()))
        return self


class _SolveRequest(_DayRequest, _FilterRequest):
    limits: DailySearchLimits


def _manifest(validated: _DayRequest) -> ExpectedDayCheckManifest:
    knowledge = build_knowledge_snapshot(
        validated.kb,
        expected_digest=validated.context.expected_kb_digest,
    )
    rules = _mandatory_checks(knowledge, validated.context)
    return ExpectedDayCheckManifest.build(
        dict(
            request=validated.request,
            knowledge=knowledge,
            required_checks=tuple(rule for rule in rules if rule.scope is RuleScope.DAY),
            deferred_checks=tuple(rule for rule in rules if rule.scope is RuleScope.WEEK),
        )
    )


def build_day_check_manifest(
    request: DailyPlanningRequest,
    *,
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: DailySourceSnapshot,
) -> ExpectedDayCheckManifest:
    """Rebuild every DAY/WEEK obligation against independent normalized inputs.

    No caller-selected rule list, stage override or affirmative eligibility record is accepted.
    Source loading/authentication remains an upstream responsibility.
    """
    return _manifest(
        _DayRequest.model_validate(
            dict(
                request=request,
                kb=knowledge,
                context=context,
                sources=sources,
            )
        )
    )


def solve_daily_plan(
    request: DailyPlanningRequest,
    *,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: DailySourceSnapshot,
    limits: DailySearchLimits | None = None,
    clock: Callable[[], float] = monotonic,
) -> DailySolveResult:
    """Return first verified feasible day or explicit finite-domain failure.

    Validate external records and call public Phase 3/4 APIs before searching.
    UNKNOWN options remain hypothetical branches; they can never authorize feasibility.
    Limits are cooperative stage boundaries, not interruption of in-flight validation.
    """
    last_time: float | None = None

    def now() -> float:
        nonlocal last_time
        reading = clock()
        if type(reading) not in (int, float):
            raise ValueError("daily clock must return finite monotonic numbers")
        try:
            value = float(reading)
        except OverflowError as error:
            raise ValueError("daily clock must return finite monotonic numbers") from error
        if not isfinite(value):
            raise ValueError("daily clock must return finite monotonic numbers")
        if last_time is not None and value < last_time:
            raise ValueError("daily clock moved backwards")
        last_time = value
        return value

    started = now()
    validated = _SolveRequest.model_validate(
        dict(
            request=request,
            candidates=candidates,
            kb=knowledge,
            context=context,
            sources=sources,
            limits=DailySearchLimits() if limits is None else limits,
        )
    )
    request, context, sources, limits = (
        validated.request,
        validated.context,
        validated.sources,
        validated.limits,
    )
    manifest = _manifest(validated)
    knowledge = manifest.knowledge
    # This public call validates the whole candidate pool even for empty domains/expired deadlines.
    recipes = filter_candidates(validated.candidates, knowledge=knowledge, context=context)
    required = sorted(
        {ref.option_id: ref for domain in request.domains for ref in domain.options}.values(),
        key=_option_order,
    )
    source_options = {option.reference.option_id: option for option in sources.options}
    decisions: list[DailyOptionDecision] = []
    exhaustion = None

    def expired() -> bool:
        return limits.deadline is not None and now() >= limits.deadline

    for ref in required:
        if expired():
            exhaustion = "DEADLINE"
            break
        if len(decisions) >= limits.max_option_evaluations:
            exhaustion = "PREPROCESSING_BUDGET"
            break
        option = source_options[ref.option_id]
        proof = evaluate_combination(
            option.combination,
            candidates=validated.candidates,
            knowledge=knowledge,
            context=context,
            trusted_combination=option.combination,
        )
        decisions.append(
            DailyOptionDecision(
                option=ref,
                combination=proof,
                slots=tuple(
                    DailySlotDecision(
                        slot=slot,
                        status=_slot_status(option, slot, proof.status)[0],
                        reasons=_slot_status(option, slot, proof.status)[1],
                    )
                    for slot in MealSlot
                ),
            )
        )
    prepared_at = now()
    by_id = {item.option.option_id: item for item in decisions}
    domain_map = {domain.slot: domain for domain in request.domains}
    # Only known unary FAIL is pruned. UNKNOWN retains its exact place in the search.
    domains = tuple(
        tuple(
            sorted(
                (
                    ref
                    for ref in domain_map[slot].options
                    if ref.option_id in by_id
                    and by_id[ref.option_id].slots[index].status is not RuleStatus.FAIL
                ),
                key=_option_order,
            )
        )
        for index, slot in enumerate(MealSlot)
    )
    program = _compile_day(manifest)
    evaluations: list[DailyAssignmentEvaluation] = []
    chosen: list[MealOptionReference] = []
    nodes = backtracks = known_rejections = 0
    found = False

    def search(depth: int) -> None:
        nonlocal exhaustion, nodes, backtracks, known_rejections, found
        for ref in domains[depth]:
            if expired():
                exhaustion = "DEADLINE"
                return
            if nodes >= limits.max_nodes:
                exhaustion = "NODE_BUDGET"
                return
            nodes += 1
            chosen.append(ref)
            if depth == 2:
                if len(evaluations) >= limits.max_completed_assignments:
                    exhaustion = "ASSIGNMENT_BUDGET"
                    return
                trial = DailyTrial.build(
                    dict(
                        request_digest=request.content_digest,
                        choices=tuple(
                            DailyTrialChoice(slot=slot, option=option)
                            for slot, option in zip(MealSlot, chosen, strict=True)
                        ),
                    )
                )
                states = tuple(
                    by_id[option.option_id].slots[index].status
                    for index, option in enumerate(chosen)
                )
                facts, trace, status = _assess_day(
                    manifest,
                    tuple((item.slot, item.option) for item in trial.choices),
                    states,
                    trial.content_digest,
                    program,
                    _evidence_union(
                        tuple(by_id[option.option_id].combination.evidence for option in chosen)
                    ),
                )
                evaluations.append(
                    DailyAssignmentEvaluation(
                        trial=trial,
                        facts=facts,
                        trace=trace,
                        status=status,
                        explanations=_explanations(manifest, trial, trace),
                    )
                )
                if status is RuleStatus.PASS:
                    found = True
                    return
                known_rejections += status is RuleStatus.FAIL
            else:
                search(depth + 1)
                if exhaustion is not None or found:
                    return
            chosen.pop()
            backtracks += 1

    if exhaustion is None and all(domains):
        search(0)
    # An empty domain following COMPLETE preparation is a sound unary infeasibility proof.
    unknown = sum(item.status is RuleStatus.UNKNOWN for item in evaluations)
    if found:
        outcome = DailyOutcome.FEASIBLE
    elif exhaustion is not None:
        outcome = DailyOutcome.TIMEOUT
    elif unknown:
        outcome = DailyOutcome.INSUFFICIENT_DATA
    else:
        outcome = DailyOutcome.INFEASIBLE
    searched_at = now()
    return DailySolveResult(
        manifest=manifest,
        limits=limits,
        recipes=recipes,
        options=tuple(decisions),
        evaluations=tuple(evaluations),
        assignment=_assignment(manifest, evaluations[-1].trial) if found else None,
        outcome=outcome,
        statistics=DailySearchStatistics(
            nodes=nodes,
            completed_assignments=len(evaluations),
            backtracks=backtracks,
            known_rejections=known_rejections,
            unknown_branches=unknown,
            option_evaluations=len(decisions),
            phase3_batch_calls=1 + len(decisions),
            phase3_candidate_evaluations=(1 + len(decisions)) * len(validated.candidates),
            search_completed=exhaustion is None,
            exhaustive=exhaustion is None and not found,
            budget_exhaustion=exhaustion,
            preprocessing_seconds=prepared_at - started,
            search_seconds=searched_at - prepared_at,
        ),
    )
