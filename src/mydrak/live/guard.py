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

import yaml


class LiveGuardError(ValueError):
    """Live execution is not sufficiently authorized or budgeted."""


@dataclass(frozen=True)
class SpendReservation:
    model_id: str
    estimated_usd: Decimal
    cumulative_reserved_usd: Decimal


DEFAULT_SPEND_LEDGER = Path(".mydrak-spend-ledger.sqlite3")
_PROVIDER_FIELDS = {
    "tier1": ("model_id", "endpoint", "timeout_s", "max_tokens",
              "max_input_tokens_estimate",
              "price_input_per_1m", "price_output_per_1m"),
    "tier2": ("model_id", "model_id_contributor", "endpoint", "timeout_s",
              "max_tokens", "max_input_tokens_estimate",
              "price_input_per_1m", "price_output_per_1m"),
    "voice": ("model_id", "endpoint", "timeout_s", "price_per_1k_minutes"),
    "sam": ("model_id", "endpoint", "timeout_s", "price_per_1k_images"),
}


def load_live_provider_config(path: str | Path, provider: str) -> dict[str, Any]:
    """Load and structurally validate one provider section without networking.

    This verifies presence, primitive types, and unresolved placeholders only;
    it does not verify the source, account entitlement, or compatibility of
    user-supplied values. Provider-specific payload contracts remain separate.
    """
    if provider not in _PROVIDER_FIELDS:
        raise LiveGuardError("provider section is unsupported")
    try:
        document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        raise LiveGuardError("provider configuration could not be loaded") from None
    if not isinstance(document, Mapping):
        raise LiveGuardError("provider configuration must be a mapping")
    section = document.get(provider)
    if not isinstance(section, Mapping):
        raise LiveGuardError("provider configuration section is missing")
    result = dict(section)
    if _contains_todo(result):
        raise LiveGuardError("provider configuration contains an unresolved TODO(verify)")
    for field in _PROVIDER_FIELDS[provider]:
        if field not in result:
            raise LiveGuardError(f"provider configuration field {field} is missing")
        value = result[field]
        if isinstance(value, str) and "TODO" in value.upper():
            raise LiveGuardError(f"provider configuration field {field} is unresolved")
        if field in {"model_id", "model_id_contributor", "endpoint"}:
            _clean_config_text(value, field)
        elif field == "timeout_s":
            _positive_decimal(value, "timeout")
        elif field == "max_tokens":
            _positive_int(value, "max_tokens")
        elif field == "max_input_tokens_estimate":
            _positive_int(value, "max_input_tokens_estimate")
        elif field.startswith("price_"):
            _nonnegative_decimal(value, field)
    if provider == "tier1":
        host = document.get("glimmer_host")
        if not isinstance(host, Mapping):
            raise LiveGuardError("Glimmer host configuration is missing")
        _clean_config_text(host.get("choice"), "Glimmer host")
    return result


def _contains_todo(value: Any) -> bool:
    if isinstance(value, str):
        return "TODO" in value.upper()
    if isinstance(value, Mapping):
        return any(_contains_todo(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_todo(item) for item in value)
    return False


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

    The configured input-token estimate and output-token maximum are both
    required. A missing bound or price is unknown and blocks authorization.
    The env mapping is injected by callers; this function neither reads nor
    retains credential values.
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

    tokens_in = _positive_int(
        config.get("max_input_tokens_estimate"), "maximum input tokens estimate"
    )
    tokens_out = _positive_int(config.get("max_tokens"), "maximum output tokens")
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
