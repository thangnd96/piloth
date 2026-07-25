import importlib.util
import pathlib

import pytest


def _bind_consumer(guard, monkeypatch, tmp_path):
    repo = tmp_path / "consumer"
    (repo / "pilothOS" / "memory" / "state").mkdir(parents=True)
    monkeypatch.setattr(guard, "REPO_ROOT", repo)
    monkeypatch.setattr(guard, "PILOTHOS_DIR", repo / "pilothOS")
    monkeypatch.setattr(
        guard, "CODEBASE_INDEX_DIR",
        repo / "pilothOS" / "memory" / "state" / "codebase-index",
    )
    monkeypatch.setattr(
        guard, "CODEBASE_INDEX_DB",
        repo / "pilothOS" / "memory" / "state" / "codebase-index" / "index.sqlite3",
    )
    return repo


def _write_fixture(repo):
    (repo / "src").mkdir()
    (repo / "generated").mkdir()
    source = (
        "def helper(value):\n"
        "    return value + 1\n\n"
        "def entry(value):\n"
        "    return helper(value)\n"
    )
    (repo / "src" / "app.py").write_text(source, encoding="utf-8")
    (repo / "generated" / "app.py").write_text(
        "# " + ("header " * 800) + "\n# GENERATED FILE - DO NOT EDIT\n" + source,
        encoding="utf-8",
    )
    (repo / "src" / "view.ts").write_text(
        "export function view() { return 1 }\n",
        encoding="utf-8",
    )


def test_index_search_trace_and_generated_alias(guard, monkeypatch, tmp_path):
    repo = _bind_consumer(guard, monkeypatch, tmp_path)
    _write_fixture(repo)

    indexed = guard.codebase_index_payload({})
    assert indexed["result"] == "codebase_indexed"
    assert indexed["generated_aliases"] == 2
    assert indexed["freshness"] == "fresh"

    search = guard.codebase_query_payload({"action": "search", "query": "helper"})
    assert search["result"] == "codebase_query"
    assert len(search["results"]) == 1
    assert search["results"][0]["path"] == "src/app.py"
    assert search["results"][0]["alias_count"] == 1

    trace = guard.codebase_query_payload({
        "action": "trace",
        "symbol": "src.app.entry",
        "direction": "outbound",
    })
    assert [row["qualified_name"] for row in trace["outbound"]] == ["src.app.helper"]


def test_status_detects_content_and_structural_staleness(guard, monkeypatch, tmp_path):
    repo = _bind_consumer(guard, monkeypatch, tmp_path)
    _write_fixture(repo)
    assert guard.codebase_index_payload({})["result"] == "codebase_indexed"
    assert guard.codebase_status_payload()["status"] == "fresh"

    (repo / "src" / "app.py").write_text("def changed():\n    return 2\n", encoding="utf-8")
    assert guard.codebase_status_payload()["status"] == "stale_content"

    (repo / "src" / "new.py").write_text("value = 1\n", encoding="utf-8")
    assert guard.codebase_status_payload()["status"] == "stale_structural"


def test_coverage_is_deep_for_python_and_shallow_elsewhere(guard, monkeypatch, tmp_path):
    repo = _bind_consumer(guard, monkeypatch, tmp_path)
    _write_fixture(repo)
    guard.codebase_index_payload({})

    out = guard.codebase_query_payload({
        "action": "coverage",
        "paths": ["src/app.py", "src/view.ts"],
    })
    statuses = {row["path"]: row["status"] for row in out["paths"]}
    assert statuses == {"src/app.py": "deep", "src/view.ts": "shallow"}
    assert all(row["caveat"] == "best_effort_not_completeness_proof" for row in out["paths"])


def test_snippet_reads_live_source_and_reports_freshness(guard, monkeypatch, tmp_path):
    repo = _bind_consumer(guard, monkeypatch, tmp_path)
    _write_fixture(repo)
    guard.codebase_index_payload({})

    fresh = guard.codebase_query_payload({
        "action": "snippet",
        "symbol": "src.app.helper",
    })
    assert fresh["source_freshness"] == "metadata_match"
    assert "return value + 1" in fresh["source"]

    path = repo / "src" / "app.py"
    path.write_text(path.read_text() + "\n# changed\n", encoding="utf-8")
    changed = guard.codebase_query_payload({
        "action": "snippet",
        "symbol": "src.app.helper",
    })
    assert changed["source_freshness"] == "changed"
    assert changed["trust"] == "candidate_only"
    assert changed["source_fallback_required"] is True


def test_external_repo_path_is_rejected(guard, monkeypatch, tmp_path):
    repo = _bind_consumer(guard, monkeypatch, tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    out = guard.codebase_index_payload({"repo_path": str(outside)})
    assert out["result"] == "codebase_index_rejected"
    assert "controlled consumer" in out["errors"][0]


def test_python_redefinition_keeps_last_definition(guard, monkeypatch, tmp_path):
    repo = _bind_consumer(guard, monkeypatch, tmp_path)
    (repo / "duplicate.py").write_text(
        "def current():\n    return 1\n\n"
        "def current():\n    return 2\n",
        encoding="utf-8",
    )

    indexed = guard.codebase_index_payload({})
    result = guard.codebase_query_payload({
        "action": "snippet", "symbol": "duplicate.current",
    })

    assert indexed["result"] == "codebase_indexed"
    assert "return 2" in result["source"]


def test_identical_consumer_sources_are_not_collapsed(guard, monkeypatch, tmp_path):
    repo = _bind_consumer(guard, monkeypatch, tmp_path)
    (repo / "one.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    (repo / "two.py").write_text("def helper():\n    return 1\n", encoding="utf-8")

    indexed = guard.codebase_index_payload({})
    search = guard.codebase_query_payload({"action": "search", "query": "helper"})

    assert indexed["generated_aliases"] == 0
    assert {row["path"] for row in search["results"]} == {"one.py", "two.py"}


def test_index_enforces_total_byte_budget(guard, monkeypatch, tmp_path):
    repo = _bind_consumer(guard, monkeypatch, tmp_path)
    (repo / "source.py").write_text("value = 1\n", encoding="utf-8")

    result = guard.codebase_index_payload({"max_total_bytes": 1})

    assert result["result"] == "codebase_index_refused"
    assert not guard.codebase_index_paths()[1].exists()


def test_index_rejects_symlinked_state_directory(guard, monkeypatch, tmp_path):
    repo = _bind_consumer(guard, monkeypatch, tmp_path)
    outside = tmp_path / "outside-state"
    outside.mkdir()
    state_dir = repo / "pilothOS" / "memory" / "state" / "codebase-index"
    try:
        state_dir.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable on this platform")

    result = guard.codebase_index_payload({})

    assert result["result"] == "codebase_index_rejected"
    assert "symlink" in result["errors"][0]


def test_dot_prefixed_paths_are_preserved(guard):
    assert guard.codebase_normalize_rel(".github/workflows/ci.yml") == (
        ".github/workflows/ci.yml"
    )


def test_missing_index_is_advisory_and_never_auto_indexes(guard, monkeypatch, tmp_path):
    _bind_consumer(guard, monkeypatch, tmp_path)
    status = guard.codebase_status_payload()
    assert status["status"] == "missing"
    query = guard.codebase_query_payload({"action": "overview"})
    assert query["result"] == "codebase_query_unavailable"


def test_distribution_excludes_local_codebase_index():
    distribution_path = pathlib.Path(__file__).parents[2] / "scripts" / "_distribution.py"
    spec = importlib.util.spec_from_file_location("piloth_distribution", distribution_path)
    distribution = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(distribution)

    assert distribution.ignored_distribution_artifact(
        pathlib.PurePosixPath("memory/state/codebase-index/index.sqlite3")
    )
