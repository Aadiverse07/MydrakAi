"""Shared one-request smoke runner; imported by the two explicit provider CLIs."""

from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path
import time
from typing import Any

from mydrak.live.clients import GlimmerClient, LiveDiagnosisError, SparkClient
from mydrak.live.guard import LiveGuardError, add_live_arguments, load_live_provider_config
from mydrak.privacy.data_policy import (
    DataClass, DataPolicy, ProcessingEvidence, ProviderMode,
)
from mydrak.trace.store import TraceStep

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
    try:
        config = load_live_provider_config(_ROOT / "config" / "models.yaml", provider)
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
        client.generate()
        latency = max(0.0, (time.perf_counter() - started) * 1000)
        step = client.last_step
        _print_report(output, "response_received" if step and step.outcome == "completed" else "failed",
                      latency, step)
        return 0 if step and step.outcome == "completed" else 1
    except (LiveGuardError, LiveDiagnosisError, ValueError):
        latency = sum(step.latency_ms for step in steps)
        _print_report(output, "refused_or_failed", latency, steps[-1] if steps else None)
        return 2


def _print_report(output, status: str, latency: float, step: TraceStep | None) -> None:
    tokens_in = "unknown" if step is None or step.tokens_in is None else str(step.tokens_in)
    tokens_out = "unknown" if step is None or step.tokens_out is None else str(step.tokens_out)
    cost = "unknown" if step is None or step.est_cost is None else str(step.est_cost)
    output(
        f"status={status} "
        f"latency_ms={latency:.2f} tokens_in={tokens_in} tokens_out={tokens_out} "
        f"estimated_cost_usd={cost}"
    )
    output("Response text, credentials, and image bytes are not printed.")


def main(provider: str) -> None:
    raise SystemExit(run_smoke(provider))
