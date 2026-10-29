"""Severity math: percent, bands, and recovery trend.

Mask fixtures below are hand-built synthetic grids for the project-local
mask helper; lesion cells outside the leaf are ignored by contract.
"""

import pytest

from mydrak.sam.scores import BinaryMask, SegmentationEvalError
from mydrak.sam.severity import band, mask_severity_pct, recovery_trend, severity_pct


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


def test_mask_severity_partial_overlap_ignores_outside_leaf():
    leaf = BinaryMask(4, 4, ["1111", "1111", "1100", "0000"])
    assert leaf.foreground == 10
    lesion = BinaryMask(4, 4, ["1100", "1000", "0000", "0001"])
    # 3 lesion cells overlap the leaf; (3, 3) lies outside and is ignored.
    assert mask_severity_pct(leaf, lesion) == 30.0


def test_mask_severity_empty_leaf_returns_none():
    leaf = BinaryMask(2, 2, ["00", "00"])
    lesion = BinaryMask(2, 2, ["10", "01"])
    assert mask_severity_pct(leaf, lesion) is None


def test_mask_severity_no_overlap_returns_zero():
    leaf = BinaryMask(2, 2, ["11", "11"])
    lesion = BinaryMask(2, 2, ["00", "00"])
    assert mask_severity_pct(leaf, lesion) == 0.0


def test_mask_severity_rejects_shape_mismatch():
    leaf = BinaryMask(2, 2, ["11", "11"])
    lesion = BinaryMask(2, 3, ["11", "11", "11"])
    with pytest.raises(SegmentationEvalError):
        mask_severity_pct(leaf, lesion)


def test_mask_severity_rejects_non_masks():
    leaf = BinaryMask(1, 1, ["1"])
    with pytest.raises(SegmentationEvalError):
        mask_severity_pct(leaf, "1")
    with pytest.raises(SegmentationEvalError):
        mask_severity_pct(None, leaf)
