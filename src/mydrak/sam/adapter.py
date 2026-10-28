"""synthetic-grid-v1 adapter: parsed SamMask to scoring BinaryMask.

Contract (synthetic fixtures ONLY — not a SAM wire decoder):
- `mask.encoding` must equal exactly `"synthetic-grid-v1"`.
- `mask.data` holds newline-separated ASCII rows of `0`/`1`; row *i* is mask
  row *i* and character *j* is column *j* (orientation preserved).
- Row count must equal mask height; every row must be exactly mask-width
  characters. A trailing newline is REJECTED: it splits into an extra empty
  row, failing the count. Empty, missing, extra, ragged, and non-binary rows
  are all malformed — never trimmed, repaired, resized, or thresholded.
- Dimensions must be positive integers within the reused project caps.
- Any other encoding is rejected explicitly; opaque payloads (base64, PNG,
  RLE, or anything else) are never decoded or guessed.
- Conversion and scoring stay separate: this module only builds the
  `BinaryMask`; IoU/Dice live in `sam/scores.py`. Objects are converted one
  at a time and never merged; boxes are never rasterized.
"""

from mydrak.sam.output import SamLimits, SamMask
from mydrak.sam.scores import BinaryMask, SegmentationEvalError

GRID_ENCODING = "synthetic-grid-v1"


def _check_dimensions(width: object, height: object, max_dimension: int) -> tuple[int, int]:
    if isinstance(width, bool) or not isinstance(width, int) or width < 1:
        raise SegmentationEvalError("grid mask width must be a positive integer")
    if isinstance(height, bool) or not isinstance(height, int) or height < 1:
        raise SegmentationEvalError("grid mask height must be a positive integer")
    if width > max_dimension:
        raise SegmentationEvalError("grid mask width exceeds the dimension cap")
    if height > max_dimension:
        raise SegmentationEvalError("grid mask height exceeds the dimension cap")
    return width, height


def grid_mask_to_binary(mask: SamMask, limits: SamLimits | None = None) -> BinaryMask:
    """Convert a synthetic-grid-v1 SamMask into a scoring BinaryMask."""
    if not isinstance(mask, SamMask):
        raise SegmentationEvalError("grid adapter input must be a SamMask")
    if mask.encoding != GRID_ENCODING:
        raise SegmentationEvalError("unsupported mask encoding for grid adapter")
    caps = limits if limits is not None else SamLimits()
    if not isinstance(mask.data, str):
        raise SegmentationEvalError("grid mask data must be a string")
    if len(mask.data) > caps.max_mask_chars:
        raise SegmentationEvalError("grid mask data exceeds the size cap")
    width, height = _check_dimensions(mask.width, mask.height, caps.max_dimension)
    rows = mask.data.split("\n")
    if len(rows) != height:
        raise SegmentationEvalError("grid row count must equal mask height")
    return BinaryMask(width, height, rows)
