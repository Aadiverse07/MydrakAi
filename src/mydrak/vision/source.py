"""Offline local image-header reader (Phase 2, Task 2).

Reads a real file from local disk and validates ONLY its header: magic,
segment structure, and dimensions. This proves the file starts like a
PNG/JPEG of the stated size. It does NOT prove the trailing payload is
intact, the pixels decode, or the full file is valid — there is
deliberately no decoder here (see Option A limits). A header-valid but
payload-garbage file passes, by design.

PNG: 8-byte signature, first chunk must be IHDR with length exactly 13;
width/height big-endian. The IHDR CRC is NOT validated.
JPEG: SOI-anchored marker walk. Standalone RSTn/TEM carry no length; every
other segment needs a 2-byte length covering enough remaining bytes.
The first SOF (C0-C3, C5-C7, C9-CB, CD-CF only) must satisfy
length == 8 + 3 * components, precision 8 or 12, nonzero dimensions.
SOS/EOI before any SOF, a nested SOI, exhausted bytes, short reads, and
bare SOF-like bytes without a preceding SOI are all malformed.
The file is opened once and at most MAX_IMAGE_BYTES + 1 bytes are read, so
the size cap holds even if the file grows between inspection and read.

Reuses intake caps and errors; never touches network, models, or media
pipelines. No new dependency (stdlib struct/os only).
"""

import os
import struct

from mydrak.intake.adapter import (
    MAX_DIMENSION,
    MAX_IMAGE_BYTES,
    IntakeError,
    IntakeImage,
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SOI = b"\xff\xd8"

_SOF_MARKERS = frozenset(
    (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
     0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF)
)
_STANDALONE_MARKERS = frozenset(range(0xD0, 0xD8)) | {0x01}
_SOS_MARKER = 0xDA
_EOI_MARKER = 0xD9
_SOI_MARKER = 0xD8


def _check_dimensions(width: int, height: int) -> tuple[int, int]:
    if not 1 <= width <= MAX_DIMENSION:
        raise IntakeError("image width out of range")
    if not 1 <= height <= MAX_DIMENSION:
        raise IntakeError("image height out of range")
    return width, height


def _png_dimensions(data: bytes) -> tuple[str, int, int]:
    if len(data) < 29:
        raise IntakeError("truncated PNG header")
    chunk_length = struct.unpack(">I", data[8:12])[0]
    if data[12:16] != b"IHDR" or chunk_length != 13:
        raise IntakeError("PNG first chunk must be IHDR with length 13")
    width, height = struct.unpack(">II", data[16:24])
    width, height = _check_dimensions(width, height)
    return "png", width, height


def _jpeg_dimensions(data: bytes) -> tuple[str, int, int]:
    pos = 2
    end = len(data)
    while True:
        while pos < end and data[pos] == 0xFF:
            pos += 1
        if pos >= end:
            raise IntakeError("truncated JPEG header: marker expected")
        marker = data[pos]
        pos += 1
        if marker == 0x00:
            raise IntakeError("malformed JPEG segment boundary")
        if marker in (_SOS_MARKER, _EOI_MARKER):
            raise IntakeError("JPEG ended before any Start Of Frame segment")
        if marker == _SOI_MARKER:
            raise IntakeError("JPEG contains a nested Start Of Image marker")
        if marker in _STANDALONE_MARKERS:
            continue
        if pos + 2 > end:
            raise IntakeError("truncated JPEG segment length")
        seg_length = struct.unpack(">H", data[pos:pos + 2])[0]
        if seg_length < 2 or pos + seg_length > end:
            raise IntakeError("malformed or truncated JPEG segment")
        if marker in _SOF_MARKERS:
            return _parse_sof(data, pos, seg_length)
        pos += seg_length


def _parse_sof(data: bytes, pos: int, seg_length: int) -> tuple[str, int, int]:
    if seg_length < 8:
        raise IntakeError("truncated JPEG Start Of Frame segment")
    precision = data[pos + 2]
    height = struct.unpack(">H", data[pos + 3:pos + 5])[0]
    width = struct.unpack(">H", data[pos + 5:pos + 7])[0]
    components = data[pos + 7]
    if seg_length != 8 + 3 * components:
        raise IntakeError("JPEG SOF length does not match its component count")
    if precision not in (8, 12):
        raise IntakeError("JPEG SOF precision out of range")
    if not 1 <= components <= 4:
        raise IntakeError("JPEG SOF component count out of range")
    width, height = _check_dimensions(width, height)
    return "jpeg", width, height


def read_local_image(path: str | os.PathLike[str]) -> IntakeImage:
    """Read a local PNG/JPEG header into an IntakeImage descriptor."""
    if not isinstance(path, (str, os.PathLike)):
        raise IntakeError("image path must be a string or path-like object")
    try:
        is_file = os.path.isfile(path)
        oversized = is_file and os.path.getsize(path) > MAX_IMAGE_BYTES
    except OSError:
        raise IntakeError("image file could not be inspected") from None
    if not is_file:
        raise IntakeError("image path is not a readable file")
    if oversized:
        raise IntakeError("image file exceeds the size cap")
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_IMAGE_BYTES + 1)
    except OSError:
        raise IntakeError("image file could not be read") from None
    if len(data) > MAX_IMAGE_BYTES:
        raise IntakeError("image file exceeds the size cap")
    if data.startswith(PNG_SIGNATURE):
        fmt, width, height = _png_dimensions(data)
    elif data.startswith(JPEG_SOI):
        fmt, width, height = _jpeg_dimensions(data)
    else:
        raise IntakeError("unsupported image format (expected PNG or JPEG bytes)")
    return IntakeImage(format=fmt, width=width, height=height, size_bytes=len(data))
