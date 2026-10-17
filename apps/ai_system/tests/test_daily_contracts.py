"""Independent fictional daily contracts; no clinical or source-authority claims."""

import hashlib
import json
from enum import StrEnum
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from savora_ai.core.reasoning.combinations import evaluate_combination
from savora_ai.core.reasoning.filtering import filter_candidates
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.manifest import build_expected_check_manifest
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    FactSubjectKind,
    IngredientCoverage,
    RuleContext,
    VersionedFact,
    validate_contract_json,
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
    AssignedMeal,
    ConstraintDiagnostic,
    DailyAssignment,
    DailyMealOption,
    DailyOutcome,
    DailyPlanningRequest,
    DailyPlanningResult,
    DailySlotDomain,
    DailySourceReference,
    DailySourceSnapshot,
    DayFact,
    DayMeasurementContribution,
    ExpectedDayCheckManifest,
    FixedMealMeasurement,
    MealOptionReference,
    MealSlot,
    MealSlotSuitability,
)
from savora_ai.schemas.filtering import ExpectedCheckManifest
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
)
from savora_ai.schemas.knowledge_base import (
    ApplicabilityDescriptor,
    CheckCatalogueEntry,
    KnowledgeBaseSnapshot,
    KnowledgeWorkflow,
    RuleCatalogueCoverage,
)
from savora_ai.schemas.reasoning import FactObservation, RuleStatus


def proof(id_: str = "daily-fiction", **changes: Any) -> EvidenceReference:
    return EvidenceReference.model_validate(
        dict(
            evidence_id=id_,
            version="1",
            source="Independent fictional daily test",
            locator="urn:daily:" + id_,
            environment=RuleEnvironment.SYNTHETIC,
        )
        | changes
    )


def declaration(id_: str = "day", **changes: Any) -> RuleDefinition:
    return RuleDefinition.model_validate(
        dict(
            rule_id=id_,
            version="1",
            scope=RuleScope.DAY,
            severity=RuleSeverity.ABSOLUTE,
            domain=RuleDomain.CULINARY,
            attribute="synthetic_day_complete",
            operator=PredicateOperator.EQ,
            value=True,
            required_facts=("synthetic_day_complete",),
            applicability_reference=RuleReference(rule_id="synthetic-context-enabled", version="1"),
            evidence=(proof(),),
            rationale="Fictional daily requirement",
            lifecycle=RuleLifecycle.ACTIVE,
            approval_status=ApprovalStatus.APPROVED,
            approved_by="fictional-reviewer",
            approval_reference=proof("approval"),
            environment=RuleEnvironment.SYNTHETIC,
        )
        | changes
    )


def packet(
    rules: tuple[RuleDefinition, ...] | None = None,
) -> tuple[KnowledgeBaseSnapshot, CandidateRecipeFacts, RuleContext]:
    if rules is None:
        rules = (declaration(),)
    node = FoodEntity(
        entity_id="daily-recipe-node",
        version="1",
        kind=FoodEntityKind.RECIPE_REFERENCE,
        canonical_name="Same fictional label",
        catalogue_reference="daily-recipe",
        evidence=(proof(),),
    )
    role = FoodEntity(
        entity_id="daily-role",
        version="1",
        kind=FoodEntityKind.CULINARY_ROLE_REFERENCE,
        canonical_name="Same fictional label",
        catalogue_reference="role",
        evidence=(proof(),),
    )
    graph = FoodGraphSnapshot(
        graph_id="daily-graph",
        version="1",
        catalogue_version="daily-catalogue",
        environment=RuleEnvironment.SYNTHETIC,
        entities=(node, role),
        relations=(),
        evidence=(proof(),),
    )
    entries = tuple(
        CheckCatalogueEntry(
            entry_id=f"cell-{workflow.value}-{scope.value}",
            version="1",
            kb_id="daily-kb",
            kb_version="1",
            check_catalogue_version="daily-checks",
            workflow=workflow,
            scope=scope,
            rule_references=tuple(
                RuleReference(rule_id=r.rule_id, version=r.version)
                for r in rules
                if r.scope is scope
                and r.lifecycle is RuleLifecycle.ACTIVE
                and r.severity is RuleSeverity.ABSOLUTE
            ),
            evidence=(proof(),),
        )
        for workflow in KnowledgeWorkflow
        for scope in RuleScope
        if workflow is not KnowledgeWorkflow.CRAVING_DISCOVERY
        or scope in (RuleScope.PROFILE, RuleScope.RECIPE)
    )
    kb = build_knowledge_snapshot(
        dict(
            kb_id="daily-kb",
            version="1",
            environment=RuleEnvironment.SYNTHETIC,
            graph_id=graph.graph_id,
            graph_version=graph.version,
            catalogue_version=graph.catalogue_version,
            taxonomy_version=None,
            check_catalogue_version="daily-checks",
            graph=graph,
            rules=rules,
            active_rules=tuple(
                RuleReference(rule_id=r.rule_id, version=r.version)
                for r in rules
                if r.lifecycle is RuleLifecycle.ACTIVE
            ),
            applicability_descriptors=(
                ApplicabilityDescriptor(
                    reference=RuleReference(rule_id="synthetic-context-enabled", version="1"),
                    rule_references=tuple(
                        RuleReference(rule_id=r.rule_id, version=r.version) for r in rules
                    ),
                    required_context_facts=("synthetic_context_enabled",),
                    evidence=(proof(),),
                ),
            )
            if rules
            else (),
            check_catalogue=entries,
            rule_catalogue_coverage=tuple(
                RuleCatalogueCoverage(
                    coverage_id="coverage-" + e.entry_id,
                    version="1",
                    kb_id="daily-kb",
                    kb_version="1",
                    check_catalogue_version="daily-checks",
                    workflow=e.workflow,
                    scope=e.scope,
                    complete=True,
                    reason="Fictional exhaustive inventory",
                    evidence=(proof(),),
                )
                for e in entries
            ),
            evidence=(proof(),),
        )
    )
    candidate = CandidateRecipeFacts.build(
        dict(
            recipe_id="daily-recipe",
            recipe_version="1",
            catalogue_version=graph.catalogue_version,
            graph_id=graph.graph_id,
            graph_version=graph.version,
            graph_recipe_entity_id=node.entity_id,
            graph_recipe_reference=node,
            snapshot_id="daily-recipe-snapshot",
            snapshot_version="1",
            ingredient_coverage=IngredientCoverage(
                coverage_id="daily-inventory",
                version="1",
                recipe_id="daily-recipe",
                recipe_version="1",
                catalogue_version=graph.catalogue_version,
                lines=(),
                inventory_complete=True,
                mapping_complete=True,
                subingredients_complete=True,
                gap_reasons=(),
                evidence=(proof(),),
            ),
            facts=(),
            evidence=(proof(),),
        )
    )
    context = RuleContext.build(
        dict(
            context_id="daily-context",
            version="1",
            profile_id="daily-profile",
            profile_version="1",
            workflow=KnowledgeWorkflow.WEEKLY_PLAN,
            expected_kb_id=kb.kb_id,
            expected_kb_version=kb.version,
            expected_kb_digest=kb.content_digest,
            expected_graph_id=kb.graph_id,
            expected_graph_version=kb.graph_version,
            expected_taxonomy_version=kb.taxonomy_version,
            expected_catalogue_version=kb.catalogue_version,
            expected_check_catalogue_version=kb.check_catalogue_version,
            facts=(),
            evidence=(proof(),),
        )
    )
    return kb, candidate, context


def test_day_owned_rule_admitted_and_deferred() -> None:
    kb, candidate, context = packet()
    assert kb.rules[0].scope is RuleScope.DAY  # KB construction already accepts this declaration.
    manifest = build_expected_check_manifest(kb, candidate, context)
    assert manifest.attribute_policy_version == "synthetic-attributes.v4-day"
    assert manifest.required_checks == ()
    assert manifest.deferred_checks == kb.rules


def independent_digest(model: Any) -> str:
    """Independent documented unordered-declaration encoder; no production hash helpers."""

    def encode(value: Any) -> str:
        if isinstance(value, dict):
            return (
                "{"
                + ",".join(json.dumps(key) + ":" + encode(value[key]) for key in sorted(value))
                + "}"
            )
        if isinstance(value, list):
            return "[" + ",".join(sorted(encode(item) for item in value)) + "]"
        return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))

    body = model.model_dump(mode="json", by_alias=True, exclude={"content_digest"})
    return hashlib.sha256(encode(body).encode("utf-8")).hexdigest()


def option_reference(combo: CombinationFacts, id_: str) -> MealOptionReference:
    return MealOptionReference(
        option_id=id_,
        combination_id=combo.combination_id,
        combination_version=combo.version,
        snapshot_id=combo.snapshot_id,
        snapshot_version=combo.snapshot_version,
        combination_digest=combo.content_digest,
        portion_state=combo.portion_state,
        portion_configuration_id=combo.portion_configuration_id,
        portion_configuration_version=combo.portion_configuration_version,
    )


def combination(
    kb: KnowledgeBaseSnapshot,
    candidate: CandidateRecipeFacts,
    context: RuleContext,
    *,
    fixed: bool = True,
    id_: str = "meal",
    amount: int = 10,
) -> CombinationFacts:
    ref = RecipeSnapshotReference(
        recipe_id=candidate.recipe_id,
        recipe_version=candidate.recipe_version,
        snapshot_id=candidate.snapshot_id,
        snapshot_version=candidate.snapshot_version,
        content_digest=candidate.content_digest,
        catalogue_version=candidate.catalogue_version,
    )
    prep = PreparationBinding(
        preparation_id="cooked",
        version="1",
        recipe_snapshot=ref,
        basis_reference=proof("cooked-basis"),
        evidence=(proof("preparation"),),
    )
    part = CombinationComponent(
        component_id="occurrence-1",
        recipe_snapshot=ref,
        preparation=prep,
        quantity=ComponentQuantity(
            amount=amount,
            unit=QuantityUnit.G,
            preparation_id="cooked",
            preparation_version="1",
            basis_reference=prep.basis_reference,
            portion_reference=proof("portion-definition"),
            evidence=(proof("quantity"),),
        )
        if fixed
        else None,
        role_references=(kb.graph.entities[1],),
        evidence=(proof("component"),),
    )
    return CombinationFacts.build(
        dict(
            combination_id=id_,
            version="1",
            snapshot_id="snapshot-" + id_,
            snapshot_version="1",
            components=(part,),
            composition_complete=True,
            composition_gap_reasons=(),
            portion_state=PortionState.FIXED if fixed else PortionState.UNASSIGNED,
            portion_configuration_id="config-" + id_ if fixed else None,
            portion_configuration_version="1" if fixed else None,
            observations=(
                CombinationObservation(
                    fact_id="synthetic_combination_roles_compatible",
                    version="1",
                    combination_id=id_,
                    combination_version="1",
                    observation=FactObservation(
                        fact_id="synthetic_combination_roles_compatible",
                        value=True,
                        complete=True,
                        evidence=(proof("compatibility"),),
                    ),
                ),
            ),
            context_id=context.context_id,
            context_version=context.version,
            context_digest=context.content_digest,
            kb_id=kb.kb_id,
            kb_version=kb.version,
            kb_digest=kb.content_digest,
            graph_id=kb.graph_id,
            graph_version=kb.graph_version,
            catalogue_version=kb.catalogue_version,
            taxonomy_version=kb.taxonomy_version,
            check_catalogue_version=kb.check_catalogue_version,
            evidence=(proof("composition"),),
        )
    )


def source_reference(source: DailySourceSnapshot) -> DailySourceReference:
    return DailySourceReference(
        source_id=source.source_id, version=source.version, content_digest=source.content_digest
    )


@pytest.fixture(scope="module")
def frame() -> dict[str, Any]:
    rules = (
        declaration(
            "recipe",
            scope=RuleScope.RECIPE,
            attribute="synthetic_flag",
            required_facts=("synthetic_flag",),
        ),
        declaration(
            "combination",
            scope=RuleScope.COMBINATION,
            attribute="synthetic_combination_roles_compatible",
            required_facts=("synthetic_combination_roles_compatible",),
        ),
        declaration(),
        declaration(
            "week",
            scope=RuleScope.WEEK,
            attribute="synthetic_flag",
            required_facts=("synthetic_flag",),
        ),
    )
    kb, candidate, context = packet(rules)
    candidate_body: dict[str, object] = candidate.model_dump(exclude={"content_digest"})
    candidate_body.update(
        {
            "facts": (
                VersionedFact(
                    fact_id="synthetic_flag",
                    version="1",
                    subject_kind=FactSubjectKind.RECIPE,
                    subject_id=candidate.recipe_id,
                    subject_version=candidate.recipe_version,
                    catalogue_version=candidate.catalogue_version,
                    observation=FactObservation(
                        fact_id="synthetic_flag", value=True, complete=True, evidence=(proof(),)
                    ),
                ),
            ),
        }
    )
    candidate = CandidateRecipeFacts.build(candidate_body)
    context_body: dict[str, object] = context.model_dump(exclude={"content_digest"})
    context_body.update(
        {
            "facts": (
                VersionedFact(
                    fact_id="synthetic_context_enabled",
                    version="1",
                    subject_kind=FactSubjectKind.CONTEXT,
                    subject_id=context.context_id,
                    subject_version=context.version,
                    context_id=context.context_id,
                    context_version=context.version,
                    observation=FactObservation(
                        fact_id="synthetic_context_enabled",
                        value=True,
                        complete=True,
                        evidence=(proof(),),
                    ),
                ),
            ),
        }
    )
    context = RuleContext.build(context_body)
    combo = combination(kb, candidate, context)
    ref = option_reference(combo, "fixed-option")
    external = DailySourceReference(source_id="upstream", version="1", content_digest="a" * 64)
    suitability = MealSlotSuitability(
        option=ref, source=external, slots=tuple(MealSlot), complete=True, evidence=(proof(),)
    )
    measurement = FixedMealMeasurement(
        option=ref,
        source=external,
        value=0,
        complete=True,
        unit=MeasurementUnit.MG,
        measurement_basis=CombinationMeasurementBasis.FIXED_PORTION_TOTAL,
        components=combo.components,
        basis_reference=proof("meal-total-basis"),
        evidence=(proof(),),
    )
    unassigned = combination(kb, candidate, context, fixed=False, id_="unassigned")
    source = DailySourceSnapshot.build(
        dict(
            source_id="daily-source",
            version="1",
            context=context,
            evidence=(proof(),),
            options=(
                DailyMealOption(
                    reference=ref,
                    combination=combo,
                    suitability=suitability,
                    measurements=(measurement,),
                ),
                DailyMealOption(
                    reference=option_reference(unassigned, "unassigned-option"),
                    combination=unassigned,
                ),
            ),
        )
    )
    request = DailyPlanningRequest.build(
        dict(
            request_id="request",
            version="1",
            day_id="day-1",
            context_id=context.context_id,
            context_version=context.version,
            context_digest=context.content_digest,
            expected_source=source_reference(source),
            source=source,
            domains=tuple(DailySlotDomain(slot=slot, options=(ref,)) for slot in MealSlot),
        )
    )
    assignment = DailyAssignment.build(
        dict(
            request_digest=request.content_digest,
            day_id=request.day_id,
            source=source_reference(source),
            context_digest=context.content_digest,
            slots=tuple(AssignedMeal(slot=slot, option=ref) for slot in MealSlot),
        )
    )
    manifest = ExpectedDayCheckManifest.build(
        dict(
            request=request,
            knowledge=kb,
            required_checks=(rules[2],),
            deferred_checks=(rules[3],),
        )
    )
    return dict(
        kb=kb,
        candidate=candidate,
        context=context,
        source=source,
        request=request,
        assignment=assignment,
        manifest=manifest,
        measurement=measurement,
        suitability=suitability,
        reference=ref,
        external=external,
    )


def revise(model: Any, **changes: Any) -> Any:
    body = model.model_dump(exclude={"content_digest"}) | changes
    return type(model).build(body)


def test_valid_three_slots_fixed_assignments_and_no_feasibility_claim(
    frame: dict[str, Any],
) -> None:
    request, assignment = frame["request"], frame["assignment"]
    assert {domain.slot for domain in request.domains} == set(MealSlot)
    assert len(assignment.slots) == 3
    assert (
        len({item.option.option_id for item in assignment.slots}) == 1
    )  # Repetition is permitted.
    result = DailyPlanningResult(manifest=frame["manifest"], assignment=assignment)
    assert result.outcome is None and result.plan_feasibility == "NOT_EVALUATED"
    assert tuple(rule.rule_id for rule in result.manifest.deferred_checks) == ("week",)


@pytest.mark.parametrize("outcome", list(DailyOutcome))
def test_prompt_one_cannot_authorize_any_resolved_outcome(
    frame: dict[str, Any], outcome: DailyOutcome
) -> None:
    with pytest.raises(ValidationError, match="does not establish"):
        DailyPlanningResult(
            manifest=frame["manifest"], assignment=frame["assignment"], outcome=outcome
        )


@pytest.mark.parametrize("kind", ["missing", "duplicate", "extra"])
@pytest.mark.parametrize("target", ["request", "assignment"])
def test_missing_duplicate_extra_slots(frame: dict[str, Any], kind: str, target: str) -> None:
    model = frame[target]
    field = "domains" if target == "request" else "slots"
    records = getattr(model, field)
    broken = (
        records[:-1]
        if kind == "missing"
        else (*records, records[0])
        if kind == "extra"
        else (records[0], records[1], records[0])
    )
    with pytest.raises(ValidationError):
        revise(model, **{field: broken})


def test_empty_domains_and_unassigned_are_representable_but_not_assignable(
    frame: dict[str, Any],
) -> None:
    request, source = frame["request"], frame["source"]
    empty = revise(request, domains=tuple(DailySlotDomain(slot=s, options=()) for s in MealSlot))
    assert all(domain.options == () for domain in empty.domains)
    unassigned = source.options[1].reference
    represented = revise(
        request, domains=tuple(DailySlotDomain(slot=s, options=(unassigned,)) for s in MealSlot)
    )
    assert represented.domains[0].options[0].portion_state is PortionState.UNASSIGNED
    with pytest.raises(ValidationError, match="FIXED"):
        AssignedMeal(slot=MealSlot.BREAKFAST, option=unassigned)
    without_data = source.options[1]
    assert without_data.suitability is None and without_data.measurements == ()


@pytest.mark.parametrize(
    "field",
    [
        "combination_id",
        "combination_version",
        "snapshot_id",
        "snapshot_version",
        "combination_digest",
        "portion_configuration_id",
        "portion_configuration_version",
    ],
)
def test_wrong_option_reference(frame: dict[str, Any], field: str) -> None:
    value = "b" * 64 if field == "combination_digest" else "different"
    reference = frame["reference"].model_copy(update={field: value})
    with pytest.raises(ValidationError, match="exact"):
        DailyMealOption(reference=reference, combination=frame["source"].options[0].combination)
    with pytest.raises(ValidationError):
        revise(
            frame["request"],
            domains=tuple(DailySlotDomain(slot=slot, options=(reference,)) for slot in MealSlot),
        )


@pytest.mark.parametrize("field", ["source_id", "version", "content_digest"])
def test_independent_source_pin_is_exact(frame: dict[str, Any], field: str) -> None:
    pin = source_reference(frame["source"]).model_copy(
        update={field: "b" * 64 if field == "content_digest" else "other"}
    )
    with pytest.raises(ValidationError, match="pin mismatch"):
        revise(frame["request"], expected_source=pin)


@pytest.mark.parametrize("field", ["context_id", "context_version", "context_digest"])
def test_request_context_is_exact(frame: dict[str, Any], field: str) -> None:
    with pytest.raises(ValidationError):
        revise(frame["request"], **{field: "b" * 64 if field.endswith("digest") else "other"})


@pytest.mark.parametrize(
    "field",
    [
        "context_id",
        "context_version",
        "context_digest",
        "kb_id",
        "kb_version",
        "kb_digest",
        "graph_id",
        "graph_version",
        "catalogue_version",
        "taxonomy_version",
        "check_catalogue_version",
    ],
)
def test_source_option_release_mismatch(frame: dict[str, Any], field: str) -> None:
    source = frame["source"]
    with pytest.raises(ValidationError):
        combo = revise(
            source.options[1].combination,
            **{field: "b" * 64 if field.endswith("digest") else "other"},
        )
        replacement = DailyMealOption(
            reference=option_reference(combo, "changed"), combination=combo
        )
        revise(source, options=(replacement,))


@pytest.mark.parametrize("size", [0, 1, 50])
def test_domain_cardinality_valid_at_limits(size: int) -> None:
    refs = tuple(
        MealOptionReference(
            option_id=f"option-{i}",
            combination_id=f"meal-{i}",
            combination_version="1",
            snapshot_id=f"snapshot-{i}",
            snapshot_version="1",
            combination_digest="a" * 64,
            portion_state=PortionState.UNASSIGNED,
        )
        for i in range(size)
    )
    assert len(DailySlotDomain(slot=MealSlot.LUNCH, options=refs).options) == size


def test_duplicate_option_ids_and_domain_overflow(frame: dict[str, Any]) -> None:
    reference = frame["reference"]
    with pytest.raises(ValidationError, match="duplicate"):
        DailySlotDomain(slot=MealSlot.DINNER, options=(reference, reference))
    with pytest.raises(ValidationError):
        DailySlotDomain(slot=MealSlot.DINNER, options=(reference,) * 51)
    with pytest.raises(ValidationError, match="duplicate"):
        revise(frame["source"], options=(frame["source"].options[0],) * 2)
    alias = (
        frame["source"]
        .options[0]
        .model_copy(
            update={
                "reference": reference.model_copy(update={"option_id": "alias"}),
                "suitability": None,
                "measurements": (),
            }
        )
    )
    with pytest.raises(ValidationError, match="aliased"):
        revise(frame["source"], options=(frame["source"].options[0], alias))


@pytest.mark.parametrize("value", [0, 1, (2**63 - 1) // 3])
def test_integer_measurement_zero_and_representation_bound(
    frame: dict[str, Any], value: int
) -> None:
    measurement = FixedMealMeasurement.model_validate(
        frame["measurement"].model_copy(update={"value": value})
    )
    assert measurement.value == value and type(measurement.value) is int


@pytest.mark.parametrize("value", [-1, 2**63, 10**100, True, False, 0.0, 1.5, "0", float("inf")])
def test_invalid_numeric_measurements(frame: dict[str, Any], value: Any) -> None:
    with pytest.raises(ValidationError):
        FixedMealMeasurement.model_validate(
            frame["measurement"].model_copy(update={"value": value})
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"unit": MeasurementUnit.G},
        {"unit": MeasurementUnit.PERCENT},
        {"unit": MeasurementUnit.DIMENSIONLESS},
        {"unit": "mg"},
        {"measurement_basis": CombinationMeasurementBasis.AS_RECORDED},
        {"measurement_basis": "PER_100_G"},
        {"aggregation_level": "INGREDIENT_TOTAL"},
        {"attribute": "gi"},
        {"attribute": "synthetic_ratio"},
        {"basis_reference": None},
        {"evidence": ()},
        {"components": ()},
        {"value": None, "complete": True},
    ],
)
def test_measurement_units_basis_evidence_and_owner_reject(
    frame: dict[str, Any], changes: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        FixedMealMeasurement.model_validate(frame["measurement"].model_copy(update=changes))


def test_missing_null_incomplete_zero_and_empty_suitability_distinct(frame: dict[str, Any]) -> None:
    complete = frame["measurement"]
    missing = FixedMealMeasurement.model_validate(
        complete.model_copy(
            update={
                "value": None,
                "complete": False,
            }
        )
    )
    incomplete = FixedMealMeasurement.model_validate(
        complete.model_copy(update={"complete": False})
    )
    assert missing.value is None and incomplete.value == 0 and complete.complete
    none_suitable = MealSlotSuitability.model_validate(
        frame["suitability"].model_copy(
            update={
                "slots": (),
                "complete": True,
            }
        )
    )
    unknown = MealSlotSuitability.model_validate(
        none_suitable.model_copy(update={"complete": False})
    )
    assert none_suitable.slots == unknown.slots == () and none_suitable != unknown


@pytest.mark.parametrize(
    "kind", ["configuration", "candidate", "preparation", "quantity", "portion"]
)
def test_measurement_transplants_rejected(frame: dict[str, Any], kind: str) -> None:
    original = frame["source"].options[0]
    measurement = frame["measurement"]
    part = measurement.components[0]
    if kind == "configuration":
        measurement = measurement.model_copy(
            update={
                "option": measurement.option.model_copy(
                    update={
                        "portion_configuration_id": "other",
                    }
                )
            }
        )
    else:
        assert part.quantity is not None
        if kind == "candidate":
            ref = part.recipe_snapshot.model_copy(update={"snapshot_version": "other"})
            part = part.model_copy(
                update={
                    "recipe_snapshot": ref,
                    "preparation": part.preparation.model_copy(update={"recipe_snapshot": ref}),
                }
            )
        elif kind == "preparation":
            part = part.model_copy(
                update={
                    "preparation": part.preparation.model_copy(update={"version": "other"}),
                    "quantity": part.quantity.model_copy(update={"preparation_version": "other"}),
                }
            )
        else:
            part = part.model_copy(
                update={
                    "quantity": part.quantity.model_copy(
                        update={"amount": 11}
                        if kind == "quantity"
                        else {"portion_reference": proof("other-portion")}
                    )
                }
            )
        measurement = measurement.model_copy(update={"components": (part,)})
    with pytest.raises(ValidationError):
        DailyMealOption.model_validate(original.model_copy(update={"measurements": (measurement,)}))


def test_no_double_counting_or_unassigned_measurement(frame: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        DailyMealOption.model_validate(
            frame["source"]
            .options[0]
            .model_copy(
                update={
                    "measurements": (frame["measurement"], frame["measurement"]),
                }
            )
        )
    with pytest.raises(ValidationError, match="FIXED"):
        FixedMealMeasurement.model_validate(
            frame["measurement"].model_copy(
                update={
                    "option": frame["source"].options[1].reference,
                }
            )
        )


def test_conflicting_evidence_and_external_source_pins(frame: dict[str, Any]) -> None:
    source = frame["source"]
    option = source.options[0]
    contradictory = proof(source="Contradictory fictional source")
    with pytest.raises(ValidationError, match="conflicting evidence"):
        revise(source, evidence=(contradictory,))
    with pytest.raises(ValidationError, match="duplicate"):
        MealSlotSuitability.model_validate(
            frame["suitability"].model_copy(
                update={
                    "evidence": (proof(), proof()),
                }
            )
        )
    measurement = frame["measurement"].model_copy(
        update={
            "source": frame["external"].model_copy(update={"content_digest": "b" * 64}),
        }
    )
    with pytest.raises(ValidationError, match="external source"):
        revise(source, options=(option.model_copy(update={"measurements": (measurement,)}),))


def test_manifest_exact_checks_week_preserved_and_no_day_checks_no_pass(
    frame: dict[str, Any],
) -> None:
    manifest = frame["manifest"]
    assert tuple(rule.rule_id for rule in manifest.required_checks) == ("day",)
    assert tuple(rule.rule_id for rule in manifest.deferred_checks) == ("week",)
    for changes in (
        {"required_checks": ()},
        {"deferred_checks": ()},
        {"required_checks": (*manifest.required_checks, *manifest.required_checks)},
    ):
        with pytest.raises(ValidationError, match="authoritative"):
            revise(manifest, **changes)
    kb, candidate, context = packet(())
    combo = combination(kb, candidate, context)
    source = DailySourceSnapshot.build(
        dict(
            source_id="empty-policy",
            version="1",
            context=context,
            evidence=(proof(),),
            options=(
                DailyMealOption(reference=option_reference(combo, "option"), combination=combo),
            ),
        )
    )
    request = revise(
        frame["request"],
        source=source,
        expected_source=source_reference(source),
        context_digest=context.content_digest,
        domains=tuple(DailySlotDomain(slot=s, options=()) for s in MealSlot),
    )
    empty = ExpectedDayCheckManifest.build(
        dict(
            request=request,
            knowledge=kb,
            required_checks=(),
            deferred_checks=(),
        )
    )
    assert DailyPlanningResult(manifest=empty).outcome is None


@pytest.mark.parametrize(
    "token", ["unknown", "synthetic-attributes.v1", "synthetic-attributes.v3-combination"]
)
def test_wrong_day_policy_even_when_rehashed(token: str) -> None:
    kb, candidate, context = packet()
    manifest = build_expected_check_manifest(kb, candidate, context)
    wrong = manifest.model_copy(update={"attribute_policy_version": token})
    digest = independent_digest(wrong)
    wrong = wrong.model_copy(
        update={
            "content_digest": digest,
            "manifest_id": "manifest-" + digest,
            "manifest_version": "synthetic-manifest.v1:" + digest,
        }
    )
    with pytest.raises(ValidationError):
        ExpectedCheckManifest.model_validate(wrong)


@pytest.mark.parametrize(
    "scope", [RuleScope.PROFILE, RuleScope.RECIPE, RuleScope.COMBINATION, RuleScope.WEEK]
)
def test_day_attributes_cannot_migrate_to_other_scopes(scope: RuleScope) -> None:
    kb, candidate, context = packet((declaration(scope=scope),))
    with pytest.raises(ValidationError):
        build_expected_check_manifest(kb, candidate, context)


@pytest.mark.parametrize(
    "changes",
    [
        {"attribute": "unregistered_day", "required_facts": ("unregistered_day",)},
        {"operator": PredicateOperator.IN, "value": ("yes",)},
        {"domain": RuleDomain.CLINICAL},
        {
            "attribute": "synthetic_day_quantity_total",
            "required_facts": ("synthetic_day_quantity_total",),
            "value": 1.0,
            "unit": MeasurementUnit.MG,
        },
        {
            "attribute": "synthetic_day_quantity_total",
            "required_facts": ("synthetic_day_quantity_total",),
            "value": 1,
            "unit": MeasurementUnit.G,
        },
        {"required_facts": ("synthetic_day_complete", "synthetic_flag")},
        {"required_facts": ("synthetic_day_complete", "synthetic_combination_roles_compatible")},
        {
            "approval_status": ApprovalStatus.PENDING,
            "approved_by": None,
            "approval_reference": None,
        },
    ],
)
def test_invalid_day_admission(changes: dict[str, Any]) -> None:
    kb, candidate, context = packet((declaration(**changes),))
    with pytest.raises(ValidationError):
        build_expected_check_manifest(kb, candidate, context)


@pytest.mark.parametrize(
    "operator",
    [
        PredicateOperator.LT,
        PredicateOperator.LE,
        PredicateOperator.GT,
        PredicateOperator.GE,
        PredicateOperator.EQ,
        PredicateOperator.NE,
    ],
)
@pytest.mark.parametrize("value", [0, 2**63 - 1])
def test_numeric_day_admission_integer_boundaries(operator: PredicateOperator, value: int) -> None:
    rule = declaration(
        attribute="synthetic_day_quantity_total",
        required_facts=("synthetic_day_quantity_total",),
        value=value,
        unit=MeasurementUnit.MG,
        operator=operator,
    )
    kb, candidate, context = packet((rule,))
    assert build_expected_check_manifest(kb, candidate, context).deferred_checks == (rule,)


def test_old_recipe_combination_versions_and_full_upstream_pipeline(frame: dict[str, Any]) -> None:
    for rules, token in (
        (
            (
                declaration(
                    scope=RuleScope.RECIPE,
                    attribute="synthetic_flag",
                    required_facts=("synthetic_flag",),
                ),
            ),
            "synthetic-attributes.v1",
        ),
        (
            (
                declaration(
                    scope=RuleScope.COMBINATION,
                    attribute="synthetic_combination_roles_compatible",
                    required_facts=("synthetic_combination_roles_compatible",),
                ),
            ),
            "synthetic-attributes.v3-combination",
        ),
    ):
        kb, candidate, context = packet(rules)
        assert (
            build_expected_check_manifest(kb, candidate, context).attribute_policy_version == token
        )
    recipes = filter_candidates(
        (frame["candidate"],), knowledge=frame["kb"], context=frame["context"]
    )
    assert recipes.eligible_ids == ("daily-recipe",)
    combo = frame["source"].options[0].combination
    result = evaluate_combination(
        combo,
        candidates=(frame["candidate"],),
        knowledge=frame["kb"],
        context=frame["context"],
        trusted_combination=combo,
    )
    assert result.status is RuleStatus.PASS and result.plan_feasibility == "NOT_EVALUATED"
    assert tuple(rule.rule_id for rule in result.deferred_checks) == ("day", "week")
    assert tuple(item.rule.rule_id for item in result.trace.evaluations) == ("combination",)


def day_fact(frame: dict[str, Any], *, numeric: bool = False) -> DayFact:
    return DayFact(
        request_digest=frame["request"].content_digest,
        assignment_digest=frame["assignment"].content_digest,
        day_id="day-1",
        source=source_reference(frame["source"]),
        context_digest=frame["context"].content_digest,
        observation=FactObservation(
            fact_id="synthetic_day_quantity_total" if numeric else "synthetic_day_complete",
            value=0 if numeric else False,
            complete=True,
            unit=MeasurementUnit.MG if numeric else None,
            evidence=(proof(),),
        ),
        measurement_basis="DAY_FIXED_TOTAL" if numeric else None,
        basis_reference=proof("day-basis") if numeric else None,
        contributions=tuple(
            DayMeasurementContribution(slot=slot, measurement=frame["measurement"])
            for slot in MealSlot
        )
        if numeric
        else (),
    )


def test_day_fact_declarations_retain_false_zero_and_assignment_pins(frame: dict[str, Any]) -> None:
    facts = (day_fact(frame), day_fact(frame, numeric=True))
    result = DailyPlanningResult(
        manifest=frame["manifest"], assignment=frame["assignment"], facts=facts
    )
    assert result.facts[0].observation.value is False
    assert type(result.facts[1].observation.value) is int
    assert result.facts[1].observation.value == 0 and result.outcome is None
    wrong = facts[1].model_copy(update={"assignment_digest": "b" * 64})
    with pytest.raises(ValidationError, match="exact"):
        DailyPlanningResult(
            manifest=frame["manifest"], assignment=frame["assignment"], facts=(wrong,)
        )


@pytest.mark.parametrize("target", ["source", "request", "assignment", "manifest"])
def test_independent_digests_roundtrip_pins_and_unordered_declarations(
    frame: dict[str, Any], target: str
) -> None:
    model = frame[target]
    assert model.content_digest == independent_digest(model)
    assert validate_contract_json(type(model), model.model_dump_json(by_alias=True)) == model
    assert type(model).build(model, expected_digest=model.content_digest) == model
    with pytest.raises(ValidationError):
        type(model).build(model, expected_digest="b" * 64)
    field = {
        "source": "options",
        "request": "domains",
        "assignment": "slots",
        "manifest": "required_checks",
    }[target]
    reordered = revise(model, **{field: tuple(reversed(getattr(model, field)))})
    assert reordered.content_digest == model.content_digest
    with pytest.raises(ValidationError):
        type(model).model_validate(model.model_copy(update={"content_digest": "b" * 64}))


def all_records(frame: dict[str, Any]) -> tuple[Any, ...]:
    return (
        frame["reference"],
        frame["external"],
        frame["suitability"],
        frame["measurement"],
        frame["source"].options[0],
        frame["source"],
        frame["request"].domains[0],
        frame["request"],
        frame["assignment"].slots[0],
        frame["assignment"],
        frame["manifest"],
        day_fact(frame),
        DayMeasurementContribution(slot=MealSlot.LUNCH, measurement=frame["measurement"]),
        ConstraintDiagnostic(
            request_digest=frame["request"].content_digest,
            stage="CONTRACT",
            code="MISSING",
            message="Fictional gap",
            status=RuleStatus.UNKNOWN,
            evidence=(proof(),),
        ),
        DailyPlanningResult(manifest=frame["manifest"]),
    )


def test_every_dto_recursive_unchecked_hostile_extra_alias_and_wire(frame: dict[str, Any]) -> None:
    class HostileDict(dict):
        def items(self) -> Any:
            raise AssertionError("hostile items must not execute")

    for record in all_records(frame):
        target = type(record)
        assert validate_contract_json(target, record.model_dump_json(by_alias=True)) == record
        with pytest.raises(ValidationError):
            target.model_validate(record.model_copy(update={"unexpected": True}))
        with pytest.raises(ValidationError):
            target.model_validate(HostileDict(record.model_dump()))
        field = next((name for name in target.model_fields if "_" in name), None)
        if field is None:
            field = next(iter(target.model_fields))
        alias = target.model_fields[field].alias
        if alias and alias != field:
            with pytest.raises(ValidationError):
                target.model_validate(record.model_copy(update={alias: getattr(record, field)}))
        with pytest.raises(ValidationError):
            setattr(record, field, getattr(record, field))


@pytest.mark.parametrize(
    "target",
    [
        MealSlot,
        PortionState,
        MeasurementUnit,
        CombinationMeasurementBasis,
        KnowledgeWorkflow,
        RuleStatus,
        DailyOutcome,
    ],
)
def test_counterfeit_enums_rejected(frame: dict[str, Any], target: type[StrEnum]) -> None:
    member = next(iter(target))
    fake = str.__new__(target, member.value)
    fake._name_ = member.name
    fake._value_ = member.value
    if target is MealSlot:
        record = frame["request"].domains[0].model_copy(update={"slot": fake})
    elif target is PortionState:
        record = frame["reference"].model_copy(update={"portion_state": fake})
    elif target is MeasurementUnit:
        record = frame["measurement"].model_copy(update={"unit": fake})
    elif target is CombinationMeasurementBasis:
        record = frame["measurement"].model_copy(update={"measurement_basis": fake})
    elif target is KnowledgeWorkflow:
        record = frame["source"].model_copy(
            update={"context": frame["context"].model_copy(update={"workflow": fake})}
        )
    elif target is DailyOutcome:
        record = DailyPlanningResult(manifest=frame["manifest"]).model_copy(
            update={"outcome": fake}
        )
    else:
        record = all_records(frame)[-2].model_copy(update={"status": fake})
    with pytest.raises(ValidationError):
        type(record).model_validate(record)


def test_original_json_duplicate_nested_alias_nonfinite_and_numeric_overflow(
    frame: dict[str, Any],
) -> None:
    raw = frame["request"].model_dump_json(by_alias=True)
    for token, replacement in (
        ('"optionId":"fixed-option"', '"optionId":"fixed-option","optionId":"other"'),
        ('"contextId":"daily-context"', '"contextId":"daily-context","context_id":"other"'),
        ('"value":0', '"value":1e9999'),
        ('"value":0', '"value":9223372036854775808'),
    ):
        changed = raw.replace(token, replacement, 1)
        assert changed != raw
        with pytest.raises(ValidationError):
            validate_contract_json(DailyPlanningRequest, changed)
    adapter = TypeAdapter(tuple[DailyPlanningRequest, ...])
    assert validate_contract_json(adapter, "[" + raw + "]") == (frame["request"],)


@pytest.mark.parametrize("token", ["unknown", "synthetic-day-policy.v2", None, False])
def test_daily_manifest_unknown_policy_versions(frame: dict[str, Any], token: Any) -> None:
    with pytest.raises(ValidationError):
        revise(frame["manifest"], day_policy_version=token)


@pytest.mark.parametrize("lifecycle", [RuleLifecycle.DRAFT, RuleLifecycle.RETIRED])
def test_nonactive_day_rule_cannot_enter_mandatory_manifest(
    frame: dict[str, Any], lifecycle: RuleLifecycle
) -> None:
    changed = declaration(lifecycle=lifecycle)
    with pytest.raises(ValidationError):
        revise(frame["manifest"], required_checks=(changed,))
    kb, candidate, context = packet((changed,))
    assert build_expected_check_manifest(kb, candidate, context).deferred_checks == ()


@pytest.mark.parametrize(
    "changes",
    [
        {
            "value": 2**63,
            "attribute": "synthetic_day_quantity_total",
            "required_facts": ("synthetic_day_quantity_total",),
            "unit": MeasurementUnit.MG,
        },
        {
            "value": False,
            "attribute": "synthetic_day_quantity_total",
            "required_facts": ("synthetic_day_quantity_total",),
        },
        {"applicability_reference": RuleReference(rule_id="synthetic-context-guard", version="1")},
    ],
)
def test_day_rule_bound_and_applicability_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        kb, candidate, context = packet((declaration(**changes),))
        build_expected_check_manifest(kb, candidate, context)


def test_applicability_descriptor_mismatch_cannot_hide_in_day_manifest(
    frame: dict[str, Any],
) -> None:
    kb = frame["kb"]
    descriptors = tuple(
        item.model_copy(update={"required_context_facts": ("unknown_fact",)})
        for item in kb.applicability_descriptors
    )
    changed = build_knowledge_snapshot(
        kb.model_dump(exclude={"content_digest"})
        | {
            "applicability_descriptors": descriptors,
        }
    )
    context = RuleContext.build(
        frame["context"].model_dump(exclude={"content_digest"})
        | {
            "expected_kb_digest": changed.content_digest,
        }
    )
    combo = combination(changed, frame["candidate"], context)
    source = revise(
        frame["source"],
        context=context,
        options=(
            DailyMealOption(
                reference=option_reference(combo, "changed"),
                combination=combo,
            ),
        ),
    )
    request = revise(
        frame["request"],
        source=source,
        expected_source=source_reference(source),
        context_digest=context.content_digest,
        domains=tuple(DailySlotDomain(slot=slot, options=()) for slot in MealSlot),
    )
    with pytest.raises(ValidationError, match="applicability descriptor"):
        revise(frame["manifest"], request=request, knowledge=changed)


@pytest.mark.parametrize(
    "workflow", [KnowledgeWorkflow.CRAVING_DISCOVERY, KnowledgeWorkflow.PLANNED_SWAP]
)
def test_no_craving_or_swap_daily_contract(
    frame: dict[str, Any], workflow: KnowledgeWorkflow
) -> None:
    context = RuleContext.build(
        frame["context"].model_dump(exclude={"content_digest"})
        | {
            "workflow": workflow,
        }
    )
    with pytest.raises(ValidationError, match="WEEKLY_PLAN"):
        revise(frame["source"], context=context, options=())


def test_bounded_source_and_configuration_cardinality(frame: dict[str, Any]) -> None:
    options = []
    original = frame["source"].options[0].combination
    for i in range(51):
        combo = revise(original, snapshot_id=f"variant-{i}", portion_configuration_id=f"config-{i}")
        options.append(
            DailyMealOption(reference=option_reference(combo, f"option-{i}"), combination=combo)
        )
    allowed = revise(frame["source"], options=tuple(options[:50]))
    assert len(allowed.options) == 50
    with pytest.raises(ValidationError, match="cardinality"):
        revise(frame["source"], options=tuple(options))
    with pytest.raises(ValidationError):
        revise(frame["source"], options=(frame["source"].options[0],) * 151)


def test_source_identity_conflicts_and_preparation_revisions(frame: dict[str, Any]) -> None:
    original = frame["source"].options[0].combination
    # Individually valid alternative snapshot, but the same snapshot ID/version cannot name both.
    combo = revise(original, portion_configuration_id="other-configuration")
    option = DailyMealOption(reference=option_reference(combo, "other"), combination=combo)
    with pytest.raises(ValidationError, match="snapshot identity"):
        revise(frame["source"], options=(frame["source"].options[0], option))
    # Reusing a fixed configuration identity with different contents is also contradictory.
    combo = revise(original, snapshot_id="other-snapshot")
    option = DailyMealOption(reference=option_reference(combo, "other"), combination=combo)
    with pytest.raises(ValidationError, match="configuration identity"):
        revise(frame["source"], options=(frame["source"].options[0], option))
    part = original.components[0]
    assert part.quantity is not None
    new_basis = proof("other-cooked-basis")
    part = part.model_copy(
        update={
            "preparation": part.preparation.model_copy(update={"basis_reference": new_basis}),
            "quantity": part.quantity.model_copy(update={"basis_reference": new_basis}),
        }
    )
    combo = revise(
        original,
        snapshot_id="other-snapshot",
        portion_configuration_id="other-config",
        components=(part,),
    )
    option = DailyMealOption(reference=option_reference(combo, "other"), combination=combo)
    with pytest.raises(ValidationError, match="preparation identity"):
        revise(frame["source"], options=(frame["source"].options[0], option))


def test_declarations_cannot_self_reference_daily_snapshot(frame: dict[str, Any]) -> None:
    suitability = frame["suitability"].model_copy(
        update={
            "source": source_reference(frame["source"]),
        }
    )
    option = frame["source"].options[0].model_copy(update={"suitability": suitability})
    with pytest.raises(ValidationError, match="self-reference"):
        revise(frame["source"], options=(option,))


def test_nested_hostile_tuples_unchecked_constructs_and_python_collection_strictness(
    frame: dict[str, Any],
) -> None:
    class HostileTuple(tuple):
        def __iter__(self) -> Any:
            raise AssertionError("hostile iterator must not execute")

    request = frame["request"]
    for malformed in (
        request.model_copy(update={"domains": HostileTuple(request.domains)}),
        request.model_copy(update={"domains": list(request.domains)}),
        request.model_copy(
            update={
                "source": frame["source"].model_copy(
                    update={
                        "options": HostileTuple(frame["source"].options),
                    }
                )
            }
        ),
        DailyPlanningRequest.model_construct(**(request.model_dump() | {"domains": None})),
    ):
        with pytest.raises(ValidationError):
            DailyPlanningRequest.model_validate(malformed)
    for digest in (None, False, "", "b" * 64):
        with pytest.raises(ValidationError):
            DailyPlanningRequest.build(request.model_copy(update={"content_digest": digest}))


@pytest.mark.parametrize(
    "changes",
    [
        {"slots": (MealSlot.LUNCH, MealSlot.LUNCH)},
        {"evidence": ()},
        {"slots": ("BREAKFAST",)},
        {"complete": 1},
    ],
)
def test_suitability_declaration_restrictions(
    frame: dict[str, Any], changes: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        MealSlotSuitability.model_validate(frame["suitability"].model_copy(update=changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"measurement_basis": None},
        {"basis_reference": None},
        {"contributions": ()},
        {
            "observation": FactObservation(
                fact_id="synthetic_day_quantity_total",
                value=1.0,
                unit=MeasurementUnit.MG,
                complete=True,
                evidence=(proof(),),
            )
        },
        {
            "observation": FactObservation(
                fact_id="synthetic_day_quantity_total",
                value=True,
                complete=True,
                evidence=(proof(),),
            )
        },
        {
            "observation": FactObservation(
                fact_id="synthetic_day_quantity_total",
                value=2**63,
                unit=MeasurementUnit.MG,
                complete=True,
                evidence=(proof(),),
            )
        },
    ],
)
def test_day_numeric_fact_structure_without_evaluating_predicates(
    frame: dict[str, Any], changes: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        DayFact.model_validate(day_fact(frame, numeric=True).model_copy(update=changes))


def test_day_gaps_preserved_and_result_contributors_cannot_be_rebound(
    frame: dict[str, Any],
) -> None:
    numeric = day_fact(frame, numeric=True)
    missing = DayFact.model_validate(
        numeric.model_copy(
            update={
                "observation": FactObservation(
                    fact_id="synthetic_day_quantity_total",
                    value=None,
                    complete=False,
                    evidence=(proof("missing-total"),),
                ),
                "contributions": (),
            }
        )
    )
    assert missing.observation.value is None and not missing.observation.complete
    partial = frame["measurement"].model_copy(update={"complete": False})
    with pytest.raises(ValidationError, match="complete meal"):
        DayFact.model_validate(
            numeric.model_copy(
                update={
                    "contributions": tuple(
                        DayMeasurementContribution(slot=slot, measurement=partial)
                        for slot in MealSlot
                    )
                }
            )
        )
    swapped = frame["measurement"].model_copy(update={"value": 1})
    changed = numeric.model_copy(
        update={
            "contributions": tuple(
                DayMeasurementContribution(slot=slot, measurement=swapped) for slot in MealSlot
            )
        }
    )
    with pytest.raises(ValidationError, match="selected source measurement"):
        DailyPlanningResult(
            manifest=frame["manifest"], assignment=frame["assignment"], facts=(changed,)
        )


@pytest.mark.parametrize("field", ["request_digest", "day_id", "source", "context_digest"])
def test_result_rejects_rehashed_assignment_rebinding(frame: dict[str, Any], field: str) -> None:
    value = (
        frame["external"]
        if field == "source"
        else "b" * 64
        if field.endswith("digest")
        else "other"
    )
    assignment = revise(frame["assignment"], **{field: value})
    with pytest.raises(ValidationError, match="exact request"):
        DailyPlanningResult(manifest=frame["manifest"], assignment=assignment)


def test_slot_mapping_changes_digest_but_permutations_do_not(frame: dict[str, Any]) -> None:
    combo = revise(
        frame["source"].options[0].combination,
        snapshot_id="second-snapshot",
        portion_configuration_id="second-config",
    )
    second = option_reference(combo, "second")
    source = revise(
        frame["source"],
        options=(*frame["source"].options, DailyMealOption(reference=second, combination=combo)),
    )
    request = revise(
        frame["request"],
        source=source,
        expected_source=source_reference(source),
        domains=tuple(
            DailySlotDomain(slot=slot, options=(frame["reference"], second)) for slot in MealSlot
        ),
    )
    first = revise(
        frame["assignment"],
        request_digest=request.content_digest,
        source=source_reference(source),
        slots=(
            AssignedMeal(slot=MealSlot.BREAKFAST, option=second),
            AssignedMeal(slot=MealSlot.LUNCH, option=frame["reference"]),
            AssignedMeal(slot=MealSlot.DINNER, option=frame["reference"]),
        ),
    )
    moved = revise(
        first,
        slots=(
            AssignedMeal(slot=MealSlot.LUNCH, option=second),
            AssignedMeal(slot=MealSlot.BREAKFAST, option=frame["reference"]),
            AssignedMeal(slot=MealSlot.DINNER, option=frame["reference"]),
        ),
    )
    assert first.content_digest != moved.content_digest
    assert revise(first, slots=tuple(reversed(first.slots))).content_digest == first.content_digest


def test_day_version_requires_day_attributes_and_existing_workflows_remain_scoped(
    frame: dict[str, Any],
) -> None:
    kb, candidate, context = packet(())
    original = build_expected_check_manifest(kb, candidate, context)
    with pytest.raises(ValidationError, match="requires DAY-owned"):
        ExpectedCheckManifest.model_validate(
            original.model_copy(
                update={
                    "attribute_policy_version": "synthetic-attributes.v4-day",
                }
            )
        )
    for workflow, expected_scopes, token in (
        (
            KnowledgeWorkflow.PLANNED_SWAP,
            {RuleScope.COMBINATION, RuleScope.DAY, RuleScope.WEEK},
            "synthetic-attributes.v4-day",
        ),
        (KnowledgeWorkflow.CRAVING_DISCOVERY, set(), "synthetic-attributes.v1"),
    ):
        context = RuleContext.build(
            frame["context"].model_dump(exclude={"content_digest"})
            | {
                "workflow": workflow,
            }
        )
        manifest = build_expected_check_manifest(frame["kb"], frame["candidate"], context)
        assert {rule.scope for rule in manifest.deferred_checks} == expected_scopes
        assert manifest.attribute_policy_version == token
