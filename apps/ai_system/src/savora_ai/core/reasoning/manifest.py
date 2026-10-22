"""Derive complete fixed-stage obligations from an accepted synthetic KB catalogue."""

from typing import Self

from pydantic import ValidationError, model_validator

from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    FactSubjectKind,
    RuleContext,
    _content_digest,
    _validate_provenance,
)
from savora_ai.schemas.filtering import (
    _APPLICABILITY,
    _ATTRIBUTES,
    _COMBINATION_ATTRIBUTES,
    _DAY_ATTRIBUTES,
    _DERIVED_ATTRIBUTES,
    _WEEK_ATTRIBUTES,
    ExpectedCheckManifest,
    _ManifestContent,
    _validate_combination_rule_policy,
    _validate_day_rule_policy,
    _validate_week_rule_policy,
)
from savora_ai.schemas.knowledge import (
    ApprovalStatus,
    EvidenceReference,
    PredicateOperator,
    RuleDefinition,
    RuleDomain,
    RuleScope,
    _ContractModel,
)
from savora_ai.schemas.knowledge_base import (
    ApplicabilityDescriptor,
    KnowledgeBaseSnapshot,
    _reference_key,
)


def _reject(message: str) -> None:
    raise ValidationError.from_exception_data(
        "SyntheticRulePolicy",
        [{"type": "value_error", "loc": (), "input": None, "ctx": {"error": ValueError(message)}}],
    )


def _evidence_tree(value: object) -> tuple[EvidenceReference, ...]:
    if isinstance(value, EvidenceReference):
        return (value,)
    if isinstance(value, _ContractModel):
        return tuple(ref for item in vars(value).values() for ref in _evidence_tree(item))
    if isinstance(value, tuple):
        return tuple(ref for item in value for ref in _evidence_tree(item))
    return ()


class _KnowledgeContextRequest(_ContractModel):
    kb: KnowledgeBaseSnapshot
    context: RuleContext

    @model_validator(mode="after")
    def validate_bindings(self) -> Self:
        kb, context = self.kb, self.context
        expected = (
            context.expected_kb_id,
            context.expected_kb_version,
            context.expected_kb_digest,
            context.expected_graph_id,
            context.expected_graph_version,
            context.expected_taxonomy_version,
            context.expected_catalogue_version,
            context.expected_check_catalogue_version,
            context.workflow_policy_version,
        )
        actual = (
            kb.kb_id,
            kb.version,
            kb.content_digest,
            kb.graph_id,
            kb.graph_version,
            kb.taxonomy_version,
            kb.catalogue_version,
            kb.check_catalogue_version,
            kb.workflow_policy_version,
        )
        if expected != actual:
            raise ValueError("exact context KB/release expectation mismatch")
        references = _evidence_tree(self)
        unique = {(item.evidence_id, item.version): item for item in references}
        _validate_provenance(tuple(unique.values()))
        if any(unique[(ref.evidence_id, ref.version)] != ref for ref in references):
            raise ValueError("conflicting evidence across KB/candidate/context")
        return self


class _ManifestRequest(_KnowledgeContextRequest):
    candidate: CandidateRecipeFacts

    @model_validator(mode="after")
    def validate_candidate_binding(self) -> Self:
        kb, candidate, context = self.kb, self.candidate, self.context
        if (candidate.graph_id, candidate.graph_version, candidate.catalogue_version) != (
            kb.graph_id,
            kb.graph_version,
            kb.catalogue_version,
        ):
            raise ValueError("candidate graph/catalogue release mismatch")
        if candidate.context_id is not None and (
            candidate.context_id,
            candidate.context_version,
        ) != (context.context_id, context.version):
            raise ValueError("candidate context identity/version mismatch")
        entity = next(
            (
                item
                for item in kb.graph.entities
                if item.entity_id == candidate.graph_recipe_entity_id
            ),
            None,
        )
        if entity != candidate.graph_recipe_reference:
            raise ValueError("candidate recipe reference differs from accepted graph entity")
        return self


def _validate_rule_policy(rule: RuleDefinition) -> None:
    if rule.approval_status is not ApprovalStatus.APPROVED:
        _reject("Phase 3 mandatory hard rule is unapproved")
    if any(name in _WEEK_ATTRIBUTES for name in rule.required_facts):
        try:
            _validate_week_rule_policy(rule)
        except ValueError as error:
            _reject(str(error))
        return
    if any(name in _DAY_ATTRIBUTES for name in rule.required_facts):
        try:
            _validate_day_rule_policy(rule)
        except ValueError as error:
            _reject(str(error))
        return
    if any(name in _COMBINATION_ATTRIBUTES for name in rule.required_facts):
        try:
            _validate_combination_rule_policy(rule)
        except ValueError as error:
            _reject(str(error))
        return
    for name in rule.required_facts:
        policy = _ATTRIBUTES.get(name)
        if policy is None:
            _reject("unsupported synthetic required attribute")
            return
        if rule.scope is RuleScope.PROFILE and policy.subject is FactSubjectKind.RECIPE:
            _reject("PROFILE check cannot require recipe facts")
        if (
            name in _DERIVED_ATTRIBUTES
            and name
            not in (
                "synthetic_allergen_absent",
                "synthetic_clinically_safe",
            )
            and rule.domain is RuleDomain.CLINICAL
        ):
            _reject("exact graph/classification facts cannot authorize wider clinical claims")
    policy = _ATTRIBUTES[rule.attribute]
    expected = rule.value
    if policy.kind == "numeric":
        valid = type(expected) in (int, float)
    elif policy.kind == "boolean":
        valid = type(expected) is bool and rule.operator in (
            PredicateOperator.EQ,
            PredicateOperator.NE,
        )
    else:
        valid = (
            type(expected) is str and rule.operator in (PredicateOperator.EQ, PredicateOperator.NE)
        ) or (
            type(expected) is tuple
            and rule.operator in (PredicateOperator.IN, PredicateOperator.NOT_IN)
        )
    if not valid or rule.unit is not policy.unit:
        _reject("unsupported synthetic predicate/attribute/unit configuration")


def _descriptors_for(
    kb: KnowledgeBaseSnapshot, rules: tuple[RuleDefinition, ...]
) -> tuple[ApplicabilityDescriptor, ...]:
    descriptors = {_reference_key(item.reference): item for item in kb.applicability_descriptors}
    pending = [_reference_key(rule.applicability_reference) for rule in rules]
    selected: dict[tuple[str, str], ApplicabilityDescriptor] = {}
    while pending:
        key = pending.pop()
        if key in selected:
            continue
        descriptor = descriptors[key]  # The accepted KB already guarantees exact resolution.
        fact = _APPLICABILITY.get(key)
        if fact is None or descriptor.required_context_facts != (fact,):
            _reject("unsupported applicability identity or descriptor context mismatch")
        selected[key] = descriptor
        pending.extend(_reference_key(ref) for ref in descriptor.dependencies)
    return tuple(selected[key] for key in sorted(selected))


def build_expected_check_manifest(
    kb: KnowledgeBaseSnapshot, candidate: CandidateRecipeFacts, context: RuleContext
) -> ExpectedCheckManifest:
    """Revalidate inputs, accept the synthetic release, then resolve catalogue definitions.

    No rule-reference, applicability, stage, scope or reduced-check override is exposed.
    The caller owns independent trusted release selection and normalized source facts.
    """
    request = _ManifestRequest.model_validate(
        {"kb": kb, "candidate": candidate, "context": context}, strict=True
    )
    kb = build_knowledge_snapshot(request.kb, expected_digest=request.context.expected_kb_digest)
    candidate, context = request.candidate, request.context
    checks = _mandatory_checks(kb, context)
    body = _ManifestContent(
        workflow_policy_version=kb.workflow_policy_version,
        attribute_policy_version=(
            "synthetic-attributes.v5-week"
            if any(name in _WEEK_ATTRIBUTES for rule in checks for name in rule.required_facts)
            else "synthetic-attributes.v4-day"
            if any(name in _DAY_ATTRIBUTES for rule in checks for name in rule.required_facts)
            else "synthetic-attributes.v3-combination"
            if any(
                name in _COMBINATION_ATTRIBUTES for rule in checks for name in rule.required_facts
            )
            else "synthetic-attributes.v2"
            if any(name in _DERIVED_ATTRIBUTES for rule in checks for name in rule.required_facts)
            else "synthetic-attributes.v1"
        ),
        kb_id=kb.kb_id,
        kb_version=kb.version,
        kb_digest=kb.content_digest,
        graph_id=kb.graph_id,
        graph_version=kb.graph_version,
        taxonomy_version=kb.taxonomy_version,
        catalogue_version=kb.catalogue_version,
        check_catalogue_version=kb.check_catalogue_version,
        workflow=context.workflow,
        candidate_id=candidate.recipe_id,
        candidate_version=candidate.recipe_version,
        candidate_snapshot_id=candidate.snapshot_id,
        candidate_snapshot_version=candidate.snapshot_version,
        candidate_digest=candidate.content_digest,
        context_id=context.context_id,
        context_version=context.version,
        context_digest=context.content_digest,
        profile_id=context.profile_id,
        profile_version=context.profile_version,
        required_checks=tuple(
            rule for rule in checks if rule.scope in (RuleScope.PROFILE, RuleScope.RECIPE)
        ),
        deferred_checks=tuple(
            rule for rule in checks if rule.scope not in (RuleScope.PROFILE, RuleScope.RECIPE)
        ),
    )
    digest = _content_digest(body)
    return ExpectedCheckManifest.model_validate(
        body.model_dump()
        | {
            "manifest_id": "manifest-" + digest,
            "manifest_version": "synthetic-manifest.v1:" + digest,
            "content_digest": digest,
        }
    )


def _mandatory_checks(
    kb: KnowledgeBaseSnapshot, context: RuleContext
) -> tuple[RuleDefinition, ...]:
    """Also validate selected obligations for empty batches without inventing a candidate."""
    definitions = {(rule.rule_id, rule.version): rule for rule in kb.rules}
    # Catalogue integrity/complete coverage for ALL workflow cells is checked by KB acceptance.
    checks = tuple(
        sorted(
            (
                definitions[_reference_key(ref)]
                for entry in kb.check_catalogue
                if entry.workflow is context.workflow
                for ref in entry.rule_references
            ),
            key=lambda rule: (rule.rule_id, rule.version),
        )
    )
    for rule in checks:
        _validate_rule_policy(rule)
    _descriptors_for(kb, checks)
    return checks
