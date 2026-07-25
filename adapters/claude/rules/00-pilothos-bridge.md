# PilothOS Bridge

Always read `pilothOS/bootstrap.md` first. Use progressive loading. Do not load all PilothOS files by default.

Use `evidence-route` through `os-start`. Adapter capability claims come only
from `pilothOS/runtime/adapter-capabilities.json` plus an explicit current
handshake; do not infer missing hook, team, model or telemetry support.
