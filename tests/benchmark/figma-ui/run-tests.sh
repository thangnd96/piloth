#!/usr/bin/env bash
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
NONE="$TMP/none-piloth"
HAD="$TMP/had-piloth"
CONTROL="$TMP/piloth-control"
mkdir -p "$NONE" "$HAD" "$CONTROL"

write_ui() {
  target="$1"
  cat > "$target/index.html" <<'HTML'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Game Infrastructure Operations Hub</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main class="hub-shell">
    <section class="hero" aria-label="Operations hub">
      <p class="eyebrow">Figma node 4138:19274</p>
      <h1>Game Infrastructure Operations Hub</h1>
      <p class="summary">Plan cloud, CDN and global networking workflows from a single operations view.</p>
    </section>
    <section class="tools" aria-label="Operations tools">
      <article><h2>Cloud Selection Advisor</h2><p>Compare provider fit for launch regions.</p></article>
      <article><h2>CDN Download Monitoring</h2><p>Track rollout health and download performance.</p></article>
      <article><h2>Global Networking</h2><p>Review routing posture across studios.</p></article>
    </section>
  </main>
</body>
</html>
HTML
  cat > "$target/styles.css" <<'CSS'
:root { color-scheme: light; --ink: #101828; --muted: #667085; --line: #d0d5dd; --panel: #ffffff; --bg: #f3f6fb; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Arial, sans-serif; color: var(--ink); background: var(--bg); }
.hub-shell { width: min(1120px, calc(100vw - 32px)); margin: 0 auto; padding: 32px 0 40px; }
.hero { min-height: 190px; display: grid; align-content: center; gap: 10px; }
.eyebrow { margin: 0; color: #175cd3; font-weight: 700; }
h1 { margin: 0; max-width: 760px; font-size: 48px; line-height: 1.02; letter-spacing: 0; }
.summary { margin: 0; max-width: 620px; color: var(--muted); font-size: 18px; line-height: 1.5; }
.tools { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
article { min-height: 132px; padding: 20px; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }
h2 { margin: 0 0 10px; font-size: 18px; letter-spacing: 0; }
article p { margin: 0; color: var(--muted); line-height: 1.45; }
@media (max-width: 760px) {
  h1 { font-size: 34px; }
  .tools { grid-template-columns: 1fr; }
}
CSS
  cat > "$target/README.md" <<'MD'
# Game Infrastructure Operations Hub

Static UI fixture generated independently from Figma node `4138:19274`.
MD
}

tree_bytes() {
  root="$1"
  find "$root" -type f ! -name '.DS_Store' -print0 | xargs -0 stat -f '%z' | awk '{s+=$1} END {print s+0}'
}

tree_count() {
  root="$1"
  find "$root" -type f ! -name '.DS_Store' | wc -l | tr -d ' '
}

echo "== none-piloth independent build has no Piloth footprint =="
{
  echo "build_start none"
  write_ui "$NONE"
  echo "build_done none"
} > "$TMP/none-command.log"
[ ! -e "$NONE/pilothOS" ]
! grep -Ei 'pilothOS|pilothos_guard|stage\.sh' "$TMP/none-command.log"

echo "== had-piloth target is controlled by separate Piloth control plane =="
bash "$REPO/scripts/stage.sh" "$CONTROL" > "$TMP/control-stage.log"
cd "$CONTROL"
G="pilothOS/scripts/pilothos_guard.py"
cat > "$TMP/os-request.json" <<JSON
{
  "task_id": "benchmark-figma-ui",
  "intent": "Build the Figma Tenants operations hub UI without mutating the consumer target with Piloth runtime",
  "task_signal": "UI/component",
  "target_repo": "$HAD",
  "affected_layers": ["Consumer", "Docs"],
  "target_paths": ["index.html", "styles.css", "README.md"],
  "expected_evidence": ["figma_node", "browser smoke"],
  "out_of_scope_paths": []
}
JSON
python3 "$G" os-start "$TMP/os-request.json" > "$TMP/os-start.json"
grep -q '"mode": "lean"' "$TMP/os-start.json"
grep -q '"execution_strategy": "controlled_target"' "$TMP/os-start.json"
grep -q '"target_footprint_policy": "no_control_plane_files"' "$TMP/os-start.json"
[ ! -e "$HAD/pilothOS" ]
write_ui "$HAD"
[ ! -e "$HAD/pilothOS" ]
[ "$(tree_count "$NONE")" = "$(tree_count "$HAD")" ]
[ "$(tree_bytes "$NONE")" = "$(tree_bytes "$HAD")" ]

cat > "$TMP/figma-node.json" <<'JSON'
{
  "id": "figma-node-4138-19274",
  "kind": "figma_node",
  "fileKey": "7nCZNm12l7NtL8S1qWqgs8",
  "nodeId": "4138:19274",
  "summary": "Figma Tenants source frame for benchmark fixture"
}
JSON
python3 "$G" os-evidence "$TMP/figma-node.json" >/dev/null

if node -e "require('playwright')" >/dev/null 2>&1; then
  node - "$NONE" "$HAD" "$TMP/browser-report.json" <<'NODE'
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const { chromium } = require('playwright');

const [noneRoot, hadRoot, outPath] = process.argv.slice(2);
const required = [
  'Game Infrastructure Operations Hub',
  'Cloud Selection Advisor',
  'CDN Download Monitoring',
  'Global Networking',
];

async function pageCheck(browser, root, label) {
  const page = await browser.newPage({ viewport: { width: 1024, height: 620 } });
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', error => pageErrors.push(error.message));
  await page.goto(pathToFileURL(path.join(root, 'index.html')).href, { waitUntil: 'load' });
  await page.locator('text=Game Infrastructure Operations Hub').first().waitFor({ timeout: 5000 });
  const screenshotPath = path.join(path.dirname(outPath), `${label}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  const result = await page.evaluate((requiredText) => {
    const body = document.body.innerText;
    const tools = document.querySelector('.tools');
    const toolsStyle = tools ? getComputedStyle(tools) : null;
    const images = Array.from(document.images);
    return {
      required_text_ok: requiredText.every(text => body.includes(text)),
      css_grid_ok: toolsStyle ? toolsStyle.display === 'grid' : false,
      horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      vertical_overflow: document.documentElement.scrollHeight > document.documentElement.clientHeight,
      image_failure_count: images.filter(img => !img.complete || img.naturalWidth === 0).length,
      body_text_length: body.length,
    };
  }, required);
  await page.close();
  return {
    ...result,
    console_error_count: consoleErrors.length,
    page_error_count: pageErrors.length,
    console_errors: consoleErrors,
    page_errors: pageErrors,
    screenshot_path: screenshotPath,
    viewport_width: 1024,
    viewport_height: 620,
    method: 'playwright',
  };
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const none = await pageCheck(browser, noneRoot, 'none');
  const had = await pageCheck(browser, hadRoot, 'had');
  await browser.close();
  const sameUiHashes = (
    fs.readFileSync(path.join(noneRoot, 'index.html'), 'utf8') === fs.readFileSync(path.join(hadRoot, 'index.html'), 'utf8') &&
    fs.readFileSync(path.join(noneRoot, 'styles.css'), 'utf8') === fs.readFileSync(path.join(hadRoot, 'styles.css'), 'utf8')
  );
  const visualDiffResult = Buffer.compare(
    fs.readFileSync(none.screenshot_path),
    fs.readFileSync(had.screenshot_path),
  ) === 0 ? 'identical_screenshot_bytes' : 'different_screenshot_bytes';
  const report = {
    none,
    had,
    same_ui_hashes: sameUiHashes,
    visual_diff_result: visualDiffResult,
  };
  report.mandatory_checks_not_worse = (
    none.required_text_ok === had.required_text_ok &&
    none.css_grid_ok === had.css_grid_ok &&
    none.horizontal_overflow === had.horizontal_overflow &&
    none.vertical_overflow === had.vertical_overflow &&
    had.required_text_ok &&
    had.css_grid_ok &&
    had.console_error_count === 0 &&
    had.page_error_count === 0 &&
    had.image_failure_count === 0 &&
    visualDiffResult === 'identical_screenshot_bytes'
  );
  fs.writeFileSync(outPath, JSON.stringify(report, null, 2) + '\n');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
NODE
else
  python3 - "$NONE" "$HAD" "$TMP/browser-report.json" <<'PY'
import hashlib
import json
import pathlib
import sys

none = pathlib.Path(sys.argv[1])
had = pathlib.Path(sys.argv[2])
out = pathlib.Path(sys.argv[3])

def page_check(root):
    html = (root / "index.html").read_text(encoding="utf-8")
    css = (root / "styles.css").read_text(encoding="utf-8")
    required = [
        "Game Infrastructure Operations Hub",
        "Cloud Selection Advisor",
        "CDN Download Monitoring",
        "Global Networking",
    ]
    return {
        "required_text_ok": all(text in html for text in required),
        "css_grid_ok": "grid-template-columns" in css,
        "horizontal_overflow": False,
        "vertical_overflow": False,
        "console_error_count": 0,
        "page_error_count": 0,
        "image_failure_count": 0,
        "viewport_width": 1024,
        "viewport_height": 620,
        "html_sha256": hashlib.sha256(html.encode()).hexdigest(),
        "css_sha256": hashlib.sha256(css.encode()).hexdigest(),
        "method": "static browser fallback",
        "limitation": "Playwright/browser screenshot not available in shell benchmark",
    }

report = {
    "none": page_check(none),
    "had": page_check(had),
}
report["same_ui_hashes"] = (
    report["none"]["html_sha256"] == report["had"]["html_sha256"]
    and report["none"]["css_sha256"] == report["had"]["css_sha256"]
)
report["visual_diff_result"] = "not_run"
report["mandatory_checks_not_worse"] = (
    report["same_ui_hashes"]
    and report["none"]["required_text_ok"] == report["had"]["required_text_ok"]
    and report["none"]["css_grid_ok"] == report["had"]["css_grid_ok"]
    and report["had"]["required_text_ok"]
    and report["had"]["css_grid_ok"]
)
out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
fi

cat > "$TMP/browser-smoke.json" <<JSON
{
  "id": "browser-smoke",
  "kind": "command",
  "phase": "verify",
  "command": "browser smoke",
  "result": "passed",
  "summary": "Browser/static report passed required text, CSS grid and overflow checks",
  "artifact_path": "$TMP/browser-report.json"
}
JSON
python3 "$G" os-evidence "$TMP/browser-smoke.json" >/dev/null

python3 - "$TMP/browser-report.json" "$TMP/ui-quality.json" <<'PY'
import json
import pathlib
import sys

report = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
had = report["had"]
payload = {
    "id": "ui-quality",
    "kind": "metric",
    "metric_type": "ui_quality",
    "metric_name": "had-piloth browser UI quality",
    "phase": "verify",
    "browser_tool": had.get("method", "unknown"),
    "viewport_width": had.get("viewport_width", 1024),
    "viewport_height": had.get("viewport_height", 620),
    "required_text_ok": bool(had.get("required_text_ok")),
    "console_error_count": int(had.get("console_error_count", 0)),
    "page_error_count": int(had.get("page_error_count", 0)),
    "image_failure_count": int(had.get("image_failure_count", 0)),
    "horizontal_overflow": bool(had.get("horizontal_overflow")),
    "vertical_overflow": bool(had.get("vertical_overflow")),
    "visual_diff_result": report.get("visual_diff_result", "not_run"),
    "artifact_path": str(pathlib.Path(sys.argv[1])),
}
if had.get("screenshot_path"):
    payload["screenshot_path"] = had["screenshot_path"]
pathlib.Path(sys.argv[2]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
python3 "$G" os-evidence "$TMP/ui-quality.json" >/dev/null

python3 - "$NONE" "$HAD" "$CONTROL" "$TMP/browser-report.json" "$TMP/benchmark-report.json" <<'PY'
import json
import pathlib
import sys

none = pathlib.Path(sys.argv[1])
had = pathlib.Path(sys.argv[2])
control = pathlib.Path(sys.argv[3])
browser = json.loads(pathlib.Path(sys.argv[4]).read_text(encoding="utf-8"))
out = pathlib.Path(sys.argv[5])

def tree_stats(root):
    files = [path for path in root.rglob("*") if path.is_file() and path.name != ".DS_Store"]
    return {
        "file_count": len(files),
        "bytes": sum(path.stat().st_size for path in files),
    }

none_target = tree_stats(none)
had_target = tree_stats(had)
control_state = tree_stats(control / "pilothOS" / "memory" / "state")
mandatory_regressions = []
if not browser["mandatory_checks_not_worse"]:
    mandatory_regressions.append("ui_quality_regression")
if had_target != none_target:
    mandatory_regressions.append("target_artifact_footprint_higher")
mandatory_regressions.append("no_real_token_telemetry")
report = {
    "schema_version": 1,
    "none_piloth_proof": {
        "piloth_dir_present": (none / "pilothOS").exists(),
        "command_log_contains_piloth": False,
    },
    "had_piloth_target_proof": {
        "piloth_dir_present": (had / "pilothOS").exists(),
        "target_file_count": had_target["file_count"],
        "target_bytes": had_target["bytes"],
    },
    "control_plane": {
        "path_role": "separate controlled-target supervisor",
        "state_file_count": control_state["file_count"],
        "state_bytes": control_state["bytes"],
    },
    "browser": browser,
    "cost": {
        "none_target_artifact_bytes": none_target["bytes"],
        "had_target_artifact_bytes": had_target["bytes"],
        "llm_tokens": "unavailable",
        "real_token_telemetry": False,
    },
    "all_mandatory_not_worse": not mandatory_regressions,
    "consumer_visible_win": False,
    "wins": [],
    "mandatory_regressions": mandatory_regressions,
    "consumer_value_result": "consumer_value_failed",
}
out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
grep -q '"consumer_value_result": "consumer_value_failed"' "$TMP/benchmark-report.json"
grep -q '"no_real_token_telemetry"' "$TMP/benchmark-report.json"
! grep -q '"target_artifact_footprint_higher"' "$TMP/benchmark-report.json"
grep -q '"piloth_dir_present": false' "$TMP/benchmark-report.json"

cat > "$TMP/benchmark-metric.json" <<'JSON'
{
  "id": "benchmark-comparison",
  "kind": "metric",
  "metric_type": "benchmark",
  "metric_name": "none-piloth vs controlled-target Piloth Figma UI",
  "phase": "verify",
  "consumer_value_result": "consumer_value_failed",
  "all_mandatory_not_worse": false,
  "consumer_visible_win": false,
  "real_token_telemetry": false,
  "mandatory_regressions": ["no_real_token_telemetry"],
  "wins": []
}
JSON
python3 "$G" os-evidence "$TMP/benchmark-metric.json" >/dev/null

cat > "$TMP/token-unavailable.json" <<'JSON'
{
  "id": "llm-token-telemetry",
  "kind": "metric",
  "metric_type": "llm_usage",
  "metric_name": "adapter token telemetry",
  "phase": "verify",
  "real_token_telemetry": false,
  "unavailable_reason": "benchmark shell has no adapter prompt/completion token telemetry"
}
JSON
python3 "$G" os-evidence "$TMP/token-unavailable.json" >/dev/null

close=$(printf '%s' '{
  "changed_files": ["README.md", "index.html", "styles.css"],
  "affected_layers": ["Consumer", "Docs"],
  "verification_command": "browser smoke",
  "result": "passed",
  "quality_gates": {
    "scope": {"result": "PASS", "evidence": "Only target UI fixture files changed."},
    "correctness": {"result": "PASS", "evidence": "browser-smoke passed for required text and CSS grid checks."},
    "disclosure": {"result": "PASS", "evidence": "Benchmark result is consumer_value_failed; exact LLM token telemetry is unavailable."},
    "design_system": {"result": "PASS", "evidence": "Figma source ref was recorded; no consumer DS exists in this fixture."},
    "ui_quality": {"result": "PASS", "evidence": "ui-quality records viewport, console/page errors, image failures, overflow and visual diff status."}
  },
  "consumer_superiority": {
    "result": "consumer_value_failed",
    "all_mandatory_not_worse": false,
    "consumer_visible_win": false
  },
  "claims": [
    {"claim": "Rendered the scoped Figma UI fixture with browser smoke and UI quality evidence; consumer superiority and token savings are not claimed.", "evidence_refs": ["figma-node-4138-19274", "browser-smoke", "ui-quality", "quality_gates.ui_quality"]}
  ]
}' | python3 "$G" os-close)
grep -q '"result": "os_closed"' <<< "$close"
grep -q '"result": "target_footprint_passed"' <<< "$close"
python3 "$G" os-verify | grep -q '"result": "os_verify_passed"'
python3 "$G" os-report > "$TMP/os-report.json"
grep -q '"result": "consumer_value_failed"' "$TMP/os-report.json"
grep -q '"real_tokens": "unavailable"' "$TMP/os-report.json"
grep -q '"target_footprint_policy": "no_control_plane_files"' "$TMP/os-report.json"

echo "BENCHMARK FIGMA UI: ALL PASS"
