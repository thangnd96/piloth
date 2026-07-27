# Agents — Index

## Purpose

Định nghĩa EXECUTION units.

## Responsibilities

Mỗi Agent chỉ định nghĩa Role, Model, Permissions và Responsibilities.

## Non-Responsibilities

- Không chứa business policy hoặc business logic.
- Không sở hữu workflow tổng thể.
- Không trực tiếp định nghĩa tool contract.

## Agents

| Agent / Role Contract | Role | Model | File |
|---|---|---|---|
| Root Identity | AI System Architect and Maintainer identity | Model do runtime cung cấp | `CLAUDE.md` |
| Software Engineer | Default single-agent executor for clear, low-to-moderate risk tasks | Model do runtime cung cấp | `software-engineer.md` |

## Convention

Mỗi agent dùng template `templates/agent.md`. Model update kích hoạt review toàn layer.

## Review Checklist

- Role và responsibility của từng Agent còn cần thiết và không chồng chéo không?
- Model hiện tại còn phù hợp với capability, chi phí và rủi ro không?
- Permission có vượt quá phạm vi tối thiểu cần thiết không?
- Agent có đang chứa business policy, business logic hoặc workflow tổng thể không?

## Agent Team Boundary

Agent definitions mô tả role execution. Piloth không có lớp team orchestration: bản trước có `agent-teams/` nhưng qua 32 run thật không run nào contract một team, nên nó bị gỡ. Mặc định là single-agent.
