# Skills — Index

## Purpose

Mô tả CAPABILITY có thể tái sử dụng.

## Responsibilities

- Workflow Skills: nhiều bước, cần judgment.
- Integration Skills: thao tác deterministic với hệ thống bên ngoài.

## Non-Responsibilities

- Không định nghĩa policy.
- Không sở hữu task lifecycle tổng thể.
- Không chứa credentials hoặc tool configuration bí mật.

## Contents

| Path | Type |
|---|---|
| `workflow/` | Quy trình reasoning nhiều bước |
| `workflow/piloth-team-setup/` | Skill scaffold/update Agent Team theo chuẩn PilothOS |
| `workflow/pilothos-init/` | Installer assets (payloads, manifest-spec) + /pilothos-uninstall. Docs init tự dọn sau khi cài (self-prune) |
| `integration/` | Wrapper deterministic cho API/CLI/MCP |

## Convention

Mỗi skill là một thư mục có `SKILL.md`. File chính phải ngắn; chi tiết nạp theo progressive disclosure.

## Review Checklist

- Workflow còn cần thiết, tối giản và có thể kiểm chứng không?
- Logic nào đang lặp giữa các Skill?
- Skill nào nên tách, hợp nhất hoặc loại bỏ?
- Integration Skill còn deterministic và khớp tool contract hiện tại không?

