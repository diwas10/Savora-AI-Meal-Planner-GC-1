"""T1: chronological interaction sequences and the global time split (ADR 0004 D1).

    train       before TRAIN_END      fit models, popularity, baselines
    validation  [TRAIN_END, VALID_END) early stopping only
    test        VALID_END onward       reported metrics only

An evaluation case is a user's FIRST interaction in a period; its history is everything
the user did before it. Earlier periods are in the past, so using them as history is not
leakage; the model's weights only ever learn from training-period targets.
Food.com gives dates, not times: within one day, file order is kept (documented limit).
"""

import csv
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

TRAIN_END = date(2012, 1, 1)  # equals the popularity cutoff (ADR 0001 D6)
VALID_END = date(2013, 1, 1)
MAX_HISTORY = 50  # the last 50 items are what any model sees


@dataclass(frozen=True)
class Interaction:
    user_id: str
    recipe_id: str  # "FC_<id>", the catalogue ID format
    day: date
    order: int  # file position: the only tie-break available within one day


@dataclass(frozen=True)
class EvalCase:
    user_id: str
    history: tuple[str, ...]  # oldest first, at most MAX_HISTORY items
    target: str


@dataclass(frozen=True)
class SplitData:
    train_sequences: dict[str, tuple[str, ...]]  # training-period items, oldest first
    validation: tuple[EvalCase, ...]
    test: tuple[EvalCase, ...]
    train_counts: dict[str, int]  # popularity from the training period only

    def report(self) -> dict[str, object]:
        lengths = sorted(len(s) for s in self.train_sequences.values())
        return {
            "trainEnd": TRAIN_END.isoformat(),
            "validEnd": VALID_END.isoformat(),
            "trainUsers": len(lengths),
            "trainInteractions": sum(lengths),
            "medianTrainHistory": lengths[len(lengths) // 2] if lengths else 0,
            "validationCases": len(self.validation),
            "testCases": len(self.test),
            "testTargetsUnseenInTrain": sum(c.target not in self.train_counts for c in self.test),
        }


def load_interactions(path: Path) -> list[Interaction]:
    csv.field_size_limit(sys.maxsize)  # reviews can be long and span lines
    rows: list[Interaction] = []
    with path.open(encoding="utf-8", newline="") as stream:
        for order, row in enumerate(csv.DictReader(stream)):
            if not row["recipe_id"].isdecimal():
                raise ValueError(f"row {order}: non-numeric recipe id {row['recipe_id']!r}")
            rows.append(
                Interaction(
                    user_id=row["user_id"],
                    recipe_id=f"FC_{int(row['recipe_id'])}",
                    day=date.fromisoformat(row["date"]),
                    order=order,
                )
            )
    return rows


def _first_case(events: list[Interaction], start: date, end: date | None) -> EvalCase | None:
    for index, event in enumerate(events):
        if event.day >= start and (end is None or event.day < end):
            history = tuple(e.recipe_id for e in events[:index])[-MAX_HISTORY:]
            if not history:
                return None  # nothing to predict from: a cold user, not a test case
            return EvalCase(event.user_id, history, event.recipe_id)
    return None


def split(
    interactions: Iterable[Interaction],
    train_end: date = TRAIN_END,
    valid_end: date = VALID_END,
) -> SplitData:
    if not train_end < valid_end:
        raise ValueError("train_end must be before valid_end")
    by_user: dict[str, list[Interaction]] = defaultdict(list)
    for event in interactions:
        by_user[event.user_id].append(event)
    train: dict[str, tuple[str, ...]] = {}
    validation: list[EvalCase] = []
    test: list[EvalCase] = []
    counts: Counter[str] = Counter()
    for user in sorted(by_user):
        events = sorted(by_user[user], key=lambda e: (e.day, e.order))
        past = tuple(e.recipe_id for e in events if e.day < train_end)
        if past:
            train[user] = past
            counts.update(past)
        for bucket, case in (
            (validation, _first_case(events, train_end, valid_end)),
            (test, _first_case(events, valid_end, None)),
        ):
            if case is not None:
                bucket.append(case)
    return SplitData(
        train_sequences=train,
        validation=tuple(validation),
        test=tuple(test),
        train_counts=dict(counts),
    )
