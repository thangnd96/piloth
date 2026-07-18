"""Shared fixtures for guard unit tests.

Loads pilothos_guard.py as an importable module straight from its file path so
its pure decision functions can be unit-tested in isolation, without going
through the CLI. The module has an `if __name__ == "__main__"` guard, so import
has no side effects.
"""
import importlib.util
import os
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
GUARD_PATH = REPO / "pilothOS" / "scripts" / "pilothos_guard.py"


def _load_guard():
    spec = importlib.util.spec_from_file_location("pilothos_guard", GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def guard(monkeypatch):
    # Preset env vars would override contract/receipt presets and make tests
    # non-deterministic across machines/CI — clear them for every test.
    monkeypatch.delenv("PILOTHOS_OPERATIONAL_PRESET", raising=False)
    monkeypatch.delenv("PILOTHOS_PRESET", raising=False)
    return _load_guard()


@pytest.fixture()
def good_receipt():
    """A minimal receipt that validates cleanly under the light preset."""
    return {
        "operational_preset": "light",
        "changed_files": ["pilothOS/scripts/pilothos_guard.py"],
        "affected_layers": ["Tools/Runtime"],
        "verification_command": "python3 -m pytest tests/unit -q",
        "result": "passed",
    }


@pytest.fixture()
def light_contract():
    return {"operational_preset": "light"}
