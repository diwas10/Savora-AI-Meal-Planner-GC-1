"""The real-sized fixture's compact wire artifacts are executable, disjoint DTOs."""

import json
from pathlib import Path

from savora_ai.schemas.candidates import validate_contract_json
from savora_ai.schemas.compact_swap import (
    CompactSwapInput,
    CompactSwapResult,
    CompactSwapVerification,
)


def test_real_compact_artifact_contracts_and_expected_results():
    path = Path(__file__).resolve().parents[3] / "docs/member2/compact_swap_real_example.json"
    fixture = json.loads(path.read_text("utf-8"))
    assert fixture["status"] == "REAL_SOURCES_FICTIONAL_AUTHORITY_STAND_IN_KB_ONLY"
    assert fixture["catalogueVersion"] == "20261021T073631Z"
    for mode, example in fixture["examples"].items():
        request = validate_contract_json(CompactSwapInput, json.dumps(example["input"]))
        result = validate_contract_json(CompactSwapResult, json.dumps(example["expectedResult"]))
        check = validate_contract_json(
            CompactSwapVerification, json.dumps(example["independentVerification"])
        )
        assert request.mode == mode.upper()
        assert result.status == "VALID" and result.verification_complete
        assert check.accepted and check.complete
        assert len(result.changed_day_totals) == 7
        assert result.reconstructed_bytes <= 4_194_304
        assert (
            example["inputBytes"]
            == len(request.model_dump_json(by_alias=True).encode())
            <= 1_048_576
        )
        assert (
            example["outputBytes"]
            == len(result.model_dump_json(by_alias=True).encode())
            <= 1_048_576
        )
