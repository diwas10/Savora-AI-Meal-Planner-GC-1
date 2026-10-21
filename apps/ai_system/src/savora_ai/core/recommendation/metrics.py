"""T2: ranking metrics for ONE held-out target per case, by full ranking (ADR 0004 D4).

rank is 1-based over every candidate recipe the user has not already interacted with.

    HR@K    share of cases whose target is in the top K
    NDCG@K  1 / log2(rank + 1) if rank <= K, else 0 (one relevant item: IDCG = 1)
    MRR     mean of 1 / rank

Beyond accuracy: catalogue coverage (share of the universe ever shown in a top K) and
intra-list diversity (mean pairwise Jaccard distance of the top K's tag sets).
"""

import math
from collections.abc import Iterable, Mapping, Sequence


def rank_metrics(ranks: Sequence[int], k: int = 10) -> dict[str, float | int]:
    if any(r < 1 for r in ranks):
        raise ValueError("ranks are 1-based")
    n = len(ranks)
    if n == 0:
        return {"cases": 0, f"hr@{k}": 0.0, f"ndcg@{k}": 0.0, "mrr": 0.0}
    return {
        "cases": n,
        f"hr@{k}": sum(r <= k for r in ranks) / n,
        f"ndcg@{k}": sum(1 / math.log2(r + 1) for r in ranks if r <= k) / n,
        "mrr": sum(1 / r for r in ranks) / n,
    }


def catalogue_coverage(top_lists: Iterable[Sequence[str]], universe_size: int) -> float:
    shown = {item for top in top_lists for item in top}
    return len(shown) / universe_size if universe_size else 0.0


def intra_list_diversity(
    top_lists: Iterable[Sequence[str]], tags: Mapping[str, frozenset[str]]
) -> float:
    """Mean over lists of the mean pairwise Jaccard distance between item tag sets."""
    values: list[float] = []
    for top in top_lists:
        pairs = [(a, b) for i, a in enumerate(top) for b in top[i + 1 :]]
        if not pairs:
            continue
        distances = []
        for a, b in pairs:
            ta, tb = tags.get(a, frozenset()), tags.get(b, frozenset())
            union = ta | tb
            distances.append(1 - len(ta & tb) / len(union) if union else 0.0)
        values.append(sum(distances) / len(distances))
    return sum(values) / len(values) if values else 0.0
