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
    PIECE = "PIECE"
    BOWL = "BOWL"
    CUP = "CUP"
    SLICE = "SLICE"
    LOAF = "LOAF"
    GRAM = "GRAM"
    MILLILITER = "MILLILITER"


class PlanStatus(StrEnum):
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    TIMEOUT = "TIMEOUT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class RejectionReason(StrEnum):
    """Why a raw recipe was kept out of the catalogue; recorded in the build report."""

    MALFORMED_NUTRITION = "MALFORMED_NUTRITION"
    MALFORMED_METADATA = "MALFORMED_METADATA"
    NUTRITION_OUT_OF_RANGE = "NUTRITION_OUT_OF_RANGE"
    ENERGY_INCONSISTENT = "ENERGY_INCONSISTENT"
    NO_MEAL_TYPE = "NO_MEAL_TYPE"
