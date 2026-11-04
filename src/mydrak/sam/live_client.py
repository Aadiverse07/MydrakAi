"""Explicitly guarded SAM 3.1 streaming client; unrelated to the fake scan path.

Request nesting follows the local user-supplied provider note. The endpoint
path, auth header, base64 image data URL, terminal event names, and exact
output grammar remain partly UNVERIFIED. No fallback or retry is performed.
"""

from __future__ import annotations

import base64
import codecs
import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from mydrak.live.guard import (
    LiveGuardError,
    reserve_live_estimated_cost,
)
from mydrak.sam.client import SAM_API_BASE_URL, SAM_DOCUMENTED_MODEL_ID, serialize_sam_body
from mydrak.sam.guard import LiveCampaignGuard
from mydrak.sam.http_transport import (
    SamSseTransportError,
    SseTransport,
    UrllibSseTransport,
)
from mydrak.sam.response_text import SamFrame, SamResponseError, parse_response_text

SAM_RESPONSES_PATH = "/responses"  # SDK-convention inference; UNVERIFIED.
SAM_CREDENTIAL_ENV = "META_API_KEY"
DEFAULT_SAM_CAMPAIGN = "sam-live-smoke"
DEFAULT_SAM_SCOPE = "synthetic-red-square-smoke"


class SamLiveError(RuntimeError):
    """Safe failure category and status; never stores request/response text."""

    def __init__(self, category: str, *, status: int | None = None,
                 condition: str | None = None) -> None:
        super().__init__("SAM live request failed")
        self.category = category
        self.status = status
        self.condition = condition


@dataclass(frozen=True)
class SamLiveResult:
    frame: SamFrame = field(repr=False)
    output_text: str = field(repr=False)
    estimated_cost_usd: Decimal
    streamed_chars: int
    parse_ok: bool = True


def _positive_int(value: Any, field_name: str) -> int:
    if type(value) is not int or value < 1:
        raise SamLiveError("config_invalid", condition=field_name)
    return value


def _read_sse(chunks: Iterable[bytes], *, max_bytes: int) -> str:
    """Decode Responses SSE incrementally and collect only output-text deltas."""
    if type(max_bytes) is not int or max_bytes < 1:
        raise SamLiveError("config_invalid", condition="max_response_bytes")
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    pending = ""
    data_lines: list[str] = []
    total = 0
    output: list[str] = []
    done = False

    def consume_event(lines: list[str]) -> bool:
        if not lines:
            return False
        data = "\n".join(lines)
        if data == "[DONE]":
            return True
        try:
            event = json.loads(data)
        except (ValueError, TypeError):
            raise SamLiveError("response_invalid") from None
        if not isinstance(event, Mapping):
            raise SamLiveError("response_invalid")
        kind = event.get("type")
        if kind in {"error", "response.failed"}:
            # These terminal names follow convention and remain UNVERIFIED.
            raise SamLiveError("provider_error")
        if kind == "response.output_text.delta":
            delta = event.get("delta")
            if not isinstance(delta, str):
                raise SamLiveError("response_invalid")
            output.append(delta)
        return False

    try:
        for chunk in chunks:
            if not isinstance(chunk, bytes):
                raise SamLiveError("response_invalid")
            total += len(chunk)
            if total > max_bytes:
                raise SamLiveError("response_too_large")
            pending += decoder.decode(chunk)
            while "\n" in pending:
                line, pending = pending.split("\n", 1)
                line = line[:-1] if line.endswith("\r") else line
                if line == "":
                    done = consume_event(data_lines)
                    data_lines = []
                    if done:
                        break
                    continue
                if line.startswith(":"):
                    continue
                field_name, sep, value = line.partition(":")
                if not sep:
                    value = ""
                elif value.startswith(" "):
                    value = value[1:]
                if field_name == "data":
                    data_lines.append(value)
                # `event:` and unknown SSE fields are intentionally ignored.
            if done:
                break
        pending += decoder.decode(b"", final=True)
        if pending and not done:
            if pending.endswith("\r"):
                pending = pending[:-1]
            if pending.startswith("data:"):
                value = pending[5:]
                data_lines.append(value[1:] if value.startswith(" ") else value)
        if data_lines and not done:
            consume_event(data_lines)
    except SamLiveError:
        raise
    except (UnicodeError, OSError, TypeError):
        raise SamLiveError("response_invalid") from None
    text = "".join(output)
    if not text:
        raise SamLiveError("empty_output")
    return text


class SamLiveClient:
    """One guarded call. Never selected by the application's mock transport."""

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        cli_authorized: bool,
        max_spend_usd: Any,
        ledger_path: str,
        environ: Mapping[str, str],
        campaign_guard: LiveCampaignGuard,
        transport: SseTransport | None = None,
    ) -> None:
        self._config = dict(config)
        self._cli_authorized = cli_authorized
        self._max_spend_usd = max_spend_usd
        self._ledger_path = ledger_path
        self._environ = environ
        self._campaign_guard = campaign_guard
        self._transport = transport if transport is not None else UrllibSseTransport()
        self.last_request_sent = False
        self.last_estimated_cost_usd: Decimal | None = None
        self._validate_config()

    def _validate_config(self) -> None:
        config = self._config
        if config.get("model_id") != SAM_DOCUMENTED_MODEL_ID:
            raise SamLiveError("config_invalid", condition="model_id")
        if config.get("endpoint") != SAM_API_BASE_URL:
            raise SamLiveError("config_invalid", condition="endpoint")
        if config.get("request_path") != SAM_RESPONSES_PATH:
            raise SamLiveError("config_invalid", condition="request_path")
        if config.get("credential_env_var") != SAM_CREDENTIAL_ENV:
            raise SamLiveError("config_invalid", condition="credential_env_var")
        timeout = config.get("timeout_s")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise SamLiveError("config_invalid", condition="timeout_s")
        if not math.isfinite(timeout) or timeout <= 0:
            raise SamLiveError("config_invalid", condition="timeout_s")
        _positive_int(config.get("max_response_bytes"), "max_response_bytes")
        _positive_int(config.get("max_input_tokens_estimate"), "max_input_tokens_estimate")
        price = config.get("price_per_1k_images")
        try:
            decimal_price = Decimal(str(price))
        except Exception:
            raise SamLiveError("config_invalid", condition="price_per_1k_images") from None
        if not decimal_price.is_finite() or decimal_price <= 0:
            raise SamLiveError("config_invalid", condition="price_per_1k_images")

    def send(
        self,
        *,
        prompt: str,
        preprocessed_image: bytes,
        expected_width: int,
        expected_height: int,
        scope: str = DEFAULT_SAM_SCOPE,
    ) -> SamLiveResult:
        self.last_request_sent = False
        if not isinstance(prompt, str) or not prompt or len(prompt) > 500:
            raise SamLiveError("config_invalid", condition="prompt")
        if not isinstance(preprocessed_image, bytes) or not preprocessed_image:
            raise SamLiveError("config_invalid", condition="image")
        if type(expected_width) is not int or expected_width < 1 or type(expected_height) is not int or expected_height < 1:
            raise SamLiveError("config_invalid", condition="image_dimensions")
        if not isinstance(scope, str) or not scope:
            raise SamLiveError("guard_refused", condition="scope")
        if type(self._campaign_guard) is not LiveCampaignGuard:
            raise SamLiveError("guard_refused", condition="campaign_guard")
        # Check the durable SAM-specific campaign authorization before writing
        # any spend reservation or consuming an attempt.
        try:
            if (
                not self._campaign_guard.authorized
                or self._campaign_guard.scope != scope
                or self._campaign_guard.breaker_tripped
                or self._campaign_guard.attempts_remaining < 1
            ):
                raise LiveGuardError("campaign authorization is missing or mismatched")
        except LiveGuardError:
            raise SamLiveError("guard_refused", condition="sam_campaign") from None

        try:
            price = Decimal(str(self._config["price_per_1k_images"]))
            estimate = price / Decimal(1000)
            reservation = reserve_live_estimated_cost(
                self._config, estimated_usd=estimate,
                cli_authorized=self._cli_authorized, environ=self._environ,
                max_spend_usd=self._max_spend_usd,
                ledger_path=self._ledger_path,
                credential_env_var=SAM_CREDENTIAL_ENV,
            )
        except LiveGuardError as exc:
            condition = getattr(exc, "condition", None)
            category = "missing_key" if condition == "credential_missing" else "guard_refused"
            raise SamLiveError(category, condition=condition) from None
        try:
            self._campaign_guard.authorize_attempt(scope=scope)
        except LiveGuardError:
            raise SamLiveError("guard_refused", condition="sam_campaign") from None

        image_ref = "data:image/jpeg;base64," + base64.b64encode(preprocessed_image).decode("ascii")
        body = serialize_sam_body(
            model_id=SAM_DOCUMENTED_MODEL_ID, prompt=prompt,
            image_ref=image_ref, stream=True,
        )
        headers = {
            "Authorization": f"Bearer {self._environ[SAM_CREDENTIAL_ENV]}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        url = SAM_API_BASE_URL + SAM_RESPONSES_PATH
        self.last_estimated_cost_usd = reservation.estimated_usd
        try:
            self.last_request_sent = True
            chunks = self._transport.post_sse(
                url, headers=headers, json_body=body,
                timeout_s=float(self._config["timeout_s"]),
                max_response_bytes=self._config["max_response_bytes"],
            )
            output_text = _read_sse(
                chunks, max_bytes=self._config["max_response_bytes"],
            )
        except SamLiveError:
            raise
        except SamSseTransportError as exc:
            raise SamLiveError(exc.category, status=exc.status) from None
        except TimeoutError:
            raise SamLiveError("timeout") from None
        except Exception:
            raise SamLiveError("network_error") from None

        try:
            frame = parse_response_text(
                output_text,
                expected_width=expected_width,
                expected_height=expected_height,
            )
        except (SamResponseError, TypeError, ValueError):
            raise SamLiveError("parse_invalid") from None
        return SamLiveResult(
            frame=frame, output_text=output_text,
            estimated_cost_usd=reservation.estimated_usd,
            streamed_chars=len(output_text),
        )
