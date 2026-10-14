"""Synthetic taxonomy declarations and conservative classification; no safety authority."""

from enum import StrEnum
from itertools import permutations, product
from typing import Any

import pytest
from pydantic import ValidationError

from savora_ai.core.reasoning.graph import resolve_food_relations
from savora_ai.core.reasoning.taxonomy import resolve_taxonomy_assignment
from savora_ai.schemas.food_graph import (
    FoodEntity,
    FoodEntityKind,
    FoodGraphSnapshot,
    FoodRelation,
    FoodRelationType,
    KnowledgeCoverage,
    RelationAssertion,
    RelationResolutionStatus,
    TaxonomyAssignment,
    TaxonomyAssignmentAssertion,
    TaxonomyKind,
    TaxonomyResolution,
    TaxonomyTerm,
    TaxonomyTraversalMode,
)
from savora_ai.schemas.knowledge import EvidenceReference, RuleEnvironment
from savora_ai.schemas.reasoning import _validation_payload


def evidence(id_: str = "synthetic:shared", **changes: Any) -> EvidenceReference:
    return EvidenceReference.model_validate(
        {
            "evidence_id": id_,
            "version": "source-v1",
            "source": "SYNTHETIC taxonomy fixture; no dietary or clinical authority",
            "locator": f"urn:savora:synthetic:{id_}",
            "environment": RuleEnvironment.SYNTHETIC,
        }
        | changes
    )


def term(id_: str = "indian", **changes: Any) -> TaxonomyTerm:
    return TaxonomyTerm.model_validate(
        {
            "term_id": id_,
            "version": "term-v1",
            "kind": TaxonomyKind.CUISINE,
            "display_label": "Synthetic " + id_,
            "parent_ids": (),
            "evidence": (evidence("term:" + id_), evidence()),
        }
        | changes
    )


def assignment(id_: str = "a-recipe", **changes: Any) -> TaxonomyAssignment:
    return TaxonomyAssignment.model_validate(
        {
            "assignment_id": id_,
            "version": "assignment-v1",
            "subject_id": "recipe",
            "term_id": "south-indian",
            "assertion": TaxonomyAssignmentAssertion.PRESENT,
            "evidence": (evidence("assignment:" + id_), evidence()),
        }
        | changes
    )


def graph(**changes: Any) -> FoodGraphSnapshot:
    entities = tuple(
        FoodEntity(
            entity_id=id_,
            version="entity-v1",
            kind=kind,
            canonical_name=label,
            catalogue_reference=reference,
            evidence=(evidence(),),
        )
        for id_, kind, label, reference in (
            (
                "recipe",
                FoodEntityKind.RECIPE_REFERENCE,
                "Synthetic South Indian recipe",
                "m1-recipe",
            ),
            ("rice", FoodEntityKind.INGREDIENT, "Synthetic rice", None),
            ("chicken", FoodEntityKind.INGREDIENT, "Synthetic chicken", None),
        )
    )
    return FoodGraphSnapshot.model_validate(
        {
            "graph_id": "synthetic-taxonomy-graph",
            "version": "graph-v1",
            "catalogue_version": "catalogue-v1",
            "environment": RuleEnvironment.SYNTHETIC,
            "entities": entities,
            "relations": (),
            "evidence": (evidence(),),
            "taxonomy_version": "taxonomy-v1",
            "taxonomy_terms": (
                term(display_label="Indian"),
                term("south-indian", display_label="South Indian", parent_ids=("indian",)),
                term("north-indian", display_label="North Indian", parent_ids=("indian",)),
                term(
                    "plant-derived",
                    kind=TaxonomyKind.DIETARY_CATEGORY,
                    display_label="Plant-derived",
                ),
                term(
                    "animal-flesh", kind=TaxonomyKind.DIETARY_CATEGORY, display_label="Animal-flesh"
                ),
                term("vegetarian", kind=TaxonomyKind.DIETARY_PATTERN, display_label="Vegetarian"),
                term("vegan", kind=TaxonomyKind.DIETARY_PATTERN, display_label="Vegan"),
                term("main", kind=TaxonomyKind.CULINARY_ROLE, display_label="Main dish"),
                term("side", kind=TaxonomyKind.CULINARY_ROLE, display_label="Side dish"),
            ),
            "taxonomy_assignments": (
                assignment(),
                assignment("a-rice", subject_id="rice", term_id="plant-derived"),
                assignment("a-chicken", subject_id="chicken", term_id="animal-flesh"),
            ),
        }
        | changes
    )


def resolve(snapshot: FoodGraphSnapshot | None = None, **changes: Any) -> TaxonomyResolution:
    parameters: dict[str, Any] = {"subject_id": "recipe", "term_id": "south-indian"} | changes
    return resolve_taxonomy_assignment(
        graph() if snapshot is None else snapshot,
        **parameters,
    )


def parents(snapshot: FoodGraphSnapshot | None = None, **changes: Any) -> TaxonomyResolution:
    return resolve(
        snapshot,
        **{"term_id": "indian", "traversal": TaxonomyTraversalMode.CUISINE_PARENTS} | changes,
    )


def counterfeit(cls: type[StrEnum], token: str) -> StrEnum:
    value = str.__new__(cls, token)
    value._name_ = token
    value._value_ = token
    return value


def unchecked(record: Any, changes: dict[str, Any], mode: str) -> Any:
    if mode == "copy":
        return record.model_copy(update=changes)
    return type(record).model_construct(**(vars(record) | changes))


@pytest.mark.parametrize("kind", list(TaxonomyKind))
@pytest.mark.parametrize("assertion", list(TaxonomyAssignmentAssertion))
def test_exact_assignments_for_each_kind_and_assertion(
    kind: TaxonomyKind, assertion: TaxonomyAssignmentAssertion
) -> None:
    snapshot = graph(
        taxonomy_terms=(term(kind=kind),),
        taxonomy_assignments=(assignment(term_id="indian", assertion=assertion),),
    )
    result = resolve(snapshot, term_id="indian")
    expected = (
        RelationResolutionStatus.SUPPORTED
        if assertion is TaxonomyAssignmentAssertion.PRESENT
        else RelationResolutionStatus.VERIFIED_ABSENT
    )
    assert result.status is expected
    assert result.assignment == snapshot.taxonomy_assignments[0]
    assert result.evidence == tuple(
        sorted(
            snapshot.taxonomy_assignments[0].evidence,
            key=lambda ref: (ref.evidence_id, ref.version),
        )
    )
    assert not result.path and not result.conflicts and not result.limit_reached
    assert result.taxonomy_version == "taxonomy-v1"
    assert (result.graph_version, result.catalogue_version) == ("graph-v1", "catalogue-v1")


@pytest.mark.parametrize(
    "subject_id,term_id",
    [("recipe", "south-indian"), ("rice", "plant-derived"), ("chicken", "animal-flesh")],
)
def test_requested_synthetic_classifications(subject_id: str, term_id: str) -> None:
    assert (
        resolve(subject_id=subject_id, term_id=term_id).status is RelationResolutionStatus.SUPPORTED
    )


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"subject_id": "missing"}, "MISSING_SUBJECT"),
        ({"term_id": "missing"}, "MISSING_TERM"),
        ({"subject_id": "Synthetic"}, "MISSING_SUBJECT"),
        ({"term_id": "Indian"}, "MISSING_TERM"),
        ({"term_id": "indian"}, "NO_ASSIGNMENT"),
        ({"term_id": "vegan"}, "NO_ASSIGNMENT"),
        ({"subject_id": "rice", "term_id": "vegetarian"}, "NO_ASSIGNMENT"),
    ],
)
def test_missing_records_and_labels_never_manufacture_classifications(
    changes: dict[str, Any], code: str
) -> None:
    result = resolve(**changes)
    assert result.status is RelationResolutionStatus.UNKNOWN
    assert result.reason_code == code and not result.path and result.assignment is None


@pytest.mark.parametrize("field", ["term_id", "version", "kind", "display_label", "evidence"])
def test_term_required_fields(field: str) -> None:
    data = term().model_dump()
    del data[field]
    with pytest.raises(ValidationError):
        TaxonomyTerm.model_validate(data)


@pytest.mark.parametrize(
    "field", ["assignment_id", "version", "subject_id", "term_id", "assertion", "evidence"]
)
def test_assignment_required_fields(field: str) -> None:
    data = assignment().model_dump()
    del data[field]
    with pytest.raises(ValidationError):
        TaxonomyAssignment.model_validate(data)


@pytest.mark.parametrize("make", [term, assignment])
@pytest.mark.parametrize("bad", [(), (evidence(), evidence())])
def test_taxonomy_records_require_nonempty_unique_evidence(make: Any, bad: Any) -> None:
    with pytest.raises(ValidationError):
        make(evidence=bad)


@pytest.mark.parametrize(
    "changes",
    [
        {"term_id": ""},
        {"term_id": "a b"},
        {"version": " "},
        {"display_label": ""},
        {"display_label": "   "},
        {"kind": "CUISINE"},
        {"parent_ids": []},
        {"evidence": []},
        {"unexpected": True},
    ],
)
def test_term_strictness(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        term(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"assignment_id": "a b"},
        {"version": " "},
        {"subject_id": 1},
        {"term_id": True},
        {"assertion": "PRESENT"},
        {"evidence": []},
        {"unexpected": True},
    ],
)
def test_assignment_strictness(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        assignment(**changes)


@pytest.mark.parametrize("parents_", [("indian",), ("other", "other")])
def test_self_and_duplicate_parents_are_rejected(parents_: tuple[str, ...]) -> None:
    with pytest.raises(ValidationError):
        term(parent_ids=parents_)


@pytest.mark.parametrize("version", ["term-v1", "term-v2"])
def test_term_identity_is_unique_across_versions(version: str) -> None:
    with pytest.raises(ValidationError, match="duplicate taxonomy term"):
        graph(taxonomy_terms=(term(), term(version=version)), taxonomy_assignments=())


@pytest.mark.parametrize("version", ["assignment-v1", "assignment-v2"])
def test_assignment_identity_is_unique_across_versions(version: str) -> None:
    with pytest.raises(ValidationError, match="duplicate taxonomy assignment"):
        graph(taxonomy_assignments=(assignment(), assignment(version=version)))


@pytest.mark.parametrize("assertion", list(TaxonomyAssignmentAssertion))
def test_same_subject_term_cannot_have_duplicate_or_opposite_assignments(
    assertion: TaxonomyAssignmentAssertion,
) -> None:
    with pytest.raises(ValidationError, match=r"contradictory|duplicate subject/term"):
        graph(
            taxonomy_assignments=(
                assignment(),
                assignment("a-other", version="v2", assertion=assertion),
            )
        )


@pytest.mark.parametrize("bad", [None, ""])
def test_taxonomy_records_require_an_explicit_release(bad: Any) -> None:
    with pytest.raises(ValidationError):
        graph(taxonomy_version=bad)


@pytest.mark.parametrize("field", ["taxonomy_terms", "taxonomy_assignments"])
def test_snapshot_taxonomy_collections_are_strict_tuples(field: str) -> None:
    with pytest.raises(ValidationError):
        graph(**{field: []})


def test_old_graph_payloads_remain_valid_without_taxonomy() -> None:
    data = graph().model_dump()
    for field in ("taxonomy_terms", "taxonomy_assignments", "taxonomy_version"):
        del data[field]
    legacy = FoodGraphSnapshot.model_validate(data)
    assert legacy.taxonomy_terms == () and legacy.taxonomy_assignments == ()
    assert legacy.taxonomy_version is None
    assert resolve(legacy).status is RelationResolutionStatus.UNKNOWN


def test_dangling_parent_is_rejected() -> None:
    with pytest.raises(ValidationError, match="dangling taxonomy parent"):
        graph(taxonomy_terms=(term(parent_ids=("missing",)),), taxonomy_assignments=())


@pytest.mark.parametrize("field", ["subject_id", "term_id"])
def test_dangling_assignment_reference_is_rejected(field: str) -> None:
    with pytest.raises(ValidationError, match=r"existing food|dangling taxonomy assignment"):
        graph(taxonomy_assignments=(assignment(**{field: "missing"}),))


def test_taxonomy_assignment_and_query_require_food_subjects() -> None:
    reference = FoodEntity(
        entity_id="role-ref",
        version="v1",
        kind=FoodEntityKind.CULINARY_ROLE_REFERENCE,
        canonical_name="Synthetic role",
        catalogue_reference="role-catalogue",
        evidence=(evidence(),),
    )
    snapshot = graph(entities=(*graph().entities, reference))
    with pytest.raises(ValidationError, match="existing food"):
        graph(entities=snapshot.entities, taxonomy_assignments=(assignment(subject_id="role-ref"),))
    with pytest.raises(ValidationError, match="ingredient or recipe"):
        resolve(snapshot, subject_id="role-ref", term_id="missing")


def test_parent_kinds_cannot_mix() -> None:
    with pytest.raises(ValidationError, match="same kind"):
        graph(
            taxonomy_terms=(
                term(),
                term("child", kind=TaxonomyKind.DIETARY_PATTERN, parent_ids=("indian",)),
            ),
            taxonomy_assignments=(),
        )


@pytest.mark.parametrize("kind", list(TaxonomyKind))
def test_hierarchy_cycles_are_rejected_for_every_kind(kind: TaxonomyKind) -> None:
    with pytest.raises(ValidationError, match="hierarchy cycles"):
        graph(
            taxonomy_terms=(
                term("a", kind=kind, parent_ids=("b",)),
                term("b", kind=kind, parent_ids=("c",)),
                term("c", kind=kind, parent_ids=("a",)),
            ),
            taxonomy_assignments=(),
        )


def test_cuisine_membership_traverses_upward_with_exact_versions_and_evidence() -> None:
    result = parents()
    assert result.status is RelationResolutionStatus.SUPPORTED
    assert result.reason_code == "HIERARCHY_SUPPORTED"
    assert tuple(item.term_id for item in result.path) == ("south-indian", "indian")
    assert result.assignment is not None and result.assignment.term_id == "south-indian"
    selected = set(ref for item in result.path for ref in item.evidence) | set(
        result.assignment.evidence
    )
    assert selected == set(result.evidence)
    assert not result.limit_reached and not result.conflicts
    assert {ref.evidence_id for ref in result.evidence} == {
        "synthetic:shared",
        "term:indian",
        "term:south-indian",
        "assignment:a-recipe",
    }


def test_parent_assignment_never_implies_child_membership() -> None:
    snapshot = graph(taxonomy_assignments=(assignment(term_id="indian"),))
    result = parents(snapshot, term_id="south-indian")
    assert (
        result.status is RelationResolutionStatus.UNKNOWN
        and result.reason_code == "NO_CUISINE_PATH"
    )


@pytest.mark.parametrize(
    "kind",
    [TaxonomyKind.DIETARY_PATTERN, TaxonomyKind.DIETARY_CATEGORY, TaxonomyKind.CULINARY_ROLE],
)
@pytest.mark.parametrize("mode", list(TaxonomyTraversalMode))
def test_non_cuisine_parent_membership_is_never_inherited(
    kind: TaxonomyKind, mode: TaxonomyTraversalMode
) -> None:
    snapshot = graph(
        taxonomy_terms=(
            term("parent", kind=kind),
            term("child", kind=kind, parent_ids=("parent",)),
        ),
        taxonomy_assignments=(assignment(term_id="child"),),
    )
    result = resolve(snapshot, term_id="parent", traversal=mode)
    assert result.status is RelationResolutionStatus.UNKNOWN
    assert result.reason_code == (
        "NO_ASSIGNMENT" if mode is TaxonomyTraversalMode.DIRECT else "UNSUPPORTED_HIERARCHY"
    )


@pytest.mark.parametrize(
    "kind",
    [TaxonomyKind.DIETARY_PATTERN, TaxonomyKind.DIETARY_CATEGORY, TaxonomyKind.CULINARY_ROLE],
)
@pytest.mark.parametrize("assertion", list(TaxonomyAssignmentAssertion))
def test_parent_mode_still_honors_exact_non_cuisine_assignments(
    kind: TaxonomyKind, assertion: TaxonomyAssignmentAssertion
) -> None:
    snapshot = graph(
        taxonomy_terms=(term(kind=kind),),
        taxonomy_assignments=(assignment(term_id="indian", assertion=assertion),),
    )
    result = parents(snapshot)
    assert result.status is (
        RelationResolutionStatus.SUPPORTED
        if assertion is TaxonomyAssignmentAssertion.PRESENT
        else RelationResolutionStatus.VERIFIED_ABSENT
    )
    assert not result.path


@pytest.mark.parametrize(
    "relation_type", [FoodRelationType.CONTAINS, FoodRelationType.DERIVED_FROM]
)
def test_food_edges_do_not_propagate_taxonomy_assignments(relation_type: FoodRelationType) -> None:
    edge = FoodRelation(
        relation_id="r-food",
        version="v1",
        source_id="rice",
        target_id="chicken",
        relation_type=relation_type,
        assertion=RelationAssertion.PRESENT,
        evidence=(evidence(),),
    )
    snapshot = graph(relations=(edge,))
    result = resolve(snapshot, subject_id="rice", term_id="animal-flesh")
    assert result.status is RelationResolutionStatus.UNKNOWN


def test_negative_cuisine_assignment_does_not_propagate_to_parents() -> None:
    snapshot = graph(
        taxonomy_assignments=(assignment(assertion=TaxonomyAssignmentAssertion.ABSENT),)
    )
    assert parents(snapshot).status is RelationResolutionStatus.UNKNOWN
    assert resolve(snapshot).status is RelationResolutionStatus.VERIFIED_ABSENT


def test_exact_negative_and_hierarchy_positive_invalidate_snapshot() -> None:
    negative = assignment(
        "a-negative", term_id="indian", assertion=TaxonomyAssignmentAssertion.ABSENT
    )
    with pytest.raises(ValidationError, match="contradictory cuisine ancestry"):
        graph(taxonomy_assignments=(assignment(), negative))


def test_negative_intermediate_membership_invalidate_snapshot() -> None:
    negative = assignment(
        "a-negative", term_id="south-indian", assertion=TaxonomyAssignmentAssertion.ABSENT
    )
    with pytest.raises(ValidationError, match="contradictory cuisine ancestry"):
        graph(
            taxonomy_terms=(*graph().taxonomy_terms, term("local", parent_ids=("south-indian",))),
            taxonomy_assignments=(assignment(term_id="local"), negative),
        )


@pytest.mark.parametrize("negative_id", ["a", "b"])
def test_conflict_on_either_diamond_branch_invalidate_snapshot(negative_id: str) -> None:
    with pytest.raises(ValidationError, match="contradictory cuisine ancestry"):
        graph(
            taxonomy_terms=(
                term("target"),
                term("a", parent_ids=("target",)),
                term("b", parent_ids=("target",)),
                term("seed", parent_ids=("b", "a")),
            ),
            taxonomy_assignments=(
                assignment(term_id="seed"),
                assignment(
                    "negative", term_id=negative_id, assertion=TaxonomyAssignmentAssertion.ABSENT
                ),
            ),
        )


@pytest.mark.parametrize("mode", list(TaxonomyTraversalMode))
@pytest.mark.parametrize(
    "limits", [{"max_hops": 1}, {"max_visited": 1}, {"max_hops": 8, "max_visited": 256}]
)
def test_query_bounds_cannot_hide_a_contradictory_snapshot(
    mode: TaxonomyTraversalMode, limits: dict[str, Any]
) -> None:
    negative = assignment(
        "a-negative", term_id="indian", assertion=TaxonomyAssignmentAssertion.ABSENT
    )
    snapshot = graph(
        taxonomy_terms=(*graph().taxonomy_terms, term("local", parent_ids=("south-indian",))),
        taxonomy_assignments=(assignment(term_id="local"),),
    )
    malformed = snapshot.model_copy(
        update={"taxonomy_assignments": (*snapshot.taxonomy_assignments, negative)}
    )
    with pytest.raises(ValidationError, match="contradictory cuisine ancestry"):
        resolve(malformed, term_id="indian", traversal=mode, **limits)
    with pytest.raises(ValidationError, match="contradictory cuisine ancestry"):
        resolve(malformed, subject_id="missing", term_id="missing", traversal=mode, **limits)


def test_exact_negative_remains_verifiable_when_parent_search_is_exhausted() -> None:
    snapshot = graph(
        taxonomy_assignments=(
            assignment("neg", term_id="indian", assertion=TaxonomyAssignmentAssertion.ABSENT),
        )
    )
    result = parents(snapshot, max_hops=1, max_visited=1)
    assert result.status is RelationResolutionStatus.VERIFIED_ABSENT
    assert not result.path and not result.limit_reached


def test_exact_positive_does_not_require_parent_search_or_seed_budget() -> None:
    snapshot = graph(
        taxonomy_assignments=(*graph().taxonomy_assignments, assignment("exact", term_id="indian"))
    )
    result = parents(snapshot, max_hops=1, max_visited=1)
    assert (
        result.status is RelationResolutionStatus.SUPPORTED
        and result.reason_code == "DIRECT_SUPPORTED"
    )
    assert not result.path


def test_shortest_witness_beats_a_smaller_assignment_id_on_a_longer_path() -> None:
    snapshot = graph(
        taxonomy_terms=(*graph().taxonomy_terms, term("local", parent_ids=("south-indian",))),
        taxonomy_assignments=(
            assignment("a-first", term_id="local"),
            assignment("z-second", term_id="north-indian"),
        ),
    )
    result = parents(snapshot)
    assert result.assignment is not None and result.assignment.assignment_id == "z-second"
    assert tuple(item.term_id for item in result.path) == ("north-indian", "indian")


def test_equal_length_witness_uses_assignment_id_before_term_ids() -> None:
    snapshot = graph(
        taxonomy_assignments=(
            assignment("z", term_id="north-indian"),
            assignment("a", term_id="south-indian"),
        )
    )
    result = parents(snapshot)
    assert result.assignment is not None and result.assignment.assignment_id == "a"


def test_parent_id_sequence_is_globally_deterministic_across_all_input_orders() -> None:
    terms = (
        term("target"),
        term("a", parent_ids=("target",)),
        term("b", parent_ids=("target",)),
        term("seed", parent_ids=("b", "a")),
    )
    assigns = (assignment(term_id="seed"),)
    expected = parents(graph(taxonomy_terms=terms, taxonomy_assignments=assigns), term_id="target")
    assert tuple(item.term_id for item in expected.path) == ("seed", "a", "target")
    for ordering in permutations(terms):
        reordered = tuple(
            item.model_copy(
                update={
                    "parent_ids": tuple(reversed(item.parent_ids)),
                    "evidence": tuple(reversed(item.evidence)),
                }
            )
            for item in ordering
        )
        snapshot = graph(
            entities=tuple(reversed(graph().entities)),
            taxonomy_terms=reordered,
            taxonomy_assignments=(
                assigns[0].model_copy(update={"evidence": tuple(reversed(assigns[0].evidence))}),
            ),
        )
        assert parents(snapshot, term_id="target").model_dump_json() == expected.model_dump_json()


@pytest.mark.parametrize("max_hops", [1, 2, 3])
def test_hop_limit_is_inclusive(max_hops: int) -> None:
    snapshot = graph(
        taxonomy_terms=(*graph().taxonomy_terms, term("local", parent_ids=("south-indian",))),
        taxonomy_assignments=(assignment(term_id="local"),),
    )
    result = parents(snapshot, max_hops=max_hops)
    assert result.status is (
        RelationResolutionStatus.UNKNOWN if max_hops < 2 else RelationResolutionStatus.SUPPORTED
    )
    assert result.limit_reached is (max_hops < 2)


@pytest.mark.parametrize("max_visited", [1, 2, 3, 4])
def test_visited_budget_counts_seed_terms_and_target(max_visited: int) -> None:
    snapshot = graph(
        taxonomy_terms=(*graph().taxonomy_terms, term("local", parent_ids=("south-indian",))),
        taxonomy_assignments=(assignment(term_id="local"),),
    )
    result = parents(snapshot, max_visited=max_visited)
    assert result.status is (
        RelationResolutionStatus.UNKNOWN if max_visited < 3 else RelationResolutionStatus.SUPPORTED
    )
    assert result.limit_reached is (max_visited < 3)


def test_all_positive_seed_terms_spend_the_shared_budget() -> None:
    snapshot = graph(
        taxonomy_assignments=(
            assignment("a", term_id="south-indian"),
            assignment("b", term_id="north-indian"),
        )
    )
    assert parents(snapshot, max_visited=1).reason_code == "MAX_VISITED_REACHED"
    assert parents(snapshot, max_visited=2).reason_code == "MAX_VISITED_REACHED"
    assert parents(snapshot, max_visited=3).status is RelationResolutionStatus.SUPPORTED


def test_visited_and_hop_values_equal_to_bounds_do_not_alone_set_limit_flag() -> None:
    snapshot = graph(taxonomy_assignments=(assignment(term_id="indian"),))
    result = parents(snapshot, term_id="north-indian", max_hops=1, max_visited=1)
    assert result.reason_code == "NO_CUISINE_PATH" and not result.limit_reached
    snapshot = graph(
        taxonomy_terms=(*graph().taxonomy_terms, term("unrelated")),
        taxonomy_assignments=(assignment(),),
    )
    result = parents(snapshot, term_id="unrelated", max_hops=1, max_visited=2)
    assert result.reason_code == "NO_CUISINE_PATH" and not result.limit_reached


def test_converging_paths_do_not_double_count_terms() -> None:
    snapshot = graph(
        taxonomy_terms=(
            term("target"),
            term("join", parent_ids=("target",)),
            term("a", parent_ids=("join",)),
            term("b", parent_ids=("join",)),
            term("seed", parent_ids=("a", "b")),
        ),
        taxonomy_assignments=(assignment(term_id="seed"),),
    )
    assert (
        parents(snapshot, term_id="target", max_visited=5).status
        is RelationResolutionStatus.SUPPORTED
    )
    assert parents(snapshot, term_id="target", max_visited=4).reason_code == "MAX_VISITED_REACHED"


@pytest.mark.parametrize("mode", list(TaxonomyTraversalMode))
@pytest.mark.parametrize("field", ["max_hops", "max_visited"])
@pytest.mark.parametrize("invalid", [0, -1, True, False, 1.0, "1", None, [], float("inf")])
def test_invalid_limits_are_rejected_before_missing_subject_fallback(
    mode: TaxonomyTraversalMode, field: str, invalid: Any
) -> None:
    with pytest.raises(ValidationError):
        resolve(subject_id="missing", traversal=mode, **{field: invalid})


@pytest.mark.parametrize("location", ["term", "assignment"])
@pytest.mark.parametrize("field", ["source", "locator", "environment"])
def test_evidence_identity_conflicts_are_global(location: str, field: str) -> None:
    changed = RuleEnvironment.PRODUCTION if field == "environment" else "conflicting metadata"
    ref = evidence(**{field: changed})
    updates = (
        {"taxonomy_terms": (term(evidence=(ref,)), *graph().taxonomy_terms[1:])}
        if location == "term"
        else {"taxonomy_assignments": (assignment(evidence=(ref,)),)}
    )
    with pytest.raises(ValidationError, match=r"conflicting evidence|environment"):
        graph(**updates)


def test_taxonomy_evidence_conflicts_with_coverage_are_rejected() -> None:
    record = KnowledgeCoverage(
        coverage_id="cov",
        version="v1",
        graph_id=graph().graph_id,
        graph_version=graph().version,
        catalogue_version=graph().catalogue_version,
        subject_id="rice",
        relation_type=FoodRelationType.DERIVED_FROM,
        complete=False,
        reason="SYNTHETIC gap",
        evidence=(evidence("term:indian", locator="urn:conflict"),),
    )
    with pytest.raises(ValidationError, match="conflicting evidence"):
        graph(coverage=(record,))


def test_revised_evidence_versions_remain_distinct_and_deterministically_selected() -> None:
    revised = evidence(
        "term:indian", version="source-v2", locator="urn:revised", source="SYNTHETIC revision"
    )
    snapshot = graph(
        taxonomy_terms=(term(evidence=(revised, *term().evidence)), *graph().taxonomy_terms[1:])
    )
    result = parents(snapshot)
    assert {(ref.evidence_id, ref.version) for ref in result.evidence} >= {
        ("term:indian", "source-v1"),
        ("term:indian", "source-v2"),
    }


def test_production_and_mixed_environments_cannot_enable_public_resolution() -> None:
    with pytest.raises(ValidationError):
        graph(environment=RuleEnvironment.PRODUCTION)
    labelled = FoodGraphSnapshot.model_validate_json(
        graph().model_dump_json().replace('"SYNTHETIC"', '"PRODUCTION"')
    )
    with pytest.raises(ValidationError, match="SYNTHETIC snapshots only"):
        parents(labelled)


@pytest.mark.parametrize("mode", ["copy", "construct"])
@pytest.mark.parametrize(
    "fault",
    [
        "cycle",
        "dangling_parent",
        "mixed_kind",
        "dangling_subject",
        "dangling_term",
        "empty_evidence",
        "contradiction",
        "duplicate_binding",
        "missing_release",
    ],
)
def test_public_resolver_revalidates_all_unchecked_taxonomy_faults(mode: str, fault: str) -> None:
    snapshot = graph()
    if fault in ("cycle", "dangling_parent", "mixed_kind", "empty_evidence"):
        changes = {
            "cycle": {"parent_ids": ("south-indian",)},
            "dangling_parent": {"parent_ids": ("missing",)},
            "mixed_kind": {"kind": TaxonomyKind.DIETARY_PATTERN},
            "empty_evidence": {"evidence": ()},
        }[fault]
        updates = {
            "taxonomy_terms": (
                unchecked(snapshot.taxonomy_terms[0], changes, mode),
                *snapshot.taxonomy_terms[1:],
            )
        }
    elif fault in ("dangling_subject", "dangling_term"):
        updates = {
            "taxonomy_assignments": (
                unchecked(
                    assignment(),
                    {"subject_id" if fault == "dangling_subject" else "term_id": "missing"},
                    mode,
                ),
            )
        }
    elif fault == "contradiction":
        updates = {
            "taxonomy_assignments": (
                assignment(),
                assignment("negative", assertion=TaxonomyAssignmentAssertion.ABSENT),
            )
        }
    elif fault == "duplicate_binding":
        updates = {
            "entities": (
                *snapshot.entities,
                snapshot.entities[0].model_copy(update={"entity_id": "recipe-alias"}),
            )
        }
    else:
        updates = {"taxonomy_version": None}
    malformed = unchecked(snapshot, updates, mode)
    with pytest.raises(ValidationError):
        parents(malformed)
    # Existing relation resolver also checks the new nested records, even for missing caller IDs.
    with pytest.raises(ValidationError):
        resolve_food_relations(
            malformed,
            source_id="missing",
            target_id="rice",
            relation_type=FoodRelationType.DERIVED_FROM,
        )


@pytest.mark.parametrize("mode", ["copy", "construct"])
@pytest.mark.parametrize(
    "location", ["kind", "assertion", "evidence_environment", "snapshot_environment"]
)
@pytest.mark.parametrize("valid_token", [True, False])
def test_counterfeit_nested_enums_never_reach_classification(
    mode: str, location: str, valid_token: bool
) -> None:
    snapshot = graph()
    if location == "kind":
        value = counterfeit(TaxonomyKind, "CUISINE" if valid_token else "UNDECLARED")
        updates = {
            "taxonomy_terms": (
                unchecked(snapshot.taxonomy_terms[0], {"kind": value}, mode),
                *snapshot.taxonomy_terms[1:],
            )
        }
    elif location == "assertion":
        value = counterfeit(TaxonomyAssignmentAssertion, "PRESENT" if valid_token else "UNDECLARED")
        updates = {"taxonomy_assignments": (unchecked(assignment(), {"assertion": value}, mode),)}
    else:
        value = counterfeit(RuleEnvironment, "SYNTHETIC" if valid_token else "UNDECLARED")
        updates = (
            {"environment": value}
            if location == "snapshot_environment"
            else {"evidence": (unchecked(evidence(), {"environment": value}, mode),)}
        )
    with pytest.raises(ValidationError, match="canonical declared enum"):
        parents(unchecked(snapshot, updates, mode))


@pytest.mark.parametrize("token", ["DIRECT", "CUISINE_PARENTS", "UNDECLARED"])
def test_counterfeit_query_traversal_is_rejected(token: str) -> None:
    with pytest.raises(ValidationError, match="canonical declared enum"):
        resolve(traversal=counterfeit(TaxonomyTraversalMode, token))


@pytest.mark.parametrize("location", ["snapshot", "term", "assignment", "evidence"])
def test_unexpected_unchecked_fields_are_not_silently_dropped(location: str) -> None:
    snapshot = graph()
    if location == "snapshot":
        malformed = snapshot.model_copy(update={"unexpected": True})
    elif location == "term":
        malformed = snapshot.model_copy(
            update={
                "taxonomy_terms": (
                    term().model_copy(update={"unexpected": True}),
                    *snapshot.taxonomy_terms[1:],
                )
            }
        )
    elif location == "assignment":
        malformed = snapshot.model_copy(
            update={"taxonomy_assignments": (assignment().model_copy(update={"unexpected": True}),)}
        )
    else:
        malformed = snapshot.model_copy(
            update={"evidence": (evidence().model_copy(update={"unexpected": True}),)}
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        parents(malformed)


def test_cyclic_payload_is_a_validation_error() -> None:
    recursive: dict[str, Any] = {}
    recursive["taxonomy_terms"] = recursive
    with pytest.raises(ValidationError, match="cyclic or excessively deep"):
        parents(graph().model_copy(update={"taxonomy_terms": recursive}))


def test_missing_fields_in_constructed_terms_are_revalidated() -> None:
    data = vars(term()).copy()
    del data["kind"]
    malformed = TaxonomyTerm.model_construct(**data)
    with pytest.raises(ValidationError):
        parents(
            graph().model_copy(update={"taxonomy_terms": (malformed, *graph().taxonomy_terms[1:])})
        )


def test_terms_labels_and_graph_ids_have_distinct_identity_namespaces() -> None:
    snapshot = graph(
        taxonomy_terms=(
            term("rice", display_label="Same label"),
            term("other", display_label="Same label"),
        ),
        taxonomy_assignments=(assignment(subject_id="rice", term_id="rice"),),
    )
    assert (
        resolve(snapshot, subject_id="rice", term_id="rice").status
        is RelationResolutionStatus.SUPPORTED
    )
    assert (
        resolve(snapshot, subject_id="rice", term_id="other").status
        is RelationResolutionStatus.UNKNOWN
    )


def test_nested_models_and_witnesses_are_immutable_and_inputs_unchanged() -> None:
    snapshot = graph()
    before = snapshot.model_dump_json()
    result = parents(snapshot)
    assert snapshot.model_dump_json() == before
    for record, field, value in (
        (snapshot, "taxonomy_version", "other"),
        (snapshot.taxonomy_terms[0], "display_label", "Changed"),
        (snapshot.taxonomy_assignments[0], "assertion", TaxonomyAssignmentAssertion.ABSENT),
        (result, "limit_reached", True),
        (result.path[0], "parent_ids", ()),
    ):
        with pytest.raises(ValidationError, match="frozen_instance"):
            setattr(record, field, value)
    assert isinstance(snapshot.taxonomy_terms, tuple) and isinstance(result.path, tuple)


def test_snapshot_and_resolution_json_round_trips_preserve_canonical_members() -> None:
    snapshot = graph()
    restored = FoodGraphSnapshot.model_validate_json(snapshot.model_dump_json(by_alias=True))
    assert restored == snapshot
    assert restored.taxonomy_terms[0].kind is TaxonomyKind.CUISINE
    assert restored.taxonomy_assignments[0].assertion is TaxonomyAssignmentAssertion.PRESENT
    negative = assignment(
        "negative", term_id="north-indian", assertion=TaxonomyAssignmentAssertion.ABSENT
    )
    for result in (
        resolve(),
        parents(),
        parents(graph(taxonomy_assignments=(assignment(), negative)), term_id="north-indian"),
        resolve(term_id="missing"),
    ):
        assert (
            TaxonomyResolution.model_validate_json(result.model_dump_json(by_alias=True)) == result
        )


@pytest.mark.parametrize(
    "fault",
    [
        "negative_seed",
        "mixed_kind",
        "reverse_path",
        "wrong_target",
        "missing_evidence",
        "fabricated_evidence",
        "repeated_term",
        "unsupported_mode",
        "false_absence",
        "false_limit",
        "false_reason",
        "conflict_on_supported",
    ],
)
def test_result_validation_rejects_false_hierarchy_witnesses(fault: str) -> None:
    result = parents()
    assert result.assignment is not None
    changes: dict[str, Any]
    if fault == "negative_seed":
        changes = {
            "assignment": result.assignment.model_copy(
                update={"assertion": TaxonomyAssignmentAssertion.ABSENT}
            )
        }
    elif fault == "mixed_kind":
        changes = {
            "path": (
                result.path[0].model_copy(update={"kind": TaxonomyKind.DIETARY_CATEGORY}),
                result.path[1],
            )
        }
    elif fault == "reverse_path":
        changes = {"path": tuple(reversed(result.path))}
    elif fault == "wrong_target":
        changes = {"term_id": "north-indian"}
    elif fault == "missing_evidence":
        changes = {"evidence": (evidence(),)}
    elif fault == "fabricated_evidence":
        changes = {"evidence": (*result.evidence, evidence("fabricated"))}
    elif fault == "repeated_term":
        changes = {"path": (*result.path, result.path[-1])}
    elif fault == "unsupported_mode":
        changes = {"traversal": TaxonomyTraversalMode.DIRECT}
    elif fault == "false_absence":
        changes = {"status": RelationResolutionStatus.VERIFIED_ABSENT}
    elif fault == "false_limit":
        changes = {"limit_reached": True}
    elif fault == "false_reason":
        changes = {"reason_code": "DIRECT_SUPPORTED"}
    else:
        changes = {
            "conflicts": (
                assignment("neg", term_id="indian", assertion=TaxonomyAssignmentAssertion.ABSENT),
            )
        }
    with pytest.raises(ValidationError):
        TaxonomyResolution.model_validate(_validation_payload(result.model_copy(update=changes)))


@pytest.mark.parametrize("fault", ["witness", "direct_reason", "flag", "positive_status"])
def test_unknown_result_metadata_cannot_manufacture_membership(fault: str) -> None:
    result = parents(graph(taxonomy_assignments=()))
    changes = {
        "witness": {"path": parents().path},
        "direct_reason": {"reason_code": "DIRECT_SUPPORTED"},
        "flag": {"limit_reached": True},
        "positive_status": {"status": RelationResolutionStatus.SUPPORTED},
    }[fault]
    with pytest.raises(ValidationError):
        TaxonomyResolution.model_validate(_validation_payload(result.model_copy(update=changes)))


@pytest.mark.parametrize("field", ["status", "traversal", "environment"])
def test_result_enum_fields_reject_counterfeit_canonical_tokens(field: str) -> None:
    result = parents()
    genuine = getattr(result, field)
    with pytest.raises(ValidationError, match="canonical declared enum"):
        TaxonomyResolution.model_validate(
            _validation_payload(
                result.model_copy(update={field: counterfeit(type(genuine), genuine.value)})
            )
        )


def test_conflict_result_cannot_be_relabelled_as_supported_or_absent() -> None:
    negative = assignment("neg", term_id="indian", assertion=TaxonomyAssignmentAssertion.ABSENT)
    supported = parents()
    # Preserve validation of legacy standalone conflict diagnostics. The resolver now
    # rejects such a snapshot before producing a classification result.
    result = TaxonomyResolution.model_validate(
        supported.model_dump()
        | {
            "status": RelationResolutionStatus.UNKNOWN,
            "reason_code": "HIERARCHY_CONFLICT",
            "conflicts": (negative,),
            "evidence": tuple(
                sorted(
                    set(supported.evidence) | set(negative.evidence),
                    key=lambda ref: (ref.evidence_id, ref.version),
                )
            ),
        }
    )
    assert TaxonomyResolution.model_validate_json(result.model_dump_json()) == result
    for status in (RelationResolutionStatus.SUPPORTED, RelationResolutionStatus.VERIFIED_ABSENT):
        with pytest.raises(ValidationError):
            TaxonomyResolution.model_validate(result.model_dump() | {"status": status})


def test_longer_conflicting_alternative_invalidate_snapshot() -> None:
    with pytest.raises(ValidationError, match="contradictory cuisine ancestry"):
        graph(
            taxonomy_terms=(
                term("target"),
                term("a", parent_ids=("target",)),
                term("b", parent_ids=("c",)),
                term("c", parent_ids=("target",)),
                term("seed", parent_ids=("a", "b")),
            ),
            taxonomy_assignments=(
                assignment(term_id="seed"),
                assignment("negative", term_id="b", assertion=TaxonomyAssignmentAssertion.ABSENT),
            ),
        )


@pytest.mark.parametrize(
    "positive_ids", [("a-positive", "z-positive"), ("z-positive", "a-positive")]
)
def test_another_positive_seed_cannot_hide_ancestry_conflict(
    positive_ids: tuple[str, str],
) -> None:
    with pytest.raises(ValidationError, match="contradictory cuisine ancestry"):
        graph(
            taxonomy_terms=(
                term("target"),
                term("clean", parent_ids=("target",)),
                term("other", parent_ids=("b",)),
                term("b", parent_ids=("target",)),
            ),
            taxonomy_assignments=(
                assignment(positive_ids[0], term_id="clean"),
                assignment(positive_ids[1], term_id="other"),
                assignment("negative", term_id="b", assertion=TaxonomyAssignmentAssertion.ABSENT),
            ),
        )


@pytest.mark.parametrize(
    "clean_id,conflicting_id",
    [
        ("a-clean", "z-conflicting"),
        ("z-clean", "a-conflicting"),
    ],
)
def test_opaque_id_renaming_cannot_change_conflict_acceptance(
    clean_id: str,
    conflicting_id: str,
) -> None:
    with pytest.raises(ValidationError, match="contradictory cuisine ancestry"):
        graph(
            taxonomy_terms=(
                term("target", display_label="Ancestor"),
                term(clean_id, display_label="Clean branch", parent_ids=("target",)),
                term(conflicting_id, display_label="Conflicting branch", parent_ids=("target",)),
                term(
                    "seed", display_label="Assigned cuisine", parent_ids=(clean_id, conflicting_id)
                ),
            ),
            taxonomy_assignments=(
                assignment(term_id="seed"),
                assignment(
                    "negative", term_id=conflicting_id, assertion=TaxonomyAssignmentAssertion.ABSENT
                ),
            ),
        )


def test_conflict_rejection_is_deterministic_across_all_record_orders() -> None:
    terms = (
        term("target"),
        term("a", parent_ids=("target",)),
        term("b", parent_ids=("target",)),
        term("seed", parent_ids=("a", "b")),
    )
    assignments = (
        assignment(term_id="seed"),
        assignment("negative", term_id="b", assertion=TaxonomyAssignmentAssertion.ABSENT),
    )
    edges = tuple(
        FoodRelation(
            relation_id=f"r-{id_}",
            version="v1",
            source_id="recipe",
            target_id=id_,
            relation_type=FoodRelationType.CONTAINS,
            assertion=RelationAssertion.PRESENT,
            evidence=(evidence(),),
        )
        for id_ in ("rice", "chicken")
    )
    errors: set[str] = set()
    for term_order in permutations(terms):
        for assignment_order in permutations(assignments):
            for relation_order in permutations(edges):
                for entities in (graph().entities, tuple(reversed(graph().entities))):
                    with pytest.raises(
                        ValidationError, match="contradictory cuisine ancestry"
                    ) as error:
                        graph(
                            entities=entities,
                            relations=relation_order,
                            taxonomy_terms=tuple(
                                item.model_copy(
                                    update={"parent_ids": tuple(reversed(item.parent_ids))}
                                )
                                for item in term_order
                            ),
                            taxonomy_assignments=assignment_order,
                        )
                    context = error.value.errors(include_input=False, include_url=False)[0].get(
                        "ctx"
                    )
                    assert context is not None
                    errors.add(str(context["error"]))
    assert len(errors) == 1


def test_valid_multiple_parent_dag_with_outside_negative_stays_supported() -> None:
    snapshot = graph(
        taxonomy_terms=(
            term("target"),
            term("a", parent_ids=("target",)),
            term("b", parent_ids=("target",)),
            term("seed", parent_ids=("b", "a")),
            term("unrelated"),
        ),
        taxonomy_assignments=(
            assignment(term_id="seed"),
            assignment(
                "negative", term_id="unrelated", assertion=TaxonomyAssignmentAssertion.ABSENT
            ),
        ),
    )
    supported = parents(snapshot, term_id="target", max_hops=2, max_visited=4)
    assert supported.status is RelationResolutionStatus.SUPPORTED
    assert tuple(item.term_id for item in supported.path) == ("seed", "a", "target")
    assert supported.assignment is not None
    assert set(supported.evidence) == (
        set(supported.assignment.evidence)
        | set(ref for item in supported.path for ref in item.evidence)
    )
    absent = resolve(snapshot, term_id="unrelated")
    assert absent.status is RelationResolutionStatus.VERIFIED_ABSENT
    missing = resolve(snapshot, term_id="a")
    assert missing.status is RelationResolutionStatus.UNKNOWN


def test_negative_cuisine_assignments_are_scoped_to_their_subject() -> None:
    snapshot = graph(
        taxonomy_assignments=(
            assignment(),
            assignment(
                "other-negative",
                subject_id="rice",
                term_id="indian",
                assertion=TaxonomyAssignmentAssertion.ABSENT,
            ),
        ),
    )
    assert parents(snapshot).status is RelationResolutionStatus.SUPPORTED
    assert (
        resolve(snapshot, subject_id="rice", term_id="indian").status
        is RelationResolutionStatus.VERIFIED_ABSENT
    )


@pytest.mark.parametrize(
    "kind",
    [
        TaxonomyKind.DIETARY_PATTERN,
        TaxonomyKind.DIETARY_CATEGORY,
        TaxonomyKind.CULINARY_ROLE,
    ],
)
def test_cuisine_consistency_does_not_propagate_other_taxonomy_kinds(kind: TaxonomyKind) -> None:
    snapshot = graph(
        taxonomy_terms=(
            term("parent", kind=kind),
            term("child", kind=kind, parent_ids=("parent",)),
        ),
        taxonomy_assignments=(
            assignment(term_id="child"),
            assignment("negative", term_id="parent", assertion=TaxonomyAssignmentAssertion.ABSENT),
        ),
    )
    assert resolve(snapshot, term_id="child").status is RelationResolutionStatus.SUPPORTED
    assert parents(snapshot, term_id="parent").status is RelationResolutionStatus.VERIFIED_ABSENT


@pytest.mark.parametrize("mode", ["copy", "construct"])
@pytest.mark.parametrize("mutation", ["assignment", "term"])
def test_unchecked_nested_records_cannot_bypass_complete_ancestor_conflict(
    mode: str,
    mutation: str,
) -> None:
    positive = assignment(term_id="seed")
    negative = assignment(
        "negative", term_id="outside", assertion=TaxonomyAssignmentAssertion.ABSENT
    )
    snapshot = graph(
        taxonomy_terms=(
            term("target"),
            term("a", parent_ids=("target",)),
            term("b", parent_ids=("target",)),
            term("seed", parent_ids=("a", "b")),
            term("outside"),
        ),
        taxonomy_assignments=(positive, negative),
    )
    if mutation == "assignment":
        bad = unchecked(negative, {"term_id": "b"}, mode)
        changes = {"taxonomy_assignments": (positive, bad)}
    else:
        bad = unchecked(snapshot.taxonomy_terms[2], {"parent_ids": ("target", "outside")}, mode)
        changes = {
            "taxonomy_terms": (*snapshot.taxonomy_terms[:2], bad, *snapshot.taxonomy_terms[3:])
        }
    malformed = unchecked(snapshot, changes, mode)
    with pytest.raises(ValidationError, match="contradictory cuisine ancestry"):
        FoodGraphSnapshot.model_validate(_validation_payload(malformed), strict=True)
    for traversal in TaxonomyTraversalMode:
        with pytest.raises(ValidationError, match="contradictory cuisine ancestry"):
            resolve(malformed, term_id="target", traversal=traversal, max_hops=1, max_visited=1)
    with pytest.raises(ValidationError, match="contradictory cuisine ancestry"):
        resolve_food_relations(
            malformed,
            source_id="missing",
            target_id="rice",
            relation_type=FoodRelationType.DERIVED_FROM,
        )


def test_contradictory_cuisine_snapshot_json_is_rejected() -> None:
    snapshot = graph(taxonomy_assignments=(assignment(),))
    negative = assignment(
        "negative", term_id="indian", assertion=TaxonomyAssignmentAssertion.ABSENT
    )
    unchecked_snapshot = snapshot.model_copy(
        update={"taxonomy_assignments": (*snapshot.taxonomy_assignments, negative)}
    )
    with pytest.raises(ValidationError, match="contradictory cuisine ancestry"):
        FoodGraphSnapshot.model_validate_json(unchecked_snapshot.model_dump_json())


def test_deep_cuisine_closure_cannot_be_hidden_by_a_shorter_clean_witness() -> None:
    ids = tuple(f"chain-{i:04d}" for i in range(1100))
    terms = tuple(
        term(id_, parent_ids=(ids[i + 1],) if i + 1 < len(ids) else ("target",))
        for i, id_ in enumerate(ids)
    )
    with pytest.raises(ValidationError, match="contradictory cuisine ancestry"):
        graph(
            taxonomy_terms=(term("target"), term("seed", parent_ids=("target", ids[0])), *terms),
            taxonomy_assignments=(
                assignment(term_id="seed"),
                assignment(
                    "negative", term_id=ids[-1], assertion=TaxonomyAssignmentAssertion.ABSENT
                ),
            ),
        )


def test_every_small_dag_assignment_pattern_obeys_complete_cuisine_consistency() -> None:
    nodes = ("n0", "n1", "n2", "n3")
    edges = [(a, b) for i, a in enumerate(nodes) for b in nodes[i + 1 :]]
    for mask in range(1 << len(edges)):
        selected = [pair for bit, pair in enumerate(edges) if mask & (1 << bit)]
        terms = tuple(
            term(node, parent_ids=tuple(parent for child, parent in selected if child == node))
            for node in nodes
        )
        for pattern in product(
            (None, TaxonomyAssignmentAssertion.PRESENT, TaxonomyAssignmentAssertion.ABSENT),
            repeat=len(nodes),
        ):
            assigned = tuple(
                assignment(f"assignment-{i}", term_id=node, assertion=assertion)
                for i, (node, assertion) in enumerate(zip(nodes, pattern, strict=True))
                if assertion is not None
            )
            negatives = {
                node
                for node, assertion in zip(nodes, pattern, strict=True)
                if assertion is TaxonomyAssignmentAssertion.ABSENT
            }
            # Independent reference: enumerate all upward routes, without the
            # production validator's subject grouping or discovered-set pruning.
            closure: set[str] = set()
            for node, assertion in zip(nodes, pattern, strict=True):
                if assertion is not TaxonomyAssignmentAssertion.PRESENT:
                    continue
                routes = [node]
                while routes:
                    endpoint = routes.pop()
                    closure.add(endpoint)
                    routes.extend(parent for child, parent in selected if child == endpoint)
            if closure & negatives:
                with pytest.raises(ValidationError, match="contradictory cuisine ancestry"):
                    graph(taxonomy_terms=terms, taxonomy_assignments=assigned)
            else:
                snapshot = graph(taxonomy_terms=terms, taxonomy_assignments=assigned)
                assert (
                    snapshot.taxonomy_terms == terms and snapshot.taxonomy_assignments == assigned
                )


def test_hierarchy_matches_exhaustive_paths_for_all_small_forward_edge_subsets() -> None:
    nodes = ("n0", "n1", "n2", "n3")
    edges = [(a, b) for i, a in enumerate(nodes) for b in nodes[i + 1 :]]
    for mask in range(1 << len(edges)):
        selected = [pair for bit, pair in enumerate(edges) if mask & (1 << bit)]
        terms = tuple(
            term(id_, parent_ids=tuple(b for a, b in selected if a == id_)) for id_ in nodes
        )
        for seed in nodes:
            snapshot = graph(taxonomy_terms=terms, taxonomy_assignments=(assignment(term_id=seed),))
            paths: dict[str, list[tuple[str, ...]]] = {}
            stack: list[tuple[str, tuple[str, ...]]] = [(seed, (seed,))]
            while stack:
                endpoint, path = stack.pop()
                paths.setdefault(endpoint, []).append(path)
                for source, target in selected:
                    if source == endpoint:
                        stack.append((target, (*path, target)))
            for target in nodes:
                for hops in (1, 2, 3):
                    result = parents(snapshot, term_id=target, max_hops=hops, max_visited=4)
                    eligible = [path for path in paths.get(target, ()) if len(path) - 1 <= hops]
                    if eligible:
                        expected = min(eligible, key=lambda path: (len(path), path))
                        assert result.status is RelationResolutionStatus.SUPPORTED
                        assert tuple(item.term_id for item in result.path) == (
                            () if seed == target else expected
                        )
                    else:
                        assert result.status is RelationResolutionStatus.UNKNOWN
                        assert not result.path
                        blocked = any(
                            min(len(path) - 1 for path in witnesses) > hops
                            for witnesses in paths.values()
                        )
                        assert result.limit_reached is blocked
