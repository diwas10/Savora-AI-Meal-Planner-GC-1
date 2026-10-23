"""Stage 6: curated cuisines (Nepali), the pairing list and their validation."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from savora_ai.core.food_data.classification import (
    ClassificationOverride,
    ClassificationOverrideFile,
    check_cuisines,
)
from savora_ai.core.food_data.selection import TARGET_CUISINES
from savora_ai.core.food_data.usda_staples import load_extract, load_spec, staple_dishes
from savora_ai.core.meal_composition.pairings import (
    PairingFile,
    load_pairings,
    validate_pairings,
)

REPO = Path(__file__).parents[3]
PAIRINGS = REPO / "Data/curated/pairings.json"
OVERRIDES = REPO / "Data/curated/classification_overrides.json"


def staples():
    spec = load_spec(REPO / "Data/curated/usda_staples.json")
    return staple_dishes(spec, load_extract(REPO / "Data/curated/usda_staples_extract.json"))


def pairing_file(**cuisine: object) -> PairingFile:
    data = json.loads(PAIRINGS.read_text(encoding="utf-8"))
    data["cuisines"] = [data["cuisines"][0] | cuisine]
    return PairingFile.model_validate_json(json.dumps(data))


def test_committed_pairings_are_valid_for_the_committed_staples() -> None:
    pairings = load_pairings(PAIRINGS)
    validate_pairings(pairings, staples())
    by_cuisine = pairings.staples_by_cuisine()
    assert set(TARGET_CUISINES) == set(by_cuisine)  # every target cuisine has staples
    assert "USDA_2707713" in by_cuisine["Nepali"]  # dal bhat with roti is allowed


@pytest.mark.parametrize(
    ("staple_id", "message"),
    [
        ("USDA_1", "unknown dish"),
        ("USDA_169967", "no STAPLE role"),  # broccoli is a vegetable
        ("USDA_169737", "not used in Indian"),  # pasta is curated for Italian only
    ],
)
def test_invalid_pairings_are_rejected(staple_id: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_pairings(pairing_file(staples=[staple_id]), staples())


def test_pairing_file_rejects_unknown_cuisines_and_duplicates() -> None:
    with pytest.raises(ValidationError):
        pairing_file(cuisine="Nepalese")  # a typo, not a known cuisine
    with pytest.raises(ValidationError):
        pairing_file(staples=["USDA_169757", "USDA_169757"])


def test_unknown_cuisine_names_are_rejected_everywhere() -> None:
    check_cuisines(("Nepali", "Indian"))
    with pytest.raises(ValueError):
        check_cuisines(("Nepalese",))
    with pytest.raises(ValidationError):
        ClassificationOverride(
            recipe_id="FC_1", cuisines=("Nepalese",), rationale="r", curated_by="c"
        )


def test_committed_overrides_include_reviewed_nepali_dishes() -> None:
    curated = ClassificationOverrideFile.model_validate_json(OVERRIDES.read_text("utf-8"))
    nepali = [o for o in curated.overrides if o.cuisines and "Nepali" in o.cuisines]
    assert len(nepali) >= 15
    ids = {o.recipe_id for o in nepali}
    assert "FC_533120" in ids  # dal bhat
    assert "FC_423471" not in ids  # bara brith is Welsh: a name-search false positive
