"""Unit tests for the commit-aware deliver gate.

Covers two fixes:
  1. `session_uncommitted_changes` — the git-aware trigger that lets a committed
     session pass the Stop gate (commit counts as delivery).
  2. `post_edit` pruning — diff-facts `changed_files` drops entries no longer in
     the working tree (committed or reverted) instead of accumulating forever.

Collaborators that hit the filesystem/git/subprocess are monkeypatched so the
tests are deterministic and do not depend on the checkout's real git state.
"""
import os


def _touch(path, mtime):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_uncommitted_changes_filters_by_mtime(guard, monkeypatch, tmp_path):
    # Only files touched after the session start (mtime > ts) are session changes.
    ts = 1000.0
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    _touch(tmp_path / "fresh.py", ts + 100)   # edited this session, still dirty
    _touch(tmp_path / "stale.py", ts - 100)   # pre-existing dirt, not this session
    monkeypatch.setattr(guard, "git_changed_file_paths", lambda: ["fresh.py", "stale.py"])
    assert guard.session_uncommitted_changes(ts) == ["fresh.py"]


def test_uncommitted_changes_empty_when_all_committed(guard, monkeypatch, tmp_path):
    # Working tree clean of session changes → nothing undelivered → gate passes.
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(guard, "git_changed_file_paths", lambda: [])
    assert guard.session_uncommitted_changes(1000.0) == []


def test_uncommitted_changes_excludes_scan_dirs_and_files(guard, monkeypatch, tmp_path):
    # node_modules etc. and the review-log/lessons files must not trigger the gate.
    ts = 1000.0
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    _touch(tmp_path / "node_modules" / "dep.js", ts + 100)     # excluded dir
    log = tmp_path / "pilothOS" / "rot" / "review-log.md"
    _touch(log, ts + 100)                                       # excluded file
    _touch(tmp_path / "real.py", ts + 100)                      # kept
    monkeypatch.setattr(guard, "SCAN_EXCLUDE_FILES", {log.resolve()})
    monkeypatch.setattr(
        guard, "git_changed_file_paths",
        lambda: ["node_modules/dep.js", "pilothOS/rot/review-log.md", "real.py"],
    )
    assert guard.session_uncommitted_changes(ts) == ["real.py"]


def test_post_edit_prunes_committed_files_from_diff_facts(guard, monkeypatch):
    # A file recorded earlier then committed drops out; the fresh edit stays.
    stale = {
        "changed_files": {
            "committed_away.py": {"layer": "Tools", "added": 3, "deleted": 0,
                                  "changed_lines": 3, "new_file": False},
        },
        "warnings": [],
    }
    guard.ensure_diff_fact_fields(stale)
    saved = {}
    monkeypatch.setattr(guard, "is_git_repo", lambda: True)
    monkeypatch.setattr(guard, "load_diff_facts", lambda hi: stale)
    monkeypatch.setattr(guard, "load_task_contract", lambda hi: ({}, None))
    monkeypatch.setattr(guard, "git_numstat", lambda rel: (2, 1))
    monkeypatch.setattr(guard, "git_path_is_new", lambda rel: False)
    # Working tree now shows only the fresh edit; committed_away.py landed in a commit.
    monkeypatch.setattr(guard, "git_changed_file_paths", lambda: ["fresh_edit.py"])
    monkeypatch.setattr(guard, "save_diff_facts", lambda hi, facts: saved.update(facts))

    guard.post_edit({"tool_input": {"file_path": "fresh_edit.py"}, "session_id": "s"})

    assert "fresh_edit.py" in saved["changed_files"]
    assert "committed_away.py" not in saved["changed_files"]
