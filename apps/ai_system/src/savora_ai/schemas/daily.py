"""Synthetic daily declarations and exact bindings, not evaluation or source authentication.

Only FIXED, evidenced options may eventually establish daily feasibility. These
contracts execute no DAY predicate, aggregation, conversion or search.
"""

from enum import StrEnum
from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, model_validator

from savora_ai.schemas.candidates import RuleContext, _build_snapshot, _content_digest
from savora_ai.schemas.combinations import (
    CombinationComponent,
    CombinationFacts,
    CombinationMeasurementBasis,
    PortionState,
)
from savora_ai.schemas.filtering import (
    _APPLICABILITY,
    _DAY_MAX_TOTAL,
    _evidence_union,
    _validate_day_rule_policy,
)
from savora_ai.schemas.food_graph import _OpaqueId
from savora_ai.schemas.knowledge import (
    ApprovalStatus,
    EvidenceReference,
    MeasurementUnit,
    RuleDefinition,
    RuleEnvironment,
    RuleLifecycle,
    RuleReference,
    RuleScope,
    RuleSeverity,
    _ContractModel,
    _NonBlank,
    _validate_evidence,
)
from savora_ai.schemas.knowledge_base import (
    KnowledgeBaseSnapshot,
    KnowledgeWorkflow,
    _canonical_enum_inputs,
    _ContentDigest,
)
from savora_ai.schemas.reasoning import FactObservation, RuleStatus

_MAX_OPTIONS = 150
_MAX_DOMAIN = 50
_MAX_COMPONENTS = 32


class MealSlot(StrEnum):
    BREAKFAST = "BREAKFAST"
    LUNCH = "LUNCH"
    DINNER = "DINNER"


class DailyOutcome(StrEnum):
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    TIMEOUT = "TIMEOUT"


class _DailyModel(_ContractModel):
    @model_validator(mode="after")
    def validate_metadata(self) -> Self:
        _canonical_enum_inputs(self)
        _evidence_union(self)
        return self


def _evidenced(evidence: tuple[EvidenceReference, ...]) -> None:
    if not evidence:
        raise ValueError("daily records require evidence, including declarations of gaps")
    _validate_evidence(evidence)


def _slots(slots: tuple[MealSlot, ...], *, exact: bool = False) -> None:
    if len(set(slots)) != len(slots) or (exact and set(slots) != set(MealSlot)):
        raise ValueError("daily slots must be unique and include exactly BREAKFAST/LUNCH/DINNER")


class DailySourceReference(_DailyModel):
    """An independent pin when provided by a trusted loader; never a credential."""

    source_id: _OpaqueId
    version: _NonBlank
    content_digest: _ContentDigest


class MealOptionReference(_DailyModel):
    schema_version: Literal["meal-option-reference.v1"] = "meal-option-reference.v1"
    option_id: _OpaqueId
    combination_id: _OpaqueId
    combination_version: _NonBlank
    snapshot_id: _OpaqueId
    snapshot_version: _NonBlank
    combination_digest: _ContentDigest
    portion_state: PortionState
    portion_configuration_id: _OpaqueId | None = None
    portion_configuration_version: _NonBlank | None = None

    @model_validator(mode="after")
    def validate_portions(self) -> Self:
        fixed = self.portion_state is PortionState.FIXED
        if fixed != (self.portion_configuration_id is not None) or fixed != (
            self.portion_configuration_version is not None
        ):
            raise ValueError(
                "option requires exact FIXED configuration pins or entirely UNASSIGNED"
            )
        return self


def _option_key(option: MealOptionReference) -> tuple[object, ...]:
    return (
        option.combination_id,
        option.combination_version,
        option.snapshot_id,
        option.snapshot_version,
        option.combination_digest,
        option.portion_state,
        option.portion_configuration_id,
        option.portion_configuration_version,
    )


def _combination_key(combination: CombinationFacts) -> tuple[object, ...]:
    return (
        combination.combination_id,
        combination.version,
        combination.snapshot_id,
        combination.snapshot_version,
        combination.content_digest,
        combination.portion_state,
        combination.portion_configuration_id,
        combination.portion_configuration_version,
    )


class MealSlotSuitability(_DailyModel):
    schema_version: Literal["meal-slot-suitability.v1"] = "meal-slot-suitability.v1"
    option: MealOptionReference
    source: DailySourceReference
    slots: Annotated[tuple[MealSlot, ...], Field(max_length=3)]
    complete: bool
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_suitability(self) -> Self:
        _slots(self.slots)
        _evidenced(self.evidence)
        return self


class FixedMealMeasurement(_DailyModel):
    """One whole-meal integer total, never an ingredient total or implicit conversion."""

    schema_version: Literal["fixed-meal-measurement.v1"] = "fixed-meal-measurement.v1"
    measurement_policy_version: Literal["synthetic-fixed-meal-measurements.v1"] = (
        "synthetic-fixed-meal-measurements.v1"
    )
    option: MealOptionReference
    source: DailySourceReference
    attribute: Literal["synthetic_meal_quantity_total"] = "synthetic_meal_quantity_total"
    value: Annotated[int, Field(ge=0, le=_DAY_MAX_TOTAL // 3)] | None
    complete: bool
    unit: MeasurementUnit
    measurement_basis: CombinationMeasurementBasis
    aggregation_level: Literal["MEAL_TOTAL"] = "MEAL_TOTAL"
    components: Annotated[
        tuple[CombinationComponent, ...], Field(min_length=1, max_length=_MAX_COMPONENTS)
    ]
    basis_reference: EvidenceReference
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_measurement(self) -> Self:
        if self.option.portion_state is not PortionState.FIXED or any(
            part.quantity is None for part in self.components
        ):
            raise ValueError("measurements require exact FIXED preparations and quantities")
        if self.unit is not MeasurementUnit.MG or (
            self.measurement_basis is not CombinationMeasurementBasis.FIXED_PORTION_TOTAL
        ):
            raise ValueError("synthetic meal measurement requires mg and FIXED_PORTION_TOTAL")
        if self.complete and self.value is None:
            raise ValueError("complete measurement requires an explicit integer value")
        if len({part.component_id for part in self.components}) != len(self.components):
            raise ValueError("duplicate measurement component occurrence")
        _evidenced(self.evidence)
        return self


class DailyMealOption(_DailyModel):
    reference: MealOptionReference
    combination: CombinationFacts
    suitability: MealSlotSuitability | None = None
    measurements: Annotated[tuple[FixedMealMeasurement, ...], Field(max_length=1)] = ()

    @model_validator(mode="after")
    def validate_option(self) -> Self:
        if _option_key(self.reference) != _combination_key(self.combination):
            raise ValueError("option differs from exact combination snapshot/configuration")
        if len(self.combination.components) > _MAX_COMPONENTS:
            raise ValueError("daily combination component bound exceeded")
        if self.suitability is not None and self.suitability.option != self.reference:
            raise ValueError("suitability differs from exact option")
        components = {part.component_id: part for part in self.combination.components}
        for measurement in self.measurements:
            if (
                measurement.option != self.reference
                or {part.component_id: part for part in measurement.components} != components
            ):
                raise ValueError("measurement differs from exact option/preparations/quantities")
        return self


class _DailySnapshot(_DailyModel):
    content_digest: _ContentDigest
    _body_type: ClassVar[type[_DailyModel]]

    @model_validator(mode="after")
    def validate_digest(self) -> Self:
        if self.content_digest != _content_digest(self):
            raise ValueError("daily snapshot content digest mismatch")
        return self

    @classmethod
    def build(
        cls, content: Self | dict[str, object], *, expected_digest: str | None = None
    ) -> Self:
        return _build_snapshot(cls, cls._body_type, content, expected_digest)


def _context_binding(combination: CombinationFacts, context: RuleContext) -> None:
    expected = (
        context.context_id,
        context.version,
        context.content_digest,
        context.expected_kb_id,
        context.expected_kb_version,
        context.expected_kb_digest,
        context.expected_graph_id,
        context.expected_graph_version,
        context.expected_catalogue_version,
        context.expected_taxonomy_version,
        context.expected_check_catalogue_version,
    )
    actual = (
        combination.context_id,
        combination.context_version,
        combination.context_digest,
        combination.kb_id,
        combination.kb_version,
        combination.kb_digest,
        combination.graph_id,
        combination.graph_version,
        combination.catalogue_version,
        combination.taxonomy_version,
        combination.check_catalogue_version,
    )
    if expected != actual:
        raise ValueError("daily option context/KB/release mismatch")


class _DailySourceContent(_DailyModel):
    schema_version: Literal["daily-source-snapshot.v1"] = "daily-source-snapshot.v1"
    source_id: _OpaqueId
    version: _NonBlank
    context: RuleContext
    options: Annotated[tuple[DailyMealOption, ...], Field(max_length=_MAX_OPTIONS)]
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if self.context.workflow is not KnowledgeWorkflow.WEEKLY_PLAN:
            raise ValueError("daily contracts require WEEKLY_PLAN, not craving or swaps")
        refs = tuple(option.reference for option in self.options)
        if len({ref.option_id for ref in refs}) != len(refs) or len(
            {_option_key(ref) for ref in refs}
        ) != len(refs):
            raise ValueError("duplicate option identity or aliased combination snapshot")
        snapshots: dict[tuple[str, str], str] = {}
        recipes: dict[str, object] = {}
        preparations: dict[tuple[object, ...], object] = {}
        configurations: dict[tuple[str, str, str], str] = {}
        counts: dict[str, int] = {}
        external: dict[tuple[str, str], str] = {}
        for option in self.options:
            combo, ref = option.combination, option.reference
            _context_binding(combo, self.context)
            key = combo.snapshot_id, combo.snapshot_version
            if snapshots.setdefault(key, combo.content_digest) != combo.content_digest:
                raise ValueError("conflicting combination snapshot identity")
            counts[combo.combination_id] = counts.get(combo.combination_id, 0) + 1
            if counts[combo.combination_id] > _MAX_DOMAIN:
                raise ValueError("combination configuration cardinality bound exceeded")
            if ref.portion_configuration_id is not None:
                assert ref.portion_configuration_version is not None
                config_key = (
                    ref.combination_id,
                    ref.portion_configuration_id,
                    ref.portion_configuration_version,
                )
                if (
                    configurations.setdefault(config_key, ref.combination_digest)
                    != ref.combination_digest
                ):
                    raise ValueError("conflicting fixed configuration identity")
            for part in combo.components:
                recipe = part.recipe_snapshot
                if recipes.setdefault(recipe.recipe_id, recipe) != recipe:
                    raise ValueError("conflicting recipe snapshot across daily options")
                preparation = part.preparation
                prep_key = (recipe, preparation.preparation_id, preparation.version)
                if preparations.setdefault(prep_key, preparation) != preparation:
                    raise ValueError("conflicting preparation identity across daily options")
            declarations = (
                *((option.suitability,) if option.suitability is not None else ()),
                *option.measurements,
            )
            for record in declarations:
                source = record.source
                key = source.source_id, source.version
                if key == (self.source_id, self.version):
                    raise ValueError("external declarations cannot self-reference the daily source")
                if external.setdefault(key, source.content_digest) != source.content_digest:
                    raise ValueError("conflicting external source identity/version/digest")
        _evidenced(self.evidence)
        return self


class DailySourceSnapshot(_DailySourceContent, _DailySnapshot):
    _body_type = _DailySourceContent


def _source_reference(source: DailySourceSnapshot) -> DailySourceReference:
    return DailySourceReference(
        source_id=source.source_id, version=source.version, content_digest=source.content_digest
    )


class DailySlotDomain(_DailyModel):
    slot: MealSlot
    options: Annotated[tuple[MealOptionReference, ...], Field(max_length=_MAX_DOMAIN)]

    @model_validator(mode="after")
    def validate_domain(self) -> Self:
        if len({ref.option_id for ref in self.options}) != len(self.options):
            raise ValueError("duplicate option IDs in slot domain")
        return self


class _DailyRequestContent(_DailyModel):
    schema_version: Literal["daily-planning-request.v1"] = "daily-planning-request.v1"
    policy_version: Literal["synthetic-daily-contracts.v1"] = "synthetic-daily-contracts.v1"
    request_id: _OpaqueId
    version: _NonBlank
    day_id: _OpaqueId
    context_id: _OpaqueId
    context_version: _NonBlank
    context_digest: _ContentDigest
    expected_source: DailySourceReference
    source: DailySourceSnapshot
    domains: Annotated[tuple[DailySlotDomain, ...], Field(min_length=3, max_length=3)]

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        _slots(tuple(domain.slot for domain in self.domains), exact=True)
        context = self.source.context
        if (self.context_id, self.context_version, self.context_digest) != (
            context.context_id,
            context.version,
            context.content_digest,
        ) or self.expected_source != _source_reference(self.source):
            raise ValueError("request source/context pin mismatch")
        accepted = {option.reference.option_id: option.reference for option in self.source.options}
        for domain in self.domains:
            for option in domain.options:
                if accepted.get(option.option_id) != option:
                    raise ValueError("domain option differs from exact source snapshot")
        return self


class DailyPlanningRequest(_DailyRequestContent, _DailySnapshot):
    _body_type = _DailyRequestContent


class AssignedMeal(_DailyModel):
    slot: MealSlot
    option: MealOptionReference

    @model_validator(mode="after")
    def validate_fixed(self) -> Self:
        if self.option.portion_state is not PortionState.FIXED:
            raise ValueError("daily assignments require FIXED options")
        return self


class _DailyAssignmentContent(_DailyModel):
    schema_version: Literal["daily-assignment.v1"] = "daily-assignment.v1"
    request_digest: _ContentDigest
    day_id: _OpaqueId
    source: DailySourceReference
    context_digest: _ContentDigest
    slots: Annotated[tuple[AssignedMeal, ...], Field(min_length=3, max_length=3)]

    @model_validator(mode="after")
    def validate_assignment(self) -> Self:
        _slots(tuple(item.slot for item in self.slots), exact=True)
        return self


class DailyAssignment(_DailyAssignmentContent, _DailySnapshot):
    """A complete structural hypothesis, not a feasibility decision."""

    _body_type = _DailyAssignmentContent


class DayMeasurementContribution(_DailyModel):
    slot: MealSlot
    measurement: FixedMealMeasurement


class DayFact(_DailyModel):
    schema_version: Literal["day-fact.v1"] = "day-fact.v1"
    request_digest: _ContentDigest
    assignment_digest: _ContentDigest
    day_id: _OpaqueId
    source: DailySourceReference
    context_digest: _ContentDigest
    observation: FactObservation
    measurement_basis: Literal["DAY_FIXED_TOTAL"] | None = None
    basis_reference: EvidenceReference | None = None
    contributions: Annotated[tuple[DayMeasurementContribution, ...], Field(max_length=3)] = ()

    @model_validator(mode="after")
    def validate_fact(self) -> Self:
        observation = self.observation
        numeric = observation.fact_id == "synthetic_day_quantity_total"
        if observation.fact_id not in ("synthetic_day_complete", "synthetic_day_quantity_total"):
            raise ValueError("unsupported DAY fact")
        if numeric:
            if observation.value is not None and not (
                type(observation.value) is int and 0 <= observation.value <= _DAY_MAX_TOTAL
            ):
                raise ValueError("DAY quantity requires a bounded nonnegative integer")
            if observation.value is not None and observation.unit is not MeasurementUnit.MG:
                raise ValueError("DAY quantity requires mg")
            if self.measurement_basis != "DAY_FIXED_TOTAL" or self.basis_reference is None:
                raise ValueError("DAY quantity requires evidenced DAY_FIXED_TOTAL basis")
            _slots(tuple(item.slot for item in self.contributions), exact=observation.complete)
            if observation.complete and any(
                not item.measurement.complete for item in self.contributions
            ):
                raise ValueError("complete DAY declarations require complete meal measurements")
        elif (
            (observation.value is not None and type(observation.value) is not bool)
            or observation.unit is not None
            or self.measurement_basis is not None
            or self.basis_reference is not None
            or self.contributions
        ):
            raise ValueError("DAY completeness requires boolean/null and no numeric basis")
        return self


class _DayManifestContent(_DailyModel):
    schema_version: Literal["expected-day-check-manifest.v1"] = "expected-day-check-manifest.v1"
    day_policy_version: Literal["synthetic-day-policy.v1"] = "synthetic-day-policy.v1"
    stage: Literal["DAY"] = "DAY"
    request: DailyPlanningRequest
    knowledge: KnowledgeBaseSnapshot
    required_checks: tuple[RuleDefinition, ...]
    deferred_checks: tuple[RuleDefinition, ...]

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        kb, context = self.knowledge, self.request.source.context
        if kb.environment is not RuleEnvironment.SYNTHETIC or (
            kb.kb_id,
            kb.version,
            kb.content_digest,
            kb.graph_id,
            kb.graph_version,
            kb.catalogue_version,
            kb.taxonomy_version,
            kb.check_catalogue_version,
            kb.workflow_policy_version,
        ) != (
            context.expected_kb_id,
            context.expected_kb_version,
            context.expected_kb_digest,
            context.expected_graph_id,
            context.expected_graph_version,
            context.expected_catalogue_version,
            context.expected_taxonomy_version,
            context.expected_check_catalogue_version,
            context.workflow_policy_version,
        ):
            raise ValueError("daily manifest KB/context/release mismatch")
        rules = {(rule.rule_id, rule.version): rule for rule in kb.rules}
        selected = {
            scope: tuple(
                sorted(
                    (
                        rules[(ref.rule_id, ref.version)]
                        for entry in kb.check_catalogue
                        if entry.workflow is context.workflow and entry.scope is scope
                        for ref in entry.rule_references
                    ),
                    key=lambda rule: (rule.rule_id, rule.version),
                )
            )
            for scope in (RuleScope.DAY, RuleScope.WEEK)
        }
        if self.required_checks != selected[RuleScope.DAY] or (
            self.deferred_checks != selected[RuleScope.WEEK]
        ):
            raise ValueError("DAY/WEEK checks differ from complete authoritative KB selection")
        for rule in (*self.required_checks, *self.deferred_checks):
            if (
                rule.lifecycle is not RuleLifecycle.ACTIVE
                or rule.severity is not RuleSeverity.ABSOLUTE
                or rule.approval_status is not ApprovalStatus.APPROVED
            ):
                raise ValueError("daily obligations must remain ACTIVE, ABSOLUTE and APPROVED")
        for rule in self.required_checks:
            _validate_day_rule_policy(rule)
        descriptors = {
            (item.reference.rule_id, item.reference.version): item
            for item in kb.applicability_descriptors
        }
        pending = [
            (rule.applicability_reference.rule_id, rule.applicability_reference.version)
            for rule in (*self.required_checks, *self.deferred_checks)
        ]
        visited: set[tuple[str, str]] = set()
        while pending:
            key = pending.pop()
            if key in visited:
                continue
            visited.add(key)
            descriptor = descriptors[key]  # KB validation guarantees exact dependency resolution.
            fact = _APPLICABILITY.get(key)
            if fact is None or descriptor.required_context_facts != (fact,):
                raise ValueError("unsupported daily applicability descriptor")
            pending.extend((ref.rule_id, ref.version) for ref in descriptor.dependencies)
        return self


class ExpectedDayCheckManifest(_DayManifestContent, _DailySnapshot):
    """Authoritative selection relative to supplied KB; no authentication or evaluation."""

    _body_type = _DayManifestContent


class ConstraintDiagnostic(_DailyModel):
    request_digest: _ContentDigest
    stage: Literal["CONTRACT", "RECIPE", "COMBINATION", "DAY", "SEARCH"]
    code: _NonBlank
    message: _NonBlank
    status: RuleStatus
    slot: MealSlot | None = None
    option: MealOptionReference | None = None
    rule_reference: RuleReference | None = None
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_diagnostic(self) -> Self:
        _evidenced(self.evidence)
        return self


class DailyPlanningResult(_DailyModel):
    """Prompt 1 handoff envelope. Resolved outcomes require Prompt 2's computed contract."""

    schema_version: Literal["daily-planning-result.v1"] = "daily-planning-result.v1"
    plan_feasibility: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    weekly_feasibility: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    outcome: DailyOutcome | None = None
    manifest: ExpectedDayCheckManifest
    assignment: DailyAssignment | None = None
    facts: Annotated[tuple[DayFact, ...], Field(max_length=2)] = ()
    diagnostics: Annotated[tuple[ConstraintDiagnostic, ...], Field(max_length=1000)] = ()

    @model_validator(mode="after")
    def validate_handoff(self) -> Self:
        if self.outcome is not None:
            raise ValueError("Prompt 1 does not establish a resolved daily outcome")
        request = self.manifest.request
        source = _source_reference(request.source)
        context_digest = request.context_digest
        domains = {domain.slot: domain.options for domain in request.domains}
        if self.assignment is not None:
            assignment = self.assignment
            if (
                assignment.request_digest != request.content_digest
                or assignment.source != source
                or assignment.context_digest != context_digest
                or assignment.day_id != request.day_id
                or any(item.option not in domains[item.slot] for item in assignment.slots)
            ):
                raise ValueError("assignment differs from exact request/domain/source/context")
        if len({fact.observation.fact_id for fact in self.facts}) != len(self.facts):
            raise ValueError("duplicate DAY fact identity")
        options = {option.reference.option_id: option for option in request.source.options}
        for fact in self.facts:
            if self.assignment is None or (
                fact.request_digest != request.content_digest
                or fact.assignment_digest != self.assignment.content_digest
                or fact.source != source
                or fact.context_digest != context_digest
                or fact.day_id != request.day_id
            ):
                raise ValueError("DAY fact differs from exact assignment/request/source/context")
            assigned = {item.slot: item.option for item in self.assignment.slots}
            for contribution in fact.contributions:
                measurement = contribution.measurement
                if measurement.option != assigned[contribution.slot] or measurement not in (
                    options[measurement.option.option_id].measurements
                ):
                    raise ValueError("DAY contributor differs from selected source measurement")
        for diagnostic in self.diagnostics:
            if diagnostic.request_digest != request.content_digest or (
                diagnostic.option is not None
                and (diagnostic.slot is None or diagnostic.option not in domains[diagnostic.slot])
            ):
                raise ValueError("diagnostic differs from request/slot domain")
            if diagnostic.rule_reference is not None and not any(
                (rule.rule_id, rule.version)
                == (diagnostic.rule_reference.rule_id, diagnostic.rule_reference.version)
                for rule in self.manifest.knowledge.rules
            ):
                raise ValueError("diagnostic rule differs from accepted KB")
        return self
