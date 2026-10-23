"""Explanation builder (XAI aggregation, ARCHITECTURE.md sections 4.2 step 6 and 4.3).

Combines what each stage already decided into one explanation per meal or recipe:

    composition  which template and curated pairing built the meal
    portion      which preset was chosen and what it trades
    nutrition    the validated totals, their weakest source, and what is UNKNOWN
    ranking      why it ranked where it did: model version, or an explicit fallback
    rules        the Rule Engine's status, as reported by Member 2 (never re-decided here)
    planning     the CSP outcome for the slot, as reported by Member 2
    limitations  data caveats the user should know (derived nutrition, unmapped ingredients)

Messages are deterministic templates, never an LLM, and every reason has a stable `code`
so the UI and tests can rely on it. Wording is honest: a rule PASS is "passed N checks",
never "safe for you"; an unknown nutrient is named, never shown as zero; a craving
recipe states that it was NOT checked against the day's remaining budget.
"""

from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from savora_ai.core.food_data.models import CatalogueRecipe, NutrientVector
from savora_ai.core.food_data.portions import standard_portion
from savora_ai.core.meal_composition.models import MealCombination, PortionConfiguration
from savora_ai.core.recommendation.ranking import (
    CombinationRanking,
    FallbackReason,
    RecipeRanking,
)
from savora_ai.schemas.enums import NutritionSource, PortionPreset

EXPLANATION_VERSION = "explanation-v1"


class _ExplanationModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        allow_inf_nan=False,
    )


class ReasonKind(StrEnum):
    COMPOSITION = "COMPOSITION"
    PORTION = "PORTION"
    NUTRITION = "NUTRITION"
    RANKING = "RANKING"
    RULES = "RULES"
    PLANNING = "PLANNING"
    LIMITATION = "LIMITATION"


class Reason(_ExplanationModel):
    kind: ReasonKind
    code: str  # stable, machine-readable, e.g. "RANKING_FALLBACK_NO_HISTORY"
    message: str
    references: tuple[str, ...] = ()  # IDs this reason rests on (rules, dishes, model)


class RuleOutcome(_ExplanationModel):
    """Member 2's verdict for the item, summarised by the orchestrator; not re-decided."""

    status: Literal["PASS", "FAIL", "UNKNOWN"]
    checked_rules: tuple[str, ...]
    failed_rules: tuple[str, ...] = ()
    unknown_rules: tuple[str, ...] = ()
    trace_id: str | None = None


class PlanningOutcome(_ExplanationModel):
    """Member 2's CSP result for the slot, summarised by the orchestrator."""

    outcome: Literal["FEASIBLE", "INFEASIBLE", "TIMEOUT", "INSUFFICIENT_DATA"]
    slot_id: str
    search_nodes: int = Field(ge=0)
    constraints: tuple[str, ...] = ()  # e.g. "day sodium <= 1500 mg"


class DishLine(_ExplanationModel):
    dish_id: str
    name: str
    role: str
    portion: str  # e.g. "2 pieces (80 g)", "1.25 servings"
    nutrition_source: NutritionSource
    ingredients: tuple[str, ...] = ()
    steps: tuple[str, ...] = ()


class MealExplanation(_ExplanationModel):
    explanation_version: Literal["explanation-v1"] = EXPLANATION_VERSION
    combination_id: str
    configuration_id: str
    slot_id: str | None
    dishes: tuple[DishLine, ...]
    totals: NutrientVector
    source_tier: NutritionSource
    unknown_nutrients: tuple[str, ...]
    reasons: tuple[Reason, ...]


class RecipeExplanation(_ExplanationModel):
    explanation_version: Literal["explanation-v1"] = EXPLANATION_VERSION
    recipe_id: str
    name: str
    standard_portion: str
    standard_nutrients: NutrientVector
    ingredients: tuple[str, ...] = ()
    steps: tuple[str, ...] = ()
    reasons: tuple[Reason, ...]


PRESET_TEXT: dict[PortionPreset, str] = {
    PortionPreset.STANDARD: "standard portions of every dish",
    PortionPreset.HIGHER_PROTEIN: "more of the main dish and less staple, for more protein",
    PortionPreset.LOWER_CARB: "the smallest staple and more vegetables, for fewer carbohydrates",
    PortionPreset.HIGHER_ENERGY: "larger main and staple portions, for more energy",
    PortionPreset.LOWER_ENERGY: "smaller main and staple, more vegetables, for less energy",
}

_NUTRIENT_LABELS = {
    "energy_kcal": "energy",
    "fat_g": "fat",
    "saturated_fat_g": "saturated fat",
    "carbohydrate_g": "carbohydrate",
    "protein_g": "protein",
    "sodium_mg": "sodium",
    "sugars_g": "sugars",
}


def _limitations(dishes: Sequence[CatalogueRecipe], unknown: Sequence[str]) -> list[Reason]:
    reasons: list[Reason] = []
    derived = [d.recipe_id for d in dishes if d.nutrition.source is NutritionSource.FOODCOM_DERIVED]
    if derived:
        reasons.append(
            Reason(
                kind=ReasonKind.LIMITATION,
                code="NUTRITION_DERIVED_FROM_PERCENT_DV",
                message="Nutrition for part of this meal is derived from Food.com %DV values; "
                "sodium and saturated fat use an assumed reference table.",
                references=tuple(derived),
            )
        )
    if unknown:
        names = ", ".join(_NUTRIENT_LABELS.get(n, n) for n in unknown)
        reasons.append(
            Reason(
                kind=ReasonKind.LIMITATION,
                code="NUTRIENTS_UNKNOWN",
                message=f"Unknown, not counted as zero: {names}.",
                references=tuple(unknown),
            )
        )
    return reasons


def _ranking_reason(
    model_version: str | None,
    fallback: FallbackReason | None,
    rank: int | None,
    total: int,
) -> Reason:
    position = f" (ranked #{rank} of {total} candidates)" if rank is not None else ""
    if model_version is None or fallback is FallbackReason.NO_HISTORY:
        return Reason(
            kind=ReasonKind.RANKING,
            code="RANKING_FALLBACK_NO_HISTORY",
            message=f"Ordered by overall popularity among home cooks; you have not saved "
            f"any seed dishes yet.{position}",
            references=() if model_version is None else (model_version,),
        )
    if fallback is FallbackReason.CANDIDATES_UNKNOWN_TO_MODEL:
        return Reason(
            kind=ReasonKind.RANKING,
            code="RANKING_FALLBACK_CANDIDATES_UNKNOWN",
            message=f"Ordered by overall popularity; the personal model has no data on these "
            f"dishes.{position}",
            references=(model_version,),
        )
    if fallback is FallbackReason.MODEL_UNAVAILABLE:
        return Reason(
            kind=ReasonKind.RANKING,
            code="RANKING_FALLBACK_MODEL_UNAVAILABLE",
            message=f"Ordered by overall popularity; the personal ranking model is not "
            f"available.{position}",
            references=(model_version,),
        )
    blend = ", blended with popularity" if "+pop" in model_version else ""
    return Reason(
        kind=ReasonKind.RANKING,
        code="RANKING_PERSONALISED",
        message=f"Ordered by a model of the dishes you liked{blend}. Scores are relative, not "
        f"a rating or a health estimate.{position}",
        references=(model_version,),
    )


def _rule_reason(rules: RuleOutcome) -> Reason:
    n = len(rules.checked_rules)
    refs = (*rules.checked_rules, *((rules.trace_id,) if rules.trace_id else ()))
    if rules.status == "PASS":
        return Reason(
            kind=ReasonKind.RULES,
            code="RULES_PASS",
            message=f"Passed all {n} applicable checks in the Rule Engine. This reflects the "
            "rules on record, not a medical guarantee.",
            references=refs,
        )
    if rules.status == "FAIL":
        return Reason(
            kind=ReasonKind.RULES,
            code="RULES_FAIL",
            message=f"Failed {len(rules.failed_rules)} of {n} checks: "
            f"{', '.join(rules.failed_rules)}.",
            references=refs,
        )
    return Reason(
        kind=ReasonKind.RULES,
        code="RULES_UNKNOWN",
        message=f"Could not be confirmed for {len(rules.unknown_rules)} of {n} checks "
        "because required information is missing; it is not treated as passing.",
        references=refs,
    )


_PLANNING_TEXT = {
    "FEASIBLE": "Chosen for {slot} by the planner, which kept the day within {c} "
    "({n} search steps).",
    "INFEASIBLE": "The planner found NO day for {slot} that keeps within {c} ({n} search "
    "steps); this meal is not a confirmed fit.",
    "TIMEOUT": "The planner stopped before finishing {slot} ({n} search steps); this meal is "
    "not a confirmed fit for {c}.",
    "INSUFFICIENT_DATA": "The planner could not check {slot} against {c} because required "
    "data is missing; this meal is not a confirmed fit.",
}


def _planning_reason(planning: PlanningOutcome) -> Reason:
    """Only FEASIBLE claims the constraints were met; every other outcome says it was not."""
    constraints = "; ".join(planning.constraints) or "the day's constraints"
    return Reason(
        kind=ReasonKind.PLANNING,
        code=f"PLANNING_{planning.outcome}",
        message=_PLANNING_TEXT[planning.outcome].format(
            slot=planning.slot_id, c=constraints, n=planning.search_nodes
        ),
        references=(planning.slot_id,),
    )


def explain_meal(
    combination: MealCombination,
    configuration: PortionConfiguration,
    dishes: Mapping[str, CatalogueRecipe],
    *,
    slot_id: str | None = None,
    ranking: CombinationRanking | None = None,
    rules: RuleOutcome | None = None,
    planning: PlanningOutcome | None = None,
    recipe_steps: Mapping[str, Sequence[str]] | None = None,
) -> MealExplanation:
    """Explain one planned meal. Every input is optional except what Member 1 owns."""
    if configuration not in combination.configurations:
        raise ValueError("configuration does not belong to this combination")
    if configuration.nutrition is None:
        raise ValueError("only validated configurations (Stage 9) can be explained")
    parts = [dishes[c.dish_id] for c in combination.components]
    options = {p.portion_id: p for d in parts for p in d.portions}
    lines = tuple(
        DishLine(
            dish_id=d.recipe_id,
            name=d.name,
            role=c.role.value,
            portion=options[p.portion_id].label,
            nutrition_source=d.nutrition.source,
            ingredients=tuple(d.ingredients),
            steps=tuple(recipe_steps.get(d.recipe_id, ())) if recipe_steps else (),
        )
        for d, c, p in zip(parts, combination.components, configuration.portions, strict=True)
    )
    reasons: list[Reason] = [
        Reason(
            kind=ReasonKind.COMPOSITION,
            code=f"TEMPLATE_{combination.template_id}",
            message=" + ".join(f"{line.name} ({line.role.lower()})" for line in lines)
            + f"; built from the {combination.template_id.lower()} meal template"
            + f" ({'/'.join(combination.cuisines)} cuisine).",
            references=tuple(line.dish_id for line in lines),
        ),
        *(
            Reason(kind=ReasonKind.COMPOSITION, code="COMPOSITION_EVIDENCE", message=e)
            for e in combination.evidence
            if e.startswith(("pairing:", "vegetable side:", "add-on:"))
        ),
        Reason(
            kind=ReasonKind.PORTION,
            code=f"PRESET_{configuration.preset.value}",
            message=f"Portions: {PRESET_TEXT[configuration.preset]}.",
            references=(configuration.configuration_id,),
        ),
    ]
    totals = configuration.nutrition.totals
    known = [
        f"{_NUTRIENT_LABELS[n]} {getattr(totals, n):g} {n.rsplit('_', 1)[1]}"
        for n in ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "sodium_mg")
        if getattr(totals, n) is not None
    ]
    reasons.append(
        Reason(
            kind=ReasonKind.NUTRITION,
            code="NUTRITION_TOTALS",
            message="Meal totals: " + ", ".join(known) + "."
            + f" Least certain source: {configuration.nutrition.source_tier.value}.",
        )
    )  # fmt: skip
    if ranking is not None:
        entry = next(
            (
                c
                for c in ranking.ranked_candidates
                if c.combination_id == combination.combination_id
            ),
            None,
        )
        reasons.append(
            _ranking_reason(
                ranking.model_version,
                ranking.fallback_reason,
                None if entry is None else entry.rank,
                len(ranking.ranked_candidates),
            )
        )
    if rules is not None:
        reasons.append(_rule_reason(rules))
    if planning is not None:
        reasons.append(_planning_reason(planning))
    reasons.extend(_limitations(parts, configuration.nutrition.unknown_nutrients))
    return MealExplanation(
        combination_id=combination.combination_id,
        configuration_id=configuration.configuration_id,
        slot_id=slot_id,
        dishes=lines,
        totals=totals,
        source_tier=configuration.nutrition.source_tier,
        unknown_nutrients=configuration.nutrition.unknown_nutrients,
        reasons=tuple(reasons),
    )


def explain_craving_recipe(
    dish: CatalogueRecipe,
    *,
    ranking: RecipeRanking | None = None,
    rules: RuleOutcome | None = None,
    steps: Sequence[str] = (),
) -> RecipeExplanation:
    """Standalone craving: standard-portion facts, NOT a fit to the day's budget (4.3)."""
    portion = standard_portion(dish)
    reasons: list[Reason] = [
        Reason(
            kind=ReasonKind.NUTRITION,
            code="CRAVING_STANDARD_PORTION_ONLY",
            message=f"Nutrition shown is for a standard portion ({portion.label}). This "
            "suggestion was not checked against what is left of today's targets.",
            references=(portion.portion_id,),
        )
    ]
    if ranking is not None:
        entry = next((c for c in ranking.ranked_candidates if c.recipe_id == dish.recipe_id), None)
        reasons.append(
            _ranking_reason(
                ranking.model_version,
                ranking.fallback_reason,
                None if entry is None else entry.rank,
                len(ranking.ranked_candidates),
            )
        )
    if rules is not None:
        reasons.append(_rule_reason(rules))
    unknown = tuple(n for n, v in portion.nutrients.model_dump().items() if v is None)
    reasons.extend(_limitations([dish], unknown))
    return RecipeExplanation(
        recipe_id=dish.recipe_id,
        name=dish.name,
        standard_portion=portion.label,
        standard_nutrients=portion.nutrients,
        ingredients=tuple(dish.ingredients),
        steps=tuple(steps),
        reasons=tuple(reasons),
    )
