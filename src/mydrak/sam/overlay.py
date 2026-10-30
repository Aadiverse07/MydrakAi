"""Offline T08 decoding, severity, and overlay for synthetic grid fixtures.

This module accepts only the JSON fixture parser's ``synthetic-grid-v1``
masks. It does not decode response-text/Base85 masks or claim SAM wire
compatibility. Object IDs for leaf and lesion roles are selected explicitly
by the caller; IDs are not interpreted as semantic labels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import math
from pathlib import Path
import warnings

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from mydrak.sam.adapter import grid_mask_to_binary
from mydrak.sam.output import SamLimits, SamObject, SamSegmentation
from mydrak.sam.scores import BinaryMask, SegmentationEvalError
from mydrak.sam.severity import band, mask_severity_pct
from mydrak.util.config import load_yaml
from mydrak.vision.preprocessing import PreprocessedImage

_SEVERITY_CONFIG = Path(__file__).resolve().parents[3] / "config" / "severity.yaml"
SYNTHETIC_PROVENANCE = "synthetic-fixture"
WATERMARK = "SYNTHETIC FIXTURE"


@dataclass(frozen=True)
class BooleanGrid:
    """Boolean cells produced only after strict synthetic-grid validation."""

    width: int
    height: int
    cells: tuple[tuple[bool, ...], ...]

    @property
    def foreground(self) -> int:
        return sum(sum(row) for row in self.cells)


@dataclass(frozen=True)
class SeverityBands:
    low_max: float
    moderate_max: float


@dataclass(frozen=True)
class T08Result:
    severity_pct: float | None
    severity_band: str | None
    overlay_bytes: bytes | None = field(repr=False)
    overlay_mime_type: str | None
    reason_code: str
    provenance: str
    watermark_text: str | None


def decode_synthetic_grid(mask: object, limits: SamLimits | None = None) -> BooleanGrid:
    """Decode the project-local 0/1 row grammar into a BooleanGrid.

    ``grid_mask_to_binary`` owns the strict encoding, dimensions, row count,
    and character validation. Other encodings, including opaque wire masks,
    are rejected rather than guessed.
    """
    if limits is not None and (
        not isinstance(limits, SamLimits)
        or type(limits.max_dimension) is not int
        or limits.max_dimension < 1
        or type(limits.max_mask_chars) is not int
        or limits.max_mask_chars < 1
    ):
        raise SegmentationEvalError("grid mask limits are invalid")
    binary = grid_mask_to_binary(mask, limits)
    return BooleanGrid(
        width=binary.width,
        height=binary.height,
        cells=tuple(tuple(cell == "1" for cell in row) for row in binary.rows),
    )


def load_severity_bands(path: str | Path | None = None) -> SeverityBands:
    """Load configurable heuristic bands; these are not agronomic thresholds."""
    config = load_yaml(path or _SEVERITY_CONFIG)
    if set(config) != {"bands", "recovery_margin_pp"}:
        raise ValueError("severity config has missing or unknown fields")
    values = config["bands"]
    if not isinstance(values, dict) or set(values) != {"low_max", "moderate_max"}:
        raise ValueError("severity bands must contain low_max and moderate_max")
    low_max, moderate_max = values["low_max"], values["moderate_max"]
    if any(type(value) not in {int, float} for value in (low_max, moderate_max)):
        raise ValueError("severity band values must be finite numbers")
    try:
        low_max, moderate_max = float(low_max), float(moderate_max)
    except OverflowError:
        raise ValueError("severity band values must be finite numbers") from None
    if not all(math.isfinite(value) for value in (low_max, moderate_max)):
        raise ValueError("severity band values must be finite numbers")
    if not 0 <= low_max < moderate_max <= 100:
        raise ValueError("severity bands must satisfy 0 <= low_max < moderate_max <= 100")
    margin = config["recovery_margin_pp"]
    if type(margin) not in {int, float}:
        raise ValueError("recovery margin must be a non-negative finite number")
    try:
        margin = float(margin)
    except OverflowError:
        raise ValueError("recovery margin must be a non-negative finite number") from None
    if not math.isfinite(margin) or margin < 0:
        raise ValueError("recovery margin must be a non-negative finite number")
    return SeverityBands(low_max, moderate_max)


def _failure(reason: str, provenance: str = SYNTHETIC_PROVENANCE) -> T08Result:
    return T08Result(
        severity_pct=None,
        severity_band=None,
        overlay_bytes=None,
        overlay_mime_type=None,
        reason_code=reason,
        provenance=provenance,
        watermark_text=None,
    )


def _choose_mask(segmentation: SamSegmentation, object_id: str, role: str):
    if not isinstance(object_id, str) or not object_id:
        return None, f"{role}_mask_missing"
    matches = [item for item in segmentation.objects if item.id == object_id]
    if len(matches) != 1:
        return None, f"{role}_mask_missing" if not matches else f"{role}_mask_ambiguous"
    return matches[0].mask, ""


def _as_binary_mask(grid: BooleanGrid) -> BinaryMask:
    rows = ["".join("1" if cell else "0" for cell in row) for row in grid.cells]
    return BinaryMask(grid.width, grid.height, rows)


def _grid_image(grid: BooleanGrid, size: tuple[int, int]) -> Image.Image:
    mask = Image.new("L", (grid.width, grid.height))
    mask.putdata([255 if cell else 0 for row in grid.cells for cell in row])
    return mask.resize(size, Image.Resampling.NEAREST)


def _watermark(canvas: Image.Image) -> None:
    """Draw a high-contrast bottom banner and readable fixture label."""
    font = ImageFont.load_default()
    left, top, right, bottom = font.getbbox(WATERMARK)
    text_width, text_height = right - left, bottom - top
    available_width = max(1, canvas.width - 8)
    available_height = max(1, canvas.height - 4)
    scale = min(
        3.0,
        available_width / max(1, text_width),
        available_height / max(1, text_height),
    )
    rendered = Image.new("RGBA", (text_width, text_height), (0, 0, 0, 0))
    ImageDraw.Draw(rendered).text((-left, -top), WATERMARK, font=font, fill=(255, 255, 255, 255))
    rendered_width = max(1, round(text_width * scale))
    rendered_height = max(1, round(text_height * scale))
    if (rendered_width, rendered_height) != rendered.size:
        rendered = rendered.resize((rendered_width, rendered_height), Image.Resampling.LANCZOS)
    x = max(0, (canvas.width - rendered.width) // 2)
    y = max(0, canvas.height - rendered.height - 4)
    banner = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(banner)
    draw.rectangle((0, y, canvas.width, canvas.height), fill=(0, 0, 0, 190))
    banner.alpha_composite(rendered, (x, min(y + 2, canvas.height - rendered.height)))
    canvas.alpha_composite(banner)


def _render_overlay(image: PreprocessedImage, lesion: BooleanGrid) -> bytes:
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(BytesIO(image.image_bytes)) as decoded:
            decoded.load()
            if decoded.size != (image.width, image.height):
                raise ValueError("preprocessed image dimensions do not match")
            canvas = decoded.convert("RGBA")
    lesion_pixels = _grid_image(lesion, canvas.size)
    fill = Image.new("RGBA", canvas.size, (255, 30, 30, 105))
    fill.putalpha(lesion_pixels.point(lambda value: 105 if value else 0))
    canvas.alpha_composite(fill)

    outer = lesion_pixels.filter(ImageFilter.MaxFilter(3))
    inner = lesion_pixels.filter(ImageFilter.MinFilter(3))
    outline = ImageChops.difference(outer, inner)
    edge = Image.new("RGBA", canvas.size, (255, 235, 0, 255))
    edge.putalpha(outline)
    canvas.alpha_composite(edge)
    _watermark(canvas)

    output = BytesIO()
    canvas.convert("RGB").save(output, format="PNG")
    return output.getvalue()


def render_synthetic_fixture(
    segmentation: SamSegmentation,
    preprocessed_image: PreprocessedImage,
    *,
    leaf_object_id: str,
    lesion_object_id: str,
    provenance: str = SYNTHETIC_PROVENANCE,
    severity_config_path: str | Path | None = None,
    limits: SamLimits | None = None,
) -> T08Result:
    """Decode selected synthetic fixture masks, compute severity, and render.

    Failure results carry a stable reason code and no numeric severity or
    overlay. This entry point accepts only synthetic-fixture provenance; it
    cannot be used to imply live SAM or provider compatibility.
    """
    if provenance != SYNTHETIC_PROVENANCE:
        return _failure("unsupported_provenance", provenance="unverified")
    if not isinstance(segmentation, SamSegmentation):
        return _failure("invalid_segmentation")
    if not isinstance(preprocessed_image, PreprocessedImage):
        return _failure("invalid_preprocessed_image")
    if (
        type(segmentation.image_width) is not int
        or type(segmentation.image_height) is not int
        or type(preprocessed_image.width) is not int
        or type(preprocessed_image.height) is not int
        or preprocessed_image.width < 1
        or preprocessed_image.height < 1
        or not isinstance(preprocessed_image.image_bytes, bytes)
        or not isinstance(segmentation.objects, tuple)
        or not all(isinstance(item, SamObject) for item in segmentation.objects)
    ):
        return _failure("invalid_preprocessed_image")
    if limits is not None and (
        not isinstance(limits, SamLimits)
        or type(limits.max_dimension) is not int
        or limits.max_dimension < 1
        or type(limits.max_mask_chars) is not int
        or limits.max_mask_chars < 1
    ):
        return _failure("invalid_limits")
    if leaf_object_id == lesion_object_id:
        return _failure("object_role_conflict")
    if (segmentation.image_width, segmentation.image_height) != (
        preprocessed_image.width, preprocessed_image.height
    ):
        return _failure("image_dimension_mismatch")

    leaf_mask, reason = _choose_mask(segmentation, leaf_object_id, "leaf")
    if reason:
        return _failure(reason)
    lesion_mask, reason = _choose_mask(segmentation, lesion_object_id, "lesion")
    if reason:
        return _failure(reason)
    try:
        leaf = decode_synthetic_grid(leaf_mask, limits)
        lesion = decode_synthetic_grid(lesion_mask, limits)
    except (SegmentationEvalError, TypeError, ValueError, OverflowError):
        return _failure("mask_decode_failed")
    if (leaf.width, leaf.height) != (lesion.width, lesion.height):
        return _failure("mask_size_mismatch")
    if leaf.foreground == 0:
        return _failure("empty_leaf_mask")
    if lesion.foreground == 0:
        return _failure("empty_lesion_mask")

    try:
        percentage = mask_severity_pct(_as_binary_mask(leaf), _as_binary_mask(lesion))
    except (TypeError, ValueError, OverflowError):
        return _failure("severity_calculation_failed")
    if percentage is None:
        return _failure("empty_leaf_mask")
    try:
        bands = load_severity_bands(severity_config_path)
    except (OSError, ValueError, TypeError, OverflowError):
        return _failure("severity_config_invalid")
    try:
        severity_band = band(percentage, bands.low_max, bands.moderate_max)
        overlay = _render_overlay(preprocessed_image, lesion)
    except (OSError, ValueError, TypeError, OverflowError, EOFError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        return _failure("render_failed")
    return T08Result(
        severity_pct=percentage,
        severity_band=severity_band,
        overlay_bytes=overlay,
        overlay_mime_type="image/png",
        reason_code="completed",
        provenance=SYNTHETIC_PROVENANCE,
        watermark_text=WATERMARK,
    )
