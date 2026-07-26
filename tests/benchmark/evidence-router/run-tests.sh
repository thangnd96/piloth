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
    plan = out["execution_plan"]
    assert plan["mandatory_independent_review"] is task["expected_independent_review"], task["id"]
    if task.get("expected_mode"):
        assert plan["mode"] == task["expected_mode"], task["id"]
    if plan["mandatory_independent_review"]:
        # The reviewer must be declared, not merely promised in prose.
        assert [r["id"] for r in plan["roles"]] == ["external_reviewer"], task["id"]
        assert plan["mode"].startswith("single_with_"), (task["id"], plan["mode"])
    results.append({
        "id": task["id"],
        "class": out["task_class"],
        "independent_review": plan["mandatory_independent_review"],
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
