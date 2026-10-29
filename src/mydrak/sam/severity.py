"""Severity: lesion_area / leaf_area * 100, mapped to configurable bands.

Bands are heuristics, NOT validated agronomic thresholds. Callers must label
the result an estimate from one photo. No SAM client in Phase 0.
"""

from mydrak.sam.scores import BinaryMask, intersection


def severity_pct(lesion_area: float, leaf_area: float) -> float | None:
    """Return percent of leaf affected, or None when there is no leaf mask."""
    if leaf_area <= 0:
        return None
    if lesion_area < 0:
        raise ValueError(f"lesion_area must be >= 0, got {lesion_area!r}")
    return lesion_area / leaf_area * 100.0


def mask_severity_pct(leaf: BinaryMask, lesion: BinaryMask) -> float | None:
    """Return 100 * (lesion cells overlapping leaf) / (leaf cells).

    Both masks must be BinaryMask values with identical dimensions;
    anything else raises SegmentationEvalError. Returns None when the
    leaf has no foreground cells (matching severity_pct), 0.0 when
    nothing overlaps, and ignores lesion cells outside the leaf. The
    result is unrounded. Grid-based and project-local: not agronomic
    validation, provider output, or real-image accuracy.
    """
    overlap = intersection(lesion, leaf)
    leaf_cells = leaf.foreground
    if leaf_cells == 0:
        return None
    return overlap / leaf_cells * 100.0


def band(pct: float, low_max: float = 10.0, moderate_max: float = 30.0) -> str:
    """Map a severity percent to low | moderate | high."""
    if pct < 0:
        raise ValueError(f"severity pct must be >= 0, got {pct!r}")
    if pct <= low_max:
        return "low"
    if pct <= moderate_max:
        return "moderate"
    return "high"


def recovery_trend(delta_pp: float, margin_pp: float = 3.0) -> str:
    """Classify a severity delta: spreading | improving | no_clear_change."""
    if delta_pp > margin_pp:
        return "spreading"
    if delta_pp < -margin_pp:
        return "improving"
    return "no_clear_change"
