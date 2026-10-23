"""Exact nutrient witness checking, independently bound to original source material.

This is supplemental verification, not search or clinical rule admission. A
structural weekly PASS alone cannot establish these additional target obligations.
"""

from savora_ai.schemas.candidates import _content_digest
from savora_ai.schemas.nutrients_v2 import (
    NutrientAssessmentV2,
    NutrientBandAssessmentV2,
    WeeklyNutrientContractV2,
    scaled_value,
)
from savora_ai.schemas.reasoning import RuleStatus
from savora_ai.schemas.weekly import WeeklyPlanningRequest, WeeklyTrial, _bind_trial


def evaluate_weekly_nutrients(
    request: WeeklyPlanningRequest,
    trial: WeeklyTrial,
    *,
    contract: WeeklyNutrientContractV2,
) -> NutrientAssessmentV2:
    """Reconstruct every DAY/WEEK total; required unknowns never become zero."""
    request = WeeklyPlanningRequest.model_validate(request)
    trial = WeeklyTrial.model_validate(trial)
    contract = WeeklyNutrientContractV2.model_validate(contract)
    contract.bind(request)
    _bind_trial(request, trial)
    ordered = sorted(
        trial.choices, key=lambda c: (c.day.day_index, tuple(type(c.slot)).index(c.slot))
    )
    pool = {o.option.option_id: o for o in contract.options}
    assessments = []
    for band in contract.bands:
        total = 0
        missing = []
        for index, choice in enumerate(ordered):
            if band.day_index is not None and choice.day.day_index != band.day_index:
                continue
            option = pool[choice.option.option_id]
            measurement = next(
                (m for m in option.measurements if m.nutrient == band.nutrient), None
            )
            if (
                option.basis != "ABSOLUTE_FIXED_PORTION"
                or option.reference_basis == "UNKNOWN"
                or (option.reference_basis == "PER_100_G" and option.mass_g is None)
                or measurement is None
                or not measurement.complete
                or measurement.value is None
            ):
                missing.append(index)
            else:
                total += scaled_value(measurement.value)
        status = RuleStatus.UNKNOWN if missing else RuleStatus.PASS
        if not missing:
            if band.lower is not None:
                low = scaled_value(band.lower)
                if total < low or (total == low and not band.lower_inclusive):
                    status = RuleStatus.FAIL
            if band.upper is not None:
                high = scaled_value(band.upper)
                if total > high or (total == high and not band.upper_inclusive):
                    status = RuleStatus.FAIL
        assessments.append(
            NutrientBandAssessmentV2(
                band_id=band.band_id,
                status=status,
                total_milli_native_units=None if missing else total,
                missing_slots=tuple(missing),
            )
        )
    status = (
        RuleStatus.FAIL
        if any(a.status is RuleStatus.FAIL for a in assessments)
        else RuleStatus.UNKNOWN
        if any(a.status is RuleStatus.UNKNOWN for a in assessments)
        else RuleStatus.PASS
    )
    return NutrientAssessmentV2(
        contract_digest=_content_digest(contract),
        trial_digest=trial.content_digest,
        assessments=tuple(assessments),
        status=status,
    )


def verify_weekly_nutrient_assessment(
    assessment: NutrientAssessmentV2,
    *,
    request: WeeklyPlanningRequest,
    trial: WeeklyTrial,
    contract: WeeklyNutrientContractV2,
) -> NutrientAssessmentV2:
    """Compare recomputed facts with the claim; caller hashes/status authorize nothing."""
    supplied = NutrientAssessmentV2.model_validate(assessment)
    expected = evaluate_weekly_nutrients(request, trial, contract=contract)
    if supplied != expected:
        raise ValueError(
            "nutrient assessment differs from independently reconstructed totals/bands"
        )
    return expected
