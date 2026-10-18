"""Build the versioned catalogue fixture from RAW_recipes.csv.

Usage (from the repo root):
    uv run python -m savora_ai.core.food_data.build_catalogue \
        --source Data/Food.com/RAW_recipes.csv --output-dir Data/catalogue --with-quarantine

Files are named by build time, so they sort chronologically:
    Data/catalogue/20261018T153045Z_catalogue.json
    Data/catalogue/20261018T153045Z_quarantine.json   (only with --with-quarantine)
    Data/catalogue/20261018T153045Z_review.json       (only with --with-review)

Curated classification overrides are read from Data/curated/classification_overrides.json.

The recipes are deterministic for a given source file, seed, DV reference and quotas.
The version is the UTC build time, so it says WHEN a build was made; the source hash and
seed recorded beside it say WHAT it was built from.
"""

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from savora_ai.core.food_data.catalogue import (
    DEFAULT_QUOTAS,
    apply_serving_masses,
    build_recipe,
    select_catalogue,
)
from savora_ai.core.food_data.classification import (
    ClassificationOverride,
    ClassificationOverrideFile,
    apply_override,
    index_overrides,
    is_plannable,
)
from savora_ai.core.food_data.models import CatalogueRecipe, QuarantinedRow, ServingMassOverride
from savora_ai.core.food_data.nutrition_convert import DV_REFERENCES, FDA_1993
from savora_ai.schemas.enums import ClassificationStatus, QuarantineReason

_REQUIRED_COLUMNS = {"id", "name", "tags", "nutrition", "ingredients"}


def catalogue_version(built_at: datetime) -> str:
    """UTC build time as `YYYYMMDDTHHMMSSZ`: sorting versions as text sorts them in time."""
    if built_at.tzinfo is None:
        raise ValueError("built_at must be timezone-aware")
    return built_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def catalogue_filename(version: str) -> str:
    return f"{version}_catalogue.json"


def quarantine_filename(version: str) -> str:
    return f"{version}_quarantine.json"


def review_filename(version: str) -> str:
    return f"{version}_review.json"


DEFAULT_CLASSIFICATION_OVERRIDES = Path("Data/curated/classification_overrides.json")


def load_classification_overrides(path: Path) -> tuple[ClassificationOverride, ...]:
    text = path.read_text(encoding="utf-8")
    return ClassificationOverrideFile.model_validate_json(text).overrides


@dataclass(frozen=True)
class BuildResult:
    """Outputs of one build: the catalogue, defective rows and dishes awaiting review."""

    catalogue: dict[str, object]
    quarantine: dict[str, object]
    review: dict[str, object]


def build(
    source: Path,
    *,
    seed: str,
    dv_name: str,
    overrides_path: Path | None,
    built_at: datetime,
    classification_overrides: Sequence[ClassificationOverride] = (),
) -> BuildResult:
    version = catalogue_version(built_at)  # fail early on a naive timestamp
    ref = DV_REFERENCES[dv_name]
    with source.open("rb") as binary:
        source_sha256 = hashlib.file_digest(binary, "sha256").hexdigest()

    overrides = index_overrides(classification_overrides)
    candidates: list[CatalogueRecipe] = []  # accepted AND plannable: selection input
    quarantined: list[QuarantinedRow] = []  # defective rows, kept for review
    review: list[dict[str, object]] = []  # REQUIRES_REVIEW dishes, compact
    reason_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    non_meal = 0  # confidently not a planning dish (dessert, drink, sauce...)
    applied: set[str] = set()
    total = 0
    csv.field_size_limit(sys.maxsize)  # some rows hold very long step text
    with source.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(reader.fieldnames or []) >= _REQUIRED_COLUMNS:
            raise ValueError(f"source must contain columns {sorted(_REQUIRED_COLUMNS)}")
        for row in reader:
            total += 1
            result: CatalogueRecipe | QuarantinedRow
            if not row["id"].isdecimal():
                # No usable ID, so build_recipe cannot be called; record the defect directly.
                result = QuarantinedRow(
                    source_id=row["id"],
                    name=row["name"],
                    reasons=(QuarantineReason.MALFORMED_METADATA,),
                )
            else:
                result = build_recipe(
                    int(row["id"]),
                    row["name"],
                    row["tags"],
                    row["nutrition"],
                    row["ingredients"],
                    ref,
                )
            if isinstance(result, QuarantinedRow):
                quarantined.append(result)
                reason_counts.update(result.reasons)  # one row can add several reasons
                continue
            override = overrides.get(result.recipe_id)
            if override is not None:
                result = apply_override(result, override)
                applied.add(result.recipe_id)
            status_counts[result.classification_status.value] += 1
            if is_plannable(result):
                candidates.append(result)
                role_counts.update(role.value for role in result.roles)
                class_counts[str(result.dish_class)] += 1
            elif result.classification_status is ClassificationStatus.REQUIRES_REVIEW:
                review.append(
                    {
                        "recipeId": result.recipe_id,
                        "name": result.name,
                        "suggestedRoles": [role.value for role in result.roles],
                        "evidence": list(result.classification_evidence),
                    }
                )
            else:
                non_meal += 1

    missing = sorted(set(overrides) - applied)
    if missing:
        # An override for a quarantined or unknown recipe is a curation error, not a no-op.
        raise ValueError(f"classification overrides match no accepted recipe: {missing}")

    selected = select_catalogue(candidates, DEFAULT_QUOTAS, seed)
    if overrides_path is not None:
        raw = json.loads(overrides_path.read_text(encoding="utf-8"))
        selected = apply_serving_masses(
            selected, [ServingMassOverride.model_validate(o) for o in raw]
        )

    catalogue: dict[str, object] = {
        "catalogueVersion": version,
        "source": {"file": source.name, "sha256": source_sha256},
        "seed": seed,
        "dvReference": ref.name,
        "quotas": {meal.value: n for meal, n in DEFAULT_QUOTAS.items()},
        "report": {
            "rawRecipes": total,
            "accepted": len(candidates) + len(review) + non_meal,
            "plannable": len(candidates),
            "requiresReview": len(review),
            "notPlanningDish": non_meal,
            "classificationStatus": dict(sorted(status_counts.items())),
            "curatedOverridesApplied": len(applied),
            # A dish can have several roles, so role counts add up to more than plannable.
            "plannableRoles": dict(sorted(role_counts.items())),
            "plannableDishClasses": dict(sorted(class_counts.items())),
            "quarantinedRows": len(quarantined),
            # A row can carry two reasons, so these may add up to more than quarantinedRows.
            "quarantineReasons": dict(sorted(reason_counts.items())),
            "selected": len(selected),
            "withVerifiedServingMass": sum(r.serving_mass_g is not None for r in selected),
        },
        "recipes": [r.model_dump(mode="json", by_alias=True) for r in selected],
    }
    quarantine: dict[str, object] = {
        "catalogueVersion": version,
        "source": {"file": source.name, "sha256": source_sha256},
        "rows": [q.model_dump(mode="json", by_alias=True) for q in quarantined],
    }
    review_queue: dict[str, object] = {
        "catalogueVersion": version,
        "source": {"file": source.name, "sha256": source_sha256},
        "rows": review,
    }
    return BuildResult(catalogue=catalogue, quarantine=quarantine, review=review_queue)


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("Data/catalogue"))
    parser.add_argument("--with-quarantine", action="store_true")  # optional, about 3 MB
    parser.add_argument("--seed", default="savora-catalogue-v0")
    parser.add_argument("--dv", default=FDA_1993.name, choices=sorted(DV_REFERENCES))
    parser.add_argument("--with-review", action="store_true")  # optional, large
    parser.add_argument("--overrides", type=Path, default=None)
    parser.add_argument(
        "--classification-overrides", type=Path, default=DEFAULT_CLASSIFICATION_OVERRIDES
    )
    args = parser.parse_args()
    # A missing curation file is an error, not "no curation": it would silently drop overrides.
    curated = load_classification_overrides(args.classification_overrides)
    result = build(
        args.source,
        seed=args.seed,
        dv_name=args.dv,
        overrides_path=args.overrides,
        built_at=datetime.now(UTC),  # the only clock read; build() itself stays testable
        classification_overrides=curated,
    )
    version = str(result.catalogue["catalogueVersion"])
    catalogue_path = args.output_dir / catalogue_filename(version)
    _write_json(catalogue_path, result.catalogue)
    print(f"wrote {catalogue_path}")
    if args.with_quarantine:
        quarantine_path = args.output_dir / quarantine_filename(version)
        _write_json(quarantine_path, result.quarantine)
        print(f"wrote {quarantine_path}")
    if args.with_review:
        review_path = args.output_dir / review_filename(version)
        _write_json(review_path, result.review)
        print(f"wrote {review_path}")
    print(json.dumps(result.catalogue["report"], indent=2))


if __name__ == "__main__":
    main()
