"""Build structurally consistent KB releases; execute no predicates or database I/O."""

from hmac import compare_digest
from typing import Self

from pydantic import ValidationError, model_validator

from savora_ai.schemas.food_graph import _Environment, _OpaqueId
from savora_ai.schemas.knowledge import RuleEnvironment, _ContractModel, _NonBlank
from savora_ai.schemas.knowledge_base import (
    KnowledgeBaseSnapshot,
    _canonical_enum_inputs,
    _compute_content_digest,
    _ContentDigest,
    _KnowledgeContent,
)
from savora_ai.schemas.reasoning import _validation_payload


class _BuildRequest(_ContractModel):
    content: object
    expected_digest: _ContentDigest | None
    expected_environment: _Environment | None
    expected_kb_id: _OpaqueId | None
    expected_kb_version: _NonBlank | None
    expected_graph_id: _OpaqueId | None
    expected_graph_version: _NonBlank | None
    expected_catalogue_version: _NonBlank | None
    expected_taxonomy_version: _NonBlank | None
    expected_check_catalogue_version: _NonBlank | None

    @model_validator(mode="before")
    @classmethod
    def validate_unchecked_request(cls, value: object) -> object:
        try:
            payload = _validation_payload(value)
            _canonical_enum_inputs(payload)
            return payload
        except RecursionError as error:
            raise ValueError("cyclic or excessively deep KB build request") from error

    @model_validator(mode="after")
    def validate_digest_aliases(self) -> Self:
        if (
            isinstance(self.content, dict)
            and "content_digest" in self.content
            and "contentDigest" in self.content
        ):
            raise ValueError("duplicate content digest aliases")
        return self


def build_knowledge_snapshot(
    content: KnowledgeBaseSnapshot | dict[str, object],
    *,
    expected_digest: str | None = None,
    expected_environment: RuleEnvironment | None = None,
    expected_kb_id: str | None = None,
    expected_kb_version: str | None = None,
    expected_graph_id: str | None = None,
    expected_graph_version: str | None = None,
    expected_catalogue_version: str | None = None,
    expected_taxonomy_version: str | None = None,
    expected_check_catalogue_version: str | None = None,
) -> KnowledgeBaseSnapshot:
    """Compute or verify a content digest after complete recursive revalidation.

    Expected pins must come from a trusted loader, not the supplied release. This
    slice accepts synthetic releases only. Production requests require trusted
    digest/environment/version pins and remain blocked pending workflow-policy approval.
    """
    request = _BuildRequest.model_validate(
        {
            "content": content,
            "expected_digest": expected_digest,
            "expected_environment": expected_environment,
            "expected_kb_id": expected_kb_id,
            "expected_kb_version": expected_kb_version,
            "expected_graph_id": expected_graph_id,
            "expected_graph_version": expected_graph_version,
            "expected_catalogue_version": expected_catalogue_version,
            "expected_taxonomy_version": expected_taxonomy_version,
            "expected_check_catalogue_version": expected_check_catalogue_version,
        },
        strict=True,
    )
    supplied = request.content
    digest_key = None
    if isinstance(supplied, dict):
        digest_key = next(
            (key for key in ("content_digest", "contentDigest") if key in supplied), None
        )
        body: object = {key: value for key, value in supplied.items() if key != digest_key}
    else:
        body = supplied
    validated = _KnowledgeContent.model_validate(body, strict=True)
    computed = _compute_content_digest(validated)
    digest = (
        supplied[digest_key] if isinstance(supplied, dict) and digest_key is not None else computed
    )
    snapshot = KnowledgeBaseSnapshot.model_validate(
        validated.model_dump() | {"content_digest": digest}, strict=True
    )
    try:
        _validate_release_acceptance(snapshot, request)
    except ValueError as error:
        raise ValidationError.from_exception_data(
            "KnowledgeReleaseAcceptance",
            [{"type": "value_error", "loc": (), "input": None, "ctx": {"error": error}}],
        ) from error
    return snapshot


def _validate_release_acceptance(snapshot: KnowledgeBaseSnapshot, request: _BuildRequest) -> None:
    pins = (
        (request.expected_kb_id, snapshot.kb_id),
        (request.expected_kb_version, snapshot.version),
        (request.expected_graph_id, snapshot.graph_id),
        (request.expected_graph_version, snapshot.graph_version),
        (request.expected_catalogue_version, snapshot.catalogue_version),
        (request.expected_taxonomy_version, snapshot.taxonomy_version),
        (request.expected_check_catalogue_version, snapshot.check_catalogue_version),
    )
    if (
        request.expected_environment is not None
        and request.expected_environment is not snapshot.environment
    ):
        raise ValueError("trusted environment pin mismatch")
    if any(expected is not None and expected != actual for expected, actual in pins):
        raise ValueError("trusted KB/graph/catalogue/taxonomy version pin mismatch")
    if request.expected_digest is not None and not compare_digest(
        request.expected_digest, snapshot.content_digest
    ):
        raise ValueError("trusted expected KB content digest mismatch")
    if snapshot.environment is RuleEnvironment.PRODUCTION:
        if (
            request.expected_digest is None
            or request.expected_environment is None
            or any(expected is None for expected, actual in pins if actual is not None)
        ):
            raise ValueError("production requires trusted expected digest and release pins")
        raise ValueError("production serving is deferred pending approved workflow/scope policy")
