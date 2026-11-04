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


@dataclass(frozen=True)
class ConsentRecord:
    user_hash: str
    consent_version: str
    consented_at: str
    revoked_at: str | None


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
                "CREATE TABLE IF NOT EXISTS privacy_notice_views ("
                "user_hash TEXT PRIMARY KEY, notice_version TEXT NOT NULL, "
                "shown_at TEXT NOT NULL);"
                "CREATE TABLE IF NOT EXISTS photo_consents ("
                "user_hash TEXT PRIMARY KEY, consent_version TEXT NOT NULL, "
                "consented_at TEXT NOT NULL, revoked_at TEXT);"
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

    def record_notice_shown(
        self, user_hash: str, version: str, *, now: datetime | None = None,
    ) -> None:
        _validate_user_hash(user_hash)
        _validate_version(version)
        stamp = _utc_timestamp(now)
        try:
            with self._db:
                self._db.execute(
                    "INSERT INTO privacy_notice_views(user_hash,notice_version,shown_at) "
                    "VALUES(?,?,?) ON CONFLICT(user_hash) DO UPDATE SET "
                    "notice_version=excluded.notice_version,shown_at=excluded.shown_at",
                    (user_hash, version, stamp),
                )
        except sqlite3.Error:
            raise ValueError("privacy notice view could not be stored") from None

    def notice_was_shown(self, user_hash: str, version: str) -> bool:
        _validate_user_hash(user_hash)
        _validate_version(version)
        try:
            row = self._db.execute(
                "SELECT 1 FROM privacy_notice_views WHERE user_hash=? AND notice_version=?",
                (user_hash, version),
            ).fetchone()
            return row is not None
        except sqlite3.Error:
            raise ValueError("privacy notice view could not be read") from None

    def record_consent(
        self, user_hash: str, version: str, *, now: datetime | None = None,
    ) -> bool:
        """Record only after this user has been shown this exact notice version."""
        _validate_user_hash(user_hash)
        _validate_version(version)
        stamp = _utc_timestamp(now)
        try:
            self._db.execute("BEGIN IMMEDIATE")
            shown = self._db.execute(
                "SELECT 1 FROM privacy_notice_views WHERE user_hash=? AND notice_version=?",
                (user_hash, version),
            ).fetchone()
            if shown is None:
                self._db.rollback()
                return False
            self._db.execute(
                "INSERT INTO photo_consents(user_hash,consent_version,consented_at,revoked_at) "
                "VALUES(?,?,?,NULL) ON CONFLICT(user_hash) DO UPDATE SET "
                "consent_version=excluded.consent_version,consented_at=excluded.consented_at,revoked_at=NULL",
                (user_hash, version, stamp),
            )
            self._db.commit()
            return True
        except sqlite3.Error:
            self._db.rollback()
            raise ValueError("photo consent could not be stored") from None

    def get_consent(self, user_hash: str) -> ConsentRecord | None:
        _validate_user_hash(user_hash)
        try:
            row = self._db.execute(
                "SELECT user_hash,consent_version,consented_at,revoked_at "
                "FROM photo_consents WHERE user_hash=?", (user_hash,),
            ).fetchone()
        except sqlite3.Error:
            raise ValueError("photo consent could not be read") from None
        if row is None:
            return None
        return ConsentRecord(row[0], row[1], row[2], row[3])

    def revoke_consent(self, user_hash: str, *, now: datetime | None = None) -> bool:
        _validate_user_hash(user_hash)
        stamp = _utc_timestamp(now)
        try:
            with self._db:
                cursor = self._db.execute(
                    "UPDATE photo_consents SET revoked_at=? WHERE user_hash=? AND revoked_at IS NULL",
                    (stamp, user_hash),
                )
            return cursor.rowcount == 1
        except sqlite3.Error:
            raise ValueError("photo consent could not be revoked") from None

    def close(self) -> None:
        self._db.close()


def _validate_user_hash(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("consent key must be a SHA-256 digest")


def _validate_version(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", value):
        raise ValueError("consent version is invalid")


def _utc_timestamp(value: datetime | None) -> str:
    current = value or datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None:
        raise ValueError("consent timestamp must be timezone-aware")
    return current.astimezone(timezone.utc).isoformat(timespec="microseconds")
