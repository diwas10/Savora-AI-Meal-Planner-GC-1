"""Onboarding seed dishes (ADR 0005 D1) over rule-safe dishes for one profile.

    suggest_seeds(profile, bundle)          -> SeedSuggestions (12 by default)
    confirm_seeds(profile, bundle, picks)   -> the picks to store, in pick order
    revalidate_seeds(profile, bundle)       -> the stored picks still allowed

"Rule-safe" = passes the stand-in profile screen AND the Rule Engine (CRAVING_DISCOVERY
recipe stage, which is the recipe-level check). Checks run lazily in suggestion order,
like the craving pipeline, so onboarding stays fast.
"""

from collections.abc import Sequence

from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.pipelines.catalogue import CatalogueBundle
from savora_ai.core.pipelines.profile import (
    PlanningProfile,
    cuisine_allowed,
    dish_allowed,
    dish_swaps,
)
from savora_ai.core.pipelines.rules import check_recipes
from savora_ai.core.recommendation.seeds import (
    DEFAULT_SUGGESTIONS,
    MIN_SEED_PICKS,
    SeedSuggestion,
    SeedSuggestions,
    is_seed_eligible,
    suggest_seed_dishes,
    validate_seed_picks,
)
from savora_ai.schemas.knowledge_base import KnowledgeWorkflow

_WORKFLOW = KnowledgeWorkflow.CRAVING_DISCOVERY


def _rule_safe(bundle: CatalogueBundle, profile: PlanningProfile, ids: Sequence[str]) -> set[str]:
    screened = [i for i in ids if i in bundle.dishes and dish_allowed(bundle.dishes[i], profile)]
    if not screened:
        return set()
    return set(check_recipes(bundle, profile, _WORKFLOW, screened).eligible_ids)


def _offer(
    profile: PlanningProfile, bundle: CatalogueBundle, order: list[str], limit: int
) -> SeedSuggestions:
    """The first `limit` rule-safe dishes of `order`, each with its swaps (if any)."""
    passed: list[str] = []
    checked = 0
    while len(passed) < limit and checked < len(order):
        chunk = order[checked : checked + limit]
        safe = _rule_safe(bundle, profile, chunk)
        passed += [i for i in chunk if i in safe]
        checked += len(chunk)
    if len(passed) < MIN_SEED_PICKS:
        return SeedSuggestions(suggestions=())
    return SeedSuggestions(
        suggestions=tuple(
            SeedSuggestion(
                recipe_id=d.recipe_id,
                name=d.name,
                cuisines=d.cuisines,
                rank=rank,
                swaps=dish_swaps(d, profile) or (),
            )
            for rank, d in enumerate((bundle.dishes[i] for i in passed[:limit]), start=1)
        )
    )


def _ordered(profile: PlanningProfile, dishes: list[CatalogueRecipe]) -> list[str]:
    """Popularity, interleaved over the profile's cuisines first (`suggest_seed_dishes`)."""
    if not dishes:
        return []
    found = suggest_seed_dishes(dishes, profile.cuisines, max(len(dishes), MIN_SEED_PICKS))
    return [s.recipe_id for s in found.suggestions]


def suggest_seeds(
    profile: PlanningProfile, bundle: CatalogueBundle, limit: int = DEFAULT_SUGGESTIONS
) -> SeedSuggestions:
    """Popular rule-safe dishes of the profile's cuisines, best fit first.

    1. Dishes of the chosen cuisines that pass the profile as they are.
    2. Then dishes of the chosen cuisines that pass once an EXCLUDED ingredient is swapped
       (onion -> asafoetida, ...); each carries its swaps. Allergies are never swapped.
    3. Other cuisines only if 1 and 2 give fewer than MIN_SEED_PICKS dishes; a STRICT
       cuisine policy never offers another cuisine, as in the plan.
    """
    eligible = [
        d
        for d in bundle.dishes.values()
        if is_seed_eligible(d) and cuisine_allowed(d.cuisines, profile)
    ]
    allowed = [(d, dish_swaps(d, profile)) for d in eligible]
    strict = [d for d, s in allowed if s == ()]
    swapped = [d for d, s in allowed if s]

    def mine(dishes: list[CatalogueRecipe]) -> list[CatalogueRecipe]:
        return [d for d in dishes if d.cuisines and d.cuisines[0] in profile.cuisines]

    if profile.cuisines:
        offered = _offer(
            profile,
            bundle,
            _ordered(profile, mine(strict)) + _ordered(profile, mine(swapped)),
            limit,
        )
        if offered.suggestions:
            return offered
    if len(strict) + len(swapped) < MIN_SEED_PICKS:
        return SeedSuggestions(suggestions=())
    return _offer(profile, bundle, _ordered(profile, strict) + _ordered(profile, swapped), limit)


def confirm_seeds(
    profile: PlanningProfile, bundle: CatalogueBundle, picks: Sequence[str]
) -> tuple[str, ...]:
    """The validated picks to store on the profile; raises ValueError on any unusable pick."""
    safe = _rule_safe(bundle, profile, list(dict.fromkeys(picks)))
    return validate_seed_picks(picks, {i: bundle.dishes[i] for i in safe})


def revalidate_seeds(profile: PlanningProfile, bundle: CatalogueBundle) -> tuple[str, ...]:
    """After a profile change: the stored seeds still rule-safe, in order. Ask the user for
    more when fewer than MIN_SEED_PICKS remain (ADR 0005 D1.6)."""
    safe = _rule_safe(bundle, profile, profile.seed_recipe_ids)
    return tuple(i for i in profile.seed_recipe_ids if i in safe)
