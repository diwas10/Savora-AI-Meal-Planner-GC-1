"""Stage 7: stratified selection is reproducible, balanced and honest about gaps."""

from savora_ai.core.food_data.catalogue import build_recipe
from savora_ai.core.food_data.classification import ClassificationOverride, apply_override
from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.food_data.nutrition_convert import FDA_1993
from savora_ai.core.food_data.selection import (
    SLOT_KINDS,
    normalized_name,
    select_stratified,
)
from savora_ai.schemas.enums import CulinaryRole, DishClass, MealType

MAIN_ONLY = tuple(k for k in SLOT_KINDS if k.name == "MAIN_WITH_ACCOMPANIMENT")


def dish(
    source_id: int, *tags: str, name: str | None = None, vegetarian: bool = False
) -> CatalogueRecipe:
    all_tags = [*tags, *(["vegetarian"] if vegetarian else [])]
    result = build_recipe(
        source_id,
        name or f"curry {source_id:04d}x",
        all_tags,
        [400.0, 20, 10, 10, 20, 10, 20],
        ["x"],
        FDA_1993,
    )
    assert isinstance(result, CatalogueRecipe)
    return result


def letters(i: int) -> str:
    """A distinct name without digits (digits are ignored by near-duplicate matching)."""
    return f"curry {chr(97 + i // 26)}{chr(97 + i % 26)}"


def indian_mains(n: int, *, vegetarian_from: int = 10**9) -> list[CatalogueRecipe]:
    return [
        dish(
            i,
            "main-dish",
            "indian",
            name=letters(i),
            vegetarian=i >= vegetarian_from,
        )
        for i in range(1, n + 1)
    ]


def ids(recipes: tuple[CatalogueRecipe, ...]) -> set[str]:
    return {r.recipe_id for r in recipes}


def test_selection_is_deterministic_order_independent_and_seed_sensitive() -> None:
    pool = indian_mains(40)
    a = select_stratified(pool, {}, "seed-a", cuisines=("Indian",), slot_kinds=MAIN_ONLY)
    b = select_stratified(
        list(reversed(pool)), {}, "seed-a", cuisines=("Indian",), slot_kinds=MAIN_ONLY
    )
    c = select_stratified(pool, {}, "seed-b", cuisines=("Indian",), slot_kinds=MAIN_ONLY)
    assert a == b
    assert ids(a.recipes) != ids(c.recipes)
    assert len(a.recipes) == 8  # the quota


def test_half_of_a_stratum_is_vegetarian_when_the_data_allows() -> None:
    pool = indian_mains(40, vegetarian_from=37)  # only 4 vegetarian dishes, ids 37-40
    popularity = {f"FC_{i}": 100 for i in range(1, 37)}  # the meat dishes are popular
    result = select_stratified(pool, popularity, "s", cuisines=("Indian",), slot_kinds=MAIN_ONLY)
    assert {f"FC_{i}" for i in range(37, 41)} <= ids(result.recipes)
    assert result.strata[0].vegetarian_selected == 4


def test_popularity_orders_within_a_stratum() -> None:
    pool = indian_mains(20)
    popular = {f"FC_{i}": 50 for i in range(13, 21)}
    result = select_stratified(pool, popular, "s", cuisines=("Indian",), slot_kinds=MAIN_ONLY)
    assert ids(result.recipes) == set(popular)


def test_curated_dishes_come_before_popular_ones() -> None:
    pool = indian_mains(20)
    override = ClassificationOverride(
        recipe_id="FC_1",
        roles=(CulinaryRole.MAIN_DISH,),
        dish_class=DishClass.REQUIRES_ACCOMPANIMENT,
        meal_types=(MealType.LUNCH, MealType.DINNER),
        rationale="reviewed",
        curated_by="tester",
    )
    pool[0] = apply_override(pool[0], override)
    popular = {f"FC_{i}": 50 for i in range(2, 21)}
    result = select_stratified(pool, popular, "s", cuisines=("Indian",), slot_kinds=MAIN_ONLY)
    assert "FC_1" in ids(result.recipes)


def test_near_duplicate_names_are_skipped() -> None:
    pool = [
        dish(1, "main-dish", "indian", name="Chicken Tikka Masala!"),
        dish(2, "main-dish", "indian", name="chicken  tikka masala"),
        dish(3, "main-dish", "indian", name="palak paneer"),
    ]
    result = select_stratified(pool, {}, "s", cuisines=("Indian",), slot_kinds=MAIN_ONLY)
    assert len(result.recipes) == 2
    assert normalized_name("Chicken Tikka Masala!") == "chicken tikka masala"


def test_a_short_stratum_is_reported_not_padded_with_other_cuisines() -> None:
    pool = [*indian_mains(3), dish(100, "main-dish", "thai", name="thai curry")]
    result = select_stratified(pool, {}, "s", cuisines=("Indian",), slot_kinds=MAIN_ONLY)
    assert "FC_100" not in ids(result.recipes)
    report = result.strata[0].as_json()
    assert report["selected"] == 3 and report["shortfall"] == 5


def test_unsettled_dishes_are_never_selected() -> None:
    review = dish(1, "main-dish", "appetizers", "indian")  # conflict: REQUIRES_REVIEW
    result = select_stratified([review], {}, "s", cuisines=("Indian",), slot_kinds=MAIN_ONLY)
    assert result.recipes == ()


def test_a_dish_in_two_strata_is_selected_once_and_counts_in_both() -> None:
    both = dish(1, "main-dish", "indian", name="dal")  # Food.com has no Nepali tag
    nepali = apply_override(
        both,
        ClassificationOverride(
            recipe_id="FC_1", cuisines=("Indian", "Nepali"), rationale="r", curated_by="c"
        ),
    )
    result = select_stratified(
        [nepali], {}, "s", cuisines=("Nepali", "Indian"), slot_kinds=MAIN_ONLY
    )
    assert len(result.recipes) == 1
    assert [s.selected for s in result.strata] == [1, 1]
