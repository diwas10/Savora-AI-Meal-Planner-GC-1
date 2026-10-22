"""Derived-ingredient terms for the stand-in allergy screen.

The stand-in screen in `profile.py` matches whole words, so "milk" alone never sees ghee,
paneer or butter, and "tree nut" never sees pesto. This table maps each allergen group a
user can name to the ingredient words that contain it, written against the 1,364
ingredient names of catalogue 20261021T073631Z. It FAILS CLOSED: a term is listed when an
ingredient usually or often contains the allergen (soy sauce for wheat, Thai curry paste
for shellfish), and exemptions are limited to names that never contain it (coconut milk,
butter lettuce).

Curation status: `ai-review:claude`, not yet reviewed by a person. It is a STAND-IN for the
production KB's ingredient-to-allergen mappings (Member 2); results stay labelled
`STAND_IN_UNVERIFIED`.

A word the table does not know is still matched as itself, exactly as before.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache

from savora_ai.core.meal_composition.composer import _tokens

ALLERGEN_TERMS_VERSION = "derived-allergen-terms.v1"


@dataclass(frozen=True, slots=True)
class AllergenGroup:
    names: tuple[str, ...]  # what a user may type: "milk", "dairy", ...
    terms: tuple[str, ...]  # ingredient words that contain the allergen
    exempt: tuple[str, ...] = ()  # names that contain a term but never the allergen


# fmt: off
_MILK = AllergenGroup(
    names=("milk", "dairy", "lactose", "cow milk", "cows milk", "milk protein", "casein"),
    terms=(
        "milk", "butter", "buttermilk", "ghee", "cream", "creme fraiche", "half-and-half",
        "yogurt", "yoghurt", "curd", "curds", "whey", "casein", "labneh", "tzatziki",
        "khoya", "paneer", "cheese", "feta", "ricotta", "mozzarella", "parmesan",
        "parmigiano", "cheddar", "brie", "gouda", "gruyere", "fontina", "provolone",
        "romano", "pecorino", "roquefort", "boursin", "queso", "kefalotyri",
        "kefalograviera", "colby", "monterey jack", "ice cream", "margarine", "pesto",
        "chocolate", "crescent roll dough", "naan", "raita", "lassi", "kheer",
    ),
    exempt=(
        "coconut milk", "coconut cream", "soymilk", "soy milk", "almond milk", "oat milk",
        "rice milk", "peanut butter", "almond butter", "cocoa butter", "butter lettuce",
        "butter bean", "cream of tartar",
    ),
)

_EGG = AllergenGroup(
    names=("egg", "eggs", "egg white", "egg yolk"),
    terms=(
        "egg", "mayonnaise", "aioli", "meringue", "hollandaise", "thousand island",
        "tartar sauce", "ravioli", "hokkien noodle", "fettuccine", "egg noodle",
    ),
)

_WHEAT_TERMS = (
    "wheat", "flour", "bread", "breadcrumb", "panko", "baguette", "roll", "pita", "naan",
    "roti", "chapati", "paratha", "puri", "tortilla", "pasta", "spaghetti", "macaroni",
    "penne", "fettuccine", "capellini", "manicotti", "ravioli", "couscous", "bulgur",
    "semolina", "seitan", "noodle", "udon", "ramen", "soba", "vermicelli", "pancit",
    "soy sauce", "soya sauce", "teriyaki", "hoisin", "oyster sauce", "ketjap manis",
    "kecap manis", "bisquick", "crescent roll dough", "pastry", "pie shell", "phyllo",
    "toast", "moo shu pancake", "cream of chicken soup", "cream of mushroom soup", "gravy",
    "breaded", "dumpling", "wonton", "cracker",
)
_WHEAT_EXEMPT = (
    "rice flour", "corn flour", "chickpea flour", "gram flour", "corn tortilla",
    "rice noodle", "rice vermicelli", "vermicelli rice noodle", "bean thread noodle",
    "bean thread vermicelli", "bean thread", "cellophane noodle", "spaghetti sauce",
    "shrimp cracker",
)
_WHEAT = AllergenGroup(names=("wheat",), terms=_WHEAT_TERMS, exempt=_WHEAT_EXEMPT)
_GLUTEN = AllergenGroup(
    names=("gluten", "celiac", "coeliac"),
    # Barley flour is wheat-free but not gluten-free, so it is not exempt for either.
    terms=(*_WHEAT_TERMS, "barley", "rye", "malt", "oat", "oatmeal", "spelt"),
    exempt=_WHEAT_EXEMPT,
)

_SOY = AllergenGroup(
    names=("soy", "soya", "soybean", "soybeans"),
    terms=(
        "soy", "soya", "soybean", "soymilk", "tofu", "tempeh", "edamame", "miso", "tamari",
        "shoyu", "bean curd", "liquid aminos", "teriyaki", "hoisin", "ketjap manis",
        "kecap manis", "oyster sauce", "ponzu", "bean paste", "chili bean sauce", "natto",
        "vegetarian bacon", "vegetarian sausage",
    ),
    exempt=("red bean paste",),
)

_PEANUT = AllergenGroup(
    names=("peanut", "peanuts", "groundnut", "groundnuts"),
    terms=("peanut", "groundnut", "satay", "nut", "nuts"),
)

_TREE_NUT = AllergenGroup(
    names=("tree nut", "tree nuts", "nut", "nuts"),
    terms=(
        "nut", "nuts", "almond", "cashew", "walnut", "pecan", "pistachio", "macadamia",
        "hazelnut", "filbert", "brazil nut", "pine nut", "pesto", "praline", "marzipan",
        "nutella", "frangipane",
    ),
    # Whole-word matching already keeps nutmeg and butternut out; coconut and water
    # chestnut are not tree-nut allergens (FDA, 2025).
)

_FISH_TERMS = (
    "fish", "anchovy", "salmon", "tuna", "tilapia", "catfish", "snapper", "swordfish",
    "cod", "sardine", "mackerel", "trout", "halibut", "haddock", "bonito", "dashi",
    "nuoc nam", "patis", "worcestershire", "caesar", "tapenade", "roe", "masago",
    "imitation crabmeat", "green curry paste", "red curry paste", "laksa paste",
)
_FISH = AllergenGroup(names=("fish",), terms=_FISH_TERMS)

_SHELLFISH_TERMS = (
    "shellfish", "shrimp", "prawn", "crab", "crabmeat", "lobster", "crayfish", "clam",
    "mussel", "oyster", "scallop", "squid", "calamari", "octopus", "shrimp paste",
    "belacan", "terasi", "xo sauce", "laksa paste", "green curry paste", "red curry paste",
)
_SHELLFISH = AllergenGroup(
    names=("shellfish", "crustacean", "crustaceans", "mollusc", "molluscs", "mollusk"),
    terms=_SHELLFISH_TERMS,
)
_SEAFOOD = AllergenGroup(names=("seafood",), terms=(*_FISH_TERMS, *_SHELLFISH_TERMS))

_SESAME = AllergenGroup(
    names=("sesame", "sesame seed", "sesame seeds"),
    terms=("sesame", "tahini", "za'atar", "hummus", "halva", "gomasio", "furikake"),
)

# fmt: on
GROUPS: tuple[AllergenGroup, ...] = (
    _MILK,
    _EGG,
    _WHEAT,
    _GLUTEN,
    _SOY,
    _PEANUT,
    _TREE_NUT,
    _FISH,
    _SHELLFISH,
    _SEAFOOD,
    _SESAME,
)


def _words(text: str) -> tuple[str, ...]:
    """The words of `_tokens`, in order: 'Coconut Milks' -> ('coconut', 'milk')."""
    return tuple(word.rstrip("s") for word in re.findall(r"[a-z]+", text.lower()))


def _strip(words: tuple[str, ...], phrase: tuple[str, ...]) -> tuple[str, ...]:
    """Remove every contiguous occurrence of `phrase`."""
    out: list[str] = []
    i, n = 0, len(phrase)
    while i < len(words):
        if words[i : i + n] == phrase:
            i += n
        else:
            out.append(words[i])
            i += 1
    return tuple(out)


@dataclass(frozen=True, slots=True)
class BlockRule:
    """One user word: block a text containing any term, unless only an exempt name does."""

    word: str
    terms: tuple[frozenset[str], ...]
    exempt: tuple[tuple[str, ...], ...]  # phrases, longest first
    derived: bool  # True when the word matched an allergen group

    def blocks(self, text: str) -> bool:
        words = _words(text)
        for phrase in self.exempt:
            words = _strip(words, phrase)
        remaining = frozenset(words)
        return any(term <= remaining for term in self.terms)


@cache
def _groups_by_name() -> dict[frozenset[str], tuple[AllergenGroup, ...]]:
    found: dict[frozenset[str], list[AllergenGroup]] = {}
    for group in GROUPS:
        for name in group.names:
            found.setdefault(_tokens(name), []).append(group)
    return {k: tuple(v) for k, v in found.items()}


@cache
def block_rules(words: tuple[str, ...]) -> tuple[BlockRule, ...]:
    """The rules for a profile's exclusions and allergies; unknown words match themselves."""
    rules: list[BlockRule] = []
    for word in words:
        own = _tokens(word)
        if not own:
            continue
        groups = _groups_by_name().get(own, ())
        if not groups:
            rules.append(BlockRule(word, (own,), (), derived=False))
            continue
        terms = {own, *(_tokens(t) for g in groups for t in g.terms)}
        # An exemption applies only when every matched group agrees it is safe.
        exempt = set.intersection(*({_words(e) for e in g.exempt} for g in groups))
        rules.append(
            BlockRule(
                word,
                tuple(sorted(terms, key=sorted)),
                tuple(sorted(exempt, key=lambda p: (-len(p), p))),
                derived=True,
            )
        )
    return tuple(rules)


def all_derived(words: Iterable[str]) -> bool:
    """True when every word matched an allergen group (so derived terms were checked)."""
    rules = block_rules(tuple(words))
    return bool(rules) and all(r.derived for r in rules)
