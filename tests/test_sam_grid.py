"""Grid-adapter tests. All masks are hand-built synthetic grids; the
`synthetic-grid-v1` contract is a local test grammar, not SAM wire output."""

import pytest

from mydrak.sam.adapter import GRID_ENCODING, grid_mask_to_binary
from mydrak.sam.output import SamLimits, SamMask
from mydrak.sam.scores import BinaryMask, SegmentationEvalError, dice, iou
from mydrak.sam.severity import mask_severity_pct


def grid(width, height, rows, encoding=GRID_ENCODING):
    return SamMask(width=width, height=height, encoding=encoding, data="\n".join(rows))


def test_valid_rectangular_grid():
    out = grid_mask_to_binary(grid(3, 2, ["101", "010"]))
    assert out == BinaryMask(3, 2, ["101", "010"])
    assert out.foreground == 3


def test_valid_all_zero_grid():
    assert grid_mask_to_binary(grid(2, 2, ["00", "00"])).foreground == 0


def test_valid_all_one_grid():
    assert grid_mask_to_binary(grid(2, 3, ["11", "11", "11"])).foreground == 6


@pytest.mark.parametrize("mask", [
    grid(4, 2, ["101", "010"]),
    grid(2, 3, ["11", "01"]),
    grid(2, 2, ["11", "01", "00"]),
    grid(2, 2, ["111", "00"]),
    grid(2, 2, ["", "00"]),
    grid(2, 2, ["1X", "00"]),
    grid(2, 2, ["1 ", "00"]),
    grid(2, 2, ["11"]),
])
def test_malformed_grids_rejected(mask):
    with pytest.raises(SegmentationEvalError):
        grid_mask_to_binary(mask)


@pytest.mark.parametrize("encoding", ["base64", "rle", "png", "SYNTHETIC-GRID-V1", ""])
def test_unsupported_encodings_rejected(encoding):
    with pytest.raises(SegmentationEvalError, match="unsupported mask encoding"):
        grid_mask_to_binary(SamMask(width=2, height=1, encoding=encoding, data="10"))


@pytest.mark.parametrize("width,height", [(0, 2), (2, 0), (-3, 2), (True, 2), ("2", 2)])
def test_zero_and_nonpositive_dimensions_rejected(width, height):
    with pytest.raises(SegmentationEvalError):
        grid_mask_to_binary(SamMask(width=width, height=height, encoding=GRID_ENCODING, data="00"))


@pytest.mark.parametrize("width,height,data", [(4, 1, "0000"), (1, 4, "0\n0\n0\n0")])
def test_dimensions_above_configured_cap_rejected(width, height, data):
    limits = SamLimits(max_dimension=3)
    with pytest.raises(SegmentationEvalError, match="dimension cap"):
        grid_mask_to_binary(SamMask(width, height, GRID_ENCODING, data), limits)


@pytest.mark.parametrize("data", [b"10", 10, None])
def test_non_string_data_rejected_with_controlled_error(data):
    mask = SamMask(width=2, height=1, encoding=GRID_ENCODING, data=data)
    with pytest.raises(SegmentationEvalError, match="data must be a string"):
        grid_mask_to_binary(mask)


def test_oversized_input_rejected_safely():
    with pytest.raises(SegmentationEvalError, match="size cap"):
        grid_mask_to_binary(
            SamMask(width=2, height=2, encoding=GRID_ENCODING, data="0" * (SamLimits().max_mask_chars + 1)),
            SamLimits(),
        )


def test_trailing_newline_rejected():
    with pytest.raises(SegmentationEvalError, match="row count"):
        grid_mask_to_binary(SamMask(width=2, height=1, encoding=GRID_ENCODING, data="10\n"))


def test_row_column_orientation_preserved():
    out = grid_mask_to_binary(grid(3, 2, ["100", "000"]))
    assert out.rows[0] == "100" and out.rows[1] == "000"
    assert iou(out, BinaryMask(3, 2, ["100", "000"])) == 1.0
    assert iou(out, BinaryMask(3, 2, ["001", "000"])) == 0.0


def test_conversion_output_accepted_by_scoring():
    converted = grid_mask_to_binary(grid(2, 2, ["11", "10"]))
    truth = BinaryMask(2, 2, ["11", "01"])
    assert iou(converted, truth) == pytest.approx(0.5)
    assert dice(converted, truth) == pytest.approx(2 / 3)


def test_multiple_objects_not_merged():
    first = grid_mask_to_binary(grid(2, 1, ["10"], ))
    second = grid_mask_to_binary(grid(2, 1, ["01"]))
    assert first != second
    assert (first.foreground, second.foreground) == (1, 1)


def test_non_mask_input_rejected():
    with pytest.raises(SegmentationEvalError):
        grid_mask_to_binary({"width": 2, "height": 1, "encoding": GRID_ENCODING, "data": "10"})


def test_errors_carry_no_values():
    with pytest.raises(SegmentationEvalError, match="unsupported mask encoding"):
        grid_mask_to_binary(SamMask(width=2, height=1, encoding="secret-encoding-value", data="10"))
    try:
        grid_mask_to_binary(SamMask(width=2, height=1, encoding="secret-encoding-value", data="10"))
    except SegmentationEvalError as exc:
        assert "secret-encoding-value" not in str(exc)


def test_grid_conversion_feeds_mask_severity():
    # Synthetic `synthetic-grid-v1` masks flow through the existing
    # converter into the project-local severity helper: 2 of 4 leaf
    # cells overlap, so the result is exactly 50.0 (unrounded).
    leaf = grid_mask_to_binary(grid(2, 2, ["11", "11"]))
    lesion = grid_mask_to_binary(grid(2, 2, ["10", "10"]))
    assert mask_severity_pct(leaf, lesion) == 50.0
