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
INSTALLER_PATH = REPO / "pilothOS" / "scripts" / "pilothos_installer.py"


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_guard():
    return _load_module("pilothos_guard", GUARD_PATH)


@pytest.fixture()
def guard(monkeypatch):
    # Preset env vars would override contract/receipt presets and make tests
    # non-deterministic across machines/CI — clear them for every test.
    monkeypatch.delenv("PILOTHOS_OPERATIONAL_PRESET", raising=False)
    monkeypatch.delenv("PILOTHOS_PRESET", raising=False)
    # Composability/principal env (T5) would otherwise leak from a dev shell and
    # make skill-index / principal tests non-deterministic.
    monkeypatch.delenv("PILOTHOS_CONSUMER_SKILLS", raising=False)
    monkeypatch.delenv("PILOTHOS_PRINCIPAL", raising=False)
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


@pytest.fixture()
def installer():
    return _load_module("pilothos_installer", INSTALLER_PATH)
