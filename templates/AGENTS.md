# AGENTS.md

> Entry point chung cho Codex, Cursor-compatible agents và các tooling đọc `AGENTS.md`.

Bạn đang vận hành trong **PilothOS** (version: xem `PILOTHOS_VERSION` trong `.claude/settings.json` hoặc `CHANGELOG.md`).

## Startup Contract

Trước khi làm việc:

1. Đọc `pilothOS/bootstrap.md`.
2. Kiểm tra `pilothOS/rot/registry.md` cho scope quá hạn.
3. Xác định layer hoặc cross-cutting system bị ảnh hưởng.
4. Chỉ nạp `index.md` và file cần thiết cho task.
5. Nếu task cần nhiều vai trò, xem `pilothOS/agent-teams/index.md`; chỉ dùng team đã validate hoặc tạo team mới sau khi có Evidence thực tế.

## Mechanical Guard Contract

Với tool không có native hooks như Claude Code, gọi cùng guard CLI để đạt cùng
mức enforcement:

1. Trước khi sửa file: `python3 pilothOS/scripts/pilothos_guard.py contract-write <contract.json>` với context/reuse evidence.
2. Trước/sau mỗi edit nếu harness hỗ trợ: `pre-edit` / `post-edit` với JSON path.
3. Trước Deliver: `python3 pilothOS/scripts/pilothos_guard.py receipt-write <receipt.json>`.

## Core Rules

- Keep changes surgical.
- Prefer simple solutions.
- Separate Fact, Assumption and Opinion.
- Use Evidence before conclusion.
- Do not refactor unrelated code.
- Report unrelated dead code instead of deleting it.
- Place responsibility in the correct PilothOS layer.
- Do not create new Rules, Skills, Agents or Teams without a real repeated need.
- Do not bypass consumer skills, hooks, tools or design systems; route them through PilothOS.

## Adapter Rule

Use PilothOS as the OS entry point. `AGENTS.md` là adapter entry point, không
phải source of truth; do not fork policy trong adapter files. Khi mâu thuẫn, ưu
tiên `pilothOS/` và ghi finding vào `pilothOS/rot/review-log.md`.
