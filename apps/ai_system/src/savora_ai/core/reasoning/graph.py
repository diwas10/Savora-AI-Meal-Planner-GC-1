"""Direct assertions and bounded, evidenced origin paths in synthetic graphs."""

from collections import deque
from typing import Self

from pydantic import ValidationError, model_validator

from savora_ai.schemas.food_graph import (
    FoodGraphSnapshot,
    FoodRelation,
    FoodRelationType,
    KnowledgeCoverage,
    RelationAssertion,
    RelationQualifiers,
    RelationResolution,
    RelationResolutionStatus,
    TraversalMode,
    _OpaqueId,
    _RelationType,
    _ResolutionReason,
    _SearchLimit,
    _Traversal,
    _validate_endpoint_kinds,
    _validate_qualifiers,
    _validate_traversal,
)
from savora_ai.schemas.knowledge import EvidenceReference, RuleEnvironment, _ContractModel
from savora_ai.schemas.reasoning import _validation_payload


class _RelationQuery(_ContractModel):
    snapshot: FoodGraphSnapshot
    source_id: _OpaqueId
    target_id: _OpaqueId
    relation_type: _RelationType
    qualifiers: RelationQualifiers
    traversal: _Traversal
    max_hops: _SearchLimit
    max_visited: _SearchLimit

    @model_validator(mode="after")
    def validate_query(self) -> Self:
        if self.snapshot.environment is not RuleEnvironment.SYNTHETIC:
            raise ValueError(
                "this slice resolves SYNTHETIC snapshots only; production trust is deferred"
            )
        _validate_qualifiers(self.relation_type, self.qualifiers)
        _validate_traversal(self.relation_type, self.traversal)
        entities = {entity.entity_id: entity for entity in self.snapshot.entities}
        if self.source_id in entities and self.target_id in entities:
            _validate_endpoint_kinds(
                self.relation_type, entities[self.source_id], entities[self.target_id]
            )
        return self


def _ordered_evidence(evidence: tuple[EvidenceReference, ...]) -> tuple[EvidenceReference, ...]:
    return tuple(sorted(evidence, key=lambda item: (item.evidence_id, item.version)))


def _ordered_relation(relation: FoodRelation) -> FoodRelation:
    # Called only after complete snapshot revalidation.
    return FoodRelation.model_validate(
        relation.model_dump() | {"evidence": _ordered_evidence(relation.evidence)}, strict=True
    )


def _find_origin_path(
    query: _RelationQuery,
) -> tuple[tuple[FoodRelation, ...], _ResolutionReason, bool]:
    if query.source_id == query.target_id:
        return (), "NO_ORIGIN_PATH", False
    adjacency: dict[str, list[FoodRelation]] = {}
    for edge in query.snapshot.relations:
        if (
            edge.relation_type is FoodRelationType.DERIVED_FROM
            and edge.assertion is RelationAssertion.PRESENT
            and edge.qualifiers == query.qualifiers
        ):
            adjacency.setdefault(edge.source_id, []).append(edge)
    for edges in adjacency.values():
        edges.sort(key=lambda edge: edge.relation_id)
    pending = deque([(query.source_id, 0)])
    visited = {query.source_id}
    parents: dict[str, FoodRelation] = {}
    hops_blocked = False
    while pending:
        entity_id, depth = pending.popleft()
        for edge in adjacency.get(entity_id, ()):
            if edge.target_id in visited:
                continue
            if depth >= query.max_hops:
                hops_blocked = True
                continue
            if len(visited) >= query.max_visited:
                return (), "MAX_VISITED_REACHED", True
            visited.add(edge.target_id)
            parents[edge.target_id] = edge
            if edge.target_id == query.target_id:
                witness: list[FoodRelation] = []
                endpoint = query.target_id
                while endpoint != query.source_id:
                    parent = parents[endpoint]
                    witness.append(parent)
                    endpoint = parent.source_id
                return tuple(reversed(witness)), "ORIGIN_PATH_SUPPORTED", False
            pending.append((edge.target_id, depth + 1))
    if hops_blocked:
        return (), "MAX_HOPS_REACHED", True
    return (), "NO_ORIGIN_PATH", False


def resolve_food_relations(
    snapshot: FoodGraphSnapshot,
    *,
    source_id: str,
    target_id: str,
    relation_type: FoodRelationType,
    qualifiers: RelationQualifiers | None = None,
    traversal: TraversalMode = TraversalMode.DIRECT,
    max_hops: int = 8,
    max_visited: int = 256,
) -> RelationResolution:
    """Revalidate all nested fields, then resolve an assertion or positive origin path.

    Invalid declarations raise ValidationError. Missing entities/edges stay UNKNOWN.
    Metadata and VERIFIED_ABSENT do not authenticate sources or establish safety.
    """
    try:
        payload = _validation_payload(
            {
                "snapshot": snapshot,
                "source_id": source_id,
                "target_id": target_id,
                "relation_type": relation_type,
                "qualifiers": RelationQualifiers() if qualifiers is None else qualifiers,
                "traversal": traversal,
                "max_hops": max_hops,
                "max_visited": max_visited,
            }
        )
    except RecursionError as error:
        raise ValidationError.from_exception_data(
            "FoodRelationQuery",
            [
                {
                    "type": "value_error",
                    "loc": (),
                    "input": None,
                    "ctx": {"error": ValueError("cyclic or excessively deep graph query payload")},
                }
            ],
        ) from error
    query = _RelationQuery.model_validate(payload, strict=True)
    graph = query.snapshot
    entity_ids = {entity.entity_id for entity in graph.entities}
    coverage = next(
        (
            item
            for item in graph.coverage
            if item.subject_id == query.source_id
            and item.relation_type is query.relation_type
            and item.qualifiers == query.qualifiers
        ),
        None,
    )
    relation = None
    path: tuple[FoodRelation, ...] = ()
    limit_reached = False
    status = RelationResolutionStatus.UNKNOWN
    if query.source_id not in entity_ids or query.target_id not in entity_ids:
        reason = "A caller entity ID is absent from this snapshot; its relationship is unknown."
        reason_code: _ResolutionReason = "MISSING_ENTITY"
    elif query.traversal is TraversalMode.ORIGIN_PATH:
        path, reason_code, limit_reached = _find_origin_path(query)
        if path:
            status = RelationResolutionStatus.SUPPORTED
            reason = "A shortest positive derivation path evidences origin reachability only."
        elif reason_code == "MAX_HOPS_REACHED":
            reason = (
                f"max_hops={query.max_hops} blocked further exploration; origin remains unknown."
            )
        elif reason_code == "MAX_VISITED_REACHED":
            reason = (
                f"max_visited={query.max_visited} blocked another entity; origin remains unknown."
            )
        else:
            reason = "Positive directed derivation search exhausted without an origin witness."
    else:
        relation = next(
            (
                item
                for item in graph.relations
                if item.source_id == query.source_id
                and item.target_id == query.target_id
                and item.relation_type is query.relation_type
                and item.qualifiers == query.qualifiers
            ),
            None,
        )
        if relation is None:
            reason_code = "NO_DIRECT_ASSERTION"
            reason = (
                "No exact directed qualified assertion exists; coverage does not prove absence."
            )
        elif relation.assertion is RelationAssertion.PRESENT:
            status = RelationResolutionStatus.SUPPORTED
            reason_code = "DIRECT_SUPPORTED"
            reason = "An explicit positive assertion supports this exact directed qualified query."
        else:
            status = RelationResolutionStatus.VERIFIED_ABSENT
            reason_code = "DIRECT_VERIFIED_ABSENT"
            reason = (
                "An explicit negative assertion supports absence for this exact direct query only."
            )
    if path:
        path_evidence = {
            (reference.evidence_id, reference.version): reference
            for edge in path
            for reference in edge.evidence
        }
        evidence = tuple(path_evidence.values())
    elif relation is not None:
        evidence = relation.evidence
    else:
        evidence = coverage.evidence if coverage is not None else graph.evidence
    # All contents have already been validated; canonicalize embedded evidence too.
    if relation is not None:
        relation = _ordered_relation(relation)
    path = tuple(_ordered_relation(edge) for edge in path)
    if coverage is not None:
        coverage = KnowledgeCoverage.model_validate(
            coverage.model_dump() | {"evidence": _ordered_evidence(coverage.evidence)}, strict=True
        )
    return RelationResolution(
        graph_id=graph.graph_id,
        graph_version=graph.version,
        catalogue_version=graph.catalogue_version,
        semantic_policy_version=graph.semantic_policy_version,
        environment=graph.environment,
        source_id=query.source_id,
        target_id=query.target_id,
        relation_type=query.relation_type,
        qualifiers=query.qualifiers,
        traversal=query.traversal,
        status=status,
        relation=relation,
        coverage=coverage,
        evidence=_ordered_evidence(evidence),
        reason=reason,
        path=path,
        limit_reached=limit_reached,
        reason_code=reason_code,
    )
