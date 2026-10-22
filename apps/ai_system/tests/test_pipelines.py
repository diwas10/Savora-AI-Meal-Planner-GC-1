"""Integration pipelines on the REAL catalogue export with the GC1 stand-in KB.

The weekly tests run Member 2's full weekly CSP (about two minutes each), so one plan and
one substitution are shared through module fixtures.
"""

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from savora_ai.core.meal_composition.composer import _tokens
from savora_ai.core.pipelines import (
    CravingStatus,
    PlanningProfile,
    PlanStatus,
    WeekPlan,
    confirm_seeds,
    load_catalogue_export,
    plan_week,
    recommend_for_craving,
    revalidate_seeds,
    substitute_slot,
    suggest_replacements,
    suggest_seeds,
)
from savora_ai.core.pipelines.catalogue import CatalogueBundle
from savora_ai.core.pipelines.craving import retrieve_for_craving
from savora_ai.core.pipelines.profile import dish_allowed
from savora_ai.core.pipelines.rules import check_recipes
from savora_ai.core.recommendation.ranking import RankingContext, rank_recipes
from savora_ai.core.recommendation.seeds import is_seed_eligible
from savora_ai.schemas.craving import CravingRequest
from savora_ai.schemas.knowledge_base import KnowledgeWorkflow

EXPORT = Path(__file__).parents[3] / "Data/catalogue"
SECTION_9_1 = (
    '{"intent":"CRAVING_RECOMMEND","cuisineIds":["CHINESE"],"flavorTags":["SPICY"],'
    '"excludedIngredientIds":["NOODLES"],"mealSlotId":null,"requiresClarification":false}'
)
START = date(2026, 10, 26)


@pytest.fixture(scope="module")
def bundle() -> CatalogueBundle:
    return load_catalogue_export(EXPORT)


def profile(**fields: object) -> PlanningProfile:
    return PlanningProfile.model_validate_json(
        json.dumps({"profileId": "user-1", "profileVersion": 1} | fields)
    )


def craving(**fields: object) -> CravingRequest:
    return CravingRequest.model_validate_json(json.dumps({"intent": "CRAVING_RECOMMEND"} | fields))


class FakeScorer:
    """Deterministic stand-in for the Transformer: prefers longer recipe IDs."""

    model_version = "fake-sequence-v1"

    def knows(self, recipe_id: str) -> bool:
        return recipe_id.startswith("FC_")

    def score(self, history: Sequence[str], candidates: Sequence[str]) -> Mapping[str, float]:
        return {c: float(len(c)) + int(c[-1]) / 10 for c in candidates if self.knows(c)}


# --- craving request contract (section 9.1) ---------------------------------------------


def test_section_9_1_example_is_the_contract() -> None:
    request = CravingRequest.model_validate_json(SECTION_9_1)
    assert request.cuisine_ids == ("CHINESE",)
    assert request.model_dump_json(by_alias=True) == SECTION_9_1


@pytest.mark.parametrize(
    "body",
    [
        '{"intent":"CRAVING_RECOMMEND","unsafe":true}',  # extra field from the model
        '{"intent":"SEARCH"}',  # unknown intent
        '{"intent":"CRAVING_RECOMMEND","cuisineIds":["chinese"]}',  # not canonical
        '{"intent":"CRAVING_RECOMMEND","flavorTags":["UMAMI"]}',  # closed vocabulary
        '{"intent":"CRAVING_RECOMMEND","cuisineIds":["THAI","THAI"]}',  # repeated
        '{"intent":"SWAP_MEAL"}',  # swap without a slot or a clarification
        '{"intent":"SWAP_MEAL","mealSlotId":"D8_LUNCH"}',  # no such slot
    ],
)
def test_untrusted_nlu_output_is_rejected(body: str) -> None:
    with pytest.raises(ValidationError):
        CravingRequest.model_validate_json(body)


def test_swap_may_ask_for_clarification() -> None:
    request = CravingRequest.model_validate_json(
        '{"intent":"SWAP_MEAL","requiresClarification":true}'
    )
    assert request.meal_slot_id is None


# --- catalogue and stand-in screen -------------------------------------------------------


def test_catalogue_bundle_and_cuisine_ids(bundle: CatalogueBundle) -> None:
    latest = sorted(EXPORT.glob("*_catalogue.json"))[-1].name.removesuffix("_catalogue.json")
    assert bundle.version == latest
    assert bundle.cuisine_ids["NEPALI"] == "Nepali"
    assert bundle.cuisine_ids["MIDDLE_EASTERN"] == "Middle Eastern"
    assert bundle.cuisine_ids["MALAYSIAN"] == "Malaysian"
    combos = json.loads((EXPORT / f"{latest}_combinations.json").read_text("utf-8"))
    assert len(bundle.combinations) == len(combos["combinations"])


def test_screen_fails_closed_on_diet_and_matches_whole_words(bundle: CatalogueBundle) -> None:
    dishes = list(bundle.dishes.values())
    vegetarian = profile(diet="VEGETARIAN")
    assert all("vegetarian" in d.diet_tags for d in dishes if dish_allowed(d, vegetarian))
    no_egg = profile(allergies=["egg"])
    eggplant = [d for d in dishes if any("eggplant" in i for i in d.ingredients)]
    egg = [d for d in dishes if any(_tokens("egg") <= _tokens(i) for i in d.ingredients)]
    assert eggplant and egg
    assert any(dish_allowed(d, no_egg) for d in eggplant if d not in egg)
    assert not any(dish_allowed(d, no_egg) for d in egg)


def test_allergy_screen_sees_derived_ingredients(bundle: CatalogueBundle) -> None:
    dishes = list(bundle.dishes.values())
    for allergy, derived in [("milk", "ghee"), ("tree nut", "cashews"), ("wheat", "soy sauce")]:
        user = profile(allergies=[allergy])
        with_derived = [d for d in dishes if any(i.endswith(derived) for i in d.ingredients)]
        assert with_derived, derived
        assert not any(dish_allowed(d, user) for d in with_derived), allergy


# --- standalone craving (section 4.3) ----------------------------------------------------


def test_craving_returns_rule_pass_recipes_matching_the_request(bundle: CatalogueBundle) -> None:
    user = profile(diet="VEGETARIAN", allergies=["peanut"])
    result = recommend_for_craving(CravingRequest.model_validate_json(SECTION_9_1), user, bundle)
    assert result.status is CravingStatus.OK and result.items
    assert [i.rank for i in result.items] == list(range(1, len(result.items) + 1))
    for item in result.items:
        dish = bundle.dishes[item.recipe_id]
        assert "Chinese" in dish.cuisines
        assert "vegetarian" in dish.diet_tags
        assert not any(
            {"noodle"} <= _tokens(i) or {"peanut"} <= _tokens(i) for i in dish.ingredients
        )
        codes = {r.code for r in item.explanation.reasons}
        assert {"CRAVING_STANDARD_PORTION_ONLY", "RULES_PASS"} <= codes
    assert result.safety.status == "STAND_IN_UNVERIFIED"
    assert result.safety.allergens_checked_by == "DERIVED_TERM_MAP"
    assert result.kb_id == "gc1-stand-in-kb"
    assert result.model_version == "popularity-fallback-v1"  # no scorer: labelled fallback


def test_lazy_rule_checks_give_the_eager_top_k(bundle: CatalogueBundle) -> None:
    request, user = craving(cuisineIds=["THAI"]), profile()
    lazy = recommend_for_craving(request, user, bundle, top_k=3)
    retrieved, _, _ = retrieve_for_craving(request, user, bundle)
    ids = [d.recipe_id for d in retrieved if dish_allowed(d, user)]
    eligible = check_recipes(bundle, user, KnowledgeWorkflow.CRAVING_DISCOVERY, ids).eligible_ids
    eager = rank_recipes(
        (),
        [i for i in ids if i in eligible],
        RankingContext(),
        scorer=None,
        fallback=bundle.popularity,
    )
    assert [i.recipe_id for i in lazy.items] == [c.recipe_id for c in eager.ranked_candidates[:3]]
    assert lazy.counts.rule_checked < len(ids)  # it really stopped early


def test_craving_uses_the_trained_model_when_given(bundle: CatalogueBundle) -> None:
    user = profile(seedRecipeIds=["FC_81284"])
    result = recommend_for_craving(
        craving(cuisineIds=["CHINESE"]), user, bundle, scorer=FakeScorer(), top_k=3
    )
    assert result.model_version == "fake-sequence-v1" and result.fallback_reason is None


def test_craving_statuses(bundle: CatalogueBundle) -> None:
    user = profile()
    unclear = recommend_for_craving(craving(requiresClarification=True), user, bundle)
    assert unclear.status is CravingStatus.NEEDS_CLARIFICATION and not unclear.items
    unknown = recommend_for_craving(craving(cuisineIds=["KLINGON"]), user, bundle)
    assert unknown.status is CravingStatus.NO_MATCH
    assert unknown.unknown_cuisine_ids == ("KLINGON",)
    flavor = recommend_for_craving(
        craving(cuisineIds=["NEPALI"], flavorTags=["SMOKY"]), user, bundle, top_k=2
    )
    assert flavor.status is CravingStatus.OK
    with pytest.raises(ValueError, match="substitute_slot"):
        recommend_for_craving(
            CravingRequest.model_validate_json('{"intent":"SWAP_MEAL","mealSlotId":"D1_LUNCH"}'),
            user,
            bundle,
        )


def test_craving_is_deterministic(bundle: CatalogueBundle) -> None:
    request, user = CravingRequest.model_validate_json(SECTION_9_1), profile()
    assert recommend_for_craving(request, user, bundle) == recommend_for_craving(
        request, user, bundle
    )


# --- onboarding seeds (ADR 0005) ---------------------------------------------------------


def test_seed_suggestions_are_rule_safe_and_confirmable(bundle: CatalogueBundle) -> None:
    user = profile(diet="VEGETARIAN", cuisinePolicy="STRICT", cuisines=["Indian"])
    offered = suggest_seeds(user, bundle).suggestions
    assert len(offered) == 12
    assert bundle.dishes[offered[0].recipe_id].cuisines[0] == "Indian"
    for s in offered:
        assert is_seed_eligible(bundle.dishes[s.recipe_id])
        assert dish_allowed(bundle.dishes[s.recipe_id], user)
    picks = [s.recipe_id for s in offered[:3]]
    assert confirm_seeds(user, bundle, picks) == tuple(picks)
    meat = next(
        d.recipe_id
        for d in bundle.dishes.values()
        if is_seed_eligible(d) and "vegetarian" not in d.diet_tags
    )
    with pytest.raises(ValueError):
        confirm_seeds(user, bundle, [*picks[:2], meat])
    stored = profile(diet="VEGETARIAN", seedRecipeIds=[*picks[:2], meat])
    assert revalidate_seeds(stored, bundle) == tuple(picks[:2])


# --- weekly plan and substitution (sections 4.2 and 4.4) ---------------------------------

PLANNER = {"diet": "VEGETARIAN", "cuisinePolicy": "STRICT", "cuisines": ["Indian"]}


@pytest.fixture(scope="module")
def week(bundle: CatalogueBundle) -> WeekPlan:
    return plan_week(profile(**PLANNER), bundle, week_id="week-1", start_date=START)


@pytest.fixture(scope="module")
def swapped(bundle: CatalogueBundle, week: WeekPlan) -> WeekPlan:
    current = {m.slot_id: m.option_id for m in week.meals}
    return substitute_slot(
        profile(**PLANNER),
        bundle,
        current=current,
        slot="D2_LUNCH",
        week_id="week-1-r2",
        start_date=START,
    )


def test_week_is_21_verified_allowed_meals(bundle: CatalogueBundle, week: WeekPlan) -> None:
    user = profile(**PLANNER)
    assert week.status is PlanStatus.FEASIBLE, week.message
    assert week.search is not None and week.search.outcome.value == "FEASIBLE"
    assert [m.slot_id for m in week.meals] == [
        f"D{d}_{meal}" for d in range(1, 8) for meal in ("BREAKFAST", "LUNCH", "DINNER")
    ]
    assert week.meals[0].calendar_date == "2026-10-26"
    for meal in week.meals:
        combo = bundle.combinations[meal.combination_id]
        assert meal.meal_type in combo.meal_types
        assert "Indian" in combo.cuisines
        assert all(dish_allowed(bundle.dishes[c.dish_id], user) for c in combo.components)
        assert "RULES_PASS" in {r.code for r in meal.explanation.reasons}
    anchors = Counter(
        bundle.combinations[m.combination_id].components[0].dish_id for m in week.meals
    )
    assert max(anchors.values()) <= 2
    assert len(week.day_totals) == 7
    assert week.day_totals[0].totals.energy_kcal is not None
    assert week.safety.diet_checked_by == "FOODCOM_TAG"


def test_substitution_changes_only_the_target_slot(week: WeekPlan, swapped: WeekPlan) -> None:
    assert swapped.status is PlanStatus.FEASIBLE, swapped.message
    assert swapped.workflow == "PLANNED_SWAP"
    before = {m.slot_id: m.option_id for m in week.meals}
    after = {m.slot_id: m.option_id for m in swapped.meals}
    assert [s for s in before if before[s] != after[s]] == ["D2_LUNCH"]


def test_too_few_meals_is_insufficient_without_solving(bundle: CatalogueBundle) -> None:
    # British is an incidental Food.com tag, not a target cuisine: one breakfast dish.
    british = profile(cuisinePolicy="STRICT", cuisines=["British"])
    result = plan_week(british, bundle, week_id="week-gb", start_date=START)
    assert result.status is PlanStatus.INSUFFICIENT_DATA
    assert "breakfast" in result.message and result.search is None and not result.meals


def test_substitution_rejects_a_partial_plan(bundle: CatalogueBundle) -> None:
    with pytest.raises(ValueError, match="21 slot"):
        substitute_slot(
            profile(),
            bundle,
            current={"D1_LUNCH": "x"},
            slot="D1_LUNCH",
            week_id="w",
            start_date=START,
        )


def test_substitution_refuses_to_lock_meals_the_profile_no_longer_allows(
    bundle: CatalogueBundle, week: WeekPlan
) -> None:
    current = {m.slot_id: m.option_id for m in week.meals}
    vegan = profile(diet="VEGAN", cuisinePolicy="STRICT", cuisines=["Indian"])
    with pytest.raises(ValueError, match="no longer fit the profile"):
        substitute_slot(
            vegan, bundle, current=current, slot="D2_LUNCH", week_id="w", start_date=START
        )


def test_strict_nepali_has_enough_breakfasts_for_a_week(bundle: CatalogueBundle) -> None:
    # 7 breakfasts with each dish at most twice need 4 distinct anchors (catalogue audit).
    from savora_ai.core.pipelines.planning import _ranked_meals
    from savora_ai.schemas.enums import MealType

    nepali = profile(cuisinePolicy="STRICT", cuisines=["Nepali"])
    _, by_meal = _ranked_meals(bundle, nepali, None)
    anchors = {c.components[0].dish_id for c in by_meal[MealType.BREAKFAST]}
    assert len(anchors) >= 4
    assert {"USDA_2707714", "USDA_2707715"} <= anchors  # puri, paratha (curated USDA)


def test_replacements_are_ranked_eligible_and_exclude_the_current_meal(
    bundle: CatalogueBundle, week: WeekPlan
) -> None:
    user = profile(**PLANNER)
    current = {m.slot_id: m.option_id for m in week.meals}
    result = suggest_replacements(user, bundle, current=current, slot="D2_LUNCH")
    assert result.options and [o.rank for o in result.options] == list(
        range(1, len(result.options) + 1)
    )
    saved = next(m.combination_id for m in week.meals if m.slot_id == "D2_LUNCH")
    assert result.current_combination_id == saved
    for option in result.options:
        combo = bundle.combinations[option.combination_id]
        assert option.combination_id != saved
        assert "LUNCH" in {m.value for m in combo.meal_types}
        assert all(dish_allowed(bundle.dishes[c.dish_id], user) for c in combo.components)
        assert option.repeats_in_week < 2
    assert result.safety.status == "STAND_IN_UNVERIFIED"


def test_replacement_preference_filters_by_exclusion_and_reports_unknowns(
    bundle: CatalogueBundle, week: WeekPlan
) -> None:
    user = profile(**PLANNER)
    current = {m.slot_id: m.option_id for m in week.meals}
    wish = craving(intent="SWAP_MEAL", mealSlotId="D2_LUNCH", excludedIngredientIds=["POTATO"])
    result = suggest_replacements(user, bundle, current=current, slot="D2_LUNCH", preference=wish)
    for option in result.options:
        combo = bundle.combinations[option.combination_id]
        for part in combo.components:
            dish = bundle.dishes[part.dish_id]
            assert not any("potato" in i.lower().split() for i in dish.ingredients)
    nowhere = craving(intent="SWAP_MEAL", mealSlotId="D2_LUNCH", cuisineIds=["ATLANTEAN"])
    empty = suggest_replacements(user, bundle, current=current, slot="D2_LUNCH", preference=nowhere)
    assert empty.options == () and empty.unknown_cuisine_ids == ("ATLANTEAN",)
    assert "No eligible" in empty.message


def test_substitution_uses_the_chosen_replacement(bundle: CatalogueBundle, week: WeekPlan) -> None:
    user = profile(**PLANNER)
    current = {m.slot_id: m.option_id for m in week.meals}
    choice = suggest_replacements(user, bundle, current=current, slot="D3_DINNER").options[-1]
    result = substitute_slot(
        user,
        bundle,
        current=current,
        slot="D3_DINNER",
        week_id="week-1-r3",
        start_date=START,
        replacement_combination_id=choice.combination_id,
    )
    assert result.status is PlanStatus.FEASIBLE, result.message
    after = {m.slot_id: m for m in result.meals}
    assert after["D3_DINNER"].combination_id == choice.combination_id
    assert [s for s in current if current[s] != after[s].option_id] == ["D3_DINNER"]


def test_substitution_refuses_a_replacement_that_is_not_eligible(
    bundle: CatalogueBundle, week: WeekPlan
) -> None:
    current = {m.slot_id: m.option_id for m in week.meals}
    saved = next(m.combination_id for m in week.meals if m.slot_id == "D2_LUNCH")
    result = substitute_slot(
        profile(**PLANNER),
        bundle,
        current=current,
        slot="D2_LUNCH",
        week_id="w",
        start_date=START,
        replacement_combination_id=saved,  # the meal being replaced is never eligible
    )
    assert result.status is PlanStatus.INSUFFICIENT_DATA and not result.meals
    assert "no longer eligible" in result.message
