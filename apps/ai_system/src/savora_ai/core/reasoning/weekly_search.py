"""Bounded chronological WEEK kernel; replay proves coverage from original inputs."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from savora_ai.core.reasoning.day_checks import _assess_day, _option_order
from savora_ai.core.reasoning.filtering import filter_candidates
from savora_ai.core.reasoning.manifest import _mandatory_checks
from savora_ai.core.reasoning.week_checks import _assess_week, _compile_week, _prepare_option
from savora_ai.schemas.candidates import CandidateRecipeFacts
from savora_ai.schemas.daily import DailyOutcome, MealSlot
from savora_ai.schemas.daily_solver import (
    DailyAssignmentEvaluation,
    DailyOptionDecision,
    DailyTrial,
    DailyTrialChoice,
    _assignment,
    _explanations,
)
from savora_ai.schemas.filtering import _evidence_union
from savora_ai.schemas.knowledge import RuleScope
from savora_ai.schemas.reasoning import RuleStatus
from savora_ai.schemas.weekly import (
    ExpectedWeekCheckManifest,
    WeeklyAssignment,
    WeeklyConstraintDiagnostic,
    WeeklyDayAssignment,
    WeeklySearchLimits,
    WeeklyTrial,
    WeeklyTrialChoice,
    _weekly_source_reference,
)
from savora_ai.schemas.weekly_evaluation import _week_explanations
from savora_ai.schemas.weekly_search import (
    Termination,
    WeeklyCoverageRecord,
    WeeklyPreparationProof,
    WeeklySearchCertificate,
    WeeklySearchStatistics,
    WeeklyWitness,
    WeeklyWitnessDay,
)


def _encoded(value: BaseModel | tuple[BaseModel, ...]) -> bytes:
    body = (
        value.model_dump(mode="json", by_alias=True)
        if isinstance(value, BaseModel)
        else [v.model_dump(mode="json", by_alias=True) for v in value]
    )
    # Ordered arrays matter for a coverage transcript. Do not use snapshot's unordered hash.
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(value: BaseModel | tuple[BaseModel, ...]) -> str:
    return hashlib.sha256(_encoded(value)).hexdigest()


@dataclass(frozen=True)
class _Run:
    certificate: WeeklySearchCertificate
    outcome: DailyOutcome
    witness: WeeklyWitness | None
    diagnostics: tuple[WeeklyConstraintDiagnostic, ...]
    prepared_at: float
    finished_at: float


def _execute(
    manifest: ExpectedWeekCheckManifest,
    candidates: tuple[CandidateRecipeFacts, ...],
    limits: WeeklySearchLimits,
    *,
    clock: Callable[[], float] | None = None,
    stop_at: int | None = None,
) -> _Run:
    request = manifest.request
    context = request.source.daily_source.context
    days = sorted(request.days, key=lambda d: d.day.day_index)
    slots = tuple(MealSlot)
    domains = tuple(
        tuple(sorted(next(x for x in d.domains if x.slot is s).options, key=_option_order))
        for d in days
        for s in slots
    )
    required = sorted(
        {r.option_id: r for domain in domains for r in domain}.values(), key=_option_order
    )
    rules = _mandatory_checks(manifest.knowledge, context)
    recipe_cost = len(candidates) * sum(
        r.scope in (RuleScope.PROFILE, RuleScope.RECIPE) for r in rules
    )
    combination_cost = recipe_cost + sum(r.scope is RuleScope.COMBINATION for r in rules)
    preparation: list[WeeklyPreparationProof] = []
    decisions: list[DailyOptionDecision] = []
    records: list[WeeklyCoverageRecord] = []
    diagnostics: list[WeeklyConstraintDiagnostic] = []
    path: list[int] = []
    cursors: list[int] = []
    termination: Termination | None = None
    deadline_checkpoint = None
    checkpoints = proof_bytes = nodes = predicates = batches = 0
    day_evaluations = week_evaluations = cache_peak = cache_hits = 0
    known = unknown = backtracks = pruned = 0
    recipe_digest = None
    witness = None

    def checkpoint() -> bool:
        nonlocal checkpoints, termination, deadline_checkpoint
        checkpoints += 1
        expired = stop_at == checkpoints or (
            clock is not None and limits.deadline is not None and clock() >= limits.deadline
        )
        if expired:
            termination = "DEADLINE"
            deadline_checkpoint = checkpoints
        return not expired

    def reserve(reason: Termination, used: int, amount: int, maximum: int) -> bool:
        nonlocal termination
        if used + amount > maximum:
            termination = reason
            return False
        return True

    def proof_room(item: BaseModel) -> bool:
        count = len(preparation) + len(records) + (recipe_digest is not None)
        return reserve("PROOF_RECORD_BUDGET", count, 1, limits.max_proof_records) and reserve(
            "PROOF_BYTE_BUDGET", proof_bytes, len(_encoded(item)) + 1, limits.max_proof_bytes
        )

    def diagnostic(stage: str, status: RuleStatus, code: str) -> None:
        if status is not RuleStatus.PASS and len(diagnostics) < limits.max_diagnostics:
            diagnostics.append(
                WeeklyConstraintDiagnostic.model_validate(
                    dict(
                        request_digest=request.content_digest,
                        week_id=request.week_id,
                        week_version=request.week_version,
                        stage=stage,
                        code=code,
                        message="Synthetic evaluation; certificate retains complete obligations",
                        status=status,
                        evidence=_evidence_union((context.evidence, manifest.knowledge.evidence)),
                    )
                )
            )

    # Reserve both the execution and the independent output-verification passes.
    # Reserve 4096 bytes for fixed certificate metadata, then the 64-byte recipe digest.
    # Per-record charges include a separator and worst-case status spelling.
    if (
        checkpoint()
        and reserve(
            "PREDICATE_BUDGET", predicates, 2 * recipe_cost, limits.max_predicate_evaluations
        )
        and reserve("PROOF_RECORD_BUDGET", 0, 1, limits.max_proof_records)
        and reserve("PROOF_BYTE_BUDGET", 0, 4160, limits.max_proof_bytes)
    ):
        recipes = filter_candidates(candidates, knowledge=manifest.knowledge, context=context)
        recipe_digest = _digest(recipes)
        proof_bytes += 4160
        predicates += 2 * recipe_cost
        batches += 2
        for decision in recipes.decisions:
            diagnostic("RECIPE", decision.status, decision.resolution.manifest.candidate_id)
        for ref in required:
            if (
                not checkpoint()
                or not reserve(
                    "PREPROCESSING_BUDGET", 2 * len(decisions), 2, limits.max_option_evaluations
                )
                or not reserve(
                    "PREDICATE_BUDGET",
                    predicates,
                    2 * combination_cost,
                    limits.max_predicate_evaluations,
                )
            ):
                break
            placeholder = WeeklyPreparationProof(
                option_id=ref.option_id,
                decision_digest="0" * 64,
                slot_statuses=(RuleStatus.UNKNOWN,) * 3,
            )
            # Reserve the maximum spelling size before evaluation. PASS/FAIL consume
            # the same charged envelope as UNKNOWN; exact budget boundaries are stable.
            if not proof_room(placeholder):
                break
            decision = _prepare_option(manifest, candidates, ref)
            decisions.append(decision)
            stamp = WeeklyPreparationProof(
                option_id=ref.option_id,
                decision_digest=_digest(decision),
                slot_statuses=tuple(s.status for s in decision.slots),
            )
            preparation.append(stamp)
            proof_bytes += len(_encoded(placeholder)) + 1
            predicates += 2 * combination_cost
            batches += 2
            diagnostic("COMBINATION", decision.combination.status, ref.option_id)
    if termination is None:
        checkpoint()  # Compilation is another cooperative stage boundary.
    program = _compile_week(manifest) if termination is None else None
    prepared_at = clock() if clock is not None else 0.0
    by_id = {d.option.option_id: d for d in decisions}
    cache: dict[tuple[int, tuple[str, ...]], DailyAssignmentEvaluation] = {}
    active_days: dict[int, DailyAssignmentEvaluation] = {}

    def record_template(kind: str) -> WeeklyCoverageRecord:
        return WeeklyCoverageRecord.model_validate(
            dict(kind=kind, path=tuple(path), evaluation_digest="0" * 64)
        )

    def assess_day(index: int) -> DailyAssignmentEvaluation | None:
        nonlocal day_evaluations, predicates, cache_peak, cache_hits, proof_bytes
        assert program is not None
        template = record_template("DAY")
        if not checkpoint() or not proof_room(template):
            return None
        chosen = tuple(domains[i][path[i]] for i in range(index * 3, index * 3 + 3))
        key = (index, tuple(r.option_id for r in chosen))
        evaluation = cache.get(key)
        if evaluation is None:
            if not reserve(
                "DAY_BUDGET", day_evaluations, 2, limits.max_day_evaluations
            ) or not reserve(
                "PREDICATE_BUDGET",
                predicates,
                2 * len(manifest.day_checks),
                limits.max_predicate_evaluations,
            ):
                return None
            daily = program.days[index]
            trial = DailyTrial.build(
                dict(
                    request_digest=daily.request.content_digest,
                    choices=tuple(
                        DailyTrialChoice(slot=s, option=r)
                        for s, r in zip(slots, chosen, strict=True)
                    ),
                )
            )
            facts, trace, status = _assess_day(
                daily,
                tuple((s, r) for s, r in zip(slots, chosen, strict=True)),
                tuple(by_id[r.option_id].slots[i].status for i, r in enumerate(chosen)),
                trial.content_digest,
                program.day_program,
                _evidence_union(tuple(by_id[r.option_id].combination.evidence for r in chosen)),
            )
            evaluation = DailyAssignmentEvaluation(
                trial=trial,
                facts=facts,
                trace=trace,
                status=status,
                explanations=_explanations(daily, trial, trace),
            )
            day_evaluations += 2
            predicates += 2 * len(manifest.day_checks)
            if limits.max_cache_entries:
                if len(cache) == limits.max_cache_entries:
                    del cache[next(iter(cache))]
                cache[key] = evaluation
                cache_peak = max(cache_peak, len(cache))
        else:
            cache_hits += 1
        records.append(
            WeeklyCoverageRecord(
                kind="DAY", path=tuple(path), evaluation_digest=_digest(evaluation)
            )
        )
        proof_bytes += len(_encoded(template)) + 1
        diagnostic("DAY", evaluation.status, "DAY_" + str(index + 1))
        return evaluation

    def assess_leaf() -> RuleStatus | None:
        nonlocal week_evaluations, predicates, proof_bytes, witness
        assert program is not None
        template = record_template("LEAF")
        if (
            not checkpoint()
            or not reserve("WEEK_BUDGET", week_evaluations, 2, limits.max_week_evaluations)
            or not reserve(
                "PREDICATE_BUDGET",
                predicates,
                2 * len(manifest.required_checks),
                limits.max_predicate_evaluations,
            )
            or not proof_room(template)
        ):
            return None
        choices = tuple(
            WeeklyTrialChoice(day=days[i // 3].day, slot=slots[i % 3], option=domains[i][p])
            for i, p in enumerate(path)
        )
        trial = WeeklyTrial.build(
            dict(
                request_digest=request.content_digest,
                week_id=request.week_id,
                week_version=request.week_version,
                start_date=request.start_date,
                choices=choices,
            )
        )
        selected_ids = {c.option.option_id for c in choices}
        selected = tuple(d for d in decisions if d.option.option_id in selected_ids)
        assessed = tuple(
            (days[i].day, program.days[i].content_digest, active_days[i]) for i in range(7)
        )
        day_records, facts, trace, week_status, status = _assess_week(
            program, trial, selected, assessed_days=assessed
        )
        # Bind every DAY, fact and WEEK trace, including known failures and unknowns.
        digest = _digest(tuple([trial, *(r[2] for r in day_records), *facts, trace]))
        records.append(
            WeeklyCoverageRecord(kind="LEAF", path=tuple(path), evaluation_digest=digest)
        )
        proof_bytes += len(_encoded(template)) + 1
        week_evaluations += 2
        predicates += 2 * len(manifest.required_checks)
        diagnostic("WEEK", week_status, "WEEK_TRIAL")
        if status is RuleStatus.PASS:
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
                        for i, (d, _, e) in enumerate(day_records)
                    ),
                )
            )
            witness = WeeklyWitness(
                trial=trial,
                assignment=assignment,
                days=tuple(
                    WeeklyWitnessDay(day=d, manifest_digest=h, evaluation=e)
                    for d, h, e in day_records
                ),
                facts=facts,
                trace=trace,
                explanations=_week_explanations(manifest, trial, trace),
            )
        return status

    def search(depth: int) -> None:
        nonlocal nodes, known, unknown, backtracks, pruned
        cursors.append(0)
        for i, ref in enumerate(domains[depth]):
            cursors[-1] = i
            if by_id[ref.option_id].slots[depth % 3].status is RuleStatus.FAIL:
                cursors[-1] = i + 1
                continue
            if not checkpoint() or not reserve("NODE_BUDGET", nodes, 1, limits.max_nodes):
                return
            nodes += 1
            path.append(i)
            cursors[-1] = i + 1
            status = None
            if depth % 3 == 2:
                day = assess_day(depth // 3)
                if day is None:
                    return
                active_days[depth // 3] = day
                status = day.status
            if status is RuleStatus.FAIL:
                known += 1
                pruned += 1
            elif depth == 20:
                status = assess_leaf()
                if status is None:
                    return
                known += status is RuleStatus.FAIL
                unknown += status is RuleStatus.UNKNOWN
            else:
                search(depth + 1)
            if termination is not None or witness is not None:
                return
            path.pop()
            backtracks += 1
        cursors.pop()

    if termination is None:
        unary = sum(
            by_id[r.option_id].slots[i % 3].status is RuleStatus.FAIL
            for i, domain in enumerate(domains)
            for r in domain
        )
        known += unary
        pruned += unary
        if all(
            any(by_id[r.option_id].slots[i % 3].status is not RuleStatus.FAIL for r in domain)
            for i, domain in enumerate(domains)
        ):
            search(0)
    if termination is None:
        checkpoint()  # Cooperative check after the final in-flight operation.
    outcome = (
        DailyOutcome.TIMEOUT
        if termination is not None
        else DailyOutcome.FEASIBLE
        if witness
        else DailyOutcome.INSUFFICIENT_DATA
        if unknown
        else DailyOutcome.INFEASIBLE
    )
    if outcome is DailyOutcome.TIMEOUT:
        witness = None
    statistics = WeeklySearchStatistics(
        nodes=nodes,
        option_evaluations=2 * len(decisions),
        day_evaluations=day_evaluations,
        week_evaluations=week_evaluations,
        predicate_evaluations=predicates,
        phase3_batch_calls=batches,
        phase3_candidate_evaluations=batches * len(candidates),
        cache_entries=cache_peak,
        cache_hits=cache_hits,
        known_failures=known,
        unknown_hypotheses=unknown,
        backtracks=backtracks,
        pruned_subtrees=pruned,
        proof_records=len(preparation) + len(records) + (recipe_digest is not None),
        proof_bytes=proof_bytes,
        checkpoints=checkpoints,
        exhaustive=termination is None and witness is None,
        termination=termination,
    )
    certificate = WeeklySearchCertificate(
        recipe_proof_digest=recipe_digest,
        preparation=tuple(preparation),
        records=tuple(records),
        frontier=tuple(path),
        next_indexes=tuple(cursors),
        deadline_checkpoint=deadline_checkpoint,
        statistics=statistics,
    )
    return _Run(
        certificate,
        outcome,
        witness,
        tuple(diagnostics),
        prepared_at,
        clock() if clock is not None else 0.0,
    )
