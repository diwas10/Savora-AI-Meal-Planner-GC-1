"""Exact synthetic applicability and compliance predicates, without filtering or KG inference."""

from savora_ai.core.reasoning.facts import resolve_rule_facts
from savora_ai.core.reasoning.manifest import (
    _descriptors_for,
    _ManifestRequest,
    _reject,
)
from savora_ai.schemas.candidates import CandidateRecipeFacts, RuleContext, VersionedFact
from savora_ai.schemas.filtering import (
    _APPLICABILITY,
    CandidateFactResolution,
    ExpectedCheckManifest,
)
from savora_ai.schemas.knowledge import EvidenceReference, PredicateOperator, RuleDefinition
from savora_ai.schemas.knowledge_base import (
    ApplicabilityDescriptor,
    KnowledgeBaseSnapshot,
    _reference_key,
)
from savora_ai.schemas.reasoning import (
    ApplicabilityStatus,
    FactObservation,
    RuleEvaluation,
    RuleStatus,
)


class _EvaluationRequest(_ManifestRequest):
    manifest: ExpectedCheckManifest


def _unique_evidence(references: tuple[EvidenceReference, ...]) -> tuple[EvidenceReference, ...]:
    # All inputs were cross-validated for conflicting provenance before deduplication.
    indexed = {(ref.evidence_id, ref.version): ref for ref in references}
    return tuple(indexed[key] for key in sorted(indexed))


def _observation(fact: VersionedFact) -> FactObservation:
    basis = fact.basis_reference
    return FactObservation.model_validate(
        fact.observation.model_dump()
        | {
            "evidence": _unique_evidence(
                (*fact.observation.evidence, *((basis,) if basis is not None else ()))
            ),
        }
    )


def _applicability(
    descriptors: tuple[ApplicabilityDescriptor, ...],
    facts: dict[str, VersionedFact],
    context: RuleContext,
) -> dict[tuple[str, str], tuple[ApplicabilityStatus, tuple[EvidenceReference, ...]]]:
    results: dict[tuple[str, str], tuple[ApplicabilityStatus, tuple[EvidenceReference, ...]]] = {}
    pending = {_reference_key(item.reference): item for item in descriptors}
    # Iterative dependency traversal avoids recursion limits on valid KB DAGs.
    while pending:
        ready = [
            key
            for key, item in pending.items()
            if all(_reference_key(ref) in results for ref in item.dependencies)
        ]
        if not ready:
            _reject("unresolved applicability dependency graph")
        for key in sorted(ready):
            descriptor = pending.pop(key)
            fact = facts.get(_APPLICABILITY[key])
            observation = None if fact is None else fact.observation
            if observation is None or observation.value is None or not observation.complete:
                own = ApplicabilityStatus.UNKNOWN
            else:
                own = (
                    ApplicabilityStatus.APPLICABLE
                    if observation.value is True
                    else ApplicabilityStatus.NOT_APPLICABLE
                )
            dependencies = [results[_reference_key(ref)] for ref in descriptor.dependencies]
            states = [own, *(result[0] for result in dependencies)]
            # Conservative conjunction: incompleteness dominates any evidenced false.
            if ApplicabilityStatus.UNKNOWN in states:
                state = ApplicabilityStatus.UNKNOWN
            elif ApplicabilityStatus.NOT_APPLICABLE in states:
                state = ApplicabilityStatus.NOT_APPLICABLE
            else:
                state = ApplicabilityStatus.APPLICABLE
            evidence = _unique_evidence(
                (
                    *descriptor.evidence,
                    *(context.evidence if observation is None else observation.evidence),
                    *(ref for result in dependencies for ref in result[1]),
                )
            )
            results[key] = state, evidence
    return results


def _predicate(rule: RuleDefinition, attribute: FactObservation) -> bool:
    value, expected = attribute.value, rule.value
    # Types/units/bases have already been checked even when required facts are unknown.
    # Narrow operands explicitly for static checking, without casting or normalization.
    if rule.operator in (PredicateOperator.IN, PredicateOperator.NOT_IN):
        assert isinstance(value, str) and isinstance(expected, tuple)
        contains = value in expected
        return contains if rule.operator is PredicateOperator.IN else not contains
    if rule.operator is PredicateOperator.EQ:
        return value == expected
    if rule.operator is PredicateOperator.NE:
        return value != expected
    assert type(value) in (int, float) and type(expected) in (int, float)
    assert isinstance(value, (int, float)) and isinstance(expected, (int, float))
    if rule.operator is PredicateOperator.LT:
        return value < expected
    if rule.operator is PredicateOperator.LE:
        return value <= expected
    if rule.operator is PredicateOperator.GT:
        return value > expected
    if rule.operator is PredicateOperator.GE:
        return value >= expected
    raise AssertionError("validated policy cannot expose an unsupported operator")


def evaluate_rule_checks(
    kb: KnowledgeBaseSnapshot,
    candidate: CandidateRecipeFacts,
    context: RuleContext,
    manifest: ExpectedCheckManifest,
) -> tuple[RuleEvaluation, ...]:
    """Return one validated evaluation per mandatory recipe-stage check, in ID order.

    Rebuild the manifest from the accepted release; self-hashed reduced/altered manifests
    are rejected. Deferred obligations are preserved on the manifest and never executed.
    Structural errors raise ValidationError; missing knowledge returns UNKNOWN.
    """
    request = _EvaluationRequest.model_validate(
        {"kb": kb, "candidate": candidate, "context": context, "manifest": manifest},
        strict=True,
    )
    kb, candidate, context = request.kb, request.candidate, request.context
    resolution = resolve_rule_facts(candidate, knowledge=kb, context=context)
    trusted = resolution.manifest
    if request.manifest.content_digest != trusted.content_digest:
        _reject("manifest differs from complete accepted-KB obligations or exact bindings")
    return _evaluate_resolved_checks(kb, context, resolution)


def _evaluate_resolved_checks(
    kb: KnowledgeBaseSnapshot,
    context: RuleContext,
    resolution: CandidateFactResolution,
) -> tuple[RuleEvaluation, ...]:
    """Internal composition only: resolution is produced locally by resolve_rule_facts."""
    trusted = resolution.manifest
    facts = {item.fact.fact_id: item.fact for item in resolution.facts}
    descriptors = _descriptors_for(kb, trusted.required_checks)
    applicability = _applicability(descriptors, facts, context)
    evaluations: list[RuleEvaluation] = []
    for rule in trusted.required_checks:
        state, evidence = applicability[_reference_key(rule.applicability_reference)]
        observations = tuple(
            _observation(facts[name]) for name in sorted(rule.required_facts) if name in facts
        )
        status = RuleStatus.UNKNOWN
        if state is ApplicabilityStatus.UNKNOWN:
            reason = "APPLICABILITY_UNKNOWN"
        elif state is ApplicabilityStatus.NOT_APPLICABLE:
            reason = "NOT_APPLICABLE"
        elif any(
            name not in facts
            or facts[name].observation.value is None
            or not facts[name].observation.complete
            for name in rule.required_facts
        ):
            reason = "REQUIRED_FACT_UNKNOWN"
        else:
            status = (
                RuleStatus.PASS
                if _predicate(rule, facts[rule.attribute].observation)
                else RuleStatus.FAIL
            )
            reason = "PREDICATE_TRUE" if status is RuleStatus.PASS else "PREDICATE_FALSE"
        evaluations.append(
            RuleEvaluation(
                rule=rule,
                applicability=state,
                applicability_evidence=evidence,
                facts=observations,
                status=status,
                reason=trusted.evaluator_policy_version + ":" + reason,
            )
        )
    return tuple(evaluations)
