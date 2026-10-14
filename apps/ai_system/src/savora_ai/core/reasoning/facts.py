"""Conservative, fixed synthetic fact adapters. Every graph query uses the accepted KB."""

from savora_ai.core.reasoning.graph import resolve_food_relations
from savora_ai.core.reasoning.manifest import (
    _descriptors_for,
    _ManifestRequest,
    _reject,
    build_expected_check_manifest,
)
from savora_ai.core.reasoning.taxonomy import resolve_taxonomy_assignment
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    FactSubjectKind,
    IngredientMappingStatus,
    RuleContext,
    VersionedFact,
    _line_records,
)
from savora_ai.schemas.filtering import (
    _ATTRIBUTES,
    _DERIVED_ATTRIBUTES,
    CandidateFactResolution,
    ResolvedRuleFact,
    _evidence_union,
)
from savora_ai.schemas.food_graph import (
    FoodEntity,
    FoodEntityKind,
    FoodRelationType,
    RelationAssertion,
    RelationQualifiers,
    RelationResolution,
    RelationResolutionStatus,
    TaxonomyKind,
    TaxonomyResolution,
    TaxonomyTraversalMode,
    TraversalMode,
)
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot
from savora_ai.schemas.reasoning import FactObservation


def _validated_fact_index(facts: tuple[VersionedFact, ...]) -> dict[str, VersionedFact]:
    """Run after envelope revalidation; incompatible supplied values never become gaps."""
    indexed: dict[str, VersionedFact] = {}
    for fact in facts:
        policy = _ATTRIBUTES.get(fact.fact_id)
        if policy is None:
            continue
        if fact.fact_id in indexed or fact.subject_kind is not policy.subject:
            _reject("conflicting or incompatible synthetic fact ownership")
        indexed[fact.fact_id] = fact
        value = fact.observation.value
        if value is None:
            continue
        compatible = {
            "numeric": type(value) in (int, float),
            "boolean": type(value) is bool,
            "categorical": type(value) is str,
        }[policy.kind]
        if not compatible or fact.observation.unit is not policy.unit:
            _reject("incompatible synthetic supplied fact type/unit")
        if fact.measurement_basis is not policy.basis:
            _reject("incompatible exact synthetic measurement basis")
        identity = (
            None
            if fact.basis_reference is None
            else (
                fact.basis_reference.evidence_id,
                fact.basis_reference.version,
            )
        )
        if identity != policy.basis_identity:
            _reject("incompatible exact synthetic basis reference")
    return indexed


def _catalogue_entity(
    kb: KnowledgeBaseSnapshot,
    canonical_id: str,
    kind: FoodEntityKind,
) -> FoodEntity | None:
    # Exact namespace mapping only. Node IDs/labels/aliases never stand in for catalogue IDs.
    return next(
        (
            entity
            for entity in kb.graph.entities
            if entity.kind is kind and entity.catalogue_reference == canonical_id
        ),
        None,
    )


def _inventory(
    kb: KnowledgeBaseSnapshot,
    candidate: CandidateRecipeFacts,
) -> tuple[tuple[FoodEntity, ...], tuple[str, ...], tuple[RelationResolution, ...]]:
    mapped: dict[str, FoodEntity] = {}
    unresolved: set[str] = set()
    for line in _line_records(candidate.ingredient_coverage.lines or ()):
        entity = (
            None
            if line.ingredient_id is None
            else _catalogue_entity(
                kb,
                line.ingredient_id,
                FoodEntityKind.INGREDIENT,
            )
        )
        if line.mapping_status is IngredientMappingStatus.UNRESOLVED or entity is None:
            unresolved.add(line.line_id)
        else:
            mapped[entity.entity_id] = entity
    relations = tuple(
        resolve_food_relations(
            kb.graph,
            source_id=candidate.graph_recipe_entity_id,
            target_id=entity_id,
            relation_type=FoodRelationType.CONTAINS,
        )
        for entity_id in sorted(mapped)
    )
    if any(result.status is RelationResolutionStatus.VERIFIED_ABSENT for result in relations):
        _reject("candidate ingredient presence contradicts exact KB containment absence")
    coverage = candidate.ingredient_coverage
    complete = (
        coverage.inventory_complete
        and coverage.mapping_complete
        and coverage.subingredients_complete
        and not unresolved
    )
    if complete:
        entities = {entity.entity_id: entity for entity in kb.graph.entities}
        for relation in kb.graph.relations:
            if (
                relation.source_id == candidate.graph_recipe_entity_id
                and relation.relation_type is FoodRelationType.CONTAINS
                and relation.assertion is RelationAssertion.PRESENT
                and entities[relation.target_id].catalogue_reference is not None
                and relation.target_id not in mapped
            ):
                _reject("complete candidate inventory contradicts exact KB ingredient presence")
    return tuple(mapped[key] for key in sorted(mapped)), tuple(sorted(unresolved)), relations


def _adapter(
    name: str,
    kb: KnowledgeBaseSnapshot,
    candidate: CandidateRecipeFacts,
    mapped: tuple[FoodEntity, ...],
    unresolved: tuple[str, ...],
) -> tuple[bool | None, str, tuple[RelationResolution, ...], TaxonomyResolution | None]:
    if name in ("synthetic_allergen_absent", "synthetic_clinically_safe"):
        return None, "UNSUPPORTED_SAFETY_INFERENCE", (), None
    if name in ("synthetic_dietary_target", "synthetic_cuisine_target"):
        dietary = name == "synthetic_dietary_target"
        term_id = "synthetic-dietary" if dietary else "synthetic-cuisine"
        result = resolve_taxonomy_assignment(
            kb.graph,
            subject_id=candidate.graph_recipe_entity_id,
            term_id=term_id,
            traversal=TaxonomyTraversalMode.DIRECT
            if dietary
            else TaxonomyTraversalMode.CUISINE_PARENTS,
        )
        kind = TaxonomyKind.DIETARY_CATEGORY if dietary else TaxonomyKind.CUISINE
        if result.term is not None and result.term.kind is not kind:
            return None, "UNSUPPORTED_TARGET_KIND", (), result
        value = (
            True
            if result.status is RelationResolutionStatus.SUPPORTED
            else False
            if result.status is RelationResolutionStatus.VERIFIED_ABSENT
            else None
        )
        return value, result.reason_code, (), result
    if name == "synthetic_dinner_compatible":
        target = _catalogue_entity(kb, "synthetic-companion", FoodEntityKind.RECIPE_REFERENCE)
        if target is None:
            return None, "UNRESOLVED_TARGET_MAPPING", (), None
        relation = resolve_food_relations(
            kb.graph,
            source_id=candidate.graph_recipe_entity_id,
            target_id=target.entity_id,
            relation_type=FoodRelationType.COMPATIBLE_WITH,
            qualifiers=RelationQualifiers(meal_type="DINNER"),
        )
        value = (
            True
            if relation.status is RelationResolutionStatus.SUPPORTED
            else False
            if relation.status is RelationResolutionStatus.VERIFIED_ABSENT
            else None
        )
        return value, relation.reason_code or "NO_DIRECT_ASSERTION", (relation,), None
    target = _catalogue_entity(kb, "synthetic-target", FoodEntityKind.INGREDIENT)
    if target is None:
        return None, "UNRESOLVED_TARGET_MAPPING", (), None
    if name == "synthetic_origin_target":
        relations = tuple(
            resolve_food_relations(
                kb.graph,
                source_id=entity.entity_id,
                target_id=target.entity_id,
                relation_type=FoodRelationType.DERIVED_FROM,
                traversal=TraversalMode.ORIGIN_PATH,
            )
            for entity in mapped
        )
        supported = any(result.status is RelationResolutionStatus.SUPPORTED for result in relations)
        code = (
            "ORIGIN_PATH_SUPPORTED"
            if supported
            else "TRAVERSAL_LIMIT"
            if any(result.limit_reached for result in relations)
            else "INGREDIENT_MAPPING_GAP"
            if unresolved
            else "NO_ORIGIN_PATH"
        )
        return True if supported else None, code, relations, None
    assert name == "synthetic_contains_target"
    result = resolve_food_relations(
        kb.graph,
        source_id=candidate.graph_recipe_entity_id,
        target_id=target.entity_id,
        relation_type=FoodRelationType.CONTAINS,
    )
    coverage = candidate.ingredient_coverage
    complete = (
        coverage.inventory_complete
        and coverage.mapping_complete
        and coverage.subingredients_complete
        and not unresolved
    )
    target_present = any(entity.entity_id == target.entity_id for entity in mapped)
    if complete and result.status is RelationResolutionStatus.SUPPORTED and not target_present:
        _reject("complete candidate inventory contradicts exact KB ingredient presence")
    if result.status is RelationResolutionStatus.SUPPORTED:
        return True, "DIRECT_SUPPORTED", (result,), None
    if result.status is RelationResolutionStatus.VERIFIED_ABSENT:
        if not complete:
            return None, "INGREDIENT_MAPPING_GAP", (result,), None
        return False, "DIRECT_VERIFIED_ABSENT", (result,), None
    return None, result.reason_code or "NO_DIRECT_ASSERTION", (result,), None


def resolve_rule_facts(
    candidate: CandidateRecipeFacts,
    *,
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
) -> CandidateFactResolution:
    """Resolve fixed exact claims internally; accept no graph/taxonomy resolution arguments.

    Recipe/profile/context scalar facts retain declared completeness. New graph facts
    require accepted KB evidence. Origin is reachability only; safety inference is unknown.
    """
    request = _ManifestRequest.model_validate(
        {"kb": knowledge, "candidate": candidate, "context": context}
    )
    knowledge, candidate, context = request.kb, request.candidate, request.context
    manifest = build_expected_check_manifest(knowledge, candidate, context)
    supplied = _validated_fact_index((*candidate.facts, *context.facts))
    mapped, unresolved, inventory_relations = _inventory(knowledge, candidate)
    descriptors = _descriptors_for(knowledge, manifest.required_checks)
    required = {name for rule in manifest.required_checks for name in rule.required_facts}
    required.update(
        name for descriptor in descriptors for name in descriptor.required_context_facts
    )
    names = sorted(required | set(supplied))
    resolved: list[ResolvedRuleFact] = []
    for name in names:
        original = supplied.get(name)
        policy = _ATTRIBUTES[name]
        if name not in _DERIVED_ATTRIBUTES and original is not None:
            resolved.append(
                ResolvedRuleFact(
                    fact=original,
                    supplied_fact=original,
                    source="SUPPLIED",
                    reason_code="DECLARED_FACT",
                )
            )
            continue
        value: bool | None = None
        relations: tuple[RelationResolution, ...] = ()
        taxonomy = None
        if name in _DERIVED_ATTRIBUTES:
            value, reason, relations, taxonomy = _adapter(
                name, knowledge, candidate, mapped, unresolved
            )
            source = (
                "UNSUPPORTED"
                if name in ("synthetic_allergen_absent", "synthetic_clinically_safe")
                else (
                    "KB_TAXONOMY"
                    if name in ("synthetic_dietary_target", "synthetic_cuisine_target")
                    else "KB_RELATION"
                )
            )
            claim = value
            # A mapping gap can block use of an exact negative but cannot hide a
            # contradiction between the supplied positive and that KB assertion.
            if name == "synthetic_contains_target" and relations:
                claim = (
                    True
                    if relations[0].status is RelationResolutionStatus.SUPPORTED
                    else False
                    if relations[0].status is RelationResolutionStatus.VERIFIED_ABSENT
                    else None
                )
            if (
                original is not None
                and original.observation.value is not None
                and claim is not None
                and (original.observation.value is not claim)
            ):
                _reject("supplied candidate fact contradicts accepted KB evidence")
        else:
            source, reason = "MISSING", "MISSING_REQUIRED_FACT"
        owner, version = {
            FactSubjectKind.RECIPE: (candidate.recipe_id, candidate.recipe_version),
            FactSubjectKind.PROFILE: (context.profile_id, context.profile_version),
            FactSubjectKind.CONTEXT: (context.context_id, context.version),
        }[policy.subject]
        evidence = _evidence_union((relations, taxonomy)) or _evidence_union(
            (
                knowledge.evidence,
                candidate.evidence
                if policy.subject is FactSubjectKind.RECIPE
                else context.evidence,
            )
        )
        if (
            reason == "INGREDIENT_MAPPING_GAP"
            or (name == "synthetic_contains_target" and value is False)
            or name == "synthetic_origin_target"
        ):
            evidence = _evidence_union((evidence, candidate.ingredient_coverage))
        derived = VersionedFact(
            fact_id=name,
            version="synthetic-fact-resolution.v1",
            subject_kind=policy.subject,
            subject_id=owner,
            subject_version=version,
            catalogue_version=knowledge.catalogue_version
            if policy.subject is FactSubjectKind.RECIPE
            else None,
            context_id=context.context_id,
            context_version=context.version,
            observation=FactObservation(
                fact_id=name, value=value, complete=value is not None, evidence=evidence
            ),
        )
        resolved.append(
            ResolvedRuleFact(
                fact=derived,
                supplied_fact=original,
                source=source,
                reason_code=reason,
                relations=relations,
                taxonomy=taxonomy,
            )
        )
    return CandidateFactResolution(
        manifest=manifest,
        ingredient_coverage=candidate.ingredient_coverage,
        unresolved_line_ids=unresolved,
        inventory_relations=inventory_relations,
        facts=tuple(resolved),
    )
