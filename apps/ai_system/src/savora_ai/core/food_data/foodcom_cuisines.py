"""Exact-tag cuisine coverage for the Food.com EDA; no runtime eligibility claims."""

import argparse
import ast
import csv
import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

# Deliberately limited EDA taxonomy: exact normalized metadata tags only.
# British includes verified constituent cuisines; British Columbia is Canadian.
# American means the explicit American label, not every cuisine of the Americas.
# Mediterranean is retained even though its exact tag is absent in this source.
CUISINE_TAGS: dict[str, frozenset[str]] = {
    "Indian": frozenset({"indian"}),
    "Chinese": frozenset({"chinese"}),
    "Italian": frozenset({"italian"}),
    "Mexican": frozenset({"mexican"}),
    "Thai": frozenset({"thai"}),
    "Japanese": frozenset({"japanese"}),
    "Korean": frozenset({"korean"}),
    "French": frozenset({"french"}),
    "Greek": frozenset({"greek"}),
    "Mediterranean": frozenset({"mediterranean"}),
    "American": frozenset({"american"}),
    "British": frozenset({"english", "scottish", "welsh"}),
    "Spanish": frozenset({"spanish"}),
    "Middle Eastern": frozenset({"middle-eastern"}),
    "Vietnamese": frozenset({"vietnamese"}),
}


def normalize_tags(value: object) -> frozenset[str]:
    """Parse Python-list CSV fields safely; strip/lower only, preserving hyphens.

    Malformed values fail explicitly instead of silently reducing coverage.
    Already parsed lists are accepted for notebook use.
    """
    if isinstance(value, str):
        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError) as exc:
            raise ValueError("Food.com tags must be a literal list of strings") from exc
    if not isinstance(value, list) or any(not isinstance(tag, str) for tag in value):
        raise ValueError("Food.com tags must be a list of strings")
    return frozenset(tag.strip().lower() for tag in value if tag.strip())


def get_cuisines(tags: object) -> list[str]:
    """Allow multiple labels only when each has an explicit mapped tag."""
    normalized = normalize_tags(tags)
    return [cuisine for cuisine, supported in CUISINE_TAGS.items() if normalized & supported]


def summarize_cuisines(
    records: Iterable[tuple[str, object]],
) -> tuple[dict[str, set[str]], set[str]]:
    """Union duplicate rows by stable recipe ID, once per supported cuisine."""
    cuisine_ids: dict[str, set[str]] = {cuisine: set() for cuisine in CUISINE_TAGS}
    recipe_ids: set[str] = set()
    for recipe_id, tags in records:
        if not recipe_id.isascii() or not recipe_id.isdecimal() or int(recipe_id) <= 0:
            raise ValueError("Food.com recipe IDs must be positive integers")
        recipe_id = str(int(recipe_id))
        recipe_ids.add(recipe_id)
        for cuisine in get_cuisines(tags):
            cuisine_ids[cuisine].add(recipe_id)
    return cuisine_ids, recipe_ids


def cuisine_coverage(
    cuisine_ids: dict[str, set[str]], recipe_ids: set[str]
) -> dict[str, int | float]:
    memberships = Counter(recipe_id for ids in cuisine_ids.values() for recipe_id in ids)
    return {
        "total_recipes": len(recipe_ids),
        "recipes_with_cuisine": len(memberships),
        "recipes_without_cuisine": len(recipe_ids) - len(memberships),
        "cuisine_assignments": memberships.total(),
        "multi_cuisine_recipes": sum(count > 1 for count in memberships.values()),
        "coverage_percentage": len(memberships) / len(recipe_ids) * 100 if recipe_ids else 0.0,
    }


def export_cuisines(source: Path, output_dir: Path, *, check: bool = False) -> None:
    """Regenerate only cuisine artifacts from actual RAW_recipes.csv records.

    --check verifies exports without changing them. Missing source files fail
    before writing anything; tag-frequency exports are never used as input.
    """
    with source.open("rb") as binary:
        source_sha256 = hashlib.file_digest(binary, "sha256").hexdigest()
    with source.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"id", "tags"} <= set(reader.fieldnames or []):
            raise ValueError("Source must contain recipe-level id and tags columns")
        cuisine_ids, recipe_ids = summarize_cuisines((row["id"], row["tags"]) for row in reader)
    coverage = cuisine_coverage(cuisine_ids, recipe_ids)
    provenance = {
        "source_file": source.name,
        "source_sha256": source_sha256,
        "taxonomy": {cuisine: sorted(tags) for cuisine, tags in CUISINE_TAGS.items()},
        "normalization": "ast.literal_eval list[str]; strip and lower; exact tag equality",
        "deduplication": "unique recipe id per cuisine; coverage is the union of recipe ids",
    }
    artifacts = {
        "foodcom_cuisine_summary_eda.csv": (
            "cuisine,recipe_count\n"
            + "".join(f"{cuisine},{len(ids)}\n" for cuisine, ids in cuisine_ids.items())
        ),
        "foodcom_cuisine_coverage_eda.csv": (
            ",".join(coverage) + "\n" + ",".join(map(str, coverage.values())) + "\n"
        ),
        "foodcom_cuisine_provenance_eda.json": json.dumps(provenance, indent=2) + "\n",
    }
    if check:
        for filename, expected in artifacts.items():
            if (output_dir / filename).read_text(encoding="utf-8") != expected:
                raise ValueError(f"Stale cuisine artifact: {filename}")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in artifacts.items():
            (output_dir / filename).write_text(content, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("Data/Food.com"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    export_cuisines(args.source, args.output_dir, check=args.check)


if __name__ == "__main__":
    main()
