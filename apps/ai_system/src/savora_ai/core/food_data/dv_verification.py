"""Verify the Food.com %DV conversion against USDA, independently of serving mass.

Question (Member 2, 20 Oct 2026): do the DV factors we use (FDA 1993: sodium 2,400 mg,
saturated fat 20 g, ...) match THIS Food.com export? The energy ratio only tests fat,
carbohydrate and protein together, and says nothing about sodium or saturated fat.

Method. Food.com has recipes made of ONE food (e.g. "bacon", "sweetened condensed milk",
"eggs" + water). For such a recipe, nutrient per kcal is a property of the food and does
NOT depend on the serving mass, which Food.com never gives:

    Food.com:  (pdv / 100 * DV) / kcal          e.g. sodium mg per 100 kcal
    USDA:      nutrient per 100 g / kcal per 100 g

If a DV table is right, the two agree within the error from rounding %DV to an integer
(+/- 0.5 %DV, i.e. a relative error of 0.5 / pdv). Recipes whose %DV is below
MIN_PDV are skipped, because rounding alone would dominate. Results per food are
medians over all matching recipes. Non-food ingredients (water) are ignored.

Usage (from the repo root; reads the 1.6 GB USDA nutrient file once, about 40 s):
    uv run python -m savora_ai.core.food_data.dv_verification
"""

import argparse
import ast
import csv
import json
import statistics
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from savora_ai.core.food_data.models import DvReference
from savora_ai.core.food_data.nutrition_convert import FDA_1993, FDA_2016

WATER = frozenset({"water", "boiling water", "cold water", "hot water", "ice water"})
MIN_PDV = 5.0  # below this, integer rounding of %DV alone exceeds +/- 10%
# A nutrient the food barely contains (e.g. sodium in raw almonds, 1 mg per 579 kcal) is
# dominated by anything a recipe adds (salt), so it is not compared for that food.
MIN_USDA_PER_100_KCAL: dict[str, float] = {"sodium_mg": 20.0}

# Food.com nutrition order: [kcal, fat, sugar, sodium, protein, saturated fat, carbs] (%DV)
_INDEX = {
    "fat_g": 1,
    "sugars_g": 2,
    "sodium_mg": 3,
    "protein_g": 4,
    "saturated_fat_g": 5,
    "carbohydrate_g": 6,
}
_USDA_IDS = {
    1008: "energy_kcal",
    1004: "fat_g",
    1258: "saturated_fat_g",
    1005: "carbohydrate_g",
    1003: "protein_g",
    1093: "sodium_mg",
    2000: "sugars_g",
}
# Candidate sugar daily values: none is documented by the dataset, so both are tested.
SUGAR_CANDIDATES_G = (25.0, 50.0)


@dataclass(frozen=True)
class VerificationFood:
    name: str
    ingredients: frozenset[str]  # Food.com single-ingredient names that mean this food
    fdc_id: int  # the USDA SR Legacy record for the RAW ingredient
    fdc_description: str  # identity guard


# Raw ingredients: Food.com computes recipe nutrition from its ingredients as purchased,
# so the comparison uses the uncooked USDA record (e.g. bacon "unprepared").
FOODS: tuple[VerificationFood, ...] = (
    VerificationFood("bacon", frozenset({"bacon"}), 168277, "Pork, cured, bacon, unprepared"),
    VerificationFood(
        "sweetened condensed milk",
        frozenset({"sweetened condensed milk"}),
        171275,
        "Milk, canned, condensed, sweetened",
    ),
    VerificationFood(
        "heavy cream",
        frozenset({"heavy cream", "heavy whipping cream"}),
        170859,
        "Cream, fluid, heavy whipping",
    ),
    VerificationFood("eggs", frozenset({"egg", "eggs"}), 171287, "Egg, whole, raw, fresh"),
    VerificationFood("almonds", frozenset({"almonds"}), 170567, "Nuts, almonds"),
    VerificationFood(
        "fresh coconut", frozenset({"fresh coconut"}), 170169, "Nuts, coconut meat, raw"
    ),
    VerificationFood("quinoa", frozenset({"quinoa"}), 168874, "Quinoa, uncooked"),
    VerificationFood(
        "white sugar",
        frozenset({"sugar", "white sugar", "granulated sugar"}),
        169655,
        "Sugars, granulated",
    ),
    VerificationFood(
        "grapes",
        frozenset({"grapes", "red seedless grapes", "green grapes", "seedless grapes"}),
        174683,
        "Grapes, red or green (European type, such as Thompson seedless), raw",
    ),
    VerificationFood(
        "apples",
        frozenset({"apples", "apple"}),
        171688,
        "Apples, raw, with skin (Includes foods for USDA's Food Distribution Program)",
    ),
)


def per_100_kcal_foodcom(
    nutrition: Sequence[float], nutrient: str, reference: Mapping[str, float]
) -> float | None:
    """Nutrient per 100 kcal from one Food.com vector; None if too small to trust."""
    kcal, pdv = nutrition[0], nutrition[_INDEX[nutrient]]
    if kcal <= 0 or pdv < MIN_PDV:
        return None
    return pdv / 100.0 * reference[nutrient] / kcal * 100.0


def reference_amounts(table: DvReference, sugar_g: float) -> dict[str, float]:
    return {
        "fat_g": table.fat_g,
        "saturated_fat_g": table.saturated_fat_g,
        "carbohydrate_g": table.carbohydrate_g,
        "protein_g": table.protein_g,
        "sodium_mg": table.sodium_mg,
        "sugars_g": sugar_g,
    }


def single_ingredient_recipes(
    rows: Iterable[Mapping[str, str]], foods: Sequence[VerificationFood] = FOODS
) -> dict[str, list[tuple[str, list[float]]]]:
    """food name -> [(recipe id, nutrition)] for recipes made of exactly that one food."""
    by_ingredient = {i: f.name for f in foods for i in f.ingredients}
    found: dict[str, list[tuple[str, list[float]]]] = {f.name: [] for f in foods}
    for row in rows:
        try:
            ingredients = [x.strip().lower() for x in ast.literal_eval(row["ingredients"])]
            nutrition = [float(x) for x in ast.literal_eval(row["nutrition"])]
        except (ValueError, SyntaxError):
            continue
        core = [i for i in ingredients if i not in WATER]
        if len(core) == 1 and core[0] in by_ingredient and len(nutrition) == 7:
            found[by_ingredient[core[0]]].append((f"FC_{row['id']}", nutrition))
    return found


def usda_per_100_kcal(amounts: Mapping[str, float]) -> dict[str, float]:
    kcal = amounts["energy_kcal"]
    return {k: v / kcal * 100.0 for k, v in amounts.items() if k != "energy_kcal"}


def compare_food(
    recipes: Sequence[tuple[str, list[float]]], usda: Mapping[str, float]
) -> dict[str, object]:
    """Median Food.com/USDA ratio per nutrient and table; 1.0 means exact agreement."""
    target = usda_per_100_kcal(usda)
    tables = {
        "FDA_1993": reference_amounts(FDA_1993, 25.0),
        "FDA_2016": reference_amounts(FDA_2016, 25.0),
        **{f"sugar_dv_{g:g}g": reference_amounts(FDA_1993, g) for g in SUGAR_CANDIDATES_G},
    }
    out: dict[str, object] = {"recipes": len(recipes), "usdaPer100Kcal": target}
    ratios: dict[str, dict[str, object]] = {}
    for nutrient in _INDEX:
        if target.get(nutrient, 0.0) <= MIN_USDA_PER_100_KCAL.get(nutrient, 0.0):
            continue
        names = (
            [f"sugar_dv_{g:g}g" for g in SUGAR_CANDIDATES_G]
            if nutrient == "sugars_g"
            else ["FDA_1993", "FDA_2016"]
        )
        row: dict[str, object] = {}
        for name in names:
            values = [
                v / target[nutrient]
                for _, n in recipes
                if (v := per_100_kcal_foodcom(n, nutrient, tables[name])) is not None
            ]
            if values:
                row[name] = {"medianRatio": round(statistics.median(values), 3), "n": len(values)}
        if row:
            ratios[nutrient] = row
    out["foodcomToUsdaRatio"] = ratios
    return out


def load_usda(usda_dir: Path, foods: Sequence[VerificationFood]) -> dict[int, dict[str, float]]:
    wanted = {str(f.fdc_id): f for f in foods}
    with (usda_dir / "food.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            food = wanted.get(row["fdc_id"])
            if food is not None and row["description"] != food.fdc_description:
                raise ValueError(f"fdc {row['fdc_id']} is {row['description']!r}")
    amounts: dict[int, dict[str, float]] = {f.fdc_id: {} for f in foods}
    with (usda_dir / "food_nutrient.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["fdc_id"] in wanted:
                key = _USDA_IDS.get(int(row["nutrient_id"]))
                if key is not None:
                    amounts[int(row["fdc_id"])][key] = float(row["amount"])
    return amounts


def run(recipes_path: Path, usda_dir: Path) -> dict[str, object]:
    csv.field_size_limit(sys.maxsize)
    with recipes_path.open(encoding="utf-8", newline="") as stream:
        found = single_ingredient_recipes(csv.DictReader(stream))
    usda = load_usda(usda_dir, FOODS)
    foods = {
        f.name: {
            "fdcId": f.fdc_id,
            "usdaDescription": f.fdc_description,
            "recipeIds": [r for r, _ in found[f.name]],
            **compare_food(found[f.name], usda[f.fdc_id]),
        }
        for f in FOODS
        if found[f.name]
    }
    return {
        "method": "nutrient per 100 kcal, Food.com single-ingredient recipes vs USDA SR Legacy raw "
        "food; median over recipes; %DV below " + f"{MIN_PDV:g} skipped (rounding)",
        "tables": {
            "FDA_1993": FDA_1993.model_dump(),
            "FDA_2016": FDA_2016.model_dump(),
            "sugarCandidatesG": list(SUGAR_CANDIDATES_G),
        },
        "foods": foods,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipes", type=Path, default=Path("Data/Food.com/RAW_recipes.csv"))
    parser.add_argument("--usda-dir", type=Path, default=Path("Data/USDA"))
    parser.add_argument("--output", type=Path, default=Path("docs/eval/dv_verification.json"))
    args = parser.parse_args()
    report = run(args.recipes, args.usda_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
