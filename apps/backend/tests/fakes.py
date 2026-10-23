"""Contract-true FakeAiGateway built from real Pydantic pipeline models."""

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, timedelta
from typing import Any, get_args

from savora_ai.core.explainability.explanation import (
    PlanningOutcome,
    RuleOutcome,
    explain_craving_recipe,
    explain_meal,
)
from savora_ai.core.food_data.models import NutrientVector
from savora_ai.core.meal_composition.member2_adapter import option_id
from savora_ai.core.pipelines import (
    CatalogueBundle,
    CravingRecommendation,
    CravingStatus,
    PlannedMeal,
    PlanningProfile,
    PlanStatus,
    ReplacementOptions,
    SwapProof,
    WeekPlan,
    confirm_seeds,
    revalidate_seeds,
    suggest_replacements,
    suggest_seeds,
)
from savora_ai.core.pipelines.craving import CravingCounts, CravingItem
from savora_ai.core.pipelines.planning import DayTotals, SearchSummary
from savora_ai.core.pipelines.profile import combination_allowed, safety_verification
from savora_ai.core.recommendation.ranking import FallbackReason
from savora_ai.core.recommendation.seeds import DEFAULT_SUGGESTIONS, SeedSuggestions
from savora_ai.schemas.compact_swap import CompactNutrientTotal
from savora_ai.schemas.craving import CravingRequest
from savora_ai.schemas.daily import DailyOutcome
from savora_ai.schemas.enums import MealType, PortionPreset
from savora_ai.schemas.nutrients_v2 import Nutrient, native_unit
from savora_backend.core.catalogue import get_catalogue_bundle


class FakeAiGateway:
    """Canned, fast AI gateway returning real Pydantic pipeline DTOs for tests."""

    def __init__(
        self,
        bundle: CatalogueBundle | None = None,
        *,
        fail_plan: bool = False,
        plan_status: PlanStatus = PlanStatus.FEASIBLE,
        swap_status: PlanStatus = PlanStatus.FEASIBLE,
        proof_status: str = "VALID",
    ) -> None:
        self._bundle = bundle or get_catalogue_bundle()
        self.fail_plan = fail_plan
        self.plan_status = plan_status
        self.swap_status = swap_status
        self.proof_status = proof_status
        self.proved: list[dict[str, object]] = []
        self.last_swap: dict[str, object] = {}
        self.planned_profiles: list[PlanningProfile] = []

    @property
    def bundle(self) -> CatalogueBundle:
        return self._bundle

    async def craving(
        self,
        request: CravingRequest,
        profile: PlanningProfile,
        *,
        top_k: int = 10,
    ) -> CravingRecommendation:
        safety = safety_verification(profile)
        if request.requires_clarification:
            return CravingRecommendation(
                status=CravingStatus.NEEDS_CLARIFICATION,
                request=request,
                items=(),
                model_version=None,
                fallback_reason=None,
                unknown_cuisine_ids=(),
                unmatched_flavor_tags=(),
                counts=CravingCounts(retrieved=0, screened_out=0, rule_checked=0, rule_excluded=0),
                kb_id="gc1-stand-in-kb",
                kb_version="stand-in-0.1",
                safety=safety,
            )
        dishes = [
            d
            for d in sorted(self._bundle.dishes.values(), key=lambda x: x.recipe_id)
            if d.training_interactions is not None
        ][: min(top_k, 3)]
        items = tuple(
            CravingItem(
                recipe_id=d.recipe_id,
                name=d.name,
                rank=idx + 1,
                score=round(1.0 / (idx + 1), 4),
                cuisines=d.cuisines,
                explanation=explain_craving_recipe(
                    d,
                    rules=RuleOutcome(status="PASS", checked_rules=("STAND_IN_RULE_1",)),
                ),
            )
            for idx, d in enumerate(dishes)
        )
        return CravingRecommendation(
            status=CravingStatus.OK,
            request=request,
            items=items,
            model_version="popularity-fallback-v1",
            fallback_reason=FallbackReason.MODEL_UNAVAILABLE,
            unknown_cuisine_ids=(),
            unmatched_flavor_tags=(),
            counts=CravingCounts(
                retrieved=len(items),
                screened_out=0,
                rule_checked=len(items),
                rule_excluded=0,
            ),
            kb_id="gc1-stand-in-kb",
            kb_version="stand-in-0.1",
            safety=safety,
        )

    def _build_meals(
        self,
        start_date: date,
        *,
        profile: PlanningProfile | None = None,
        override_slot: str | None = None,
        exclude_combos: set[str] | None = None,
        replacement: str | None = None,
    ) -> tuple[tuple[PlannedMeal, ...], tuple[DayTotals, ...]]:
        combos = [
            c
            for c in sorted(self._bundle.combinations.values(), key=lambda x: x.combination_id)
            if any(
                cfg.preset is PortionPreset.STANDARD and cfg.nutrition is not None
                for cfg in c.configurations
            )
            # Like the real planner, only meals the profile allows.
            and (profile is None or combination_allowed(c, self._bundle.dishes, profile))
        ]
        meals: list[PlannedMeal] = []
        day_totals: list[DayTotals] = []
        exclude = exclude_combos or set()
        for day_idx in range(1, 8):
            cal_date = (start_date + timedelta(days=day_idx - 1)).isoformat()
            day_meals: list[PlannedMeal] = []
            for m_idx, meal_type in enumerate(
                (MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER)
            ):
                slot_id = f"D{day_idx}_{meal_type.value}"
                combo = combos[(day_idx * 3 + m_idx) % len(combos)]
                if slot_id == override_slot and replacement is not None:
                    combo = self._bundle.combinations[replacement]
                elif slot_id == override_slot:
                    combo = next(
                        c
                        for c in combos
                        if c.combination_id != combo.combination_id
                        and c.combination_id not in exclude
                    )
                config = next(
                    cfg
                    for cfg in combo.configurations
                    if cfg.preset is PortionPreset.STANDARD and cfg.nutrition is not None
                )
                oid = option_id(config)
                exp = explain_meal(
                    combo,
                    config,
                    self._bundle.dishes,
                    slot_id=slot_id,
                    rules=RuleOutcome(status="PASS", checked_rules=("STAND_IN_RULE_1",)),
                    planning=PlanningOutcome(
                        outcome="FEASIBLE",
                        slot_id=slot_id,
                        search_nodes=21,
                        constraints=("stand-in: every slot resolved",),
                    ),
                )
                pm = PlannedMeal(
                    slot_id=slot_id,
                    day_index=day_idx,
                    calendar_date=cal_date,
                    meal_type=meal_type,
                    option_id=oid,
                    combination_id=combo.combination_id,
                    configuration_id=config.configuration_id,
                    preset=config.preset,
                    explanation=exp,
                )
                meals.append(pm)
                day_meals.append(pm)
            day_totals.append(
                DayTotals(
                    day_index=day_idx,
                    calendar_date=cal_date,
                    totals=NutrientVector(
                        energy_kcal=1800.0,
                        protein_g=75.0,
                        carbohydrate_g=220.0,
                        fat_g=60.0,
                        saturated_fat_g=15.0,
                        sodium_mg=1400.0,
                        sugars_g=30.0,
                    ),
                )
            )
        return tuple(meals), tuple(day_totals)

    async def plan_week(
        self,
        profile: PlanningProfile,
        *,
        week_id: str,
        start_date: date,
    ) -> WeekPlan:
        self.planned_profiles.append(profile)
        if self.fail_plan:
            raise RuntimeError("Simulated solver crash")
        safety = safety_verification(profile)
        if self.plan_status is not PlanStatus.FEASIBLE:
            return WeekPlan(
                status=self.plan_status,
                workflow="WEEKLY_PLAN",
                week_id=week_id,
                start_date=start_date.isoformat(),
                profile_id=profile.profile_id,
                profile_version=profile.profile_version,
                catalogue_version=self._bundle.version,
                meals=(),
                day_totals=(),
                model_version="popularity-fallback-v1",
                fallback_reason=FallbackReason.MODEL_UNAVAILABLE,
                kb_id="gc1-stand-in-kb",
                kb_version="stand-in-0.1",
                search=None,
                message=f"Simulated {self.plan_status.value}",
                safety=safety,
            )
        meals, totals = self._build_meals(start_date, profile=profile)
        return WeekPlan(
            status=PlanStatus.FEASIBLE,
            workflow="WEEKLY_PLAN",
            week_id=week_id,
            start_date=start_date.isoformat(),
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            catalogue_version=self._bundle.version,
            meals=meals,
            day_totals=totals,
            model_version="popularity-fallback-v1",
            fallback_reason=FallbackReason.MODEL_UNAVAILABLE,
            kb_id="gc1-stand-in-kb",
            kb_version="stand-in-0.1",
            search=SearchSummary(
                outcome=DailyOutcome.FEASIBLE,
                nodes=21,
                exhaustive=False,
                diagnostics=(),
                seconds=0.01,
            ),
            message="21 meals verified by the weekly CSP against the stand-in rule set.",
            safety=safety,
        )

    async def substitute(
        self,
        profile: PlanningProfile,
        *,
        current: Mapping[str, str],
        slot: str,
        week_id: str,
        start_date: date,
        exclude_combination_ids: Iterable[str] = (),
        replacement_combination_id: str | None = None,
        preference: CravingRequest | None = None,
    ) -> WeekPlan:
        del current
        self.last_swap = {"replacement": replacement_combination_id, "preference": preference}
        safety = safety_verification(profile)
        if self.swap_status is not PlanStatus.FEASIBLE:
            return WeekPlan(
                status=self.swap_status,
                workflow="PLANNED_SWAP",
                week_id=week_id,
                start_date=start_date.isoformat(),
                profile_id=profile.profile_id,
                profile_version=profile.profile_version,
                catalogue_version=self._bundle.version,
                meals=(),
                day_totals=(),
                model_version="popularity-fallback-v1",
                fallback_reason=FallbackReason.MODEL_UNAVAILABLE,
                kb_id="gc1-stand-in-kb",
                kb_version="stand-in-0.1",
                search=None,
                message=f"Simulated {self.swap_status.value}",
                safety=safety,
            )
        meals, totals = self._build_meals(
            start_date,
            profile=profile,
            override_slot=slot,
            exclude_combos=set(exclude_combination_ids),
            replacement=replacement_combination_id,
        )
        return WeekPlan(
            status=PlanStatus.FEASIBLE,
            workflow="PLANNED_SWAP",
            week_id=week_id,
            start_date=start_date.isoformat(),
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            catalogue_version=self._bundle.version,
            meals=meals,
            day_totals=totals,
            model_version="popularity-fallback-v1",
            fallback_reason=FallbackReason.MODEL_UNAVAILABLE,
            kb_id="gc1-stand-in-kb",
            kb_version="stand-in-0.1",
            search=SearchSummary(
                outcome=DailyOutcome.FEASIBLE,
                nodes=21,
                exhaustive=False,
                diagnostics=(),
                seconds=0.01,
            ),
            message="Replacement meal verified by the weekly CSP.",
            safety=safety,
        )

    async def prove_swap(
        self,
        profile: PlanningProfile,
        *,
        saved: Mapping[str, str],
        slot: str,
        replacement_option_id: str,
        plan_id: str,
        revision: int,
        owner_id: str,
        start_date: date,
        calculator_payload: Mapping[str, Any] | None = None,
    ) -> SwapProof:
        del profile, start_date
        self.proved.append(
            {
                "saved": dict(saved),
                "slot": slot,
                "option": replacement_option_id,
                "plan": plan_id,
                "revision": revision,
                "owner": owner_id,
                "calculatorPayload": dict(calculator_payload or {}),
            }
        )
        valid = self.proof_status == "VALID"
        return SwapProof(
            protocol="compact-planned-swap-input.v1",
            status=self.proof_status,  # type: ignore[arg-type]
            verified=valid,
            reason="simulated",
            certificate_digest="c" * 64 if valid else None,
            input_digest="i" * 64,
            changed_day_totals=tuple(
                CompactNutrientTotal(nutrient=n, unit=native_unit(n), value="1.000", complete=True)
                for n in get_args(Nutrient)
            )
            if valid
            else (),
            seconds=0.01,
        )

    async def replacements(
        self,
        profile: PlanningProfile,
        *,
        current: Mapping[str, str],
        slot: str,
        preference: CravingRequest | None = None,
        exclude_combination_ids: Iterable[str] = (),
        limit: int = 6,
    ) -> ReplacementOptions:
        # The real (fast) ranking step; the slow CSP is what the fake replaces.
        return suggest_replacements(
            profile,
            self._bundle,
            current=current,
            slot=slot,
            preference=preference,
            exclude_combination_ids=exclude_combination_ids,
            limit=limit,
        )

    async def seeds(
        self,
        profile: PlanningProfile,
        *,
        limit: int = DEFAULT_SUGGESTIONS,
    ) -> SeedSuggestions:
        return suggest_seeds(profile, self._bundle, limit=limit)

    async def confirm_seeds(
        self,
        profile: PlanningProfile,
        picks: Sequence[str],
    ) -> tuple[str, ...]:
        return confirm_seeds(profile, self._bundle, picks)

    async def revalidate_seeds(
        self,
        profile: PlanningProfile,
    ) -> tuple[str, ...]:
        return revalidate_seeds(profile, self._bundle)
