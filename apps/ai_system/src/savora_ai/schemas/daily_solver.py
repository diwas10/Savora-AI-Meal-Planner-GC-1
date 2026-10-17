"""Computed daily results, bounded search witnesses and strict output verification.

Retained results are evidence records, never authentication or public solver inputs.
Prompt 1's unevaluated DailyPlanningResult remains unchanged.
"""

from itertools import product
from math import prod
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from savora_ai.core.reasoning.day_checks import (
    _assess_day,
    _compile_day,
    _option_order,
    _slot_status,
)
from savora_ai.core.reasoning.evaluation import (
    _applicability,
    _evaluate_resolved_checks,
    _predicate,
)
from savora_ai.core.reasoning.facts import _validated_fact_index
from savora_ai.core.reasoning.manifest import _descriptors_for, _mandatory_checks
from savora_ai.schemas.combination_evaluation import CombinationEligibilityResult
from savora_ai.schemas.daily import (
    AssignedMeal,
    DailyAssignment,
    DailyOutcome,
    DayFact,
    ExpectedDayCheckManifest,
    MealOptionReference,
    MealSlot,
    _DailyModel,
    _DailySnapshot,
    _source_reference,
)
from savora_ai.schemas.filtering import FilterCandidatesResult, _evidence_union
from savora_ai.schemas.knowledge import EvidenceReference, RuleReference, RuleScope, _NonBlank
from savora_ai.schemas.knowledge_base import _ContentDigest
from savora_ai.schemas.reasoning import ApplicabilityStatus, RuleStatus, RuleTrace


class DailySearchLimits(_DailyModel):
    policy_version: Literal["synthetic-daily-search-limits.v1"] = "synthetic-daily-search-limits.v1"
    max_nodes: Annotated[int, Field(ge=0, le=200_000)] = 10_000
    max_completed_assignments: Annotated[int, Field(ge=0, le=4096)] = 256
    max_option_evaluations: Annotated[int, Field(ge=0, le=150)] = 150
    deadline: Annotated[int | float, Field(allow_inf_nan=False)] | None = None


class DailySlotDecision(_DailyModel):
    slot: MealSlot
    status: RuleStatus
    reasons: tuple[_NonBlank, ...]


class DailyOptionDecision(_DailyModel):
    option: MealOptionReference
    combination: CombinationEligibilityResult
    slots: Annotated[tuple[DailySlotDecision, ...], Field(min_length=3, max_length=3)]


class DailyTrialChoice(_DailyModel):
    slot: MealSlot
    option: MealOptionReference


class _TrialContent(_DailyModel):
    schema_version: Literal["daily-trial.v1"] = "daily-trial.v1"
    request_digest: _ContentDigest
    choices: Annotated[tuple[DailyTrialChoice, ...], Field(min_length=3, max_length=3)]

    @model_validator(mode="after")
    def validate_slots(self) -> Self:
        if tuple(item.slot for item in self.choices) != tuple(MealSlot):
            raise ValueError("daily trials require canonical BREAKFAST/LUNCH/DINNER choices")
        return self


class DailyTrial(_TrialContent, _DailySnapshot):
    """A bound hypothetical assignment, including unresolved UNASSIGNED choices."""

    _body_type = _TrialContent


class DayRuleExplanation(_DailyModel):
    manifest_digest: _ContentDigest
    trial_digest: _ContentDigest
    rule_reference: RuleReference
    status: RuleStatus
    reason: _NonBlank
    evidence: tuple[EvidenceReference, ...]


def _explanations(
    manifest: ExpectedDayCheckManifest,
    trial: DailyTrial,
    trace: RuleTrace,
) -> tuple[DayRuleExplanation, ...]:
    return tuple(
        DayRuleExplanation(
            manifest_digest=manifest.content_digest,
            trial_digest=trial.content_digest,
            rule_reference=RuleReference(rule_id=item.rule.rule_id, version=item.rule.version),
            status=item.status,
            reason=item.reason,
            evidence=_evidence_union(item),
        )
        for item in trace.evaluations
    )


class DailyAssignmentEvaluation(_DailyModel):
    trial: DailyTrial
    facts: Annotated[tuple[DayFact, ...], Field(min_length=2, max_length=2)]
    trace: RuleTrace
    status: RuleStatus
    explanations: tuple[DayRuleExplanation, ...]


class DailySearchStatistics(_DailyModel):
    nodes: Annotated[int, Field(ge=0, le=200_000)]
    completed_assignments: Annotated[int, Field(ge=0, le=4096)]
    backtracks: Annotated[int, Field(ge=0, le=200_000)]
    known_rejections: Annotated[int, Field(ge=0, le=200_000)]
    unknown_branches: Annotated[int, Field(ge=0, le=4096)]
    option_evaluations: Annotated[int, Field(ge=0, le=150)]
    phase3_batch_calls: Annotated[int, Field(ge=1, le=151)]
    phase3_candidate_evaluations: Annotated[int, Field(ge=0)]
    search_completed: bool
    exhaustive: bool
    budget_exhaustion: (
        Literal["NODE_BUDGET", "ASSIGNMENT_BUDGET", "PREPROCESSING_BUDGET", "DEADLINE"] | None
    ) = None
    preprocessing_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    search_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)]


def _assignment(manifest: ExpectedDayCheckManifest, trial: DailyTrial) -> DailyAssignment:
    request = manifest.request
    return DailyAssignment.build(
        dict(
            request_digest=request.content_digest,
            day_id=request.day_id,
            source=_source_reference(request.source),
            context_digest=request.context_digest,
            slots=tuple(AssignedMeal(slot=item.slot, option=item.option) for item in trial.choices),
        )
    )


def _interrupted_prefix(nodes: int, lunches: int, dinners: int) -> tuple[int, int]:
    """Count leaves and active ancestors before the next chronological node visit.

    Each breakfast subtree visits 1 + lunches * (1 + dinners) nodes.
    This verifies bounded-search accounting without replaying its Cartesian product.
    """
    breakfasts, remaining = divmod(nodes, 1 + lunches * (1 + dinners))
    leaves = breakfasts * lunches * dinners
    if remaining == 0:
        return leaves, 0
    completed_lunches, remaining = divmod(remaining - 1, 1 + dinners)
    leaves += completed_lunches * dinners + max(0, remaining - 1)
    return leaves, 1 if remaining == 0 else 2


class DailySolveResult(_DailyModel):
    schema_version: Literal["daily-solve-result.v1"] = "daily-solve-result.v1"
    evaluator_policy_version: Literal["synthetic-day-evaluation.v1"] = "synthetic-day-evaluation.v1"
    search_policy_version: Literal["synthetic-chronological-daily-search.v1"] = (
        "synthetic-chronological-daily-search.v1"
    )
    criterion: Literal["FIRST_FEASIBLE"] = "FIRST_FEASIBLE"
    weekly_feasibility: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    manifest: ExpectedDayCheckManifest
    limits: DailySearchLimits
    recipes: FilterCandidatesResult
    options: Annotated[tuple[DailyOptionDecision, ...], Field(max_length=150)]
    evaluations: Annotated[tuple[DailyAssignmentEvaluation, ...], Field(max_length=4096)]
    assignment: DailyAssignment | None = None
    outcome: DailyOutcome
    statistics: DailySearchStatistics

    @model_validator(mode="after")
    def validate_computation(self) -> Self:
        manifest, request, stats = self.manifest, self.manifest.request, self.statistics
        if (
            self.recipes.kb_id,
            self.recipes.kb_version,
            self.recipes.kb_digest,
            self.recipes.context.content_digest,
        ) != (
            manifest.knowledge.kb_id,
            manifest.knowledge.version,
            manifest.knowledge.content_digest,
            request.source.context.content_digest,
        ):
            raise ValueError("daily recipe prerequisites differ from exact KB/context")
        # Verify labels without rerunning public graph/KB validation.
        for recipe in self.recipes.decisions:
            if recipe.trace.evaluations != _evaluate_resolved_checks(
                manifest.knowledge,
                self.recipes.context,
                recipe.resolution,
            ):
                raise ValueError("recipe prerequisite outcomes contradict retained resolved facts")
        sources = {option.reference.option_id: option for option in request.source.options}
        required = sorted(
            {ref.option_id: ref for domain in request.domains for ref in domain.options}.values(),
            key=_option_order,
        )
        if tuple(item.option for item in self.options) != tuple(required[: len(self.options)]):
            raise ValueError("daily preprocessing proofs must be an exact canonical domain prefix")
        by_id = {item.option.option_id: item for item in self.options}
        combination_checks = tuple(
            rule
            for rule in _mandatory_checks(manifest.knowledge, self.recipes.context)
            if rule.scope is RuleScope.COMBINATION
        )
        applicability = _applicability(
            _descriptors_for(manifest.knowledge, combination_checks),
            _validated_fact_index(self.recipes.context.facts),
            self.recipes.context,
        )
        for decision in self.options:
            option = sources[decision.option.option_id]
            proof = decision.combination
            if proof.combination.content_digest != option.combination.content_digest or (
                proof.trusted_combination is None
                or proof.trusted_combination.content_digest != option.combination.content_digest
            ):
                raise ValueError("daily combination proof differs from independently bound source")
            recipe_ids = {part.recipe_snapshot.recipe_id for part in option.combination.components}
            if proof.recipes.decisions != tuple(
                r
                for r in self.recipes.decisions
                if r.resolution.manifest.candidate_id in recipe_ids
            ):
                raise ValueError("combination proof differs from recomputed recipe prerequisites")
            if proof.deferred_checks != tuple(
                sorted(
                    (*manifest.required_checks, *manifest.deferred_checks),
                    key=lambda rule: (rule.rule_id, rule.version),
                )
            ):
                raise ValueError("combination proof loses complete DAY/WEEK obligations")
            if proof.trace.required_checks != combination_checks:
                raise ValueError("combination proof differs from authoritative mandatory checks")
            for evaluation in proof.trace.evaluations:
                reference = evaluation.rule.applicability_reference
                state, evidence = applicability[(reference.rule_id, reference.version)]
                status = RuleStatus.UNKNOWN
                if state is ApplicabilityStatus.UNKNOWN:
                    reason = "APPLICABILITY_UNKNOWN"
                elif state is ApplicabilityStatus.NOT_APPLICABLE:
                    reason = "NOT_APPLICABLE"
                elif any(f.value is None or not f.complete for f in evaluation.facts):
                    reason = "REQUIRED_FACT_UNKNOWN"
                else:
                    attribute = next(
                        f for f in evaluation.facts if f.fact_id == evaluation.rule.attribute
                    )
                    status = (
                        RuleStatus.PASS
                        if _predicate(evaluation.rule, attribute)
                        else RuleStatus.FAIL
                    )
                    reason = "PREDICATE_TRUE" if status is RuleStatus.PASS else "PREDICATE_FALSE"
                if (
                    evaluation.applicability is not state
                    or evaluation.applicability_evidence != evidence
                    or evaluation.status is not status
                    or evaluation.reason
                    != self.recipes.context.evaluator_policy_version + ":" + reason
                ):
                    raise ValueError(
                        "combination evaluation contradicts accepted context/predicate"
                    )
            expected = tuple(
                DailySlotDecision(
                    slot=slot,
                    status=_slot_status(option, slot, proof.status)[0],
                    reasons=_slot_status(option, slot, proof.status)[1],
                )
                for slot in MealSlot
            )
            if decision.slots != expected:
                raise ValueError(
                    "daily slot statuses contradict exact eligibility/suitability/portions"
                )
        prepared = len(self.options) == len(required)
        if not prepared and (
            self.evaluations
            or stats.nodes
            or stats.backtracks
            or stats.budget_exhaustion not in ("PREPROCESSING_BUDGET", "DEADLINE")
        ):
            raise ValueError("search cannot start before complete preprocessing")
        domains = {
            domain.slot: tuple(
                sorted(
                    (
                        ref
                        for ref in domain.options
                        if ref.option_id in by_id
                        and by_id[ref.option_id].slots[list(MealSlot).index(domain.slot)].status
                        is not RuleStatus.FAIL
                    ),
                    key=_option_order,
                )
            )
            for domain in request.domains
        }
        expected_trials = product(*(domains[slot] for slot in MealSlot))
        program = _compile_day(manifest)
        unknown = 0
        for index, evaluation in enumerate(self.evaluations):
            refs = next(expected_trials, None)
            trial = evaluation.trial
            if (
                refs is None
                or trial.request_digest != request.content_digest
                or tuple(item.option for item in trial.choices) != refs
            ):
                raise ValueError("daily trial coverage/order differs from canonical finite domains")
            states = tuple(
                by_id[item.option.option_id].slots[i].status for i, item in enumerate(trial.choices)
            )
            facts, trace, status = _assess_day(
                manifest,
                tuple((item.slot, item.option) for item in trial.choices),
                states,
                trial.content_digest,
                program,
                _evidence_union(
                    tuple(
                        by_id[item.option.option_id].combination.evidence for item in trial.choices
                    )
                ),
            )
            if (
                evaluation.facts != facts
                or evaluation.trace != trace
                or evaluation.status is not status
            ):
                raise ValueError(
                    "daily facts/evaluations contradict exact source arithmetic or predicates"
                )
            if evaluation.explanations != _explanations(manifest, trial, trace):
                raise ValueError("daily explanations differ from complete evidenced evaluations")
            unknown += status is RuleStatus.UNKNOWN
            if status is RuleStatus.PASS and index != len(self.evaluations) - 1:
                raise ValueError("first-feasible search cannot continue past a feasible assignment")
        feasible = bool(self.evaluations and self.evaluations[-1].status is RuleStatus.PASS)
        exhausted = prepared and len(self.evaluations) == prod(len(domains[s]) for s in MealSlot)
        if stats.option_evaluations != len(self.options) or stats.phase3_batch_calls != 1 + len(
            self.options
        ):
            raise ValueError("public Phase 3/4 evaluation counts mismatch")
        if stats.phase3_candidate_evaluations != stats.phase3_batch_calls * len(
            self.recipes.decisions
        ):
            raise ValueError("recipe evaluation count mismatch")
        if (
            stats.completed_assignments != len(self.evaluations)
            or stats.unknown_branches != unknown
        ):
            raise ValueError("daily assignment/UNKNOWN accounting mismatch")
        if (
            stats.nodes > self.limits.max_nodes
            or stats.completed_assignments > self.limits.max_completed_assignments
        ):
            raise ValueError("search exceeds declared node/assignment bounds")
        if len(self.options) > self.limits.max_option_evaluations or stats.backtracks > stats.nodes:
            raise ValueError("preprocessing/backtrack bounds exceeded")
        if stats.known_rejections > stats.backtracks:
            raise ValueError("known rejection accounting exceeds backtracks")
        if stats.known_rejections != sum(
            item.status is RuleStatus.FAIL for item in self.evaluations
        ):
            raise ValueError(
                "known rejection accounting differs from completed assignment failures"
            )
        if stats.search_completed:
            _, n_l, n_d = (len(domains[slot]) for slot in MealSlot)
            k = len(self.evaluations)
            expected_nodes = (
                (k + (k + n_d - 1) // n_d + (k + n_l * n_d - 1) // (n_l * n_d)) if k else 0
            )
            if stats.nodes != expected_nodes or stats.backtracks != stats.nodes - (
                3 if feasible else 0
            ):
                raise ValueError(
                    "chronological node/backtrack accounting contradicts completed search"
                )
        elif prepared:
            _, n_l, n_d = (len(domains[slot]) for slot in MealSlot)
            if not n_l or not n_d:
                raise ValueError("empty prepared domains cannot have interrupted search")
            visited_leaves, active = _interrupted_prefix(stats.nodes, n_l, n_d)
            blocked_leaf = stats.budget_exhaustion == "ASSIGNMENT_BUDGET"
            if blocked_leaf:
                active = 3  # The blocked complete choice is still on the solver stack.
                k = len(self.evaluations) + 1
                leaf_node = k + (k + n_d - 1) // n_d + (k + n_l * n_d - 1) // (n_l * n_d)
                if stats.nodes != leaf_node:
                    raise ValueError("assignment budget must stop at the next complete choice")
            if visited_leaves != len(self.evaluations) + int(blocked_leaf) or (
                stats.backtracks != stats.nodes - active
            ):
                raise ValueError("interrupted counters contradict the chronological search prefix")
        if stats.exhaustive != (exhausted and not feasible):
            raise ValueError("exhaustion claim differs from finite-domain coverage")
        if feasible:
            expected_outcome = DailyOutcome.FEASIBLE
            if self.assignment != _assignment(manifest, self.evaluations[-1].trial):
                raise ValueError("feasible assignment differs from the first verified trial")
        elif self.assignment is not None:
            raise ValueError("non-feasible results cannot expose a feasible assignment")
        elif exhausted:
            expected_outcome = (
                DailyOutcome.INSUFFICIENT_DATA if unknown else DailyOutcome.INFEASIBLE
            )
        else:
            expected_outcome = DailyOutcome.TIMEOUT
        if self.outcome is not expected_outcome or stats.search_completed != (
            expected_outcome is not DailyOutcome.TIMEOUT
        ):
            raise ValueError("daily outcome/completion claim contradicts validated search evidence")
        if (stats.budget_exhaustion is not None) != (self.outcome is DailyOutcome.TIMEOUT):
            raise ValueError("budget exhaustion must distinguish incomplete search")
        if stats.budget_exhaustion == "NODE_BUDGET" and stats.nodes != self.limits.max_nodes:
            raise ValueError("node budget exhaustion was not reached")
        if (
            stats.budget_exhaustion == "ASSIGNMENT_BUDGET"
            and stats.completed_assignments != self.limits.max_completed_assignments
        ):
            raise ValueError("assignment budget exhaustion was not reached")
        if stats.budget_exhaustion == "PREPROCESSING_BUDGET" and (
            len(self.options) != self.limits.max_option_evaluations or prepared or stats.nodes
        ):
            raise ValueError("preprocessing budget exhaustion was not reached")
        if stats.budget_exhaustion == "DEADLINE" and self.limits.deadline is None:
            raise ValueError("deadline exhaustion requires a declared deadline")
        return self
