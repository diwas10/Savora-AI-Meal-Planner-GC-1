"""Stage 8: the Meal Composition Engine (ARCHITECTURE.md section 6, ADR 0002).

Builds sensible meals of 1 to 3 COMPLETE dishes (never ingredient-level synthesis):

    ONE_DISH               biryani
    MAIN_STAPLE            dal + rice           (staple from the curated pairing list)
    MAIN_STAPLE_VEGETABLE  dal + rice + spinach (side: same cuisine or cuisine-neutral)
    BREAKFAST(_FRUIT|_PROTEIN)  poha (+ banana | + boiled egg)

It does not decide eligibility (Member 2's Rule Engine does, on the whole combination)
and does not rank (the Transformer does). It sets curated portion PRESETS only; the CSP
picks among them. Output is deterministic for the same inputs and seed, and bounded by
named limits applied while generating, so no list is ever silently truncated.
"""

import hashlib
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from savora_ai.core.food_data.classification import is_plannable
from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.meal_composition.models import (
    ComponentPortion,
    ComponentRef,
    MealCombination,
    PortionConfiguration,
)
from savora_ai.core.meal_composition.pairings import PairingFile
from savora_ai.core.meal_composition.presets import preset_portions
from savora_ai.core.meal_composition.templates import MealTemplate, TemplateFile
from savora_ai.schemas.enums import MealType


@dataclass(frozen=True)
class CompositionLimits:
    """PROVISIONAL size caps (ADR 0002 D4); to be tuned with Member 2's solver timings."""

    staples_per_main: int = 2
    vegetables_per_main_staple: int = 1
    add_ons_per_base: int = 2
    max_per_meal_type: int = 600  # safety bound: exceeding it is an error, not a cut


DEFAULT_LIMITS = CompositionLimits()


@dataclass(frozen=True)
class CompositionResult:
    combinations: tuple[MealCombination, ...]
    report: dict[str, object]


def _rank(seed: str, *parts: str) -> str:
    return hashlib.sha256(":".join((seed, *parts)).encode()).hexdigest()


def overlaps(base: CatalogueRecipe, add_on: CatalogueRecipe) -> bool:
    """An add-on already in the base (banana with banana pancakes, egg with an omelette)."""
    words = [w.lower() for w in add_on.ingredients]
    return any(word in ingredient.lower() for ingredient in base.ingredients for word in words)


def combination_id_for(template_id: str, dishes: Sequence[CatalogueRecipe]) -> str:
    """Template + dishes: a frittata as a lunch ONE_DISH and as a BREAKFAST differ."""
    return "__".join((f"C_{template_id}", *(d.recipe_id for d in dishes)))


def _combination(
    template: MealTemplate, dishes: tuple[CatalogueRecipe, ...], evidence: tuple[str, ...]
) -> MealCombination:
    combination_id = combination_id_for(template.template_id, dishes)
    slots = tuple(s.slot for s in template.slots)
    configurations = tuple(
        PortionConfiguration(
            configuration_id=f"{combination_id}#{preset}",
            preset=preset,
            portions=tuple(
                ComponentPortion(
                    dish_id=dish.recipe_id,
                    portion_id=option.portion_id,
                    quantity=option.quantity,
                    unit=option.unit,
                    grams=option.grams,
                )
                for dish, option in zip(dishes, options, strict=True)
            ),
        )
        for preset, options in preset_portions(slots, dishes).items()
    )
    meals = tuple(meal for meal in template.meal_types if all(meal in d.meal_types for d in dishes))
    return MealCombination(
        combination_id=combination_id,
        template_id=template.template_id,
        meal_types=meals,
        cuisines=dishes[0].cuisines,
        components=tuple(
            ComponentRef(slot=slot.slot, dish_id=dish.recipe_id, role=slot.role)
            for slot, dish in zip(template.slots, dishes, strict=True)
        ),
        configurations=configurations,
        evidence=(f"template {template.template_id}: {template.rationale}", *evidence),
    )


def compose(
    dishes: Iterable[CatalogueRecipe],
    templates: TemplateFile,
    pairings: PairingFile,
    seed: str,
    limits: CompositionLimits = DEFAULT_LIMITS,
) -> CompositionResult:
    pool = sorted((d for d in dishes if is_plannable(d) and d.portions), key=lambda d: d.recipe_id)
    by_id = {d.recipe_id: d for d in pool}
    staples_for = pairings.staples_by_cuisine()
    combos: list[MealCombination] = []
    skipped_overlap = 0

    def candidates(template: MealTemplate, index: int) -> list[CatalogueRecipe]:
        slot = template.slots[index]
        return [d for d in pool if slot.accepts(d, template.meal_types)]

    for template in templates.templates:
        slot_names = [s.slot for s in template.slots]
        anchors = [d for d in candidates(template, 0) if d.cuisines]  # anchor sets cuisine
        for anchor in anchors:
            if len(slot_names) == 1:
                combos.append(_combination(template, (anchor,), ()))
                continue
            second = slot_names[1]
            if second == "STAPLE":
                paired = {
                    sid
                    for cuisine in anchor.cuisines
                    for sid in staples_for.get(cuisine, ())
                    if sid in by_id and template.slots[1].accepts(by_id[sid], template.meal_types)
                }
                staples = sorted(paired, key=lambda sid: _rank(seed, anchor.recipe_id, sid))
                for staple_id in staples[: limits.staples_per_main]:
                    staple = by_id[staple_id]
                    pairing = (f"pairing: {'/'.join(anchor.cuisines)} main with {staple.name}",)
                    if len(slot_names) == 2:
                        combos.append(_combination(template, (anchor, staple), pairing))
                        continue
                    sides = [
                        v
                        for v in candidates(template, 2)
                        if not v.cuisines or set(v.cuisines) & set(anchor.cuisines)
                    ]
                    sides.sort(
                        key=lambda v: (
                            not v.cuisines,  # same cuisine before cuisine-neutral
                            _rank(seed, anchor.recipe_id, staple_id, v.recipe_id),
                        )
                    )
                    for side in sides[: limits.vegetables_per_main_staple]:
                        why = "same cuisine" if side.cuisines else "cuisine-neutral"
                        combos.append(
                            _combination(
                                template,
                                (anchor, staple, side),
                                (*pairing, f"vegetable side: {side.name} ({why})"),
                            )
                        )
            else:  # breakfast add-on: fruit or protein
                add_ons = []
                for add_on in candidates(template, 1):
                    if overlaps(anchor, add_on):
                        skipped_overlap += 1
                    elif not add_on.cuisines or set(add_on.cuisines) & set(anchor.cuisines):
                        add_ons.append(add_on)
                add_ons.sort(key=lambda a: _rank(seed, anchor.recipe_id, a.recipe_id))
                for add_on in add_ons[: limits.add_ons_per_base]:
                    combos.append(
                        _combination(template, (anchor, add_on), (f"add-on: {add_on.name}",))
                    )

    ids = [c.combination_id for c in combos]
    duplicates = [i for i, n in Counter(ids).items() if n > 1]
    if duplicates:
        raise ValueError(f"duplicate combinations: {duplicates[:5]}")
    per_meal = Counter(meal.value for c in combos for meal in c.meal_types)
    over = {m: n for m, n in per_meal.items() if n > limits.max_per_meal_type}
    if over:
        raise ValueError(f"combinations per meal type exceed the bound: {over}")
    return CompositionResult(
        combinations=tuple(sorted(combos, key=lambda c: c.combination_id)),
        report=_report(combos, skipped_overlap, limits),
    )


def _report(
    combos: Sequence[MealCombination], skipped_overlap: int, limits: CompositionLimits
) -> dict[str, object]:
    return {
        "combinations": len(combos),
        "configurations": sum(len(c.configurations) for c in combos),
        "byTemplate": dict(sorted(Counter(c.template_id for c in combos).items())),
        "byMealType": {meal.value: sum(meal in c.meal_types for c in combos) for meal in MealType},
        "byCuisine": dict(sorted(Counter(x for c in combos for x in c.cuisines).items())),
        "addOnsSkippedForIngredientOverlap": skipped_overlap,
        "limits": {
            "staplesPerMain": limits.staples_per_main,
            "vegetablesPerMainStaple": limits.vegetables_per_main_staple,
            "addOnsPerBase": limits.add_ons_per_base,
            "maxPerMealType": limits.max_per_meal_type,
        },
    }
