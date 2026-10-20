"""Private DAY computations shared by search and computed-output verification.

Inputs here are request-local validated records, never public eligibility overrides.
No KB/source loading, conversion, cache or search occurs in this module.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from savora_ai.core.reasoning.evaluation import _applicability, _observation, _predicate
from savora_ai.core.reasoning.facts import _validated_fact_index
from savora_ai.core.reasoning.manifest import _descriptors_for
from savora_ai.schemas.combination_evaluation import _combine_statuses
from savora_ai.schemas.combinations import PortionState
from savora_ai.schemas.daily import (
    DailyMealOption,
    DayFact,
    DayMeasurementContribution,
    ExpectedDayCheckManifest,
    MealOptionReference,
    MealSlot,
    _source_reference,
)
from savora_ai.schemas.filtering import _evidence_union
from savora_ai.schemas.knowledge import EvidenceReference, MeasurementUnit, RuleEnvironment
from savora_ai.schemas.reasoning import (
    ApplicabilityStatus,
    FactObservation,
    RuleEvaluation,
    RuleStatus,
    RuleTrace,
    aggregate_hard_status,
)


def _option_order(ref: MealOptionReference) -> tuple[str, ...]:
    return (
        ref.option_id,
        ref.combination_id,
        ref.combination_version,
        ref.snapshot_id,
        ref.snapshot_version,
        ref.portion_configuration_id or "",
        ref.portion_configuration_version or "",
        ref.combination_digest,
    )


def _slot_status(
    option: DailyMealOption,
    slot: MealSlot,
    combination_status: RuleStatus,
) -> tuple[RuleStatus, tuple[str, ...]]:
    suitability = option.suitability
    suitable = (
        RuleStatus.UNKNOWN
        if suitability is None or not suitability.complete
        else RuleStatus.PASS
        if slot in suitability.slots
        else RuleStatus.FAIL
    )
    portions = (
        RuleStatus.PASS
        if option.reference.portion_state is PortionState.FIXED
        else RuleStatus.UNKNOWN
    )
    reasons = (
        "COMBINATION_" + combination_status.value,
        "PORTIONS_FIXED" if portions is RuleStatus.PASS else "PORTIONS_UNASSIGNED",
        "SLOT_" + suitable.value,
    )
    return _combine_statuses((combination_status, portions, suitable)), reasons


@dataclass(frozen=True)
class _DayProgram:
    options: Mapping[str, DailyMealOption]
    observations: Mapping[str, FactObservation]
    applicability: Mapping[
        tuple[str, str], tuple[ApplicabilityStatus, tuple[EvidenceReference, ...]]
    ]


def _compile_day(manifest: ExpectedDayCheckManifest) -> _DayProgram:
    context = manifest.request.source.context
    indexed = _validated_fact_index(context.facts)
    return _DayProgram(
        options=MappingProxyType(
            {o.reference.option_id: o for o in manifest.request.source.options}
        ),
        observations=MappingProxyType({name: _observation(fact) for name, fact in indexed.items()}),
        applicability=MappingProxyType(
            _applicability(
                _descriptors_for(manifest.knowledge, manifest.required_checks),
                indexed,
                context,
            )
        ),
    )


def _derivation_evidence() -> EvidenceReference:
    return EvidenceReference(
        evidence_id="synthetic-day-derivation",
        version="1",
        source="Synthetic exact fixed-meal integer aggregation and three-slot derivation",
        locator="urn:savora:synthetic-day-derivation:1",
        environment=RuleEnvironment.SYNTHETIC,
    )


def _assess_day(
    manifest: ExpectedDayCheckManifest,
    choices: tuple[tuple[MealSlot, MealOptionReference], ...],
    statuses: tuple[RuleStatus, ...],
    trial_digest: str,
    program: _DayProgram,
    prerequisite_evidence: tuple[EvidenceReference, ...] = (),
) -> tuple[tuple[DayFact, ...], RuleTrace, RuleStatus]:
    # The authoritative path always derives from the selected original records.
    return _evaluate_day(manifest, choices, statuses, trial_digest, program, prerequisite_evidence)


def _evaluate_day(
    manifest: ExpectedDayCheckManifest,
    choices: tuple[tuple[MealSlot, MealOptionReference], ...],
    statuses: tuple[RuleStatus, ...],
    trial_digest: str,
    program: _DayProgram,
    prerequisite_evidence: tuple[EvidenceReference, ...] = (),
    *,
    quantity: tuple[int | None, bool] | None = None,
) -> tuple[tuple[DayFact, ...], RuleTrace, RuleStatus]:
    """Assemble full evidence and evaluate every rule; optional private arithmetic only.

    Only execution's incremental adapter supplies quantity. Authoritative verification
    calls _assess_day, which never accepts an aggregate or skips full derivation.
    """
    request = manifest.request
    selected = tuple(program.options[ref.option_id] for _, ref in choices)
    source = request.source
    complete = all(status is RuleStatus.PASS for status in statuses)
    contributions = tuple(
        DayMeasurementContribution(slot=slot, measurement=option.measurements[0])
        for (slot, _), option in zip(choices, selected, strict=True)
        if option.measurements
    )
    if quantity is None:
        numeric_complete = len(contributions) == 3 and all(
            item.measurement.complete and item.measurement.value is not None
            for item in contributions
        )
        total = (
            sum(
                item.measurement.value
                for item in contributions
                if item.measurement.value is not None
            )
            if numeric_complete
            else None
        )
    else:
        total, numeric_complete = quantity
    derivation = _derivation_evidence()
    evidence = _evidence_union((source.evidence, selected, derivation, prerequisite_evidence))
    bindings: dict[str, object] = dict(
        request_digest=request.content_digest,
        assignment_digest=trial_digest,
        day_id=request.day_id,
        source=_source_reference(source),
        context_digest=request.context_digest,
    )
    facts = (
        DayFact.model_validate(
            bindings
            | {
                "observation": FactObservation(
                    fact_id="synthetic_day_complete",
                    value=True if complete else None,
                    complete=complete,
                    evidence=evidence,
                ),
            }
        ),
        DayFact.model_validate(
            bindings
            | {
                "observation": FactObservation(
                    fact_id="synthetic_day_quantity_total",
                    value=total,
                    complete=numeric_complete,
                    unit=MeasurementUnit.MG if numeric_complete else None,
                    evidence=evidence,
                ),
                "measurement_basis": "DAY_FIXED_TOTAL",
                "basis_reference": derivation,
                "contributions": contributions,
            }
        ),
    )
    observed = dict(program.observations)
    for fact in facts:
        observation = fact.observation
        observed[observation.fact_id] = FactObservation.model_validate(
            observation.model_dump()
            | {
                "evidence": _evidence_union(fact),
            }
        )
    evaluations = []
    for rule in manifest.required_checks:
        required = tuple(
            observed.get(name)
            or FactObservation(
                fact_id=name,
                value=None,
                complete=False,
                evidence=evidence,
            )
            for name in sorted(rule.required_facts)
        )
        applicability, applicability_evidence = program.applicability[
            (rule.applicability_reference.rule_id, rule.applicability_reference.version)
        ]
        status = RuleStatus.UNKNOWN
        if applicability is ApplicabilityStatus.UNKNOWN:
            reason = "APPLICABILITY_UNKNOWN"
        elif applicability is ApplicabilityStatus.NOT_APPLICABLE:
            reason = "NOT_APPLICABLE"
        elif any(fact.value is None or not fact.complete for fact in required):
            reason = "REQUIRED_FACT_UNKNOWN"
        else:
            predicate = next(fact for fact in required if fact.fact_id == rule.attribute)
            status = RuleStatus.PASS if _predicate(rule, predicate) else RuleStatus.FAIL
            reason = "PREDICATE_TRUE" if status is RuleStatus.PASS else "PREDICATE_FALSE"
        evaluations.append(
            RuleEvaluation(
                rule=rule,
                applicability=applicability,
                applicability_evidence=applicability_evidence,
                facts=required,
                status=status,
                reason="synthetic-day-evaluation.v1:" + reason,
            )
        )
    trace = RuleTrace(
        candidate_id=trial_digest,
        context_id=request.context_id,
        manifest_id="day-manifest-" + manifest.content_digest,
        manifest_version="expected-day-check-manifest.v1:" + manifest.content_digest,
        required_checks=manifest.required_checks,
        evaluations=tuple(evaluations),
    )
    return facts, trace, _combine_statuses((*statuses, aggregate_hard_status(trace)))
