"""Offline T04 pixel preprocessing tests with generated synthetic images."""

from hashlib import sha256
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter
import pytest

from mydrak.intake.adapter import IntakeError
from mydrak.trace.store import TraceCase, TraceStep, TraceStore
from mydrak.vision.preprocessing import (
    ImagePreprocessingConfig,
    load_image_preprocessing_config,
    preprocess_local_image,
)


def _encoded(image: Image.Image, fmt: str = "PNG", *, exif=None) -> bytes:
    stream = BytesIO()
    image.save(stream, format=fmt, exif=exif or b"")
    return stream.getvalue()


def _write(tmp_path, name: str, content: bytes):
    path = tmp_path / name
    path.write_bytes(content)
    return path


def _config(**overrides) -> ImagePreprocessingConfig:
    values = dict(
        max_long_edge=2048, jpeg_quality=85, retake_enabled=False,
        leaf_hue_min=35, leaf_hue_max=150, leaf_saturation_min=40,
    )
    values.update(overrides)
    return ImagePreprocessingConfig(**values)


@pytest.mark.parametrize("fmt", ["PNG", "JPEG"])
def test_valid_synthetic_png_and_jpeg_are_normalized_to_jpeg(tmp_path, fmt):
    result = preprocess_local_image(
        _write(tmp_path, f"synthetic_input.{fmt.lower()}", _encoded(Image.new("RGB", (32, 24), "green"), fmt))
    )
    assert result.image_bytes.startswith(b"\xff\xd8")
    assert result.image_hash == sha256(result.image_bytes).hexdigest()
    assert (result.width, result.height) == (32, 24)
    assert result.retake_enabled is False
    assert result.measurements.leaf_coverage_method == "unverified_green_hue_pixel_proxy"


@pytest.mark.parametrize("content", [b"", b"not image bytes", b"\x89PNG\r\n\x1a\n" + b"\x00" * 30])
def test_zero_byte_non_image_and_truncated_payload_fail_closed(tmp_path, content):
    with pytest.raises(IntakeError):
        preprocess_local_image(_write(tmp_path, "synthetic_bad.bin", content))


def test_corrupt_pixels_after_valid_png_header_are_rejected(tmp_path):
    # Synthetically generated valid PNG header followed by invalid image data.
    import struct

    header = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
    header += struct.pack(">IIBBBBB", 12, 10, 8, 2, 0, 0, 0) + b"\x00\x00\x00\x00"
    with pytest.raises(IntakeError, match="decoded safely"):
        preprocess_local_image(_write(tmp_path, "synthetic_corrupt.png", header + b"bad payload"))


def test_synthetic_blur_brightness_and_leaf_proxy_are_measurements_only(tmp_path):
    checker = Image.new("L", (96, 96), 0)
    draw = ImageDraw.Draw(checker)
    for y in range(0, 96, 8):
        for x in range(0, 96, 8):
            if (x // 8 + y // 8) % 2:
                draw.rectangle((x, y, x + 7, y + 7), fill=255)
    sharp = checker.convert("RGB")
    blurred = sharp.filter(ImageFilter.GaussianBlur(radius=3))
    sharp_result = preprocess_local_image(_write(tmp_path, "synthetic_sharp.png", _encoded(sharp)))
    blur_result = preprocess_local_image(_write(tmp_path, "synthetic_blurred.png", _encoded(blurred)))
    assert sharp_result.measurements.laplacian_variance > blur_result.measurements.laplacian_variance

    dark = preprocess_local_image(_write(tmp_path, "synthetic_dark.png", _encoded(Image.new("RGB", (20, 20), (5, 5, 5)))))
    bright = preprocess_local_image(_write(tmp_path, "synthetic_bright.png", _encoded(Image.new("RGB", (20, 20), (245, 245, 245)))))
    assert dark.measurements.mean_brightness_0_255 < bright.measurements.mean_brightness_0_255
    assert 0 <= sharp_result.measurements.leaf_coverage_fraction <= 1
    assert not hasattr(sharp_result, "quality_score")


def test_exif_orientation_is_applied_before_dimension_reporting(tmp_path):
    image = Image.new("RGB", (40, 20), "orange")
    exif = Image.Exif()
    exif[274] = 6
    result = preprocess_local_image(
        _write(tmp_path, "synthetic_exif.jpg", _encoded(image, "JPEG", exif=exif.tobytes()))
    )
    assert (result.width, result.height) == (20, 40)


def test_long_edge_is_capped_and_output_is_jpeg(tmp_path):
    source = Image.new("RGB", (300, 150), "blue")
    result = preprocess_local_image(
        _write(tmp_path, "synthetic_oversized.png", _encoded(source)),
        config=_config(max_long_edge=100),
    )
    assert (result.width, result.height) == (100, 50)
    assert Image.open(BytesIO(result.image_bytes)).format == "JPEG"


def test_measurements_are_separate_from_decider_signals_in_trace(tmp_path):
    store = TraceStore(":memory:")
    case_id = "00000000000000000000000000000081"
    store.record_case(
        TraceCase(case_id, "manual_review", "en", "photo", "private"),
        [TraceStep("preprocess", "completed", 1.0)],
    )
    result = preprocess_local_image(
        _write(tmp_path, "synthetic_traced.png", _encoded(Image.new("RGB", (24, 24), "green"))),
        trace_store=store,
        trace_case_id=case_id,
    )
    row = store.get_image_measurements(case_id)
    assert row["laplacian_variance"] == result.measurements.laplacian_variance
    assert row["mean_brightness_0_255"] == result.measurements.mean_brightness_0_255
    assert row["leaf_coverage_method"] == "unverified_green_hue_pixel_proxy"
    assert store.get_signals(case_id) is None
    assert store.get_case(case_id)["quality_scores"] is None


def test_measurement_trace_requires_existing_case_and_is_single_write(tmp_path):
    store = TraceStore(":memory:")
    path = _write(tmp_path, "synthetic_trace.png", _encoded(Image.new("RGB", (12, 12), "white")))
    case_id = "00000000000000000000000000000082"
    with pytest.raises(IntakeError, match="could not be recorded"):
        preprocess_local_image(path, trace_store=store, trace_case_id=case_id)
    store.record_case(
        TraceCase(case_id, "manual_review", "en", "photo", "private"),
        [TraceStep("preprocess", "completed", 1.0)],
    )
    preprocess_local_image(path, trace_store=store, trace_case_id=case_id)
    with pytest.raises(IntakeError, match="could not be recorded"):
        preprocess_local_image(path, trace_store=store, trace_case_id=case_id)


def test_retake_config_must_remain_disabled_and_config_values_are_unverified(tmp_path):
    settings = load_image_preprocessing_config()
    assert settings.retake_enabled is False
    config_path = tmp_path / "synthetic_invalid_config.yaml"
    config_path.write_text(
        "max_long_edge: 2048\njpeg_quality: 85\nretake_enabled: true\n"
        "leaf_hue_min: 35\nleaf_hue_max: 150\nleaf_saturation_min: 40\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="retake routing is disabled"):
        load_image_preprocessing_config(config_path)
