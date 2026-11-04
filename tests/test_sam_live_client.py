"""Offline SAM stream/client tests; transport and credentials are synthetic."""

import base64
from hashlib import sha256
import json
from decimal import Decimal
from urllib.error import HTTPError

import pytest

from conftest import REPO_ROOT
from mydrak.live.guard import LiveGuardError, load_live_provider_config
from mydrak.sam.guard import LiveCampaignGuard
from mydrak.sam.http_transport import SamSseTransportError, UrllibSseTransport
from mydrak.sam.live_client import (
    DEFAULT_SAM_SCOPE,
    SAM_RESPONSES_PATH,
    SamLiveClient,
    SamLiveError,
    _read_sse,
)
from mydrak.sam.response_text import SamFrame
from scripts.smoke_sam import _structure_summary
from scripts import smoke_sam


IMAGE = b"already-preprocessed synthetic jpeg bytes"
FRAME_TEXT = (
    "<0f>0<|box;x1=0;y1=0;x2=3;y2=3;w=4;h=4|>"
    "<|mask;x=0;y=0;data=1,1,~x|>"
)


class FakeStreamTransport:
    def __init__(self, chunks=None, error=None):
        self.chunks = list(chunks or [])
        self.error = error
        self.calls = []

    def post_sse(self, url, *, headers, json_body, timeout_s, max_response_bytes):
        self.calls.append({
            "url": url, "headers": dict(headers), "json_body": json_body,
            "timeout_s": timeout_s, "max_response_bytes": max_response_bytes,
        })
        if self.error:
            raise self.error
        return iter(self.chunks)


def event(value):
    return ("data: " + json.dumps(value) + "\n\n").encode()


def config():
    return load_live_provider_config(REPO_ROOT / "config/models.yaml", "sam")


def campaign(tmp_path, *, scope=DEFAULT_SAM_SCOPE, attempts=0, campaign_id=None):
    identity = campaign_id or sha256(f"{scope}:{attempts}".encode()).hexdigest()[:10]
    guard = LiveCampaignGuard(
        campaign_id="sam-test-" + identity, state_dir=tmp_path / ("sam-guard-" + identity),
    )
    guard.authorize_campaign(approval_token="synthetic-campaign-token", scope=scope)
    for _ in range(attempts):
        guard.authorize_attempt(scope=scope)
    return guard


def client(tmp_path, transport=None, **overrides):
    effective_transport = transport or FakeStreamTransport([
        event({"type": "response.output_text.delta", "delta": FRAME_TEXT}),
        b"data: [DONE]\n\n",
    ])
    identity = sha256(str(id(effective_transport)).encode()).hexdigest()[:10]
    selected_guard = overrides.pop("campaign_guard", None)
    values = {
        "config": config(), "cli_authorized": True,
        "max_spend_usd": "0.01", "ledger_path": str(tmp_path / "ledger.sqlite3"),
        "environ": {"MYDRAK_LIVE": "1", "META_API_KEY": "SYNTHETIC-META-KEY"},
        "campaign_guard": selected_guard or campaign(tmp_path, campaign_id=identity),
        "transport": effective_transport,
    }
    values.update(overrides)
    return SamLiveClient(**values)


def test_stream_request_shape_data_url_and_cost_reservation(tmp_path):
    transport = FakeStreamTransport([
        event({"type": "response.output_text.delta", "delta": FRAME_TEXT}),
        b"data: [DONE]\n\n",
    ])
    instance = client(tmp_path, transport)
    result = instance.send(
        prompt="red square", preprocessed_image=IMAGE,
        expected_width=4, expected_height=4,
    )
    assert isinstance(result.frame, SamFrame)
    assert result.parse_ok is True
    assert result.streamed_chars == len(FRAME_TEXT)
    assert result.estimated_cost_usd == Decimal("0.0025")
    request, = transport.calls
    assert request["url"] == "https://api.meta.ai/v1" + SAM_RESPONSES_PATH
    assert request["headers"] == {
        "Authorization": "Bearer SYNTHETIC-META-KEY",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    assert request["json_body"] == {
        "model": "sam-3.1",
        "input": [{
            "type": "message", "role": "user", "content": [
                {"type": "input_text", "text": "red square"},
                {"type": "input_image", "image_url":
                 "data:image/jpeg;base64," + base64.b64encode(IMAGE).decode("ascii")},
            ],
        }],
        "stream": True,
    }
    assert request["max_response_bytes"] == 2097152


def test_sse_multiple_split_deltas_unknown_fields_and_done():
    payload = (
        b": comment\n"
        b"event: response.output_text.delta\n"
        b"data: {\"type\":\"unknown.event\"}\n\n"
        b"data: {\"type\":\"response.output_text.delta\",\"delta\":\"one\"}\n\n"
        b"data: {\"type\":\"response.output_text.delta\",\"delta\":\" two\"}\n\n"
        b"data: [DONE]\n\n"
        b"data: {\"type\":\"response.output_text.delta\",\"delta\":\"ignored\"}\n\n"
    )
    assert _read_sse([payload[:31], payload[31:73], payload[73:]], max_bytes=4096) == "one two"


@pytest.mark.parametrize("chunks,category", [
    ([event({"type": "error"})], "provider_error"),
    ([event({"type": "response.failed"})], "provider_error"),
    ([b"data: {bad json}\n\n"], "response_invalid"),
    ([b"data: {\"type\":\"response.output_text.delta\",\"delta\":2}\n\n"], "response_invalid"),
    ([b"event: ignored\n\n"], "empty_output"),
])
def test_sse_failures_are_typed(chunks, category):
    with pytest.raises(SamLiveError) as exc:
        _read_sse(chunks, max_bytes=4096)
    assert exc.value.category == category


def test_sse_oversize_is_bounded():
    with pytest.raises(SamLiveError) as exc:
        _read_sse([b"x" * 10], max_bytes=9)
    assert exc.value.category == "response_too_large"


@pytest.mark.parametrize("override,category", [
    ({"cli_authorized": False}, "guard_refused"),
    ({"environ": {"META_API_KEY": "SYNTHETIC-META-KEY"}}, "guard_refused"),
    ({"max_spend_usd": None}, "guard_refused"),
    ({"ledger_path": ""}, "guard_refused"),
    ({"environ": {"MYDRAK_LIVE": "1"}}, "missing_key"),
])
def test_global_live_gates_refuse_before_transport(tmp_path, override, category):
    transport = FakeStreamTransport()
    values = {
        "config": config(), "cli_authorized": True,
        "max_spend_usd": "0.01", "ledger_path": str(tmp_path / "ledger.sqlite3"),
        "environ": {"MYDRAK_LIVE": "1", "META_API_KEY": "SYNTHETIC-META-KEY"},
        "campaign_guard": campaign(tmp_path), "transport": transport,
    }
    values.update(override)
    instance = SamLiveClient(**values)
    with pytest.raises(SamLiveError) as exc:
        instance.send(prompt="red square", preprocessed_image=IMAGE,
                      expected_width=4, expected_height=4)
    assert exc.value.category == category
    assert instance.last_request_sent is False
    assert transport.calls == []


def test_sam_campaign_guard_refuses_without_spending_or_dispatch(tmp_path):
    guard = LiveCampaignGuard(campaign_id="sam-unauthorized", state_dir=tmp_path / "guard")
    transport = FakeStreamTransport()
    instance = client(tmp_path, transport, campaign_guard=guard)
    with pytest.raises(SamLiveError) as exc:
        instance.send(prompt="red square", preprocessed_image=IMAGE,
                      expected_width=4, expected_height=4)
    assert (exc.value.category, exc.value.condition) == ("guard_refused", "sam_campaign")
    assert instance.last_request_sent is False and transport.calls == []
    assert not (tmp_path / "ledger.sqlite3").exists()


@pytest.mark.parametrize("field,value", [
    ("model_id", "other-model"),
    ("endpoint", "http://api.meta.ai/v1"),
    ("request_path", "/other"),
    ("credential_env_var", "MODEL_API_KEY"),
    ("timeout_s", 0),
    ("max_response_bytes", True),
    ("max_input_tokens_estimate", None),
    ("price_per_1k_images", "TODO(verify)"),
])
def test_sam_config_gates_fail_closed(field, value, tmp_path):
    values = config() | {field: value}
    with pytest.raises(SamLiveError) as exc:
        SamLiveClient(
            values, cli_authorized=True, max_spend_usd="0.01",
            ledger_path=str(tmp_path / "ledger.sqlite3"),
            environ={"MYDRAK_LIVE": "1", "META_API_KEY": "SYNTHETIC-META-KEY"},
            campaign_guard=campaign(tmp_path), transport=FakeStreamTransport(),
        )
    assert exc.value.category == "config_invalid"
    assert not (tmp_path / "ledger.sqlite3").exists()


def test_sam_scope_breaker_and_request_validation_fail_closed(tmp_path):
    wrong_scope = campaign(tmp_path, scope="different-scope")
    transport = FakeStreamTransport()
    instance = client(tmp_path, transport, campaign_guard=wrong_scope)
    with pytest.raises(SamLiveError, match="SAM live request failed"):
        instance.send(prompt="red square", preprocessed_image=IMAGE,
                      expected_width=4, expected_height=4)
    assert transport.calls == []
    exhausted = campaign(tmp_path, attempts=5)
    instance = client(tmp_path, transport, campaign_guard=exhausted)
    with pytest.raises(SamLiveError) as exc:
        instance.send(prompt="red square", preprocessed_image=IMAGE,
                      expected_width=4, expected_height=4)
    assert exc.value.category == "guard_refused" and transport.calls == []
    with pytest.raises(SamLiveError) as bad_input:
        client(tmp_path, transport).send(prompt="", preprocessed_image=IMAGE,
                                         expected_width=4, expected_height=4)
    assert bad_input.value.condition == "prompt" and transport.calls == []


def test_transport_failures_and_parse_failure_have_no_raw_content(tmp_path):
    broken = client(tmp_path, FakeStreamTransport(error=SamSseTransportError("http_error", status=429)))
    with pytest.raises(SamLiveError) as exc:
        broken.send(prompt="red square", preprocessed_image=IMAGE,
                    expected_width=4, expected_height=4)
    assert (exc.value.category, exc.value.status) == ("http_error", 429)
    malformed = client(tmp_path, FakeStreamTransport([
        event({"type": "response.output_text.delta", "delta": "PRIVATE-RAW-RESPONSE"}),
        b"data: [DONE]\n\n",
    ]))
    with pytest.raises(SamLiveError) as parse_exc:
        malformed.send(prompt="red square", preprocessed_image=IMAGE,
                       expected_width=4, expected_height=4)
    assert parse_exc.value.category == "parse_invalid"
    assert "PRIVATE-RAW-RESPONSE" not in str(parse_exc.value)


def test_key_and_output_text_do_not_appear_in_result_repr(tmp_path):
    result = client(tmp_path).send(
        prompt="red square", preprocessed_image=IMAGE,
        expected_width=4, expected_height=4,
    )
    assert "SYNTHETIC-META-KEY" not in repr(result)
    assert FRAME_TEXT not in repr(result)


def test_structural_summary_reports_lengths_without_raw_strings():
    private = "SYNTHETIC-PRIVATE-OUTPUT"
    summary = _structure_summary(json.dumps({"message": private, "items": ["x", "y"]}))
    assert "is_json=true" in summary
    assert '"message"' in summary and "2" in summary
    assert private not in summary


def test_sam_http_transport_does_not_follow_redirects():
    transport = UrllibSseTransport()

    class RedirectResponse:
        calls = 0

        def open(self, request, timeout):
            self.calls += 1
            raise HTTPError(request.full_url, 302, "redirect", {}, None)

    fake = RedirectResponse()
    transport._opener = fake
    with pytest.raises(SamSseTransportError) as error:
        transport.post_sse(
            "https://api.meta.ai/v1/responses",
            headers={"Authorization": "Bearer synthetic"},
            json_body={"stream": True}, timeout_s=2, max_response_bytes=100,
        )
    assert error.value.category == "http_error"
    assert error.value.status == 302
    assert fake.calls == 1


@pytest.mark.parametrize(("condition", "expected"), [
    ("spend_cap", "spend_cap"),
    ("../../synthetic-secret", "unknown"),
])
def test_sam_smoke_guard_refusal_prints_safe_condition_only(monkeypatch, condition, expected):
    class StubClient:
        last_request_sent = False
        last_estimated_cost_usd = None

        def __init__(self, *_args, **_kwargs):
            pass

        def send(self, **_kwargs):
            raise SamLiveError("guard_refused", condition=condition)

    monkeypatch.setattr(smoke_sam, "_ROOT", REPO_ROOT)
    monkeypatch.setattr(smoke_sam, "load_live_provider_config", lambda *_args: {})
    monkeypatch.setattr(smoke_sam, "LiveCampaignGuard", lambda **_kwargs: object())
    monkeypatch.setattr(smoke_sam, "SamLiveClient", StubClient)
    lines = []
    result = smoke_sam.run(
        ["--live-authorized", "--max-spend-usd", "0.01"],
        environ={"MYDRAK_LIVE": "1", "META_API_KEY": "SYNTHETIC-NO-OUTPUT"},
        output=lines.append,
    )
    assert result == 1 and len(lines) == 1
    assert "failure_category=guard_refused" in lines[0]
    assert f"guard_condition={expected}" in lines[0]
    assert "SYNTHETIC-NO-OUTPUT" not in lines[0]
