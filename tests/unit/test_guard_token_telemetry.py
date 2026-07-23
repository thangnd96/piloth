"""Unit tests for real token telemetry — pricing, cost ledger, metric schema.

Covers the schema-extension slice: the model price map + cost computation, the
extended cost_ledger_summary (cache tokens + cost_usd), and the metric-evidence
validator/sanitizer accepting the new llm_usage fields. The transcript-parsing
extractor (token-telemetry mode) is exercised separately.
"""


def _llm(**over):
    base = {
        "kind": "metric",
        "metric_type": "llm_usage",
        "metric_name": "session-token-usage",
        "real_token_telemetry": True,
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_creation_input_tokens": 10,
        "cache_read_input_tokens": 1000,
        "cost_usd": 0.01,
        "model": "claude-opus-4-8",
    }
    base.update(over)
    return base


_PRICING = {
    "models": {
        "claude-opus-4-8": {"input": 5.0, "output": 25.0, "cache_write_5m": 6.25, "cache_read": 0.50},
    }
}


# ---- price map ----

def test_pricing_file_loads_and_has_models(guard):
    pricing = guard.load_model_pricing()
    assert isinstance(pricing, dict) and isinstance(pricing.get("models"), dict)
    assert "claude-opus-4-8" in pricing["models"]


def test_model_price_known_and_unknown(guard):
    assert guard.model_price("claude-opus-4-8", _PRICING) == _PRICING["models"]["claude-opus-4-8"]
    assert guard.model_price("gpt-4", _PRICING) is None
    assert guard.model_price("", _PRICING) is None


def test_compute_token_cost_usd_math(guard):
    usage = {
        "input_tokens": 1_000_000,
        "output_tokens": 1_000_000,
        "cache_creation_input_tokens": 1_000_000,
        "cache_read_input_tokens": 1_000_000,
    }
    # 5 + 25 + 6.25 + 0.50 = 36.75
    assert guard.compute_token_cost_usd(usage, "claude-opus-4-8", _PRICING) == 36.75


def test_compute_token_cost_usd_unknown_model_returns_none(guard):
    assert guard.compute_token_cost_usd({"input_tokens": 100}, "gpt-4", _PRICING) is None


# ---- cost_ledger_summary ----

def test_cost_ledger_surfaces_cache_and_cost(guard):
    ledger = guard.cost_ledger_summary([_llm(cost_usd=0.02)])
    assert ledger["real_token_telemetry"] is True
    rt = ledger["real_tokens"]
    assert rt["input_tokens"] == 100 and rt["output_tokens"] == 50
    assert rt["cache_creation_input_tokens"] == 10 and rt["cache_read_input_tokens"] == 1000
    assert rt["cost_usd"] == 0.02


def test_cost_ledger_unavailable_without_real_telemetry(guard):
    ledger = guard.cost_ledger_summary([
        _llm(real_token_telemetry=False, unavailable_reason="adapter has no token telemetry")
    ])
    assert ledger["real_token_telemetry"] is False
    assert ledger["real_tokens"] == "unavailable"
    assert ledger["token_unavailable_reasons"]


# ---- validate_metric_evidence (new fields) ----

def test_metric_accepts_cache_and_cost_fields(guard):
    assert guard.validate_metric_evidence(_llm()) == []


def test_metric_rejects_negative_cost(guard):
    errs = guard.validate_metric_evidence(_llm(cost_usd=-1))
    assert any("cost_usd" in e for e in errs)


def test_metric_rejects_negative_cache(guard):
    errs = guard.validate_metric_evidence(_llm(cache_read_input_tokens=-5))
    assert any("cache_read_input_tokens" in e for e in errs)


def test_metric_requires_unavailable_reason_without_real_telemetry(guard):
    errs = guard.validate_metric_evidence(_llm(real_token_telemetry=False))
    assert any("unavailable_reason" in e for e in errs)


# ---- sanitization keeps the new keys ----

def test_llm_metric_payload_survives_sanitization(guard):
    sanitized, errors = guard.sanitize_os_evidence_payload(_llm())
    assert errors == []
    assert sanitized.get("cache_read_input_tokens") == 1000
    assert sanitized.get("cost_usd") == 0.01
    assert sanitized.get("model") == "claude-opus-4-8"


# ---- transcript parsing (extractor helpers) ----

def test_parse_iso_timestamp_handles_z_suffix(guard):
    dt = guard.parse_iso_timestamp("2026-07-22T00:09:51.404Z")
    assert dt is not None and dt.year == 2026
    assert guard.parse_iso_timestamp("not-a-date") is None
    assert guard.parse_iso_timestamp("") is None


def test_resolve_transcript_path_explicit_flag(guard):
    assert str(guard.resolve_transcript_path(["--transcript", "/x/y.jsonl"])) == "/x/y.jsonl"
    assert str(guard.resolve_transcript_path(["--transcript=/a/b.jsonl"])) == "/a/b.jsonl"


def _write_transcript(tmp_path):
    import json as _json
    lines = [
        {"timestamp": "2026-07-22T00:00:00Z", "message": {"model": "claude-opus-4-8",
         "usage": {"input_tokens": 9999, "output_tokens": 9999}}},  # before window
        {"timestamp": "2026-07-22T01:00:00Z", "message": {"model": "claude-opus-4-8",
         "usage": {"input_tokens": 1_000_000, "output_tokens": 0,
                   "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}},
        {"timestamp": "2026-07-22T02:00:00Z", "message": {"model": "claude-opus-4-8",
         "usage": {"input_tokens": 0, "output_tokens": 1_000_000}}},
        {"timestamp": "2026-07-22T03:00:00Z", "type": "user"},  # no usage
    ]
    p = tmp_path / "session.jsonl"
    p.write_text("\n".join(_json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    return p


def test_sum_transcript_usage_windowed_with_cost(guard, tmp_path):
    p = _write_transcript(tmp_path)
    since = guard.parse_iso_timestamp("2026-07-22T00:30:00Z")
    summed = guard.sum_transcript_usage(p, since=since, pricing=_PRICING)
    assert summed["records"] == 2  # the pre-window and no-usage rows are excluded
    assert summed["usage"]["input_tokens"] == 1_000_000
    assert summed["usage"]["output_tokens"] == 1_000_000
    assert summed["primary_model"] == "claude-opus-4-8"
    assert summed["cost_usd"] == 30.0  # 1M input @ $5 + 1M output @ $25


def test_sum_transcript_usage_no_window_includes_all(guard, tmp_path):
    p = _write_transcript(tmp_path)
    summed = guard.sum_transcript_usage(p, since=None, pricing=_PRICING)
    assert summed["records"] == 3
    assert summed["usage"]["input_tokens"] == 1_009_999


def test_sum_transcript_usage_unpriced_model_cost_none(guard, tmp_path):
    import json as _json
    p = tmp_path / "s.jsonl"
    p.write_text(_json.dumps({"timestamp": "2026-07-22T01:00:00Z",
        "message": {"model": "some-other-model", "usage": {"input_tokens": 100}}}) + "\n", encoding="utf-8")
    summed = guard.sum_transcript_usage(p, since=None, pricing=_PRICING)
    assert summed["cost_usd"] is None
    assert summed["usage"]["input_tokens"] == 100


def test_sum_transcript_usage_missing_file_returns_none(guard, tmp_path):
    assert guard.sum_transcript_usage(tmp_path / "does-not-exist.jsonl", since=None) is None
