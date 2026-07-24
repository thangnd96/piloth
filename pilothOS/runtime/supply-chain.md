# Supply-Chain Provenance (T4)

## Purpose

Làm cho phân phối PilothOS **verifiable / tamper-evident / reproducible** — probe
#5 ("phân phối đáng tin?"). Bản Piloth của BLAKE3-manifest + content-addressed
verification của AOS, bổ sung cho hash-chained `receipt-seals.jsonl` sẵn có.

## Content-addressed manifest

`pilothOS/dist-manifest.json` (sinh bởi `scripts/build_manifest.py`):

- mỗi file ship có `sha256` (hash nội dung SOURCE sẽ ship),
- `manifest_digest` = SHA-256 over sorted `path:sha256` — **tamper-evident** +
  **reproducible** (regen từ cùng nguồn → cùng digest),
- `source_commit` = git HEAD lúc build (fail-soft None).

## Kiểm

```bash
python3 pilothOS/scripts/pilothos_guard.py provenance          # self-consistency: recompute digest == stored
python3 pilothOS/scripts/pilothos_guard.py provenance --files . # consumer: so file trên đĩa vs sha256
```

- `provenance` (self-consistency) chạy được ngay trong dev repo (đọc manifest).
  `os-inspect` cũng surface một dòng health `supply-chain provenance`.
- `provenance --files <root>` cho **consumer** xác minh bản cài khớp release
  (bỏ qua `consumer-owned`/`personalize` vì có chủ đích khác sau cài).

## Nguyên tắc

- **Reproducible:** `manifest_digest` chỉ phụ thuộc nội dung file (không phụ thuộc
  `generated_at`) → cùng nguồn cho cùng digest.
- **Bổ sung, không thay:** cùng với `receipt-seals.jsonl` (hash-chain per-delivery)
  và target-seal (SHA-256 per-task), provenance phủ lớp *distribution*.

## Giới hạn trung thực (ghi cùng `VALIDATION.md`)

- SHA-256 self-describing manifest + hash-chain **KHÔNG** phải code
  signing / notarization / Sigstore. Chống tamper đầy đủ cần **ký digest**
  (Sigstore-class) — phụ thuộc CI, là bước tiếp theo.
- **Channels** (stable/dev/nightly) và **upgrade-self-heal test** (frozen-home:
  install `v_prev` → `/piloth:update` → verify state/customization bảo toàn) là
  hạ tầng release/CI — chưa làm, ghi nhận cho vòng sau.
- `provenance` (self-consistency) chứng minh manifest nội bộ nhất quán; chống
  tamper *file* thật cần `provenance --files` ở consumer hoặc digest đã ký.
