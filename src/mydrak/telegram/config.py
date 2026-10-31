"""Strict Telegram access-mode and public-limit configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import os
from pathlib import Path
import math
from typing import Any

import yaml


class BotConfigError(ValueError):
    """Bot configuration is missing, malformed, or unsafe."""


class AccessMode(StrEnum):
    ALLOWLIST = "allowlist"
    PUBLIC = "public"


@dataclass(frozen=True)
class PublicLimits:
    per_user_daily_requests: int
    global_daily_requests: int
    global_spend_cap_usd: Decimal
    max_photo_bytes: int
    min_seconds_between_requests_per_user: float

    def __post_init__(self) -> None:
        if type(self.per_user_daily_requests) is not int or self.per_user_daily_requests < 1:
            raise BotConfigError("per-user daily request limit must be a positive integer")
        if type(self.global_daily_requests) is not int or self.global_daily_requests < 1:
            raise BotConfigError("global daily request limit must be a positive integer")
        if type(self.max_photo_bytes) is not int or not 1 <= self.max_photo_bytes <= 20 * 1024 * 1024:
            raise BotConfigError("maximum photo size is outside the documented download limit")
        if not isinstance(self.global_spend_cap_usd, Decimal) or not self.global_spend_cap_usd.is_finite() or self.global_spend_cap_usd <= 0:
            raise BotConfigError("global spend cap must be a positive number")
        cooldown = self.min_seconds_between_requests_per_user
        if isinstance(cooldown, bool) or not isinstance(cooldown, (int, float)) or not math.isfinite(cooldown) or cooldown < 0:
            raise BotConfigError("per-user cooldown must be a finite non-negative number")


_LIMIT_FIELDS = {
    "per_user_daily_requests", "global_daily_requests", "global_spend_cap_usd",
    "max_photo_bytes", "min_seconds_between_requests_per_user",
}


def resolve_access_mode(*, public_flag: bool, environ: Mapping[str, str] | None = None
                        ) -> tuple[AccessMode, frozenset[str]]:
    values = os.environ if environ is None else environ
    if type(public_flag) is not bool:
        raise BotConfigError("public access flag is invalid")
    if public_flag:
        if values.get("MYDRAK_PUBLIC") != "1":
            raise BotConfigError("public mode requires MYDRAK_PUBLIC=1")
        return AccessMode.PUBLIC, frozenset()
    raw = values.get("TELEGRAM_ALLOWED_CHAT_IDS", "")
    ids = frozenset(part.strip() for part in raw.split(",") if part.strip())
    if not ids:
        raise BotConfigError("allowlist mode requires TELEGRAM_ALLOWED_CHAT_IDS")
    if any(len(item) > 256 for item in ids):
        raise BotConfigError("allowlist contains an invalid chat identifier")
    return AccessMode.ALLOWLIST, ids


def load_public_limits(path: str | Path) -> PublicLimits:
    try:
        value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        raise BotConfigError("public bot limits are missing or invalid") from None
    if not isinstance(value, Mapping) or set(value) != _LIMIT_FIELDS:
        raise BotConfigError("public bot limits have missing or unknown fields")
    user = _positive_int(value["per_user_daily_requests"], "per-user daily request limit")
    global_count = _positive_int(value["global_daily_requests"], "global daily request limit")
    photo_bytes = _positive_int(value["max_photo_bytes"], "maximum photo size")
    # Bot API excerpt documents file downloads up to 20 MB.
    if photo_bytes > 20 * 1024 * 1024:
        raise BotConfigError("maximum photo size exceeds the documented download limit")
    spend = _positive_decimal(value["global_spend_cap_usd"], "global spend cap")
    cooldown = value["min_seconds_between_requests_per_user"]
    if isinstance(cooldown, bool) or not isinstance(cooldown, (int, float)) or not math.isfinite(cooldown) or cooldown < 0:
        raise BotConfigError("per-user cooldown must be a finite non-negative number")
    return PublicLimits(user, global_count, spend, photo_bytes, float(cooldown))


def _positive_int(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise BotConfigError(f"{label} must be a positive integer")
    return value


def _positive_decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise BotConfigError(f"{label} must be a positive number")
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise BotConfigError(f"{label} must be a positive number") from None
    if not result.is_finite() or result <= 0:
        raise BotConfigError(f"{label} must be a positive number")
    return result
