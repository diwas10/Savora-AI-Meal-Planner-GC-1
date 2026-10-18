"""Shared string enums for food, nutrition, composition and planning contracts.

Member values are the wire (JSON) and database (VARCHAR + CHECK) tokens, so they must
not be renamed casually; tests pin them. Values follow ARCHITECTURE.md and are provisional
where the team has open decisions (section 15). Rule-engine enums live in
``schemas.knowledge`` / ``schemas.reasoning``.
"""

from enum import StrEnum


class Sex(StrEnum):
    """Only the values needed by the resting-energy estimator."""

    MALE = "MALE"
    FEMALE = "FEMALE"


class ActivityLevel(StrEnum):
    SEDENTARY = "SEDENTARY"
    LIGHT = "LIGHT"
    MODERATE = "MODERATE"
    ACTIVE = "ACTIVE"
    VERY_ACTIVE = "VERY_ACTIVE"


class Goal(StrEnum):
    LOSE = "LOSE"
    MAINTAIN = "MAINTAIN"
    GAIN = "GAIN"


class HealthCondition(StrEnum):
    """The three conditions in GC1 scope (ARCHITECTURE.md section 1)."""

    TYPE_2_DIABETES = "TYPE_2_DIABETES"
    HYPERTENSION = "HYPERTENSION"
    DYSLIPIDEMIA = "DYSLIPIDEMIA"


class CuisinePolicy(StrEnum):
    """Provisional; the shared team document uses different names for the last two."""

    STRICT = "STRICT"
    MAJORITY = "MAJORITY"
    MIXED = "MIXED"


class MealType(StrEnum):
    BREAKFAST = "BREAKFAST"
    LUNCH = "LUNCH"
    DINNER = "DINNER"


class DishClass(StrEnum):
    COMPLETE_MEAL = "COMPLETE_MEAL"
    REQUIRES_ACCOMPANIMENT = "REQUIRES_ACCOMPANIMENT"
    COMPONENT = "COMPONENT"


class CulinaryRole(StrEnum):
    """Contextual and non-exclusive: one dish may carry several roles."""

    STAPLE = "STAPLE"
    MAIN_DISH = "MAIN_DISH"
    PROTEIN_SOURCE = "PROTEIN_SOURCE"
    VEGETABLE = "VEGETABLE"
    BREAKFAST_BASE = "BREAKFAST_BASE"
    FRUIT = "FRUIT"
    SUPPLEMENT = "SUPPLEMENT"


class PortionUnit(StrEnum):
    """Household units. SERVING is one recipe serving, whose mass may be unknown."""

    PIECE = "PIECE"
    BOWL = "BOWL"
    CUP = "CUP"
    SLICE = "SLICE"
    LOAF = "LOAF"
    GRAM = "GRAM"
    MILLILITER = "MILLILITER"
    SERVING = "SERVING"


class PlanStatus(StrEnum):
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    TIMEOUT = "TIMEOUT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class QuarantineReason(StrEnum):
    """Why a raw recipe was quarantined: a DATA DEFECT, not a classification gap.

    A recipe with no meal tag is not defective, it is unclassified (Stage 2), so it has
    no reason here. A quarantined row is kept, with all its reasons, for later review.
    """

    MALFORMED_NUTRITION = "MALFORMED_NUTRITION"
    MALFORMED_METADATA = "MALFORMED_METADATA"
    NUTRITION_OUT_OF_RANGE = "NUTRITION_OUT_OF_RANGE"
    ENERGY_INCONSISTENT = "ENERGY_INCONSISTENT"  # NO_MEAL_TYPE is gone on purpose


class ClassificationStatus(StrEnum):
    """How a dish's roles and meal types were decided (ADR 0001 D5).

    Only AUTO and CURATED dishes may be selected for planning; REQUIRES_REVIEW dishes
    go to the review queue until a curated override settles them.
    """

    AUTO = "AUTO"
    CURATED = "CURATED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class NutritionSource(StrEnum):
    """Where a nutrient value came from (ADR 0003 D1). A dish keeps its own source."""

    FOODCOM_DERIVED = "FOODCOM_DERIVED"  # kcal + %DV converted with a named DV table
    USDA_FNDDS = "USDA_FNDDS"
    USDA_SR_LEGACY = "USDA_SR_LEGACY"
    USDA_FOUNDATION = "USDA_FOUNDATION"
    CURATED = "CURATED"


class NutritionBasis(StrEnum):
    """What quantity the values describe. Tokens match Member 2's MeasurementBasis."""

    PER_SERVING = "PER_SERVING"  # one recipe serving; its mass may be unknown
    PER_100_G = "PER_100_G"
