"""Segmentation metric tests. Every mask is a hand-built synthetic grid;
nothing here is a real SAM mask, a real photo, or a performance claim."""

import pytest

from mydrak.sam.scores import (
    METRICS_VERSION,
    BinaryMask,
    SegmentationEvalError,
    dice,
    evaluate_case,
    intersection,
    iou,
    mark_invalid,
    summarize,
)


def mask(rows):
    return BinaryMask(len(rows[0]), len(rows), list(rows))


def test_perfect_prediction():
    pred = mask(["11", "10"])
    assert iou(pred, pred) == 1.0
    assert dice(pred, pred) == 1.0
    assert intersection(pred, pred) == 3


def test_partial_overlap_matches_hand_computation():
    pred = mask(["11", "10"])
    truth = mask(["11", "01"])
    assert intersection(pred, truth) == 2
    assert iou(pred, truth) == pytest.approx(0.5)
    assert dice(pred, truth) == pytest.approx(2 / 3)


def test_no_overlap_scores_zero():
    assert iou(mask(["10", "00"]), mask(["01", "00"])) == 0.0
    assert dice(mask(["10", "00"]), mask(["01", "00"])) == 0.0


def test_both_empty_scores_one():
    empty = mask(["00", "00"])
    assert iou(empty, empty) == 1.0
    assert dice(empty, empty) == 1.0


@pytest.mark.parametrize("pred_rows,truth_rows", [
    (["00", "00"], ["11", "11"]),
    (["11", "11"], ["00", "00"]),
])
def test_one_sided_empty_scores_zero(pred_rows, truth_rows):
    assert iou(mask(pred_rows), mask(truth_rows)) == 0.0
    assert dice(mask(pred_rows), mask(truth_rows)) == 0.0


@pytest.mark.parametrize("kwargs", [
    {"width": 0, "height": 2, "rows": ["00", "00"]},
    {"width": 2, "height": 2, "rows": ["00"]},
    {"width": 2, "height": 2, "rows": ["00", "0"]},
    {"width": 2, "height": 2, "rows": ["02", "00"]},
    {"width": 2, "height": 2, "rows": ["0X", "00"]},
    {"width": True, "height": 2, "rows": ["00", "00"]},
    {"width": 2.0, "height": 2, "rows": ["00", "00"]},
])
def test_invalid_masks_rejected(kwargs):
    with pytest.raises(SegmentationEvalError):
        BinaryMask(**kwargs)


def test_shape_mismatch_rejected_not_resized():
    with pytest.raises(SegmentationEvalError):
        iou(mask(["11", "11"]), mask(["111", "111", "111"]))
    with pytest.raises(SegmentationEvalError):
        evaluate_case("mismatch", mask(["1"]), mask(["1", "1"]))


def test_missing_sides_skipped():
    assert evaluate_case("no-pred", None, mask(["1"]))["status"] == "skipped"
    assert evaluate_case("no-truth", mask(["1"]), None)["status"] == "skipped"
    assert evaluate_case("neither", None, None)["reason"] == "missing prediction"


def test_bad_case_ids_rejected():
    with pytest.raises(SegmentationEvalError):
        evaluate_case("", mask(["1"]), mask(["1"]))
    with pytest.raises(SegmentationEvalError):
        evaluate_case("/abs/path", mask(["1"]), mask(["1"]))
    with pytest.raises(SegmentationEvalError):
        mark_invalid("x" * 129, "too long")


def test_evaluate_case_record_shape():
    record = evaluate_case("synth-a", mask(["11", "10"]), mask(["11", "01"]))
    assert record == {"id": "synth-a", "status": "valid", "reason": None,
                      "iou": pytest.approx(0.5), "dice": pytest.approx(2 / 3)}


def test_multiple_cases_aggregate_over_valid_only():
    cases = [
        evaluate_case("perfect", mask(["1"]), mask(["1"])),
        evaluate_case("half", mask(["11", "10"]), mask(["11", "01"])),
        evaluate_case("missing", None, mask(["1"])),
        mark_invalid("broken", "synthetic shape mismatch"),
    ]
    report = summarize(cases)
    assert report["version"] == METRICS_VERSION
    assert report["aggregates"]["mean_iou"] == pytest.approx(0.75)
    assert report["aggregates"]["mean_dice"] == pytest.approx(5 / 6)
    assert report["counts"] == {"valid": 2, "invalid": 1, "skipped": 1}


def test_no_valid_cases_gives_null_aggregates():
    report = summarize([evaluate_case("s", None, mask(["1"])), mark_invalid("i", "synthetic")])
    assert report["aggregates"] == {"mean_iou": None, "mean_dice": None}
    assert report["counts"] == {"valid": 0, "invalid": 1, "skipped": 1}


def test_deterministic_results():
    first = summarize([evaluate_case("a", mask(["11", "10"]), mask(["11", "01"]))])
    second = summarize([evaluate_case("a", mask(["11", "10"]), mask(["11", "01"]))])
    assert first == second
