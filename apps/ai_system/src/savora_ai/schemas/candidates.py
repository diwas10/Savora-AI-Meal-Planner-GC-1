"""Synthetic subject-bound facts and snapshots; no inference or eligibility execution."""

import hashlib
import json
from collections.abc import Iterator
from enum import EnumType, StrEnum
from hmac import compare_digest
from math import isfinite
from typing import Literal, Self, cast

from pydantic import BaseModel, TypeAdapter, ValidationError, field_validator, model_validator

from savora_ai.schemas.food_graph import FoodEntity, FoodEntityKind, _OpaqueId
from savora_ai.schemas.knowledge import (
    EvidenceReference,
    MeasurementUnit,
    RuleEnvironment,
    _ContractModel,
    _NonBlank,
    _require_canonical_enum,
    _validate_evidence,
)
from savora_ai.schemas.knowledge_base import KnowledgeWorkflow, _ContentDigest
from savora_ai.schemas.reasoning import FactObservation

STRICT_JSON_MAX_BYTES = 1_048_576
STRICT_JSON_MAX_DEPTH = 64
STRICT_JSON_MAX_OUTPUT_DEPTH = 128
STRICT_JSON_MAX_OUTPUT_NODES = 1_048_576


def _unique_json_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
    members: dict[str, object] = {}
    for name, value in pairs:
        if name in members:
            raise ValueError("duplicate JSON object member name")
        members[name] = value
    return members


def _reject_json_constant(token: str) -> object:
    raise ValueError("nonfinite JSON numeric constants are unsupported")


def _finite_json_float(token: str) -> float:
    value = float(token)
    if not isfinite(value):
        raise ValueError("JSON number exceeds finite floating-point range")
    return value


def _check_json_depth(text: str) -> None:
    """Bound containers before decoding; the JSON parser checks the actual grammar."""
    depth = 0
    quoted = False
    escaped = False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > STRICT_JSON_MAX_DEPTH:
                raise ValueError("JSON container nesting exceeds the 64-level ingress limit")
        elif character in "]}":
            # Invalid unmatched closing delimiters are rejected by json.loads.
            depth = max(0, depth - 1)


def _output_children(value: object) -> Iterator[object]:
    kind = type(value)
    if kind is dict:
        for key, item in dict.items(cast(dict[object, object], value)):
            yield key
            yield item
    elif kind is list:
        yield from list.__iter__(cast(list[object], value))
    elif kind is tuple:
        yield from tuple.__iter__(cast(tuple[object, ...], value))
    elif kind is set:
        yield from set.__iter__(cast(set[object], value))
    elif kind is frozenset:
        yield from frozenset.__iter__(cast(frozenset[object], value))
    else:
        # Inspect actual class ancestry without object __class__ tricks or arbitrary
        # metaclass attribute access. These are Python's own fixed descriptors.
        bases = type.__dict__["__mro__"].__get__(kind)
        if not any(base is BaseModel for base in bases):
            raise ValueError("unsupported validated output type")
        model_type = cast(type[BaseModel], kind)
        computed = model_type.model_computed_fields
        if type(computed) is not dict or computed:
            raise ValueError("models with computed fields are unsupported at strict JSON ingress")
        for name in ("__dict__", "__pydantic_extra__", "__pydantic_private__"):
            # Read actual managed storage, bypassing instance properties, overridden
            # __getattribute__ and serializers. Never enumerate arbitrary attributes.
            try:
                storage = BaseModel.__dict__[name].__get__(value, kind)
            except AttributeError:
                if name == "__dict__":
                    raise ValueError("validated model is missing field storage") from None
                continue  # RootModel may leave extra/private slots unset.
            if storage is not None:
                if type(storage) is not dict:
                    raise ValueError("validated model storage requires a built-in dictionary")
                yield storage


def _check_validated_output(result: object) -> None:
    """Inspect a bounded data graph without coercion, serialization or custom iteration."""
    pending: list[tuple[object, int, bool]] = [(result, 0, False)]
    active: set[int] = set()
    complete: set[int] = set()
    visited = 0
    while pending:
        value, depth, leaving = pending.pop()
        identity = id(value)
        if leaving:
            active.remove(identity)
            complete.add(identity)
            continue
        visited += 1
        if visited > STRICT_JSON_MAX_OUTPUT_NODES or depth > STRICT_JSON_MAX_OUTPUT_DEPTH:
            raise ValueError("validated output exceeds the bounded traversal limit")
        kind = type(value)
        if (
            value is None
            or kind is bool
            or kind is int
            or kind is str
            or kind is bytes
            or kind is bytearray
        ):
            continue
        if kind is float:
            if not isfinite(cast(float, value)):
                raise ValueError("validated output contains a nonfinite float")
            continue
        bases = type.__dict__["__mro__"].__get__(kind)
        if any(base is StrEnum for base in bases):
            if type(kind) is not EnumType:
                raise ValueError("custom enum metaclasses are unsupported at strict JSON ingress")
            _require_canonical_enum(cast(StrEnum, value))
            if type(object.__getattribute__(value, "_value_")) is not str:
                raise ValueError("validated StrEnum requires a built-in string value")
            continue
        if identity in active:
            raise ValueError("cyclic validated outputs are unsupported at strict JSON ingress")
        if identity in complete:
            continue  # Shared acyclic data is allowed; it was already inspected.
        active.add(identity)
        pending.append((value, depth, True))
        for child in _output_children(value):
            if visited + len(pending) >= STRICT_JSON_MAX_OUTPUT_NODES:
                raise ValueError("validated output exceeds the bounded traversal limit")
            pending.append((child, depth + 1, False))


def validate_contract_json[Result](
    target: type[Result] | TypeAdapter[Result], payload: str | bytes | bytearray
) -> Result:
    """Strict raw-JSON ingress for model classes or adapters, including nested DTOs.

    Native model/adapter JSON methods cannot inspect duplicate keys after decoding;
    security-sensitive callers must use this function on the original raw input.
    Limits are UTF-8 without BOM, 1 MiB and 64 object/array levels. Python-object
    contracts are unchanged. Parse/output errors use ValidationError with no raw input.
    Supported results are built-in scalar/containers, canonical StrEnum and ordinary
    BaseModel/RootModel data without computed fields. Opaque/custom outputs are rejected.
    """
    try:
        # Do not invoke custom input subclasses' len/encode/decode implementations.
        if type(payload) not in (str, bytes, bytearray):
            raise ValueError("JSON ingress requires a built-in str, bytes or bytearray")
        if len(payload) > STRICT_JSON_MAX_BYTES:
            raise ValueError("JSON input exceeds the 1 MiB ingress limit")
        if isinstance(payload, str):
            text = payload
            size = len(text.encode("utf-8"))
        else:
            size = len(payload)
            text = payload.decode("utf-8")
        if size > STRICT_JSON_MAX_BYTES:
            raise ValueError("JSON input exceeds the 1 MiB ingress limit")
        _check_json_depth(text)
        json.loads(
            text,
            object_pairs_hook=_unique_json_members,
            parse_constant=_reject_json_constant,
            parse_float=_finite_json_float,
        )
    except (ValueError, RecursionError, OverflowError) as error:
        raise ValidationError.from_exception_data(
            "StrictJsonIngress",
            [
                {
                    "type": "value_error",
                    "loc": (),
                    "input": None,
                    # JSONDecodeError stores the raw document; keep only its message
                    # in the public validation context, not that exception object.
                    "ctx": {"error": ValueError(str(error))},
                }
            ],
        ) from error
    # Keep original spelling/order/numeric tokens and native JSON enum/array behavior.
    # Never feed the parsed Python tree to strict Python-mode DTO validation.
    adapter = target if isinstance(target, TypeAdapter) else TypeAdapter(target)
    result = adapter.validate_json(text, strict=True)
    try:
        _check_validated_output(result)
    except ValueError as error:
        raise ValidationError.from_exception_data(
            "StrictJsonOutput",
            [{"type": "value_error", "loc": (), "input": None, "ctx": {"error": error}}],
        ) from error
    return result


class FactSubjectKind(StrEnum):
    RECIPE = "RECIPE"
    INGREDIENT = "INGREDIENT"
    PROFILE = "PROFILE"
    CONTEXT = "CONTEXT"


class MeasurementBasis(StrEnum):
    AS_RECORDED = "AS_RECORDED"
    PER_100_G = "PER_100_G"
    PER_SERVING = "PER_SERVING"


class IngredientMappingStatus(StrEnum):
    MAPPED = "MAPPED"
    UNRESOLVED = "UNRESOLVED"


class IngredientGapReason(StrEnum):
    MISSING_INVENTORY = "MISSING_INVENTORY"
    INCOMPLETE_INVENTORY = "INCOMPLETE_INVENTORY"
    UNRESOLVED_MAPPING = "UNRESOLVED_MAPPING"
    INCOMPLETE_SUBINGREDIENTS = "INCOMPLETE_SUBINGREDIENTS"


_FOOD_SUBJECTS = (FactSubjectKind.RECIPE, FactSubjectKind.INGREDIENT)


def _validate_provenance(references: tuple[EvidenceReference, ...]) -> None:
    """Allow identical reuse globally, but never contradictory or production labels."""
    seen: dict[tuple[str, str], EvidenceReference] = {}
    for reference in references:
        _require_canonical_enum(reference.environment)
        if reference.environment is not RuleEnvironment.SYNTHETIC:
            raise ValueError("candidate contracts require SYNTHETIC evidence")
        key = reference.evidence_id, reference.version
        if key in seen and seen[key] != reference:
            raise ValueError("conflicting evidence metadata for one identity/version")
        seen[key] = reference


def _require_evidence(references: tuple[EvidenceReference, ...]) -> None:
    if not references:
        raise ValueError("records require evidence, including declared gaps")
    _validate_evidence(references)
    _validate_provenance(references)


def _paired_context(context_id: str | None, context_version: str | None) -> None:
    if (context_id is None) != (context_version is None):
        raise ValueError("context identity and version must be supplied together")


def _validate_gap_reasons(
    reasons: tuple[IngredientGapReason, ...], expected: set[IngredientGapReason]
) -> None:
    for reason in reasons:
        _require_canonical_enum(reason)
    if len(set(reasons)) != len(reasons) or set(reasons) != expected:
        raise ValueError("gap reason codes must exactly describe incomplete declarations")


class VersionedFact(_ContractModel):
    fact_id: _NonBlank
    version: _NonBlank
    subject_kind: FactSubjectKind
    subject_id: _OpaqueId
    subject_version: _NonBlank
    catalogue_version: _NonBlank | None = None
    observation: FactObservation
    measurement_basis: MeasurementBasis | None = None
    basis_reference: EvidenceReference | None = None
    context_id: _OpaqueId | None = None
    context_version: _NonBlank | None = None

    @field_validator("subject_kind", "measurement_basis", mode="after")
    @classmethod
    def validate_enum_members(cls, value: StrEnum | None) -> StrEnum | None:
        if value is not None:
            _require_canonical_enum(value)
        return value

    @model_validator(mode="after")
    def validate_fact(self) -> Self:
        if self.fact_id != self.observation.fact_id:
            raise ValueError("fact identity differs from embedded observation")
        food_subject = self.subject_kind in _FOOD_SUBJECTS
        if food_subject != (self.catalogue_version is not None):
            raise ValueError("only food subjects require a catalogue release")
        _paired_context(self.context_id, self.context_version)
        if self.subject_kind is FactSubjectKind.CONTEXT and (
            self.context_id != self.subject_id or self.context_version != self.subject_version
        ):
            raise ValueError("context facts must bind to their own context identity/version")
        numeric = type(self.observation.value) in (int, float)
        if numeric:
            if self.measurement_basis is None or self.basis_reference is None:
                raise ValueError("numeric facts require a measurement basis and versioned evidence")
            normalized = self.measurement_basis is not MeasurementBasis.AS_RECORDED
            if normalized and (
                not food_subject
                or self.observation.unit in (MeasurementUnit.DIMENSIONLESS, MeasurementUnit.PERCENT)
            ):
                raise ValueError("normalized food bases require a food subject and measured unit")
        elif self.measurement_basis is not None or self.basis_reference is not None:
            raise ValueError("null, boolean and categorical facts cannot carry numeric bases")
        references = self.observation.evidence
        if self.basis_reference is not None:
            references = (*references, self.basis_reference)
        _validate_provenance(references)
        return self


def _line_records(lines: tuple["IngredientLine", ...]) -> Iterator["IngredientLine"]:
    pending = list(lines)
    while pending:
        line = pending.pop()
        yield line
        pending.extend(line.subingredients)


def _validate_line_bindings(
    lines: tuple["IngredientLine", ...], recipe_id: str, recipe_version: str, catalogue_version: str
) -> tuple[EvidenceReference, ...]:
    identities: set[str] = set()
    ingredient_versions: dict[str, str] = {}
    references: list[EvidenceReference] = []
    for line in _line_records(lines):
        if (line.recipe_id, line.recipe_version, line.catalogue_version) != (
            recipe_id,
            recipe_version,
            catalogue_version,
        ):
            raise ValueError("ingredient line recipe/catalogue binding mismatch")
        if line.line_id in identities:
            raise ValueError("duplicate ingredient-line identity, including subingredients")
        identities.add(line.line_id)
        if line.ingredient_id is not None and line.ingredient_version is not None:
            previous = ingredient_versions.setdefault(line.ingredient_id, line.ingredient_version)
            if previous != line.ingredient_version:
                raise ValueError("conflicting ingredient content versions in one catalogue")
        references.extend(line.evidence)
    return tuple(references)


class IngredientLine(_ContractModel):
    line_id: _OpaqueId
    version: _NonBlank
    recipe_id: _OpaqueId
    recipe_version: _NonBlank
    catalogue_version: _NonBlank
    mapping_status: IngredientMappingStatus
    ingredient_id: _OpaqueId | None = None
    ingredient_version: _NonBlank | None = None
    subingredients_complete: bool
    subingredients: tuple["IngredientLine", ...] = ()
    gap_reasons: tuple[IngredientGapReason, ...]
    evidence: tuple[EvidenceReference, ...]

    @field_validator("mapping_status", mode="after")
    @classmethod
    def validate_mapping_member(cls, value: IngredientMappingStatus) -> IngredientMappingStatus:
        _require_canonical_enum(value)
        return value

    @model_validator(mode="after")
    def validate_line(self) -> Self:
        _require_evidence(self.evidence)
        expected: set[IngredientGapReason] = set()
        if self.mapping_status is IngredientMappingStatus.MAPPED:
            if self.ingredient_id is None or self.ingredient_version is None:
                raise ValueError("mapped lines require canonical ingredient identity/version")
        else:
            if self.ingredient_id is not None or self.ingredient_version is not None:
                raise ValueError("unresolved lines cannot declare a verified canonical mapping")
            expected.add(IngredientGapReason.UNRESOLVED_MAPPING)
        if self.subingredients_complete:
            if any(not line.subingredients_complete for line in self.subingredients):
                raise ValueError("complete subingredient declaration contains an incomplete child")
        else:
            expected.add(IngredientGapReason.INCOMPLETE_SUBINGREDIENTS)
        _validate_gap_reasons(self.gap_reasons, expected)
        references = _validate_line_bindings(
            (self,), self.recipe_id, self.recipe_version, self.catalogue_version
        )
        _validate_provenance(references)
        return self


class IngredientCoverage(_ContractModel):
    coverage_id: _OpaqueId
    version: _NonBlank
    recipe_id: _OpaqueId
    recipe_version: _NonBlank
    catalogue_version: _NonBlank
    lines: tuple[IngredientLine, ...] | None
    inventory_complete: bool
    mapping_complete: bool
    subingredients_complete: bool
    gap_reasons: tuple[IngredientGapReason, ...]
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_coverage(self) -> Self:
        _require_evidence(self.evidence)
        if self.lines is None:
            if self.inventory_complete or self.mapping_complete or self.subingredients_complete:
                raise ValueError("missing ingredient inventory cannot declare completeness")
            _validate_gap_reasons(self.gap_reasons, {IngredientGapReason.MISSING_INVENTORY})
            return self
        references = _validate_line_bindings(
            self.lines, self.recipe_id, self.recipe_version, self.catalogue_version
        )
        mapped = all(
            line.mapping_status is IngredientMappingStatus.MAPPED
            for line in _line_records(self.lines)
        )
        expanded = all(line.subingredients_complete for line in _line_records(self.lines))
        if self.mapping_complete != mapped or self.subingredients_complete != expanded:
            raise ValueError("coverage completeness differs from supplied ingredient records")
        expected: set[IngredientGapReason] = set()
        if not self.inventory_complete:
            expected.add(IngredientGapReason.INCOMPLETE_INVENTORY)
        if not mapped:
            expected.add(IngredientGapReason.UNRESOLVED_MAPPING)
        if not expanded:
            expected.add(IngredientGapReason.INCOMPLETE_SUBINGREDIENTS)
        _validate_gap_reasons(self.gap_reasons, expected)
        _validate_provenance((*self.evidence, *references))
        return self


def _fact_references(facts: tuple[VersionedFact, ...]) -> tuple[EvidenceReference, ...]:
    identities: set[tuple[FactSubjectKind, str, str]] = set()
    references: list[EvidenceReference] = []
    for fact in facts:
        key = fact.subject_kind, fact.subject_id, fact.fact_id
        if key in identities:
            raise ValueError("duplicate subject-bound fact identity or revisions")
        identities.add(key)
        references.extend(fact.observation.evidence)
        if fact.basis_reference is not None:
            references.append(fact.basis_reference)
    return tuple(references)


def _check_fact_context(fact: VersionedFact, context_id: str | None, version: str | None) -> None:
    if fact.context_id is not None and (fact.context_id, fact.context_version) != (
        context_id,
        version,
    ):
        raise ValueError("fact context identity/version binding mismatch")


class _CandidateContent(_ContractModel):
    schema_version: Literal["candidate-recipe-facts.v1"] = "candidate-recipe-facts.v1"
    digest_policy_version: Literal["candidate-content-digest.v1"] = "candidate-content-digest.v1"
    recipe_id: _OpaqueId
    recipe_version: _NonBlank
    catalogue_version: _NonBlank
    graph_id: _OpaqueId
    graph_version: _NonBlank
    graph_recipe_entity_id: _OpaqueId
    graph_recipe_reference: FoodEntity
    snapshot_id: _OpaqueId
    snapshot_version: _NonBlank
    context_id: _OpaqueId | None = None
    context_version: _NonBlank | None = None
    ingredient_coverage: IngredientCoverage
    facts: tuple[VersionedFact, ...]
    evidence: tuple[EvidenceReference, ...]

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        _paired_context(self.context_id, self.context_version)
        _require_evidence(self.evidence)
        reference = self.graph_recipe_reference
        if (
            reference.kind is not FoodEntityKind.RECIPE_REFERENCE
            or reference.entity_id != self.graph_recipe_entity_id
            or reference.catalogue_reference != self.recipe_id
        ):
            raise ValueError("recipe-to-graph reference binding mismatch")
        coverage = self.ingredient_coverage
        if (coverage.recipe_id, coverage.recipe_version, coverage.catalogue_version) != (
            self.recipe_id,
            self.recipe_version,
            self.catalogue_version,
        ):
            raise ValueError("candidate ingredient coverage binding mismatch")
        lines = () if coverage.lines is None else coverage.lines
        ingredient_versions = {
            line.ingredient_id: line.ingredient_version
            for line in _line_records(lines)
            if line.mapping_status is IngredientMappingStatus.MAPPED
        }
        for fact in self.facts:
            if fact.catalogue_version != self.catalogue_version:
                raise ValueError("candidate fact catalogue release mismatch")
            if fact.subject_kind is FactSubjectKind.RECIPE:
                valid = (fact.subject_id, fact.subject_version) == (
                    self.recipe_id,
                    self.recipe_version,
                )
            elif fact.subject_kind is FactSubjectKind.INGREDIENT:
                valid = (
                    fact.subject_id in ingredient_versions
                    and fact.subject_version == ingredient_versions[fact.subject_id]
                )
            else:
                valid = False
            if not valid:
                raise ValueError("candidate fact subject identity/version mismatch")
            _check_fact_context(fact, self.context_id, self.context_version)
        line_evidence = tuple(ref for line in _line_records(lines) for ref in line.evidence)
        _validate_provenance(
            (
                *self.evidence,
                *reference.evidence,
                *coverage.evidence,
                *line_evidence,
                *_fact_references(self.facts),
            )
        )
        return self


class _ContextContent(_ContractModel):
    schema_version: Literal["rule-context.v1"] = "rule-context.v1"
    digest_policy_version: Literal["candidate-content-digest.v1"] = "candidate-content-digest.v1"
    context_id: _OpaqueId
    version: _NonBlank
    profile_id: _OpaqueId
    profile_version: _NonBlank
    workflow: KnowledgeWorkflow
    expected_kb_id: _OpaqueId
    expected_kb_version: _NonBlank
    expected_kb_digest: _ContentDigest
    expected_graph_id: _OpaqueId
    expected_graph_version: _NonBlank
    expected_taxonomy_version: _NonBlank | None
    expected_catalogue_version: _NonBlank
    expected_check_catalogue_version: _NonBlank
    workflow_policy_version: Literal["synthetic-workflow-scopes.v1"] = (
        "synthetic-workflow-scopes.v1"
    )
    evaluator_policy_version: Literal["synthetic-rule-evaluation.v1"] = (
        "synthetic-rule-evaluation.v1"
    )
    facts: tuple[VersionedFact, ...]
    evidence: tuple[EvidenceReference, ...]

    @field_validator("workflow", mode="after")
    @classmethod
    def validate_workflow_member(cls, value: KnowledgeWorkflow) -> KnowledgeWorkflow:
        _require_canonical_enum(value)
        return value

    @model_validator(mode="after")
    def validate_context(self) -> Self:
        _require_evidence(self.evidence)
        for fact in self.facts:
            if fact.subject_kind is FactSubjectKind.PROFILE:
                valid = (fact.subject_id, fact.subject_version) == (
                    self.profile_id,
                    self.profile_version,
                )
            elif fact.subject_kind is FactSubjectKind.CONTEXT:
                valid = (fact.subject_id, fact.subject_version) == (self.context_id, self.version)
            else:
                valid = False
            if not valid:
                raise ValueError("profile/context fact subject identity/version mismatch")
            _check_fact_context(fact, self.context_id, self.version)
        _validate_provenance((*self.evidence, *_fact_references(self.facts)))
        return self


def _canonical_content(value: object) -> object:
    # These DTOs contain unordered records/sets only, never ordered witness paths.
    if isinstance(value, dict):
        return {key: _canonical_content(item) for key, item in value.items()}
    if isinstance(value, list):
        return sorted((_canonical_content(item) for item in value), key=_encode_content)
    return value


def _encode_content(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    )


def _content_digest(content: _ContractModel) -> str:
    data = content.model_dump(mode="json", by_alias=True, exclude={"content_digest"})
    return hashlib.sha256(_encode_content(_canonical_content(data)).encode("utf-8")).hexdigest()


class _DigestBuildRequest(_ContractModel):
    content: object
    expected_digest: _ContentDigest | None


def _build_snapshot[Snapshot: _ContractModel](
    target: type[Snapshot],
    body_type: type[_ContractModel],
    content: object,
    expected_digest: str | None,
) -> Snapshot:
    request = _DigestBuildRequest.model_validate(
        {"content": content, "expected_digest": expected_digest}, strict=True
    )
    payload = request.content
    try:
        target._validate_alias_keys(payload)
    except ValueError as error:
        raise ValidationError.from_exception_data(
            target.__name__,
            [{"type": "value_error", "loc": (), "input": None, "ctx": {"error": error}}],
        ) from error
    supplied_digest = None
    digest_present = False
    if isinstance(payload, dict):
        digest_key = next(
            (key for key in ("content_digest", "contentDigest") if key in payload), None
        )
        if digest_key is not None:
            digest_present = True
            supplied_digest = payload[digest_key]
        payload = {key: value for key, value in payload.items() if key != digest_key}
    body = body_type.model_validate(payload, strict=True)
    digest = _content_digest(body)
    # A supplied null/invalid digest is validated, never replaced by a computed value.
    result = target.model_validate(
        body.model_dump() | {"content_digest": supplied_digest if digest_present else digest},
        strict=True,
    )
    if request.expected_digest is not None and not compare_digest(request.expected_digest, digest):
        raise ValidationError.from_exception_data(
            target.__name__,
            [
                {
                    "type": "value_error",
                    "loc": (),
                    "input": None,
                    "ctx": {
                        "error": ValueError("trusted expected snapshot content digest mismatch")
                    },
                }
            ],
        )
    return result


class CandidateRecipeFacts(_CandidateContent):
    content_digest: _ContentDigest

    @model_validator(mode="after")
    def validate_digest(self) -> Self:
        if self.content_digest != _content_digest(self):
            raise ValueError("candidate fact snapshot content digest mismatch")
        return self

    @classmethod
    def build(
        cls, content: Self | dict[str, object], *, expected_digest: str | None = None
    ) -> Self:
        """Validate before computing/verifying integrity; pins are not authentication."""
        return _build_snapshot(cls, _CandidateContent, content, expected_digest)


class RuleContext(_ContextContent):
    content_digest: _ContentDigest

    @model_validator(mode="after")
    def validate_digest(self) -> Self:
        if self.content_digest != _content_digest(self):
            raise ValueError("rule context content digest mismatch")
        return self

    @classmethod
    def build(
        cls, content: Self | dict[str, object], *, expected_digest: str | None = None
    ) -> Self:
        """Bind supplied normalized facts and release expectations; execute no policy."""
        return _build_snapshot(cls, _ContextContent, content, expected_digest)
