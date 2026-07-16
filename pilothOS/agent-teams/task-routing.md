# Task Routing

> Routing này tối giản để tránh speculation. Default luôn là single agent.

| Task Signal | Routing |
|---|---|
| Task nhỏ, rõ, rủi ro thấp | Single Agent |
| Task cần generator/evaluator loop hoặc contract negotiation | `piloth-team.md` |
| Task cần team mới nhưng chưa có team phù hợp | Dùng single agent trước, ghi finding, chỉ tạo team sau khi có Evidence lặp lại |

## Rule

Không tạo routing table song song ở settings YAML. File này là routing source of truth cho Agent Teams.
