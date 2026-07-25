# Architecture: Codebase Intelligence

## Decision

Piloth treats a codebase graph as derived, disposable evidence infrastructure.
It is not Memory and it is never the source of truth.

The stable boundary is the guard JSON CLI. A Python standard-library reference
engine locks the contract first; the target implementation is a Piloth-built,
vendored static engine selected by platform.

## Ownership

| Layer | Owns |
|---|---|
| Runtime | when to index/query/fallback and evidence requirements |
| Tools | CLI/MCP transport and health contract |
| Knowledge | architecture facts and upstream provenance |
| Memory state | ignored SQLite generations only |
| Native engine | parsing, graph build, traversal and coverage mechanics |
| Consumer source | final truth |

## Invariants

1. Indexing is explicit and budgeted, never an implicit session-start side
   effect.
2. State stays under `pilothOS/memory/state/codebase-index/`.
3. Query results are `candidate_only` unless exact live source is returned.
4. Stale content requires source fallback; structural/HEAD changes require full
   rebuild.
5. Negative or exhaustive claims require a coverage check.
6. Generated artifacts may alias canonical source but cannot silently replace
   it.
7. The engine cannot read outside the controlled consumer repository.
8. Archive size, installed size, RSS and latency are separate metrics.
9. A byte reduction is not token telemetry.

## Reference engine boundary

The stdlib engine provides universal shallow coverage and deep Python AST
coverage. Unsupported or partially parsed files remain visible in the coverage
ledger. This preserves honest uncertainty while the vendored native engine is
built.

The reference schema and response fields are compatibility fixtures, not a
commitment to its indexing performance or language depth.

## Source provenance

Canonical identity uses qualified name, kind and normalized body structure.
When equivalent symbols occur in generated and source files, Piloth prefers the
non-generated source and records generated nodes as aliases. Later milestones
must extend this with distribution manifests and build provenance.

## Freshness model

| Change | State | Required behavior |
|---|---|---|
| no relevant change | `fresh` | graph candidate flow allowed |
| dirty source content | `stale_content` | source fallback; overlay later |
| HEAD/path set/schema/engine change | `stale_structural` | full rebuild |
| DB/root mismatch or corruption | `invalid` | do not query as trusted |
| no DB | `missing` | source routing or explicit adaptive index |

## Consequences

Positive:

- all adapters share one contract;
- no consumer package dependency for the reference path;
- graph failures degrade to source routing;
- generated duplication is addressed as provenance, not search noise.

Costs:

- shallow adapters cannot claim semantic parity;
- live fingerprinting has overhead in non-Git repositories;
- full native parity requires a maintained fork, platform builds and a large
  differential corpus.

Evidence and delivery gates for full parity are tracked vendor-side in the Piloth
source repo; they are not part of this distribution. The gates that must pass are
listed in `pilothOS/runtime/codebase-intelligence.md` under "Current limitation".
