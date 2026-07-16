# Piloth Team Setup — Workflow Skill

## Purpose

Scaffold hoặc cập nhật một **Agent Team** theo chuẩn PilothOS, bắt đầu từ `piloth-team` và có thể mở rộng thành team khác khi có Evidence vận hành thật.

Skill này được migrate từ asset team-setup đã validate, nhưng đã được chuẩn hóa lại theo PilothOS: role-name phản ánh trách nhiệm, team definition thuộc `agent-teams/`, orchestration thuộc `runtime/`, adapter native thuộc `.claude/` hoặc adapter tương ứng.

## Responsibilities

- Elicit yêu cầu tạo/cập nhật team theo từng stage.
- Tạo hoặc cập nhật team definition trong `pilothOS/agent-teams/`.
- Tạo role contracts trong `pilothOS/agents/team-roles/` khi cần.
- Tạo runtime skill hoặc adapter bridge cho tool cụ thể khi có yêu cầu thật.
- Bảo toàn nguyên tắc: không tạo team generic nếu chưa có Evidence.

## Non-Responsibilities

- Không dispatch task cho team đang tồn tại.
- Không chạy workflow implementation của team.
- Không cài MCP hoặc external tool.
- Không ghi đè `CLAUDE.md` ngoài adapter sentinel đã kiểm soát.
- Không tạo role dựa trên tên cá nhân; role phải dùng tên trách nhiệm.

## Activation

Dùng skill này khi user yêu cầu:

- Tạo hoặc cập nhật agent team.
- Setup team runtime cho Claude/Codex/Cursor/Antigravity.
- Migrate một team skill cũ sang chuẩn PilothOS.
- Chuẩn hóa Generator/Evaluator/Lead team contract.

Không dùng skill này cho task nhỏ hoặc task chỉ cần single agent.

## Inputs

- Team purpose.
- Team trigger phrases hoặc command name.
- Role composition.
- Task profile hoặc domain.
- Tool adapter target nếu cần native integration.
- Evidence chứng minh team cần tồn tại.

## Outputs

Tùy scope, skill có thể tạo hoặc cập nhật:

| Output | Layer |
|---|---|
| `pilothOS/agent-teams/<team>.md` | Agent Teams |
| `pilothOS/agents/team-roles/*.md` | Agents |
| `pilothOS/runtime/team-orchestration.md` | Runtime |
| `pilothOS/skills/workflow/<skill>/SKILL.md` | Skills |
| `.claude/skills/<skill>/SKILL.md` | Claude adapter |
| `.claude/commands/<command>.md` | Claude adapter |
| `.claude/scripts/*.sh` | Claude adapter/tooling |

## Workflow

| Stage | Name | Evidence |
|---|---|---|
| 0 | Pre-flight | Existing team files, adapter support, scope |
| 1 | Team intent | Purpose, trigger, expected use cases |
| 2 | Team profile | Domain, stack, risk, complexity |
| 3 | Role composition | Lead, Generator, Evaluator, optional QA/Specialist |
| 4 | Boundary check | Non-responsibilities and layer ownership |
| 5 | Contract negotiation | Inputs/outputs/stop condition |
| 6 | Adapter decision | Whether native adapter is required |
| 7 | Generate/update files | Smallest necessary change |
| 8 | Verify | Files exist, no duplicate SSOT, routing works |
| 9 | Log | Append review-log or lessons-learned if architecture changed |

## Role Naming Rule

Role names must describe responsibility, not people.

| Forbidden style | Correct style |
|---|---|
| nickname cá nhân | `Solution Generator` |
| tên viết tắt cá nhân | `Critical Evaluator` |
| `member-1` | `Implementation Executor` |
| `member-2` | `QA Reviewer` |

## Strict Elicitation

When operating inside Claude Code and `AskUserQuestion` is available, every user-facing setup question should use it. If unavailable, use batched text questions and mark the fallback in the report.

## Verification

Before delivery:

```bash
find pilothOS/agent-teams -maxdepth 1 -type f -name "*.md"
find pilothOS/agents/team-roles -maxdepth 1 -type f -name "*.md"
```

Before delivery, confirm that active team and role definitions use responsibility-based names instead of nickname, member number, or opaque personal identifiers. Historical references are allowed only in append-only logs when they record the actual name used at that time.

## Supporting Files

Load only when needed:

| File | Purpose |
|---|---|
| `elicitation.md` | staged setup questions |
| `recommendation-matrix.md` | recommended options by profile/archetype |
| `role-archetypes.md` | role archetype definitions |
| `team-architecture-principles.md` | team design principles |
| `claude-adapter-sentinel.md` | controlled CLAUDE.md adapter sentinel template |
| `templates/` | generated file templates |
