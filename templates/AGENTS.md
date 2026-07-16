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

## Core Rules

- Keep changes surgical.
- Prefer simple solutions.
- Separate Fact, Assumption and Opinion.
- Use Evidence before conclusion.
- Do not refactor unrelated code.
- Report unrelated dead code instead of deleting it.
- Place responsibility in the correct PilothOS layer.
- Do not create new Rules, Skills, Agents or Teams without a real repeated need.

## Adapter Rule

`AGENTS.md` là adapter entry point, không phải source of truth. Khi mâu thuẫn, ưu tiên `pilothOS/` và ghi finding vào `pilothOS/rot/review-log.md`.
