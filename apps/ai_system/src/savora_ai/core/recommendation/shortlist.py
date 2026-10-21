"""Per-slot candidate shortlist: ranked meals -> the FIXED options the CSP searches.

The Transformer ranks whole meal COMBINATIONS (never portions). The CSP then chooses one
portion configuration per slot. Member 2's solver has structural budgets (20 Oct 2026):
at most 50 options per slot and 150 per day, and a weekly effective ceiling of about 75
distinct options. Its suggested first experiment is 2 combinations x 4 configurations per
meal type, so those are the defaults here, as named limits.

Order is the ranking order, then the preset order (STANDARD first), so the shortlist is
deterministic and the CSP's first-feasible search tries the best-ranked meal first.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from savora_ai.core.meal_composition.models import MealCombination
from savora_ai.core.recommendation.ranking import CombinationRanking
from savora_ai.schemas.enums import MealType, PortionPreset

PRESET_ORDER = tuple(PortionPreset)


@dataclass(frozen=True)
class ShortlistLimits:
    combinations_per_slot: int = 2
    configurations_per_combination: int = 4
    max_options_per_slot: int = 50  # Member 2 structural limit
    max_options_per_day: int = 150  # Member 2 structural limit

    def __post_init__(self) -> None:
        if self.combinations_per_slot < 1 or self.configurations_per_combination < 1:
            raise ValueError("a shortlist needs at least one combination and configuration")
        if self.combinations_per_slot * self.configurations_per_combination > (
            self.max_options_per_slot
        ):
            raise ValueError("combinations x configurations exceeds the per-slot option limit")


DEFAULT_SHORTLIST = ShortlistLimits()


@dataclass(frozen=True)
class ShortlistOption:
    option_id: str  # "<combinationId>:<PRESET>": Member 2's opaque ID pattern (no '#')
    combination_id: str
    configuration_id: str
    preset: PortionPreset
    combination_rank: int


@dataclass(frozen=True)
class SlotShortlist:
    meal_type: MealType
    options: tuple[ShortlistOption, ...]
    skipped_unsuitable: tuple[str, ...]  # ranked IDs that do not suit this meal type


def shortlist_slot(
    meal_type: MealType,
    ranking: CombinationRanking,
    combinations: Mapping[str, MealCombination],
    limits: ShortlistLimits = DEFAULT_SHORTLIST,
) -> SlotShortlist:
    """Top-ranked combinations that suit `meal_type`, each with its first configurations."""
    options: list[ShortlistOption] = []
    skipped: list[str] = []
    taken = 0
    for candidate in ranking.ranked_candidates:
        if taken >= limits.combinations_per_slot:
            break
        combo = combinations.get(candidate.combination_id)
        if combo is None:
            raise ValueError(f"ranked combination {candidate.combination_id} is not supplied")
        if meal_type not in combo.meal_types:
            skipped.append(combo.combination_id)
            continue
        configs = sorted(combo.configurations, key=lambda c: PRESET_ORDER.index(c.preset))
        for config in configs[: limits.configurations_per_combination]:
            options.append(
                ShortlistOption(
                    option_id=config.configuration_id.replace("#", ":"),
                    combination_id=combo.combination_id,
                    configuration_id=config.configuration_id,
                    preset=config.preset,
                    combination_rank=candidate.rank,
                )
            )
        taken += 1
    return SlotShortlist(
        meal_type=meal_type, options=tuple(options), skipped_unsuitable=tuple(skipped)
    )


def shortlist_day(
    rankings: Mapping[MealType, CombinationRanking],
    combinations: Mapping[str, MealCombination],
    limits: ShortlistLimits = DEFAULT_SHORTLIST,
) -> dict[MealType, SlotShortlist]:
    """One shortlist per meal type; the day's DISTINCT options must fit Member 2's budget
    (lunch and dinner may share options, which count once)."""
    day = {meal: shortlist_slot(meal, rankings[meal], combinations, limits) for meal in MealType}
    distinct = {o.option_id for s in day.values() for o in s.options}
    if len(distinct) > limits.max_options_per_day:
        raise ValueError(f"{len(distinct)} distinct options exceed the daily limit")
    return day


def option_ids(shortlist: SlotShortlist) -> Sequence[str]:
    return [o.option_id for o in shortlist.options]
