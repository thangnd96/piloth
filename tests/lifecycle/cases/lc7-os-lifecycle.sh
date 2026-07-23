#!/usr/bin/env bash
set -euo pipefail
cd "$1"
G="pilothOS/scripts/pilothos_guard.py"

echo "== os-start creates repo-local state and active contract =="
cat > os-request.json <<'JSON'
{
  "task_id": "lc7-docs",
  "intent": "OS lifecycle docs fixture",
  "task_signal": "not_applicable",
  "affected_layers": ["Docs"],
  "allowed_paths": ["README.md"],
  "expected_evidence": ["docs smoke"],
  "out_of_scope_paths": []
}
JSON
out=$(python3 "$G" os-start os-request.json)
grep -q '"result": "os_started"' <<< "$out"
grep -q '"task_id": "lc7-docs"' <<< "$out"
[ -f pilothOS/memory/state/os-runs/lc7-docs/state.json ]
[ -f pilothOS/memory/state/os-runs/lc7-docs/contract.json ]
out=$(python3 "$G" os-status)
grep -q '"result": "os_status"' <<< "$out"
grep -q '"status": "open"' <<< "$out"

echo "== os-evidence sanitizes full output and secrets =="
cat > evidence.json <<'JSON'
{
  "id": "docs-smoke",
  "command": "docs smoke",
  "result": "passed",
  "summary": "README rendered in lifecycle fixture",
  "stdout": "full command output with token=supersecret"
}
JSON
out=$(python3 "$G" os-evidence evidence.json)
grep -q '"result": "os_evidence_recorded"' <<< "$out"
grep -q '"sanitized": true' <<< "$out"
! grep -q "supersecret" pilothOS/memory/state/os-runs/lc7-docs/evidence.jsonl
! grep -q "full command output" pilothOS/memory/state/os-runs/lc7-docs/evidence.jsonl

printf 'os lifecycle docs\n' > README.md
printf '%s' '{"tool_input":{"file_path":"README.md"}}' | python3 "$G" post-edit >/dev/null

echo "== receipt-template is gate-aware (docs run omits UI fields) =="
tmpl=$(python3 "$G" receipt-template)
grep -q '"scope"' <<< "$tmpl"
! grep -q "design_system_checked" <<< "$tmpl"

echo "== os-close --dry-run validates without sealing =="
dry=$(printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed"
}' | python3 "$G" os-close --dry-run)
grep -q '"result": "os_close_dry_run"' <<< "$dry"
grep -q '"would_pass": false' <<< "$dry"
# dry-run must NOT mutate state, seal or write target-diff.json
grep -q '"status": "open"' <<< "$(python3 "$G" os-status)"
[ ! -f pilothOS/memory/state/os-runs/lc7-docs/target-diff.json ]

echo "== os-close rejects missing claims and required gates =="
out=$(printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed"
}' | python3 "$G" os-close)
grep -q '"result": "os_close_rejected"' <<< "$out"
grep -q "claims" <<< "$out"
grep -q "quality_gates" <<< "$out"

echo "== os-close records receipt seal and os-verify detects tampering =="
RC="$(mktemp)"
cat > "$RC" <<'JSON'
{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed",
  "quality_gates": {
    "scope": {"result": "PASS", "evidence": "README.md is the only changed file and is allowed by the OS contract."},
    "correctness": {"result": "PASS", "evidence": "docs smoke evidence ref docs-smoke passed."},
    "traceability": {"result": "PASS", "evidence": "os-start state, post-edit facts, receipt and seal are recorded."},
    "disclosure": {"result": "PASS", "evidence": "No skipped checks or limitations in this docs fixture."}
  },
  "claims": [
    {"claim": "README docs smoke passed for the scoped docs change.", "evidence_refs": ["docs-smoke", "quality_gates.correctness"]}
  ]
}
JSON
# dry-run of a complete receipt must agree with the real close verdict and must
# not itself seal (never returns os_closed)
dry=$(python3 "$G" os-close --dry-run "$RC")
grep -q '"would_pass": true' <<< "$dry"
! grep -q '"result": "os_closed"' <<< "$dry"
out=$(python3 "$G" os-close "$RC")
grep -q '"result": "os_closed"' <<< "$out"
grep -q '"recorded_to": "pilothOS/memory/state/receipt-seals.jsonl"' <<< "$out"
# os-close runs the state-janitor (safe subset) after sealing; it is fail-soft
# and must never turn a good close into a rejection. The active run just sealed
# is always within retention, so a clean project reports no prunable artifacts.
grep -q '"state_janitor"' <<< "$out"
grep -q '"result": "state_janitor_clean"' <<< "$out"
out=$(python3 "$G" os-verify)
grep -q '"result": "os_verify_passed"' <<< "$out"
printf 'tamper\n' >> README.md
out=$(python3 "$G" os-verify)
grep -q '"result": "os_verify_failed"' <<< "$out"
grep -q '"changed_files": false' <<< "$out"

echo "== truth-in-seal rejects unqualified absolute claims but accepts qualified limitations =="
cat > truth-request.json <<'JSON'
{
  "task_id": "lc7-truth",
  "intent": "Truth in seal fixture",
  "task_signal": "not_applicable",
  "affected_layers": ["Docs"],
  "allowed_paths": ["README.md"],
  "expected_evidence": ["pixel diff"],
  "out_of_scope_paths": []
}
JSON
python3 "$G" os-start truth-request.json >/dev/null
cat > pixel-evidence.json <<'JSON'
{
  "id": "pixel-diff",
  "command": "pixel diff",
  "result": "failed",
  "summary": "pixel diff report says different because a font is missing",
  "limitation": "missing font"
}
JSON
python3 "$G" os-evidence pixel-evidence.json >/dev/null
printf 'truth fixture docs\n' > README.md
printf '%s' '{"tool_input":{"file_path":"README.md"}}' | python3 "$G" post-edit >/dev/null
bad=$(printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "pixel diff",
  "result": "passed",
  "limitation": "missing font blocks pixel comparison",
  "quality_gates": {
    "scope": {"result": "PASS", "evidence": "README.md is within scope."},
    "correctness": {"result": "PASS", "evidence": "pixel-diff records the comparison limitation."},
    "traceability": {"result": "PASS", "evidence": "OS state and evidence are recorded."},
    "disclosure": {"result": "PASS", "evidence": "The missing font limitation is disclosed."}
  },
  "claims": [
    {"claim": "The output is production-ready and pixel-perfect.", "evidence_refs": ["pixel-diff"]}
  ]
}' | python3 "$G" os-close)
grep -q '"result": "os_close_rejected"' <<< "$bad"
grep -q "absolute claim" <<< "$bad"
good=$(printf '%s' '{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "pixel diff",
  "result": "passed",
  "limitation": "missing font blocks pixel comparison",
  "quality_gates": {
    "scope": {"result": "PASS", "evidence": "README.md is within scope."},
    "correctness": {"result": "PASS", "evidence": "pixel-diff records the comparison limitation."},
    "traceability": {"result": "PASS", "evidence": "OS state and evidence are recorded."},
    "disclosure": {"result": "PASS", "evidence": "The missing font limitation is disclosed."}
  },
  "claims": [
    {"claim": "Layout metrics were checked; pixel-perfect verification is blocked by the missing font.", "evidence_refs": ["pixel-diff"]}
  ]
}' | python3 "$G" os-close)
grep -q '"result": "os_closed"' <<< "$good"

echo "== controlled git target records metadata, seals target file, and detects tampering =="
mkdir -p target-git/docs
git -C target-git init -q
printf 'git target baseline\n' > target-git/docs/seed.md
cat > git-target-request.json <<JSON
{
  "task_id": "lc7-git-target",
  "intent": "Controlled git target fixture",
  "target_repo": "$PWD/target-git",
  "task_signal": "not_applicable",
  "affected_layers": ["Docs"],
  "target_paths": ["docs/seed.md"],
  "expected_evidence": ["git target smoke"],
  "out_of_scope_paths": []
}
JSON
out=$(python3 "$G" os-start git-target-request.json)
grep -q '"result": "os_started"' <<< "$out"
grep -q '"target_vcs": "git"' <<< "$out"
grep -q '"docs/seed.md"' <<< "$out"
cat > git-target-evidence.json <<'JSON'
{
  "id": "git-target-smoke",
  "kind": "command",
  "command": "git target smoke",
  "result": "passed",
  "summary": "controlled git target smoke passed"
}
JSON
python3 "$G" os-evidence git-target-evidence.json >/dev/null
printf 'git target changed\n' > target-git/docs/seed.md
out=$(printf '%s' '{
  "changed_files": ["docs/seed.md"],
  "affected_layers": ["Docs"],
  "verification_command": "git target smoke",
  "result": "passed",
  "quality_gates": {
    "scope": {"result": "PASS", "evidence": "docs/seed.md is the only target changed file and is allowed."},
    "correctness": {"result": "PASS", "evidence": "git-target-smoke passed."},
    "traceability": {"result": "PASS", "evidence": "target snapshot, target diff, receipt and target seal are recorded."},
    "disclosure": {"result": "PASS", "evidence": "No skipped checks or limitations in this target fixture."}
  },
  "claims": [
    {"claim": "The controlled git target docs smoke passed for docs/seed.md.", "evidence_refs": ["git-target-smoke", "quality_gates.correctness"]}
  ]
}' | python3 "$G" os-close)
grep -q '"result": "os_closed"' <<< "$out"
grep -q '"target_seal_path": "pilothOS/memory/state/os-runs/lc7-git-target/target-seal.json"' <<< "$out"
out=$(python3 "$G" os-verify)
grep -q '"result": "os_verify_passed"' <<< "$out"
printf 'git target tamper\n' >> target-git/docs/seed.md
out=$(python3 "$G" os-verify)
grep -q '"result": "os_verify_failed"' <<< "$out"
grep -q 'target.changed_files' <<< "$out"

echo "== controlled non-git target snapshot fallback seals hashes =="
mkdir -p target-nongit/docs
printf 'non git baseline\n' > target-nongit/docs/token-notes.md
cat > nongit-target-request.json <<JSON
{
  "task_id": "lc7-nongit-target",
  "intent": "Controlled non-git target fixture",
  "target_repo": "$PWD/target-nongit",
  "task_signal": "not_applicable",
  "affected_layers": ["Docs"],
  "target_paths": ["docs/token-notes.md"],
  "expected_evidence": ["non-git target smoke"],
  "out_of_scope_paths": []
}
JSON
out=$(python3 "$G" os-start nongit-target-request.json)
grep -q '"result": "os_started"' <<< "$out"
grep -q '"target_vcs": "non_git"' <<< "$out"
cat > nongit-target-evidence.json <<'JSON'
{
  "id": "nongit-target-smoke",
  "kind": "command",
  "command": "non-git target smoke",
  "result": "passed",
  "summary": "controlled non-git target smoke passed"
}
JSON
python3 "$G" os-evidence nongit-target-evidence.json >/dev/null
printf 'non git changed\n' > target-nongit/docs/token-notes.md
out=$(printf '%s' '{
  "changed_files": ["docs/token-notes.md"],
  "affected_layers": ["Docs"],
  "verification_command": "non-git target smoke",
  "result": "passed",
  "quality_gates": {
    "scope": {"result": "PASS", "evidence": "docs/token-notes.md is the only changed target file and is allowed."},
    "correctness": {"result": "PASS", "evidence": "nongit-target-smoke passed."},
    "traceability": {"result": "PASS", "evidence": "non-git target snapshot, diff, receipt and seal are recorded."},
    "disclosure": {"result": "PASS", "evidence": "No skipped checks or limitations in this target fixture."}
  },
  "claims": [
    {"claim": "The controlled non-git target docs smoke passed for docs/token-notes.md.", "evidence_refs": ["nongit-target-smoke", "quality_gates.correctness"]}
  ]
}' | python3 "$G" os-close)
grep -q '"result": "os_closed"' <<< "$out"
out=$(python3 "$G" os-verify)
grep -q '"result": "os_verify_passed"' <<< "$out"
printf 'non git tamper\n' >> target-nongit/docs/token-notes.md
out=$(python3 "$G" os-verify)
grep -q '"result": "os_verify_failed"' <<< "$out"
grep -q 'target.changed_files' <<< "$out"

echo "== target janitor rejects known artifacts in external target =="
ARTIFACT_TARGET="$(mktemp -d)"
mkdir -p "$ARTIFACT_TARGET/docs"
printf 'artifact baseline\n' > "$ARTIFACT_TARGET/docs/artifact.md"
printf 'local artifact\n' > "$ARTIFACT_TARGET/.DS_Store"
cat > artifact-target-request.json <<JSON
{
  "task_id": "lc7-target-janitor",
  "intent": "Target janitor fixture",
  "target_repo": "$ARTIFACT_TARGET",
  "task_signal": "not_applicable",
  "affected_layers": ["Docs"],
  "target_paths": ["docs/artifact.md"],
  "expected_evidence": ["target janitor smoke"],
  "out_of_scope_paths": []
}
JSON
python3 "$G" os-start artifact-target-request.json >/dev/null
cat > artifact-target-evidence.json <<'JSON'
{
  "id": "target-janitor-smoke",
  "kind": "command",
  "command": "target janitor smoke",
  "result": "passed",
  "summary": "target janitor fixture command passed"
}
JSON
python3 "$G" os-evidence artifact-target-evidence.json >/dev/null
printf 'artifact changed\n' > "$ARTIFACT_TARGET/docs/artifact.md"
out=$(printf '%s' '{
  "changed_files": ["docs/artifact.md"],
  "affected_layers": ["Docs"],
  "verification_command": "target janitor smoke",
  "result": "passed",
  "quality_gates": {
    "scope": {"result": "PASS", "evidence": "docs/artifact.md is within target scope."},
    "correctness": {"result": "PASS", "evidence": "target-janitor-smoke passed."},
    "traceability": {"result": "PASS", "evidence": "target snapshot and receipt are recorded."},
    "disclosure": {"result": "PASS", "evidence": "Target artifact should be disclosed by janitor."}
  },
  "claims": [
    {"claim": "The target janitor smoke command passed before artifact cleanup.", "evidence_refs": ["target-janitor-smoke", "quality_gates.correctness"]}
  ]
}' | python3 "$G" os-close)
grep -q '"result": "os_close_rejected"' <<< "$out"
grep -q "target artifact janitor found local artifacts" <<< "$out"
rm -rf "$ARTIFACT_TARGET"

echo "== design token profile rejects full-token overclaim and accepts qualified coverage =="
mkdir -p target-tokens/docs
printf 'token baseline\n' > target-tokens/docs/tokens.md
cat > token-request.json <<JSON
{
  "task_id": "lc7-design-tokens",
  "intent": "Design token evidence profile fixture",
  "target_repo": "$PWD/target-tokens",
  "task_signal": "UI/component",
  "affected_layers": ["Docs"],
  "target_paths": ["docs/tokens.md"],
  "evidence_profile": "design_tokens",
  "expected_evidence": ["token typecheck"],
  "out_of_scope_paths": []
}
JSON
python3 "$G" os-start token-request.json >/dev/null
cat > figma-node.json <<'JSON'
{
  "id": "figma-token-node",
  "kind": "figma_node",
  "fileKey": "FILE123",
  "nodeId": "1:2",
  "summary": "Figma token source node sampled for semantic content tokens"
}
JSON
python3 "$G" os-evidence figma-node.json >/dev/null
cat > token-coverage.json <<'JSON'
{
  "id": "token-coverage",
  "kind": "design_token_coverage",
  "fileKey": "FILE123",
  "nodeId": "1:2",
  "coverage_scope": "sampled_frames",
  "covered_groups": ["semantic.content", "dimension.scale"],
  "generated_surfaces": ["ts", "css_vars"],
  "token_count": 12,
  "verification": "token typecheck passed",
  "summary": "Semantic content tokens and dimension scale were generated from sampled frames"
}
JSON
python3 "$G" os-evidence token-coverage.json >/dev/null
printf 'token changed\n' > target-tokens/docs/tokens.md
bad=$(printf '%s' '{
  "changed_files": ["docs/tokens.md"],
  "affected_layers": ["Docs"],
  "evidence_profile": "design_tokens",
  "verification_command": "token typecheck",
  "result": "passed",
  "quality_gates": {
    "scope": {"result": "PASS", "evidence": "docs/tokens.md is within target scope."},
    "correctness": {"result": "PASS", "evidence": "token typecheck and token-coverage recorded."},
    "traceability": {"result": "PASS", "evidence": "Figma node, token coverage, target seal and receipt are recorded."},
    "disclosure": {"result": "PASS", "evidence": "Coverage scope is sampled_frames."},
    "design_token_coverage": {"result": "PASS", "evidence": "token-coverage covers semantic.content and dimension.scale from FILE123 node 1:2."}
  },
  "claims": [
    {"claim": "Full design tokens were implemented.", "evidence_refs": ["token-coverage", "figma-token-node"]}
  ]
}' | python3 "$G" os-close)
grep -q '"result": "os_close_rejected"' <<< "$bad"
grep -q "full design-token coverage" <<< "$bad"
good=$(printf '%s' '{
  "changed_files": ["docs/tokens.md"],
  "affected_layers": ["Docs"],
  "evidence_profile": "design_tokens",
  "verification_command": "token typecheck",
  "result": "passed",
  "quality_gates": {
    "scope": {"result": "PASS", "evidence": "docs/tokens.md is within target scope."},
    "correctness": {"result": "PASS", "evidence": "token typecheck and token-coverage recorded."},
    "traceability": {"result": "PASS", "evidence": "Figma node, token coverage, target seal and receipt are recorded."},
    "disclosure": {"result": "PASS", "evidence": "Full Figma variable library enumeration is not claimed."},
    "design_token_coverage": {"result": "PASS", "evidence": "token-coverage covers semantic.content and dimension.scale from FILE123 node 1:2."}
  },
  "claims": [
    {"claim": "Semantic content tokens and dimension scale from FILE123 node 1:2 were implemented; full Figma variable library enumeration is not claimed.", "evidence_refs": ["token-coverage", "figma-token-node", "quality_gates.design_token_coverage"]}
  ]
}' | python3 "$G" os-close)
grep -q '"result": "os_closed"' <<< "$good"
