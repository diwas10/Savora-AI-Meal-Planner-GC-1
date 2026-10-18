"""Hand-computed checks for the nutrition target calculator."""

from datetime import UTC, datetime

import pytest

from savora_ai.core.nutrition.models import NutritionTargets, TargetInput
from savora_ai.core.nutrition.targets import (
    ACTIVITY_FACTORS,
    GOAL_FACTORS,
    body_mass_index,
    calculate_nutrition_targets,
    input_hash,
    resting_energy_kcal,
)
from savora_ai.schemas.enums import ActivityLevel, Goal, MealType, Sex

NOW = datetime(2026, 10, 19, tzinfo=UTC)


def person(**overrides: object) -> TargetInput:
    data: dict[str, object] = {
        "age_years": 30,
        "sex": Sex.FEMALE,
        "height_cm": 165.0,
        "weight_kg": 60.0,
        "activity": ActivityLevel.LIGHT,
        "goal": Goal.MAINTAIN,
    }
    data.update(overrides)
    return TargetInput.model_validate(data)


def test_resting_energy_female() -> None:
    # 10*60 + 6.25*165 - 5*30 - 161
    assert resting_energy_kcal(person()) == pytest.approx(1320.25)


def test_resting_energy_male() -> None:
    # 10*80 + 6.25*180 - 5*25 + 5
    male = person(sex=Sex.MALE, age_years=25, height_cm=180.0, weight_kg=80.0)
    assert resting_energy_kcal(male) == pytest.approx(1805.0)


def test_sex_constants_differ_by_166_kcal() -> None:
    male = resting_energy_kcal(person(sex=Sex.MALE))
    female = resting_energy_kcal(person(sex=Sex.FEMALE))
    assert male - female == pytest.approx(166.0)


def test_bmi() -> None:
    assert body_mass_index(person(height_cm=180.0, weight_kg=81.0)) == pytest.approx(25.0)


def test_target_applies_activity_and_goal() -> None:
    # 1320.25 * 1.375 = 1815.34 -> 1815 (maintain)
    maintain = calculate_nutrition_targets(person(), profile_version=1, calculated_at=NOW)
    assert maintain.energy_kcal.target == 1815
    # 1320.25 * 1.375 * 0.85 = 1543.04 -> 1543
    lose = calculate_nutrition_targets(person(goal=Goal.LOSE), profile_version=1, calculated_at=NOW)
    assert lose.energy_kcal.target == 1543
    # 1320.25 * 1.375 * 1.10 = 1996.87 -> 1997
    gain = calculate_nutrition_targets(person(goal=Goal.GAIN), profile_version=1, calculated_at=NOW)
    assert gain.energy_kcal.target == 1997


def test_energy_band_is_symmetric_and_ordered() -> None:
    bounds = calculate_nutrition_targets(person(), profile_version=1, calculated_at=NOW).energy_kcal
    assert bounds.min is not None and bounds.target is not None and bounds.max is not None
    assert bounds.min < bounds.target < bounds.max
    assert bounds.target - bounds.min == bounds.max - bounds.target


def test_every_enum_member_has_a_factor() -> None:
    assert set(ACTIVITY_FACTORS) == set(ActivityLevel)
    assert set(GOAL_FACTORS) == set(Goal)


def test_output_metadata_and_unknown_nutrients() -> None:
    result = calculate_nutrition_targets(person(), profile_version=3, calculated_at=NOW)
    assert result.profile_version == 3
    assert result.method == "MIFFLIN_ST_JEOR"
    assert result.bmi == 22.0
    assert result.nutrient_bounds == ()  # unknown, not zero
    assert {m.meal_type for m in result.meal_energy_policy} == set(MealType)
    assert NutritionTargets.model_validate_json(result.model_dump_json(by_alias=True)) == result


def test_calculation_is_deterministic() -> None:
    first = calculate_nutrition_targets(person(), profile_version=1, calculated_at=NOW)
    second = calculate_nutrition_targets(person(), profile_version=1, calculated_at=NOW)
    assert first == second


def test_input_hash_changes_with_input_and_is_stable() -> None:
    assert input_hash(person()) == input_hash(person())
    assert input_hash(person()) != input_hash(person(weight_kg=61.0))
    assert len(input_hash(person())) == 64


@pytest.mark.parametrize(
    "changes",
    [{"age_years": 12}, {"height_cm": 50.0}, {"weight_kg": 10.0}, {"age_years": 101}],
)
def test_inputs_outside_the_adult_estimator_range_are_rejected(changes: dict[str, object]) -> None:
    # Review: tiny heights/weights gave a negative Mifflin-St Jeor energy and an
    # unexplained validation error deep inside the target snapshot.
    from pydantic import ValidationError

    from savora_ai.core.nutrition.models import TargetInput
    from savora_ai.schemas.enums import ActivityLevel, Goal, Sex

    base = dict(
        age_years=30, sex=Sex.FEMALE, height_cm=165.0, weight_kg=60.0,
        activity=ActivityLevel.MODERATE, goal=Goal.MAINTAIN,
    )  # fmt: skip
    TargetInput(**base)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        TargetInput(**(base | changes))  # type: ignore[arg-type]
