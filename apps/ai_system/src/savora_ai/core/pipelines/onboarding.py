"""Onboarding seed dishes (ADR 0005 D1) over rule-safe dishes for one profile.

    suggest_seeds(profile, bundle)          -> SeedSuggestions (12 by default)
    confirm_seeds(profile, bundle, picks)   -> the picks to store, in pick order
    revalidate_seeds(profile, bundle)       -> the stored picks still allowed

"Rule-safe" = passes the stand-in profile screen AND the Rule Engine (CRAVING_DISCOVERY
recipe stage, which is the recipe-level check). Checks run lazily in suggestion order,
like the craving pipeline, so onboarding stays fast.
"""

from collections.abc import Sequence

from savora_ai.core.pipelines.catalogue import CatalogueBundle
from savora_ai.core.pipelines.profile import PlanningProfile, dish_allowed
from savora_ai.core.pipelines.rules import check_recipes
from savora_ai.core.recommendation.seeds import (
    DEFAULT_SUGGESTIONS,
    MIN_SEED_PICKS,
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


def suggest_seeds(
    profile: PlanningProfile, bundle: CatalogueBundle, limit: int = DEFAULT_SUGGESTIONS
) -> SeedSuggestions:
    """Popular rule-safe dishes, the profile's cuisines first (`suggest_seed_dishes`)."""
    pool = [d for d in bundle.dishes.values() if is_seed_eligible(d) and dish_allowed(d, profile)]
    if len(pool) < MIN_SEED_PICKS:
        return SeedSuggestions(suggestions=())
    order = [
        s.recipe_id for s in suggest_seed_dishes(pool, profile.cuisines, len(pool)).suggestions
    ]
    passed: list[str] = []
    checked = 0
    while len(passed) < limit and checked < len(order):
        chunk = order[checked : checked + limit]
        safe = _rule_safe(bundle, profile, chunk)
        passed += [i for i in chunk if i in safe]
        checked += len(chunk)
    if len(passed) < MIN_SEED_PICKS:
        return SeedSuggestions(suggestions=())
    dishes = [bundle.dishes[i] for i in passed]
    return suggest_seed_dishes(dishes, profile.cuisines, min(limit, len(dishes)))


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
