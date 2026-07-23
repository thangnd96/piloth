#!/usr/bin/env bash
# Evaluation suite: consumer-aware contract/receipt gates and asset preservation.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

BASE="$TMP/base"
bash "$REPO/scripts/stage.sh" "$BASE" >/dev/null

fresh_case() {
  local name="$1"
  local dir="$TMP/$name"
  mkdir -p "$dir"
  cp -a "$BASE/." "$dir/"
  printf '%s\n' "$dir"
}

reuse_receipt='
  "reuse_discipline": {
    "existing_code_checked": "pilothOS/scripts/pilothos_guard.py",
    "existing_component_checked": "not_applicable: non-UI guard path",
    "existing_pattern_followed": "existing guard validator flow",
    "new_code_reason": "required by test case",
    "duplicate_risk": "low: extends one guard",
    "kiss_dry_rationale": "kept in existing validator"
  }'

delivery_receipt='
  "scope_evidence": "changed files match the task contract allowed_paths and affected layer",
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
    "reason": "unit case did not expose a repeated operational mistake"
  },
  "quality_gates": {
    "reuse_non_duplication": {
      "result": "PASS",
      "evidence": "reuse_discipline and context_used were recorded for this unit case"
    }
  }'

judgment_receipt='
  "judgment_checklist": {
    "layer_fit": "Tools/Runtime owns guard behavior.",
    "abstraction": "No new abstraction.",
    "scope": "Only guard test path.",
    "evidence": "Receipt validator result is the evidence."
  }'

echo "== E1 contract requires context evidence for code, docs-only remains optional =="
W="$(fresh_case e1)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
cat > missing-context.json <<'JSON'
{
  "task_scope": "code edit",
  "affected_layers": ["Tools/Runtime"],
  "allowed_paths": ["pilothOS/scripts/pilothos_guard.py"],
  "expected_evidence": ["py_compile"],
  "out_of_scope_paths": []
}
JSON
out=$(python3 "$G" contract-write missing-context.json)
grep -q "contract_rejected" <<< "$out"
grep -q "context_evidence" <<< "$out"
out=$(printf '%s' '{"tool_input":{"file_path":"pilothOS/scripts/pilothos_guard.py"}}' | env PILOTHOS_TASK_CONTRACT="$PWD/missing-context.json" python3 "$G" pre-edit)
grep -q '"decision": "block"' <<< "$out"
grep -q "context_evidence" <<< "$out"
cat > docs-contract.json <<'JSON'
{
  "task_scope": "docs edit",
  "affected_layers": ["Docs"],
  "allowed_paths": ["README.md"],
  "expected_evidence": ["docs smoke"],
  "out_of_scope_paths": []
}
JSON
python3 "$G" contract-write docs-contract.json >/dev/null
[ -z "$(printf '%s' '{"tool_input":{"file_path":"README.md"}}' | python3 "$G" pre-edit)" ]

echo "== E2 reuse evidence required for code contracts =="
W="$(fresh_case e2)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
cat > missing-reuse.json <<'JSON'
{
  "task_scope": "code edit",
  "affected_layers": ["Tools/Runtime"],
  "allowed_paths": ["pilothOS/scripts/pilothos_guard.py"],
  "expected_evidence": ["py_compile"],
  "out_of_scope_paths": [],
  "consumer_scope": "guard runtime only",
  "context_evidence": [
    {"source": "pilothOS/scripts/pilothos_guard.py", "reason": "guard owner", "finding": "validators live here"}
  ],
  "decision_limits": ["Do not change adapter policy."]
}
JSON
out=$(python3 "$G" contract-write missing-reuse.json)
grep -q "contract_rejected" <<< "$out"
grep -q "reuse_evidence" <<< "$out"
cat > valid-code-contract.json <<'JSON'
{
  "task_scope": "code edit",
  "affected_layers": ["Tools/Runtime"],
  "allowed_paths": ["pilothOS/scripts/pilothos_guard.py"],
  "expected_evidence": ["py_compile"],
  "out_of_scope_paths": [],
  "consumer_scope": "guard runtime only",
  "context_evidence": [
    {"source": "pilothOS/scripts/pilothos_guard.py", "reason": "guard owner", "finding": "validators live here"}
  ],
  "reuse_evidence": [
    {"asset": "existing validate_task_contract", "decision": "reuse", "reason": "extend current validation"}
  ],
  "decision_limits": ["Do not change adapter policy."],
  "consumer_asset_routing": [
    {"task_signal": "not_applicable", "asset_type": "not_applicable", "decision": "not_applicable", "reason": "guard runtime task does not route consumer assets"}
  ]
}
JSON
python3 "$G" contract-write valid-code-contract.json >/dev/null
[ -z "$(printf '%s' '{"tool_input":{"file_path":"pilothOS/scripts/pilothos_guard.py"}}' | python3 "$G" pre-edit)" ]

echo "== E3 UI design-system evidence required for UI paths =="
W="$(fresh_case e3)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
mkdir -p src/components
cat > ui-no-ds.json <<'JSON'
{
  "task_scope": "UI edit",
  "affected_layers": ["Consumer"],
  "allowed_paths": ["src/components/Button.tsx"],
  "expected_evidence": ["screenshot"],
  "out_of_scope_paths": [],
  "consumer_scope": "consumer UI only",
  "context_evidence": [
    {"source": "src/components/Button.tsx", "reason": "target path", "finding": "UI component path"}
  ],
  "reuse_evidence": [
    {"asset": "component catalog", "decision": "not_enough", "reason": "DS evidence intentionally omitted"}
  ],
  "decision_limits": ["Do not invent DS tokens."],
  "consumer_asset_routing": [
    {"task_signal": "UI/component", "asset_type": "design-system", "decision": "skipped", "reason": "DS evidence intentionally omitted for negative case"}
  ]
}
JSON
out=$(python3 "$G" contract-write ui-no-ds.json)
grep -q "contract_rejected" <<< "$out"
grep -q "ui_design_system_evidence" <<< "$out"
out=$(printf '%s' '{"tool_input":{"file_path":"src/components/Button.tsx"}}' | env PILOTHOS_TASK_CONTRACT="$PWD/ui-no-ds.json" python3 "$G" pre-edit)
grep -q '"decision": "block"' <<< "$out"
grep -q "ui_design_system_evidence" <<< "$out"
cat > ui-with-ds.json <<'JSON'
{
  "task_scope": "UI edit",
  "affected_layers": ["Consumer"],
  "allowed_paths": ["src/components/Button.tsx"],
  "expected_evidence": ["screenshot"],
  "out_of_scope_paths": [],
  "consumer_scope": "consumer UI only",
  "context_evidence": [
    {"source": "src/components/Button.tsx", "reason": "target path", "finding": "UI component path"}
  ],
  "reuse_evidence": [
    {"asset": "component catalog", "decision": "reuse", "reason": "button pattern checked"}
  ],
  "decision_limits": ["Do not invent DS tokens."],
  "consumer_asset_routing": [
    {"task_signal": "UI/component", "asset_type": "design-system", "decision": "loaded", "reason": "component catalog is relevant to UI component edits"}
  ],
  "ui_design_system_evidence": [
    {"source": "component catalog", "checked": "Button component and tokens", "decision": "reuse", "reason": "existing button covers the need"}
  ]
}
JSON
python3 "$G" contract-write ui-with-ds.json >/dev/null
[ -z "$(printf '%s' '{"tool_input":{"file_path":"src/components/Button.tsx"}}' | python3 "$G" pre-edit)" ]

echo "== E4 receipt reuse discipline required for code facts =="
W="$(fresh_case e4)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
cat > valid-code-contract.json <<'JSON'
{
  "task_scope": "guard receipt",
  "affected_layers": ["Tools/Runtime"],
  "allowed_paths": ["pilothOS/scripts/pilothos_guard.py"],
  "expected_evidence": ["receipt-write"],
  "out_of_scope_paths": [],
  "consumer_scope": "guard runtime only",
  "context_evidence": [
    {"source": "pilothOS/scripts/pilothos_guard.py", "reason": "guard owner", "finding": "receipt validation lives here"}
  ],
  "reuse_evidence": [
    {"asset": "validate_deliver_receipt", "decision": "reuse", "reason": "extend current receipt validator"}
  ],
  "decision_limits": ["Do not change unrelated guard modes."],
  "consumer_asset_routing": [
    {"task_signal": "not_applicable", "asset_type": "not_applicable", "decision": "not_applicable", "reason": "guard runtime task does not route consumer assets"}
  ],
  "requires_judgment": true
}
JSON
python3 "$G" contract-write valid-code-contract.json >/dev/null
printf '%s' '{"tool_input":{"file_path":"pilothOS/scripts/pilothos_guard.py"}}' | python3 "$G" post-edit >/dev/null
out=$(printf '%s' "{
  \"changed_files\": [\"pilothOS/scripts/pilothos_guard.py\"],
  \"affected_layers\": [\"Tools/Runtime\"],
  \"verification_command\": \"receipt validator negative case\",
  \"result\": \"passed\",
  $judgment_receipt
}" | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "reuse_discipline" <<< "$out"
out=$(printf '%s' "{
  \"changed_files\": [\"pilothOS/scripts/pilothos_guard.py\"],
  \"affected_layers\": [\"Tools/Runtime\"],
  \"verification_command\": \"receipt validator context case\",
  \"result\": \"passed\",
  $judgment_receipt,
  $reuse_receipt
}" | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "scope_evidence" <<< "$out"
out=$(printf '%s' "{
  \"changed_files\": [\"pilothOS/scripts/pilothos_guard.py\"],
  \"affected_layers\": [\"Tools/Runtime\"],
  \"verification_command\": \"receipt validator warning case\",
  \"result\": \"passed\",
  \"scope_evidence\": \"changed files match the task contract allowed_paths and affected layer\",
  \"context_used\": [
    {\"source\": \"pilothOS/scripts/pilothos_guard.py\", \"reason\": \"guard owner\", \"finding\": \"receipt validation lives here\"}
  ],
  \"consumer_asset_routing\": [
    {\"task_signal\": \"not_applicable\", \"asset_type\": \"not_applicable\", \"decision\": \"not_applicable\", \"reason\": \"guard runtime task does not route consumer assets\"}
  ],
  $judgment_receipt,
  $reuse_receipt
}" | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "learning_review" <<< "$out"
out=$(printf '%s' "{
  \"changed_files\": [\"pilothOS/scripts/pilothos_guard.py\"],
  \"affected_layers\": [\"Tools/Runtime\"],
  \"verification_command\": \"receipt validator gate case\",
  \"result\": \"passed\",
  \"scope_evidence\": \"changed files match the task contract allowed_paths and affected layer\",
  \"context_used\": [
    {\"source\": \"pilothOS/scripts/pilothos_guard.py\", \"reason\": \"guard owner\", \"finding\": \"receipt validation lives here\"}
  ],
  \"consumer_asset_routing\": [
    {\"task_signal\": \"not_applicable\", \"asset_type\": \"not_applicable\", \"decision\": \"not_applicable\", \"reason\": \"guard runtime task does not route consumer assets\"}
  ],
  \"learning_review\": {
    \"mistake_checked\": \"none\",
    \"lesson_decision\": \"none\",
    \"promoted_to\": \"not_applicable\",
    \"reason\": \"unit case did not expose a repeated operational mistake\"
  },
  $judgment_receipt,
  $reuse_receipt
}" | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "quality_gates" <<< "$out"
out=$(printf '%s' "{
  \"changed_files\": [\"pilothOS/scripts/pilothos_guard.py\"],
  \"affected_layers\": [\"Tools/Runtime\"],
  \"verification_command\": \"receipt validator warning case\",
  \"result\": \"passed\",
  $delivery_receipt,
  $judgment_receipt,
  $reuse_receipt
}" | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "code_without_test_reason" <<< "$out"
printf '%s' "{
  \"changed_files\": [\"pilothOS/scripts/pilothos_guard.py\"],
  \"affected_layers\": [\"Tools/Runtime\"],
  \"verification_command\": \"receipt validator positive case\",
  \"result\": \"passed\",
  $delivery_receipt,
  $judgment_receipt,
  $reuse_receipt,
  \"warning_checklist\": {
    \"code_without_test_reason\": \"code-path warning is expected in this receipt validator unit case\"
  }
}" | python3 "$G" receipt-write | grep -q "deliver receipt recorded"

echo "== E5 dependency warnings require reason checklist =="
W="$(fresh_case e5)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
cat > package.json <<'JSON'
{"name":"dep-test","version":"0.0.0"}
JSON
cat > dep-contract.json <<'JSON'
{
  "task_scope": "dependency edit",
  "affected_layers": ["Consumer"],
  "allowed_paths": ["package.json"],
  "expected_evidence": ["dependency smoke"],
  "out_of_scope_paths": [],
  "consumer_scope": "dependency manifest only",
  "context_evidence": [
    {"source": "package.json", "reason": "target manifest", "finding": "dependency file"}
  ],
  "reuse_evidence": [
    {"asset": "existing package manifest", "decision": "reuse", "reason": "modify existing manifest only"}
  ],
  "decision_limits": ["Do not run install or deploy without approval."],
  "consumer_asset_routing": [
    {"task_signal": "tool/MCP", "asset_type": "tool", "decision": "loaded", "reason": "package manifest is the target consumer tool asset"}
  ]
}
JSON
python3 "$G" contract-write dep-contract.json >/dev/null
out=$(printf '%s' '{"tool_input":{"file_path":"package.json"}}' | python3 "$G" post-edit)
grep -q "dependency file changed" <<< "$out"
out=$(printf '%s' "{
  \"changed_files\": [\"package.json\"],
  \"affected_layers\": [\"Consumer\"],
  \"verification_command\": \"dependency smoke\",
  \"result\": \"passed\",
  $reuse_receipt
}" | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "dependency_change_reason" <<< "$out"
printf '%s' "{
  \"changed_files\": [\"package.json\"],
  \"affected_layers\": [\"Consumer\"],
  \"verification_command\": \"dependency smoke\",
  \"result\": \"passed\",
  $delivery_receipt,
  $reuse_receipt,
  \"warning_checklist\": {
    \"dependency_change_reason\": \"package metadata changed in a controlled test case\"
  }
}" | python3 "$G" receipt-write | grep -q "deliver receipt recorded"

echo "== E6 consumer hook preservation merge semantics =="
cd "$REPO"
python3 - <<'PY'
import importlib.util, json
spec=importlib.util.spec_from_file_location('installer','pilothOS/scripts/pilothos_installer.py')
installer=importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
consumer_hook={"matcher":"Write|Edit","hooks":[{"type":"command","command":"echo consumer"}]}
duplicate={"matcher":"Write|Edit","hooks":[{"type":"command","command":"echo duplicate"}]}
piloth_hook={"matcher":"Write|Edit","hooks":[{"type":"command","command":"echo piloth"}]}
consumer={"hooks":{"PreToolUse":[consumer_hook, duplicate]}}
payload={"hooks":{"PreToolUse":[duplicate, piloth_hook]}}
merged=installer.merge_settings_content(consumer, payload, {}, [])
hooks=merged["hooks"]["PreToolUse"]
assert hooks[0] == consumer_hook, hooks
assert hooks[1] == duplicate, hooks
assert hooks[2] == piloth_hook, hooks
assert hooks.count(duplicate) == 1, hooks
try:
    installer.merge_settings_content(
        {"env": {"PILOTHOS_MODE": "consumer"}},
        {"env": {"PILOTHOS_MODE": "pilothos"}},
        {},
        [],
    )
except installer.NeedsJudgment as e:
    assert e.items[0]["type"] == "env_conflict", e.items
else:
    raise AssertionError("env conflict did not require judgment")
try:
    installer.merge_settings_content(
        {"statusLine": {"type": "command", "command": "echo consumer"}},
        {"statusLine": {"type": "command", "command": "echo piloth"}},
        {},
        [],
    )
except installer.NeedsJudgment as e:
    assert e.items[0]["type"] == "statusline_conflict", e.items
else:
    raise AssertionError("statusLine conflict did not require judgment")
print("hook preservation PASS")
PY

echo "== E7 consumer asset registry docs =="
[ -f pilothOS/runtime/consumer-assets.md ]
grep -q "Asset | Type | Owner | Capability | Config/Path | Risk | Load When | Health Check | Notes" pilothOS/runtime/consumer-assets.md
grep -q "Consumer Asset Registry" pilothOS/tools/index.md
grep -q "Consumer assets" pilothOS/tools/index.md
python3 pilothOS/scripts/pilothos_guard.py self-check | grep -q "consumer asset registry hop le"
W="$(fresh_case e7bad)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
python3 - <<'PY'
import pathlib
path = pathlib.Path("pilothOS/runtime/consumer-assets.md")
path.write_text(path.read_text(encoding="utf-8").replace("approval-required", "approval_required"), encoding="utf-8")
PY
out=$(python3 "$G" self-check)
grep -q "SELF-CHECK FAILED" <<< "$out"
grep -q "consumer asset registry thieu contract terms" <<< "$out"

echo "== E8 state isolation across repo keys and latest repo facts =="
A="$(fresh_case e8a)"
B="$(fresh_case e8b)"
GA="$A/pilothOS/scripts/pilothos_guard.py"
GB="$B/pilothOS/scripts/pilothos_guard.py"
printf '%s' '{"session_id":"same-session","tool_input":{"file_path":"pilothOS/scripts/pilothos_guard.py"}}' | (cd "$A" && python3 "$GA" post-edit) >/dev/null
printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed"
}' | (cd "$B" && python3 "$GB" receipt-write) | grep -q "deliver receipt recorded"
out=$(printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed"
}' | (cd "$A" && python3 "$GA" receipt-write))
grep -q "receipt_rejected" <<< "$out"
grep -q "pilothOS/scripts/pilothos_guard.py" <<< "$out"

echo "== E9 tool-control receipt enforcement =="
W="$(fresh_case e9)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
printf '%s' '{
  "tool": "scripts/test.sh",
  "command": "bash scripts/test.sh",
  "risk": "low",
  "timeout": "30s",
  "expected_evidence": "test output"
}' | python3 "$G" tool-check > no-contract-tool.out || true
grep -q '"decision": "block"' no-contract-tool.out
grep -q "active task contract" no-contract-tool.out
out=$(printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed",
  "tool_uses": [
    {"tool": "scripts/test.sh", "command": "bash scripts/test.sh", "risk": "low", "timeout": "30s", "result": "passed", "evidence_output": "test output summary"}
  ]
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "active task contract" <<< "$out"
out=$(printf '%s' '{
  "tool": "scripts/test.sh",
  "command": "bash scripts/test.sh",
  "risk": "low",
  "timeout": "soon",
  "expected_evidence": "test output"
}' | python3 "$G" tool-check)
grep -q '"decision": "block"' <<< "$out"
grep -q "timeout must be a duration" <<< "$out"
out=$(printf '%s' '{
  "tool": "deploy",
  "command": "deploy prod",
  "risk": "medium",
  "timeout": "60s",
  "expected_evidence": "deploy receipt"
}' | python3 "$G" tool-check)
grep -q '"decision": "block"' <<< "$out"
grep -q "risk must be high" <<< "$out"
out=$(printf '%s' '{
  "tool": "deploy",
  "command": "deploy prod",
  "risk": "high",
  "timeout": "60s",
  "expected_evidence": "deploy receipt"
}' | python3 "$G" tool-check)
grep -q '"decision": "block"' <<< "$out"
grep -q "approval_evidence" <<< "$out"
printf '%s' '{
  "tool": "deploy",
  "command": "deploy prod",
  "risk": "high",
  "timeout": "60s",
  "expected_evidence": "deploy receipt",
  "approval_evidence": "user approved production deploy in task thread"
}' | python3 "$G" tool-check > approved-no-contract-tool.out || true
grep -q '"decision": "block"' approved-no-contract-tool.out
grep -q "active task contract" approved-no-contract-tool.out
cat > tool-contract.json <<'JSON'
{
  "task_scope": "tool evidence route",
  "affected_layers": ["Consumer"],
  "allowed_paths": ["README.md"],
  "expected_evidence": ["bash scripts/test.sh produces test output"],
  "out_of_scope_paths": [],
  "consumer_scope": "verification tool only",
  "allowed_entitlements": ["tool.test-runner"],
  "context_evidence": [
    {"source": "scripts/test.sh", "reason": "consumer test runner", "finding": "test command is the expected evidence command"}
  ],
  "reuse_evidence": [
    {"asset": "scripts/test.sh", "decision": "reuse", "reason": "use existing consumer test runner"}
  ],
  "decision_limits": ["Do not run unrelated tools outside the active task contract."],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "test-runner", "decision": "loaded", "reason": "scripts/test.sh is the contract evidence command"}
  ]
}
JSON
python3 "$G" contract-write tool-contract.json >/dev/null
printf '%s' '{
  "tool": "scripts/test.sh",
  "command": "bash scripts/test.sh",
  "risk": "low",
  "timeout": "30s",
  "expected_evidence": "test output"
}' | python3 "$G" tool-check | grep -q "tool check passed"
printf '%s' '{
  "tool": "scripts/test.sh",
  "command": "bash scripts/test.sh",
  "risk": "low",
  "timeout": "30s",
  "expected_evidence": "test output",
  "entitlements": ["tool.test-runner"]
}' | python3 "$G" tool-check | grep -q "tool check passed"
cat > readonly-guard-contract.json <<'JSON'
{
  "task_scope": "local read-only guard evidence route",
  "affected_layers": ["Tools/Runtime"],
  "allowed_paths": ["README.md"],
  "expected_evidence": ["python3 pilothOS/scripts/pilothos_guard.py production-review returns production_review_passed"],
  "out_of_scope_paths": [],
  "consumer_scope": "read-only local guard evidence only",
  "allowed_entitlements": ["tool.release-review"],
  "context_evidence": [
    {"source": "pilothOS/scripts/pilothos_guard.py", "reason": "guard owner", "finding": "production-review is read-only local release review"}
  ],
  "reuse_evidence": [
    {"asset": "tool-control", "decision": "reuse", "reason": "use existing tool-check validation path"}
  ],
  "decision_limits": ["Do not treat external deploy commands as read-only guard evidence."],
  "consumer_asset_routing": [
    {"task_signal": "tool/MCP", "asset_type": "tool", "decision": "loaded", "reason": "local guard command"}
  ]
}
JSON
python3 "$G" contract-write readonly-guard-contract.json >/dev/null
printf '%s' '{
  "tool": "pilothos_guard",
  "command": "python3 pilothOS/scripts/pilothos_guard.py production-review",
  "risk": "low",
  "timeout": "30s",
  "expected_evidence": "production_review_passed",
  "entitlement": "tool.release-review"
}' | python3 "$G" tool-check | grep -q "tool check passed"
printf '%s' '{
  "tool": "pilothos_guard",
  "command": "PYTHONPYCACHEPREFIX=/tmp/piloth-pycache python3 pilothOS/scripts/pilothos_guard.py production-review",
  "risk": "low",
  "timeout": "30s",
  "expected_evidence": "production_review_passed",
  "entitlement": "tool.release-review"
}' | python3 "$G" tool-check | grep -q "tool check passed"
out=$(printf '%s' '{
  "tool": "pilothos_guard",
  "command": "AWS_PROFILE=prod python3 pilothOS/scripts/pilothos_guard.py production-review",
  "risk": "low",
  "timeout": "30s",
  "expected_evidence": "production_review_passed",
  "entitlement": "tool.release-review"
}' | python3 "$G" tool-check)
grep -q '"decision": "block"' <<< "$out"
grep -q "risk must be high" <<< "$out"
out=$(printf '%s' '{
  "tool": "pilothos_guard",
  "command": "python3 pilothOS/scripts/pilothos_guard.py production-review && deploy prod",
  "risk": "low",
  "timeout": "30s",
  "expected_evidence": "production_review_passed",
  "entitlement": "tool.release-review"
}' | python3 "$G" tool-check)
grep -q '"decision": "block"' <<< "$out"
grep -q "risk must be high" <<< "$out"
out=$(printf '%s' '{
  "tool": "scripts/test.sh",
  "command": "bash scripts/test.sh",
  "risk": "low",
  "timeout": "30s",
  "expected_evidence": "test output",
  "entitlements": ["deploy.production"]
}' | python3 "$G" tool-check)
grep -q '"decision": "block"' <<< "$out"
grep -q "entitlement not allowed" <<< "$out"
out=$(printf '%s' '{
  "tool": "scripts/build.sh",
  "command": "bash scripts/build.sh",
  "risk": "medium",
  "timeout": "60s",
  "expected_evidence": "build output"
}' | python3 "$G" tool-check)
grep -q '"decision": "block"' <<< "$out"
grep -q "active task contract" <<< "$out"
out=$(printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed",
  "tool_uses": [
    {"tool": "scripts/test.sh", "command": "bash scripts/test.sh", "risk": "low"}
  ]
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "tool_uses\\[0\\].result" <<< "$out"
out=$(printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed",
  "tool_uses": [
    {"tool": "scripts/test.sh", "command": "bash scripts/test.sh", "risk": "low", "result": "passed", "evidence_output": "test output summary"}
  ]
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "tool_uses\\[0\\].timeout" <<< "$out"
out=$(printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed",
  "tool_uses": [
    {"tool": "scripts/build.sh", "command": "bash scripts/build.sh", "risk": "medium", "timeout": "60s", "result": "passed", "evidence_output": "build output summary"}
  ]
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "active task contract" <<< "$out"
out=$(printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed",
  "tool_uses": [
    {"tool": "scripts/test.sh", "command": "bash scripts/test.sh", "risk": "low", "timeout": "eventually", "result": "passed", "evidence_output": "test output summary"}
  ]
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "timeout must be a duration" <<< "$out"
out=$(printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed",
  "tool_uses": [
    {"tool": "scripts/test.sh", "command": "bash scripts/test.sh", "risk": "low", "timeout": "30s", "result": "passed", "evidence_output": "test output summary", "entitlements": ["deploy.production"]}
  ]
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "entitlement not allowed" <<< "$out"
out=$(printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "deploy prod",
  "result": "passed",
  "tool_uses": [
    {"tool": "deploy", "command": "deploy prod", "risk": "high", "timeout": "60s", "result": "passed", "evidence_output": "deploy command returned success"}
  ]
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "approval_evidence" <<< "$out"
cat > deploy-contract.json <<'JSON'
{
  "task_scope": "deploy evidence route",
  "affected_layers": ["Docs"],
  "allowed_paths": ["README.md"],
  "expected_evidence": ["deploy prod command returns deploy command returned success"],
  "out_of_scope_paths": []
}
JSON
python3 "$G" contract-write deploy-contract.json >/dev/null
printf '%s' '{
  "tool": "deploy",
  "command": "deploy prod",
  "risk": "high",
  "timeout": "60s",
  "expected_evidence": "deploy command returned success",
  "approval_evidence": "user approved production deploy in task thread"
}' | python3 "$G" tool-check | grep -q "tool check passed"
printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "deploy prod",
  "result": "passed",
  "approval_evidence": "user approved production deploy in task thread",
  "tool_uses": [
    {"tool": "deploy", "command": "deploy prod", "risk": "high", "timeout": "60s", "result": "passed", "evidence_output": "deploy command returned success"}
  ]
}' | python3 "$G" receipt-write | grep -q "deliver receipt recorded"

echo "== E10 brownfield asset audit table =="
W="$(fresh_case e10)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
mkdir -p .claude/commands .claude/skills/design-system .codex src/components
printf '# Consumer task command\n' > .claude/commands/consumer-task.md
printf '# Design skill\n' > .claude/skills/design-system/SKILL.md
printf '# Consumer Codex config\nproject_doc_max_bytes = 12345\n' > .codex/config.toml
printf '{"mcpServers":{"figma":{"command":"figma-mcp"}}}\n' > .mcp.json
cat > package.json <<'JSON'
{
  "scripts": {
    "test": "vitest run",
    "build": "vite build",
    "deploy": "vercel --prod"
  }
}
JSON
out=$(python3 "$G" audit-assets)
grep -q "| Asset | Type | Capability | Owner | Risk | Proposed Piloth Handling |" <<< "$out"
grep -q "| .codex | tool | native agent adapter with consumer content | consumer | medium | preserve |" <<< "$out"
grep -q "| .codex/config.toml | tool | Codex adapter config | consumer | medium | preserve |" <<< "$out"
grep -q "| .claude/commands/consumer-task.md | command | agent command | consumer | medium | route |" <<< "$out"
grep -q "| .claude/skills/design-system | skill | agent skill | consumer | medium | route |" <<< "$out"
grep -q "| .mcp.json | mcp | MCP/tool configuration | consumer | medium | route |" <<< "$out"
grep -q "| package.json:scripts.test | test-runner | vitest run | consumer | low | route |" <<< "$out"
grep -q "| package.json:scripts.deploy | command | vercel --prod | consumer | high | wrap |" <<< "$out"
grep -q "| src/components | design-system | UI components/tokens/patterns | consumer | medium | route |" <<< "$out"
out=$(python3 "$G" registry-assets)
grep -q "| Asset | Type | Owner | Capability | Config/Path | Risk | Load When | Health Check | Notes |" <<< "$out"
grep -q "| .codex/config.toml | tool | consumer | Codex adapter config | .codex/config.toml | medium | task-routed | path exists | Consumer-owned; do not move or overwrite |" <<< "$out"
grep -q "| .claude/commands/consumer-task.md | command | consumer | agent command | .claude/commands/consumer-task.md | medium | task-routed | command exists or package script defined | Generated by audit-assets; confirm during brownfield audit |" <<< "$out"
grep -q "| .claude/skills/design-system | skill | consumer | agent skill | .claude/skills/design-system | medium | task-routed | path exists | Generated by audit-assets; confirm during brownfield audit |" <<< "$out"
grep -q "| package.json:scripts.deploy | command | consumer | vercel --prod | package.json:scripts.deploy | high | approval-required | package JSON parses | Route through approval/tool-control boundary |" <<< "$out"
grep -q "| .mcp.json | mcp | consumer | MCP/tool configuration | .mcp.json | medium | task-routed | config exists; list tools succeeds | Generated by audit-assets; confirm during brownfield audit |" <<< "$out"

echo "== E11 operational presets =="
W="$(fresh_case e11)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
printf '%s' '{"tool_input":{"file_path":"pilothOS/scripts/pilothos_guard.py"}}' | python3 "$G" post-edit >/dev/null
out=$(printf '%s' '{
  "changed_files": ["pilothOS/scripts/pilothos_guard.py"],
  "affected_layers": ["Tools/Runtime"],
  "verification_command": "smoke",
  "result": "passed"
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "scope_evidence" <<< "$out"
printf '%s' '{
  "changed_files": ["pilothOS/scripts/pilothos_guard.py"],
  "affected_layers": ["Tools/Runtime"],
  "verification_command": "smoke",
  "result": "passed"
}' | env PILOTHOS_PRESET=light python3 "$G" receipt-write | grep -q "deliver receipt recorded"
W="$(fresh_case e11strict)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
out=$(printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "not run",
  "result": "not run",
  "limitation": "strict negative case"
}' | env PILOTHOS_PRESET=strict python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "strict preset requires clean verification" <<< "$out"
printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed"
}' | env PILOTHOS_PRESET=strict python3 "$G" receipt-write | grep -q "deliver receipt recorded"

echo "== E12 UI receipt requires DS fields and new-component warning reason =="
W="$(fresh_case e12)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
mkdir -p src/components
cat > ui-contract.json <<'JSON'
{
  "task_scope": "UI component edit",
  "affected_layers": ["Consumer"],
  "allowed_paths": ["src/components/FreshButton.tsx"],
  "expected_evidence": ["visual smoke"],
  "out_of_scope_paths": [],
  "consumer_scope": "consumer UI component only",
  "context_evidence": [
    {"source": "src/components", "reason": "component location", "finding": "UI component path"}
  ],
  "reuse_evidence": [
    {"asset": "design-system catalog", "decision": "reuse", "reason": "button pattern checked"}
  ],
  "decision_limits": ["Do not invent tokens outside the design system."],
  "consumer_asset_routing": [
    {"task_signal": "UI/component", "asset_type": "design-system", "decision": "loaded", "reason": "UI component edit requires design-system evidence"}
  ],
  "ui_design_system_evidence": [
    {"source": "design-system catalog", "checked": "button component and tokens", "decision": "extend", "reason": "existing pattern covers most behavior"}
  ]
}
JSON
python3 "$G" contract-write ui-contract.json >/dev/null
cat > src/components/FreshButton.tsx <<'TSX'
export function FreshButton() {
  return <button>Fresh</button>
}
TSX
printf '%s' '{"tool_input":{"file_path":"src/components/FreshButton.tsx"}}' | python3 "$G" post-edit >/dev/null
out=$(printf '%s' '{
  "changed_files": ["src/components/FreshButton.tsx"],
  "affected_layers": ["Consumer"],
  "scope_evidence": "UI file is within allowed_paths for the component edit.",
  "context_used": [
    {"source": "src/components", "reason": "component location", "finding": "component path is UI"}
  ],
  "consumer_asset_routing": [
    {"task_signal": "UI/component", "asset_type": "design-system", "decision": "loaded", "reason": "UI component edit requires design-system evidence"}
  ],
  "learning_review": {
    "mistake_checked": "none",
    "lesson_decision": "none",
    "promoted_to": "not_applicable",
    "reason": "unit case did not expose a repeated operational mistake"
  },
  "verification_command": "visual smoke",
  "result": "passed",
  "reuse_discipline": {
    "existing_code_checked": "src/components",
    "existing_component_checked": "design-system catalog",
    "existing_pattern_followed": "button pattern",
    "new_code_reason": "component variant test case",
    "duplicate_risk": "low in test fixture",
    "kiss_dry_rationale": "single focused component"
  }
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "design_system_checked" <<< "$out"
out=$(printf '%s' '{
  "changed_files": ["src/components/FreshButton.tsx"],
  "affected_layers": ["Consumer"],
  "scope_evidence": "UI file is within allowed_paths for the component edit.",
  "context_used": [
    {"source": "src/components", "reason": "component location", "finding": "component path is UI"}
  ],
  "consumer_asset_routing": [
    {"task_signal": "UI/component", "asset_type": "design-system", "decision": "loaded", "reason": "UI component edit requires design-system evidence"}
  ],
  "learning_review": {
    "mistake_checked": "none",
    "lesson_decision": "none",
    "promoted_to": "not_applicable",
    "reason": "unit case did not expose a repeated operational mistake"
  },
  "verification_command": "visual smoke",
  "result": "passed",
  "reuse_discipline": {
    "existing_code_checked": "src/components",
    "existing_component_checked": "design-system catalog",
    "existing_pattern_followed": "button pattern",
    "new_code_reason": "component variant test case",
    "duplicate_risk": "low in test fixture",
    "kiss_dry_rationale": "single focused component"
  },
  "quality_gates": {
    "reuse_non_duplication": {
      "result": "PASS",
      "evidence": "design-system evidence and reuse discipline recorded"
    }
  },
  "design_system_checked": "design-system catalog checked",
  "component_reuse_decision": "extend existing button pattern",
  "token_reuse_decision": "reuse existing tokens"
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "new_component_reason" <<< "$out"
printf '%s' '{
  "changed_files": ["src/components/FreshButton.tsx"],
  "affected_layers": ["Consumer"],
  "scope_evidence": "UI file is within allowed_paths for the component edit.",
  "context_used": [
    {"source": "src/components", "reason": "component location", "finding": "component path is UI"}
  ],
  "consumer_asset_routing": [
    {"task_signal": "UI/component", "asset_type": "design-system", "decision": "loaded", "reason": "UI component edit requires design-system evidence"}
  ],
  "learning_review": {
    "mistake_checked": "none",
    "lesson_decision": "none",
    "promoted_to": "not_applicable",
    "reason": "unit case did not expose a repeated operational mistake"
  },
  "verification_command": "visual smoke",
  "result": "passed",
  "reuse_discipline": {
    "existing_code_checked": "src/components",
    "existing_component_checked": "design-system catalog",
    "existing_pattern_followed": "button pattern",
    "new_code_reason": "component variant test case",
    "duplicate_risk": "low in test fixture",
    "kiss_dry_rationale": "single focused component"
  },
  "quality_gates": {
    "reuse_non_duplication": {
      "result": "PASS",
      "evidence": "design-system evidence and reuse discipline recorded"
    }
  },
  "design_system_checked": "design-system catalog checked",
  "component_reuse_decision": "extend existing button pattern",
  "token_reuse_decision": "reuse existing tokens",
  "design_system_candidate_review": [
    {"candidate": "all", "decision": "extend", "reason": "component and token candidates were checked in the synthetic UI fixture"}
  ],
  "warning_checklist": {
    "new_component_reason": "new component-like file created by UI test fixture",
    "code_without_test_reason": "visual smoke recorded as receipt verification in this unit case"
  }
}' | python3 "$G" receipt-write | grep -q "deliver receipt recorded"

echo "== E13 large delta warning requires checklist =="
W="$(fresh_case e13)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
git init -q
mkdir -p src
cat > large-contract.json <<'JSON'
{
  "task_scope": "large code edit",
  "affected_layers": ["Consumer"],
  "allowed_paths": ["src/large.ts"],
  "expected_evidence": ["unit smoke"],
  "out_of_scope_paths": [],
  "consumer_scope": "consumer source file only",
  "context_evidence": [
    {"source": "src", "reason": "source location", "finding": "consumer code path"}
  ],
  "reuse_evidence": [
    {"asset": "existing source patterns", "decision": "not_applicable", "reason": "large delta warning test fixture"}
  ],
  "decision_limits": ["Do not add broad abstractions without review."],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "convention", "decision": "not_applicable", "reason": "synthetic large delta test has no consumer convention asset"}
  ]
}
JSON
python3 "$G" contract-write large-contract.json >/dev/null
for i in $(seq 1 260); do printf 'export const value%s = %s;\n' "$i" "$i"; done > src/large.ts
out=$(printf '%s' '{"tool_input":{"file_path":"src/large.ts"}}' | python3 "$G" post-edit)
grep -q "large delta requires reuse discipline" <<< "$out"
out=$(printf '%s' '{
  "changed_files": ["src/large.ts"],
  "affected_layers": ["Consumer"],
  "scope_evidence": "src/large.ts is within allowed_paths for the large delta test.",
  "context_used": [
    {"source": "src", "reason": "source location", "finding": "consumer code path"}
  ],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "convention", "decision": "not_applicable", "reason": "synthetic large delta test has no consumer convention asset"}
  ],
  "learning_review": {
    "mistake_checked": "none",
    "lesson_decision": "none",
    "promoted_to": "not_applicable",
    "reason": "unit case did not expose a repeated operational mistake"
  },
  "quality_gates": {
    "reuse_non_duplication": {
      "result": "PASS",
      "evidence": "large delta warning requires explicit rationale in warning_checklist"
    }
  },
  "verification_command": "unit smoke",
  "result": "passed",
  "reuse_discipline": {
    "existing_code_checked": "src",
    "existing_component_checked": "not_applicable: no UI component",
    "existing_pattern_followed": "source module constants for fixture",
    "new_code_reason": "large delta warning fixture",
    "duplicate_risk": "medium, covered by warning checklist",
    "kiss_dry_rationale": "single synthetic file"
  },
  "warning_checklist": {
    "code_without_test_reason": "unit smoke recorded as receipt verification in this unit case"
  }
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "large_delta_reason" <<< "$out"
printf '%s' '{
  "changed_files": ["src/large.ts"],
  "affected_layers": ["Consumer"],
  "scope_evidence": "src/large.ts is within allowed_paths for the large delta test.",
  "context_used": [
    {"source": "src", "reason": "source location", "finding": "consumer code path"}
  ],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "convention", "decision": "not_applicable", "reason": "synthetic large delta test has no consumer convention asset"}
  ],
  "learning_review": {
    "mistake_checked": "none",
    "lesson_decision": "none",
    "promoted_to": "not_applicable",
    "reason": "unit case did not expose a repeated operational mistake"
  },
  "quality_gates": {
    "reuse_non_duplication": {
      "result": "PASS",
      "evidence": "large delta warning has explicit rationale"
    }
  },
  "verification_command": "unit smoke",
  "result": "passed",
  "reuse_discipline": {
    "existing_code_checked": "src",
    "existing_component_checked": "not_applicable: no UI component",
    "existing_pattern_followed": "source module constants for fixture",
    "new_code_reason": "large delta warning fixture",
    "duplicate_risk": "medium, covered by warning checklist",
    "kiss_dry_rationale": "single synthetic file"
  },
  "warning_checklist": {
    "code_without_test_reason": "unit smoke recorded as receipt verification in this unit case",
    "large_delta_reason": "large delta is intentional synthetic test fixture"
  }
}' | python3 "$G" receipt-write | grep -q "deliver receipt recorded"

echo "== E14 receipt paths must stay inside task contract scope =="
W="$(fresh_case e14)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
cat > docs-contract.json <<'JSON'
{
  "task_scope": "docs edit",
  "affected_layers": ["Docs"],
  "allowed_paths": ["README.md"],
  "expected_evidence": ["docs smoke"],
  "out_of_scope_paths": ["package.json"]
}
JSON
python3 "$G" contract-write docs-contract.json >/dev/null
out=$(printf '%s' '{
  "changed_files": ["package.json"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed"
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "receipt changed path is out_of_scope: package.json" <<< "$out"
printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed"
}' | python3 "$G" receipt-write | grep -q "deliver receipt recorded"

echo "== E15 learning review vocabulary is enforced =="
W="$(fresh_case e15)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
mkdir -p src
cat > learning-contract.json <<'JSON'
{
  "task_scope": "learning review receipt",
  "affected_layers": ["Consumer"],
  "allowed_paths": ["src/learning.ts"],
  "expected_evidence": ["unit smoke"],
  "out_of_scope_paths": [],
  "consumer_scope": "consumer source file only",
  "context_evidence": [
    {"source": "src", "reason": "source location", "finding": "consumer code path"}
  ],
  "reuse_evidence": [
    {"asset": "existing source patterns", "decision": "not_applicable", "reason": "synthetic learning receipt test"}
  ],
  "decision_limits": ["Do not promote lessons without a target."],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "convention", "decision": "not_applicable", "reason": "synthetic learning test has no consumer convention asset"}
  ]
}
JSON
python3 "$G" contract-write learning-contract.json >/dev/null
printf 'export const learningValue = 1;\n' > src/learning.ts
printf '%s' '{"tool_input":{"file_path":"src/learning.ts"}}' | python3 "$G" post-edit >/dev/null
python3 "$G" evidence-add "unit smoke" passed >/dev/null
out=$(printf '%s' '{
  "changed_files": ["src/learning.ts"],
  "affected_layers": ["Consumer"],
  "scope_evidence": "src/learning.ts is within allowed_paths for the learning receipt test.",
  "context_used": [
    {"source": "src", "reason": "source location", "finding": "consumer code path"}
  ],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "convention", "decision": "not_applicable", "reason": "synthetic learning test has no consumer convention asset"}
  ],
  "learning_review": {
    "mistake_checked": "none",
    "lesson_decision": "ignored",
    "promoted_to": "not_applicable",
    "reason": "negative enum case"
  },
  "quality_gates": {
    "reuse_non_duplication": {
      "result": "PASS",
      "evidence": "learning review vocabulary is the focus of this unit case"
    }
  },
  "verification_command": "unit smoke",
  "result": "passed",
  "reuse_discipline": {
    "existing_code_checked": "src",
    "existing_component_checked": "not_applicable: no UI component",
    "existing_pattern_followed": "source module fixture",
    "new_code_reason": "learning review vocabulary fixture",
    "duplicate_risk": "low",
    "kiss_dry_rationale": "single synthetic file"
  }
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "learning_review.lesson_decision" <<< "$out"
out=$(printf '%s' '{
  "changed_files": ["src/learning.ts"],
  "affected_layers": ["Consumer"],
  "scope_evidence": "src/learning.ts is within allowed_paths for the learning receipt test.",
  "context_used": [
    {"source": "src", "reason": "source location", "finding": "consumer code path"}
  ],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "convention", "decision": "not_applicable", "reason": "synthetic learning test has no consumer convention asset"}
  ],
  "learning_review": {
    "mistake_checked": "wrong_tool",
    "lesson_decision": "promoted",
    "promoted_to": "not_applicable",
    "reason": "negative promotion target case"
  },
  "quality_gates": {
    "reuse_non_duplication": {
      "result": "PASS",
      "evidence": "learning review vocabulary is the focus of this unit case"
    }
  },
  "verification_command": "unit smoke",
  "result": "passed",
  "reuse_discipline": {
    "existing_code_checked": "src",
    "existing_component_checked": "not_applicable: no UI component",
    "existing_pattern_followed": "source module fixture",
    "new_code_reason": "learning review vocabulary fixture",
    "duplicate_risk": "low",
    "kiss_dry_rationale": "single synthetic file"
  }
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "promotion target" <<< "$out"
out=$(printf '%s' '{
  "changed_files": ["src/learning.ts"],
  "affected_layers": ["Consumer"],
  "scope_evidence": "src/learning.ts is within allowed_paths for the learning receipt test.",
  "context_used": [
    {"source": "src", "reason": "source location", "finding": "consumer code path"}
  ],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "convention", "decision": "not_applicable", "reason": "synthetic learning test has no consumer convention asset"}
  ],
  "learning_review": {
    "mistake_checked": "wrong_tool",
    "lesson_decision": "none",
    "promoted_to": "not_applicable",
    "reason": "negative contradiction case"
  },
  "quality_gates": {
    "reuse_non_duplication": {
      "result": "PASS",
      "evidence": "learning review vocabulary is the focus of this unit case"
    }
  },
  "verification_command": "unit smoke",
  "result": "passed",
  "reuse_discipline": {
    "existing_code_checked": "src",
    "existing_component_checked": "not_applicable: no UI component",
    "existing_pattern_followed": "source module fixture",
    "new_code_reason": "learning review vocabulary fixture",
    "duplicate_risk": "low",
    "kiss_dry_rationale": "single synthetic file"
  }
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "mistake_checked is not none" <<< "$out"
out=$(printf '%s' '{
  "changed_files": ["src/learning.ts"],
  "affected_layers": ["Consumer"],
  "scope_evidence": "src/learning.ts is within allowed_paths for the learning receipt test.",
  "context_used": [
    {"source": "src", "reason": "source location", "finding": "consumer code path"}
  ],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "convention", "decision": "not_applicable", "reason": "synthetic learning test has no consumer convention asset"}
  ],
  "learning_review": {
    "mistake_checked": "none",
    "lesson_decision": "recorded",
    "promoted_to": "not_applicable",
    "reason": "negative no-mistake action case"
  },
  "quality_gates": {
    "reuse_non_duplication": {
      "result": "PASS",
      "evidence": "learning review vocabulary is the focus of this unit case"
    }
  },
  "verification_command": "unit smoke",
  "result": "passed",
  "reuse_discipline": {
    "existing_code_checked": "src",
    "existing_component_checked": "not_applicable: no UI component",
    "existing_pattern_followed": "source module fixture",
    "new_code_reason": "learning review vocabulary fixture",
    "duplicate_risk": "low",
    "kiss_dry_rationale": "single synthetic file"
  }
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "mistake_checked is none" <<< "$out"
printf '%s' '{
  "changed_files": ["src/learning.ts"],
  "affected_layers": ["Consumer"],
  "scope_evidence": "src/learning.ts is within allowed_paths for the learning receipt test.",
  "context_used": [
    {"source": "src", "reason": "source location", "finding": "consumer code path"}
  ],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "convention", "decision": "not_applicable", "reason": "synthetic learning test has no consumer convention asset"}
  ],
  "learning_review": {
    "mistake_checked": "wrong_tool",
    "lesson_decision": "promoted",
    "promoted_to": "tools/index.md",
    "reason": "valid promotion target vocabulary"
  },
  "quality_gates": {
    "reuse_non_duplication": {
      "result": "PASS",
      "evidence": "learning review vocabulary is the focus of this unit case"
    }
  },
  "verification_command": "unit smoke",
  "result": "passed",
  "reuse_discipline": {
    "existing_code_checked": "src",
    "existing_component_checked": "not_applicable: no UI component",
    "existing_pattern_followed": "source module fixture",
    "new_code_reason": "learning review vocabulary fixture",
    "duplicate_risk": "low",
    "kiss_dry_rationale": "single synthetic file"
  }
}' | python3 "$G" receipt-write | grep -q "deliver receipt recorded"

echo "== E16 contract evidence vocabularies are enforced =="
W="$(fresh_case e16)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
mkdir -p src/components
out=$(printf '%s' '{
  "task_scope": "invalid vocabulary contract",
  "affected_layers": ["Consumer"],
  "allowed_paths": ["src/foo.ts"],
  "expected_evidence": ["unit smoke"],
  "out_of_scope_paths": [],
  "consumer_scope": "consumer source file only",
  "context_evidence": [
    {"source": "src", "reason": "source location", "finding": "consumer source path"}
  ],
  "reuse_evidence": [
    {"asset": "existing source patterns", "decision": "maybe", "reason": "negative vocabulary case"}
  ],
  "decision_limits": ["Do not accept unknown evidence vocabulary."],
  "consumer_asset_routing": [
    {"task_signal": "mystery-signal", "asset_type": "mystery", "decision": "maybe", "reason": "negative vocabulary case"}
  ]
}' | python3 "$G" contract-write)
grep -q "contract_rejected" <<< "$out"
grep -q "reuse_evidence\\[0\\].decision" <<< "$out"
grep -q "consumer_asset_routing\\[0\\].task_signal" <<< "$out"
grep -q "consumer_asset_routing\\[0\\].asset_type" <<< "$out"
grep -q "consumer_asset_routing\\[0\\].decision" <<< "$out"
out=$(printf '%s' '{
  "task_scope": "invalid UI vocabulary contract",
  "affected_layers": ["Consumer"],
  "allowed_paths": ["src/components/Foo.tsx"],
  "expected_evidence": ["visual smoke"],
  "out_of_scope_paths": [],
  "consumer_scope": "consumer UI component only",
  "context_evidence": [
    {"source": "src/components", "reason": "component location", "finding": "UI component path"}
  ],
  "reuse_evidence": [
    {"asset": "design-system catalog", "decision": "not_enough", "reason": "synthetic component gap"}
  ],
  "decision_limits": ["Do not invent tokens outside DS."],
  "consumer_asset_routing": [
    {"task_signal": "UI/component", "asset_type": "design-system", "decision": "loaded", "reason": "UI component edit requires DS"}
  ],
  "ui_design_system_evidence": [
    {"source": "design-system catalog", "checked": "component gap", "decision": "copy", "reason": "negative vocabulary case"}
  ]
}' | python3 "$G" contract-write)
grep -q "contract_rejected" <<< "$out"
grep -q "ui_design_system_evidence\\[0\\].decision" <<< "$out"
printf '%s' '{
  "task_scope": "valid UI vocabulary contract",
  "affected_layers": ["Consumer"],
  "allowed_paths": ["src/components/Foo.tsx"],
  "expected_evidence": ["visual smoke"],
  "out_of_scope_paths": [],
  "consumer_scope": "consumer UI component only",
  "context_evidence": [
    {"source": "src/components", "reason": "component location", "finding": "UI component path"}
  ],
  "reuse_evidence": [
    {"asset": "design-system catalog", "decision": "not_enough", "reason": "synthetic component gap"}
  ],
  "decision_limits": ["Do not invent tokens outside DS."],
  "consumer_asset_routing": [
    {"task_signal": "UI/component", "asset_type": "design-system", "decision": "loaded", "reason": "UI component edit requires DS"}
  ],
  "ui_design_system_evidence": [
    {"source": "design-system catalog", "checked": "component gap", "decision": "new", "reason": "existing component gap is explicit"}
  ]
}' | python3 "$G" contract-write | grep -q "task contract recorded"

echo "== E17 log-append lesson promotion target vocabulary is enforced =="
W="$(fresh_case e17)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
before=$(wc -l < pilothOS/memory/lessons-learned.md)
out=$(python3 "$G" log-append lesson "Wrong tool" "Route tool behavior through tools index" "maybe")
grep -q "FAIL log-append lesson: PromotedTo" <<< "$out"
after=$(wc -l < pilothOS/memory/lessons-learned.md)
[ "$after" = "$before" ]
python3 "$G" log-append lesson "Wrong tool" "Route tool behavior through tools index" "tools/index.md, upstream" | grep -q "da append"
grep -q "| Wrong tool | Route tool behavior through tools index | tools/index.md, upstream |" pilothOS/memory/lessons-learned.md

echo "== E18 receipt template is gate-aware and vocabulary stays in sync =="
W="$(fresh_case e18)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
mkdir -p src/components
printf 'export const Widget = () => null;\n' > src/components/Widget.tsx
printf '%s' '{"tool_input":{"file_path":"src/components/Widget.tsx"}}' | python3 "$G" post-edit >/dev/null
# A UI run emits the reuse + UI fields, with allowed vocab derived from the
# constants (in _allowed_values) so template and enums cannot drift.
out=$(python3 "$G" receipt-template)
for needle in '"design_system_checked"' '"consumer_asset_routing"' \
  design-system build-runner ignored_consumer_asset duplicated_component \
  bypassed_design_system tools/index.md upstream; do
  grep -q "$needle" <<< "$out" || { echo "E18 missing: $needle"; exit 1; }
done

echo "== E19 route-task suggests scheduler routing from consumer assets =="
W="$(fresh_case e19)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
mkdir -p .claude/skills/design-system src/components
printf '# Design skill\n' > .claude/skills/design-system/SKILL.md
cat > package.json <<'JSON'
{
  "scripts": {
    "test": "vitest run",
    "deploy": "vercel --prod"
  }
}
JSON
out=$(python3 "$G" route-task '{"task_signal":"UI/component"}')
grep -q '"result": "route_suggested"' <<< "$out"
grep -q '"task_signal": "UI/component"' <<< "$out"
grep -q '"asset": ".claude/skills/design-system"' <<< "$out"
grep -q '"asset": "src/components"' <<< "$out"
grep -q '"context_evidence"' <<< "$out"
grep -q '"source": ".claude/skills/design-system"' <<< "$out"
grep -q '"skipped_assets"' <<< "$out"
grep -q '"asset": "package.json:scripts.deploy"' <<< "$out"
grep -q '"reason": "command is not routed for UI/component"' <<< "$out"
grep -q '"consumer_asset_routing"' <<< "$out"
out=$(python3 "$G" route-task '{"task_signal":"release/deploy"}')
grep -q '"load_policy": "approval-required"' <<< "$out"
grep -q '"asset": "package.json:scripts.deploy"' <<< "$out"
grep -q '"decision": "approval_required"' <<< "$out"
out=$(python3 "$G" route-task '{"task_signal":"unknown"}')
grep -q '"result": "route_rejected"' <<< "$out"
out=$(python3 "$G" route-task not-json)
grep -q '"result": "route_rejected"' <<< "$out"

echo "== E20 docs/test exemption is path-aware =="
W="$(fresh_case e20)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
mkdir -p src docs tests
cat > mismatched-doc-code.json <<'JSON'
{
  "task_scope": "mismatched docs claim",
  "affected_layers": ["Docs"],
  "allowed_paths": ["src/foo.ts"],
  "expected_evidence": ["docs smoke"],
  "out_of_scope_paths": []
}
JSON
out=$(python3 "$G" contract-write mismatched-doc-code.json)
grep -q "contract_rejected" <<< "$out"
grep -q "consumer_scope" <<< "$out"
out=$(printf '%s' '{"tool_input":{"file_path":"src/foo.ts"}}' | env PILOTHOS_TASK_CONTRACT="$PWD/mismatched-doc-code.json" python3 "$G" pre-edit)
grep -q '"decision": "block"' <<< "$out"
grep -q "consumer_scope" <<< "$out"
cat > valid-doc-paths.json <<'JSON'
{
  "task_scope": "docs edit",
  "affected_layers": ["Docs"],
  "allowed_paths": ["docs/guide.md", "README.md"],
  "expected_evidence": ["docs smoke"],
  "out_of_scope_paths": []
}
JSON
python3 "$G" contract-write valid-doc-paths.json >/dev/null
cat > valid-test-paths.json <<'JSON'
{
  "task_scope": "test edit",
  "affected_layers": ["Tests"],
  "allowed_paths": ["tests/evaluation/run-tests.sh"],
  "expected_evidence": ["bash tests/evaluation/run-tests.sh"],
  "out_of_scope_paths": []
}
JSON
python3 "$G" contract-write valid-test-paths.json >/dev/null

echo "== E21 post-edit emits expanded diff facts =="
W="$(fresh_case e21)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
mkdir -p src/components tests docs
cat > diff-facts-contract.json <<'JSON'
{
  "task_scope": "diff facts classification",
  "affected_layers": ["Consumer", "Tests", "Docs"],
  "allowed_paths": [".gitignore", "package.json", "src/components/FactsButton.tsx", "tests/facts.test.ts", "docs/facts.md"],
  "expected_evidence": ["diff facts smoke"],
  "out_of_scope_paths": [],
  "consumer_scope": "synthetic diff-facts paths only",
  "context_evidence": [
    {"source": ".gitignore", "reason": "dotfile classification", "finding": "dotfile path should stay intact"},
    {"source": "package.json", "reason": "dependency classification", "finding": "dependency file path"},
    {"source": "src/components", "reason": "UI classification", "finding": "component path"},
    {"source": "tests", "reason": "test classification", "finding": "test path"},
    {"source": "docs", "reason": "docs classification", "finding": "docs path"}
  ],
  "reuse_evidence": [
    {"asset": "existing diff facts classifier", "decision": "reuse", "reason": "extend current post-edit output only"}
  ],
  "decision_limits": ["Do not add semantic file classification."],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "test-runner", "decision": "not_applicable", "reason": "classification fixture does not route an actual runner"}
  ],
  "ui_design_system_evidence": [
    {"source": "component catalog", "checked": "component path classification", "decision": "not_applicable", "reason": "synthetic diff-facts UI fixture"}
  ]
}
JSON
python3 "$G" contract-write diff-facts-contract.json >/dev/null
printf 'local-state\n' >> .gitignore
printf '{"name":"diff-facts"}\n' > package.json
printf 'export function FactsButton() { return <button>Facts</button>; }\n' > src/components/FactsButton.tsx
printf 'test("facts", () => {});\n' > tests/facts.test.ts
printf '# Facts\n' > docs/facts.md
out=$(printf '%s' '{"tool_input":{"files":[".gitignore","package.json","src/components/FactsButton.tsx","tests/facts.test.ts","docs/facts.md"]}}' | python3 "$G" post-edit)
grep -q '"new_files_count"' <<< "$out"
grep -q '"total_added"' <<< "$out"
grep -q '"total_deleted"' <<< "$out"
grep -q '"largest_file_delta"' <<< "$out"
grep -Fq '"dependency_files_changed": ["package.json"]' <<< "$out"
grep -Fq '"ui_files_changed": ["src/components/FactsButton.tsx"]' <<< "$out"
grep -Fq '"test_files_changed": ["tests/facts.test.ts"]' <<< "$out"
grep -Fq '"docs_files_changed": ["docs/facts.md"]' <<< "$out"
grep -Fq '"component_like_files_changed": ["src/components/FactsButton.tsx"]' <<< "$out"
grep -q '".gitignore"' <<< "$out"

echo "== E22 self-host check verifies dogfood docs/tests/manifest =="
W="$(fresh_case e22)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
out=$(python3 "$G" self-host-check)
grep -q '"result": "self_host_check_passed"' <<< "$out"
grep -q 'guard mode route-task' <<< "$out"
grep -q 'guard mode scheduler-record' <<< "$out"
grep -q 'guard mode team-receipt-write' <<< "$out"
rm pilothOS/runtime/self-hosting.md
out=$(python3 "$G" self-host-check)
grep -q '"result": "self_host_check_failed"' <<< "$out"
grep -q "self-hosting.md" <<< "$out"

echo "== E23 asset scan, health, and sync preserve manual notes =="
W="$(fresh_case e23)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
cat > package.json <<'JSON'
{
  "scripts": {
    "test": "vitest run",
    "deploy": "vercel --prod"
  }
}
JSON
python3 "$G" asset-scan --format json > scan.json
grep -q '"result": "asset_scan"' scan.json
grep -q '"detected_at": "repository-scan"' scan.json
python3 "$G" asset-scan --format md > scan.md
grep -q "Detected At" scan.md
grep -q "Confidence" scan.md
out=$(python3 "$G" asset-health package.json:scripts.deploy)
grep -q '"status": "needs_approval"' <<< "$out"
out=$(env PILOTHOS_APPROVAL_EVIDENCE="user approved high-risk health check" python3 "$G" asset-health package.json:scripts.deploy)
grep -q '"status": "healthy"' <<< "$out"
printf '\nMANUAL-NOTE: preserve me\n' >> pilothOS/runtime/consumer-assets.md
out=$(python3 "$G" asset-sync --source scan.json)
grep -q '"result": "asset_synced"' <<< "$out"
grep -q '"preserved_manual_sections": true' <<< "$out"
grep -q "PILOTHOS-GENERATED-ASSETS:START" pilothOS/runtime/consumer-assets.md
grep -q "PILOTHOS-GENERATED-ASSETS:END" pilothOS/runtime/consumer-assets.md
grep -q "MANUAL-NOTE: preserve me" pilothOS/runtime/consumer-assets.md

echo "== E24 reuse-scan and ds-scan require explicit receipt decisions =="
W="$(fresh_case e24)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
mkdir -p src/helpers src/components src/tokens
cat > src/helpers/date-helper.ts <<'TS'
export function formatDateHelper(value: Date) {
  return value.toISOString()
}
TS
cat > src/new-date-helper.ts <<'TS'
export function newDateHelper(value: Date) {
  return value.toISOString()
}
TS
cat > reuse-request.json <<'JSON'
{
  "task_signal": "tool/MCP",
  "changed_paths": ["src/new-date-helper.ts"],
  "allowed_paths": ["src/**"]
}
JSON
out=$(python3 "$G" reuse-scan reuse-request.json)
grep -q '"result": "reuse_scan"' <<< "$out"
grep -q '"high_confidence_candidates"' <<< "$out"
grep -q 'src/helpers/date-helper.ts' <<< "$out"
cat > src/components/Button.tsx <<'TSX'
export function Button() {
  return <button />
}
TSX
cat > src/tokens/colors.css <<'CSS'
:root { --color-brand: #234567; }
CSS
cat > ds-request.json <<'JSON'
{
  "task_signal": "UI/component",
  "changed_paths": ["src/components/NewButton.tsx"],
  "allowed_paths": ["src/**"]
}
JSON
out=$(python3 "$G" ds-scan ds-request.json)
grep -q '"result": "ds_scan"' <<< "$out"
grep -q '"component_candidates"' <<< "$out"
grep -q '"token_candidates"' <<< "$out"
cat > reuse-contract.json <<'JSON'
{
  "task_scope": "semantic reuse receipt",
  "affected_layers": ["Consumer"],
  "allowed_paths": ["src/new-date-helper.ts"],
  "expected_evidence": ["unit smoke"],
  "out_of_scope_paths": [],
  "consumer_scope": "synthetic helper fixture only",
  "context_evidence": [
    {"source": "src/helpers/date-helper.ts", "reason": "existing helper", "finding": "date helper candidate"}
  ],
  "reuse_evidence": [
    {"asset": "src/helpers/date-helper.ts", "decision": "reuse", "reason": "existing helper checked before adding new helper"}
  ],
  "decision_limits": ["Do not add duplicate helpers without review."],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "convention", "decision": "not_applicable", "reason": "synthetic helper fixture has no convention asset"}
  ]
}
JSON
python3 "$G" contract-write reuse-contract.json >/dev/null
printf '%s' '{"tool_input":{"file_path":"src/new-date-helper.ts"}}' | python3 "$G" post-edit >/dev/null
python3 "$G" evidence-add "unit smoke" passed >/dev/null
out=$(printf '%s' '{
  "changed_files": ["src/new-date-helper.ts"],
  "affected_layers": ["Consumer"],
  "scope_evidence": "src/new-date-helper.ts is within allowed_paths.",
  "context_used": [
    {"source": "src/helpers/date-helper.ts", "reason": "existing helper", "finding": "candidate helper exists"}
  ],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "convention", "decision": "not_applicable", "reason": "synthetic helper fixture has no convention asset"}
  ],
  "learning_review": {
    "mistake_checked": "none",
    "lesson_decision": "none",
    "promoted_to": "not_applicable",
    "reason": "unit case did not expose a repeated operational mistake"
  },
  "quality_gates": {
    "reuse_non_duplication": {
      "result": "PASS",
      "evidence": "reuse-scan candidate is present"
    }
  },
  "semantic_reuse_candidates": [
    {"id": "reuse:src-helpers-date-helper-ts", "path": "src/helpers/date-helper.ts", "confidence": 0.9, "reason": "helper candidate"}
  ],
  "verification_command": "unit smoke",
  "result": "passed",
  "reuse_discipline": {
    "existing_code_checked": "src/helpers/date-helper.ts",
    "existing_component_checked": "not_applicable: no UI component",
    "existing_pattern_followed": "date helper fixture",
    "new_code_reason": "semantic review negative case",
    "duplicate_risk": "medium until semantic review is recorded",
    "kiss_dry_rationale": "single helper fixture"
  }
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "semantic_reuse_review" <<< "$out"
printf '%s' '{
  "changed_files": ["src/new-date-helper.ts"],
  "affected_layers": ["Consumer"],
  "scope_evidence": "src/new-date-helper.ts is within allowed_paths.",
  "context_used": [
    {"source": "src/helpers/date-helper.ts", "reason": "existing helper", "finding": "candidate helper exists"}
  ],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "convention", "decision": "not_applicable", "reason": "synthetic helper fixture has no convention asset"}
  ],
  "learning_review": {
    "mistake_checked": "none",
    "lesson_decision": "none",
    "promoted_to": "not_applicable",
    "reason": "unit case did not expose a repeated operational mistake"
  },
  "quality_gates": {
    "reuse_non_duplication": {
      "result": "PASS",
      "evidence": "semantic reuse review recorded"
    }
  },
  "semantic_reuse_candidates": [
    {"id": "reuse:src-helpers-date-helper-ts", "path": "src/helpers/date-helper.ts", "confidence": 0.9, "reason": "helper candidate"}
  ],
  "semantic_reuse_review": [
    {"candidate": "reuse:src-helpers-date-helper-ts", "decision": "reuse", "reason": "existing helper candidate was reviewed"}
  ],
  "verification_command": "unit smoke",
  "result": "passed",
  "reuse_discipline": {
    "existing_code_checked": "src/helpers/date-helper.ts",
    "existing_component_checked": "not_applicable: no UI component",
    "existing_pattern_followed": "date helper fixture",
    "new_code_reason": "semantic review positive case",
    "duplicate_risk": "low after semantic review",
    "kiss_dry_rationale": "single helper fixture"
  }
}' | python3 "$G" receipt-write | grep -q "deliver receipt recorded"

echo "== E25 scheduler suggests targeted suites and falls back on corrupt state =="
W="$(fresh_case e25)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
out=$(python3 "$G" scheduler-suggest '{"task_signal":"tool/MCP","affected_paths":["pilothOS/scripts/pilothos_guard.py"],"intent":"guard policy"}')
grep -q '"result": "scheduler_suggested"' <<< "$out"
grep -q 'tests/evaluation/run-tests.sh' <<< "$out"
mkdir -p .claude-plugin scripts
printf '{"version":"0.0.0"}\n' > .claude-plugin/plugin.json
printf 'print("stage")\n' > scripts/stage.py
printf 'print("manifest")\n' > scripts/build_manifest.py
out=$(python3 "$G" scheduler-suggest '{"task_signal":"tool/MCP","affected_paths":["scripts/stage.py"],"intent":"installer"}')
grep -q 'tests/install/run-tests.sh' <<< "$out"
out=$(python3 "$G" scheduler-suggest '{"task_signal":"not_applicable","affected_paths":["docs/workflow.md"],"intent":"docs"}')
grep -q 'tests/docs/run-tests.sh' <<< "$out"
mkdir -p pilothOS/memory/state
printf 'not-json\n' > pilothOS/memory/state/scheduler-history.jsonl
out=$(python3 "$G" scheduler-suggest '{"task_signal":"bug fix","affected_paths":["src/foo.ts"],"intent":"corrupt history fallback"}')
grep -q '"history_status": "fallback_corrupt_state"' <<< "$out"
grep -q '"fallback_used": true' <<< "$out"
python3 "$G" scheduler-record '{"task_signal":"bug fix","affected_layers":["Consumer"],"verification_command":"unit smoke","result":"passed"}' >/dev/null
tail -1 pilothOS/memory/state/scheduler-history.jsonl | grep -q '"repo_key"'

echo "== E26 team contract, role permissions, QA verdict, and repair loop gates =="
W="$(fresh_case e26)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
out=$(printf '%s' '{
  "task_id": "team-negative",
  "team": "piloth-team",
  "allowed_paths": ["README.md"],
  "role_permissions": {},
  "handoff_artifacts": ["pilothOS/memory/state/team-runs/team-negative/**"],
  "max_repair_loops": 1,
  "expected_evidence": ["team receipt"]
}' | python3 "$G" team-contract-write)
grep -q "team_contract_rejected" <<< "$out"
grep -q "roles" <<< "$out"
grep -q "stop_condition" <<< "$out"
printf '%s' '{
  "task_scope": "team edit fixture",
  "affected_layers": ["Docs"],
  "allowed_paths": ["README.md"],
  "expected_evidence": ["docs smoke"],
  "out_of_scope_paths": []
}' | python3 "$G" contract-write >/dev/null
cat > team-contract.json <<'JSON'
{
  "task_id": "team-positive",
  "team": "piloth-team",
  "roles": ["lead", "executor", "reviewer", "qa"],
  "allowed_paths": ["README.md"],
  "role_permissions": {
    "lead": ["plan", "review"],
    "executor": ["edit"],
    "reviewer": ["review"],
    "qa": ["qa"]
  },
  "handoff_artifacts": ["pilothOS/memory/state/team-runs/team-positive/**"],
  "stop_condition": "QA PASS or documented FAIL with lead final decision",
  "max_repair_loops": 1,
  "expected_evidence": ["team receipt", "final V1 receipt"]
}
JSON
python3 "$G" team-contract-write team-contract.json | grep -q "team_contract_recorded"
out=$(printf '%s' '{"role":"reviewer","tool_input":{"file_path":"README.md"}}' | python3 "$G" pre-edit)
grep -q '"decision": "block"' <<< "$out"
grep -q "does not have edit permission" <<< "$out"
out=$(printf '%s' '{"role":"executor","tool_input":{"file_path":"package.json"}}' | python3 "$G" pre-edit)
grep -q '"decision": "block"' <<< "$out"
grep -q "team allowed_paths" <<< "$out"
[ -z "$(printf '%s' '{"tool_input":{"file_path":"README.md"}}' | python3 "$G" pre-edit)" ]
out=$(printf '%s' '{
  "task_id": "team-positive",
  "team": "piloth-team",
  "role_outputs": [
    {"role": "lead", "output": "plan", "evidence": "contract"},
    {"role": "executor", "output": "edit", "evidence": "diff"},
    {"role": "qa", "output": "qa", "evidence": "tests"}
  ],
  "handoff_paths": ["pilothOS/memory/state/team-runs/team-positive/qa.md"],
  "repair_loop_count": 0,
  "final_lead_decision": "ship after QA"
}' | python3 "$G" team-receipt-write)
grep -q "team_receipt_rejected" <<< "$out"
grep -q "qa_verdict" <<< "$out"
out=$(printf '%s' '{
  "task_id": "team-positive",
  "team": "piloth-team",
  "role_outputs": [
    {"role": "lead", "output": "plan", "evidence": "contract"},
    {"role": "executor", "output": "edit", "evidence": "diff"},
    {"role": "qa", "output": "qa", "evidence": "tests"}
  ],
  "handoff_paths": ["pilothOS/memory/state/team-runs/team-positive/qa.md"],
  "repair_loop_count": 2,
  "qa_verdict": {"result": "PASS", "evidence": "qa smoke"},
  "final_lead_decision": "ship after QA"
}' | python3 "$G" team-receipt-write)
grep -q "team_receipt_rejected" <<< "$out"
grep -q "repair_loop_count exceeds max_repair_loops" <<< "$out"
printf '%s' '{
  "task_id": "team-positive",
  "team": "piloth-team",
  "role_outputs": [
    {"role": "lead", "output": "plan", "evidence": "contract"},
    {"role": "executor", "output": "edit", "evidence": "diff"},
    {"role": "reviewer", "output": "review", "evidence": "findings"},
    {"role": "qa", "output": "qa", "evidence": "tests"}
  ],
  "handoff_paths": ["pilothOS/memory/state/team-runs/team-positive/qa.md"],
  "repair_loop_count": 1,
  "qa_verdict": {"result": "PASS", "evidence": "qa smoke"},
  "final_lead_decision": "ship after QA"
}' | python3 "$G" team-receipt-write | grep -q "team_receipt_recorded"

echo "== E27 asset scan exposes signals and manifest health metadata =="
W="$(fresh_case e27)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
cat > package.json <<'JSON'
{
  "scripts": {
    "test": "vitest run"
  }
}
JSON
out=$(python3 "$G" asset-scan --format json)
grep -q '"detected_signals"' <<< "$out"
grep -q '"package-script"' <<< "$out"
grep -q '"piloth-owned"' <<< "$out"
out=$(python3 "$G" asset-health pilothOS/runtime)
grep -q '"manifest_status": "indexed"' <<< "$out"
grep -q '"status": "healthy"' <<< "$out"

echo "== E28 reuse-scan includes imports and nearby evidence =="
W="$(fresh_case e28)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
mkdir -p src
cat > src/format-helper.ts <<'TS'
export function formatCurrencyHelper(value: number) {
  return String(value)
}
TS
cat > src/format-helper.test.ts <<'TS'
import { formatCurrencyHelper } from "./format-helper"
TS
cat > src/new-format-helper.ts <<'TS'
import { formatCurrencyHelper } from "./format-helper"
export function newFormatHelper(value: number) {
  return formatCurrencyHelper(value)
}
TS
out=$(python3 "$G" reuse-scan '{
  "task_signal": "bug fix",
  "changed_paths": ["src/new-format-helper.ts"],
  "allowed_paths": ["src/**"]
}')
grep -q '"imports"' <<< "$out"
grep -q '"nearby_evidence"' <<< "$out"
grep -q 'src/format-helper.test.ts' <<< "$out"

echo "== E29 scheduler applies successful local history =="
W="$(fresh_case e29)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
python3 "$G" scheduler-record '{
  "task_signal": "bug fix",
  "affected_layers": ["Consumer"],
  "changed_files": ["src/foo.ts"],
  "verification_command": "custom smoke",
  "result": "passed",
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "test-runner", "decision": "loaded", "reason": "history runner"}
  ],
  "learning_review": {
    "lesson_decision": "recorded"
  }
}' >/dev/null
out=$(python3 "$G" scheduler-suggest '{
  "task_signal": "bug fix",
  "affected_paths": ["src/bar.ts"],
  "intent": "history reuse"
}')
grep -q '"history_status": "loaded"' <<< "$out"
grep -q '"history_applied": true' <<< "$out"
grep -q '"custom smoke"' <<< "$out"
grep -q 'history learning decision: recorded' <<< "$out"

echo "== E29b scheduler ignores deprecated host-level history =="
W="$(fresh_case e29b)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
python3 "$G" scheduler-record '{
  "task_signal": "tool/MCP",
  "affected_layers": ["Tools/Runtime"],
  "changed_files": ["pilothOS/scripts/pilothos_hostd.py"],
  "verification_command": "host authority smoke",
  "result": "passed",
  "consumer_asset_routing": [
    {"task_signal": "tool/MCP", "asset_type": "tool", "decision": "loaded", "reason": "host authority"}
  ],
  "learning_review": {
    "lesson_decision": "recorded"
  }
}' >/dev/null
out=$(python3 "$G" scheduler-suggest '{
  "task_signal": "tool/MCP",
  "affected_paths": ["pilothOS/scripts/pilothos_guard.py"],
  "intent": "project-local OS guard"
}')
grep -q '"history_status": "loaded"' <<< "$out"
grep -q '"history_applied": false' <<< "$out"
! grep -q 'host authority smoke' <<< "$out"
python3 "$G" scheduler-record '{
  "affected_layers": ["Tools/Runtime", "Runtime"],
  "changed_files": ["pilothOS/scripts/pilothos_hostd.py", "pilothOS/scripts/pilothos_guard.py"],
  "verification_command": "state doctor smoke",
  "result": "passed",
  "consumer_asset_routing": [
    {"task_signal": "tool/MCP", "asset_type": "tool", "decision": "loaded", "reason": "guard owns state-doctor"}
  ],
  "learning_review": {
    "lesson_decision": "recorded"
  }
}' >/dev/null
out=$(python3 "$G" scheduler-suggest '{
  "task_signal": "tool/MCP",
  "affected_paths": ["pilothOS/scripts/pilothos_guard.py"],
  "intent": "project-local OS guard"
}')
grep -q '"history_applied": true' <<< "$out"
grep -q 'state doctor smoke' <<< "$out"
! grep -q 'pilothos_hostd.py' <<< "$out"

echo "== E30 team receipt materializes artifacts and enforces edited_paths =="
W="$(fresh_case e30)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
printf '%s' '{
  "task_scope": "team artifact fixture",
  "affected_layers": ["Docs"],
  "allowed_paths": ["README.md"],
  "expected_evidence": ["docs smoke"],
  "out_of_scope_paths": []
}' | python3 "$G" contract-write >/dev/null
cat > team-contract.json <<'JSON'
{
  "task_id": "team-artifact",
  "team": "piloth-team",
  "roles": ["lead", "executor", "reviewer", "qa"],
  "allowed_paths": ["README.md"],
  "role_permissions": {
    "lead": ["plan", "review"],
    "executor": ["edit"],
    "reviewer": ["review"],
    "qa": ["qa"]
  },
  "handoff_artifacts": ["pilothOS/memory/state/team-runs/team-artifact/**"],
  "stop_condition": "QA PASS or documented FAIL with lead final decision",
  "max_repair_loops": 1,
  "expected_evidence": ["team receipt", "final V1 receipt"]
}
JSON
python3 "$G" team-contract-write team-contract.json >/dev/null
out=$(printf '%s' '{
  "task_id": "team-artifact",
  "team": "piloth-team",
  "role_outputs": [
    {"role": "reviewer", "output": "review", "evidence": "finding", "edited_paths": ["README.md"]}
  ],
  "handoff_paths": ["pilothOS/memory/state/team-runs/team-artifact/reviewer.md"],
  "repair_loop_count": 0,
  "qa_verdict": {"result": "PASS", "evidence": "qa smoke"},
  "final_lead_decision": "reject reviewer edit"
}' | python3 "$G" team-receipt-write)
grep -q "team_receipt_rejected" <<< "$out"
grep -q "edited_paths not allowed" <<< "$out"
out=$(printf '%s' '{
  "task_id": "team-artifact",
  "team": "piloth-team",
  "role_outputs": [
    {"role": "lead", "output": "plan", "evidence": "contract"},
    {"role": "executor", "output": "edit", "evidence": "diff", "edited_paths": ["README.md"]},
    {"role": "reviewer", "output": "review", "evidence": "no blockers"},
    {"role": "qa", "output": "qa", "evidence": "tests"}
  ],
  "handoff_paths": ["pilothOS/memory/state/team-runs/team-artifact/qa.md"],
  "repair_loop_count": 0,
  "qa_verdict": {"result": "PASS", "evidence": "qa smoke"},
  "final_lead_decision": "ship after QA"
}' | python3 "$G" team-receipt-write)
grep -q "team_receipt_recorded" <<< "$out"
grep -q "generated_artifacts" pilothOS/memory/state/team-runs/team-artifact/team-receipt.json
[ -f pilothOS/memory/state/team-runs/team-artifact/role-executor.md ]
[ -f pilothOS/memory/state/team-runs/team-artifact/qa-verdict.md ]
[ -f pilothOS/memory/state/team-runs/team-artifact/final-lead-decision.md ]

echo "== E31 dynamic asset discovery and JSON errors for new modes =="
W="$(fresh_case e31)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
mkdir -p .agents/skills/release-check .codex/commands scripts
printf '# Release check skill\n' > .agents/skills/release-check/SKILL.md
printf '# Ship command\n' > .codex/commands/ship.md
printf '#!/usr/bin/env bash\nexit 0\n' > scripts/custom-test.sh
printf '#!/usr/bin/env bash\nexit 0\n' > scripts/deploy-prod.sh
chmod +x scripts/custom-test.sh scripts/deploy-prod.sh
out=$(python3 "$G" asset-scan --format json)
grep -q '.agents/skills/release-check' <<< "$out"
grep -q '.codex/commands/ship.md' <<< "$out"
grep -q 'scripts/custom-test.sh' <<< "$out"
grep -q 'scripts/deploy-prod.sh' <<< "$out"
grep -q '"risk": "high"' <<< "$out"
out=$(python3 "$G" asset-scan --format nope)
grep -q '"result": "asset_scan_rejected"' <<< "$out"
out=$(python3 "$G" asset-sync)
grep -q '"result": "asset_sync_rejected"' <<< "$out"

echo "== E32 reuse-scan emits repeated duplicate learning suggestions =="
W="$(fresh_case e32)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
mkdir -p src
cat > src/format-helper.ts <<'TS'
export function formatCurrencyHelper(value: number) {
  return String(value)
}
TS
cat > src/new-format-helper.ts <<'TS'
import { formatCurrencyHelper } from "./format-helper"
export function newFormatHelper(value: number) {
  return formatCurrencyHelper(value)
}
TS
python3 "$G" scheduler-record '{
  "task_signal": "bug fix",
  "affected_layers": ["Consumer"],
  "changed_files": ["src/new-format-helper.ts"],
  "verification_command": "unit smoke",
  "result": "passed",
  "semantic_reuse_candidates": [
    {"id": "reuse:src-format-helper-ts", "path": "src/format-helper.ts", "confidence": 0.9, "reason": "helper candidate"}
  ],
  "semantic_reuse_review": [
    {"candidate": "reuse:src-format-helper-ts", "decision": "new", "reason": "synthetic duplicate history"}
  ]
}' >/dev/null
out=$(python3 "$G" reuse-scan '{
  "task_signal": "bug fix",
  "changed_paths": ["src/new-format-helper.ts"],
  "allowed_paths": ["src/**"]
}')
grep -q '"learning_suggestions"' <<< "$out"
grep -q '"repeated": true' <<< "$out"
grep -q '"mistake_checked": "duplicated_helper"' <<< "$out"
grep -q '"lesson_decision": "recorded"' <<< "$out"

echo "== E33 installer layer is first-class for scheduler and edit facts =="
W="$(fresh_case e33)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
mkdir -p .claude-plugin scripts
printf '{"version":"0.0.0"}\n' > .claude-plugin/plugin.json
printf 'print("stage")\n' > scripts/stage.py
printf 'print("manifest")\n' > scripts/build_manifest.py
cat > installer-layer-contract.json <<'JSON'
{
  "task_scope": "installer layer fixture",
  "affected_layers": ["Installer"],
  "allowed_paths": ["scripts/stage.py", "scripts/build_manifest.py"],
  "expected_evidence": ["installer smoke"],
  "out_of_scope_paths": [],
  "consumer_scope": "synthetic installer paths only",
  "context_evidence": [
    {"source": "scripts/stage.py", "reason": "staging owner", "finding": "installer layer path"},
    {"source": "scripts/build_manifest.py", "reason": "manifest owner", "finding": "installer layer path"}
  ],
  "reuse_evidence": [
    {"asset": "existing installer scripts", "decision": "reuse", "reason": "classify existing distribution scripts"}
  ],
  "decision_limits": ["Do not edit runtime guard in this fixture."],
  "consumer_asset_routing": [
    {"task_signal": "release/deploy", "asset_type": "build-runner", "decision": "loaded", "reason": "installer layer fixture routes distribution assets"}
  ],
  "energy_budget_reason": "installer fixture validates full-suite routing shape"
}
JSON
python3 "$G" contract-write installer-layer-contract.json >/dev/null
out=$(printf '%s' '{"tool_input":{"files":["scripts/stage.py","scripts/build_manifest.py"]}}' | python3 "$G" pre-edit)
! grep -q '"decision": "block"' <<< "$out"
out=$(printf '%s' '{"tool_input":{"files":["scripts/stage.py","scripts/build_manifest.py"]}}' | python3 "$G" post-edit)
grep -q '"Installer"' <<< "$out"
out=$(python3 "$G" scheduler-suggest '{"task_signal":"tool/MCP","affected_paths":["scripts/stage.py","scripts/build_manifest.py"],"intent":"installer layer"}')
grep -q '"Installer"' <<< "$out"
grep -q 'tests/install/run-tests.sh' <<< "$out"
python3 "$G" asset-scan --format json > scan.json
python3 - <<'PY'
import json
from pathlib import Path

assets = {item["asset"]: item for item in json.loads(Path("scan.json").read_text())["assets"]}
for rel in ("scripts/stage.py", "scripts/build_manifest.py"):
    item = assets[rel]
    assert item["owner"] == "piloth", item
    assert "piloth-owned" in item["detected_signals"], item
PY

echo "== E34 source-only installer classification does not relabel consumer scripts =="
W="$(fresh_case e34)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
mkdir -p scripts
printf 'print("consumer stage")\n' > scripts/stage.py
cat > consumer-script-contract.json <<'JSON'
{
  "task_scope": "consumer script fixture",
  "affected_layers": ["Consumer"],
  "allowed_paths": ["scripts/stage.py"],
  "expected_evidence": ["consumer script smoke"],
  "out_of_scope_paths": [],
  "consumer_scope": "synthetic consumer script only",
  "context_evidence": [
    {"source": "scripts/stage.py", "reason": "consumer-owned script", "finding": "same name as source installer path"}
  ],
  "reuse_evidence": [
    {"asset": "consumer script", "decision": "reuse", "reason": "fixture keeps consumer ownership"}
  ],
  "decision_limits": ["Do not infer Piloth source installer ownership without source markers."],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "command", "decision": "loaded", "reason": "consumer script is a normal routed asset"}
  ]
}
JSON
python3 "$G" contract-write consumer-script-contract.json >/dev/null
out=$(printf '%s' '{"tool_input":{"files":["scripts/stage.py"]}}' | python3 "$G" post-edit)
! grep -q '"Installer"' <<< "$out"
grep -q '"Consumer"' <<< "$out"
out=$(python3 "$G" scheduler-suggest '{"task_signal":"bug fix","affected_paths":["scripts/stage.py"],"intent":"consumer script"}')
! grep -q '"Installer"' <<< "$out"
python3 "$G" asset-scan --format json > scan.json
python3 - <<'PY'
import json
from pathlib import Path

assets = {item["asset"]: item for item in json.loads(Path("scan.json").read_text())["assets"]}
item = assets["scripts/stage.py"]
assert item["owner"] == "consumer", item
assert "piloth-owned" not in item["detected_signals"], item
PY

echo "== E35 DRY/KISS gate cannot fail on a passed receipt =="
W="$(fresh_case e35)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
mkdir -p src
printf 'export function newHelper() { return 1 }\n' > src/new-helper.ts
cat > dry-kiss-contract.json <<'JSON'
{
  "task_scope": "dry kiss receipt fixture",
  "affected_layers": ["Consumer"],
  "allowed_paths": ["src/new-helper.ts"],
  "expected_evidence": ["unit smoke"],
  "out_of_scope_paths": [],
  "consumer_scope": "synthetic helper fixture only",
  "context_evidence": [
    {"source": "src/new-helper.ts", "reason": "changed helper", "finding": "DRY/KISS gate fixture"}
  ],
  "reuse_evidence": [
    {"asset": "existing helper search", "decision": "reuse", "reason": "receipt must prove non-duplication"}
  ],
  "decision_limits": ["Do not mark delivery passed when reuse_non_duplication is FAIL."],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "convention", "decision": "not_applicable", "reason": "synthetic helper fixture has no convention asset"}
  ]
}
JSON
python3 "$G" contract-write dry-kiss-contract.json >/dev/null
printf '%s' '{"tool_input":{"file_path":"src/new-helper.ts"}}' | python3 "$G" post-edit >/dev/null
python3 "$G" evidence-add "unit smoke" passed >/dev/null
out=$(printf '%s' '{
  "changed_files": ["src/new-helper.ts"],
  "affected_layers": ["Consumer"],
  "scope_evidence": "src/new-helper.ts is within allowed_paths.",
  "context_used": [
    {"source": "src/new-helper.ts", "reason": "changed helper", "finding": "DRY/KISS gate fixture"}
  ],
  "consumer_asset_routing": [
    {"task_signal": "bug fix", "asset_type": "convention", "decision": "not_applicable", "reason": "synthetic helper fixture has no convention asset"}
  ],
  "learning_review": {
    "mistake_checked": "duplicated_helper",
    "lesson_decision": "recorded",
    "promoted_to": "not_applicable",
    "reason": "fixture declares the non-duplication gate failed"
  },
  "quality_gates": {
    "reuse_non_duplication": {
      "result": "FAIL",
      "evidence": "fixture says DRY/KISS was not satisfied"
    }
  },
  "verification_command": "unit smoke",
  "result": "passed",
  "reuse_discipline": {
    "existing_code_checked": "synthetic helper search",
    "existing_component_checked": "not_applicable: no UI component",
    "existing_pattern_followed": "simple helper fixture",
    "new_code_reason": "DRY/KISS negative fixture",
    "duplicate_risk": "high because quality gate failed",
    "kiss_dry_rationale": "fixture intentionally violates the gate"
  }
}' | python3 "$G" receipt-write)
grep -q "receipt_rejected" <<< "$out"
grep -q "reuse_non_duplication.result cannot be FAIL" <<< "$out"
grep -q "limitation is required when quality_gates.reuse_non_duplication.result is FAIL" <<< "$out"

echo "== E36 receipt seal detects post-delivery tampering =="
W="$(fresh_case e36)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
printf 'sealed docs\n' > README.md
cat > seal-contract.json <<'JSON'
{
  "task_scope": "receipt seal fixture",
  "affected_layers": ["Docs"],
  "allowed_paths": ["README.md"],
  "expected_evidence": ["docs smoke"],
  "out_of_scope_paths": [],
  "consumer_scope": "synthetic docs receipt only"
}
JSON
python3 "$G" contract-write seal-contract.json >/dev/null
printf '%s' '{"tool_input":{"file_path":"README.md"}}' | python3 "$G" post-edit >/dev/null
python3 "$G" evidence-add "docs smoke" passed >/dev/null
printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed"
}' | python3 "$G" receipt-write | grep -q "deliver receipt recorded"
python3 "$G" receipt-seal > seal.json
grep -q '"result": "receipt_sealed"' seal.json
grep -q '"receipt_sha256"' seal.json
grep -q '"changed_files"' seal.json
out=$(python3 "$G" receipt-verify seal.json)
grep -q '"result": "receipt_verify_passed"' <<< "$out"
printf 'tamper\n' >> README.md
out=$(python3 "$G" receipt-verify seal.json)
grep -q '"result": "receipt_verify_failed"' <<< "$out"
grep -q '"changed_files": false' <<< "$out"
python3 "$G" receipt-seal --record > recorded-seal.json
grep -q '"recorded_to": "pilothOS/memory/state/receipt-seals.jsonl"' recorded-seal.json
[ -f pilothOS/memory/state/receipt-seals.jsonl ]

echo "== E37 production-review blocks stale artifacts and noisy release tokens =="
W="$(fresh_case e37)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
out=$(python3 "$G" production-review)
grep -q '"result": "production_review_passed"' <<< "$out"
printf 'print("stale")\n' > pilothOS/scripts/pilothos_hostd.py
out=$(python3 "$G" production-review)
grep -q '"result": "production_review_failed"' <<< "$out"
grep -q 'removed deprecated host-level artifacts' <<< "$out"
rm -f pilothOS/scripts/pilothos_hostd.py
printf '\nTO''DO: remove this before release\n' >> pilothOS/VALIDATION.md
out=$(python3 "$G" production-review)
grep -q '"result": "production_review_failed"' <<< "$out"
grep -q 'production noise scan' <<< "$out"

echo "== E38 state-doctor checks repo-local state health =="
W="$(fresh_case e38)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
out=$(python3 "$G" state-doctor)
grep -q '"result": "state_doctor_passed"' <<< "$out"
grep -q 'repo-local state excluded from manifest' <<< "$out"
mkdir -p pilothOS/memory/state
printf 'not-json\n' > pilothOS/memory/state/scheduler-history.jsonl
out=$(python3 "$G" state-doctor)
grep -q '"result": "state_doctor_failed"' <<< "$out"
grep -q 'scheduler history jsonl' <<< "$out"
rm -f pilothOS/memory/state/scheduler-history.jsonl
python3 "$G" scheduler-record '{"task_signal":"bug fix","affected_layers":["Consumer"],"verification_command":"unit smoke","result":"passed"}' >/dev/null
printf 'state seal docs\n' > README.md
python3 "$G" contract-write '{"task_scope":"state seal fixture","affected_layers":["Docs"],"allowed_paths":["README.md"],"expected_evidence":["docs smoke"],"out_of_scope_paths":[]}' >/dev/null
printf '%s' '{"tool_input":{"file_path":"README.md"}}' | python3 "$G" post-edit >/dev/null
python3 "$G" evidence-add "docs smoke" passed >/dev/null
printf '%s' '{"changed_files":["README.md"],"affected_layers":["Docs"],"verification_command":"docs smoke","result":"passed"}' | python3 "$G" receipt-write >/dev/null
python3 "$G" receipt-seal --record >/dev/null
out=$(python3 "$G" state-doctor)
grep -q '"result": "state_doctor_passed"' <<< "$out"
grep -q 'receipt seal chain' <<< "$out"
out=$(python3 "$G" production-review)
grep -q '"result": "production_review_passed"' <<< "$out"
grep -q 'state-doctor' <<< "$out"

echo "== E39 artifact-janitor detects and cleans deterministic local artifacts =="
W="$(fresh_case e39)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
out=$(python3 "$G" artifact-janitor)
grep -q '"result": "artifact_janitor_passed"' <<< "$out"
printf 'local artifact\n' > .DS_Store
mkdir -p pilothOS/runtime/__pycache__
printf 'bytecode\n' > pilothOS/runtime/__pycache__/x.pyc
out=$(python3 "$G" artifact-janitor)
grep -q '"result": "artifact_janitor_failed"' <<< "$out"
grep -q '.DS_Store' <<< "$out"
out=$(python3 "$G" artifact-janitor --fix)
grep -Eq '"result": "artifact_janitor_(cleaned|passed)"' <<< "$out"
[ ! -e .DS_Store ]
[ ! -d pilothOS/runtime/__pycache__ ]
out=$(python3 "$G" artifact-janitor)
grep -q '"result": "artifact_janitor_passed"' <<< "$out"

echo "== E40 control-plane-check gates manifest, active receipt and recorded seal =="
W="$(fresh_case e40)"
cd "$W"
G="pilothOS/scripts/pilothos_guard.py"
printf 'obsolete baseline docs\n' > obsolete.md
git init -q
git config user.email "pilothos@example.test"
git config user.name "PilothOS Test"
git add .
git commit -qm baseline
out=$(python3 "$G" control-plane-check --no-active-task)
grep -q '"result": "control_plane_passed"' <<< "$out"
out=$(python3 "$G" control-plane-check --active-task)
grep -q '"result": "control_plane_failed"' <<< "$out"
grep -q 'missing active task contract' <<< "$out"
printf 'control plane docs\n' > README.md
cat > "$TMP/control-plane-contract-e40.json" <<'JSON'
{
  "task_scope": "control plane docs fixture",
  "affected_layers": ["Docs"],
  "allowed_paths": ["README.md", "obsolete.md"],
  "expected_evidence": ["docs smoke"],
  "out_of_scope_paths": []
}
JSON
python3 "$G" contract-write "$TMP/control-plane-contract-e40.json" >/dev/null
python3 "$G" os-start '{
  "task_id": "e40-control-plane",
  "intent": "control plane docs fixture",
  "task_signal": "not_applicable",
  "affected_layers": ["Docs"],
  "allowed_paths": ["README.md", "obsolete.md"],
  "expected_evidence": ["docs smoke"],
  "out_of_scope_paths": []
}' >/dev/null
printf '%s' '{"tool_input":{"file_path":"README.md"}}' | python3 "$G" post-edit >/dev/null
rm obsolete.md
printf '%s' '{"tool_input":{"file_path":"obsolete.md"}}' | python3 "$G" post-edit >/dev/null
python3 "$G" os-evidence '{"id":"docs-smoke","command":"docs smoke","result":"passed","summary":"control-plane fixture docs smoke"}' >/dev/null
printf '%s' '{
  "changed_files": ["README.md", "obsolete.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed",
  "quality_gates": {
    "scope": {"result": "PASS", "evidence": "README.md and obsolete.md are allowed by the OS contract."},
    "correctness": {"result": "PASS", "evidence": "docs-smoke passed."},
    "traceability": {"result": "PASS", "evidence": "os-start, post-edit facts, receipt and seal are recorded."},
    "disclosure": {"result": "PASS", "evidence": "No limitation in this control-plane fixture."}
  },
  "claims": [
    {"claim": "The docs smoke evidence passed for the scoped changed files.", "evidence_refs": ["docs-smoke", "quality_gates.correctness"]}
  ]
}' | python3 "$G" os-close | grep -q '"result": "os_closed"'
out=$(python3 "$G" control-plane-check --active-task)
grep -q '"result": "control_plane_passed"' <<< "$out"
grep -q 'receipt seal' <<< "$out"
grep -q '"missing"' <<< "$out"
printf 'uncovered\n' > uncovered.md
out=$(python3 "$G" control-plane-check --active-task)
grep -q '"result": "control_plane_failed"' <<< "$out"
grep -q 'git changed file coverage' <<< "$out"
grep -q 'missing_from_receipt' <<< "$out"

echo "EVALUATION SUITE: ALL PASS"
