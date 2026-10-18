"""Provisional catalogue contracts for normalized Food.com recipes.

These DTOs are Member 1's draft; joint approval of canonical IDs and nutrient names is
still pending (ARCHITECTURE.md section 15), so keep them local to food_data for now.
"""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.alias_generators import to_camel

from savora_ai.schemas.enums import (
    ClassificationStatus,
    CulinaryRole,
    DishClass,
    MealType,
    NutritionBasis,
    NutritionSource,
    PortionUnit,
    QuarantineReason,
)

# A string with at least one non-space character.
_NonBlank = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]


class _FoodModel(BaseModel):
    # Same house style as the nutrition models: strict, immutable, no unknown fields.
    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        allow_inf_nan=False,
    )


class DvReference(_FoodModel):
    """Daily-value amounts that 100 %DV equals. Food.com stores %DV, not grams."""

    name: _NonBlank
    fat_g: float = Field(gt=0)
    saturated_fat_g: float = Field(gt=0)
    carbohydrate_g: float = Field(gt=0)
    protein_g: float = Field(gt=0)
    sodium_mg: float = Field(gt=0)


class NutrientVector(_FoodModel):
    """Nutrient amounts for one basis quantity, in canonical units.

    Every field is optional because sources differ: None means UNKNOWN and is never
    treated as zero (ARCHITECTURE.md section 3). Food.com sugar is always None (ADR 0001).
    """

    energy_kcal: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)
    saturated_fat_g: float | None = Field(default=None, ge=0)
    carbohydrate_g: float | None = Field(default=None, ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    sodium_mg: float | None = Field(default=None, ge=0)
    sugars_g: float | None = Field(default=None, ge=0)


# Canonical nutrient keys, in a fixed order, for summing and reporting.
NUTRIENT_FIELDS: tuple[str, ...] = tuple(NutrientVector.model_fields)


class NutritionRecord(_FoodModel):
    """A dish's nutrition with its provenance (ADR 0003 D1-D3)."""

    source: NutritionSource
    basis: NutritionBasis
    values: NutrientVector
    # The exact origin: a DV table name for Food.com, "fdc:<id>" for a USDA food.
    source_reference: _NonBlank
    # Problems found in the source values, e.g. a negative value set to unknown.
    quality_flags: tuple[_NonBlank, ...] = ()


class PortionOption(_FoodModel):
    """One discrete quantity of one dish, with its ABSOLUTE nutrients (ADR 0003 D2).

    The CSP chooses among options and only adds their nutrient vectors, so it never needs
    a dish's mass. `grams` is None when the mass is unknown (Food.com servings).
    """

    portion_id: _NonBlank  # "<dishId>:<quantity>x<unit>", e.g. "USDA_2707713:2xPIECE"
    quantity: float = Field(gt=0)
    unit: PortionUnit
    grams: float | None = Field(default=None, gt=0)
    label: _NonBlank
    is_standard: bool
    nutrients: NutrientVector


class CatalogueRecipe(_FoodModel):
    recipe_id: _NonBlank  # "FC_<food.com id>"; ID format awaits team approval
    name: _NonBlank
    ingredients: tuple[_NonBlank, ...]
    cuisines: tuple[_NonBlank, ...]  # exact-tag cuisines only; may be empty
    diet_tags: tuple[_NonBlank, ...]  # Food.com metadata labels, NOT verified diet facts
    # Stage 2 classification (see classification.py). Empty roles = not a planning dish.
    roles: tuple[CulinaryRole, ...]
    dish_class: DishClass | None
    meal_types: tuple[MealType, ...]  # derived from roles, never from one tag alone
    classification_status: ClassificationStatus
    classification_evidence: tuple[_NonBlank, ...]
    nutrition: NutritionRecord  # Food.com: PER_SERVING; USDA staple: PER_100_G
    # Unknown until a person verifies it (ADR 0001); None means unknown, never zero.
    serving_mass_g: float | None = Field(default=None, gt=0)
    serving_mass_source: _NonBlank | None = None
    provenance: tuple[_NonBlank, ...] = ()
    # Stage 5: Food.com interactions before the popularity cutoff (training only). None for
    # USDA staples, which have no interaction data; never a guessed count.
    training_interactions: int | None = Field(default=None, ge=0)
    # Stage 4: discrete options, increasing quantity, exactly one standard. Empty until the
    # dish is selected for the catalogue (only selected dishes need portions).
    portions: tuple[PortionOption, ...] = ()

    @model_validator(mode="after")
    def check_serving_mass_has_source(self) -> Self:
        # A mass without a source (or a source without a mass) cannot be audited.
        if (self.serving_mass_g is None) != (self.serving_mass_source is None):
            raise ValueError("servingMassG and servingMassSource must be set together")
        return self

    @model_validator(mode="after")
    def check_portions(self) -> Self:
        if not self.portions:
            return self
        quantities = [p.quantity for p in self.portions]
        if quantities != sorted(set(quantities)):
            raise ValueError("portions must have strictly increasing quantities")
        if sum(p.is_standard for p in self.portions) != 1:
            raise ValueError("exactly one portion must be the standard portion")
        if len({p.unit for p in self.portions}) != 1:
            raise ValueError("all portions of a dish use one unit")
        if any(not p.portion_id.startswith(f"{self.recipe_id}:") for p in self.portions):
            raise ValueError("portion IDs must start with the dish ID")
        return self


class ServingMassOverride(_FoodModel):
    """A human-verified serving mass for one catalogue recipe."""

    recipe_id: _NonBlank
    serving_mass_g: float = Field(gt=0)
    source: _NonBlank


class QuarantinedRow(_FoodModel):
    """A raw row with a data defect. Kept with ALL its reasons so a person can review it."""

    source_id: str  # raw text: a defective row may not even have a numeric ID
    name: str  # plain str, not _NonBlank: a blank name is itself a defect we must record
    reasons: tuple[QuarantineReason, ...] = Field(min_length=1)  # at least one, any number
