"""Mock-first segmentation evaluation (Phase 2, Task 8).

Measures binary-mask overlap (IoU, Dice) between an explicitly supplied
prediction and explicitly supplied ground truth. Everything here is
synthetic and offline: no SAM calls, no image decoding, no diagnosis, and no
claim about real model performance.

Boundary with `sam/output.py`: that parser's mask payloads are opaque,
never-decoded strings, so they CANNOT feed this contract. Masks here use an
explicit synthetic representation (rows of "0"/"1") validated field by
field. A future adapter must decode real provider masks into `BinaryMask`
first; until then, no result here says anything about SAM accuracy.

Conventions (documented, tested):
- Coordinates are pixel-grid cells; both masks in a case must share exact
  width/height. Mismatched shapes are rejected, never resized or aligned.
- Empty/empty (no foreground on either side) scores IoU = Dice = 1.0:
  perfect agreement that nothing is present. One-sided emptiness scores 0.0.
- Invalid data (bad characters, ragged rows, dimension mismatch) is never a
  score: construction raises `SegmentationEvalError`.
- Missing prediction or truth skips the case with a reason; aggregates run
  over valid cases only and are null when none exist.
- Case ids are caller-supplied labels: non-empty strings, never absolute
  paths. Reports carry no timestamps, so equal inputs give equal reports.
"""

import os

METRICS_VERSION = 1


class SegmentationEvalError(ValueError):
    """Raised when evaluation input fails validation."""


class BinaryMask:
    """Explicit synthetic binary mask: rows of "0"/"1", strictly validated."""

    __slots__ = ("width", "height", "rows")

    def __init__(self, width: int, height: int, rows: list[str] | tuple[str, ...]) -> None:
        if isinstance(width, bool) or not isinstance(width, int) or width < 1:
            raise SegmentationEvalError("mask width must be a positive integer")
        if isinstance(height, bool) or not isinstance(height, int) or height < 1:
            raise SegmentationEvalError("mask height must be a positive integer")
        rows = tuple(rows)
        if len(rows) != height:
            raise SegmentationEvalError("mask row count must equal height")
        for row in rows:
            if not isinstance(row, str) or len(row) != width:
                raise SegmentationEvalError("mask rows must be strings of length width")
            if any(cell not in ("0", "1") for cell in row):
                raise SegmentationEvalError("mask rows must contain only '0' and '1'")
        self.width = width
        self.height = height
        self.rows = rows

    @property
    def foreground(self) -> int:
        """Count of foreground ('1') cells."""
        return sum(row.count("1") for row in self.rows)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, BinaryMask)
            and (self.width, self.height, self.rows) == (other.width, other.height, other.rows)
        )

    def __repr__(self) -> str:
        return f"BinaryMask({self.width}x{self.height}, foreground={self.foreground})"


def _check_pair(pred: BinaryMask, truth: BinaryMask) -> None:
    if not isinstance(pred, BinaryMask) or not isinstance(truth, BinaryMask):
        raise SegmentationEvalError("prediction and truth must both be BinaryMask values")
    if pred.width != truth.width or pred.height != truth.height:
        raise SegmentationEvalError("prediction and truth shapes must match exactly")


def intersection(pred: BinaryMask, truth: BinaryMask) -> int:
    """Foreground cells present in both masks."""
    _check_pair(pred, truth)
    return sum(
        1
        for prow, trow in zip(pred.rows, truth.rows)
        for pcell, tcell in zip(prow, trow)
        if pcell == "1" and tcell == "1"
    )


def iou(pred: BinaryMask, truth: BinaryMask) -> float:
    """Intersection over union; 1.0 when both masks are empty."""
    union = pred.foreground + truth.foreground - intersection(pred, truth)
    if union == 0:
        return 1.0
    return intersection(pred, truth) / union


def dice(pred: BinaryMask, truth: BinaryMask) -> float:
    """Dice coefficient; 1.0 when both masks are empty."""
    total = pred.foreground + truth.foreground
    if total == 0:
        return 1.0
    return 2 * intersection(pred, truth) / total


def _check_case_id(case_id: str) -> None:
    if not isinstance(case_id, str) or not case_id or len(case_id) > 128:
        raise SegmentationEvalError("case id must be a non-empty string within 128 chars")
    if os.path.isabs(case_id):
        raise SegmentationEvalError("case id must not be an absolute path")


def evaluate_case(case_id: str, pred: BinaryMask | None, truth: BinaryMask | None) -> dict:
    """Score one prediction/truth pair into a JSON-serializable record."""
    _check_case_id(case_id)
    if pred is None or truth is None:
        missing = "prediction" if pred is None else "ground truth"
        return {"id": case_id, "status": "skipped", "reason": f"missing {missing}", "iou": None, "dice": None}
    _check_pair(pred, truth)
    return {
        "id": case_id,
        "status": "valid",
        "reason": None,
        "iou": iou(pred, truth),
        "dice": dice(pred, truth),
    }


def mark_invalid(case_id: str, reason: str) -> dict:
    """Record a case that could not be scored, without inventing a score."""
    _check_case_id(case_id)
    if not isinstance(reason, str) or not reason:
        raise SegmentationEvalError("invalid-case reason must be a non-empty string")
    return {"id": case_id, "status": "invalid", "reason": reason, "iou": None, "dice": None}


def summarize(cases: list[dict]) -> dict:
    """Aggregate case records deterministically; null aggregates if none valid."""
    valid = [case for case in cases if case["status"] == "valid"]
    if valid:
        aggregates: dict = {
            "mean_iou": sum(case["iou"] for case in valid) / len(valid),
            "mean_dice": sum(case["dice"] for case in valid) / len(valid),
        }
    else:
        aggregates = {"mean_iou": None, "mean_dice": None}
    return {
        "version": METRICS_VERSION,
        "metrics": {
            "iou": "intersection / union; 1.0 when both masks are empty",
            "dice": "2 * intersection / (predicted + truth foreground); 1.0 when both masks are empty",
        },
        "cases": [dict(case) for case in cases],
        "aggregates": aggregates,
        "counts": {
            "valid": len(valid),
            "invalid": sum(1 for case in cases if case["status"] == "invalid"),
            "skipped": sum(1 for case in cases if case["status"] == "skipped"),
        },
    }
