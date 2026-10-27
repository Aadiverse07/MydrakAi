"""Signal combination: weighted score and input validation."""

import pytest

from mydrak.decider.signals import combine

W = {"s1_agreement": 0.25, "s2_kb_match": 0.25, "s3_quality": 0.25, "s4_stated_confidence": 0.25}


def test_combine_equal_weights_is_mean():
    assert combine(1.0, 0.5, 0.0, 0.5, W) == pytest.approx(0.5)


def test_combine_perfect_and_empty():
    assert combine(1.0, 1.0, 1.0, 1.0, W) == pytest.approx(1.0)
    assert combine(0.0, 0.0, 0.0, 0.0, W) == pytest.approx(0.0)


def test_combine_rejects_out_of_range_signal():
    with pytest.raises(ValueError):
        combine(1.5, 0.0, 0.0, 0.0, W)


def test_combine_rejects_weights_not_summing_to_one():
    bad = dict(W, s1_agreement=0.9)
    with pytest.raises(ValueError):
        combine(1.0, 1.0, 1.0, 1.0, bad)
