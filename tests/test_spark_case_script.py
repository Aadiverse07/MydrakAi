"""Offline tests for the guarded Spark case CLI."""

import json
import socket

from PIL import Image

from scripts.run_spark_case import run_case


def jpeg(path):
    image = Image.new("RGB", (24, 24), (45, 140, 50))
    image.save(path, format="JPEG")
    return path


class NeverTransport:
    def __init__(self):
        self.calls = 0

    def post_json(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("guard-refusal path must not dispatch")


def test_cli_requires_full_live_guard_and_reports_safe_fields(tmp_path, monkeypatch):
    def no_socket(*args, **kwargs):
        raise AssertionError("offline CLI test must not open sockets")

    monkeypatch.setattr(socket, "socket", no_socket)
    monkeypatch.setattr(socket, "create_connection", no_socket)
    image_path = jpeg(tmp_path / "synthetic-public.jpg")
    transport = NeverTransport()
    lines = []
    code = run_case(
        [str(image_path), "--public-test-confirmed", "--rights-confirmed",
         "--max-spend-usd", "0.25"],
        output=lines.append, environ={"MYDRAK_LIVE": "1", "META_API_KEY": "SYNTHETIC_KEY"},
        transport=transport, trace_path=tmp_path / "trace.sqlite",
        ledger_path=tmp_path / "ledger.sqlite",
    )
    assert code == 2 and transport.calls == 0
    assert "failure_category=guard_refused" in lines[0]
    assert "guard_condition=cli_authorization" in lines[0]
    assert "request_sent=false" in lines[0]
    assert "SYNTHETIC_KEY" not in lines[0]
    assert "data:image" not in lines[0]


def test_cli_success_uses_only_fake_transport_and_prints_no_model_text(tmp_path):
    image_path = jpeg(tmp_path / "synthetic-public.jpg")
    output_json = json.dumps({
        "plant_visible": False, "crop": "unknown", "issue": "unknown",
        "alternatives": [], "symptoms_observed": [], "image_issues": [],
        "stated_confidence": "medium", "segment_prompts": [],
    })

    class FakeTransport:
        def __init__(self):
            self.calls = []

        def post_json(self, url, *, headers, body, timeout_s):
            self.calls.append((url, headers, body, timeout_s))
            return 200, json.dumps({
                "choices": [{"message": {"content": output_json}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            }).encode()

    transport = FakeTransport()
    lines = []
    code = run_case(
        [str(image_path), "--public-test-confirmed", "--rights-confirmed",
         "--live-authorized", "--max-spend-usd", "0.25"],
        output=lines.append,
        environ={"MYDRAK_LIVE": "1", "META_API_KEY": "SYNTHETIC_KEY"},
        transport=transport, trace_path=tmp_path / "trace.sqlite",
        ledger_path=tmp_path / "ledger.sqlite",
    )
    assert code == 0 and len(transport.calls) == 1
    assert "outcome_category=refer" in lines[0]
    assert "confidence=cannot tell" in lines[0]
    assert "overlay_exists=false" in lines[0] and "severity_exists=false" in lines[0]
    assert "request_sent=true" in lines[0] and "tokens_out=10" in lines[0]
    assert "estimated_cost_usd=0.000055" in lines[0]
    assert "SYNTHETIC_KEY" not in lines[0]
    assert output_json not in lines[0]
    assert "data:image" not in lines[0]
    content = transport.calls[0][2]["messages"][0]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert transport.calls[0][2]["max_tokens"] == 512
