"""Signal combination for the Decider (spec B3).

S1 sample agreement, S2 KB match, S3 image quality, S4 stated confidence.
Each signal ranges 0..1; weights must sum to 1.
"""

import math
from collections.abc import Mapping
from numbers import Real

SIGNAL_WEIGHT_KEYS = frozenset({
    "s1_agreement", "s2_kb_match", "s3_quality", "s4_stated_confidence",
})


def _check_unit(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number within 0..1")
    try:
        valid = math.isfinite(value) and 0.0 <= value <= 1.0
    except (OverflowError, TypeError):
        valid = False
    if not valid:
        raise ValueError(f"{name} must be a finite number within 0..1")


def combine(s1: float, s2: float, s3: float, s4: float, weights: Mapping[str, float]) -> float:
    """Weighted score: w1*S1 + w2*S2 + w3*S3 + w4*S4."""
    for name, value in (("s1", s1), ("s2", s2), ("s3", s3), ("s4", s4)):
        _check_unit(name, value)
    if not isinstance(weights, Mapping) or set(weights) != SIGNAL_WEIGHT_KEYS:
        raise ValueError("weights must define exactly the four B3 signals")
    checked_weights: dict[str, float] = {}
    for name in SIGNAL_WEIGHT_KEYS:
        weight = weights[name]
        if isinstance(weight, bool) or not isinstance(weight, Real):
            raise ValueError("weights must be finite nonnegative numbers")
        try:
            valid = math.isfinite(weight) and weight >= 0.0
        except (OverflowError, TypeError):
            valid = False
        if not valid:
            raise ValueError("weights must be finite nonnegative numbers")
        checked_weights[name] = float(weight)
    total = sum(checked_weights.values())
    if not math.isfinite(total) or abs(total - 1.0) > 1e-6:
        raise ValueError("weights must sum to 1")
    return (
        checked_weights["s1_agreement"] * s1
        + checked_weights["s2_kb_match"] * s2
        + checked_weights["s3_quality"] * s3
        + checked_weights["s4_stated_confidence"] * s4
    )
