# Governance — Index

> Cross-cutting control system; không phải layer business mới.

## Purpose

Kiểm soát quyền hạn, rủi ro, chi phí, retry và escalation trong toàn bộ lifecycle.

## Responsibilities

- Approval gates.
- Permission boundaries.
- Budget và resource limits.
- Retry, timeout, cancellation và escalation.
- Human-in-the-loop cho thay đổi rủi ro cao.

## Non-Responsibilities

- Không định nghĩa business policy thuộc Rules.
- Không đánh giá chất lượng output; đó là Evaluation.
- Không thực thi task; đó là Agents.

## Contents

| File | Scope |
|---|---|
| `operational-controls.md` | Approval, budget, retry, timeout, escalation |
| `capability-manifest.json` | Fail-closed authority SSOT: per-capability paths/guard_modes/entitlements/enforcement_surface/writes_policy — read by `capability-list/check`, `authority-delta`, `os-inspect` (T0, preview) |

## Review Checklist

- Approval gate và permission boundary còn phù hợp với mức rủi ro không?
- Budget, timeout, retry và cancellation có giới hạn rõ ràng không?
- Escalation có đúng đối tượng và đủ Evidence không?
- Governance có đang lấn sang business policy hoặc quality evaluation không?

