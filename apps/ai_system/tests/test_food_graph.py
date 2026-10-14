"""Synthetic graph fixtures only; no clinical, dietary, or nutritional advice."""

from enum import StrEnum
from itertools import permutations
from typing import Any

import pytest
from pydantic import ValidationError

from savora_ai.core.reasoning.graph import resolve_food_relations
from savora_ai.schemas import EvidenceReference, RuleEnvironment
from savora_ai.schemas.food_graph import (
    FoodEntity,
    FoodEntityKind,
    FoodGraphSnapshot,
    FoodRelation,
    FoodRelationType,
    KnowledgeCoverage,
    RelationAssertion,
    RelationQualifiers,
    RelationResolution,
    RelationResolutionStatus,
    TraversalMode,
)


def evidence(**changes: Any) -> EvidenceReference:
    return EvidenceReference.model_validate(
        {
            "evidence_id": "synthetic-graph-evidence",
            "version": "fixture-v1",
            "source": "SYNTHETIC graph fixture; no clinical or nutritional meaning",
            "locator": "urn:savora:test:food-graph",
            "environment": RuleEnvironment.SYNTHETIC,
        }
        | changes
    )


def entity(entity_id: str = "f001", **changes: Any) -> FoodEntity:
    return FoodEntity.model_validate(
        {
            "entity_id": entity_id,
            "version": "fixture-v1",
            "kind": FoodEntityKind.INGREDIENT,
            "canonical_name": "Synthetic peanut",
            "evidence": (evidence(),),
        }
        | changes
    )


def relation(**changes: Any) -> FoodRelation:
    return FoodRelation.model_validate(
        {
            "relation_id": "r001",
            "version": "fixture-v1",
            "relation_type": FoodRelationType.DERIVED_FROM,
            "source_id": "f002",
            "target_id": "f001",
            "assertion": RelationAssertion.PRESENT,
            "evidence": (evidence(),),
        }
        | changes
    )


def coverage(**changes: Any) -> KnowledgeCoverage:
    return KnowledgeCoverage.model_validate(
        {
            "coverage_id": "c001",
            "version": "fixture-v1",
            "graph_id": "synthetic-graph",
            "graph_version": "fixture-v1",
            "catalogue_version": "synthetic-catalogue-v1",
            "subject_id": "f006",
            "relation_type": FoodRelationType.DERIVED_FROM,
            "complete": False,
            "reason": "SYNTHETIC incomplete ingredient relationship documentation",
            "evidence": (evidence(),),
        }
        | changes
    )


def snapshot(**changes: Any) -> FoodGraphSnapshot:
    return FoodGraphSnapshot.model_validate(
        {
            "graph_id": "synthetic-graph",
            "version": "fixture-v1",
            "catalogue_version": "synthetic-catalogue-v1",
            "environment": RuleEnvironment.SYNTHETIC,
            "entities": (
                entity(),
                entity("f002", canonical_name="Synthetic peanut butter"),
                entity(
                    "f003",
                    kind=FoodEntityKind.RECIPE_REFERENCE,
                    canonical_name="Synthetic peanut-containing recipe reference",
                    catalogue_reference="fixture-recipe-1",
                ),
                entity("f004", canonical_name="Synthetic rice"),
                entity("f005", canonical_name="Synthetic chicken"),
                entity("f006", canonical_name="Synthetic incomplete-coverage ingredient"),
                entity(
                    "f007",
                    kind=FoodEntityKind.CULINARY_ROLE_REFERENCE,
                    canonical_name="Synthetic role reference",
                    catalogue_reference="fixture-role-1",
                ),
                entity(
                    "f008",
                    kind=FoodEntityKind.CUISINE_REFERENCE,
                    canonical_name="Synthetic cuisine reference",
                    catalogue_reference="fixture-cuisine-1",
                ),
            ),
            "relations": (
                relation(),
                relation(
                    relation_id="r002",
                    relation_type=FoodRelationType.CONTAINS,
                    source_id="f003",
                ),
                relation(
                    relation_id="r003",
                    relation_type=FoodRelationType.CONTAINS,
                    source_id="f003",
                    target_id="f005",
                    assertion=RelationAssertion.ABSENT,
                ),
            ),
            "coverage": (coverage(),),
            "evidence": (evidence(),),
        }
        | changes
    )


def resolve(graph: FoodGraphSnapshot | None = None, **changes: Any) -> RelationResolution:
    return resolve_food_relations(
        snapshot() if graph is None else graph,
        **{
            "source_id": "f002",
            "target_id": "f001",
            "relation_type": FoodRelationType.DERIVED_FROM,
        }
        | changes,
    )


def test_direct_peanut_derivation_returns_exact_evidence_and_versions() -> None:
    result = resolve()
    assert result.status is RelationResolutionStatus.SUPPORTED
    assert result.relation == relation()
    assert result.evidence == (evidence(),)
    assert result.graph_version == "fixture-v1"
    assert result.catalogue_version == "synthetic-catalogue-v1"
    assert result.environment is RuleEnvironment.SYNTHETIC
    assert result.traversal is TraversalMode.DIRECT


def test_reverse_derivation_stays_unknown() -> None:
    assert resolve(source_id="f001", target_id="f002").status is RelationResolutionStatus.UNKNOWN


def test_exact_negative_containment_has_its_own_assertion() -> None:
    result = resolve(source_id="f003", target_id="f005", relation_type=FoodRelationType.CONTAINS)
    assert result.status is RelationResolutionStatus.VERIFIED_ABSENT
    assert result.relation is not None
    assert result.relation.assertion is RelationAssertion.ABSENT
    assert result.relation.version == "fixture-v1"


@pytest.mark.parametrize(
    "changes",
    [
        {"source_id": "f001", "target_id": "f004"},
        {"source_id": "f999"},
        {"target_id": "f999"},
        {"source_id": "f999", "target_id": "f999"},
        {"source_id": "Synthetic-peanut"},
        {"source_id": "F002"},
    ],
)
def test_missing_relationships_and_caller_ids_stay_unknown(changes: dict[str, Any]) -> None:
    result = resolve(**changes)
    assert result.status is RelationResolutionStatus.UNKNOWN
    assert result.relation is None


@pytest.mark.parametrize("complete", [False, True])
def test_coverage_never_manufactures_negative_evidence(complete: bool) -> None:
    graph = snapshot(coverage=(coverage(complete=complete),))
    result = resolve(graph, source_id="f006")
    assert result.status is RelationResolutionStatus.UNKNOWN
    assert result.coverage is not None
    assert result.coverage.complete is complete
    assert result.evidence == result.coverage.evidence


def test_coverage_is_exactly_scoped_and_can_coexist_with_positive_evidence() -> None:
    graph = snapshot(coverage=(coverage(subject_id="f002"),))
    result = resolve(graph)
    assert result.status is RelationResolutionStatus.SUPPORTED
    assert result.coverage is not None and result.coverage.complete is False
    assert resolve(graph, source_id="f006").coverage is None


def test_no_transitive_or_mixed_relation_inference() -> None:
    graph = snapshot(
        relations=(
            *snapshot().relations,
            relation(relation_id="r004", source_id="f006", target_id="f002"),
            relation(
                relation_id="r005",
                relation_type=FoodRelationType.CONTAINS,
                source_id="f004",
                target_id="f002",
            ),
        )
    )
    assert resolve(graph, source_id="f006").status is RelationResolutionStatus.UNKNOWN
    assert (
        resolve(graph, source_id="f004", relation_type=FoodRelationType.CONTAINS).status
        is RelationResolutionStatus.UNKNOWN
    )


@pytest.mark.parametrize("relation_type", list(FoodRelationType))
@pytest.mark.parametrize("assertion", list(RelationAssertion))
def test_all_five_tokens_resolve_only_exact_direction_and_qualifiers(
    relation_type: FoodRelationType, assertion: RelationAssertion
) -> None:
    target_id = "f007" if relation_type is FoodRelationType.HAS_CULINARY_ROLE else "f001"
    qualifiers = (
        RelationQualifiers(culinary_role_id="f007", cuisine_id="f008", meal_type="LUNCH")
        if relation_type is FoodRelationType.FUNCTIONAL_SUBSTITUTE_FOR
        else RelationQualifiers()
    )
    edge = relation(
        relation_type=relation_type,
        target_id=target_id,
        assertion=assertion,
        qualifiers=qualifiers,
    )
    graph = snapshot(relations=(edge,))
    result = resolve(graph, relation_type=relation_type, target_id=target_id, qualifiers=qualifiers)
    expected = (
        RelationResolutionStatus.SUPPORTED
        if assertion is RelationAssertion.PRESENT
        else RelationResolutionStatus.VERIFIED_ABSENT
    )
    assert result.status is expected
    if relation_type is not FoodRelationType.HAS_CULINARY_ROLE:
        assert (
            resolve(
                graph,
                source_id=target_id,
                target_id="f002",
                relation_type=relation_type,
                qualifiers=qualifiers,
            ).status
            is RelationResolutionStatus.UNKNOWN
        )


@pytest.mark.parametrize(
    "relation_type", [FoodRelationType.COMPATIBLE_WITH, FoodRelationType.HAS_CULINARY_ROLE]
)
@pytest.mark.parametrize("assertion", list(RelationAssertion))
def test_context_specific_edges_do_not_match_missing_or_different_context(
    relation_type: FoodRelationType, assertion: RelationAssertion
) -> None:
    target_id = "f007" if relation_type is FoodRelationType.HAS_CULINARY_ROLE else "f001"
    qualifiers = RelationQualifiers(cuisine_id="f008", meal_type="LUNCH")
    graph = snapshot(
        relations=(
            relation(
                relation_type=relation_type,
                target_id=target_id,
                assertion=assertion,
                qualifiers=qualifiers,
            ),
        )
    )
    for context in (
        None,
        RelationQualifiers(cuisine_id="f008", meal_type="DINNER"),
        RelationQualifiers(cuisine_id="f999", meal_type="LUNCH"),
    ):
        assert (
            resolve(
                graph, relation_type=relation_type, target_id=target_id, qualifiers=context
            ).status
            is RelationResolutionStatus.UNKNOWN
        )


@pytest.mark.parametrize("valid_id", ["f001", "a", "ID_2", "id.v1:part-2", "a" * 128])
def test_valid_opaque_ids_preserved(valid_id: str) -> None:
    assert entity(valid_id).entity_id == valid_id


@pytest.mark.parametrize(
    "invalid", ["", " ", "f001\n", " f001", "food name", "/food", "é", "a" * 129, 12, None]
)
def test_invalid_ids_rejected_at_declaration_and_query(invalid: Any) -> None:
    with pytest.raises(ValidationError):
        entity(invalid)
    with pytest.raises(ValidationError):
        resolve(source_id=invalid)


@pytest.mark.parametrize("field", ["entity_id", "version", "kind", "canonical_name", "evidence"])
def test_entity_required_fields_cannot_be_omitted(field: str) -> None:
    data = entity().model_dump()
    del data[field]
    with pytest.raises(ValidationError):
        FoodEntity.model_validate(data)


@pytest.mark.parametrize(
    "kind",
    [
        FoodEntityKind.RECIPE_REFERENCE,
        FoodEntityKind.CULINARY_ROLE_REFERENCE,
        FoodEntityKind.CUISINE_REFERENCE,
    ],
)
def test_reference_entities_require_catalogue_identity(kind: FoodEntityKind) -> None:
    with pytest.raises(ValidationError, match="catalogue reference"):
        entity(kind=kind)


@pytest.mark.parametrize(
    "duplicate",
    [entity(), entity(version="fixture-v2"), entity(canonical_name="Conflicting synthetic name")],
)
def test_duplicate_or_conflicting_entity_identity_rejected(duplicate: FoodEntity) -> None:
    with pytest.raises(ValidationError, match="duplicate entity"):
        snapshot(entities=(*snapshot().entities, duplicate))


def test_duplicate_aliases_rejected_but_shared_names_do_not_merge_entities() -> None:
    with pytest.raises(ValidationError, match="aliases"):
        entity(aliases=("alias", "alias"))
    graph = snapshot(entities=(entity(), entity("f002")), relations=(), coverage=())
    assert len(graph.entities) == 2


@pytest.mark.parametrize("duplicate", [relation(), relation(version="fixture-v2")])
def test_relation_identity_unique_across_versions(duplicate: FoodRelation) -> None:
    with pytest.raises(ValidationError, match="duplicate relation identity"):
        snapshot(relations=(relation(), duplicate))


@pytest.mark.parametrize("assertion", list(RelationAssertion))
def test_same_directed_qualified_assertion_cannot_be_redeclared(
    assertion: RelationAssertion,
) -> None:
    with pytest.raises(ValidationError, match=r"contradictory|duplicate directed"):
        snapshot(relations=(relation(), relation(relation_id="r999", assertion=assertion)))


@pytest.mark.parametrize("field", ["source_id", "target_id"])
@pytest.mark.parametrize("assertion", list(RelationAssertion))
def test_dangling_endpoints_invalidate_positive_and_negative_edges(
    field: str, assertion: RelationAssertion
) -> None:
    with pytest.raises(ValidationError, match="dangling"):
        snapshot(relations=(relation(assertion=assertion, **{field: "f999"}),))


@pytest.mark.parametrize(
    "changes", [{"source_id": "f007"}, {"target_id": "f003"}, {"source_id": "f003"}]
)
def test_invalid_derivation_endpoint_types_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        snapshot(relations=(relation(**changes),))
    with pytest.raises(ValidationError):
        resolve(**changes)


@pytest.mark.parametrize(
    "relation_type,qualifiers",
    [
        (FoodRelationType.CONTAINS, RelationQualifiers(meal_type="LUNCH")),
        (FoodRelationType.DERIVED_FROM, RelationQualifiers(cuisine_id="f008")),
        (FoodRelationType.HAS_CULINARY_ROLE, RelationQualifiers(culinary_role_id="f007")),
        (FoodRelationType.FUNCTIONAL_SUBSTITUTE_FOR, RelationQualifiers()),
    ],
)
def test_unsupported_qualifier_combinations_rejected_for_records_and_queries(
    relation_type: FoodRelationType, qualifiers: RelationQualifiers
) -> None:
    with pytest.raises(ValidationError):
        relation(relation_type=relation_type, qualifiers=qualifiers)
    with pytest.raises(ValidationError):
        resolve(relation_type=relation_type, qualifiers=qualifiers)


@pytest.mark.parametrize("context_id", ["f999", "f001", "f007"])
def test_snapshot_qualifiers_must_reference_correct_existing_kind(context_id: str) -> None:
    with pytest.raises(ValidationError, match="qualifiers require"):
        snapshot(
            relations=(
                relation(
                    relation_type=FoodRelationType.COMPATIBLE_WITH,
                    qualifiers=RelationQualifiers(cuisine_id=context_id),
                ),
            )
        )


@pytest.mark.parametrize("relation_type", list(FoodRelationType))
def test_self_relations_rejected(relation_type: FoodRelationType) -> None:
    qualifiers = (
        RelationQualifiers(culinary_role_id="f007")
        if relation_type is FoodRelationType.FUNCTIONAL_SUBSTITUTE_FOR
        else RelationQualifiers()
    )
    with pytest.raises(ValidationError, match="self-relations"):
        relation(relation_type=relation_type, source_id="f001", qualifiers=qualifiers)


@pytest.mark.parametrize(
    "relation_type", [FoodRelationType.CONTAINS, FoodRelationType.DERIVED_FROM]
)
def test_positive_structural_cycles_rejected(relation_type: FoodRelationType) -> None:
    with pytest.raises(ValidationError, match="cycles"):
        snapshot(
            relations=(
                relation(relation_type=relation_type),
                relation(
                    relation_id="r002",
                    relation_type=relation_type,
                    source_id="f001",
                    target_id="f002",
                ),
            )
        )


def test_reciprocal_compatibility_is_valid_only_when_explicit() -> None:
    graph = snapshot(
        relations=(
            relation(relation_type=FoodRelationType.COMPATIBLE_WITH),
            relation(
                relation_id="r002",
                relation_type=FoodRelationType.COMPATIBLE_WITH,
                source_id="f001",
                target_id="f002",
            ),
        )
    )
    assert (
        resolve(
            graph,
            source_id="f001",
            target_id="f002",
            relation_type=FoodRelationType.COMPATIBLE_WITH,
        ).status
        is RelationResolutionStatus.SUPPORTED
    )


@pytest.mark.parametrize("make", [entity, relation, coverage, snapshot])
def test_every_record_requires_nonduplicate_evidence(make: Any) -> None:
    with pytest.raises(ValidationError, match="require evidence"):
        make(evidence=())
    with pytest.raises(ValidationError, match="duplicate evidence"):
        make(evidence=(evidence(), evidence()))


@pytest.mark.parametrize("location", ["entity", "relation", "coverage", "snapshot"])
@pytest.mark.parametrize(
    "changes",
    [
        {"source": "Conflicting SYNTHETIC source"},
        {"locator": "urn:conflict"},
        {"environment": RuleEnvironment.PRODUCTION},
    ],
)
def test_global_evidence_identity_cannot_change_metadata(
    location: str, changes: dict[str, Any]
) -> None:
    conflicting = evidence(**changes)
    overrides: dict[str, Any] = {}
    if location == "entity":
        overrides["entities"] = (entity(evidence=(conflicting,)), *snapshot().entities[1:])
    elif location == "relation":
        overrides["relations"] = (relation(evidence=(conflicting,)),)
    elif location == "coverage":
        overrides["coverage"] = (coverage(evidence=(conflicting,)),)
    else:
        overrides["evidence"] = (conflicting,)
    with pytest.raises(ValidationError, match=r"conflicting evidence|environment"):
        snapshot(**overrides)


def test_identical_provenance_reuse_and_distinct_versions_are_valid() -> None:
    graph = snapshot(
        evidence=(evidence(), evidence(version="fixture-v2", source="Revised SYNTHETIC source"))
    )
    assert resolve(graph).status is RelationResolutionStatus.SUPPORTED


def test_environment_labels_cannot_mix_or_enable_production_resolution() -> None:
    with pytest.raises(ValidationError, match="environment"):
        snapshot(environment=RuleEnvironment.PRODUCTION)
    # Adversarial relabelling is not a usable fixture or authenticated production data.
    wire = snapshot().model_dump_json(by_alias=True).replace('"SYNTHETIC"', '"PRODUCTION"')
    relabelled = FoodGraphSnapshot.model_validate_json(wire)
    with pytest.raises(ValidationError, match="SYNTHETIC snapshots only"):
        resolve(relabelled)


@pytest.mark.parametrize(
    "changes",
    [
        {"graph_id": "other"},
        {"graph_version": "fixture-v2"},
        {"catalogue_version": "other"},
        {"subject_id": "f999"},
        {"subject_id": "f007"},
    ],
)
def test_coverage_must_bind_to_exact_graph_catalogue_and_subject(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        snapshot(coverage=(coverage(**changes),))


def test_duplicate_coverage_identity_and_scope_rejected() -> None:
    for duplicate in (coverage(), coverage(coverage_id="c002", complete=True)):
        with pytest.raises(ValidationError, match="duplicate"):
            snapshot(coverage=(coverage(), duplicate))


@pytest.mark.parametrize("field", ["schema_version", "semantic_policy_version"])
def test_unsupported_policy_versions_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        snapshot(**{field: "unsupported-v2"})


@pytest.mark.parametrize(
    "changes", [{"entities": []}, {"environment": "SYNTHETIC"}, {"unknown_field": True}]
)
def test_strict_python_snapshot_boundary(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        snapshot(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"traversal": "DIRECT"},
        {"traversal": "ORIGIN_PATH"},
        {"relation_type": "DERIVED_FROM"},
        {"relation_type": "IS_A"},
        {"qualifiers": {"meal_type": "UNKNOWN"}},
        {"qualifiers": {"unexpected_field": True}},
    ],
)
def test_query_rejects_unsupported_or_unvalidated_tokens(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        resolve(**changes)


def test_nested_models_and_collections_are_frozen() -> None:
    graph = snapshot()
    with pytest.raises(ValidationError, match="frozen_instance"):
        graph.version = "fixture-v2"
    with pytest.raises(ValidationError, match="frozen_instance"):
        graph.entities[0].canonical_name = "Changed"
    with pytest.raises(ValidationError, match="frozen_instance"):
        graph.relations[0].qualifiers.meal_type = "DINNER"
    with pytest.raises(ValidationError, match="frozen_instance"):
        graph.coverage[0].complete = True
    with pytest.raises(ValidationError, match="frozen_instance"):
        graph.evidence[0].source = "Changed"
    assert isinstance(graph.entities, tuple)
    assert isinstance(graph.relations, tuple)
    assert isinstance(graph.coverage, tuple)


def test_snapshot_and_resolution_serialization_round_trip() -> None:
    graph = snapshot()
    wire = graph.model_dump_json(by_alias=True)
    assert '"catalogueVersion"' in wire and '"evidenceId"' in wire
    restored = FoodGraphSnapshot.model_validate_json(wire)
    assert restored == graph
    result = resolve(restored)
    assert RelationResolution.model_validate_json(result.model_dump_json(by_alias=True)) == result


@pytest.mark.parametrize(
    "location", ["snapshot", "entity", "relation", "qualifiers", "evidence", "coverage"]
)
def test_resolver_preserves_unexpected_fields_in_unchecked_nested_copies(location: str) -> None:
    graph = snapshot()
    update = {"unexpected_unchecked_field": True}
    if location == "snapshot":
        graph = graph.model_copy(update=update)
    elif location == "entity":
        graph = graph.model_copy(
            update={"entities": (graph.entities[0].model_copy(update=update), *graph.entities[1:])}
        )
    elif location == "relation":
        graph = graph.model_copy(
            update={"relations": (graph.relations[0].model_copy(update=update),)}
        )
    elif location == "qualifiers":
        unchecked = graph.relations[0].model_copy(
            update={"qualifiers": RelationQualifiers().model_copy(update=update)}
        )
        graph = graph.model_copy(update={"relations": (unchecked,)})
    elif location == "evidence":
        unchecked = graph.relations[0].model_copy(
            update={"evidence": (evidence().model_copy(update=update),)}
        )
        graph = graph.model_copy(update={"relations": (unchecked,)})
    else:
        graph = graph.model_copy(
            update={"coverage": (graph.coverage[0].model_copy(update=update),)}
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        resolve(graph)


@pytest.mark.parametrize(
    "changes", [{"target_id": "f999"}, {"evidence": ()}, {"assertion": "PRESENT"}, {"version": " "}]
)
def test_resolver_rejects_unchecked_relation_defects(changes: dict[str, Any]) -> None:
    graph = snapshot()
    graph = graph.model_copy(update={"relations": (graph.relations[0].model_copy(update=changes),)})
    with pytest.raises(ValidationError):
        resolve(graph)


def test_resolver_rejects_constructed_snapshot_and_copied_contradiction() -> None:
    graph = snapshot()
    unchecked_data: dict[str, Any] = graph.model_dump()
    unchecked_data["relations"] = []
    constructed = FoodGraphSnapshot.model_construct(**unchecked_data)
    with pytest.raises(ValidationError):
        resolve(constructed)
    contradictory = relation(relation_id="r999", assertion=RelationAssertion.ABSENT)
    unchecked = graph.model_copy(update={"relations": (*graph.relations, contradictory)})
    with pytest.raises(ValidationError, match="contradictory"):
        resolve(unchecked)


def test_resolver_rejects_unchecked_evidence_conflict() -> None:
    graph = snapshot()
    bad = graph.relations[0].model_copy(update={"evidence": (evidence(locator="urn:conflict"),)})
    with pytest.raises(ValidationError, match="conflicting evidence"):
        resolve(graph.model_copy(update={"relations": (bad,)}))


def test_resolver_reports_cyclic_payload_as_validation_error() -> None:
    cyclic: dict[str, Any] = {}
    cyclic["entities"] = cyclic
    graph = snapshot().model_copy(update={"entities": cyclic})
    with pytest.raises(ValidationError, match="cyclic or excessively deep"):
        resolve(graph)


def test_resolver_revalidates_unchecked_query_qualifiers() -> None:
    bad = RelationQualifiers().model_copy(update={"unexpected_query_field": True})
    with pytest.raises(ValidationError, match="Extra inputs"):
        resolve(qualifiers=bad)


def test_empty_graph_is_unknown_with_snapshot_provenance() -> None:
    graph = snapshot(entities=(), relations=(), coverage=())
    result = resolve(graph)
    assert result.status is RelationResolutionStatus.UNKNOWN
    assert result.evidence == graph.evidence


def test_entity_and_relation_order_do_not_change_results() -> None:
    graph = snapshot()
    expected = resolve(graph)
    for edges in permutations(graph.relations):
        reordered = snapshot(entities=tuple(reversed(graph.entities)), relations=edges)
        assert resolve(reordered) == expected


def test_resolution_rejects_status_and_release_mismatches() -> None:
    result = resolve()
    data = result.model_dump()
    with pytest.raises(ValidationError, match="contradicts"):
        RelationResolution.model_validate(
            data | {"status": RelationResolutionStatus.VERIFIED_ABSENT}
        )
    with pytest.raises(ValidationError, match="unknown resolutions"):
        RelationResolution.model_validate(data | {"status": RelationResolutionStatus.UNKNOWN})
    scoped = resolve(snapshot(coverage=(coverage(subject_id="f002"),)))
    with pytest.raises(ValidationError, match="coverage differs"):
        RelationResolution.model_validate(scoped.model_dump() | {"graph_version": "fixture-v2"})


def test_evidence_order_is_deterministic_in_embedded_records_and_unknown_results() -> None:
    first = evidence()
    second = evidence(evidence_id="synthetic-second-source", locator="urn:savora:test:second")
    graphs = [
        snapshot(
            relations=(relation(evidence=references),),
            coverage=(coverage(subject_id="f002", evidence=references),),
            evidence=references,
        )
        for references in ((first, second), (second, first))
    ]
    for query in ({}, {"target_id": "f004"}, {"source_id": "f006"}):
        results = [resolve(graph, **query).model_dump_json(by_alias=True) for graph in graphs]
        assert results[0] == results[1]


def fabricated_enum(enum_type: type[StrEnum], token: str) -> StrEnum:
    """Adversarial object of the right class that is not a declared singleton."""
    forged = str.__new__(enum_type, token)
    forged._name_ = token
    forged._value_ = token
    return forged


def unchecked_model(record: Any, changes: dict[str, Any], mode: str) -> Any:
    if mode == "copy":
        return record.model_copy(update=changes)
    data: dict[str, Any] = vars(record) | (record.model_extra or {})
    return type(record).model_construct(**(data | changes))


@pytest.mark.parametrize(
    "record,field",
    [
        (entity(), "kind"),
        (relation(), "relation_type"),
        (relation(), "assertion"),
        (coverage(), "relation_type"),
        (snapshot(), "environment"),
        (resolve(), "environment"),
        (resolve(), "relation_type"),
        (resolve(), "traversal"),
        (resolve(), "status"),
    ],
)
@pytest.mark.parametrize("valid_token", [False, True])
def test_every_graph_enum_field_requires_canonical_members(
    record: Any, field: str, valid_token: bool
) -> None:
    member = getattr(record, field)
    forged = fabricated_enum(type(member), member.value if valid_token else "UNAPPROVED")
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        type(record).model_validate(record.model_dump() | {field: forged})


@pytest.mark.parametrize(
    "location,field",
    [
        ("entity", "kind"),
        ("relation", "relation_type"),
        ("relation", "assertion"),
        ("coverage", "relation_type"),
        ("snapshot", "environment"),
        ("evidence", "environment"),
    ],
)
@pytest.mark.parametrize("valid_token", [False, True])
@pytest.mark.parametrize("mode", ["copy", "construct"])
def test_public_boundary_rejects_nested_fabricated_enums(
    location: str, field: str, valid_token: bool, mode: str
) -> None:
    graph = snapshot()
    records: dict[str, Any] = {
        "entity": graph.entities[0],
        "relation": graph.relations[0],
        "coverage": graph.coverage[0],
        "snapshot": graph,
        "evidence": graph.relations[0].evidence[0],
    }
    record = records[location]
    member = getattr(record, field)
    forged = fabricated_enum(type(member), member.value if valid_token else "UNAPPROVED")
    bad = unchecked_model(record, {field: forged}, mode)
    if location == "entity":
        graph = graph.model_copy(update={"entities": (bad, *graph.entities[1:])})
    elif location == "relation":
        graph = graph.model_copy(update={"relations": (bad,)})
    elif location == "coverage":
        graph = graph.model_copy(update={"coverage": (bad,)})
    elif location == "evidence":
        edge = graph.relations[0].model_copy(update={"evidence": (bad,)})
        graph = graph.model_copy(update={"relations": (edge,)})
    else:
        graph = bad
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        resolve(graph)


@pytest.mark.parametrize(
    "field,member",
    [("relation_type", FoodRelationType.DERIVED_FROM), ("traversal", TraversalMode.DIRECT)],
)
@pytest.mark.parametrize("valid_token", [False, True])
@pytest.mark.parametrize("assertion", list(RelationAssertion))
def test_fabricated_public_query_enums_never_return_affirmative_results(
    field: str, member: StrEnum, valid_token: bool, assertion: RelationAssertion
) -> None:
    graph = snapshot(relations=(relation(assertion=assertion),))
    forged = fabricated_enum(type(member), member.value if valid_token else "UNAPPROVED")
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        resolve(graph, **{field: forged})


@pytest.mark.parametrize("assertion", list(RelationAssertion))
@pytest.mark.parametrize("mode", ["copy", "construct"])
def test_original_unsupported_relation_reproduction_is_rejected(
    assertion: RelationAssertion, mode: str
) -> None:
    graph = snapshot()
    forged = fabricated_enum(FoodRelationType, "UNAPPROVED")
    edge = unchecked_model(
        graph.relations[0], {"relation_type": forged, "assertion": assertion}, mode
    )
    graph = graph.model_copy(update={"relations": (edge,)})
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        resolve(graph, relation_type=forged)


@pytest.mark.parametrize("mode", ["copy", "construct"])
def test_counterfeit_derivation_cannot_bypass_endpoint_restrictions(mode: str) -> None:
    graph = snapshot()
    forged = fabricated_enum(FoodRelationType, "DERIVED_FROM")
    edge = unchecked_model(graph.relations[0], {"relation_type": forged, "source_id": "f003"}, mode)
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        resolve(
            graph.model_copy(update={"relations": (edge,)}), source_id="f003", relation_type=forged
        )
    # Canonical members still enforce the original endpoint policy.
    with pytest.raises(ValidationError, match="derivation sources must be ingredients"):
        snapshot(relations=(relation(source_id="f003"),))


@pytest.mark.parametrize(
    "relation_type", [FoodRelationType.CONTAINS, FoodRelationType.DERIVED_FROM]
)
@pytest.mark.parametrize("mode", ["copy", "construct"])
def test_counterfeit_members_cannot_hide_positive_cycles(
    relation_type: FoodRelationType, mode: str
) -> None:
    graph = snapshot()
    forged = fabricated_enum(FoodRelationType, relation_type.value)
    forward = unchecked_model(graph.relations[0], {"relation_type": forged}, mode)
    reverse = unchecked_model(
        forward, {"relation_id": "r999", "source_id": "f001", "target_id": "f002"}, mode
    )
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        resolve(graph.model_copy(update={"relations": (forward, reverse)}), relation_type=forged)


@pytest.mark.parametrize("assertion", list(RelationAssertion))
def test_fake_origin_traversal_is_rejected(assertion: RelationAssertion) -> None:
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        resolve(
            snapshot(relations=(relation(assertion=assertion),)),
            traversal=fabricated_enum(TraversalMode, "ORIGIN_PATH"),
        )


@pytest.mark.parametrize("assertion", list(RelationAssertion))
def test_canonical_enum_results_survive_json_round_trips(assertion: RelationAssertion) -> None:
    graph = snapshot(relations=(relation(assertion=assertion),))
    restored = FoodGraphSnapshot.model_validate_json(graph.model_dump_json(by_alias=True))
    assert restored.environment is RuleEnvironment.SYNTHETIC
    assert restored.entities[0].kind is FoodEntityKind.INGREDIENT
    assert restored.relations[0].relation_type is FoodRelationType.DERIVED_FROM
    assert restored.relations[0].assertion is assertion
    result = resolve(restored)
    restored_result = RelationResolution.model_validate_json(result.model_dump_json(by_alias=True))
    assert restored_result == result
    assert restored_result.traversal is TraversalMode.DIRECT
    assert restored_result.status is result.status
    invalid_wire = result.model_dump_json(by_alias=True).replace('"DERIVED_FROM"', '"UNAPPROVED"')
    with pytest.raises(ValidationError):
        RelationResolution.model_validate_json(invalid_wire)


@pytest.mark.parametrize("kind", list(FoodEntityKind))
@pytest.mark.parametrize("duplicate_version", ["fixture-v1", "fixture-v2"])
def test_catalogue_bindings_are_unique_regardless_of_entity_content_version(
    kind: FoodEntityKind, duplicate_version: str
) -> None:
    first = entity("f001", kind=kind, catalogue_reference="synthetic-object-1")
    duplicate = entity(
        "f002", kind=kind, catalogue_reference="synthetic-object-1", version=duplicate_version
    )
    with pytest.raises(ValidationError, match="duplicate catalogue binding"):
        snapshot(entities=(first, duplicate), relations=(), coverage=())


@pytest.mark.parametrize("mode", ["copy", "construct"])
def test_original_duplicate_recipe_binding_reproduction_is_rejected(mode: str) -> None:
    graph = snapshot()
    duplicate = entity(
        "f009",
        kind=FoodEntityKind.RECIPE_REFERENCE,
        catalogue_reference="fixture-recipe-1",
    )
    negative = relation(
        relation_id="r999",
        relation_type=FoodRelationType.CONTAINS,
        source_id="f009",
        assertion=RelationAssertion.ABSENT,
    )
    changes = {"entities": (*graph.entities, duplicate), "relations": (*graph.relations, negative)}
    with pytest.raises(ValidationError, match="duplicate catalogue binding"):
        FoodGraphSnapshot.model_validate(graph.model_dump() | changes)
    with pytest.raises(ValidationError, match="duplicate catalogue binding"):
        resolve(
            unchecked_model(graph, changes, mode),
            source_id="f009",
            relation_type=FoodRelationType.CONTAINS,
        )


@pytest.mark.parametrize(
    "kind,field,original_id,reference",
    [
        (FoodEntityKind.CUISINE_REFERENCE, "cuisine_id", "f008", "fixture-cuisine-1"),
        (FoodEntityKind.CULINARY_ROLE_REFERENCE, "culinary_role_id", "f007", "fixture-role-1"),
    ],
)
def test_duplicate_context_bindings_cannot_split_opposing_assertions(
    kind: FoodEntityKind, field: str, original_id: str, reference: str
) -> None:
    graph = snapshot()
    duplicate = entity("f009", kind=kind, catalogue_reference=reference)
    edges = tuple(
        relation(
            relation_id=f"r00{index}",
            relation_type=FoodRelationType.COMPATIBLE_WITH,
            qualifiers=RelationQualifiers.model_validate({field: context_id}),
            assertion=assertion,
        )
        for index, context_id, assertion in (
            (1, original_id, RelationAssertion.PRESENT),
            (2, "f009", RelationAssertion.ABSENT),
        )
    )
    with pytest.raises(ValidationError, match="duplicate catalogue binding"):
        resolve(
            graph.model_copy(update={"entities": (*graph.entities, duplicate), "relations": edges}),
            relation_type=FoodRelationType.COMPATIBLE_WITH,
        )


@pytest.mark.parametrize("kind", list(FoodEntityKind))
def test_display_names_do_not_merge_distinct_catalogue_objects(kind: FoodEntityKind) -> None:
    first = entity("f001", kind=kind, catalogue_reference="synthetic-object-1")
    second = entity("f002", kind=kind, catalogue_reference="synthetic-object-2")
    graph = snapshot(entities=(first, second), relations=(), coverage=())
    assert graph.entities[0].canonical_name == graph.entities[1].canonical_name
    assert graph.entities[0].catalogue_reference != graph.entities[1].catalogue_reference


def test_catalogue_identity_is_scoped_by_kind_and_snapshot_release() -> None:
    refs = tuple(
        entity(f"f00{index}", kind=kind, catalogue_reference="synthetic-object-1")
        for index, kind in enumerate(FoodEntityKind, start=1)
    )
    assert len(snapshot(entities=refs, relations=(), coverage=()).entities) == 4
    first = snapshot(coverage=())
    second = snapshot(catalogue_version="synthetic-catalogue-v2", coverage=())
    assert first.entities == second.entities
    assert resolve(first).catalogue_version != resolve(second).catalogue_version
    # Stale coverage is still invalid; the uniqueness fix does not relax version binding.
    with pytest.raises(ValidationError, match="version mismatch"):
        snapshot(catalogue_version="synthetic-catalogue-v2")


def origin_edge(relation_id: str, source_id: str, target_id: str, **changes: Any) -> FoodRelation:
    return relation(
        **{
            "relation_id": relation_id,
            "source_id": source_id,
            "target_id": target_id,
            "evidence": (
                evidence(
                    evidence_id=f"synthetic-{relation_id}", locator=f"urn:savora:test:{relation_id}"
                ),
            ),
        }
        | changes
    )


def origin_graph(
    edges: tuple[FoodRelation, ...] | None = None, **changes: Any
) -> FoodGraphSnapshot:
    return snapshot(
        **{
            "entities": (
                *snapshot().entities,
                entity("f009", canonical_name="Synthetic peanut derivative"),
                entity("f010", canonical_name="Synthetic unrelated ingredient"),
            ),
            "relations": (
                origin_edge("r101", "f009", "f006"),
                origin_edge("r102", "f006", "f002"),
                origin_edge("r103", "f002", "f001"),
            )
            if edges is None
            else edges,
        }
        | changes
    )


def resolve_origin(graph: FoodGraphSnapshot | None = None, **changes: Any) -> RelationResolution:
    return resolve(
        origin_graph() if graph is None else graph,
        **{"source_id": "f009", "traversal": TraversalMode.ORIGIN_PATH} | changes,
    )


@pytest.mark.parametrize(
    "source_id,expected_ids",
    [
        ("f002", ("r103",)),
        ("f006", ("r102", "r103")),
        ("f009", ("r101", "r102", "r103")),
    ],
)
def test_origin_one_two_and_three_hop_witnesses(
    source_id: str, expected_ids: tuple[str, ...]
) -> None:
    result = resolve_origin(source_id=source_id)
    assert result.status is RelationResolutionStatus.SUPPORTED
    assert tuple(edge.relation_id for edge in result.path) == expected_ids
    assert result.relation is None
    assert result.reason_code == "ORIGIN_PATH_SUPPORTED"
    assert result.limit_reached is False
    assert {ref.evidence_id for ref in result.evidence} == {
        f"synthetic-{id_}" for id_ in expected_ids
    }


@pytest.mark.parametrize(
    "source_id,target_id,reason",
    [
        ("f001", "f009", "NO_ORIGIN_PATH"),
        ("f009", "f010", "NO_ORIGIN_PATH"),
        ("f999", "f001", "MISSING_ENTITY"),
        ("f009", "f999", "MISSING_ENTITY"),
        ("f009", "f009", "NO_ORIGIN_PATH"),
    ],
)
def test_origin_missing_reverse_and_reflexive_queries_are_unknown(
    source_id: str, target_id: str, reason: str
) -> None:
    result = resolve_origin(source_id=source_id, target_id=target_id)
    assert result.status is RelationResolutionStatus.UNKNOWN
    assert result.reason_code == reason
    assert not result.path and result.relation is None and not result.limit_reached


@pytest.mark.parametrize("blocked_type", ["negative", "contains", "compatible"])
def test_origin_never_traverses_negative_or_mixed_edges(blocked_type: str) -> None:
    overrides: dict[str, Any] = {}
    if blocked_type == "negative":
        overrides["assertion"] = RelationAssertion.ABSENT
    else:
        overrides["relation_type"] = (
            FoodRelationType.CONTAINS
            if blocked_type == "contains"
            else FoodRelationType.COMPATIBLE_WITH
        )
    graph = origin_graph(
        (origin_edge("r101", "f009", "f002", **overrides), origin_edge("r102", "f002", "f001"))
    )
    result = resolve_origin(graph)
    assert result.status is RelationResolutionStatus.UNKNOWN
    assert result.reason_code == "NO_ORIGIN_PATH" and not result.limit_reached
    assert not result.path


def test_negative_direct_assertion_does_not_deny_an_indirect_origin() -> None:
    graph = origin_graph(
        (
            origin_edge("r100", "f009", "f001", assertion=RelationAssertion.ABSENT),
            origin_edge("r101", "f009", "f002"),
            origin_edge("r102", "f002", "f001"),
        )
    )
    direct = resolve(graph, source_id="f009")
    assert direct.status is RelationResolutionStatus.VERIFIED_ABSENT
    assert direct.reason_code == "DIRECT_VERIFIED_ABSENT" and not direct.path
    origin = resolve_origin(graph)
    assert origin.status is RelationResolutionStatus.SUPPORTED
    assert tuple(edge.relation_id for edge in origin.path) == ("r101", "r102")
    assert {ref.evidence_id for ref in origin.evidence} == {"synthetic-r101", "synthetic-r102"}


def test_negative_direct_assertion_alone_never_proves_origin_absence() -> None:
    graph = origin_graph((origin_edge("r100", "f009", "f001", assertion=RelationAssertion.ABSENT),))
    result = resolve_origin(graph, max_hops=1, max_visited=1)
    assert result.status is RelationResolutionStatus.UNKNOWN
    assert result.reason_code == "NO_ORIGIN_PATH" and not result.limit_reached


def test_bfs_prefers_shortest_path_over_smaller_ids_on_longer_paths() -> None:
    graph = origin_graph(
        (
            origin_edge("r001", "f009", "f006"),
            origin_edge("r002", "f006", "f002"),
            origin_edge("r003", "f002", "f001"),
            origin_edge("r900", "f009", "f001"),
        )
    )
    assert tuple(edge.relation_id for edge in resolve_origin(graph).path) == ("r900",)


def test_equal_length_ties_use_relation_id_sequences_independent_of_insertion_order() -> None:
    edges = (
        origin_edge("r100", "f009", "f006"),
        origin_edge("r900", "f006", "f001"),
        origin_edge("r200", "f009", "f002"),
        origin_edge("r001", "f002", "f001"),
    )
    expected = resolve_origin(origin_graph(edges))
    assert tuple(edge.relation_id for edge in expected.path) == ("r100", "r900")
    for ordering in permutations(edges):
        graph = origin_graph(ordering, entities=tuple(reversed(origin_graph().entities)))
        assert resolve_origin(graph).model_dump_json(by_alias=True) == expected.model_dump_json(
            by_alias=True
        )


def test_converging_paths_count_each_discovered_entity_once() -> None:
    graph = origin_graph(
        (
            origin_edge("r100", "f009", "f006"),
            origin_edge("r200", "f009", "f004"),
            origin_edge("r300", "f006", "f002"),
            origin_edge("r400", "f004", "f002"),
            origin_edge("r500", "f002", "f001"),
        )
    )
    result = resolve_origin(graph, max_visited=5)
    assert result.status is RelationResolutionStatus.SUPPORTED
    assert tuple(edge.relation_id for edge in result.path) == ("r100", "r300", "r500")
    bounded = resolve_origin(graph, max_visited=4)
    assert bounded.status is RelationResolutionStatus.UNKNOWN
    assert bounded.reason_code == "MAX_VISITED_REACHED" and bounded.limit_reached


@pytest.mark.parametrize(
    "max_hops,status,reason",
    [
        (1, RelationResolutionStatus.UNKNOWN, "MAX_HOPS_REACHED"),
        (2, RelationResolutionStatus.UNKNOWN, "MAX_HOPS_REACHED"),
        (3, RelationResolutionStatus.SUPPORTED, "ORIGIN_PATH_SUPPORTED"),
        (4, RelationResolutionStatus.SUPPORTED, "ORIGIN_PATH_SUPPORTED"),
    ],
)
def test_max_hops_is_inclusive_and_never_proves_absence(
    max_hops: int, status: RelationResolutionStatus, reason: str
) -> None:
    result = resolve_origin(max_hops=max_hops)
    assert result.status is status and result.reason_code == reason
    assert result.limit_reached is (status is RelationResolutionStatus.UNKNOWN)


@pytest.mark.parametrize("max_visited", [1, 2, 3, 4, 5])
def test_max_visited_includes_source_and_target(max_visited: int) -> None:
    result = resolve_origin(max_visited=max_visited)
    if max_visited < 4:
        assert result.status is RelationResolutionStatus.UNKNOWN
        assert result.limit_reached and result.reason_code == "MAX_VISITED_REACHED"
    else:
        assert result.status is RelationResolutionStatus.SUPPORTED
        assert not result.limit_reached


def test_hitting_a_budget_value_without_blocked_work_is_ordinary_exhaustion() -> None:
    leaf = resolve_origin(origin_graph(()), max_hops=1, max_visited=1)
    assert leaf.status is RelationResolutionStatus.UNKNOWN and not leaf.limit_reached
    exact = resolve_origin(
        origin_graph((origin_edge("r100", "f009", "f006"),)),
        target_id="f010",
        max_hops=1,
        max_visited=2,
    )
    assert exact.reason_code == "NO_ORIGIN_PATH" and not exact.limit_reached


def test_visited_budget_is_checked_before_target_acceptance() -> None:
    graph = origin_graph((origin_edge("r100", "f009", "f006"), origin_edge("r900", "f009", "f001")))
    assert resolve_origin(graph, max_visited=2).reason_code == "MAX_VISITED_REACHED"
    result = resolve_origin(graph, max_visited=3)
    assert result.status is RelationResolutionStatus.SUPPORTED
    assert tuple(edge.relation_id for edge in result.path) == ("r900",)


@pytest.mark.parametrize("limit", ["max_hops", "max_visited"])
@pytest.mark.parametrize("invalid", [0, -1, True, False, 1.0, "1", None, [], float("inf")])
@pytest.mark.parametrize("traversal", [TraversalMode.DIRECT, TraversalMode.ORIGIN_PATH])
def test_invalid_limits_are_rejected_before_missing_entity_fallback(
    limit: str, invalid: Any, traversal: TraversalMode
) -> None:
    with pytest.raises(ValidationError):
        resolve(origin_graph(), source_id="f999", traversal=traversal, **{limit: invalid})


@pytest.mark.parametrize(
    "relation_type",
    [type_ for type_ in FoodRelationType if type_ is not FoodRelationType.DERIVED_FROM],
)
@pytest.mark.parametrize("source_id", ["f009", "f999"])
def test_origin_mode_requires_derivation_even_for_missing_entities(
    relation_type: FoodRelationType, source_id: str
) -> None:
    qualifiers = (
        RelationQualifiers(culinary_role_id="f007")
        if relation_type is FoodRelationType.FUNCTIONAL_SUBSTITUTE_FOR
        else None
    )
    with pytest.raises(ValidationError, match="ORIGIN_PATH supports DERIVED_FROM only"):
        resolve_origin(source_id=source_id, relation_type=relation_type, qualifiers=qualifiers)


@pytest.mark.parametrize("source_id,target_id", [("f003", "f001"), ("f009", "f007")])
def test_origin_query_endpoint_kinds_are_enforced(source_id: str, target_id: str) -> None:
    with pytest.raises(ValidationError):
        resolve_origin(source_id=source_id, target_id=target_id)


@pytest.mark.parametrize(
    "fault", ["cycle", "dangling", "self", "duplicate_binding", "evidence_conflict"]
)
@pytest.mark.parametrize("mode", ["copy", "construct"])
def test_origin_boundary_rejects_invalid_snapshots(fault: str, mode: str) -> None:
    graph = origin_graph()
    if fault == "cycle":
        changes = {"relations": (*graph.relations, origin_edge("r999", "f001", "f009"))}
    elif fault == "dangling":
        bad = unchecked_model(graph.relations[0], {"target_id": "f999"}, mode)
        changes = {"relations": (bad, *graph.relations[1:])}
    elif fault == "self":
        bad = unchecked_model(graph.relations[0], {"target_id": "f009"}, mode)
        changes = {"relations": (bad, *graph.relations[1:])}
    elif fault == "duplicate_binding":
        changes = {
            "entities": (
                *graph.entities,
                entity(
                    "f011",
                    kind=FoodEntityKind.RECIPE_REFERENCE,
                    catalogue_reference="fixture-recipe-1",
                ),
            )
        }
    else:
        bad = unchecked_model(
            graph.relations[0], {"evidence": (evidence(locator="urn:conflicting-source"),)}, mode
        )
        changes = {"relations": (bad, *graph.relations[1:])}
    with pytest.raises(ValidationError):
        resolve_origin(unchecked_model(graph, changes, mode))


@pytest.mark.parametrize(
    "field,enum_type,token",
    [
        ("relation_type", FoodRelationType, "DERIVED_FROM"),
        ("relation_type", FoodRelationType, "UNAPPROVED"),
        ("assertion", RelationAssertion, "PRESENT"),
    ],
)
@pytest.mark.parametrize("mode", ["copy", "construct"])
def test_origin_boundary_rejects_nested_counterfeit_enums(
    field: str, enum_type: type[StrEnum], token: str, mode: str
) -> None:
    graph = origin_graph()
    bad = unchecked_model(graph.relations[0], {field: fabricated_enum(enum_type, token)}, mode)
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        resolve_origin(graph.model_copy(update={"relations": (bad, *graph.relations[1:])}))


@pytest.mark.parametrize(
    "field,enum_type,token",
    [
        ("traversal", TraversalMode, "ORIGIN_PATH"),
        ("relation_type", FoodRelationType, "DERIVED_FROM"),
    ],
)
def test_origin_query_counterfeit_enums_remain_invalid(
    field: str, enum_type: type[StrEnum], token: str
) -> None:
    changes: dict[str, Any] = {field: fabricated_enum(enum_type, token)}
    with pytest.raises(ValidationError, match="canonical declared enum member"):
        resolve_origin(**changes)


@pytest.mark.parametrize("location", ["snapshot", "entity", "relation", "evidence"])
def test_origin_boundary_preserves_unexpected_field_detection(location: str) -> None:
    graph = origin_graph()
    if location == "snapshot":
        graph = graph.model_copy(update={"unexpected": True})
    elif location == "entity":
        graph = graph.model_copy(
            update={
                "entities": (
                    graph.entities[0].model_copy(update={"unexpected": True}),
                    *graph.entities[1:],
                )
            }
        )
    else:
        edge = graph.relations[0]
        if location == "relation":
            edge = edge.model_copy(update={"unexpected": True})
        else:
            edge = edge.model_copy(
                update={"evidence": (edge.evidence[0].model_copy(update={"unexpected": True}),)}
            )
        graph = graph.model_copy(update={"relations": (edge, *graph.relations[1:])})
    with pytest.raises(ValidationError, match="Extra inputs"):
        resolve_origin(graph)


def test_origin_path_evidence_is_deduplicated_versioned_and_stably_ordered() -> None:
    first = evidence(evidence_id="synthetic-path-source", version="fixture-v1")
    second = evidence(
        evidence_id="synthetic-path-source", version="fixture-v2", source="Revised SYNTHETIC source"
    )
    graphs = [
        origin_graph(
            (
                origin_edge("r100", "f009", "f002", version="edge-v2", evidence=refs),
                origin_edge("r200", "f002", "f001", version="edge-v3", evidence=(first,)),
            )
        )
        for refs in ((first, second), (second, first))
    ]
    results = [resolve_origin(graph) for graph in graphs]
    assert results[0].model_dump_json(by_alias=True) == results[1].model_dump_json(by_alias=True)
    assert results[0].evidence == (first, second)
    assert tuple(edge.version for edge in results[0].path) == ("edge-v2", "edge-v3")
    assert (
        RelationResolution.model_validate_json(results[0].model_dump_json(by_alias=True))
        == results[0]
    )


def test_origin_does_not_mutate_snapshot_and_keeps_path_models_frozen() -> None:
    graph = origin_graph()
    before = graph.model_dump_json(by_alias=True)
    result = resolve_origin(graph)
    assert graph.model_dump_json(by_alias=True) == before
    assert isinstance(result.path, tuple)
    with pytest.raises(ValidationError, match="frozen_instance"):
        result.path[0].assertion = RelationAssertion.ABSENT
    with pytest.raises(ValidationError, match="frozen_instance"):
        result.limit_reached = True


@pytest.mark.parametrize(
    "fault",
    [
        "negative",
        "mixed",
        "disconnected",
        "wrong_target",
        "missing_evidence",
        "verified_absent",
        "direct_relation",
        "limit_flag",
        "repeated_entity",
    ],
)
def test_origin_resolution_rejects_false_witness_and_absence_claims(fault: str) -> None:
    result = resolve_origin()
    path = result.path
    changes: dict[str, Any] = {}
    if fault == "negative":
        changes["path"] = (
            path[0].model_copy(update={"assertion": RelationAssertion.ABSENT}),
            *path[1:],
        )
    elif fault == "mixed":
        changes["path"] = (
            path[0].model_copy(update={"relation_type": FoodRelationType.CONTAINS}),
            *path[1:],
        )
    elif fault == "disconnected":
        changes["path"] = tuple(reversed(path))
    elif fault == "wrong_target":
        changes["target_id"] = "f010"
    elif fault == "missing_evidence":
        changes["evidence"] = (result.evidence[0],)
    elif fault == "verified_absent":
        changes["status"] = RelationResolutionStatus.VERIFIED_ABSENT
    elif fault == "direct_relation":
        changes["relation"] = origin_edge("r999", "f009", "f001")
    elif fault == "limit_flag":
        changes["limit_reached"] = True
    else:
        changes["path"] = (path[0], origin_edge("r999", "f006", "f009"))
    with pytest.raises(ValidationError):
        RelationResolution.model_validate(result.model_dump() | changes)


def test_origin_unknown_reason_and_limit_flag_must_agree() -> None:
    result = resolve_origin(max_hops=1)
    with pytest.raises(ValidationError, match="limit flag contradicts"):
        RelationResolution.model_validate(result.model_dump() | {"limit_reached": False})
    with pytest.raises(ValidationError):
        RelationResolution.model_validate(
            result.model_dump() | {"status": RelationResolutionStatus.SUPPORTED}
        )


def test_unknown_origin_resolution_rejects_a_positive_witness() -> None:
    unknown = resolve_origin(max_hops=1)
    supported = resolve_origin()
    with pytest.raises(ValidationError, match="unknown origin resolutions cannot carry a witness"):
        RelationResolution.model_validate(unknown.model_dump() | {"path": supported.path})


def test_unknown_origin_resolution_rejects_a_direct_reason_code() -> None:
    unknown = resolve_origin(max_hops=1)
    with pytest.raises(ValidationError, match="unknown origin resolutions require"):
        RelationResolution.model_validate(
            unknown.model_dump() | {"reason_code": "DIRECT_SUPPORTED"}
        )


def test_direct_results_preserve_exact_assertions_and_ignore_valid_search_budgets() -> None:
    graph = origin_graph((origin_edge("r100", "f009", "f001"),))
    result = resolve(graph, source_id="f009", max_hops=1, max_visited=1)
    assert result.status is RelationResolutionStatus.SUPPORTED
    assert result.reason_code == "DIRECT_SUPPORTED" and not result.path and not result.limit_reached
    with pytest.raises(ValidationError):
        RelationResolution.model_validate(
            result.model_dump() | {"path": result.relation and (result.relation,)}
        )


def test_bfs_matches_independent_path_enumeration_for_forward_edge_subsets() -> None:
    nodes = ("f009", "f006", "f002", "f001")
    possible = tuple(
        origin_edge(f"r{9 - i}{9 - j}", source, target)
        for i, source in enumerate(nodes)
        for j, target in enumerate(nodes)
        if i < j
    )
    for mask in range(1 << len(possible)):
        edges = tuple(edge for bit, edge in enumerate(possible) if mask & (1 << bit))
        graph = origin_graph(tuple(reversed(edges)))
        for source in nodes:
            # Enumerate all positive paths independently; do not reuse BFS/visited logic.
            paths: dict[str, list[tuple[str, ...]]] = {}
            pending: list[tuple[str, tuple[str, ...]]] = [(source, ())]
            while pending:
                endpoint, prefix = pending.pop()
                for edge in edges:
                    if edge.source_id == endpoint:
                        path = (*prefix, edge.relation_id)
                        paths.setdefault(edge.target_id, []).append(path)
                        pending.append((edge.target_id, path))
            for target in nodes:
                for max_hops in (1, 2, 3):
                    eligible = [path for path in paths.get(target, ()) if len(path) <= max_hops]
                    result = resolve_origin(
                        graph, source_id=source, target_id=target, max_hops=max_hops, max_visited=4
                    )
                    if eligible:
                        expected = min(eligible, key=lambda path: (len(path), path))
                        assert result.status is RelationResolutionStatus.SUPPORTED
                        assert tuple(edge.relation_id for edge in result.path) == expected
                        assert not result.limit_reached
                    else:
                        assert result.status is RelationResolutionStatus.UNKNOWN
                        blocked = source != target and any(
                            min(map(len, witnesses)) > max_hops for witnesses in paths.values()
                        )
                        assert result.limit_reached is blocked
                        assert result.reason_code == (
                            "MAX_HOPS_REACHED" if blocked else "NO_ORIGIN_PATH"
                        )
