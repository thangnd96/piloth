#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

# Caches stay out of the repo — see tests/unit/run-tests.sh for why (artifact
# janitor counts them, so the mandated verification command must not create any).
PYTHONPYCACHEPREFIX=/tmp/piloth-codebase-memory-pycache \
  python3 -m pytest tests/unit/test_guard_codebase_intelligence.py -q \
  -o cache_dir=/tmp/piloth-codebase-memory-pytest-cache

python3 - <<'PY'
import importlib.util
import json
import pathlib
import tempfile
import time

root = pathlib.Path.cwd()
spec = importlib.util.spec_from_file_location(
    "pilothos_guard", root / "pilothOS/scripts/pilothos_guard.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

with tempfile.TemporaryDirectory() as tmp:
    repo = pathlib.Path(tmp) / "consumer"
    (repo / "pilothOS/memory/state").mkdir(parents=True)
    (repo / "src").mkdir()
    for index in range(240):
        next_call = f"fn_{index + 1}()" if index < 239 else "return 239"
        (repo / "src" / f"module_{index:03d}.py").write_text(
            f"def fn_{index}():\n    {next_call}\n", encoding="utf-8")

    guard.REPO_ROOT = repo
    guard.PILOTHOS_DIR = repo / "pilothOS"

    t0 = time.perf_counter()
    indexed = guard.codebase_index_payload({})
    index_ms = (time.perf_counter() - t0) * 1000
    assert indexed["result"] == "codebase_indexed", indexed

    samples = []
    for _ in range(15):
        start = time.perf_counter()
        graph = guard.codebase_query_payload({
            "action": "trace", "symbol": "src.module_000.fn_0",
            "direction": "outbound", "depth": 5, "limit": 20,
        })
        samples.append((time.perf_counter() - start) * 1000)
    graph_rows = graph["outbound"]
    assert [row["qualified_name"] for row in graph_rows[:2]] == [
        "src.module_001.fn_1", "src.module_002.fn_2"]

    baseline_bytes = sum(path.stat().st_size for path in (repo / "src").glob("*.py"))
    graph_bytes = len(json.dumps(graph, separators=(",", ":")).encode())
    context_reduction = 1 - graph_bytes / baseline_bytes
    median_ms = sorted(samples)[len(samples) // 2]
    assert context_reduction >= 0.30, (baseline_bytes, graph_bytes)

    print(json.dumps({
        "result": "PASS",
        "metric_type": "deterministic_retrieval_proxy",
        "quality": "ground_truth_call_chain_matched",
        "index_ms": round(index_ms, 3),
        "median_query_ms": round(median_ms, 3),
        "baseline_context_bytes": baseline_bytes,
        "graph_context_bytes": graph_bytes,
        "context_reduction_pct": round(context_reduction * 100, 1),
        "limitation": "context bytes are not real LLM token telemetry",
    }, sort_keys=True))
PY
