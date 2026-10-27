"""Signal combination for the Decider (spec B3).

S1 sample agreement, S2 KB match, S3 image quality, S4 stated confidence.
Each signal ranges 0..1; weights must sum to 1.
"""


def _check_unit(name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be within 0..1, got {value!r}")


def combine(s1: float, s2: float, s3: float, s4: float, weights: dict[str, float]) -> float:
    """Weighted score: w1*S1 + w2*S2 + w3*S3 + w4*S4."""
    for name, value in (("s1", s1), ("s2", s2), ("s3", s3), ("s4", s4)):
        _check_unit(name, value)
    total = weights["s1_agreement"] + weights["s2_kb_match"] + weights["s3_quality"] + weights["s4_stated_confidence"]
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"weights must sum to 1, got {total!r}")
    return (
        weights["s1_agreement"] * s1
        + weights["s2_kb_match"] * s2
        + weights["s3_quality"] * s3
        + weights["s4_stated_confidence"] * s4
    )
