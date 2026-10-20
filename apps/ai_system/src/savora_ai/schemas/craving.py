"""Normalized craving request (ARCHITECTURE.md section 9.1): the ONLY shape NLU may emit.

Qwen (or the template baseline) turns free text into this object; nothing downstream
reads raw model text. Validation is strict so a model cannot smuggle in extra fields,
unknown flavors or free-form IDs:

- `intent` is CRAVING_RECOMMEND (standalone discovery, section 4.3) or SWAP_MEAL
  (replace a saved plan slot, section 4.4).
- IDs are upper-case canonical tokens (`CHINESE`, `NOODLES`). Cuisine IDs are checked
  against the catalogue by the craving pipeline; unknown ones are reported, not guessed.
- `excludedIngredientIds` are dish preferences ("no noodles"), never allergies. Allergies
  come only from the user's confirmed profile (section 9.1 last paragraph).
- `mealSlotId` names a saved plan slot, `D<day>_<MEAL>` (e.g. `D2_LUNCH`). SWAP_MEAL needs
  one unless the parser asks for clarification.
"""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.alias_generators import to_camel

CRAVING_SCHEMA_VERSION = "craving-request.v1"
MAX_IDS = 10

CanonicalId = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")]
MealSlotId = Annotated[str, StringConstraints(pattern=r"^D[1-7]_(BREAKFAST|LUNCH|DINNER)$")]


class CravingIntent(StrEnum):
    CRAVING_RECOMMEND = "CRAVING_RECOMMEND"
    SWAP_MEAL = "SWAP_MEAL"


class FlavorTag(StrEnum):
    """Closed vocabulary; the craving pipeline maps each tag to ingredient words."""

    SPICY = "SPICY"
    SWEET = "SWEET"
    SOUR = "SOUR"
    SMOKY = "SMOKY"
    CREAMY = "CREAMY"


class CravingRequest(BaseModel):
    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
    )

    intent: CravingIntent
    cuisine_ids: Annotated[tuple[CanonicalId, ...], Field(max_length=MAX_IDS)] = ()
    flavor_tags: Annotated[tuple[FlavorTag, ...], Field(max_length=len(FlavorTag))] = ()
    excluded_ingredient_ids: Annotated[tuple[CanonicalId, ...], Field(max_length=MAX_IDS)] = ()
    meal_slot_id: MealSlotId | None = None
    requires_clarification: bool = False

    @model_validator(mode="after")
    def check_request(self) -> Self:
        for name in ("cuisine_ids", "flavor_tags", "excluded_ingredient_ids"):
            values = getattr(self, name)
            if len(set(values)) != len(values):
                raise ValueError(f"{to_camel(name)} must not repeat a value")
        swap = self.intent is CravingIntent.SWAP_MEAL
        if swap and self.meal_slot_id is None and not self.requires_clarification:
            raise ValueError("SWAP_MEAL needs mealSlotId or requiresClarification=true")
        return self

    @property
    def meal_type(self) -> str | None:
        """`BREAKFAST` | `LUNCH` | `DINNER` from `mealSlotId`, if any."""
        return None if self.meal_slot_id is None else self.meal_slot_id.split("_", 1)[1]
