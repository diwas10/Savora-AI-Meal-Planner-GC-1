"""Independent synthetic ownership/integrity tests; no food or clinical assertions."""

import hashlib
import json
import math
from collections.abc import Iterator
from enum import StrEnum
from itertools import permutations
from typing import Any

import pytest
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    RootModel,
    TypeAdapter,
    ValidationError,
    computed_field,
    field_validator,
)

from savora_ai.schemas.candidates import (
    STRICT_JSON_MAX_BYTES,
    STRICT_JSON_MAX_DEPTH,
    CandidateRecipeFacts,
    FactSubjectKind,
    IngredientCoverage,
    IngredientGapReason,
    IngredientLine,
    IngredientMappingStatus,
    MeasurementBasis,
    RuleContext,
    VersionedFact,
    validate_contract_json,
)
from savora_ai.schemas.food_graph import FoodEntity, FoodEntityKind
from savora_ai.schemas.knowledge import EvidenceReference, MeasurementUnit, RuleEnvironment
from savora_ai.schemas.knowledge_base import KnowledgeWorkflow
from savora_ai.schemas.reasoning import FactObservation


def evidence(id_: str = "synthetic-source", **changes: Any) -> EvidenceReference:
    return EvidenceReference.model_validate(
        {
            "evidence_id": id_,
            "version": "source-v1",
            "source": "SYNTHETIC Task 3.1 fixture; no verified food or medical meaning",
            "locator": "urn:savora:synthetic:task3.1:" + id_,
            "environment": RuleEnvironment.SYNTHETIC,
        }
        | changes
    )


def observed(**changes: Any) -> FactObservation:
    return FactObservation.model_validate(
        {
            "fact_id": "fixture_flag",
            "value": False,
            "unit": None,
            "complete": True,
            "evidence": (evidence(),),
        }
        | changes
    )


def fact(**changes: Any) -> VersionedFact:
    return VersionedFact.model_validate(
        {
            "fact_id": "fixture_flag",
            "version": "fact-v1",
            "subject_kind": FactSubjectKind.RECIPE,
            "subject_id": "synthetic-recipe",
            "subject_version": "recipe-v1",
            "catalogue_version": "catalogue-v1",
            "observation": observed(),
        }
        | changes
    )


def line(**changes: Any) -> IngredientLine:
    return IngredientLine.model_validate(
        {
            "line_id": "source-line-1",
            "version": "line-v1",
            "recipe_id": "synthetic-recipe",
            "recipe_version": "recipe-v1",
            "catalogue_version": "catalogue-v1",
            "mapping_status": IngredientMappingStatus.MAPPED,
            "ingredient_id": "synthetic-ingredient",
            "ingredient_version": "ingredient-v1",
            "subingredients_complete": True,
            "gap_reasons": (),
            "evidence": (evidence(),),
        }
        | changes
    )


def coverage(**changes: Any) -> IngredientCoverage:
    return IngredientCoverage.model_validate(
        {
            "coverage_id": "synthetic-coverage",
            "version": "coverage-v1",
            "recipe_id": "synthetic-recipe",
            "recipe_version": "recipe-v1",
            "catalogue_version": "catalogue-v1",
            "lines": (line(),),
            "inventory_complete": True,
            "mapping_complete": True,
            "subingredients_complete": True,
            "gap_reasons": (),
            "evidence": (evidence(),),
        }
        | changes
    )


def candidate_content(**changes: Any) -> dict[str, Any]:
    return {
        "recipe_id": "synthetic-recipe",
        "recipe_version": "recipe-v1",
        "catalogue_version": "catalogue-v1",
        "graph_id": "synthetic-graph",
        "graph_version": "graph-v1",
        "graph_recipe_entity_id": "synthetic-graph-recipe",
        "graph_recipe_reference": FoodEntity(
            entity_id="synthetic-graph-recipe",
            version="graph-entity-v9",
            kind=FoodEntityKind.RECIPE_REFERENCE,
            canonical_name="Synthetic recipe identity fixture",
            catalogue_reference="synthetic-recipe",
            evidence=(evidence(),),
        ),
        "snapshot_id": "synthetic-facts",
        "snapshot_version": "snapshot-v1",
        "ingredient_coverage": coverage(),
        "facts": (fact(),),
        "evidence": (evidence(),),
    } | changes


def candidate(**changes: Any) -> CandidateRecipeFacts:
    return CandidateRecipeFacts.build(candidate_content(**changes))


def context_content(**changes: Any) -> dict[str, Any]:
    return {
        "context_id": "synthetic-context",
        "version": "context-v1",
        "profile_id": "synthetic-profile",
        "profile_version": "profile-v1",
        "workflow": KnowledgeWorkflow.CRAVING_DISCOVERY,
        "expected_kb_id": "synthetic-kb",
        "expected_kb_version": "kb-v1",
        "expected_kb_digest": "1" * 64,
        "expected_graph_id": "synthetic-graph",
        "expected_graph_version": "graph-v1",
        "expected_taxonomy_version": None,
        "expected_catalogue_version": "catalogue-v1",
        "expected_check_catalogue_version": "checks-v1",
        "facts": (
            fact(
                subject_kind=FactSubjectKind.PROFILE,
                subject_id="synthetic-profile",
                subject_version="profile-v1",
                catalogue_version=None,
            ),
        ),
        "evidence": (evidence(),),
    } | changes


def context(**changes: Any) -> RuleContext:
    return RuleContext.build(context_content(**changes))


def independent_digest(data: dict[str, Any]) -> str:
    # Independent encoding of the documented unordered JSON collections, not the
    # implementation's digest/canonicalization helpers or its field introspection.
    def encode(value: Any) -> str:
        if isinstance(value, dict):
            pairs = (json.dumps(key) + ":" + encode(value[key]) for key in sorted(value))
            return "{" + ",".join(pairs) + "}"
        if isinstance(value, list):
            return "[" + ",".join(sorted(encode(item) for item in value)) + "]"
        return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))

    return hashlib.sha256(encode(data).encode("utf-8")).hexdigest()


FACTORIES = (fact, line, coverage, candidate, context)


@pytest.mark.parametrize("factory", FACTORIES)
def test_strict_python_and_camel_json_round_trips(factory: Any) -> None:
    record = factory()
    wire = record.model_dump_json(by_alias=True)
    assert type(record).model_validate_json(wire) == record
    assert TypeAdapter(type(record)).validate_json(wire) == record
    assert type(record).model_validate(record) == record
    assert TypeAdapter(type(record)).validate_python(record) == record
    assert type(record)(**record.model_dump()) == record
    assert "_id" not in wire and "_version" not in wire
    assert '"version"' in wire


@pytest.mark.parametrize("value", [None, 0, False, (), ("synthetic-tag",)])
def test_null_zero_false_and_empty_sets_remain_distinct(value: Any) -> None:
    numeric = type(value) is int
    item = fact(
        observation=observed(
            value=value,
            unit=MeasurementUnit.DIMENSIONLESS if numeric else None,
            complete=value is not None,
        ),
        measurement_basis=MeasurementBasis.AS_RECORDED if numeric else None,
        basis_reference=evidence("basis") if numeric else None,
    )
    restored = VersionedFact.model_validate_json(item.model_dump_json(by_alias=True))
    assert type(restored.observation.value) is type(value)
    assert restored.observation.value == value
    assert restored.observation.complete is (value is not None)
    assert candidate(facts=(item,)).facts[0] == item
    assert candidate(facts=()).facts == ()


def test_incomplete_nonnull_fact_and_profile_false_do_not_become_missing() -> None:
    item = fact(observation=observed(value=(), complete=False))
    assert not candidate(facts=(item,)).facts[0].observation.complete
    present = context()
    missing = context(facts=())
    null_fact = present.facts[0].model_copy(
        update={"observation": observed(value=None, complete=False)}
    )
    null = context(facts=(null_fact,))
    assert present.facts[0].observation.value is False
    assert missing.facts == () and null.facts[0].observation.value is None
    assert len({present.content_digest, missing.content_digest, null.content_digest}) == 3


@pytest.mark.parametrize("factory", FACTORIES)
@pytest.mark.parametrize("evidence_value", [(), (evidence(), evidence())])
def test_missing_or_duplicate_fact_record_evidence_is_rejected(
    factory: Any, evidence_value: Any
) -> None:
    with pytest.raises(ValidationError):
        if factory is fact:
            factory(observation=observed().model_copy(update={"evidence": evidence_value}))
        else:
            factory(evidence=evidence_value)


@pytest.mark.parametrize(
    "changes",
    [
        {"fact_id": "different-fact"},
        {"subject_kind": FactSubjectKind.PROFILE},
        {"catalogue_version": None},
        {"context_id": "synthetic-context"},
        {"context_version": "context-v1"},
        {"version": " "},
        {"subject_id": "invalid identifier"},
        {"observation": observed().model_copy(update={"complete": "true"})},
        {"observation": observed().model_copy(update={"value": None})},
    ],
)
def test_invalid_standalone_fact_bindings(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        fact(**changes)


@pytest.mark.parametrize("unit", list(MeasurementUnit))
def test_numeric_units_require_an_explicit_versioned_basis(unit: MeasurementUnit) -> None:
    observation = observed(value=0, unit=unit)
    valid = fact(
        observation=observation,
        measurement_basis=MeasurementBasis.AS_RECORDED,
        basis_reference=evidence("basis"),
    )
    assert valid.observation.unit is unit
    for changes in (
        {"measurement_basis": None},
        {"basis_reference": None},
        {"measurement_basis": "PER_BOWL"},
        {"measurement_basis": MeasurementBasis.PER_100_G}
        if unit in (MeasurementUnit.PERCENT, MeasurementUnit.DIMENSIONLESS)
        else {"observation": observation.model_copy(update={"unit": None})},
    ):
        with pytest.raises(ValidationError):
            VersionedFact.model_validate(valid.model_copy(update=changes))


@pytest.mark.parametrize("basis", [MeasurementBasis.PER_100_G, MeasurementBasis.PER_SERVING])
@pytest.mark.parametrize("owner", list(FactSubjectKind))
def test_normalized_measurement_bases_are_food_only(
    basis: MeasurementBasis, owner: FactSubjectKind
):
    data = {
        "subject_kind": owner,
        "catalogue_version": "catalogue-v1"
        if owner in (FactSubjectKind.RECIPE, FactSubjectKind.INGREDIENT)
        else None,
        "observation": observed(value=2, unit=MeasurementUnit.MG),
        "measurement_basis": basis,
        "basis_reference": evidence("basis"),
    }
    if owner is FactSubjectKind.CONTEXT:
        data.update(context_id="synthetic-recipe", context_version="recipe-v1")
    if owner in (FactSubjectKind.RECIPE, FactSubjectKind.INGREDIENT):
        assert fact(**data).measurement_basis is basis
    else:
        with pytest.raises(ValidationError, match="normalized food bases"):
            fact(**data)


@pytest.mark.parametrize("value", [False, "synthetic-label", (), None])
def test_nonnumeric_values_reject_measurement_bases(value: Any) -> None:
    with pytest.raises(ValidationError, match="cannot carry numeric bases"):
        fact(
            observation=observed(value=value, complete=value is not None),
            measurement_basis=MeasurementBasis.AS_RECORDED,
            basis_reference=evidence("basis"),
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 101])
def test_invalid_numeric_values_cannot_hide_in_unchecked_observations(value: Any) -> None:
    invalid = observed().model_copy(update={"value": value, "unit": MeasurementUnit.PERCENT})
    with pytest.raises(ValidationError):
        fact(
            observation=invalid,
            measurement_basis=MeasurementBasis.AS_RECORDED,
            basis_reference=evidence("basis"),
        )


def test_missing_empty_partial_and_unresolved_inventories_are_distinct() -> None:
    missing = coverage(
        lines=None,
        inventory_complete=False,
        mapping_complete=False,
        subingredients_complete=False,
        gap_reasons=(IngredientGapReason.MISSING_INVENTORY,),
    )
    empty = coverage(lines=())
    partial = coverage(
        lines=(), inventory_complete=False, gap_reasons=(IngredientGapReason.INCOMPLETE_INVENTORY,)
    )
    unresolved_line = line(
        mapping_status=IngredientMappingStatus.UNRESOLVED,
        ingredient_id=None,
        ingredient_version=None,
        gap_reasons=(IngredientGapReason.UNRESOLVED_MAPPING,),
    )
    unresolved = coverage(
        lines=(unresolved_line,),
        mapping_complete=False,
        gap_reasons=(IngredientGapReason.UNRESOLVED_MAPPING,),
    )
    assert missing.lines is None
    assert empty.lines == partial.lines == ()
    assert empty.inventory_complete and not partial.inventory_complete
    assert unresolved.inventory_complete and not unresolved.mapping_complete
    digests = {
        candidate(ingredient_coverage=item).content_digest
        for item in (missing, empty, partial, unresolved)
    }
    assert len(digests) == 4
    assert all(not hasattr(item, "eligible") for item in (missing, empty, partial, unresolved))


@pytest.mark.parametrize(
    "changes",
    [
        {"ingredient_id": None},
        {"ingredient_version": None},
        {"mapping_status": IngredientMappingStatus.UNRESOLVED},
        {"subingredients_complete": False},
        {"gap_reasons": (IngredientGapReason.MISSING_INVENTORY,)},
        {"gap_reasons": (IngredientGapReason.UNRESOLVED_MAPPING,) * 2},
    ],
)
def test_contradictory_line_declarations_are_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        line(**changes)


@pytest.mark.parametrize(
    "flag", ["inventory_complete", "mapping_complete", "subingredients_complete"]
)
def test_missing_inventory_never_declares_any_completeness(flag: str) -> None:
    data = coverage(
        lines=None,
        inventory_complete=False,
        mapping_complete=False,
        subingredients_complete=False,
        gap_reasons=(IngredientGapReason.MISSING_INVENTORY,),
    ).model_dump()
    data[flag] = True
    with pytest.raises(ValidationError, match="missing ingredient inventory"):
        IngredientCoverage.model_validate(data)


@pytest.mark.parametrize(
    "changes",
    [
        {"mapping_complete": False},
        {"subingredients_complete": False},
        {"inventory_complete": False},
        {"lines": (line(), line())},
        {"lines": (line(recipe_id="another-recipe"),)},
        {"lines": (line(recipe_version="recipe-v2"),)},
        {"lines": (line(catalogue_version="catalogue-v2"),)},
        {"gap_reasons": (IngredientGapReason.UNRESOLVED_MAPPING,)},
    ],
)
def test_coverage_flags_duplicates_and_bindings(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        coverage(**changes)


def test_nested_subingredients_preserve_gaps_and_duplicate_global_ids_are_rejected() -> None:
    child = line(
        line_id="child-line",
        ingredient_id="synthetic-child",
        subingredients_complete=False,
        gap_reasons=(IngredientGapReason.INCOMPLETE_SUBINGREDIENTS,),
    )
    with pytest.raises(ValidationError, match="incomplete child"):
        line(subingredients=(child,))
    parent = line(
        subingredients=(child,),
        subingredients_complete=False,
        gap_reasons=(IngredientGapReason.INCOMPLETE_SUBINGREDIENTS,),
    )
    partial = coverage(
        lines=(parent,),
        subingredients_complete=False,
        gap_reasons=(IngredientGapReason.INCOMPLETE_SUBINGREDIENTS,),
    )
    assert not candidate(ingredient_coverage=partial).ingredient_coverage.subingredients_complete
    with pytest.raises(ValidationError, match="duplicate ingredient-line"):
        coverage(
            lines=(parent, child),
            subingredients_complete=False,
            gap_reasons=(IngredientGapReason.INCOMPLETE_SUBINGREDIENTS,),
        )
    with pytest.raises(ValidationError, match="duplicate ingredient-line"):
        line(subingredients=(line(),))
    with pytest.raises(ValidationError, match="conflicting ingredient content versions"):
        coverage(lines=(line(), line(line_id="line-2", ingredient_version="ingredient-v2")))


def test_ingredient_facts_require_a_mapped_subject_and_exact_revision() -> None:
    ingredient_fact = fact(
        subject_kind=FactSubjectKind.INGREDIENT,
        subject_id="synthetic-ingredient",
        subject_version="ingredient-v1",
    )
    # The same attribute is distinct for a different explicitly bound owner.
    assert len(candidate(facts=(fact(), ingredient_fact)).facts) == 2
    for changes in ({"subject_id": "missing-ingredient"}, {"subject_version": "ingredient-v2"}):
        with pytest.raises(ValidationError, match="subject identity/version"):
            candidate(facts=(ingredient_fact.model_copy(update=changes),))
    with pytest.raises(ValidationError, match="subject identity/version"):
        candidate(ingredient_coverage=coverage(lines=()), facts=(ingredient_fact,))


@pytest.mark.parametrize(
    "changes",
    [
        {"recipe_id": "different-recipe"},
        {"recipe_version": "recipe-v2"},
        {"catalogue_version": "catalogue-v2"},
        {"graph_recipe_entity_id": "different-node"},
        {
            "graph_recipe_reference": candidate_content()["graph_recipe_reference"].model_copy(
                update={"catalogue_reference": "different-recipe"}
            )
        },
        {
            "graph_recipe_reference": candidate_content()["graph_recipe_reference"].model_copy(
                update={"kind": FoodEntityKind.INGREDIENT}
            )
        },
        {"facts": (fact(subject_id="different-recipe"),)},
        {"facts": (fact(subject_version="recipe-v2"),)},
        {"facts": (fact(catalogue_version="catalogue-v2"),)},
        {"context_id": "synthetic-context"},
        {"schema_version": "candidate-recipe-facts.v2"},
        {"digest_policy_version": "unknown-policy"},
    ],
)
def test_candidate_ownership_graph_metadata_and_versions(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        candidate(**changes)


@pytest.mark.parametrize("second_version", ["fact-v1", "fact-v2"])
@pytest.mark.parametrize("factory", [candidate, context])
def test_duplicate_and_contradictory_fact_revisions_are_rejected(
    second_version: str, factory: Any
) -> None:
    first = factory().facts[0]
    second = first.model_copy(
        update={"version": second_version, "observation": observed(value=True)}
    )
    for item in (first, second):
        with pytest.raises(ValidationError, match="duplicate subject-bound fact"):
            factory(facts=(first, item))


def test_candidate_context_dependent_facts_cannot_move_between_contexts() -> None:
    bound = fact(context_id="synthetic-context", context_version="context-v1")
    data = {"context_id": "synthetic-context", "context_version": "context-v1", "facts": (bound,)}
    assert candidate(**data).facts[0].context_id == "synthetic-context"
    for changes in ({"context_id": "other-context"}, {"context_version": "context-v2"}):
        with pytest.raises(ValidationError, match="context identity/version"):
            candidate(**(data | changes))
    with pytest.raises(ValidationError, match="context identity/version"):
        candidate(facts=(bound,))


def test_context_facts_require_exact_profile_or_context_owners() -> None:
    context_fact = fact(
        subject_kind=FactSubjectKind.CONTEXT,
        subject_id="synthetic-context",
        subject_version="context-v1",
        catalogue_version=None,
        context_id="synthetic-context",
        context_version="context-v1",
    )
    assert len(context(facts=(*context().facts, context_fact)).facts) == 2
    with pytest.raises(ValidationError):
        context(facts=(fact(),))
    for changes in ({"profile_id": "other-profile"}, {"profile_version": "profile-v2"}):
        with pytest.raises(ValidationError, match="subject identity/version"):
            context(**changes)
    for changes in ({"context_id": "other-context"}, {"version": "context-v2"}):
        with pytest.raises(ValidationError, match="subject identity/version"):
            context(facts=(context_fact,), **changes)
    for changes in ({"context_id": None, "context_version": None}, {"context_id": "other"}):
        with pytest.raises(ValidationError, match="own context identity/version"):
            VersionedFact.model_validate(context_fact.model_copy(update=changes))


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "digest_policy_version",
        "workflow_policy_version",
        "evaluator_policy_version",
    ],
)
def test_unknown_context_policy_versions_are_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        context(**{field: "unknown-v99"})


@pytest.mark.parametrize("workflow", list(KnowledgeWorkflow))
def test_context_preserves_workflow_and_explicit_taxonomy_absence(workflow: KnowledgeWorkflow):
    record = context(workflow=workflow)
    assert record.workflow is workflow and record.expected_taxonomy_version is None
    changed = context(workflow=workflow, expected_taxonomy_version="taxonomy-v1")
    assert changed.content_digest != record.content_digest
    with pytest.raises(ValidationError):
        RuleContext.build(
            {
                key: value
                for key, value in context_content().items()
                if key != "expected_taxonomy_version"
            }
        )


@pytest.mark.parametrize("factory", FACTORIES)
def test_frozen_models_nested_records_and_collections(factory: Any) -> None:
    record = factory()
    name = next(iter(type(record).model_fields))
    with pytest.raises(ValidationError, match="frozen_instance"):
        setattr(record, name, "changed")
    if factory in (candidate, context):
        with pytest.raises(ValidationError, match="frozen_instance"):
            record.facts[0].observation.complete = False
        assert type(record.facts) is tuple
    if factory is candidate:
        with pytest.raises(ValidationError, match="frozen_instance"):
            record.ingredient_coverage.lines[0].ingredient_id = "changed"


@pytest.mark.parametrize("factory", [candidate, context])
def test_digest_matches_independent_encoder_and_input_is_untouched(factory: Any) -> None:
    content_factory = candidate_content if factory is candidate else context_content
    data = content_factory()
    original = repr(data)
    target: Any = CandidateRecipeFacts if factory is candidate else RuleContext
    result = target.build(data)
    assert repr(data) == original and "content_digest" not in data
    body = result.model_dump(mode="json", by_alias=True, exclude={"content_digest"})
    assert result.content_digest == independent_digest(body)
    assert type(result).build(result, expected_digest=result.content_digest) == result


@pytest.mark.parametrize("factory", [candidate, context])
@pytest.mark.parametrize("digest", [None, "0" * 64, "invalid", "A" * 64, 1])
def test_supplied_digest_is_never_silently_recomputed(factory: Any, digest: Any) -> None:
    result = factory()
    for key in ("content_digest", "contentDigest"):
        data = result.model_dump(exclude={"content_digest"}) | {key: digest}
        with pytest.raises(ValidationError):
            type(result).build(data)
    with pytest.raises(ValidationError):
        type(result).model_validate(result.model_copy(update={"content_digest": digest}))


@pytest.mark.parametrize("factory", [candidate, context])
def test_old_independent_pin_rejects_valid_revision_and_json_tampering(factory: Any) -> None:
    original = factory()
    data = original.model_dump(exclude={"content_digest"})
    field = "snapshot_version" if factory is candidate else "version"
    data[field] = "changed-release"
    changed = type(original).build(data)
    assert changed.content_digest != original.content_digest
    with pytest.raises(ValidationError, match="digest mismatch"):
        type(original).build(data, expected_digest=original.content_digest)
    wire = json.loads(original.model_dump_json(by_alias=True))
    wire["snapshotVersion" if factory is candidate else "version"] = "tampered"
    with pytest.raises(ValidationError, match="digest mismatch"):
        type(original).model_validate_json(json.dumps(wire))


def test_digest_covers_basis_identity_values_and_all_candidate_content_groups() -> None:
    numeric = fact(
        observation=observed(value=2, unit=MeasurementUnit.MG),
        measurement_basis=MeasurementBasis.PER_100_G,
        basis_reference=evidence("basis"),
    )
    original = candidate(facts=(numeric,))
    mutations = [
        {"graph_id": "changed-graph"},
        {"graph_version": "graph-v2"},
        {"snapshot_id": "changed-snapshot"},
        {"snapshot_version": "snapshot-v2"},
        {"context_id": "synthetic-context", "context_version": "context-v1"},
        {"evidence": (evidence("revised-snapshot-source"),)},
        {
            "graph_recipe_reference": original.graph_recipe_reference.model_copy(
                update={"version": "entity-v10"}
            )
        },
        {"ingredient_coverage": coverage(version="coverage-v2")},
        {"facts": (numeric.model_copy(update={"version": "fact-v2"}),)},
        {
            "facts": (
                numeric.model_copy(update={"measurement_basis": MeasurementBasis.PER_SERVING}),
            )
        },
        {"facts": (numeric.model_copy(update={"basis_reference": evidence("other-basis")}),)},
        {
            "facts": (
                numeric.model_copy(
                    update={"observation": observed(value=2.0, unit=MeasurementUnit.MG)}
                ),
            )
        },
    ]
    for changes in mutations:
        body = original.model_dump(exclude={"content_digest"}) | changes
        assert CandidateRecipeFacts.build(body).content_digest != original.content_digest
        with pytest.raises(ValidationError, match="digest mismatch"):
            CandidateRecipeFacts.build(body, expected_digest=original.content_digest)


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_kb_id", "changed-kb"),
        ("expected_kb_version", "kb-v2"),
        ("expected_kb_digest", "2" * 64),
        ("expected_graph_id", "changed-graph"),
        ("expected_graph_version", "graph-v2"),
        ("expected_taxonomy_version", "taxonomy-v1"),
        ("expected_catalogue_version", "catalogue-v2"),
        ("expected_check_catalogue_version", "checks-v2"),
        ("workflow", KnowledgeWorkflow.PLANNED_SWAP),
    ],
)
def test_context_digest_binds_every_release_expectation(field: str, value: Any) -> None:
    original = context()
    assert context(**{field: value}).content_digest != original.content_digest
    data = original.model_dump(exclude={"content_digest"}) | {field: value}
    with pytest.raises(ValidationError):
        RuleContext.build(data, expected_digest=original.content_digest)


@pytest.mark.parametrize("factory", [candidate, context])
def test_digest_is_independent_of_fact_evidence_and_categorical_set_order(factory: Any) -> None:
    original_fact = factory().facts[0]
    refs = (evidence("a"), evidence("b"))
    first = original_fact.model_copy(
        update={"observation": observed(value=("a", "b"), evidence=refs)}
    )
    second = original_fact.model_copy(
        update={
            "fact_id": "second_flag",
            "observation": observed(fact_id="second_flag", value=True),
        }
    )
    baseline = factory(facts=(first, second), evidence=refs)
    for fact_order in permutations((first, second)):
        for evidence_order in permutations(refs):
            changed = factory(facts=fact_order, evidence=evidence_order)
            assert changed.content_digest == baseline.content_digest
    reordered_first = first.model_copy(
        update={"observation": observed(value=("b", "a"), evidence=tuple(reversed(refs)))}
    )
    assert (
        factory(facts=(second, reordered_first), evidence=tuple(reversed(refs))).content_digest
        == baseline.content_digest
    )


def test_line_and_subingredient_order_does_not_change_digest() -> None:
    child = line(line_id="child", ingredient_id="synthetic-child")
    parent = line(subingredients=(child,))
    second = line(line_id="second", ingredient_id="synthetic-second")
    original = candidate(ingredient_coverage=coverage(lines=(parent, second)))
    reordered = candidate(ingredient_coverage=coverage(lines=(second, parent)))
    assert original.content_digest == reordered.content_digest


@pytest.mark.parametrize("factory", FACTORIES)
def test_production_evidence_and_conflicting_metadata_are_rejected(factory: Any) -> None:
    conflicting = evidence(source="Contradictory SYNTHETIC source")
    with pytest.raises(ValidationError):
        if factory is fact:
            factory(
                basis_reference=conflicting,
                measurement_basis=MeasurementBasis.AS_RECORDED,
                observation=observed(value=2, unit=MeasurementUnit.MG),
            )
        elif factory is line:
            factory(subingredients=(line(line_id="child", evidence=(conflicting,)),))
        else:
            factory(evidence=(conflicting,))
    production = evidence(environment=RuleEnvironment.PRODUCTION)
    with pytest.raises(ValidationError, match="SYNTHETIC"):
        if factory is fact:
            factory(observation=observed(evidence=(production,)))
        else:
            factory(evidence=(production,))


def forged(enum: type[StrEnum], token: str) -> Any:
    value = str.__new__(enum, token)
    object.__setattr__(value, "_name_", token)
    object.__setattr__(value, "_value_", token)
    return value


@pytest.mark.parametrize("mode", ["copy", "construct"])
@pytest.mark.parametrize("valid_token", [True, False])
@pytest.mark.parametrize(
    "location",
    ["subject", "basis", "mapping", "gap", "workflow", "unit", "environment", "graph_kind"],
)
def test_counterfeit_enums_reject_even_legitimate_looking_tokens(
    mode: str, valid_token: bool, location: str
) -> None:
    def unchecked(record: Any, changes: dict[str, Any]) -> Any:
        return (
            record.model_copy(update=changes)
            if mode == "copy"
            else type(record).model_construct(**(vars(record) | changes))
        )

    if location in ("subject", "basis", "unit", "environment"):
        record = fact()
        enum: Any = {
            "subject": FactSubjectKind,
            "basis": MeasurementBasis,
            "unit": MeasurementUnit,
            "environment": RuleEnvironment,
        }[location]
        token = {
            "subject": "RECIPE",
            "basis": "AS_RECORDED",
            "unit": "mg",
            "environment": "SYNTHETIC",
        }[location]
        fake = forged(enum, token if valid_token else "UNDECLARED")
        if location == "subject":
            invalid = unchecked(record, {"subject_kind": fake})
        elif location == "basis":
            invalid = unchecked(record, {"measurement_basis": fake})
        elif location == "unit":
            invalid = unchecked(
                record, {"observation": unchecked(record.observation, {"unit": fake})}
            )
        else:
            invalid = unchecked(
                record,
                {
                    "observation": unchecked(
                        record.observation,
                        {"evidence": (unchecked(evidence(), {"environment": fake}),)},
                    )
                },
            )
        target: Any = VersionedFact
    elif location in ("mapping", "gap"):
        enum = IngredientMappingStatus if location == "mapping" else IngredientGapReason
        token = "MAPPED" if location == "mapping" else "UNRESOLVED_MAPPING"
        fake = forged(enum, token if valid_token else "UNDECLARED")
        invalid = unchecked(
            line(), {"mapping_status": fake} if location == "mapping" else {"gap_reasons": (fake,)}
        )
        target = IngredientLine
    elif location == "workflow":
        invalid = unchecked(
            context(),
            {
                "workflow": forged(
                    KnowledgeWorkflow, "CRAVING_DISCOVERY" if valid_token else "UNDECLARED"
                )
            },
        )
        target = RuleContext
    else:
        record = candidate()
        invalid = unchecked(
            record,
            {
                "graph_recipe_reference": unchecked(
                    record.graph_recipe_reference,
                    {
                        "kind": forged(
                            FoodEntityKind, "RECIPE_REFERENCE" if valid_token else "UNDECLARED"
                        )
                    },
                )
            },
        )
        target = CandidateRecipeFacts
    with pytest.raises(ValidationError):
        target.model_validate(invalid)
    with pytest.raises(ValidationError):
        TypeAdapter(target).validate_python(invalid)
    if target in (CandidateRecipeFacts, RuleContext):
        with pytest.raises(ValidationError):
            target.build(invalid)


_container_calls: list[str] = []


class HiddenDict(dict[str, Any]):
    def items(self) -> Any:
        _container_calls.append("items")
        return iter(())

    def __iter__(self) -> Iterator[str]:
        _container_calls.append("dict.__iter__")
        return iter(())

    def __or__(self, other: Any) -> Any:
        _container_calls.append("dict.__or__")
        return {}


class HiddenTuple(tuple[Any, ...]):
    def __iter__(self) -> Iterator[Any]:
        _container_calls.append("tuple.__iter__")
        return iter(())


class HiddenList(list[Any]):
    def __iter__(self) -> Iterator[Any]:
        _container_calls.append("list.__iter__")
        return iter(())


@pytest.mark.parametrize("factory", FACTORIES)
@pytest.mark.parametrize("entry", ["model", "adapter", "constructor"])
def test_hostile_root_dicts_are_rejected_before_methods(factory: Any, entry: str) -> None:
    record = factory()
    payload = HiddenDict(record.model_dump())
    _container_calls.clear()
    with pytest.raises(ValidationError, match="custom container"):
        if entry == "model":
            type(record).model_validate(payload)
        elif entry == "adapter":
            TypeAdapter(type(record)).validate_python(payload)
        else:
            # Python ** expansion invokes mapping methods before the constructor;
            # use the validating constructor's nested field instead.
            data = record.model_dump()
            if factory is fact:
                data["observation"]["evidence"] = HiddenTuple(record.observation.evidence)
            else:
                data["evidence"] = HiddenTuple(record.evidence)
            type(record)(**data)
    assert not _container_calls


@pytest.mark.parametrize("factory", FACTORIES)
@pytest.mark.parametrize("container", [HiddenDict, HiddenTuple, HiddenList])
@pytest.mark.parametrize("storage", ["fields", "extras", "nested"])
def test_hostile_nested_and_unchecked_storage_is_rejected_before_methods(
    factory: Any, container: Any, storage: str
) -> None:
    record = factory()
    invalid = record.model_copy()
    if storage == "fields":
        payload = container(vars(record)) if container is HiddenDict else container((record,))
        object.__setattr__(
            invalid, "__dict__", payload
        ) if container is HiddenDict else object.__setattr__(invalid, "__pydantic_extra__", payload)
    elif storage == "extras":
        payload = (
            container({"unexpected": record}) if container is HiddenDict else container((record,))
        )
        object.__setattr__(invalid, "__pydantic_extra__", payload)
    else:
        references = record.observation.evidence if factory is fact else record.evidence
        payload = (
            container({"unexpected": record}) if container is HiddenDict else container(references)
        )
        if factory is fact:
            invalid = record.model_copy(
                update={"observation": record.observation.model_copy(update={"evidence": payload})}
            )
        else:
            invalid = record.model_copy(update={"evidence": payload})
    _container_calls.clear()
    with pytest.raises(ValidationError, match="custom container"):
        type(record).model_validate(invalid)
    assert not _container_calls
    if factory in (candidate, context):
        with pytest.raises(ValidationError, match="custom container"):
            type(record).build(invalid)
        assert not _container_calls


@pytest.mark.parametrize("factory", FACTORIES)
@pytest.mark.parametrize("mode", ["copy", "construct"])
def test_unchecked_fields_are_preserved_for_validation(factory: Any, mode: str) -> None:
    original = factory()
    changes = {"unexpected": "must not disappear"}
    invalid = (
        original.model_copy(update=changes)
        if mode == "copy"
        else type(original).model_construct(**vars(original))
    )
    if mode == "construct":
        # model_construct drops forbidden extras itself; retain an actual unchecked
        # field in storage, as model_copy(update=...) does, before testing the boundary.
        vars(invalid).update(changes)
    with pytest.raises(ValidationError):
        type(original).model_validate(invalid)
    if factory in (candidate, context):
        with pytest.raises(ValidationError):
            type(original).build(invalid)
    assert original == factory()


@pytest.mark.parametrize("factory", FACTORIES)
def test_direct_alias_collisions_and_nested_unchecked_copies_are_rejected(factory: Any) -> None:
    original = factory()
    field = next(name for name in type(original).model_fields if "_" in name)
    alias = type(original).model_fields[field].alias
    assert alias is not None
    bad = original.model_dump() | {alias: getattr(original, field)}
    with pytest.raises(ValidationError, match="colliding DTO"):
        type(original).model_validate(bad)
    with pytest.raises(ValidationError, match="colliding DTO"):
        type(original).model_validate_json(
            json.dumps(original.model_dump(mode="json") | {alias: getattr(original, field)})
        )
    if factory in (candidate, context):
        with pytest.raises(ValidationError, match="colliding DTO"):
            type(original).build(bad)


class ExtraFact(VersionedFact):
    model_config = ConfigDict(extra="allow", alias_generator=lambda name: "input_" + name)


class AliasedCandidate(CandidateRecipeFacts):
    content_digest: str = Field(alias="digest")


@pytest.mark.parametrize("mode", ["copy", "construct"])
@pytest.mark.parametrize("shadow_key", ["subject_kind", "input_subject_kind"])
def test_subclass_extra_field_collisions_cannot_hide_fact_ownership(
    mode: str, shadow_key: str
) -> None:
    values = {"input_" + name: value for name, value in vars(fact()).items()}
    malicious = ExtraFact.model_construct(**values)
    object.__setattr__(malicious, "__pydantic_extra__", {shadow_key: FactSubjectKind.PROFILE})
    if mode == "copy":
        malicious = malicious.model_copy()
    for validate in (VersionedFact.model_validate, ExtraFact.model_validate):
        with pytest.raises(ValidationError, match="colliding DTO"):
            validate(malicious)
    with pytest.raises(ValidationError, match="colliding DTO"):
        candidate(facts=(malicious,))


def test_inherited_digest_alias_cannot_hide_tampering() -> None:
    original = candidate()
    data: dict[str, Any] = vars(original) | {"content_digest": "0" * 64}
    malicious = AliasedCandidate.model_construct(**data)
    vars(malicious)["contentDigest"] = original.content_digest
    for validate in (
        CandidateRecipeFacts.model_validate,
        AliasedCandidate.model_validate,
        CandidateRecipeFacts.build,
    ):
        with pytest.raises(ValidationError, match="colliding DTO"):
            validate(malicious)


@pytest.mark.parametrize("factory", [candidate, context])
def test_both_digest_aliases_and_cyclic_unchecked_content_are_rejected(factory: Any) -> None:
    original = factory()
    with pytest.raises(ValidationError, match="colliding DTO"):
        type(original).build(original.model_dump() | {"contentDigest": original.content_digest})
    cyclic: dict[str, Any] = original.model_dump()
    cyclic["unexpected"] = cyclic
    with pytest.raises(ValidationError):
        type(original).build(cyclic)


@pytest.mark.parametrize("factory", FACTORIES)
def test_python_lists_are_not_normalized_into_tuple_collections(factory: Any) -> None:
    record = factory()
    data = record.model_dump()
    if factory is fact:
        data["observation"]["evidence"] = list(record.observation.evidence)
    else:
        data["evidence"] = list(record.evidence)
    with pytest.raises(ValidationError):
        type(record).model_validate(data)


def test_no_execution_api_or_changed_phase_one_exports() -> None:
    from savora_ai import schemas

    assert schemas.FactObservation is FactObservation
    for record in (fact(), line(), coverage(), candidate(), context()):
        assert not hasattr(record, "eligible") and not hasattr(record, "status")
    assert "CandidateRecipeFacts" not in schemas.__all__


@pytest.mark.parametrize("mode", ["copy", "construct"])
@pytest.mark.parametrize("location", ["observation", "line", "coverage", "graph", "profile"])
def test_nested_unchecked_defects_reach_enclosing_snapshot_validation(
    mode: str, location: str
) -> None:
    def unchecked(record: Any, changes: dict[str, Any]) -> Any:
        if mode == "copy":
            return record.model_copy(update=changes)
        return type(record).model_construct(**(vars(record) | changes))

    if location == "profile":
        outer: Any = context()
        owner = outer.facts[0]
        invalid = unchecked(
            outer, {"facts": (unchecked(owner, {"subject_version": "stale-profile"}),)}
        )
    else:
        outer = candidate()
        if location == "observation":
            invalid_fact = unchecked(
                outer.facts[0],
                {"observation": unchecked(outer.facts[0].observation, {"evidence": ()})},
            )
            changes = {"facts": (invalid_fact,)}
        elif location == "line":
            invalid_line = unchecked(line(), {"ingredient_id": None})
            changes = {"ingredient_coverage": unchecked(coverage(), {"lines": (invalid_line,)})}
        elif location == "coverage":
            changes = {"ingredient_coverage": unchecked(coverage(), {"lines": None})}
        else:
            changes = {
                "graph_recipe_reference": unchecked(
                    outer.graph_recipe_reference, {"catalogue_reference": "wrong-recipe"}
                )
            }
        invalid = unchecked(outer, changes)
    for validate in (type(outer).model_validate, TypeAdapter(type(outer)).validate_python):
        with pytest.raises(ValidationError):
            validate(invalid)
    with pytest.raises(ValidationError):
        type(outer).build(invalid)


@pytest.mark.parametrize("value", [0, 1, "true", "false", None])
def test_completeness_flags_remain_strict_booleans(value: Any) -> None:
    for factory, flag in (
        (line, "subingredients_complete"),
        (coverage, "inventory_complete"),
        (coverage, "mapping_complete"),
    ):
        with pytest.raises(ValidationError):
            factory(**{flag: value})


@pytest.mark.parametrize("factory", FACTORIES)
@pytest.mark.parametrize("revision", [None, "", "   ", 1, False])
def test_content_and_record_versions_are_explicit_nonblank_strings(
    factory: Any, revision: Any
) -> None:
    field = "snapshot_version" if factory is candidate else "version"
    with pytest.raises(ValidationError):
        factory(**{field: revision})


@pytest.mark.parametrize("enum_field", ["subject", "basis", "mapping", "gap", "workflow"])
def test_python_enum_tokens_require_members_while_json_uses_tokens(enum_field: str) -> None:
    if enum_field == "subject":
        record: Any = fact()
        changes = {"subject_kind": "RECIPE"}
    elif enum_field == "basis":
        record = fact(
            observation=observed(value=0, unit=MeasurementUnit.DIMENSIONLESS),
            measurement_basis=MeasurementBasis.AS_RECORDED,
            basis_reference=evidence("basis"),
        )
        changes = {"measurement_basis": "AS_RECORDED"}
    elif enum_field == "mapping":
        record = line()
        changes = {"mapping_status": "MAPPED"}
    elif enum_field == "gap":
        record = coverage(
            inventory_complete=False,
            gap_reasons=(IngredientGapReason.INCOMPLETE_INVENTORY,),
        )
        changes = {"gap_reasons": ("INCOMPLETE_INVENTORY",)}
    else:
        record = context()
        changes = {"workflow": "CRAVING_DISCOVERY"}
    with pytest.raises(ValidationError):
        type(record).model_validate(record.model_copy(update=changes))
    assert type(record).model_validate_json(record.model_dump_json(by_alias=True)) == record


def test_nested_unresolved_mappings_and_incomplete_expansion_have_independent_flags() -> None:
    unresolved_child = line(
        line_id="child",
        mapping_status=IngredientMappingStatus.UNRESOLVED,
        ingredient_id=None,
        ingredient_version=None,
        gap_reasons=(IngredientGapReason.UNRESOLVED_MAPPING,),
    )
    parent = line(subingredients=(unresolved_child,))
    declared = coverage(
        lines=(parent,),
        mapping_complete=False,
        gap_reasons=(IngredientGapReason.UNRESOLVED_MAPPING,),
    )
    assert declared.subingredients_complete and not declared.mapping_complete
    restored = IngredientCoverage.model_validate_json(declared.model_dump_json(by_alias=True))
    assert restored == declared and restored.lines is not None
    assert restored.lines[0].subingredients[0].ingredient_id is None
    assert candidate(ingredient_coverage=restored).ingredient_coverage == declared


def test_global_line_ids_and_provenance_are_checked_across_sibling_branches() -> None:
    child = line(line_id="shared-child", ingredient_id="synthetic-child")
    first = line(subingredients=(child,))
    second = line(
        line_id="second-parent", ingredient_id="synthetic-parent-2", subingredients=(child,)
    )
    with pytest.raises(ValidationError, match="duplicate ingredient-line"):
        coverage(lines=(first, second))
    incompatible = line(
        line_id="other-child",
        ingredient_id="synthetic-other",
        evidence=(evidence(source="Conflicting synthetic metadata"),),
    )
    with pytest.raises(ValidationError, match="conflicting evidence"):
        candidate(ingredient_coverage=coverage(lines=(first, incompatible)))


@pytest.mark.parametrize("factory", [candidate, context])
def test_valid_json_schema_and_absent_digest_behavior(factory: Any) -> None:
    record = factory()
    schema = type(record).model_json_schema()
    assert schema["additionalProperties"] is False
    assert "contentDigest" in schema["required"]
    body = record.model_dump(exclude={"content_digest"})
    assert type(record).build(body) == record
    with pytest.raises(ValidationError):
        type(record).model_validate(body)
    wire_body = record.model_dump(mode="json", by_alias=True, exclude={"content_digest"})
    with pytest.raises(ValidationError):
        type(record).model_validate_json(json.dumps(wire_body))


_DUPLICATE_JSON_FIELDS = (
    (candidate, "mappingStatus", "UNRESOLVED"),
    (candidate, "contentDigest", "0" * 64),
    (candidate, "subjectId", "wrong-owner"),
    (candidate, "complete", False),
    (context, "contentDigest", "0" * 64),
    (context, "profileVersion", "wrong-version"),
    (context, "workflow", "UNDECLARED"),
    (context, "expectedKbVersion", "wrong-version"),
)


def duplicated_json(
    record: Any, key: str, first: Any, *, identical: bool = False, escaped: bool = False
) -> str:
    # Author raw member pairs; a Python dict/json.dumps cannot preserve duplicate keys.
    wire = record.model_dump_json(by_alias=True)
    quoted_key = json.dumps(key)
    position = wire.index(quoted_key + ":")
    tail = wire[position + len(quoted_key) + 1 :]
    final, _ = json.JSONDecoder().raw_decode(tail)
    first_key = '"\\u' + format(ord(key[0]), "04x") + key[1:] + '"' if escaped else quoted_key
    extra = first_key + ":" + json.dumps(final if identical else first) + ","
    return wire[:position] + extra + wire[position:]


@pytest.mark.parametrize("factory,key,first", _DUPLICATE_JSON_FIELDS)
@pytest.mark.parametrize("identical", [False, True])
@pytest.mark.parametrize("escaped", [False, True])
@pytest.mark.parametrize("entry", ["model", "adapter"])
def test_strict_json_ingress_rejects_root_nested_and_escaped_duplicate_keys(
    factory: Any, key: str, first: Any, identical: bool, escaped: bool, entry: str
) -> None:
    record = factory()
    raw = duplicated_json(record, key, first, identical=identical, escaped=escaped)
    target = type(record) if entry == "model" else TypeAdapter(type(record))
    with pytest.raises(ValidationError, match="duplicate JSON object member") as caught:
        validate_contract_json(target, raw)
    assert caught.value.title == "StrictJsonIngress"


@pytest.mark.parametrize("factory,key,first", _DUPLICATE_JSON_FIELDS)
@pytest.mark.parametrize("entry", ["native_model", "native_adapter", "native_schema"])
def test_native_json_bypass_routes_remain_unsupported_for_untrusted_input(
    factory: Any, key: str, first: Any, entry: str
) -> None:
    record = factory()
    raw = duplicated_json(record, key, first)
    # Evidence for the documented boundary: these unchanged native methods still
    # discard duplicates. Do not claim a model override protects arbitrary adapters.
    if entry == "native_model":
        accepted = type(record).model_validate_json(raw)
    elif entry == "native_adapter":
        accepted = TypeAdapter(type(record)).validate_json(raw)
    else:
        accepted = type(record).__pydantic_validator__.validate_json(raw)
    assert accepted == record
    with pytest.raises(ValidationError, match="duplicate JSON"):
        validate_contract_json(type(record), raw)


@pytest.mark.parametrize("factory", FACTORIES)
@pytest.mark.parametrize("container", [str, bytes, bytearray])
@pytest.mark.parametrize("entry", ["model", "adapter"])
def test_strict_json_ingress_preserves_valid_dtos_and_native_wire_semantics(
    factory: Any, container: Any, entry: str
) -> None:
    record = factory()
    text = record.model_dump_json(by_alias=True)
    raw = text if container is str else container(text.encode("utf-8"))
    target = type(record) if entry == "model" else TypeAdapter(type(record))
    assert validate_contract_json(target, raw) == record


@pytest.mark.parametrize("value", [0, 0.0, False, None, [], {}, [0, False, None], {"value": "NaN"}])
def test_strict_json_ingress_preserves_legitimate_scalar_and_container_values(value: Any) -> None:
    result = validate_contract_json(TypeAdapter(object), json.dumps(value))
    assert type(result) is type(value) and result == value


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e400", "-1e400"])
@pytest.mark.parametrize("nested", [False, True])
def test_strict_json_ingress_rejects_nonfinite_constants_and_numeric_overflow(
    token: str, nested: bool
) -> None:
    raw = '{"nested":[{"value":' + token + "}]}" if nested else token
    with pytest.raises(ValidationError) as caught:
        validate_contract_json(TypeAdapter(object), raw)
    assert caught.value.title == "StrictJsonIngress"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "{",
        '{"a":1,}',
        '{"a":01}',
        "[1,]",
        "true trailing",
        '{"a": /* comment */ 1}',
        '"unterminated',
        "\ufeff{}",
        b"\xff",
        b"\xff\xfe{\x00}\x00",
    ],
)
def test_strict_json_ingress_rejects_invalid_grammar_and_non_utf8(raw: Any) -> None:
    with pytest.raises(ValidationError) as caught:
        validate_contract_json(TypeAdapter(object), raw)
    assert caught.value.title == "StrictJsonIngress"


@pytest.mark.parametrize("container", [str, bytes, bytearray])
def test_strict_json_ingress_size_limit_accepts_boundary_and_rejects_overflow(
    container: Any,
) -> None:
    text = "null" + " " * (STRICT_JSON_MAX_BYTES - 4)
    raw = text if container is str else container(text.encode("utf-8"))
    assert validate_contract_json(TypeAdapter(object), raw) is None
    oversized = text + " " if container is str else container((text + " ").encode("utf-8"))
    with pytest.raises(ValidationError, match="1 MiB"):
        validate_contract_json(TypeAdapter(object), oversized)


def test_strict_json_ingress_limits_utf8_bytes_not_only_character_count() -> None:
    raw = '"' + "é" * (STRICT_JSON_MAX_BYTES // 2 - 1) + '"'
    assert len(raw.encode("utf-8")) == STRICT_JSON_MAX_BYTES
    assert validate_contract_json(str, raw) == "é" * (STRICT_JSON_MAX_BYTES // 2 - 1)
    with pytest.raises(ValidationError, match="1 MiB"):
        validate_contract_json(str, raw[:-1] + 'é"')


def test_strict_json_ingress_depth_limit_and_quoted_delimiters() -> None:
    at_limit = "[" * STRICT_JSON_MAX_DEPTH + "0" + "]" * STRICT_JSON_MAX_DEPTH
    accepted = validate_contract_json(TypeAdapter(object), at_limit)
    for _ in range(STRICT_JSON_MAX_DEPTH):
        assert type(accepted) is list
        accepted = accepted[0]
    assert accepted == 0
    with pytest.raises(ValidationError, match="64-level"):
        validate_contract_json(TypeAdapter(object), "[" + at_limit + "]")
    value = {"quoted": '\\"' + "[{" * 100 + '\\"' + "}]" * 100}
    assert validate_contract_json(TypeAdapter(object), json.dumps(value)) == value


class HostileJsonString(str):
    def __len__(self) -> int:
        _container_calls.append("string.__len__")
        return 0

    def encode(self, *args: Any, **kwargs: Any) -> bytes:
        _container_calls.append("string.encode")
        return b"{}"


class HostileJsonBytes(bytes):
    def decode(self, *args: Any, **kwargs: Any) -> str:
        _container_calls.append("bytes.decode")
        return "{}"


class HostileJsonBytearray(bytearray):
    def decode(self, *args: Any, **kwargs: Any) -> str:
        _container_calls.append("bytearray.decode")
        return "{}"


@pytest.mark.parametrize(
    "raw",
    [
        None,
        {},
        [],
        1,
        memoryview(b"{}"),
        HostileJsonString("{}"),
        HostileJsonBytes(b"{}"),
        HostileJsonBytearray(b"{}"),
    ],
)
def test_strict_json_ingress_rejects_unsupported_input_before_custom_methods(raw: Any) -> None:
    _container_calls.clear()
    with pytest.raises(ValidationError, match="built-in"):
        validate_contract_json(TypeAdapter(object), raw)
    assert not _container_calls


@pytest.mark.parametrize("factory", [candidate, context])
def test_strict_json_ingress_keeps_existing_alias_digest_and_python_guards(factory: Any) -> None:
    record = factory()
    data = record.model_dump(mode="json", by_alias=True)
    field = "recipe_id" if factory is candidate else "profile_id"
    data[field] = getattr(record, field)
    with pytest.raises(ValidationError, match="colliding DTO"):
        validate_contract_json(type(record), json.dumps(data))
    wire = record.model_dump_json(by_alias=True).replace(record.content_digest, "0" * 64, 1)
    with pytest.raises(ValidationError, match="digest mismatch"):
        validate_contract_json(type(record), wire)
    # A duplicate discarded by an earlier parser cannot be recovered by Python validation.
    raw = duplicated_json(record, "contentDigest", "0" * 64)
    normalized = json.loads(raw)
    accepted = type(record).model_validate_json(json.dumps(normalized))
    assert accepted == record
    with pytest.raises(ValidationError, match="duplicate JSON"):
        validate_contract_json(type(record), raw)


@pytest.mark.parametrize("entry", ["model", "adapter"])
def test_shared_ingress_protects_phase_one_two_dtos_without_modifying_their_schemas(
    entry: str,
) -> None:
    from test_knowledge_base import content
    from test_knowledge_contracts import rule, trace

    from savora_ai.core.reasoning.kb import build_knowledge_snapshot
    from savora_ai.schemas.knowledge import RuleReference

    kb = build_knowledge_snapshot(content())
    records = (
        (RuleReference(rule_id="synthetic-rule", version="1"), "version", "wrong"),
        (evidence(), "environment", "PRODUCTION"),
        (observed(), "complete", False),
        (rule(), "severity", "SOFT"),
        (trace(), "candidateId", "wrong"),
        (kb.graph.entities[0], "entityId", "wrong"),
        (kb.graph, "graphId", "wrong"),
        (kb, "contentDigest", "0" * 64),
    )
    for record, field, first in records:
        target = type(record) if entry == "model" else TypeAdapter(type(record))
        assert validate_contract_json(target, record.model_dump_json(by_alias=True)) == record
        with pytest.raises(ValidationError, match="duplicate JSON"):
            validate_contract_json(target, duplicated_json(record, field, first))


def test_strict_json_ingress_protects_dtos_nested_in_public_adapter_collections() -> None:
    record = candidate()
    target = TypeAdapter(tuple[CandidateRecipeFacts, ...])
    assert validate_contract_json(target, "[" + record.model_dump_json(by_alias=True) + "]") == (
        record,
    )
    bad = "[" + duplicated_json(record, "mappingStatus", "UNRESOLVED") + "]"
    with pytest.raises(ValidationError, match="duplicate JSON"):
        validate_contract_json(target, bad)


def test_strict_json_parse_errors_do_not_expose_raw_documents_in_public_context() -> None:
    raw = '{"private_fixture_marker":"not-for-public-error-output", invalid}'
    with pytest.raises(ValidationError) as caught:
        validate_contract_json(TypeAdapter(object), raw)
    details = caught.value.errors()
    assert details[0]["input"] is None
    error_context = details[0].get("ctx")
    assert error_context is not None
    assert type(error_context["error"]) is ValueError
    assert not hasattr(error_context["error"], "doc")
    assert "not-for-public-error-output" not in caught.value.json()


class JsonFloatModel(BaseModel):
    value: float


class JsonNestedFloatModel(BaseModel):
    inner: JsonFloatModel
    values: tuple[float, ...]


@pytest.mark.parametrize("negative", [False, True])
@pytest.mark.parametrize(
    "target,template",
    [
        (float, "NUMBER"),
        (TypeAdapter(float), "NUMBER"),
        (TypeAdapter(list[float]), "[NUMBER]"),
        (TypeAdapter(tuple[float, ...]), "[NUMBER]"),
        (TypeAdapter(dict[str, float]), '{"value":NUMBER}'),
        (TypeAdapter(set[float]), "[NUMBER]"),
        (TypeAdapter(frozenset[float]), "[NUMBER]"),
        (JsonFloatModel, '{"value":NUMBER}'),
        (TypeAdapter(JsonFloatModel), '{"value":NUMBER}'),
        (JsonNestedFloatModel, '{"inner":{"value":NUMBER},"values":[NUMBER]}'),
        (RootModel[float], "NUMBER"),
        (TypeAdapter(list[JsonFloatModel]), '[{"value":NUMBER}]'),
    ],
)
def test_strict_json_rejects_integer_to_float_overflow_in_validated_outputs(
    negative: bool, target: Any, template: str
) -> None:
    raw = ("-" if negative else "") + "9" * 400
    with pytest.raises(ValidationError, match="nonfinite float") as caught:
        validate_contract_json(target, template.replace("NUMBER", raw))
    assert caught.value.title == "StrictJsonOutput"


@pytest.mark.parametrize("negative", [False, True])
def test_strict_json_preserves_large_integers_for_integer_targets(negative: bool) -> None:
    raw = ("-" if negative else "") + "9" * 400
    expected = int(raw)
    for target in (int, TypeAdapter(int)):
        actual = validate_contract_json(target, raw)
        assert type(actual) is int and actual == expected
    assert validate_contract_json(TypeAdapter(list[int]), "[" + raw + "]") == [expected]
    assert validate_contract_json(TypeAdapter(dict[str, int]), '{"value":' + raw + "}") == {
        "value": expected
    }


@pytest.mark.parametrize("raw", ["0", "-0.0", "1.25", "-2.5", "1e308", "-1e-300"])
def test_strict_json_preserves_finite_float_controls(raw: str) -> None:
    expected = float(raw)
    actual = validate_contract_json(TypeAdapter(float), raw)
    assert type(actual) is float and actual == expected and math.isfinite(actual)
    assert math.copysign(1, actual) == math.copysign(1, expected)
    model = validate_contract_json(JsonFloatModel, '{"value":' + raw + "}")
    assert model.value == expected and math.isfinite(model.value)


def output_target(produced: Any) -> type[Any]:
    """Test schema returns a chosen data graph; no production safety helper is used."""

    class ProducedOutput(BaseModel):
        payload: Any

        @field_validator("payload", mode="after")
        @classmethod
        def produce(cls, value: Any) -> Any:
            return produced

    return ProducedOutput


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
@pytest.mark.parametrize("where", ["direct", "list", "tuple", "dict_value", "dict_key", "model"])
def test_output_guard_rejects_nonfinite_values_anywhere_in_supported_data(
    bad: float, where: str
) -> None:
    produced: Any = {
        "direct": bad,
        "list": [bad],
        "tuple": (False, None, bad),
        "dict_value": {"key": bad},
        "dict_key": {bad: 0},
        "model": JsonFloatModel.model_construct(value=bad),
    }[where]
    with pytest.raises(ValidationError, match="nonfinite float") as caught:
        validate_contract_json(output_target(produced), '{"payload":null}')
    assert caught.value.title == "StrictJsonOutput"


def test_output_guard_inspects_root_extra_and_private_model_storage() -> None:
    class ExtraModel(BaseModel):
        model_config = ConfigDict(extra="allow")

    class PrivateModel(BaseModel):
        _hidden: float = PrivateAttr(default=float("inf"))

    extras = ExtraModel.model_construct()
    object.__setattr__(extras, "__pydantic_extra__", {"hidden": float("-inf")})
    for model in (extras, PrivateModel(), RootModel[float].model_construct(root=float("nan"))):
        with pytest.raises(ValidationError, match="nonfinite float"):
            validate_contract_json(output_target(model), '{"payload":null}')


def test_output_guard_preserves_complex_finite_results_and_shared_references() -> None:
    shared: list[Any] = [0, False, None, -0.0, 1.25, int("9" * 400)]
    nested = JsonFloatModel(value=2.5)
    produced = {
        "first": shared,
        "second": shared,
        "tuple": (nested, {1.0, 2.0}, frozenset({3.0})),
        "enum": RuleEnvironment.SYNTHETIC,
        "bytes": b"synthetic",
        "bytearray": bytearray(b"synthetic"),
    }
    original = repr(produced)
    result = validate_contract_json(output_target(produced), '{"payload":null}')
    assert result.payload is produced
    assert result.payload["first"] is result.payload["second"] is shared
    assert result.payload["tuple"][0] is nested
    assert repr(produced) == original


def test_strict_json_preserves_nested_finite_typed_outputs() -> None:
    target = TypeAdapter(dict[str, tuple[list[JsonFloatModel], set[float], frozenset[float]]])
    result = validate_contract_json(target, '{"data":[[{"value":1.25}],[0,2.5],[-1.5]]}')
    models, values, frozen = result["data"]
    assert type(result) is dict and type(result["data"]) is tuple
    assert type(models) is list and models[0].value == 1.25
    assert type(values) is set and values == {0.0, 2.5}
    assert type(frozen) is frozenset and frozen == {-1.5}
    assert all(math.isfinite(value) for value in (*values, *frozen))


@pytest.mark.parametrize(
    "raw,expected", [("true", True), ("false", False), ("null", None), ("0", 0)]
)
def test_output_guard_preserves_plain_json_scalar_types(raw: str, expected: Any) -> None:
    result = validate_contract_json(TypeAdapter(Any), raw)
    assert type(result) is type(expected) and result == expected


def test_output_guard_rejects_nested_typed_dictionary_key_overflow() -> None:
    # JSON keys are strings; Pydantic's JSON mode can convert them into float keys.
    raw = '{"' + "9" * 400 + '":0}'
    with pytest.raises(ValidationError, match="nonfinite float"):
        validate_contract_json(TypeAdapter(dict[float, int]), raw)


@pytest.mark.parametrize("container", [HiddenDict, HiddenList, HiddenTuple])
def test_output_guard_rejects_custom_containers_before_overridden_iteration(container: Any) -> None:
    produced = (
        container({"bad": float("inf")}) if container is HiddenDict else container((float("inf"),))
    )
    target = output_target(produced)
    _container_calls.clear()
    with pytest.raises(ValidationError, match="unsupported validated output type"):
        validate_contract_json(target, '{"payload":null}')
    assert not _container_calls


def test_output_guard_rejects_custom_scalar_and_opaque_values_without_inspecting_them() -> None:
    class FloatSubclass(float):
        def __float__(self) -> float:
            _container_calls.append("float.__float__")
            return 0.0

    class Opaque:
        @property
        def hidden(self) -> float:
            _container_calls.append("opaque.hidden")
            return float("inf")

    for produced in (FloatSubclass("inf"), Opaque()):
        target = output_target(produced)
        _container_calls.clear()
        with pytest.raises(ValidationError, match="unsupported validated output type"):
            validate_contract_json(target, '{"payload":null}')
        assert not _container_calls


def test_output_guard_rejects_lazy_outputs_without_advancing_iterators() -> None:
    def lazy() -> Iterator[float]:
        _container_calls.append("iterator advanced")
        yield float("inf")

    _container_calls.clear()
    with pytest.raises(ValidationError, match="unsupported validated output type"):
        validate_contract_json(output_target(lazy()), '{"payload":null}')
    assert not _container_calls


def test_output_guard_rejects_custom_model_storage_before_iteration() -> None:
    model = JsonFloatModel(value=0.0)
    object.__setattr__(model, "__dict__", HiddenDict({"value": float("inf")}))
    _container_calls.clear()
    with pytest.raises(ValidationError, match="built-in dictionary"):
        validate_contract_json(output_target(model), '{"payload":null}')
    assert not _container_calls


def test_output_guard_rejects_computed_fields_without_evaluating_properties() -> None:
    class ComputedModel(BaseModel):
        value: float

        @computed_field
        @property
        def hidden(self) -> float:
            _container_calls.append("computed.hidden")
            return float("inf")

    _container_calls.clear()
    with pytest.raises(ValidationError, match="computed fields"):
        validate_contract_json(ComputedModel, '{"value":0}')
    assert not _container_calls


def test_output_guard_bypasses_model_instance_attribute_overrides() -> None:
    class HiddenAttributesModel(BaseModel):
        value: float

        def __getattribute__(self, name: str) -> Any:
            if name in ("value", "__dict__", "__pydantic_extra__", "__pydantic_private__"):
                _container_calls.append("model attribute: " + name)
                raise AssertionError("ordinary attribute access must not be used")
            return super().__getattribute__(name)

    _container_calls.clear()
    with pytest.raises(ValidationError, match="nonfinite float"):
        validate_contract_json(HiddenAttributesModel, '{"value":' + "9" * 400 + "}")
    assert not _container_calls


def test_output_guard_rejects_opaque_standard_schema_results_instead_of_claiming_safety() -> None:
    from dataclasses import dataclass
    from datetime import datetime
    from decimal import Decimal
    from typing import NamedTuple
    from uuid import UUID

    @dataclass
    class Data:
        value: float

    class Named(NamedTuple):
        value: float

    cases: tuple[tuple[TypeAdapter[Any], str], ...] = (
        (TypeAdapter(Data), '{"value":1}'),
        (TypeAdapter(Named), "[1]"),
        (TypeAdapter(Decimal), "1.25"),
        (TypeAdapter(datetime), '"2026-10-14T00:00:00Z"'),
        (TypeAdapter(UUID), '"00000000-0000-0000-0000-000000000000"'),
    )
    for target, raw in cases:
        with pytest.raises(ValidationError, match="unsupported validated output type"):
            validate_contract_json(target, raw)


def test_output_guard_rejects_cycles_without_rejecting_shared_acyclic_values() -> None:
    cyclic: list[Any] = []
    cyclic.append(cyclic)
    with pytest.raises(ValidationError, match="cyclic validated outputs"):
        validate_contract_json(output_target(cyclic), '{"payload":null}')
    shared = [1.0]
    result = validate_contract_json(output_target([shared, shared]), '{"payload":null}')
    assert result.payload[0] is result.payload[1] is shared


@pytest.mark.parametrize("limit", ["STRICT_JSON_MAX_OUTPUT_DEPTH", "STRICT_JSON_MAX_OUTPUT_NODES"])
def test_output_guard_bounds_expansion_created_by_trusted_schema_validators(
    limit: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from savora_ai.schemas import candidates as contracts

    monkeypatch.setattr(contracts, limit, 8)
    if limit.endswith("DEPTH"):
        produced: Any = 0
        for _ in range(12):
            produced = [produced]
    else:
        produced = [0] * 32
    with pytest.raises(ValidationError, match="bounded traversal limit"):
        validate_contract_json(output_target(produced), '{"payload":null}')
