"""Model delivery: the tracked manifest pins the checkpoint; a wrong file never loads."""

import hashlib
import io
from pathlib import Path

import pytest

from savora_ai.core.recommendation import model_store
from savora_ai.core.recommendation.model_store import (
    DEFAULT_MANIFEST,
    ModelIntegrityError,
    ModelManifest,
    fetch_model,
    load_manifest,
    verify_model,
)
from savora_ai.core.recommendation.ranking import load_scorer

PAYLOAD = b"not really a checkpoint"
URL = "https://example.invalid/model.pt"


def manifest_for(data: bytes, url: str | None = URL) -> ModelManifest:
    return ModelManifest(
        model_version="test-v1",
        file_name="model.pt",
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        source_url=url,
    )


class FakeResponse(io.BytesIO):
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def serve(monkeypatch: pytest.MonkeyPatch, data: bytes) -> list[str]:
    calls: list[str] = []

    def urlopen(url: str, timeout: float) -> FakeResponse:
        calls.append(url)
        assert timeout == model_store.DOWNLOAD_TIMEOUT_S
        return FakeResponse(data)

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    return calls


def test_the_tracked_manifest_pins_the_shipped_model_version() -> None:
    torch_model = pytest.importorskip("savora_ai.core.recommendation.torch_model")
    manifest = load_manifest(DEFAULT_MANIFEST)
    assert manifest.model_version == torch_model.MODEL_VERSION
    assert manifest.source_url is not None and manifest.source_url.startswith("https://")


def test_the_local_shipped_model_matches_the_manifest() -> None:
    manifest = load_manifest(DEFAULT_MANIFEST)
    path = model_store.model_path(manifest)
    if not path.exists():
        pytest.skip("trained model not present (git-ignored; fetch with --download)")
    verify_model(path, manifest)


def test_a_matching_file_verifies(tmp_path: Path) -> None:
    (tmp_path / "model.pt").write_bytes(PAYLOAD)
    verify_model(tmp_path / "model.pt", manifest_for(PAYLOAD))


@pytest.mark.parametrize("data", [PAYLOAD + b"!", PAYLOAD.replace(b"n", b"N")])
def test_a_different_file_is_refused(tmp_path: Path, data: bytes) -> None:
    (tmp_path / "model.pt").write_bytes(data)
    with pytest.raises(ModelIntegrityError):
        verify_model(tmp_path / "model.pt", manifest_for(PAYLOAD))


def test_download_verifies_then_renames(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = serve(monkeypatch, PAYLOAD)
    path = fetch_model(manifest_for(PAYLOAD), tmp_path)
    assert path.read_bytes() == PAYLOAD and calls == [URL]
    assert fetch_model(manifest_for(PAYLOAD), tmp_path) == path  # present: no download
    assert calls == [URL]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["model.pt"]


def test_a_bad_download_leaves_nothing_under_the_real_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, b"tampered")
    with pytest.raises(ModelIntegrityError):
        fetch_model(manifest_for(PAYLOAD), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_missing_file_without_a_source_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="no sourceUrl"):
        fetch_model(manifest_for(PAYLOAD, url=None), tmp_path)


@pytest.mark.parametrize(
    "update",
    [{"sourceUrl": "http://insecure/model.pt"}, {"fileName": "../model.pt"}, {"sha256": "x"}],
)
def test_manifest_rejects_unsafe_values(update: dict[str, str]) -> None:
    wire = {**manifest_for(PAYLOAD).model_dump(by_alias=True), **update}
    with pytest.raises(ValueError):
        ModelManifest.model_validate(wire)


def test_load_scorer_refuses_a_file_that_is_not_the_pinned_one(tmp_path: Path) -> None:
    (tmp_path / "model.pt").write_bytes(b"tampered")
    with pytest.raises(ModelIntegrityError):
        load_scorer(tmp_path / "model.pt", manifest=manifest_for(PAYLOAD))
    assert load_scorer(tmp_path / "absent.pt", manifest=manifest_for(PAYLOAD)) is None
