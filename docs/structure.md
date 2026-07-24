# Piloth Structure

Tài liệu này mô tả cấu trúc của **Piloth v1.12.0** và trách nhiệm của từng khu vực trong repository cũng như trong project sau khi cài đặt.

## Tổng quan

Piloth gồm hai phần chính:

1. **Plugin Distribution** — package dùng để phân phối, cài đặt, kiểm thử và bảo trì Piloth.
2. **PilothOS Runtime** — kernel trung lập với model được stage vào project của consumer.

```text
Piloth Plugin
    ↓ stage / install
Consumer Project
    ↓ bootstrap
PilothOS Runtime
    ↓ route context + enforce rules
AI Coding Agent
```

## Repository Structure

```text
piloth/
├── .claude-plugin/           # Manifest cho Claude Code plugin/marketplace
├── adapters/                 # Native adapters cho từng AI coding tool
├── commands/                 # Plugin commands: init, update, adapter, uninstall
├── docs/                     # Tài liệu workflow và cấu trúc phân phối
├── pilothOS/                 # Kernel, runtime, rules và installer SSOT
├── scripts/                  # Staging, manifest và version tooling
├── templates/                # Root files được merge vào consumer project
├── tests/                    # Engine, install và lifecycle test suites
├── CHANGELOG.md              # Lịch sử release
├── LICENSE                   # MIT License của Piloth
└── README.md                 # Entry point của repository
```

## Plugin Distribution

### `.claude-plugin/`

Chứa metadata để Claude Code nhận diện Piloth như một plugin.

```text
.claude-plugin/
├── plugin.json               # Tên, version, mô tả, repository, license
└── marketplace.json          # Marketplace definition
```

### `commands/`

Các command được expose bởi plugin:

```text
commands/
├── init.md                   # /piloth:init
├── update.md                 # /piloth:update
├── adapter.md                # /piloth:adapter
└── uninstall.md              # /piloth:uninstall
```

Command chỉ là entry point mỏng. Logic cài đặt thực tế thuộc `pilothOS/skills/` và `pilothOS/scripts/`.

### `adapters/`

Bridge PilothOS sang cấu trúc native của từng tool:

```text
adapters/
├── claude/                   # Rules, commands, skills, agents cho Claude Code
├── cursor/                   # Cursor rules
├── codex/                    # Codex config / AGENTS contract
└── antigravity/              # Antigravity rules
```

Adapter không phải source of truth và không được định nghĩa lại policy. Khi có mâu thuẫn, `pilothOS/` luôn được ưu tiên.

### `scripts/`

Tooling cấp distribution:

| File | Trách nhiệm |
|---|---|
| `stage.sh` | Wrapper gọi staging engine |
| `stage.py` | Copy distribution vào consumer project theo cách deterministic, không ghi đè file đã có |
| `build_manifest.py` | Tạo `pilothOS/dist-manifest.json` |
| `bump-version.sh` | Bump version, regenerate manifest và audit version |

### `templates/`

Các file root được installer merge hoặc tạo cho consumer:

```text
templates/
├── CLAUDE.md                 # Identity contract cho Claude Code
├── AGENTS.md                 # Entry point chung cho tool hỗ trợ AGENTS.md
└── gitignore                 # Các artifact runtime cần ignore
```

### `tests/`

```text
tests/
├── engine/                   # Unit/contract tests cho installer engine
├── install/                  # Staging và installation tests
├── lifecycle/               # E2E: apply, receipt, rollback, prune, uninstall, guard
├── bin/                      # Test utilities, timeout runner
└── run_all.sh                # Gate tổng của release
```

## PilothOS Kernel

`pilothOS/` là **Single Source of Truth** của hệ thống.

```text
pilothOS/
├── PilothOS.md               # Constitution và kiến trúc cốt lõi
├── bootstrap.md              # Entry point và startup contract
├── VALIDATION.md             # Phạm vi đã kiểm chứng và giới hạn
├── dist-manifest.json        # Danh sách file bắt buộc của distribution
├── rules/                    # POLICY
├── memory/                   # CONTEXT
├── knowledge/                # FACT
├── skills/                   # CAPABILITY
├── runtime/                  # ORCHESTRATION
├── agents/                   # EXECUTION
├── tools/                    # INTEGRATION
├── agent-teams/              # Validated role compositions
├── governance/               # Permission, risk, approval, escalation
├── evaluation/               # Quality gates và Evidence
├── rot/                      # Health registry và review history
├── scripts/                  # Installer engine và guard enforcement
├── templates/                # Contract mẫu cho artifact mới
└── examples/                 # Ví dụ routing và sử dụng
```

## Seven Core Layers

```text
Identity
    ↓
Rules & Hooks
    ↓
Memory & Knowledge
    ↓
Skills
    ↓
Runtime
    ↓
Agents
    ↓
Tools / MCP / CLI
```

| Layer | Responsibility | Nội dung chính |
|---|---|---|
| Identity | WHY | Persona, mục tiêu, giá trị, ranh giới |
| Rules & Hooks | POLICY | Quy tắc hành vi và enforcement |
| Memory | CONTEXT | Trạng thái, lịch sử, lessons của implementation |
| Knowledge | FACT | Architecture, domain và standards |
| Skills | CAPABILITY | Workflow hoặc integration capability tái sử dụng |
| Runtime | ORCHESTRATION | Task lifecycle, context loading, team coordination |
| Agents | EXECUTION | Role, model, permission và responsibility |
| Tools | INTEGRATION | API, MCP, CLI và external services |

Các hệ thống cắt ngang:

- **Governance** — quyền hạn, approval, risk và escalation.
- **Evaluation** — quality gates, acceptance và Evidence.
- **Adapters** — bridge sang native tool.
- **Agent Teams** — composition tạm thời của nhiều role đã được validate.

## Operational Components

### `pilothOS/scripts/pilothos_installer.py`

Engine deterministic chịu trách nhiệm:

- validate install plan;
- simulate trước khi ghi;
- backup file hiện có;
- tạo manifest;
- apply đúng plan đã approve;
- self-check;
- auto-rollback khi lỗi;
- uninstall/restore từ manifest.

AI agent không được tự sửa file trong giai đoạn Apply.

### `pilothOS/scripts/pilothos_guard.py`

Guard cung cấp enforcement cơ học:

- preflight và detect project state;
- rot warning qua session/prompt/statusline;
- auto-log gate trước khi kết thúc session;
- self-check cấu hình hooks;
- log append có validation.

### `pilothOS/rot/`

```text
rot/
├── registry.md               # Scope, owner, last review, next due, status
├── review-guide.md           # Checklist review theo layer
└── review-log.md             # Append-only traceability log
```

### `pilothOS/memory/`

```text
memory/
├── state/                    # Project/runtime context
└── lessons-learned.md        # Lessons của consumer implementation
```

Các log này được ship trống có chủ đích và chỉ được điền từ vận hành thật.

## Structure Sau Khi Cài

Sau `/piloth:init` hoặc manual staging + install, consumer project có dạng:

```text
consumer-project/
├── CLAUDE.md                 # Identity đã được điền cho implementation
├── AGENTS.md                 # Entry point đa công cụ
├── .claude/                  # Claude native adapter + hooks
├── .cursor/                  # Cursor adapter nếu được chọn
├── .codex/                   # Codex adapter nếu được chọn
├── .antigravity/             # Antigravity adapter nếu được chọn
└── pilothOS/                 # Kernel, runtime, engine, logs và contracts
```

Installer tự dọn mặt tiền cài đặt một lần sau khi hoàn tất, nhưng giữ lại:

- kernel;
- installer engine;
- uninstall path;
- manifest và backup;
- guard;
- runtime và operational logs.

## Structural Rules

- `pilothOS/` là SSOT; adapter chỉ được tham chiếu.
- Mỗi thành phần phải nằm đúng layer responsibility.
- Không tạo file cấu hình nếu không có tool/script đọc nó.
- Không tạo Rule, Skill, Agent hoặc Team khi chưa có task, incident hoặc nhu cầu lặp lại thật.
- Logs của consumer không được chứa lessons nội bộ của vendor.
- File append-only không được sửa lịch sử đã ghi.
- Progressive loading phải route qua `index.md`, không import toàn bộ thư mục.
