# Piloth Review

Governed Visual Review — a **faithful, zero-dependency reimplementation of
[annotron](https://github.com/hueanmy/annotron)** (built from behaviour, not
cloned) that lives inside Piloth as a companion tool. Point-and-click review of
an artifact (Markdown or HTML), a Claude Code agent loop that applies the
feedback, a live activity mirror, and a browser permission gate.

The core preserves annotron's DNA: **Node built-ins only (zero runtime
dependency)**, disk files stay clean (the review SDK is injected at serve time),
loopback-only, and **fail-open** hooks (if the server is down, the agent is never
blocked).

## Loop

```
you run `review open <artifact.md|html> --agent`
        │
        ▼
review editor opens in the browser + agent loop starts
        │
you annotate (click element / select text / add note) → Send feedback
        │
agent long-polls /poll → gets structured feedback → runs `claude -p` → edits file
        │
file changes → editor live-reloads → agent replies into the thread
        │
repeat until you Finalize / Done (finalized: true)
```

Meanwhile every tool call the agent makes is mirrored to the sidebar, and (when
"Approve tools here" is on) each PreToolUse waits for your Allow / Allow-always /
Deny in the browser.

## CLI

```
review open <file> [--agent]     open the editor (optionally start the agent loop)
review agent <file>              run the poll → apply(claude -p) → reply loop
review poll <file> [--reply msg] [--annotation-id id]
review progress <file> "step"    push a live activity step to the browser
review check <file>              print {cancelled}
review stop                      shut the server down
```

Defaults: `REVIEW_HOST=127.0.0.1`, `REVIEW_PORT=7321` (env-overridable).

## Hook bridge (Claude Code)

Piloth installs these hooks **on by default** (activity mirror + PreToolUse gate).
The hook script is fail-open (server down → curl fails fast → allow, ~0 cost).

**Disable** with a single env var — set `PILOTH_REVIEW=off` in `.claude/settings.json`:

```json
{ "env": { "PILOTH_REVIEW": "off" } }
```

That turns `review-hook.sh` into a complete no-op (gate defers, fire does nothing).
Alternatively remove the four `review-hook.sh` entries from `.claude/settings.json`.
For standalone (non-Piloth) use, merge `hooks/hooks.json` into your settings.

## Governance integration (Piloth)

This core is standalone (1:1 with annotron). A separate Piloth layer turns the
feedback into evidence for the `human_review` quality gate enforced by
`pilothos_guard.py` at `os-close` — see the project plan and the guard
`review-request` / `review-feedback` / `review-verify` modes.

## Layout

```
bin/review            CLI
src/server.js         coordination server (routes, SSE, loop, hooks, permission gate)
src/sdk.js            injected capture layer (click/text → structured feedback)
src/chrome.html       review UI (outline, iframe, activity mirror, permission cards, composer)
src/mdRender.js       Markdown → HTML (+ mermaid fences)
hooks/                review-hook.sh + hooks.json
```
