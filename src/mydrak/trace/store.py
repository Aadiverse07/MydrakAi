"""Small offline SQLite trace store for B9 case and step accounting.

This stores workflow metadata only. It never accepts image bytes, raw prompts,
user text, model output, or exception messages. Provider prices are optional;
unknown pricing stays NULL rather than being represented as zero.
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


class TraceError(ValueError):
    """Raised for invalid trace values or storage failures."""


@dataclass(frozen=True)
class TraceStep:
    step_name: str
    outcome: str
    latency_ms: float
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    est_cost: Decimal | None = None
    error_code: str | None = None
    retries: int = 0
    started_at: str | None = None


@dataclass(frozen=True)
class EvalRun:
    run_id: str
    strategy: str
    git_sha: str | None
    timestamp: str
    metrics_json: str


@dataclass(frozen=True)
class TraceCase:
    case_id: str
    final_action: str
    lang: str
    input_type: str
    data_policy: str | None
    user_hash: str | None = None
    image_hash: str | None = None
    quality_scores: str | None = None
    kb_card_id: str | None = None
    severity_pct: float | None = None


CACHE_SCHEMA = "mydrak-demo-response-v1"
CACHE_PROVENANCE = "synthetic-offline-demo"
WORKFLOW_CACHE_SCHEMA = "mydrak-workflow-result-v1"
WORKFLOW_CACHE_PROVENANCE = "SYNTHETIC / MOCK"
CACHE_RESPONSE_CODES = {
    ("blocked", "policy_blocked"),
    ("referred", "safe_referral"),
    ("manual_review", "manual_review"),
    ("answer", "synthetic_answer"),
    ("ask", "synthetic_ask"),
    ("refer", "synthetic_referral"),
    ("retake", "synthetic_retake"),
}
MAX_CACHE_RESPONSE_BYTES = 512
MAX_WORKFLOW_CACHE_RESPONSE_BYTES = 8192


@dataclass(frozen=True)
class CachedResponse:
    cache_key: str
    status: str
    response_code: str
    timestamp: str
    provenance: str = CACHE_PROVENANCE
    reason: str | None = None
    reply: str | None = None
    severity_pct: float | None = None
    severity_band: str | None = None


def estimate_token_cost(
    tokens_in: int,
    tokens_out: int,
    input_price_per_million: Any,
    output_price_per_million: Any,
) -> Decimal | None:
    """Estimate USD cost, or return None when either price is unavailable."""
    for count in (tokens_in, tokens_out):
        if type(count) is not int or count < 0:
            raise TraceError("token counts must be non-negative integers")
    if not _price_known(input_price_per_million) or not _price_known(output_price_per_million):
        return None
    try:
        incoming = Decimal(str(input_price_per_million))
        outgoing = Decimal(str(output_price_per_million))
        cost = (tokens_in * incoming + tokens_out * outgoing) / Decimal(1_000_000)
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not cost.is_finite() or cost < 0:
        return None
    return cost


def _price_known(value: Any) -> bool:
    if not isinstance(value, (str, int, float, Decimal)) or isinstance(value, bool):
        return False
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return False
    return parsed.is_finite() and parsed >= 0


class TraceStore:
    """SQLite store with atomic case-plus-steps insertion."""

    def __init__(self, database: str | Path = ":memory:") -> None:
        try:
            self._database_path = str(database)
            self._connection = sqlite3.connect(str(database))
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    user_hash TEXT,
                    lang TEXT NOT NULL,
                    input_type TEXT NOT NULL,
                    image_hash TEXT,
                    quality_scores TEXT,
                    final_action TEXT NOT NULL,
                    kb_card_id TEXT,
                    severity_pct REAL,
                    latency_ms_total REAL NOT NULL,
                    est_cost TEXT,
                    data_policy TEXT
                );
                CREATE TABLE IF NOT EXISTS steps (
                    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL,
                    step_name TEXT NOT NULL,
                    model TEXT,
                    started_at TEXT,
                    latency_ms REAL NOT NULL,
                    tokens_in INTEGER,
                    tokens_out INTEGER,
                    est_cost TEXT,
                    error TEXT,
                    retries INTEGER NOT NULL,
                    outcome TEXT NOT NULL,
                    PRIMARY KEY (case_id, ordinal)
                );
                CREATE TABLE IF NOT EXISTS signals (
                    case_id TEXT PRIMARY KEY REFERENCES cases(case_id) ON DELETE CASCADE,
                    s1 REAL,
                    s2 REAL,
                    s3 REAL,
                    s4 REAL,
                    score REAL,
                    decision TEXT NOT NULL,
                    escalated INTEGER NOT NULL CHECK (escalated IN (0, 1))
                );
                CREATE TABLE IF NOT EXISTS image_measurements (
                    case_id TEXT PRIMARY KEY REFERENCES cases(case_id) ON DELETE CASCADE,
                    laplacian_variance REAL NOT NULL CHECK (laplacian_variance >= 0),
                    mean_brightness_0_255 REAL NOT NULL
                        CHECK (mean_brightness_0_255 BETWEEN 0 AND 255),
                    leaf_coverage_fraction REAL NOT NULL
                        CHECK (leaf_coverage_fraction BETWEEN 0 AND 1),
                    leaf_coverage_method TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS scans (
                    scan_id TEXT PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    plant_label TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    image_hash TEXT NOT NULL,
                    severity_pct REAL NOT NULL,
                    case_id TEXT NOT NULL REFERENCES cases(case_id)
                );
                CREATE INDEX IF NOT EXISTS scans_same_plant_latest
                    ON scans(user_hash, plant_label, ts DESC);
                CREATE TABLE IF NOT EXISTS cache (
                    "key" TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    ts TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS eval_runs (
                    run_id TEXT PRIMARY KEY,
                    strategy TEXT NOT NULL,
                    git_sha TEXT,
                    ts TEXT NOT NULL,
                    metrics_json TEXT NOT NULL
                );
                """
            )
            self._migrate_legacy_steps()
        except sqlite3.Error:
            raise TraceError("trace database could not be initialized") from None

    def _migrate_legacy_steps(self) -> None:
        """Add B9 started_at to older databases without rebuilding trace rows."""
        columns = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(steps)").fetchall()
        }
        if "started_at" not in columns:
            self._connection.execute("ALTER TABLE steps ADD COLUMN started_at TEXT")

    def record_case(self, case: TraceCase, steps: tuple[TraceStep, ...] | list[TraceStep]) -> None:
        _validate_case(case)
        if not isinstance(steps, (tuple, list)) or not steps:
            raise TraceError("at least one trace step is required")
        for step in steps:
            _validate_step(step)
        total_latency = sum(step.latency_ms for step in steps)
        total_cost = None if any(step.est_cost is None for step in steps) else sum(
            (step.est_cost for step in steps if step.est_cost is not None), Decimal(0)
        )
        try:
            with self._connection:
                self._connection.execute(
                    """INSERT INTO cases(case_id,user_hash,lang,input_type,image_hash,
                       quality_scores,final_action,kb_card_id,severity_pct,
                       latency_ms_total,est_cost,data_policy)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (case.case_id, case.user_hash, case.lang, case.input_type,
                     case.image_hash, case.quality_scores, case.final_action,
                     case.kb_card_id, case.severity_pct, total_latency,
                     str(total_cost) if total_cost is not None else None,
                     case.data_policy),
                )
                self._connection.executemany(
                    """INSERT INTO steps(case_id,ordinal,step_name,model,started_at,latency_ms,
                       tokens_in,tokens_out,est_cost,error,retries,outcome)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    [(case.case_id, index, step.step_name, step.model,
                      _normalize_timestamp(step.started_at) if step.started_at is not None else _utc_now(),
                      step.latency_ms, step.tokens_in, step.tokens_out,
                      str(step.est_cost) if step.est_cost is not None else None,
                      step.error_code, step.retries, step.outcome)
                     for index, step in enumerate(steps)],
                )
        except sqlite3.Error:
            raise TraceError("trace record could not be stored") from None

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        row = self._connection.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        return dict(row) if row else None

    def get_steps(self, case_id: str) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            "SELECT * FROM steps WHERE case_id=? ORDER BY ordinal", (case_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def record_eval_run(
        self,
        *,
        run_id: str,
        strategy: str,
        git_sha: str | None,
        metrics: Mapping[str, object],
        timestamp: str | None = None,
    ) -> EvalRun:
        """Persist one bounded B9 evaluation summary without cost inference."""
        _validate_eval_run(run_id, strategy, git_sha, metrics)
        stamp = _normalize_timestamp(timestamp) if timestamp is not None else _utc_now()
        try:
            metrics_json = json.dumps(dict(metrics), sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError, RecursionError):
            raise TraceError("evaluation metrics are not valid JSON") from None
        if len(metrics_json.encode("utf-8")) > 65_536:
            raise TraceError("evaluation metrics exceed the size limit")
        try:
            with self._connection:
                self._connection.execute(
                    "INSERT INTO eval_runs(run_id,strategy,git_sha,ts,metrics_json) VALUES(?,?,?,?,?)",
                    (run_id, strategy, git_sha, stamp, metrics_json),
                )
        except sqlite3.IntegrityError:
            raise TraceError("evaluation run already exists") from None
        except sqlite3.Error:
            raise TraceError("evaluation run could not be stored") from None
        return EvalRun(run_id, strategy, git_sha, stamp, metrics_json)

    def get_eval_run(self, run_id: str) -> EvalRun | None:
        if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{32}", run_id):
            raise TraceError("evaluation run ID must be lowercase UUID hex")
        try:
            row = self._connection.execute(
                "SELECT run_id,strategy,git_sha,ts,metrics_json FROM eval_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
        except sqlite3.Error:
            raise TraceError("evaluation run could not be read") from None
        if row is None:
            return None
        return EvalRun(row["run_id"], row["strategy"], row["git_sha"], row["ts"], row["metrics_json"])

    def record_image_measurements(
        self,
        case_id: str,
        *,
        laplacian_variance: float,
        mean_brightness: float,
        leaf_coverage_fraction: float,
        leaf_coverage_method: str,
    ) -> None:
        """Persist observation-only T04 values separately from B3 signals."""
        if not isinstance(case_id, str) or not re.fullmatch(r"[0-9a-f]{32}", case_id):
            raise TraceError("case ID must be a generated lowercase UUID hex value")
        values = (laplacian_variance, mean_brightness, leaf_coverage_fraction)
        if any(type(value) not in {int, float} for value in values):
            raise TraceError("image measurements must be finite numbers")
        try:
            laplacian_variance, mean_brightness, leaf_coverage_fraction = (
                float(value) for value in values
            )
        except OverflowError:
            raise TraceError("image measurements must be finite numbers") from None
        values = (laplacian_variance, mean_brightness, leaf_coverage_fraction)
        if any(not math.isfinite(value) for value in values):
            raise TraceError("image measurements must be finite numbers")
        if laplacian_variance < 0 or not 0 <= mean_brightness <= 255 or not 0 <= leaf_coverage_fraction <= 1:
            raise TraceError("image measurements are outside their measurement ranges")
        if leaf_coverage_method != "unverified_green_hue_pixel_proxy":
            raise TraceError("image measurement method is unsupported")
        try:
            with self._connection:
                self._connection.execute(
                    """INSERT INTO image_measurements(
                         case_id,laplacian_variance,mean_brightness_0_255,
                         leaf_coverage_fraction,leaf_coverage_method)
                       VALUES(?,?,?,?,?)""",
                    (case_id, laplacian_variance, mean_brightness,
                     leaf_coverage_fraction, leaf_coverage_method),
                )
        except sqlite3.IntegrityError:
            raise TraceError("image measurements require a new existing case") from None
        except sqlite3.Error:
            raise TraceError("image measurements could not be stored") from None

    def get_image_measurements(self, case_id: str) -> dict[str, Any] | None:
        """Read T04 observations without mapping them to S3 or routing."""
        if not isinstance(case_id, str) or not re.fullmatch(r"[0-9a-f]{32}", case_id):
            raise TraceError("case ID must be a generated lowercase UUID hex value")
        row = self._connection.execute(
            "SELECT * FROM image_measurements WHERE case_id=?", (case_id,)
        ).fetchone()
        return dict(row) if row else None

    def record_signals(
        self,
        case_id: str,
        *,
        s1: float | None,
        s2: float | None,
        s3: float | None,
        s4: float | None,
        score: float | None,
        decision: str,
        escalated: bool,
    ) -> None:
        """Persist one B9 signal/decision row for an existing case.

        Unavailable measurements are SQL NULL. No source text or measurement
        reasons are stored because they are outside the B9 signals schema.
        Duplicate decisions fail rather than overwriting a prior trace.
        """
        _validate_signal_record(case_id, (s1, s2, s3, s4, score), decision, escalated)
        try:
            with self._connection:
                self._connection.execute(
                    """INSERT INTO signals(case_id,s1,s2,s3,s4,score,decision,escalated)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (case_id, s1, s2, s3, s4, score, decision, int(escalated)),
                )
        except sqlite3.IntegrityError:
            raise TraceError("signal trace is duplicate or has no case") from None
        except sqlite3.Error:
            raise TraceError("signal trace could not be stored") from None

    def get_signals(self, case_id: str) -> dict[str, Any] | None:
        """Read the B9 decision signals row for a case, if present."""
        if not isinstance(case_id, str) or not re.fullmatch(r"[0-9a-f]{32}", case_id):
            raise TraceError("case ID must be a generated lowercase UUID hex value")
        try:
            row = self._connection.execute(
                "SELECT * FROM signals WHERE case_id=?", (case_id,)
            ).fetchone()
        except sqlite3.Error:
            raise TraceError("signal trace could not be read") from None
        return dict(row) if row else None

    def put_cache(
        self,
        cache_key: str,
        payload: Mapping[str, object],
        *,
        timestamp: str | None = None,
    ) -> CachedResponse:
        """Insert one strict synthetic demo response; duplicate keys fail."""
        _validate_cache_key(cache_key)
        normalized = _normalize_cache_payload(payload)
        stamp = _normalize_cache_timestamp(timestamp) if timestamp is not None else _utc_now()
        response_json = json.dumps(normalized, sort_keys=True, separators=(",", ":"), allow_nan=False)
        size_limit = MAX_WORKFLOW_CACHE_RESPONSE_BYTES if normalized["schema"] == WORKFLOW_CACHE_SCHEMA else MAX_CACHE_RESPONSE_BYTES
        if len(response_json.encode("utf-8")) > size_limit:
            raise TraceError("cached response exceeds the size limit")
        try:
            with self._connection:
                self._connection.execute(
                    'INSERT INTO cache("key", response_json, ts) VALUES(?,?,?)',
                    (cache_key, response_json, stamp),
                )
        except sqlite3.IntegrityError:
            raise TraceError("cache key already exists") from None
        except sqlite3.Error:
            raise TraceError("cache entry could not be stored") from None
        if normalized["schema"] == WORKFLOW_CACHE_SCHEMA:
            return CachedResponse(
                cache_key=cache_key,
                status=str(normalized["action"]),
                response_code=str(normalized["action"]),
                timestamp=stamp,
                provenance=WORKFLOW_CACHE_PROVENANCE,
                reason=str(normalized["reason"]),
                reply=str(normalized["reply"]),
                severity_pct=normalized["severity_pct"],
                severity_band=normalized["severity_band"],
            )
        return CachedResponse(
            cache_key=cache_key,
            status=normalized["status"],
            response_code=normalized["response_code"],
            timestamp=stamp,
        )

    def get_cache(self, cache_key: str) -> CachedResponse | None:
        """Read and revalidate one cache row; malformed rows fail closed."""
        _validate_cache_key(cache_key)
        try:
            row = self._connection.execute(
                'SELECT response_json, ts FROM cache WHERE "key"=?', (cache_key,)
            ).fetchone()
        except sqlite3.Error:
            raise TraceError("cache entry could not be read") from None
        if row is None:
            return None
        payload = _decode_cache_payload(row["response_json"])
        stamp = _normalize_cache_timestamp(row["ts"])
        if stamp != row["ts"]:
            raise TraceError("cached response timestamp is not canonical")
        if payload["schema"] == WORKFLOW_CACHE_SCHEMA:
            return CachedResponse(
                cache_key=cache_key,
                status=str(payload["action"]),
                response_code=str(payload["action"]),
                timestamp=stamp,
                provenance=WORKFLOW_CACHE_PROVENANCE,
                reason=str(payload["reason"]),
                reply=str(payload["reply"]),
                severity_pct=payload["severity_pct"],
                severity_band=payload["severity_band"],
            )
        return CachedResponse(
            cache_key=cache_key,
            status=payload["status"],
            response_code=payload["response_code"],
            timestamp=stamp,
            provenance=CACHE_PROVENANCE,
        )

    def record_scan(
        self,
        *,
        scan_id: str,
        user_hash: str,
        plant_label: str,
        timestamp: str,
        image_hash: str,
        severity_pct: float,
        case_id: str,
    ) -> dict[str, Any] | None:
        """Atomically store a scan and return its prior same-plant scan.

        The case must already exist and carry the same hashed user ID. Labels
        match exactly as stored; no localization, trimming, or fuzzy matching
        is inferred here. Equal/older timestamps are rejected to keep ordering
        deterministic.
        """
        _validate_scan(scan_id, user_hash, plant_label, timestamp, image_hash, severity_pct, case_id)
        normalized_ts = _normalize_timestamp(timestamp)
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            case = self._connection.execute(
                "SELECT user_hash FROM cases WHERE case_id=?", (case_id,)
            ).fetchone()
            if case is None or case["user_hash"] != user_hash:
                self._connection.rollback()
                raise TraceError("scan case is missing or belongs to a different user")
            duplicate = self._connection.execute(
                "SELECT 1 FROM scans WHERE scan_id=?", (scan_id,)
            ).fetchone()
            if duplicate is not None:
                self._connection.rollback()
                raise TraceError("scan ID is already recorded")
            previous = self._connection.execute(
                """SELECT * FROM scans WHERE user_hash=? AND plant_label=?
                   ORDER BY ts DESC, scan_id DESC LIMIT 1""",
                (user_hash, plant_label),
            ).fetchone()
            if previous is not None and normalized_ts <= previous["ts"]:
                self._connection.rollback()
                raise TraceError("scan timestamp must follow the previous plant scan")
            self._connection.execute(
                """INSERT INTO scans(scan_id,user_hash,plant_label,ts,image_hash,
                   severity_pct,case_id) VALUES(?,?,?,?,?,?,?)""",
                (scan_id, user_hash, plant_label, normalized_ts, image_hash,
                 float(severity_pct), case_id),
            )
            self._connection.commit()
            return dict(previous) if previous is not None else None
        except TraceError:
            raise
        except sqlite3.IntegrityError:
            self._connection.rollback()
            raise TraceError("scan is duplicate or violates trace references") from None
        except sqlite3.Error:
            self._connection.rollback()
            raise TraceError("scan record could not be stored") from None

    def get_scan(self, scan_id: str) -> dict[str, Any] | None:
        row = self._connection.execute("SELECT * FROM scans WHERE scan_id=?", (scan_id,)).fetchone()
        return dict(row) if row else None

    def latest_scan(self, user_hash: str, plant_label: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            """SELECT * FROM scans WHERE user_hash=? AND plant_label=?
               ORDER BY ts DESC, scan_id DESC LIMIT 1""",
            (user_hash, plant_label),
        ).fetchone()
        return dict(row) if row else None

    def backup_to(self, destination: str | Path) -> Path:
        """Create a local SQLite backup without replacing an existing file."""
        target = Path(destination)
        try:
            if self._database_path != ":memory:" and target.resolve() == Path(self._database_path).resolve():
                raise TraceError("backup destination must differ from the open database")
            descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
        except TraceError:
            raise
        except OSError:
            raise TraceError("backup destination is unavailable") from None
        target_connection: sqlite3.Connection | None = None
        try:
            target_connection = sqlite3.connect(str(target))
            self._connection.backup(target_connection)
            target_connection.close()
            target_connection = None
            return target
        except sqlite3.Error:
            if target_connection is not None:
                target_connection.close()
            target.unlink(missing_ok=True)
            raise TraceError("trace backup failed") from None

    def close(self) -> None:
        self._connection.close()


def _validate_cache_key(cache_key: str) -> None:
    if not isinstance(cache_key, str) or not re.fullmatch(r"[0-9a-f]{64}", cache_key):
        raise TraceError("cache key must be a lowercase SHA-256 digest")


def _validate_signal_record(
    case_id: str,
    values: tuple[float | None, ...],
    decision: str,
    escalated: bool,
) -> None:
    if not isinstance(case_id, str) or not re.fullmatch(r"[0-9a-f]{32}", case_id):
        raise TraceError("case ID must be a generated lowercase UUID hex value")
    for value in values:
        if value is None:
            continue
        try:
            valid = (
                not isinstance(value, bool)
                and isinstance(value, (int, float))
                and math.isfinite(value)
                and 0 <= value <= 1
            )
        except (OverflowError, TypeError):
            valid = False
        if not valid:
            raise TraceError("signal values must be finite normalized values or NULL")
    if not isinstance(decision, str) or decision not in {"retake", "answer", "escalate", "ask", "refer"}:
        raise TraceError("signal decision is unsupported")
    if type(escalated) is not bool:
        raise TraceError("escalated must be boolean")


def _normalize_cache_payload(payload: Mapping[str, object]) -> dict[str, object]:
    if isinstance(payload, Mapping) and payload.get("schema") == WORKFLOW_CACHE_SCHEMA:
        return _normalize_workflow_cache_payload(payload)
    fields = {"schema", "provenance", "status", "response_code"}
    if not isinstance(payload, Mapping) or set(payload) != fields:
        raise TraceError("cached response fields do not match the demo schema")
    if payload["schema"] != CACHE_SCHEMA or payload["provenance"] != CACHE_PROVENANCE:
        raise TraceError("cached response schema or provenance is invalid")
    status = payload["status"]
    response_code = payload["response_code"]
    if not isinstance(status, str) or not isinstance(response_code, str):
        raise TraceError("cached response status fields must be strings")
    if (status, response_code) not in CACHE_RESPONSE_CODES:
        raise TraceError("cached response outcome is unsupported")
    return {
        "schema": CACHE_SCHEMA,
        "provenance": CACHE_PROVENANCE,
        "status": status,
        "response_code": response_code,
    }


def _normalize_workflow_cache_payload(payload: Mapping[str, object]) -> dict[str, object]:
    fields = {"schema", "provenance", "action", "reason", "reply", "severity_pct", "severity_band"}
    if set(payload) != fields or payload.get("provenance") != WORKFLOW_CACHE_PROVENANCE:
        raise TraceError("cached workflow fields or provenance are invalid")
    action, reason, reply = payload["action"], payload["reason"], payload["reply"]
    if not isinstance(action, str) or action not in {"answer", "ask", "refer", "retake"}:
        raise TraceError("cached workflow action is unsupported")
    if not isinstance(reason, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", reason):
        raise TraceError("cached workflow reason is invalid")
    if (
        not isinstance(reply, str) or len(reply.encode("utf-8")) > 4096
        or not reply.startswith(WORKFLOW_CACHE_PROVENANCE)
        or "preliminary guidance" not in reply
        or any(ord(char) < 32 and char not in "\n\t" for char in reply)
    ):
        raise TraceError("cached workflow reply is invalid")
    severity, band_value = payload["severity_pct"], payload["severity_band"]
    if severity is None:
        if band_value is not None:
            raise TraceError("cached workflow severity band has no percentage")
    elif (
        isinstance(severity, bool) or not isinstance(severity, (int, float))
        or not math.isfinite(severity) or not 0 <= severity <= 100
        or band_value not in {"low", "moderate", "high"}
    ):
        raise TraceError("cached workflow severity is invalid")
    return {
        "schema": WORKFLOW_CACHE_SCHEMA,
        "provenance": WORKFLOW_CACHE_PROVENANCE,
        "action": action,
        "reason": reason,
        "reply": reply,
        "severity_pct": severity,
        "severity_band": band_value,
    }


def _decode_cache_payload(raw: object) -> dict[str, object]:
    if not isinstance(raw, str) or len(raw.encode("utf-8", errors="replace")) > MAX_WORKFLOW_CACHE_RESPONSE_BYTES:
        raise TraceError("cached response is malformed or oversized")

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    try:
        parsed = json.loads(raw, object_pairs_hook=unique_object)
    except (json.JSONDecodeError, ValueError, RecursionError):
        raise TraceError("cached response JSON is invalid") from None
    normalized = _normalize_cache_payload(parsed)
    size_limit = MAX_WORKFLOW_CACHE_RESPONSE_BYTES if normalized["schema"] == WORKFLOW_CACHE_SCHEMA else MAX_CACHE_RESPONSE_BYTES
    if len(raw.encode("utf-8")) > size_limit:
        raise TraceError("cached response is oversized")
    return normalized


def _normalize_cache_timestamp(value: str) -> str:
    if not isinstance(value, str) or len(value) > 64:
        raise TraceError("cache timestamp is invalid")
    return _normalize_timestamp(value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _validate_case(case: TraceCase) -> None:
    if not isinstance(case, TraceCase):
        raise TraceError("case must be a TraceCase")
    if not isinstance(case.case_id, str) or not re.fullmatch(r"[0-9a-f]{32}", case.case_id):
        raise TraceError("case ID must be a generated lowercase UUID hex value")
    if not isinstance(case.final_action, str) or case.final_action not in {"answer", "ask", "refer", "retake", "escalate", "blocked", "referred", "manual_review", "unknown"}:
        raise TraceError("final action is unsupported")
    if not isinstance(case.lang, str) or case.lang not in {"en", "hi"} or not isinstance(case.input_type, str) or case.input_type not in {"photo", "voice", "text"}:
        raise TraceError("case language or input type is unsupported")
    if case.data_policy is not None and (not isinstance(case.data_policy, str) or case.data_policy not in {"private", "public_test"}):
        raise TraceError("data policy is unsupported")
    for field in ("user_hash", "image_hash"):
        value = getattr(case, field)
        if value is not None and (
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
        ):
            raise TraceError("stored identifiers must be SHA-256 hex digests")
    if case.kb_card_id is not None and (
        not isinstance(case.kb_card_id, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", case.kb_card_id)
    ):
        raise TraceError("KB card ID must be a bounded identifier")
    if case.quality_scores is not None:
        try:
            scores = json.loads(case.quality_scores)
        except (TypeError, json.JSONDecodeError):
            raise TraceError("quality scores must be a numeric JSON mapping") from None
        if not isinstance(scores, dict) or set(scores) - {"s1", "s2", "s3", "s4"}:
            raise TraceError("quality scores must use B3 signal keys")
        if any(value is not None and (
            type(value) not in {int, float} or not math.isfinite(value) or not 0 <= value <= 1
        ) for value in scores.values()):
            raise TraceError("quality scores must be finite normalized values")
    if case.severity_pct is not None and (
        not isinstance(case.severity_pct, (int, float))
        or isinstance(case.severity_pct, bool)
        or not math.isfinite(case.severity_pct)
        or not 0 <= case.severity_pct <= 100
    ):
        raise TraceError("severity must be a finite percentage")


def _validate_step(step: TraceStep) -> None:
    if not isinstance(step, TraceStep):
        raise TraceError("steps must be TraceStep values")
    for value in (step.step_name, step.outcome):
        if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value):
            raise TraceError("step labels must be bounded strings")
    if not isinstance(step.latency_ms, (int, float)) or isinstance(step.latency_ms, bool) or not math.isfinite(step.latency_ms) or step.latency_ms < 0:
        raise TraceError("step latency must be finite and non-negative")
    if type(step.retries) is not int or not 0 <= step.retries <= 2:
        raise TraceError("retry count is outside the B11 bound")
    if step.started_at is not None:
        _normalize_timestamp(step.started_at)
    for count in (step.tokens_in, step.tokens_out):
        if count is not None and (type(count) is not int or count < 0):
            raise TraceError("token counts must be non-negative integers")
    if step.est_cost is not None and (not isinstance(step.est_cost, Decimal) or not step.est_cost.is_finite() or step.est_cost < 0):
        raise TraceError("step cost must be a finite non-negative Decimal")
    if step.model is not None and (
        not isinstance(step.model, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", step.model)
    ):
        raise TraceError("model must be a bounded identifier")
    if step.error_code is not None and (not isinstance(step.error_code, str) or len(step.error_code) > 64 or not step.error_code.replace("_", "").isalnum()):
        raise TraceError("error must be a safe code")


def _validate_scan(
    scan_id: str,
    user_hash: str,
    plant_label: str,
    timestamp: str,
    image_hash: str,
    severity_pct: float,
    case_id: str,
) -> None:
    if not isinstance(scan_id, str) or not re.fullmatch(r"[0-9a-f]{32}", scan_id):
        raise TraceError("scan ID must be a lowercase UUID hex value")
    if not isinstance(case_id, str) or not re.fullmatch(r"[0-9a-f]{32}", case_id):
        raise TraceError("case ID must be a lowercase UUID hex value")
    for value in (user_hash, image_hash):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise TraceError("scan identities must be SHA-256 hex digests")
    if not isinstance(plant_label, str) or not plant_label.strip() or len(plant_label) > 256:
        raise TraceError("plant label must be non-empty and at most 256 characters")
    if any(unicodedata.category(char) == "Cc" for char in plant_label):
        raise TraceError("plant label contains a control character")
    if (
        not isinstance(severity_pct, (int, float)) or isinstance(severity_pct, bool)
        or not math.isfinite(severity_pct) or not 0 <= severity_pct <= 100
    ):
        raise TraceError("severity must be a finite percentage")
    _normalize_timestamp(timestamp)


def _validate_eval_run(
    run_id: str,
    strategy: str,
    git_sha: str | None,
    metrics: Mapping[str, object],
) -> None:
    if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise TraceError("evaluation run ID must be lowercase UUID hex")
    if not isinstance(strategy, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", strategy):
        raise TraceError("evaluation strategy is invalid")
    if git_sha is not None and (
        not isinstance(git_sha, str) or not re.fullmatch(r"[0-9a-f]{40,64}", git_sha)
    ):
        raise TraceError("evaluation git SHA is invalid")
    if not isinstance(metrics, Mapping) or not metrics:
        raise TraceError("evaluation metrics must be a non-empty mapping")


def _normalize_timestamp(value: str) -> str:
    if not isinstance(value, str):
        raise TraceError("timestamp must be an ISO-8601 string with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise TraceError("timestamp must include a timezone")
        return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    except (ValueError, OverflowError):
        raise TraceError("timestamp must be an ISO-8601 string with timezone") from None
