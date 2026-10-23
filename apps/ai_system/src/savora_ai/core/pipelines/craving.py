"""Standalone craving (ARCHITECTURE.md section 4.3): the one call the backend makes after NLU.

    recommend_for_craving(request, profile, bundle, scorer=..., top_k=10)

    CravingRequest (validated NLU output, section 9.1)
      -> retrieval: cuisine, meal slot, explicit exclusions, flavor (catalogue facts only)
      -> stand-in profile screen: diet tag, excluded/allergen words (profile.py)
      -> Rule Engine: Member 2's filter_candidates (CRAVING_DISCOVERY workflow)
      -> Transformer: rank_recipes over rule-PASS recipe IDs (popularity fallback, labelled)
      -> explanation per recipe, standard-portion nutrition only

No Meal Composition and no CSP. Nutrition is the catalogue's verified standard portion and
is never checked against the day's remaining targets (the explanation says so).

Rules run lazily, in ranked order: the retrieved recipes are ranked, then rule-checked a
batch at a time until `top_k` have PASSED. Rule checks are per recipe and independent, and
the ranker scores each recipe independently, so the order of the PASSED recipes is the
order a filter-everything-first run would give; only rule-PASS recipes are re-ranked and
returned. This keeps a request to a few seconds (Member 2's check costs ~0.1 s a recipe).
"""

from collections.abc import Sequence
from enum import StrEnum
from typing import Literal

from savora_ai.core.explainability.explanation import (
    RecipeExplanation,
    RuleOutcome,
    explain_craving_recipe,
)
from savora_ai.core.food_data.classification import is_plannable
from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.meal_composition.composer import _tokens
from savora_ai.core.pipelines.catalogue import CatalogueBundle
from savora_ai.core.pipelines.profile import (
    PlanningProfile,
    SafetyVerification,
    _PipelineModel,
    dish_allowed,
    safety_verification,
    with_cook_without,
)
from savora_ai.core.pipelines.rules import check_recipes
from savora_ai.core.recommendation.ranking import (
    FallbackReason,
    RankingContext,
    SequenceScorer,
    rank_recipes,
)
from savora_ai.schemas.craving import CravingIntent, CravingRequest, FlavorTag
from savora_ai.schemas.enums import CuisinePolicy
from savora_ai.schemas.knowledge_base import KnowledgeWorkflow

DEFAULT_TOP_K = 10
MAX_TOP_K = 20

# PROVISIONAL ingredient words per flavor (whole-word match on ingredients and dish name).
FLAVOR_WORDS: dict[FlavorTag, tuple[str, ...]] = {
    FlavorTag.SPICY: (
        "chili", "chile", "chilli", "jalapeno", "cayenne", "sriracha", "chipotle",
        "habanero", "serrano", "gochujang", "red pepper flake", "hot sauce", "curry paste",
        "szechuan", "sichuan", "spicy",
    ),
    FlavorTag.SWEET: (
        "sugar", "brown sugar", "honey", "maple syrup", "chocolate", "jaggery", "sweet",
    ),
    FlavorTag.SOUR: ("lemon", "lime", "vinegar", "tamarind", "sour", "tangy"),
    FlavorTag.SMOKY: ("smoked", "chipotle", "bacon", "smoky", "liquid smoke"),
    FlavorTag.CREAMY: (
        "cream", "heavy cream", "coconut milk", "yogurt", "cheese", "cream cheese",
        "sour cream", "creamy",
    ),
}  # fmt: skip


class CravingStatus(StrEnum):
    OK = "OK"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"  # the NLU asked; show its question
    NO_MATCH = "NO_MATCH"  # nothing retrieved or nothing passed the rules


class CravingItem(_PipelineModel):
    recipe_id: str
    name: str
    rank: int
    score: float
    cuisines: tuple[str, ...]
    explanation: RecipeExplanation  # includes standard portion + its nutrients


class CravingCounts(_PipelineModel):
    retrieved: int  # after cuisine / meal / exclusion / flavor retrieval
    screened_out: int  # removed by the stand-in diet/allergy/exclusion screen
    rule_checked: int  # sent to the Rule Engine (lazily, in ranked order)
    rule_excluded: int  # FAIL or UNKNOWN among those checked (never shown)


class CravingRecommendation(_PipelineModel):
    status: CravingStatus
    workflow: Literal["CRAVING_DISCOVERY"] = "CRAVING_DISCOVERY"
    request: CravingRequest
    items: tuple[CravingItem, ...]
    model_version: str | None
    fallback_reason: FallbackReason | None
    unknown_cuisine_ids: tuple[str, ...]
    unmatched_flavor_tags: tuple[FlavorTag, ...]
    counts: CravingCounts
    kb_id: str | None
    kb_version: str | None
    safety: SafetyVerification


def _has_word(dish: CatalogueRecipe, phrase: str) -> bool:
    words = _tokens(phrase)
    return any(words <= _tokens(text) for text in (dish.name, *dish.ingredients))


def _flavored(dish: CatalogueRecipe, tag: FlavorTag) -> bool:
    return any(_has_word(dish, phrase) for phrase in FLAVOR_WORDS[tag])


def retrieve_for_craving(
    request: CravingRequest, profile: PlanningProfile, bundle: CatalogueBundle
) -> tuple[list[CatalogueRecipe], tuple[str, ...], tuple[FlavorTag, ...]]:
    """Recipes matching the craving, the unknown cuisine IDs and the unmatched flavors.

    Cuisines named in the craving win over the profile's cuisine preference (a preference,
    not a restriction); without any, a STRICT profile keeps its own cuisines."""
    known = bundle.cuisine_ids
    unknown = tuple(c for c in request.cuisine_ids if c not in known)
    wanted = {known[c] for c in request.cuisine_ids if c in known}
    if request.cuisine_ids and not wanted:
        return [], unknown, ()
    if not wanted and profile.cuisine_policy is CuisinePolicy.STRICT:
        wanted = set(profile.cuisines)
    pool = [
        d
        for d in sorted(bundle.dishes.values(), key=lambda d: d.recipe_id)
        if d.training_interactions is not None  # Food.com dishes: a recipe, not a staple
        and is_plannable(d)
        and (not wanted or wanted & set(d.cuisines))
        and (request.meal_type is None or request.meal_type in {m.value for m in d.meal_types})
        and not any(
            _has_word(d, ex.replace("_", " ").lower()) for ex in request.excluded_ingredient_ids
        )
    ]
    unmatched = tuple(t for t in request.flavor_tags if not any(_flavored(d, t) for d in pool))
    matched = [t for t in request.flavor_tags if t not in unmatched]
    return [d for d in pool if all(_flavored(d, t) for t in matched)], unknown, unmatched


def recommend_for_craving(
    request: CravingRequest,
    profile: PlanningProfile,
    bundle: CatalogueBundle,
    *,
    scorer: SequenceScorer | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> CravingRecommendation:
    """Top `top_k` rule-PASS recipes for a validated craving; see the module docstring."""
    if request.intent is not CravingIntent.CRAVING_RECOMMEND:
        raise ValueError("SWAP_MEAL goes to substitute_slot, not the craving pipeline")
    if not 1 <= top_k <= MAX_TOP_K:
        raise ValueError(f"top_k must be 1..{MAX_TOP_K}")
    safety = safety_verification(profile)
    empty = CravingCounts(retrieved=0, screened_out=0, rule_checked=0, rule_excluded=0)

    def result(
        status: CravingStatus,
        counts: CravingCounts,
        unknown: tuple[str, ...],
        unmatched: tuple[FlavorTag, ...],
        items: Sequence[CravingItem] = (),
        *,
        model: tuple[str | None, FallbackReason | None] = (None, None),
        kb: tuple[str | None, str | None] = (None, None),
    ) -> CravingRecommendation:
        return CravingRecommendation(
            status=status,
            request=request,
            items=tuple(items),
            model_version=model[0],
            fallback_reason=model[1],
            unknown_cuisine_ids=unknown,
            unmatched_flavor_tags=unmatched,
            counts=counts,
            kb_id=kb[0],
            kb_version=kb[1],
            safety=safety,
        )

    if request.requires_clarification:
        return result(CravingStatus.NEEDS_CLARIFICATION, empty, (), ())

    retrieved, unknown, unmatched = retrieve_for_craving(request, profile, bundle)
    screened = [d for d in retrieved if dish_allowed(d, profile)]
    counts = empty.model_copy(
        update={"retrieved": len(retrieved), "screened_out": len(retrieved) - len(screened)}
    )
    if not screened:
        return result(CravingStatus.NO_MATCH, counts, unknown, unmatched)

    history = profile.seed_recipe_ids
    context = RankingContext(slot_id=request.meal_slot_id)
    order = rank_recipes(
        history,
        [d.recipe_id for d in screened],
        context,
        scorer=scorer,
        fallback=bundle.popularity,
    )
    ranked_ids = [c.recipe_id for c in order.ranked_candidates]
    passed: list[str] = []
    outcomes: dict[str, RuleOutcome] = {}
    checked = 0
    batch = 2 * top_k
    kb: tuple[str | None, str | None] = (None, None)
    while len(passed) < top_k and checked < len(ranked_ids):
        chunk = ranked_ids[checked : checked + batch]
        check = check_recipes(bundle, profile, KnowledgeWorkflow.CRAVING_DISCOVERY, chunk)
        kb = (check.kb_id, check.kb_version)
        outcomes.update(check.outcomes)
        passed += [i for i in chunk if i in check.eligible_ids]
        checked += len(chunk)
    counts = counts.model_copy(
        update={"rule_checked": checked, "rule_excluded": checked - len(passed)}
    )
    if not passed:
        return result(CravingStatus.NO_MATCH, counts, unknown, unmatched, kb=kb)

    final = rank_recipes(
        history, passed[:top_k], context, scorer=scorer, fallback=bundle.popularity
    )
    items = [
        CravingItem(
            recipe_id=c.recipe_id,
            name=bundle.dishes[c.recipe_id].name,
            rank=c.rank,
            score=c.score,
            cuisines=bundle.dishes[c.recipe_id].cuisines,
            explanation=with_cook_without(
                explain_craving_recipe(
                    bundle.dishes[c.recipe_id],
                    ranking=final,
                    rules=outcomes[c.recipe_id],
                    steps=bundle.recipe_steps.get(c.recipe_id, ()),
                ),
                [bundle.dishes[c.recipe_id]],
                profile,
            ),
        )
        for c in final.ranked_candidates
    ]
    return result(
        CravingStatus.OK,
        counts,
        unknown,
        unmatched,
        items,
        model=(final.model_version, final.fallback_reason),
        kb=kb,
    )
