"""Native-unit general target contracts; no clinical authorization or KB activation.

All numbers are exact decimal STRINGS with <=3 decimal places. There is no
implicit rounding or conversion of kcal/g to mg. Integer milli-native-units are
used internally; values outside this policy are rejected, never approximated.
"""

from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from savora_ai.schemas.daily import (
    DailySourceReference,
    MealOptionReference,
    _DailyModel,
    _evidenced,
)
from savora_ai.schemas.food_graph import _OpaqueId
from savora_ai.schemas.knowledge import EvidenceReference, _NonBlank
from savora_ai.schemas.knowledge_base import _ContentDigest
from savora_ai.schemas.reasoning import RuleStatus
from savora_ai.schemas.weekly import WeeklyPlanningRequest, WeeklySourceReference

Nutrient = Literal[
    "energy_kcal",
    "protein_g",
    "carbs_g",
    "fat_g",
    "saturated_fat_g",
    "sodium_mg",
    "sugars_g",
]
Unit = Literal["kcal", "g", "mg"]
ExactValue = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]{0,8})(\.[0-9]{1,3})?$")]
EXACT_POLICY = "native-decimal-3dp-no-rounding.v1"


def scaled_value(value: str) -> int:
    """A validated decimal token, without Decimal context or binary arithmetic."""
    whole, _, fraction = value.partition(".")
    return int(whole) * 1000 + int(fraction.ljust(3, "0"))


def native_unit(nutrient: Nutrient) -> Unit:
    return "kcal" if nutrient == "energy_kcal" else "mg" if nutrient == "sodium_mg" else "g"


class NutrientMeasurementV2(_DailyModel):
    nutrient: Nutrient
    unit: Unit
    value: ExactValue | None
    complete: bool
    source: DailySourceReference
    evidence: Annotated[tuple[EvidenceReference, ...], Field(min_length=1, max_length=16)]

    @model_validator(mode="after")
    def exact_measurement(self) -> Self:
        if self.unit != native_unit(self.nutrient):
            raise ValueError("nutrient requires its native unit")
        if self.complete != (self.value is not None):
            raise ValueError("complete nutrient measurement requires an exact value")
        _evidenced(self.evidence)
        return self


class OptionNutrientsV2(_DailyModel):
    schema_version: Literal["daily-nutrients.v2"] = "daily-nutrients.v2"
    arithmetic_policy: Literal["native-decimal-3dp-no-rounding.v1"] = EXACT_POLICY
    option: MealOptionReference
    basis: Literal["ABSOLUTE_FIXED_PORTION", "UNKNOWN"]
    reference_basis: Literal["PER_SERVING", "PER_100_G", "VALIDATED_ABSOLUTE_AGGREGATE", "UNKNOWN"]
    mass_g: ExactValue | None
    measurements: Annotated[tuple[NutrientMeasurementV2, ...], Field(max_length=7)]

    @model_validator(mode="after")
    def fixed_measurements(self) -> Self:
        if self.option.portion_state.value != "FIXED":
            raise ValueError("native nutrients require exact fixed option identity")
        keys = tuple(m.nutrient for m in self.measurements)
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate nutrient measurements")
        if self.mass_g is not None and scaled_value(self.mass_g) == 0:
            raise ValueError("known serving mass must be positive")
        return self


class NutrientBandV2(_DailyModel):
    schema_version: Literal["daily-nutrient-band.v2"] = "daily-nutrient-band.v2"
    band_id: _OpaqueId
    scope: Literal["DAY", "WEEK"]
    day_index: Annotated[int, Field(ge=1, le=7)] | None
    nutrient: Nutrient
    unit: Unit
    lower: ExactValue | None
    upper: ExactValue | None
    lower_inclusive: bool = True
    upper_inclusive: bool = True
    purpose: Literal["GENERAL_TARGET"] = "GENERAL_TARGET"
    source: DailySourceReference
    evidence: Annotated[tuple[EvidenceReference, ...], Field(min_length=1, max_length=16)]

    @model_validator(mode="after")
    def possible_band(self) -> Self:
        if (self.scope == "DAY") != (self.day_index is not None):
            raise ValueError("DAY band requires its exact day; WEEK band has no day index")
        if self.unit != native_unit(self.nutrient) or (self.lower is None and self.upper is None):
            raise ValueError("band requires native unit and at least one bound")
        if self.lower is not None and self.upper is not None:
            low, high = scaled_value(self.lower), scaled_value(self.upper)
            if low > high or (low == high and not (self.lower_inclusive and self.upper_inclusive)):
                raise ValueError("empty or impossible nutrient band")
        _evidenced(self.evidence)
        return self


class WeeklyNutrientContractV2(_DailyModel):
    schema_version: Literal["weekly-nutrient-contract.v2"] = "weekly-nutrient-contract.v2"
    arithmetic_policy: Literal["native-decimal-3dp-no-rounding.v1"] = EXACT_POLICY
    request_digest: _ContentDigest
    weekly_source: WeeklySourceReference
    profile_id: _OpaqueId
    profile_version: _NonBlank
    catalogue_version: _NonBlank
    target: DailySourceReference
    options: Annotated[tuple[OptionNutrientsV2, ...], Field(max_length=75)]
    bands: Annotated[tuple[NutrientBandV2, ...], Field(min_length=1, max_length=128)]

    @model_validator(mode="after")
    def unique_inventory(self) -> Self:
        ids = [o.option.option_id for o in self.options]
        if len(ids) != len(set(ids)) or len({b.band_id for b in self.bands}) != len(self.bands):
            raise ValueError("duplicate option or band identity")
        if any(b.source != self.target for b in self.bands):
            raise ValueError("every band must bind the exact independently selected target source")
        return self

    def bind(self, request: WeeklyPlanningRequest) -> None:
        context = request.source.daily_source.context
        if (self.request_digest, self.weekly_source, self.profile_id, self.profile_version) != (
            request.content_digest,
            request.expected_source,
            context.profile_id,
            context.profile_version,
        ):
            raise ValueError("nutrient contract differs from weekly request/source/profile")
        required = {
            o.option_id: o for d in request.days for domain in d.domains for o in domain.options
        }
        if {o.option.option_id: o.option for o in self.options} != required:
            raise ValueError("nutrient contract must cover exact complete weekly option identities")
        pool = {o.reference.option_id: o for o in request.source.daily_source.options}
        if any(
            pool[option_id].combination.catalogue_version != self.catalogue_version
            for option_id in required
        ):
            raise ValueError(
                "nutrient catalogue version differs from authoritative option catalogue"
            )


class NutrientBandAssessmentV2(_DailyModel):
    band_id: _OpaqueId
    status: RuleStatus
    total_milli_native_units: Annotated[int, Field(ge=0, le=21 * 999_999_999_999)] | None
    missing_slots: Annotated[tuple[int, ...], Field(max_length=21)]


class NutrientAssessmentV2(_DailyModel):
    schema_version: Literal["weekly-nutrient-assessment.v2"] = "weekly-nutrient-assessment.v2"
    contract_digest: _ContentDigest
    trial_digest: _ContentDigest
    assessments: tuple[NutrientBandAssessmentV2, ...]
    status: RuleStatus
