"""Provisional KB release consistency, not source authentication or rule execution."""

import hashlib
import json
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Literal, Self

from pydantic import StringConstraints, model_validator

from savora_ai.schemas.food_graph import (
    FoodGraphSnapshot,
    _Environment,
    _OpaqueId,
    _require_evidence,
    _validate_canonical_enum,
)
from savora_ai.schemas.knowledge import (
    ApprovalStatus,
    EvidenceReference,
    RuleDefinition,
    RuleDomain,
    RuleEnvironment,
    RuleLifecycle,
    RuleReference,
    RuleScope,
    RuleSeverity,
    _ContractModel,
    _NonBlank,
)
from savora_ai.schemas.workflow_policy import (
    REGISTERED_SWAP_EXTENSIONS,
    WORKFLOW_POLICY_V2,
    WorkflowPolicyVersion,
)


class KnowledgeWorkflow(StrEnum):
    WEEKLY_PLAN = "WEEKLY_PLAN"
    CRAVING_DISCOVERY = "CRAVING_DISCOVERY"
    PLANNED_SWAP = "PLANNED_SWAP"


_SYNTHETIC_WORKFLOW_SCOPES = MappingProxyType(
    {
        KnowledgeWorkflow.WEEKLY_PLAN: tuple(RuleScope),
        KnowledgeWorkflow.CRAVING_DISCOVERY: (RuleScope.PROFILE, RuleScope.RECIPE),
        KnowledgeWorkflow.PLANNED_SWAP: tuple(RuleScope),
    }
)
_ContentDigest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


def _canonical_enum_inputs(value: object) -> None:
    """Guard Phase 1 enum instances before their identity-based validators run."""
    if isinstance(value, StrEnum):
        _validate_canonical_enum(value)
    elif isinstance(value, _ContractModel):
        for item in vars(value).values():
            _canonical_enum_inputs(item)
    elif isinstance(value, dict):
        for item in value.values():
            _canonical_enum_inputs(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _canonical_enum_inputs(item)


def _reference_key(reference: RuleReference) -> tuple[str, str]:
    return reference.rule_id, reference.version


def _unique_references(references: tuple[RuleReference, ...]) -> None:
    if len({_reference_key(item) for item in references}) != len(references):
        raise ValueError("duplicate exact rule reference")


class ApplicabilityDescriptor(_ContractModel):
    """Versioned dependency/context metadata; no applicability outcome is computed."""

    reference: RuleReference
    rule_references: tuple[RuleReference, ...]
    required_context_facts: tuple[_NonBlank, ...]
    dependencies: tuple[RuleReference, ...] = ()
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_descriptor(self) -> Self:
        _require_evidence(self.evidence)
        _unique_references(self.rule_references)
        _unique_references(self.dependencies)
        if not self.required_context_facts or (
            len(set(self.required_context_facts)) != len(self.required_context_facts)
        ):
            raise ValueError("applicability context facts must be nonempty and unique")
        if self.reference in self.dependencies:
            raise ValueError("self-dependent applicability descriptors are unsupported")
        return self


class CheckCatalogueEntry(_ContractModel):
    entry_id: _OpaqueId
    version: _NonBlank
    kb_id: _OpaqueId
    kb_version: _NonBlank
    check_catalogue_version: _NonBlank
    workflow: KnowledgeWorkflow
    scope: RuleScope
    rule_references: tuple[RuleReference, ...]
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_entry(self) -> Self:
        _validate_canonical_enum(self.workflow)
        _validate_canonical_enum(self.scope)
        _require_evidence(self.evidence)
        _unique_references(self.rule_references)
        return self


class RuleCatalogueCoverage(_ContractModel):
    """A KB-bound workflow/scope declaration; relation coverage has different semantics."""

    coverage_id: _OpaqueId
    version: _NonBlank
    kb_id: _OpaqueId
    kb_version: _NonBlank
    check_catalogue_version: _NonBlank
    workflow: KnowledgeWorkflow
    scope: RuleScope
    complete: bool
    reason: _NonBlank
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_coverage(self) -> Self:
        _validate_canonical_enum(self.workflow)
        _validate_canonical_enum(self.scope)
        _require_evidence(self.evidence)
        return self


class _KnowledgeContent(_ContractModel):
    """Shared release fields, validated before building or verifying the digest."""

    schema_version: Literal["knowledge-base.v1"] = "knowledge-base.v1"
    semantic_policy_version: Literal["knowledge-base-integrity.v1"] = "knowledge-base-integrity.v1"
    workflow_policy_version: WorkflowPolicyVersion = "synthetic-workflow-scopes.v1"
    kb_id: _OpaqueId
    version: _NonBlank
    environment: _Environment
    graph_id: _OpaqueId
    graph_version: _NonBlank
    catalogue_version: _NonBlank
    taxonomy_version: _NonBlank | None
    check_catalogue_version: _NonBlank
    graph: FoodGraphSnapshot
    rules: tuple[RuleDefinition, ...]
    active_rules: tuple[RuleReference, ...]
    applicability_descriptors: tuple[ApplicabilityDescriptor, ...]
    check_catalogue: tuple[CheckCatalogueEntry, ...]
    rule_catalogue_coverage: tuple[RuleCatalogueCoverage, ...]
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_content(self) -> Self:
        # The builder also guards raw enums before Phase 1 validators. This
        # check covers direct schema construction and native JSON decoding.
        _canonical_enum_inputs(self)
        _require_evidence(self.evidence)
        if (
            self.graph.graph_id != self.graph_id
            or self.graph.version != self.graph_version
            or self.graph.catalogue_version != self.catalogue_version
            or self.graph.taxonomy_version != self.taxonomy_version
            or self.graph.environment is not self.environment
        ):
            raise ValueError("KB graph/catalogue/taxonomy/environment binding mismatch")
        definitions = {(rule.rule_id, rule.version): rule for rule in self.rules}
        if len(definitions) != len(self.rules):
            raise ValueError("duplicate rule identity/version")
        _unique_references(self.active_rules)
        if len({item.rule_id for item in self.active_rules}) != len(self.active_rules):
            raise ValueError("multiple simultaneously serving versions of a rule")
        declared_active = {
            (rule.rule_id, rule.version)
            for rule in self.rules
            if rule.lifecycle is RuleLifecycle.ACTIVE
        }
        active = {_reference_key(item) for item in self.active_rules}
        for identity in active:
            rule = definitions.get(identity)
            if rule is None or rule.lifecycle is not RuleLifecycle.ACTIVE:
                raise ValueError("active references require exact ACTIVE rule definitions")
            if (
                rule.domain is RuleDomain.CLINICAL
                and rule.approval_status is not ApprovalStatus.APPROVED
            ):
                raise ValueError("serving clinical rules require explicit approval")
        if active != declared_active:
            raise ValueError("active references must include every declared ACTIVE definition")
        self._validate_applicability(definitions)
        self._validate_catalogue(definitions, active)
        self._validate_provenance()
        return self

    def _validate_applicability(self, definitions: dict[tuple[str, str], RuleDefinition]) -> None:
        descriptors = {
            _reference_key(item.reference): item for item in self.applicability_descriptors
        }
        if len(descriptors) != len(self.applicability_descriptors):
            raise ValueError("duplicate applicability identity/version")
        if len({item.reference.rule_id for item in self.applicability_descriptors}) != len(
            descriptors
        ):
            raise ValueError("multiple applicability versions in one release")
        hosts: dict[tuple[str, str], set[tuple[str, str]]] = {}
        for identity, rule in definitions.items():
            key = _reference_key(rule.applicability_reference)
            if key not in descriptors:
                raise ValueError("missing or stale applicability descriptor")
            hosts.setdefault(key, set()).add(identity)
        indegrees = dict.fromkeys(descriptors, 0)
        for key, descriptor in descriptors.items():
            references = {_reference_key(item) for item in descriptor.rule_references}
            if references != hosts.get(key, set()):
                raise ValueError(
                    "applicability rule references differ from exact hosted definitions"
                )
            for dependency in descriptor.dependencies:
                target = _reference_key(dependency)
                if target not in descriptors:
                    raise ValueError("missing or stale applicability dependency")
                indegrees[target] += 1
        pending = [key for key, degree in indegrees.items() if degree == 0]
        visited = 0
        while pending:
            key = pending.pop()
            visited += 1
            for dependency in descriptors[key].dependencies:
                target = _reference_key(dependency)
                indegrees[target] -= 1
                if indegrees[target] == 0:
                    pending.append(target)
        if visited != len(descriptors):
            raise ValueError("applicability dependency cycles are unsupported")

    def _validate_catalogue(
        self, definitions: dict[tuple[str, str], RuleDefinition], active: set[tuple[str, str]]
    ) -> None:
        # V1 deliberately ignores the registry, retaining exact legacy equality.
        extensions = {}
        if self.workflow_policy_version == WORKFLOW_POLICY_V2:
            if self.environment is not RuleEnvironment.SYNTHETIC:
                raise ValueError("registered workflow policy is synthetic only")
            for registration in REGISTERED_SWAP_EXTENSIONS:
                identity = registration.rule_id, registration.version
                rule = definitions.get(identity)
                if (
                    identity not in active
                    or rule is None
                    or rule.scope is not registration.scope
                    or rule.severity is not RuleSeverity.ABSOLUTE
                ):
                    raise ValueError("required registered workflow extension is missing or altered")
                encoded = json.dumps(
                    _canonical_value(rule.model_dump(mode="json", by_alias=True)),
                    sort_keys=True,
                    ensure_ascii=True,
                    allow_nan=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                if hashlib.sha256(encoded).hexdigest() != registration.definition_digest:
                    raise ValueError("registered workflow extension definition digest mismatch")
                extensions[identity] = registration
        required_cells = {
            (workflow, scope)
            for workflow, scopes in _SYNTHETIC_WORKFLOW_SCOPES.items()
            for scope in scopes
        }
        if len({entry.entry_id for entry in self.check_catalogue}) != len(self.check_catalogue):
            raise ValueError("duplicate expected-check entry identity")
        if len({item.coverage_id for item in self.rule_catalogue_coverage}) != len(
            self.rule_catalogue_coverage
        ):
            raise ValueError("duplicate rule-catalogue coverage identity")
        entries: dict[tuple[KnowledgeWorkflow, RuleScope], CheckCatalogueEntry] = {}
        for entry in self.check_catalogue:
            self._validate_release_binding(entry)
            cell = (entry.workflow, entry.scope)
            if cell not in required_cells or cell in entries:
                raise ValueError("unsupported or duplicate workflow/scope entry")
            expected = {
                identity
                for identity in active
                if definitions[identity].severity is RuleSeverity.ABSOLUTE
                and definitions[identity].scope is entry.scope
                and (
                    identity not in extensions
                    or entry.workflow.value in extensions[identity].workflows
                )
            }
            actual = {_reference_key(item) for item in entry.rule_references}
            for identity in actual:
                rule = definitions.get(identity)
                if (
                    identity not in active
                    or rule is None
                    or rule.severity is not RuleSeverity.ABSOLUTE
                    or rule.scope is not entry.scope
                ):
                    raise ValueError(
                        "checks require exact ACTIVE ABSOLUTE rules of the stated scope"
                    )
            if actual != expected:
                raise ValueError("expected-check entry omits a mandatory active hard rule")
            entries[cell] = entry
        if set(entries) != required_cells:
            raise ValueError("missing required workflow/scope expected-check entries")
        coverage: set[tuple[KnowledgeWorkflow, RuleScope]] = set()
        for item in self.rule_catalogue_coverage:
            self._validate_release_binding(item)
            cell = (item.workflow, item.scope)
            if cell not in required_cells or cell in coverage:
                raise ValueError("unsupported or duplicate workflow/scope coverage")
            if not item.complete:
                raise ValueError("incomplete expected-check catalogue coverage")
            coverage.add(cell)
        if coverage != required_cells:
            raise ValueError("missing required expected-check catalogue coverage")

    def _validate_release_binding(
        self, record: CheckCatalogueEntry | RuleCatalogueCoverage
    ) -> None:
        if (
            record.kb_id != self.kb_id
            or record.kb_version != self.version
            or record.check_catalogue_version != self.check_catalogue_version
        ):
            raise ValueError("expected-check KB/catalogue release binding mismatch")

    def _validate_provenance(self) -> None:
        references = [*self.evidence, *self.graph.evidence]
        for record in (
            *self.graph.entities,
            *self.graph.relations,
            *self.graph.coverage,
            *self.graph.taxonomy_terms,
            *self.graph.taxonomy_assignments,
            *self.applicability_descriptors,
            *self.check_catalogue,
            *self.rule_catalogue_coverage,
        ):
            references.extend(record.evidence)
        for rule in self.rules:
            if rule.environment is not self.environment:
                raise ValueError("every rule must match the KB environment")
            references.extend(rule.evidence)
            if rule.approval_reference is not None:
                references.append(rule.approval_reference)
        provenance: dict[tuple[str, str], EvidenceReference] = {}
        for reference in references:
            _validate_canonical_enum(reference.environment)
            identity = reference.evidence_id, reference.version
            if identity in provenance and provenance[identity] != reference:
                raise ValueError("conflicting evidence metadata across KB records")
            if reference.environment is not self.environment:
                raise ValueError("every evidence reference must match the KB environment")
            provenance[identity] = reference


def _canonical_value(value: object) -> object:
    """All release collections are unordered; preserve values/types, not tuple order."""
    if isinstance(value, dict):
        return {key: _canonical_value(item) for key, item in value.items()}
    if isinstance(value, list):
        normalized = [_canonical_value(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(
                item, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")
            ),
        )
    return value


def _compute_content_digest(content: _KnowledgeContent) -> str:
    data = content.model_dump(mode="json", by_alias=True, exclude={"content_digest"})
    canonical = json.dumps(
        _canonical_value(data),
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class KnowledgeBaseSnapshot(_KnowledgeContent):
    """Structurally consistent declarations; use the builder for release acceptance."""

    content_digest: _ContentDigest

    @model_validator(mode="after")
    def validate_digest(self) -> Self:
        if self.content_digest != _compute_content_digest(self):
            raise ValueError("KB content digest mismatch")
        return self
