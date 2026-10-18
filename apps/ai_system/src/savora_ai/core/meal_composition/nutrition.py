"""Stage 9: combination-level nutrition validation, the acceptance test before handoff
to Member 2 (ADR 0003 D4).

For every portion configuration of every combination:

1. Sum per nutrient. known + known = known; ANY unknown component makes that nutrient
   unknown for the meal. Unknown is never zero (ARCHITECTURE.md section 3).
2. Weakest source wins. A meal is only as trustworthy as its least trusted component:
   one USDA staple never makes a Food.com curry "verified".
3. FULLY_KNOWN only if every required nutrient is known for every component; otherwise
   PARTIAL. Whether PARTIAL may pass a hard clinical rule is Member 2's decision.
4. Sanity. Meal energy is recomputed independently from each dish's BASE record (not
   the rounded portion vectors) and must agree; it must also be known and fall in a
   plausible meal range. A failing configuration is dropped with its reason; a
   combination left with none is rejected, never passed on half-checked.
"""

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from savora_ai.core.food_data.models import NUTRIENT_FIELDS, CatalogueRecipe, NutrientVector
from savora_ai.core.meal_composition.models import (
    CombinationNutrition,
    MealCombination,
    PortionConfiguration,
)
from savora_ai.schemas.enums import NutritionBasis, NutritionSource

# PROVISIONAL trust order, weakest first (ADR 0003 open item; Member 2 decides its use).
# FOODCOM_DERIVED is converted from %DV with an assumed sodium/saturated-fat table.
SOURCE_TRUST: dict[NutritionSource, int] = {
    NutritionSource.FOODCOM_DERIVED: 0,
    NutritionSource.CURATED: 1,
    NutritionSource.USDA_FNDDS: 2,
    NutritionSource.USDA_SR_LEGACY: 3,
    NutritionSource.USDA_FOUNDATION: 4,
}

# Nutrients a meal needs to be FULLY_KNOWN. Sugar is excluded: Food.com never has it
# (ADR 0001 D2) and no active rule needs it yet. Member 2's active rules may extend this.
REQUIRED_NUTRIENTS: tuple[str, ...] = (
    "energy_kcal",
    "fat_g",
    "saturated_fat_g",
    "carbohydrate_g",
    "protein_g",
    "sodium_mg",
)

# PROVISIONAL plausible energy of one meal, and the recomputation tolerance.
MEAL_KCAL_RANGE = (150.0, 2000.0)
ENERGY_AGREEMENT_KCAL = 1.0  # portion vectors are rounded to 3 decimals


def sum_nutrients(vectors: Iterable[NutrientVector]) -> NutrientVector:
    """Per-nutrient sum; one unknown makes that nutrient unknown."""
    items = list(vectors)
    totals: dict[str, float | None] = {}
    for name in NUTRIENT_FIELDS:
        values = [getattr(v, name) for v in items]
        totals[name] = None if any(x is None for x in values) else round(sum(values), 3)
    return NutrientVector(**totals)


def weakest_source(sources: Iterable[NutritionSource]) -> NutritionSource:
    return min(sources, key=lambda source: SOURCE_TRUST[source])


def _base_energy(dish: CatalogueRecipe, quantity: float, grams: float | None) -> float | None:
    """Energy straight from the dish's own record, independent of the portion vectors."""
    energy = dish.nutrition.values.energy_kcal
    if energy is None:
        return None
    if dish.nutrition.basis is NutritionBasis.PER_SERVING:
        return energy * quantity
    return None if grams is None else energy * grams / 100.0


@dataclass(frozen=True)
class Problem:
    code: str  # UNKNOWN_PORTION | ENERGY_UNKNOWN | ENERGY_DISAGREES | ENERGY_OUT_OF_RANGE
    message: str


@dataclass(frozen=True)
class ConfigurationCheck:
    configuration: PortionConfiguration | None  # with nutrition set, or None if rejected
    problems: tuple[Problem, ...]


def check_configuration(
    configuration: PortionConfiguration, dishes: Mapping[str, CatalogueRecipe]
) -> ConfigurationCheck:
    parts = [(dishes[p.dish_id], p) for p in configuration.portions]
    vectors: list[NutrientVector] = []
    for dish, portion in parts:
        option = next((o for o in dish.portions if o.portion_id == portion.portion_id), None)
        if option is None:
            message = f"{portion.portion_id} is not a portion of its dish"
            return ConfigurationCheck(None, (Problem("UNKNOWN_PORTION", message),))
        vectors.append(option.nutrients)
    totals = sum_nutrients(vectors)
    unknown = tuple(n for n in REQUIRED_NUTRIENTS if getattr(totals, n) is None)
    problems: list[Problem] = []
    energy = totals.energy_kcal
    base = [_base_energy(d, p.quantity, p.grams) for d, p in parts]
    if energy is None or any(b is None for b in base):
        problems.append(Problem("ENERGY_UNKNOWN", "meal energy is unknown"))
    else:
        recomputed = sum(b for b in base if b is not None)
        if abs(recomputed - energy) > ENERGY_AGREEMENT_KCAL:
            message = f"energy {energy:g} disagrees with recomputed {recomputed:.3f} kcal"
            problems.append(Problem("ENERGY_DISAGREES", message))
        low, high = MEAL_KCAL_RANGE
        if not low <= energy <= high:
            message = f"meal energy {energy:g} kcal outside {low:g}-{high:g}"
            problems.append(Problem("ENERGY_OUT_OF_RANGE", message))
    if problems:
        return ConfigurationCheck(None, tuple(problems))
    nutrition = CombinationNutrition(
        totals=totals,
        source_tier=weakest_source(d.nutrition.source for d, _ in parts),
        fully_known=not unknown,
        unknown_nutrients=unknown,
    )
    return ConfigurationCheck(
        PortionConfiguration.model_validate({**configuration.model_dump(), "nutrition": nutrition}),
        (),
    )


@dataclass(frozen=True)
class ValidationResult:
    combinations: tuple[MealCombination, ...]
    rejected: tuple[dict[str, object], ...]  # combination ID + every problem found
    report: dict[str, object]


def validate_combinations(
    combinations: Iterable[MealCombination], dishes: Iterable[CatalogueRecipe]
) -> ValidationResult:
    by_id = {d.recipe_id: d for d in dishes}
    kept: list[MealCombination] = []
    rejected: list[dict[str, object]] = []
    problem_counts: Counter[str] = Counter()
    dropped_configurations = 0
    for combo in combinations:
        missing = [c.dish_id for c in combo.components if c.dish_id not in by_id]
        if missing:
            problem = f"UNKNOWN_DISH: {missing}"
            rejected.append({"combinationId": combo.combination_id, "problems": [problem]})
            problem_counts["UNKNOWN_DISH"] += 1
            continue
        valid: list[PortionConfiguration] = []
        problems: list[str] = []
        for configuration in combo.configurations:
            checked = check_configuration(configuration, by_id)
            if checked.configuration is None:
                dropped_configurations += 1
                problems.extend(
                    f"{configuration.preset} {p.code}: {p.message}" for p in checked.problems
                )
                problem_counts.update(p.code for p in checked.problems)
            else:
                valid.append(checked.configuration)
        if valid:
            kept.append(
                MealCombination.model_validate(
                    {**combo.model_dump(), "configurations": tuple(valid)}
                )
            )
        else:
            rejected.append({"combinationId": combo.combination_id, "problems": problems})
    configurations = [c for combo in kept for c in combo.configurations]
    return ValidationResult(
        combinations=tuple(kept),
        rejected=tuple(rejected),
        report={
            "combinationsKept": len(kept),
            "combinationsRejected": len(rejected),
            "configurationsKept": len(configurations),
            "configurationsDropped": dropped_configurations,
            "problems": dict(sorted(problem_counts.items())),
            "fullyKnownConfigurations": sum(
                c.nutrition is not None and c.nutrition.fully_known for c in configurations
            ),
            "sourceTiers": dict(
                sorted(
                    Counter(
                        c.nutrition.source_tier.value for c in configurations if c.nutrition
                    ).items()
                )
            ),
            "requiredNutrients": list(REQUIRED_NUTRIENTS),
            "mealKcalRange": list(MEAL_KCAL_RANGE),
        },
    )
