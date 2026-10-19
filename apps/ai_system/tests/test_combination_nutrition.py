"""Stage 9: combination nutrition sums, weakest source tier, completeness and sanity."""

from pathlib import Path

import pytest

from savora_ai.core.food_data.catalogue import build_recipe
from savora_ai.core.food_data.models import CatalogueRecipe, NutrientVector
from savora_ai.core.food_data.nutrition_convert import FDA_1993
from savora_ai.core.food_data.portions import serving_portions, with_portions
from savora_ai.core.food_data.usda_staples import load_extract, load_spec, staple_dishes
from savora_ai.core.meal_composition.composer import compose
from savora_ai.core.meal_composition.models import MealCombination
from savora_ai.core.meal_composition.nutrition import (
    check_configuration,
    sum_nutrients,
    validate_combinations,
    weakest_source,
)
from savora_ai.core.meal_composition.pairings import load_pairings
from savora_ai.core.meal_composition.templates import load_templates
from savora_ai.schemas.enums import NutritionSource, PortionPreset

REPO = Path(__file__).parents[3]
STAPLES = staple_dishes(
    load_spec(REPO / "Data/curated/usda_staples.json"),
    load_extract(REPO / "Data/curated/usda_staples_extract.json"),
)
RICE = next(s for s in STAPLES if s.name == "steamed white rice")


def dish(source_id: int, name: str, kcal: float, *tags: str) -> CatalogueRecipe:
    # %DV scaled so Atwater energy matches: 20% fat, carbs, protein = 13, 60, 10 g = 397 kcal.
    scale = kcal / 397.0
    nutrition = [kcal, 20 * scale, 0, 10, 20 * scale, 10, 20 * scale]
    recipe = build_recipe(source_id, name, list(tags), nutrition, ["x"], FDA_1993)
    assert isinstance(recipe, CatalogueRecipe)
    return with_portions(recipe, serving_portions(recipe))


DAL = dish(1, "yellow dal", 400.0, "main-dish", "indian")


def meals(*dishes: CatalogueRecipe) -> tuple[MealCombination, ...]:
    return compose(
        (*dishes, *STAPLES), load_templates(REPO / "Data/curated/meal_templates.json"),
        load_pairings(REPO / "Data/curated/pairings.json"), "s",
    ).combinations  # fmt: skip


def dal_rice() -> MealCombination:
    """Dal with whichever staple the seed pairs first."""
    return next(c for c in meals(DAL) if c.template_id == "MAIN_STAPLE")


def test_sum_is_per_nutrient_and_unknown_propagates() -> None:
    dal = NutrientVector(energy_kcal=350.0, sugars_g=None)
    rice = NutrientVector(energy_kcal=195.0, sugars_g=1.0)
    total = sum_nutrients([dal, rice])
    assert total.energy_kcal == 545.0  # the ADR 0003 dal + rice example
    assert total.sugars_g is None  # one unknown component -> unknown, never 1.0


def test_weakest_source_wins() -> None:
    tiers = [NutritionSource.USDA_SR_LEGACY, NutritionSource.FOODCOM_DERIVED]
    assert weakest_source(tiers) is NutritionSource.FOODCOM_DERIVED
    assert weakest_source([NutritionSource.USDA_FOUNDATION, NutritionSource.USDA_FNDDS]) is (
        NutritionSource.USDA_FNDDS
    )


def test_validated_meal_carries_totals_tier_and_completeness() -> None:
    combo = dal_rice()
    result = validate_combinations([combo], (DAL, *STAPLES))
    [kept] = result.combinations
    standard = next(c for c in kept.configurations if c.preset is PortionPreset.STANDARD)
    assert standard.nutrition is not None
    dal_kcal = 400.0
    staple = next(s for s in STAPLES if s.recipe_id == combo.components[1].dish_id)
    staple_kcal = next(p for p in staple.portions if p.is_standard).nutrients.energy_kcal
    assert staple_kcal is not None
    assert standard.nutrition.totals.energy_kcal == pytest.approx(dal_kcal + staple_kcal)
    assert standard.nutrition.source_tier is NutritionSource.FOODCOM_DERIVED  # not "verified"
    assert standard.nutrition.fully_known  # sugar is not a required nutrient
    assert standard.nutrition.totals.sugars_g is None


def test_implausible_meal_energy_drops_the_configuration_only() -> None:
    heavy = dish(2, "huge curry", 1450.0, "main-dish", "indian")  # 1.5 servings > 2000 kcal
    [combo] = [c for c in meals(heavy) if c.template_id == "MAIN_STAPLE"][:1]
    result = validate_combinations([combo], (heavy, *STAPLES))
    [kept] = result.combinations
    assert len(kept.configurations) < len(combo.configurations)
    problems = result.report["problems"]
    assert isinstance(problems, dict) and problems.get("ENERGY_OUT_OF_RANGE", 0) >= 1
    assert sum(problems.values()) == result.report["configurationsDropped"]  # all explained


def test_a_meal_with_no_valid_configuration_is_rejected_with_reasons() -> None:
    light = dish(3, "thin broth meal", 60.0, "main-dish", "one-dish-meal", "indian")
    [combo] = [c for c in meals(light) if c.template_id == "ONE_DISH"]
    result = validate_combinations([combo], (light, *STAPLES))
    assert result.combinations == ()
    [rejected] = result.rejected
    assert rejected["combinationId"] == combo.combination_id
    assert all("ENERGY_OUT_OF_RANGE" in p for p in rejected["problems"])  # type: ignore[union-attr]


def test_unknown_energy_and_unknown_portions_are_rejected() -> None:
    combo = dal_rice()
    no_energy = DAL.model_copy(
        update={"nutrition": DAL.nutrition.model_copy(update={"values": NutrientVector()})}
    )
    checked = check_configuration(
        combo.configurations[0], {DAL.recipe_id: no_energy, **{s.recipe_id: s for s in STAPLES}}
    )
    assert checked.configuration is None
    assert {p.code for p in checked.problems} == {"ENERGY_UNKNOWN"}
    result = validate_combinations([combo], STAPLES)  # the dal is missing from the catalogue
    assert result.rejected[0]["problems"] == [f"UNKNOWN_DISH: {['FC_1']}"]


def test_recomputed_energy_must_agree_with_the_portion_vectors() -> None:
    combo = dal_rice()
    tampered = [
        p.model_copy(update={"nutrients": p.nutrients.model_copy(update={"energy_kcal": 1.0})})
        for p in DAL.portions
    ]
    bad_dal = DAL.model_copy(update={"portions": tuple(tampered)})
    checked = check_configuration(
        combo.configurations[0], {DAL.recipe_id: bad_dal, **{s.recipe_id: s for s in STAPLES}}
    )
    assert any(p.code == "ENERGY_DISAGREES" for p in checked.problems)


# --- preset intent ------------------------------------------------------------------


def _with_totals(config, **totals: float | None):
    assert config.nutrition is not None
    vector = config.nutrition.totals.model_copy(update=totals)
    return config.model_copy(
        update={"nutrition": config.nutrition.model_copy(update={"totals": vector})}
    )


def test_a_preset_must_do_what_its_name_says() -> None:
    from savora_ai.core.meal_composition.nutrition import intent_problem

    [combo] = validate_combinations([dal_rice()], (DAL, *STAPLES)).combinations
    configs = {c.preset: c for c in combo.configurations}
    standard = _with_totals(configs[PortionPreset.STANDARD], carbohydrate_g=100.0, protein_g=20.0)
    lower = configs[PortionPreset.LOWER_CARB]
    assert intent_problem(_with_totals(lower, carbohydrate_g=90.0), standard) is None
    failed = intent_problem(_with_totals(lower, carbohydrate_g=110.0), standard)
    assert failed is not None and failed.code == "PRESET_INTENT_NOT_MET"
    protein = configs[PortionPreset.HIGHER_PROTEIN]
    unknown = intent_problem(_with_totals(protein, protein_g=None), standard)
    assert unknown is not None and unknown.code == "PRESET_INTENT_UNVERIFIED"
    no_base = intent_problem(protein, None)
    assert no_base is not None and no_base.code == "PRESET_INTENT_UNVERIFIED"
    assert intent_problem(standard, None) is None  # STANDARD is the reference itself


def test_every_kept_preset_beats_standard_on_its_own_nutrient() -> None:
    from savora_ai.core.meal_composition.nutrition import PRESET_INTENT

    [combo] = validate_combinations([dal_rice()], (DAL, *STAPLES)).combinations
    configs = {c.preset: c for c in combo.configurations}
    base = configs[PortionPreset.STANDARD].nutrition
    assert base is not None
    for preset, config in configs.items():
        if preset is PortionPreset.STANDARD:
            continue
        nutrient, direction = PRESET_INTENT[preset]
        assert config.nutrition is not None
        diff = getattr(config.nutrition.totals, nutrient) - getattr(base.totals, nutrient)
        assert diff * direction > 0
