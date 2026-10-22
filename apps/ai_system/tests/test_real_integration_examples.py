"""The handoff JSON is executable contract material, with fictional values."""

import json
from pathlib import Path

from pydantic import TypeAdapter
from test_planned_swap_contracts import foundation_case

from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.nutrients_v2 import NutrientBandV2, OptionNutrientsV2
from savora_ai.schemas.weekly_search_v2 import WeeklyValueOrderV1


def test_handoff_examples_validate_and_bind_exact_request():
    path = Path(__file__).resolve().parents[3] / "docs/member2/real_integration_examples.json"
    examples = json.loads(path.read_text("utf-8"))
    assert examples["status"] == "FICTIONAL_CONTRACT_EXAMPLES_ONLY"
    option = validate_contract_json(OptionNutrientsV2, json.dumps(examples["optionNutrients"]))
    bands = validate_contract_json(
        TypeAdapter(tuple[NutrientBandV2, ...]), json.dumps(examples["dailyTargetBands"])
    )
    declaration = validate_contract_json(
        WeeklyValueOrderV1, json.dumps(examples["valuePriorityDeclaration"])
    )
    declaration.bind(foundation_case()["saved_plan"].snapshot.original_request)
    assert len(option.measurements) == 7 and option.measurements[-1].value is None
    assert {b.nutrient for b in bands} == {"energy_kcal", "protein_g"}
    assert all(b.purpose == "GENERAL_TARGET" for b in bands)
