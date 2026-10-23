"""Deterministic grounding of a model's craving answer ("never trust Qwen output").

`ground()` runs after schema-constrained decoding and BEFORE strict validation. It keeps
only what the user's own words support and never adds a value:

- cuisines: a cuisine named in the text (typos allowed) wins over the model's guess;
  with no cuisine word, at most one dish-implied cuisine from the model is kept
- flavors: only a flavor whose word appears, and not negated ("not too spicy")
- exclusions: only an ingredient named after a negation ("no", "without", ...)
- intent: SWAP_MEAL only when the text has a swap word (swap, replace, change...)
- slot: read from the words (weekday or "day N", plus a meal), never the model's guess
- clarification: forced on any allergy mention and on a swap without a slot

Measured in `docs/reports/craving_nlu_feasibility_report.md`: with qwen3:0.6b it raises
slot precision from 0.67 to 0.97.
"""

import re
from collections.abc import Mapping
from typing import Any

FLAVOR_WORDS: dict[str, tuple[str, ...]] = {
    "SPICY": ("spicy", "spice", "hot", "chili", "chilli", "fiery", "szechuan", "sichuan"),
    "SWEET": ("sweet", "dessert", "sugary"),
    "SOUR": ("sour", "tangy", "tart"),
    "SMOKY": ("smoky", "smoked", "smokey", "bbq", "barbecue"),
    "CREAMY": ("creamy", "cream"),
}
DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
SWAP_WORDS = re.compile(r"\b(swap|replace|substitute|change|switch|instead)\b")
NEGATION = re.compile(r"\b(no|without|not|don t|dont|except|free of|minus)\b")


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def norm_ingredient(value: str) -> str:
    """Compare ingredient IDs singular/plural-insensitively: EGG == EGGS."""
    return value.removesuffix("ES") if value.endswith("OES") else value.removesuffix("S")


def _near(a: str, b: str) -> bool:
    """Equal, or one edit apart for words of 4+ letters (thia ~ thai, chineese ~ chinese)."""
    if a == b:
        return True
    if min(len(a), len(b)) < 4 or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        return len(diff) == 1 or (
            len(diff) == 2 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]
        )
    short, long = sorted((a, b), key=len)
    return any(long[:i] + long[i + 1 :] == short for i in range(len(long)))


def ground(text: str, body: dict[str, Any], cuisines: Mapping[str, str]) -> dict[str, Any]:
    """Keep only what the message supports. Deterministic; never adds a value."""
    if not isinstance(body, dict):
        raise ValueError("the answer is not a JSON object")
    words = _words(text)
    lowered = " ".join(words)
    out = dict(body)
    if body.get("intent") == "SWAP_MEAL" and not SWAP_WORDS.search(lowered):
        out["intent"] = "CRAVING_RECOMMEND"
    named = {
        cid
        for cid, name in cuisines.items()
        if all(any(_near(w, part) for w in words) for part in _words(name))
    }
    # A cuisine word in the text wins; otherwise one dish-implied cuisine may stay.
    model_cuisines = [c for c in body.get("cuisineIds", []) if c in cuisines]
    out["cuisineIds"] = (
        [c for c in model_cuisines if c in named] or sorted(named) if named else model_cuisines[:1]
    )
    out["flavorTags"] = [
        tag
        for tag in body.get("flavorTags", [])
        if tag in FLAVOR_WORDS
        and any(w in FLAVOR_WORDS[tag] for w in words)
        and not re.search(rf"not (too |very )?({'|'.join(FLAVOR_WORDS[tag])})", lowered)
    ]
    negated = NEGATION.search(lowered)
    after = lowered[negated.start() :] if negated else ""
    out["excludedIngredientIds"] = [
        x
        for x in body.get("excludedIngredientIds", [])
        if isinstance(x, str) and after and norm_ingredient(x).lower() in after
    ]
    # The slot is read from the words when they name it (weekday or "day N", and a meal);
    # the model's guess is never kept without them.
    meal = next((m for m in ("breakfast", "lunch", "dinner") if m in words), None)
    day = next((i + 1 for i, d in enumerate(DAYS) if d in lowered), None)
    number = re.search(r"\b(?:day ?|d)([1-7])\b", lowered)
    day = int(number.group(1)) if number else day
    slot = None
    swap = out.get("intent") == "SWAP_MEAL"
    if swap and meal and day:
        slot = f"D{day}_{meal.upper()}"
    out["mealSlotId"] = slot
    clarify = bool(body.get("requiresClarification"))
    if "allerg" in lowered or (swap and slot is None):
        clarify = True
    out["requiresClarification"] = clarify
    return out
