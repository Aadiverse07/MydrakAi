"""Synthetic-only regressions for B5 recovery history persistence."""

from dataclasses import replace

import pytest

from mydrak.recovery.history import RecoveryHistoryError, RecoveryScan, record_recovery_scan
from mydrak.trace.store import TraceCase, TraceStep, TraceStore


USER_HASH = "a" * 64
IMAGE_HASH_1 = "b" * 64
IMAGE_HASH_2 = "c" * 64


def _case(case_id: str, *, user_hash=USER_HASH, image_hash=IMAGE_HASH_1):
    return TraceCase(
        case_id=case_id,
        final_action="referred",
        lang="en",
        input_type="photo",
        data_policy="private",
        user_hash=user_hash,
        image_hash=image_hash,
    )


def _add_case(store, case_id, *, user_hash=USER_HASH, image_hash=IMAGE_HASH_1):
    store.record_case(_case(case_id, user_hash=user_hash, image_hash=image_hash),
                      [TraceStep("offline_case", "completed", 1.0)])


def _scan(scan_id, case_id, *, ts="2026-01-01T00:00:00Z", label="tomato row 2",
          severity=20.0, user_hash=USER_HASH, image_hash=IMAGE_HASH_1):
    return RecoveryScan(
        scan_id=scan_id,
        case_id=case_id,
        user_hash=user_hash,
        plant_label=label,
        timestamp=ts,
        severity_pct=severity,
        image_hash=image_hash,
    )


def test_baseline_and_rescan_persist_and_use_existing_trend_helper():
    store = TraceStore(":memory:")
    _add_case(store, "00000000000000000000000000000001")
    _add_case(store, "00000000000000000000000000000002", image_hash=IMAGE_HASH_2)
    first = record_recovery_scan(
        store, _scan("00000000000000000000000000000011", "00000000000000000000000000000001")
    )
    second = record_recovery_scan(
        store,
        _scan("00000000000000000000000000000012", "00000000000000000000000000000002",
              ts="2026-01-02T00:00:00+00:00", severity=24, image_hash=IMAGE_HASH_2),
    )
    assert first.trend is None and first.severity_delta_pp is None
    assert second.prior_scan_id == first.scan_id
    assert second.prior_severity_pct == 20
    assert second.severity_delta_pp == 4
    assert second.trend == "spreading"
    assert second.caveat_key == "measurement_conditions_angle_light_distance"
    assert second.treatment_effect_claim_allowed is False
    record = store.get_scan(second.scan_id)
    assert record["plant_label"] == "tomato row 2"
    assert record["user_hash"] == USER_HASH
    assert record["image_hash"] == IMAGE_HASH_2
    assert record["severity_pct"] == 24


@pytest.mark.parametrize(
    ("severity", "expected"),
    [(23, "no_clear_change"), (23.01, "spreading"), (17, "no_clear_change"), (16.99, "improving")],
)
def test_default_three_percentage_point_margin_boundaries(severity, expected):
    store = TraceStore(":memory:")
    _add_case(store, "00000000000000000000000000000021")
    _add_case(store, "00000000000000000000000000000022")
    record_recovery_scan(store, _scan("00000000000000000000000000000031", "00000000000000000000000000000021", severity=20))
    result = record_recovery_scan(store, _scan(
        "00000000000000000000000000000032", "00000000000000000000000000000022",
        ts="2026-01-02T00:00:00Z", severity=severity,
    ))
    assert result.trend == expected


@pytest.mark.parametrize("bad", ["farmer-raw-id", "A" * 64, "short"])
def test_raw_or_malformed_user_identifiers_are_rejected_without_storage(bad):
    store = TraceStore(":memory:")
    _add_case(store, "00000000000000000000000000000041", user_hash=USER_HASH)
    scan = _scan("00000000000000000000000000000042", "00000000000000000000000000000041", user_hash=bad)
    with pytest.raises(RecoveryHistoryError):
        record_recovery_scan(store, scan)
    assert store.get_scan(scan.scan_id) is None


@pytest.mark.parametrize(
    "updates",
    [
        {"plant_label": "  "},
        {"plant_label": "x" * 257},
        {"plant_label": "bad\nlabel"},
        {"plant_label": "bad\u0085label"},
        {"timestamp": "2026-01-01T00:00:00"},
        {"timestamp": "not-a-time"},
        {"timestamp": "0001-01-01T00:00:00+23:00"},
        {"image_hash": "raw-image-bytes"},
        {"image_hash": b"synthetic image bytes"},
        {"severity_pct": float("nan")},
        {"severity_pct": 101},
        {"severity_pct": -1},
    ],
)
def test_malformed_required_fields_fail_without_inserting(updates):
    store = TraceStore(":memory:")
    case_id = "00000000000000000000000000000051"
    _add_case(store, case_id)
    scan_id = "00000000000000000000000000000052"
    with pytest.raises(RecoveryHistoryError):
        record_recovery_scan(store, replace(_scan(scan_id, case_id), **updates))
    assert store.get_scan(scan_id) is None


def test_duplicate_and_out_of_order_scans_are_rejected():
    store = TraceStore(":memory:")
    _add_case(store, "00000000000000000000000000000061")
    _add_case(store, "00000000000000000000000000000062")
    base = _scan("00000000000000000000000000000063", "00000000000000000000000000000061")
    record_recovery_scan(store, base)
    with pytest.raises(RecoveryHistoryError):
        record_recovery_scan(store, base)
    stale = _scan("00000000000000000000000000000064", "00000000000000000000000000000062", ts="2025-12-31T23:59:59Z")
    with pytest.raises(RecoveryHistoryError):
        record_recovery_scan(store, stale)
    assert len(store.get_steps(base.case_id)) == 1


def test_exact_plant_label_and_user_hash_define_comparison_scope():
    store = TraceStore(":memory:")
    _add_case(store, "00000000000000000000000000000071")
    _add_case(store, "00000000000000000000000000000072")
    _add_case(store, "00000000000000000000000000000073", user_hash="d" * 64)
    record_recovery_scan(store, _scan("00000000000000000000000000000074", "00000000000000000000000000000071"))
    other_label = record_recovery_scan(store, _scan(
        "00000000000000000000000000000075", "00000000000000000000000000000072",
        ts="2026-01-02T00:00:00Z", label="tomato row 3",
    ))
    other_user = record_recovery_scan(store, _scan(
        "00000000000000000000000000000076", "00000000000000000000000000000073",
        ts="2026-01-02T00:00:00Z", user_hash="d" * 64,
    ))
    assert other_label.prior_scan_id is None
    assert other_user.prior_scan_id is None


def test_history_survives_reopening_existing_t09_database(tmp_path):
    path = tmp_path / "trace.sqlite"
    store = TraceStore(path)
    _add_case(store, "00000000000000000000000000000081")
    first = _scan("00000000000000000000000000000082", "00000000000000000000000000000081")
    record_recovery_scan(store, first)
    store.close()
    reopened = TraceStore(path)
    _add_case(reopened, "00000000000000000000000000000083", image_hash=IMAGE_HASH_2)
    second = record_recovery_scan(reopened, _scan(
        "00000000000000000000000000000084", "00000000000000000000000000000083",
        ts="2026-01-02T00:00:00Z", severity=10, image_hash=IMAGE_HASH_2,
    ))
    assert second.prior_scan_id == first.scan_id
    assert second.trend == "improving"


def test_recovery_scan_requires_case_link_for_same_hashed_user():
    store = TraceStore(":memory:")
    _add_case(store, "00000000000000000000000000000091", user_hash="e" * 64)
    scan = _scan("00000000000000000000000000000092", "00000000000000000000000000000091", user_hash=USER_HASH)
    with pytest.raises(RecoveryHistoryError):
        record_recovery_scan(store, scan)


@pytest.mark.parametrize("margin", [-1, float("nan"), float("inf"), True])
def test_invalid_margin_fails_before_writing(margin):
    store = TraceStore(":memory:")
    _add_case(store, "000000000000000000000000000000a1")
    scan = _scan("000000000000000000000000000000a2", "000000000000000000000000000000a1")
    with pytest.raises(RecoveryHistoryError):
        record_recovery_scan(store, scan, margin_pp=margin)
    assert store.get_scan(scan.scan_id) is None


def test_margin_is_configurable_without_changing_stored_severity():
    store = TraceStore(":memory:")
    _add_case(store, "000000000000000000000000000000b1")
    _add_case(store, "000000000000000000000000000000b2")
    record_recovery_scan(store, _scan("000000000000000000000000000000b3", "000000000000000000000000000000b1", severity=20))
    assessment = record_recovery_scan(store, _scan(
        "000000000000000000000000000000b4", "000000000000000000000000000000b2",
        ts="2026-01-02T00:00:00Z", severity=24,
    ), margin_pp=5)
    assert assessment.severity_delta_pp == 4
    assert assessment.trend == "no_clear_change"
