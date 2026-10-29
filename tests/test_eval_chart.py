"""SVG and offline CLI regression tests for the evaluation report."""

import json
from pathlib import Path
from xml.etree import ElementTree

from eval.chart import accuracy_coverage_svg, cost_accuracy_svg
from eval.run_eval import main
from eval.metrics import accuracy_coverage_curve, compute_metrics


def test_charts_mark_synthetic_and_unknown_cost():
    row = {
        "case_id": "synthetic-01", "split": "test", "strategy": "<unsafe>",
        "label": "x", "predicted": None, "action": "ask", "escalated": False,
        "tokens_in": None, "tokens_out": None, "latency_ms": 1,
        "price_in_per_1m": None, "price_out_per_1m": None,
        "out_of_scope": True, "provenance": "synthetic_fixture", "score": 0.5,
    }
    metrics = compute_metrics([row])
    cost_chart = cost_accuracy_svg(metrics, [row])
    coverage_chart = accuracy_coverage_svg({"<unsafe>": accuracy_coverage_curve([row])}, [row])
    ElementTree.fromstring(cost_chart)
    ElementTree.fromstring(coverage_chart)
    assert "SYNTHETIC FIXTURE" in cost_chart and "cost unknown" in cost_chart
    assert "&lt;unsafe&gt;" in cost_chart and "&lt;unsafe&gt;" in coverage_chart
    assert "SYNTHETIC FIXTURE" in coverage_chart


def test_empty_charts_are_valid_svg():
    empty_cost = cost_accuracy_svg({}, [])
    empty_coverage = accuracy_coverage_svg({}, [])
    assert empty_cost.startswith("<svg")
    assert "No recorded scores" in empty_coverage
    ElementTree.fromstring(empty_cost)
    ElementTree.fromstring(empty_coverage)


def test_cli_writes_offline_artifacts_and_marks_missing_thresholds(tmp_path):
    root = Path(__file__).parent / "fixtures" / "eval"
    output = tmp_path / "reports"
    code = main([
        "--labels", str(root / "synthetic_labels.csv"),
        "--predictions", str(root / "synthetic_predictions.json"),
        "--run-id", "synthetic-smoke", "--out-dir", str(output),
        "--frozen-thresholds", str(tmp_path / "not-present.json"),
    ])
    assert code == 0
    report = json.loads((output / "synthetic-smoke.json").read_text())
    assert report["mode"] == "replay"
    assert report["synthetic"] is True
    assert report["frozen_thresholds"]["status"] == "missing"
    assert report["test_case_count"] == 6
    assert (output / "synthetic-smoke.md").is_file()
    assert (output / "synthetic-smoke_cost_accuracy.svg").is_file()
    assert (output / "synthetic-smoke_accuracy_coverage.svg").is_file()


def test_cli_rejects_live_mode_without_writing(tmp_path):
    root = Path(__file__).parent / "fixtures" / "eval"
    try:
        main(["--labels", str(root / "synthetic_labels.csv"), "--predictions", str(root / "synthetic_predictions.json"), "--mode", "live", "--out-dir", str(tmp_path)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("live mode was accepted")
    assert list(tmp_path.iterdir()) == []
