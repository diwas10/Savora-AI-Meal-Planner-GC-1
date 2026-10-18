"""Stage 7: stratified, reproducible catalogue selection (ADR 0001 D6).

The planning catalogue is small (about 200 dishes), so WHICH dishes it holds decides
what plans are possible. Picking by hash alone gave 122 American dishes out of 191 and 3
Indian ones. Selection therefore fills a quota per stratum = (cuisine, slot kind):

    breakfast base | complete-meal main | main needing an accompaniment | vegetable side

Why these sizes: a dish may repeat at most twice a week, so 7 breakfasts need at least 4
distinct dishes and 14 lunches + dinners at least 7 distinct mains; rule filtering (diet,
allergy) then removes some, so each stratum aims for 10, at least half vegetarian.

Within a stratum the order is: curated first (a reviewer chose it), then training-split
popularity (Stage 5; never held-out data), then a seeded hash. A stratum that cannot fill
its quota is reported, never padded with off-target dishes.
"""

import hashlib
import math
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from savora_ai.core.food_data.classification import is_plannable
from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.schemas.enums import ClassificationStatus, CulinaryRole, DishClass, MealType

# PROVISIONAL target cuisines (project lead's choice): the Asian focus plus three western
# cuisines for MIXED-policy variety. Order matters: thinner cuisines pick first, so a
# dish labelled both Indian and Nepali is credited to Nepali, which has fewer dishes.
TARGET_CUISINES: tuple[str, ...] = (
    "Nepali",
    "Thai",
    "Chinese",
    "Indian",
    "Mexican",
    "Italian",
    "American",
)

VEGETARIAN_TAG = "vegetarian"
MIN_VEGETARIAN_SHARE = 0.5


@dataclass(frozen=True)
class SlotKind:
    name: str
    quota: int
    accepts: Callable[[CatalogueRecipe], bool]


def _breakfast(r: CatalogueRecipe) -> bool:
    return CulinaryRole.BREAKFAST_BASE in r.roles and MealType.BREAKFAST in r.meal_types


def _main(dish_class: DishClass) -> Callable[[CatalogueRecipe], bool]:
    def accepts(r: CatalogueRecipe) -> bool:
        return (
            CulinaryRole.MAIN_DISH in r.roles
            and r.dish_class is dish_class
            and MealType.LUNCH in r.meal_types
        )

    return accepts


def _vegetable_side(r: CatalogueRecipe) -> bool:
    return CulinaryRole.VEGETABLE in r.roles and r.dish_class is DishClass.COMPONENT


# PROVISIONAL quotas per cuisine, tuned with Stage 10 scenario coverage: 8 left three of
# eight synthetic scenarios short; 10 leaves two, both data limits (no Nepali breakfasts
# exist; peanut-free Thai breakfasts are 3 at any quota); 12 adds dishes but no coverage.
SLOT_KINDS: tuple[SlotKind, ...] = (
    SlotKind("BREAKFAST_BASE", 10, _breakfast),
    SlotKind("COMPLETE_MAIN", 10, _main(DishClass.COMPLETE_MEAL)),
    SlotKind("MAIN_WITH_ACCOMPANIMENT", 10, _main(DishClass.REQUIRES_ACCOMPANIMENT)),
    SlotKind("VEGETABLE_SIDE", 4, _vegetable_side),
)


def normalized_name(name: str) -> str:
    """Near-duplicate key: 'Chicken  Tikka Masala (Easy!)' == 'chicken tikka masala easy'."""
    return " ".join(re.findall(r"[a-z]+", name.lower()))


def _hash(seed: str, recipe_id: str) -> str:
    return hashlib.sha256(f"{seed}:{recipe_id}".encode()).hexdigest()


@dataclass(frozen=True)
class StratumReport:
    cuisine: str
    slot_kind: str
    quota: int
    eligible: int
    selected: int
    vegetarian_selected: int

    def as_json(self) -> dict[str, object]:
        return {
            "cuisine": self.cuisine,
            "slotKind": self.slot_kind,
            "quota": self.quota,
            "eligible": self.eligible,
            "selected": self.selected,
            "vegetarianSelected": self.vegetarian_selected,
            "shortfall": max(0, self.quota - self.selected),
        }


@dataclass(frozen=True)
class Selection:
    recipes: tuple[CatalogueRecipe, ...]
    strata: tuple[StratumReport, ...]


def select_stratified(
    candidates: Iterable[CatalogueRecipe],
    popularity: Mapping[str, int],
    seed: str,
    *,
    cuisines: tuple[str, ...] = TARGET_CUISINES,
    slot_kinds: tuple[SlotKind, ...] = SLOT_KINDS,
) -> Selection:
    """Same candidates + popularity + seed => same selection, in any input order."""
    pool = [r for r in candidates if is_plannable(r)]

    def order(r: CatalogueRecipe) -> tuple[bool, int, str]:
        curated = r.classification_status is ClassificationStatus.CURATED
        return (not curated, -popularity.get(r.recipe_id, 0), _hash(seed, r.recipe_id))

    pool.sort(key=order)
    chosen: dict[str, CatalogueRecipe] = {}
    reports: list[StratumReport] = []
    for cuisine in cuisines:
        for kind in slot_kinds:
            eligible = [r for r in pool if cuisine in r.cuisines and kind.accepts(r)]
            # Dishes already chosen for another stratum count here too, once.
            in_stratum = [r for r in eligible if r.recipe_id in chosen]
            names = {normalized_name(r.name) for r in in_stratum}
            need_veg = math.ceil(kind.quota * MIN_VEGETARIAN_SHARE)
            veg = sum(VEGETARIAN_TAG in r.diet_tags for r in in_stratum)
            # Pass 1 fills the vegetarian share; pass 2 fills the rest by order.
            for vegetarian_only in (True, False):
                for recipe in eligible:
                    if len(in_stratum) >= kind.quota or (vegetarian_only and veg >= need_veg):
                        break
                    is_veg = VEGETARIAN_TAG in recipe.diet_tags
                    key = normalized_name(recipe.name)
                    if recipe.recipe_id in chosen or key in names:
                        continue
                    if vegetarian_only and not is_veg:
                        continue
                    chosen[recipe.recipe_id] = recipe
                    in_stratum.append(recipe)
                    names.add(key)
                    veg += is_veg
            reports.append(
                StratumReport(
                    cuisine=cuisine,
                    slot_kind=kind.name,
                    quota=kind.quota,
                    eligible=len(eligible),
                    selected=len(in_stratum),
                    vegetarian_selected=veg,
                )
            )
    recipes = tuple(sorted(chosen.values(), key=lambda r: r.recipe_id))
    return Selection(recipes=recipes, strata=tuple(reports))
