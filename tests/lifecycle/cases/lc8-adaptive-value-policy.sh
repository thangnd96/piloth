#!/usr/bin/env bash
set -euo pipefail
cd "$1"
G="pilothOS/scripts/pilothos_guard.py"

echo "== adaptive UI task starts lean and records cost metrics =="
cat > adaptive-ui-request.json <<'JSON'
{
  "task_id": "lc8-adaptive-ui",
  "intent": "Build a small UI from a Figma frame",
  "task_signal": "UI/component",
  "affected_layers": ["Consumer"],
  "target_paths": ["index.html", "styles.css"],
  "expected_evidence": ["figma_node", "browser smoke"],
  "out_of_scope_paths": []
}
JSON
out=$(python3 "$G" os-start adaptive-ui-request.json)
grep -q '"result": "os_started"' <<< "$out"
grep -q '"mode": "lean"' <<< "$out"
grep -q '"design_system"' <<< "$out"

cat > figma-node.json <<'JSON'
{
  "id": "figma-node",
  "kind": "figma_node",
  "fileKey": "FILE123",
  "nodeId": "4138:19274",
  "summary": "Figma source node for the adaptive UI fixture"
}
JSON
python3 "$G" os-evidence figma-node.json >/dev/null

cat > browser-smoke.json <<'JSON'
{
  "id": "browser-smoke",
  "kind": "command",
  "phase": "verify",
  "command": "browser smoke",
  "result": "passed",
  "summary": "Rendered title, tool cards and image placeholders were checked"
}
JSON
python3 "$G" os-evidence browser-smoke.json >/dev/null

cat > ui-quality.json <<'JSON'
{
  "id": "ui-quality",
  "kind": "metric",
  "metric_type": "ui_quality",
  "metric_name": "browser UI quality smoke",
  "phase": "verify",
  "browser_tool": "static lifecycle fixture",
  "viewport_width": 1024,
  "viewport_height": 620,
  "required_text_ok": true,
  "console_error_count": 0,
  "page_error_count": 0,
  "image_failure_count": 0,
  "horizontal_overflow": false,
  "vertical_overflow": false,
  "visual_diff_result": "not_run",
  "limitation": "Lifecycle fixture records browser invariants; pixel diff is not run."
}
JSON
python3 "$G" os-evidence ui-quality.json >/dev/null

cat > no-token-telemetry.json <<'JSON'
{
  "id": "llm-unavailable",
  "kind": "metric",
  "metric_type": "llm_usage",
  "metric_name": "adapter token telemetry",
  "phase": "verify",
  "real_token_telemetry": false,
  "unavailable_reason": "adapter did not provide prompt/completion token usage"
}
JSON
python3 "$G" os-evidence no-token-telemetry.json >/dev/null

cat > tool-output.json <<'JSON'
{
  "id": "tool-output",
  "kind": "metric",
  "metric_type": "tool_output",
  "metric_name": "browser verification output",
  "phase": "verify",
  "chars": 2048,
  "unit": "chars"
}
JSON
python3 "$G" os-evidence tool-output.json >/dev/null

cat > benchmark-failed.json <<'JSON'
{
  "id": "benchmark-failed",
  "kind": "metric",
  "metric_type": "benchmark",
  "metric_name": "none-piloth vs had-piloth",
  "phase": "verify",
  "consumer_value_result": "consumer_value_failed",
  "all_mandatory_not_worse": true,
  "consumer_visible_win": false,
  "wins": [],
  "mandatory_regressions": []
}
JSON
python3 "$G" os-evidence benchmark-failed.json >/dev/null

cat > index.html <<'HTML'
<!doctype html>
<html>
<head><meta charset="utf-8"><title>Game Infrastructure Operations Hub</title><link rel="stylesheet" href="styles.css"></head>
<body><main><h1>Game Infrastructure Operations Hub</h1><section class="tools"><article>Cloud Selection Advisor</article><article>CDN Download Monitoring</article><article>Global Networking</article></section></main></body>
</html>
HTML
cat > styles.css <<'CSS'
body { margin: 0; font-family: Arial, sans-serif; color: #111827; background: #f5f7fb; }
main { max-width: 960px; margin: 0 auto; padding: 32px; }
.tools { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
article { border: 1px solid #d8dde8; background: white; border-radius: 8px; padding: 16px; }
CSS
printf '%s' '{"tool_input":{"file_path":"index.html"}}' | python3 "$G" post-edit >/dev/null
printf '%s' '{"tool_input":{"file_path":"styles.css"}}' | python3 "$G" post-edit >/dev/null

echo "== superiority claims require benchmark pass evidence =="
bad=$(printf '%s' '{
  "changed_files": ["index.html", "styles.css"],
  "affected_layers": ["Consumer"],
  "verification_command": "browser smoke",
  "result": "passed",
  "quality_gates": {
    "scope": {"result": "PASS", "evidence": "index.html and styles.css are inside target_paths."},
    "correctness": {"result": "PASS", "evidence": "browser-smoke passed."},
    "disclosure": {"result": "PASS", "evidence": "Exact visual parity and token telemetry are not claimed."},
    "design_system": {"result": "PASS", "evidence": "figma-node records source context; no consumer DS existed in this fixture."},
    "ui_quality": {"result": "PASS", "evidence": "ui-quality records viewport, console/page errors, image failures and overflow checks."}
  },
  "consumer_superiority": {
    "result": "consumer_value_failed",
    "all_mandatory_not_worse": true,
    "consumer_visible_win": false
  },
  "claims": [
    {"claim": "Piloth is cheaper and better than none-piloth for this UI task.", "evidence_refs": ["benchmark-failed"]}
  ]
}' | python3 "$G" os-close)
grep -q '"result": "os_close_rejected"' <<< "$bad"
grep -q "consumer superiority" <<< "$bad"

good=$(printf '%s' '{
  "changed_files": ["index.html", "styles.css"],
  "affected_layers": ["Consumer"],
  "verification_command": "browser smoke",
  "result": "passed",
  "quality_gates": {
    "scope": {"result": "PASS", "evidence": "index.html and styles.css are inside target_paths."},
    "correctness": {"result": "PASS", "evidence": "browser-smoke passed."},
    "disclosure": {"result": "PASS", "evidence": "Exact visual parity and token telemetry are not claimed."},
    "design_system": {"result": "PASS", "evidence": "figma-node records source context; no consumer DS existed in this fixture."},
    "ui_quality": {"result": "PASS", "evidence": "ui-quality records viewport, console/page errors, image failures and overflow checks."}
  },
  "consumer_superiority": {
    "result": "consumer_value_failed",
    "all_mandatory_not_worse": true,
    "consumer_visible_win": false
  },
  "claims": [
    {"claim": "Rendered the scoped UI from Figma source with browser smoke and UI quality evidence; exact visual parity is not claimed.", "evidence_refs": ["figma-node", "browser-smoke", "ui-quality", "quality_gates.ui_quality"]}
  ]
}' | python3 "$G" os-close)
grep -q '"result": "os_closed"' <<< "$good"

out=$(python3 "$G" os-report)
grep -q '"result": "os_report"' <<< "$out"
grep -q '"mode": "lean"' <<< "$out"
grep -q '"real_tokens": "unavailable"' <<< "$out"
grep -q '"tool_output_chars": 2048' <<< "$out"
grep -q '"result": "consumer_value_failed"' <<< "$out"
out=$(python3 "$G" os-verify)
grep -q '"result": "os_verify_passed"' <<< "$out"
