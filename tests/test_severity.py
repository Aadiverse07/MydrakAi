"""Severity math: percent, bands, and recovery trend."""

import pytest

from mydrak.sam.severity import band, recovery_trend, severity_pct


def test_severity_pct_known_fixture():
    assert severity_pct(18.0, 100.0) == pytest.approx(18.0)


def test_severity_pct_empty_leaf_returns_none():
    assert severity_pct(0.0, 0.0) is None
    assert severity_pct(5.0, -1.0) is None


def test_severity_pct_rejects_negative_lesion():
    with pytest.raises(ValueError):
        severity_pct(-2.0, 100.0)


def test_band_boundaries():
    assert band(10.0) == "low"
    assert band(10.1) == "moderate"
    assert band(30.0) == "moderate"
    assert band(30.1) == "high"


def test_recovery_trend_margin():
    assert recovery_trend(5.0) == "spreading"
    assert recovery_trend(-5.0) == "improving"
    assert recovery_trend(3.0) == "no_clear_change"
    assert recovery_trend(0.0) == "no_clear_change"
