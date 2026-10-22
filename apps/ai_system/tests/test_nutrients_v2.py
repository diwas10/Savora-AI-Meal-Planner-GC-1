"""Literal exact native arithmetic, completeness, binding and forged assessment tests."""

import pytest
from pydantic import ValidationError
from test_planned_swap_contracts import foundation_case
from test_weekly_contracts import evidence

from savora_ai.core.reasoning.nutrients_v2 import (
    evaluate_weekly_nutrients,
    verify_weekly_nutrient_assessment,
)
from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.daily import DailySourceReference
from savora_ai.schemas.nutrients_v2 import (
    NutrientAssessmentV2,
    NutrientBandV2,
    NutrientMeasurementV2,
    OptionNutrientsV2,
    WeeklyNutrientContractV2,
)


@pytest.fixture(scope="module")
def packet():
    saved = foundation_case()["saved_plan"].snapshot
    request, trial = saved.original_request, saved.original_trial
    source = DailySourceReference(source_id="targets", version="1", content_digest="b" * 64)
    options = tuple(
        OptionNutrientsV2(
            option=o.reference,
            basis="ABSOLUTE_FIXED_PORTION",
            reference_basis="PER_SERVING",
            mass_g=None,
            measurements=(
                NutrientMeasurementV2(
                    nutrient="energy_kcal",
                    unit="kcal",
                    value="2.001",
                    complete=True,
                    source=source,
                    evidence=(evidence(),),
                ),
            ),
        )
        for o in request.source.daily_source.options
    )
    bands = tuple(
        NutrientBandV2(
            band_id=f"day-{i}",
            scope="DAY",
            day_index=i,
            nutrient="energy_kcal",
            unit="kcal",
            lower="6.003",
            upper="6.003",
            source=source,
            evidence=(evidence(),),
        )
        for i in range(1, 8)
    )
    contract = WeeklyNutrientContractV2(
        request_digest=request.content_digest,
        weekly_source=request.expected_source,
        profile_id=saved.original_context.profile_id,
        profile_version=saved.original_context.profile_version,
        catalogue_version=request.source.daily_source.options[0].combination.catalogue_version,
        target=source,
        options=options,
        bands=bands,
    )
    return request, trial, contract


def changed(contract, **updates):
    return WeeklyNutrientContractV2.model_validate(contract.model_dump() | updates)


def test_exact_21_slots_seven_days_and_week(packet):
    request, trial, contract = packet
    week = contract.bands[0].model_dump() | dict(
        band_id="week", scope="WEEK", day_index=None, lower="42.021", upper="42.021"
    )
    contract = changed(contract, bands=(*contract.bands, NutrientBandV2.model_validate(week)))
    result = evaluate_weekly_nutrients(request, trial, contract=contract)
    assert result.status.value == "PASS"
    assert [a.total_milli_native_units for a in result.assessments] == [6003] * 7 + [42021]
    assert (
        verify_weekly_nutrient_assessment(result, request=request, trial=trial, contract=contract)
        == result
    )
    assert (
        validate_contract_json(NutrientAssessmentV2, result.model_dump_json(by_alias=True))
        == result
    )


@pytest.mark.parametrize(
    "lower,upper,li,ui,expected",
    [
        ("6.003", "6.003", True, True, "PASS"),
        ("6.004", None, True, True, "FAIL"),
        (None, "6.002", True, True, "FAIL"),
        ("6.003", None, False, True, "FAIL"),
        (None, "6.003", True, False, "FAIL"),
    ],
)
def test_one_native_milliunit_and_exact_exclusive_boundaries(
    packet, lower, upper, li, ui, expected
):
    request, trial, contract = packet
    band = NutrientBandV2.model_validate(
        contract.bands[0].model_dump()
        | dict(lower=lower, upper=upper, lower_inclusive=li, upper_inclusive=ui)
    )
    result = evaluate_weekly_nutrients(request, trial, contract=changed(contract, bands=(band,)))
    assert result.status.value == expected


@pytest.mark.parametrize("axis", ["nutrient", "basis", "mass", "reference_basis", "incomplete"])
def test_missing_required_information_stays_unknown(packet, axis):
    request, trial, contract = packet
    option = contract.options[0]
    update = {
        "nutrient": dict(measurements=()),
        "basis": dict(basis="UNKNOWN"),
        "mass": dict(reference_basis="PER_100_G", mass_g=None),
        "reference_basis": dict(reference_basis="UNKNOWN"),
        "incomplete": dict(
            measurements=(
                NutrientMeasurementV2.model_validate(
                    option.measurements[0].model_dump() | dict(value=None, complete=False)
                ),
            )
        ),
    }[axis]
    option = OptionNutrientsV2.model_validate(option.model_dump() | update)
    result = evaluate_weekly_nutrients(
        request, trial, contract=changed(contract, options=(option, *contract.options[1:]))
    )
    assert result.status.value == "UNKNOWN"
    assert result.assessments[0].total_milli_native_units is None


def test_known_fail_dominates_unknown_and_conflicting_bands(packet):
    request, trial, contract = packet
    fail = NutrientBandV2.model_validate(
        contract.bands[0].model_dump() | dict(lower="100", upper=None)
    )
    unknown = NutrientBandV2.model_validate(
        contract.bands[1].model_dump() | dict(nutrient="sugars_g", unit="g", lower=None, upper="1")
    )
    result = evaluate_weekly_nutrients(
        request, trial, contract=changed(contract, bands=(fail, unknown))
    )
    assert [a.status.value for a in result.assessments] == ["FAIL", "UNKNOWN"]
    assert result.status.value == "FAIL"


@pytest.mark.parametrize(
    "value", ["NaN", "Infinity", "1.0001", "1000000000", "-1", "1e2", 1.1, True]
)
def test_precision_and_non_native_values_are_rejected(packet, value):
    measurement = packet[2].options[0].measurements[0]
    with pytest.raises(ValidationError):
        NutrientMeasurementV2.model_validate(measurement.model_dump() | {"value": value})


def test_units_impossible_bands_omissions_and_forged_rehash(packet):
    request, trial, contract = packet
    with pytest.raises(ValidationError, match="native unit"):
        NutrientMeasurementV2.model_validate(
            contract.options[0].measurements[0].model_dump() | {"unit": "mg"}
        )
    for update in (dict(lower="7", upper="6"), dict(lower="6", upper="6", upper_inclusive=False)):
        with pytest.raises(ValidationError, match="impossible"):
            NutrientBandV2.model_validate(contract.bands[0].model_dump() | update)
    with pytest.raises(ValueError, match="complete weekly option"):
        evaluate_weekly_nutrients(
            request, trial, contract=changed(contract, options=contract.options[:-1])
        )
    result = evaluate_weekly_nutrients(request, trial, contract=contract)
    forged = result.model_copy(update={"status": type(result.status).FAIL})
    with pytest.raises(ValueError, match="reconstructed"):
        verify_weekly_nutrient_assessment(forged, request=request, trial=trial, contract=contract)


def nutrient_search_packet(packet, *, outcome="PASS"):
    from types import SimpleNamespace

    from test_planned_swap_contracts import rebuild
    from test_weekly_value_priority import priority

    from savora_ai.schemas import weekly_search_v2 as v2
    from savora_ai.schemas.daily import DailySlotDomain

    request, _, contract = packet
    original = foundation_case()["saved_plan"].snapshot
    days = tuple(
        day.model_copy(
            update={
                "domains": tuple(
                    DailySlotDomain(
                        slot=domain.slot,
                        options=domain.options if index == 0 and j == 0 else domain.options[:1],
                    )
                    for j, domain in enumerate(day.domains)
                )
            }
        )
        for index, day in enumerate(request.days)
    )
    request = rebuild(request, days=days)
    option = contract.options[1]
    observation = NutrientMeasurementV2.model_validate(
        option.measurements[0].model_dump() | {"value": "1.000"}
    )
    option = OptionNutrientsV2.model_validate(
        option.model_dump() | {"measurements": (observation,)}
    )
    band = NutrientBandV2.model_validate(
        contract.bands[0].model_dump()
        | dict(
            lower="5.002" if outcome == "PASS" else "100",
            upper=None,
            nutrient="sugars_g" if outcome == "UNKNOWN" else "energy_kcal",
            unit="g" if outcome == "UNKNOWN" else "kcal",
        )
    )
    if outcome == "PASS":
        band = NutrientBandV2.model_validate(band.model_dump() | {"upper": "5.002"})
    contract = changed(
        contract,
        request_digest=request.content_digest,
        options=(contract.options[0], option),
        bands=(band, *contract.bands[1:]),
    )
    strategy = v2.WeeklyNutrientSearchStrategyV2(
        declaration=priority(SimpleNamespace(request=request), high=False).declaration,
        nutrient_contract=contract,
    )
    args = dict(
        request=request,
        candidates=original.original_candidates,
        knowledge=foundation_case()["knowledge"],
        context=original.original_context,
        sources=original.original_sources,
    )
    return args, strategy


@pytest.mark.parametrize("expected", ["PASS", "FAIL", "UNKNOWN"])
def test_v2_search_and_independent_proof_enforce_native_bands(packet, expected):
    from test_weekly_bounds import forward_limits

    from savora_ai.core.reasoning.weekly_search_v2 import (
        solve_weekly_plan_v2,
        verify_weekly_plan_v2,
    )
    from savora_ai.schemas.weekly_solver_v2 import ComputedWeeklySolveResultV2

    args, strategy = nutrient_search_packet(packet, outcome=expected)
    result = solve_weekly_plan_v2(
        **args, strategy=strategy, limits=forward_limits(), reuse_preparation=True
    )
    assert (
        result.outcome.value
        == {"PASS": "FEASIBLE", "FAIL": "INFEASIBLE", "UNKNOWN": "INSUFFICIENT_DATA"}[expected]
    )
    assert result.verification_complete
    assert (
        result.certificate.proof_policy_version == "synthetic-weekly-nutrient-priority-coverage.v2"
    )
    assert verify_weekly_plan_v2(result, **args, expected_strategy=strategy) == result
    with pytest.raises(ValueError, match="independently selected"):
        verify_weekly_plan_v2(result, **args)
    if expected == "PASS":
        assert result.witness is not None
        assert (
            result.witness.trial.choices[0].option == strategy.nutrient_contract.options[1].option
        )
    else:
        assert result.witness is None
    forged = result.model_dump()
    forged["certificate"]["events"][-1]["evaluation_digest"] = "f" * 64
    with pytest.raises(ValidationError):
        ComputedWeeklySolveResultV2.model_validate(forged)


def test_catalogue_version_is_independent_of_combination_revision(packet):
    request, _, contract = packet
    assert contract.catalogue_version == "foods-1"
    assert contract.options[0].option.combination_version == "1"
    contract.bind(request)
    with pytest.raises(ValueError, match="authoritative option catalogue"):
        changed(contract, catalogue_version="1").bind(request)


def test_conflicting_bands_and_literal_cumulative_native_work(packet):
    from test_weekly_bounds import forward_limits

    from savora_ai.core.reasoning.weekly_search_v2 import (
        solve_weekly_plan_v2,
        verify_weekly_plan_v2,
    )
    from savora_ai.schemas.weekly_search_v2 import WeeklyNutrientSearchStrategyV2

    args, strategy = nutrient_search_packet(packet)
    contract = strategy.nutrient_contract
    conflicting = NutrientBandV2.model_validate(
        contract.bands[0].model_dump()
        | dict(band_id="contradictory-day-one", lower="6.003", upper=None)
    )
    contract = changed(contract, bands=(*contract.bands, conflicting))
    strategy = WeeklyNutrientSearchStrategyV2(
        declaration=strategy.declaration, nutrient_contract=contract
    )
    result = solve_weekly_plan_v2(
        **args, strategy=strategy, limits=forward_limits(), reuse_preparation=True
    )
    assert result.outcome.value == "INFEASIBLE"
    assert verify_weekly_plan_v2(result, **args, expected_strategy=strategy).verification_complete
    # Independent arithmetic: 21 slots + 22 option entries, then two complete
    # alternatives x 8 DAY bands x 3 measurements. Each side performs 91 units.
    accounting = result.certificate.accounting
    assert accounting.execution_work.heuristic_evaluations == 91
    assert result.verification_work.heuristic_evaluations == 91
    assert accounting.reserved_work.heuristic_evaluations == 182


def test_historical_saved_verification_cannot_relabel_native_protocol():
    from savora_ai.schemas.planned_swap import SavedPlanVerificationRecord, SwapReference

    with pytest.raises(ValidationError):
        SavedPlanVerificationRecord.model_validate(
            dict(
                status="VERIFIED_AT_SAVE",
                prior_protocol="computed-weekly-nutrient-solve-result.v1",
                prior_result=SwapReference(
                    record_id="native-result", version="1", content_digest="a" * 64
                ),
                verification_policy="native-test",
                evidence=(evidence(),),
            )
        )
