from typing import Annotated, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.alias_generators import to_camel

from savora_ai.schemas.enums import ActivityLevel, MealType, Sex

# A string with at least one non-space character. "" and "   " are rejected
_NonBlank = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]

_Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class _NutritionModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="ignore",
        alias_generator=to_camel,
        populate_by_name=True,
        allow_inf_nan=False,
    )


class TargetInput(_NutritionModel):
    age_years: int = Field(gt=0, le=120)
    sex: Sex
    height_cm: float = Field(gt=0)
    weight_kg: float = Field(gt=0)
    activity: ActivityLevel


class Bounds(_NutritionModel):
    """None means unknown or unbounded, never zero."""

    min: float | None = Field(default=None, ge=0)
    target: float | None = Field(default=None, ge=0)
    max: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def check_order(self) -> Self:
        known = [v for v in (self.min, self.target, self.max) if v is not None]
        # keep only values that were actually provided, in min, target and max order
        if known != sorted(known):
            raise ValueError("bounds must satisfy min <= target <= max")
        return self


class NutrientsBounds(_NutritionModel):
    # One nutrient name paired with its bounds, for example "sodium_mg" with max 2000
    nutrient: _NonBlank

    bounds: Bounds


class MealEnergyRange(_NutritionModel):
    """What share of the day's calories a meal should provide, e.g. lunch 30% to 40%."""

    meal_type: MealType
    min_fraction: float = Field(ge=0, le=1)
    max_fraction: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def check_order(self) -> Self:
        if self.min_fraction > self.max_fraction:
            raise ValueError("minFraction must not exceed maxFraction")
        return self


class NutritionTargets(_NutritionModel):
    profile_version: int = Field(ge=1)
    formula_version: _NonBlank
    method: _NonBlank
    # Name of the equation used (for example the Mifflin-St Jeor equation).
    input_hash: _Sha256Hex
    calculated_at: AwareDatetime
    energy_kcal: Bounds
    nutrient_bounds: tuple[NutrientsBounds, ...] = ()
    meal_energy_policy: tuple[MealEnergyRange, ...] = ()
    bmi: float | None = Field(default=None, gt=0)
    provenance: tuple[_NonBlank, ...] = ()

    @model_validator(mode="after")
    def check_unique_keys(self) -> Self:
        nutrients = [n.nutrient for n in self.nutrient_bounds]
        meals = [m.meal_type for m in self.meal_energy_policy]

        if len(set(nutrients)) != len(nutrients) or len(set(meals)) != len(meals):
            # A set drops duplicates. If its size is smaller than the list, something repeated.
            raise ValueError("duplicate nutrient or meal entries")
        return self
