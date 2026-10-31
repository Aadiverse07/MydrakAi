"""Guarded Together Glimmer and Meta Spark diagnosis clients.

Request fields follow the user-supplied references in ``docs/providers``.
The references are not independent provider verification. This module has no
default use in the mock workflow; callers must explicitly construct a client.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Collection, Mapping
from decimal import Decimal
from http import HTTPStatus
import json
import os
import socket
import time
from typing import Any
from urllib.error import URLError

from mydrak.live.guard import LiveConfigError, LiveGuardError, reserve_live_call
from mydrak.live.http import MAX_RESPONSE_BYTES, JsonTransport, UrllibJsonTransport
from mydrak.live.provider_contract import (
    chat_completions_url, parse_chat_response, require_text, validate_vocabulary,
)
from mydrak.live.retry import call_with_retries
from mydrak.privacy.data_policy import (
    DataClass, DataPolicy, DataPolicyError,
)
from mydrak.trace.store import TraceStep, estimate_token_cost
from mydrak.vision.diagnosis import DiagnosisProvider

MAX_PROVIDER_RESPONSE_BYTES = MAX_RESPONSE_BYTES
_B8_INSTRUCTIONS = (
    "Return only one JSON object with exactly these fields: plant_visible (boolean), "
    "crop (supported crop ID or unknown), issue (supported disease ID or unknown), "
    "alternatives (array of supported disease IDs), symptoms_observed (array of strings), "
    "image_issues (array of strings), stated_confidence (0..1 number or configured band), "
    "segment_prompts (array of strings). Describe visible symptoms before naming an issue. "
    "Do not include treatment advice, dosages, or chemical names. If no plant is visible, "
    "set plant_visible false and crop and issue to unknown."
)


class LiveDiagnosisError(RuntimeError):
    """Provider request failed with a sanitized, caller-safe error."""

    def __init__(self, message: str, *, category: str = "network_error",
                 http_status: int | None = None, http_reason: str | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.http_status = http_status
        self.http_reason = http_reason


class RetryableProviderError(LiveDiagnosisError):
    """A provider transport/HTTP/envelope error eligible for B11 retry."""


class ProviderTraceError(LiveDiagnosisError):
    """Trace callback failed after a request attempt."""


class _BaseClient(DiagnosisProvider):
    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        cli_authorized: bool,
        max_spend_usd: Any,
        ledger_path: str,
        credential_env_var: str,
        environ: Mapping[str, str] | None,
        transport: JsonTransport,
        trace_callback: Callable[[TraceStep], None] | None,
        retry_delays_s: tuple[float, ...],
        sleep: Callable[[float], None],
        supported_crops: Collection[str],
        disease_ids: Collection[str],
        confidence_bands: Collection[str],
    ) -> None:
        self._config = dict(config)
        self._cli_authorized = cli_authorized
        self._max_spend_usd = max_spend_usd
        self._ledger_path = ledger_path
        self._credential_env_var = credential_env_var
        self._environ = os.environ if environ is None else environ
        self._transport = transport
        self._trace_callback = trace_callback
        self._retry_delays_s = retry_delays_s
        self._sleep = sleep
        self._supported_crops = validate_vocabulary(supported_crops, "crop")
        self._disease_ids = validate_vocabulary(disease_ids, "disease")
        self._confidence_bands = validate_vocabulary(confidence_bands, "confidence")
        if not callable(trace_callback):
            raise ValueError("a trace callback is required")
        self.last_step: TraceStep | None = None
        self.last_request_sent = False
        self.request_ever_sent = False
        self.last_guard_condition: str | None = None
        self.last_config_condition: str | None = None
        self._last_failure: tuple[str, int | None, str | None] = ("network_error", None, None)

    def generate(self) -> object:
        return self._request(self._prompt())

    def repair(self, invalid_output: str) -> object:
        if not isinstance(invalid_output, str):
            raise LiveDiagnosisError("invalid output cannot be repaired")
        repair_prompt = (
            self._prompt() + " Repair the following prior response into the required JSON only: "
            + invalid_output
        )
        return self._request(repair_prompt)

    def _request(self, text: str) -> str:
        self.last_request_sent = False
        self.last_guard_condition = None
        self.last_config_condition = None
        self._last_failure = ("network_error", None, None)
        try:
            url = chat_completions_url(self._config.get("endpoint"))
            model = require_text(self._config.get("model_id"), "model ID")
            body = self._body(model, text)
        except LiveConfigError as exc:
            self.last_config_condition = exc.condition
            raise
        except (KeyError, TypeError, ValueError):
            self.last_config_condition = "provider_request"
            raise LiveConfigError("provider configuration or request is invalid", condition="provider_request") from None

        def attempt() -> str:
            try:
                reserve_live_call(
                    self._config, cli_authorized=self._cli_authorized,
                    environ=self._environ, max_spend_usd=self._max_spend_usd,
                    ledger_path=self._ledger_path, credential_env_var=self._credential_env_var,
                )
            except LiveGuardError as exc:
                self.last_guard_condition = exc.condition
                raise
            key = self._environ.get(self._credential_env_var)
            if not isinstance(key, str) or not key:
                raise LiveGuardError("required credential environment variable is missing")
            started = time.perf_counter()
            transport_error: Exception | None = None
            try:
                self.last_request_sent = True
                self.request_ever_sent = True
                status, raw = self._transport.post_json(
                    url, headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
                    body=body, timeout_s=float(self._config["timeout_s"]),
                )
            except Exception as exc:
                transport_error = exc
            elapsed_ms = max(0.0, (time.perf_counter() - started) * 1000)
            if transport_error is not None:
                category = _transport_failure_category(transport_error)
                self._last_failure = (category, None, None)
                self._record(None, None, None, category, elapsed_ms)
                raise RetryableProviderError("provider request failed", category=category) from None
            if type(status) is not int or not 100 <= status <= 599 or not isinstance(raw, bytes):
                self._last_failure = ("response_invalid", None, None)
                self._record(None, None, None, "response_invalid", elapsed_ms)
                raise RetryableProviderError("provider returned an invalid response", category="response_invalid") from None
            if status < 200 or status >= 300:
                reason = HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else None
                self._last_failure = ("http_error", status, reason)
                self._record(None, None, None, "http_error", elapsed_ms)
                raise RetryableProviderError(
                    "provider returned an HTTP error", category="http_error",
                    http_status=status, http_reason=reason,
                ) from None
            if len(raw) > MAX_PROVIDER_RESPONSE_BYTES:
                self._last_failure = ("response_invalid", None, None)
                self._record(None, None, None, "response_invalid", elapsed_ms)
                raise RetryableProviderError("provider response is too large", category="response_invalid") from None
            invalid_envelope = False
            try:
                content, tokens_in, tokens_out = parse_chat_response(
                    raw, max_bytes=MAX_PROVIDER_RESPONSE_BYTES,
                )
            except (TypeError, ValueError, UnicodeError, KeyError, IndexError, RecursionError):
                invalid_envelope = True
            if invalid_envelope:
                self._record(None, None, None, "response_invalid", elapsed_ms)
                self._last_failure = ("response_invalid", None, None)
                raise RetryableProviderError("provider returned an invalid response envelope", category="response_invalid") from None
            if key in content:
                self._record(tokens_in, tokens_out, None, "response_redacted", elapsed_ms)
                self._last_failure = ("response_invalid", None, None)
                raise LiveDiagnosisError("provider response was rejected", category="response_invalid") from None
            cost = estimate_token_cost(
                tokens_in, tokens_out,
                self._config.get("price_input_per_1m"), self._config.get("price_output_per_1m"),
            ) if tokens_in is not None and tokens_out is not None else None
            self._record(tokens_in, tokens_out, cost, "completed", elapsed_ms)
            return content

        def exhausted() -> str:
            category, status, reason = self._last_failure
            raise LiveDiagnosisError(
                "provider unavailable after bounded retries", category=category,
                http_status=status, http_reason=reason,
            ) from None

        return call_with_retries(
            attempt, exhausted, retry_delays_s=self._retry_delays_s,
            sleep=self._sleep, retry_on=(RetryableProviderError,),
        )

    def _record(
        self, tokens_in: int | None, tokens_out: int | None, cost: Decimal | None,
        outcome: str, latency_ms: float,
    ) -> None:
        step = TraceStep(
            step_name=self._step_name, outcome=outcome, latency_ms=latency_ms,
            model=str(self._config.get("model_id")), tokens_in=tokens_in,
            tokens_out=tokens_out, est_cost=cost, error_code=None if outcome == "completed" else outcome,
        )
        self.last_step = step
        failed = False
        try:
            self._trace_callback(step)
        except Exception:
            failed = True
        if failed:
            raise ProviderTraceError("provider trace could not be recorded", category="response_invalid") from None

    @property
    def _step_name(self) -> str:
        raise NotImplementedError

    def _prompt(self) -> str:
        return _B8_INSTRUCTIONS + " Supported crop IDs: " + ", ".join(sorted(self._supported_crops)) + ". Supported disease IDs: " + ", ".join(sorted(self._disease_ids)) + ". Confidence bands: " + ", ".join(sorted(self._confidence_bands)) + "."

    def _body(self, model: str, text: str) -> dict[str, Any]:
        raise NotImplementedError


class GlimmerClient(_BaseClient):
    """Together-hosted image diagnosis; accepts public-test JPEG only."""

    def __init__(self, config: Mapping[str, Any], *, image_bytes: bytes,
                 data_policy: DataPolicy, data_class: DataClass,
                 public_test_marker: str, rights_confirmed: bool,
                 cli_authorized: bool, max_spend_usd: Any, ledger_path: str,
                 environ: Mapping[str, str] | None = None,
                 transport: JsonTransport | None = None,
                 trace_callback: Callable[[TraceStep], None] | None = None,
                 retry_delays_s: tuple[float, ...] = (0.1, 0.2),
                 sleep: Callable[[float], None] = time.sleep,
                 supported_crops: Collection[str] = (), disease_ids: Collection[str] = (),
                 confidence_bands: Collection[str] = ("low", "medium", "high")) -> None:
        if (data_policy is not DataPolicy.PUBLIC_TEST or data_class is not DataClass.PUBLIC_TEST
                or public_test_marker != "public-test" or rights_confirmed is not True):
            raise DataPolicyError("Glimmer accepts only rights-cleared public-test images")
        if not isinstance(image_bytes, bytes) or not image_bytes.startswith(b"\xff\xd8\xff"):
            raise ValueError("Glimmer input must be JPEG bytes")
        self._image_data = base64.b64encode(image_bytes).decode("ascii")
        super().__init__(
            config, cli_authorized=cli_authorized, max_spend_usd=max_spend_usd,
            ledger_path=ledger_path, credential_env_var="TOGETHER_API_KEY",
            environ=environ, transport=transport if transport is not None else UrllibJsonTransport(),
            trace_callback=trace_callback, retry_delays_s=retry_delays_s, sleep=sleep,
            supported_crops=supported_crops, disease_ids=disease_ids,
            confidence_bands=confidence_bands,
        )

    @property
    def _step_name(self) -> str:
        return "glimmer_together"

    def _body(self, model: str, text: str) -> dict[str, Any]:
        return {
            "model": model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {
                    "url": "data:image/jpeg;base64," + self._image_data,
                }},
            ]}],
            "max_tokens": self._config["max_tokens"],
            "temperature": 0.2,
        }


def _transport_failure_category(exc: Exception) -> str:
    reason = exc.reason if isinstance(exc, URLError) else None
    if isinstance(exc, (TimeoutError, socket.timeout)) or isinstance(reason, (TimeoutError, socket.timeout)):
        return "timeout"
    return "network_error"


def __getattr__(name: str) -> Any:
    """Lazily preserve the historical SparkClient import without a cycle."""
    if name == "SparkClient":
        from mydrak.live.spark_client import SparkClient
        return SparkClient
    raise AttributeError(name)
