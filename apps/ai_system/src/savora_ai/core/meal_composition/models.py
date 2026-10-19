"""Stage 8 output contracts: meal combinations and their portion configurations.

PROVISIONAL Member 1 DTOs (ADR 0002). Member 2's symbolic contracts
(`schemas.combinations`, `schemas.daily`) map from these; see
docs/member1_catalogue_contract.md for the field mapping.
"""

from typing import Self

from pydantic import Field, model_validator

from savora_ai.core.food_data.models import NutrientVector, _FoodModel, _NonBlank
from savora_ai.schemas.enums import (
    CulinaryRole,
    MealType,
    NutritionSource,
    PortionPreset,
    PortionUnit,
)


class ComponentRef(_FoodModel):
    slot: _NonBlank  # template slot, e.g. MAIN, STAPLE, VEGETABLE
    dish_id: _NonBlank
    role: CulinaryRole


class ComponentPortion(_FoodModel):
    dish_id: _NonBlank
    portion_id: _NonBlank
    quantity: float = Field(gt=0)
    unit: PortionUnit
    grams: float | None = Field(default=None, gt=0)  # None: Food.com serving, mass unknown


class CombinationNutrition(_FoodModel):
    """Stage 9: validated totals of one configuration (ADR 0003 D4)."""

    totals: NutrientVector  # sum per nutrient; any unknown component -> unknown
    source_tier: NutritionSource  # the weakest source among the components
    fully_known: bool  # every REQUIRED nutrient known for every component
    unknown_nutrients: tuple[_NonBlank, ...]


class PortionConfiguration(_FoodModel):
    configuration_id: _NonBlank  # "<combinationId>#<PRESET>"
    preset: PortionPreset
    portions: tuple[ComponentPortion, ...] = Field(min_length=1)
    nutrition: CombinationNutrition | None = None  # set by Stage 9 validation


class MealCombination(_FoodModel):
    combination_id: _NonBlank  # "C_<templateId>__<dishId>__<dishId>", slot order
    template_id: _NonBlank
    meal_types: tuple[MealType, ...] = Field(min_length=1)
    cuisines: tuple[_NonBlank, ...] = Field(min_length=1)  # the anchor dish's cuisines
    components: tuple[ComponentRef, ...] = Field(min_length=1, max_length=3)
    configurations: tuple[PortionConfiguration, ...] = Field(min_length=1)
    evidence: tuple[_NonBlank, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def check(self) -> Self:
        dish_ids = [c.dish_id for c in self.components]
        if len(set(dish_ids)) != len(dish_ids):
            raise ValueError("a dish may appear only once in a meal")
        if self.combination_id != "__".join((f"C_{self.template_id}", *dish_ids)):
            raise ValueError("combinationId must be C_<templateId>__ + dish IDs in slot order")
        presets = [c.preset for c in self.configurations]
        if len(set(presets)) != len(presets):
            raise ValueError("one configuration per preset")
        for configuration in self.configurations:
            if configuration.configuration_id != f"{self.combination_id}#{configuration.preset}":
                raise ValueError("configurationId must be <combinationId>#<preset>")
            if [p.dish_id for p in configuration.portions] != dish_ids:
                raise ValueError("a configuration must portion every component, in order")
        return self
