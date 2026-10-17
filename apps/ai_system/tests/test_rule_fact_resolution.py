"""Independent exact-claim fixtures; no real foods, allergen assertions or clinical advice."""

from itertools import pairwise
from typing import Any

import pytest
from pydantic import ValidationError
from test_rule_manifest import changed_candidate, changed_context, definition, fact, packet, source

from savora_ai.core.reasoning.facts import resolve_rule_facts
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    IngredientCoverage,
    IngredientGapReason,
    IngredientLine,
    IngredientMappingStatus,
    RuleContext,
    VersionedFact,
    validate_contract_json,
)
from savora_ai.schemas.filtering import CandidateFactResolution
from savora_ai.schemas.food_graph import (
    FoodEntity,
    FoodEntityKind,
    FoodGraphSnapshot,
    FoodRelation,
    FoodRelationType,
    KnowledgeCoverage,
    RelationAssertion,
    RelationQualifiers,
    RelationResolutionStatus,
    TaxonomyAssignment,
    TaxonomyAssignmentAssertion,
    TaxonomyKind,
    TaxonomyTerm,
)
from savora_ai.schemas.knowledge import RuleDefinition, RuleDomain
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot, KnowledgeWorkflow


def ingredient_line(canonical: str = "synthetic-source", **changes: Any) -> IngredientLine:
    return IngredientLine.model_validate(
        {
            "line_id": "line-" + canonical,
            "version": "line-v3",
            "recipe_id": "recipe",
            "recipe_version": "recipe-v1",
            "catalogue_version": "catalogue-v1",
            "mapping_status": IngredientMappingStatus.MAPPED,
            "ingredient_id": canonical,
            "ingredient_version": "ingredient-content-v17",
            "subingredients_complete": True,
            "gap_reasons": (),
            "evidence": (source("line-" + canonical),),
        }
        | changes
    )


def coverage(
    state: str = "complete",
    lines: tuple[IngredientLine, ...] | None = None,
) -> IngredientCoverage:
    actual = (ingredient_line(),) if lines is None else lines
    reasons: list[IngredientGapReason] = []
    if state == "missing":
        actual_lines = None
        reasons.append(IngredientGapReason.MISSING_INVENTORY)
        mapped = expanded = False
    else:
        actual_lines = actual
        records: list[IngredientLine] = []
        pending = list(actual)
        while pending:
            record = pending.pop()
            records.append(record)
            pending.extend(record.subingredients)
        mapped = all(line.mapping_status is IngredientMappingStatus.MAPPED for line in records)
        expanded = all(line.subingredients_complete for line in records)
        if state == "partial":
            reasons.append(IngredientGapReason.INCOMPLETE_INVENTORY)
        if not mapped:
            reasons.append(IngredientGapReason.UNRESOLVED_MAPPING)
        if not expanded:
            reasons.append(IngredientGapReason.INCOMPLETE_SUBINGREDIENTS)
    return IngredientCoverage(
        coverage_id="inventory",
        version="inventory-v5",
        recipe_id="recipe",
        recipe_version="recipe-v1",
        catalogue_version="catalogue-v1",
        lines=actual_lines,
        inventory_complete=state == "complete",
        mapping_complete=mapped,
        subingredients_complete=expanded,
        gap_reasons=tuple(reasons),
        evidence=(source("inventory"),),
    )


def edge(
    id_: str,
    source_id: str,
    target_id: str,
    kind: FoodRelationType = FoodRelationType.CONTAINS,
    assertion: RelationAssertion = RelationAssertion.PRESENT,
    qualifiers: RelationQualifiers | None = None,
) -> FoodRelation:
    return FoodRelation(
        relation_id=id_,
        version="edge-v7",
        source_id=source_id,
        target_id=target_id,
        relation_type=kind,
        assertion=assertion,
        qualifiers=RelationQualifiers() if qualifiers is None else qualifiers,
        evidence=(source("evidence-" + id_),),
    )


def graph_packet(
    attributes: tuple[str, ...] = ("synthetic_contains_target",),
    *,
    rules: tuple[RuleDefinition, ...] | None = None,
    contains: RelationAssertion | None = None,
    origin_length: int = 0,
    dietary: TaxonomyAssignmentAssertion | None = None,
    cuisine: TaxonomyAssignmentAssertion | None = None,
    hierarchy: bool = False,
    compatibility: RelationAssertion | None = None,
    inventory_state: str = "complete",
    inventory_lines: tuple[IngredientLine, ...] | None = None,
    candidate_facts: tuple[VersionedFact, ...] = (),
    workflow: KnowledgeWorkflow = KnowledgeWorkflow.CRAVING_DISCOVERY,
) -> tuple[KnowledgeBaseSnapshot, CandidateRecipeFacts, RuleContext]:
    definitions = (
        rules
        if rules is not None
        else tuple(
            definition(
                "check-" + name,
                attribute=name,
                required_facts=(name,),
                value=True,
            )
            for name in attributes
        )
    )
    kb, candidate, context = packet(definitions, candidate_facts=candidate_facts, workflow=workflow)
    entities = [*kb.graph.entities]
    for node, canonical in (
        ("node-source", "synthetic-source"),
        ("node-target", "synthetic-target"),
    ):
        entities.append(
            FoodEntity(
                entity_id=node,
                version="graph-node-v4",
                kind=FoodEntityKind.INGREDIENT,
                catalogue_reference=canonical,
                canonical_name="Synthetic ingredient",
                evidence=(source("entity-" + node),),
            )
        )
    entities.append(
        FoodEntity(
            entity_id="node-companion",
            version="graph-node-v4",
            kind=FoodEntityKind.RECIPE_REFERENCE,
            catalogue_reference="synthetic-companion",
            canonical_name="Synthetic companion",
            evidence=(source("companion"),),
        )
    )
    relations = [edge("source-contained", "graph-recipe", "node-source")]
    if contains is not None:
        relations.append(
            edge("target-contained", "graph-recipe", "node-target", assertion=contains)
        )
    if origin_length:
        node_ids = ["node-source"]
        for number in range(origin_length - 1):
            node = f"node-origin-{number}"
            entities.append(
                FoodEntity(
                    entity_id=node,
                    version="graph-node-v4",
                    kind=FoodEntityKind.INGREDIENT,
                    canonical_name="Synthetic intermediary",
                    evidence=(source(node),),
                )
            )
            node_ids.append(node)
        node_ids.append("node-target")
        relations.extend(
            edge(f"origin-{number}", start, end, FoodRelationType.DERIVED_FROM)
            for number, (start, end) in enumerate(pairwise(node_ids))
        )
    if compatibility is not None:
        relations.append(
            edge(
                "dinner-compatible",
                "graph-recipe",
                "node-companion",
                FoodRelationType.COMPATIBLE_WITH,
                assertion=compatibility,
                qualifiers=RelationQualifiers(meal_type="DINNER"),
            )
        )
    terms = [
        TaxonomyTerm(
            term_id="synthetic-dietary",
            version="diet-v2",
            kind=TaxonomyKind.DIETARY_CATEGORY,
            display_label="Synthetic dietary category",
            evidence=(source("diet-term"),),
        ),
        TaxonomyTerm(
            term_id="synthetic-cuisine",
            version="cuisine-v3",
            kind=TaxonomyKind.CUISINE,
            display_label="Synthetic cuisine",
            evidence=(source("cuisine-term"),),
        ),
    ]
    assignments = []
    if dietary is not None:
        assignments.append(
            TaxonomyAssignment(
                assignment_id="diet-assignment",
                version="assignment-v4",
                subject_id="graph-recipe",
                term_id="synthetic-dietary",
                assertion=dietary,
                evidence=(source("diet-assignment"),),
            )
        )
    if cuisine is not None:
        if hierarchy:
            terms.append(
                TaxonomyTerm(
                    term_id="synthetic-child-cuisine",
                    version="child-v6",
                    kind=TaxonomyKind.CUISINE,
                    display_label="Synthetic child",
                    parent_ids=("synthetic-cuisine",),
                    evidence=(source("child-term"),),
                )
            )
        assignments.append(
            TaxonomyAssignment(
                assignment_id="cuisine-assignment",
                version="assignment-v4",
                subject_id="graph-recipe",
                term_id="synthetic-child-cuisine" if hierarchy else "synthetic-cuisine",
                assertion=cuisine,
                evidence=(source("cuisine-assignment"),),
            )
        )
    graph = FoodGraphSnapshot.model_validate(
        kb.graph.model_dump()
        | {
            "entities": tuple(entities),
            "relations": tuple(relations),
            "taxonomy_version": "taxonomy-v9",
            "taxonomy_terms": tuple(terms),
            "taxonomy_assignments": tuple(assignments),
        }
    )
    body: dict[str, Any] = kb.model_dump(exclude={"content_digest"}) | {
        "graph": graph,
        "taxonomy_version": graph.taxonomy_version,
    }
    kb = build_knowledge_snapshot(body)
    if inventory_lines is None and contains is RelationAssertion.PRESENT:
        inventory_lines = (ingredient_line(), ingredient_line("synthetic-target"))
    candidate = changed_candidate(
        candidate, ingredient_coverage=coverage(inventory_state, inventory_lines)
    )
    context = changed_context(
        context, expected_kb_digest=kb.content_digest, expected_taxonomy_version=kb.taxonomy_version
    )
    return kb, candidate, context


def resolve(
    inputs: tuple[KnowledgeBaseSnapshot, CandidateRecipeFacts, RuleContext],
) -> CandidateFactResolution:
    return resolve_rule_facts(inputs[1], knowledge=inputs[0], context=inputs[2])


def selected(resolution: CandidateFactResolution, name: str) -> Any:
    return next(item for item in resolution.facts if item.fact.fact_id == name)


@pytest.mark.parametrize(
    "assertion,expected",
    [(None, None), (RelationAssertion.PRESENT, True), (RelationAssertion.ABSENT, False)],
)
def test_exact_containment_requires_kb_assertion(
    assertion: RelationAssertion | None, expected: bool | None
) -> None:
    inputs = graph_packet(contains=assertion)
    result = resolve(inputs)
    record = selected(result, "synthetic_contains_target")
    assert record.fact.observation.value is expected
    assert record.fact.observation.complete is (expected is not None)
    assert (
        record.relations[0].relation is None
        if assertion is None
        else record.relations[0].relation.assertion is assertion
    )
    assert result.manifest.attribute_policy_version == "synthetic-attributes.v2"
    assert result.manifest.candidate_digest == inputs[1].content_digest
    assert (
        validate_contract_json(CandidateFactResolution, result.model_dump_json(by_alias=True))
        == result
    )


@pytest.mark.parametrize("state", ["partial", "missing"])
@pytest.mark.parametrize("assertion", [RelationAssertion.PRESENT, RelationAssertion.ABSENT])
def test_incomplete_inventory_does_not_gain_completeness_or_negative_claims(
    state: str, assertion: RelationAssertion
) -> None:
    result = resolve(graph_packet(contains=assertion, inventory_state=state))
    record = selected(result, "synthetic_contains_target")
    assert record.fact.observation.value is (
        True if assertion is RelationAssertion.PRESENT else None
    )
    assert not result.ingredient_coverage.inventory_complete
    assert result.ingredient_coverage.gap_reasons
    if assertion is RelationAssertion.ABSENT:
        assert record.relations[0].status is RelationResolutionStatus.VERIFIED_ABSENT
        assert record.reason_code == "INGREDIENT_MAPPING_GAP"


@pytest.mark.parametrize("case", ["unresolved", "no_graph_mapping", "incomplete_subingredients"])
def test_mapping_and_expansion_gaps_remain_visible(case: str) -> None:
    line = (
        ingredient_line(
            mapping_status=IngredientMappingStatus.UNRESOLVED,
            ingredient_id=None,
            ingredient_version=None,
            gap_reasons=(IngredientGapReason.UNRESOLVED_MAPPING,),
        )
        if case == "unresolved"
        else ingredient_line("unknown-canonical")
        if case == "no_graph_mapping"
        else ingredient_line(
            subingredients_complete=False,
            gap_reasons=(IngredientGapReason.INCOMPLETE_SUBINGREDIENTS,),
        )
    )
    result = resolve(graph_packet(contains=RelationAssertion.ABSENT, inventory_lines=(line,)))
    assert selected(result, "synthetic_contains_target").fact.observation.value is None
    if case != "incomplete_subingredients":
        assert result.unresolved_line_ids == (line.line_id,)
    else:
        assert not result.ingredient_coverage.subingredients_complete


@pytest.mark.parametrize("claim", [False, True])
def test_caller_graph_claim_does_not_fill_missing_assertion(claim: bool) -> None:
    result = resolve(graph_packet(candidate_facts=(fact("synthetic_contains_target", claim),)))
    record = selected(result, "synthetic_contains_target")
    assert record.supplied_fact.observation.value is claim
    assert record.fact.observation.value is None


@pytest.mark.parametrize("complete", [False, True])
@pytest.mark.parametrize(
    "assertion,claim", [(RelationAssertion.PRESENT, False), (RelationAssertion.ABSENT, True)]
)
def test_opposing_caller_and_kb_claims_rejected(
    assertion: RelationAssertion, claim: bool, complete: bool
) -> None:
    with pytest.raises(ValidationError, match="contradicts"):
        resolve(
            graph_packet(
                contains=assertion,
                candidate_facts=(fact("synthetic_contains_target", claim, complete=complete),),
            )
        )


def test_opposing_inventory_and_graph_assertions_rejected() -> None:
    with pytest.raises(ValidationError, match="contradicts"):
        resolve(
            graph_packet(
                contains=RelationAssertion.ABSENT,
                inventory_lines=(ingredient_line("synthetic-target"),),
            )
        )
    with pytest.raises(ValidationError, match="contradicts"):
        resolve(
            graph_packet(
                attributes=("synthetic_flag",),
                contains=RelationAssertion.PRESENT,
                inventory_lines=(ingredient_line(),),
                candidate_facts=(fact(),),
            )
        )


@pytest.mark.parametrize("length", [1, 3, 8, 9])
def test_origin_paths_preserve_order_and_never_establish_allergen_absence(length: int) -> None:
    result = resolve(
        graph_packet(
            (
                "synthetic_origin_target",
                "synthetic_contains_target",
                "synthetic_allergen_absent",
                "synthetic_clinically_safe",
            ),
            origin_length=length,
        )
    )
    origin = selected(result, "synthetic_origin_target")
    assert origin.fact.observation.value is (True if length <= 8 else None)
    witness = origin.relations[0]
    if length <= 8:
        assert [record.relation_id for record in witness.path] == [
            f"origin-{number}" for number in range(length)
        ]
        assert all(record.version == "edge-v7" for record in witness.path)
        assert witness.path[0].source_id == "node-source"
        assert witness.path[-1].target_id == "node-target"
    else:
        assert witness.limit_reached and witness.reason_code == "MAX_HOPS_REACHED"
        assert witness.path == ()
    for name in (
        "synthetic_contains_target",
        "synthetic_allergen_absent",
        "synthetic_clinically_safe",
    ):
        assert selected(result, name).fact.observation.value is None
    assert (
        validate_contract_json(CandidateFactResolution, result.model_dump_json(by_alias=True))
        == result
    )


@pytest.mark.parametrize("kind", ["dietary", "cuisine"])
@pytest.mark.parametrize(
    "assertion,expected",
    [
        (None, None),
        (TaxonomyAssignmentAssertion.PRESENT, True),
        (TaxonomyAssignmentAssertion.ABSENT, False),
    ],
)
def test_exact_taxonomy_semantics(
    kind: str, assertion: TaxonomyAssignmentAssertion | None, expected: bool | None
) -> None:
    inputs = graph_packet(
        ("synthetic_" + kind + "_target",),
        dietary=assertion if kind == "dietary" else None,
        cuisine=assertion if kind == "cuisine" else None,
    )
    result = resolve(inputs)
    record = selected(result, "synthetic_" + kind + "_target")
    assert record.fact.observation.value is expected
    assert record.taxonomy.taxonomy_version == "taxonomy-v9"
    assert record.fact.catalogue_version == "catalogue-v1"


def test_cuisine_hierarchy_and_prediction_do_not_prove_dietary_classification() -> None:
    result = resolve(
        graph_packet(
            ("synthetic_cuisine_target", "synthetic_dietary_target"),
            cuisine=TaxonomyAssignmentAssertion.PRESENT,
            hierarchy=True,
            candidate_facts=(fact("synthetic_dietary_target", True),),
        )
    )
    cuisine = selected(result, "synthetic_cuisine_target")
    assert cuisine.fact.observation.value is True
    assert [term.term_id for term in cuisine.taxonomy.path] == [
        "synthetic-child-cuisine",
        "synthetic-cuisine",
    ]
    assert selected(result, "synthetic_dietary_target").fact.observation.value is None
    predicted = resolve(
        graph_packet(
            ("synthetic_cuisine_target",), candidate_facts=(fact("synthetic_cuisine_target", True),)
        )
    )
    assert selected(predicted, "synthetic_cuisine_target").fact.observation.value is None


@pytest.mark.parametrize(
    "assertion,expected",
    [(None, None), (RelationAssertion.PRESENT, True), (RelationAssertion.ABSENT, False)],
)
def test_qualified_compatibility_is_exact_and_retains_qualifiers(
    assertion: RelationAssertion | None, expected: bool | None
) -> None:
    record = selected(
        resolve(graph_packet(("synthetic_dinner_compatible",), compatibility=assertion)),
        "synthetic_dinner_compatible",
    )
    assert record.fact.observation.value is expected
    assert record.relations[0].qualifiers.meal_type == "DINNER"
    assert record.relations[0].path == ()


@pytest.mark.parametrize("name", ["synthetic_allergen_absent", "synthetic_clinically_safe"])
@pytest.mark.parametrize("value", [False, True, None])
def test_unsupported_safety_semantics_stay_unknown(name: str, value: bool | None) -> None:
    record = selected(
        resolve(
            graph_packet((name,), candidate_facts=(fact(name, value, complete=value is not None),))
        ),
        name,
    )
    assert record.fact.observation.value is None
    assert record.reason_code == "UNSUPPORTED_SAFETY_INFERENCE"


@pytest.mark.parametrize(
    "name",
    [
        "synthetic_contains_target",
        "synthetic_origin_target",
        "synthetic_dietary_target",
        "synthetic_cuisine_target",
        "synthetic_dinner_compatible",
    ],
)
def test_exact_graph_claims_cannot_be_admitted_as_clinical_rules(name: str) -> None:
    clinical = definition(
        attribute=name, required_facts=(name,), value=True, domain=RuleDomain.CLINICAL
    )
    with pytest.raises(ValidationError, match="clinical"):
        resolve(graph_packet(rules=(clinical,)))


def test_candidate_and_graph_node_content_versions_remain_distinct() -> None:
    inputs = graph_packet(contains=RelationAssertion.PRESENT)
    result = resolve(inputs)
    assert result.ingredient_coverage.version == "inventory-v5"
    assert result.ingredient_coverage.lines is not None
    assert result.ingredient_coverage.lines[0].ingredient_version == "ingredient-content-v17"
    assert inputs[0].graph.entities[1].version == "graph-node-v4"
    assert result.manifest.candidate_version == "recipe-v1"
    assert result.manifest.graph_version == "graph-v1"


def test_foreign_resolution_payloads_are_not_accepted() -> None:
    kb, candidate, context = graph_packet()
    with pytest.raises(TypeError):
        resolve_rule_facts(candidate, knowledge=kb, context=context, resolutions=())  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        resolve_rule_facts(
            candidate.model_copy(update={"graph_resolution": True}), knowledge=kb, context=context
        )


@pytest.mark.parametrize("target", ["candidate", "context", "kb"])
@pytest.mark.parametrize("mode", ["copy", "construct"])
def test_malformed_inputs_revalidated(target: str, mode: str) -> None:
    inputs: list[Any] = list(graph_packet())
    index = {"kb": 0, "candidate": 1, "context": 2}[target]
    record = inputs[index]
    changes = {"content_digest": "0" * 64}
    inputs[index] = (
        record.model_copy(update=changes)
        if mode == "copy"
        else type(record).model_construct(**(vars(record) | changes))
    )
    with pytest.raises(ValidationError):
        resolve_rule_facts(inputs[1], knowledge=inputs[0], context=inputs[2])


def replace_graph(
    inputs: tuple[KnowledgeBaseSnapshot, CandidateRecipeFacts, RuleContext],
    graph: FoodGraphSnapshot,
) -> tuple[KnowledgeBaseSnapshot, CandidateRecipeFacts, RuleContext]:
    kb, candidate, context = inputs
    body: dict[str, Any] = kb.model_dump(exclude={"content_digest"}) | {
        "graph": graph,
        "taxonomy_version": graph.taxonomy_version,
    }
    kb = build_knowledge_snapshot(body)
    context = changed_context(
        context, expected_kb_digest=kb.content_digest, expected_taxonomy_version=kb.taxonomy_version
    )
    return kb, candidate, context


def test_complete_graph_coverage_does_not_create_absence() -> None:
    inputs = graph_packet()
    record = KnowledgeCoverage(
        coverage_id="complete-edges",
        version="1",
        graph_id="graph",
        graph_version="graph-v1",
        catalogue_version="catalogue-v1",
        subject_id="graph-recipe",
        relation_type=FoodRelationType.CONTAINS,
        complete=True,
        reason="Synthetic complete outgoing declaration",
        evidence=(source("edge-coverage"),),
    )
    graph = FoodGraphSnapshot.model_validate(inputs[0].graph.model_dump() | {"coverage": (record,)})
    result = selected(resolve(replace_graph(inputs, graph)), "synthetic_contains_target")
    assert result.fact.observation.value is None
    assert result.relations[0].coverage.complete


def test_nested_unresolved_ingredient_lines_prevent_negative_claim() -> None:
    child = ingredient_line(
        "child",
        mapping_status=IngredientMappingStatus.UNRESOLVED,
        ingredient_id=None,
        ingredient_version=None,
        gap_reasons=(IngredientGapReason.UNRESOLVED_MAPPING,),
    )
    parent = ingredient_line(subingredients=(child,))
    result = resolve(graph_packet(contains=RelationAssertion.ABSENT, inventory_lines=(parent,)))
    assert result.unresolved_line_ids == (child.line_id,)
    assert not result.ingredient_coverage.mapping_complete
    assert selected(result, "synthetic_contains_target").fact.observation.value is None


@pytest.mark.parametrize("state", ["partial", "missing"])
def test_opposing_supplied_positive_cannot_hide_behind_inventory_gap(state: str) -> None:
    with pytest.raises(ValidationError, match="contradicts"):
        resolve(
            graph_packet(
                contains=RelationAssertion.ABSENT,
                inventory_state=state,
                candidate_facts=(fact("synthetic_contains_target", True, complete=False),),
            )
        )


def test_origin_visited_limit_is_visible_and_not_a_negative() -> None:
    inputs = graph_packet(("synthetic_origin_target",))
    graph = inputs[0].graph
    nodes = tuple(
        FoodEntity(
            entity_id=f"branch-{number}",
            version="1",
            kind=FoodEntityKind.INGREDIENT,
            canonical_name="Synthetic branch",
            evidence=(source(f"branch-{number}"),),
        )
        for number in range(256)
    )
    branches = tuple(
        edge(f"branch-{number:03}", "node-source", node.entity_id, FoodRelationType.DERIVED_FROM)
        for number, node in enumerate(nodes)
    )
    graph = FoodGraphSnapshot.model_validate(
        graph.model_dump()
        | {
            "entities": (*graph.entities, *nodes),
            "relations": (
                *graph.relations,
                *branches,
                edge("z-target", "node-source", "node-target", FoodRelationType.DERIVED_FROM),
            ),
        }
    )
    record = selected(resolve(replace_graph(inputs, graph)), "synthetic_origin_target")
    assert record.fact.observation.value is None
    assert record.relations[0].limit_reached
    assert record.relations[0].reason_code == "MAX_VISITED_REACHED"
    assert record.reason_code == "TRAVERSAL_LIMIT"


def test_non_cuisine_hierarchy_does_not_generalize_dietary_membership() -> None:
    inputs = graph_packet(("synthetic_dietary_target",))
    graph = inputs[0].graph
    child = TaxonomyTerm(
        term_id="child-diet",
        version="1",
        kind=TaxonomyKind.DIETARY_CATEGORY,
        display_label="Synthetic diet child",
        parent_ids=("synthetic-dietary",),
        evidence=(source("child-diet"),),
    )
    assignment = TaxonomyAssignment(
        assignment_id="child-diet-assignment",
        version="1",
        subject_id="graph-recipe",
        term_id="child-diet",
        assertion=TaxonomyAssignmentAssertion.PRESENT,
        evidence=(source("child-diet-assignment"),),
    )
    graph = FoodGraphSnapshot.model_validate(
        graph.model_dump()
        | {
            "taxonomy_terms": (*graph.taxonomy_terms, child),
            "taxonomy_assignments": (assignment,),
        }
    )
    record = selected(resolve(replace_graph(inputs, graph)), "synthetic_dietary_target")
    assert record.fact.observation.value is None
    assert record.taxonomy.reason_code == "NO_ASSIGNMENT"


def test_target_label_or_node_id_does_not_substitute_for_canonical_mapping() -> None:
    inputs = graph_packet()
    graph = inputs[0].graph
    graph = FoodGraphSnapshot.model_validate(
        graph.model_dump()
        | {
            "entities": tuple(
                entity.model_copy(
                    update={
                        "catalogue_reference": None,
                        "canonical_name": "synthetic-target",
                        "aliases": ("synthetic-target",),
                    }
                )
                if entity.entity_id == "node-target"
                else entity
                for entity in graph.entities
            ),
        }
    )
    record = selected(resolve(replace_graph(inputs, graph)), "synthetic_contains_target")
    assert record.fact.observation.value is None
    assert record.reason_code == "UNRESOLVED_TARGET_MAPPING"


def test_other_qualified_compatibility_does_not_match_dinner_claim() -> None:
    inputs = graph_packet(("synthetic_dinner_compatible",), compatibility=RelationAssertion.PRESENT)
    graph = FoodGraphSnapshot.model_validate(
        inputs[0].graph.model_dump()
        | {
            "relations": tuple(
                relation.model_copy(
                    update={"qualifiers": RelationQualifiers(meal_type="BREAKFAST")}
                )
                if relation.relation_type is FoodRelationType.COMPATIBLE_WITH
                else relation
                for relation in inputs[0].graph.relations
            ),
        }
    )
    record = selected(resolve(replace_graph(inputs, graph)), "synthetic_dinner_compatible")
    assert record.fact.observation.value is None
    assert record.relations[0].reason_code == "NO_DIRECT_ASSERTION"


@pytest.mark.parametrize(
    "name",
    [
        "synthetic_contains_target",
        "synthetic_origin_target",
        "synthetic_dietary_target",
        "synthetic_cuisine_target",
        "synthetic_dinner_compatible",
        "synthetic_allergen_absent",
        "synthetic_clinically_safe",
    ],
)
def test_malformed_supplied_adapter_value_is_rejected_even_with_unknown_condition(
    name: str,
) -> None:
    kb, candidate, context = graph_packet(
        (name,), candidate_facts=(fact(name, ("True",), complete=False),)
    )
    context = changed_context(context, facts=())
    with pytest.raises(ValidationError, match="incompatible"):
        resolve_rule_facts(candidate, knowledge=kb, context=context)
