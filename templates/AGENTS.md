# AGENTS.md

> Entry point chung cho Codex, Cursor-compatible agents và các tooling đọc `AGENTS.md`.

Bạn đang vận hành trong **PilothOS** (version: xem `PILOTHOS_VERSION` trong `.claude/settings.json` hoặc `CHANGELOG.md`).

## Startup Contract

Đọc `pilothOS/bootstrap.md` và thực hiện đúng Startup Contract trong đó — đó là
bản duy nhất. File này không nhắc lại các bước; nhắc lại sẽ tạo bản sao thứ hai
tự do trôi khỏi bản gốc.

Riêng bước cuối cần nhấn vì tool không có Stop hook sẽ không được nhắc tự động:
**trước khi kết thúc một phiên có thay đổi file**, append log vào
`pilothOS/rot/review-log.md` hoặc `pilothOS/memory/lessons-learned.md`, hoặc nêu
rõ "Không có finding hoặc lesson cần ghi" kèm lý do.

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
Normal tasks start through `os-start`, which invokes the canonical
`evidence-route` decision and records adapter limitations honestly.
