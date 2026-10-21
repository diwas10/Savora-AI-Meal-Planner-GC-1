"""Review sample for Member 2 (requested 20 Oct 2026): a few meals, fully evidenced.

For each chosen meal and every portion preset it writes the ABSOLUTE nutrient vector,
and for every nutrient: value, unit, known/unknown, and the contribution of each
component (source, basis, value per basis, multiplication factor), so each number can be
traced to an original record. Original source records are included: the raw Food.com
nutrition row with the file checksum, and the raw USDA record with its portion row.

This is REAL catalogue data in Member 1's own format, labelled REVIEW_SAMPLE. It is not
Member 2's synthetic DTOs and claims no production or clinical approval. Field status
follows Member 2's legend: EXISTING (in the export today), ADAPTER_REQUIRED (needs a
Member 2 adapter), PROPOSED (needs team approval).

Usage (from the repo root; needs RAW_recipes.csv for the original rows):
    uv run python -m savora_ai.core.meal_composition.review_export
"""

import argparse
import ast
import csv
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from savora_ai.core.food_data.models import NUTRIENT_FIELDS, CatalogueRecipe
from savora_ai.core.food_data.nutrition_convert import DV_REFERENCES
from savora_ai.core.food_data.usda_staples import DEFAULT_EXTRACT, load_extract
from savora_ai.core.meal_composition.models import MealCombination, PortionConfiguration
from savora_ai.core.recommendation.ranking import (
    PopularityScorer,
    RankingContext,
    rank_combinations,
)
from savora_ai.core.recommendation.shortlist import shortlist_day
from savora_ai.schemas.enums import MealType, NutritionBasis, PortionUnit

SAMPLE_VERSION = "member1-review-sample.v1"
UNITS = {"energy_kcal": "kcal", "sodium_mg": "mg"}  # every other nutrient is in g
WIRE = {
    "energy_kcal": "energyKcal",
    "fat_g": "fatG",
    "saturated_fat_g": "saturatedFatG",
    "carbohydrate_g": "carbohydrateG",
    "protein_g": "proteinG",
    "sodium_mg": "sodiumMg",
    "sugars_g": "sugarsG",
}
FOODCOM_FIELDS = (
    "calories (kcal)",
    "total fat (%DV)",
    "sugar (%DV)",
    "sodium (%DV)",
    "protein (%DV)",
    "saturated fat (%DV)",
    "carbohydrates (%DV)",
)
FIELD_STATUS = {
    "combinationId, templateId, components, roles": "EXISTING",
    "portionConfigurationId (preset), configurationVersion": "EXISTING",
    "optionId <combinationId>:<PRESET>": "EXISTING (Member 2 opaque-ID pattern)",
    "component quantity + unit + grams/null": "EXISTING",
    "per-nutrient absolute totals with contributions": "EXISTING",
    "per-nutrient known flag (null = unknown, never zero)": "EXISTING",
    "original Food.com row, file SHA-256, DV table": "EXISTING",
    "original USDA record, fdc_id, portion row": "EXISTING",
    "meal-type suitability with classification evidence": "EXISTING",
    "seven-nutrient vector in Member 2 FixedMealMeasurement": "ADAPTER_REQUIRED",
    "canonical ingredient mapping, subingredients, allergen status": (
        "PROPOSED (not mapped: UNKNOWN)"
    ),
    "rule-specific source admission policy": "PROPOSED (Member 2)",
    "sugar from Food.com %DV (25 g reference, verified)": "PROPOSED (kept null until approved)",
}


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def content_sha256(data: object) -> str:
    text = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def foodcom_rows(path: Path, ids: set[str]) -> dict[str, dict[str, object]]:
    """The original rows for `ids` ("FC_<id>"), as stored in RAW_recipes.csv."""
    csv.field_size_limit(sys.maxsize)
    wanted = {i.removeprefix("FC_") for i in ids}
    rows: dict[str, dict[str, object]] = {}
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["id"] in wanted:
                values = ast.literal_eval(row["nutrition"])
                rows[f"FC_{row['id']}"] = {
                    "id": int(row["id"]),
                    "name": row["name"],
                    "nutrition": values,
                    "nutritionFields": list(FOODCOM_FIELDS),
                    "ingredients": ast.literal_eval(row["ingredients"]),
                    "tags": ast.literal_eval(row["tags"]),
                }
    missing = sorted(ids - set(rows))
    if missing:
        raise ValueError(f"original rows not found: {missing}")
    return rows


def _factor(dish: CatalogueRecipe, quantity: float, grams: float | None) -> float:
    if dish.nutrition.basis is NutritionBasis.PER_SERVING:
        return quantity  # servings of the per-serving record
    if grams is None:
        raise ValueError(f"{dish.recipe_id}: per-100 g record without grams")
    return grams / 100.0


def nutrient_breakdown(
    configuration: PortionConfiguration, dishes: Mapping[str, CatalogueRecipe]
) -> dict[str, object]:
    """Per nutrient: total, unit, known flag and every component's contribution."""
    if configuration.nutrition is None:
        raise ValueError("only validated configurations (Stage 9) can be exported")
    totals = configuration.nutrition.totals
    out: dict[str, object] = {}
    for name in NUTRIENT_FIELDS:
        contributions = []
        for portion in configuration.portions:
            dish = dishes[portion.dish_id]
            option = next(o for o in dish.portions if o.portion_id == portion.portion_id)
            per_basis = getattr(dish.nutrition.values, name)
            contributions.append(
                {
                    "dishId": dish.recipe_id,
                    "portionId": portion.portion_id,
                    "value": getattr(option.nutrients, name),
                    "known": getattr(option.nutrients, name) is not None,
                    "source": dish.nutrition.source.value,
                    "basis": dish.nutrition.basis.value,
                    "valuePerBasis": per_basis,
                    "factor": round(_factor(dish, portion.quantity, portion.grams), 6),
                    "sourceReference": dish.nutrition.source_reference,
                }
            )
        value = getattr(totals, name)
        entry: dict[str, object] = {
            "value": value,
            "unit": UNITS.get(name, "g"),
            "known": value is not None,
            "contributions": contributions,
        }
        if value is None:
            unknown = [c["dishId"] for c in contributions if not c["known"]]
            entry["reason"] = (
                f"unknown for {unknown}; one unknown component makes the total unknown"
            )
        out[WIRE[name]] = entry
    return out


def _component(
    dish: CatalogueRecipe,
    slot: str,
    role: str,
    foodcom: Mapping[str, Mapping[str, object]],
    usda: Mapping[int, Mapping[str, object]],
    raw_sha: str,
    extract_sha: str,
) -> dict[str, object]:
    nutrition = dish.nutrition
    if dish.recipe_id.startswith("FC_"):
        table = DV_REFERENCES[nutrition.source_reference]
        original: dict[str, object] = {
            "dataset": "Food.com Recipes and Interactions (Majumder et al., EMNLP 2019)",
            "file": "RAW_recipes.csv",
            "fileSha256": raw_sha,
            "row": foodcom[dish.recipe_id],
            "conversion": {
                "table": table.name,
                "gramsAt100PercentDv": table.model_dump(exclude={"name"}),
                "rule": "grams = %DV / 100 x reference; kcal as stated; sugar left null",
                "verification": "docs/eval/dv_verification.json",
            },
        }
    else:
        fdc = int(dish.recipe_id.removeprefix("USDA_"))
        original = {"dataset": "USDA FoodData Central", "extractSha256": extract_sha, **usda[fdc]}
    return {
        "slot": slot,
        "role": role,
        "dishId": dish.recipe_id,
        "name": dish.name,
        "cuisines": list(dish.cuisines),
        "dishClass": str(dish.dish_class),
        "mealTypes": [m.value for m in dish.meal_types],
        "classificationStatus": dish.classification_status.value,
        "classificationEvidence": list(dish.classification_evidence),
        "ingredients": list(dish.ingredients),
        "ingredientMapping": {
            "status": "UNRESOLVED",
            "canonicalIngredients": None,
            "subingredientsKnown": False,
            "allergenStatus": "UNKNOWN",
            "note": "raw names only; no canonical mapping exists yet, so allergen rules "
            "cannot PASS (fail closed)",
        },
        "dietTags": {"values": list(dish.diet_tags), "status": "UNVERIFIED_METADATA"},
        "nutritionRecord": {
            "source": nutrition.source.value,
            "basis": nutrition.basis.value,
            "valuesPerBasis": nutrition.values.model_dump(mode="json", by_alias=True),
            "sourceReference": nutrition.source_reference,
            "qualityFlags": list(nutrition.quality_flags),
        },
        "portionOptions": [p.model_dump(mode="json", by_alias=True) for p in dish.portions],
        "servingMassG": dish.serving_mass_g,
        "originalSourceRecord": original,
    }


def build_review_sample(
    version: str,
    dishes: Mapping[str, CatalogueRecipe],
    combinations: Sequence[MealCombination],
    chosen: Sequence[str],
    foodcom: Mapping[str, Mapping[str, object]],
    usda: Mapping[int, Mapping[str, object]],
    raw_sha: str,
    extract_sha: str,
) -> dict[str, object]:
    by_id = {c.combination_id: c for c in combinations}
    meals = []
    for cid in chosen:
        combo = by_id[cid]
        meals.append(
            {
                "combinationId": combo.combination_id,
                "combinationVersion": version,
                "combinationContentSha256": content_sha256(
                    combo.model_dump(mode="json", by_alias=True)
                ),
                "templateId": combo.template_id,
                "mealTypes": [m.value for m in combo.meal_types],
                "cuisines": list(combo.cuisines),
                "compositionEvidence": list(combo.evidence),
                "components": [
                    _component(
                        dishes[c.dish_id], c.slot, c.role.value, foodcom, usda, raw_sha, extract_sha
                    )
                    for c in combo.components
                ],
                "configurations": [
                    {
                        "optionId": config.configuration_id.replace("#", ":"),
                        "portionConfigurationId": config.preset.value,
                        "configurationVersion": version,
                        "portionState": "FIXED",
                        "componentQuantities": [
                            {
                                "dishId": p.dish_id,
                                "portionId": p.portion_id,
                                "quantity": p.quantity,
                                "unit": p.unit.value,
                                "grams": p.grams,
                                "massKnown": p.grams is not None,
                                "member2QuantityUnit": "serving"
                                if p.unit is PortionUnit.SERVING
                                else "g",
                            }
                            for p in config.portions
                        ],
                        "nutrients": nutrient_breakdown(config, dishes),
                        "sourceTier": config.nutrition.source_tier.value
                        if config.nutrition
                        else None,
                        "fullyKnownForRequiredNutrients": bool(
                            config.nutrition and config.nutrition.fully_known
                        ),
                    }
                    for config in combo.configurations
                ],
            }
        )
    rankings = {
        meal: rank_combinations(
            [],
            [c.combination_id for c in combinations if meal in c.meal_types],
            RankingContext(slot_id=f"D1_{meal.value}"),
            scorer=None,
            fallback=PopularityScorer({d: r.training_interactions or 0 for d, r in dishes.items()}),
        )
        for meal in MealType
    }
    shortlists = shortlist_day(rankings, by_id)
    return {
        "sampleVersion": SAMPLE_VERSION,
        "environment": (
            "REVIEW_SAMPLE (real catalogue data; not production- or clinically-approved)"
        ),
        "catalogueVersion": version,
        "fieldStatus": FIELD_STATUS,
        "nutrientKeys": {
            WIRE[n]: {"pythonKey": n, "unit": UNITS.get(n, "g")} for n in NUTRIENT_FIELDS
        },
        "missingValueRule": "null = unknown, never zero; known=false; a meal total is null if "
        "any component is null",
        "meals": meals,
        "slotShortlists": {
            "protocol": "popularity ranking (no user history, so fallback "
            f"{rankings[MealType.LUNCH].fallback_reason}); top 2 meals x first 4 presets",
            **{meal.value: [o.option_id for o in s.options] for meal, s in shortlists.items()},
        },
    }


def _usda_records(extract_path: Path) -> dict[int, dict[str, object]]:
    data = load_extract(extract_path)
    return {
        s.fdc_id: {
            "fdcId": s.fdc_id,
            "dataType": s.data_type,
            "description": s.description,
            "publicationDate": s.publication_date,
            "per100G": s.per_100_g.model_dump(mode="json", by_alias=True),
            "portion": s.portion.model_dump(mode="json", by_alias=True),
            "qualityFlags": list(s.quality_flags),
        }
        for s in data.staples
    }


def default_choice(combinations: Sequence[MealCombination]) -> list[str]:
    """3 meals with 4+ presets: a 3-dish Indian lunch with USDA staple and vegetable, a
    Nepali one-dish meal, and an Indian breakfast with a USDA fruit."""

    def has_four(c: MealCombination) -> bool:
        return len(c.configurations) >= 4

    picks = []
    for template, cuisine in (
        ("MAIN_STAPLE_VEGETABLE", "Indian"),
        ("ONE_DISH", "Nepali"),
        ("BREAKFAST_FRUIT", "Indian"),
    ):
        picks.append(
            next(
                c.combination_id
                for c in combinations
                if c.template_id == template and cuisine in c.cuisines and has_four(c)
            )
        )
    return picks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue-dir", type=Path, default=Path("Data/catalogue"))
    parser.add_argument("--recipes", type=Path, default=Path("Data/Food.com/RAW_recipes.csv"))
    parser.add_argument("--staples-extract", type=Path, default=DEFAULT_EXTRACT)
    parser.add_argument(
        "--output", type=Path, default=Path("docs/member2/member1_review_sample.json")
    )
    parser.add_argument("--combination", action="append", default=None)
    args = parser.parse_args()
    path = sorted(args.catalogue_dir.glob("*_catalogue.json"))[-1]
    version = path.name.removesuffix("_catalogue.json")
    catalogue = json.loads(path.read_text(encoding="utf-8"))
    combos_raw = json.loads(
        (args.catalogue_dir / f"{version}_combinations.json").read_text(encoding="utf-8")
    )
    dishes = {
        r["recipeId"]: CatalogueRecipe.model_validate_json(json.dumps(r))
        for r in catalogue["recipes"]
    }
    combinations = [
        MealCombination.model_validate_json(json.dumps(c)) for c in combos_raw["combinations"]
    ]
    chosen = args.combination or default_choice(combinations)
    by_id = {c.combination_id: c for c in combinations}
    fc_ids = {
        d.dish_id for cid in chosen for d in by_id[cid].components if d.dish_id.startswith("FC_")
    }
    sample = build_review_sample(
        version,
        dishes,
        combinations,
        chosen,
        foodcom_rows(args.recipes, fc_ids),
        _usda_records(args.staples_extract),
        catalogue["source"]["sha256"],
        file_sha256(args.staples_extract),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(sample, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.output} ({len(chosen)} meals)")


if __name__ == "__main__":
    main()
