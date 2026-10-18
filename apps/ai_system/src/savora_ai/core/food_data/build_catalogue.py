"""Build the versioned catalogue fixture from RAW_recipes.csv.

Usage (from the repo root):
    uv run python -m savora_ai.core.food_data.build_catalogue \
        --source Data/Food.com/RAW_recipes.csv --output-dir Data/catalogue --with-quarantine

Files are named by build time, so they sort chronologically:
    Data/catalogue/20261018T153045Z_catalogue.json
    Data/catalogue/20261018T153045Z_quarantine.json   (only with --with-quarantine)

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
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from savora_ai.core.food_data.catalogue import (
    DEFAULT_QUOTAS,
    apply_serving_masses,
    build_recipe,
    select_catalogue,
)
from savora_ai.core.food_data.models import CatalogueRecipe, QuarantinedRow, ServingMassOverride
from savora_ai.core.food_data.nutrition_convert import DV_REFERENCES, FDA_1993
from savora_ai.schemas.enums import QuarantineReason

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


@dataclass(frozen=True)
class BuildResult:
    """The two outputs of one build: the catalogue and the quarantine review file."""

    catalogue: dict[str, object]
    quarantine: dict[str, object]


def build(
    source: Path,
    *,
    seed: str,
    dv_name: str,
    overrides_path: Path | None,
    built_at: datetime,
) -> BuildResult:
    version = catalogue_version(built_at)  # fail early on a naive timestamp
    ref = DV_REFERENCES[dv_name]
    with source.open("rb") as binary:
        source_sha256 = hashlib.file_digest(binary, "sha256").hexdigest()

    candidates: list[CatalogueRecipe] = []  # accepted AND classified: selection input
    quarantined: list[QuarantinedRow] = []  # defective rows, kept for review
    reason_counts: Counter[str] = Counter()
    unclassified = 0  # accepted but no meal tag; counted only, Stage 2 will classify them
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
            elif result.meal_types:
                candidates.append(result)
            else:
                unclassified += 1

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
            "accepted": len(candidates) + unclassified,
            "acceptedWithMealType": len(candidates),
            "acceptedUnclassified": unclassified,
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
    return BuildResult(catalogue=catalogue, quarantine=quarantine)


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
    parser.add_argument("--overrides", type=Path, default=None)
    args = parser.parse_args()
    result = build(
        args.source,
        seed=args.seed,
        dv_name=args.dv,
        overrides_path=args.overrides,
        built_at=datetime.now(UTC),  # the only clock read; build() itself stays testable
    )
    version = str(result.catalogue["catalogueVersion"])
    catalogue_path = args.output_dir / catalogue_filename(version)
    _write_json(catalogue_path, result.catalogue)
    print(f"wrote {catalogue_path}")
    if args.with_quarantine:
        quarantine_path = args.output_dir / quarantine_filename(version)
        _write_json(quarantine_path, result.quarantine)
        print(f"wrote {quarantine_path}")
    print(json.dumps(result.catalogue["report"], indent=2))


if __name__ == "__main__":
    main()
