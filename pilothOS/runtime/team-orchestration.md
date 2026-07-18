# Team Orchestration

## Purpose

Định nghĩa protocol runtime khi một Agent Team được kích hoạt.

## Responsibilities

- Điều phối lifecycle của team execution.
- Chuẩn hóa handoff output.
- Xử lý conflict giữa role outputs.
- Dừng team loop khi đạt stop condition.

## Non-Responsibilities

- Không định nghĩa team nào tồn tại; team definitions thuộc `agent-teams/`.
- Không định nghĩa role identity; role thuộc `agents/` hoặc team contract.
- Không định nghĩa policy; policy thuộc Rules & Hooks.

## Handoff Protocol

Mỗi role output phải có:

- Role decision
- Evidence
- Risks
- Next handoff

## Control Plane

Multi-agent work is scheduled by PilothOS, not ad hoc conversation. Before role
work starts, record a team contract:

```bash
python3 pilothOS/scripts/pilothos_guard.py team-contract-write team-contract.json
```

Minimum contract fields:

- `task_id`
- `team`
- `roles`
- `allowed_paths`
- `role_permissions`
- `handoff_artifacts`
- `stop_condition`
- `max_repair_loops`
- `expected_evidence`

The `team` must reference an existing definition in `pilothOS/agent-teams/`.
Role permissions are mechanical where possible:

| Role Class | Default Boundary |
|---|---|
| Lead | plan/review/final decision |
| Executor | may edit only `allowed_paths` |
| Reviewer/QA | read/review only unless `edit` is explicitly granted |
| Specialist | advise or produce handoff artifacts, no mutation by default |

After role work, record:

```bash
python3 pilothOS/scripts/pilothos_guard.py team-receipt-write team-receipt.json
```

Team receipts must include role outputs, handoff paths, QA verdict when a QA
role exists, repair loop count and the final lead decision. Team use does not
replace the normal V1 deliver receipt; release-level Piloth work still needs
`receipt-write`.

`team-receipt-write` materializes a repo-local evidence bundle:

- `role-<role>.md`
- `qa-verdict.md`
- `handoff-summary.md`
- `final-lead-decision.md`
- `team-contract-summary.md`

If a role output records `edited_paths`, the role must have `edit` permission
and every edited path must match the team contract `allowed_paths`.

## Conflict Protocol

Nếu roles bất đồng:

1. Xác định assumption đang xung đột.
2. Yêu cầu Evidence từ mỗi role.
3. Ưu tiên phương án đơn giản hơn và có thể verify.
4. Escalate sang Governance hoặc user nếu conflict phụ thuộc constraint chưa rõ.

## Stop Conditions

- `max_repair_loops` reached.
- QA PASS, or QA FAIL documented with limitation.
- Lead final receipt recorded.
- Missing role permission or edit outside `allowed_paths` blocks mutation.
