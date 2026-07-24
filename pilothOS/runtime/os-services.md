# OS Services Map (legibility)

## Purpose

Làm cho PilothOS **đọc ra là một OS** khi đặt cạnh một agent OS runtime (như
AOS): gọi đúng tên từng dịch vụ OS mà Piloth đã cung cấp. Đây là probe #6
("đọc ra là một OS mạch lạc?") trong lộ trình parity — áp dụng văn hoá tài liệu
của AOS (mỗi thành phần nêu OS-analog).

Xem toàn hệ thống một-lần-nhìn: `python3 pilothOS/scripts/pilothos_guard.py os-inspect`.

## Bản đồ dịch vụ

| Khái niệm OS | AOS (runtime) | PilothOS (governance) |
|---|---|---|
| Microkernel | Astrid (route event + enforce capability) | `pilothOS/` control plane + guard dispatch (`COMMAND_TABLE`) |
| Syscalls | typed IPC / tool bus | guard modes (`os-*`, `tool-check`, `receipt-*`, `capability-*`, `broker-check`…) |
| Process / đơn vị | capsule (WASM sandbox) | governed task-run (lifecycle `os-start`→`os-close`) |
| Capabilities / permissions | manifest ACL (fail-closed) | `capability-manifest.json` + `authority-delta` (T0) |
| Exec safety / airlock | capsule-shell Process Airlock | **execution broker** `broker-check` (catastrophic hard-deny, T1) |
| Self-inspection | capsule-system (`list`/`inspect`/`status`) | **`os-inspect`** (T2) |
| Self-extension | Forge / meta-harness | Piloth Forge `forge-*` (T3, đã có — preview) |
| Scheduler | react loop / priority dispatch | scheduler (`route-task`/`scheduler-suggest`) + phase plan |
| Filesystem / state | session + memory | `memory/state/os-runs/**` |
| GC | context-engine compaction | `state-janitor` / `artifact-janitor` |
| Drivers | provider drivers (openai-compat) | adapters (claude/codex/cursor/antigravity) |
| Identity / /etc/profile | capsule-identity | `CLAUDE.md` + `PilothOS.md` (hiến pháp) |
| Users / multi-tenant | capsule-users / principals | `repo_key` + `principal` introspection (T5, preview); attribution trên receipt là future |
| Supply chain / audit | Sigstore/BLAKE3/channels + Unicity Audit | receipt-seals hash-chain + truth-in-seal + `provenance`/`upgrade-verify` (T4/T6, preview); Sigstore/channels là future |

## Nguyên tắc

- **Piloth là governance OS, không phải runtime OS** — cưỡng chế tại biên
  tool-call + vòng đời task, không sandbox thực thi token-level của model. Đây là
  ranh giới thể loại có chủ đích (xem `VALIDATION.md`).
- Mỗi dòng trên là dịch vụ THẬT, có thể `os-inspect` để kiểm — không phải nhãn
  marketing. Không claim ngang AOS mà thiếu benchmark (`os-control-plane.md`).
