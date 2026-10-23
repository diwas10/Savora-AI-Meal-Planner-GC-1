"""Standalone SASRec + Content Recommendation Model for Hugging Face Deployment.

Self-contained module for serving next-recipe recommendations from interaction history.
No external repository dependencies required (only PyTorch).
"""

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor, nn

MODEL_VERSION = "sasrec-content-v2"
PAD = 0  # item index 0 and feature index 0 are padding
MAX_HISTORY = 50
CHECKPOINT_SHA256 = "87f1855284befc8e6b43d86779edc177b592bbe68f0cb3a8f89c288e41f0cb45"


@dataclass(frozen=True)
class ModelConfig:
    dim: int = 64
    layers: int = 2
    heads: int = 2
    dropout: float = 0.2
    max_len: int = MAX_HISTORY
    top_ingredients: int = 3000
    max_tags: int = 40
    max_ingredients: int = 30
    use_id: bool = True
    use_content: bool = True
    use_bias: bool = True


class SASRecContent(nn.Module):
    feat_tags: Tensor
    feat_ingredients: Tensor
    has_id: Tensor
    hybrid_weight: float = 0.0

    def __init__(self, items: int, tags: int, ingredients: int, config: ModelConfig) -> None:
        super().__init__()
        self.config = config
        self.item = nn.Embedding(items, config.dim, padding_idx=PAD)
        self.tag = nn.EmbeddingBag(tags + 1, config.dim, mode="mean", padding_idx=PAD)
        self.ingredient = nn.EmbeddingBag(ingredients + 1, config.dim, mode="mean", padding_idx=PAD)
        self.position = nn.Embedding(config.max_len, config.dim)
        layer = nn.TransformerEncoderLayer(
            config.dim,
            config.heads,
            dim_feedforward=config.dim * 2,
            dropout=config.dropout,
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, config.layers, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(config.dim)
        self.dropout = nn.Dropout(config.dropout)
        self.register_buffer("feat_tags", torch.zeros(items, config.max_tags, dtype=torch.long))
        self.register_buffer(
            "feat_ingredients", torch.zeros(items, config.max_ingredients, dtype=torch.long)
        )
        self.register_buffer("has_id", torch.zeros(items))
        self.bias = nn.Embedding(items, 1)

    def item_vectors(self, rows: Tensor) -> Tensor:
        flat = rows.reshape(-1)
        vector = torch.zeros(len(flat), self.config.dim, device=rows.device)
        if self.config.use_id:
            vector = vector + self.item(flat) * self.has_id[flat].unsqueeze(-1)
        if self.config.use_content:
            vector = vector + self.tag(self.feat_tags[flat])
            vector = vector + self.ingredient(self.feat_ingredients[flat])
        return vector.reshape(*rows.shape, self.config.dim)

    def item_bias(self, rows: Tensor) -> Tensor:
        if not self.config.use_bias:
            return torch.zeros(rows.shape, device=rows.device)
        return self.bias(rows).squeeze(-1) * self.has_id[rows]

    def score(self, states: Tensor, rows: Tensor) -> Tensor:
        """[N, d] states x [M] item rows -> [N, M] scores = h . v(i) + b(i)."""
        return states @ self.item_vectors(rows).T + self.item_bias(rows)

    def encode(self, sequences: Tensor) -> Tensor:
        """[batch, len <= max_len] left-padded rows -> [batch, len, dim] causal states."""
        length = sequences.size(1)
        if length > self.config.max_len:
            raise ValueError(f"sequence length {length} exceeds max_len {self.config.max_len}")
        device = sequences.device
        positions = torch.arange(self.config.max_len - length, self.config.max_len, device=device)
        x = self.item_vectors(sequences) + self.position(positions)
        x = self.dropout(x) * (sequences != PAD).unsqueeze(-1)

        future = torch.triu(torch.ones(length, length, dtype=torch.bool, device=device), 1)
        blocked = future.unsqueeze(0) | (sequences == PAD).unsqueeze(1)
        blocked = blocked & ~torch.eye(length, dtype=torch.bool, device=device)
        mask = blocked.repeat_interleave(self.config.heads, dim=0)
        return self.norm(self.encoder(x, mask=mask))


def load_model(
    path: str | Path, device: torch.device | None = None,
    config_path: str | Path | None = None,
) -> tuple[SASRecContent, list[str], dict[str, int]]:
    """Loads the model checkpoint, item ID catalog, and row lookup table."""
    path = Path(path)
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != CHECKPOINT_SHA256:
            raise ValueError("Checkpoint integrity check failed")
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if checkpoint.get("modelVersion") != MODEL_VERSION:
        raise ValueError(
            f"Checkpoint is {checkpoint.get('modelVersion')!r}, expected {MODEL_VERSION!r}"
        )
    config = ModelConfig(**checkpoint["config"])
    metadata = json.loads(Path(config_path or path.with_suffix(".json")).read_text())
    if metadata["modelVersion"] != MODEL_VERSION or metadata["modelConfig"] != asdict(config):
        raise ValueError("Checkpoint and JSON configuration disagree")
    if asdict(config) != asdict(ModelConfig()):
        raise ValueError("Unsupported model configuration")
    ids: list[str] = checkpoint["index"]["ids"]
    if (not ids or ids[0] != "<pad>" or len(set(ids)) != len(ids)
            or any(not isinstance(rid, str) or not rid.startswith("FC_")
                   or not rid[3:].isdigit() for rid in ids[1:])):
        raise ValueError("Invalid recipe catalog")
    if metadata["items"] != len(ids) - 1:
        raise ValueError("Catalog size mismatch")
    tag_count = len(checkpoint["index"]["tag_row"])
    ingredient_count = len(checkpoint["index"]["ingredient_row"])
    for key, count in (("tag_row", tag_count), ("ingredient_row", ingredient_count)):
        if set(checkpoint["index"][key].values()) != set(range(1, count + 1)):
            raise ValueError("Invalid content vocabulary")

    model = SASRecContent(len(ids), tag_count, ingredient_count, config)
    model.load_state_dict(checkpoint["state"], strict=True)
    if any(not bool(torch.isfinite(t).all()) for t in model.state_dict().values()):
        raise ValueError("Non-finite checkpoint values")
    for features, count in ((model.feat_tags, tag_count),
                            (model.feat_ingredients, ingredient_count)):
        if int(features.min()) < 0 or int(features.max()) > count:
            raise ValueError("Content feature index out of bounds")
    if not bool(((model.has_id == 0) | (model.has_id == 1)).all()):
        raise ValueError("Invalid ID availability mask")
    if int(model.has_id.sum()) != metadata["itemsWithIdVector"]:
        raise ValueError("ID availability count mismatch")
    model.hybrid_weight = float(checkpoint.get("hybridWeight", 0.0))
    if not math.isfinite(model.hybrid_weight) or model.hybrid_weight != metadata["hybridWeight"]:
        raise ValueError("Hybrid weight mismatch")
    model.to(device or torch.device("cpu"))
    model.eval()
    model.requires_grad_(False)

    row_map = {rid: i for i, rid in enumerate(ids)}
    return model, ids, row_map


def score_candidates(model: SASRecContent, history: Sequence[str],
                     candidates: Sequence[str], row_map: Mapping[str, int]) -> list[float]:
    """Raw trained Transformer logits, aligned with supplied candidate order.

    No popularity blending: the bundle does not contain popularity counts.
    History is chronological, oldest first, right aligned with left PAD rows.
    """
    if not 1 <= len(history) <= model.config.max_len or not 1 <= len(candidates) <= 512:
        raise ValueError("Input length out of bounds")
    if len(set(candidates)) != len(candidates):
        raise ValueError("Duplicate candidates")
    if any(rid not in row_map or row_map[rid] == PAD for rid in (*history, *candidates)):
        raise ValueError("Unavailable recipe identifier")
    if model.training:
        raise RuntimeError("Model is not in evaluation mode")
    device = model.item.weight.device
    rows = [row_map[rid] for rid in history]
    sequence = torch.tensor([[PAD] * (model.config.max_len - len(rows)) + rows],
                            dtype=torch.long, device=device)
    candidate_rows = torch.tensor([row_map[rid] for rid in candidates],
                                  dtype=torch.long, device=device)
    with torch.inference_mode():
        scores = model.score(model.encode(sequence)[:, -1, :], candidate_rows).squeeze(0)
        if scores.shape != (len(candidates),) or not bool(torch.isfinite(scores).all()):
            raise RuntimeError("Invalid model output")
        return scores.tolist()


def recommend_next(
    model: SASRecContent,
    sequence_recipe_ids: Sequence[str],
    ids: Sequence[str],
    row_map: Mapping[str, int],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Generates top-K recipe recommendations given user interaction history."""
    if not sequence_recipe_ids or any(rid not in row_map or row_map[rid] == PAD
                                      for rid in sequence_recipe_ids):
        raise ValueError("History must contain valid recipe identifiers")
    rows = [row_map[rid] for rid in sequence_recipe_ids]

    # Limit to max_len
    rows = rows[-model.config.max_len :]
    seq_tensor = torch.tensor([rows], dtype=torch.long)

    with torch.inference_mode():
        states = model.encode(seq_tensor)
        last_state = states[:, -1, :]  # [1, dim]

        # Score across all items
        all_rows = torch.arange(len(ids))
        scores = model.score(last_state, all_rows).squeeze(0)  # [total_items]

        # Zero out padding
        scores[PAD] = -float("inf")

        # Mask recently viewed items to avoid duplicate recommendations
        for r in rows:
            scores[r] = -float("inf")

        top_scores, top_indices = torch.topk(scores, k=min(top_k, len(ids) - 1))

    return [
        {"rank": rank + 1, "recipe_id": ids[idx], "score": round(float(score), 4)}
        for rank, (score, idx) in enumerate(zip(top_scores.tolist(), top_indices.tolist()))
    ]
