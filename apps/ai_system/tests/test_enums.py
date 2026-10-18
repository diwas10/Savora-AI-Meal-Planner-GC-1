"""Pin enum tokens: they are persisted and exchanged, so changes must be deliberate."""

from enum import StrEnum

import pytest

from savora_ai.schemas import enums

EXPECTED: dict[type[StrEnum], tuple[str, ...]] = {
    enums.Sex: ("MALE", "FEMALE"),
    enums.ActivityLevel: ("SEDENTARY", "LIGHT", "MODERATE", "ACTIVE", "VERY_ACTIVE"),
    enums.Goal: ("LOSE", "MAINTAIN", "GAIN"),
    enums.HealthCondition: ("TYPE_2_DIABETES", "HYPERTENSION", "DYSLIPIDEMIA"),
    enums.CuisinePolicy: ("STRICT", "MAJORITY", "MIXED"),
    enums.MealType: ("BREAKFAST", "LUNCH", "DINNER"),
    enums.DishClass: ("COMPLETE_MEAL", "REQUIRES_ACCOMPANIMENT", "COMPONENT"),
    enums.CulinaryRole: (
        "STAPLE",
        "MAIN_DISH",
        "PROTEIN_SOURCE",
        "VEGETABLE",
        "BREAKFAST_BASE",
        "FRUIT",
        "SUPPLEMENT",
    ),
    enums.PortionUnit: ("PIECE", "BOWL", "CUP", "SLICE", "LOAF", "GRAM", "MILLILITER"),
    enums.PlanStatus: ("FEASIBLE", "INFEASIBLE", "TIMEOUT", "INSUFFICIENT_DATA"),
    enums.QuarantineReason: (
        "MALFORMED_NUTRITION",
        "MALFORMED_METADATA",
        "NUTRITION_OUT_OF_RANGE",
        "ENERGY_INCONSISTENT",
    ),
    enums.ClassificationStatus: ("AUTO", "CURATED", "REQUIRES_REVIEW"),
}


@pytest.mark.parametrize("enum_type", list(EXPECTED), ids=lambda e: e.__name__)
def test_enum_values_are_pinned(enum_type: type[StrEnum]) -> None:
    assert tuple(member.value for member in enum_type) == EXPECTED[enum_type]


@pytest.mark.parametrize("enum_type", list(EXPECTED), ids=lambda e: e.__name__)
def test_member_names_equal_values(enum_type: type[StrEnum]) -> None:
    assert all(member.name == member.value for member in enum_type)


def test_every_public_enum_is_pinned() -> None:
    public = {
        obj
        for obj in vars(enums).values()
        if isinstance(obj, type) and issubclass(obj, StrEnum) and obj is not StrEnum
    }
    assert public == set(EXPECTED)
