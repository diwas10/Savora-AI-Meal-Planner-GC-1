"""Real native vectors and M1 targets over an explicitly synthetic stand-in KB."""

import os
from datetime import date
from pathlib import Path

from savora_ai.core.pipelines.catalogue import load_catalogue_export
from savora_ai.core.pipelines.planning import _ranked_meals, _rotation, _standard
from savora_ai.core.pipelines.profile import DietPattern, PlanningProfile
from savora_ai.evals.real_catalogue_inputs import build_real_week_inputs
from savora_ai.schemas.enums import CuisinePolicy
from savora_ai.schemas.weekly import WeeklyTrial, WeeklyTrialChoice


def test_real_native_vectors_and_independent_proof():
    default = Path(__file__).resolve().parents[3] / "Data/catalogue"
    directory = Path(os.environ.get("SAVORA_INTEGRATION_CATALOGUE", str(default)))
    bundle = load_catalogue_export(directory)
    profile = PlanningProfile(
        profile_id="integration-strict-indian-vegetarian",
        profile_version=1,
        diet=DietPattern.VEGETARIAN,
        cuisine_policy=CuisinePolicy.STRICT,
        cuisines=("Indian",),
    )
    _, by_meal = _ranked_meals(bundle, profile, None)
    chosen = {}
    for slot, combo in _rotation(by_meal).items():
        config = _standard(combo)
        assert config is not None
        chosen[slot] = (combo, config)
    inputs = build_real_week_inputs(
        bundle, profile, "real-benchmark-week", date(2026, 10, 26), chosen
    )
    trial = WeeklyTrial.build(
        dict(
            request_digest=inputs.request.content_digest,
            week_id=inputs.request.week_id,
            week_version=inputs.request.week_version,
            start_date=inputs.request.start_date,
            choices=tuple(
                WeeklyTrialChoice(day=day.day, slot=domain.slot, option=domain.options[0])
                for day in inputs.request.days
                for domain in day.domains
            ),
        )
    )
    _check_native_vectors(bundle, inputs, trial)


def _check_native_vectors(bundle, inputs, trial):
    import hashlib
    from datetime import UTC, datetime
    from decimal import Decimal
    from types import SimpleNamespace

    from test_weekly_bounds import forward_limits
    from test_weekly_value_priority import priority

    from savora_ai.core.meal_composition.member2_adapter import evidence, option_id
    from savora_ai.core.nutrition.models import TargetInput
    from savora_ai.core.nutrition.targets import calculate_nutrition_targets
    from savora_ai.core.reasoning.nutrients_v2 import (
        evaluate_weekly_nutrients,
        verify_weekly_nutrient_assessment,
    )
    from savora_ai.core.reasoning.weekly_search_v2 import (
        solve_weekly_plan_v2,
        verify_weekly_plan_v2,
    )
    from savora_ai.schemas.daily import DailySourceReference
    from savora_ai.schemas.enums import ActivityLevel, Goal, Sex
    from savora_ai.schemas.nutrients_v2 import (
        NutrientBandV2,
        NutrientMeasurementV2,
        OptionNutrientsV2,
        WeeklyNutrientContractV2,
        native_unit,
    )
    from savora_ai.schemas.weekly_search_v2 import WeeklyNutrientSearchStrategyV2

    # Fictional adult target inputs; real validated catalogue vectors. No clinical rules.
    targets = calculate_nutrition_targets(
        TargetInput(
            age_years=30,
            sex=Sex.MALE,
            height_cm=170.0,
            weight_kg=70.0,
            activity=ActivityLevel.MODERATE,
            goal=Goal.MAINTAIN,
        ),
        profile_version=1,
        calculated_at=datetime(2026, 10, 22, tzinfo=UTC),
    )
    target_source = DailySourceReference(
        source_id="real-data-fictional-target-fixture",
        version="targets-0.2",
        content_digest=hashlib.sha256(targets.model_dump_json(by_alias=True).encode()).hexdigest(),
    )
    field_names = (
        "energy_kcal",
        "protein_g",
        "carbs_g",
        "fat_g",
        "saturated_fat_g",
        "sodium_mg",
        "sugars_g",
    )
    vectors = []
    configurations = {}
    for option in inputs.options.values():
        combo = bundle.combinations[option.reference.combination_id]
        config = next(c for c in combo.configurations if option_id(c) == option.reference.option_id)
        assert config.nutrition is not None
        configurations[option.reference.option_id] = config
        key = hashlib.sha256(option.reference.option_id.encode()).hexdigest()[:32]
        source = DailySourceReference(
            source_id="real-native-" + key,
            version=bundle.version,
            content_digest=hashlib.sha256(
                config.model_dump_json(by_alias=True).encode()
            ).hexdigest(),
        )
        measurements = tuple(
            NutrientMeasurementV2.model_validate(
                dict(
                    nutrient=name,
                    unit=native_unit(name),
                    value=str(
                        getattr(
                            config.nutrition.totals, "carbohydrate_g" if name == "carbs_g" else name
                        )
                    )
                    if getattr(
                        config.nutrition.totals, "carbohydrate_g" if name == "carbs_g" else name
                    )
                    is not None
                    else None,
                    complete=getattr(
                        config.nutrition.totals, "carbohydrate_g" if name == "carbs_g" else name
                    )
                    is not None,
                    source=source,
                    evidence=(evidence(bundle.version, "native-vector-" + key),),
                )
            )
            for name in field_names
        )
        vectors.append(
            OptionNutrientsV2(
                option=option.reference,
                basis="ABSOLUTE_FIXED_PORTION",
                reference_basis="VALIDATED_ABSOLUTE_AGGREGATE",
                mass_g=None,
                measurements=measurements,
            )
        )
    bands = []
    bounds = [
        ("energy_kcal", targets.energy_kcal),
        *(
            ("carbs_g" if b.nutrient == "carbohydrate_g" else b.nutrient, b.bounds)
            for b in targets.nutrient_bounds
        ),
    ]
    for day in range(1, 8):
        for nutrient, bound in bounds:
            bands.append(
                NutrientBandV2.model_validate(
                    dict(
                        band_id=f"target-{day}-{nutrient}",
                        scope="DAY",
                        day_index=day,
                        nutrient=nutrient,
                        unit="kcal" if nutrient == "energy_kcal" else "g",
                        lower=None if bound.min is None else str(bound.min),
                        upper=None if bound.max is None else str(bound.max),
                        source=target_source,
                        evidence=(evidence(bundle.version, "fictional-general-target-fixture"),),
                    )
                )
            )
    contract = WeeklyNutrientContractV2(
        request_digest=inputs.request.content_digest,
        weekly_source=inputs.request.expected_source,
        profile_id=inputs.context.profile_id,
        profile_version=inputs.context.profile_version,
        catalogue_version=bundle.version,
        target=target_source,
        options=tuple(vectors),
        bands=tuple(bands),
    )
    assessment = evaluate_weekly_nutrients(inputs.request, trial, contract=contract)
    assert (
        verify_weekly_nutrient_assessment(
            assessment,
            request=inputs.request,
            trial=trial,
            contract=contract,
        )
        == assessment
    )
    first_day = trial.choices[:3]
    literal_energy = sum(
        Decimal(str(configurations[c.option.option_id].nutrition.totals.energy_kcal))
        for c in first_day
    )
    assert assessment.assessments[0].total_milli_native_units == int(literal_energy * 1000)
    # Preserve the pinned export's actual completeness, including nulls where present.
    # The newer M1 snapshot may declare sugar known; this is not source approval.
    for vector in vectors:
        original = configurations[vector.option.option_id].nutrition.totals
        for measurement in vector.measurements:
            key = "carbohydrate_g" if measurement.nutrient == "carbs_g" else measurement.nutrient
            value = getattr(original, key)
            assert measurement.complete is (value is not None)
            assert measurement.value == (None if value is None else str(value))
    strategy = WeeklyNutrientSearchStrategyV2(
        declaration=priority(SimpleNamespace(request=inputs.request)).declaration,
        nutrient_contract=contract,
    )
    result = solve_weekly_plan_v2(
        inputs.request,
        candidates=tuple(inputs.candidates.values()),
        knowledge=inputs.knowledge,
        context=inputs.context,
        sources=inputs.weekly,
        strategy=strategy,
        limits=forward_limits(),
        reuse_preparation=True,
    )
    assert result.schema_version == "computed-weekly-nutrient-solve-result.v1"
    assert result.verification_complete
    assert (
        result.outcome.value
        == {"PASS": "FEASIBLE", "FAIL": "INFEASIBLE", "UNKNOWN": "INSUFFICIENT_DATA"}[
            assessment.status.value
        ]
    )
    assert verify_weekly_plan_v2(
        result,
        request=inputs.request,
        candidates=tuple(inputs.candidates.values()),
        knowledge=inputs.knowledge,
        context=inputs.context,
        sources=inputs.weekly,
        expected_strategy=strategy,
    ).verification_complete
