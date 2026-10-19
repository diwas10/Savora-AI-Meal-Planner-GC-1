"""Stage 8: templates, curated pairings, presets and bounded deterministic composition."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from savora_ai.core.food_data.catalogue import build_recipe
from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.food_data.nutrition_convert import FDA_1993
from savora_ai.core.food_data.portions import serving_portions, with_portions
from savora_ai.core.food_data.usda_staples import load_extract, load_spec, staple_dishes
from savora_ai.core.meal_composition.composer import CompositionLimits, compose, overlaps
from savora_ai.core.meal_composition.models import MealCombination
from savora_ai.core.meal_composition.pairings import load_pairings
from savora_ai.core.meal_composition.presets import step_portion
from savora_ai.core.meal_composition.templates import TemplateFile, load_templates
from savora_ai.schemas.enums import MealType, PortionPreset

REPO = Path(__file__).parents[3]
TEMPLATES = load_templates(REPO / "Data/curated/meal_templates.json")
PAIRINGS = load_pairings(REPO / "Data/curated/pairings.json")
STAPLES = staple_dishes(
    load_spec(REPO / "Data/curated/usda_staples.json"),
    load_extract(REPO / "Data/curated/usda_staples_extract.json"),
)
RICE, ROTI, NAAN, BROWN_RICE = "USDA_169757", "USDA_2707713", "USDA_2707613", "USDA_169704"
INDIAN_STAPLES = {RICE, ROTI, NAAN, BROWN_RICE}


def dish(
    source_id: int, name: str, *tags: str, ingredients: tuple[str, ...] = ("x",)
) -> CatalogueRecipe:
    recipe = build_recipe(
        source_id, name, list(tags), [400.0, 20, 10, 10, 20, 10, 20], list(ingredients), FDA_1993
    )
    assert isinstance(recipe, CatalogueRecipe)
    return with_portions(recipe, serving_portions(recipe))


DAL = dish(1, "yellow dal", "main-dish", "indian")
BIRYANI = dish(2, "veg biryani", "main-dish", "indian")
INDIAN_SIDE = dish(3, "aloo gobi", "side-dishes", "vegetables", "indian")
THAI_SIDE = dish(4, "thai cucumber salad", "salads", "thai")
OMELETTE = dish(5, "masala omelette", "breakfast", "indian", ingredients=("eggs", "onion"))
CATALOGUE = (DAL, BIRYANI, INDIAN_SIDE, THAI_SIDE, OMELETTE, *STAPLES)


def by_template(combos: tuple[MealCombination, ...], template_id: str) -> list[MealCombination]:
    return [c for c in combos if c.template_id == template_id]


def run(**limits: int) -> tuple[MealCombination, ...]:
    return compose(CATALOGUE, TEMPLATES, PAIRINGS, "s", CompositionLimits(**limits)).combinations


def test_complete_dish_stands_alone_and_a_dal_never_does() -> None:
    one_dish = by_template(run(), "ONE_DISH")
    assert [c.components[0].dish_id for c in one_dish] == ["FC_2"]  # biryani, not dal


def test_main_is_paired_only_with_its_cuisines_staples() -> None:
    pairs = by_template(run(staples_per_main=10), "MAIN_STAPLE")
    assert {c.components[1].dish_id for c in pairs} == INDIAN_STAPLES
    assert all(c.combination_id.startswith("C_MAIN_STAPLE__FC_1__") for c in pairs)


def test_staples_per_main_bounds_the_pairs_and_the_seed_picks_them() -> None:
    assert len(by_template(run(staples_per_main=2), "MAIN_STAPLE")) == 2
    chosen = {
        seed: {
            c.components[1].dish_id
            for c in compose(CATALOGUE, TEMPLATES, PAIRINGS, seed).combinations
            if c.template_id == "MAIN_STAPLE"
        }
        for seed in ("a", "b", "c", "d")
    }
    assert len({frozenset(v) for v in chosen.values()}) > 1  # seed-dependent, yet bounded


def test_vegetable_side_is_same_cuisine_first_and_never_another_cuisine() -> None:
    triples = by_template(
        run(staples_per_main=10, vegetables_per_main_staple=1), "MAIN_STAPLE_VEGETABLE"
    )
    assert {c.components[2].dish_id for c in triples} == {"FC_3"}  # aloo gobi, not Thai salad
    more = by_template(run(vegetables_per_main_staple=20), "MAIN_STAPLE_VEGETABLE")
    sides = {c.components[2].dish_id for c in more}
    assert "FC_4" not in sides and {"FC_3", "USDA_169967"} <= sides  # broccoli is neutral


def test_breakfast_add_on_already_in_the_base_is_skipped() -> None:
    assert overlaps(OMELETTE, next(s for s in STAPLES if s.name == "boiled egg"))
    assert by_template(run(), "BREAKFAST_PROTEIN") == []  # no boiled egg with an omelette
    fruit = by_template(run(add_ons_per_base=10), "BREAKFAST_FRUIT")
    assert len(fruit) == 6 and all(c.meal_types == (MealType.BREAKFAST,) for c in fruit)


def test_composition_is_deterministic_and_input_order_independent() -> None:
    a = compose(CATALOGUE, TEMPLATES, PAIRINGS, "s")
    b = compose(tuple(reversed(CATALOGUE)), TEMPLATES, PAIRINGS, "s")
    assert a == b


def test_exceeding_the_safety_bound_is_an_error_not_a_silent_cut() -> None:
    with pytest.raises(ValueError, match="exceed the bound"):
        run(max_per_meal_type=1)


def test_dishes_without_portions_are_not_composed() -> None:
    bare = build_recipe(
        9, "dal two", ["main-dish", "indian"], [400.0, 20, 10, 10, 20, 10, 20], ["x"], FDA_1993
    )
    assert isinstance(bare, CatalogueRecipe)
    combos = compose((bare, *STAPLES), TEMPLATES, PAIRINGS, "s").combinations
    assert all("FC_9" not in c.combination_id for c in combos)


# --- presets ------------------------------------------------------------------------


def test_presets_move_each_component_along_its_own_options() -> None:
    [pair] = by_template(run(staples_per_main=10), "MAIN_STAPLE")[:1]
    configs = {c.preset: c for c in pair.configurations}
    standard = configs[PortionPreset.STANDARD].portions
    protein = configs[PortionPreset.HIGHER_PROTEIN].portions
    assert standard[0].quantity == 1.0 and protein[0].quantity == 1.5  # main +2 steps
    staple = next(s for s in STAPLES if s.recipe_id == pair.components[1].dish_id)
    assert protein[1].quantity < standard[1].quantity or protein[1].quantity == min(
        p.quantity for p in staple.portions
    )
    assert all(
        c.configuration_id == f"{pair.combination_id}#{c.preset}" for c in pair.configurations
    )


def test_identical_presets_are_merged_and_standard_always_survives() -> None:
    for combo in run():
        presets = [c.preset for c in combo.configurations]
        assert presets[0] is PortionPreset.STANDARD
        keys = [tuple(p.portion_id for p in c.portions) for c in combo.configurations]
        assert len(keys) == len(set(keys))


def test_steps_clamp_to_the_ends() -> None:
    assert step_portion(DAL, -9).quantity == 0.5
    assert step_portion(DAL, 9).quantity == 1.5


# --- contracts and data -------------------------------------------------------------


def test_combination_contract_rejects_bad_ids_and_repeated_dishes() -> None:
    combo = by_template(run(), "ONE_DISH")[0]
    data = combo.model_dump()
    with pytest.raises(ValidationError):
        MealCombination.model_validate(data | {"combination_id": "C_X"})
    repeated = data | {"components": (*data["components"], data["components"][0])}
    with pytest.raises(ValidationError):
        MealCombination.model_validate(repeated)


def test_templates_allow_at_most_three_distinct_roles() -> None:
    raw = json.loads((REPO / "Data/curated/meal_templates.json").read_text("utf-8"))
    triple = next(t for t in raw["templates"] if t["templateId"] == "MAIN_STAPLE_VEGETABLE")
    four = triple | {"slots": [*triple["slots"], triple["slots"][0] | {"slot": "EXTRA"}]}
    with pytest.raises(ValidationError):
        TemplateFile.model_validate_json(json.dumps(raw | {"templates": [four]}))
    repeated_role = triple | {"slots": [triple["slots"][0], triple["slots"][0] | {"slot": "X"}]}
    with pytest.raises(ValidationError):
        TemplateFile.model_validate_json(json.dumps(raw | {"templates": [repeated_role]}))


# --- review regressions -------------------------------------------------------------


def test_overlap_uses_whole_words() -> None:
    def base(*ingredients: str) -> CatalogueRecipe:
        return dish(30, "breakfast thing", "breakfast", "indian", ingredients=ingredients)

    apple = next(s for s in STAPLES if s.name == "apple")
    egg = next(s for s in STAPLES if s.name == "boiled egg")
    assert not overlaps(base("pineapple"), apple)  # apple is not in pineapple
    assert not overlaps(base("eggplant"), egg)  # egg is not in eggplant
    assert overlaps(base("eggs", "onion"), egg)  # plural still matches


def test_pairing_without_a_common_meal_is_skipped_not_a_crash() -> None:
    lunch_only = DAL.model_copy(update={"meal_types": (MealType.LUNCH,)})
    rice = next(s for s in STAPLES if s.recipe_id == RICE)
    dinner_rice = rice.model_copy(update={"meal_types": (MealType.DINNER,)})
    others = tuple(s for s in STAPLES if s.recipe_id != RICE)
    result = compose((lunch_only, dinner_rice, *others), TEMPLATES, PAIRINGS, "s",
                     CompositionLimits(staples_per_main=10))  # fmt: skip
    assert all(RICE not in c.combination_id or c.meal_types for c in result.combinations)
    skipped = result.report["skippedNoCommonMealType"]
    assert isinstance(skipped, int) and skipped >= 1


@pytest.mark.parametrize(
    "slots",
    [
        # a supported role set in an unsupported order
        [("MAIN", "MAIN_DISH"), ("VEGETABLE", "VEGETABLE"), ("STAPLE", "STAPLE")],
        # a slot name with no portion-preset rule
        [("MAIN", "MAIN_DISH"), ("SIDE", "STAPLE")],
    ],
)
def test_unsupported_template_shapes_fail_at_load(slots: list[tuple[str, str]]) -> None:
    raw = json.loads((REPO / "Data/curated/meal_templates.json").read_text("utf-8"))
    template = raw["templates"][1] | {
        "slots": [
            {"slot": name, "role": role, "dishClasses": ["REQUIRES_ACCOMPANIMENT", "COMPONENT"]}
            for name, role in slots
        ]
    }
    with pytest.raises(ValidationError):
        TemplateFile.model_validate_json(json.dumps(raw | {"templates": [template]}))
