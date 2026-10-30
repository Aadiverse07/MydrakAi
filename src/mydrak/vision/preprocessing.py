"""Deterministic, offline image normalization and measurement-only T04 slice."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
import math
from pathlib import Path
import warnings

from PIL import Image, ImageOps, ImageStat

from mydrak.intake.adapter import IntakeError, MAX_DIMENSION
from mydrak.trace.store import TraceError, TraceStore
from mydrak.util.config import load_yaml
from mydrak.vision.source import read_local_image_data

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "image_preprocessing.yaml"
_CONFIG_KEYS = {
    "max_long_edge", "jpeg_quality", "retake_enabled", "leaf_hue_min",
    "leaf_hue_max", "leaf_saturation_min",
}
LEAF_COVERAGE_METHOD = "unverified_green_hue_pixel_proxy"


@dataclass(frozen=True)
class ImagePreprocessingConfig:
    max_long_edge: int
    jpeg_quality: int
    retake_enabled: bool
    leaf_hue_min: int
    leaf_hue_max: int
    leaf_saturation_min: int


@dataclass(frozen=True)
class ImageMeasurements:
    laplacian_variance: float
    mean_brightness_0_255: float
    leaf_coverage_fraction: float
    leaf_coverage_method: str = LEAF_COVERAGE_METHOD


@dataclass(frozen=True)
class PreprocessedImage:
    image_bytes: bytes = field(repr=False)
    image_hash: str
    width: int
    height: int
    measurements: ImageMeasurements
    retake_enabled: bool


def load_image_preprocessing_config(
    path: str | Path | None = None,
) -> ImagePreprocessingConfig:
    """Read strict, project-local preprocessing settings from YAML."""
    values = load_yaml(path or _CONFIG_PATH)
    if set(values) != _CONFIG_KEYS:
        raise ValueError("image preprocessing config has missing or unknown fields")
    max_long_edge = values["max_long_edge"]
    jpeg_quality = values["jpeg_quality"]
    hue_min = values["leaf_hue_min"]
    hue_max = values["leaf_hue_max"]
    saturation_min = values["leaf_saturation_min"]
    for field_name, value in (
        ("max_long_edge", max_long_edge), ("jpeg_quality", jpeg_quality),
        ("leaf_hue_min", hue_min), ("leaf_hue_max", hue_max),
        ("leaf_saturation_min", saturation_min),
    ):
        if type(value) is not int:
            raise ValueError(f"{field_name} must be an integer")
    if values["retake_enabled"] is not False:
        raise ValueError("retake routing is disabled for measurement-only T04")
    config = ImagePreprocessingConfig(
        max_long_edge, jpeg_quality, False, hue_min, hue_max, saturation_min
    )
    _validate_settings(config)
    return config


def _validate_settings(config: ImagePreprocessingConfig) -> None:
    integers = (
        config.max_long_edge, config.jpeg_quality, config.leaf_hue_min,
        config.leaf_hue_max, config.leaf_saturation_min,
    )
    if any(type(value) is not int for value in integers):
        raise IntakeError("image preprocessing settings are invalid")
    if config.retake_enabled is not False:
        raise IntakeError("retake routing is disabled for measurement-only T04")
    if not 1 <= config.max_long_edge <= MAX_DIMENSION:
        raise IntakeError("max_long_edge is outside the local image bound")
    if not 1 <= config.jpeg_quality <= 100:
        raise IntakeError("jpeg_quality is outside the local encoding range")
    if not 0 <= config.leaf_hue_min <= config.leaf_hue_max <= 255:
        raise IntakeError("green-pixel proxy hue settings are invalid")
    if not 0 <= config.leaf_saturation_min <= 255:
        raise IntakeError("green-pixel proxy saturation setting is invalid")


def _laplacian_variance(gray: Image.Image) -> float:
    """Compute variance of the signed four-neighbor grayscale Laplacian."""
    width, height = gray.size
    if width < 3 or height < 3:
        return 0.0
    pixels = gray.load()
    count = 0
    total = 0
    total_squares = 0
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            value = (
                pixels[x - 1, y] + pixels[x + 1, y]
                + pixels[x, y - 1] + pixels[x, y + 1]
                - 4 * pixels[x, y]
            )
            total += value
            total_squares += value * value
            count += 1
    variance = total_squares / count - (total / count) ** 2
    return max(0.0, float(variance))


def _green_pixel_fraction(hsv: Image.Image, config: ImagePreprocessingConfig) -> float:
    hues = hsv.getchannel("H").tobytes()
    saturations = hsv.getchannel("S").tobytes()
    count = sum(
        config.leaf_hue_min <= hue <= config.leaf_hue_max
        and saturation >= config.leaf_saturation_min
        for hue, saturation in zip(hues, saturations, strict=True)
    )
    pixels = hsv.width * hsv.height
    return count / pixels if pixels else 0.0


def _measure(image: Image.Image, config: ImagePreprocessingConfig) -> ImageMeasurements:
    gray = image.convert("L")
    brightness = float(ImageStat.Stat(gray).mean[0])
    hsv = image.convert("HSV")
    coverage = _green_pixel_fraction(hsv, config)
    return ImageMeasurements(
        laplacian_variance=_laplacian_variance(gray),
        mean_brightness_0_255=brightness,
        leaf_coverage_fraction=coverage,
    )


def preprocess_local_image(
    path: str | Path,
    *,
    config: ImagePreprocessingConfig | None = None,
    config_path: str | Path | None = None,
    trace_store: TraceStore | None = None,
    trace_case_id: str | None = None,
) -> PreprocessedImage:
    """Decode, orient, cap, measure, and JPEG-encode one local image.

    Measurements are observations only. This function does not calculate S3,
    make a retake decision, or alter any Decider signal. If a trace store is
    supplied, ``trace_case_id`` must identify an already-recorded case.
    """
    if config is not None and config_path is not None:
        raise IntakeError("provide either config or config_path")
    settings = config or load_image_preprocessing_config(config_path)
    if not isinstance(settings, ImagePreprocessingConfig):
        raise IntakeError("image preprocessing settings are invalid")
    _validate_settings(settings)
    if (trace_store is None) != (trace_case_id is None):
        raise IntakeError("trace store and existing case ID must be provided together")
    raw, descriptor = read_local_image_data(path)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as decoded:
                decoded.load()
                if decoded.format not in {"PNG", "JPEG"}:
                    raise IntakeError("decoded format is unsupported")
                if decoded.size != (descriptor.width, descriptor.height):
                    raise IntakeError("decoded dimensions do not match the image header")
                oriented = ImageOps.exif_transpose(decoded)
                rgba = oriented.convert("RGBA")
                rgb = Image.new("RGB", rgba.size, (255, 255, 255))
                rgb.paste(rgba, mask=rgba.getchannel("A"))
    except IntakeError:
        raise
    except (OSError, ValueError, SyntaxError, EOFError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise IntakeError("image pixels could not be decoded safely") from None

    width, height = rgb.size
    longest = max(width, height)
    if longest > settings.max_long_edge:
        ratio = settings.max_long_edge / longest
        size = (max(1, round(width * ratio)), max(1, round(height * ratio)))
        rgb = rgb.resize(size, Image.Resampling.LANCZOS)
    measurements = _measure(rgb, settings)
    if not all(math.isfinite(value) for value in (
        measurements.laplacian_variance,
        measurements.mean_brightness_0_255,
        measurements.leaf_coverage_fraction,
    )):
        raise IntakeError("image measurements are invalid")

    output = BytesIO()
    try:
        rgb.save(output, format="JPEG", quality=settings.jpeg_quality)
    except (OSError, ValueError):
        raise IntakeError("normalized image could not be encoded") from None
    encoded = output.getvalue()
    image_hash = sha256(encoded).hexdigest()
    if trace_store is not None and trace_case_id is not None:
        try:
            trace_store.record_image_measurements(
                trace_case_id,
                laplacian_variance=measurements.laplacian_variance,
                mean_brightness=measurements.mean_brightness_0_255,
                leaf_coverage_fraction=measurements.leaf_coverage_fraction,
                leaf_coverage_method=measurements.leaf_coverage_method,
            )
        except TraceError:
            raise IntakeError("image measurements could not be recorded") from None
    return PreprocessedImage(
        image_bytes=encoded,
        image_hash=image_hash,
        width=rgb.width,
        height=rgb.height,
        measurements=measurements,
        retake_enabled=settings.retake_enabled,
    )
