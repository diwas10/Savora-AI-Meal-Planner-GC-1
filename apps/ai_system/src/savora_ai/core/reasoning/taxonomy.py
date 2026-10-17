"""Exact taxonomy assignments and bounded, conservative cuisine membership only."""

from collections import deque
from typing import Self

from pydantic import ValidationError, model_validator

from savora_ai.schemas.food_graph import (
    _FOOD_KINDS,
    FoodGraphSnapshot,
    RelationResolutionStatus,
    TaxonomyAssignment,
    TaxonomyAssignmentAssertion,
    TaxonomyKind,
    TaxonomyResolution,
    TaxonomyTerm,
    TaxonomyTraversalMode,
    _OpaqueId,
    _SearchLimit,
    _TaxonomyResolutionReason,
    _TaxonomyTraversal,
)
from savora_ai.schemas.knowledge import EvidenceReference, RuleEnvironment, _ContractModel
from savora_ai.schemas.reasoning import _validation_payload


class _TaxonomyQuery(_ContractModel):
    snapshot: FoodGraphSnapshot
    subject_id: _OpaqueId
    term_id: _OpaqueId
    traversal: _TaxonomyTraversal
    max_hops: _SearchLimit
    max_visited: _SearchLimit

    @model_validator(mode="after")
    def validate_query(self) -> Self:
        if self.snapshot.environment is not RuleEnvironment.SYNTHETIC:
            raise ValueError("taxonomy resolution accepts SYNTHETIC snapshots only")
        subject = next(
            (item for item in self.snapshot.entities if item.entity_id == self.subject_id), None
        )
        if subject is not None and subject.kind not in _FOOD_KINDS:
            raise ValueError("taxonomy queries require an ingredient or recipe reference subject")
        return self


def _ordered_evidence(references: set[EvidenceReference]) -> tuple[EvidenceReference, ...]:
    return tuple(sorted(references, key=lambda item: (item.evidence_id, item.version)))


def _ordered_term(term: TaxonomyTerm) -> TaxonomyTerm:
    return TaxonomyTerm.model_validate(
        term.model_dump()
        | {
            "parent_ids": tuple(sorted(term.parent_ids)),
            "evidence": _ordered_evidence(set(term.evidence)),
        }
    )


def _ordered_assignment(assignment: TaxonomyAssignment) -> TaxonomyAssignment:
    return TaxonomyAssignment.model_validate(
        assignment.model_dump() | {"evidence": _ordered_evidence(set(assignment.evidence))}
    )


def _find_cuisine_path(
    query: _TaxonomyQuery, terms: dict[str, TaxonomyTerm]
) -> tuple[TaxonomyAssignment | None, tuple[TaxonomyTerm, ...], _TaxonomyResolutionReason, bool]:
    seeds = sorted(
        (
            assignment
            for assignment in query.snapshot.taxonomy_assignments
            if assignment.subject_id == query.subject_id
            and assignment.assertion is TaxonomyAssignmentAssertion.PRESENT
            and terms[assignment.term_id].kind is TaxonomyKind.CUISINE
        ),
        key=lambda assignment: assignment.assignment_id,
    )
    pending: deque[tuple[str, int]] = deque()
    visited: set[str] = set()
    roots: dict[str, TaxonomyAssignment] = {}
    parents: dict[str, str] = {}
    for seed in seeds:
        if len(visited) >= query.max_visited:
            return None, (), "MAX_VISITED_REACHED", True
        visited.add(seed.term_id)
        roots[seed.term_id] = seed
        pending.append((seed.term_id, 0))
    hops_blocked = False
    while pending:
        term_id, depth = pending.popleft()
        for parent_id in sorted(terms[term_id].parent_ids):
            if parent_id in visited:
                continue
            if depth >= query.max_hops:
                hops_blocked = True
                continue
            if len(visited) >= query.max_visited:
                return None, (), "MAX_VISITED_REACHED", True
            visited.add(parent_id)
            parents[parent_id] = term_id
            if parent_id == query.term_id:
                reverse_ids = [parent_id]
                while reverse_ids[-1] in parents:
                    reverse_ids.append(parents[reverse_ids[-1]])
                path = tuple(terms[item] for item in reversed(reverse_ids))
                return roots[reverse_ids[-1]], path, "HIERARCHY_SUPPORTED", False
            pending.append((parent_id, depth + 1))
    if hops_blocked:
        return None, (), "MAX_HOPS_REACHED", True
    return None, (), "NO_CUISINE_PATH", False


def resolve_taxonomy_assignment(
    snapshot: FoodGraphSnapshot,
    *,
    subject_id: str,
    term_id: str,
    traversal: TaxonomyTraversalMode = TaxonomyTraversalMode.DIRECT,
    max_hops: int = 8,
    max_visited: int = 256,
) -> TaxonomyResolution:
    """Revalidate everything; missing knowledge stays UNKNOWN, invalid input raises.

    Snapshot validation rejects any cuisine negative in the complete positive
    ancestor closure for that subject, regardless of query bounds or path order.
    CUISINE_PARENTS then checks exact positives and selects a shortest positive
    child-to-parent witness. Selected-witness checks remain defensive safeguards.
    """
    try:
        payload = _validation_payload(
            {
                "snapshot": snapshot,
                "subject_id": subject_id,
                "term_id": term_id,
                "traversal": traversal,
                "max_hops": max_hops,
                "max_visited": max_visited,
            }
        )
    except RecursionError as error:
        raise ValidationError.from_exception_data(
            "TaxonomyQuery",
            [
                {
                    "type": "value_error",
                    "loc": (),
                    "input": None,
                    "ctx": {
                        "error": ValueError("cyclic or excessively deep taxonomy query payload")
                    },
                }
            ],
        ) from error
    query = _TaxonomyQuery.model_validate(payload, strict=True)
    graph = query.snapshot
    terms = {term.term_id: term for term in graph.taxonomy_terms}
    term = terms.get(query.term_id)
    exact = next(
        (
            assignment
            for assignment in graph.taxonomy_assignments
            if assignment.subject_id == query.subject_id and assignment.term_id == query.term_id
        ),
        None,
    )
    assignment = None
    path: tuple[TaxonomyTerm, ...] = ()
    conflicts: tuple[TaxonomyAssignment, ...] = ()
    limited = False
    status = RelationResolutionStatus.UNKNOWN
    if query.subject_id not in {entity.entity_id for entity in graph.entities}:
        code: _TaxonomyResolutionReason = "MISSING_SUBJECT"
    elif term is None:
        code = "MISSING_TERM"
    elif query.traversal is TaxonomyTraversalMode.DIRECT or (
        exact is not None and exact.assertion is TaxonomyAssignmentAssertion.PRESENT
    ):
        assignment = exact
        if exact is None:
            code = "NO_ASSIGNMENT"
        elif exact.assertion is TaxonomyAssignmentAssertion.PRESENT:
            status = RelationResolutionStatus.SUPPORTED
            code = "DIRECT_SUPPORTED"
        else:
            status = RelationResolutionStatus.VERIFIED_ABSENT
            code = "DIRECT_VERIFIED_ABSENT"
    elif term.kind is not TaxonomyKind.CUISINE:
        if exact is not None:
            assignment = exact
            status = RelationResolutionStatus.VERIFIED_ABSENT
            code = "DIRECT_VERIFIED_ABSENT"
        else:
            code = "UNSUPPORTED_HIERARCHY"
    else:
        assignment, path, code, limited = _find_cuisine_path(query, terms)
        if path:
            # Defensive result check; accepted snapshots cannot contain these conflicts.
            path_ids = {item.term_id for item in path}
            conflicts = tuple(
                sorted(
                    (
                        item
                        for item in graph.taxonomy_assignments
                        if item.subject_id == query.subject_id
                        and item.term_id in path_ids
                        and item.assertion is TaxonomyAssignmentAssertion.ABSENT
                    ),
                    key=lambda item: item.assignment_id,
                )
            )
            if conflicts:
                code = "HIERARCHY_CONFLICT"
            else:
                status = RelationResolutionStatus.SUPPORTED
        elif exact is not None and not limited:
            assignment = exact
            status = RelationResolutionStatus.VERIFIED_ABSENT
            code = "DIRECT_VERIFIED_ABSENT"
    if assignment is not None:
        selected = set(assignment.evidence)
        for item in path:
            selected.update(item.evidence)
        for item in conflicts:
            selected.update(item.evidence)
    else:
        selected = set(exact.evidence if exact is not None else graph.evidence)
    reasons = {
        "DIRECT_SUPPORTED": "An exact positive assignment evidences classification only.",
        "DIRECT_VERIFIED_ABSENT": "An exact negative assignment is evidenced; this is not safety.",
        "MISSING_SUBJECT": "The subject ID is absent; classification is unknown.",
        "MISSING_TERM": "The taxonomy term ID is absent; labels are never matched automatically.",
        "NO_ASSIGNMENT": "No exact taxonomy assignment exists; its absence proves nothing.",
        "NO_CUISINE_PATH": "Positive cuisine parent search exhausted without a membership witness.",
        "UNSUPPORTED_HIERARCHY": "Only cuisine membership supports parent traversal.",
        "HIERARCHY_SUPPORTED": "A shortest positive cuisine parent witness supports membership.",
        "HIERARCHY_CONFLICT": "Negative assignments contradict membership on the selected witness.",
        "MAX_HOPS_REACHED": f"max_hops={query.max_hops} blocked exploration; membership unknown.",
        "MAX_VISITED_REACHED": f"max_visited={query.max_visited} blocked discovery; unknown.",
    }
    return TaxonomyResolution(
        graph_id=graph.graph_id,
        graph_version=graph.version,
        catalogue_version=graph.catalogue_version,
        semantic_policy_version=graph.semantic_policy_version,
        taxonomy_version=graph.taxonomy_version,
        environment=graph.environment,
        subject_id=query.subject_id,
        term_id=query.term_id,
        term=None if term is None else _ordered_term(term),
        traversal=query.traversal,
        status=status,
        assignment=None if assignment is None else _ordered_assignment(assignment),
        path=tuple(_ordered_term(item) for item in path),
        conflicts=tuple(_ordered_assignment(item) for item in conflicts),
        evidence=_ordered_evidence(selected),
        reason_code=code,
        reason=reasons[code],
        limit_reached=limited,
    )
