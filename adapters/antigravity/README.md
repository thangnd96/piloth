# Antigravity Adapter

This folder contains short Markdown bridges into PilothOS. The OS source of truth remains in `pilothOS/`.

Use `os-start`/`evidence-route` and the shared
`pilothOS/runtime/adapter-capabilities.json` vocabulary. Rules/CLI transport is
the fallback; missing hooks, teams, model pinning or telemetry must be reported
as unavailable rather than inferred.
