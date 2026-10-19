"""Member 2 review sample: every total is traceable to evidenced contributions."""

import json
from pathlib import Path

import pytest

from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.meal_composition.models import MealCombination
from savora_ai.core.meal_composition.review_export import (
    FOODCOM_FIELDS,
    build_review_sample,
    default_choice,
    nutrient_breakdown,
)

REPO = Path(__file__).parents[3]
EXPORT = REPO / "Data/catalogue"


def load() -> tuple[str, dict[str, CatalogueRecipe], list[MealCombination]]:
    path = sorted(EXPORT.glob("*_catalogue.json"))[-1]
    version = path.name.removesuffix("_catalogue.json")
    recipes = json.loads(path.read_text("utf-8"))["recipes"]
    combos = json.loads((EXPORT / f"{version}_combinations.json").read_text("utf-8"))
    dishes = {r["recipeId"]: CatalogueRecipe.model_validate_json(json.dumps(r)) for r in recipes}
    meals = [MealCombination.model_validate_json(json.dumps(c)) for c in combos["combinations"]]
    return version, dishes, meals


VERSION, DISHES, MEALS = load()
CHOSEN = default_choice(MEALS)


def sample() -> dict[str, object]:
    by_id = {m.combination_id: m for m in MEALS}
    fc = {c.dish_id for cid in CHOSEN for c in by_id[cid].components if c.dish_id.startswith("FC_")}
    fake_rows = {  # the raw CSV is not in CI; the shape is what matters here
        i: {
            "id": int(i[3:]),
            "name": "x",
            "nutrition": [1.0] * 7,
            "nutritionFields": list(FOODCOM_FIELDS),
        }
        for i in fc
    }
    usda = {int(d[5:]): {"fdcId": int(d[5:])} for d in DISHES if d.startswith("USDA_")}
    return build_review_sample(VERSION, DISHES, MEALS, CHOSEN, fake_rows, usda, "a" * 64, "b" * 64)


def test_default_choice_mixes_bases_and_templates() -> None:
    templates = {m.template_id for m in MEALS if m.combination_id in CHOSEN}
    assert templates == {"MAIN_STAPLE_VEGETABLE", "ONE_DISH", "BREAKFAST_FRUIT"}
    dishes = {c.dish_id for m in MEALS if m.combination_id in CHOSEN for c in m.components}
    assert any(d.startswith("USDA_") for d in dishes) and any(d.startswith("FC_") for d in dishes)


def test_every_total_equals_the_sum_of_its_evidenced_contributions() -> None:
    for meal in MEALS[:40]:
        for config in meal.configurations:
            for key, entry in nutrient_breakdown(config, DISHES).items():
                parts = entry["contributions"]  # type: ignore[index]
                for part in parts:
                    if part["known"]:
                        assert part["value"] == pytest.approx(
                            part["valuePerBasis"] * part["factor"], abs=0.01
                        )
                if entry["known"]:  # type: ignore[index]
                    total = sum(p["value"] for p in parts)
                    assert entry["value"] == pytest.approx(total, abs=0.01), key  # type: ignore[index]
                else:
                    assert entry["value"] is None and "unknown for" in entry["reason"]  # type: ignore[index]


def test_sample_carries_ids_unknowns_status_and_shortlists() -> None:
    data = sample()
    assert data["environment"].startswith("REVIEW_SAMPLE")  # type: ignore[union-attr]
    assert "SYNTHETIC" not in json.dumps(data)  # real data is never labelled synthetic
    meals = data["meals"]
    assert isinstance(meals, list) and len(meals) == 3
    for meal in meals:
        for config in meal["configurations"]:
            assert (
                config["optionId"] == f"{meal['combinationId']}:{config['portionConfigurationId']}"
            )
            assert "#" not in config["optionId"]
            sugar = config["nutrients"]["sugarsG"]
            assert sugar["value"] is None and sugar["known"] is False  # Food.com sugar unknown
            for q in config["componentQuantities"]:
                assert (q["grams"] is None) == (q["member2QuantityUnit"] == "serving")
    shortlists = data["slotShortlists"]
    assert isinstance(shortlists, dict)
    assert all(len(shortlists[m]) <= 8 for m in ("BREAKFAST", "LUNCH", "DINNER"))
    assert set(data["fieldStatus"].values()) >= {"EXISTING", "ADAPTER_REQUIRED"}  # type: ignore[union-attr]
