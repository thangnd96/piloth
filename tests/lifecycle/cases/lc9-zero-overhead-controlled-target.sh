#!/usr/bin/env bash
set -euo pipefail
cd "$1"
G="pilothOS/scripts/pilothos_guard.py"
TARGET="$PWD/controlled-ui-target"
mkdir -p "$TARGET"

cat > zero-target-request.json <<JSON
{
  "task_id": "lc9-zero-overhead-target",
  "intent": "Build a small controlled target UI without installing Piloth into the target",
  "task_signal": "UI/component",
  "target_repo": "$TARGET",
  "evidence_profile": "ui",
  "affected_layers": ["Consumer"],
  "target_paths": ["index.html", "styles.css"],
  "expected_evidence": ["browser smoke"],
  "out_of_scope_paths": []
}
JSON
out=$(python3 "$G" os-start zero-target-request.json)
grep -q '"result": "os_started"' <<< "$out"
grep -q '"execution_strategy": "controlled_target"' <<< "$out"
grep -q '"target_footprint_policy": "no_control_plane_files"' <<< "$out"
grep -q '"ui_quality"' <<< "$out"

cat > ui-quality.json <<'JSON'
{
  "id": "ui-quality",
  "kind": "metric",
  "metric_type": "ui_quality",
  "metric_name": "controlled target browser smoke",
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
cat > browser-smoke.json <<'JSON'
{
  "id": "browser-smoke",
  "kind": "command",
  "phase": "verify",
  "command": "browser smoke",
  "result": "passed",
  "summary": "Required title and card text were checked in the controlled target fixture"
}
JSON
python3 "$G" os-evidence browser-smoke.json >/dev/null

cat > "$TARGET/index.html" <<'HTML'
<!doctype html>
<html>
<head><meta charset="utf-8"><title>Controlled Target UI</title><link rel="stylesheet" href="styles.css"></head>
<body><main><h1>Controlled Target UI</h1><section class="tools"><article>Cloud Selection Advisor</article></section></main></body>
</html>
HTML
cat > "$TARGET/styles.css" <<'CSS'
body { margin: 0; font-family: Arial, sans-serif; color: #101828; background: #f3f6fb; }
main { max-width: 960px; margin: 0 auto; padding: 32px; }
.tools { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; }
article { border: 1px solid #d0d5dd; background: #fff; border-radius: 8px; padding: 16px; }
CSS

mkdir -p "$TARGET/pilothOS/memory/state"
printf '{}\n' > "$TARGET/pilothOS/memory/state/noise.json"
bad=$(printf '%s' '{
  "changed_files": ["index.html", "styles.css", "pilothOS/memory/state/noise.json"],
  "affected_layers": ["Consumer"],
  "verification_command": "browser smoke",
  "result": "passed",
  "quality_gates": {
    "scope": {"result": "PASS", "evidence": "target files are inside the fixture target."},
    "correctness": {"result": "PASS", "evidence": "browser-smoke passed."},
    "disclosure": {"result": "PASS", "evidence": "Pixel diff is not claimed."},
    "design_system": {"result": "PASS", "evidence": "No consumer design system exists in this fixture."},
    "ui_quality": {"result": "PASS", "evidence": "ui-quality records browser invariants."}
  },
  "claims": [
    {"claim": "Controlled target UI smoke passed; pixel-perfect parity is not claimed.", "evidence_refs": ["browser-smoke", "ui-quality", "quality_gates.ui_quality"]}
  ]
}' | python3 "$G" os-close)
grep -q '"result": "os_close_rejected"' <<< "$bad"
grep -q 'Piloth/control-plane' <<< "$bad"

rm -rf "$TARGET/pilothOS"
good=$(printf '%s' '{
  "changed_files": ["index.html", "styles.css"],
  "affected_layers": ["Consumer"],
  "verification_command": "browser smoke",
  "result": "passed",
  "quality_gates": {
    "scope": {"result": "PASS", "evidence": "target files are inside the fixture target."},
    "correctness": {"result": "PASS", "evidence": "browser-smoke passed."},
    "disclosure": {"result": "PASS", "evidence": "Pixel diff is not claimed."},
    "design_system": {"result": "PASS", "evidence": "No consumer design system exists in this fixture."},
    "ui_quality": {"result": "PASS", "evidence": "ui-quality records browser invariants."}
  },
  "claims": [
    {"claim": "Controlled target UI smoke passed with UI quality evidence; pixel-perfect parity is not claimed.", "evidence_refs": ["browser-smoke", "ui-quality", "quality_gates.ui_quality"]}
  ]
}' | python3 "$G" os-close)
grep -q '"result": "os_closed"' <<< "$good"
grep -q '"result": "target_footprint_passed"' <<< "$good"
[ ! -e "$TARGET/pilothOS" ]
out=$(python3 "$G" os-verify)
grep -q '"result": "os_verify_passed"' <<< "$out"
out=$(python3 "$G" os-report)
grep -q '"target_footprint_policy": "no_control_plane_files"' <<< "$out"
grep -q '"result": "target_footprint_passed"' <<< "$out"
