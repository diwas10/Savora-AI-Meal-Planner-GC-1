"""Public composition API (ARCHITECTURE.md section 11: `generate_meal_combinations`).

One call runs the whole Member 1 composition path: check the curated pairings against
the dishes, compose bounded 1-3 dish meals with portion presets (Stage 8), and validate
each configuration's nutrition (Stage 9). Only validated meals are returned; rejected
ones come back with their reasons. Eligibility stays with Member 2's Rule Engine.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.meal_composition.composer import DEFAULT_LIMITS, CompositionLimits, compose
from savora_ai.core.meal_composition.models import MealCombination
from savora_ai.core.meal_composition.nutrition import validate_combinations
from savora_ai.core.meal_composition.pairings import PairingFile, validate_pairings
from savora_ai.core.meal_composition.templates import TemplateFile


@dataclass(frozen=True)
class GenerationResult:
    combinations: tuple[MealCombination, ...]  # validated, deterministic order
    rejected: tuple[dict[str, object], ...]  # combination ID + every problem found
    composition_report: dict[str, object]
    validation_report: dict[str, object]


def generate_meal_combinations(
    dishes: Iterable[CatalogueRecipe],
    templates: TemplateFile,
    pairings: PairingFile,
    seed: str,
    limits: CompositionLimits = DEFAULT_LIMITS,
    check_pairings: bool = True,
) -> GenerationResult:
    """`check_pairings` verifies every curated pairing against `dishes`: right for a build
    from the full catalogue. Pass False for a pool already narrowed by the Rule Engine,
    where a removed staple must only drop its meals (`compose` skips absent staples), not
    abort the call; the build-time check still guards the curated file itself."""
    pool = tuple(dishes)
    if check_pairings:
        validate_pairings(pairings, pool)
    composition = compose(pool, templates, pairings, seed, limits)
    validation = validate_combinations(composition.combinations, pool)
    return GenerationResult(
        combinations=validation.combinations,
        rejected=validation.rejected,
        composition_report=composition.report,
        validation_report=validation.report,
    )
