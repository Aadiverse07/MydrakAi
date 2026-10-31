"""Guarded Telegram runner; real wire polling remains blocked by TODO(verify)."""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any

from mydrak.bot.adapter import OfflineTelegramAdapter
from mydrak.live.clients import SparkClient
from mydrak.live.guard import (
    DEFAULT_SPEND_LEDGER, LiveGuardError, add_live_arguments,
    load_live_provider_config,
)
from mydrak.replay import (
    REGISTERED_DEMO_FIXTURE_IDS, run_registered_cached_replay,
    seed_registered_demo_cache,
)
from mydrak.telegram.client import TelegramClient, TelegramClientError
from mydrak.telegram.config import (
    AccessMode, BotConfigError, load_public_limits, resolve_access_mode,
)
from mydrak.telegram.limits import PublicLimitStore
from mydrak.telegram.runner import TelegramBotRunner
from mydrak.trace.store import TraceStore

_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guarded Mydrak Telegram bot")
    parser.add_argument("--public-access", action="store_true")
    parser.add_argument("--replay", nargs="?", const="synthetic-referral-01",
                        choices=sorted(REGISTERED_DEMO_FIXTURE_IDS))
    parser.add_argument("--bot-limits", type=Path, default=_ROOT / "config" / "bot_limits.yaml")
    parser.add_argument("--ledger", type=Path, default=_ROOT / DEFAULT_SPEND_LEDGER)
    add_live_arguments(parser)
    return parser


def run(argv: list[str] | None = None, *, environ: dict[str, str] | None = None,
        output=print, stderr=None) -> int:
    args = build_parser().parse_args(argv)
    environment = os.environ if environ is None else environ
    error_stream = sys.stderr if stderr is None else stderr
    if args.replay is not None:
        return _run_replay(args.replay, output=output)
    try:
        mode, allowlist = resolve_access_mode(
            public_flag=args.public_access, environ=environment,
        )
        limits = load_public_limits(args.bot_limits) if mode is AccessMode.PUBLIC else None
        cap = _require_bot_live_gate(args.live_authorized, args.max_spend_usd,
                                     environment, args.ledger)
        token = environment.get("TELEGRAM_BOT_TOKEN")
        if not isinstance(token, str) or not token:
            raise BotConfigError("TELEGRAM_BOT_TOKEN is required")
        spark = load_live_provider_config(_ROOT / "config" / "models.yaml", "tier2")
    except (BotConfigError, LiveGuardError, ValueError):
        print("Telegram startup refused; check access mode, live guard, and local configuration.",
              file=error_stream)
        return 2

    if mode is AccessMode.PUBLIC:
        assert limits is not None
        output("WARNING: PUBLIC ACCESS ENABLED. Anyone can message this bot; photos may be sent to an AI model provider, costs can accrue up to configured safeguards, and this machine must remain running.")
        cap = min(cap, limits.global_spend_cap_usd)
    try:
        client = TelegramClient.from_environment(environ=environment)
        trace = TraceStore(_ROOT / ".mydrak-trace.sqlite3")
        limit_store = PublicLimitStore(_ROOT / ".mydrak-bot-limits.sqlite3") if limits else None
    except (TelegramClientError, ValueError, OSError):
        print("Telegram startup refused; local client or storage is unavailable.", file=error_stream)
        return 2

    def spark_factory(**values: Any) -> SparkClient:
        return SparkClient(
            spark, context=None, data_policy=values["data_policy"],
            data_class=values["data_class"], evidence=values["evidence"],
            image_bytes=values["image_bytes"],
            image_provenance=values["image_provenance"], use_contributor=False,
            cli_authorized=args.live_authorized, max_spend_usd=cap,
            ledger_path=str(args.ledger), environ=environment,
            trace_callback=values["trace_callback"],
        )

    runner = TelegramBotRunner(
        client=client, trace_store=trace, adapter=OfflineTelegramAdapter(),
        mode=mode, allowed_chat_ids=allowlist, limits=limits,
        limit_store=limit_store, spark_config=spark,
        spark_provider_factory=spark_factory,
        spend_cap_available=lambda: _ledger_has_headroom(args.ledger, cap),
    )
    try:
        # Default transport intentionally refuses because the local source file
        # lacks HTTP encoding and raw Update/File response schemas.
        result = runner.run_forever()
        output(f"telegram_runner_exit={result}")
        return result
    finally:
        trace.close()
        if limit_store is not None:
            limit_store.close()


def _require_bot_live_gate(cli_authorized: bool, raw_cap: Any,
                           environ: dict[str, str], ledger: Path) -> Decimal:
    if cli_authorized is not True:
        raise LiveGuardError("explicit live authorization is required")
    if environ.get("MYDRAK_LIVE") != "1":
        raise LiveGuardError("MYDRAK_LIVE=1 is required")
    try:
        cap = Decimal(str(raw_cap))
    except (InvalidOperation, ValueError, TypeError):
        raise LiveGuardError("a positive spend cap is required") from None
    if not cap.is_finite() or cap <= 0:
        raise LiveGuardError("a positive spend cap is required")
    if not ledger.is_file():
        raise LiveGuardError("the existing spend ledger file is required")
    return cap


def _ledger_has_headroom(path: Path, cap: Decimal) -> bool:
    """Read the existing reservation total; Spark's guard remains authoritative."""
    try:
        uri = f"file:{path.resolve()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=1) as database:
            exists = database.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='spend_ledger'"
            ).fetchone()
            if exists is None:
                return True
            row = database.execute(
                "SELECT reserved_usd FROM spend_ledger WHERE singleton=1"
            ).fetchone()
            reserved = Decimal("0") if row is None else Decimal(row[0])
            return reserved.is_finite() and Decimal("0") <= reserved < cap
    except Exception:
        return False


def _run_replay(fixture_id: str, *, output) -> int:
    trace = TraceStore(":memory:")
    try:
        seed_registered_demo_cache(trace)
        result = run_registered_cached_replay(fixture_id, trace_store=trace)
    except Exception:
        output("replay_status=unavailable provenance=SYNTHETIC / MOCK")
        return 2
    finally:
        trace.close()
    output(f"replay_status={result.status} provenance={result.provenance} reply={result.reply}")
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
