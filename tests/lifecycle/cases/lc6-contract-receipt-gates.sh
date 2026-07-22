#!/usr/bin/env bash
set -euo pipefail
cd "$1"
G="pilothOS/scripts/pilothos_guard.py"

echo "== missing task contract blocks edit =="
out=$(printf '%s' '{"tool_input":{"file_path":"README.md"}}' | python3 "$G" pre-edit)
grep -q '"decision": "block"' <<< "$out"
grep -q "missing task contract" <<< "$out"

echo "== docs/tests contract cannot touch runtime core =="
out=$(printf '%s' '{
  "task_scope": "docs-only change",
  "affected_layers": ["Docs", "Tests"],
  "allowed_paths": ["pilothOS/scripts/pilothos_guard.py"],
  "expected_evidence": ["docs smoke"],
  "out_of_scope_paths": []
}' | python3 "$G" contract-write)
grep -q "contract_rejected" <<< "$out"
grep -q "consumer_scope" <<< "$out"
printf '%s' '{
  "task_scope": "docs-only change",
  "affected_layers": ["Docs", "Tests"],
  "allowed_paths": ["README.md"],
  "expected_evidence": ["docs smoke"],
  "out_of_scope_paths": []
}' | python3 "$G" contract-write >/dev/null
out=$(printf '%s' '{"tool_input":{"file_path":"pilothOS/scripts/pilothos_guard.py"}}' | python3 "$G" pre-edit)
grep -q '"decision": "block"' <<< "$out"
grep -q "outside allowed_paths" <<< "$out"

echo "== allowed runtime contract passes and out-of-scope path blocks =="
printf '%s' '{
  "task_scope": "guard enforcement",
  "affected_layers": ["Tools/Runtime", "Tests"],
  "allowed_paths": ["pilothOS/scripts/pilothos_guard.py", "tests/lifecycle/**"],
  "expected_evidence": ["py_compile", "lifecycle"],
  "out_of_scope_paths": ["README.md"],
  "consumer_scope": "PilothOS guard runtime only; no consumer app files.",
  "context_evidence": [
    {"source": "pilothOS/scripts/pilothos_guard.py", "reason": "guard owner", "finding": "pre-edit and receipt gates live here"}
  ],
  "reuse_evidence": [
    {"asset": "existing validate_task_contract/pre_edit flow", "decision": "reuse", "reason": "extend existing guard instead of adding a new gate"}
  ],
  "decision_limits": ["Do not relax existing allowed_paths or layer checks without judgment."],
  "consumer_asset_routing": [
    {"task_signal": "not_applicable", "asset_type": "not_applicable", "decision": "not_applicable", "reason": "guard runtime task does not route consumer assets"}
  ],
  "requires_judgment": true
}' | python3 "$G" contract-write >/dev/null
[ -z "$(printf '%s' '{"tool_input":{"file_path":"pilothOS/scripts/pilothos_guard.py"}}' | python3 "$G" pre-edit)" ]
out=$(printf '%s' '{"tool_input":{"file_path":"README.md"}}' | python3 "$G" pre-edit)
grep -q "out of scope" <<< "$out"

echo "== adapter policy changes require pilothOS/rules source =="
printf '%s' '{
  "task_scope": "adapter policy bridge",
  "affected_layers": ["Rules", "Adapters"],
  "allowed_paths": ["adapters/cursor/rules/pilothos-core.mdc"],
  "expected_evidence": ["pre-edit"],
  "out_of_scope_paths": [],
  "consumer_scope": "Adapter bridge files only.",
  "context_evidence": [
    {"source": "adapters/cursor/rules/pilothos-core.mdc", "reason": "target adapter", "finding": "adapter rule delegates to PilothOS"}
  ],
  "reuse_evidence": [
    {"asset": "pilothOS/rules hooks policy", "decision": "not_enough", "reason": "first contract intentionally omits source path to verify block"}
  ],
  "decision_limits": ["Do not fork policy into adapter files."],
  "consumer_asset_routing": [
    {"task_signal": "not_applicable", "asset_type": "not_applicable", "decision": "not_applicable", "reason": "adapter bridge test does not route consumer assets"}
  ]
}' | python3 "$G" contract-write >/dev/null
out=$(printf '%s' '{"tool_input":{"file_path":"adapters/cursor/rules/pilothos-core.mdc"}}' | python3 "$G" pre-edit)
grep -q "source of truth" <<< "$out"
printf '%s' '{
  "task_scope": "adapter policy bridge",
  "affected_layers": ["Rules", "Adapters"],
  "allowed_paths": ["adapters/cursor/rules/pilothos-core.mdc", "pilothOS/rules/hooks.md"],
  "expected_evidence": ["pre-edit"],
  "out_of_scope_paths": [],
  "consumer_scope": "Adapter bridge files and PilothOS hook source only.",
  "context_evidence": [
    {"source": "pilothOS/rules/hooks.md", "reason": "policy source", "finding": "hook policy lives in PilothOS rules"},
    {"source": "adapters/cursor/rules/pilothos-core.mdc", "reason": "target adapter", "finding": "adapter must bridge rather than fork"}
  ],
  "reuse_evidence": [
    {"asset": "existing adapter bridge pattern", "decision": "reuse", "reason": "keep adapter as entry point only"}
  ],
  "decision_limits": ["Do not duplicate OS policy in adapter files."],
  "consumer_asset_routing": [
    {"task_signal": "not_applicable", "asset_type": "not_applicable", "decision": "not_applicable", "reason": "adapter bridge test does not route consumer assets"}
  ]
}' | python3 "$G" contract-write >/dev/null
[ -z "$(printf '%s' '{"tool_input":{"file_path":"adapters/cursor/rules/pilothos-core.mdc"}}' | python3 "$G" pre-edit)" ]

printf '%s' '{
  "task_scope": "guard enforcement",
  "affected_layers": ["Tools/Runtime", "Tests"],
  "allowed_paths": ["pilothOS/scripts/pilothos_guard.py", "tests/lifecycle/**"],
  "expected_evidence": ["py_compile", "lifecycle"],
  "out_of_scope_paths": ["README.md"],
  "consumer_scope": "PilothOS guard runtime only; no consumer app files.",
  "context_evidence": [
    {"source": "pilothOS/scripts/pilothos_guard.py", "reason": "guard owner", "finding": "pre-edit and receipt gates live here"}
  ],
  "reuse_evidence": [
    {"asset": "existing validate_task_contract/pre_edit flow", "decision": "reuse", "reason": "extend existing guard instead of adding a new gate"}
  ],
  "decision_limits": ["Do not relax existing allowed_paths or layer checks without judgment."],
  "consumer_asset_routing": [
    {"task_signal": "not_applicable", "asset_type": "not_applicable", "decision": "not_applicable", "reason": "guard runtime task does not route consumer assets"}
  ],
  "requires_judgment": true
}' | python3 "$G" contract-write >/dev/null

echo "== post-edit records diff facts =="
out=$(printf '%s' '{"tool_input":{"file_path":"pilothOS/scripts/pilothos_guard.py"}}' | python3 "$G" post-edit)
grep -q "diff_facts_recorded" <<< "$out"
grep -q "Tools/Runtime" <<< "$out"

echo "== receipt requires judgment checklist for judgment-sensitive work =="
out=$(printf '%s' '{
  "changed_files": ["pilothOS/scripts/pilothos_guard.py"],
  "affected_layers": ["Tools/Runtime"],
  "verification_command": "python3 -m py_compile pilothOS/scripts/pilothos_guard.py",
  "result": "passed"
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "judgment_checklist" <<< "$out"

echo "== valid receipt records =="
printf '%s' '{
  "changed_files": ["pilothOS/scripts/pilothos_guard.py"],
  "affected_layers": ["Tools/Runtime"],
  "verification_command": "python3 -m py_compile pilothOS/scripts/pilothos_guard.py",
  "result": "passed",
  "scope_evidence": "pilothOS/scripts/pilothos_guard.py is within the task contract allowed_paths and Tools/Runtime layer.",
  "context_used": [
    {"source": "pilothOS/scripts/pilothos_guard.py", "reason": "guard owner", "finding": "receipt validation lives here"}
  ],
  "consumer_asset_routing": [
    {"task_signal": "not_applicable", "asset_type": "not_applicable", "decision": "not_applicable", "reason": "guard runtime task does not route consumer assets"}
  ],
  "learning_review": {
    "mistake_checked": "none",
    "lesson_decision": "none",
    "promoted_to": "not_applicable",
    "reason": "Lifecycle guard test did not expose a repeated operational mistake."
  },
  "quality_gates": {
    "reuse_non_duplication": {
      "result": "PASS",
      "evidence": "reuse_discipline and context_used were recorded for this lifecycle case."
    }
  },
  "judgment_checklist": {
    "layer_fit": "Tools/Runtime is the owner of guard enforcement.",
    "abstraction": "No new external abstraction; only guard modes.",
    "scope": "Scope limited to guard enforcement and lifecycle tests.",
    "evidence": "Compile and lifecycle gate tests cover the mechanical claims."
  },
  "reuse_discipline": {
    "existing_code_checked": "pilothOS/scripts/pilothos_guard.py",
    "existing_component_checked": "not_applicable: no UI components in guard runtime",
    "existing_pattern_followed": "existing validate/write/read guard flow",
    "new_code_reason": "extend enforcement fields requested by lifecycle gate",
    "duplicate_risk": "low: reused current guard validators",
    "kiss_dry_rationale": "single guard path, no new runner"
  },
  "warning_checklist": {
    "code_without_test_reason": "This lifecycle unit records guard diff facts without running a separate test file in the same fact set."
  }
}' | python3 "$G" receipt-write | grep -q "deliver receipt recorded"

echo "== session post-edit facts feed manual receipt-write =="
printf '%s' '{"session_id":"lc6facts","tool_input":{"file_path":"tests/lifecycle/cases/lc6-contract-receipt-gates.sh"}}' | python3 "$G" post-edit >/dev/null
out=$(printf '%s' '{
  "changed_files": ["pilothOS/scripts/pilothos_guard.py"],
  "affected_layers": ["Tools/Runtime"],
  "verification_command": "python3 -m py_compile pilothOS/scripts/pilothos_guard.py",
  "result": "passed",
  "judgment_checklist": {
    "layer_fit": "Tools/Runtime is the owner of guard enforcement.",
    "abstraction": "No new external abstraction; only guard modes.",
    "scope": "Scope limited to guard enforcement and lifecycle tests.",
    "evidence": "Compile and lifecycle gate tests cover the mechanical claims."
  },
  "reuse_discipline": {
    "existing_code_checked": "pilothOS/scripts/pilothos_guard.py",
    "existing_component_checked": "not_applicable: no UI components in guard runtime",
    "existing_pattern_followed": "existing validate/write/read guard flow",
    "new_code_reason": "extend enforcement fields requested by lifecycle gate",
    "duplicate_risk": "low: reused current guard validators",
    "kiss_dry_rationale": "single guard path, no new runner"
  }
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "lc6-contract-receipt-gates.sh" <<< "$out"

echo "== stop-check blocks invalid deliver receipt =="
bad_receipt="$(mktemp)"
printf '%s' '{"changed_files":[]}' > "$bad_receipt"
printf '%s' '{"session_id":"lc6"}' | python3 "$G" session-start >/dev/null
printf '\n# lc6 temp change\n' >> pilothOS/VALIDATION.md
out=$(printf '%s' '{"session_id":"lc6"}' | env PILOTHOS_DELIVER_RECEIPT="$bad_receipt" python3 "$G" stop-check)
grep -q '"decision": "block"' <<< "$out"
grep -q "Deliver receipt invalid" <<< "$out"

# The staged workspace is NOT a git repo, so the two checks above exercise the
# mtime fallback (deliver gate still fires when git is unavailable). The next two
# cases turn it into a git repo to exercise the commit-as-delivery waiver.
echo "== committed session passes deliver gate (commit = delivery) =="
git init -q .
git config user.email "lc6@test.local"
git config user.name "lc6"
git add -A
git commit -q -m "lc6 baseline"
printf '%s' '{"session_id":"lc6commit"}' | python3 "$G" session-start >/dev/null
printf '\n# lc6 committed change\n' >> pilothOS/VALIDATION.md
git add -A
git commit -q -m "lc6 session change delivered via commit"
out=$(printf '%s' '{"session_id":"lc6commit"}' | python3 "$G" stop-check)
[ -z "$out" ] || { echo "FAIL: expected no block after commit, got: $out"; exit 1; }

echo "== uncommitted change still triggers gate under git =="
printf '%s' '{"session_id":"lc6dirty"}' | python3 "$G" session-start >/dev/null
printf '\n# lc6 uncommitted change\n' >> pilothOS/VALIDATION.md
out=$(printf '%s' '{"session_id":"lc6dirty"}' | env PILOTHOS_DELIVER_RECEIPT="$bad_receipt" python3 "$G" stop-check)
grep -q '"decision": "block"' <<< "$out"
