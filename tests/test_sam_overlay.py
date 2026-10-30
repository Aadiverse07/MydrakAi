"""T08 renderer tests using generated images and synthetic-grid-v1 masks."""

from hashlib import sha256
from io import BytesIO

from PIL import Image
import pytest

from mydrak.sam.output import parse_sam_output
from mydrak.sam.overlay import (
    SYNTHETIC_PROVENANCE,
    WATERMARK,
    decode_synthetic_grid,
    render_synthetic_fixture,
)
from mydrak.vision.preprocessing import ImageMeasurements, PreprocessedImage


def _preprocessed(width: int, height: int) -> PreprocessedImage:
    image = Image.new("RGB", (width, height), (210, 220, 200))
    stream = BytesIO()
    image.save(stream, format="JPEG", quality=90)
    data = stream.getvalue()
    return PreprocessedImage(
        image_bytes=data,
        image_hash=sha256(data).hexdigest(),
        width=width,
        height=height,
        measurements=ImageMeasurements(0.0, 0.0, 0.0),
        retake_enabled=False,
    )


def _segmentation(leaf_rows, lesion_rows, *, frame=(160, 120)):
    """Build parser output with explicit synthetic leaf/lesion fixture IDs."""
    objects = []
    for object_id, rows in (("leaf", leaf_rows), ("lesion", lesion_rows)):
        height = len(rows)
        width = len(rows[0])
        objects.append({
            "id": object_id,
            "box": [0, 0, frame[0], frame[1]],
            "mask": {
                "width": width,
                "height": height,
                "encoding": "synthetic-grid-v1",
                "data": "\n".join(rows),
            },
        })
    return parse_sam_output({
        "image": {"width": frame[0], "height": frame[1]},
        "objects": objects,
    })


def _render(segmentation, image=None, **kwargs):
    return render_synthetic_fixture(
        segmentation,
        image or _preprocessed(segmentation.image_width, segmentation.image_height),
        leaf_object_id="leaf",
        lesion_object_id="lesion",
        **kwargs,
    )


def test_synthetic_mask_decodes_to_boolean_grid():
    parsed = _segmentation(["10", "01"], ["00", "10"])
    decoded = decode_synthetic_grid(parsed.objects[0].mask)
    assert decoded.cells == ((True, False), (False, True))
    assert decoded.foreground == 2


def test_known_synthetic_fixture_gives_exact_severity_and_overlay():
    # 4x4 fixture: 10 leaf cells; 3 overlapping lesion cells; 1 outside leaf.
    leaf = ["1111", "1111", "1100", "0000"]
    lesion = ["1100", "1000", "0000", "0001"]
    result = _render(_segmentation(leaf, lesion))
    assert result.severity_pct == 30.0
    assert result.severity_band == "moderate"
    assert result.reason_code == "completed"
    assert result.overlay_bytes is not None
    assert result.overlay_mime_type == "image/png"
    assert result.provenance == SYNTHETIC_PROVENANCE


def test_lesion_cells_outside_leaf_do_not_increase_severity():
    result = _render(_segmentation(["10", "00"], ["01", "10"]))
    assert result.severity_pct == 0.0
    assert result.severity_band == "low"


@pytest.mark.parametrize(
    ("leaf", "lesion", "reason"),
    [
        (["11", "11"], ["00", "00"], "empty_lesion_mask"),
        (["00", "00"], ["10", "00"], "empty_leaf_mask"),
    ],
)
def test_empty_masks_fail_without_severity_or_overlay(leaf, lesion, reason):
    result = _render(_segmentation(leaf, lesion))
    assert result.reason_code == reason
    assert result.severity_pct is None
    assert result.severity_band is None
    assert result.overlay_bytes is None
    assert result.overlay_mime_type is None


def test_mask_size_mismatch_fails_without_severity_or_overlay():
    result = _render(_segmentation(["111", "111"], ["1", "0"]))
    assert result.reason_code == "mask_size_mismatch"
    assert result.severity_pct is result.overlay_bytes is None


@pytest.mark.parametrize(
    ("affected", "expected"),
    [(10, "low"), (11, "moderate"), (30, "moderate"), (31, "high")],
)
def test_configured_severity_band_boundaries(affected, expected):
    leaf = ["1" * 10 for _ in range(10)]
    cells = ["1" if index < affected else "0" for index in range(100)]
    lesion = ["".join(cells[offset:offset + 10]) for offset in range(0, 100, 10)]
    result = _render(_segmentation(leaf, lesion, frame=(160, 160)))
    assert result.severity_pct == affected
    assert result.severity_band == expected


def test_overlay_matches_preprocessed_image_and_has_visible_synthetic_watermark():
    image = _preprocessed(240, 160)
    result = _render(
        _segmentation(["1111"] * 4, ["1000"] * 4, frame=(240, 160)), image
    )
    with Image.open(BytesIO(result.overlay_bytes)) as rendered:
        assert rendered.size == (image.width, image.height)
        assert rendered.format == "PNG"
        pixels = rendered.convert("RGB").tobytes()
        colors = {tuple(pixels[index:index + 3]) for index in range(0, len(pixels), 3)}
        assert (255, 235, 0) in colors  # lesion boundary outline
        assert any(red > green + 25 and green < 190 for red, green, _ in colors)
        # A dark full-width backing strip is drawn under the visible label.
        assert rendered.getpixel((rendered.width - 2, rendered.height - 2))[0] < 170
    assert result.watermark_text == WATERMARK == "SYNTHETIC FIXTURE"


def test_unsupported_mask_encoding_returns_reason_without_partial_result():
    fixture = {
        "image": {"width": 160, "height": 120},
        "objects": [
            {"id": "leaf", "box": [0, 0, 160, 120],
             "mask": {"width": 2, "height": 2, "encoding": "opaque-base85", "data": "abc"}},
            {"id": "lesion", "box": [0, 0, 160, 120],
             "mask": {"width": 2, "height": 2, "encoding": "synthetic-grid-v1", "data": "10\n00"}},
        ],
    }
    result = _render(parse_sam_output(fixture))
    assert result.reason_code == "mask_decode_failed"
    assert result.severity_pct is result.overlay_bytes is None


def test_failure_result_never_contains_overlay_or_severity():
    segmentation = parse_sam_output({
        "image": {"width": 160, "height": 120},
        "objects": [{
            "id": "lesion", "box": [0, 0, 160, 120],
            "mask": {"width": 1, "height": 1,
                     "encoding": "synthetic-grid-v1", "data": "1"},
        }],
    })
    result = _render(segmentation)
    assert result.reason_code == "leaf_mask_missing"
    assert result.severity_pct is None
    assert result.overlay_bytes is None
