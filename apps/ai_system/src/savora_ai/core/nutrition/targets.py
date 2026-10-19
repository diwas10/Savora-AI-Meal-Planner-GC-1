"""Deterministic daily energy target calculation.

Resting energy uses the Mifflin-St Jeor equation: Mifflin MD, St Jeor ST, et al.,
"A new predictive equation for resting energy expenditure in healthy individuals",
Am J Clin Nutr 1990;51(2):241-247. BMI is reported for information only and never
feeds an energy formula. Nutrient bounds are not set here: clinical limits come from
the sourced rule KB (Member 2) and stay unknown (empty) until supplied.

Activity factors, goal adjustments, the energy band and meal shares are PROVISIONAL
planning assumptions awaiting team approval (ARCHITECTURE.md section 15).

Macronutrient bounds are GENERAL-POPULATION reference ranges, not clinical limits:
Institute of Medicine, "Dietary Reference Intakes for Energy, Carbohydrate, Fiber, Fat,
Fatty Acids, Cholesterol, Protein, and Amino Acids (Macronutrients)", National Academies
Press, 2005: the Acceptable Macronutrient Distribution Ranges (AMDR) for adults and the
protein RDA of 0.8 g/kg/day. Sodium, saturated fat and sugar limits are clinical or
policy rules and stay with Member 2's sourced rule KB, so they are absent here.
"""

import hashlib
import json
from datetime import datetime

from savora_ai.core.nutrition.models import (
    Bounds,
    MealEnergyRange,
    NutrientBounds,
    NutritionTargets,
    TargetInput,
)
from savora_ai.schemas.enums import ActivityLevel, Goal, MealType, Sex

FORMULA_VERSION = "targets-0.2"  # 0.2 adds AMDR macronutrient bounds
METHOD = "MIFFLIN_ST_JEOR"

# Mifflin-St Jeor sex constant added to the weight/height/age terms.
_SEX_CONSTANT_KCAL: dict[Sex, float] = {Sex.MALE: 5.0, Sex.FEMALE: -161.0}

# PROVISIONAL: conventional activity multipliers on resting energy.
ACTIVITY_FACTORS: dict[ActivityLevel, float] = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.ACTIVE: 1.725,
    ActivityLevel.VERY_ACTIVE: 1.9,
}

# PROVISIONAL: goal adjustment as a multiplier of maintenance energy.
GOAL_FACTORS: dict[Goal, float] = {Goal.LOSE: 0.85, Goal.MAINTAIN: 1.0, Goal.GAIN: 1.10}

# PROVISIONAL: half-width of the acceptable daily energy band around the target.
ENERGY_BAND_FRACTION = 0.05

# PROVISIONAL planning assumption, not a medical standard.
DEFAULT_MEAL_ENERGY_POLICY: tuple[MealEnergyRange, ...] = (
    MealEnergyRange(meal_type=MealType.BREAKFAST, min_fraction=0.2, max_fraction=0.3),
    MealEnergyRange(meal_type=MealType.LUNCH, min_fraction=0.3, max_fraction=0.4),
    MealEnergyRange(meal_type=MealType.DINNER, min_fraction=0.3, max_fraction=0.4),
)


# IOM 2005 AMDR for adults (19+): share of energy -> grams via Atwater kcal per gram.
AMDR_ADULT: dict[str, tuple[float, float, float]] = {
    "protein_g": (0.10, 0.35, 4.0),
    "carbohydrate_g": (0.45, 0.65, 4.0),
    "fat_g": (0.20, 0.35, 9.0),
}
PROTEIN_RDA_G_PER_KG = 0.8  # IOM 2005, adults


def macronutrient_bounds(energy_kcal: float, weight_kg: float) -> tuple[NutrientBounds, ...]:
    """AMDR ranges in grams for the energy target; protein never below the RDA.

    Only protein gets a target (the RDA-based minimum); carbohydrate and fat are ranges.
    """
    bounds: list[NutrientBounds] = []
    for nutrient, (low, high, kcal_per_g) in AMDR_ADULT.items():
        minimum = round(energy_kcal * low / kcal_per_g)
        maximum = round(energy_kcal * high / kcal_per_g)
        target = None
        if nutrient == "protein_g":
            rda = round(PROTEIN_RDA_G_PER_KG * weight_kg)
            minimum = min(max(minimum, rda), maximum)
            target = minimum
        bounds.append(
            NutrientBounds(
                nutrient=nutrient, bounds=Bounds(min=minimum, target=target, max=maximum)
            )
        )
    return tuple(bounds)


def resting_energy_kcal(data: TargetInput) -> float:
    """Mifflin-St Jeor resting energy expenditure in kcal/day."""
    return (
        10.0 * data.weight_kg
        + 6.25 * data.height_cm
        - 5.0 * data.age_years
        + _SEX_CONSTANT_KCAL[data.sex]
    )


def body_mass_index(data: TargetInput) -> float:
    """Informational only; never used to derive energy or the goal."""
    height_m = data.height_cm / 100.0
    return data.weight_kg / (height_m * height_m)


def input_hash(data: TargetInput) -> str:
    """Stable SHA-256 of the canonical input, to detect stale targets."""
    canonical = json.dumps(data.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def calculate_nutrition_targets(
    data: TargetInput,
    *,
    profile_version: int,
    calculated_at: datetime,
) -> NutritionTargets:
    """Build a versioned energy target snapshot.

    Pure and deterministic: version and timestamp are supplied by the caller.
    """
    resting = resting_energy_kcal(data)
    if resting <= 0:  # unreachable inside TargetInput's ranges; never return a bogus target
        raise ValueError(f"resting energy {resting:.1f} kcal is not plausible for this input")
    target = round(resting * ACTIVITY_FACTORS[data.activity] * GOAL_FACTORS[data.goal])
    band = round(target * ENERGY_BAND_FRACTION)
    return NutritionTargets(
        profile_version=profile_version,
        formula_version=FORMULA_VERSION,
        method=METHOD,
        input_hash=input_hash(data),
        calculated_at=calculated_at,
        energy_kcal=Bounds(min=target - band, target=target, max=target + band),
        nutrient_bounds=macronutrient_bounds(target, data.weight_kg),
        meal_energy_policy=DEFAULT_MEAL_ENERGY_POLICY,
        bmi=round(body_mass_index(data), 1),
        provenance=(
            "Mifflin-St Jeor 1990 (Am J Clin Nutr 51(2):241-247)",
            "PROVISIONAL activity factors, goal adjustments, energy band and meal shares",
            "Macronutrients: IOM 2005 Dietary Reference Intakes, adult AMDR and protein RDA "
            "0.8 g/kg (general-population reference, not clinical)",
            "No clinical nutrient bounds (sodium, saturated fat, sugar); awaiting sourced rule KB",
        ),
    )
