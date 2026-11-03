"""Atomic SQLite limits keyed only by SHA-256 user hashes and UTC dates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import sqlite3
from pathlib import Path

from mydrak.telegram.config import PublicLimits


@dataclass(frozen=True)
class LimitResult:
    allowed: bool
    reason: str | None = None


class PublicLimitStore:
    """Persist only digest, date, counts, and request time; never raw IDs."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path == ":memory:":
            raise ValueError("public limits require persistent local storage")
        try:
            self._db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            self._db.execute("PRAGMA busy_timeout=5000")
            self._db.executescript(
                "CREATE TABLE IF NOT EXISTS user_daily ("
                "user_hash TEXT NOT NULL, day TEXT NOT NULL, count INTEGER NOT NULL, "
                "last_request_at TEXT NOT NULL, PRIMARY KEY(user_hash,day));"
                "CREATE TABLE IF NOT EXISTS global_daily ("
                "day TEXT PRIMARY KEY, count INTEGER NOT NULL);"
            )
        except sqlite3.Error:
            raise ValueError("public limit database is unavailable") from None

    def reserve_photo(self, user_hash: str, *, limits: PublicLimits,
                      photo_size: int, now: datetime | None = None) -> LimitResult:
        if not isinstance(user_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", user_hash):
            raise ValueError("public limit key must be a SHA-256 digest")
        if type(photo_size) is not int or photo_size < 0:
            raise ValueError("photo size is invalid")
        if photo_size > limits.max_photo_bytes:
            return LimitResult(False, "photo_size")
        current = now or datetime.now(timezone.utc)
        if not isinstance(current, datetime) or current.tzinfo is None:
            raise ValueError("request time must be timezone-aware")
        current = current.astimezone(timezone.utc)
        day = current.date().isoformat()
        timestamp = current.isoformat(timespec="microseconds")
        try:
            self._db.execute("BEGIN IMMEDIATE")
            user = self._db.execute(
                "SELECT count,last_request_at FROM user_daily WHERE user_hash=? AND day=?",
                (user_hash, day),
            ).fetchone()
            global_row = self._db.execute(
                "SELECT count FROM global_daily WHERE day=?", (day,)
            ).fetchone()
            user_count, last = (0, None) if user is None else (int(user[0]), datetime.fromisoformat(user[1]))
            global_count = 0 if global_row is None else int(global_row[0])
            if user_count >= limits.per_user_daily_requests:
                self._db.rollback()
                return LimitResult(False, "per_user_daily")
            if global_count >= limits.global_daily_requests:
                self._db.rollback()
                return LimitResult(False, "global_daily")
            if last is not None:
                elapsed = (current - last.astimezone(timezone.utc)).total_seconds()
                if elapsed < 0 or elapsed < limits.min_seconds_between_requests_per_user:
                    self._db.rollback()
                    return LimitResult(False, "cooldown")
            self._db.execute(
                "INSERT INTO user_daily(user_hash,day,count,last_request_at) VALUES(?,?,1,?) "
                "ON CONFLICT(user_hash,day) DO UPDATE SET count=count+1,last_request_at=excluded.last_request_at",
                (user_hash, day, timestamp),
            )
            self._db.execute(
                "INSERT INTO global_daily(day,count) VALUES(?,1) "
                "ON CONFLICT(day) DO UPDATE SET count=count+1", (day,),
            )
            self._db.commit()
            return LimitResult(True)
        except sqlite3.Error:
            self._db.rollback()
            raise ValueError("public request limit could not be checked") from None

    def close(self) -> None:
        self._db.close()
