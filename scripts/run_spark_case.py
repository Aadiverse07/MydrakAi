"""Run one explicitly authorized public-test image through Spark-only mode."""

from __future__ import annotations

import argparse
from decimal import Decimal
import os
from pathlib import Path
from typing import Any, Callable

from mydrak.live.clients import SparkClient
from mydrak.live.guard import LiveConfigError, add_live_arguments, load_live_provider_config
from mydrak.privacy.data_policy import (
    DataClass, DataPolicy, ProcessingEvidence, ProviderMode,
)
from mydrak.trace.store import TraceStore
from mydrak.vision.source import read_local_image_data
from mydrak.workflow.modes import run_pipeline_mode

_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="One guarded Spark-only public-test image case")
    parser.add_argument("image", type=Path, help="local image explicitly approved as public-test")
    parser.add_argument("--language", choices=("en", "hi"), default="en")
    parser.add_argument("--public-test-confirmed", action="store_true")
    parser.add_argument("--rights-confirmed", action="store_true")
    add_live_arguments(parser)
    return parser


def run_case(
    argv: list[str] | None = None, *, output: Callable[[str], None] = print,
    environ: dict[str, str] | None = None, transport: Any = None,
    trace_path: str | Path | None = None, ledger_path: str | Path | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    environment = os.environ if environ is None else environ
    client_box: dict[str, SparkClient] = {}
    request_sent = False
    try:
        if not args.public_test_confirmed or not args.rights_confirmed:
            _report(output, "blocked", "data_policy_refused", False, None)
            return 2
        photo_bytes, _ = read_local_image_data(args.image)
        config = load_live_provider_config(_ROOT / "config" / "models.yaml", "tier2")
        evidence = ProcessingEvidence(
            provider_mode=ProviderMode.STANDARD, provider_mode_verified=True,
            rights_confirmed=True, public_test_provenance_verified=True,
        )
        db_path = trace_path or (_ROOT / ".mydrak-trace.sqlite3")
        spend_path = ledger_path or (_ROOT / ".mydrak-spend-ledger.sqlite3")

        def factory(**kwargs: Any) -> SparkClient:
            client = SparkClient(
                kwargs["config"], context=None,
                data_policy=kwargs["data_policy"], data_class=kwargs["data_class"],
                evidence=kwargs["evidence"], image_bytes=kwargs["image_bytes"],
                image_provenance=kwargs["image_provenance"],
                use_contributor=False, cli_authorized=args.live_authorized,
                max_spend_usd=args.max_spend_usd, ledger_path=str(spend_path),
                environ=environment, transport=transport,
                trace_callback=kwargs["trace_callback"],
                supported_crops=(), disease_ids=(),
                confidence_bands=("low", "medium", "high"),
            )
            client_box["client"] = client
            return client

        store = TraceStore(db_path)
        try:
            result = run_pipeline_mode(
                "spark_only", photo_bytes=photo_bytes, language=args.language,
                trace_store=store, spark_provider_factory=factory,
                provider_config=config, data_policy_value=DataPolicy.PUBLIC_TEST.value,
                data_class=DataClass.PUBLIC_TEST, image_provenance="public-test",
                evidence=evidence, use_contributor=False,
            )
        finally:
            store.close()
        client = client_box.get("client")
        request_sent = bool(client and client.request_ever_sent)
        if result.reason == "provider_setup_refused":
            _report(output, "blocked", "config_invalid", request_sent, result)
            return 2
        if client and client.last_guard_condition:
            _report(output, "blocked", "guard_refused", request_sent, result,
                    guard_condition=client.last_guard_condition)
            return 2
        if client and client.last_config_condition:
            _report(output, "blocked", "config_invalid", request_sent, result)
            return 2
        if result.action == "blocked":
            _report(output, "blocked", "workflow_blocked", request_sent, result)
            return 2
        _report(output, result.action, None, request_sent, result)
        return 0
    except LiveConfigError:
        _report(output, "blocked", "config_invalid", request_sent, None)
        return 2
    except (OSError, TypeError, ValueError):
        _report(output, "blocked", "input_or_workflow_invalid", request_sent, None)
        return 2


def _report(output, category: str, failure: str | None, request_sent: bool,
            result: Any, *, guard_condition: str | None = None) -> None:
    tokens_in = getattr(result, "tokens_in", None)
    tokens_out = getattr(result, "tokens_out", None)
    cost = getattr(result, "estimated_cost_usd", None)
    latency = getattr(result, "latency_ms", 0.0)
    fields = [f"outcome_category={category}", f"confidence={getattr(result, 'confidence_word', 'cannot tell')}"]
    if failure:
        fields.append(f"failure_category={failure}")
    if guard_condition:
        fields.append(f"guard_condition={guard_condition}")
    fields.extend((
        f"overlay_exists={str(bool(getattr(result, 'overlay_bytes', None))).lower()}",
        f"severity_exists={str(getattr(result, 'severity_pct', None) is not None).lower()}",
        f"request_sent={str(request_sent).lower()}", f"latency_ms={latency:.2f}",
        f"tokens_in={'unknown' if tokens_in is None else tokens_in}",
        f"tokens_out={'unknown' if tokens_out is None else tokens_out}",
        f"estimated_cost_usd={'unknown' if cost is None else str(Decimal(cost))}",
    ))
    output(" ".join(fields))


def main() -> None:
    raise SystemExit(run_case())


if __name__ == "__main__":
    main()
