"""Build the versioned catalogue fixture from RAW_recipes.csv.

Usage (from the repo root):
    uv run python -m savora_ai.core.food_data.build_catalogue \
        --source Data/Food.com/RAW_recipes.csv --output Data/catalogue/catalogue_v0.json

The output is deterministic for a given source file, seed, DV reference and quotas.
"""

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from savora_ai.core.food_data.catalogue import (
    DEFAULT_QUOTAS,
    apply_serving_masses,
    build_recipe,
    select_catalogue,
)
from savora_ai.core.food_data.models import CatalogueRecipe, ServingMassOverride
from savora_ai.core.food_data.nutrition_convert import DV_REFERENCES, FDA_1993
from savora_ai.schemas.enums import RejectionReason

CATALOGUE_VERSION = "catalogue-v0"
_REQUIRED_COLUMNS = {"id", "name", "tags", "nutrition", "ingredients"}


def build(
    source: Path,
    *,
    seed: str,
    dv_name: str,
    overrides_path: Path | None,
) -> dict[str, object]:
    ref = DV_REFERENCES[dv_name]
    with source.open("rb") as binary:
        source_sha256 = hashlib.file_digest(binary, "sha256").hexdigest()

    candidates: list[CatalogueRecipe] = []
    rejections: Counter[str] = Counter()
    total = 0
    csv.field_size_limit(sys.maxsize)  # some rows hold very long step text
    with source.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(reader.fieldnames or []) >= _REQUIRED_COLUMNS:
            raise ValueError(f"source must contain columns {sorted(_REQUIRED_COLUMNS)}")
        for row in reader:
            total += 1
            if not row["id"].isdecimal():
                rejections[RejectionReason.MALFORMED_METADATA] += 1
                continue
            result = build_recipe(
                int(row["id"]), row["name"], row["tags"], row["nutrition"], row["ingredients"], ref
            )
            if isinstance(result, RejectionReason):
                rejections[result] += 1
            else:
                candidates.append(result)

    selected = select_catalogue(candidates, DEFAULT_QUOTAS, seed)
    if overrides_path is not None:
        raw = json.loads(overrides_path.read_text(encoding="utf-8"))
        selected = apply_serving_masses(
            selected, [ServingMassOverride.model_validate(o) for o in raw]
        )

    return {
        "catalogueVersion": CATALOGUE_VERSION,
        "source": {"file": source.name, "sha256": source_sha256},
        "seed": seed,
        "dvReference": ref.name,
        "quotas": {meal.value: n for meal, n in DEFAULT_QUOTAS.items()},
        "report": {
            "rawRecipes": total,
            "eligibleCandidates": len(candidates),
            "selected": len(selected),
            "withVerifiedServingMass": sum(r.serving_mass_g is not None for r in selected),
            "rejections": dict(sorted(rejections.items())),
        },
        "recipes": [r.model_dump(mode="json", by_alias=True) for r in selected],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("Data/catalogue/catalogue_v0.json"))
    parser.add_argument("--seed", default="savora-catalogue-v0")
    parser.add_argument("--dv", default=FDA_1993.name, choices=sorted(DV_REFERENCES))
    parser.add_argument("--overrides", type=Path, default=None)
    args = parser.parse_args()
    catalogue = build(args.source, seed=args.seed, dv_name=args.dv, overrides_path=args.overrides)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalogue, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(catalogue["report"], indent=2))


if __name__ == "__main__":
    main()
