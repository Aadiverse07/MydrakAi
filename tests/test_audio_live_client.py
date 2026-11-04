"""Hermetic tests for voice conversion and guarded transcription."""

from __future__ import annotations

from decimal import Decimal
import io
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from io import StringIO
from urllib.parse import parse_qs, urlsplit
import uuid
import wave

import pytest
import yaml

from conftest import REPO_ROOT
from mydrak.audio.client import (
    VoiceClientError, VoiceTranscriptionClient,
)
from mydrak.audio.convert import AudioConversionError, convert_audio, validate_wav
from mydrak.audio.http import VoiceTransportError
from mydrak.live.guard import load_live_provider_config
from scripts import smoke_voice


def make_wav(seconds=2, *, rate=24000, channels=1, width=2):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(b"\0" * int(seconds * rate * channels * width))
    return output.getvalue()


class FakeMultipart:
    def __init__(self, response=None, status=200, error=None):
        self.response = response if response is not None else json.dumps({"transcript": "synthetic phrase", "audioDurationMs": 2000, "turns": []}).encode()
        self.status = status
        self.error = error
        self.calls = []

    def post_multipart(self, url, *, headers, body, timeout_s, max_response_bytes):
        self.calls.append((url, dict(headers), body, timeout_s, max_response_bytes))
        if self.error:
            raise self.error
        return self.status, self.response


def cfg():
    return load_live_provider_config(REPO_ROOT / "config/models.yaml", "voice")


def make_client(tmp_path, transport=None, *, env=None, authorized=True, cap="0.01", config=None):
    return VoiceTranscriptionClient(
        config or cfg(), cli_authorized=authorized, max_spend_usd=cap,
        ledger_path=str(tmp_path / "spend.sqlite3"),
        environ=env or {"MYDRAK_LIVE": "1", "META_API_KEY": "SYNTHETIC-VOICE-KEY"},
        transport=transport or FakeMultipart(),
    )


def test_voice_request_multipart_headers_response_and_cost(tmp_path):
    fake = FakeMultipart()
    result = make_client(tmp_path, fake).transcribe(make_wav(3.2))
    assert result.transcript == "synthetic phrase"
    assert "synthetic phrase" not in repr(result)
    assert result.audio_seconds == pytest.approx(3.2)
    assert result.turns_count == 0
    assert result.estimated_cost_usd == Decimal("0.0002")
    url, headers, body, timeout, max_response = fake.calls[0]
    assert url.startswith("https://api.meta.ai/v1/asr/transcribe?sessionId=")
    session_id = parse_qs(urlsplit(url).query)["sessionId"][0]
    assert uuid.UUID(session_id).version == 4
    assert headers["Authorization"].startswith("Bearer ")
    assert headers["Accept"] == "application/json"
    boundary = headers["Content-Type"].split("boundary=", 1)[1]
    assert f'name="request"\r\nContent-Type: application/json'.encode() in body
    assert f'name="audio"; filename="audio.wav"\r\nContent-Type: audio/wav'.encode() in body
    assert b'"mode":"PUSH_TO_TALK"' in body
    assert b'"model":"muse-voice-transcribe-1.0"' in body
    assert b'"audioEncoding":"WAV"' in body
    request_part = body.split(b"\r\n\r\n", 1)[1].split(b"\r\n--" + boundary.encode(), 1)[0]
    assert json.loads(request_part) == {
        "mode": "PUSH_TO_TALK", "model": "muse-voice-transcribe-1.0",
        "audioEncoding": "WAV", "languageBias": ["Hindi", "English"],
        "keywords": ["tomato", "potato", "soybean", "टमाटर", "आलू", "सोयाबीन"],
    }
    assert body.startswith(f"--{boundary}".encode())
    assert body.endswith(f"--{boundary}--\r\n".encode())
    assert timeout == 30
    assert max_response > 0


def test_empty_transcript_is_valid_typed_result(tmp_path):
    fake = FakeMultipart(response=b'{"transcript":"","turns":[]}')
    result = make_client(tmp_path, fake).transcribe(make_wav(1))
    assert result.status == "empty_transcript"
    assert result.transcript == ""


@pytest.mark.parametrize("response", [
    b"not-json", b'{"transcript":3}', b'{"transcript":"x","audioDurationMs":true}',
    b'{"transcript":"x","turns":{}}',
])
def test_invalid_voice_responses_fail_closed(tmp_path, response):
    with pytest.raises(VoiceClientError) as error:
        make_client(tmp_path, FakeMultipart(response=response)).transcribe(make_wav(1))
    assert error.value.category == "response_invalid"


@pytest.mark.parametrize(("status", "category"), [
    (400, "bad_audio"), (406, "unsupported_accept"), (413, "request_too_large"),
    (429, "rate_limited"), (500, "provider_error"), (418, "http_error"),
])
def test_documented_http_failure_categories(tmp_path, status, category):
    client = make_client(tmp_path, FakeMultipart(status=status))
    with pytest.raises(VoiceClientError) as error:
        client.transcribe(make_wav(1))
    assert error.value.category == category
    assert error.value.status == status
    assert client.last_request_sent is True


@pytest.mark.parametrize(("failure", "category"), [
    (VoiceTransportError("timeout"), "timeout"),
    (VoiceTransportError("network_error"), "network_error"),
])
def test_transport_failures_are_sanitized_and_never_retried(tmp_path, failure, category):
    fake = FakeMultipart(error=failure)
    client = make_client(tmp_path, fake)
    with pytest.raises(VoiceClientError) as caught:
        client.transcribe(make_wav(1))
    assert caught.value.category == category
    assert len(fake.calls) == 1
    assert "SYNTHETIC-VOICE-KEY" not in str(caught.value)


def test_missing_key_and_guard_refusal_are_before_dispatch(tmp_path):
    fake = FakeMultipart()
    client = make_client(tmp_path, fake, env={"MYDRAK_LIVE": "1"})
    with pytest.raises(VoiceClientError) as error:
        client.transcribe(make_wav(1))
    assert error.value.category == "missing_key"
    assert not fake.calls and client.last_request_sent is False

    fake2 = FakeMultipart()
    client2 = make_client(tmp_path, fake2, authorized=False)
    with pytest.raises(VoiceClientError) as error2:
        client2.transcribe(make_wav(1))
    assert error2.value.category == "guard_refused"
    assert not fake2.calls and client2.last_request_sent is False


def test_bad_cost_or_cap_fails_before_dispatch(tmp_path):
    config = dict(cfg())
    config["price_per_1k_minutes"] = None
    fake = FakeMultipart()
    with pytest.raises(VoiceClientError, match="voice transcription request failed"):
        make_client(tmp_path, fake, config=config).transcribe(make_wav(1))
    assert not fake.calls
    fake2 = FakeMultipart()
    with pytest.raises(VoiceClientError) as error:
        make_client(tmp_path, fake2, cap="0.000001").transcribe(make_wav(2))
    assert error.value.category == "guard_refused"
    assert not fake2.calls


@pytest.mark.parametrize(("field", "value"), [
    ("model_id", "other"), ("endpoint", "http://api.meta.ai/v1"),
    ("request_path", "/other"), ("credential_env_var", "MODEL_API_KEY"),
    ("mode", "ENDPOINTING"), ("max_audio_seconds", 0),
    ("max_input_bytes", True), ("max_upload_bytes", 0),
    ("target_sample_rate", 16000),
])
def test_invalid_voice_configuration_refuses_before_dispatch(tmp_path, field, value):
    fake = FakeMultipart()
    config = dict(cfg())
    config[field] = value
    with pytest.raises(VoiceClientError) as error:
        make_client(tmp_path, fake, config=config).transcribe(make_wav(1))
    assert error.value.category == "config_invalid"
    assert fake.calls == []


def test_response_key_and_transcript_are_not_in_error_surface(tmp_path):
    secretish = "SYNTHETIC-PRIVATE-TRANSCRIPT-DO-NOT-LEAK"
    fake = FakeMultipart(response=secretish.encode(), status=500)
    client = make_client(tmp_path, fake)
    with pytest.raises(VoiceClientError) as caught:
        client.transcribe(make_wav(1))
    assert secretish not in str(caught.value)
    assert "SYNTHETIC-VOICE-KEY" not in repr(caught.value)
    assert "SYNTHETIC-VOICE-KEY" not in str(caught.value.__cause__)


def test_conversion_exact_ffmpeg_args_shell_false_and_temp_cleanup(tmp_path):
    output_wav = make_wav(1)
    seen = {}

    def runner(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        Path(command[-1]).write_bytes(output_wav)
        return subprocess.CompletedProcess(command, 0)

    converted, info = convert_audio(
        b"synthetic ogg input", max_input_bytes=100, max_upload_bytes=100000,
        max_audio_seconds=60, ffmpeg_path="/usr/bin/ffmpeg", runner=runner,
    )
    assert converted == output_wav
    assert info.duration_seconds == pytest.approx(1)
    cmd = seen["command"]
    assert cmd[1:-1] == [
        "-nostdin", "-hide_banner", "-loglevel", "error", "-i", cmd[6],
        "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", "-map_metadata", "-1",
    ]
    assert seen["kwargs"]["shell"] is False
    assert seen["kwargs"]["timeout"] == 30
    assert not Path(cmd[5]).exists() and not Path(cmd[-1]).exists()


def test_converter_rejects_oversize_before_runner_and_missing_ffmpeg(monkeypatch):
    called = False

    def runner(*_args, **_kwargs):
        nonlocal called
        called = True

    with pytest.raises(AudioConversionError) as error:
        convert_audio(b"1234", max_input_bytes=3, max_upload_bytes=100,
                      max_audio_seconds=2, ffmpeg_path="ffmpeg", runner=runner)
    assert error.value.category == "input_too_large" and not called
    monkeypatch.setattr("mydrak.audio.convert.shutil.which", lambda _name: None)
    with pytest.raises(AudioConversionError) as missing:
        convert_audio(b"x", max_input_bytes=2, max_upload_bytes=100,
                      max_audio_seconds=2, runner=runner)
    assert missing.value.category == "ffmpeg_missing"


@pytest.mark.parametrize("options", [
    {"rate": 16000}, {"channels": 2}, {"width": 1}, {"seconds": 61},
])
def test_wav_shape_and_duration_limits(options):
    with pytest.raises(AudioConversionError):
        validate_wav(make_wav(**options), max_audio_seconds=60,
                     max_upload_bytes=3_000_000)


def test_wav_upload_size_and_corruption_are_rejected():
    with pytest.raises(AudioConversionError) as oversized:
        validate_wav(make_wav(1), max_audio_seconds=60, max_upload_bytes=10)
    assert oversized.value.category == "upload_too_large"
    with pytest.raises(AudioConversionError) as corrupt:
        validate_wav(b"bad", max_audio_seconds=60, max_upload_bytes=100)
    assert corrupt.value.category == "wav_invalid"


def test_voice_model_config_contains_only_approved_project_bounds():
    raw = yaml.safe_load((REPO_ROOT / "config/models.yaml").read_text())
    assert raw["voice"]["request_path"] == "/asr/transcribe"
    assert raw["voice"]["max_audio_seconds"] == 60
    assert raw["voice"]["max_input_bytes"] == 1_000_000
    assert raw["voice"]["max_upload_bytes"] == 3_000_000


def test_voice_smoke_hides_transcript_unless_explicitly_requested(monkeypatch):
    transcript = "SYNTHETIC-TEST-TRANSCRIPT"

    class StubClient:
        last_request_sent = False
        last_estimated_cost_usd = None

        def __init__(self, *_args, **_kwargs):
            pass

        def transcribe(self, audio):
            validate_wav(audio, max_audio_seconds=60, max_upload_bytes=3_000_000)
            self.last_request_sent = True
            return SimpleNamespace(
                transcript=transcript, audio_seconds=2.0, turns_count=0,
                estimated_cost_usd=Decimal("0.0001"), status="response_received",
            )

    monkeypatch.setattr(smoke_voice, "VoiceTranscriptionClient", StubClient)
    output: list[str] = []
    err = StringIO()
    rc = smoke_voice.run(
        ["--max-spend-usd", "0.01"],
        environ={"MYDRAK_LIVE": "1", "META_API_KEY": "SYNTHETIC-KEY"},
        output=output.append, stderr=err,
    )
    assert rc == 0 and len(output) == 1
    assert "transcript_chars=" in output[0] and transcript not in "\n".join(output)
    assert "WARNING" not in err.getvalue()

    output.clear()
    rc = smoke_voice.run(
        ["--max-spend-usd", "0.01", "--show-transcript"],
        environ={"MYDRAK_LIVE": "1", "META_API_KEY": "SYNTHETIC-KEY"},
        output=output.append, stderr=err,
    )
    assert rc == 0 and transcript in output[-1]
    assert "non-farmer test audio" in err.getvalue()


def test_voice_smoke_guard_refusal_prints_safe_condition_without_key(monkeypatch):
    class StubClient:
        last_request_sent = False
        last_estimated_cost_usd = None

        def __init__(self, *_args, **_kwargs):
            pass

        def transcribe(self, _audio):
            raise VoiceClientError("guard_refused", condition="MYDRAK_LIVE")

    monkeypatch.setattr(smoke_voice, "load_live_provider_config", lambda *_args: {
        "max_audio_seconds": 60, "max_input_bytes": 1_000_000,
        "max_upload_bytes": 3_000_000,
        "target_sample_rate": 24000,
    })
    monkeypatch.setattr(smoke_voice, "VoiceTranscriptionClient", StubClient)
    output = []
    result = smoke_voice.run(
        ["--live-authorized", "--max-spend-usd", "0.01"],
        environ={"MYDRAK_LIVE": "1", "META_API_KEY": "SYNTHETIC-VOICE-KEY"},
        output=output.append,
    )
    assert result == 1 and len(output) == 1
    assert "failure_category=guard_refused" in output[0]
    assert "guard_condition=MYDRAK_LIVE" in output[0]
    assert "SYNTHETIC-VOICE-KEY" not in output[0]
