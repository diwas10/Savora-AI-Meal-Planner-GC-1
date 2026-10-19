"""Stage 6: curated main-to-staple pairings per cuisine (ADR 0002 D1).

A main that REQUIRES_ACCOMPANIMENT may only be paired with the staples listed for one of
its cuisines. The list is small, readable data (`Data/curated/pairings.json`) that a person
can review, rather than rules hidden in code. Vegetable sides pair by cuisine (the same
cuisine, or cuisine-neutral), so they need no list.
"""

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from savora_ai.core.food_data.classification import check_cuisines
from savora_ai.core.food_data.models import CatalogueRecipe, _FoodModel, _NonBlank
from savora_ai.schemas.enums import CulinaryRole

DEFAULT_PAIRINGS = Path("Data/curated/pairings.json")


class CuisinePairing(_FoodModel):
    cuisine: _NonBlank
    staples: tuple[_NonBlank, ...] = Field(min_length=1)  # catalogue dish IDs
    rationale: _NonBlank

    @model_validator(mode="after")
    def check(self) -> Self:
        check_cuisines((self.cuisine,))
        if len(set(self.staples)) != len(self.staples):
            raise ValueError(f"duplicate staple in {self.cuisine} pairing")
        return self


class PairingFile(_FoodModel):
    schema_version: Literal["pairings.v1"]
    note: _NonBlank
    curated_by: _NonBlank
    cuisines: tuple[CuisinePairing, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique(self) -> Self:
        names = [c.cuisine for c in self.cuisines]
        if len(set(names)) != len(names):
            raise ValueError("a cuisine may appear only once")
        return self

    def staples_by_cuisine(self) -> Mapping[str, tuple[str, ...]]:
        return {c.cuisine: c.staples for c in self.cuisines}


def load_pairings(path: Path = DEFAULT_PAIRINGS) -> PairingFile:
    return PairingFile.model_validate_json(path.read_text(encoding="utf-8"))


def validate_pairings(pairings: PairingFile, dishes: Iterable[CatalogueRecipe]) -> None:
    """Every paired staple exists, is a STAPLE, and is used in that cuisine (or neutral)."""
    by_id = {d.recipe_id: d for d in dishes}
    for pairing in pairings.cuisines:
        for staple_id in pairing.staples:
            staple = by_id.get(staple_id)
            if staple is None:
                raise ValueError(f"{pairing.cuisine} pairing names unknown dish {staple_id}")
            if CulinaryRole.STAPLE not in staple.roles:
                raise ValueError(f"{staple_id} is paired as a staple but has no STAPLE role")
            if staple.cuisines and pairing.cuisine not in staple.cuisines:
                raise ValueError(f"{staple_id} is not used in {pairing.cuisine} cuisine")
