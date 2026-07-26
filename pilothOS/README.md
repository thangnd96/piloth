# PilothOS

PilothOS là một **Agentic Operating System** trung lập với model, dùng để tổ chức Identity, Rules, Memory, Knowledge, Skills, Runtime, Agents và Tools thành một hệ thống có thể vận hành, kiểm chứng và bảo trì lâu dài.

## Distribution Model

Đây là **verified baseline** của PilothOS (version hiện hành: xem `CHANGELOG.md` cùng thư mục): kiến trúc và enforcement đã được kiểm chứng qua vận hành thực tế — phạm vi kiểm chứng và giới hạn đã biết: xem `pilothOS/VALIDATION.md`; thay đổi theo version: xem `CHANGELOG.md`. `CLAUDE.md` ship với Persona/Mục tiêu dạng placeholder — `/pilothos-init` sẽ điền cho implementation của bạn.

`rot/review-log.md` và `memory/lessons-learned.md` ship **trống có chủ đích**: lịch sử review và bài học thuộc về từng implementation, được tích lũy qua vận hành thật — đúng nguyên tắc "Rule sinh từ incident thật". Việc ghi log được **enforce tự động**: Stop hook chặn kết thúc phiên có thay đổi file cho đến khi agent append log hoặc tuyên bố rõ không có finding.

PilothOS được phân phối theo hai lớp:

1. **OS Source of Truth**: toàn bộ kiến trúc, rules, runtime, rot và contracts nằm trong `pilothOS/`.
2. **Native Tool Adapters**: `.claude/` là adapter duy nhất Piloth ship — bridge để Claude Code đọc được PilothOS, không định nghĩa lại source of truth. Harness khác đọc `AGENTS.md`. Nếu project đã có `.cursor/`, `.codex/` hay `.antigravity/` của riêng nó, đó là tài sản consumer: Piloth index chúng và không ghi đè.

PilothOS là control plane. Tài sản consumer như skills, hooks, tools, MCP,
commands, design system và project conventions là userland apps/drivers:
PilothOS điều phối và ghi evidence, không sở hữu hoặc overwrite.

Nếu adapter mâu thuẫn với `pilothOS/`, ưu tiên `pilothOS/` và ghi finding vào `pilothOS/rot/review-log.md`.

Các file trong `pilothOS/templates/` chỉ là template dùng khi tạo artifact mới; template không được xem là operational state cho đến khi đã điền đủ dữ liệu bắt buộc.

## Bắt đầu

**Cài đặt:** qua plugin Piloth (`/piloth:init` trong Claude Code) hoặc thủ công:
`scripts/stage.sh /đường/dẫn/project` từ bản clone repo, rồi làm theo
`pilothOS/skills/workflow/pilothos-init/SKILL.md`. Installer chạy theo mô hình
**plan/apply**: bạn approve đúng file `install-plan.json`, engine deterministic
thực thi đúng file đó — có backup, manifest, auto-rollback, self-prune sau khi xong.
Gỡ: `/pilothos-uninstall` (phục hồi từ manifest).

Các bước thủ công tương đương:

1. Đọc `CLAUDE.md` hoặc `AGENTS.md` tùy tool đang dùng.
2. Đi vào `pilothOS/bootstrap.md`.
3. Kiểm tra `pilothOS/rot/registry.md`.
4. Nạp context theo progressive loading; không nạp toàn bộ repo mặc định.

## Ranh giới phân phối

Bản ship gồm: kernel (`pilothOS/`), engine + guard, skills, payloads, adapters,
tài liệu consumer — đầy đủ để vận hành và tự học trong project của bạn.
KHÔNG ship: lịch sử phát triển, lessons nội bộ của vendor, heuristics chưa chín —
chúng thuộc vendor-side và quay lại bản phân phối qua kênh `upstream`.
License: xem `LICENSE`.

## Cấu trúc

```text
CLAUDE.md                  # Identity cho Claude Code
AGENTS.md                  # Entry point cho harness đọc chuẩn AGENTS.md
.claude/                   # Claude Code adapter
pilothOS/
├── bootstrap.md           # Entry point và context routing
├── PilothOS.md            # Hiến pháp kiến trúc
├── VALIDATION.md          # Giới hạn đã biết và điều kiện của mọi claim
├── dist-manifest.json     # SSOT về tính đầy đủ của bản phân phối
├── rot/                   # Registry và lịch sử review
├── rules/                 # POLICY
├── memory/                # CONTEXT
├── knowledge/             # FACT
├── skills/                # CAPABILITY
├── runtime/               # ORCHESTRATION
├── agents/                # EXECUTION
├── tools/                 # INTEGRATION
├── scripts/               # Guard engine và installer engine
├── governance/            # Kiểm soát vận hành cắt ngang
├── evaluation/            # Quality gates và evidence
├── templates/             # Contract mẫu
```

Mapping giữa PilothOS và từng native tool nằm ở adapter directory tại root của
project (`.claude/`, `.cursor/`, `.codex/`, `.antigravity/`), không nằm trong
`pilothOS/`.

## Layer Index Contract

Mỗi `index.md` của layer hoặc cross-cutting system PHẢI có đủ ba mục sau —
chúng định nghĩa ranh giới mà progressive context loading dựa vào để route:

1. `Purpose` — layer này tồn tại để làm gì
2. `Responsibilities` — thuộc về nó
3. `Non-Responsibilities` — KHÔNG thuộc về nó

Gate: bộ test doc-contract trong repo Piloth (không ship kèm bản cài).

Khuyến nghị thêm khi có nội dung tương ứng: `Contents`, `Convention`,
`Review Checklist`. Bản trước liệt kê cả sáu mục là bắt buộc "khi áp dụng" —
mệnh đề thoát đó khiến không gate nào kiểm được, và 5/10 index đã lặng lẽ dùng nó.

`Identity` là ngoại lệ: Identity nằm trong `CLAUDE.md`, còn checklist review của Identity nằm trong `pilothOS/rot/review-guide.md` để giữ đúng ranh giới layer.

## Nguyên tắc mở rộng

- Không tạo Rule, Skill, Agent hoặc Team mới nếu chưa có task thật, incident thật hoặc nhu cầu lặp lại.
- Không tạo cấu hình song song nếu không có tool hoặc script đọc nó.
- Không duplicate source of truth giữa adapter và `pilothOS/`.
- Mọi mở rộng phải có Evidence và được ghi lại khi có tác động kiến trúc.

> Stable things guide change. Change must never redefine stability.
