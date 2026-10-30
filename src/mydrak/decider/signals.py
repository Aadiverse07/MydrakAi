"""Signal combination for the Decider (spec B3).

S1 sample agreement, S2 KB match, S3 image quality, S4 stated confidence.
Each signal ranges 0..1; weights must sum to 1.
"""

import math
import unicodedata
from collections.abc import Mapping
from numbers import Real

SIGNAL_WEIGHT_KEYS = frozenset({
    "s1_agreement", "s2_kb_match", "s3_quality", "s4_stated_confidence",
})


def _normalize_symptom(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("symptom phrases must be text")
    text = value.strip().lower()
    if not text:
        raise ValueError("symptom phrases must be nonempty")
    # Treat punctuation as a word boundary, then collapse all whitespace.
    normalized = " ".join(
        "".join(" " if unicodedata.category(char).startswith("P") else char for char in text).split()
    )
    if not normalized:
        raise ValueError("symptom phrases must contain non-punctuation text")
    return normalized


def s2_symptom_overlap(
    observed_symptoms: object,
    card_symptoms: object,
) -> float | None:
    """Return distinct observed phrase matches / distinct observations.

    Punctuation is normalized to word boundaries; matching is exact after
    case, whitespace, and punctuation normalization. Extra card phrases do not
    affect the denominator. No observations means the signal is unavailable.
    """
    if (
        isinstance(observed_symptoms, (str, bytes))
        or not isinstance(observed_symptoms, (list, tuple))
        or isinstance(card_symptoms, (str, bytes))
        or not isinstance(card_symptoms, (list, tuple))
    ):
        raise ValueError("symptom phrases must be lists or tuples")
    observed = {_normalize_symptom(value) for value in observed_symptoms}
    card = {_normalize_symptom(value) for value in card_symptoms}
    if not observed:
        return None
    return len(observed & card) / len(observed)


def _check_unit(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number within 0..1")
    try:
        valid = math.isfinite(value) and 0.0 <= value <= 1.0
    except (OverflowError, TypeError):
        valid = False
    if not valid:
        raise ValueError(f"{name} must be a finite number within 0..1")


CONFIDENCE_BAND_KEYS = frozenset({"low", "medium", "high"})


def validate_confidence_band_mapping(mapping: object) -> dict[str, float]:
    """Validate the user-approved, explicitly UNVERIFIED config mapping."""
    if not isinstance(mapping, Mapping) or set(mapping) != CONFIDENCE_BAND_KEYS:
        raise ValueError("confidence band mapping must define exactly low, medium, and high")
    result: dict[str, float] = {}
    for band in CONFIDENCE_BAND_KEYS:
        value = mapping[band]
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError("confidence band mapping values must be finite numbers within 0..1")
        try:
            valid = math.isfinite(value) and 0.0 <= value <= 1.0
        except (OverflowError, TypeError):
            valid = False
        if not valid:
            raise ValueError("confidence band mapping values must be finite numbers within 0..1")
        result[band] = float(value)
    return result


def aggregate_stated_confidence(
    first: object,
    second: object,
    mapping: object,
) -> float | None:
    """Map two B3 confidence values and return the lower; invalid samples are unavailable.

    Numeric B8 confidence values are already in B3's 0..1 range. Text bands
    use only the supplied config mapping; no numeric mapping is embedded here.
    """
    checked = validate_confidence_band_mapping(mapping)

    def value_for(item: object) -> float | None:
        if isinstance(item, str):
            return checked.get(item)
        if isinstance(item, bool) or not isinstance(item, Real):
            return None
        try:
            return float(item) if math.isfinite(item) and 0.0 <= item <= 1.0 else None
        except (OverflowError, TypeError):
            return None

    left, right = value_for(first), value_for(second)
    if left is None or right is None:
        return None
    return min(left, right)


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
