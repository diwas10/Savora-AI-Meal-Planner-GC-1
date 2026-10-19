"""XAI aggregation: explanations are complete, deterministic and honestly worded."""

import json
from pathlib import Path

import pytest

from savora_ai.core.explainability.explanation import (
    PlanningOutcome,
    Reason,
    ReasonKind,
    RuleOutcome,
    explain_craving_recipe,
    explain_meal,
)
from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.food_data.usda_staples import load_extract, load_spec, staple_dishes
from savora_ai.core.meal_composition.api import generate_meal_combinations
from savora_ai.core.meal_composition.models import MealCombination
from savora_ai.core.meal_composition.pairings import load_pairings
from savora_ai.core.meal_composition.templates import load_templates
from savora_ai.core.recommendation.ranking import (
    PopularityScorer,
    RankingContext,
    rank_combinations,
    rank_recipes,
)
from savora_ai.schemas.enums import PortionPreset

REPO = Path(__file__).parents[3]
EXPORT = REPO / "Data/catalogue"


def export() -> tuple[dict[str, CatalogueRecipe], list[MealCombination]]:
    path = sorted(EXPORT.glob("*_catalogue.json"))[-1]
    version = path.name.removesuffix("_catalogue.json")
    recipes = json.loads(path.read_text(encoding="utf-8"))["recipes"]
    combos = json.loads((EXPORT / f"{version}_combinations.json").read_text("utf-8"))
    dishes = {r["recipeId"]: CatalogueRecipe.model_validate_json(json.dumps(r)) for r in recipes}
    meals = [MealCombination.model_validate_json(json.dumps(c)) for c in combos["combinations"]]
    return dishes, meals


DISHES, MEALS = export()
DAL_RICE = next(m for m in MEALS if m.template_id == "MAIN_STAPLE_VEGETABLE")


def codes(reasons: tuple[Reason, ...]) -> set[str]:
    return {r.code for r in reasons}


def test_meal_explanation_covers_every_stage_with_stable_codes() -> None:
    config = next(c for c in DAL_RICE.configurations if c.preset is PortionPreset.HIGHER_PROTEIN)
    ranking = rank_combinations(
        [],
        [m.combination_id for m in MEALS[:20]],
        RankingContext(slot_id="D1_LUNCH"),
        scorer=None,
        fallback=PopularityScorer({}),
    )
    explanation = explain_meal(
        DAL_RICE,
        config,
        DISHES,
        slot_id="D1_LUNCH",
        ranking=ranking,
        rules=RuleOutcome(status="PASS", checked_rules=("r1", "r2"), trace_id="T1"),
        planning=PlanningOutcome(
            outcome="FEASIBLE",
            slot_id="D1_LUNCH",
            search_nodes=6,
            constraints=("day sodium <= 1500 mg",),
        ),
    )
    got = codes(explanation.reasons)
    assert {
        "TEMPLATE_MAIN_STAPLE_VEGETABLE",
        "PRESET_HIGHER_PROTEIN",
        "NUTRITION_TOTALS",
        "RANKING_FALLBACK_MODEL_UNAVAILABLE",
        "RULES_PASS",
        "PLANNING_FEASIBLE",
        "NUTRITION_DERIVED_FROM_PERCENT_DV",
    } <= got
    assert {r.kind for r in explanation.reasons} == set(ReasonKind)  # all seven stages
    assert [d.dish_id for d in explanation.dishes] == [c.dish_id for c in DAL_RICE.components]
    assert explanation.totals == config.nutrition.totals  # type: ignore[union-attr]
    assert explanation == explain_meal(  # deterministic
        DAL_RICE,
        config,
        DISHES,
        slot_id="D1_LUNCH",
        ranking=ranking,
        rules=RuleOutcome(status="PASS", checked_rules=("r1", "r2"), trace_id="T1"),
        planning=PlanningOutcome(
            outcome="FEASIBLE",
            slot_id="D1_LUNCH",
            search_nodes=6,
            constraints=("day sodium <= 1500 mg",),
        ),
    )


def test_wording_never_claims_safety_and_unknown_rules_are_not_passes() -> None:
    config = DAL_RICE.configurations[0]
    outcome = RuleOutcome(status="PASS", checked_rules=("r",))
    passed = explain_meal(DAL_RICE, config, DISHES, rules=outcome)
    text = " ".join(r.message for r in passed.reasons).lower()
    assert "safe" not in text and "not a medical guarantee" in text
    unknown = explain_meal(
        DAL_RICE,
        config,
        DISHES,
        rules=RuleOutcome(status="UNKNOWN", checked_rules=("r",), unknown_rules=("r",)),
    )
    [rule] = [r for r in unknown.reasons if r.kind is ReasonKind.RULES]
    assert rule.code == "RULES_UNKNOWN" and "not treated as passing" in rule.message


def test_failed_rules_are_named() -> None:
    outcome = RuleOutcome(status="FAIL", checked_rules=("a", "b"), failed_rules=("b",))
    explanation = explain_meal(DAL_RICE, DAL_RICE.configurations[0], DISHES, rules=outcome)
    [rule] = [r for r in explanation.reasons if r.kind is ReasonKind.RULES]
    assert rule.code == "RULES_FAIL" and "b" in rule.message


def test_a_configuration_from_another_meal_is_rejected() -> None:
    other = next(m for m in MEALS if m.combination_id != DAL_RICE.combination_id)
    with pytest.raises(ValueError):
        explain_meal(DAL_RICE, other.configurations[0], DISHES)


def test_craving_explanation_says_it_was_not_budget_checked() -> None:
    dish = DISHES[DAL_RICE.components[0].dish_id]
    ranking = rank_recipes(
        [], [dish.recipe_id], RankingContext(), scorer=None, fallback=PopularityScorer({})
    )
    explanation = explain_craving_recipe(dish, ranking=ranking)
    got = codes(explanation.reasons)
    assert {"CRAVING_STANDARD_PORTION_ONLY", "RANKING_FALLBACK_MODEL_UNAVAILABLE"} <= got
    [nutrition] = [r for r in explanation.reasons if r.code == "CRAVING_STANDARD_PORTION_ONLY"]
    assert "not checked against what is left of today's targets" in nutrition.message
    # Food.com sugar is unknown: named as unknown, never zero.
    [unknown] = [r for r in explanation.reasons if r.code == "NUTRIENTS_UNKNOWN"]
    assert "sugars" in unknown.message and explanation.standard_nutrients.sugars_g is None


def test_generate_meal_combinations_matches_the_committed_export() -> None:
    staples = staple_dishes(
        load_spec(REPO / "Data/curated/usda_staples.json"),
        load_extract(REPO / "Data/curated/usda_staples_extract.json"),
    )
    foodcom = [d for d in DISHES.values() if d.recipe_id.startswith("FC_")]
    result = generate_meal_combinations(
        (*foodcom, *staples),
        load_templates(REPO / "Data/curated/meal_templates.json"),
        load_pairings(REPO / "Data/curated/pairings.json"),
        "savora-catalogue-v0",
    )
    assert [m.combination_id for m in result.combinations] == [m.combination_id for m in MEALS]
    assert result.validation_report["combinationsKept"] == len(MEALS)


# --- review regressions -------------------------------------------------------------


@pytest.mark.parametrize("outcome", ["INFEASIBLE", "TIMEOUT", "INSUFFICIENT_DATA"])
def test_only_a_feasible_plan_claims_the_constraints_were_met(outcome: str) -> None:
    planning = PlanningOutcome(
        outcome=outcome,  # type: ignore[arg-type]
        slot_id="D2_LUNCH",
        search_nodes=9,
        constraints=("day sodium <= 1500 mg",),
    )
    explanation = explain_meal(DAL_RICE, DAL_RICE.configurations[0], DISHES, planning=planning)
    [reason] = [r for r in explanation.reasons if r.kind is ReasonKind.PLANNING]
    assert "kept the day within" not in reason.message
    assert "not a confirmed fit" in reason.message


def test_pure_model_ranking_does_not_claim_a_popularity_blend() -> None:
    from savora_ai.core.explainability.explanation import _ranking_reason

    pure = _ranking_reason("sasrec-content-v2", None, 1, 3)
    hybrid = _ranking_reason("sasrec-content-v2+pop4", None, 1, 3)
    assert "popularity" not in pure.message and "blended with popularity" in hybrid.message


def test_filtered_pool_missing_a_paired_staple_still_composes() -> None:
    # Review: the Rule Engine may remove a staple (e.g. naan); that drops its meals only.
    staples = staple_dishes(
        load_spec(REPO / "Data/curated/usda_staples.json"),
        load_extract(REPO / "Data/curated/usda_staples_extract.json"),
    )
    pairings = load_pairings(REPO / "Data/curated/pairings.json")
    paired = {s for p in pairings.cuisines for s in p.staples}
    removed = sorted(paired)[0]
    pool = (
        *[d for d in DISHES.values() if d.recipe_id.startswith("FC_")],
        *[s for s in staples if s.recipe_id != removed],
    )
    templates = load_templates(REPO / "Data/curated/meal_templates.json")
    with pytest.raises(ValueError, match="unknown dish"):
        generate_meal_combinations(pool, templates, pairings, "seed")  # strict by default
    result = generate_meal_combinations(pool, templates, pairings, "seed", check_pairings=False)
    assert result.combinations
    assert all(removed not in m.combination_id for m in result.combinations)
