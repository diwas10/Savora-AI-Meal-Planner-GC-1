"""Stage 5: recipe popularity from TRAINING interactions only (ADR 0001 D6).

Popularity is used twice: as a tie-breaker when choosing catalogue dishes, and as the
cold-start prior for ranking. If it counted interactions the ranker is later evaluated
on, the evaluation would leak: a recipe would look popular *because of* the test data.

So only interactions strictly before a global date cutoff count. The Food.com files
`interactions_train/validation/test.csv` are NOT used: they split each user's history,
so "train" holds 2018 interactions while "test" holds 2000 ones; counting that train
file would still leak the future of other users. A global time cutoff cannot.

The cutoff is PROVISIONAL and must equal the Transformer's training cutoff once that
split is decided (ARCHITECTURE.md section 7).
"""

import csv
import hashlib
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# About 80% of the 1.13 M Food.com interactions fall before this date (80th percentile is
# 2011-12-27), leaving 2012-2018 for validation and test.
DEFAULT_POPULARITY_CUTOFF = date(2012, 1, 1)


@dataclass(frozen=True)
class PopularityTable:
    """Training-interaction counts per catalogue recipe ID (FC_<id>)."""

    cutoff: date
    counts: dict[str, int]
    training_interactions: int
    held_out_interactions: int  # on/after the cutoff: never counted
    source_sha256: str | None = None

    def count(self, recipe_id: str) -> int:
        """Training interactions; a recipe never seen before the cutoff counts 0."""
        return self.counts.get(recipe_id, 0)

    def report(self) -> dict[str, object]:
        return {
            "cutoff": self.cutoff.isoformat(),
            "rule": "interactions strictly before the cutoff only",
            "trainingInteractions": self.training_interactions,
            "heldOutInteractionsIgnored": self.held_out_interactions,
            "recipesWithTrainingInteractions": len(self.counts),
            "sourceSha256": self.source_sha256,
        }


def count_interactions(
    rows: Iterable[tuple[str, str]], cutoff: date, *, source_sha256: str | None = None
) -> PopularityTable:
    """Count (recipe_id, ISO date) rows dated before `cutoff`; fail loudly on bad rows."""
    counts: Counter[str] = Counter()
    held_out = 0
    for recipe_id, day in rows:
        if not recipe_id.isdecimal():
            raise ValueError(f"interaction has a non-numeric recipe id {recipe_id!r}")
        if date.fromisoformat(day) < cutoff:
            counts[f"FC_{int(recipe_id)}"] += 1
        else:
            held_out += 1
    return PopularityTable(
        cutoff=cutoff,
        counts=dict(sorted(counts.items())),
        training_interactions=sum(counts.values()),
        held_out_interactions=held_out,
        source_sha256=source_sha256,
    )


def load_popularity(path: Path, cutoff: date = DEFAULT_POPULARITY_CUTOFF) -> PopularityTable:
    """Stream RAW_interactions.csv (reviews span lines; the csv module handles quotes)."""
    with path.open("rb") as binary:
        digest = hashlib.file_digest(binary, "sha256").hexdigest()
    csv.field_size_limit(sys.maxsize)
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"recipe_id", "date"} <= set(reader.fieldnames or []):
            raise ValueError("interactions file needs recipe_id and date columns")
        return count_interactions(
            ((row["recipe_id"], row["date"]) for row in reader), cutoff, source_sha256=digest
        )
