"""Offline-only evaluation CLI; inputs are labels and recorded predictions."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # Support both direct CLI execution and package imports in tests.
    from .chart import accuracy_coverage_svg, cost_accuracy_svg
    from .metrics import EvaluationError, accuracy_coverage_curve, compute_metrics, validate_records
except ImportError:  # pragma: no cover - direct script execution
    from chart import accuracy_coverage_svg, cost_accuracy_svg
    from metrics import EvaluationError, accuracy_coverage_curve, compute_metrics, validate_records


def _load_inputs(labels_path: Path, predictions_path: Path) -> list[dict[str, Any]]:
    with labels_path.open("r", encoding="utf-8", newline="") as handle:
        labels = list(csv.DictReader(handle))
    label_fields = {"case_id", "split", "label", "out_of_scope", "provenance"}
    if not labels or set(labels[0]) != label_fields:
        raise EvaluationError("labels CSV is empty or missing required columns")
    try:
        predictions = json.loads(predictions_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError("predictions JSON could not be read") from None
    if not isinstance(predictions, list) or not all(isinstance(row, dict) for row in predictions):
        raise EvaluationError("predictions JSON must be a list of prediction objects")
    label_by_id: dict[str, dict[str, Any]] = {}
    for label in labels:
        case_id = label.get("case_id")
        if not case_id or case_id in label_by_id:
            raise EvaluationError("labels require unique non-empty case IDs")
        if label.get("split") not in {"dev", "test"} or label.get("out_of_scope") not in {"true", "false"}:
            raise EvaluationError("labels contain an invalid split or out_of_scope value")
        label_by_id[case_id] = label
    if any(
        not isinstance(row.get("case_id"), str) or not row["case_id"]
        or not isinstance(row.get("strategy"), str) or not row["strategy"]
        for row in predictions
    ):
        raise EvaluationError("predictions require non-empty string case and strategy IDs")
    strategies = {row["strategy"] for row in predictions}
    if not strategies:
        raise EvaluationError("predictions require bounded strategy identifiers")
    expected = {(case_id, strategy) for case_id in label_by_id for strategy in strategies}
    actual = {(row.get("case_id"), row.get("strategy")) for row in predictions}
    if expected != actual:
        raise EvaluationError("predictions must contain exactly one row per label and strategy")
    joined = []
    for prediction in predictions:
        label = label_by_id[prediction["case_id"]]
        joined.append({
            **prediction,
            "split": label["split"],
            "label": label["label"],
            "out_of_scope": label["out_of_scope"] == "true",
            "provenance": label["provenance"],
        })
    return validate_records(joined)


def _frozen_threshold_status(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "missing", "path": str(path)}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "invalid", "path": str(path)}
    if (
        not isinstance(data, dict) or data.get("schema") != "mydrak-frozen-thresholds-v1"
        or data.get("frozen") is not True or not isinstance(data.get("thresholds"), dict)
    ):
        return {"status": "invalid", "path": str(path)}
    thresholds = data["thresholds"]
    if not thresholds or any(
        not isinstance(name, str) or not name
        or isinstance(value, bool) or not isinstance(value, (int, float))
        or not math.isfinite(value) or not 0 <= value <= 1
        for name, value in thresholds.items()
    ):
        return {"status": "invalid", "path": str(path)}
    return {"status": "loaded", "path": str(path), "thresholds": thresholds}


def _git_sha(repo: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"], cwd=repo,
            capture_output=True, text=True, timeout=2, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = result.stdout.strip()
    return sha if re.fullmatch(r"[0-9a-f]{40}", sha) else None


def _markdown(metrics: dict[str, dict[str, Any]], threshold_status: dict[str, Any]) -> str:
    lines = ["# Offline evaluation report", "", "Synthetic fixture values are not model or agricultural evidence.", "",
             "| Strategy | Cases | Answered accuracy | All-case accuracy | Coverage | Escalation | Deferral | Cost/task | Median ms | P90 ms |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, item in sorted(metrics.items()):
        def fmt(value: object) -> str:
            return "UNKNOWN" if value is None else f"{value:.4f}" if isinstance(value, float) else str(value)
        cost = "UNKNOWN" if item["cost_unknown"] else fmt(item["cost_per_task_usd"])
        lines.append("| " + " | ".join((name, str(item["case_count"]), fmt(item["accuracy_answered"]),
            fmt(item["accuracy_all"]), fmt(item["coverage"]), fmt(item["escalation_rate"]),
            fmt(item["deferral_rate"]), cost, fmt(item["latency_ms_median"]), fmt(item["latency_ms_p90"]))) + " |")
    lines.extend(["", f"Frozen thresholds: **{threshold_status['status']}** ({threshold_status['path']}).",
                  "Cost and accuracy are unknown when required input evidence is missing.",
                  "No performance claim, diagnosis, or provider compatibility is established by this offline report.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--mode", default="replay", choices=("replay",))
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).parent / "results")
    parser.add_argument("--frozen-thresholds", type=Path, default=Path(__file__).parent / "frozen_thresholds.json")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", args.run_id):
        parser.error("run-id must contain 1-64 safe ASCII characters")
    try:
        records = _load_inputs(args.labels, args.predictions)
        test_records = [row for row in records if row["split"] == "test"]
        metrics = compute_metrics(test_records)
        curves = {
            strategy: accuracy_coverage_curve(group)
            for strategy in sorted({row["strategy"] for row in test_records})
            for group in [[row for row in test_records if row["strategy"] == strategy]]
        }
        threshold_status = _frozen_threshold_status(args.frozen_thresholds)
        report: dict[str, Any] = {
            "schema": "mydrak-offline-eval-v1", "mode": "replay",
            "synthetic": any(row["provenance"].lower().startswith("synthetic") for row in records),
            "test_case_count": len(test_records), "metrics": metrics,
            "accuracy_coverage_curves": curves, "frozen_thresholds": threshold_status,
        }
        sha = _git_sha(Path(__file__).resolve().parents[1])
        if sha:
            report["git_sha"] = sha
        args.out_dir.mkdir(parents=True, exist_ok=True)
        base = args.out_dir / args.run_id
        base.with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        base.with_suffix(".md").write_text(_markdown(metrics, threshold_status), encoding="utf-8")
        base.with_name(base.name + "_cost_accuracy.svg").write_text(cost_accuracy_svg(metrics, test_records), encoding="utf-8")
        base.with_name(base.name + "_accuracy_coverage.svg").write_text(accuracy_coverage_svg(curves, test_records), encoding="utf-8")
    except (EvaluationError, OSError, ValueError) as exc:
        print(f"evaluation failed: {exc}", file=sys.stderr)
        return 2
    print(f"wrote offline evaluation report: {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
