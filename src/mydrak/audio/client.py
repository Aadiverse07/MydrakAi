"""One-shot, explicitly guarded Muse Voice Transcribe client.

The request fields and response fields follow docs/providers/meta_voice.md.
Provider compatibility, Hindi quality, and retention settings remain unverified.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING
import json
import math
from typing import Any
from urllib.parse import urlencode

from mydrak.audio.convert import AudioConversionError, WavInfo, validate_wav
from mydrak.audio.http import (
    MAX_VOICE_RESPONSE_BYTES, MultipartTransport, UrllibMultipartTransport,
    VoiceTransportError, encode_multipart,
)
from mydrak.live.guard import LiveGuardError, reserve_live_estimated_cost

VOICE_ENDPOINT = "https://api.meta.ai/v1"
VOICE_PATH = "/asr/transcribe"
VOICE_MODEL_ID = "muse-voice-transcribe-1.0"
VOICE_CREDENTIAL_ENV = "META_API_KEY"


class VoiceClientError(RuntimeError):
    """Safe machine-readable failure; never retains request/response text."""

    def __init__(self, category: str, *, status: int | None = None,
                 condition: str | None = None) -> None:
        super().__init__("voice transcription request failed")
        self.category = category
        self.status = status
        self.condition = condition


@dataclass(frozen=True)
class VoiceResult:
    transcript: str = field(repr=False)
    audio_seconds: float
    turns_count: int
    estimated_cost_usd: Decimal
    status: str = "response_received"


def _config_value(config: Mapping[str, Any], key: str, expected: type) -> Any:
    value = config.get(key)
    if expected is int:
        valid = type(value) is int
    else:
        valid = isinstance(value, expected)
    if not valid:
        raise VoiceClientError("config_invalid", condition=key)
    return value


def _validate_config(config: Mapping[str, Any]) -> tuple[int, int, int, int, float, Decimal]:
    if not isinstance(config, Mapping):
        raise VoiceClientError("config_invalid", condition="voice")
    if config.get("model_id") != VOICE_MODEL_ID:
        raise VoiceClientError("config_invalid", condition="model_id")
    if config.get("endpoint") != VOICE_ENDPOINT:
        raise VoiceClientError("config_invalid", condition="endpoint")
    if config.get("request_path") != VOICE_PATH:
        raise VoiceClientError("config_invalid", condition="request_path")
    if config.get("credential_env_var") != VOICE_CREDENTIAL_ENV:
        raise VoiceClientError("config_invalid", condition="credential_env_var")
    if config.get("mode") != "PUSH_TO_TALK":
        raise VoiceClientError("config_invalid", condition="mode")
    max_seconds = _config_value(config, "max_audio_seconds", int)
    max_input = _config_value(config, "max_input_bytes", int)
    max_upload = _config_value(config, "max_upload_bytes", int)
    sample_rate = _config_value(config, "target_sample_rate", int)
    timeout = config.get("timeout_s")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise VoiceClientError("config_invalid", condition="timeout_s")
    try:
        price = Decimal(str(config.get("price_per_1k_minutes")))
    except Exception:
        raise VoiceClientError("config_invalid", condition="price_per_1k_minutes") from None
    if not price.is_finite() or price <= 0:
        raise VoiceClientError("config_invalid", condition="price_per_1k_minutes")
    langs = config.get("language_bias")
    keywords = config.get("keywords")
    if (not isinstance(langs, list) or not langs or any(not isinstance(x, str) or not x for x in langs)
            or not isinstance(keywords, list) or any(not isinstance(x, str) or not x for x in keywords)):
        raise VoiceClientError("config_invalid", condition="language_or_keyword_bias")
    if min(max_seconds, max_input, max_upload, sample_rate) < 1:
        raise VoiceClientError("config_invalid", condition="audio_bounds")
    if sample_rate != 24000:
        raise VoiceClientError("config_invalid", condition="target_sample_rate")
    return max_seconds, max_input, max_upload, sample_rate, float(timeout), price


def _response_fields(raw: bytes) -> tuple[str, int, int]:
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError, TypeError):
        raise VoiceClientError("response_invalid") from None
    if not isinstance(document, Mapping) or not isinstance(document.get("transcript"), str):
        raise VoiceClientError("response_invalid")
    duration = document.get("audioDurationMs", 0)
    turns = document.get("turns", [])
    if type(duration) is not int or duration < 0 or not isinstance(turns, list):
        raise VoiceClientError("response_invalid")
    return document["transcript"], duration, len(turns)


class VoiceTranscriptionClient:
    """Single-request Meta voice client, never selected implicitly by Telegram."""

    def __init__(self, config: Mapping[str, Any], *, cli_authorized: bool,
                 max_spend_usd: Any, ledger_path: str,
                 environ: Mapping[str, str], transport: MultipartTransport | None = None) -> None:
        self._config = dict(config)
        self._cli_authorized = cli_authorized
        self._max_spend_usd = max_spend_usd
        self._ledger_path = ledger_path
        self._environ = environ
        self._transport = transport if transport is not None else UrllibMultipartTransport()
        self.last_request_sent = False
        self.last_estimated_cost_usd: Decimal | None = None

    def transcribe(self, wav_bytes: bytes) -> VoiceResult:
        self.last_request_sent = False
        max_seconds, _max_input, max_upload, sample_rate, timeout, price = _validate_config(self._config)
        try:
            info = validate_wav(
                wav_bytes, max_audio_seconds=max_seconds,
                max_upload_bytes=max_upload, target_sample_rate=sample_rate,
            )
        except AudioConversionError as exc:
            raise VoiceClientError(exc.category) from None
        key = self._environ.get(VOICE_CREDENTIAL_ENV)
        if not isinstance(key, str) or not key:
            raise VoiceClientError("missing_key", condition="credential_missing")
        billable_seconds = int(Decimal(str(info.duration_seconds)).to_integral_value(rounding=ROUND_CEILING))
        estimate = Decimal(billable_seconds) * price / Decimal(1000 * 60)
        try:
            reserve_live_estimated_cost(
                self._config, estimated_usd=estimate,
                cli_authorized=self._cli_authorized, environ=self._environ,
                max_spend_usd=self._max_spend_usd, ledger_path=self._ledger_path,
                credential_env_var=VOICE_CREDENTIAL_ENV,
            )
        except LiveGuardError as exc:
            condition = getattr(exc, "condition", None)
            category = "missing_key" if condition == "credential_missing" else "guard_refused"
            raise VoiceClientError(category, condition=condition) from None
        request_fields = {
            "mode": self._config["mode"], "model": self._config["model_id"],
            "audioEncoding": "WAV", "languageBias": list(self._config["language_bias"]),
            "keywords": list(self._config["keywords"]),
        }
        boundary, body = encode_multipart(request_fields, wav_bytes)
        session_id = __import__("uuid").uuid4().hex
        url = VOICE_ENDPOINT + VOICE_PATH + "?" + urlencode({"sessionId": session_id})
        headers = {
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        self.last_estimated_cost_usd = estimate
        try:
            self.last_request_sent = True
            status, raw = self._transport.post_multipart(
                url, headers=headers, body=body, timeout_s=timeout,
                max_response_bytes=MAX_VOICE_RESPONSE_BYTES,
            )
        except VoiceTransportError as exc:
            raise VoiceClientError(exc.category) from None
        except Exception:
            raise VoiceClientError("network_error") from None
        if not isinstance(status, int) or status < 100 or status > 599:
            raise VoiceClientError("response_invalid")
        if status != 200:
            category = {400: "bad_audio", 406: "unsupported_accept", 413: "request_too_large",
                        429: "rate_limited", 500: "provider_error"}.get(status, "http_error")
            raise VoiceClientError(category, status=status)
        if not isinstance(raw, bytes) or len(raw) > MAX_VOICE_RESPONSE_BYTES:
            raise VoiceClientError("response_too_large")
        transcript, _duration_ms, turns_count = _response_fields(raw)
        return VoiceResult(
            transcript=transcript, audio_seconds=info.duration_seconds,
            turns_count=turns_count, estimated_cost_usd=estimate,
            status="empty_transcript" if transcript == "" else "response_received",
        )
