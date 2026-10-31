"""Offline smoke failure diagnostics, exercised with mocked transports only."""

import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

import scripts._live_smoke as smoke
from mydrak.live.guard import LiveConfigError
import mydrak.live.http as live_http

VALID_ENVELOPE = json.dumps({
    "choices": [{"message": {"content": "not a diagnosis JSON"}}],
    "usage": {"prompt_tokens": 3, "completion_tokens": 2},
}).encode()
VALID_DIAGNOSIS = json.dumps({
    "plant_visible": False, "crop": "unknown", "issue": "unknown",
    "alternatives": [], "symptoms_observed": [], "image_issues": [],
    "stated_confidence": "medium", "segment_prompts": [],
}).encode()
TIER_CONFIG = {
    "model_id": "synthetic-model", "endpoint": "https://example.invalid/v1",
    "timeout_s": 1, "max_tokens": 8, "max_input_tokens_estimate": 10,
    "price_input_per_1m": 1, "price_output_per_1m": 1,
    "model_id_contributor": "synthetic-contributor",
}


class MockTransport:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def post_json(self, *args, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def invoke(monkeypatch, tmp_path, transport, *, provider="tier2", argv=None, env=None):
    monkeypatch.setattr(smoke, "_ROOT", tmp_path)
    monkeypatch.setattr(smoke, "load_live_provider_config", lambda _path, _provider: TIER_CONFIG)
    lines = []
    result = smoke.run_smoke(
        provider, argv or [], transport=transport,
        environ=env or {"MYDRAK_LIVE": "1", "META_API_KEY": "SYNTHETIC-KEY"},
        output=lines.append,
    )
    assert len(lines) == 1
    assert line_category_count(lines[0]) <= 1
    assert "SYNTHETIC-KEY" not in lines[0]
    assert "response body" not in lines[0].lower()
    return result, lines[0]


def line_category_count(line):
    return line.count("failure_category=")


@pytest.mark.parametrize(("argv", "env", "condition"), [
    ([], {"MYDRAK_LIVE": "1", "META_API_KEY": "SYNTHETIC-KEY"}, "cli_authorization"),
    (["--live-authorized", "--max-spend-usd", "0.25"],
     {"META_API_KEY": "SYNTHETIC-KEY"}, "MYDRAK_LIVE"),
    (["--live-authorized"],
     {"MYDRAK_LIVE": "1", "META_API_KEY": "SYNTHETIC-KEY"}, "max_spend_usd"),
])
def test_guard_refusal_names_condition_and_says_request_not_sent(
    monkeypatch, tmp_path, argv, env, condition,
):
    transport = MockTransport((200, VALID_ENVELOPE))
    result, line = invoke(monkeypatch, tmp_path, transport, argv=argv, env=env)
    assert result == 2 and transport.calls == 0
    assert f"failure_category=guard_refused" in line
    assert f"guard_condition={condition}" in line
    assert "request_sent=false" in line


def test_config_invalid_is_diagnosed_before_dispatch(monkeypatch, tmp_path):
    def invalid_config(*_args):
        raise LiveConfigError("safe config failure", condition="config_unresolved")
    monkeypatch.setattr(smoke, "load_live_provider_config", invalid_config)
    monkeypatch.setattr(smoke, "_ROOT", tmp_path)
    transport = MockTransport((200, VALID_ENVELOPE))
    lines = []
    result = smoke.run_smoke(
        "tier2", ["--live-authorized", "--max-spend-usd", "0.25"],
        transport=transport, environ={"MYDRAK_LIVE": "1", "META_API_KEY": "SYNTHETIC-KEY"},
        output=lines.append,
    )
    assert result == 2 and transport.calls == 0
    assert len(lines) == 1 and "failure_category=config_invalid" in lines[0]
    assert "request_sent=false" in lines[0]


def test_missing_key_is_separate_from_other_guard_refusals(monkeypatch, tmp_path):
    transport = MockTransport((200, VALID_ENVELOPE))
    result, line = invoke(
        monkeypatch, tmp_path, transport,
        argv=["--live-authorized", "--max-spend-usd", "0.25"],
        env={"MYDRAK_LIVE": "1"},
    )
    assert result == 2 and transport.calls == 0
    assert "failure_category=missing_key" in line
    assert "request_sent=false" in line


@pytest.mark.parametrize(("error", "category"), [
    (TimeoutError("synthetic secret timeout"), "timeout"),
    (OSError("synthetic secret network failure"), "network_error"),
])
def test_network_failures_are_categorized_without_exception_text(
    monkeypatch, tmp_path, error, category,
):
    transport = MockTransport(error=error)
    result, line = invoke(
        monkeypatch, tmp_path, transport,
        argv=["--live-authorized", "--max-spend-usd", "0.25"],
    )
    assert result == 1 and transport.calls == 3
    assert f"failure_category={category}" in line
    assert "request_sent=true" in line
    assert "synthetic secret" not in line


def test_http_error_reports_only_status_and_standard_phrase(monkeypatch, tmp_path):
    transport = MockTransport((429, b"private body and synthetic secret"))
    result, line = invoke(
        monkeypatch, tmp_path, transport,
        argv=["--live-authorized", "--max-spend-usd", "0.25"],
    )
    assert result == 1 and transport.calls == 3
    assert "failure_category=http_error" in line and "request_sent=true" in line
    assert "http_status=429" in line and "http_reason='Too Many Requests'" in line
    assert "private body" not in line and "synthetic secret" not in line


def test_urllib_http_error_discards_and_closes_body_without_network(monkeypatch):
    body = BytesIO(b"synthetic private response body")
    error = HTTPError("https://example.invalid", 429, "provider text", {}, body)

    def raise_http_error(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(live_http, "urlopen", raise_http_error)
    status, response_body = live_http.UrllibJsonTransport().post_json(
        "https://example.invalid/v1/chat/completions", headers={}, body={}, timeout_s=1,
    )
    assert status == 429 and response_body == b""
    assert body.closed


def test_invalid_response_envelope_is_separated_from_http_error(monkeypatch, tmp_path):
    transport = MockTransport((200, b"synthetic secret invalid body"))
    result, line = invoke(
        monkeypatch, tmp_path, transport,
        argv=["--live-authorized", "--max-spend-usd", "0.25"],
    )
    assert result == 1 and transport.calls == 3
    assert "failure_category=response_invalid" in line
    assert "request_sent=true" in line and "synthetic secret" not in line


def test_invalid_diagnosis_schema_is_reported_after_response(monkeypatch, tmp_path):
    transport = MockTransport((200, VALID_ENVELOPE))
    result, line = invoke(
        monkeypatch, tmp_path, transport,
        argv=["--live-authorized", "--max-spend-usd", "0.25"],
    )
    assert result == 1 and transport.calls == 1
    assert "failure_category=schema_invalid" in line
    assert "request_sent=true" in line


def test_valid_smoke_response_prints_safe_operational_fields(monkeypatch, tmp_path):
    envelope = json.dumps({
        "choices": [{"message": {"content": VALID_DIAGNOSIS.decode()}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2},
    }).encode()
    transport = MockTransport((200, envelope))
    result, line = invoke(
        monkeypatch, tmp_path, transport,
        argv=["--live-authorized", "--max-spend-usd", "0.25"],
    )
    assert result == 0 and transport.calls == 1
    assert "status=response_received" in line and "request_sent=true" in line
    assert "tokens_in=3" in line and "tokens_out=2" in line
    assert "estimated_cost_usd=" in line


@pytest.mark.parametrize("provider", ["tier1", "tier2"])
def test_both_smoke_entrypoints_share_safe_diagnostics(monkeypatch, tmp_path, provider):
    transport = MockTransport(error=TimeoutError("synthetic key must not print"))
    env = {"MYDRAK_LIVE": "1", "TOGETHER_API_KEY": "SYNTHETIC-KEY",
           "META_API_KEY": "SYNTHETIC-KEY"}
    result, line = invoke(
        monkeypatch, tmp_path, transport, provider=provider,
        argv=["--live-authorized", "--max-spend-usd", "0.25"], env=env,
    )
    assert result == 1 and transport.calls == 3
    assert "failure_category=timeout" in line and "request_sent=true" in line
