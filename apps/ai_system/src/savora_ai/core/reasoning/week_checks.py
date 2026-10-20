"""Request-local WEEK preparation and pure supplied-trial evaluation; no search."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from savora_ai.core.reasoning.combinations import evaluate_combination
from savora_ai.core.reasoning.day_checks import (
    _assess_day,
    _compile_day,
    _DayProgram,
    _option_order,
    _slot_status,
)
from savora_ai.core.reasoning.evaluation import _applicability, _observation, _predicate
from savora_ai.core.reasoning.facts import _validated_fact_index
from savora_ai.core.reasoning.filtering import filter_candidates
from savora_ai.core.reasoning.manifest import _descriptors_for
from savora_ai.schemas.candidates import CandidateRecipeFacts, _content_digest
from savora_ai.schemas.combination_evaluation import _combine_statuses
from savora_ai.schemas.daily import ExpectedDayCheckManifest, MealOptionReference, MealSlot
from savora_ai.schemas.daily_solver import (
    DailyAssignmentEvaluation,
    DailyOptionDecision,
    DailySlotDecision,
    DailyTrial,
    DailyTrialChoice,
    _explanations,
)
from savora_ai.schemas.filtering import FilterCandidatesResult, _evidence_union
from savora_ai.schemas.knowledge import EvidenceReference, MeasurementUnit, RuleEnvironment
from savora_ai.schemas.reasoning import (
    ApplicabilityStatus,
    FactObservation,
    RuleEvaluation,
    RuleStatus,
    RuleTrace,
    aggregate_hard_status,
)
from savora_ai.schemas.weekly import (
    ExpectedWeekCheckManifest,
    WeekDayReference,
    WeekFact,
    WeeklyTrial,
    WeekMeasurementContribution,
    WeekRecipeOccurrence,
    _bind_trial,
    _daily_request,
    _weekly_source_reference,
)


def _week_derivation_evidence() -> EvidenceReference:
    return EvidenceReference(
        evidence_id="synthetic-week-derivation",
        version="1",
        source="Synthetic exact 21-slot quantity, recipe presence and DAY completeness derivation",
        locator="urn:savora:synthetic-week-fact-derivation:1",
        environment=RuleEnvironment.SYNTHETIC,
    )


def _prepare_options(
    manifest: ExpectedWeekCheckManifest,
    candidates: tuple[CandidateRecipeFacts, ...],
    trial: WeeklyTrial,
) -> tuple[FilterCandidatesResult, tuple[DailyOptionDecision, ...]]:
    """Public prerequisites once per distinct selected option, never per day or predicate."""
    _bind_trial(manifest.request, trial)
    context = manifest.request.source.daily_source.context
    recipes = filter_candidates(candidates, knowledge=manifest.knowledge, context=context)
    refs = sorted({c.option.option_id: c.option for c in trial.choices}.values(), key=_option_order)
    return recipes, tuple(_prepare_option(manifest, candidates, ref) for ref in refs)


def _prepare_option(
    manifest: ExpectedWeekCheckManifest,
    candidates: tuple[CandidateRecipeFacts, ...],
    ref: MealOptionReference,
) -> DailyOptionDecision:
    """One authoritative option; shared by supplied-trial evaluation and bounded search."""
    context = manifest.request.source.daily_source.context
    option = next(o for o in manifest.request.source.daily_source.options if o.reference == ref)
    proof = evaluate_combination(
        option.combination,
        candidates=candidates,
        knowledge=manifest.knowledge,
        context=context,
        trusted_combination=option.combination,
    )
    deferred = tuple(
        sorted(
            (*manifest.day_checks, *manifest.required_checks), key=lambda r: (r.rule_id, r.version)
        )
    )
    if proof.deferred_checks != deferred:
        raise ValueError("combination loses authoritative DAY/WEEK definitions")
    return DailyOptionDecision(
        option=ref,
        combination=proof,
        slots=tuple(
            DailySlotDecision(slot=slot, status=state, reasons=reasons)
            for slot in MealSlot
            for state, reasons in (_slot_status(option, slot, proof.status),)
        ),
    )


@dataclass(frozen=True)
class _WeekProgram:
    manifest: ExpectedWeekCheckManifest
    days: tuple[ExpectedDayCheckManifest, ...]
    day_program: _DayProgram
    observations: Mapping[str, FactObservation]
    applicability: Mapping[
        tuple[str, str], tuple[ApplicabilityStatus, tuple[EvidenceReference, ...]]
    ]


def _compile_week(manifest: ExpectedWeekCheckManifest) -> _WeekProgram:
    days = tuple(
        ExpectedDayCheckManifest.build(
            dict(
                request=_daily_request(manifest.request, d),
                knowledge=manifest.knowledge,
                required_checks=manifest.day_checks,
                deferred_checks=manifest.required_checks,
            )
        )
        for d in sorted(manifest.request.days, key=lambda d: d.day.day_index)
    )
    context = manifest.request.source.daily_source.context
    indexed = _validated_fact_index(context.facts)
    return _WeekProgram(
        manifest,
        days,
        _compile_day(days[0]),
        MappingProxyType({name: _observation(f) for name, f in indexed.items()}),
        MappingProxyType(
            _applicability(
                _descriptors_for(manifest.knowledge, manifest.required_checks), indexed, context
            )
        ),
    )


def _assess_week(
    program: _WeekProgram,
    trial: WeeklyTrial,
    options: tuple[DailyOptionDecision, ...],
    *,
    assessed_days: tuple[tuple[WeekDayReference, str, DailyAssignmentEvaluation], ...]
    | None = None,
) -> tuple[
    tuple[tuple[WeekDayReference, str, DailyAssignmentEvaluation], ...],
    tuple[WeekFact, ...],
    RuleTrace,
    RuleStatus,
    RuleStatus,
]:
    manifest = program.manifest
    request = manifest.request
    _bind_trial(request, trial)
    decisions = {o.option.option_id: o for o in options}
    selected_choices = sorted(
        trial.choices, key=lambda c: (c.day.day_index, tuple(MealSlot).index(c.slot))
    )
    source_options = {o.reference.option_id: o for o in request.source.daily_source.options}
    day_records = list(assessed_days) if assessed_days is not None else []
    for index, day_manifest in enumerate(program.days if assessed_days is None else (), 1):
        choices = tuple(c for c in selected_choices if c.day.day_index == index)
        daily_trial = DailyTrial.build(
            dict(
                request_digest=day_manifest.request.content_digest,
                choices=tuple(DailyTrialChoice(slot=c.slot, option=c.option) for c in choices),
            )
        )
        states = tuple(decisions[c.option.option_id].slots[i].status for i, c in enumerate(choices))
        facts, trace, status = _assess_day(
            day_manifest,
            tuple((c.slot, c.option) for c in choices),
            states,
            daily_trial.content_digest,
            program.day_program,
            _evidence_union(
                tuple(decisions[c.option.option_id].combination.evidence for c in choices)
            ),
        )
        evaluation = DailyAssignmentEvaluation(
            trial=daily_trial,
            facts=facts,
            trace=trace,
            status=status,
            explanations=_explanations(day_manifest, daily_trial, trace),
        )
        day_records.append((choices[0].day, day_manifest.content_digest, evaluation))
    selected = tuple(source_options[c.option.option_id] for c in selected_choices)
    derivation = _week_derivation_evidence()
    evidence = _evidence_union(
        (
            selected,
            options,
            tuple(r[2] for r in day_records),
            request.source.evidence,
            manifest.knowledge.evidence,
            derivation,
        )
    )
    contributions = tuple(
        WeekMeasurementContribution(
            day=c.day,
            slot=c.slot,
            option=c.option,
            measurement_source=o.measurements[0].source,
            measurement_digest=_content_digest(o.measurements[0]),
        )
        for c, o in zip(selected_choices, selected, strict=True)
        if o.measurements
    )
    quantity_complete = len(contributions) == 21 and all(
        o.measurements and o.measurements[0].complete and o.measurements[0].value is not None
        for o in selected
    )
    total = (
        sum(
            o.measurements[0].value
            for o in selected
            if o.measurements and o.measurements[0].value is not None
        )
        if quantity_complete
        else None
    )
    occurrences = tuple(
        WeekRecipeOccurrence(
            day=c.day,
            slot=c.slot,
            option=c.option,
            recipe_ids=tuple(
                sorted({part.recipe_snapshot.recipe_id for part in o.combination.components})
            ),
        )
        for c, o in zip(selected_choices, selected, strict=True)
    )
    count_complete = all(
        all(
            p.status is RuleStatus.PASS
            for p in decisions[o.reference.option_id].combination.prerequisites
            if p.name in ("CANDIDATE_MEMBERSHIP", "COMPOSITION_COMPLETENESS", "SOURCE_AUTHORITY")
        )
        for o in selected
    )
    counts = Counter(recipe for occurrence in occurrences for recipe in occurrence.recipe_ids)
    maximum = max(counts.values(), default=0) if count_complete else None
    complete = all(record[2].status is RuleStatus.PASS for record in day_records)
    binding = dict(
        request_digest=request.content_digest,
        trial_digest=trial.content_digest,
        week_id=request.week_id,
        week_version=request.week_version,
        source=_weekly_source_reference(request.source),
        context_digest=request.context_digest,
    )
    week_facts = (
        WeekFact.model_validate(
            binding
            | dict(
                observation=FactObservation(
                    fact_id="synthetic_week_complete",
                    value=True if complete else None,
                    complete=complete,
                    evidence=evidence,
                ),
            )
        ),
        WeekFact.model_validate(
            binding
            | dict(
                observation=FactObservation(
                    fact_id="synthetic_week_quantity_total",
                    value=total,
                    complete=quantity_complete,
                    unit=MeasurementUnit.MG if quantity_complete else None,
                    evidence=evidence,
                ),
                measurement_basis="WEEK_FIXED_TOTAL",
                basis_reference=derivation,
                contributions=contributions,
            )
        ),
        WeekFact.model_validate(
            binding
            | dict(
                observation=FactObservation(
                    fact_id="synthetic_week_max_recipe_slot_occurrences",
                    value=maximum,
                    complete=count_complete,
                    unit=MeasurementUnit.DIMENSIONLESS if count_complete else None,
                    evidence=evidence,
                ),
                basis_reference=derivation,
                occurrences=occurrences,
            )
        ),
    )
    observations = dict(program.observations)
    observations.update(
        {
            f.observation.fact_id: FactObservation.model_validate(
                f.observation.model_dump() | {"evidence": _evidence_union(f)}
            )
            for f in week_facts
        }
    )
    evaluations = []
    for rule in manifest.required_checks:
        required = tuple(
            observations.get(name)
            or FactObservation(fact_id=name, value=None, complete=False, evidence=evidence)
            for name in sorted(rule.required_facts)
        )
        state, app_evidence = program.applicability[
            (rule.applicability_reference.rule_id, rule.applicability_reference.version)
        ]
        status = RuleStatus.UNKNOWN
        if state is ApplicabilityStatus.UNKNOWN:
            reason = "APPLICABILITY_UNKNOWN"
        elif state is ApplicabilityStatus.NOT_APPLICABLE:
            reason = "NOT_APPLICABLE"
        elif any(f.value is None or not f.complete for f in required):
            reason = "REQUIRED_FACT_UNKNOWN"
        else:
            attribute = next(f for f in required if f.fact_id == rule.attribute)
            status = RuleStatus.PASS if _predicate(rule, attribute) else RuleStatus.FAIL
            reason = "PREDICATE_TRUE" if status is RuleStatus.PASS else "PREDICATE_FALSE"
        evaluations.append(
            RuleEvaluation(
                rule=rule,
                applicability=state,
                applicability_evidence=app_evidence,
                facts=required,
                status=status,
                reason="synthetic-week-evaluation.v1:" + reason,
            )
        )
    trace = RuleTrace(
        candidate_id=trial.content_digest,
        context_id=request.context_id,
        manifest_id="week-manifest-" + manifest.content_digest,
        manifest_version="expected-week-check-manifest.v1:" + manifest.content_digest,
        required_checks=manifest.required_checks,
        evaluations=tuple(evaluations),
    )
    week_status = aggregate_hard_status(trace)
    combined = _combine_statuses((*tuple(r[2].status for r in day_records), week_status))
    return tuple(day_records), week_facts, trace, week_status, combined
