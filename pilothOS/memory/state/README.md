# Memory State

Trạng thái task đang chạy. Chỉ tạo file khi cần lưu context xuyên session; mỗi
file phải có thời điểm, phạm vi và điều kiện hết hạn.

## Repo-Local Runtime State

| Path | Owner | Contract |
|---|---|---|
| `scheduler-history.jsonl` | Scheduler | Append-only route/test/tool summaries. No secrets, no full command output. |
| `receipt-seals.jsonl` | OS control plane | Append-only receipt/contract/diff/file hash seals. No secrets, no command output. |
| `os-runs/<task-id>/state.json` | OS control plane | Repo-local lifecycle state from `os-start` through `os-close`. |
| `os-runs/<task-id>/evidence.jsonl` | OS control plane | Sanitized evidence refs; no full command output or secrets. |
| `team-runs/<task-id>/team-contract.json` | Team control plane | Team, roles, permissions, allowed paths, handoff artifacts and stop condition. |
| `team-runs/<task-id>/team-receipt.json` | Team control plane | Role outputs, handoff paths, QA verdict, repair loop count and final lead decision. |

These files are repo-scoped memory. They must not contaminate another staged
repo, and adapters must not fork policy from this state.

Generated state files are local runtime artifacts and are ignored by git and
distribution. The policy source of truth remains in runtime docs, evaluation
docs and agent-team definitions, not copied scheduler, OS-run or team-run
history.

## Retention / cleanup

These runtime files accumulate; `state-janitor` keeps them bounded (see
`runtime/os-control-plane.md`). `os-close` runs the safe subset automatically
after sealing (fail-soft): it removes the heavy `os-runs/<task-id>/artifacts/`
of **sealed** runs outside retention — keeping `state.json`/`target-seal.json`
for audit — and tail-truncates `scheduler-history.jsonl`. Retention defaults:
keep the active run + last 10 runs + anything within 14 days
(`PILOTHOS_RETENTION_RUNS` / `PILOTHOS_RETENTION_DAYS`).

`receipt-seals.jsonl` is a hash-chained ledger and is **never** auto-pruned.
Growing kernel logs (`lessons-learned.md`, `review-log.md`) are rotated
losslessly to `*-archive.md` only via the explicit
`state-janitor --kernel-logs --fix`.
