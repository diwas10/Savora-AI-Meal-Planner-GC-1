"""Provisional food graph declarations; source metadata does not establish authority."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from savora_ai.schemas.knowledge import (
    EvidenceReference,
    RuleEnvironment,
    _ContractModel,
    _NonBlank,
    _validate_evidence,
)

_OpaqueId = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"),
]


class FoodEntityKind(StrEnum):
    INGREDIENT = "INGREDIENT"
    RECIPE_REFERENCE = "RECIPE_REFERENCE"
    CULINARY_ROLE_REFERENCE = "CULINARY_ROLE_REFERENCE"
    CUISINE_REFERENCE = "CUISINE_REFERENCE"


class FoodRelationType(StrEnum):
    CONTAINS = "CONTAINS"
    DERIVED_FROM = "DERIVED_FROM"
    HAS_CULINARY_ROLE = "HAS_CULINARY_ROLE"
    COMPATIBLE_WITH = "COMPATIBLE_WITH"
    FUNCTIONAL_SUBSTITUTE_FOR = "FUNCTIONAL_SUBSTITUTE_FOR"


class RelationAssertion(StrEnum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


class RelationResolutionStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    VERIFIED_ABSENT = "VERIFIED_ABSENT"
    UNKNOWN = "UNKNOWN"


class TraversalMode(StrEnum):
    DIRECT = "DIRECT"
    ORIGIN_PATH = "ORIGIN_PATH"


class TaxonomyKind(StrEnum):
    CUISINE = "CUISINE"
    DIETARY_PATTERN = "DIETARY_PATTERN"
    DIETARY_CATEGORY = "DIETARY_CATEGORY"
    CULINARY_ROLE = "CULINARY_ROLE"


class TaxonomyAssignmentAssertion(StrEnum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


class TaxonomyTraversalMode(StrEnum):
    DIRECT = "DIRECT"
    CUISINE_PARENTS = "CUISINE_PARENTS"


def _validate_canonical_enum(value: StrEnum) -> StrEnum:
    """Reject forged instances, including those that reuse a declared token."""
    if not any(value is member for member in type(value)):
        raise ValueError(f"{type(value).__name__} requires a canonical declared enum member")
    return value


_EntityKind = Annotated[FoodEntityKind, AfterValidator(_validate_canonical_enum)]
_RelationType = Annotated[FoodRelationType, AfterValidator(_validate_canonical_enum)]
_Assertion = Annotated[RelationAssertion, AfterValidator(_validate_canonical_enum)]
_ResolutionStatus = Annotated[RelationResolutionStatus, AfterValidator(_validate_canonical_enum)]
_Traversal = Annotated[TraversalMode, AfterValidator(_validate_canonical_enum)]
_Environment = Annotated[RuleEnvironment, AfterValidator(_validate_canonical_enum)]
_TaxonomyKind = Annotated[TaxonomyKind, AfterValidator(_validate_canonical_enum)]
_TaxonomyAssertion = Annotated[
    TaxonomyAssignmentAssertion, AfterValidator(_validate_canonical_enum)
]
_TaxonomyTraversal = Annotated[TaxonomyTraversalMode, AfterValidator(_validate_canonical_enum)]
_SearchLimit = Annotated[int, Field(strict=True, gt=0)]
_ResolutionReason = Literal[
    "DIRECT_SUPPORTED",
    "DIRECT_VERIFIED_ABSENT",
    "NO_DIRECT_ASSERTION",
    "MISSING_ENTITY",
    "ORIGIN_PATH_SUPPORTED",
    "NO_ORIGIN_PATH",
    "MAX_HOPS_REACHED",
    "MAX_VISITED_REACHED",
]
_TaxonomyResolutionReason = Literal[
    "DIRECT_SUPPORTED",
    "DIRECT_VERIFIED_ABSENT",
    "MISSING_SUBJECT",
    "MISSING_TERM",
    "NO_ASSIGNMENT",
    "NO_CUISINE_PATH",
    "UNSUPPORTED_HIERARCHY",
    "HIERARCHY_SUPPORTED",
    "HIERARCHY_CONFLICT",
    "MAX_HOPS_REACHED",
    "MAX_VISITED_REACHED",
]


class RelationQualifiers(_ContractModel):
    cuisine_id: _OpaqueId | None = None
    culinary_role_id: _OpaqueId | None = None
    meal_type: Literal["BREAKFAST", "LUNCH", "DINNER"] | None = None


def _validate_qualifiers(relation_type: FoodRelationType, qualifiers: RelationQualifiers) -> None:
    if relation_type in (FoodRelationType.CONTAINS, FoodRelationType.DERIVED_FROM):
        if qualifiers != RelationQualifiers():
            raise ValueError("containment and derivation do not support qualifiers in this slice")
    elif relation_type is FoodRelationType.HAS_CULINARY_ROLE:
        if qualifiers.culinary_role_id is not None:
            raise ValueError("HAS_CULINARY_ROLE names its role through the target, not a qualifier")
    elif (
        relation_type is FoodRelationType.FUNCTIONAL_SUBSTITUTE_FOR
        and qualifiers.culinary_role_id is None
    ):
        raise ValueError("functional substitution requires a culinary role qualifier")


def _validate_traversal(relation_type: FoodRelationType, traversal: TraversalMode) -> None:
    if (
        traversal is TraversalMode.ORIGIN_PATH
        and relation_type is not FoodRelationType.DERIVED_FROM
    ):
        raise ValueError("ORIGIN_PATH supports DERIVED_FROM only")


def _require_evidence(evidence: tuple[EvidenceReference, ...]) -> None:
    if not evidence:
        raise ValueError("graph records require evidence, including declared coverage gaps")
    _validate_evidence(evidence)
    # Keep Phase 1 DTOs unchanged while enforcing graph-scoped enum integrity.
    for reference in evidence:
        _validate_canonical_enum(reference.environment)


class FoodEntity(_ContractModel):
    entity_id: _OpaqueId
    version: _NonBlank
    kind: _EntityKind
    canonical_name: _NonBlank
    aliases: tuple[_NonBlank, ...] = ()
    catalogue_reference: _OpaqueId | None = None
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_entity(self) -> Self:
        _require_evidence(self.evidence)
        if len(set(self.aliases)) != len(self.aliases):
            raise ValueError("duplicate entity aliases")
        if self.kind is not FoodEntityKind.INGREDIENT and self.catalogue_reference is None:
            raise ValueError("reference entities require a catalogue reference")
        return self


class FoodRelation(_ContractModel):
    relation_id: _OpaqueId
    version: _NonBlank
    relation_type: _RelationType
    source_id: _OpaqueId
    target_id: _OpaqueId
    assertion: _Assertion
    qualifiers: RelationQualifiers = Field(default_factory=RelationQualifiers)
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_relation(self) -> Self:
        _require_evidence(self.evidence)
        _validate_qualifiers(self.relation_type, self.qualifiers)
        if self.source_id == self.target_id:
            raise ValueError("self-relations are unsupported")
        return self


class KnowledgeCoverage(_ContractModel):
    """Declared outgoing coverage for one subject/type/context in one graph release."""

    coverage_id: _OpaqueId
    version: _NonBlank
    graph_id: _OpaqueId
    graph_version: _NonBlank
    catalogue_version: _NonBlank
    subject_id: _OpaqueId
    relation_type: _RelationType
    qualifiers: RelationQualifiers = Field(default_factory=RelationQualifiers)
    complete: bool
    reason: _NonBlank
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_coverage(self) -> Self:
        _require_evidence(self.evidence)
        _validate_qualifiers(self.relation_type, self.qualifiers)
        return self


class TaxonomyTerm(_ContractModel):
    """A versioned concept; its evidence backs its declared child-to-parent links."""

    term_id: _OpaqueId
    version: _NonBlank
    kind: _TaxonomyKind
    display_label: _NonBlank
    parent_ids: tuple[_OpaqueId, ...] = ()
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_term(self) -> Self:
        _require_evidence(self.evidence)
        if len(set(self.parent_ids)) != len(self.parent_ids):
            raise ValueError("duplicate taxonomy parent reference")
        if self.term_id in self.parent_ids:
            raise ValueError("self-parent taxonomy terms are unsupported")
        return self


class TaxonomyAssignment(_ContractModel):
    assignment_id: _OpaqueId
    version: _NonBlank
    subject_id: _OpaqueId
    term_id: _OpaqueId
    assertion: _TaxonomyAssertion
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_assignment(self) -> Self:
        _require_evidence(self.evidence)
        return self


_FOOD_KINDS = (FoodEntityKind.INGREDIENT, FoodEntityKind.RECIPE_REFERENCE)


def _validate_endpoint_kinds(
    relation_type: FoodRelationType, source: FoodEntity, target: FoodEntity
) -> None:
    if source.kind not in _FOOD_KINDS:
        raise ValueError("relation sources must be ingredients or recipe references")
    if relation_type in (FoodRelationType.CONTAINS, FoodRelationType.DERIVED_FROM):
        if target.kind is not FoodEntityKind.INGREDIENT:
            raise ValueError("containment and derivation targets must be ingredients")
        if (
            relation_type is FoodRelationType.DERIVED_FROM
            and source.kind is not FoodEntityKind.INGREDIENT
        ):
            raise ValueError("derivation sources must be ingredients")
    elif relation_type is FoodRelationType.HAS_CULINARY_ROLE:
        if target.kind is not FoodEntityKind.CULINARY_ROLE_REFERENCE:
            raise ValueError("culinary role targets must be role references")
    elif target.kind not in _FOOD_KINDS:
        raise ValueError("compatibility and substitution targets must be food entities")


def _validate_qualifier_references(
    qualifiers: RelationQualifiers, entities: dict[str, FoodEntity]
) -> None:
    for entity_id, expected in (
        (qualifiers.cuisine_id, FoodEntityKind.CUISINE_REFERENCE),
        (qualifiers.culinary_role_id, FoodEntityKind.CULINARY_ROLE_REFERENCE),
    ):
        if entity_id is not None:
            entity = entities.get(entity_id)
            if entity is None or entity.kind is not expected:
                raise ValueError("qualifiers require existing references of the correct kind")


def _validate_acyclic(relations: tuple[FoodRelation, ...]) -> None:
    # Validate structural cycles iteratively; this does not resolve indirect facts.
    for relation_type in (FoodRelationType.CONTAINS, FoodRelationType.DERIVED_FROM):
        adjacency: dict[str, set[str]] = {}
        indegrees: dict[str, int] = {}
        for relation in relations:
            if (
                relation.relation_type is relation_type
                and relation.assertion is RelationAssertion.PRESENT
            ):
                targets = adjacency.setdefault(relation.source_id, set())
                indegrees.setdefault(relation.source_id, 0)
                if relation.target_id not in targets:
                    targets.add(relation.target_id)
                    indegrees[relation.target_id] = indegrees.get(relation.target_id, 0) + 1
        pending = [entity_id for entity_id, degree in indegrees.items() if degree == 0]
        visited = 0
        while pending:
            entity_id = pending.pop()
            visited += 1
            for target_id in adjacency.get(entity_id, ()):
                indegrees[target_id] -= 1
                if indegrees[target_id] == 0:
                    pending.append(target_id)
        if visited != len(indegrees):
            raise ValueError("positive containment and derivation cycles are unsupported")


def _validate_taxonomy(
    terms: tuple[TaxonomyTerm, ...],
    assignments: tuple[TaxonomyAssignment, ...],
    entities: dict[str, FoodEntity],
) -> None:
    by_id = {term.term_id: term for term in terms}
    if len(by_id) != len(terms):
        raise ValueError("duplicate taxonomy term identity or versions")
    indegrees = dict.fromkeys(by_id, 0)
    for term in terms:
        for parent_id in term.parent_ids:
            parent = by_id.get(parent_id)
            if parent is None:
                raise ValueError("dangling taxonomy parent reference")
            if parent.kind is not term.kind:
                raise ValueError("taxonomy parents must have the same kind as their child")
            indegrees[parent_id] += 1
    pending = [term_id for term_id, degree in indegrees.items() if degree == 0]
    visited = 0
    while pending:
        term_id = pending.pop()
        visited += 1
        for parent_id in by_id[term_id].parent_ids:
            indegrees[parent_id] -= 1
            if indegrees[parent_id] == 0:
                pending.append(parent_id)
    if visited != len(terms):
        raise ValueError("taxonomy hierarchy cycles are unsupported")
    if len({item.assignment_id for item in assignments}) != len(assignments):
        raise ValueError("duplicate taxonomy assignment identity or versions")
    assertions: dict[tuple[str, str], TaxonomyAssignmentAssertion] = {}
    cuisine_positive: dict[str, set[str]] = {}
    cuisine_negative: dict[str, set[str]] = {}
    for assignment in assignments:
        subject = entities.get(assignment.subject_id)
        if subject is None or subject.kind not in _FOOD_KINDS:
            raise ValueError("taxonomy assignment subjects must reference existing food entities")
        if assignment.term_id not in by_id:
            raise ValueError("dangling taxonomy assignment term")
        key = (assignment.subject_id, assignment.term_id)
        if key in assertions:
            if assertions[key] is not assignment.assertion:
                raise ValueError("contradictory positive/negative taxonomy assignments")
            raise ValueError("duplicate subject/term assignment; combine its evidence")
        assertions[key] = assignment.assertion
        if by_id[assignment.term_id].kind is TaxonomyKind.CUISINE:
            grouped = (
                cuisine_positive
                if assignment.assertion is TaxonomyAssignmentAssertion.PRESENT
                else cuisine_negative
            )
            grouped.setdefault(assignment.subject_id, set()).add(assignment.term_id)
    # Complete cuisine consistency is independent of query limits and selected witnesses.
    # Walk each subject's reachable terms once; avoid storing every term's ancestor set.
    for subject_id in sorted(cuisine_positive):
        negative = cuisine_negative.get(subject_id)
        if not negative:
            continue
        pending = sorted(cuisine_positive[subject_id], reverse=True)
        discovered = set(pending)
        while pending:
            term_id = pending.pop()
            if term_id in negative:
                raise ValueError(
                    f"contradictory cuisine ancestry for subject {subject_id!r}: "
                    f"{term_id!r} has positive ancestry and an explicit ABSENT assignment"
                )
            for parent_id in sorted(by_id[term_id].parent_ids, reverse=True):
                if parent_id not in discovered:
                    discovered.add(parent_id)
                    pending.append(parent_id)


class FoodGraphSnapshot(_ContractModel):
    schema_version: Literal["food-graph.v1"] = "food-graph.v1"
    semantic_policy_version: Literal["food-graph-direct.v1"] = "food-graph-direct.v1"
    graph_id: _OpaqueId
    version: _NonBlank
    catalogue_version: _NonBlank
    environment: _Environment
    entities: tuple[FoodEntity, ...]
    relations: tuple[FoodRelation, ...]
    coverage: tuple[KnowledgeCoverage, ...] = ()
    evidence: tuple[EvidenceReference, ...]
    taxonomy_version: _NonBlank | None = None
    taxonomy_terms: tuple[TaxonomyTerm, ...] = ()
    taxonomy_assignments: tuple[TaxonomyAssignment, ...] = ()

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        _require_evidence(self.evidence)
        if (self.taxonomy_terms or self.taxonomy_assignments) and self.taxonomy_version is None:
            raise ValueError("taxonomy records require an explicit taxonomy release version")
        entities = {entity.entity_id: entity for entity in self.entities}
        if len(entities) != len(self.entities):
            raise ValueError("duplicate entity identity or versions")
        catalogue_bindings: set[tuple[str, FoodEntityKind, str]] = set()
        for entity in self.entities:
            if entity.catalogue_reference is not None:
                binding = (self.catalogue_version, entity.kind, entity.catalogue_reference)
                if binding in catalogue_bindings:
                    raise ValueError(
                        "duplicate catalogue binding within the snapshot catalogue version"
                    )
                catalogue_bindings.add(binding)
        if len({item.relation_id for item in self.relations}) != len(self.relations):
            raise ValueError("duplicate relation identity or versions")
        assertions: dict[
            tuple[str, str, FoodRelationType, RelationQualifiers], RelationAssertion
        ] = {}
        for relation in self.relations:
            if relation.source_id not in entities or relation.target_id not in entities:
                raise ValueError("dangling relation endpoint")
            _validate_endpoint_kinds(
                relation.relation_type, entities[relation.source_id], entities[relation.target_id]
            )
            _validate_qualifier_references(relation.qualifiers, entities)
            key = (
                relation.source_id,
                relation.target_id,
                relation.relation_type,
                relation.qualifiers,
            )
            if key in assertions:
                if assertions[key] is not relation.assertion:
                    raise ValueError("contradictory positive/negative relation assertions")
                raise ValueError("duplicate directed qualified assertion; combine its evidence")
            assertions[key] = relation.assertion
        _validate_acyclic(self.relations)
        if len({item.coverage_id for item in self.coverage}) != len(self.coverage):
            raise ValueError("duplicate coverage identity or versions")
        coverage_keys: set[tuple[str, FoodRelationType, RelationQualifiers]] = set()
        for item in self.coverage:
            if (
                item.graph_id != self.graph_id
                or item.graph_version != self.version
                or item.catalogue_version != self.catalogue_version
            ):
                raise ValueError("coverage graph/catalogue version mismatch")
            if item.subject_id not in entities or entities[item.subject_id].kind not in _FOOD_KINDS:
                raise ValueError("coverage subjects must reference existing food entities")
            if (
                item.relation_type is FoodRelationType.DERIVED_FROM
                and entities[item.subject_id].kind is not FoodEntityKind.INGREDIENT
            ):
                raise ValueError("derivation coverage subjects must be ingredients")
            _validate_qualifier_references(item.qualifiers, entities)
            coverage_key = (item.subject_id, item.relation_type, item.qualifiers)
            if coverage_key in coverage_keys:
                raise ValueError("duplicate outgoing relation coverage")
            coverage_keys.add(coverage_key)
        _validate_taxonomy(self.taxonomy_terms, self.taxonomy_assignments, entities)
        provenance: dict[tuple[str, str], EvidenceReference] = {}
        references = [*self.evidence]
        for record in (
            *self.entities,
            *self.relations,
            *self.coverage,
            *self.taxonomy_terms,
            *self.taxonomy_assignments,
        ):
            references.extend(record.evidence)
        for reference in references:
            identity = (reference.evidence_id, reference.version)
            previous = provenance.get(identity)
            if previous is not None and previous != reference:
                raise ValueError("conflicting evidence metadata for one identity/version")
            if reference.environment is not self.environment:
                raise ValueError("all evidence must match the snapshot environment")
            provenance[identity] = reference
        return self


class RelationResolution(_ContractModel):
    graph_id: _OpaqueId
    graph_version: _NonBlank
    catalogue_version: _NonBlank
    semantic_policy_version: Literal["food-graph-direct.v1"]
    environment: _Environment
    source_id: _OpaqueId
    target_id: _OpaqueId
    relation_type: _RelationType
    qualifiers: RelationQualifiers
    traversal: _Traversal
    status: _ResolutionStatus
    relation: FoodRelation | None
    coverage: KnowledgeCoverage | None
    evidence: tuple[EvidenceReference, ...]
    reason: _NonBlank
    path: tuple[FoodRelation, ...] = ()
    limit_reached: bool = False
    reason_code: _ResolutionReason | None = None

    @model_validator(mode="after")
    def validate_resolution(self) -> Self:
        _require_evidence(self.evidence)
        _validate_qualifiers(self.relation_type, self.qualifiers)
        _validate_traversal(self.relation_type, self.traversal)
        if self.traversal is TraversalMode.ORIGIN_PATH:
            self._validate_origin_path()
        elif self.status is RelationResolutionStatus.UNKNOWN:
            if self.relation is not None:
                raise ValueError("unknown resolutions cannot carry a resolved assertion")
        else:
            if self.relation is None:
                raise ValueError("resolved relationships require the exact evidenced assertion")
            if (
                self.relation.source_id != self.source_id
                or self.relation.target_id != self.target_id
                or self.relation.relation_type is not self.relation_type
                or self.relation.qualifiers != self.qualifiers
            ):
                raise ValueError("resolution assertion differs from the query")
            expected = (
                RelationAssertion.PRESENT
                if self.status is RelationResolutionStatus.SUPPORTED
                else RelationAssertion.ABSENT
            )
            if self.relation.assertion is not expected:
                raise ValueError("resolution status contradicts its assertion")
            if set(self.evidence) != set(self.relation.evidence):
                raise ValueError("resolved evidence must match the assertion evidence")
        if self.traversal is TraversalMode.DIRECT:
            if self.path or self.limit_reached:
                raise ValueError("DIRECT resolutions cannot carry an origin path or search limit")
            if self.reason_code is not None:
                allowed = {
                    RelationResolutionStatus.SUPPORTED: ("DIRECT_SUPPORTED",),
                    RelationResolutionStatus.VERIFIED_ABSENT: ("DIRECT_VERIFIED_ABSENT",),
                    RelationResolutionStatus.UNKNOWN: ("NO_DIRECT_ASSERTION", "MISSING_ENTITY"),
                }
                if self.reason_code not in allowed[self.status]:
                    raise ValueError("DIRECT reason code contradicts its status")
        if self.coverage is not None and (
            self.coverage.graph_id != self.graph_id
            or self.coverage.graph_version != self.graph_version
            or self.coverage.catalogue_version != self.catalogue_version
            or self.coverage.subject_id != self.source_id
            or self.coverage.relation_type is not self.relation_type
            or self.coverage.qualifiers != self.qualifiers
        ):
            raise ValueError("resolution coverage differs from the query or graph release")
        references = [*self.evidence]
        if self.relation is not None:
            references.extend(self.relation.evidence)
        if self.coverage is not None:
            references.extend(self.coverage.evidence)
        for edge in self.path:
            references.extend(edge.evidence)
        provenance: dict[tuple[str, str], EvidenceReference] = {}
        for reference in references:
            key = (reference.evidence_id, reference.version)
            if key in provenance and provenance[key] != reference:
                raise ValueError("conflicting resolution evidence metadata")
            if reference.environment is not self.environment:
                raise ValueError("resolution evidence must match its environment")
            provenance[key] = reference
        return self

    def _validate_origin_path(self) -> None:
        if self.relation is not None:
            raise ValueError("origin paths cannot declare a new direct relation")
        if self.status is RelationResolutionStatus.VERIFIED_ABSENT:
            raise ValueError("origin reachability cannot establish VERIFIED_ABSENT")
        if self.status is RelationResolutionStatus.UNKNOWN:
            if self.path:
                raise ValueError("unknown origin resolutions cannot carry a witness path")
            if self.reason_code not in (
                "MISSING_ENTITY",
                "NO_ORIGIN_PATH",
                "MAX_HOPS_REACHED",
                "MAX_VISITED_REACHED",
            ):
                raise ValueError("unknown origin resolutions require an exhaustion or gap reason")
            limited = self.reason_code in ("MAX_HOPS_REACHED", "MAX_VISITED_REACHED")
            if self.limit_reached != limited:
                raise ValueError("origin limit flag contradicts its reason code")
            return
        if not self.path or self.limit_reached or self.reason_code != "ORIGIN_PATH_SUPPORTED":
            raise ValueError(
                "supported origins require a positive witness and no search-limit claim"
            )
        endpoint = self.source_id
        visited = {endpoint}
        relation_ids: set[str] = set()
        path_evidence: set[EvidenceReference] = set()
        for edge in self.path:
            if (
                edge.relation_type is not FoodRelationType.DERIVED_FROM
                or edge.assertion is not RelationAssertion.PRESENT
                or edge.qualifiers != self.qualifiers
                or edge.source_id != endpoint
            ):
                raise ValueError(
                    "origin witnesses require contiguous positive directed derivation edges"
                )
            if edge.target_id in visited or edge.relation_id in relation_ids:
                raise ValueError("origin witnesses cannot repeat entities or relations")
            visited.add(edge.target_id)
            relation_ids.add(edge.relation_id)
            endpoint = edge.target_id
            path_evidence.update(edge.evidence)
        if endpoint != self.target_id:
            raise ValueError("origin witness must end at the query target")
        if path_evidence != set(self.evidence):
            raise ValueError("origin evidence must exactly match the selected path evidence")


class TaxonomyResolution(_ContractModel):
    """Evidenced classification only; a conflict witness is never an affirmative result."""

    graph_id: _OpaqueId
    graph_version: _NonBlank
    catalogue_version: _NonBlank
    semantic_policy_version: Literal["food-graph-direct.v1"]
    taxonomy_version: _NonBlank | None
    taxonomy_policy_version: Literal["food-taxonomy.v1"] = "food-taxonomy.v1"
    environment: _Environment
    subject_id: _OpaqueId
    term_id: _OpaqueId
    term: TaxonomyTerm | None
    traversal: _TaxonomyTraversal
    status: _ResolutionStatus
    assignment: TaxonomyAssignment | None
    path: tuple[TaxonomyTerm, ...] = ()
    conflicts: tuple[TaxonomyAssignment, ...] = ()
    evidence: tuple[EvidenceReference, ...]
    reason_code: _TaxonomyResolutionReason
    reason: _NonBlank
    limit_reached: bool = False

    @model_validator(mode="after")
    def validate_resolution(self) -> Self:
        _require_evidence(self.evidence)
        if self.term is not None and self.term.term_id != self.term_id:
            raise ValueError("resolved taxonomy term differs from the query")
        if self.traversal is TaxonomyTraversalMode.DIRECT and (
            self.path or self.conflicts or self.limit_reached
        ):
            raise ValueError("DIRECT taxonomy results cannot carry hierarchy or limit metadata")
        if self.status is RelationResolutionStatus.UNKNOWN:
            if self.reason_code == "HIERARCHY_CONFLICT":
                self._validate_hierarchy_witness()
                if not self.conflicts or self.limit_reached:
                    raise ValueError("hierarchy conflicts require negative assertions and no limit")
                path_ids = {term.term_id for term in self.path}
                for conflict in self.conflicts:
                    if (
                        conflict.subject_id != self.subject_id
                        or conflict.term_id not in path_ids
                        or conflict.assertion is not TaxonomyAssignmentAssertion.ABSENT
                    ):
                        raise ValueError(
                            "conflicts must be exact negative assignments on the witness"
                        )
                if len({item.assignment_id for item in self.conflicts}) != len(self.conflicts):
                    raise ValueError("duplicate conflicting assignment identity")
                if self.assignment is not None and any(
                    item.assignment_id == self.assignment.assignment_id for item in self.conflicts
                ):
                    raise ValueError("positive and negative witness identities must differ")
                self._validate_selected_evidence()
            else:
                if self.assignment is not None or self.path or self.conflicts:
                    raise ValueError("unknown taxonomy results cannot carry a resolved witness")
                allowed = {
                    "MISSING_SUBJECT",
                    "MISSING_TERM",
                    "NO_ASSIGNMENT",
                    "NO_CUISINE_PATH",
                    "UNSUPPORTED_HIERARCHY",
                    "MAX_HOPS_REACHED",
                    "MAX_VISITED_REACHED",
                }
                if self.reason_code not in allowed:
                    raise ValueError("unknown taxonomy status requires a gap or search reason")
                if self.traversal is TaxonomyTraversalMode.DIRECT and self.reason_code not in (
                    "MISSING_SUBJECT",
                    "MISSING_TERM",
                    "NO_ASSIGNMENT",
                ):
                    raise ValueError("DIRECT taxonomy results require a direct reason")
                if self.limit_reached != (
                    self.reason_code in ("MAX_HOPS_REACHED", "MAX_VISITED_REACHED")
                ):
                    raise ValueError("taxonomy limit flag contradicts its reason code")
                if self.reason_code == "MISSING_TERM" and self.term is not None:
                    raise ValueError("MISSING_TERM cannot carry the queried term")
                if self.reason_code == "UNSUPPORTED_HIERARCHY" and (
                    self.term is None or self.term.kind is TaxonomyKind.CUISINE
                ):
                    raise ValueError("unsupported hierarchy requires a known non-cuisine term")
        elif self.status is RelationResolutionStatus.SUPPORTED and self.path:
            self._validate_hierarchy_witness()
            if self.reason_code != "HIERARCHY_SUPPORTED" or self.conflicts or self.limit_reached:
                raise ValueError("supported cuisine witnesses cannot carry conflicts or limits")
            self._validate_selected_evidence()
        else:
            if (
                self.term is None
                or self.taxonomy_version is None
                or self.assignment is None
                or self.path
                or self.conflicts
                or self.limit_reached
            ):
                raise ValueError("direct taxonomy results require an exact versioned assignment")
            if (
                self.assignment.subject_id != self.subject_id
                or self.assignment.term_id != self.term_id
            ):
                raise ValueError("taxonomy assignment differs from the query")
            supported = self.status is RelationResolutionStatus.SUPPORTED
            expected = (
                TaxonomyAssignmentAssertion.PRESENT
                if supported
                else TaxonomyAssignmentAssertion.ABSENT
            )
            code = "DIRECT_SUPPORTED" if supported else "DIRECT_VERIFIED_ABSENT"
            if self.assignment.assertion is not expected or self.reason_code != code:
                raise ValueError("direct taxonomy status/reason contradicts its assertion")
            self._validate_selected_evidence()
        records = [*self.path]
        if self.term is not None:
            records.append(self.term)
        references = [*self.evidence, *(ref for term in records for ref in term.evidence)]
        if self.assignment is not None:
            references.extend(self.assignment.evidence)
        for conflict in self.conflicts:
            references.extend(conflict.evidence)
        provenance: dict[tuple[str, str], EvidenceReference] = {}
        for reference in references:
            identity = (reference.evidence_id, reference.version)
            if identity in provenance and provenance[identity] != reference:
                raise ValueError("conflicting taxonomy resolution evidence metadata")
            if reference.environment is not self.environment:
                raise ValueError("taxonomy resolution evidence must match its environment")
            provenance[identity] = reference
        return self

    def _validate_hierarchy_witness(self) -> None:
        if (
            self.traversal is not TaxonomyTraversalMode.CUISINE_PARENTS
            or self.term is None
            or self.taxonomy_version is None
            or self.assignment is None
            or len(self.path) < 2
        ):
            raise ValueError("hierarchy witnesses require cuisine traversal and versioned records")
        if (
            self.assignment.assertion is not TaxonomyAssignmentAssertion.PRESENT
            or self.assignment.subject_id != self.subject_id
            or self.assignment.term_id != self.path[0].term_id
            or self.path[-1] != self.term
        ):
            raise ValueError("hierarchy witness differs from its positive assignment or target")
        if any(term.kind is not TaxonomyKind.CUISINE for term in self.path):
            raise ValueError("only cuisine terms support hierarchy witnesses")
        if len({term.term_id for term in self.path}) != len(self.path):
            raise ValueError("hierarchy witnesses cannot repeat terms")
        for child, parent in zip(self.path, self.path[1:], strict=False):
            if parent.term_id not in child.parent_ids:
                raise ValueError("hierarchy witnesses require exact child-to-parent references")

    def _validate_selected_evidence(self) -> None:
        selected = set(self.assignment.evidence) if self.assignment is not None else set()
        for term in self.path:
            selected.update(term.evidence)
        for conflict in self.conflicts:
            selected.update(conflict.evidence)
        if selected != set(self.evidence):
            raise ValueError("taxonomy evidence must exactly match the selected witness records")
