"""Stage 2: culinary roles, dish class and meal types from Food.com tags (ADR 0001 D5).

Tags are EVIDENCE, not answers. Food.com mixes two kinds of tag:

- course tags say what a dish is in a meal (`main-dish`, `side-dishes`, `breakfast`);
- main-ingredient tags say what it is made of (`vegetables`, `rice`, `pasta`).

"Vegetable soup" carries `vegetables` but is not a vegetable side, so roles come from
course tags and ingredient tags only qualify them. Every rule that fires is recorded in
`evidence`, so a reviewer can see why a dish got its labels. Conflicting or weak evidence
gives REQUIRES_REVIEW, never a silent guess. The tables are PROVISIONAL and curated.
"""

import re
from collections.abc import Iterable, Mapping
from typing import Literal, Self

from pydantic import Field, model_validator

from savora_ai.core.food_data.foodcom_cuisines import CUISINE_TAGS
from savora_ai.core.food_data.models import CatalogueRecipe, _FoodModel, _NonBlank
from savora_ai.schemas.enums import ClassificationStatus, CulinaryRole, DishClass, MealType

# --- course evidence ----------------------------------------------------------------
# A dish with one of these courses is not served as part of a planned meal.
NON_MEAL_TAGS = frozenset(
    {
        "appetizers",
        "bar-cookies",
        "beverages",
        "cakes",
        "candy",
        "cocktails",
        "condiments-etc",
        "cookies-and-brownies",
        "desserts",
        "dips",
        "frostings-and-icing",
        "pies",
        "pies-and-tarts",
        "punch",
        "sauces",
        "smoothies",
        "snacks",
    }
)
MAIN_TAG = "main-dish"
ONE_DISH_TAG = "one-dish-meal"
BREAKFAST_TAGS = frozenset({"breakfast", "brunch"})
SIDE_TAG = "side-dishes"
SALAD_TAG = "salads"
BREADS_TAG = "breads"
LUNCH_TAG = "lunch"
SOUP_TAG = "soups-stews"  # weak: a soup can be a main (dal) or a starter

# --- qualifiers (main-ingredient and dish-type tags) --------------------------------
STAPLE_INGREDIENT_TAGS = frozenset({"pasta-rice-and-grains", "rice", "grains", "pasta", "potatoes"})
VEGETABLE_INGREDIENT_TAGS = frozenset({"vegetables", "greens"})
SWEET_TAGS = frozenset(
    {"sweet", "chocolate", "desserts", "cakes", "cookies-and-brownies", "muffins", "fruit"}
)
# Sweet baked goods that Food.com files under `breads`; they are not a meal staple.
SWEET_BREAD_NAME_WORDS = (
    "muffin",
    "banana bread",
    "scone",
    "cinnamon",
    "coffee cake",
    "doughnut",
    "donut",
    "sweet roll",
    "pumpkin bread",
    "zucchini bread",
)
# A main dish with one of these already contains its own staple, so it stands alone.
SELF_CONTAINED_TAGS = frozenset({"pasta", "sandwiches", "pizza", "casseroles", "salads"})
SELF_CONTAINED_NAME_WORDS = (
    "biryani",
    "pulao",
    "pilaf",
    "fried rice",
    "risotto",
    "paella",
    "noodle",
    "lo mein",
    "chow mein",
    "pad thai",
    "ramen",
    "lasagna",
    "spaghetti",
    "burrito",
    "sandwich",
    "wrap",
    "pizza",
    "burger",
    "quesadilla",
    "momo",
    "dumpling",
    "rice",
    "pasta",
    "macaroni",
    "enchilada",
    "pot pie",
    "taco",
)

# Cuisine names a curated record may use: the exact-tag cuisines plus curated-only ones.
# Food.com has no Nepali tag, so Nepali comes from curation alone (ADR 0001 open item 1).
CURATED_ONLY_CUISINES = ("Nepali",)
KNOWN_CUISINES = frozenset((*CUISINE_TAGS, *CURATED_ONLY_CUISINES))


def check_cuisines(cuisines: Iterable[str]) -> None:
    unknown = sorted(set(cuisines) - KNOWN_CUISINES)
    if unknown:
        raise ValueError(f"unknown cuisine names {unknown}; use one of {sorted(KNOWN_CUISINES)}")


# A main or complete meal below this energy per serving is implausible as a meal.
MIN_MEAL_KCAL = 50.0
# A side or staple above this per "serving" is usually a whole batch or loaf.
MAX_COMPONENT_KCAL = 700.0

# Role -> meals it suits. A main dish suits lunch AND dinner (no `main-dish -> DINNER`).
ROLE_MEALS: dict[CulinaryRole, frozenset[MealType]] = {
    CulinaryRole.BREAKFAST_BASE: frozenset({MealType.BREAKFAST}),
    CulinaryRole.MAIN_DISH: frozenset({MealType.LUNCH, MealType.DINNER}),
    CulinaryRole.PROTEIN_SOURCE: frozenset({MealType.LUNCH, MealType.DINNER}),
    CulinaryRole.STAPLE: frozenset({MealType.LUNCH, MealType.DINNER}),
    CulinaryRole.VEGETABLE: frozenset({MealType.LUNCH, MealType.DINNER}),
    CulinaryRole.FRUIT: frozenset({MealType.BREAKFAST}),
    CulinaryRole.SUPPLEMENT: frozenset({MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER}),
}

_MEAL_ROLES = frozenset({CulinaryRole.MAIN_DISH, CulinaryRole.BREAKFAST_BASE})


class Classification(_FoodModel):
    roles: tuple[CulinaryRole, ...]
    dish_class: DishClass | None
    meal_types: tuple[MealType, ...]
    status: ClassificationStatus
    evidence: tuple[_NonBlank, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def check_consistent(self) -> Self:
        # A dish without roles has no class and suits no meal; one with roles has both.
        if (not self.roles) != (self.dish_class is None) or (not self.roles) != (
            not self.meal_types
        ):
            raise ValueError("roles, dishClass and mealTypes must be all set or all empty")
        return self


class ClassificationOverride(_FoodModel):
    """A curated correction for one recipe (Stage 2b, Stage 6).

    Classification fields are replaced together, or not at all (a cuisine-only override).
    Empty roles mark a dish as deliberately not plannable.
    """

    recipe_id: _NonBlank
    roles: tuple[CulinaryRole, ...] | None = None
    dish_class: DishClass | None = None
    meal_types: tuple[MealType, ...] | None = None
    cuisines: tuple[_NonBlank, ...] | None = None
    rationale: _NonBlank
    curated_by: _NonBlank

    @model_validator(mode="after")
    def check_complete(self) -> Self:
        if (self.roles is None) != (self.meal_types is None):
            raise ValueError("roles and mealTypes must be overridden together")
        if self.roles is None and self.dish_class is not None:
            raise ValueError("dishClass cannot be overridden without roles")
        if self.roles is not None and bool(self.roles) != (self.dish_class is not None):
            raise ValueError("a plannable override needs a dishClass; an exclusion has none")
        if self.roles is None and self.cuisines is None:
            raise ValueError("an override must change something")
        if self.cuisines is not None:
            check_cuisines(self.cuisines)
        return self


class ClassificationOverrideFile(_FoodModel):
    """The curated file `Data/curated/classification_overrides.json`."""

    schema_version: Literal["classification-overrides.v1"]
    note: _NonBlank
    overrides: tuple[ClassificationOverride, ...]


def _ordered[T](values: Iterable[T], order: Iterable[T]) -> tuple[T, ...]:
    """Enum order, so output never depends on set iteration order."""
    found = set(values)
    return tuple(item for item in order if item in found)


def meals_for_roles(roles: Iterable[CulinaryRole]) -> tuple[MealType, ...]:
    return _ordered((meal for role in roles for meal in ROLE_MEALS[role]), MealType)


def has_name_word(name: str, words: Iterable[str]) -> bool:
    """Whole words (plural allowed): 'rice' matches 'fried rice', not 'licorice';
    'wrap' matches 'chicken wraps', not 'bacon-wrapped'."""
    return any(re.search(rf"\b{re.escape(word)}s?\b", name) for word in words)


def _dish_class(roles: set[CulinaryRole], tags: frozenset[str], name: str) -> DishClass:
    if ONE_DISH_TAG in tags:
        return DishClass.COMPLETE_MEAL
    if CulinaryRole.MAIN_DISH in roles:
        lowered = name.lower()
        if tags & SELF_CONTAINED_TAGS or has_name_word(lowered, SELF_CONTAINED_NAME_WORDS):
            return DishClass.COMPLETE_MEAL
        return DishClass.REQUIRES_ACCOMPANIMENT
    if CulinaryRole.BREAKFAST_BASE in roles:
        return DishClass.COMPLETE_MEAL  # a breakfast dish stands alone; fruit is optional
    return DishClass.COMPONENT


def classify(name: str, tags: frozenset[str], energy_kcal: float) -> Classification:
    """Derive roles, dish class and meal types; pure and deterministic."""
    evidence: list[str] = []
    roles: set[CulinaryRole] = set()
    weak = False
    unqualified_side = False  # only weak if it is the sole role evidence

    if MAIN_TAG in tags or ONE_DISH_TAG in tags:
        roles.add(CulinaryRole.MAIN_DISH)
        evidence.append("course main-dish/one-dish-meal -> MAIN_DISH")
    if tags & BREAKFAST_TAGS:
        roles.add(CulinaryRole.BREAKFAST_BASE)
        evidence.append("course breakfast/brunch -> BREAKFAST_BASE")
    if SIDE_TAG in tags:
        if tags & STAPLE_INGREDIENT_TAGS:
            roles.add(CulinaryRole.STAPLE)
            evidence.append("side-dishes + rice/grain/pasta/potato -> STAPLE")
        elif tags & VEGETABLE_INGREDIENT_TAGS:
            roles.add(CulinaryRole.VEGETABLE)
            evidence.append("side-dishes + vegetables -> VEGETABLE")
        else:
            unqualified_side = True
            evidence.append("side-dishes without a staple/vegetable qualifier")
    if SALAD_TAG in tags and CulinaryRole.MAIN_DISH not in roles:
        if tags & STAPLE_INGREDIENT_TAGS:  # pasta, rice or potato salad
            roles.add(CulinaryRole.STAPLE)
            evidence.append("salads + rice/grain/pasta/potato -> STAPLE")
        else:
            roles.add(CulinaryRole.VEGETABLE)
            evidence.append("course salads -> VEGETABLE")
    if BREADS_TAG in tags:
        lowered = name.lower()
        if tags & SWEET_TAGS or has_name_word(lowered, SWEET_BREAD_NAME_WORDS):
            evidence.append("sweet bread: not a staple")
        else:
            roles.add(CulinaryRole.STAPLE)
            evidence.append("course breads (not sweet) -> STAPLE")
    if unqualified_side and not roles:
        weak = True
    if not roles and SOUP_TAG in tags:
        roles.add(CulinaryRole.MAIN_DISH)
        weak = True
        evidence.append("soups-stews only: main or starter is unclear")
    if not roles and LUNCH_TAG in tags:
        roles.add(CulinaryRole.MAIN_DISH)
        weak = True
        evidence.append("lunch only: dish role is unclear")

    non_meal = sorted(tags & NON_MEAL_TAGS)
    if non_meal:
        evidence.append(f"non-meal course: {', '.join(non_meal)}")

    if not roles:
        if non_meal:  # confidently a dessert, drink, sauce...: not a planning dish
            return Classification(
                roles=(),
                dish_class=None,
                meal_types=(),
                status=ClassificationStatus.AUTO,
                evidence=tuple(evidence),
            )
        evidence.append("no usable course evidence")
        return Classification(
            roles=(),
            dish_class=None,
            meal_types=(),
            status=ClassificationStatus.REQUIRES_REVIEW,
            evidence=tuple(evidence),
        )

    dish_class = _dish_class(roles, tags, name)
    evidence.append(f"dish class {dish_class.value}")
    review = weak or bool(non_meal)  # a role next to a non-meal course is a conflict
    if dish_class is not DishClass.COMPONENT and energy_kcal < MIN_MEAL_KCAL:
        review = True
        evidence.append(f"meal dish below {MIN_MEAL_KCAL:g} kcal per serving")
    if dish_class is DishClass.COMPONENT and energy_kcal > MAX_COMPONENT_KCAL:
        review = True
        evidence.append(f"side above {MAX_COMPONENT_KCAL:g} kcal per serving: batch-sized?")
    if roles & _MEAL_ROLES and non_meal:
        evidence.append("conflict: meal course and non-meal course")
    ordered_roles = _ordered(roles, CulinaryRole)
    return Classification(
        roles=ordered_roles,
        dish_class=dish_class,
        meal_types=meals_for_roles(ordered_roles),
        status=ClassificationStatus.REQUIRES_REVIEW if review else ClassificationStatus.AUTO,
        evidence=tuple(evidence),
    )


def is_plannable(recipe: CatalogueRecipe) -> bool:
    """Only settled (AUTO or CURATED) dishes with a role may enter a plan."""
    return bool(recipe.roles) and recipe.classification_status in (
        ClassificationStatus.AUTO,
        ClassificationStatus.CURATED,
    )


def apply_override(recipe: CatalogueRecipe, override: ClassificationOverride) -> CatalogueRecipe:
    """Curated values win over tag evidence; the auto evidence is kept for audit."""
    if override.recipe_id != recipe.recipe_id:
        raise ValueError("override applied to the wrong recipe")
    update: dict[str, object] = {}
    note = f"curated by {override.curated_by}: {override.rationale}"
    if override.cuisines is not None:
        update["cuisines"] = override.cuisines
    if override.roles is not None and override.meal_types is not None:
        update["roles"] = _ordered(override.roles, CulinaryRole)
        update["dish_class"] = override.dish_class
        update["meal_types"] = _ordered(override.meal_types, MealType)
        update["classification_status"] = ClassificationStatus.CURATED
    update["classification_evidence"] = (*recipe.classification_evidence, note)
    return CatalogueRecipe.model_validate({**recipe.model_dump(), **update})


def index_overrides(
    overrides: Iterable[ClassificationOverride],
) -> Mapping[str, ClassificationOverride]:
    by_id: dict[str, ClassificationOverride] = {}
    for override in overrides:
        if override.recipe_id in by_id:
            raise ValueError(f"duplicate override for {override.recipe_id}")
        by_id[override.recipe_id] = override
    return by_id
