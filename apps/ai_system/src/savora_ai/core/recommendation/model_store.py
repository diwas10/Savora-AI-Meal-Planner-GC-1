"""Model delivery: the trained checkpoint is not in git, so a tracked manifest pins it.

The manifest (`Data/models/manifest.json`) records the model version, file name, size,
SHA-256 and where to download it. The backend verifies the file against the manifest
before loading it, and a mismatch is an error, never a silent fallback to popularity:
a missing file falls back (explicitly, `MODEL_UNAVAILABLE`); a wrong file does not load.

    uv run python -m savora_ai.core.recommendation.model_store --download
    uv run python -m savora_ai.core.recommendation.model_store   # verify only
"""

import argparse
import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

REPO = Path(__file__).parents[6]
DEFAULT_MANIFEST = REPO / "Data/models/manifest.json"
DOWNLOAD_TIMEOUT_S = 120
_CHUNK = 1 << 20


class ModelIntegrityError(RuntimeError):
    """The model file exists but is not the one the manifest pins."""


class ModelManifest(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", alias_generator=to_camel, populate_by_name=True
    )

    model_version: str = Field(min_length=1)
    file_name: str = Field(min_length=1, pattern=r"^[\w.-]+$")  # a bare name, no path
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_url: str | None = Field(default=None, pattern=r"^https://")


def load_manifest(path: Path = DEFAULT_MANIFEST) -> ModelManifest:
    return ModelManifest.model_validate_json(path.read_text(encoding="utf-8"))


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model(path: Path, manifest: ModelManifest) -> None:
    """Raise ModelIntegrityError unless `path` is exactly the pinned file."""
    size = path.stat().st_size
    if size != manifest.size_bytes:
        raise ModelIntegrityError(f"{path.name}: {size} bytes, manifest pins {manifest.size_bytes}")
    actual = sha256_of(path)
    if actual != manifest.sha256:
        raise ModelIntegrityError(f"{path.name}: sha256 {actual}, manifest pins {manifest.sha256}")


def model_path(manifest: ModelManifest, directory: Path | None = None) -> Path:
    return (directory or DEFAULT_MANIFEST.parent) / manifest.file_name


def fetch_model(manifest: ModelManifest, directory: Path | None = None) -> Path:
    """The verified model file, downloading it first if it is missing.

    Downloads to a temporary file in the same directory and renames it only after it
    verifies, so a partial or wrong download never sits under the real name."""
    target = model_path(manifest, directory)
    if target.exists():
        verify_model(target, manifest)
        return target
    if manifest.source_url is None:
        raise FileNotFoundError(f"{target} is missing and the manifest has no sourceUrl")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    tmp = Path(tmp_name)
    try:
        with (
            os.fdopen(fd, "wb") as out,
            urllib.request.urlopen(manifest.source_url, timeout=DOWNLOAD_TIMEOUT_S) as response,
        ):
            while chunk := response.read(_CHUNK):
                out.write(chunk)
        verify_model(tmp, manifest)
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--dir", type=Path, default=None, help="default: the manifest's folder")
    parser.add_argument("--download", action="store_true", help="download if missing")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    directory = args.dir or args.manifest.parent
    if args.download:
        path = fetch_model(manifest, directory)
    else:
        path = model_path(manifest, directory)
        verify_model(path, manifest)
    print(f"{path}: {manifest.model_version} verified")


if __name__ == "__main__":
    main()
