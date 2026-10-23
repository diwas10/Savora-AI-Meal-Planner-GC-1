"""Test-only artifact selection; never downloads or copies trained weights."""

import os
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parent
CHECKPOINT = Path(os.environ.get("SAVORA_TEST_CHECKPOINT_PATH", SERVICE_DIR / "sasrec_content.pt"))


def pytest_collection_modifyitems(items):
    if CHECKPOINT.is_file():
        return
    if os.environ.get("SAVORA_TEST_CHECKPOINT_PATH"):
        raise pytest.UsageError("SAVORA_TEST_CHECKPOINT_PATH must identify an existing checkpoint")
    skip = pytest.mark.skip(reason="Trained checkpoint absent; see README.md")
    for item in items:
        if item.get_closest_marker("checkpoint"):
            item.add_marker(skip)
