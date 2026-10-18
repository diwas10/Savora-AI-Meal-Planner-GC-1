"""Stage 3: curated USDA staples (rice, roti, naan, fruit...) as catalogue dishes.

A USDA record is used only when it is the SAME food as the dish (ADR 0003 D1), chosen by
a curated `fdc_id`, never by fuzzy name matching. Three files are involved:

- `Data/curated/usda_staples.json`: the curated spec (identity, roles, portion), by hand;
- the raw USDA FoodData Central CSVs (1.6 GB, git-ignored), read once by `extract`;
- `Data/curated/usda_staples_extract.json`: the small committed extract, so a catalogue
  build never needs the raw USDA files.

Usage (from the repo root):
    uv run python -m savora_ai.core.food_data.usda_staples --usda-dir Data/USDA
    uv run python -m savora_ai.core.food_data.usda_staples --usda-dir Data/USDA --check
"""

import argparse
import csv
import hashlib
import json
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from savora_ai.core.food_data.models import (
    CatalogueRecipe,
    NutrientVector,
    NutritionRecord,
    _FoodModel,
    _NonBlank,
)
from savora_ai.core.food_data.portions import measured_portions, with_portions
from savora_ai.schemas.enums import (
    ClassificationStatus,
    CulinaryRole,
    DishClass,
    MealType,
    NutritionBasis,
    NutritionSource,
    PortionUnit,
)

DEFAULT_SPEC = Path("Data/curated/usda_staples.json")
DEFAULT_EXTRACT = Path("Data/curated/usda_staples_extract.json")

# USDA nutrient.csv IDs -> our canonical keys. Units match: KCAL, G, MG.
USDA_NUTRIENT_IDS: dict[int, str] = {
    1008: "energy_kcal",
    1004: "fat_g",
    1258: "saturated_fat_g",
    1005: "carbohydrate_g",  # carbohydrate by difference: can be slightly negative
    1003: "protein_g",
    1093: "sodium_mg",
    2000: "sugars_g",
}

DATA_TYPE_SOURCES: dict[str, NutritionSource] = {
    "survey_fndds_food": NutritionSource.USDA_FNDDS,
    "sr_legacy_food": NutritionSource.USDA_SR_LEGACY,
    "foundation_food": NutritionSource.USDA_FOUNDATION,
}

_Positive = Annotated[float, Field(gt=0)]


class StaplePortionSpec(_FoodModel):
    """Household measure from USDA food_portion.csv and the quantities a plan may use."""

    unit: PortionUnit
    usda_portion_id: int = Field(gt=0)  # exact food_portion.csv row; must belong to the food
    allowed_quantities: tuple[_Positive, ...] = Field(min_length=2)
    standard_quantity: _Positive

    @model_validator(mode="after")
    def check_quantities(self) -> Self:
        if list(self.allowed_quantities) != sorted(set(self.allowed_quantities)):
            raise ValueError("allowedQuantities must be strictly increasing")
        if self.standard_quantity not in self.allowed_quantities:
            raise ValueError("standardQuantity must be one of allowedQuantities")
        return self


class StapleSpec(_FoodModel):
    dish_id: _NonBlank
    fdc_id: int = Field(gt=0)
    name: _NonBlank
    expected_description: _NonBlank  # identity guard: must equal the USDA description
    roles: tuple[CulinaryRole, ...] = Field(min_length=1)
    dish_class: DishClass
    meal_types: tuple[MealType, ...] = Field(min_length=1)
    cuisines: tuple[_NonBlank, ...]  # empty = cuisine-neutral, pairs with any cuisine
    diet_tags: tuple[_NonBlank, ...]
    ingredients: tuple[_NonBlank, ...] = Field(min_length=1)
    portion: StaplePortionSpec
    rationale: _NonBlank
    curated_by: _NonBlank

    @model_validator(mode="after")
    def check_id(self) -> Self:
        if self.dish_id != f"USDA_{self.fdc_id}":
            raise ValueError("dishId must be USDA_<fdcId>")
        return self


class StapleSpecFile(_FoodModel):
    schema_version: Literal["usda-staples.v1"]
    note: _NonBlank
    staples: tuple[StapleSpec, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique(self) -> Self:
        ids = [s.fdc_id for s in self.staples]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate fdcId in staple spec")
        return self


class UsdaPortion(_FoodModel):
    """One USDA household measure. FNDDS writes "1 medium chappatti or roti (7")" in the
    description; SR Legacy writes amount 0.5 + modifier "cup, chopped". Both reduce to
    grams per ONE unit, which is what portions use."""

    portion_id: int = Field(gt=0)  # food_portion.csv `id`, for provenance
    label: _NonBlank
    amount: _Positive
    gram_weight: _Positive
    grams_per_unit: _Positive


class StapleExtract(_FoodModel):
    """What USDA says about one staple; written by `extract`, read by every build."""

    fdc_id: int = Field(gt=0)
    data_type: _NonBlank
    description: _NonBlank
    publication_date: _NonBlank
    per_100_g: NutrientVector
    quality_flags: tuple[_NonBlank, ...]
    portion: UsdaPortion


class StapleExtractFile(_FoodModel):
    schema_version: Literal["usda-staples-extract.v1"]
    spec_sha: _NonBlank  # which spec content the extract was made from
    staples: tuple[StapleExtract, ...]


def spec_digest(spec: StapleSpecFile) -> str:
    payload = json.dumps(spec.model_dump(mode="json", by_alias=True), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def nutrients_from_amounts(amounts: Mapping[int, float]) -> tuple[NutrientVector, tuple[str, ...]]:
    """Map USDA amounts to our keys. Missing stays None; a negative value is flagged, not
    clamped to zero (carbohydrate by difference can be slightly negative)."""
    values: dict[str, float | None] = {}
    flags: list[str] = []
    for nutrient_id, key in USDA_NUTRIENT_IDS.items():
        amount = amounts.get(nutrient_id)
        if amount is not None and amount < 0:
            flags.append(f"{key} reported as {amount:g}: set to unknown")
            amount = None
        values[key] = amount
    missing = [key for key, value in values.items() if value is None]
    if missing:
        flags.append(f"unknown in USDA: {', '.join(missing)}")
    return NutrientVector(**values), tuple(flags)


def parse_portion(row: Mapping[str, str]) -> UsdaPortion:
    """Normalise a food_portion.csv row; FNDDS leaves `amount` blank, meaning one unit."""
    amount = float(row["amount"]) if row["amount"].strip() else 1.0
    label = row["portion_description"].strip() or f"{amount:g} {row['modifier'].strip()}"
    grams = float(row["gram_weight"])
    return UsdaPortion(
        portion_id=int(row["id"]),
        label=label,
        amount=amount,
        gram_weight=grams,
        grams_per_unit=grams / amount,
    )


def _read_rows(path: Path, fdc_ids: set[str]) -> Iterable[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["fdc_id"] in fdc_ids:
                yield row


def extract(spec: StapleSpecFile, usda_dir: Path) -> StapleExtractFile:
    """Read the raw USDA CSVs once for the curated IDs; fail loudly on any mismatch."""
    wanted = {str(s.fdc_id) for s in spec.staples}
    foods = {row["fdc_id"]: row for row in _read_rows(usda_dir / "food.csv", wanted)}
    amounts: dict[str, dict[int, float]] = {fdc: {} for fdc in wanted}
    for row in _read_rows(usda_dir / "food_nutrient.csv", wanted):
        nutrient_id = int(row["nutrient_id"])
        if nutrient_id in USDA_NUTRIENT_IDS:
            amounts[row["fdc_id"]][nutrient_id] = float(row["amount"])
    portions: dict[str, list[dict[str, str]]] = {fdc: [] for fdc in wanted}
    for row in _read_rows(usda_dir / "food_portion.csv", wanted):
        portions[row["fdc_id"]].append(row)

    extracts: list[StapleExtract] = []
    for staple in spec.staples:
        key = str(staple.fdc_id)
        food = foods.get(key)
        if food is None:
            raise ValueError(f"fdc_id {key} not found in food.csv")
        if food["description"] != staple.expected_description:
            raise ValueError(
                f"fdc_id {key} is {food['description']!r}, not {staple.expected_description!r}"
            )
        if food["data_type"] not in DATA_TYPE_SOURCES:
            raise ValueError(f"fdc_id {key} has unsupported data type {food['data_type']}")
        portion_id = str(staple.portion.usda_portion_id)
        matches = [p for p in portions[key] if p["id"] == portion_id]
        if len(matches) != 1:
            raise ValueError(f"fdc_id {key} has no food_portion row {portion_id}")
        portion = parse_portion(matches[0])
        values, flags = nutrients_from_amounts(amounts[key])
        extracts.append(
            StapleExtract(
                fdc_id=staple.fdc_id,
                data_type=food["data_type"],
                description=food["description"],
                publication_date=food["publication_date"],
                per_100_g=values,
                quality_flags=flags,
                portion=portion,
            )
        )
    return StapleExtractFile(
        schema_version="usda-staples-extract.v1",
        spec_sha=spec_digest(spec),
        staples=tuple(extracts),
    )


def staple_dish(spec: StapleSpec, data: StapleExtract) -> CatalogueRecipe:
    """A curated staple as a catalogue dish, with per-100 g USDA nutrition and portions."""
    if spec.fdc_id != data.fdc_id:
        raise ValueError("spec and extract describe different foods")
    dish = CatalogueRecipe(
        recipe_id=spec.dish_id,
        name=spec.name,
        ingredients=spec.ingredients,
        cuisines=spec.cuisines,
        diet_tags=spec.diet_tags,
        roles=spec.roles,
        dish_class=spec.dish_class,
        meal_types=spec.meal_types,
        classification_status=ClassificationStatus.CURATED,
        classification_evidence=(f"curated by {spec.curated_by}: {spec.rationale}",),
        nutrition=NutritionRecord(
            source=DATA_TYPE_SOURCES[data.data_type],
            basis=NutritionBasis.PER_100_G,
            values=data.per_100_g,
            source_reference=f"fdc:{data.fdc_id} {data.description} ({data.publication_date})",
            quality_flags=data.quality_flags,
        ),
        provenance=(
            f"USDA FoodData Central {data.data_type} fdc_id {data.fdc_id}",
            "exact identity, curated fdc_id list (ADR 0003 D1)",
            f"portion: {data.portion.label} = {data.portion.gram_weight:g} g "
            f"(food_portion id {data.portion.portion_id})",
        ),
    )
    portions = measured_portions(
        dish,
        spec.portion.unit,
        data.portion.grams_per_unit,
        spec.portion.allowed_quantities,
        spec.portion.standard_quantity,
    )
    return with_portions(dish, portions)


def load_spec(path: Path) -> StapleSpecFile:
    return StapleSpecFile.model_validate_json(path.read_text(encoding="utf-8"))


def load_extract(path: Path) -> StapleExtractFile:
    return StapleExtractFile.model_validate_json(path.read_text(encoding="utf-8"))


def staple_dishes(spec: StapleSpecFile, data: StapleExtractFile) -> tuple[CatalogueRecipe, ...]:
    """Join spec and extract; a stale extract (spec edited since) is an error."""
    if data.spec_sha != spec_digest(spec):
        raise ValueError("usda_staples_extract.json is stale: re-run the extraction")
    by_id = {e.fdc_id: e for e in data.staples}
    return tuple(staple_dish(s, by_id[s.fdc_id]) for s in spec.staples)


def _dump(data: StapleExtractFile) -> str:
    return json.dumps(data.model_dump(mode="json", by_alias=True), indent=2) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--usda-dir", type=Path, default=Path("Data/USDA"))
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output", type=Path, default=DEFAULT_EXTRACT)
    parser.add_argument("--check", action="store_true", help="fail if the extract is stale")
    args = parser.parse_args()
    text = _dump(extract(load_spec(args.spec), args.usda_dir))
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != text:
            print(f"{args.output} is stale; re-run without --check", file=sys.stderr)
            raise SystemExit(1)
        print(f"{args.output} is up to date")
        return
    args.output.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
