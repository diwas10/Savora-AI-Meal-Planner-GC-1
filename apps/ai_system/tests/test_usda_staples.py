"""Stage 3: curated USDA staples, exact identities, unknown-vs-zero and stale extracts."""

import csv
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from savora_ai.core.food_data.models import NutrientVector
from savora_ai.core.food_data.nutrition_convert import energy_ratio, scale
from savora_ai.core.food_data.usda_staples import (
    StapleSpecFile,
    extract,
    load_extract,
    load_spec,
    nutrients_from_amounts,
    parse_portion,
    spec_digest,
    staple_dishes,
)
from savora_ai.schemas.enums import ClassificationStatus, NutritionBasis, NutritionSource

REPO = Path(__file__).parents[3]
SPEC = REPO / "Data/curated/usda_staples.json"
EXTRACT = REPO / "Data/curated/usda_staples_extract.json"

ROTI_SPEC = {
    "schemaVersion": "usda-staples.v1",
    "note": "test",
    "staples": [
        {
            "dishId": "USDA_7",
            "fdcId": 7,
            "name": "roti",
            "expectedDescription": "Bread, chappatti or roti",
            "roles": ["STAPLE"],
            "dishClass": "COMPONENT",
            "mealTypes": ["LUNCH", "DINNER"],
            "cuisines": ["Indian"],
            "dietTags": ["vegan"],
            "ingredients": ["whole wheat flour"],
            "portion": {
                "unit": "PIECE",
                "usdaPortionId": 70,
                "allowedQuantities": [1.0, 2.0],
                "standardQuantity": 2.0,
            },
            "rationale": "test",
            "curatedBy": "tester",
        }
    ],
}


def roti_spec(**portion: object) -> StapleSpecFile:
    data = json.loads(json.dumps(ROTI_SPEC))
    data["staples"][0]["portion"].update(portion)
    return StapleSpecFile.model_validate_json(json.dumps(data))


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, quoting=csv.QUOTE_ALL)
        writer.writerow(header)
        writer.writerows(rows)


def fake_usda(tmp_path: Path, *, description: str = "Bread, chappatti or roti") -> Path:
    write_csv(
        tmp_path / "food.csv",
        ["fdc_id", "data_type", "description", "food_category_id", "publication_date"],
        [["7", "survey_fndds_food", description, "1", "2024-10-31"]],
    )
    write_csv(
        tmp_path / "food_nutrient.csv",
        ["id", "fdc_id", "nutrient_id", "amount"],
        [
            ["1", "7", "1008", "299.0"],
            ["2", "7", "1003", "7.85"],
            ["3", "7", "1004", "9.2"],
            ["4", "7", "1005", "-0.3"],  # carbohydrate by difference below zero
            ["5", "7", "1093", "298.0"],
            ["6", "8", "1008", "999.0"],  # another food: ignored
        ],
    )
    write_csv(
        tmp_path / "food_portion.csv",
        ["id", "fdc_id", "seq_num", "amount", "portion_description", "modifier", "gram_weight"],
        [
            ["70", "7", "1", "", '1 medium chappatti or roti (7")', "61316", "40.0"],
            ["71", "8", "1", "1.0", "", "cup", "158.0"],
        ],
    )
    return tmp_path


# --- unknown is never zero ----------------------------------------------------------


def test_missing_usda_nutrients_stay_unknown_and_are_flagged() -> None:
    values, flags = nutrients_from_amounts({1008: 130.0, 1003: 2.7})
    assert values.energy_kcal == 130.0 and values.protein_g == 2.7
    assert values.sodium_mg is None and values.saturated_fat_g is None  # not 0
    assert any("unknown in USDA" in flag for flag in flags)


def test_negative_value_is_flagged_not_clamped() -> None:
    values, flags = nutrients_from_amounts({1005: -0.3})
    assert values.carbohydrate_g is None
    assert any("carbohydrate_g reported as -0.3" in flag for flag in flags)


def test_scaling_keeps_unknown_unknown() -> None:
    half = scale(NutrientVector(energy_kcal=100.0, sodium_mg=None), 0.5)
    assert half.energy_kcal == 50.0 and half.sodium_mg is None
    with pytest.raises(ValueError):
        scale(NutrientVector(), -1.0)


def test_energy_ratio_needs_every_macro() -> None:
    assert energy_ratio(NutrientVector(energy_kcal=100.0, fat_g=1.0)) is None


# --- portions -----------------------------------------------------------------------


def test_fndds_and_sr_legacy_portions_reduce_to_grams_per_unit() -> None:
    fndds = parse_portion(
        {
            "id": "1",
            "amount": "",
            "portion_description": "1 egg",
            "modifier": "x",
            "gram_weight": "50",
        }
    )
    assert fndds.label == "1 egg" and fndds.grams_per_unit == 50.0
    legacy = parse_portion(
        {
            "id": "2",
            "amount": "0.5",
            "portion_description": "",
            "modifier": "cup, chopped",
            "gram_weight": "78",
        }
    )
    assert legacy.label == "0.5 cup, chopped" and legacy.grams_per_unit == 156.0


@pytest.mark.parametrize(
    "portion",
    [
        {"standardQuantity": 3.0},  # not an allowed quantity
        {"allowedQuantities": [2.0, 1.0]},  # not increasing
        {"allowedQuantities": [1.0]},  # a single option is no choice
    ],
)
def test_bad_portion_specs_are_rejected(portion: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        roti_spec(**portion)


def test_dish_id_must_follow_the_fdc_id() -> None:
    data = json.loads(json.dumps(ROTI_SPEC))
    data["staples"][0]["dishId"] = "USDA_8"
    with pytest.raises(ValidationError):
        StapleSpecFile.model_validate_json(json.dumps(data))


# --- extraction ---------------------------------------------------------------------


def test_extraction_reads_only_the_curated_food(tmp_path: Path) -> None:
    data = extract(roti_spec(), fake_usda(tmp_path))
    [roti] = data.staples
    assert roti.per_100_g.energy_kcal == 299.0  # food 8's 999 kcal is ignored
    assert roti.per_100_g.carbohydrate_g is None  # negative -> unknown, flagged
    assert roti.portion.grams_per_unit == 40.0 and roti.portion.portion_id == 70
    assert data.spec_sha == spec_digest(roti_spec())


def test_extraction_refuses_a_different_food(tmp_path: Path) -> None:
    usda = fake_usda(tmp_path, description="Bread, naan")
    with pytest.raises(ValueError, match="not 'Bread, chappatti or roti'"):
        extract(roti_spec(), usda)


def test_extraction_refuses_a_portion_of_another_food(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no food_portion row 71"):
        extract(roti_spec(usdaPortionId=71), fake_usda(tmp_path))


def test_stale_extract_is_detected(tmp_path: Path) -> None:
    data = extract(roti_spec(), fake_usda(tmp_path))
    with pytest.raises(ValueError, match="stale"):
        staple_dishes(roti_spec(standardQuantity=1.0), data)


# --- the committed curated files ----------------------------------------------------


def test_committed_extract_matches_the_committed_spec() -> None:
    dishes = staple_dishes(load_spec(SPEC), load_extract(EXTRACT))
    assert len(dishes) == len(load_spec(SPEC).staples)
    for dish in dishes:
        assert dish.recipe_id.startswith("USDA_")
        assert dish.classification_status is ClassificationStatus.CURATED
        assert dish.nutrition.basis is NutritionBasis.PER_100_G
        assert dish.nutrition.source in {
            NutritionSource.USDA_FNDDS,
            NutritionSource.USDA_SR_LEGACY,
            NutritionSource.USDA_FOUNDATION,
        }
        assert dish.nutrition.values.energy_kcal is not None


def test_plain_rice_is_the_unsalted_identity() -> None:
    # The FNDDS "cooked" record assumes salted water (~245 mg/100 g); Asian steamed rice
    # is unsalted, so the curated identity is SR Legacy "cooked without salt".
    by_name = {d.name: d for d in staple_dishes(load_spec(SPEC), load_extract(EXTRACT))}
    rice = by_name["steamed white rice"].nutrition.values
    assert rice.sodium_mg is not None and rice.sodium_mg < 10
