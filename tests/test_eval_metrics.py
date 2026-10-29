"""Deterministic tests for the offline evaluation metrics."""

import pytest

from eval.metrics import (
    EvaluationError,
    accuracy_coverage_curve,
    compute_metrics,
    dev_tuning_curves,
    validate_record,
)


def record(**changes):
    row = {
        "case_id": "synthetic-01", "split": "dev", "strategy": "synthetic_strategy",
        "label": "crop_a_condition_a", "predicted": "crop_a_condition_a", "action": "answer",
        "escalated": False, "tokens_in": 10, "tokens_out": 5, "latency_ms": 100,
        "price_in_per_1m": 1.0, "price_out_per_1m": 2.0,
        "out_of_scope": False, "provenance": "synthetic_fixture", "score": 0.8,
    }
    row.update(changes)
    return row


def test_empty_input_is_empty_and_unknown_cost_is_not_zero():
    assert compute_metrics([]) == {}
    result = compute_metrics([record(tokens_in=None)])["synthetic_strategy"]
    assert result["cost_per_task_usd"] is None
    assert result["cost_unknown"] is True


def test_all_deferred_has_no_answer_accuracy_or_coverage():
    result = compute_metrics([record(predicted=None, action="ask")])["synthetic_strategy"]
    assert result["accuracy_answered"] is None
    assert result["coverage"] == 0
    assert result["accuracy_all"] == 0
    assert result["deferral_rate"] == 1


def test_all_correct_answered_metrics():
    result = compute_metrics([record()])["synthetic_strategy"]
    assert result["accuracy_answered"] == result["accuracy_all"] == result["coverage"] == 1


def test_tuning_rejects_any_test_record():
    with pytest.raises(EvaluationError, match="dev records only"):
        dev_tuning_curves([record(split="test")])


@pytest.mark.parametrize("latencies, expected", [
    ([5], (5, 5)), ([5, 15], (10, 15)), ([1, 2, 3, 4, 5], (3, 5)),
])
def test_median_and_nearest_rank_p90_edge_cases(latencies, expected):
    rows = [record(case_id=f"synthetic-{i}", latency_ms=value) for i, value in enumerate(latencies)]
    metrics = compute_metrics(rows)["synthetic_strategy"]
    assert (metrics["latency_ms_median"], metrics["latency_ms_p90"]) == expected


def test_out_of_scope_uncertainty_and_score_curve():
    rows = [record(out_of_scope=True), record(case_id="synthetic-02", predicted=None, action="refer", out_of_scope=True, score=0.2)]
    result = compute_metrics(rows)["synthetic_strategy"]
    assert result["out_of_scope_count"] == 2
    assert result["out_of_scope_uncertainty_handled"] == 0.5
    curve = accuracy_coverage_curve(rows)
    assert curve[0]["coverage"] == 1
    assert curve[-1]["coverage"] == 0.5


@pytest.mark.parametrize("changes", [
    {"unexpected": 1}, {"action": "answer", "predicted": None},
    {"latency_ms": float("nan")}, {"tokens_in": -1}, {"split": "validation"},
    {"score": 1.1}, {"strategy": ""}, {"split": []},
])
def test_malformed_record_rejected(changes):
    with pytest.raises(EvaluationError):
        validate_record(record(**changes))


def test_conflicting_case_labels_and_duplicate_rows_rejected():
    with pytest.raises(EvaluationError, match="duplicate"):
        compute_metrics([record(), record()])
    with pytest.raises(EvaluationError, match="agree"):
        compute_metrics([record(), record(strategy="other_strategy", label="different")])


def test_nonanswer_cannot_count_as_correct_even_if_it_carries_a_prediction():
    row = record(action="refer")
    result = compute_metrics([row])["synthetic_strategy"]
    assert result["accuracy_all"] == 0


def test_synthetic_fixture_records_load_without_touching_images():
    import csv
    import json
    from pathlib import Path

    fixture_dir = Path(__file__).parent / "fixtures" / "eval"
    with (fixture_dir / "synthetic_labels.csv").open(newline="", encoding="utf-8") as handle:
        labels = list(csv.DictReader(handle))
    predictions = json.loads((fixture_dir / "synthetic_predictions.json").read_text(encoding="utf-8"))
    assert len(labels) == 3 and len(predictions) == 9
    assert all(row["provenance"] == "synthetic_fixture" for row in labels)
