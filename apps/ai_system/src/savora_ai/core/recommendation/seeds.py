"""Onboarding seed dishes: the cold-start shortlist and the picks that become history.

ADR 0004 D7 / ADR 0005: a new user has no history, so onboarding offers liked-dish
suggestions and the user picks 3 to 5. Those picks are stored as a PROFILE PREFERENCE and
are the only history `rank_recipes` / `rank_combinations` ever receive (never ratings,
consumption or saved plans).

    suggest_seed_dishes(rule_safe_dishes, preferred_cuisines, limit)
    validate_seed_picks(picks, rule_safe_dishes)

Guarantees:
- Only the SUPPLIED dishes are offered; the caller passes dishes the Rule Engine already
  passed for this profile (and its cuisine policy), so this never decides safety.
- Only Food.com dishes with a meal-anchor role are offered: the model knows them, and an
  anchor is what scores a meal (ADR 0004 D6). USDA staples and plain sides are not.
- Deterministic: training popularity, interleaved across cuisines, then recipe ID.
"""

from collections.abc import Iterable, Mapping, Sequence

from pydantic import Field

from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.recommendation.ranking import _RankingModel
from savora_ai.schemas.enums import CulinaryRole

SEED_METHOD = "popularity-cuisine-interleave-v1"
MIN_SEED_PICKS = 3
MAX_SEED_PICKS = 5
DEFAULT_SUGGESTIONS = 12
ANCHOR_ROLES = frozenset({CulinaryRole.MAIN_DISH, CulinaryRole.BREAKFAST_BASE})
NO_CUISINE = "Other"


class SeedSuggestion(_RankingModel):
    recipe_id: str
    name: str
    cuisines: tuple[str, ...]
    rank: int = Field(ge=1)


class SeedSuggestions(_RankingModel):
    suggestions: tuple[SeedSuggestion, ...]
    method: str = SEED_METHOD
    min_picks: int = MIN_SEED_PICKS
    max_picks: int = MAX_SEED_PICKS


def is_seed_eligible(dish: CatalogueRecipe) -> bool:
    """A recognisable dish the model knows: Food.com, with a main or breakfast-base role."""
    return dish.training_interactions is not None and bool(ANCHOR_ROLES & set(dish.roles))


def _popularity_order(dishes: Iterable[CatalogueRecipe]) -> list[CatalogueRecipe]:
    return sorted(dishes, key=lambda d: (-(d.training_interactions or 0), d.recipe_id))


def suggest_seed_dishes(
    rule_safe_dishes: Iterable[CatalogueRecipe],
    preferred_cuisines: Sequence[str] = (),
    limit: int = DEFAULT_SUGGESTIONS,
) -> SeedSuggestions:
    """Popular dishes, one cuisine at a time, so the list is not ten dishes of one cuisine.

    Cuisines the user prefers come first (in their order), then the others by their most
    popular dish. A dish counts once, under its first cuisine."""
    if limit < MIN_SEED_PICKS:
        raise ValueError(f"offer at least {MIN_SEED_PICKS} suggestions")
    groups: dict[str, list[CatalogueRecipe]] = {}
    for dish in _popularity_order(d for d in rule_safe_dishes if is_seed_eligible(d)):
        groups.setdefault(dish.cuisines[0] if dish.cuisines else NO_CUISINE, []).append(dish)
    preferred = [c for c in dict.fromkeys(preferred_cuisines) if c in groups]
    others = [c for c in groups if c not in preferred]  # already in popularity order
    order = preferred + others
    picked: list[CatalogueRecipe] = []
    depth = 0
    while len(picked) < limit and any(depth < len(groups[c]) for c in order):
        picked += [groups[c][depth] for c in order if depth < len(groups[c])]
        depth += 1
    return SeedSuggestions(
        suggestions=tuple(
            SeedSuggestion(recipe_id=d.recipe_id, name=d.name, cuisines=d.cuisines, rank=i + 1)
            for i, d in enumerate(picked[:limit])
        )
    )


def validate_seed_picks(
    picks: Sequence[str], rule_safe_dishes: Mapping[str, CatalogueRecipe]
) -> tuple[str, ...]:
    """The user's picks as history, in pick order; raises on anything the planner may not use.

    Picks may come from search as well as the suggestions, but every pick must be a
    seed-eligible dish that is still rule-safe for this profile."""
    if not MIN_SEED_PICKS <= len(picks) <= MAX_SEED_PICKS:
        raise ValueError(f"pick {MIN_SEED_PICKS} to {MAX_SEED_PICKS} dishes")
    if len(set(picks)) != len(picks):
        raise ValueError("a dish may be picked only once")
    unusable = [p for p in picks if p not in rule_safe_dishes]
    if unusable:
        raise ValueError(f"not rule-safe for this profile: {unusable}")
    not_seeds = [p for p in picks if not is_seed_eligible(rule_safe_dishes[p])]
    if not_seeds:
        raise ValueError(f"not a dish that can seed recommendations: {not_seeds}")
    return tuple(picks)
