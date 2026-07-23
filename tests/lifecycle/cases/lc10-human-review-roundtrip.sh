#!/usr/bin/env bash
# lc10 — Governed human-review round-trip: os-start(requires_human_review) →
# review-request → os-close blocked without an approving finalized artifact →
# review-feedback rounds → os-close seals only on approve+finalized. Mirrors lc7.
set -euo pipefail
cd "$1"
G="pilothOS/scripts/pilothos_guard.py"
RUN="pilothOS/memory/state/os-runs/lc10-human-review"

# Shared receipt: full base gates + a self-declared human_review PASS. The gate
# only truly passes when a backing approve+finalized review-feedback exists — so
# this same receipt is rejected until the human artifact says approve.
RECEIPT='{
  "changed_files": ["README.md"],
  "affected_layers": ["Docs"],
  "verification_command": "docs smoke",
  "result": "passed",
  "quality_gates": {
    "scope": {"result": "PASS", "evidence": "README.md is the only changed file and is allowed by the OS contract."},
    "correctness": {"result": "PASS", "evidence": "docs smoke evidence ref docs-smoke passed."},
    "traceability": {"result": "PASS", "evidence": "os-start state, post-edit facts, receipt and seal are recorded."},
    "disclosure": {"result": "PASS", "evidence": "No skipped checks or limitations in this docs fixture."},
    "human_review": {"result": "PASS", "evidence": "human reviewer approved via the review round-trip artifact."}
  },
  "claims": [
    {"claim": "README docs smoke passed and human review approved the scoped docs change.", "evidence_refs": ["docs-smoke", "quality_gates.human_review"]}
  ]
}'

echo "== os-start with requires_human_review adds the human_review gate =="
cat > hr-request.json <<'JSON'
{
  "task_id": "lc10-human-review",
  "intent": "Human review round-trip fixture",
  "task_signal": "not_applicable",
  "affected_layers": ["Docs"],
  "allowed_paths": ["README.md"],
  "expected_evidence": ["docs smoke"],
  "requires_human_review": true,
  "out_of_scope_paths": []
}
JSON
out=$(python3 "$G" os-start hr-request.json)
grep -q '"result": "os_started"' <<< "$out"
grep -q '"human_review"' <<< "$out"

echo "== review-request emits the artifact carrying the human_review gate =="
out=$(python3 "$G" review-request lc10-human-review)
grep -q '"result": "review_requested"' <<< "$out"
grep -q '"human_review"' <<< "$out"
[ -f "$RUN/review-request.json" ]

cat > evidence.json <<'JSON'
{ "id": "docs-smoke", "command": "docs smoke", "result": "passed", "summary": "README rendered in the human-review fixture" }
JSON
python3 "$G" os-evidence evidence.json >/dev/null
printf 'human review fixture\n' > README.md
printf '%s' '{"tool_input":{"file_path":"README.md"}}' | python3 "$G" post-edit >/dev/null

echo "== os-close is rejected when no review-feedback artifact backs the gate =="
out=$(printf '%s' "$RECEIPT" | python3 "$G" os-close)
grep -q '"result": "os_close_rejected"' <<< "$out"
grep -q "review-feedback artifact" <<< "$out"

echo "== review-feedback round 1 (approve? no — blocker, finalized) keeps it rejected and routes Repair =="
printf '%s' '{"task_id":"lc10-human-review","reviewer":"qa","review_round":1,"verdict":"request-changes","finalized":true,"findings":[{"id":"f1","location":{"gate":"correctness"},"note":"edge case missing","severity":"blocker","disposition":"request-changes"}]}' | python3 "$G" review-feedback >/dev/null
out=$(printf '%s' "$RECEIPT" | python3 "$G" os-close)
grep -q '"result": "os_close_rejected"' <<< "$out"
grep -q "unresolved blocking findings" <<< "$out"
grep -q '"repair"' "$RUN/state.json"

echo "== review-feedback round 2 (approve, finalized, no blockers) lets os-close seal =="
printf '%s' '{"task_id":"lc10-human-review","reviewer":"qa","review_round":2,"verdict":"approve","finalized":true,"findings":[{"id":"f2","location":{"file":"README.md"},"note":"resolved","severity":"nit","disposition":"approve"}]}' | python3 "$G" review-feedback >/dev/null
out=$(printf '%s' "$RECEIPT" | python3 "$G" os-close)
grep -q '"result": "os_closed"' <<< "$out"
out=$(python3 "$G" os-verify)
grep -q '"result": "os_verify_passed"' <<< "$out"

echo "== review-verify reports the human_review gate PASS =="
out=$(python3 "$G" review-verify lc10-human-review)
grep -q '"result": "review_verified"' <<< "$out"

echo "== invalid feedback severity is rejected =="
out=$(printf '%s' '{"task_id":"lc10-human-review","verdict":"approve","finalized":true,"findings":[{"id":"f3","location":{"gate":"scope"},"note":"x","severity":"critical","disposition":"approve"}]}' | python3 "$G" review-feedback)
grep -q '"result": "review_feedback_rejected"' <<< "$out"
grep -q "blocker, major, minor, nit" <<< "$out"
