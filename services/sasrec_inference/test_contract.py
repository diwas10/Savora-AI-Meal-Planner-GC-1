"""Credential, protocol and provenance checks that need no trained checkpoint."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

import app as service
from conftest import SERVICE_DIR
from model import CHECKPOINT_SHA256, ModelConfig, SASRecContent, score_candidates

FIXTURE = json.loads((SERVICE_DIR / "fixture.json").read_text())
REMOTE = json.loads((SERVICE_DIR / "evidence/remote.json").read_text())
SECRET = "test-only-never-a-deployment-credential-12345"
AUTH = {"X-Savora-Authorization": "Bearer " + SECRET}


@pytest.fixture
def fake_client(monkeypatch):
    """Exercise HTTP handling with an explicit fake, never label it real inference."""
    ids = ["<pad>", *FIXTURE["history_ids"], *FIXTURE["candidate_ids"]]
    row_map = {rid: i for i, rid in enumerate(ids)}
    monkeypatch.setenv("SAVORA_SERVICE_TOKEN", SECRET)
    monkeypatch.setattr(service, "load_model", lambda path: (object(), ids, row_map))
    monkeypatch.setattr(service, "score_candidates", lambda model, history, candidates, rows:
                        [float(rows[rid] % 2) for rid in candidates])
    with TestClient(service.create_app()) as client:
        yield client


def test_fake_candidate_alignment_and_stable_ties(fake_client):
    response = fake_client.post("/rank", json=FIXTURE, headers=AUTH)
    assert response.status_code == 200
    result = response.json()
    assert result["schema_version"] == "savora-rank-v1"
    assert result["model_version"] == "sasrec-content-v2"
    assert result["score_mode"] == "transformer_only"
    assert [entry["candidate_id"] for entry in result["scores"]] == FIXTURE["candidate_ids"]
    assert [entry["rank"] for entry in result["scores"]] == [3, 1, 4, 2, 5]


@pytest.mark.parametrize("change", [
    {"schema_version": "future"}, {"history_ids": []},
    {"history_ids": ["FC_100"] * 51}, {"candidate_ids": []},
    {"candidate_ids": [f"FC_{i}" for i in range(513)]},
    {"candidate_ids": ["FC_100001"] * 2}, {"candidate_ids": [100001]},
    {"candidate_ids": ["FC_1234567890123"]}, {"candidate_ids": ["<pad>"]},
    {"candidate_ids": ["FC_999999999999"]},
    {"history_ids": ["FC_999999999999"]}, {"profile": {"name": "private"}},
])
def test_invalid_requests_without_weights(fake_client, change):
    response = fake_client.post("/rank", json=dict(FIXTURE, **change), headers=AUTH)
    assert response.status_code == 422
    assert "private" not in response.text


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"},
                                      {"X-Savora-Authorization": "Bearer wrong"}])
def test_missing_or_wrong_application_auth(fake_client, headers):
    assert fake_client.post("/rank", json=FIXTURE, headers=headers).status_code == 401


def test_custom_auth_takes_precedence_over_gateway_header(fake_client):
    headers = dict(AUTH, Authorization="Bearer fake-gateway-credential")
    assert fake_client.post("/rank", json=FIXTURE, headers=headers).status_code == 200
    headers = {"Authorization": "Bearer " + SECRET, "X-Savora-Authorization": "Bearer wrong"}
    assert fake_client.post("/rank", json=FIXTURE, headers=headers).status_code == 401


def test_malformed_json_and_body_limit_without_weights(fake_client):
    assert fake_client.post("/rank", content="{", headers=AUTH).status_code == 422
    assert fake_client.post("/rank", content="x" * 32769, headers=AUTH).status_code == 413


def test_remote_fixture_is_internally_consistent():
    result = service.RankResponse.model_validate(REMOTE["response"])
    assert [s.candidate_id for s in result.scores] == FIXTURE["candidate_ids"]
    order = sorted(result.scores, key=lambda entry: -entry.score)
    assert [s.rank for s in order] == list(range(1, len(order) + 1))
    assert REMOTE["health"]["checkpoint_sha256"] == CHECKPOINT_SHA256
    assert REMOTE["sha"] == "ed1392996183abfdc844529dd93c251d568b2cb8"


def test_runtime_matches_deployed_source_manifest():
    manifest = json.loads((SERVICE_DIR / "evidence/upload-manifest.json").read_text())
    runtime_files = {"app.py", "model.py", "Dockerfile", ".dockerignore",
                     "requirements.in", "requirements.txt", "sasrec_content.json", "fixture.json"}
    entries = {entry["path"]: entry for entry in manifest["files"]}
    for name in runtime_files:
        content = (SERVICE_DIR / name).read_bytes()
        assert len(content) == entries[name]["bytes"]
        assert hashlib.sha256(content).hexdigest() == entries[name]["sha256"]
    assert entries["sasrec_content.pt"]["sha256"] == CHECKPOINT_SHA256
    assert entries["sasrec_content.pt"]["bytes"] == 196509717


def test_synthetic_model_candidate_permutation():
    # A tiny random model tests tensor indexing only, not trained model quality.
    import torch

    torch.manual_seed(7)
    model = SASRecContent(5, 1, 1, ModelConfig())
    model.eval()
    model.requires_grad_(False)
    model.has_id[1:] = 1
    row_map = {f"FC_{i}": i for i in range(1, 5)}
    first = score_candidates(model, ["FC_1"], ["FC_2", "FC_3"], row_map)
    second = score_candidates(model, ["FC_1"], ["FC_3", "FC_2"], row_map)
    assert second == pytest.approx(first[::-1])


def test_missing_checkpoint_is_never_random_model(tmp_path, monkeypatch):
    monkeypatch.setenv("SAVORA_SERVICE_TOKEN", SECRET)
    with TestClient(service.create_app(tmp_path / "absent.pt")) as client:
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json()["ready"] is False
        assert response.json()["checkpoint_sha256"] is None
        assert client.post("/rank", json=FIXTURE, headers=AUTH).status_code == 503
