# Init — Nhánh Brownfield (judgment guide)

> Merge semantics máy móc KHÔNG nằm ở đây — SSOT:
> `python3 pilothOS/scripts/pilothos_installer.py explain`.
> File này chỉ chứa phần cần judgment.

## Audit (việc của Claude)

1. Chạy baseline audit:

   ```bash
   python3 pilothOS/scripts/pilothos_guard.py audit-assets
   ```

   Output là bảng máy móc ban đầu. Claude bổ sung judgment cho asset bị thiếu,
   conflict hoặc capability không thể suy ra bằng path/config.
   Khi cần registry 9 cột để route trong runtime, chạy thêm:

   ```bash
   python3 pilothOS/scripts/pilothos_guard.py registry-assets
   ```

2. Liệt kê tài sản hiện có:
   - agent docs: `CLAUDE.md`, `AGENTS.md`;
   - adapters: `.claude`, `.cursor`, `.codex`, `.antigravity`;
   - skills, hooks, commands;
   - MCP/tool configs;
   - test/build/lint scripts;
   - design system docs/components/tokens;
   - project conventions.
3. Output audit bắt buộc:

   | Asset | Type | Capability | Owner | Risk | Proposed Piloth Handling |
   |---|---|---|---|---|---|
   | `path-or-config` | `skill|hook|tool|mcp|command|design-system|doc|convention|test-runner|build-runner` | short capability | consumer/piloth | low/medium/high | preserve/index/route/wrap/merge/needs-judgment/ignore |

4. Nguyên tắc: tài sản consumer **giữ nguyên vị trí** khi tool cần nó ở đó;
   đăng ký vào index layer là tùy chọn, hoãn được. Bỏ qua rác (`.DS_Store`...).
5. Không move/rewrite consumer assets trong install. Chỉ index hoặc merge
   settings/hook theo engine semantics.
6. CLAUDE.md consumer chứa khối nghi là policy/fact → THẢO LUẬN với user việc
   chuyển layer (đề xuất, chờ quyết) — việc chuyển làm sau init như task thường,
   KHÔNG nhét vào plan.
7. Xung đột nguyên tắc giữa AGENTS.md cũ và PilothOS → flag theo Instruction
   Precedence, chờ user quyết trước khi soạn plan.

## Soạn plan (các step điển hình)

> Staging đã copy đủ phần verbatim (adapters, bridges, pilothOS/); file
> consumer-owned (CLAUDE.md, AGENTS.md, .gitignore, settings, README...) được
> GIỮ NGUYÊN của consumer — plan xử lý phần merge dưới đây.

- `fill_placeholders → pilothOS/rot/registry.md` (baseline registry, luôn cần)

- `prepend_block identity-block.md → CLAUDE.md` (consumer đã có CLAUDE.md; fill áp ngay trong payload)
- `prepend_block startup-contract-block.md → AGENTS.md`
- `merge_settings settings.json → .claude/settings.json` — consumer có settings:
  env/statusLine conflict sẽ trả NEEDS-JUDGMENT; hỏi user rồi khai
  `options.statusline` hoặc thống nhất env, sửa plan, dry-run lại.
- `append_lines → .gitignore`
- `remove_path → .cursor|.codex|.antigravity` cho adapter user không chọn
- 5 step self-prune (xem SKILL.md — mặc định, bắt buộc)
- `write_marker` (cuối, bắt buộc)

## Heuristics tích lũy từ vận hành

> Mục này tự dày lên qua các lần adopt. Heuristic có giá trị ngoài phạm vi một
> project → khi ghi lesson, cột Promoted To ghi thêm `upstream`.

1. Điều kiện kèm approve phải được echo và xác nhận — nay structural: user
   approve chính file plan, engine chạy đúng file đó.
2. Bản sao Startup Contract phải ghi nguồn chuẩn — đã nướng trong payload.
3. Ghi log bằng tay gây lỗi — dùng `log-append`.
4. Payload chuẩn phải có sẵn — engine tự nạp, Claude không đọc payload.
5. Detect bỏ qua file rác hệ điều hành (`.DS_Store`, `Thumbs.db`).
