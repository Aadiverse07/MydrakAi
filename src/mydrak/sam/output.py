"""Offline-only SAM 3.1 segmentation output parser (Phase 2, Task 1).

Verified shape (docs/verification/official_meta_api_matrix.md, SAM 3.1 row):
`output_text` uses special-token records, one line per image or video frame,
carrying an object ID, a box in SOURCE PIXELS, and a mask with
dimensions/encoding. Zero matches are valid.

What this module is NOT: it does not parse Meta wire text, call any API, or
decode mask payloads. It validates a project-local synthetic fixture grammar
that mirrors only the verified shape above, so offline severity math can be
exercised without network access:

    {"image": {"width": <int>, "height": int},
     "objects": [{"id": <str>,
                  "box": [x_min, y_min, x_max, y_max],
                  "mask": {"width": <int>, "height": <int>,
                           "encoding": <str>, "data": <str>},
                  "score"?: <float 0..1>}]}

Rules, all fail-closed (SamOutputError, a ValueError, on any violation):

- Boxes are absolute source-pixel coordinates: 0 <= min < max, bounded by the
  image dimensions. Normalized 0..1 coordinates are UNVERIFIED and unsupported.
- Mask dimensions must fit inside the frame they refer to; a larger mask is
  malformed. Mask/frame equality is not required (crops allowed).
- The mask `encoding` label and `data` payload are opaque strings. The exact
  on-the-wire mask encoding is UNVERIFIED, so NOTHING here decodes them and no
  encoding value is assumed valid beyond being a non-empty string.
- Unknown keys at any level are rejected: schema drift must fail loudly, not
  pass silently. Error messages never echo untrusted strings.
- Size caps in SamLimits are local test boundaries, NOT SAM-specific limits
  (UNVERIFIED per the matrix). Pass custom limits to exercise oversized input
  without huge allocations.

No SAM client exists in this repository; a future client must map the real
`output_text` records onto this grammar first, and that mapping itself remains
UNVERIFIED until tested against official documentation or an authorized
response sample.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class SamOutputError(ValueError):
    """Raised when synthetic SAM output fails validation."""


@dataclass(frozen=True)
class SamLimits:
    """Local test boundaries (not SAM-specific limits)."""

    max_dimension: int = 20000
    max_objects: int = 256
    max_id_len: int = 128
    max_encoding_len: int = 64
    max_mask_chars: int = 4_000_000


@dataclass(frozen=True)
class SamMask:
    """Opaque mask payload with its dimensions. Never decoded here."""

    width: int
    height: int
    encoding: str
    data: str


@dataclass(frozen=True)
class SamObject:
    """One validated segmentation record: id, pixel box, mask, optional score."""

    id: str
    box: tuple[float, float, float, float]
    mask: SamMask
    score: float | None


@dataclass(frozen=True)
class SamSegmentation:
    """Validated internal representation of one frame's SAM output."""

    image_width: int
    image_height: int
    objects: tuple[SamObject, ...]

    @property
    def match_count(self) -> int:
        return len(self.objects)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True  # ints are always finite; never convert to float here
    return isinstance(value, float) and math.isfinite(value)


def _safe_float(value: Any) -> float:
    """Convert a validated number, normalizing overflow to SamOutputError.

    Callers must check _is_number first; arbitrarily large ints pass that
    check but crash float(), so the conversion stays guarded here.
    """
    try:
        return float(value)
    except OverflowError as exc:
        raise SamOutputError("numeric value out of representable range") from exc


def _require_keys(node: Mapping[str, Any], where: str, required: set[str]) -> None:
    if set(node) != required:
        raise SamOutputError(f"{where} must contain exactly {sorted(required)}")


def _parse_frame(node: Any, limits: SamLimits) -> tuple[int, int]:
    if not isinstance(node, Mapping):
        raise SamOutputError("image frame must be a mapping")
    _require_keys(node, "image frame", {"width", "height"})
    for key in ("width", "height"):
        value = node[key]
        if not _is_int(value):
            raise SamOutputError(f"image frame {key!r} must be an integer")
        if not 1 <= value <= limits.max_dimension:
            raise SamOutputError(f"image frame {key!r} out of range")
    return node["width"], node["height"]


def _parse_box(node: Any, width: int, height: int) -> tuple[float, float, float, float]:
    if not isinstance(node, (list, tuple)) or len(node) != 4:
        raise SamOutputError("box must be a list of 4 coordinates")
    if not all(_is_number(v) for v in node):
        raise SamOutputError("box coordinates must be finite numbers")
    x_min, y_min, x_max, y_max = (_safe_float(v) for v in node)
    if not (0 <= x_min < x_max <= width):
        raise SamOutputError("box x coordinates out of frame or inverted")
    if not (0 <= y_min < y_max <= height):
        raise SamOutputError("box y coordinates out of frame or inverted")
    return (x_min, y_min, x_max, y_max)


def _parse_mask(node: Any, width: int, height: int, limits: SamLimits) -> SamMask:
    if not isinstance(node, Mapping):
        raise SamOutputError("mask must be a mapping")
    _require_keys(node, "mask", {"width", "height", "encoding", "data"})
    for key in ("width", "height"):
        value = node[key]
        if not _is_int(value):
            raise SamOutputError(f"mask {key!r} must be an integer")
    mask_w, mask_h = node["width"], node["height"]
    if not 1 <= mask_w <= width:
        raise SamOutputError("mask width out of range for this frame")
    if not 1 <= mask_h <= height:
        raise SamOutputError("mask height out of range for this frame")
    encoding = node["encoding"]
    if not isinstance(encoding, str) or not 1 <= len(encoding) <= limits.max_encoding_len:
        raise SamOutputError("mask encoding must be a short non-empty string")
    data = node["data"]
    if not isinstance(data, str) or not 1 <= len(data) <= limits.max_mask_chars:
        raise SamOutputError("mask data must be a non-empty string within the size cap")
    return SamMask(width=mask_w, height=mask_h, encoding=encoding, data=data)


def _parse_object(node: Any, width: int, height: int, limits: SamLimits) -> SamObject:
    if not isinstance(node, Mapping):
        raise SamOutputError("segmentation object must be a mapping")
    keys = set(node)
    if not {"id", "box", "mask"} <= keys <= {"id", "box", "mask", "score"}:
        raise SamOutputError("object must contain id, box, mask, and only an optional score")
    obj_id = node["id"]
    if not isinstance(obj_id, str) or not 1 <= len(obj_id) <= limits.max_id_len:
        raise SamOutputError("object id must be a non-empty string within the length cap")
    box = _parse_box(node["box"], width, height)
    mask = _parse_mask(node["mask"], width, height, limits)
    if "score" not in node:
        return SamObject(id=obj_id, box=box, mask=mask, score=None)
    raw_score = node["score"]
    if raw_score is None:
        raise SamOutputError("object score must be omitted or a finite number in 0..1, not null")
    if not _is_number(raw_score) or not 0.0 <= _safe_float(raw_score) <= 1.0:
        raise SamOutputError("object score must be a finite number in 0..1")
    return SamObject(id=obj_id, box=box, mask=mask, score=_safe_float(raw_score))


def parse_sam_output(document: Any, limits: SamLimits | None = None) -> SamSegmentation:
    """Validate a synthetic SAM output fixture into a SamSegmentation."""
    caps = limits if limits is not None else SamLimits()
    if not isinstance(document, Mapping):
        raise SamOutputError("SAM output must be a mapping")
    _require_keys(document, "SAM output", {"image", "objects"})
    width, height = _parse_frame(document["image"], caps)
    raw_objects = document["objects"]
    if not isinstance(raw_objects, list):
        raise SamOutputError("SAM output objects must be a list")
    if len(raw_objects) > caps.max_objects:
        raise SamOutputError("SAM output has more objects than the limit allows")
    parsed = tuple(_parse_object(item, width, height, caps) for item in raw_objects)
    return SamSegmentation(image_width=width, image_height=height, objects=parsed)
