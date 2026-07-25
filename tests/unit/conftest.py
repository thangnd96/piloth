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
def guard(monkeypatch, tmp_path):
    # Preset env vars would override contract/receipt presets and make tests
    # non-deterministic across machines/CI — clear them for every test.
    monkeypatch.delenv("PILOTHOS_OPERATIONAL_PRESET", raising=False)
    monkeypatch.delenv("PILOTHOS_PRESET", raising=False)
    module = _load_guard()
    # Same reason for adapter identity: the harness running the suite would
    # otherwise decide which capability profile the router sees, so a test would
    # pass under Claude Code and fail in CI.
    monkeypatch.delenv("PILOTHOS_ADAPTER", raising=False)
    for var, _adapter in module.ADAPTER_ENV_SIGNALS:
        monkeypatch.delenv(var, raising=False)
    # Compatibility history is repo-local runtime state. Unit tests must never
    # consume or mutate a developer's real scheduler history.
    module.SCHEDULER_HISTORY = tmp_path / "scheduler-history.jsonl"
    return module


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
