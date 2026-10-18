"""Stage 8: meal templates as reviewable data (`Data/curated/meal_templates.json`)."""

from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from savora_ai.core.food_data.models import CatalogueRecipe, _FoodModel, _NonBlank
from savora_ai.schemas.enums import CulinaryRole, DishClass, MealType

DEFAULT_TEMPLATES = Path("Data/curated/meal_templates.json")


class TemplateSlot(_FoodModel):
    slot: _NonBlank
    role: CulinaryRole
    dish_classes: tuple[DishClass, ...] = Field(min_length=1)

    def accepts(self, dish: CatalogueRecipe, meals: tuple[MealType, ...]) -> bool:
        return (
            self.role in dish.roles
            and dish.dish_class in self.dish_classes
            and any(meal in dish.meal_types for meal in meals)
        )


class MealTemplate(_FoodModel):
    template_id: _NonBlank
    meal_types: tuple[MealType, ...] = Field(min_length=1)
    slots: tuple[TemplateSlot, ...] = Field(min_length=1, max_length=3)  # N <= 3
    rationale: _NonBlank

    @model_validator(mode="after")
    def check(self) -> Self:
        names = [s.slot for s in self.slots]
        if len(set(names)) != len(names):
            raise ValueError(f"{self.template_id}: duplicate slot names")
        roles = [s.role for s in self.slots]
        if len(set(roles)) != len(roles):
            raise ValueError(f"{self.template_id}: a role may fill only one slot")
        return self


class TemplateFile(_FoodModel):
    schema_version: Literal["meal-templates.v1"]
    note: _NonBlank
    templates: tuple[MealTemplate, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique(self) -> Self:
        ids = [t.template_id for t in self.templates]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate templateId")
        return self


def load_templates(path: Path = DEFAULT_TEMPLATES) -> TemplateFile:
    return TemplateFile.model_validate_json(path.read_text(encoding="utf-8"))
