"""Access mode and public limit configuration fails closed."""

from decimal import Decimal

import pytest
import yaml

from mydrak.telegram.config import (
    AccessMode, BotConfigError, load_public_limits, resolve_access_mode,
)


def test_allowlist_is_default_and_requires_nonempty_ids():
    with pytest.raises(BotConfigError, match="TELEGRAM_ALLOWED_CHAT_IDS"):
        resolve_access_mode(public_flag=False, environ={})
    mode, ids = resolve_access_mode(
        public_flag=False,
        environ={"TELEGRAM_ALLOWED_CHAT_IDS": "123, -44,123"},
    )
    assert mode is AccessMode.ALLOWLIST
    assert ids == frozenset({"123", "-44"})


def test_public_requires_both_flag_and_environment():
    with pytest.raises(BotConfigError, match="MYDRAK_PUBLIC"):
        resolve_access_mode(public_flag=True, environ={})
    assert resolve_access_mode(
        public_flag=True, environ={"MYDRAK_PUBLIC": "1"},
    ) == (AccessMode.PUBLIC, frozenset())


def test_public_limits_missing_or_blank_values_refuse(tmp_path):
    with pytest.raises(BotConfigError, match="missing or invalid"):
        load_public_limits(tmp_path / "absent.yaml")
    path = tmp_path / "limits.yaml"
    path.write_text("per_user_daily_requests: null\n", encoding="utf-8")
    with pytest.raises(BotConfigError, match="missing or unknown"):
        load_public_limits(path)
    path.write_text(yaml.safe_dump({
        "per_user_daily_requests": None,
        "global_daily_requests": 10,
        "global_spend_cap_usd": 3,
        "max_photo_bytes": 100,
        "min_seconds_between_requests_per_user": 1,
    }), encoding="utf-8")
    with pytest.raises(BotConfigError, match="positive integer"):
        load_public_limits(path)


def test_complete_limits_parse_and_provider_photo_bound_is_enforced(tmp_path):
    path = tmp_path / "limits.yaml"
    path.write_text(yaml.safe_dump({
        "per_user_daily_requests": 4,
        "global_daily_requests": 20,
        "global_spend_cap_usd": "2.50",
        "max_photo_bytes": 1000,
        "min_seconds_between_requests_per_user": 2.5,
    }), encoding="utf-8")
    limits = load_public_limits(path)
    assert limits.per_user_daily_requests == 4
    assert limits.global_daily_requests == 20
    assert limits.global_spend_cap_usd == Decimal("2.50")
    assert limits.max_photo_bytes == 1000
    assert limits.min_seconds_between_requests_per_user == 2.5

    values = yaml.safe_load(path.read_text())
    values["max_photo_bytes"] = 20 * 1024 * 1024 + 1
    path.write_text(yaml.safe_dump(values), encoding="utf-8")
    with pytest.raises(BotConfigError, match="documented download limit"):
        load_public_limits(path)


@pytest.mark.parametrize("cooldown", [-1, True, "bad"])
def test_invalid_cooldown_refuses(tmp_path, cooldown):
    path = tmp_path / "limits.yaml"
    path.write_text(yaml.safe_dump({
        "per_user_daily_requests": 2,
        "global_daily_requests": 4,
        "global_spend_cap_usd": 1,
        "max_photo_bytes": 100,
        "min_seconds_between_requests_per_user": cooldown,
    }), encoding="utf-8")
    with pytest.raises(BotConfigError):
        load_public_limits(path)
