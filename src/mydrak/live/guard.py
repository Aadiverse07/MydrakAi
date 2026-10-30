"""Offline-testable authorization and conservative spend reservation.

This module does not read process credentials or make requests. A future
caller must pass explicit authorization evidence and a parsed provider
configuration. Reservations record worst-case estimates, not actual billing.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


class LiveGuardError(ValueError):
    """Live execution is not sufficiently authorized or budgeted."""


@dataclass(frozen=True)
class SpendReservation:
    model_id: str
    estimated_usd: Decimal
    cumulative_reserved_usd: Decimal


DEFAULT_SPEND_LEDGER = Path(".mydrak-spend-ledger.sqlite3")


def add_live_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add the explicit opt-in and cap switches expected by future CLIs."""
    parser.add_argument(
        "--live-authorized", action="store_true",
        help="explicitly authorize a live request for this invocation",
    )
    parser.add_argument(
        "--max-spend-usd", default=None,
        help="per-run estimated spend cap; required for a live request",
    )
    return parser


def reserve_live_call(
    config: Mapping[str, Any],
    *,
    cli_authorized: bool,
    environ: Mapping[str, str],
    max_spend_usd: Any,
    ledger_path: str | Path = DEFAULT_SPEND_LEDGER,
    credential_env_var: str = "META_API_KEY",
) -> SpendReservation:
    """Validate every gate and atomically reserve one worst-case token cost.

    Separate input and output token bounds must exist in the provider mapping;
    the current config only has an ambiguously named ``max_tokens`` field. A
    missing bound or price is unknown and blocks authorization. The env mapping
    is injected by callers; this function neither reads nor retains credential
    values.
    """
    if cli_authorized is not True:
        raise LiveGuardError("explicit --live-authorized flag is required")
    if environ.get("MYDRAK_LIVE") != "1":
        raise LiveGuardError("MYDRAK_LIVE=1 is required")
    if not isinstance(environ.get(credential_env_var), str) or not environ[credential_env_var]:
        raise LiveGuardError("required credential environment variable is missing")
    cap = _positive_decimal(max_spend_usd, "--max-spend-usd")
    if not isinstance(config, Mapping):
        raise LiveGuardError("provider configuration is unavailable")
    model_id = _clean_config_text(config.get("model_id"), "model ID")
    endpoint = _clean_config_text(config.get("endpoint"), "endpoint")
    try:
        parsed_endpoint = urlsplit(endpoint)
        if (parsed_endpoint.scheme != "https" or not parsed_endpoint.hostname
                or parsed_endpoint.username is not None or parsed_endpoint.password is not None
                or parsed_endpoint.fragment):
            raise ValueError
        parsed_endpoint.port  # Force malformed/out-of-range port validation.
    except ValueError:
        raise LiveGuardError("provider endpoint is malformed") from None
    timeout = _positive_decimal(config.get("timeout_s"), "timeout")
    del timeout  # Validated here; the future transport must apply this value.

    tokens_in = _positive_int(config.get("max_input_tokens"), "maximum input tokens")
    tokens_out = _positive_int(config.get("max_output_tokens"), "maximum output tokens")
    input_price = _nonnegative_decimal(config.get("price_input_per_1m"), "input price")
    output_price = _nonnegative_decimal(config.get("price_output_per_1m"), "output price")
    estimate = (
        Decimal(tokens_in) * input_price + Decimal(tokens_out) * output_price
    ) / Decimal(1_000_000)
    if estimate > cap:
        raise LiveGuardError("worst-case reservation exceeds spend cap")

    path = Path(ledger_path)
    if str(path) == ":memory:" or path.name in {"", ".", ".."}:
        raise LiveGuardError("a persistent local spend-ledger file is required")
    if not path.parent.exists() or not path.parent.is_dir():
        raise LiveGuardError("spend-ledger directory is unavailable")
    try:
        db = sqlite3.connect(path, timeout=5.0, isolation_level=None)
        try:
            db.execute("PRAGMA busy_timeout = 5000")
            db.execute(
                "CREATE TABLE IF NOT EXISTS spend_ledger "
                "(singleton INTEGER PRIMARY KEY CHECK(singleton=1), reserved_usd TEXT NOT NULL)"
            )
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT reserved_usd FROM spend_ledger WHERE singleton=1"
            ).fetchone()
            current = Decimal(row[0]) if row else Decimal(0)
            if not current.is_finite() or current < 0:
                raise LiveGuardError("spend ledger is invalid")
            cumulative = current + estimate
            if cumulative > cap:
                raise LiveGuardError("worst-case reservation exceeds spend cap")
            db.execute(
                "INSERT INTO spend_ledger(singleton,reserved_usd) VALUES(1,?) "
                "ON CONFLICT(singleton) DO UPDATE SET reserved_usd=excluded.reserved_usd",
                (str(cumulative),),
            )
            db.commit()
        finally:
            db.close()
    except LiveGuardError:
        raise
    except (OSError, sqlite3.Error, InvalidOperation, ValueError, TypeError):
        raise LiveGuardError("spend ledger could not authorize this call") from None
    return SpendReservation(model_id, estimate, cumulative)


def _clean_config_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise LiveGuardError(f"provider {name} is missing or malformed")
    if "TODO" in value.upper() or any(char.isspace() for char in value):
        raise LiveGuardError(f"provider {name} is unresolved")
    return value


def _positive_int(value: Any, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise LiveGuardError(f"{name} is missing or invalid")
    return value


def _positive_decimal(value: Any, name: str) -> Decimal:
    parsed = _nonnegative_decimal(value, name)
    if parsed <= 0:
        raise LiveGuardError(f"{name} must be greater than zero")
    return parsed


def _nonnegative_decimal(value: Any, name: str) -> Decimal:
    if isinstance(value, bool) or value is None or isinstance(value, str) and "TODO" in value.upper():
        raise LiveGuardError(f"{name} is unknown")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise LiveGuardError(f"{name} is unknown") from None
    if not parsed.is_finite() or parsed < 0:
        raise LiveGuardError(f"{name} is invalid")
    return parsed
