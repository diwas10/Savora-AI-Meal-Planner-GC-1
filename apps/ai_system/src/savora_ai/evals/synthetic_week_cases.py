"""Bounded fictional Phase 7.1b inputs and a literal, independent product oracle.

Only the fixed vocabulary below is modelled. This is not a general rule evaluator,
nutrition calculator, provider authentication mechanism or clinical benchmark.
No test modules, production decision helpers or external sources are used as truth.
"""

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import product
from math import prod
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    FactSubjectKind,
    IngredientCoverage,
    RuleContext,
    VersionedFact,
)
from savora_ai.schemas.combinations import (
    CombinationComponent,
    CombinationFacts,
    CombinationMeasurementBasis,
    CombinationObservation,
    ComponentQuantity,
    PortionState,
    PreparationBinding,
    QuantityUnit,
    RecipeSnapshotReference,
)
from savora_ai.schemas.daily import (
    DailyMealOption,
    DailySlotDomain,
    DailySourceReference,
    DailySourceSnapshot,
    FixedMealMeasurement,
    MealOptionReference,
    MealSlot,
    MealSlotSuitability,
)
from savora_ai.schemas.food_graph import FoodEntity, FoodEntityKind, FoodGraphSnapshot
from savora_ai.schemas.knowledge import (
    ApprovalStatus,
    EvidenceReference,
    MeasurementUnit,
    PredicateOperator,
    RuleDefinition,
    RuleDomain,
    RuleEnvironment,
    RuleLifecycle,
    RuleReference,
    RuleScope,
    RuleSeverity,
    _ContractModel,
)
from savora_ai.schemas.knowledge_base import (
    ApplicabilityDescriptor,
    CheckCatalogueEntry,
    KnowledgeBaseSnapshot,
    KnowledgeWorkflow,
    RuleCatalogueCoverage,
)
from savora_ai.schemas.reasoning import FactObservation
from savora_ai.schemas.weekly import (
    WeekDayReference,
    WeeklyDayDomain,
    WeeklyPlanningRequest,
    WeeklySearchLimits,
    WeeklySourceReference,
    WeeklySourceSnapshot,
)

Outcome = Literal["FEASIBLE", "INFEASIBLE", "INSUFFICIENT_DATA", "TIMEOUT"]
ProblemOutcome = Literal["FEASIBLE", "INFEASIBLE", "INSUFFICIENT_DATA"]
Truth = Literal["PASS", "FAIL", "UNKNOWN"]
OptionIndex = Annotated[int, Field(ge=0, le=2)]
MAX_ORACLE_ASSIGNMENTS = 256


class WeekCaseSpec(_ContractModel):
    """The exact limited oracle language; no arbitrary rules/callbacks are accepted."""

    case_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")]
    description: Annotated[str, Field(min_length=1)]
    domains: Annotated[tuple[tuple[OptionIndex, ...], ...], Field(min_length=21, max_length=21)]
    target: Annotated[int, Field(ge=0)] = 63
    day_cap: Annotated[int, Field(ge=0)] | None = None
    repeat_cap: Annotated[int, Field(ge=0, le=21)] = 21
    day_unknown: bool = False
    missing_measurement: bool = False
    duplicate_components: bool = False
    expected_outcome: Outcome = "FEASIBLE"
    limits: WeeklySearchLimits = WeeklySearchLimits(
        max_nodes=2000,
        max_option_evaluations=6,
        max_day_evaluations=256,
        max_week_evaluations=128,
        max_predicate_evaluations=10000,
        max_cache_entries=64,
        max_diagnostics=10,
        max_proof_records=256,
        max_proof_bytes=131072,
    )
    clock_mode: Literal["MONOTONIC", "EXPIRED_CONSTANT"] = "MONOTONIC"

    @model_validator(mode="after")
    def validate_spec(self) -> Self:
        if any(tuple(sorted(set(domain))) != domain for domain in self.domains):
            raise ValueError("oracle domains must be sorted unique literal option indexes")
        if self.clock_mode == "EXPIRED_CONSTANT":
            if self.limits.deadline != 10 or self.expected_outcome != "TIMEOUT":
                raise ValueError("expired clock requires deadline=10 and expected TIMEOUT")
        elif self.limits.deadline is not None:
            raise ValueError("ordinary baseline uses work caps, not nondeterministic deadlines")
        return self


def case_specs() -> tuple[WeekCaseSpec, ...]:
    """Fresh immutable declarations; at most eight leaves per registered workload."""

    def spec(
        name: str,
        description: str,
        *,
        variable: tuple[int, ...] = (),
        overrides: tuple[tuple[int, tuple[int, ...]], ...] = (),
        **changes: object,
    ) -> WeekCaseSpec:
        domains: list[tuple[int, ...]] = [(0, 1) if i in variable else (0,) for i in range(21)]
        for position, options in overrides:
            domains[position] = options
        return WeekCaseSpec.model_validate(
            dict(
                case_id=name,
                description=description,
                domains=tuple(domains),
                **changes,
            )
        )

    exact = WeeklySearchLimits(
        max_nodes=21,
        max_option_evaluations=2,
        max_day_evaluations=14,
        max_week_evaluations=2,
        max_predicate_evaluations=38,
        max_proof_records=10,
    )
    return (
        spec("single", "One fixed option in each of 21 slots."),
        spec("early", "First of eight alternatives is feasible.", variable=(0, 3, 6)),
        spec(
            "late", "Only the last of eight alternatives reaches 75.", variable=(0, 3, 6), target=75
        ),
        spec(
            "exhaustive",
            "Four complete alternatives cannot total 64.",
            variable=(18, 19),
            target=64,
            expected_outcome="INFEASIBLE",
        ),
        spec(
            "unknown-day",
            "Missing required profile prerequisite survives.",
            day_unknown=True,
            expected_outcome="INSUFFICIENT_DATA",
        ),
        spec(
            "unknown-measurement",
            "Missing measurement is not zero.",
            missing_measurement=True,
            expected_outcome="INSUFFICIENT_DATA",
        ),
        spec(
            "unknown-refuted",
            "Known WEEK quantity failure refutes DAY unknown.",
            day_unknown=True,
            target=64,
            expected_outcome="INFEASIBLE",
        ),
        spec(
            "day-pruning",
            "DAY cap refutes the only total-75 completion.",
            variable=(0, 1, 20),
            target=75,
            day_cap=13,
            expected_outcome="INFEASIBLE",
        ),
        spec(
            "week-quantity",
            "Complete known total 63 fails WEEK EQ 64.",
            target=64,
            expected_outcome="INFEASIBLE",
        ),
        spec(
            "week-repetition",
            "Two configurations cannot change canonical recipe identity.",
            variable=(20,),
            target=67,
            repeat_cap=20,
            expected_outcome="INFEASIBLE",
        ),
        spec(
            "repeated-identities",
            "Duplicate components count once per recipe per slot.",
            overrides=((18, (0, 1)), (20, (0, 2))),
            target=75,
            repeat_cap=20,
            duplicate_components=True,
        ),
        spec(
            "empty-domain",
            "An empty original slot domain has no completions.",
            overrides=((20, ()),),
            expected_outcome="INFEASIBLE",
        ),
        spec(
            "exact-work",
            "Exact node, evaluation, predicate and proof-record capacities.",
            limits=exact,
        ),
        spec(
            "node-short",
            "One less node than the full witness requires.",
            limits=WeeklySearchLimits(max_nodes=20),
            expected_outcome="TIMEOUT",
        ),
        spec(
            "option-odd",
            "One option unit cannot reserve execution and replay.",
            limits=WeeklySearchLimits(max_option_evaluations=1),
            expected_outcome="TIMEOUT",
        ),
        spec(
            "day-zero",
            "No DAY evaluation capacity.",
            limits=WeeklySearchLimits(max_day_evaluations=0),
            expected_outcome="TIMEOUT",
        ),
        spec(
            "week-zero",
            "No WEEK evaluation capacity.",
            limits=WeeklySearchLimits(max_week_evaluations=0),
            expected_outcome="TIMEOUT",
        ),
        spec(
            "predicate-zero",
            "No predicate reservation capacity.",
            limits=WeeklySearchLimits(max_predicate_evaluations=0),
            expected_outcome="TIMEOUT",
        ),
        spec(
            "proof-short",
            "Nine records cannot retain the final leaf proof.",
            limits=WeeklySearchLimits(max_proof_records=9),
            expected_outcome="TIMEOUT",
        ),
        spec(
            "proof-bytes-zero",
            "No mandatory certificate byte capacity.",
            limits=WeeklySearchLimits(max_proof_bytes=0),
            expected_outcome="TIMEOUT",
        ),
        spec(
            "cache-zero",
            "No memo capacity; logical alternatives remain intact.",
            variable=(0, 3, 6),
            target=75,
            limits=WeeklySearchLimits(max_cache_entries=0),
        ),
        spec(
            "deadline-before-preparation",
            "Public injected clock is already at deadline.",
            clock_mode="EXPIRED_CONSTANT",
            limits=WeeklySearchLimits(deadline=10),
            expected_outcome="TIMEOUT",
        ),
    )


@dataclass(frozen=True)
class SyntheticWeekCase:
    spec: WeekCaseSpec
    request: WeeklyPlanningRequest
    candidates: tuple[CandidateRecipeFacts, ...]
    knowledge: KnowledgeBaseSnapshot
    context: RuleContext
    sources: WeeklySourceSnapshot

    @property
    def fixture_digest(self) -> str:
        """Full ordered fixture identity, including expected outcome, limits and clock mode."""
        body = dict(
            fixture_version="synthetic-week-benchmark-fixture.v1",
            spec=self.spec.model_dump(mode="json", by_alias=True),
            request=self.request.model_dump(mode="json", by_alias=True),
            candidates=[c.model_dump(mode="json", by_alias=True) for c in self.candidates],
            knowledge=self.knowledge.model_dump(mode="json", by_alias=True),
            context=self.context.model_dump(mode="json", by_alias=True),
            sources=self.sources.model_dump(mode="json", by_alias=True),
        )
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _evidence(name: str = "origin") -> EvidenceReference:
    return EvidenceReference(
        evidence_id="bench-" + name,
        version="1",
        source="Fictional Phase 7 baseline",
        locator="urn:savora:synthetic-benchmark:" + name,
        environment=RuleEnvironment.SYNTHETIC,
    )


def _rule(
    name: str,
    scope: RuleScope,
    attribute: str,
    value: bool | int = True,
    operator: PredicateOperator = PredicateOperator.EQ,
    *,
    unknown: bool = False,
) -> RuleDefinition:
    unit = (
        MeasurementUnit.MG
        if attribute.endswith("quantity_total")
        else MeasurementUnit.DIMENSIONLESS
        if attribute.endswith("slot_occurrences")
        else None
    )
    return RuleDefinition(
        rule_id="bench-" + name,
        version="1",
        scope=scope,
        severity=RuleSeverity.ABSOLUTE,
        domain=RuleDomain.CULINARY,
        attribute=attribute,
        operator=operator,
        value=value,
        unit=unit,
        required_facts=(attribute, "synthetic_profile_enabled") if unknown else (attribute,),
        applicability_reference=RuleReference(rule_id="synthetic-context-enabled", version="1"),
        evidence=(_evidence(),),
        rationale="Synthetic test only; no nutritional meaning",
        lifecycle=RuleLifecycle.ACTIVE,
        approval_status=ApprovalStatus.APPROVED,
        approved_by="fictional-benchmark-reviewer",
        approval_reference=_evidence("approval"),
        environment=RuleEnvironment.SYNTHETIC,
    )


def build_week_case(case_id: str) -> SyntheticWeekCase:
    """Build fresh validated synthetic declarations, never cached computed decisions."""
    spec = next((s for s in case_specs() if s.case_id == case_id), None)
    if spec is None:
        raise ValueError(f"unknown benchmark case: {case_id}")
    evidence = (_evidence(),)
    rules = (
        _rule("profile", RuleScope.PROFILE, "synthetic_profile_flag"),
        _rule("recipe", RuleScope.RECIPE, "synthetic_flag"),
        _rule("combination", RuleScope.COMBINATION, "synthetic_combination_roles_compatible"),
        _rule("day", RuleScope.DAY, "synthetic_day_complete", unknown=spec.day_unknown),
        _rule("week-complete", RuleScope.WEEK, "synthetic_week_complete"),
        _rule("week-total", RuleScope.WEEK, "synthetic_week_quantity_total", spec.target),
        _rule(
            "week-repeat",
            RuleScope.WEEK,
            "synthetic_week_max_recipe_slot_occurrences",
            spec.repeat_cap,
            PredicateOperator.LE,
        ),
    )
    if spec.day_cap is not None:
        rules += (
            _rule(
                "day-cap",
                RuleScope.DAY,
                "synthetic_day_quantity_total",
                spec.day_cap,
                PredicateOperator.LE,
            ),
        )
    nodes = tuple(
        FoodEntity(
            entity_id="bench-node-" + name,
            version="1",
            kind=FoodEntityKind.RECIPE_REFERENCE,
            canonical_name="Fictional " + name,
            catalogue_reference="bench-recipe-" + name,
            evidence=evidence,
        )
        for name in ("a", "b")
    )
    role = FoodEntity(
        entity_id="bench-role",
        version="1",
        kind=FoodEntityKind.CULINARY_ROLE_REFERENCE,
        canonical_name="Fictional role",
        catalogue_reference="bench-role",
        evidence=evidence,
    )
    graph = FoodGraphSnapshot(
        graph_id="bench-graph",
        version="1",
        catalogue_version="bench-foods",
        environment=RuleEnvironment.SYNTHETIC,
        entities=(*nodes, role),
        relations=(),
        evidence=evidence,
    )
    references = tuple(RuleReference(rule_id=r.rule_id, version=r.version) for r in rules)
    cells = tuple(
        CheckCatalogueEntry(
            entry_id=f"bench-{workflow.value}-{scope.value}",
            version="1",
            kb_id="bench-kb",
            kb_version="1",
            check_catalogue_version="bench-checks",
            workflow=workflow,
            scope=scope,
            rule_references=tuple(
                ref for ref, rule in zip(references, rules, strict=True) if rule.scope is scope
            ),
            evidence=evidence,
        )
        for workflow in KnowledgeWorkflow
        for scope in RuleScope
        if workflow is not KnowledgeWorkflow.CRAVING_DISCOVERY
        or scope in (RuleScope.PROFILE, RuleScope.RECIPE)
    )
    kb = build_knowledge_snapshot(
        dict(
            kb_id="bench-kb",
            version="1",
            environment=RuleEnvironment.SYNTHETIC,
            graph_id=graph.graph_id,
            graph_version=graph.version,
            catalogue_version=graph.catalogue_version,
            taxonomy_version=None,
            check_catalogue_version="bench-checks",
            graph=graph,
            rules=rules,
            active_rules=references,
            applicability_descriptors=(
                ApplicabilityDescriptor(
                    reference=RuleReference(rule_id="synthetic-context-enabled", version="1"),
                    rule_references=references,
                    required_context_facts=("synthetic_context_enabled",),
                    evidence=evidence,
                ),
            ),
            check_catalogue=cells,
            rule_catalogue_coverage=tuple(
                RuleCatalogueCoverage(
                    coverage_id="coverage-" + cell.entry_id,
                    version="1",
                    kb_id=cell.kb_id,
                    kb_version=cell.kb_version,
                    check_catalogue_version=cell.check_catalogue_version,
                    workflow=cell.workflow,
                    scope=cell.scope,
                    complete=True,
                    reason="Complete fictional benchmark inventory",
                    evidence=evidence,
                )
                for cell in cells
            ),
            evidence=evidence,
        )
    )
    context = RuleContext.build(
        dict(
            context_id="bench-context",
            version="1",
            profile_id="bench-profile",
            profile_version="1",
            workflow=KnowledgeWorkflow.WEEKLY_PLAN,
            expected_kb_id=kb.kb_id,
            expected_kb_version=kb.version,
            expected_kb_digest=kb.content_digest,
            expected_graph_id=kb.graph_id,
            expected_graph_version=kb.graph_version,
            expected_catalogue_version=kb.catalogue_version,
            expected_taxonomy_version=kb.taxonomy_version,
            expected_check_catalogue_version=kb.check_catalogue_version,
            facts=tuple(
                VersionedFact(
                    fact_id=attribute,
                    version="1",
                    subject_kind=kind,
                    subject_id=owner,
                    subject_version="1",
                    context_id="bench-context" if kind is FactSubjectKind.CONTEXT else None,
                    context_version="1" if kind is FactSubjectKind.CONTEXT else None,
                    observation=FactObservation(
                        fact_id=attribute, value=True, complete=True, evidence=evidence
                    ),
                )
                for attribute, kind, owner in (
                    ("synthetic_context_enabled", FactSubjectKind.CONTEXT, "bench-context"),
                    ("synthetic_profile_flag", FactSubjectKind.PROFILE, "bench-profile"),
                )
            ),
            evidence=evidence,
        )
    )
    candidates = tuple(
        CandidateRecipeFacts.build(
            dict(
                recipe_id="bench-recipe-" + name,
                recipe_version="1",
                catalogue_version=kb.catalogue_version,
                graph_id=kb.graph_id,
                graph_version=kb.graph_version,
                graph_recipe_entity_id=node.entity_id,
                graph_recipe_reference=node,
                snapshot_id="snapshot-" + node.entity_id,
                snapshot_version="1",
                ingredient_coverage=IngredientCoverage(
                    coverage_id="inventory-" + node.entity_id,
                    version="1",
                    recipe_id="bench-recipe-" + name,
                    recipe_version="1",
                    catalogue_version=kb.catalogue_version,
                    lines=(),
                    inventory_complete=True,
                    mapping_complete=True,
                    subingredients_complete=True,
                    gap_reasons=(),
                    evidence=evidence,
                ),
                facts=(
                    VersionedFact(
                        fact_id="synthetic_flag",
                        version="1",
                        subject_kind=FactSubjectKind.RECIPE,
                        subject_id="bench-recipe-" + name,
                        subject_version="1",
                        catalogue_version=kb.catalogue_version,
                        observation=FactObservation(
                            fact_id="synthetic_flag", value=True, complete=True, evidence=evidence
                        ),
                    ),
                ),
                evidence=evidence,
            )
        )
        for node, name in zip(nodes, ("a", "b"), strict=True)
    )
    options = tuple(
        _option(i, candidate, context, role, spec)
        for i, candidate in enumerate((candidates[0], candidates[0], candidates[1]))
    )
    daily = DailySourceSnapshot.build(
        dict(
            source_id="bench-daily-source",
            version="1",
            context=context,
            options=options,
            evidence=evidence,
        )
    )
    source = WeeklySourceSnapshot.build(
        dict(
            source_id="bench-week-source",
            version="1",
            daily_source=daily,
            expected_daily_source=DailySourceReference(
                source_id=daily.source_id,
                version=daily.version,
                content_digest=daily.content_digest,
            ),
            evidence=evidence,
        )
    )
    start = date(2026, 10, 19)
    request = WeeklyPlanningRequest.build(
        dict(
            request_id="bench-request",
            version="1",
            week_id="bench-week",
            week_version="1",
            start_date=start.isoformat(),
            context_id=context.context_id,
            context_version=context.version,
            context_digest=context.content_digest,
            source=source,
            expected_source=WeeklySourceReference(
                source_id=source.source_id,
                version=source.version,
                content_digest=source.content_digest,
            ),
            days=tuple(
                WeeklyDayDomain(
                    day=WeekDayReference(
                        week_id="bench-week",
                        week_version="1",
                        day_id=f"bench-day-{d + 1}",
                        day_index=d + 1,
                        calendar_date=(start + timedelta(days=d)).isoformat(),
                    ),
                    domains=tuple(
                        DailySlotDomain(
                            slot=slot,
                            options=tuple(options[i].reference for i in spec.domains[3 * d + j]),
                        )
                        for j, slot in enumerate(MealSlot)
                    ),
                )
                for d in range(7)
            ),
        )
    )
    return SyntheticWeekCase(spec, request, candidates, kb, context, source)


def _option(
    index: int,
    candidate: CandidateRecipeFacts,
    context: RuleContext,
    role: FoodEntity,
    spec: WeekCaseSpec,
) -> DailyMealOption:
    evidence = (_evidence(),)
    recipe = RecipeSnapshotReference(
        recipe_id=candidate.recipe_id,
        recipe_version=candidate.recipe_version,
        snapshot_id=candidate.snapshot_id,
        snapshot_version=candidate.snapshot_version,
        content_digest=candidate.content_digest,
        catalogue_version=candidate.catalogue_version,
    )
    prep = PreparationBinding(
        preparation_id="prepared-" + candidate.recipe_id,
        version="1",
        recipe_snapshot=recipe,
        basis_reference=_evidence("basis-" + candidate.recipe_id),
        evidence=evidence,
    )
    parts = tuple(
        CombinationComponent(
            component_id=f"part-{i}",
            recipe_snapshot=recipe,
            preparation=prep,
            quantity=ComponentQuantity(
                amount=index + 1,
                unit=QuantityUnit.G,
                preparation_id=prep.preparation_id,
                preparation_version=prep.version,
                basis_reference=prep.basis_reference,
                portion_reference=_evidence(f"portion-{index}"),
                evidence=evidence,
            ),
            role_references=(role,),
            evidence=evidence,
        )
        for i in range(2 if spec.duplicate_components else 1)
    )
    combo = CombinationFacts.build(
        dict(
            combination_id="meal-" + candidate.recipe_id,
            version="1",
            snapshot_id=f"bench-combo-{index}",
            snapshot_version="1",
            components=parts,
            composition_complete=True,
            composition_gap_reasons=(),
            portion_state=PortionState.FIXED,
            portion_configuration_id=f"bench-config-{index}",
            portion_configuration_version="1",
            observations=(
                CombinationObservation(
                    fact_id="synthetic_combination_roles_compatible",
                    version="1",
                    combination_id="meal-" + candidate.recipe_id,
                    combination_version="1",
                    observation=FactObservation(
                        fact_id="synthetic_combination_roles_compatible",
                        value=True,
                        complete=True,
                        evidence=evidence,
                    ),
                ),
            ),
            context_id=context.context_id,
            context_version=context.version,
            context_digest=context.content_digest,
            kb_id=context.expected_kb_id,
            kb_version=context.expected_kb_version,
            kb_digest=context.expected_kb_digest,
            graph_id=context.expected_graph_id,
            graph_version=context.expected_graph_version,
            catalogue_version=context.expected_catalogue_version,
            taxonomy_version=context.expected_taxonomy_version,
            check_catalogue_version=context.expected_check_catalogue_version,
            evidence=evidence,
        )
    )
    ref = MealOptionReference(
        option_id=f"bench-option-{index}",
        combination_id=combo.combination_id,
        combination_version=combo.version,
        snapshot_id=combo.snapshot_id,
        snapshot_version=combo.snapshot_version,
        combination_digest=combo.content_digest,
        portion_state=PortionState.FIXED,
        portion_configuration_id=combo.portion_configuration_id,
        portion_configuration_version=combo.portion_configuration_version,
    )
    external = DailySourceReference(
        source_id="fictional-provider", version="1", content_digest="a" * 64
    )
    return DailyMealOption(
        reference=ref,
        combination=combo,
        suitability=MealSlotSuitability(
            option=ref,
            source=external,
            slots=tuple(MealSlot),
            complete=True,
            evidence=evidence,
        ),
        measurements=(
            FixedMealMeasurement(
                option=ref,
                source=external,
                value=None if spec.missing_measurement else (3, 7, 11)[index],
                complete=not spec.missing_measurement,
                unit=MeasurementUnit.MG,
                measurement_basis=CombinationMeasurementBasis.FIXED_PORTION_TOTAL,
                components=parts,
                basis_reference=_evidence(f"measurement-{index}"),
                evidence=evidence,
            ),
        ),
    )


# Explicit hard-status truth table, independent of aggregate_hard_status.
_TRUTH_TABLE: dict[tuple[Truth, Truth], Truth] = {
    ("PASS", "PASS"): "PASS",
    ("PASS", "FAIL"): "FAIL",
    ("PASS", "UNKNOWN"): "UNKNOWN",
    ("FAIL", "PASS"): "FAIL",
    ("FAIL", "FAIL"): "FAIL",
    ("FAIL", "UNKNOWN"): "FAIL",
    ("UNKNOWN", "PASS"): "UNKNOWN",
    ("UNKNOWN", "FAIL"): "FAIL",
    ("UNKNOWN", "UNKNOWN"): "UNKNOWN",
}


def literal_trial_status(spec: WeekCaseSpec, selected: tuple[int, ...]) -> Truth:
    """Only this fixture language: known prerequisites, one DAY flag and exact totals."""
    if len(selected) != 21 or any(
        type(i) is not int or i not in domain
        for i, domain in zip(selected, spec.domains, strict=True)
    ):
        raise ValueError("witness is not in the literal original 21-slot domains")
    weights = [(3, 7, 11)[i] for i in selected]
    days: list[Truth] = []
    for d in range(7):
        status: Truth = "UNKNOWN" if spec.day_unknown else "PASS"
        if spec.day_cap is not None:
            quantity: Truth = (
                "UNKNOWN"
                if spec.missing_measurement
                else "PASS"
                if sum(weights[3 * d : 3 * d + 3]) <= spec.day_cap
                else "FAIL"
            )
            status = _TRUTH_TABLE[status, quantity]
        days.append(status)
    complete: Truth = "PASS" if all(d == "PASS" for d in days) else "UNKNOWN"
    total: Truth = (
        "UNKNOWN" if spec.missing_measurement else "PASS" if sum(weights) == spec.target else "FAIL"
    )
    # Options 0 and 1 are configurations of A; option 2 is B. Duplicate
    # components within a meal never create another slot occurrence.
    counts = Counter("A" if i in (0, 1) else "B" for i in selected)
    repeat: Truth = "PASS" if max(counts.values()) <= spec.repeat_cap else "FAIL"
    result: Truth = "PASS"
    for check in (*days, complete, total, repeat):
        result = _TRUTH_TABLE[result, check]
    return result


@dataclass(frozen=True)
class OracleResult:
    outcome: ProblemOutcome
    first_witness: tuple[int, ...] | None
    assignments: int
    passed: int
    failed: int
    unknown: int


def exhaustive_oracle(
    spec: WeekCaseSpec,
    *,
    max_assignments: int = MAX_ORACLE_ASSIGNMENTS,
) -> OracleResult:
    """Exhaust the bounded original Cartesian space, irrespective of solver budgets.

    TIMEOUT is not an oracle truth value. For interrupted solver workloads this
    supplies problem truth only, not a simulation of reserved work or deadlines.
    """
    spec = WeekCaseSpec.model_validate(spec)
    if type(max_assignments) is not int or not 1 <= max_assignments <= MAX_ORACLE_ASSIGNMENTS:
        raise ValueError("oracle bound must be an integer in 1..256")
    size = prod(len(domain) for domain in spec.domains)
    if size > max_assignments:
        raise ValueError(f"oracle Cartesian size {size} exceeds bound {max_assignments}")
    counts = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
    first = None
    for selected in product(*spec.domains):
        status = literal_trial_status(spec, selected)
        counts[status] += 1
        if status == "PASS" and first is None:
            first = selected
    outcome: ProblemOutcome = (
        "FEASIBLE"
        if first is not None
        else "INSUFFICIENT_DATA"
        if counts["UNKNOWN"]
        else "INFEASIBLE"
    )
    return OracleResult(outcome, first, size, counts["PASS"], counts["FAIL"], counts["UNKNOWN"])
