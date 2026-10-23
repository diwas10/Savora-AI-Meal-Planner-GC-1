"""Catalogue queries over the in-memory export (no database: section 10 of the spec)."""

from savora_ai.core.food_data.portions import standard_portion
from savora_ai.core.pipelines import CatalogueBundle
from savora_ai.core.recommendation.seeds import is_seed_eligible
from savora_backend.core.catalogue.dto import (
    CatalogueDishDetailDto,
    CatalogueDishDto,
    CuisineOptionDto,
)

MAX_DISH_RESULTS = 50


class CatalogueService:
    def __init__(self, bundle: CatalogueBundle) -> None:
        self._bundle = bundle

    def cuisines(self) -> list[CuisineOptionDto]:
        """The target cuisines a profile may choose (incidental tags are left out)."""
        return [
            CuisineOptionDto(id=cid, name=name)
            for cid, name in sorted(self._bundle.target_cuisine_ids.items(), key=lambda i: i[1])
        ]

    def search_dishes(self, q: str) -> list[CatalogueDishDto]:
        """Seed-eligible Food.com dishes whose name or cuisine contains `q`, most popular first."""
        query = q.strip().lower()
        results: list[CatalogueDishDto] = []
        for dish in sorted(
            self._bundle.dishes.values(),
            key=lambda d: (-(d.training_interactions or 0), d.recipe_id),
        ):
            if dish.training_interactions is None or not is_seed_eligible(dish):
                continue
            if (
                query
                and query not in dish.name.lower()
                and not any(query in c.lower() for c in dish.cuisines)
            ):
                continue
            results.append(
                CatalogueDishDto(recipe_id=dish.recipe_id, name=dish.name, cuisines=dish.cuisines)
            )
            if len(results) >= MAX_DISH_RESULTS:
                break
        return results

    def get_dish(self, recipe_id: str) -> CatalogueDishDetailDto | None:
        """Full dish details: ingredients, steps, roles, and standard portion nutrition."""
        dish = self._bundle.dishes.get(recipe_id)
        if dish is None:
            return None
        portion = standard_portion(dish)
        return CatalogueDishDetailDto(
            recipe_id=dish.recipe_id,
            name=dish.name,
            cuisines=dish.cuisines,
            roles=tuple(r.value for r in dish.roles),
            meal_types=tuple(m.value for m in dish.meal_types),
            ingredients=dish.ingredients,
            steps=self._bundle.recipe_steps.get(dish.recipe_id, ()),
            standard_portion=portion.label,
            standard_nutrients=portion.nutrients,
        )
