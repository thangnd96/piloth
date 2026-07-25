

# ------------------------------------------------- OS cost and token telemetry
def metric_records(os_evidence):
    return [
        item for item in os_evidence
        if isinstance(item, dict) and item.get("kind") == "metric"
    ]


def metric_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def metric_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_model_pricing():
    """Load the advisory model price map (USD per MTok). Fail-soft → {} when the
    file is missing or malformed, so telemetry never breaks on a bad price map."""
    data = load_json_file(PILOTHOS_DIR / "runtime" / "model-pricing.json")
    if isinstance(data, dict) and isinstance(data.get("models"), dict):
        return data
    return {}


def model_price(model, pricing=None):
    """Return the price row {input, output, cache_write_5m, cache_read} for a
    model id in USD/MTok, or None when the model is unknown (cost then omitted)."""
    if not non_empty_string(model):
        return None
    pricing = pricing if isinstance(pricing, dict) else load_model_pricing()
    models = pricing.get("models") if isinstance(pricing, dict) else None
    row = models.get(model) if isinstance(models, dict) else None
    return row if isinstance(row, dict) else None


def compute_token_cost_usd(usage, model, pricing=None):
    """Cost of one usage record given a price row, or None when the model is
    unpriced. usage keys: input_tokens/output_tokens/cache_creation_input_tokens/
    cache_read_input_tokens. Cache tiers are priced separately (cache_read ~0.1x,
    cache_write ~1.25x input) — ignoring them would misstate cost badly."""
    row = model_price(model, pricing)
    if row is None:
        return None
    per_mtok = lambda tokens, rate: metric_float(tokens) / 1_000_000.0 * metric_float(rate)
    cost = (
        per_mtok(usage.get("input_tokens"), row.get("input"))
        + per_mtok(usage.get("output_tokens"), row.get("output"))
        + per_mtok(usage.get("cache_creation_input_tokens"), row.get("cache_write_5m"))
        + per_mtok(usage.get("cache_read_input_tokens"), row.get("cache_read"))
    )
    return round(cost, 6)


def parse_iso_timestamp(ts):
    """Parse an ISO-8601 timestamp (accepting a trailing Z) to a datetime, or
    None. Used to window transcript records by the OS run's created_at."""
    if not non_empty_string(ts):
        return None
    text = ts.strip().replace("Z", "+00:00")
    try:
        return datetime.datetime.fromisoformat(text)
    except ValueError:
        return None


def transcript_project_slug():
    """Claude Code encodes the project cwd into the transcript dir name by
    replacing '/' and '.' with '-' (e.g. -Users-me-VNG-tools-piloth)."""
    return re.sub(r"[/.]", "-", str(REPO_ROOT.resolve()))


def resolve_transcript_path(argv, hook_input=None):
    """Locate the Claude Code session transcript: explicit --transcript wins,
    then a hook's transcript_path, then the newest *.jsonl for this project.
    Returns a Path or None (None → telemetry unavailable, recorded honestly)."""
    argv = argv or []
    for i, arg in enumerate(argv):
        if arg == "--transcript" and i + 1 < len(argv):
            return pathlib.Path(argv[i + 1]).expanduser()
        if arg.startswith("--transcript="):
            return pathlib.Path(arg.split("=", 1)[1]).expanduser()
    if isinstance(hook_input, dict) and non_empty_string(hook_input.get("transcript_path")):
        return pathlib.Path(hook_input["transcript_path"]).expanduser()
    base = pathlib.Path.home() / ".claude" / "projects" / transcript_project_slug()
    if not base.exists():
        return None
    def _mtime(p):
        try:
            return p.stat().st_mtime
        except OSError:
            return 0
    candidates = sorted(base.glob("*.jsonl"), key=_mtime)
    return candidates[-1] if candidates else None


TRANSCRIPT_USAGE_KEYS = (
    "input_tokens", "output_tokens",
    "cache_creation_input_tokens", "cache_read_input_tokens",
)


def sum_transcript_usage(path, since=None, pricing=None):
    """Sum real per-turn `message.usage` from a Claude Code transcript, windowed
    to records at/after `since` (a datetime). Returns a dict with summed usage,
    per-model token totals, a summed cost (or None when any model is unpriced),
    and record/model counts — or None if the file can't be read.

    Attribution is main-session-only: background subagent transcripts are
    separate files and are not summed here (disclosed as subagent_scope)."""
    usage = {k: 0 for k in TRANSCRIPT_USAGE_KEYS}
    per_model_tokens = {}
    records = 0
    cost_total = 0.0
    cost_available = True
    pricing = pricing if isinstance(pricing, dict) else load_model_pricing()
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict):
                    continue
                if since is not None:
                    rec_ts = parse_iso_timestamp(rec.get("timestamp"))
                    if rec_ts is not None and rec_ts < since:
                        continue
                msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
                u = msg.get("usage") if isinstance(msg, dict) else None
                if not isinstance(u, dict):
                    continue
                records += 1
                row = {k: metric_int(u.get(k)) for k in TRANSCRIPT_USAGE_KEYS}
                for k in TRANSCRIPT_USAGE_KEYS:
                    usage[k] += row[k]
                model = msg.get("model") if non_empty_string(msg.get("model")) else "unknown"
                per_model_tokens[model] = per_model_tokens.get(model, 0) + sum(row.values())
                c = compute_token_cost_usd(row, model, pricing)
                if c is None:
                    cost_available = False
                else:
                    cost_total += c
    except OSError:
        return None
    primary_model = max(per_model_tokens, key=per_model_tokens.get) if per_model_tokens else ""
    return {
        "usage": usage,
        "records": records,
        "models": sorted(per_model_tokens),
        "primary_model": primary_model,
        "cost_usd": round(cost_total, 6) if cost_available else None,
        "pricing_source": pricing.get("source") if isinstance(pricing, dict) else "",
    }


def token_telemetry(argv):
    """Extract real LLM token telemetry from the Claude Code session transcript
    and record it as an `os-evidence kind=metric metric_type=llm_usage
    real_token_telemetry=true` for the active OS run. Windowed to the run's
    created_at; main-session-only (disclosed). Fails soft: no transcript →
    records real_token_telemetry=false + unavailable_reason.

    Usage: token-telemetry [--task <id>] [--transcript <path>]
    """
    argv = argv or []
    task_id = None
    for i, arg in enumerate(argv):
        if arg == "--task" and i + 1 < len(argv):
            task_id = argv[i + 1]
        elif arg.startswith("--task="):
            task_id = arg.split("=", 1)[1]
    state, _ = load_os_state(task_id)
    if not state:
        json_print({"result": "token_telemetry_rejected", "errors": ["no active OS run; call os-start first"]})
        return
    if state.get("status") in {"closed", "sealed"}:
        json_print({"result": "token_telemetry_rejected", "task_id": state.get("task_id"), "errors": ["OS run is already closed"]})
        return
    task_id = state["task_id"]
    created_at = state.get("created_at")
    since = parse_iso_timestamp(created_at)
    transcript = resolve_transcript_path(argv)
    summed = sum_transcript_usage(transcript, since=since) if transcript else None

    if not summed or summed.get("records", 0) == 0:
        payload = {
            "task_id": task_id,
            "kind": "metric",
            "metric_type": "llm_usage",
            "metric_name": "session-token-usage",
            "real_token_telemetry": False,
            "unavailable_reason": "no Claude Code transcript usage found for this session (harness may not expose per-turn token telemetry)",
            "subagent_scope": "main_session_only",
            "summary": "token telemetry unavailable",
        }
        result_label = "token_telemetry_unavailable"
    else:
        usage = summed["usage"]
        payload = {
            "task_id": task_id,
            "kind": "metric",
            "metric_type": "llm_usage",
            "metric_name": "session-token-usage",
            "real_token_telemetry": True,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "cache_creation_input_tokens": usage["cache_creation_input_tokens"],
            "cache_read_input_tokens": usage["cache_read_input_tokens"],
            "total_tokens": usage["input_tokens"] + usage["output_tokens"],
            "model": summed.get("primary_model") or "",
            "window_start": created_at or "",
            "subagent_scope": "main_session_only",
            "summary": f"session token telemetry from Claude Code transcript ({summed['records']} turns)",
        }
        if summed.get("cost_usd") is not None:
            payload["cost_usd"] = summed["cost_usd"]
            if non_empty_string(summed.get("pricing_source")):
                payload["pricing_source"] = summed["pricing_source"]
        result_label = "token_telemetry_recorded"

    evidence, errors = sanitize_os_evidence_payload(payload)
    if errors:
        json_print({"result": "token_telemetry_rejected", "task_id": task_id, "errors": errors})
        return
    evidence["task_id"] = task_id
    append_os_evidence(task_id, evidence)
    state.setdefault("lifecycle", [])
    if "tool/evidence" not in state["lifecycle"]:
        state["lifecycle"].append("tool/evidence")
    state["evidence_count"] = len(os_evidence_records(task_id))
    save_os_state(state)
    out = {
        "result": result_label,
        "task_id": task_id,
        "evidence_ref": evidence["id"],
        "transcript": str(transcript) if transcript else None,
        "window_start": created_at or "",
        "real_token_telemetry": bool(payload.get("real_token_telemetry")),
        "subagent_scope": "main_session_only",
    }
    if result_label == "token_telemetry_recorded":
        out.update({
            "records": summed["records"],
            "models": summed["models"],
            "model": payload.get("model", ""),
            "tokens": summed["usage"],
            "cost_usd": payload.get("cost_usd", "unavailable_unpriced_model"),
        })
    json_print(out)


def cost_ledger_summary(os_evidence):
    metrics = metric_records(os_evidence)
    real_llm = [item for item in metrics if item.get("metric_type") == "llm_usage" and item.get("real_token_telemetry") is True]
    unavailable_llm = [
        item for item in metrics
        if item.get("metric_type") == "llm_usage" and item.get("real_token_telemetry") is not True
    ]
    benchmark = [
        item for item in metrics
        if item.get("metric_type") == "benchmark"
    ]
    real_tokens = None
    if real_llm:
        real_tokens = {
            "input_tokens": sum(metric_int(item.get("input_tokens")) for item in real_llm),
            "output_tokens": sum(metric_int(item.get("output_tokens")) for item in real_llm),
            "total_tokens": sum(metric_int(item.get("total_tokens")) for item in real_llm),
            "cache_creation_input_tokens": sum(metric_int(item.get("cache_creation_input_tokens")) for item in real_llm),
            "cache_read_input_tokens": sum(metric_int(item.get("cache_read_input_tokens")) for item in real_llm),
            "cost_usd": round(sum(metric_float(item.get("cost_usd")) for item in real_llm), 6),
        }
    return {
        "schema_version": 1,
        "metric_records": len(metrics),
        "real_tokens": real_tokens if real_tokens is not None else "unavailable",
        "real_token_telemetry": bool(real_llm),
        "token_unavailable_reasons": sorted(set(
            str(item.get("unavailable_reason", "")).strip()
            for item in unavailable_llm
            if str(item.get("unavailable_reason", "")).strip()
        )),
        "tool_output_chars": sum(metric_int(item.get("chars")) for item in metrics if item.get("metric_type") == "tool_output"),
        "context_loads": sum(metric_int(item.get("count") or 1) for item in metrics if item.get("metric_type") == "context_load"),
        "commands": sum(metric_int(item.get("count") or 1) for item in metrics if item.get("metric_type") == "command"),
        "retries": sum(metric_int(item.get("count") or 1) for item in metrics if item.get("metric_type") == "retry"),
        "repairs": sum(metric_int(item.get("count") or 1) for item in metrics if item.get("metric_type") == "repair"),
        "duration_ms": sum(metric_int(item.get("duration_ms")) for item in metrics),
        "benchmark_results": [
            {
                "id": item.get("id"),
                "result": item.get("consumer_value_result", ""),
                "all_mandatory_not_worse": bool(item.get("all_mandatory_not_worse")),
                "consumer_visible_win": bool(item.get("consumer_visible_win")),
                "real_token_telemetry": bool(item.get("real_token_telemetry")),
                "wins": item.get("wins", []),
                "mandatory_regressions": item.get("mandatory_regressions", []),
            }
            for item in benchmark
        ],
    }


def budget_status(contract, os_evidence):
    """Advisory-only budget view: compare real spend (from token telemetry) to an
    optional contract budget.max_usd. Surfaced in os-status / os-report; it NEVER
    blocks os-close. Returns advisory_unavailable when no ceiling is set or no
    real-token cost has been recorded yet."""
    budget = contract.get("budget") if isinstance(contract, dict) else None
    max_usd = None
    if isinstance(budget, dict) and budget.get("max_usd") is not None:
        try:
            max_usd = float(budget.get("max_usd"))
        except (TypeError, ValueError):
            max_usd = None
    if max_usd is None:
        return {"status": "advisory_unavailable", "reason": "no budget.max_usd in contract"}
    ledger = cost_ledger_summary(os_evidence)
    real = ledger.get("real_tokens")
    spent = real.get("cost_usd") if isinstance(real, dict) else None
    if not isinstance(spent, (int, float)):
        return {
            "status": "advisory_unavailable",
            "reason": "no real token telemetry / cost recorded yet (run token-telemetry)",
            "max_usd": max_usd,
        }
    return {
        "advisory": True,
        "max_usd": max_usd,
        "spent_usd": round(float(spent), 6),
        "remaining_usd": round(max_usd - float(spent), 6),
        "over_budget": float(spent) > max_usd,
        "note": "advisory only — does not block os-close",
    }


def record_checkpoint_from_evidence(state, evidence):
    phase = str(evidence.get("phase") or "").strip()
    if not phase:
        return
    checkpoints = state.setdefault("checkpoints", [])
    checkpoints.append({
        "phase": phase,
        "evidence_ref": evidence.get("id", ""),
        "kind": evidence.get("kind", ""),
        "recorded_at": evidence.get("recorded_at", ""),
        "summary": evidence.get("summary", ""),
        "metric_type": evidence.get("metric_type", ""),
    })


def update_state_runtime_cost(state, task_id):
    evidence = os_evidence_records(task_id)
    state["cost_ledger"] = cost_ledger_summary(evidence)
    return state["cost_ledger"]


def consumer_superiority_payloads(receipt, os_evidence):
    payloads = []
    if isinstance(receipt, dict) and isinstance(receipt.get("consumer_superiority"), dict):
        payloads.append(receipt.get("consumer_superiority"))
    for item in os_evidence:
        if isinstance(item, dict) and item.get("kind") == "metric" and item.get("metric_type") == "benchmark":
            payloads.append(item)
    return payloads


def consumer_superiority_ok(receipt, os_evidence):
    for payload in consumer_superiority_payloads(receipt, os_evidence):
        result = str(payload.get("result") or payload.get("consumer_value_result") or "").strip().lower()
        if (
            result in SUPERIORITY_PASS_RESULTS
            and payload.get("all_mandatory_not_worse") is True
            and payload.get("consumer_visible_win") is True
            and (
                payload.get("real_token_telemetry") is True
                or has_real_llm_token_telemetry(os_evidence)
            )
        ):
            return True
    return False
