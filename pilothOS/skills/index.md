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
| `workflow/pilothos-adapter/` | Add/remove tool adapter (cursor/codex/antigravity) sau init — targeted, không đụng kernel |
| `workflow/pilothos-update/` | Upgrade bản đã init lên version plugin hiện tại (re-stage `--upgrade` + engine `mode=upgrade`), giữ customization + state |
| `workflow/piloth-discovery/` | Front-of-phase discovery gate: hỏi-xác nhận câu hỏi mở qua Governed Visual Review, fold quyết định vào contract/evidence |
| `workflow/piloth-prototype/` | Prototype phase: sinh ≥2 biến thể UI, human chọn qua human_review round-trip, ghi `PROTOTYPE.md` + evidence `kind=prototype` |
| `integration/` | Wrapper deterministic cho API/CLI/MCP |

## Convention

Mỗi skill là một thư mục có `SKILL.md`. File chính phải ngắn; chi tiết nạp theo progressive disclosure.

## Review Checklist

- Workflow còn cần thiết, tối giản và có thể kiểm chứng không?
- Logic nào đang lặp giữa các Skill?
- Skill nào nên tách, hợp nhất hoặc loại bỏ?
- Integration Skill còn deterministic và khớp tool contract hiện tại không?

