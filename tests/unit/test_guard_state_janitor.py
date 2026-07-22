"""Unit tests for state-janitor — retention/GC của rác vòng đời task.

Khoá lại các bất biến an toàn:
- CHỈ xoá thư mục `artifacts/` của os-run ĐÃ SEAL nằm ngoài retention; giữ
  nguyên state/seal JSON và mọi run chưa seal.
- receipt-seals.jsonl (hash-chain) chỉ WARN, không bao giờ bị auto-sửa.
- scheduler-history.jsonl tail-truncate an toàn (không phải chain).
- --kernel-logs rotate lessons/review-log LOSSLESS sang *-archive.md.
- detect mặc định không đổi đĩa.
"""
import json
import os
import time

import pytest


@pytest.fixture()
def env(guard, tmp_path, monkeypatch):
    """Trỏ mọi hằng số path của guard vào một cây state tạm, cô lập repo thật."""
    repo = tmp_path
    state = repo / "pilothOS" / "memory" / "state"
    runs = state / "os-runs"
    runs.mkdir(parents=True)
    monkeypatch.setattr(guard, "REPO_ROOT", repo)
    monkeypatch.setattr(guard, "REPO_KEY", "testrepokey000000")
    monkeypatch.setattr(guard, "OS_RUNS_DIR", runs)
    monkeypatch.setattr(guard, "OS_CURRENT", runs / "current.json")
    monkeypatch.setattr(guard, "SCHEDULER_HISTORY", state / "scheduler-history.jsonl")
    monkeypatch.setattr(guard, "RECEIPT_SEALS", state / "receipt-seals.jsonl")
    monkeypatch.setattr(guard, "LESSONS", repo / "pilothOS" / "memory" / "lessons-learned.md")
    monkeypatch.setattr(guard, "REVIEW_LOG", repo / "pilothOS" / "rot" / "review-log.md")
    monkeypatch.setattr(guard, "LESSONS_ARCHIVE", repo / "pilothOS" / "memory" / "lessons-learned-archive.md")
    monkeypatch.setattr(guard, "REVIEW_LOG_ARCHIVE", repo / "pilothOS" / "rot" / "review-log-archive.md")
    return guard


def mkrun(env, name, sealed=True, age_days=0.0, artifacts=True):
    run_dir = env.OS_RUNS_DIR / name
    run_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "task_id": name,
        "repo_key": env.REPO_KEY,
        "status": "sealed" if sealed else "open",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    if sealed:
        state["seal_sha256"] = "deadbeef"
    state_path = run_dir / "state.json"
    state_path.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "target-seal.json").write_text('{"target_seal_sha256":"x"}\n', encoding="utf-8")
    if artifacts:
        art = run_dir / "artifacts"
        art.mkdir(exist_ok=True)
        (art / "PROTOTYPE.html").write_text("<html>heavy</html>", encoding="utf-8")
        (art / "shot.png").write_bytes(b"\x89PNG" + b"0" * 500)
    t = time.time() - age_days * 86400
    os.utime(state_path, (t, t))
    return run_dir


def set_current(env, name):
    env.OS_CURRENT.write_text(json.dumps({"task_id": name, "repo_key": env.REPO_KEY}) + "\n", encoding="utf-8")


# --------------------------------------------------------------- retention plan

def test_keeps_active_recent_and_protects_unsealed(env):
    set_current(env, "run-a")
    mkrun(env, "run-a", sealed=True, age_days=0)     # active + newest
    mkrun(env, "run-b", sealed=True, age_days=10)     # older, sealed → prunable
    mkrun(env, "run-c", sealed=False, age_days=20)    # oldest, unsealed → protected
    plan = env.os_run_retention_plan(keep_runs=1, keep_days=0)
    by_name = {r["name"]: r for r in plan["runs"]}
    assert by_name["run-a"]["keep"] is True
    assert by_name["run-a"]["prune_artifacts"] is False
    assert by_name["run-b"]["keep"] is False
    assert by_name["run-b"]["prune_artifacts"] is True
    assert by_name["run-c"]["keep"] is False
    assert by_name["run-c"]["prune_artifacts"] is False  # never prune unsealed


def test_age_window_keeps_recent_runs(env):
    mkrun(env, "recent", sealed=True, age_days=1)
    mkrun(env, "ancient", sealed=True, age_days=60)
    plan = env.os_run_retention_plan(keep_runs=0, keep_days=30)
    by_name = {r["name"]: r for r in plan["runs"]}
    assert by_name["recent"]["keep"] is True
    assert by_name["ancient"]["prune_artifacts"] is True


# --------------------------------------------------------------- fix behaviour

def test_fix_removes_only_artifacts_keeps_json(env):
    set_current(env, "keep")
    mkrun(env, "keep", sealed=True, age_days=0)
    old = mkrun(env, "old", sealed=True, age_days=99)
    out = env.state_janitor_result(fix=True, keep_runs=1, keep_days=1)
    assert out["result"] == "state_janitor_cleaned"
    assert not (old / "artifacts").exists()            # heavy artifacts gone
    assert (old / "state.json").exists()               # audit JSON preserved
    assert (old / "target-seal.json").exists()
    assert (env.OS_RUNS_DIR / "keep" / "artifacts").exists()  # in-retention untouched


def test_detect_mode_changes_nothing(env):
    mkrun(env, "old", sealed=True, age_days=99)
    out = env.state_janitor_result(fix=False, keep_runs=0, keep_days=0)
    assert out["mode"] == "detect"
    assert out["result"] == "state_janitor_findings"
    assert (env.OS_RUNS_DIR / "old" / "artifacts").exists()  # detect never deletes


def test_safety_prune_rejects_non_artifacts_path(env):
    mkrun(env, "run", sealed=True)
    res = env._prune_artifacts_dir("pilothOS/memory/state/os-runs/run/state.json")
    assert res["status"] == "skipped"
    assert (env.OS_RUNS_DIR / "run" / "state.json").exists()


# --------------------------------------------------------- receipt-seals (chain)

def test_receipt_seals_warn_only_untouched(env):
    monkeypatch_lines = 3
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(env, "RECEIPT_SEALS_WARN_LINES", monkeypatch_lines)
    try:
        env.RECEIPT_SEALS.write_text(
            "".join(json.dumps({"n": i}) + "\n" for i in range(5)), encoding="utf-8"
        )
        before = env.RECEIPT_SEALS.read_bytes()
        out = env.state_janitor_result(fix=True)
        warn = [f for f in out["findings"] if f["kind"] == "warn"]
        assert warn and warn[0]["action"] == "none"
        assert env.RECEIPT_SEALS.read_bytes() == before  # byte-identical, chain intact
    finally:
        monkeypatch.undo()


# --------------------------------------------------------- scheduler-history tail

def test_scheduler_history_truncates_to_last_n(env):
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(env, "SCHEDULER_HISTORY_KEEP", 3)
    try:
        env.SCHEDULER_HISTORY.write_text(
            "".join(json.dumps({"n": i}) + "\n" for i in range(6)), encoding="utf-8"
        )
        env.state_janitor_result(fix=True)
        lines = [json.loads(l) for l in env.SCHEDULER_HISTORY.read_text().splitlines() if l.strip()]
        assert [r["n"] for r in lines] == [3, 4, 5]  # last 3 kept, oldest dropped
    finally:
        monkeypatch.undo()


# ------------------------------------------------------- kernel-log lossless rotate

LESSONS_HEADER = (
    "# Lessons Learned\n\nAppend-only.\n\n"
    "| Date | Context | Lesson | Promoted To |\n|---|---|---|---|\n"
)


def _rows(n):
    return "".join(f"| 2026-01-0{i%9+1} | ctx{i} | lesson{i} | none |\n" for i in range(n))


def test_kernel_logs_rotation_is_lossless(env):
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(env, "KERNEL_LOG_KEEP_ROWS", 2)
    try:
        env.LESSONS.parent.mkdir(parents=True, exist_ok=True)
        env.LESSONS.write_text(LESSONS_HEADER + _rows(5), encoding="utf-8")
        out = env.state_janitor_result(fix=True, kernel_logs=True)
        assert out["retention"]["kernel_logs"] is True
        live_rows = env._md_table_rowcount(env.LESSONS)
        arch_rows = env._md_table_rowcount(env.LESSONS_ARCHIVE)
        assert live_rows == 2                # live keeps last N
        assert arch_rows == 3               # older moved out
        assert live_rows + arch_rows == 5   # lossless: nothing lost
        # live keeps the NEWEST rows
        assert "lesson4" in env.LESSONS.read_text()
        assert "lesson0" in env.LESSONS_ARCHIVE.read_text()
    finally:
        monkeypatch.undo()


def test_kernel_logs_not_touched_without_flag(env):
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(env, "KERNEL_LOG_KEEP_ROWS", 2)
    try:
        env.LESSONS.parent.mkdir(parents=True, exist_ok=True)
        env.LESSONS.write_text(LESSONS_HEADER + _rows(5), encoding="utf-8")
        env.state_janitor_result(fix=True, kernel_logs=False)
        assert env._md_table_rowcount(env.LESSONS) == 5   # untouched in default path
        assert not env.LESSONS_ARCHIVE.exists()
    finally:
        monkeypatch.undo()
