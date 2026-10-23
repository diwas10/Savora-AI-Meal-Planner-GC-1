import json
import threading
import time

import pytest
import torch
from fastapi.testclient import TestClient

import app as service
from conftest import CHECKPOINT, SERVICE_DIR
from model import CHECKPOINT_SHA256, load_model

FIXTURE = json.loads((SERVICE_DIR / "fixture.json").read_text())
AUTH = {"X-Savora-Authorization": "Bearer " + "test-service-secret-" * 3}


@pytest.fixture(scope="module")
def client():
    import os
    os.environ["SAVORA_SERVICE_TOKEN"] = "test-service-secret-" * 3
    with TestClient(service.create_app(CHECKPOINT)) as client:
        yield client


@pytest.mark.checkpoint
def test_real_checkpoint_and_readiness(client):
    assert client.get("/health").status_code == 200
    assert client.get("/health").json()["checkpoint_sha256"] == CHECKPOINT_SHA256
    model = client.app.state.model
    assert not model.training
    assert sum(p.numel() for p in model.parameters()) == 15354134
    assert all(not p.requires_grad and p.grad is None for p in model.parameters())
    assert len(client.app.state.ids) == 231638


@pytest.mark.checkpoint
def test_rank_deterministic_and_unchanged_weights(client):
    model = client.app.state.model
    versions = {name: tensor._version for name, tensor in model.state_dict().items()}
    first = client.post("/rank", json=FIXTURE, headers=AUTH)
    assert first.status_code == 200
    data = first.json()
    assert data == client.post("/rank", json=FIXTURE, headers=AUTH).json()
    assert len(data["scores"]) == 5
    assert [s["candidate_id"] for s in data["scores"]] == FIXTURE["candidate_ids"]
    assert all(torch.isfinite(torch.tensor(s["score"])) for s in data["scores"])
    assert versions == {name: tensor._version for name, tensor in model.state_dict().items()}
    assert all(p.grad is None for p in model.parameters())
    assert sorted(s["rank"] for s in data["scores"]) == [1, 2, 3, 4, 5]


@pytest.mark.checkpoint
def test_candidate_reordering(client):
    data = client.post("/rank", json=FIXTURE, headers=AUTH).json()
    reversed_fixture = dict(FIXTURE, candidate_ids=FIXTURE["candidate_ids"][::-1])
    result = client.post("/rank", json=reversed_fixture, headers=AUTH).json()
    assert result["scores"] == data["scores"][::-1]


@pytest.mark.checkpoint
@pytest.mark.parametrize("change", [
    {"schema_version": "wrong"}, {"history_ids": []}, {"history_ids": ["FC_100"] * 51},
    {"candidate_ids": []}, {"candidate_ids": ["FC_100"] * 513},
    {"candidate_ids": ["FC_100", "FC_100"]}, {"candidate_ids": ["FC_999999999999"]},
    {"history_ids": ["FC_999999999999"]}, {"candidate_ids": ["<pad>"]},
    {"candidate_ids": [100]}, {"candidate_ids": [float("nan")]},
    {"candidate_ids": [float("inf")]}, {"user_profile": {"name": "private"}},
])
def test_invalid_request(client, change):
    # Send literal NaN/Infinity to exercise validation of non-standard JSON as well.
    response = client.post("/rank", content=json.dumps(dict(FIXTURE, **change)),
                           headers=dict(AUTH, **{"Content-Type": "application/json"}))
    assert response.status_code == 422
    assert "private" not in response.text


@pytest.mark.checkpoint
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"},
                                       {"X-Savora-Authorization": "Bearer wrong"}])
def test_auth_rejection(client, headers):
    assert client.post("/rank", json=FIXTURE, headers=headers).status_code == 401


@pytest.mark.checkpoint
def test_standard_bearer(client):
    headers = {"Authorization": AUTH["X-Savora-Authorization"]}
    assert client.post("/rank", json=FIXTURE, headers=headers).status_code == 200


@pytest.mark.checkpoint
def test_malformed_and_body_limit(client):
    assert client.post("/rank", content="{", headers=AUTH).status_code == 422
    assert client.post("/rank", content="x" * 32769, headers=AUTH).status_code == 413


@pytest.mark.parametrize("kind", ["missing", "corrupt"])
def test_missing_or_corrupt_fail_closed(tmp_path, monkeypatch, kind):
    monkeypatch.setenv("SAVORA_SERVICE_TOKEN", "test-service-secret-" * 3)
    path = tmp_path / "sasrec_content.pt"
    if kind == "corrupt":
        path.write_bytes(b"not a checkpoint")
    with TestClient(service.create_app(path)) as client:
        assert client.get("/health").status_code == 503
        assert client.post("/rank", json=FIXTURE, headers=AUTH).status_code == 503


@pytest.mark.checkpoint
def test_config_mismatch(tmp_path):
    metadata = json.loads((SERVICE_DIR / "sasrec_content.json").read_text())
    metadata["modelConfig"]["heads"] = 4
    path = tmp_path / "config.json"
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="configuration disagree"):
        load_model(CHECKPOINT, config_path=path)


def test_missing_secret_fail_closed(monkeypatch):
    monkeypatch.delenv("SAVORA_SERVICE_TOKEN", raising=False)
    with TestClient(service.create_app()) as client:
        assert client.get("/health").status_code == 503
        assert client.post("/rank", json=FIXTURE, headers=AUTH).status_code == 503


@pytest.mark.checkpoint
def test_nonfinite_output_rejected(client, monkeypatch):
    model = client.app.state.model
    monkeypatch.setattr(model, "score", lambda *a: torch.full((1, 5), float("nan")))
    assert client.post("/rank", json=FIXTURE, headers=AUTH).status_code == 503


@pytest.mark.checkpoint
def test_timeout_and_busy_protection(client, monkeypatch):
    original = service.score_candidates
    started, finish = threading.Event(), threading.Event()
    def slow(*args):
        started.set()
        finish.wait(2)
        return original(*args)
    monkeypatch.setattr(service, "score_candidates", slow)
    client.app.state.timeout = 0.05
    try:
        assert client.post("/rank", json=FIXTURE, headers=AUTH).status_code == 504
        assert started.is_set()
        assert client.post("/rank", json=FIXTURE, headers=AUTH).status_code == 429
    finally:
        finish.set()
        client.app.state.timeout = 5
    for _ in range(100):
        if not client.app.state.gate.locked():
            break
        time.sleep(0.01)
    assert not client.app.state.gate.locked()
