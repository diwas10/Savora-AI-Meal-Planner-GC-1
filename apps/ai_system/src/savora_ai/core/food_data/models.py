"""Provisional catalogue contracts for normalized Food.com recipes.

These DTOs are Member 1's draft; joint approval of canonical IDs and nutrient names is
still pending (ARCHITECTURE.md section 15), so keep them local to food_data for now.
"""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.alias_generators import to_camel

from savora_ai.schemas.enums import MealType

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


class ServingNutrition(_FoodModel):
    """Nutrition of ONE recipe serving in canonical units. Mass of a serving is separate."""

    energy_kcal: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    saturated_fat_g: float = Field(ge=0)
    carbohydrate_g: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    sodium_mg: float = Field(ge=0)
    # Sugar %DV has no verified reference yet, so grams stay unknown (None, never 0).
    sugars_g: float | None = Field(default=None, ge=0)


class CatalogueRecipe(_FoodModel):
    recipe_id: _NonBlank  # "FC_<food.com id>"; ID format awaits team approval
    name: _NonBlank
    ingredients: tuple[_NonBlank, ...]
    cuisines: tuple[_NonBlank, ...]  # exact-tag cuisines only; may be empty
    diet_tags: tuple[_NonBlank, ...]  # Food.com metadata labels, NOT verified diet facts
    meal_types: tuple[MealType, ...] = Field(min_length=1)
    nutrition_per_serving: ServingNutrition
    dv_reference: _NonBlank  # which DvReference produced the gram/mg values
    # Unknown until a person verifies it (ADR 0001); None means unknown, never zero.
    serving_mass_g: float | None = Field(default=None, gt=0)
    serving_mass_source: _NonBlank | None = None
    provenance: tuple[_NonBlank, ...] = ()

    @model_validator(mode="after")
    def check_serving_mass_has_source(self) -> Self:
        # A mass without a source (or a source without a mass) cannot be audited.
        if (self.serving_mass_g is None) != (self.serving_mass_source is None):
            raise ValueError("servingMassG and servingMassSource must be set together")
        return self


class ServingMassOverride(_FoodModel):
    """A human-verified serving mass for one catalogue recipe."""

    recipe_id: _NonBlank
    serving_mass_g: float = Field(gt=0)
    source: _NonBlank
