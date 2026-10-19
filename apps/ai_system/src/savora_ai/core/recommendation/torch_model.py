# pyright: reportMissingImports=false
# torch is the optional `ml` extra; CI type-checks without it, locally with it.
"""T3: SASRec with content features (ADR 0004 D3). Requires the optional `ml` extra.

    item vector  v(i) = [i seen in training] * E_id[i] + mean(E_tag[tags(i)])
                        + mean(E_ingredient[ingredients(i)])
    user state   h    = causal self-attention over the last 50 item vectors (+ position)
    score(i)          = h . v(i) + b(i)   (b: learned per-item bias, 0 if unseen)

Why content: the median user has ONE training interaction and 13.6% of test targets are
recipes never seen in training. An ID-only model gives those items an untrained random
vector; here an unseen recipe is still placed by its tags and ingredients, and its ID
part is exactly zero, never noise. Training: next-item prediction at every position of
every training-period sequence, sampled softmax with logQ correction, early stopping on
the WHOLE validation period by the model alone, then the weight w of the shipped hybrid
(model + w log popularity) for that epoch, saved with the model. Sized for a laptop (CPU
or Apple MPS): batches are trimmed to their longest sequence, and ranking is batched.

Usage (from the repo root):
    uv run --extra ml python -m savora_ai.core.recommendation.torch_model \
        --output Data/models/sasrec_content.pt
"""

import argparse
import ast
import csv
import json
import math
import random
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch import Tensor, nn

from savora_ai.core.food_data.foodcom_cuisines import normalize_tags
from savora_ai.core.recommendation.metrics import (
    catalogue_coverage,
    intra_list_diversity,
    rank_metrics,
)
from savora_ai.core.recommendation.sequences import (
    MAX_HISTORY,
    EvalCase,
    SplitData,
    load_interactions,
    split,
)

MODEL_VERSION = "sasrec-content-v2"
# Hybrid: score + w * log(1 + training count). w is chosen for the selected epoch on
# VALIDATION only and saved in the checkpoint; test is scored once afterwards.
HYBRID_WEIGHTS = (0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0)
PAD = 0  # item index 0 and feature index 0 are padding
EVAL_BATCH = 256


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
    # Ablation switches (experiments.py); the shipped model uses all three.
    use_id: bool = True
    use_content: bool = True
    use_bias: bool = True


@dataclass(frozen=True)
class TrainConfig:
    epochs: int = 40
    batch_size: int = 256
    negatives: int = 1024
    # 1e-3 (v1) memorises training sequences within one or two epochs and validation
    # falls from there; 1e-4 climbs for several epochs to a higher peak (ADR 0004).
    lr: float = 1e-4
    # The tag and ingredient tables are shared by many recipes and cannot memorise one
    # sequence; at 1e-4 they barely move and content no longer separates cuisines (Indian
    # neighbours of Indian dishes: 1.6x chance at 1e-4, 15.6x at 3e-4; validation equal).
    content_lr: float = 3e-4
    weight_decay: float = 1e-5
    patience: int = 3
    validation_cases: int = 0  # 0 = every validation case (cheap since ranking is batched)
    # Negatives come from q = share * popularity^0.75 + (1 - share) * uniform, and every
    # logit is corrected by -log(K q(i)) (sampled softmax with logQ correction), so the
    # sampled loss approximates the full-catalogue softmax that evaluation ranks with.
    popular_negative_share: float = 0.8
    seed: int = 7


class ItemIndex:
    """Recipe ID <-> row, and each row's padded tag/ingredient feature IDs."""

    def __init__(
        self,
        recipe_ids: Sequence[str],
        features: Mapping[str, tuple[list[str], list[str]]],
        train_items: set[str],
        config: ModelConfig,
    ) -> None:
        self.ids = ["<pad>", *recipe_ids]
        self.row = {rid: i for i, rid in enumerate(self.ids)}
        tag_vocab = sorted({t for tags, _ in features.values() for t in tags})
        counts = Counter(g for _, ingredients in features.values() for g in ingredients)
        top = sorted(counts, key=lambda g: (-counts[g], g))[: config.top_ingredients]
        self.tag_row = {t: i + 1 for i, t in enumerate(tag_vocab)}
        self.ingredient_row = {g: i + 1 for i, g in enumerate(top)}
        n = len(self.ids)
        self.tags = torch.zeros((n, config.max_tags), dtype=torch.long)
        self.ingredients = torch.zeros((n, config.max_ingredients), dtype=torch.long)
        self.has_id = torch.zeros(n)
        for rid, (tags, ingredients) in features.items():
            row = self.row.get(rid)
            if row is None:
                continue
            t = [self.tag_row[x] for x in tags if x in self.tag_row][: config.max_tags]
            g = [self.ingredient_row[x] for x in ingredients if x in self.ingredient_row]
            g = g[: config.max_ingredients]
            self.tags[row, : len(t)] = torch.tensor(t, dtype=torch.long)
            self.ingredients[row, : len(g)] = torch.tensor(g, dtype=torch.long)
        for rid in train_items:
            if rid in self.row:
                self.has_id[self.row[rid]] = 1.0  # only trained items get an ID vector

    def state(self) -> dict[str, object]:
        return {
            "ids": self.ids,
            "tag_row": self.tag_row,
            "ingredient_row": self.ingredient_row,
        }


class SASRecContent(nn.Module):
    feat_tags: Tensor  # registered buffers, saved with the model
    feat_ingredients: Tensor
    has_id: Tensor
    hybrid_weight: float = 0.0  # chosen on validation; restored by `load`

    def __init__(self, items: int, tags: int, ingredients: int, config: ModelConfig) -> None:
        super().__init__()
        self.config = config
        self.item = nn.Embedding(items, config.dim, padding_idx=PAD)
        # Mean over a recipe's non-padding features; a recipe with none gives zeros.
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
        # Per-item popularity bias, learned; masked to 0 for items unseen in training.
        self.bias = nn.Embedding(items, 1)
        # Small init: N(0, 1) embeddings summed give dot products near +/-100, which
        # saturate the softmax (measured: loss 23.5 and HR@10 0 after one epoch).
        for table in (self.item, self.tag, self.ingredient, self.position):
            nn.init.normal_(table.weight, std=0.02)
        nn.init.zeros_(self.bias.weight)
        with torch.no_grad():
            for table in (self.item, self.tag, self.ingredient):
                table.weight[PAD] = 0

    def set_features(self, index: ItemIndex) -> None:
        self.feat_tags.copy_(index.tags)
        self.feat_ingredients.copy_(index.ingredients)
        self.has_id.copy_(index.has_id)

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
        """[batch, len <= max_len] left-padded rows -> [batch, len, dim] causal states.

        Positions count from the END (the last item always uses position max_len - 1), so
        a batch may be trimmed to its longest sequence: leading padding is masked out and
        never changes a real position's state, it only costs time.
        """
        length = sequences.size(1)
        if length > self.config.max_len:
            raise ValueError(f"sequence length {length} exceeds max_len {self.config.max_len}")
        device = sequences.device
        positions = torch.arange(self.config.max_len - length, self.config.max_len, device=device)
        x = self.item_vectors(sequences) + self.position(positions)
        x = self.dropout(x) * (sequences != PAD).unsqueeze(-1)
        # Block future keys and padding keys, but always let a position see itself, so a
        # padded position never has an all-blocked row (which would give NaN gradients).
        future = torch.triu(torch.ones(length, length, dtype=torch.bool, device=device), 1)
        blocked = future.unsqueeze(0) | (sequences == PAD).unsqueeze(1)  # [B, L, L]
        blocked = blocked & ~torch.eye(length, dtype=torch.bool, device=device)
        mask = blocked.repeat_interleave(self.config.heads, dim=0)  # [B * heads, L, L]
        return self.norm(self.encoder(x, mask=mask))

    def all_item_vectors(self, chunk: int = 50_000) -> Tensor:
        n = self.item.num_embeddings
        device = self.item.weight.device
        parts = [
            self.item_vectors(torch.arange(s, min(s + chunk, n), device=device))
            for s in range(0, n, chunk)
        ]
        return torch.cat(parts)


# --- data ---------------------------------------------------------------------------


def load_features(path: Path) -> dict[str, tuple[list[str], list[str]]]:
    csv.field_size_limit(sys.maxsize)
    features: dict[str, tuple[list[str], list[str]]] = {}
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if not row["id"].isdecimal():
                continue
            try:
                tags = sorted(normalize_tags(row["tags"]))
                ingredients = [str(x).strip().lower() for x in ast.literal_eval(row["ingredients"])]
            except (ValueError, SyntaxError):
                continue  # a defective row keeps no features (it is quarantined anyway)
            features[f"FC_{int(row['id'])}"] = (tags, ingredients)
    return features


def _left_pad(rows: list[int], length: int) -> list[int]:
    rows = rows[-length:]
    return [PAD] * (length - len(rows)) + rows


def _pad_batch(sequences: Sequence[list[int]], max_len: int, device: torch.device) -> Tensor:
    """Left-pad to the batch's longest sequence (at most max_len), not always to max_len."""
    length = max(1, min(max_len, max(len(s) for s in sequences)))
    return torch.tensor([_left_pad(s, length) for s in sequences], device=device)


def _training_windows(data: SplitData, index: ItemIndex, max_len: int) -> list[list[int]]:
    """Each training sequence's last max_len+1 items; positions 1.. are the targets.

    Measured: also training on the older part of long sequences (twice the targets, mostly
    from heavy users' early years) did not improve validation, and doubled the epoch time.
    """
    windows = []
    for sequence in data.train_sequences.values():
        rows = [index.row[r] for r in sequence if r in index.row]
        if len(rows) >= 2:
            windows.append(rows[-(max_len + 1) :])
    return windows


def _length_batches(
    windows: Sequence[list[int]], batch_size: int, rng: random.Random
) -> list[list[int]]:
    """Random batches of similar-length windows (sorted within random chunks), so a
    trimmed batch carries little padding; batch order is shuffled again."""
    order = list(range(len(windows)))
    rng.shuffle(order)
    chunk = batch_size * 50
    batches: list[list[int]] = []
    for start in range(0, len(order), chunk):
        part = sorted(order[start : start + chunk], key=lambda i: len(windows[i]))
        batches += [part[j : j + batch_size] for j in range(0, len(part), batch_size)]
    rng.shuffle(batches)
    return batches


# --- evaluation ---------------------------------------------------------------------


@torch.no_grad()
def scored_batches(
    model: SASRecContent,
    index: ItemIndex,
    cases: Sequence[EvalCase],
    candidate_rows: Tensor | None = None,
) -> Iterator[tuple[Sequence[EvalCase], Tensor, Tensor]]:
    """THE evaluation protocol, shared by evaluate.py and experiments.py.

    Yields (cases, scores [cases, every item row], target rows [cases]). Padding, items
    outside `candidate_rows` and each user's own history (except the target) score -inf.
    """
    model.eval()
    device = next(model.parameters()).device
    vectors = model.all_item_vectors()
    vectors[PAD] = 0
    bias = model.item_bias(torch.arange(len(vectors), device=device))
    blocked = torch.zeros(len(vectors), dtype=torch.bool, device=device)
    if candidate_rows is not None:
        blocked[:] = True
        blocked[candidate_rows.to(device)] = False
    blocked[PAD] = True
    for start in range(0, len(cases), EVAL_BATCH):
        batch = cases[start : start + EVAL_BATCH]
        histories = [[index.row[r] for r in c.history] for c in batch]
        states = model.encode(_pad_batch(histories, model.config.max_len, device))[:, -1]
        scores = (states @ vectors.T + bias).masked_fill_(blocked, float("-inf"))
        targets = torch.tensor([index.row[c.target] for c in batch], device=device)
        target_scores = scores.gather(1, targets.unsqueeze(1))
        scores.scatter_(1, _pad_batch(histories, MAX_HISTORY, device), float("-inf"))
        scores.scatter_(1, targets.unsqueeze(1), target_scores)  # the target is never excluded
        yield batch, scores, targets


def batch_ranks(scores: Tensor, targets: Tensor) -> list[int]:
    """1-based ranks: items scoring strictly higher, plus one (ties favour the target)."""
    target_scores = scores.gather(1, targets.unsqueeze(1))
    return ((scores > target_scores).sum(1) + 1).tolist()


def dense_ranks(
    model: SASRecContent,
    index: ItemIndex,
    cases: Sequence[EvalCase],
    device: torch.device,
    tops: list[list[str]] | None = None,
    top_cases: int = 0,
    log_popularity: Tensor | None = None,  # added to every score when given (hybrid)
    candidate_rows: Tensor | None = None,  # rank only among these rows (catalogue eval)
) -> list[int]:
    del device  # the model's own device is used
    ranks: list[int] = []
    for batch, scores, targets in scored_batches(model, index, cases, candidate_rows):
        if log_popularity is not None:
            scores = scores + log_popularity.to(scores.device)
        if tops is not None and len(tops) < top_cases:
            take = min(len(batch), top_cases - len(tops))
            for top in torch.topk(scores[:take], 10).indices.tolist():
                tops.append([index.ids[j] for j in top])
        ranks += batch_ranks(scores, targets)
    return ranks


def weighted_ranks(
    model: SASRecContent,
    index: ItemIndex,
    cases: Sequence[EvalCase],
    log_popularity: Tensor,
    weights: Sequence[float],
    candidate_rows: Tensor | None = None,
) -> dict[float, list[int]]:
    """Ranks for several hybrid weights (score + w * log(1 + count)) in one scoring pass."""
    # De-duplicate: (0.0, best) with best == 0.0 must not append every rank twice.
    weights = tuple(dict.fromkeys(weights))
    ranks: dict[float, list[int]] = {w: [] for w in weights}
    device = next(model.parameters()).device
    pop = log_popularity.to(device)
    for _, scores, targets in scored_batches(model, index, cases, candidate_rows):
        for w in weights:
            ranks[w] += batch_ranks(scores + w * pop if w else scores, targets)
    return ranks


def _hr10(ranks: Sequence[int]) -> float:
    return sum(r <= 10 for r in ranks) / max(1, len(ranks))


def _ndcg10(ranks: Sequence[int]) -> float:
    return sum(1 / math.log2(r + 1) for r in ranks if r <= 10) / max(1, len(ranks))


# --- training -----------------------------------------------------------------------


def pick_device(name: str) -> torch.device:
    if name == "auto":
        if torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(name)


def log_popularity(ids: Sequence[str], counts: Mapping[str, int]) -> Tensor:
    return torch.tensor([math.log1p(counts.get(i, 0)) for i in ids])


def train(
    data: SplitData,
    features: Mapping[str, tuple[list[str], list[str]]],
    universe: Sequence[str],
    model_config: ModelConfig = ModelConfig(),  # noqa: B008 - frozen dataclass
    train_config: TrainConfig = TrainConfig(),  # noqa: B008 - frozen dataclass
    device: torch.device | None = None,
    log: Callable[[str], None] = print,
) -> tuple[SASRecContent, ItemIndex, dict[str, object]]:
    device = device or pick_device("auto")
    random.seed(train_config.seed)
    torch.manual_seed(train_config.seed)
    index = ItemIndex(sorted(universe), features, set(data.train_counts), model_config)
    model = SASRecContent(
        len(index.ids),
        len(index.tag_row),
        len(index.ingredient_row),
        model_config,
    )
    model.set_features(index)
    model.to(device)
    content = [model.tag.weight, model.ingredient.weight]
    rest = [p for p in model.parameters() if all(p is not c for c in content)]
    optimizer = torch.optim.AdamW(
        [{"params": rest}, {"params": content, "lr": train_config.content_lr}],
        lr=train_config.lr,
        weight_decay=train_config.weight_decay,
    )
    windows = _training_windows(data, index, model_config.max_len)
    train_rows = sorted(index.row[r] for r in data.train_counts if r in index.row)
    row_ids = torch.tensor(train_rows, device=device)
    weights = torch.tensor([data.train_counts[index.ids[r]] ** 0.75 for r in train_rows])
    share = train_config.popular_negative_share
    proposal = share * weights / weights.sum() + (1 - share) / len(train_rows)
    log_q = torch.full((len(index.ids),), float("inf"))  # never sampled: no correction use
    log_q[torch.tensor(train_rows)] = torch.log(train_config.negatives * proposal)
    log_q = log_q.to(device)
    generator = torch.Generator(device="cpu").manual_seed(train_config.seed)
    rng = random.Random(train_config.seed)
    valid = list(data.validation)
    if train_config.validation_cases:
        rng.shuffle(valid)
        valid = valid[: train_config.validation_cases]
    popularity = log_popularity(index.ids, data.train_counts)
    best: tuple[float, float] = (-1.0, -1.0)  # (validation NDCG@10, HR@10), model alone
    best_state, best_weight, stale, history = None, 0.0, 0, []
    for epoch in range(1, train_config.epochs + 1):
        model.train()
        started, total, steps = time.time(), 0.0, 0
        for batch_rows in _length_batches(windows, train_config.batch_size, rng):
            batch = [windows[i] for i in batch_rows]
            inputs = _pad_batch([w[:-1] for w in batch], model_config.max_len, device)
            targets = _pad_batch([w[1:] for w in batch], model_config.max_len, device)
            states = model.encode(inputs)  # [B, L, d]
            mask = targets != PAD
            h, pos = states[mask], targets[mask]  # [N, d], [N]
            sampled = torch.multinomial(
                proposal, train_config.negatives, replacement=True, generator=generator
            ).to(device)
            negatives = row_ids[sampled]
            positive = (h * model.item_vectors(pos)).sum(-1, keepdim=True) + model.item_bias(
                pos
            ).unsqueeze(-1)  # [N, 1]
            positive = positive - log_q[pos].unsqueeze(-1)  # logQ correction
            negative = model.score(h, negatives) - log_q[negatives]  # [N, negs], shared
            # A sampled negative that IS the target must not be pushed down.
            negative = negative.masked_fill(
                negatives.unsqueeze(0) == pos.unsqueeze(1), float("-inf")
            )
            logits = torch.cat([positive, negative], dim=1)
            loss = nn.functional.cross_entropy(
                logits, torch.zeros(len(pos), dtype=torch.long, device=device)
            )
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total += float(loss.item())
            steps += 1
        # Selection: the epoch by the MODEL ALONE on validation NDCG@10 (HR@10 breaks
        # ties). Recipes without training counts (curated dishes, new recipes) are ranked
        # by the model alone, and the hybrid curve is too flat to choose an epoch: every
        # epoch's best hybrid is within noise. Then the hybrid weight for that epoch.
        by_weight = weighted_ranks(model, index, valid, popularity, HYBRID_WEIGHTS)
        alone = (_ndcg10(by_weight[0.0]), _hr10(by_weight[0.0]))
        weight = max(HYBRID_WEIGHTS, key=lambda w: (_ndcg10(by_weight[w]), _hr10(by_weight[w])))
        history.append(
            {
                "epoch": epoch,
                "loss": total / max(1, steps),
                "validNdcg@10": alone[0],
                "validHr@10": alone[1],
                "validHybridWeight": weight,
                "validHybridNdcg@10": _ndcg10(by_weight[weight]),
                "validHybridHr@10": _hr10(by_weight[weight]),
            }
        )
        log(f"epoch {epoch}: loss {total / max(1, steps):.4f}  valid NDCG@10 {alone[0]:.4f} "
            f"HR@10 {alone[1]:.4f}  hybrid(w={weight:g}) NDCG@10 "
            f"{_ndcg10(by_weight[weight]):.4f} HR@10 {_hr10(by_weight[weight]):.4f}  "
            f"({time.time() - started:.0f}s)")  # fmt: skip
        if alone > best:
            best, best_weight, stale = alone, weight, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
            if stale >= train_config.patience:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    model.hybrid_weight = best_weight
    report = {
        "modelVersion": MODEL_VERSION,
        "modelConfig": asdict(model_config),
        "trainConfig": asdict(train_config),
        "trainingWindows": len(windows),
        "trainingTargets": sum(len(w) - 1 for w in windows),
        "items": len(index.ids) - 1,
        "itemsWithIdVector": int(index.has_id.sum().item()),
        "epochs": history,
        "hybridWeight": best_weight,
        "bestValidNdcg@10": best[0],
        "bestValidHr@10": best[1],
        "device": str(device),
    }
    return model, index, report


def save(path: Path, model: SASRecContent, index: ItemIndex, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "modelVersion": MODEL_VERSION,
            "state": {k: v.cpu() for k, v in model.state_dict().items()},
            "config": asdict(model.config),
            "index": index.state(),
            "hybridWeight": model.hybrid_weight,
            "report": report,
        },
        path,
    )


def load(path: Path, device: torch.device | None = None) -> tuple[SASRecContent, dict[str, int]]:
    """The trained model (with its validated `hybrid_weight`) and its recipe-ID -> row map."""
    # weights_only: tensors and plain containers only, never arbitrary pickled objects.
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if checkpoint.get("modelVersion") != MODEL_VERSION:
        raise ValueError(
            f"{path} is {checkpoint.get('modelVersion', 'sasrec-content-v1')!r}, "
            f"this code reads {MODEL_VERSION!r}: retrain the model"
        )
    config = ModelConfig(**checkpoint["config"])
    ids: list[str] = checkpoint["index"]["ids"]
    model = SASRecContent(
        len(ids),
        len(checkpoint["index"]["tag_row"]),
        len(checkpoint["index"]["ingredient_row"]),
        config,
    )
    model.load_state_dict(checkpoint["state"])
    model.hybrid_weight = float(checkpoint["hybridWeight"])
    model.to(device or torch.device("cpu"))
    model.eval()
    return model, {rid: i for i, rid in enumerate(ids)}


def evaluator(model_path: Path, hybrid: bool = False) -> Callable[..., dict[str, object]]:
    """Adapter for evaluate.run: same cases, same universe, full ranking. `hybrid` adds
    the checkpoint's validated popularity weight."""

    def evaluate(
        *,
        cases: Sequence[EvalCase],
        tags: Mapping[str, frozenset[str]],
        data: SplitData,
        **_: object,
    ) -> dict[str, object]:
        device = pick_device("auto")
        model, rows = load(model_path, device)
        index = _RowsOnly(rows)
        popularity = (
            model.hybrid_weight * log_popularity(index.ids, data.train_counts)
            if hybrid and model.hybrid_weight
            else None
        )
        tops: list[list[str]] = []
        ranks = dense_ranks(model, index, cases, device, tops, 2000, popularity)  # type: ignore[arg-type]
        return {
            **rank_metrics(ranks, 10),
            "catalogueCoverage@10": catalogue_coverage(tops, len(rows) - 1),
            "intraListDiversity@10": intra_list_diversity(tops, tags),
        }

    return evaluate


class TorchScorer:
    """The trained model behind ranking.SequenceScorer; CPU inference is enough.

    With training counts it scores the validated hybrid (the checkpoint's weight unless
    one is given); without them, the pure model. Item vectors do not depend on the user,
    so they are computed once at load; a request only encodes its history.
    """

    def __init__(
        self,
        path: Path,
        popularity_counts: Mapping[str, int] | None = None,
        popularity_weight: float | None = None,
    ) -> None:
        self.model, self.rows = load(path, torch.device("cpu"))
        self.counts = dict(popularity_counts or {})
        weight = self.model.hybrid_weight if popularity_weight is None else popularity_weight
        self.weight = weight if popularity_counts is not None else 0.0
        self.model_version = MODEL_VERSION + (f"+pop{self.weight:g}" if self.weight else "")
        with torch.inference_mode():
            self._vectors = self.model.all_item_vectors()
            self._bias = self.model.item_bias(torch.arange(len(self._vectors)))

    def knows(self, recipe_id: str) -> bool:
        return recipe_id in self.rows

    @torch.inference_mode()
    def score(self, history: Sequence[str], candidates: Sequence[str]) -> dict[str, float]:
        rows = [self.rows[h] for h in history if h in self.rows]
        known = [c for c in candidates if c in self.rows]
        if not rows or not known:
            return {}
        seq = torch.tensor([rows[-self.model.config.max_len :]])  # no padding needed
        state = self.model.encode(seq)[0, -1]
        rows_t = torch.tensor([self.rows[c] for c in known])
        values = (self._vectors[rows_t] @ state + self._bias[rows_t]).tolist()
        return {
            c: float(v) + self.weight * math.log1p(self.counts.get(c, 0))
            for c, v in zip(known, values, strict=True)
        }


class _RowsOnly:
    def __init__(self, rows: dict[str, int]) -> None:
        self.row = rows
        self.ids = [""] * len(rows)
        for rid, i in rows.items():
            self.ids[i] = rid


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--interactions", type=Path, default=Path("Data/Food.com/RAW_interactions.csv")
    )
    parser.add_argument("--recipes", type=Path, default=Path("Data/Food.com/RAW_recipes.csv"))
    parser.add_argument("--output", type=Path, default=Path("Data/models/sasrec_content.pt"))
    parser.add_argument("--epochs", type=int, default=TrainConfig.epochs)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    data = split(load_interactions(args.interactions))
    features = load_features(args.recipes)
    universe = set(features) | {
        r for c in (*data.validation, *data.test) for r in (c.target, *c.history)
    } | set(data.train_counts)  # fmt: skip
    model, index, report = train(
        data,
        features,
        sorted(universe),
        train_config=TrainConfig(epochs=args.epochs),
        device=pick_device(args.device),
    )
    save(args.output, model, index, report)
    report_path = args.output.with_suffix(".json")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output} and {report_path}")


if __name__ == "__main__":
    main()
