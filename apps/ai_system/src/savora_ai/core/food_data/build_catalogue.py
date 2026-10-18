"""Build the versioned catalogue fixture from RAW_recipes.csv.

Usage (from the repo root):
    uv run python -m savora_ai.core.food_data.build_catalogue \
        --source Data/Food.com/RAW_recipes.csv --output-dir Data/catalogue --with-quarantine

Files are named by build time, so they sort chronologically:
    Data/catalogue/20261018T153045Z_catalogue.json      dishes, portions, nutrition
    Data/catalogue/20261018T153045Z_combinations.json   validated 1-3 dish meals + presets
    Data/catalogue/20261018T153045Z_build_report.json   counts, strata, coverage (readable)
    Data/catalogue/20261018T153045Z_quarantine.json   (only with --with-quarantine)
    Data/catalogue/20261018T153045Z_review.json       (only with --with-review)

Curated classification overrides are read from Data/curated/classification_overrides.json.

`--check` rebuilds and compares the content (everything except the version) with the
latest export in the output directory; it fails if they differ, i.e. the export is stale.
It needs the raw Food.com files, so run it locally before committing an export.

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
from datetime import UTC, date, datetime
from pathlib import Path

from savora_ai.core.food_data.catalogue import apply_serving_masses, build_recipe
from savora_ai.core.food_data.classification import (
    ClassificationOverride,
    ClassificationOverrideFile,
    apply_override,
    index_overrides,
    is_plannable,
)
from savora_ai.core.food_data.models import CatalogueRecipe, QuarantinedRow, ServingMassOverride
from savora_ai.core.food_data.nutrition_convert import DV_REFERENCES, FDA_1993
from savora_ai.core.food_data.popularity import (
    DEFAULT_POPULARITY_CUTOFF,
    PopularityTable,
    load_popularity,
)
from savora_ai.core.food_data.portions import serving_portions, with_portions
from savora_ai.core.food_data.selection import TARGET_CUISINES, select_stratified
from savora_ai.core.food_data.usda_staples import (
    DEFAULT_EXTRACT,
    DEFAULT_SPEC,
    load_extract,
    load_spec,
    staple_dishes,
)
from savora_ai.core.meal_composition.api import generate_meal_combinations
from savora_ai.core.meal_composition.coverage import coverage_report
from savora_ai.core.meal_composition.pairings import DEFAULT_PAIRINGS, PairingFile, load_pairings
from savora_ai.core.meal_composition.templates import (
    DEFAULT_TEMPLATES,
    TemplateFile,
    load_templates,
)
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


def combinations_filename(version: str) -> str:
    return f"{version}_combinations.json"


def build_report_filename(version: str) -> str:
    return f"{version}_build_report.json"


def content_sha256(data: object) -> str:
    """Digest of canonical JSON, so consumers can pin exactly what they read."""
    text = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


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
    combinations: dict[str, object]
    build_report: dict[str, object]


def build(
    source: Path,
    *,
    seed: str,
    dv_name: str,
    overrides_path: Path | None,
    built_at: datetime,
    classification_overrides: Sequence[ClassificationOverride] = (),
    staples: Sequence[CatalogueRecipe] = (),
    popularity: PopularityTable | None = None,
    templates: TemplateFile | None = None,
    pairings: PairingFile | None = None,
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

    selection = select_stratified(candidates, {} if popularity is None else popularity.counts, seed)
    selected = selection.recipes
    if overrides_path is not None:
        raw = json.loads(overrides_path.read_text(encoding="utf-8"))
        selected = apply_serving_masses(
            selected, [ServingMassOverride.model_validate(o) for o in raw]
        )
    selected = tuple(with_portions(r, serving_portions(r)) for r in selected)
    if popularity is not None:
        selected = tuple(with_popularity(r, popularity.count(r.recipe_id)) for r in selected)

    catalogue: dict[str, object] = {
        "catalogueVersion": version,
        "source": {"file": source.name, "sha256": source_sha256},
        "seed": seed,
        "dvReference": ref.name,
        "targetCuisines": list(TARGET_CUISINES),
        "popularity": None if popularity is None else popularity.report(),
        # The catalogue never reads held-out interactions (ADR 0001 D6).
        "independentOfHeldOutData": True,
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
            "usdaStaples": len(staples),
            "withVerifiedServingMass": sum(r.serving_mass_g is not None for r in selected),
            "strata": [stratum.as_json() for stratum in selection.strata],
            "strataWithShortfall": sum(s.selected < s.quota for s in selection.strata),
        },
        # Food.com selection first, then the curated USDA staples (ADR 0003 D1).
        "recipes": [r.model_dump(mode="json", by_alias=True) for r in (*selected, *staples)],
    }
    dishes = (*selected, *staples)
    combinations: dict[str, object] = {"catalogueVersion": version, "combinations": []}
    build_report: dict[str, object] = {
        "catalogueVersion": version,
        "catalogue": catalogue["report"],
        "popularity": catalogue["popularity"],
    }
    if templates is not None and pairings is not None:
        generated = generate_meal_combinations(dishes, templates, pairings, seed)
        coverage = coverage_report(dishes, generated.combinations)
        combinations = {
            "catalogueVersion": version,
            # Pins the exact dish content these meals reference.
            "catalogueContentSha256": content_sha256(catalogue["recipes"]),
            "templatesSchema": templates.schema_version,
            "pairingsSchema": pairings.schema_version,
            "composition": generated.composition_report,
            "validation": generated.validation_report,
            "rejected": list(generated.rejected),
            "combinations": [
                c.model_dump(mode="json", by_alias=True) for c in generated.combinations
            ],
        }
        build_report |= {
            "composition": generated.composition_report,
            "validation": generated.validation_report,
            "coverage": coverage,
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
    return BuildResult(
        catalogue=catalogue,
        quarantine=quarantine,
        review=review_queue,
        combinations=combinations,
        build_report=build_report,
    )


def _without_version(data: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in data.items() if k != "catalogueVersion"}


def check_exports(output_dir: Path, result: BuildResult) -> list[str]:
    """Problems if the latest export differs from a fresh build (ignoring the version)."""
    exports = sorted(output_dir.glob("*_catalogue.json"))
    if not exports:
        return [f"no export in {output_dir}"]
    version = exports[-1].name.removesuffix("_catalogue.json")  # versions sort by time
    problems: list[str] = []
    for name, fresh in (
        (catalogue_filename(version), result.catalogue),
        (combinations_filename(version), result.combinations),
    ):
        path = output_dir / name
        if not path.exists():
            problems.append(f"{path} is missing")
        elif _without_version(json.loads(path.read_text(encoding="utf-8"))) != _without_version(
            json.loads(json.dumps(fresh))
        ):
            problems.append(f"{path} is stale: rebuild and commit the new export")
    return problems


def with_popularity(recipe: CatalogueRecipe, count: int) -> CatalogueRecipe:
    return CatalogueRecipe.model_validate({**recipe.model_dump(), "training_interactions": count})


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
    parser.add_argument(
        "--interactions", type=Path, default=Path("Data/Food.com/RAW_interactions.csv")
    )
    parser.add_argument(
        "--popularity-cutoff", type=date.fromisoformat, default=DEFAULT_POPULARITY_CUTOFF
    )
    parser.add_argument("--staples-spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--staples-extract", type=Path, default=DEFAULT_EXTRACT)
    parser.add_argument("--templates", type=Path, default=DEFAULT_TEMPLATES)
    parser.add_argument("--pairings", type=Path, default=DEFAULT_PAIRINGS)
    parser.add_argument("--check", action="store_true", help="fail if the export is stale")
    args = parser.parse_args()
    # A missing curation file is an error, not "no curation": it would silently drop overrides.
    curated = load_classification_overrides(args.classification_overrides)
    staples = staple_dishes(load_spec(args.staples_spec), load_extract(args.staples_extract))
    result = build(
        args.source,
        seed=args.seed,
        dv_name=args.dv,
        overrides_path=args.overrides,
        built_at=datetime.now(UTC),  # the only clock read; build() itself stays testable
        classification_overrides=curated,
        staples=staples,
        popularity=load_popularity(args.interactions, args.popularity_cutoff),
        templates=load_templates(args.templates),
        pairings=load_pairings(args.pairings),
    )
    if args.check:
        problems = check_exports(args.output_dir, result)
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            raise SystemExit(1)
        print(f"latest export in {args.output_dir} is up to date")
        return
    version = str(result.catalogue["catalogueVersion"])
    for path, data in (
        (args.output_dir / catalogue_filename(version), result.catalogue),
        (args.output_dir / combinations_filename(version), result.combinations),
        (args.output_dir / build_report_filename(version), result.build_report),
    ):
        _write_json(path, data)
        print(f"wrote {path}")
    if args.with_quarantine:
        quarantine_path = args.output_dir / quarantine_filename(version)
        _write_json(quarantine_path, result.quarantine)
        print(f"wrote {quarantine_path}")
    if args.with_review:
        review_path = args.output_dir / review_filename(version)
        _write_json(review_path, result.review)
        print(f"wrote {review_path}")
    summary = {
        key: result.build_report.get(key)
        for key in ("composition", "validation")
        if key in result.build_report
    }
    print(json.dumps({"catalogue": result.catalogue["report"], **summary}, indent=2))


if __name__ == "__main__":
    main()
