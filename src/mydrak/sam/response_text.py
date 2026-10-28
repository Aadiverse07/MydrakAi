"""Offline parser for documented Meta SAM 3.1 single-image output text.

Documented wire shape (token spelling corroborated 2026-10-28 via
official parser-repo sources — meta-sam parser READMEs, protocol
reference, cookbook, and independent API usage; exact URLs recorded in
the verification matrix; primary dev.meta.ai pages not freshly fetched):
one line per frame; a single image is frame ``<0f>``; each line is a frame
marker followed by comma-separated records; each record is a bare
non-negative integer object ID, one box token, then one mask token::

    <0f>id<|box;x1=..;y1=..;x2=..;y2=..;w=..;h=..;c=..|><|mask;x=0;y=0;c=..;data=<H>,<W>,<enc>payload|>,...

Box corners and ``w``/``h`` are source-image pixels. The mask tuple is
height,width,payload; the first payload character selects the encoding:
``~`` for lossless (the API default) or ``!`` for one_bit. The payload is
base85, never decoded here. Per the Codex review of the primary grammar
page: mask origin is ``x=0;y=0``; mask width/height are each smaller than
the corresponding source-image dimensions; confidence is absent from both
tokens or present on both with equal values. Only the exact empty string
is a valid zero-match result; whitespace-only input is malformed.
IDs need not be contiguous. A bare ``<0f>`` marker,
a trailing separator, and a leading separator are rejected: only an empty
output is a zero-match, and a marked frame must carry at least one record.

What this module does NOT do: video/multi-frame output, request building,
API clients, network, or mask decoding. Payloads stay opaque strings and are
never sent to ``synthetic-grid-v1`` or the IoU/Dice path. Fixtures exercising
this parser are synthetic documentation fixtures, not real SAM responses.

Rules enforced below: frame marker, record order (id, box, mask),
canonical key order inside tokens, ASCII-only unsigned numerics with a
local digit-length cap, pixel geometry against declared frame dims,
declared dims equal to caller-supplied expected dims, zero mask origin,
strictly-smaller mask dims, both-or-neither confidence with agreement,
encoding marker membership, payload charset, and a bounded record scan
that stops once the configured object limit is exceeded.

Recorded limitations (not guessed): box edge-inclusivity (``x2 == w``
accepted as in-bounds); the official confidence range (a local 0..1 bound
is enforced and marked as such); whether opaque payloads may contain the
``|>`` terminator or which Base85 variant Meta uses (comma is excluded
per RFC 1924 — UNVERIFIED). A payload containing ``|>`` is consumed
greedily through the record's last ``|>``; payloads ending in a literal
``|>`` stay ambiguous. The stricter semantic rules (zero origin,
strictly-smaller masks, both-or-neither confidence) rest on the Codex
review of the primary grammar page; my own snippet corroboration covers
token spelling only. All size caps are local project boundaries, never
Meta limits.
"""

import re
from dataclasses import dataclass
from typing import Any

from mydrak.sam.output import SamLimits

#: Local input-size bound (not a Meta limit), checked before parsing.
MAX_OUTPUT_CHARS = 8 * 1024 * 1024

#: Local digit-run bound so hostile inputs cannot force huge int conversions.
MAX_INT_DIGITS = 10

_FRAME_RE = re.compile(r"<([0-9A-Za-z]+)f>")
# ASCII digits only: ``\d`` would also match Unicode decimal digits (which
# ``int`` would then silently accept), so every numeric class is explicit.
_UINT_RE = re.compile(r"[0-9]+")
_ID_RE = re.compile(r"[0-9]+")
_CONF_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")
# Record boundary: a comma that starts a new record (unsigned ASCII ID
# followed by a box token). Mask ``data`` commas are followed by ``H,W,enc``
# rather than ``id<|box;``, so they never match; a comma smuggled inside an
# opaque payload can only split the input into pieces that fail record
# validation (fail-closed).
_BOUNDARY_RE = re.compile(r",(?=[0-9]+\<\|box;)")

_SINGLE_IMAGE_FRAME = "0"
_ENCODINGS = ("~", "!")
_PAYLOAD_FIRST = 0x21
_PAYLOAD_LAST = 0x7E


class SamResponseError(ValueError):
    """Raised for malformed, inconsistent, or unsupported wire text.

    Messages name the failing stage and record index only; raw untrusted
    output and payloads are never echoed.
    """


@dataclass(frozen=True)
class SamBox:
    """Parsed box token: pixel corners, declared frame dims, optional confidence."""

    x1: int
    y1: int
    x2: int
    y2: int
    width: int
    height: int
    confidence: float | None


@dataclass(frozen=True)
class SamWireMask:
    """Parsed mask token: origin, raster dims, opaque encoding/payload."""

    origin_x: int
    origin_y: int
    height: int
    width: int
    encoding: str
    payload: str
    confidence: float | None


@dataclass(frozen=True)
class SamRecord:
    """One parsed object record: integer ID, box, then mask, in that order."""

    object_id: int
    box: SamBox
    mask: SamWireMask


@dataclass(frozen=True)
class SamFrame:
    """Parsed single-image frame: expected dims plus parsed records."""

    frame_index: int
    image_width: int
    image_height: int
    objects: tuple[SamRecord, ...]

    @property
    def match_count(self) -> int:
        return len(self.objects)


def _parse_uint(text: str, index: int, what: str) -> int:
    if not _UINT_RE.fullmatch(text) or len(text) > MAX_INT_DIGITS:
        raise SamResponseError(f"record {index} has a malformed {what}")
    try:
        return int(text, 10)
    except (ValueError, OverflowError):
        raise SamResponseError(f"record {index} has a malformed {what}") from None


def _parse_confidence(text: str, index: int) -> float:
    if not _CONF_RE.fullmatch(text):
        raise SamResponseError(f"record {index} has malformed confidence")
    try:
        value = float(text)
    except (ValueError, OverflowError):
        raise SamResponseError(f"record {index} has malformed confidence") from None
    # Local sanity bound only; the official range is unverified.
    if not 0.0 <= value <= 1.0:
        raise SamResponseError(f"record {index} confidence out of range")
    return value


def _check_dimensions(value: int, index: int, what: str, cap: int) -> int:
    if not 1 <= value <= cap:
        raise SamResponseError(f"record {index} {what} out of range")
    return value


def _parse_box(body: str, index: int, expected: tuple[int, int], cap: int) -> SamBox:
    parts = body.split(";")
    if len(parts) not in (6, 7):
        raise SamResponseError(f"record {index} has a malformed box")
    names = ("x1", "y1", "x2", "y2", "w", "h")
    values: dict[str, int] = {}
    for part, name in zip(parts[:6], names):
        key, sep, val = part.partition("=")
        if not sep or key != name:
            raise SamResponseError(f"record {index} has a malformed box")
        values[name] = _parse_uint(val, index, f"box {name}")
    confidence = None
    if len(parts) == 7:
        key, sep, val = parts[6].partition("=")
        if not sep or key != "c":
            raise SamResponseError(f"record {index} has a malformed box")
        confidence = _parse_confidence(val, index)
    width = _check_dimensions(values["w"], index, "frame width", cap)
    height = _check_dimensions(values["h"], index, "frame height", cap)
    if (width, height) != expected:
        raise SamResponseError(f"record {index} declares unexpected source dimensions")
    x1, y1, x2, y2 = values["x1"], values["y1"], values["x2"], values["y2"]
    if not 0 <= x1 <= x2 <= width:
        raise SamResponseError(f"record {index} box x coordinates out of frame or inverted")
    if not 0 <= y1 <= y2 <= height:
        raise SamResponseError(f"record {index} box y coordinates out of frame or inverted")
    return SamBox(x1=x1, y1=y1, x2=x2, y2=y2, width=width, height=height, confidence=confidence)


def _take_field(body: str, index: int, key: str) -> tuple[int, str]:
    prefix = key + "="
    if not body.startswith(prefix):
        raise SamResponseError(f"record {index} has a malformed mask")
    tail = body[len(prefix):]
    match = _UINT_RE.match(tail)
    if match is None or not tail[match.end():].startswith(";"):
        raise SamResponseError(f"record {index} has a malformed mask")
    digits = match.group(0)
    if len(digits) > MAX_INT_DIGITS:
        raise SamResponseError(f"record {index} has a malformed mask")
    try:
        return int(digits, 10), tail[match.end() + 1:]
    except (ValueError, OverflowError):
        raise SamResponseError(f"record {index} has a malformed mask") from None


def _parse_mask(
    body: str, index: int, expected: tuple[int, int], cap: int, max_payload: int
) -> SamWireMask:
    origin_x, rest = _take_field(body, index, "x")
    origin_y, rest = _take_field(rest, index, "y")
    # Codex-confirmed grammar rule: the mask origin is fixed at (0, 0).
    if origin_x != 0 or origin_y != 0:
        raise SamResponseError(f"record {index} has a nonzero mask origin")
    confidence = None
    if rest.startswith("c="):
        tail = rest[len("c="):]
        match = _CONF_RE.match(tail)
        if match is None or not tail[match.end():].startswith(";"):
            raise SamResponseError(f"record {index} has malformed confidence")
        confidence = _parse_confidence(match.group(0), index)
        rest = tail[match.end() + 1:]
    if not rest.startswith("data="):
        raise SamResponseError(f"record {index} has a malformed mask")
    # Bounded delimiter scan: take exactly the two dimension delimiters and
    # treat everything after the second as the encoding marker plus opaque
    # payload, instead of splitting a comma-heavy payload into a list.
    height_text, sep, tail = rest[len("data="):].partition(",")
    if not sep:
        raise SamResponseError(f"record {index} has a malformed mask payload")
    height = _parse_uint(height_text, index, "mask height")
    width_text, sep, enc_payload = tail.partition(",")
    if not sep:
        raise SamResponseError(f"record {index} has a malformed mask payload")
    width = _parse_uint(width_text, index, "mask width")
    _check_dimensions(height, index, "mask height", cap)
    _check_dimensions(width, index, "mask width", cap)
    # Codex-confirmed grammar rule: mask raster dims are each smaller than
    # the corresponding source-image dimensions — equality is rejected.
    if not (height < expected[1] and width < expected[0]):
        raise SamResponseError(f"record {index} mask dimensions not smaller than source")
    encoding, payload = enc_payload[:1], enc_payload[1:]
    if encoding not in _ENCODINGS or not payload:
        raise SamResponseError(f"record {index} has an unsupported mask encoding")
    if len(payload) > max_payload or any(
        not _PAYLOAD_FIRST <= ord(char) <= _PAYLOAD_LAST or char == "," for char in payload
    ):
        raise SamResponseError(f"record {index} has a malformed mask payload")
    return SamWireMask(
        origin_x=origin_x,
        origin_y=origin_y,
        height=height,
        width=width,
        encoding=encoding,
        payload=payload,
        confidence=confidence,
    )


def _parse_record(text: str, index: int, expected: tuple[int, int], caps: SamLimits) -> SamRecord:
    match = _ID_RE.match(text)
    if match is None or not text[match.end():].startswith("<|box;"):
        raise SamResponseError(f"record {index} has a malformed object id")
    digits = match.group(0)
    # Unsigned ASCII IDs only, digit-capped before conversion so hostile
    # inputs cannot reach Python's integer conversion limit.
    if len(digits) > MAX_INT_DIGITS:
        raise SamResponseError(f"record {index} has a malformed object id")
    try:
        object_id = int(digits, 10)
    except (ValueError, OverflowError):
        raise SamResponseError(f"record {index} has a malformed object id") from None
    after_box_open = match.end() + len("<|box;")
    box_end = text.find("|>", after_box_open)
    if box_end < 0:
        raise SamResponseError(f"record {index} has a truncated box")
    box = _parse_box(text[after_box_open:box_end], index, expected, caps.max_dimension)
    mask_open = box_end + len("|>")
    if not text[mask_open:].startswith("<|mask;"):
        raise SamResponseError(f"record {index} has a malformed mask")
    mask_body = text[mask_open + len("<|mask;"):]
    if not text.endswith("|>") or not mask_body:
        raise SamResponseError(f"record {index} has a truncated mask")
    mask = _parse_mask(mask_body[: -len("|>")], index, expected, caps.max_dimension, caps.max_mask_chars)
    # Codex-confirmed grammar rule: confidence is absent from both tokens
    # or present on both with equal values — one-sided confidence is invalid.
    if (box.confidence is None) != (mask.confidence is None):
        raise SamResponseError(f"record {index} has one-sided confidence")
    if box.confidence is not None and box.confidence != mask.confidence:
        raise SamResponseError(f"record {index} box and mask confidence disagree")
    return SamRecord(object_id=object_id, box=box, mask=mask)


def _check_expected(value: object, what: str, cap: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= cap:
        raise SamResponseError(f"expected image {what} out of range")
    return value


def parse_response_text(
    text: Any,
    *,
    expected_width: int,
    expected_height: int,
    limits: SamLimits | None = None,
    max_chars: int = MAX_OUTPUT_CHARS,
) -> SamFrame:
    """Parse documented single-image SAM output text into a SamFrame."""
    caps = limits if limits is not None else SamLimits()
    width = _check_expected(expected_width, "width", caps.max_dimension)
    height = _check_expected(expected_height, "height", caps.max_dimension)
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 1:
        raise SamResponseError("input-size cap is invalid")
    if not isinstance(text, str):
        raise SamResponseError("response text must be a string")
    if len(text) > max_chars:
        raise SamResponseError("response text exceeds the input-size cap")
    # Only the exact empty string is a valid zero-match response.
    # Whitespace-only input is malformed, never silently normalized.
    if text == "":
        return SamFrame(frame_index=0, image_width=width, image_height=height, objects=())
    stripped = text.strip()
    if "\n" in stripped or "\r" in stripped:
        raise SamResponseError("multi-line output is not supported")
    marker = _FRAME_RE.match(stripped)
    if marker is None or not stripped.startswith("<"):
        raise SamResponseError("response has a malformed frame marker")
    if marker.group(1) != _SINGLE_IMAGE_FRAME:
        raise SamResponseError("multi-frame output is not supported")
    rest = stripped[marker.end():].strip()
    # Only an empty output is a zero-match: a frame marker with no records,
    # a trailing separator, or a leading separator are all malformed.
    if rest == "":
        raise SamResponseError("frame marker has no records")
    # Bounded scan: recognize record boundaries without materializing an
    # unbounded fragment list, and stop as soon as the configured object
    # limit is exceeded instead of parsing further records.
    parsed: list[SamRecord] = []
    start = 0
    index = 0
    while True:
        boundary = _BOUNDARY_RE.search(rest, start)
        end = boundary.start() if boundary is not None else len(rest)
        if index >= caps.max_objects:
            raise SamResponseError("response has more records than the limit allows")
        parsed.append(_parse_record(rest[start:end], index, (width, height), caps))
        if boundary is None:
            break
        start = boundary.end()
        index += 1
    return SamFrame(frame_index=0, image_width=width, image_height=height, objects=tuple(parsed))
