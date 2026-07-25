# Codebase Intelligence Runtime

## Goal

Return the smallest useful structural evidence while preserving source
correctness. The graph is optional derived state; normal Piloth routing remains
the fallback.

## CLI

Index explicitly:

```bash
python3 pilothOS/scripts/pilothos_guard.py codebase-index '{"repo_path":"."}'
```

Inspect freshness and coverage counts:

```bash
python3 pilothOS/scripts/pilothos_guard.py codebase-status '{"repo_path":"."}'
```

Query:

```bash
python3 pilothOS/scripts/pilothos_guard.py codebase-query \
  '{"action":"search","query":"route_task_payload"}'
```

Supported reference actions:

- `overview`: file/language/coverage counts;
- `search`: canonical symbol candidates;
- `trace`: bounded inbound/outbound call path;
- `snippet`: exact live source for a resolved symbol;
- `coverage`: per-path deep/shallow/skip state;
- `impact`: inbound candidates for changed or requested paths.

## Adaptive policy

Do not build an index merely because a session starts. Prefer the existing
index/doc/source route when the task is narrow.

Index/query when at least one is true:

- the task asks a structural or cross-file question;
- repeated source search is likely to cost more than index reuse;
- impact/caller/callee evidence is part of the acceptance criteria;
- a consumer repository is large enough that progressive source routing is
  insufficient.

Stay source-only when:

- the task is a known one-file edit;
- index status is missing/stale and rebuild cost exceeds task value;
- relevant coverage is shallow/partial;
- exact source or runtime behavior is the question.

## Query protocol

1. Call `codebase-status`.
2. If missing, decide explicitly whether index cost is justified.
3. Search for a qualified candidate.
4. Check relevant path coverage.
5. Trace only with bounded depth/limit.
6. Read exact live snippet before editing or making a source-grounded claim.
7. Fall back to normal source tools for stale, partial, ambiguous or negative
   results.

## Trust fields

- `candidate_only`: structural lead, not final evidence.
- `source_grounded`: live snippet was read.
- `coverage_signal=best_effort`: coverage improves confidence but is not proof
  of semantic completeness.
- `source_fallback_required=true`: graph must not be used alone.

## Safety and budgets

- Repository paths must resolve to the installed Piloth consumer root.
- Symlinks, binary files and files above the size budget are not parsed.
- `max_files` and `max_total_bytes` are explicit; exceeding either refuses
  indexing. The reference default total byte budget is 512 MiB.
- SQLite is built atomically with owner-only state permissions.
- Query depth/result size is bounded.
- No dependency download, subprocess toolchain detection or source mutation is
  performed by the reference engine.

## Current limitation

The current engine is a contract reference with Python deep parsing and
universal shallow coverage. It does not meet the full parity plan, cross-platform
native SLA, real token reduction SLA or end-to-end speed SLA. Those claims remain
blocked until the matrix in `docs/codebase-memory-plan.md` passes.
