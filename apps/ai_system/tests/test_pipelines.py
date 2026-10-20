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
    assert bundle.version == "20261019T012206Z"
    assert bundle.cuisine_ids["NEPALI"] == "Nepali"
    assert bundle.cuisine_ids["MIDDLE_EASTERN"] == "Middle Eastern"
    assert len(bundle.combinations) == 465


def test_screen_fails_closed_on_diet_and_matches_whole_words(bundle: CatalogueBundle) -> None:
    dishes = list(bundle.dishes.values())
    vegetarian = profile(diet="VEGETARIAN")
    assert all("vegetarian" in d.diet_tags for d in dishes if dish_allowed(d, vegetarian))
    no_egg = profile(allergies=["egg"])
    eggplant = [d for d in dishes if any("eggplant" in i for i in d.ingredients)]
    egg = [d for d in dishes if any(_tokens("egg") <= _tokens(i) for i in d.ingredients)]
    assert eggplant and egg
    assert all(dish_allowed(d, no_egg) for d in eggplant if d not in egg)
    assert not any(dish_allowed(d, no_egg) for d in egg)


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
    assert result.safety.allergens_checked_by == "INGREDIENT_NAME_MATCH"
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
    nepali = profile(cuisinePolicy="STRICT", cuisines=["Nepali"])
    result = plan_week(nepali, bundle, week_id="week-np", start_date=START)
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
