"""Independent fixtures and optional full-source checks for the EDA exports."""

import ast
import csv
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

import pytest

from savora_ai.core.food_data.foodcom_cuisines import (
    cuisine_coverage,
    export_cuisines,
    get_cuisines,
    normalize_tags,
    summarize_cuisines,
)

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "Data/Food.com"
# Expectations are independent of the implementation mapping and reducer.
EXPECTED_TAGS = {
    "Indian": {"indian"},
    "Chinese": {"chinese"},
    "Italian": {"italian"},
    "Mexican": {"mexican"},
    "Thai": {"thai"},
    "Japanese": {"japanese"},
    "Korean": {"korean"},
    "French": {"french"},
    "Greek": {"greek"},
    "Mediterranean": {"mediterranean"},
    "American": {"american"},
    "British": {"english", "scottish", "welsh"},
    "Spanish": {"spanish"},
    "Middle Eastern": {"middle-eastern"},
    "Vietnamese": {"vietnamese"},
}
EXPECTED_COUNTS = {
    "Indian": 2708,
    "Chinese": 2008,
    "Italian": 7410,
    "Mexican": 6694,
    "Thai": 1208,
    "Japanese": 851,
    "Korean": 253,
    "French": 2268,
    "Greek": 2391,
    "Mediterranean": 0,
    "American": 31179,
    "British": 2249,
    "Spanish": 1072,
    "Middle Eastern": 2067,
    "Vietnamese": 351,
}
EXPECTED_COVERAGE = {
    "total_recipes": 231637,
    "recipes_with_cuisine": 59381,
    "recipes_without_cuisine": 172256,
    "cuisine_assignments": 62709,
    "multi_cuisine_recipes": 3176,
    "coverage_percentage": 25.635369133601284,
}


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        (["british-columbian"], []),
        (["english", "scottish", "welsh"], ["British"]),
        (["middle-eastern"], ["Middle Eastern"]),
        (["middle eastern", "middle-eastern-main-dish"], []),
        (["chinese-new-year"], []),
        (["north-american", "south-american", "central-american", "native-american"], []),
        ([" AMERICAN ", "Mexican"], ["Mexican", "American"]),
    ],
)
def test_exact_tags(tags: list[str], expected: list[str]) -> None:
    assert get_cuisines(tags) == expected


def test_literal_list_normalization() -> None:
    assert normalize_tags("[' English ', 'ENGLISH', 'middle-eastern']") == {
        "english",
        "middle-eastern",
    }
    assert normalize_tags("[]") == frozenset()


@pytest.mark.parametrize("value", ["not a list", "'english'", "{'english'}", "[1]", None])
def test_invalid_tags_fail(value: object) -> None:
    with pytest.raises(ValueError):
        normalize_tags(value)


def test_recipe_deduplication_and_multi_cuisine() -> None:
    ids, recipes = summarize_cuisines(
        [
            ("1", ["english", "scottish", "english"]),
            ("01", ["welsh"]),
            ("2", ["american", "mexican"]),
            ("2", ["mexican"]),
            ("3", ["british-columbian"]),
            ("4", ["middle-eastern"]),
        ]
    )
    assert ids["British"] == {"1"}
    assert ids["American"] == ids["Mexican"] == {"2"}
    assert ids["Middle Eastern"] == {"4"}
    assert recipes == {"1", "2", "3", "4"}
    assert cuisine_coverage(ids, recipes) == {
        "total_recipes": 4,
        "recipes_with_cuisine": 3,
        "recipes_without_cuisine": 1,
        "cuisine_assignments": 4,
        "multi_cuisine_recipes": 1,
        "coverage_percentage": 75.0,
    }


@pytest.mark.parametrize("recipe_id", ["", "missing", "1.0", "-1", "0"])
def test_invalid_recipe_id_fails(recipe_id: str) -> None:
    with pytest.raises(ValueError):
        summarize_cuisines([(recipe_id, ["english"])])


def test_export_records_and_staleness(tmp_path: Path) -> None:
    source = tmp_path / "RAW_recipes.csv"
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["id", "tags"])
        writer.writerows(
            [
                ["1", "['british-columbian']"],
                ["2", "['english', 'welsh']"],
                ["2", "['scottish']"],
                ["3", "['middle-eastern', 'american']"],
            ]
        )
    target = tmp_path / "exports"
    export_cuisines(source, target)
    export_cuisines(source, target, check=True)
    with (target / "foodcom_cuisine_summary_eda.csv").open() as stream:
        counts = {r["cuisine"]: int(r["recipe_count"]) for r in csv.DictReader(stream)}
    assert {c: counts[c] for c in ["British", "Middle Eastern", "American"]} == {
        "British": 1,
        "Middle Eastern": 1,
        "American": 1,
    }
    (target / "foodcom_cuisine_summary_eda.csv").write_text("stale\n")
    with pytest.raises(ValueError, match="Stale cuisine artifact"):
        export_cuisines(source, target, check=True)


def test_absent_source_never_writes_exports(tmp_path: Path) -> None:
    target = tmp_path / "exports"
    with pytest.raises(FileNotFoundError):
        export_cuisines(tmp_path / "missing.csv", target)
    assert not target.exists()


def test_checked_in_summary_consistency() -> None:
    with (DATA / "foodcom_cuisine_summary_eda.csv").open() as stream:
        counts = {r["cuisine"]: int(r["recipe_count"]) for r in csv.DictReader(stream)}
    assert counts == EXPECTED_COUNTS
    with (DATA / "foodcom_cuisine_coverage_eda.csv").open() as stream:
        coverage = next(csv.DictReader(stream))
    assert {k: float(v) for k, v in coverage.items()} == EXPECTED_COVERAGE
    assert sum(counts.values()) == EXPECTED_COVERAGE["cuisine_assignments"]
    markdown = (ROOT / "eda/food.com_eda.md").read_text(encoding="utf-8")
    for cuisine, count in counts.items():
        assert f"| {cuisine} | {count:,} |" in markdown
    assert "59,381" in markdown and "25.64%" in markdown
    assert "68,631" not in markdown and "29.63%" not in markdown
    notebook = json.loads((ROOT / "eda/food.com_eda.ipynb").read_text(encoding="utf-8"))
    summary_cells = [
        cell
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
        and "".join(cell["source"]).endswith(
            'cuisine_summary.sort_values("recipe_count", ascending=False)'
        )
    ]
    assert len(summary_cells) == 2
    for cell in summary_cells:
        text = "".join(
            "".join(out.get("data", {}).get("text/plain", [])) for out in cell["outputs"]
        )
        for cuisine, count in counts.items():
            assert re.search(rf"\b{re.escape(cuisine)}\s+{count}\b", text)
    for cell in notebook["cells"]:
        for out in cell.get("outputs", []):
            text = "".join(out.get("text", [])) + str(out.get("data", {}).get("text/plain", []))
            assert "68631" not in text and "29.628686" not in text


def test_exports_against_independent_recipe_level_source() -> None:
    configured = os.environ.get("FOODCOM_RAW_RECIPES")
    source = Path(configured) if configured else DATA / "RAW_recipes.csv"
    if not source.is_file():
        if configured:
            pytest.fail(f"Configured recipe source is missing: {source}")
        pytest.skip("Set FOODCOM_RAW_RECIPES to run the full recipe-level verification")
    # Do not call the implementation parser, classifier, or reducer.
    ids_by_cuisine: dict[str, set[str]] = {c: set() for c in EXPECTED_TAGS}
    recipe_ids: set[str] = set()
    tag_counts: Counter[str] = Counter()
    with source.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            recipe_id = row["id"]
            recipe_ids.add(recipe_id)
            tags = {t.strip().lower() for t in ast.literal_eval(row["tags"])}
            tag_counts.update(tags)
            for cuisine, exact_tags in EXPECTED_TAGS.items():
                if not tags.isdisjoint(exact_tags):
                    ids_by_cuisine[cuisine].add(recipe_id)
    assert {c: len(ids) for c, ids in ids_by_cuisine.items()} == EXPECTED_COUNTS
    memberships = Counter(i for ids in ids_by_cuisine.values() for i in ids)
    assert len(recipe_ids) == 231637
    assert len(memberships) == 59381
    assert len(recipe_ids - memberships.keys()) == 172256
    assert sum(memberships.values()) == 62709
    assert sum(n > 1 for n in memberships.values()) == 3176
    assert len(memberships) / len(recipe_ids) * 100 == EXPECTED_COVERAGE["coverage_percentage"]
    with (DATA / "foodcom_all_tags_eda.csv").open(encoding="utf-8") as stream:
        assert dict(tag_counts) == {
            r["tag"]: int(r["recipe_count"]) for r in csv.DictReader(stream)
        }
    provenance = json.loads((DATA / "foodcom_cuisine_provenance_eda.json").read_text())
    with source.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == provenance["source_sha256"]
    assert provenance["taxonomy"] == {c: sorted(tags) for c, tags in EXPECTED_TAGS.items()}
    export_cuisines(source, DATA, check=True)
