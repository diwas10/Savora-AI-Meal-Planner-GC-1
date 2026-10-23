"""Closed canonical DAG codecs for the explicit compact input/proof protocols."""

import hashlib
import json
from typing import Any

from pydantic import BaseModel


class CompactCanonicalLimitError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", by_alias=True)
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _encode(value: Any, *, proof: bool) -> bytes:
    nodes: dict[str, Any] = {}
    indexes: dict[str, int] = {}
    visits = 0
    code = "PROOF_LIMIT" if proof else "MATERIAL_LIMIT"

    def intern(item: Any, depth: int = 0) -> Any:
        nonlocal visits
        visits += 1
        if visits > 1_048_576 or depth > 128:
            raise CompactCanonicalLimitError(code)
        if isinstance(item, BaseModel):
            item = item.model_dump(mode="json", by_alias=True)
        if isinstance(item, dict):
            node = ["object", [[key, intern(item[key], depth + 1)] for key in sorted(item)]]
        elif isinstance(item, (tuple, list)):
            node = ["array", [intern(child, depth + 1) for child in item]]
        else:
            return ["value", item]
        key = digest(node)
        if key in nodes and nodes[key] != node:
            raise ValueError("conflicting canonical node")
        if key not in nodes:
            indexes[key] = len(nodes)
            nodes[key] = node
        return ["ref", indexes[key] if proof else key]

    root = intern(value)
    material = canonical_bytes(
        dict(
            policy="compact-swap-canonical-proof.v1" if proof else "compact-swap-canonical-dag.v1",
            root=root,
            nodes=list(nodes.values()) if proof else nodes,
        )
    )
    if len(material) > (1_048_576 if proof else 4_194_304):
        raise CompactCanonicalLimitError(code)
    return material


def canonical_material(value: Any) -> bytes:
    return _encode(value, proof=False)


def canonical_proof(value: Any) -> bytes:
    return _encode(value, proof=True)
