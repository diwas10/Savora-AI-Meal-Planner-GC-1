"""Independent fictional Phase 4 contracts and deferred-admission regressions."""

import hashlib
import json
from enum import StrEnum
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from savora_ai.core.reasoning.filtering import filter_candidates
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.manifest import build_expected_check_manifest
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    FactSubjectKind,
    IngredientCoverage,
    IngredientGapReason,
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
    CompositionGapReason,
    PortionState,
    PreparationBinding,
    QuantityUnit,
    RecipeSnapshotReference,
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


def evidence(id_: str = "fictional-source", **changes: Any) -> EvidenceReference:
    return EvidenceReference.model_validate(
        dict(
            evidence_id=id_,
            version="1",
            source="Fictional contract test; no medical meaning",
            locator="urn:fictional:" + id_,
            environment=RuleEnvironment.SYNTHETIC,
        )
        | changes
    )


def rule(id_: str = "combination-check", **changes: Any) -> RuleDefinition:
    return RuleDefinition.model_validate(
        dict(
            rule_id=id_,
            version="1",
            scope=RuleScope.COMBINATION,
            severity=RuleSeverity.ABSOLUTE,
            domain=RuleDomain.CULINARY,
            attribute="synthetic_combination_roles_compatible",
            operator=PredicateOperator.EQ,
            value=True,
            required_facts=("synthetic_combination_roles_compatible",),
            applicability_reference=RuleReference(rule_id="synthetic-context-enabled", version="1"),
            evidence=(evidence(),),
            rationale="Fictional quantity-independent culinary declaration",
            lifecycle=RuleLifecycle.ACTIVE,
            approval_status=ApprovalStatus.APPROVED,
            approved_by="fictional-reviewer",
            approval_reference=evidence("approval"),
            environment=RuleEnvironment.SYNTHETIC,
        )
        | changes
    )


def packet(
    rules: tuple[RuleDefinition, ...] = (),
) -> tuple[KnowledgeBaseSnapshot, CandidateRecipeFacts, RuleContext]:
    node = FoodEntity(
        entity_id="recipe-node",
        version="1",
        kind=FoodEntityKind.RECIPE_REFERENCE,
        canonical_name="Fictional dish",
        catalogue_reference="recipe",
        evidence=(evidence(),),
    )
    graph = FoodGraphSnapshot(
        graph_id="graph",
        version="1",
        catalogue_version="catalogue-1",
        environment=RuleEnvironment.SYNTHETIC,
        entities=(node,),
        relations=(),
        evidence=(evidence(),),
    )
    entries = tuple(
        CheckCatalogueEntry(
            entry_id=f"cell-{workflow.value}-{scope.value}",
            version="1",
            kb_id="kb",
            kb_version="1",
            check_catalogue_version="checks-1",
            workflow=workflow,
            scope=scope,
            rule_references=tuple(
                RuleReference(rule_id=r.rule_id, version=r.version)
                for r in rules
                if r.scope is scope
                and r.lifecycle is RuleLifecycle.ACTIVE
                and r.severity is RuleSeverity.ABSOLUTE
            ),
            evidence=(evidence(),),
        )
        for workflow in KnowledgeWorkflow
        for scope in RuleScope
        if workflow is not KnowledgeWorkflow.CRAVING_DISCOVERY
        or scope in (RuleScope.PROFILE, RuleScope.RECIPE)
    )
    kb = build_knowledge_snapshot(
        dict(
            kb_id="kb",
            version="1",
            environment=RuleEnvironment.SYNTHETIC,
            graph_id="graph",
            graph_version="1",
            catalogue_version="catalogue-1",
            taxonomy_version=None,
            check_catalogue_version="checks-1",
            graph=graph,
            rules=rules,
            active_rules=tuple(
                RuleReference(rule_id=r.rule_id, version=r.version)
                for r in rules
                if r.lifecycle is RuleLifecycle.ACTIVE
            ),
            applicability_descriptors=(
                ApplicabilityDescriptor(
                    reference=rules[0].applicability_reference,
                    rule_references=tuple(
                        RuleReference(rule_id=r.rule_id, version=r.version) for r in rules
                    ),
                    required_context_facts=(
                        "synthetic_context_guard"
                        if rules[0].applicability_reference.rule_id == "synthetic-context-guard"
                        else "synthetic_context_enabled",
                    ),
                    evidence=(evidence(),),
                ),
            )
            if rules
            else (),
            check_catalogue=entries,
            rule_catalogue_coverage=tuple(
                RuleCatalogueCoverage(
                    coverage_id="coverage-" + e.entry_id,
                    version="1",
                    kb_id="kb",
                    kb_version="1",
                    check_catalogue_version="checks-1",
                    workflow=e.workflow,
                    scope=e.scope,
                    complete=True,
                    reason="Fictional complete inventory",
                    evidence=(evidence(),),
                )
                for e in entries
            ),
            evidence=(evidence(),),
        )
    )
    candidate = CandidateRecipeFacts.build(
        dict(
            recipe_id="recipe",
            recipe_version="1",
            catalogue_version="catalogue-1",
            graph_id="graph",
            graph_version="1",
            graph_recipe_entity_id="recipe-node",
            graph_recipe_reference=node,
            snapshot_id="recipe-snapshot",
            snapshot_version="1",
            ingredient_coverage=IngredientCoverage(
                coverage_id="inventory",
                version="1",
                recipe_id="recipe",
                recipe_version="1",
                catalogue_version="catalogue-1",
                lines=None,
                inventory_complete=False,
                mapping_complete=False,
                subingredients_complete=False,
                gap_reasons=(IngredientGapReason.MISSING_INVENTORY,),
                evidence=(evidence(),),
            ),
            facts=(),
            evidence=(evidence(),),
        )
    )
    context = RuleContext.build(
        dict(
            context_id="context",
            version="1",
            profile_id="profile",
            profile_version="1",
            workflow=KnowledgeWorkflow.WEEKLY_PLAN,
            expected_kb_id=kb.kb_id,
            expected_kb_version=kb.version,
            expected_kb_digest=kb.content_digest,
            expected_graph_id="graph",
            expected_graph_version="1",
            expected_taxonomy_version=None,
            expected_catalogue_version="catalogue-1",
            expected_check_catalogue_version="checks-1",
            facts=(),
            evidence=(evidence(),),
        )
    )
    return kb, candidate, context


def test_new_combination_attribute_admitted_and_deferred() -> None:
    kb, candidate, context = packet((rule(),))
    manifest = build_expected_check_manifest(kb, candidate, context)
    assert manifest.attribute_policy_version == "synthetic-attributes.v3-combination"
    assert manifest.required_checks == ()
    assert manifest.deferred_checks == kb.rules


def test_unknown_combination_attribute_rejected() -> None:
    kb, candidate, context = packet(
        (rule(attribute="unregistered", required_facts=("unregistered",)),)
    )
    with pytest.raises(ValidationError, match="unsupported synthetic required attribute"):
        build_expected_check_manifest(kb, candidate, context)


def reference(candidate: CandidateRecipeFacts | None = None) -> RecipeSnapshotReference:
    if candidate is None:
        _, candidate, _ = packet()
    return RecipeSnapshotReference(
        recipe_id=candidate.recipe_id,
        recipe_version=candidate.recipe_version,
        snapshot_id=candidate.snapshot_id,
        snapshot_version=candidate.snapshot_version,
        content_digest=candidate.content_digest,
        catalogue_version=candidate.catalogue_version,
    )


def preparation(ref: RecipeSnapshotReference | None = None) -> PreparationBinding:
    return PreparationBinding(
        preparation_id="cooked-preparation",
        version="1",
        recipe_snapshot=ref or reference(),
        basis_reference=evidence("cooked-basis"),
        evidence=(evidence("preparation"),),
    )


def quantity(**changes: Any) -> ComponentQuantity:
    return ComponentQuantity.model_validate(
        dict(
            amount=25,
            unit=QuantityUnit.G,
            preparation_id="cooked-preparation",
            preparation_version="1",
            basis_reference=evidence("cooked-basis"),
            portion_reference=evidence("portion-definition"),
            evidence=(evidence("quantity"),),
        )
        | changes
    )


def component(id_: str = "occurrence-a", *, fixed: bool = False) -> CombinationComponent:
    ref = reference()
    return CombinationComponent(
        component_id=id_,
        recipe_snapshot=ref,
        preparation=preparation(ref),
        quantity=quantity() if fixed else None,
        role_references=(
            FoodEntity(
                entity_id="fictional-role",
                version="1",
                kind=FoodEntityKind.CULINARY_ROLE_REFERENCE,
                canonical_name="A display label, never an identity",
                catalogue_reference="role-1",
                evidence=(evidence("role"),),
            ),
        ),
        evidence=(evidence("component"),),
    )


def observation(value: Any = True, **changes: Any) -> CombinationObservation:
    name = changes.pop("fact_id", "synthetic_combination_roles_compatible")
    return CombinationObservation.model_validate(
        dict(
            fact_id=name,
            version="1",
            combination_id="combination",
            combination_version="1",
            observation=FactObservation(
                fact_id=name,
                value=value,
                complete=value is not None,
                unit=MeasurementUnit.MG if type(value) in (int, float) else None,
                evidence=(evidence("observation"),),
            ),
        )
        | changes
    )


def content(*, fixed: bool = False, **changes: Any) -> dict[str, Any]:
    kb, _, context = packet()
    return (
        dict(
            combination_id="combination",
            version="1",
            snapshot_id="combination-snapshot",
            snapshot_version="1",
            components=(component(fixed=fixed),),
            composition_complete=True,
            composition_gap_reasons=(),
            portion_state=PortionState.FIXED if fixed else PortionState.UNASSIGNED,
            portion_configuration_id="configuration" if fixed else None,
            portion_configuration_version="1" if fixed else None,
            observations=(observation(),),
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
            evidence=(evidence("combination"),),
        )
        | changes
    )


def independent_digest(wire: dict[str, Any]) -> str:
    # Encode from the documented format, with no production canonicalization helpers.
    def encode(value: Any) -> str:
        if type(value) is dict:
            return (
                "{" + ",".join(json.dumps(k) + ":" + encode(value[k]) for k in sorted(value)) + "}"
            )
        if type(value) is list:
            return "[" + ",".join(sorted(encode(item) for item in value)) + "]"
        return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))

    return hashlib.sha256(encode(wire).encode("utf-8")).hexdigest()


@pytest.mark.parametrize("fixed", [False, True])
def test_valid_snapshot_independent_digest_roundtrip_and_frozen(fixed: bool) -> None:
    result = CombinationFacts.build(content(fixed=fixed))
    wire = result.model_dump(mode="json", by_alias=True, exclude={"content_digest"})
    assert result.content_digest == independent_digest(wire)
    assert result.composition_complete is True
    assert result.portion_state is (PortionState.FIXED if fixed else PortionState.UNASSIGNED)
    assert CombinationFacts.build(result, expected_digest=result.content_digest) == result
    assert validate_contract_json(CombinationFacts, result.model_dump_json(by_alias=True)) == result
    assert validate_contract_json(
        TypeAdapter(tuple[CombinationFacts, ...]), "[" + result.model_dump_json() + "]"
    ) == (result,)
    with pytest.raises(ValidationError):
        result.composition_complete = False  # type: ignore[misc]
    with pytest.raises(ValidationError):
        result.components[0].component_id = "changed"  # type: ignore[misc]


def test_repeated_recipe_occurrences_preserved_and_order_independent() -> None:
    a, b = component(), component("occurrence-b")
    first = CombinationFacts.build(content(components=(a, b)))
    second = CombinationFacts.build(content(components=(b, a)))
    assert len(first.components) == 2
    assert first.components[0].recipe_snapshot == first.components[1].recipe_snapshot
    assert first.content_digest == second.content_digest
    assert first.content_digest != CombinationFacts.build(content(components=(a,))).content_digest


@pytest.mark.parametrize("parts", [(), (component(), component()), None, False, []])
def test_invalid_component_collections(parts: Any) -> None:
    with pytest.raises(ValidationError):
        CombinationFacts.build(content(components=parts))


@pytest.mark.parametrize(
    "changes",
    [
        {"components": (component(fixed=True),)},
        {"components": (component(), component("b", fixed=True))},
        {"portion_state": PortionState.FIXED},
        {"portion_configuration_id": "configuration"},
        {"portion_configuration_id": "configuration", "portion_configuration_version": "1"},
    ],
)
def test_reject_partial_or_contradictory_portions(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        CombinationFacts.build(content(**changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"components": (component(),)},
        {"components": (component(fixed=True), component("b"))},
        {"portion_configuration_id": None},
        {"portion_configuration_version": None},
        {"portion_state": PortionState.UNASSIGNED},
    ],
)
def test_reject_partial_fixed_configuration(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        CombinationFacts.build(content(fixed=True, **changes))


@pytest.mark.parametrize(
    "amount", [0, -1, False, True, None, "25", float("nan"), float("inf"), -float("inf"), (), {}]
)
def test_malformed_amount(amount: Any) -> None:
    with pytest.raises(ValidationError):
        quantity(amount=amount)


@pytest.mark.parametrize("unit", ["g", "kg", "ml", "mL", "serving", False, 0, None])
def test_python_units_require_exact_enum(unit: Any) -> None:
    with pytest.raises(ValidationError):
        quantity(unit=unit)


@pytest.mark.parametrize("unit", list(QuantityUnit))
@pytest.mark.parametrize("amount", [1, 0.1, 25, 25.5])
def test_positive_amount_explicit_units(unit: QuantityUnit, amount: int | float) -> None:
    result = quantity(unit=unit, amount=amount)
    assert result.unit is unit and result.amount == amount
    assert validate_contract_json(ComponentQuantity, result.model_dump_json()) == result


@pytest.mark.parametrize(
    "target,record,field",
    [
        (PreparationBinding, preparation(), "evidence"),
        (PreparationBinding, preparation(), "basis_reference"),
        (ComponentQuantity, quantity(), "evidence"),
        (ComponentQuantity, quantity(), "basis_reference"),
        (ComponentQuantity, quantity(), "portion_reference"),
        (CombinationComponent, component(), "evidence"),
        (CombinationFacts, CombinationFacts.build(content()), "evidence"),
    ],
)
def test_missing_preparation_or_basis_evidence(target: Any, record: Any, field: str) -> None:
    payload = record.model_dump()
    del payload[field]
    with pytest.raises(ValidationError):
        target.model_validate(payload)
    payload[field] = () if field == "evidence" else None
    with pytest.raises(ValidationError):
        target.model_validate(payload)


@pytest.mark.parametrize(
    "changes",
    [
        {"composition_complete": False},
        {"composition_gap_reasons": (CompositionGapReason.INCOMPLETE_COMPOSITION,)},
        {
            "composition_complete": False,
            "composition_gap_reasons": (CompositionGapReason.INCOMPLETE_COMPOSITION,) * 2,
        },
        {"composition_gap_reasons": ("INCOMPLETE_COMPOSITION",)},
    ],
)
def test_contradictory_composition_completeness(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        CombinationFacts.build(content(**changes))


def test_composition_completeness_does_not_assert_ingredient_completeness() -> None:
    _, candidate, _ = packet()
    assert candidate.ingredient_coverage.lines is None
    result = CombinationFacts.build(content())
    assert result.composition_complete is True
    incomplete = CombinationFacts.build(
        content(
            composition_complete=False,
            composition_gap_reasons=(CompositionGapReason.UNVERIFIED_COMPOSITION,),
        )
    )
    assert incomplete.composition_complete is False


@pytest.mark.parametrize(
    "observations",
    [
        (observation(), observation()),
        (observation(), observation(False)),
        (observation(), observation(version="2")),
        (observation(combination_id="recipe"),),
        (observation(combination_version="stale"),),
        (observation(portion_configuration_id="configuration", portion_configuration_version="1"),),
        (observation(False, fact_id="synthetic_combination_composition_complete"),),
    ],
)
def test_duplicate_conflicting_or_wrong_owner_observations(observations: Any) -> None:
    with pytest.raises(ValidationError):
        CombinationFacts.build(content(observations=observations))


def test_false_null_missing_and_zero_preserve_meaning() -> None:
    assert (
        CombinationFacts.build(content(observations=(observation(False),)))
        .observations[0]
        .observation.value
        is False
    )
    assert (
        CombinationFacts.build(content(observations=(observation(None),)))
        .observations[0]
        .observation.value
        is None
    )
    assert CombinationFacts.build(content(observations=())).observations == ()
    zero = observation(
        0,
        measurement_basis=CombinationMeasurementBasis.AS_RECORDED,
        basis_reference=evidence("recorded-basis"),
    )
    result = CombinationFacts.build(content(observations=(zero,)))
    assert type(result.observations[0].observation.value) is int
    assert result.observations[0].observation.value == 0
    payload = zero.model_dump()
    del payload["observation"]["value"]
    with pytest.raises(ValidationError):
        CombinationObservation.model_validate(payload)


def test_numeric_fixed_observation_requires_exact_configuration() -> None:
    fixed = observation(
        0,
        measurement_basis=CombinationMeasurementBasis.FIXED_PORTION_TOTAL,
        basis_reference=evidence("total-basis"),
        portion_configuration_id="configuration",
        portion_configuration_version="1",
    )
    assert CombinationFacts.build(content(fixed=True, observations=(fixed,)))
    wrong = fixed.model_copy(update={"portion_configuration_version": "2"})
    with pytest.raises(ValidationError, match="configuration mismatch"):
        CombinationFacts.build(content(fixed=True, observations=(wrong,)))
    for updates in (
        {"basis_reference": None},
        {"measurement_basis": None},
        {"portion_configuration_id": None, "portion_configuration_version": None},
    ):
        with pytest.raises(ValidationError):
            CombinationObservation.model_validate(fixed.model_dump() | updates)
    with pytest.raises(ValidationError):
        observation(
            True,
            measurement_basis=CombinationMeasurementBasis.AS_RECORDED,
            basis_reference=evidence(),
        )


def test_preparation_snapshot_basis_and_roles_are_exact() -> None:
    part = component(fixed=True)
    for updates in (
        {"preparation": preparation(reference().model_copy(update={"snapshot_version": "2"}))},
        {"quantity": quantity(preparation_id="raw-preparation")},
        {"quantity": quantity(preparation_version="2")},
        {"quantity": quantity(basis_reference=evidence("raw-basis"))},
        {"role_references": ()},
        {"role_references": part.role_references * 2},
        {"role_references": (packet()[1].graph_recipe_reference,)},
    ):
        with pytest.raises(ValidationError):
            CombinationComponent.model_validate(part.model_dump() | updates)


def test_conflicting_snapshot_preparation_role_and_evidence_declarations() -> None:
    a, b = component(), component("b")
    variants = [
        b.model_copy(
            update={
                "recipe_snapshot": reference().model_copy(update={"content_digest": "a" * 64}),
                "preparation": preparation(
                    reference().model_copy(update={"content_digest": "a" * 64})
                ),
            }
        ),
        b.model_copy(
            update={
                "preparation": preparation().model_copy(
                    update={"basis_reference": evidence("other-basis")}
                )
            }
        ),
        b.model_copy(
            update={"role_references": (b.role_references[0].model_copy(update={"version": "2"}),)}
        ),
        b.model_copy(update={"evidence": (evidence("component", locator="urn:contradiction"),)}),
    ]
    for variant in variants:
        with pytest.raises(ValidationError):
            CombinationFacts.build(content(components=(a, variant)))


@pytest.mark.parametrize(
    "field",
    [
        "combination_id",
        "version",
        "snapshot_id",
        "snapshot_version",
        "context_id",
        "context_version",
        "context_digest",
        "kb_id",
        "kb_version",
        "kb_digest",
        "graph_id",
        "graph_version",
        "catalogue_version",
        "check_catalogue_version",
        "evidence",
    ],
)
@pytest.mark.parametrize("bad", [None, False, 0, ""])
def test_required_bindings_are_strict(field: str, bad: Any) -> None:
    with pytest.raises(ValidationError):
        CombinationFacts.build(content(**{field: bad}))


@pytest.mark.parametrize("field", ["context_digest", "kb_digest", "content_digest"])
def test_malformed_binding_hash(field: str) -> None:
    payload = content()
    payload[field] = "not-a-sha256"
    with pytest.raises(ValidationError):
        CombinationFacts.build(payload)


def test_release_binding_within_snapshot_and_external_membership_boundary() -> None:
    with pytest.raises(ValidationError, match="catalogue"):
        CombinationFacts.build(content(catalogue_version="wrong-release"))
    # Independently trusted KB/context/candidate lookup is intentionally deferred.
    original = CombinationFacts.build(content())
    for field in ("context_id", "context_version", "kb_id", "kb_version", "graph_version"):
        payload = content()
        payload[field] = "different"
        changed = CombinationFacts.build(payload)
        assert changed.content_digest != original.content_digest
        with pytest.raises(ValidationError):
            CombinationFacts.build(payload, expected_digest=original.content_digest)


@pytest.mark.parametrize("field", ["context_digest", "kb_digest"])
def test_alternate_external_digest_invalidates_old_pin(field: str) -> None:
    original = CombinationFacts.build(content())
    payload = content()
    payload[field] = "a" * 64
    with pytest.raises(ValidationError):
        CombinationFacts.build(payload, expected_digest=original.content_digest)


@pytest.mark.parametrize(
    "mutation", ["occurrence", "recipe", "preparation", "quantity", "evidence", "context"]
)
def test_component_content_changes_invalidate_digest(mutation: str) -> None:
    original = CombinationFacts.build(content(fixed=True))
    body = original.model_dump(exclude={"content_digest"})
    part = body["components"][0]
    if mutation == "occurrence":
        part["component_id"] = "other-occurrence"
    elif mutation == "recipe":
        part["recipe_snapshot"]["snapshot_version"] = "2"
        part["preparation"]["recipe_snapshot"]["snapshot_version"] = "2"
    elif mutation == "preparation":
        part["preparation"]["version"] = "2"
        part["quantity"]["preparation_version"] = "2"
    elif mutation == "quantity":
        part["quantity"]["amount"] = 26
    elif mutation == "evidence":
        body["evidence"] = (evidence("revised-proof"),)
    else:
        body["context_version"] = "2"
    changed = CombinationFacts.build(body)
    assert changed.content_digest != original.content_digest
    with pytest.raises(ValidationError):
        body["content_digest"] = original.content_digest
        CombinationFacts.build(body)
    del body["content_digest"]
    with pytest.raises(ValidationError):
        CombinationFacts.build(body, expected_digest=original.content_digest)


@pytest.mark.parametrize("digest", [None, "", "a" * 64, False, 0])
def test_supplied_digest_is_verified_never_replaced(digest: Any) -> None:
    with pytest.raises(ValidationError):
        CombinationFacts.build(content(content_digest=digest))


def records() -> tuple[Any, ...]:
    return (
        reference(),
        preparation(),
        quantity(),
        component(),
        observation(),
        CombinationFacts.build(content()),
    )


@pytest.mark.parametrize("record", records())
def test_every_dto_rejects_unchecked_objects_aliases_extras_and_hostile_containers(
    record: Any,
) -> None:
    target = type(record)
    for forged in (
        record.model_copy(update={"eligibility": True}),
        target.model_construct(),
    ):
        with pytest.raises(ValidationError):
            target.model_validate(forged)
    payload = record.model_dump()
    field = next(name for name, info in target.model_fields.items() if info.alias != name)
    alias = target.model_fields[field].alias
    with pytest.raises(ValidationError):
        target.model_validate(payload | {alias: payload[field]})

    class HostileDict(dict):
        def items(self) -> Any:
            raise AssertionError("custom iteration must never execute")

    with pytest.raises(ValidationError):
        target.model_validate(HostileDict(payload))
    wire = record.model_dump_json(by_alias=True)
    token = json.dumps(alias)
    # Duplicate the exact original member, including identical values.
    duplicate = "{" + token + ":" + json.dumps(json.loads(wire)[alias]) + "," + wire[1:]
    with pytest.raises(ValidationError, match="duplicate JSON"):
        validate_contract_json(target, duplicate)


def test_nested_unchecked_containers_and_counterfeit_enums() -> None:
    class HostileTuple(tuple):
        def __iter__(self) -> Any:
            raise AssertionError("hostile tuple must not execute")

    class FakeState(StrEnum):
        UNASSIGNED = "UNASSIGNED"

    for value in (FakeState.UNASSIGNED, "UNASSIGNED"):
        with pytest.raises(ValidationError):
            CombinationFacts.build(content(portion_state=value))
    forged = str.__new__(PortionState, "UNASSIGNED")
    object.__setattr__(forged, "_name_", "UNASSIGNED")
    object.__setattr__(forged, "_value_", "UNASSIGNED")
    with pytest.raises(ValidationError):
        CombinationFacts.build(content(portion_state=forged))
    for updates in (
        {"components": HostileTuple((component(),))},
        {"components": (component().model_copy(update={"evidence": HostileTuple((evidence(),))}),)},
        {
            "components": (
                component().model_copy(
                    update={"quantity": quantity().model_copy(update={"amount": False})}
                ),
            )
        },
    ):
        payload = content()
        payload.update(updates)
        with pytest.raises(ValidationError):
            CombinationFacts.build(payload)


@pytest.mark.parametrize(
    "scope", [RuleScope.PROFILE, RuleScope.RECIPE, RuleScope.DAY, RuleScope.WEEK]
)
def test_new_attributes_cannot_migrate_to_other_scopes(scope: RuleScope) -> None:
    kb, candidate, context = packet((rule(scope=scope),))
    with pytest.raises(ValidationError, match="combination scope"):
        build_expected_check_manifest(kb, candidate, context)


@pytest.mark.parametrize(
    "changes",
    [
        {"domain": RuleDomain.CLINICAL},
        {"domain": RuleDomain.DIETARY},
        {"value": 1, "unit": MeasurementUnit.DIMENSIONLESS},
        {"required_facts": ("synthetic_combination_roles_compatible", "synthetic_flag")},
        {"required_facts": ("synthetic_combination_roles_compatible", "unregistered")},
        {
            "attribute": "synthetic_flag",
            "required_facts": ("synthetic_flag", "synthetic_combination_roles_compatible"),
        },
        {
            "approval_status": ApprovalStatus.PENDING,
            "approved_by": None,
            "approval_reference": None,
        },
    ],
)
def test_invalid_combination_policy_declarations(changes: dict[str, Any]) -> None:
    kb, candidate, context = packet((rule(**changes),))
    with pytest.raises(ValidationError):
        build_expected_check_manifest(kb, candidate, context)


@pytest.mark.parametrize("operator", [PredicateOperator.EQ, PredicateOperator.NE])
@pytest.mark.parametrize(
    "attribute",
    ["synthetic_combination_roles_compatible", "synthetic_combination_composition_complete"],
)
def test_exact_supported_combination_registry(attribute: str, operator: PredicateOperator) -> None:
    kb, candidate, context = packet(
        (rule(attribute=attribute, required_facts=(attribute,), operator=operator),)
    )
    assert build_expected_check_manifest(kb, candidate, context).deferred_checks == kb.rules


@pytest.mark.parametrize(
    "token", ["synthetic-attributes.v1", "synthetic-attributes.v2", "unknown-policy"]
)
def test_rehashed_policy_downgrade_or_unknown_version_rejected(token: str) -> None:
    manifest = build_expected_check_manifest(*packet((rule(),)))
    wire = manifest.model_dump(
        mode="json", by_alias=True, exclude={"content_digest", "manifest_id", "manifest_version"}
    )
    wire["attributePolicyVersion"] = token
    digest = independent_digest(wire)
    wire.update(
        contentDigest=digest,
        manifestId="manifest-" + digest,
        manifestVersion="synthetic-manifest.v1:" + digest,
    )
    with pytest.raises(ValidationError):
        validate_contract_json(ExpectedCheckManifest, json.dumps(wire))


def test_old_recipe_policy_and_day_week_obligations_unchanged() -> None:
    rules = tuple(
        rule(
            scope.value,
            scope=scope,
            attribute="synthetic_flag",
            required_facts=("synthetic_flag",),
        )
        for scope in (RuleScope.RECIPE, RuleScope.COMBINATION, RuleScope.DAY, RuleScope.WEEK)
    )
    kb, candidate, context = packet(rules)
    old = build_expected_check_manifest(kb, candidate, context)
    assert old.attribute_policy_version == "synthetic-attributes.v1"
    assert tuple(r.scope for r in old.required_checks) == (RuleScope.RECIPE,)
    assert {r.scope for r in old.deferred_checks} == {
        RuleScope.COMBINATION,
        RuleScope.DAY,
        RuleScope.WEEK,
    }
    wire = old.model_dump(
        mode="json", by_alias=True, exclude={"content_digest", "manifest_id", "manifest_version"}
    )
    assert independent_digest(wire) == old.content_digest
    kb, candidate, context = packet((*rules, rule()))
    new = build_expected_check_manifest(kb, candidate, context)
    assert new.attribute_policy_version == "synthetic-attributes.v3-combination"
    assert new.required_checks == old.required_checks
    assert all(r in new.deferred_checks for r in old.deferred_checks)
    result = filter_candidates((candidate,), knowledge=kb, context=context)
    assert result.eligible_ids == ()
    assert result.excluded_ids == ("recipe",)
    assert result.decisions[0].status is RuleStatus.UNKNOWN
    assert result.decisions[0].resolution.manifest == new


def test_zero_recipe_mandatory_checks_never_pass_deferred_checks_never_execute() -> None:
    kb, candidate, context = packet((rule(),))
    result = filter_candidates((candidate,), knowledge=kb, context=context)
    assert result.eligible_ids == ()
    assert result.decisions[0].status is RuleStatus.UNKNOWN
    assert result.decisions[0].trace.evaluations == ()
    assert result.decisions[0].resolution.manifest.deferred_checks == kb.rules


def test_recipe_pass_and_prerequisites_survive_new_deferred_policy() -> None:
    recipe_rule = rule(
        "recipe-check",
        scope=RuleScope.RECIPE,
        attribute="synthetic_flag",
        required_facts=("synthetic_flag",),
    )
    profile_rule = rule(
        "profile-check",
        scope=RuleScope.PROFILE,
        attribute="synthetic_profile_flag",
        required_facts=("synthetic_profile_flag",),
    )
    later = tuple(
        rule(
            scope.value,
            scope=scope,
            attribute="synthetic_flag",
            required_facts=("synthetic_flag",),
        )
        for scope in (RuleScope.DAY, RuleScope.WEEK)
    )
    outcomes = []
    for added in ((), (rule(),)):
        kb, candidate, context = packet((recipe_rule, profile_rule, *later, *added))
        candidate_body: dict[str, Any] = candidate.model_dump(exclude={"content_digest"}) | {
            "facts": (
                VersionedFact(
                    fact_id="synthetic_flag",
                    version="1",
                    subject_kind=FactSubjectKind.RECIPE,
                    subject_id="recipe",
                    subject_version="1",
                    catalogue_version="catalogue-1",
                    observation=FactObservation(
                        fact_id="synthetic_flag",
                        value=True,
                        complete=True,
                        evidence=(evidence("recipe-fact"),),
                    ),
                ),
            ),
        }
        candidate = CandidateRecipeFacts.build(candidate_body)
        context_body: dict[str, Any] = context.model_dump(exclude={"content_digest"}) | {
            "facts": tuple(
                VersionedFact(
                    fact_id=name,
                    version="1",
                    subject_kind=owner,
                    subject_id=id_,
                    subject_version="1",
                    context_id="context",
                    context_version="1",
                    observation=FactObservation(
                        fact_id=name, value=True, complete=True, evidence=(evidence(name),)
                    ),
                )
                for name, owner, id_ in (
                    ("synthetic_profile_flag", FactSubjectKind.PROFILE, "profile"),
                    ("synthetic_context_enabled", FactSubjectKind.CONTEXT, "context"),
                )
            ),
        }
        context = RuleContext.build(context_body)
        result = filter_candidates((candidate,), knowledge=kb, context=context)
        decision = result.decisions[0]
        outcomes.append(decision.status)
        assert result.eligible_ids == ("recipe",)
        assert {e.rule.rule_id for e in decision.trace.evaluations} == {
            "recipe-check",
            "profile-check",
        }
        assert {r.scope for r in decision.resolution.manifest.deferred_checks} == (
            {RuleScope.COMBINATION, RuleScope.DAY, RuleScope.WEEK}
            if added
            else {RuleScope.DAY, RuleScope.WEEK}
        )
    assert outcomes == [RuleStatus.PASS, RuleStatus.PASS]


def test_supported_combination_context_prerequisites_and_exact_applicability() -> None:
    mandatory = rule(
        required_facts=(
            "synthetic_combination_roles_compatible",
            "synthetic_context_enabled",
            "synthetic_profile_flag",
        )
    )
    kb, candidate, context = packet((mandatory,))
    assert build_expected_check_manifest(kb, candidate, context).deferred_checks == (mandatory,)
    wrong = rule(
        applicability_reference=RuleReference(rule_id="synthetic-context-guard", version="1")
    )
    kb, candidate, context = packet((wrong,))
    with pytest.raises(ValidationError, match="applicability"):
        build_expected_check_manifest(kb, candidate, context)


@pytest.mark.parametrize("corruption", ["stale", "inactive", "soft", "missing"])
def test_authoritative_catalogue_cannot_drop_or_relabel_new_check(corruption: str) -> None:
    kb, candidate, context = packet((rule(),))
    body = kb.model_dump(exclude={"content_digest"})
    if corruption == "stale":
        body["check_catalogue"][2]["rule_references"] = (
            RuleReference(rule_id="combination-check", version="stale"),
        )
    elif corruption == "inactive":
        body["rules"][0]["lifecycle"] = RuleLifecycle.RETIRED
    elif corruption == "soft":
        body["rules"][0]["severity"] = RuleSeverity.SOFT
    else:
        for cell in body["check_catalogue"]:
            if cell["scope"] is RuleScope.COMBINATION:
                cell["rule_references"] = ()
    with pytest.raises(ValidationError):
        bad = build_knowledge_snapshot(body)
        build_expected_check_manifest(bad, candidate, context)


def test_new_policy_does_not_relabel_empty_or_old_only_manifests() -> None:
    manifest = build_expected_check_manifest(*packet())
    body = manifest.model_dump(exclude={"content_digest", "manifest_id", "manifest_version"})
    body["attribute_policy_version"] = "synthetic-attributes.v3-combination"
    # Version consistency is checked before digest identity, including empty check sets.
    with pytest.raises(ValidationError, match="scope-aware policy"):
        ExpectedCheckManifest.model_validate(
            body
            | {
                "manifest_id": manifest.manifest_id,
                "manifest_version": manifest.manifest_version,
                "content_digest": manifest.content_digest,
            }
        )


@pytest.mark.parametrize("field", ["unit", "measurement_basis", "composition_gap_reasons"])
def test_each_new_enum_rejects_counterfeit_members(field: str) -> None:
    enum_type, token = {
        "unit": (QuantityUnit, "g"),
        "measurement_basis": (CombinationMeasurementBasis, "AS_RECORDED"),
        "composition_gap_reasons": (CompositionGapReason, "INCOMPLETE_COMPOSITION"),
    }[field]
    forged = str.__new__(enum_type, token)
    object.__setattr__(forged, "_name_", next(m.name for m in enum_type if m.value == token))
    object.__setattr__(forged, "_value_", token)
    with pytest.raises(ValidationError):
        if field == "unit":
            quantity(unit=forged)
        elif field == "measurement_basis":
            observation(0, measurement_basis=forged, basis_reference=evidence())
        else:
            CombinationFacts.build(
                content(composition_complete=False, composition_gap_reasons=(forged,))
            )


@pytest.mark.parametrize("location", ["recipe", "preparation", "observation", "quantity"])
def test_nested_original_json_duplicate_keys_and_alias_collisions(location: str) -> None:
    result = CombinationFacts.build(content(fixed=True))
    wire = result.model_dump_json(by_alias=True)
    token = {
        "recipe": '"recipeId":"recipe"',
        "preparation": '"preparationId":"cooked-preparation"',
        "observation": '"complete":true',
        "quantity": '"amount":25',
    }[location]
    assert token in wire
    with pytest.raises(ValidationError, match="duplicate JSON"):
        validate_contract_json(CombinationFacts, wire.replace(token, token + "," + token, 1))
    payload = result.model_dump()
    payload["components"][0]["recipe_snapshot"]["recipeId"] = "recipe"
    with pytest.raises(ValidationError, match="alias"):
        CombinationFacts.model_validate(payload)


def test_original_numeric_json_nonfinite_and_missing_quantity_fields_rejected() -> None:
    wire = quantity().model_dump_json(by_alias=True)
    for token in ("0", "false", "null", "1e400", "NaN", "-1"):
        with pytest.raises(ValidationError):
            validate_contract_json(
                ComponentQuantity, wire.replace('"amount":25', '"amount":' + token)
            )
    for field in (
        "amount",
        "unit",
        "preparation_id",
        "preparation_version",
        "basis_reference",
        "portion_reference",
    ):
        payload = quantity().model_dump()
        del payload[field]
        with pytest.raises(ValidationError):
            ComponentQuantity.model_validate(payload)


def test_missing_candidate_has_no_eligibility_path_in_contract_slice() -> None:
    body = content()
    body["components"] = (
        component().model_copy(
            update={
                "recipe_snapshot": reference().model_copy(update={"snapshot_id": "not-supplied"}),
                "preparation": preparation(
                    reference().model_copy(update={"snapshot_id": "not-supplied"})
                ),
            }
        ),
    )
    declaration = CombinationFacts.build(body)
    assert "eligible" not in CombinationFacts.model_fields
    assert "status" not in CombinationFacts.model_fields
    # Structural declarations cannot claim candidate membership. Prompt 2 must reject
    # this reference against its independent accepted candidate set before evaluation.
    with pytest.raises(ValidationError):
        CombinationFacts.model_validate(declaration.model_copy(update={"eligible": True}))
