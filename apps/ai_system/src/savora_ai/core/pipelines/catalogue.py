"""The validated catalogue export, loaded once and shared by every pipeline call.

The backend loads it at startup (`load_catalogue_export(Path("Data/catalogue"))`) and
passes the bundle into each call; the AI layer never reads files per request.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.meal_composition.models import MealCombination
from savora_ai.core.recommendation.ranking import PopularityScorer


@dataclass(frozen=True)
class CatalogueBundle:
    version: str  # the export's catalogueVersion, e.g. "20261021T073631Z"
    dishes: dict[str, CatalogueRecipe]
    combinations: dict[str, MealCombination]
    popularity: PopularityScorer = field(compare=False)
    # The cuisines the catalogue was built to cover; other names are incidental Food.com
    # tags (e.g. British). Empty for exports that predate the field: then every cuisine.
    target_cuisines: tuple[str, ...] = ()

    @property
    def cuisine_ids(self) -> dict[str, str]:
        """Canonical cuisine ID (`NEPALI`) -> catalogue cuisine name (`Nepali`)."""
        names = sorted({c for d in self.dishes.values() for c in d.cuisines})
        return {cuisine_id(name): name for name in names}

    @property
    def target_cuisine_ids(self) -> dict[str, str]:
        """`cuisine_ids` limited to the target cuisines (what a profile may choose)."""
        targets = set(self.target_cuisines)
        return {k: v for k, v in self.cuisine_ids.items() if not targets or v in targets}


def cuisine_id(name: str) -> str:
    """`Middle Eastern` -> `MIDDLE_EASTERN`: the ID NLU emits (section 9.1)."""
    return "_".join(name.upper().split())


def load_catalogue_export(directory: Path, version: str | None = None) -> CatalogueBundle:
    """The newest (or the named) `<version>_catalogue.json` + `_combinations.json` pair."""
    if version is None:
        files = sorted(directory.glob("*_catalogue.json"))
        if not files:
            raise FileNotFoundError(f"no *_catalogue.json export in {directory}")
        version = files[-1].name.removesuffix("_catalogue.json")
    catalogue = json.loads((directory / f"{version}_catalogue.json").read_text("utf-8"))
    combos = json.loads((directory / f"{version}_combinations.json").read_text("utf-8"))
    if catalogue["catalogueVersion"] != version or combos["catalogueVersion"] != version:
        raise ValueError(f"export files disagree with their version {version!r}")
    dishes = {
        r["recipeId"]: CatalogueRecipe.model_validate_json(json.dumps(r))
        for r in catalogue["recipes"]
    }
    meals = [MealCombination.model_validate_json(json.dumps(c)) for c in combos["combinations"]]
    missing = {c.dish_id for m in meals for c in m.components} - dishes.keys()
    if missing:
        raise ValueError(f"combinations use dishes not in the catalogue: {sorted(missing)[:5]}")
    counts = {
        d.recipe_id: d.training_interactions
        for d in dishes.values()
        if d.training_interactions is not None
    }
    return CatalogueBundle(
        version=version,
        dishes=dishes,
        combinations={m.combination_id: m for m in meals},
        popularity=PopularityScorer(counts),
        target_cuisines=tuple(sorted(catalogue.get("targetCuisines", ()))),
    )
