"""Contract tests for nutrition target models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from savora_ai.core.nutrition.models import (
    Bounds,
    MealEnergyRange,
    NutrientsBounds,
    NutritionTargets,
    TargetInput,
)
from savora_ai.schemas.enums import ActivityLevel, MealType, Sex

HASH = "a" * 64


def make_input(**overrides: object) -> TargetInput:
    data: dict[str, object] = {
        "age_years": 30,
        "sex": Sex.FEMALE,
        "height_cm": 165.0,
        "weight_kg": 60.0,
        "activity": ActivityLevel.LIGHT,
    }
    data.update(overrides)
    return TargetInput.model_validate(data)


def make_targets(**overrides: object) -> NutritionTargets:
    data: dict[str, object] = {
        "profile_version": 1,
        "formula_version": "targets-0.1",
        "method": "EXAMPLE_ONLY",
        "input_hash": HASH,
        "calculated_at": datetime(2026, 10, 19, tzinfo=UTC),
        "energy_kcal": Bounds(min=1900, target=2000, max=2100),
    }
    data.update(overrides)
    return NutritionTargets.model_validate(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("age_years", 0),
        ("age_years", 121),
        ("height_cm", 0.0),
        ("weight_kg", -1.0),
        ("weight_kg", float("nan")),
    ],
)
def test_input_rejects_invalid_numbers(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        make_input(**{field: value})


def test_input_rejects_unknown_enum_token() -> None:
    payload = '{"ageYears":30,"sex":"OTHER","heightCm":165,"weightKg":60,"activity":"LIGHT"}'
    with pytest.raises(ValidationError):
        TargetInput.model_validate_json(payload)


def test_input_json_round_trip_uses_camel_case() -> None:
    original = make_input()
    dumped = original.model_dump_json(by_alias=True)
    assert '"ageYears":30' in dumped
    assert '"sex":"FEMALE"' in dumped
    assert TargetInput.model_validate_json(dumped) == original


def test_models_are_frozen() -> None:
    with pytest.raises(ValidationError):
        make_input().age_years = 31  # type: ignore[misc]


def test_bounds_default_to_unknown_not_zero() -> None:
    bounds = Bounds()
    assert bounds.min is None and bounds.target is None and bounds.max is None


@pytest.mark.parametrize(
    "kwargs",
    [{"min": 5, "max": 1}, {"min": 3, "target": 2}, {"target": 9, "max": 8}, {"min": -1}],
)
def test_bounds_reject_disordered_or_negative(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        Bounds(**kwargs)


def test_partial_bounds_are_allowed() -> None:
    assert Bounds(max=2000).min is None


def test_meal_range_ordering_and_limits() -> None:
    MealEnergyRange(meal_type=MealType.LUNCH, min_fraction=0.3, max_fraction=0.4)
    with pytest.raises(ValidationError):
        MealEnergyRange(meal_type=MealType.LUNCH, min_fraction=0.5, max_fraction=0.4)
    with pytest.raises(ValidationError):
        MealEnergyRange(meal_type=MealType.LUNCH, min_fraction=0.3, max_fraction=1.2)


def test_targets_json_round_trip_and_tuples() -> None:
    targets = make_targets(
        nutrient_bounds=(NutrientsBounds(nutrient="sodium_mg", bounds=Bounds(max=2000)),),
        meal_energy_policy=(
            MealEnergyRange(meal_type=MealType.BREAKFAST, min_fraction=0.2, max_fraction=0.3),
        ),
    )
    dumped = targets.model_dump_json(by_alias=True)
    assert '"mealEnergyPolicy"' in dumped and '"inputHash"' in dumped
    assert NutritionTargets.model_validate_json(dumped) == targets


def test_targets_reject_bad_hash_naive_time_and_duplicates() -> None:
    with pytest.raises(ValidationError):
        make_targets(input_hash="xyz")
    with pytest.raises(ValidationError):
        make_targets(calculated_at=datetime(2026, 10, 19))
    entry = NutrientsBounds(nutrient="sodium_mg", bounds=Bounds(max=2000))
    with pytest.raises(ValidationError):
        make_targets(nutrient_bounds=(entry, entry))
