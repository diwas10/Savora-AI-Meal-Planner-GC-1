"""Stage 8: meal templates as reviewable data (`Data/curated/meal_templates.json`)."""

from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from savora_ai.core.food_data.models import CatalogueRecipe, _FoodModel, _NonBlank
from savora_ai.core.meal_composition.presets import PRESET_SLOTS
from savora_ai.schemas.enums import CulinaryRole, DishClass, MealType

DEFAULT_TEMPLATES = Path("Data/curated/meal_templates.json")

_R = CulinaryRole
# Meal shapes the composer implements, by slot ROLES. Anything else is rejected when the
# template file loads, never discovered as a crash in the middle of a build.
SUPPORTED_SHAPES: frozenset[tuple[CulinaryRole, ...]] = frozenset(
    {
        (_R.MAIN_DISH,),
        (_R.MAIN_DISH, _R.STAPLE),
        (_R.MAIN_DISH, _R.STAPLE, _R.VEGETABLE),
        (_R.BREAKFAST_BASE,),
        (_R.BREAKFAST_BASE, _R.FRUIT),
        (_R.BREAKFAST_BASE, _R.PROTEIN_SOURCE),
    }
)


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
        roles = tuple(s.role for s in self.slots)
        if len(set(roles)) != len(roles):
            raise ValueError(f"{self.template_id}: a role may fill only one slot")
        if roles not in SUPPORTED_SHAPES:
            raise ValueError(
                f"{self.template_id}: unsupported meal shape {[r.value for r in roles]}"
            )
        unknown = sorted(set(names) - set(PRESET_SLOTS))
        if unknown:
            raise ValueError(f"{self.template_id}: no portion-preset rule for slots {unknown}")
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
