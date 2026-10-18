"""Tests for nutrition conversion, catalogue building and the deterministic selection."""

import csv
import json
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from savora_ai.core.food_data import build_catalogue
from savora_ai.core.food_data.build_catalogue import build, catalogue_version
from savora_ai.core.food_data.catalogue import (
    apply_serving_masses,
    build_recipe,
    parse_string_list,
)
from savora_ai.core.food_data.classification import ClassificationOverride
from savora_ai.core.food_data.models import CatalogueRecipe, QuarantinedRow, ServingMassOverride
from savora_ai.core.food_data.nutrition_convert import (
    FDA_1993,
    energy_ratio,
    parse_nutrition,
    per_100g,
    to_serving_nutrition,
)
from savora_ai.schemas.enums import (
    ClassificationStatus,
    CulinaryRole,
    DishClass,
    MealType,
    NutritionBasis,
    NutritionSource,
    QuarantineReason,
)

# [kcal, fat%, sugar%, sodium%, protein%, sat fat%, carbs%] -> 13 g fat, 60 g carbs, 10 g protein
GOOD_NUTRITION = [400.0, 20.0, 10.0, 10.0, 20.0, 10.0, 20.0]
GOOD_TAGS = ["main-dish", "indian", "vegetarian"]
GOOD_INGREDIENTS = ["lentils", "rice"]


def make(
    source_id: int = 1,
    *,
    name: str = "dal",
    tags: object = GOOD_TAGS,
    nutrition: object = GOOD_NUTRITION,
    ingredients: object = GOOD_INGREDIENTS,
) -> CatalogueRecipe | QuarantinedRow:
    return build_recipe(source_id, name, tags, nutrition, ingredients, FDA_1993)


def make_ok(source_id: int = 1, **kwargs: object) -> CatalogueRecipe:
    result = make(source_id, **kwargs)  # type: ignore[arg-type]
    assert isinstance(result, CatalogueRecipe)
    return result


def make_quarantined(source_id: int = 1, **kwargs: object) -> QuarantinedRow:
    result = make(source_id, **kwargs)  # type: ignore[arg-type]
    assert isinstance(result, QuarantinedRow)
    return result


# --- parsing and conversion ---------------------------------------------------------


def test_parse_nutrition_accepts_text_and_lists() -> None:
    assert parse_nutrition("[51.5, 0.0, 13.0, 0.0, 2.0, 0.0, 4.0]")[0] == 51.5
    assert parse_nutrition([1, 2, 3, 4, 5, 6, 7])[6] == 7.0


@pytest.mark.parametrize(
    "bad", ["[1, 2]", "not a list", [1, 2, 3, 4, 5, 6, -1], [True] * 7, [1, 2, 3, 4, 5, 6, "x"]]
)
def test_parse_nutrition_rejects_bad_vectors(bad: object) -> None:
    with pytest.raises(ValueError):
        parse_nutrition(bad)


def test_percent_dv_converts_with_reference() -> None:
    n = to_serving_nutrition(parse_nutrition(GOOD_NUTRITION), FDA_1993)
    assert n.fat_g == pytest.approx(13.0)  # 20% of 65 g
    assert n.saturated_fat_g == pytest.approx(2.0)  # 10% of 20 g
    assert n.carbohydrate_g == pytest.approx(60.0)  # 20% of 300 g
    assert n.protein_g == pytest.approx(10.0)  # 20% of 50 g
    assert n.sodium_mg == pytest.approx(240.0)  # 10% of 2400 mg
    assert n.sugars_g is None  # unknown, never converted or zero


def test_energy_ratio_matches_atwater() -> None:
    n = to_serving_nutrition(parse_nutrition(GOOD_NUTRITION), FDA_1993)
    assert energy_ratio(n) == pytest.approx((9 * 13 + 4 * 60 + 4 * 10) / 400)


def test_per_100g_needs_a_verified_mass() -> None:
    n = to_serving_nutrition(parse_nutrition(GOOD_NUTRITION), FDA_1993)
    assert per_100g(n, None) is None
    half = per_100g(n, 200.0)
    assert half is not None and half.energy_kcal == pytest.approx(200.0)
    assert half.sugars_g is None


def test_parse_string_list() -> None:
    assert parse_string_list("['a', ' b ']") == ("a", "b")
    with pytest.raises(ValueError):
        parse_string_list("[1, 2]")


# --- row validation -----------------------------------------------------------------


def test_good_row_becomes_catalogue_entry() -> None:
    recipe = make_ok(137739)
    assert recipe.recipe_id == "FC_137739"
    assert recipe.cuisines == ("Indian",)
    assert recipe.diet_tags == ("vegetarian",)
    assert recipe.roles == (CulinaryRole.MAIN_DISH,)
    assert recipe.dish_class is DishClass.REQUIRES_ACCOMPANIMENT  # dal needs rice or roti
    assert recipe.meal_types == (MealType.LUNCH, MealType.DINNER)  # a main suits both
    assert recipe.classification_status is ClassificationStatus.AUTO
    assert recipe.serving_mass_g is None and recipe.serving_mass_source is None
    assert recipe.nutrition.source is NutritionSource.FOODCOM_DERIVED
    assert recipe.nutrition.basis is NutritionBasis.PER_SERVING
    assert recipe.nutrition.source_reference == FDA_1993.name
    assert recipe.nutrition.values.sugars_g is None


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"nutrition": "oops"}, QuarantineReason.MALFORMED_NUTRITION),
        ({"tags": "oops"}, QuarantineReason.MALFORMED_METADATA),
        ({"ingredients": []}, QuarantineReason.MALFORMED_METADATA),
        ({"name": "  "}, QuarantineReason.MALFORMED_METADATA),
        ({"nutrition": [5.0, 0, 0, 0, 0, 0, 0]}, QuarantineReason.NUTRITION_OUT_OF_RANGE),
        ({"nutrition": [5000.0, 20, 10, 10, 20, 10, 20]}, QuarantineReason.NUTRITION_OUT_OF_RANGE),
        ({"nutrition": [400.0, 20, 10, 10, 20, 10, 9999]}, QuarantineReason.NUTRITION_OUT_OF_RANGE),
        ({"nutrition": [900.0, 20, 10, 10, 20, 10, 20]}, QuarantineReason.ENERGY_INCONSISTENT),
    ],
)
def test_defects_are_quarantined_with_their_reason(
    kwargs: dict[str, object], reason: QuarantineReason
) -> None:
    assert make_quarantined(**kwargs).reasons == (reason,)  # type: ignore[arg-type]


def test_non_positive_source_id_is_quarantined() -> None:
    row = make_quarantined(0)
    assert row.reasons == (QuarantineReason.MALFORMED_METADATA,)
    assert row.source_id == "0"


def test_one_row_collects_every_defect() -> None:
    row = make_quarantined(nutrition="oops", ingredients=[])
    assert row.reasons == (
        QuarantineReason.MALFORMED_NUTRITION,
        QuarantineReason.MALFORMED_METADATA,
    )


def test_energy_check_is_skipped_when_the_range_check_fails() -> None:
    # 5000 kcal is also inconsistent with its macros, but only the range reason is reported.
    row = make_quarantined(nutrition=[5000.0, 20, 10, 10, 20, 10, 20])
    assert QuarantineReason.ENERGY_INCONSISTENT not in row.reasons


def test_recipe_without_course_evidence_is_accepted_for_review_not_quarantined() -> None:
    recipe = make_ok(1, tags=["dessert", "indian"])  # "dessert" is not a Food.com course
    assert recipe.roles == () and recipe.meal_types == ()
    assert recipe.classification_status is ClassificationStatus.REQUIRES_REVIEW


def test_light_dish_within_rounding_gap_is_energy_consistent() -> None:
    # 20 kcal stated; 1 %DV carbohydrate = 3 g = 12 kcal implied: ratio 0.6, gap 8 kcal.
    recipe = make_ok(1, tags=["side-dishes", "vegetables"], nutrition=[20.0, 0, 0, 0, 0, 0, 1])
    assert recipe.roles == (CulinaryRole.VEGETABLE,)


def test_large_gap_on_a_light_dish_is_still_inconsistent() -> None:
    # 60 kcal stated, 0 implied: a 60 kcal gap is not rounding.
    row = make_quarantined(nutrition=[60.0, 0, 0, 0, 0, 0, 0])
    assert row.reasons == (QuarantineReason.ENERGY_INCONSISTENT,)


def test_quarantined_row_needs_at_least_one_reason() -> None:
    with pytest.raises(ValidationError):
        QuarantinedRow(source_id="1", name="x", reasons=())


def test_quarantined_row_keeps_defective_raw_values() -> None:
    # A non-numeric ID and a blank name are exactly what a defective row can contain.
    row = QuarantinedRow(source_id="abc", name="", reasons=(QuarantineReason.MALFORMED_METADATA,))
    assert row.source_id == "abc" and row.name == ""


# --- serving mass overrides ---------------------------------------------------------


def test_override_sets_mass_and_source() -> None:
    recipe = make_ok(1)
    [updated] = apply_serving_masses(
        [recipe], [ServingMassOverride(recipe_id="FC_1", serving_mass_g=250.0, source="weighed")]
    )
    assert updated.serving_mass_g == 250.0 and updated.serving_mass_source == "weighed"


def test_unknown_override_id_is_an_error() -> None:
    override = ServingMassOverride(recipe_id="FC_99", serving_mass_g=100.0, source="weighed")
    with pytest.raises(ValueError):
        apply_serving_masses([make_ok(1)], [override])


def test_mass_without_source_is_rejected() -> None:
    data = make_ok(1).model_dump() | {"serving_mass_g": 100.0}
    with pytest.raises(ValidationError):
        CatalogueRecipe.model_validate(data)


# --- end to end ---------------------------------------------------------------------

BUILT_AT = datetime(2026, 10, 18, 15, 30, 45, tzinfo=UTC)
REPO = Path(__file__).parents[3]


def write_source(path: Path) -> None:
    fields = ["name", "id", "tags", "nutrition", "ingredients"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for i in range(1, 6):  # five accepted and classified
            writer.writerow(
                {
                    "name": f"dal {'abcde'[i - 1]}",  # distinct names: no near-duplicates
                    "id": str(i),
                    "tags": str(GOOD_TAGS),
                    "nutrition": str(GOOD_NUTRITION),
                    "ingredients": str(GOOD_INGREDIENTS),
                }
            )
        writer.writerow(  # accepted but no usable course tag: awaits review
            {
                "name": "mystery",
                "id": "10",
                "tags": "['dessert']",
                "nutrition": str(GOOD_NUTRITION),
                "ingredients": str(GOOD_INGREDIENTS),
            }
        )
        writer.writerow(  # accepted, confidently not a planning dish
            {
                "name": "brownies",
                "id": "11",
                "tags": "['desserts']",
                "nutrition": str(GOOD_NUTRITION),
                "ingredients": str(GOOD_INGREDIENTS),
            }
        )
        writer.writerow(  # two defects in one row
            {"name": "bad", "id": "9", "tags": "[]", "nutrition": "oops", "ingredients": "[]"}
        )
        writer.writerow(  # an ID that is not a number
            {
                "name": "bad id",
                "id": "abc",
                "tags": str(GOOD_TAGS),
                "nutrition": str(GOOD_NUTRITION),
                "ingredients": str(GOOD_INGREDIENTS),
            }
        )


def run_build(source: Path) -> build_catalogue.BuildResult:
    return build(source, seed="s", dv_name=FDA_1993.name, overrides_path=None, built_at=BUILT_AT)


def test_build_reports_and_is_reproducible(tmp_path: Path) -> None:
    source = tmp_path / "RAW_recipes.csv"
    write_source(source)
    first = run_build(source)
    assert first == run_build(source)
    report = first.catalogue["report"]
    assert isinstance(report, dict)
    assert report["rawRecipes"] == 9
    assert report["accepted"] == 7
    assert report["plannable"] == 5
    assert report["requiresReview"] == 1
    assert report["notPlanningDish"] == 1
    assert report["classificationStatus"] == {"AUTO": 6, "REQUIRES_REVIEW": 1}
    assert report["plannableRoles"] == {"MAIN_DISH": 5}
    assert report["quarantinedRows"] == 2
    # Row 9 has two reasons and "abc" has one, so reasons add up to more than the rows.
    assert report["quarantineReasons"] == {"MALFORMED_METADATA": 2, "MALFORMED_NUTRITION": 1}
    # Every raw row is accounted for.
    assert report["accepted"] + report["quarantinedRows"] == report["rawRecipes"]
    assert json.dumps(first.catalogue) and json.dumps(first.quarantine)  # JSON serializable


def test_quarantine_file_keeps_every_defective_row(tmp_path: Path) -> None:
    source = tmp_path / "RAW_recipes.csv"
    write_source(source)
    rows = run_build(source).quarantine["rows"]
    assert isinstance(rows, list)
    by_id = {row["sourceId"]: row for row in rows}
    assert set(by_id) == {"9", "abc"}
    assert by_id["9"]["reasons"] == ["MALFORMED_NUTRITION", "MALFORMED_METADATA"]
    assert by_id["abc"]["reasons"] == ["MALFORMED_METADATA"]


def test_selected_recipes_exclude_unsettled_and_non_meal_dishes(tmp_path: Path) -> None:
    source = tmp_path / "RAW_recipes.csv"
    write_source(source)
    recipes = run_build(source).catalogue["recipes"]
    assert isinstance(recipes, list)
    assert {"FC_10", "FC_11"}.isdisjoint({r["recipeId"] for r in recipes})


def test_review_file_lists_dishes_awaiting_review_with_evidence(tmp_path: Path) -> None:
    source = tmp_path / "RAW_recipes.csv"
    write_source(source)
    [row] = run_build(source).review["rows"]  # type: ignore[misc]
    assert row["recipeId"] == "FC_10"
    assert "no usable course evidence" in row["evidence"]


def test_curated_override_settles_a_review_dish(tmp_path: Path) -> None:
    source = tmp_path / "RAW_recipes.csv"
    write_source(source)
    override = ClassificationOverride(
        recipe_id="FC_10",
        roles=(CulinaryRole.MAIN_DISH,),
        dish_class=DishClass.REQUIRES_ACCOMPANIMENT,
        meal_types=(MealType.LUNCH, MealType.DINNER),
        rationale="test",
        curated_by="tester",
    )
    result = build(
        source,
        seed="s",
        dv_name=FDA_1993.name,
        overrides_path=None,
        built_at=BUILT_AT,
        classification_overrides=(override,),
    )
    report = result.catalogue["report"]
    assert isinstance(report, dict)
    assert report["plannable"] == 6 and report["requiresReview"] == 0
    assert report["curatedOverridesApplied"] == 1


def test_override_for_a_missing_recipe_is_an_error(tmp_path: Path) -> None:
    source = tmp_path / "RAW_recipes.csv"
    write_source(source)
    override = ClassificationOverride(
        recipe_id="FC_9",  # quarantined, so not an accepted recipe
        cuisines=("Nepali",),
        rationale="test",
        curated_by="tester",
    )
    with pytest.raises(ValueError, match="FC_9"):
        build(
            source,
            seed="s",
            dv_name=FDA_1993.name,
            overrides_path=None,
            built_at=BUILT_AT,
            classification_overrides=(override,),
        )


# --- catalogue version --------------------------------------------------------------


def test_version_is_a_utc_timestamp() -> None:
    assert catalogue_version(BUILT_AT) == "20261018T153045Z"
    assert re.fullmatch(r"\d{8}T\d{6}Z", catalogue_version(BUILT_AT))


def test_version_converts_other_time_zones_to_utc() -> None:
    nepal = timezone(timedelta(hours=5, minutes=45))
    assert catalogue_version(datetime(2026, 10, 18, 21, 15, 45, tzinfo=nepal)) == "20261018T153045Z"


def test_versions_sort_in_time_order() -> None:
    stamps = [
        datetime(2026, 12, 1, tzinfo=UTC),
        datetime(2026, 10, 18, 15, 30, 45, tzinfo=UTC),
        datetime(2027, 1, 2, tzinfo=UTC),
        datetime(2026, 10, 18, 9, 0, 0, tzinfo=UTC),
    ]
    by_time = [catalogue_version(t) for t in sorted(stamps)]
    assert by_time == sorted(by_time)  # sorting the text gives the same order as time


def test_naive_timestamp_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        catalogue_version(datetime(2026, 10, 18, 15, 30, 45))
    source = tmp_path / "RAW_recipes.csv"
    write_source(source)
    with pytest.raises(ValueError):
        build(
            source,
            seed="s",
            dv_name=FDA_1993.name,
            overrides_path=None,
            built_at=datetime(2026, 10, 18),
        )


def test_both_outputs_share_the_same_version(tmp_path: Path) -> None:
    source = tmp_path / "RAW_recipes.csv"
    write_source(source)
    result = run_build(source)
    assert result.catalogue["catalogueVersion"] == "20261018T153045Z"
    assert result.quarantine["catalogueVersion"] == "20261018T153045Z"


# --- command line -------------------------------------------------------------------


def test_cli_names_files_by_build_time_and_writes_quarantine_on_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "RAW_recipes.csv"
    write_source(source)
    out_dir = tmp_path / "out"
    interactions = tmp_path / "RAW_interactions.csv"
    interactions.write_text(
        'user_id,recipe_id,date,rating,review\n1,1,2005-01-01,5,"great,\nreally"\n',
        encoding="utf-8",
    )
    curation = tmp_path / "overrides.json"
    curation.write_text(
        '{"schemaVersion": "classification-overrides.v1", "note": "t", "overrides": []}',
        encoding="utf-8",
    )
    argv = [
        "build",
        "--source",
        str(source),
        "--output-dir",
        str(out_dir),
        "--classification-overrides",
        str(curation),
        "--interactions",
        str(interactions),
        "--staples-spec",
        str(REPO / "Data/curated/usda_staples.json"),
        "--staples-extract",
        str(REPO / "Data/curated/usda_staples_extract.json"),
    ]

    monkeypatch.setattr("sys.argv", argv)
    build_catalogue.main()
    [catalogue_file] = out_dir.iterdir()  # exactly one file: no quarantine unless asked for
    match = re.fullmatch(r"(\d{8}T\d{6}Z)_catalogue\.json", catalogue_file.name)
    assert match is not None
    version = match.group(1)
    written = json.loads(catalogue_file.read_text(encoding="utf-8"))
    assert written["catalogueVersion"] == version
    assert written["independentOfHeldOutData"] is True
    by_id = {r["recipeId"]: r for r in written["recipes"]}
    assert by_id["FC_1"]["trainingInteractions"] == 1  # the multi-line review row counts
    assert by_id["FC_2"]["trainingInteractions"] == 0

    monkeypatch.setattr("sys.argv", [*argv, "--with-quarantine"])
    build_catalogue.main()
    quarantine_files = sorted(out_dir.glob("*_quarantine.json"))
    assert len(quarantine_files) == 1
    written = json.loads(quarantine_files[0].read_text(encoding="utf-8"))
    assert len(written["rows"]) == 2


def test_file_names_embed_the_version() -> None:
    assert (
        build_catalogue.catalogue_filename("20261018T153045Z") == "20261018T153045Z_catalogue.json"
    )
    assert (
        build_catalogue.quarantine_filename("20261018T153045Z")
        == "20261018T153045Z_quarantine.json"
    )
