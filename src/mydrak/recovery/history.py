"""Offline B5 recovery-history contract over the shared T09 SQLite store."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import uuid

from mydrak.sam.severity import recovery_trend
from mydrak.trace.store import TraceError, TraceStore


DEFAULT_RECOVERY_MARGIN_PP = 3.0
CAVEAT_KEY = "measurement_conditions_angle_light_distance"


class RecoveryHistoryError(ValueError):
    """Raised when a recovery scan cannot be safely recorded."""


@dataclass(frozen=True)
class RecoveryScan:
    """One validated scan record; identifiers are pre-hashed SHA-256 values."""

    user_hash: str
    plant_label: str
    timestamp: str
    image_hash: str
    severity_pct: float
    case_id: str
    scan_id: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass(frozen=True)
class RecoveryAssessment:
    """Persisted scan and optional comparison with the preceding same plant."""

    scan_id: str
    prior_scan_id: str | None
    prior_severity_pct: float | None
    severity_delta_pp: float | None
    trend: str | None
    caveat_key: str = CAVEAT_KEY
    treatment_effect_claim_allowed: bool = False


def record_recovery_scan(
    store: TraceStore,
    scan: RecoveryScan,
    *,
    margin_pp: float = DEFAULT_RECOVERY_MARGIN_PP,
) -> RecoveryAssessment:
    """Persist a scan and compare it to the latest exact-label scan.

    No image content is accepted. The caller supplies the B5 image digest and
    the already-hashed user identifier; raw identifiers are rejected by the
    shared store. The label is matched exactly. A baseline has no trend.
    """
    if not isinstance(store, TraceStore) or not isinstance(scan, RecoveryScan):
        raise RecoveryHistoryError("trace store and recovery scan are required")
    if (
        not isinstance(margin_pp, (int, float)) or isinstance(margin_pp, bool)
        or not math.isfinite(margin_pp) or margin_pp < 0
    ):
        raise RecoveryHistoryError("recovery margin must be finite and non-negative")
    try:
        previous = store.record_scan(
            scan_id=scan.scan_id,
            user_hash=scan.user_hash,
            plant_label=scan.plant_label,
            timestamp=scan.timestamp,
            image_hash=scan.image_hash,
            severity_pct=scan.severity_pct,
            case_id=scan.case_id,
        )
    except TraceError:
        raise RecoveryHistoryError("recovery scan was rejected") from None
    if previous is None:
        return RecoveryAssessment(scan_id=scan.scan_id, prior_scan_id=None,
                                  prior_severity_pct=None, severity_delta_pp=None,
                                  trend=None)
    delta = float(scan.severity_pct) - float(previous["severity_pct"])
    return RecoveryAssessment(
        scan_id=scan.scan_id,
        prior_scan_id=previous["scan_id"],
        prior_severity_pct=float(previous["severity_pct"]),
        severity_delta_pp=delta,
        trend=recovery_trend(delta, float(margin_pp)),
    )
