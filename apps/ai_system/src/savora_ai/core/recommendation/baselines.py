"""T2: popularity, item-kNN and first-order Markov baselines, with EXACT full ranking.

Each baseline gives a sparse "primary" score (most recipes score 0). Every recipe is then
ordered by (primary score desc, training popularity desc, recipe ID). So popularity is
the shared tie-break, and a baseline that knows nothing degrades to popularity, never to
an arbitrary order. The target's rank is counted, not sorted, so ranking all ~231,000
recipes per case stays cheap. Items already in the history are excluded for every model
the same way (the target itself is never excluded).
"""

import itertools
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

KNN_WINDOW = 20  # co-occurrence uses each user's last 20 training items (bounds memory)
KNN_NEIGHBOURS = 100
KNN_HISTORY = 20  # items of history that vote


@dataclass(frozen=True)
class PopularityOrder:
    """Every recipe in the universe ordered by training count, then ID: the tie-break."""

    position: dict[str, int]  # 0 = most popular
    order: tuple[str, ...]

    @classmethod
    def build(cls, universe: Iterable[str], counts: Mapping[str, int]) -> "PopularityOrder":
        order = tuple(sorted(set(universe), key=lambda i: (-counts.get(i, 0), i)))
        return cls(position={item: i for i, item in enumerate(order)}, order=order)


class Ranker(Protocol):
    name: str

    def primary_scores(self, history: Sequence[str]) -> Mapping[str, float]:
        """Positive scores only; an absent recipe scores 0."""
        ...


def full_rank(
    primary: Mapping[str, float], target: str, history: Sequence[str], pop: PopularityOrder
) -> int:
    """1-based rank of `target` among all recipes not in the history."""
    if target not in pop.position:
        raise ValueError(f"target {target} is not in the ranking universe")
    p_t, q_t = primary.get(target, 0.0), pop.position[target]

    def above(item: str) -> bool:
        p = primary.get(item, 0.0)
        return p > p_t or (p == p_t and pop.position[item] < q_t)

    if p_t > 0:  # only scored items can beat a scored target
        count = sum(1 for item in primary if above(item))
    else:  # every scored item, plus unscored items more popular than the target
        scored_more_popular = sum(1 for item in primary if pop.position[item] < q_t)
        count = len(primary) + (q_t - scored_more_popular)
    # History outside the universe (e.g. a non-catalogue dish when ranking the catalogue)
    # was never a competitor, so it is not subtracted.
    count -= sum(1 for item in set(history) - {target} if item in pop.position and above(item))
    return count + 1


def top_k(
    primary: Mapping[str, float],
    history: Sequence[str],
    pop: PopularityOrder,
    k: int,
    target: str | None = None,
) -> list[str]:
    """The k best items. As in `full_rank`, the held-out `target` is never excluded."""
    seen = set(history) - {target}
    ranked = sorted(primary, key=lambda i: (-primary[i], pop.position[i]))
    result = [i for i in ranked if i not in seen][:k]
    for item in pop.order:
        if len(result) >= k:
            break
        if item not in seen and item not in primary:
            result.append(item)
    return result


class Popularity:
    name = "popularity"

    def primary_scores(self, history: Sequence[str]) -> Mapping[str, float]:
        return {}  # the shared tie-break IS popularity


class Markov:
    """First-order transitions: P(next | last item) from consecutive training pairs."""

    name = "markov"

    def __init__(self, sequences: Iterable[Sequence[str]]) -> None:
        self.transitions: dict[str, Counter[str]] = defaultdict(Counter)
        for sequence in sequences:
            for a, b in itertools.pairwise(sequence):
                if a != b:
                    self.transitions[a][b] += 1

    def primary_scores(self, history: Sequence[str]) -> Mapping[str, float]:
        if not history or history[-1] not in self.transitions:
            return {}
        nexts = self.transitions[history[-1]]
        total = sum(nexts.values())
        return {item: n / total for item, n in nexts.items()}


class ItemKNN:
    """Cosine co-occurrence within users' training histories ("similar users also had")."""

    name = "item_knn"

    def __init__(self, sequences: Iterable[Sequence[str]]) -> None:
        co: dict[str, Counter[str]] = defaultdict(Counter)
        users_with: Counter[str] = Counter()
        for sequence in sequences:
            items = list(dict.fromkeys(sequence[-KNN_WINDOW:]))  # unique, order kept
            users_with.update(items)
            for i, a in enumerate(items):
                for b in items[i + 1 :]:
                    co[a][b] += 1
                    co[b][a] += 1
        self.neighbours: dict[str, list[tuple[str, float]]] = {}
        for a, row in co.items():
            sims = [(b, n / math.sqrt(users_with[a] * users_with[b])) for b, n in row.items()]
            sims.sort(key=lambda x: (-x[1], x[0]))
            self.neighbours[a] = sims[:KNN_NEIGHBOURS]

    def primary_scores(self, history: Sequence[str]) -> Mapping[str, float]:
        scores: defaultdict[str, float] = defaultdict(float)
        for item in history[-KNN_HISTORY:]:
            for neighbour, sim in self.neighbours.get(item, ()):
                scores[neighbour] += sim
        return dict(scores)
