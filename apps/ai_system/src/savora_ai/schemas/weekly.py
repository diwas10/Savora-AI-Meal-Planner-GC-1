"""Synthetic WEEK declarations. No fact derivation, predicate evaluation or search.

Digests bind declarations, not external authority. Prompt 1 results are always
NOT_EVALUATED; future computed outcomes need a separate verified result contract.
"""

from datetime import date, timedelta
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.manifest import _KnowledgeContextRequest, _mandatory_checks
from savora_ai.schemas.candidates import _content_digest
from savora_ai.schemas.daily import (
    DailyAssignment,
    DailyOutcome,
    DailyPlanningRequest,
    DailySlotDomain,
    DailySourceReference,
    DailySourceSnapshot,
    MealOptionReference,
    MealSlot,
    _DailyModel,
    _DailySnapshot,
    _evidenced,
    _slots,
    _source_reference,
)
from savora_ai.schemas.daily_solver import DailyTrial
from savora_ai.schemas.filtering import (
    _WEEK_MAX_TOTAL,
    _evidence_union,
    _validate_day_rule_policy,
    _validate_week_rule_policy,
)
from savora_ai.schemas.food_graph import _OpaqueId
from savora_ai.schemas.knowledge import (
    EvidenceReference,
    MeasurementUnit,
    RuleDefinition,
    RuleReference,
    RuleScope,
    _NonBlank,
)
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot, _ContentDigest
from savora_ai.schemas.reasoning import FactObservation, RuleStatus


def _calendar_date(value: str) -> str:
    date.fromisoformat(value)
    return value


# Canonical date strings preserve the existing strict ingress scalar vocabulary.
_CalendarDate = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", min_length=10, max_length=10),
    AfterValidator(_calendar_date),
]


class WeeklySourceReference(_DailyModel):
    source_id: _OpaqueId
    version: _NonBlank
    content_digest: _ContentDigest


class _WeeklySourceContent(_DailyModel):
    schema_version: Literal["weekly-source-snapshot.v1"] = "weekly-source-snapshot.v1"
    source_id: _OpaqueId
    version: _NonBlank
    expected_daily_source: DailySourceReference
    daily_source: DailySourceSnapshot
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if self.expected_daily_source != _source_reference(self.daily_source):
            raise ValueError("weekly source differs from exact daily source pin")
        own = self.source_id, self.version
        if own == (self.daily_source.source_id, self.daily_source.version):
            raise ValueError("weekly and daily source identities must be distinct")
        for option in self.daily_source.options:
            for record in (
                *option.measurements,
                *((option.suitability,) if option.suitability is not None else ()),
            ):
                if (record.source.source_id, record.source.version) == own:
                    raise ValueError("external evidence cannot self-reference the weekly source")
        _evidenced(self.evidence)
        return self


class WeeklySourceSnapshot(_WeeklySourceContent, _DailySnapshot):
    _body_type = _WeeklySourceContent


def _weekly_source_reference(source: WeeklySourceSnapshot) -> WeeklySourceReference:
    return WeeklySourceReference(
        source_id=source.source_id, version=source.version, content_digest=source.content_digest
    )


class WeekDayReference(_DailyModel):
    week_id: _OpaqueId
    week_version: _NonBlank
    day_id: _OpaqueId
    day_index: Annotated[int, Field(ge=1, le=7)]
    calendar_date: _CalendarDate


def _week_days(
    days: tuple[WeekDayReference, ...], week_id: str, week_version: str, start_date: _CalendarDate
) -> None:
    if len(days) != 7 or {d.day_index for d in days} != set(range(1, 8)):
        raise ValueError("week requires exactly seven unique indexes 1 through 7")
    if len({d.day_id for d in days}) != 7 or week_id in {d.day_id for d in days}:
        raise ValueError("week/day identities must be distinct")
    for day in days:
        try:
            expected_date = (
                date.fromisoformat(start_date) + timedelta(days=day.day_index - 1)
            ).isoformat()
        except OverflowError as error:
            raise ValueError("week extends beyond supported calendar dates") from error
        if (day.week_id, day.week_version) != (week_id, week_version) or (
            day.calendar_date != expected_date
        ):
            raise ValueError("foreign week identity or nonsequential calendar date")


class WeeklyDayDomain(_DailyModel):
    day: WeekDayReference
    domains: Annotated[tuple[DailySlotDomain, ...], Field(min_length=3, max_length=3)]

    @model_validator(mode="after")
    def validate_domains(self) -> Self:
        _slots(tuple(d.slot for d in self.domains), exact=True)
        return self


class _WeeklyRequestContent(_DailyModel):
    schema_version: Literal["weekly-planning-request.v1"] = "weekly-planning-request.v1"
    contract_policy_version: Literal["synthetic-weekly-contracts.v1"] = (
        "synthetic-weekly-contracts.v1"
    )
    week_policy_version: Literal["synthetic-week-policy.v1"] = "synthetic-week-policy.v1"
    request_id: _OpaqueId
    version: _NonBlank
    week_id: _OpaqueId
    week_version: _NonBlank
    start_date: _CalendarDate
    context_id: _OpaqueId
    context_version: _NonBlank
    context_digest: _ContentDigest
    expected_source: WeeklySourceReference
    source: WeeklySourceSnapshot
    days: Annotated[tuple[WeeklyDayDomain, ...], Field(min_length=7, max_length=7)]

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        _week_days(
            tuple(d.day for d in self.days), self.week_id, self.week_version, self.start_date
        )
        context = self.source.daily_source.context
        if (self.context_id, self.context_version, self.context_digest) != (
            context.context_id,
            context.version,
            context.content_digest,
        ) or self.expected_source != _weekly_source_reference(self.source):
            raise ValueError("weekly request source/context pin mismatch")
        options = {o.reference.option_id: o.reference for o in self.source.daily_source.options}
        for day in self.days:
            for domain in day.domains:
                for ref in domain.options:
                    if options.get(ref.option_id) != ref:
                        raise ValueError("weekly domain differs from exact source option")
        return self


class WeeklyPlanningRequest(_WeeklyRequestContent, _DailySnapshot):
    _body_type = _WeeklyRequestContent


def _daily_request(request: WeeklyPlanningRequest, day: WeeklyDayDomain) -> DailyPlanningRequest:
    """Deterministic bridge to the unchanged daily request/trial identity contract."""
    if day not in request.days:
        raise ValueError("daily bridge requires an exact weekly day domain")
    return DailyPlanningRequest.build(
        dict(
            request_id=f"weekly-day-{request.content_digest}-{day.day.day_index}",
            version=request.version,
            day_id=day.day.day_id,
            context_id=request.context_id,
            context_version=request.context_version,
            context_digest=request.context_digest,
            expected_source=request.source.expected_daily_source,
            source=request.source.daily_source,
            domains=day.domains,
        )
    )


class WeeklyDayAssignment(_DailyModel):
    day: WeekDayReference
    trial: DailyTrial
    assignment: DailyAssignment

    @model_validator(mode="after")
    def validate_trial_binding(self) -> Self:
        if (
            self.assignment.day_id != self.day.day_id
            or (self.trial.request_digest != self.assignment.request_digest)
            or {m.slot: m.option for m in self.assignment.slots}
            != {m.slot: m.option for m in self.trial.choices}
        ):
            raise ValueError("daily trial and assignment differ in day/request/choices")
        return self


class _WeeklyAssignmentContent(_DailyModel):
    schema_version: Literal["weekly-assignment.v1"] = "weekly-assignment.v1"
    request_digest: _ContentDigest
    week_id: _OpaqueId
    week_version: _NonBlank
    start_date: _CalendarDate
    source: WeeklySourceReference
    daily_source: DailySourceReference
    context_digest: _ContentDigest
    days: Annotated[tuple[WeeklyDayAssignment, ...], Field(min_length=7, max_length=7)]

    @model_validator(mode="after")
    def validate_assignment(self) -> Self:
        _week_days(
            tuple(d.day for d in self.days), self.week_id, self.week_version, self.start_date
        )
        for day in self.days:
            if day.assignment.source != self.daily_source or (
                day.assignment.context_digest != self.context_digest
            ):
                raise ValueError("daily assignment differs from weekly source/context")
        return self


class WeeklyAssignment(_WeeklyAssignmentContent, _DailySnapshot):
    """Structural FIXED assignment; eligibility and feasibility are not established."""

    _body_type = _WeeklyAssignmentContent


class WeeklyTrialChoice(_DailyModel):
    day: WeekDayReference
    slot: MealSlot
    option: MealOptionReference


class _WeeklyTrialContent(_DailyModel):
    schema_version: Literal["weekly-trial.v1"] = "weekly-trial.v1"
    request_digest: _ContentDigest
    week_id: _OpaqueId
    week_version: _NonBlank
    start_date: _CalendarDate
    choices: Annotated[tuple[WeeklyTrialChoice, ...], Field(min_length=21, max_length=21)]

    @model_validator(mode="after")
    def validate_choices(self) -> Self:
        days: dict[int, WeekDayReference] = {}
        for choice in self.choices:
            if days.setdefault(choice.day.day_index, choice.day) != choice.day:
                raise ValueError("conflicting day reference in weekly trial")
        _week_days(tuple(days.values()), self.week_id, self.week_version, self.start_date)
        for index in range(1, 8):
            _slots(tuple(c.slot for c in self.choices if c.day.day_index == index), exact=True)
        return self


class WeeklyTrial(_WeeklyTrialContent, _DailySnapshot):
    """A complete hypothetical week, including unresolved UNASSIGNED options."""

    _body_type = _WeeklyTrialContent


class WeekMeasurementContribution(_DailyModel):
    day: WeekDayReference
    slot: MealSlot
    option: MealOptionReference
    measurement_source: DailySourceReference
    measurement_digest: _ContentDigest


class WeekRecipeOccurrence(_DailyModel):
    day: WeekDayReference
    slot: MealSlot
    option: MealOptionReference
    recipe_ids: Annotated[tuple[_OpaqueId, ...], Field(min_length=1, max_length=32)]

    @model_validator(mode="after")
    def validate_recipe_ids(self) -> Self:
        if len(set(self.recipe_ids)) != len(self.recipe_ids):
            raise ValueError("recipe presence counts once per slot, not per component")
        return self


class WeekFact(_DailyModel):
    """Bound declaration only; neither totals nor occurrences are calculated here."""

    schema_version: Literal["week-fact.v1"] = "week-fact.v1"
    week_policy_version: Literal["synthetic-week-policy.v1"] = "synthetic-week-policy.v1"
    request_digest: _ContentDigest
    trial_digest: _ContentDigest
    week_id: _OpaqueId
    week_version: _NonBlank
    source: WeeklySourceReference
    context_digest: _ContentDigest
    observation: FactObservation
    measurement_basis: Literal["WEEK_FIXED_TOTAL"] | None = None
    basis_reference: EvidenceReference | None = None
    contributions: Annotated[tuple[WeekMeasurementContribution, ...], Field(max_length=21)] = ()
    occurrences: Annotated[tuple[WeekRecipeOccurrence, ...], Field(max_length=21)] = ()

    @model_validator(mode="after")
    def validate_fact(self) -> Self:
        obs = self.observation
        if obs.fact_id == "synthetic_week_complete":
            if (obs.value is not None and type(obs.value) is not bool) or (
                obs.unit is not None
                or self.measurement_basis is not None
                or self.basis_reference is not None
                or self.contributions
                or self.occurrences
            ):
                raise ValueError("weekly completeness requires boolean/null and no numeric basis")
        elif obs.fact_id in (
            "synthetic_week_quantity_total",
            "synthetic_week_max_recipe_slot_occurrences",
        ):
            quantity = obs.fact_id == "synthetic_week_quantity_total"
            maximum = _WEEK_MAX_TOTAL if quantity else 21
            if obs.value is not None and (
                type(obs.value) is not int
                or not 0 <= obs.value <= maximum
                or obs.unit
                is not (MeasurementUnit.MG if quantity else MeasurementUnit.DIMENSIONLESS)
            ):
                raise ValueError("weekly numeric fact requires bounded exact integer and unit")
            if (
                self.basis_reference is None
                or (quantity and (self.measurement_basis != "WEEK_FIXED_TOTAL" or self.occurrences))
                or (not quantity and (self.measurement_basis is not None or self.contributions))
            ):
                raise ValueError("weekly numeric fact requires exact basis/contribution kind")
            records = self.contributions if quantity else self.occurrences
            keys = {(r.day.day_index, r.slot) for r in records}
            if len(keys) != len(records) or (obs.complete and len(keys) != 21):
                raise ValueError("weekly contributors require unique slots and complete coverage")
        else:
            raise ValueError("unsupported WEEK fact")
        return self


class _WeekManifestContent(_DailyModel):
    schema_version: Literal["expected-week-check-manifest.v1"] = "expected-week-check-manifest.v1"
    week_policy_version: Literal["synthetic-week-policy.v1"] = "synthetic-week-policy.v1"
    day_policy_version: Literal["synthetic-day-policy.v1"] = "synthetic-day-policy.v1"
    stage: Literal["WEEK"] = "WEEK"
    request: WeeklyPlanningRequest
    knowledge: KnowledgeBaseSnapshot
    required_checks: tuple[RuleDefinition, ...]
    day_checks: tuple[RuleDefinition, ...]

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        context = self.request.source.daily_source.context
        binding = _KnowledgeContextRequest(kb=self.knowledge, context=context)
        accepted = build_knowledge_snapshot(binding.kb, expected_digest=context.expected_kb_digest)
        checks = _mandatory_checks(accepted, context)
        if self.required_checks != tuple(r for r in checks if r.scope is RuleScope.WEEK) or (
            self.day_checks != tuple(r for r in checks if r.scope is RuleScope.DAY)
        ):
            raise ValueError("weekly DAY/WEEK checks differ from complete authoritative KB")
        for check in self.required_checks:
            _validate_week_rule_policy(check)  # Reject unsupported legacy WEEK predicates here.
        for check in self.day_checks:
            _validate_day_rule_policy(check)
        return self


class ExpectedWeekCheckManifest(_WeekManifestContent, _DailySnapshot):
    _body_type = _WeekManifestContent


class WeeklySearchLimits(_DailyModel):
    """Synthetic resource ceilings, not nutritional limits or a production SLO."""

    schema_version: Literal["weekly-search-limits.v1"] = "weekly-search-limits.v1"
    max_nodes: Annotated[int, Field(ge=0, le=200_000)] = 10_000
    max_option_evaluations: Annotated[int, Field(ge=0, le=150)] = 150
    max_day_evaluations: Annotated[int, Field(ge=0, le=4096)] = 256
    max_week_evaluations: Annotated[int, Field(ge=0, le=4096)] = 256
    max_predicate_evaluations: Annotated[int, Field(ge=0, le=1_000_000)] = 100_000
    max_cache_entries: Annotated[int, Field(ge=0, le=4096)] = 256
    max_diagnostics: Annotated[int, Field(ge=0, le=1000)] = 100
    max_proof_records: Annotated[int, Field(ge=0, le=8192)] = 1024
    max_proof_bytes: Annotated[int, Field(ge=0, le=1_048_576)] = 524_288
    deadline: Annotated[int | float, Field(allow_inf_nan=False)] | None = None


class WeeklyFrontierChoice(WeeklyTrialChoice):
    """One declaration in a chronological prefix, not a coverage certificate."""


class WeeklySearchState(_DailyModel):
    coverage: Literal["NOT_VERIFIED"] = "NOT_VERIFIED"
    phase: Literal["NOT_STARTED", "PREPARING", "SEARCHING", "INTERRUPTED"] = "NOT_STARTED"
    exhaustive: bool = False
    nodes: Annotated[int, Field(ge=0, le=200_000)] = 0
    option_evaluations: Annotated[int, Field(ge=0, le=150)] = 0
    day_evaluations: Annotated[int, Field(ge=0, le=4096)] = 0
    week_evaluations: Annotated[int, Field(ge=0, le=4096)] = 0
    predicate_evaluations: Annotated[int, Field(ge=0, le=1_000_000)] = 0
    cache_entries: Annotated[int, Field(ge=0, le=4096)] = 0
    proof_records: Annotated[int, Field(ge=0, le=8192)] = 0
    proof_bytes: Annotated[int, Field(ge=0, le=1_048_576)] = 0
    frontier: Annotated[tuple[WeeklyFrontierChoice, ...], Field(max_length=21)] = ()
    next_option_indexes: Annotated[
        tuple[Annotated[int, Field(ge=0, le=50)], ...], Field(max_length=21)
    ] = ()
    exhaustion_reason: (
        Literal[
            "NODE_BUDGET",
            "PREPROCESSING_BUDGET",
            "DAY_BUDGET",
            "WEEK_BUDGET",
            "PREDICATE_BUDGET",
            "PROOF_RECORD_BUDGET",
            "PROOF_BYTE_BUDGET",
            "DEADLINE",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if self.exhaustive:
            raise ValueError("unverified search state cannot establish exhaustive coverage")
        keys = tuple((c.day.day_index, tuple(MealSlot).index(c.slot)) for c in self.frontier)
        if keys != tuple((i // 3 + 1, i % 3) for i in range(len(keys))):
            raise ValueError("frontier must be a chronological 21-slot prefix")
        if self.next_option_indexes and len(self.next_option_indexes) != len(self.frontier):
            raise ValueError("frontier cursor cardinality mismatch")
        if (self.phase == "INTERRUPTED") != (self.exhaustion_reason is not None):
            raise ValueError("interrupted state requires an explicit exhaustion reason")
        if self.phase == "NOT_STARTED" and (
            self.nodes
            or self.option_evaluations
            or self.day_evaluations
            or self.week_evaluations
            or self.predicate_evaluations
            or self.cache_entries
            or self.proof_records
            or self.proof_bytes
            or self.frontier
            or self.next_option_indexes
        ):
            raise ValueError("not-started search cannot contain work or frontier declarations")
        return self


class WeeklyConstraintDiagnostic(_DailyModel):
    request_digest: _ContentDigest
    week_id: _OpaqueId
    week_version: _NonBlank
    stage: Literal["CONTRACT", "RECIPE", "COMBINATION", "DAY", "WEEK", "SEARCH"]
    code: _NonBlank
    message: _NonBlank
    status: RuleStatus
    day: WeekDayReference | None = None
    slot: MealSlot | None = None
    option: MealOptionReference | None = None
    rule_reference: RuleReference | None = None
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_diagnostic(self) -> Self:
        if (self.slot is not None and self.day is None) or (
            self.option is not None and self.slot is None
        ):
            raise ValueError("diagnostic option/slot requires its containing slot/day")
        _evidenced(self.evidence)
        return self


def _bind_trial(request: WeeklyPlanningRequest, trial: WeeklyTrial) -> None:
    if (trial.request_digest, trial.week_id, trial.week_version, trial.start_date) != (
        request.content_digest,
        request.week_id,
        request.week_version,
        request.start_date,
    ):
        raise ValueError("weekly trial differs from request/week identity")
    days = {d.day.day_index: d for d in request.days}
    for choice in trial.choices:
        day = days[choice.day.day_index]
        domain = next(d for d in day.domains if d.slot is choice.slot)
        if choice.day != day.day or choice.option not in domain.options:
            raise ValueError("weekly trial differs from exact day/slot/domain")


class WeeklySolveResult(_DailyModel):
    """Unevaluated Prompt 1 envelope; resolved outcomes are intentionally rejected."""

    schema_version: Literal["weekly-solve-result.v1"] = "weekly-solve-result.v1"
    plan_feasibility: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    weekly_feasibility: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    outcome: DailyOutcome | None = None
    manifest: ExpectedWeekCheckManifest
    limits: WeeklySearchLimits = Field(default_factory=WeeklySearchLimits)
    search: WeeklySearchState = Field(default_factory=WeeklySearchState)
    assignment: WeeklyAssignment | None = None
    trial: WeeklyTrial | None = None
    facts: Annotated[tuple[WeekFact, ...], Field(max_length=3)] = ()
    diagnostics: Annotated[tuple[WeeklyConstraintDiagnostic, ...], Field(max_length=1000)] = ()

    @model_validator(mode="after")
    def validate_handoff(self) -> Self:
        if self.outcome is not None or self.search.phase != "NOT_STARTED":
            raise ValueError("Prompt 1 cannot establish a computed outcome or search progress")
        request = self.manifest.request
        days = {d.day.day_index: d for d in request.days}
        source_ref = _weekly_source_reference(request.source)
        if self.trial is not None:
            _bind_trial(request, self.trial)
        if self.assignment is not None:
            assignment = self.assignment
            if (
                assignment.request_digest,
                assignment.week_id,
                assignment.week_version,
                assignment.start_date,
                assignment.source,
                assignment.daily_source,
                assignment.context_digest,
            ) != (
                request.content_digest,
                request.week_id,
                request.week_version,
                request.start_date,
                source_ref,
                request.source.expected_daily_source,
                request.context_digest,
            ):
                raise ValueError("weekly assignment differs from exact request/source/context")
            selected = []
            for day in assignment.days:
                domain = days[day.day.day_index]
                daily = _daily_request(request, domain)
                if day.day != domain.day or day.trial.request_digest != daily.content_digest:
                    raise ValueError("daily trial differs from exact weekly-derived request")
                allowed = {d.slot: d.options for d in domain.domains}
                for choice in day.trial.choices:
                    if choice.option not in allowed[choice.slot]:
                        raise ValueError("daily assignment differs from weekly slot domain")
                    selected.append((day.day, choice.slot, choice.option))
            if self.trial is not None and set(selected) != {
                (c.day, c.slot, c.option) for c in self.trial.choices
            }:
                raise ValueError("weekly assignment and trial select different options")
        if len({f.observation.fact_id for f in self.facts}) != len(self.facts):
            raise ValueError("duplicate WEEK fact identity")
        options = {o.reference.option_id: o for o in request.source.daily_source.options}
        choices = (
            {} if self.trial is None else {(c.day.day_index, c.slot): c for c in self.trial.choices}
        )
        for fact in self.facts:
            if self.trial is None or (
                fact.request_digest,
                fact.trial_digest,
                fact.week_id,
                fact.week_version,
                fact.source,
                fact.context_digest,
            ) != (
                request.content_digest,
                self.trial.content_digest,
                request.week_id,
                request.week_version,
                source_ref,
                request.context_digest,
            ):
                raise ValueError("WEEK fact differs from exact trial/request/source/context")
            for record in (*fact.contributions, *fact.occurrences):
                selected_choice = choices.get((record.day.day_index, record.slot))
                if selected_choice is None or (record.day, record.option) != (
                    selected_choice.day,
                    selected_choice.option,
                ):
                    raise ValueError("WEEK contributor differs from selected slot/option")
                option = options[record.option.option_id]
                if isinstance(record, WeekMeasurementContribution):
                    measurement = option.measurements[0] if option.measurements else None
                    if measurement is None or (
                        record.measurement_source,
                        record.measurement_digest,
                    ) != (measurement.source, _content_digest(measurement)):
                        raise ValueError("WEEK measurement differs from exact source evidence")
                    if fact.observation.complete and not measurement.complete:
                        raise ValueError("complete WEEK quantity requires complete measurements")
                else:
                    recipe_ids = {
                        c.recipe_snapshot.recipe_id for c in option.combination.components
                    }
                    if set(record.recipe_ids) != recipe_ids or (
                        fact.observation.complete and not option.combination.composition_complete
                    ):
                        raise ValueError("WEEK recipe presence differs from exact composition")
        if len(self.diagnostics) > self.limits.max_diagnostics:
            raise ValueError("weekly diagnostic capacity exceeded")
        known_days = tuple(d.day for d in request.days)
        rules = {(r.rule_id, r.version) for r in self.manifest.knowledge.rules}
        for diagnostic in self.diagnostics:
            if (diagnostic.request_digest, diagnostic.week_id, diagnostic.week_version) != (
                request.content_digest,
                request.week_id,
                request.week_version,
            ) or (diagnostic.day is not None and diagnostic.day not in known_days):
                raise ValueError("weekly diagnostic differs from request/week/day")
            if diagnostic.option is not None:
                assert diagnostic.day is not None and diagnostic.slot is not None
                domain = next(
                    d for d in days[diagnostic.day.day_index].domains if d.slot is diagnostic.slot
                )
                if diagnostic.option not in domain.options:
                    raise ValueError("weekly diagnostic option differs from slot domain")
            if (
                diagnostic.rule_reference is not None
                and (
                    diagnostic.rule_reference.rule_id,
                    diagnostic.rule_reference.version,
                )
                not in rules
            ):
                raise ValueError("weekly diagnostic rule differs from accepted KB")
        _evidence_union(self)
        return self
