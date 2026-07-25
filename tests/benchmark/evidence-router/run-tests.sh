#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

PYTHONPYCACHEPREFIX=/tmp/piloth-evidence-router-benchmark-pycache python3 - <<'PY'
import importlib.util
import json
import pathlib

root = pathlib.Path.cwd()
spec = importlib.util.spec_from_file_location(
    "pilothos_guard", root / "pilothOS/scripts/pilothos_guard.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

corpus = json.loads(
    (root / "tests/benchmark/evidence-router/corpus.json").read_text(encoding="utf-8")
)
results = []
for task in corpus["tasks"]:
    out = guard.evidence_route_payload(task["request"])
    assert out["result"] == "evidence_route", (task["id"], out)
    assert out["task_class"] == task["expected_class"], (task["id"], out["task_class"])
    assert out["execution_plan"]["team"] is task["expected_team"], task["id"]
    if task.get("expected_mode"):
        assert out["execution_plan"]["mode"] == task["expected_mode"], task["id"]
    if out["execution_plan"]["team"]:
        assert out["execution_plan"]["team_score"] >= 60, task["id"]
        assert len([
            package for package in out["execution_plan"]["work_packages"]
            if package["independent"]
        ]) >= 2, task["id"]
    results.append({
        "id": task["id"],
        "class": out["task_class"],
        "team": out["execution_plan"]["team"],
        "confidence": out["confidence"],
        "evidence_items": len(out["evidence_plan"]),
    })

print(json.dumps({
    "result": "PASS",
    "metric_type": "deterministic_router_policy_corpus",
    "comparison_modes": corpus["comparison_modes"],
    "tasks": results,
    "quality_floor": corpus["quality_floor"],
    "limitation": "Resource SLA claims require external agent runs and real_token_telemetry=true; this gate verifies policy invariants only."
}, sort_keys=True))
PY
