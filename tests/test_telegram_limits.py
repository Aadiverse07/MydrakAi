"""Persistent public controls retain hashes/counts/dates only."""

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256

from mydrak.telegram.config import PublicLimits
from mydrak.telegram.limits import PublicLimitStore


def limits(**overrides):
    fields = {
        "per_user_daily_requests": 2,
        "global_daily_requests": 3,
        "global_spend_cap_usd": Decimal("1"),
        "max_photo_bytes": 1000,
        "min_seconds_between_requests_per_user": 5,
    }
    fields.update(overrides)
    return PublicLimits(**fields)


def test_per_user_global_daily_photo_size_and_cooldown_limits(tmp_path):
    store = PublicLimitStore(tmp_path / "limits.sqlite3")
    user_hash = sha256(b"test-user").hexdigest()
    day = datetime(2026, 10, 31, tzinfo=timezone.utc)
    cfg = limits()
    assert store.reserve_photo(user_hash, limits=cfg, photo_size=999, now=day).allowed
    assert store.reserve_photo(user_hash, limits=cfg, photo_size=999,
                               now=day.replace(second=2)).reason == "cooldown"
    assert store.reserve_photo(user_hash, limits=cfg, photo_size=1001,
                               now=day.replace(second=20)).reason == "photo_size"
    assert store.reserve_photo(user_hash, limits=cfg, photo_size=999,
                               now=day.replace(second=20)).allowed
    assert store.reserve_photo(user_hash, limits=cfg, photo_size=999,
                               now=day.replace(second=30)).reason == "per_user_daily"
    store.close()


def test_global_daily_limit_and_new_utc_day(tmp_path):
    store = PublicLimitStore(tmp_path / "limits.sqlite3")
    cfg = limits(per_user_daily_requests=5, global_daily_requests=1,
                 min_seconds_between_requests_per_user=0)
    day = datetime(2026, 10, 31, tzinfo=timezone.utc)
    first = sha256(b"one").hexdigest()
    second = sha256(b"two").hexdigest()
    assert store.reserve_photo(first, limits=cfg, photo_size=10, now=day).allowed
    assert store.reserve_photo(second, limits=cfg, photo_size=10, now=day).reason == "global_daily"
    assert store.reserve_photo(second, limits=cfg, photo_size=10,
                               now=datetime(2026, 11, 1, tzinfo=timezone.utc),
                               ).allowed
    store.close()


def test_database_contains_only_user_hash_not_raw_identifier(tmp_path):
    path = tmp_path / "limits.sqlite3"
    raw = "private-user-id-synthetic"
    user_hash = sha256(raw.encode()).hexdigest()
    store = PublicLimitStore(path)
    assert store.reserve_photo(user_hash, limits=limits(), photo_size=10).allowed
    store.close()
    content = path.read_bytes()
    assert raw.encode() not in content
    assert user_hash.encode() in content
