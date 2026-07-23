#!/usr/bin/env bash
# lc11 — Prototype phase round-trip: os-start(requires_prototype) auto-adds the
# human_review gate; os-close is blocked until (a) >=2 prototype options + a
# chosen one are recorded as evidence AND (b) the human pick is approved+finalized
# via the reused human_review round-trip. Mirrors lc10.
set -euo pipefail
cd "$1"
G="pilothOS/scripts/pilothos_guard.py"

# Shared receipt: base gates + self-declared prototype + human_review PASS. The
# gates only truly pass when a >=2-option prototype evidence and an
# approve+finalized review artifact exist — so this receipt is rejected until both
# are in place (anti-checkbox).
RECEIPT='{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed",
  "quality_gates": {
    "scope": {"result": "PASS", "evidence": "README.md is the only changed file and is allowed by the OS contract."},
    "correctness": {"result": "PASS", "evidence": "docs smoke evidence ref docs-smoke passed."},
    "traceability": {"result": "PASS", "evidence": "os-start state, post-edit facts, receipt and seal are recorded."},
    "disclosure": {"result": "PASS", "evidence": "No skipped checks or limitations in this fixture."},
    "human_review": {"result": "PASS", "evidence": "human reviewer picked the prototype option via the review round-trip."},
    "prototype": {"result": "PASS", "evidence": "two options generated, option2 chosen, method artifacts."}
  },
  "claims": [
    {"claim": "Prototype produced two options; the human picked option2; docs smoke passed.", "evidence_refs": ["docs-smoke", "quality_gates.prototype", "quality_gates.human_review"]}
  ]
}'

echo "== os-start requires_prototype adds prototype + human_review gates =="
cat > pt-request.json <<'JSON'
{
  "task_id": "lc11-prototype",
  "intent": "Prototype phase round-trip fixture",
  "task_signal": "ui/component",
  "affected_layers": ["Docs"],
  "allowed_paths": ["README.md"],
  "expected_evidence": ["docs smoke"],
  "requires_prototype": true,
  "out_of_scope_paths": []
}
JSON
out=$(python3 "$G" os-start pt-request.json)
grep -q '"result": "os_started"' <<< "$out"
grep -q '"prototype"' <<< "$out"
grep -q '"human_review"' <<< "$out"

cat > evidence.json <<'JSON'
{ "id": "docs-smoke", "command": "docs smoke", "result": "passed", "summary": "README rendered in the prototype fixture" }
JSON
python3 "$G" os-evidence evidence.json >/dev/null
printf 'prototype fixture\n' > README.md
printf '%s' '{"tool_input":{"file_path":"README.md"}}' | python3 "$G" post-edit >/dev/null

echo "== os-close rejected when no prototype evidence backs the gate =="
out=$(printf '%s' "$RECEIPT" | python3 "$G" os-close)
grep -q '"result": "os_close_rejected"' <<< "$out"
grep -q "no prototype evidence recorded" <<< "$out"

echo "== prototype evidence with <2 options is rejected at record time =="
out=$(python3 "$G" os-evidence '{"task_id":"lc11-prototype","kind":"prototype","method":"artifacts","options":[{"id":"option1"}],"chosen":"option1"}')
grep -q '"result": "os_evidence_rejected"' <<< "$out"
grep -q ">=2 options" <<< "$out"

echo "== prototype evidence with a chosen id outside the options is rejected =="
out=$(python3 "$G" os-evidence '{"task_id":"lc11-prototype","kind":"prototype","method":"artifacts","options":[{"id":"option1"},{"id":"option2"}],"chosen":"option9"}')
grep -q '"result": "os_evidence_rejected"' <<< "$out"
grep -q "chosen must be one of" <<< "$out"

echo "== valid prototype evidence (2 options + chosen) is recorded =="
cat > proto.json <<'JSON'
{
  "task_id": "lc11-prototype",
  "kind": "prototype",
  "method": "artifacts",
  "prototype_doc": "pilothOS/memory/state/os-runs/lc11-prototype/artifacts/PROTOTYPE.md",
  "options": [
    {"id": "option1", "artifact": "PROTOTYPE-option1.html", "intent": "compact sidebar"},
    {"id": "option2", "artifact": "PROTOTYPE-option2.html", "intent": "top-nav wide"}
  ],
  "chosen": "option2"
}
JSON
python3 "$G" os-evidence proto.json >/dev/null

echo "== os-close still blocked without an approving human pick (reused human_review) =="
out=$(printf '%s' "$RECEIPT" | python3 "$G" os-close)
grep -q '"result": "os_close_rejected"' <<< "$out"
grep -q "review-feedback artifact" <<< "$out"

echo "== human pick (approve, finalized) lets os-close seal both gates =="
printf '%s' '{"task_id":"lc11-prototype","reviewer":"qa","review_round":1,"verdict":"approve","finalized":true,"findings":[{"id":"f1","location":{"gate":"scope"},"note":"chose option2","severity":"nit","disposition":"approve"}]}' | python3 "$G" review-feedback >/dev/null
out=$(printf '%s' "$RECEIPT" | python3 "$G" os-close)
grep -q '"result": "os_closed"' <<< "$out"
out=$(python3 "$G" os-verify)
grep -q '"result": "os_verify_passed"' <<< "$out"
