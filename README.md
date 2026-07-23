# Piloth

> **An Agentic Operating System for reliable software delivery.**

Piloth biến AI coding agent từ một công cụ viết code thành một hệ thống làm việc có **kiến trúc, quy tắc, bằng chứng, kiểm chứng và khả năng tự cải tiến**.

Piloth cung cấp một kernel thống nhất cho **Claude Code, Codex, Cursor và Antigravity**, để các agent cùng tuân theo một cách làm việc thay vì mỗi công cụ tự suy diễn quy trình riêng.

```text
Task
  ↓
Understand
  ↓
Plan
  ↓
Execute
  ↓
Review
  ↓
Repair
  ↓
Deliver with Evidence
```

## Quickstart

### Claude Code

Đăng ký marketplace và cài plugin:

```text
/plugin marketplace add thangnd96/piloth
/plugin install piloth@piloth-marketplace
```

Khởi động một Claude Code session mới trong project, sau đó chạy:

```text
/piloth:init
```

Piloth sẽ audit project, đề xuất install plan và chỉ thay đổi file sau khi bạn phê duyệt chính xác plan đó.

Sau khi hoàn tất, xác nhận installation:

```bash
python3 pilothOS/scripts/pilothos_guard.py self-check
```

Kết quả mong đợi:

```text
SELF-CHECK PASSED
```

### Codex, Cursor và Antigravity

Clone Piloth và stage vào project:

```bash
git clone https://github.com/thangnd96/piloth /tmp/piloth
/tmp/piloth/scripts/stage.sh /path/to/your/project
```

Mở coding agent trong project và yêu cầu agent thực hiện skill:

```text
pilothOS/skills/workflow/pilothos-init/SKILL.md
```

Không apply thay đổi trước khi review và phê duyệt install plan.

> Installation khác nhau theo từng coding-agent harness. Nếu sử dụng nhiều harness trong cùng project, hãy kích hoạt adapter tương ứng cho từng harness.

## Piloth làm gì?

Coding agents thường thất bại không phải vì thiếu khả năng viết code, mà vì thiếu một operating model nhất quán:

- bắt đầu code trước khi hiểu đúng yêu cầu;
- tự tạo assumptions, policies hoặc conventions;
- thay đổi quá phạm vi;
- đặt logic sai layer;
- tuyên bố hoàn thành khi chưa có Evidence;
- lặp lại lỗi cũ vì lessons không được ghi nhận;
- nhiều agent phối hợp nhưng không có handoff và stop condition rõ ràng.

Piloth giải quyết các vấn đề này bằng một **Agentic Operating System** và các adapter mỏng:

```text
Claude Code · Codex · Cursor · Antigravity
                     ↓
                Native Adapters
                     ↓
                   PilothOS
                     ↓
Identity · Rules · Memory · Knowledge · Skills · Runtime · Agents · Tools
```

`pilothOS/` là **Single Source of Truth**. Adapter chỉ giúp từng công cụ native-load đúng instruction, skill, hook hoặc agent contract; adapter không fork business logic của PilothOS.

PilothOS là **control plane**: nó inventory, classify, route, sandbox, observe
và learn từ tài sản consumer. Skills, hooks, tools, MCP, design system và
convention riêng của consumer là **userland apps/drivers**; PilothOS không sở
hữu hoặc overwrite chúng.

## Cách Piloth hoạt động

Piloth bắt đầu từ lúc coding agent nhận task. Thay vì nhảy ngay vào implementation, agent phải xác định mục tiêu, assumptions, layer bị ảnh hưởng và tiêu chí thành công.

### 1. Bootstrap đúng context

Agent đọc entry point của harness (`CLAUDE.md`, `AGENTS.md` hoặc native adapter), sau đó đi vào `pilothOS/bootstrap.md`.

Bootstrap:

1. đọc Constitution của PilothOS;
2. kiểm tra Rot Registry;
3. nạp các Rules bắt buộc;
4. xác định Runtime lifecycle;
5. phân loại layer bị ảnh hưởng;
6. chỉ nạp các tài liệu cần cho task hiện tại.

### 2. Làm việc theo lifecycle

```text
Intake
  ↓
Plan
  ↓
Execute
  ↓
Review
  ↓
Repair
  ↓
Deliver
```

- **Intake** — hiểu scope, constraints, assumptions và affected layers.
- **Plan** — chia task thành bước nhỏ với success criteria kiểm chứng được.
- **Execute** — thực hiện thay đổi tối thiểu, không refactor ngoài phạm vi.
- **Review** — kiểm tra specification, code quality, tests, risk và Evidence.
- **Repair** — xử lý finding theo root cause rồi verify lại.
- **Deliver** — báo cáo kết quả, Evidence, limitations và các finding còn lại.

### 3. Progressive context loading

Piloth không yêu cầu agent đọc toàn bộ repository hoặc toàn bộ PilothOS cho mọi task.

```text
Task
  ↓
Classify affected layers
  ↓
Load relevant index.md
  ↓
Load referenced rules / skills / knowledge
  ↓
Execute and verify
```

Cơ chế này giảm token cost, hạn chế instruction conflict và giữ context tập trung vào công việc hiện tại.

### 4. Verify trước khi tuyên bố hoàn thành

Piloth phân biệt rõ:

- **Claim** — agent nói rằng việc đã xong;
- **Evidence** — test output, receipt, diff, log hoặc artifact chứng minh việc đã xong.

Task chỉ được Deliver khi các quality gates liên quan đã đạt hoặc limitation được khai báo minh bạch.

### 5. Học từ lỗi thật

Piloth không thêm Rule, Skill hoặc Agent chỉ vì “có thể sẽ cần”.

- Lỗi lặp lại → cân nhắc promote thành **Rule** hoặc **Hook**.
- Workflow lặp lại → cân nhắc promote thành **Skill**.
- Context lâu dài → đưa vào **Knowledge**.
- Bài học từ vận hành → ghi vào **Memory / Review Log**.
- Role chỉ được tách thành Agent khi task thật chứng minh nhu cầu.

## Installation workflow

`/piloth:init` sử dụng quy trình transactional thay vì để AI chỉnh file tùy ý:

```text
Stage
  ↓
Preflight
  ↓
Detect greenfield / brownfield
  ↓
Audit project
  ↓
Collect Persona, Goals and Adapters
  ↓
Generate install-plan.json
  ↓
Dry-run
  ↓
Consumer approves exact plan
  ↓
Transactional Apply
  ↓
Verify receipt + completeness
  ↓
Self-check + log
```

Installer:

- không ghi đè file consumer một cách âm thầm;
- tạo backup và manifest trước khi sửa;
- thực thi đúng plan đã được approve;
- tạo receipt để truy vết;
- rollback tự động nếu postcondition thất bại;
- hỗ trợ uninstall dựa trên install manifest thay vì xóa mù.

Chi tiết: [workflow.md](docs/workflow.md)

## Agent Teams

Piloth không mặc định biến mọi task thành multi-agent workflow.

Agent Team chỉ được kích hoạt khi task có đủ độ phức tạp hoặc cần vai trò độc lập để tạo, đánh giá và ra quyết định.

Team mặc định đã được migrate và validate là **Piloth Team**:

| Role | Trách nhiệm |
|---|---|
| Lead Solution Architect | Làm rõ mục tiêu, điều phối team, sở hữu quyết định cuối cùng |
| Solution Generator | Tạo phương án và giải pháp khả thi |
| Critical Evaluator | Phản biện assumptions, risks, quality và Evidence |

Mỗi handoff phải chứa:

- decision hoặc output;
- Evidence;
- risks;
- unresolved questions;
- next owner.

Runtime sở hữu orchestration. Agent definitions chỉ sở hữu execution role.

## Khả năng chính

- **Model-neutral kernel** — một hệ thống vận hành dùng cho nhiều coding agents.
- **Native adapters** — Claude Code, Codex, Cursor và Antigravity.
- **Transactional installation** — plan, approval, backup, manifest, receipt và rollback.
- **Progressive context loading** — chỉ nạp đúng context cần thiết.
- **Measurable token optimization** — `context-budget` đo footprint context (bytes/token) mỗi task nạp vs full kernel; routing tiết kiệm ~88–91% context. Xem [token-optimization.md](docs/token-optimization.md).
- **Rules & Hooks** — instruction-level policies và mechanical enforcement khi có thể.
- **Evidence-first delivery** — verify trước khi claim completion.
- **Governed Visual Review** — companion tool review trực quan (annotron-faithful, zero-dep) + gate `human_review`: structured feedback thành evidence, `os-close` chặn Seal khi chưa duyệt. Bind `--task`/`--govern` để thêm pipeline/gate stepper + option-picker. Xem `pilothOS/tools/review/`.
- **Prototype phase & Discovery gate** — skill `piloth-prototype` sinh ≥2 UI options rồi human chọn (tái dùng `human_review`, gate `prototype` kiểm invariant); skill `piloth-discovery` hỏi-xác nhận câu hỏi mở đầu phase, fold vào contract. Recipe `phase_plan_suggestion` khuyến nghị (advisory, không auto-enable).
- **Rot Management** — cadence, next due, owner, checklist và append-only review log.
- **Agent Teams** — composition, role contract, handoff và stop condition.
- **Safe uninstall** — khôi phục dựa trên installation evidence.

## Hỗ trợ công cụ

| Capability | Claude Code | Codex | Cursor | Antigravity |
|---|:---:|:---:|:---:|:---:|
| PilothOS kernel | ✅ | ✅ | ✅ | ✅ |
| Identity, Rules, Knowledge và Skills | ✅ | ✅ | ✅ | ✅ |
| Native adapter | ✅ | ✅ | ✅ | ✅ |
| Transactional init / uninstall | ✅ | ✅ | ✅ | ✅ |
| Native hooks và statusline | ✅ | Contract | Contract | Contract |
| Plugin UI installation | ✅ | — | — | — |

`Contract` nghĩa là harness đọc và tuân theo PilothOS adapter, nhưng chưa có cùng mức native mechanical enforcement như Claude Code.

## Cấu trúc repository

```text
piloth/
├── .claude-plugin/       # Plugin và marketplace manifests
├── adapters/             # Native adapters theo từng harness
├── commands/             # Plugin commands: init, uninstall
├── scripts/              # Distribution, staging và release tooling
├── tests/                # Engine, install và lifecycle suites
└── pilothOS/             # Agentic Operating System kernel
    ├── bootstrap.md
    ├── PilothOS.md
    ├── rules/
    ├── memory/
    ├── knowledge/
    ├── skills/
    ├── runtime/
    ├── agents/
    ├── tools/
    ├── governance/
    ├── evaluation/
    ├── rot/
    └── scripts/
```

### Bảy layer cốt lõi

| Layer | Responsibility |
|---|---|
| Identity | WHY |
| Rules & Hooks | POLICY |
| Memory & Knowledge | CONTEXT + FACT |
| Skills | CAPABILITY |
| Runtime | ORCHESTRATION |
| Agents | EXECUTION |
| Tools / MCP / CLI | INTEGRATION |

Governance, Evaluation, Rot Management và Adapters là các hệ thống cắt ngang, không thay thế trách nhiệm của bảy layer cốt lõi.

Chi tiết: [structure.md](docs/structure.md)

## Các nguyên tắc

- **Evidence over claims** — không tuyên bố thành công khi chưa kiểm chứng.
- **Simplicity over speculation** — không tạo capability chưa có nhu cầu thật.
- **Minimal, surgical changes** — mọi dòng thay đổi phải truy về task.
- **Correct layer ownership** — logic phải nằm đúng responsibility.
- **Stable guides change** — layer biến động không được định nghĩa lại layer ổn định.
- **Learn from incidents** — lỗi thật phải tạo ra improvement có thể truy vết.
- **Mechanically enforce what can be enforced** — phần cần judgment phải được khai báo trung thực là contract.

## Updating

Với Claude Code, cập nhật plugin qua Plugin UI (hoặc `/plugin update piloth`) và mở session mới.

Sau đó nâng bản PilothOS đã init trong project lên version mới — không cần re-init:

```text
/piloth:update
```

`update` re-stage kernel + adapter từ nguồn plugin (`stage.sh --upgrade`) rồi đóng dấu version mới qua engine (`mode=upgrade`); GIỮ nguyên `CLAUDE.md`/`AGENTS.md`/`.gitignore`/`.claude/settings.json` + state. Chi tiết: `pilothOS/skills/workflow/pilothos-update/SKILL.md`.

Trước khi nâng cấp: đọc `CHANGELOG.md` + migration notes, bảo đảm working tree sạch; sau update chạy `self-check`. Không ghi đè installation hiện tại bằng cách copy file thủ công.

## Quản lý tool adapters (sau init)

Chọn thiếu adapter khi init, hoặc muốn bật thêm sau này? Dùng lệnh (không cần re-init):

```text
/piloth:adapter
```

ADD copy targeted đúng adapter thiếu (`cursor`/`codex`/`antigravity`) từ nguồn Piloth,
không đụng kernel; REMOVE qua engine (`remove_path`, có backup, uninstall khôi phục được).
`claude` là adapter nền, luôn giữ. Chi tiết: `pilothOS/skills/workflow/pilothos-adapter/SKILL.md`.

## Uninstall

Trong Claude Code:

```text
/piloth:uninstall
```

Hoặc thực hiện uninstall workflow được định nghĩa trong command:

```text
commands/uninstall.md
```

Uninstaller sử dụng manifest và backup của installation để khôi phục file consumer an toàn.

## Documentation

- [structure.md](docs/structure.md) — cấu trúc plugin, kernel, adapters và project sau khi cài.
- [workflow.md](docs/workflow.md) — installation, bootstrap, task lifecycle, hooks, teams và uninstall.
- [token-optimization.md](docs/token-optimization.md) — đo và giảm token: routing, preset, adaptive mode.
- [`pilothOS/PilothOS.md`](pilothOS/PilothOS.md) — Constitution của Agentic Operating System.
- [`pilothOS/VALIDATION.md`](pilothOS/VALIDATION.md) — những capability đã được validate và giới hạn enforcement.
- [`CHANGELOG.md`](CHANGELOG.md) — lịch sử release.

## Contributing

Piloth ưu tiên asset được chứng minh bằng vận hành thật.

Trước khi thêm hoặc sửa Rule, Skill, Agent, Hook hay Runtime contract:

1. cung cấp task, incident hoặc repeated need làm Evidence;
2. xác định đúng layer chịu trách nhiệm;
3. viết test hoặc verification scenario tái hiện hành vi;
4. thực hiện thay đổi tối thiểu;
5. chạy engine, install và lifecycle suites liên quan;
6. cập nhật review log hoặc release documentation.

Không thêm capability generic chỉ để làm repository “đầy đủ hơn”.

## License

Xem [LICENSE](LICENSE) để biết điều khoản sử dụng và phân phối.
