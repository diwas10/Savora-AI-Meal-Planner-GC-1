"""Adapter: Member 1 catalogue export -> Member 2 symbolic contracts (scenario A).

Member 2's contracts (`savora_ai.schemas.candidates`, `.combinations`, `.daily`) need
decisions that are still open (docs/member1_catalogue_contract.md section 5). This module
assumes ONE answer to each, written down below in `SCENARIO_A`, so the real catalogue can
run through Member 2's Rule Engine and daily CSP today. If Member 2 decides differently,
only this block and the functions that read it change.

Scenario A assumptions:

1. Portions: Food.com quantities are `QuantityUnit.SERVING`; USDA quantities are grams.
2. Food.com-derived nutrition counts as KNOWN (`complete=True`); its tier is kept in the
   evidence. A None value is an incomplete fact and can never pass a rule.
3. Member 2's daily CSP supports ONE whole-meal measurement and requires it in mg, so
   it carries the meal's SODIUM total as an integer mg, rounded half-up from the
   validated configuration total. Energy (kcal) cannot be passed yet: a gap to raise.
4. Evidence is labelled SYNTHETIC: Member 2's contracts accept nothing else yet. This
   adapter must not feed production until a production evidence path is approved.
5. Ingredients are listed but NOT mapped to canonical ingredient entities (no mapping
   exists yet), so coverage declares UNRESOLVED_MAPPING and ingredient rules stay UNKNOWN.
6. Member 2's Rule Engine admits only a fixed SYNTHETIC attribute vocabulary, so our real
   facts are published under those names (`Scenario.fact_names`): classification settled
   -> synthetic_flag; sodium per serving -> synthetic_serving_quantity (mg, PER_SERVING);
   sodium per 100 g -> synthetic_quantity (mg, PER_100_G); template-built meal ->
   synthetic_combination_roles_compatible / _composition_complete. When real names are
   approved, only this table changes.

The adapter only builds records Member 1 owns. The knowledge base, rule context and
manifests belong to Members 2 and 3; `graph_entities` returns the recipe and role
reference nodes they must include in the food graph.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from savora_ai.core.food_data.models import CatalogueRecipe
from savora_ai.core.meal_composition.models import MealCombination, PortionConfiguration
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    FactSubjectKind,
    IngredientCoverage,
    IngredientGapReason,
    IngredientLine,
    IngredientMappingStatus,
    MeasurementBasis,
    RuleContext,
    VersionedFact,
)
from savora_ai.schemas.combinations import (
    CombinationComponent,
    CombinationFacts,
    CombinationMeasurementBasis,
    CombinationObservation,
    ComponentQuantity,
    PortionState,
    PreparationBinding,
    QuantityUnit,
    RecipeSnapshotReference,
)
from savora_ai.schemas.daily import (
    DailyMealOption,
    DailyPlanningRequest,
    DailySlotDomain,
    DailySourceReference,
    DailySourceSnapshot,
    FixedMealMeasurement,
    MealOptionReference,
    MealSlot,
    MealSlotSuitability,
)
from savora_ai.schemas.enums import CulinaryRole, NutritionBasis, PortionUnit
from savora_ai.schemas.food_graph import FoodEntity, FoodEntityKind
from savora_ai.schemas.knowledge import EvidenceReference, MeasurementUnit, RuleEnvironment
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot
from savora_ai.schemas.reasoning import FactObservation


@dataclass(frozen=True)
class Scenario:
    name: str
    environment: RuleEnvironment
    foodcom_nutrition_known: bool
    meal_measurement_nutrient: str  # a NutrientVector field, carried in mg
    fact_names: Mapping[str, str]  # our fact -> the attribute Member 2's KB admits
    basis_evidence: Mapping[NutritionBasis, tuple[str, str]]  # Member 2's basis identity


# The single place where assumed Member 2 decisions live (see the module docstring).
SCENARIO_A = Scenario(
    name="scenario-a",
    environment=RuleEnvironment.SYNTHETIC,
    foodcom_nutrition_known=True,
    meal_measurement_nutrient="sodium_mg",
    fact_names={
        "classification_settled": "synthetic_flag",
        "sodium_per_serving_mg": "synthetic_serving_quantity",
        "sodium_per_100_g_mg": "synthetic_quantity",
        "meal_roles_compatible": "synthetic_combination_roles_compatible",
        "meal_composition_complete": "synthetic_combination_composition_complete",
    },
    basis_evidence={
        NutritionBasis.PER_SERVING: ("synthetic-serving", "1"),
        NutritionBasis.PER_100_G: ("synthetic-per-100-g", "1"),
    },
)
MEAL_MEASUREMENT_UNIT = MeasurementUnit.MG  # Member 2's daily measurement requires mg
_BASES = {
    NutritionBasis.PER_SERVING: MeasurementBasis.PER_SERVING,
    NutritionBasis.PER_100_G: MeasurementBasis.PER_100_G,
}
_SODIUM_FACT = {
    NutritionBasis.PER_SERVING: "sodium_per_serving_mg",
    NutritionBasis.PER_100_G: "sodium_per_100_g_mg",
}
_SLOTS = {"BREAKFAST": MealSlot.BREAKFAST, "LUNCH": MealSlot.LUNCH, "DINNER": MealSlot.DINNER}


def evidence(
    catalogue_version: str, kind: str, scenario: Scenario = SCENARIO_A
) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=f"m1-{kind}",
        version=catalogue_version,
        source=f"Savora Member 1 catalogue export ({scenario.name}; not production evidence)",
        locator=f"urn:savora:catalogue:{catalogue_version}:{kind}",
        environment=scenario.environment,
    )


def recipe_entity_id(dish_id: str) -> str:
    return f"recipe:{dish_id}"


def role_entity_id(role: CulinaryRole) -> str:
    return f"role:{role.value}"


def graph_entities(
    dishes: Iterable[CatalogueRecipe], catalogue_version: str
) -> tuple[FoodEntity, ...]:
    """Recipe and culinary-role reference nodes Member 2's food graph must contain."""
    ev = (evidence(catalogue_version, "catalogue"),)
    recipes = [
        FoodEntity(
            entity_id=recipe_entity_id(d.recipe_id),
            version=catalogue_version,
            kind=FoodEntityKind.RECIPE_REFERENCE,
            canonical_name=d.name,
            catalogue_reference=d.recipe_id,
            evidence=ev,
        )
        for d in sorted(dishes, key=lambda d: d.recipe_id)
    ]
    roles = [
        FoodEntity(
            entity_id=role_entity_id(role),
            version=catalogue_version,
            kind=FoodEntityKind.CULINARY_ROLE_REFERENCE,
            canonical_name=role.value.replace("_", " ").lower(),
            catalogue_reference=role_entity_id(role),
            evidence=ev,
        )
        for role in CulinaryRole
    ]
    return (*recipes, *roles)


def _sodium_fact(dish: CatalogueRecipe, version: str, scenario: Scenario) -> VersionedFact:
    """Real sodium on the dish's own basis; unknown stays an incomplete null fact."""
    name = scenario.fact_names[_SODIUM_FACT[dish.nutrition.basis]]
    value = dish.nutrition.values.sodium_mg
    known = value is not None and (
        scenario.foodcom_nutrition_known or dish.nutrition.source.value != "FOODCOM_DERIVED"
    )
    basis_id, basis_version = scenario.basis_evidence[dish.nutrition.basis]
    source_ev = evidence(version, f"nutrition-{dish.nutrition.source.value.lower()}", scenario)
    return VersionedFact(
        fact_id=name,
        version=version,
        subject_kind=FactSubjectKind.RECIPE,
        subject_id=dish.recipe_id,
        subject_version=version,
        catalogue_version=version,
        observation=FactObservation(
            fact_id=name,
            value=value,
            complete=known,
            unit=None if value is None else MeasurementUnit.MG,
            evidence=(source_ev,),
        ),
        measurement_basis=None if value is None else _BASES[dish.nutrition.basis],
        basis_reference=None
        if value is None
        else EvidenceReference(
            evidence_id=basis_id,
            version=basis_version,
            source=f"Savora Member 1 catalogue export ({scenario.name})",
            locator=f"urn:savora:basis:{basis_id}",
            environment=scenario.environment,
        ),
    )


def candidate_facts(
    dish: CatalogueRecipe, catalogue_version: str, graph_id: str, graph_version: str,
    scenario: Scenario = SCENARIO_A,
) -> CandidateRecipeFacts:  # fmt: skip
    """One dish as Member 2's subject-bound candidate snapshot."""
    v = catalogue_version
    ev = (evidence(v, "catalogue", scenario),)
    lines = tuple(
        IngredientLine(
            line_id=f"{dish.recipe_id}:line:{i}",
            version=v,
            recipe_id=dish.recipe_id,
            recipe_version=v,
            catalogue_version=v,
            mapping_status=IngredientMappingStatus.UNRESOLVED,  # assumption 5
            subingredients_complete=True,
            gap_reasons=(IngredientGapReason.UNRESOLVED_MAPPING,),
            evidence=ev,
        )
        for i, _ in enumerate(dish.ingredients)
    )
    settled_name = scenario.fact_names["classification_settled"]
    settled = VersionedFact(
        fact_id=settled_name,
        version=v,
        subject_kind=FactSubjectKind.RECIPE,
        subject_id=dish.recipe_id,
        subject_version=v,
        catalogue_version=v,
        observation=FactObservation(
            fact_id=settled_name,
            value=dish.classification_status.value in ("AUTO", "CURATED"),
            complete=True,
            evidence=ev,
        ),
    )
    return CandidateRecipeFacts.build(
        dict(
            recipe_id=dish.recipe_id,
            recipe_version=v,
            catalogue_version=v,
            graph_id=graph_id,
            graph_version=graph_version,
            graph_recipe_entity_id=recipe_entity_id(dish.recipe_id),
            graph_recipe_reference=FoodEntity(
                entity_id=recipe_entity_id(dish.recipe_id),
                version=v,
                kind=FoodEntityKind.RECIPE_REFERENCE,
                canonical_name=dish.name,
                catalogue_reference=dish.recipe_id,
                evidence=ev,
            ),
            snapshot_id=f"{dish.recipe_id}:snapshot",
            snapshot_version=v,
            ingredient_coverage=IngredientCoverage(
                coverage_id=f"{dish.recipe_id}:ingredients",
                version=v,
                recipe_id=dish.recipe_id,
                recipe_version=v,
                catalogue_version=v,
                lines=lines,
                inventory_complete=True,  # the full ingredient list, without quantities
                mapping_complete=False,
                subingredients_complete=True,
                gap_reasons=(IngredientGapReason.UNRESOLVED_MAPPING,),
                evidence=ev,
            ),
            facts=(settled, _sodium_fact(dish, v, scenario)),
            evidence=ev,
        )
    )


def round_half_up(value: float) -> int:
    """Integer total for Member 2's FixedMealMeasurement (assumption 3); no banker's rounding."""
    return int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def option_id(configuration: PortionConfiguration) -> str:
    """`#` is not allowed in Member 2's opaque IDs: `<combinationId>:<PRESET>`."""
    return configuration.configuration_id.replace("#", ":")


@dataclass(frozen=True)
class KnowledgeBinding:
    """The independently selected KB and context the meal snapshots are bound to."""

    knowledge: KnowledgeBaseSnapshot
    context: RuleContext


def meal_option(
    combination: MealCombination,
    configuration: PortionConfiguration,
    candidates: Mapping[str, CandidateRecipeFacts],
    dishes: Mapping[str, CatalogueRecipe],
    binding: KnowledgeBinding,
    provider: DailySourceReference,
    scenario: Scenario = SCENARIO_A,
) -> DailyMealOption:
    """One validated portion configuration as a FIXED daily meal option."""
    if configuration.nutrition is None:
        raise ValueError(f"{configuration.configuration_id} has not been validated (Stage 9)")
    total = getattr(configuration.nutrition.totals, scenario.meal_measurement_nutrient)
    kb, context = binding.knowledge, binding.context
    v = kb.catalogue_version
    ev = (evidence(v, "composition", scenario),)
    parts: list[CombinationComponent] = []
    for ref, portion in zip(combination.components, configuration.portions, strict=True):
        candidate = candidates[ref.dish_id]
        snapshot = RecipeSnapshotReference(
            recipe_id=candidate.recipe_id,
            recipe_version=candidate.recipe_version,
            snapshot_id=candidate.snapshot_id,
            snapshot_version=candidate.snapshot_version,
            content_digest=candidate.content_digest,
            catalogue_version=candidate.catalogue_version,
        )
        basis = evidence(v, f"basis-{dishes[ref.dish_id].nutrition.basis.value.lower()}", scenario)
        preparation = PreparationBinding(
            preparation_id=f"{ref.dish_id}:as-catalogued",
            version=v,
            recipe_snapshot=snapshot,
            basis_reference=basis,
            evidence=ev,
        )
        serving = portion.unit is PortionUnit.SERVING
        amount = portion.quantity if serving else portion.grams  # assumption 1
        if amount is None:
            raise ValueError(f"{portion.portion_id} has neither servings nor grams")
        parts.append(
            CombinationComponent(
                component_id=ref.slot,
                recipe_snapshot=snapshot,
                preparation=preparation,
                quantity=ComponentQuantity(
                    amount=amount,
                    unit=QuantityUnit.SERVING if serving else QuantityUnit.G,
                    preparation_id=preparation.preparation_id,
                    preparation_version=preparation.version,
                    basis_reference=basis,
                    portion_reference=evidence(v, "portion", scenario),
                    evidence=ev,
                ),
                role_references=(
                    FoodEntity(
                        entity_id=role_entity_id(ref.role),
                        version=v,
                        kind=FoodEntityKind.CULINARY_ROLE_REFERENCE,
                        canonical_name=ref.role.value.replace("_", " ").lower(),
                        catalogue_reference=role_entity_id(ref.role),
                        evidence=(evidence(v, "catalogue", scenario),),
                    ),
                ),
                evidence=ev,
            )
        )
    oid = option_id(configuration)
    combo = CombinationFacts.build(
        dict(
            combination_id=combination.combination_id,
            version=v,
            snapshot_id=f"{oid}:snapshot",
            snapshot_version=v,
            components=tuple(parts),
            composition_complete=True,
            composition_gap_reasons=(),
            portion_state=PortionState.FIXED,
            portion_configuration_id=oid,
            portion_configuration_version=v,
            observations=tuple(
                CombinationObservation(
                    fact_id=scenario.fact_names[name],
                    version=v,
                    combination_id=combination.combination_id,
                    combination_version=v,
                    observation=FactObservation(
                        fact_id=scenario.fact_names[name], value=True, complete=True, evidence=ev
                    ),
                )
                # The composer only emits meals from curated templates and pairings, whole.
                for name in ("meal_roles_compatible", "meal_composition_complete")
            ),
            context_id=context.context_id,
            context_version=context.version,
            context_digest=context.content_digest,
            kb_id=kb.kb_id,
            kb_version=kb.version,
            kb_digest=kb.content_digest,
            graph_id=kb.graph_id,
            graph_version=kb.graph_version,
            catalogue_version=kb.catalogue_version,
            taxonomy_version=kb.taxonomy_version,
            check_catalogue_version=kb.check_catalogue_version,
            evidence=ev,
        )
    )
    reference = MealOptionReference(
        option_id=oid,
        combination_id=combo.combination_id,
        combination_version=combo.version,
        snapshot_id=combo.snapshot_id,
        snapshot_version=combo.snapshot_version,
        combination_digest=combo.content_digest,
        portion_state=combo.portion_state,
        portion_configuration_id=combo.portion_configuration_id,
        portion_configuration_version=combo.portion_configuration_version,
    )
    return DailyMealOption(
        reference=reference,
        combination=combo,
        suitability=MealSlotSuitability(
            option=reference,
            source=provider,
            slots=tuple(_SLOTS[m.value] for m in combination.meal_types),
            complete=True,
            evidence=ev,
        ),
        measurements=(
            FixedMealMeasurement(
                option=reference,
                source=provider,
                # assumption 3; an unknown total stays unknown (None, incomplete)
                value=None if total is None else round_half_up(total),
                complete=total is not None,
                unit=MEAL_MEASUREMENT_UNIT,
                measurement_basis=CombinationMeasurementBasis.FIXED_PORTION_TOTAL,
                components=tuple(parts),
                basis_reference=evidence(
                    v, f"meal-total-{scenario.meal_measurement_nutrient}", scenario
                ),
                evidence=ev,
            ),
        ),
    )


def daily_request(
    request_id: str,
    day_id: str,
    options: Sequence[DailyMealOption],
    domains: Mapping[MealSlot, Sequence[str]],
    binding: KnowledgeBinding,
    source_id: str = "m1-catalogue-meals",
) -> tuple[DailyPlanningRequest, DailySourceSnapshot]:
    """The day's source snapshot and request; `domains` names option IDs per slot."""
    context = binding.context
    v = binding.knowledge.catalogue_version
    source = DailySourceSnapshot.build(
        dict(
            source_id=source_id,
            version=v,
            context=context,
            options=tuple(options),
            evidence=(evidence(v, "meal-options"),),
        )
    )
    by_id = {o.reference.option_id: o.reference for o in options}
    request = DailyPlanningRequest.build(
        dict(
            request_id=request_id,
            version=v,
            day_id=day_id,
            context_id=context.context_id,
            context_version=context.version,
            context_digest=context.content_digest,
            expected_source=DailySourceReference(
                source_id=source.source_id,
                version=source.version,
                content_digest=source.content_digest,
            ),
            source=source,
            domains=tuple(
                DailySlotDomain(slot=slot, options=tuple(by_id[i] for i in domains[slot]))
                for slot in MealSlot
            ),
        )
    )
    return request, source
