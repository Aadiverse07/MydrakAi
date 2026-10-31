"""Shared one-request smoke runner; imported by the two explicit provider CLIs."""

from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path
import time
from typing import Any

from mydrak.live.clients import GlimmerClient, LiveDiagnosisError, SparkClient
from mydrak.live.guard import (
    LiveConfigError, LiveGuardError, add_live_arguments, load_live_provider_config,
)
from mydrak.privacy.data_policy import (
    DataClass, DataPolicy, ProcessingEvidence, ProviderMode,
)
from mydrak.trace.store import TraceStep
from mydrak.vision.diagnosis import validate_diagnosis_json

_ROOT = Path(__file__).resolve().parents[1]
_SYNTHETIC_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA0JCgsKCA0LCgsODg0PEyAVExISEyccHhcgLikxMC4pLSwzOko+"
    "MzZGNywtQFdBRkxOUlNSMj5aYVpQYEpRUk//2wBDAQ4ODhMREyYVFSZPNS01T09PT09PT09PT09PT09PT09"
    "PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0//wAARCAABAAEDASIAAhEBAxEB/8QAFAABAAAAAAAA"
    "AAAAAAAAAAAAAP/EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAA"
    "AAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AAA//2Q=="
)


def build_parser(provider: str) -> argparse.ArgumentParser:
    if provider not in {"tier1", "tier2"}:
        raise ValueError("only Glimmer and Spark are available in this phase")
    parser = argparse.ArgumentParser(description=f"One {provider} request using a synthetic test input")
    add_live_arguments(parser)
    if provider == "tier2":
        parser.add_argument("--contributor", action="store_true", help="Spark public-test-only Contributor model")
    return parser


def run_smoke(
    provider: str,
    argv: list[str] | None = None,
    *,
    transport: Any = None,
    environ: dict[str, str] | None = None,
    output=print,
) -> int:
    args = build_parser(provider).parse_args(argv)
    environment = os.environ if environ is None else environ
    steps: list[TraceStep] = []
    client = None
    try:
        try:
            config = load_live_provider_config(_ROOT / "config" / "models.yaml", provider)
        except LiveConfigError:
            _print_report(output, "failed", "config_invalid", False, None)
            return 2
        common = dict(
            cli_authorized=args.live_authorized,
            max_spend_usd=args.max_spend_usd,
            ledger_path=str(_ROOT / ".mydrak-spend-ledger.sqlite3"),
            environ=environment,
            transport=transport,
            trace_callback=steps.append,
            supported_crops=(), disease_ids=(), confidence_bands=("low", "medium", "high"),
        )
        if provider == "tier1":
            client = GlimmerClient(
                config, image_bytes=base64.b64decode(_SYNTHETIC_JPEG_B64),
                data_policy=DataPolicy.PUBLIC_TEST, data_class=DataClass.PUBLIC_TEST,
                public_test_marker="public-test", rights_confirmed=True, **common,
            )
        else:
            contributor = bool(args.contributor)
            mode = ProviderMode.CONTRIBUTOR if contributor else ProviderMode.STANDARD
            evidence = ProcessingEvidence(
                provider_mode=mode, provider_mode_verified=True, rights_confirmed=True,
                public_test_provenance_verified=True,
            )
            client = SparkClient(
                config, context=None, data_policy=DataPolicy.PUBLIC_TEST,
                data_class=DataClass.PUBLIC_TEST, evidence=evidence,
                use_contributor=contributor, **common,
            )
        started = time.perf_counter()
        try:
            raw = client.generate()
        except LiveConfigError:
            _print_report(output, "failed", "config_invalid", client.last_request_sent,
                          client.last_step, latency_ms=(time.perf_counter() - started) * 1000)
            return 2
        except LiveGuardError as exc:
            if exc.condition == "credential_missing":
                category, condition = "missing_key", None
            else:
                category, condition = "guard_refused", exc.condition
            _print_report(output, "failed", category, client.last_request_sent,
                          client.last_step, condition=condition,
                          latency_ms=(time.perf_counter() - started) * 1000)
            return 2
        except LiveDiagnosisError as exc:
            _print_report(output, "failed", exc.category, client.last_request_sent,
                          client.last_step, http_status=exc.http_status,
                          http_reason=exc.http_reason,
                          latency_ms=(time.perf_counter() - started) * 1000)
            return 1
        latency = max(0.0, (time.perf_counter() - started) * 1000)
        step = client.last_step
        try:
            validate_diagnosis_json(
                raw, supported_crops=(), disease_ids=(),
                confidence_bands=("low", "medium", "high"),
            )
        except (TypeError, ValueError):
            _print_report(output, "failed", "schema_invalid", client.last_request_sent, step,
                          latency_ms=latency)
            return 1
        _print_report(output, "response_received" if step and step.outcome == "completed" else "failed",
                      None, client.last_request_sent, step, latency_ms=latency)
        return 0 if step and step.outcome == "completed" else 1
    except LiveConfigError:
        _print_report(output, "failed", "config_invalid", False, None)
        return 2
    except ValueError:
        sent = bool(client is not None and client.last_request_sent)
        category = "response_invalid" if sent else "config_invalid"
        _print_report(output, "failed", category, sent,
                      client.last_step if client is not None else None)
        return 2


def _print_report(output, status: str, category: str | None, request_sent: bool,
                  step: TraceStep | None, *, latency_ms: float | None = None,
                  condition: str | None = None, http_status: int | None = None,
                  http_reason: str | None = None) -> None:
    tokens_in = "unknown" if step is None or step.tokens_in is None else str(step.tokens_in)
    tokens_out = "unknown" if step is None or step.tokens_out is None else str(step.tokens_out)
    cost = "unknown" if step is None or step.est_cost is None else str(step.est_cost)
    latency = step.latency_ms if latency_ms is None and step is not None else (latency_ms or 0.0)
    fields = [f"status={status}"]
    if category is not None:
        fields.append(f"failure_category={category}")
    if condition is not None:
        fields.append(f"guard_condition={condition}")
    fields.extend((
        f"request_sent={str(request_sent).lower()}", f"latency_ms={latency:.2f}",
        f"tokens_in={tokens_in}", f"tokens_out={tokens_out}", f"estimated_cost_usd={cost}",
    ))
    if http_status is not None:
        fields.append(f"http_status={http_status}")
    if http_reason is not None:
        fields.append(f"http_reason={http_reason!r}")
    output(" ".join(fields))


def main(provider: str) -> None:
    raise SystemExit(run_smoke(provider))
