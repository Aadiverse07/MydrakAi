"""Pure standard-library metrics for explicit per-case evaluation records."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
import math
from numbers import Real
from typing import Any

SPLITS = frozenset({"dev", "test"})
ACTIONS = frozenset({"answer", "ask", "refer", "retake"})
REQUIRED_FIELDS = frozenset({
    "case_id", "split", "strategy", "label", "predicted", "action",
    "escalated", "tokens_in", "tokens_out", "latency_ms",
    "price_in_per_1m", "price_out_per_1m", "out_of_scope", "provenance",
})
OPTIONAL_FIELDS = frozenset({"score"})


class EvaluationError(ValueError):
    """Raised when evaluation data does not match the bounded input contract."""


def validate_record(record: Mapping[str, object]) -> dict[str, Any]:
    """Validate and normalize one record; no input is read from image files."""
    if not isinstance(record, Mapping):
        raise EvaluationError("each evaluation record must be a mapping")
    fields = set(record)
    if fields - REQUIRED_FIELDS - OPTIONAL_FIELDS or REQUIRED_FIELDS - fields:
        raise EvaluationError("evaluation record fields do not match the schema")

    result = dict(record)
    for name in ("case_id", "strategy", "label", "provenance"):
        value = result[name]
        if (
            not isinstance(value, str) or not value.strip() or len(value) > 256
            or any(ord(char) < 32 for char in value)
        ):
            raise EvaluationError(f"{name} must be a bounded non-empty string")
        result[name] = value.strip()
    if not isinstance(result["split"], str) or result["split"] not in SPLITS:
        raise EvaluationError("split must be dev or test")
    predicted = result["predicted"]
    if predicted is not None and (
        not isinstance(predicted, str) or not predicted.strip() or len(predicted) > 256
    ):
        raise EvaluationError("predicted must be a bounded label or null")
    if predicted is not None:
        result["predicted"] = predicted.strip()
    action = result["action"]
    if not isinstance(action, str) or action not in ACTIONS:
        raise EvaluationError("action is unsupported")
    if action == "answer" and predicted is None:
        raise EvaluationError("answer action requires a predicted label")
    if type(result["escalated"]) is not bool or type(result["out_of_scope"]) is not bool:
        raise EvaluationError("escalated and out_of_scope must be booleans")

    for name in ("tokens_in", "tokens_out"):
        value = result[name]
        if value is not None and (type(value) is not int or value < 0):
            raise EvaluationError(f"{name} must be a non-negative integer or null")
    for name in ("price_in_per_1m", "price_out_per_1m", "latency_ms", "score"):
        value = result.get(name)
        if name == "score" and value is None:
            result[name] = None
            continue
        if name in {"price_in_per_1m", "price_out_per_1m"} and value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, Real):
            raise EvaluationError(f"{name} must be a finite non-negative number or null")
        try:
            normalized = float(value)
            valid = math.isfinite(normalized) and normalized >= 0
            if name == "score":
                valid = valid and normalized <= 1
        except (OverflowError, TypeError, ValueError):
            valid = False
            normalized = 0.0
        if not valid:
            raise EvaluationError(f"{name} is outside its valid range")
        result[name] = normalized
    return result


def validate_records(records: Sequence[Mapping[str, object]]) -> list[dict[str, Any]]:
    """Validate a batch, rejecting duplicate case-strategy rows or label drift."""
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise EvaluationError("records must be a sequence")
    normalized = [validate_record(record) for record in records]
    seen: set[tuple[str, str]] = set()
    case_context: dict[str, tuple[object, ...]] = {}
    for row in normalized:
        key = (row["case_id"], row["strategy"])
        if key in seen:
            raise EvaluationError("duplicate case and strategy record")
        seen.add(key)
        context = (row["split"], row["label"], row["out_of_scope"], row["provenance"])
        previous = case_context.setdefault(row["case_id"], context)
        if previous != context:
            raise EvaluationError("case labels and provenance must agree across strategies")
    return normalized


def compute_metrics(records: Sequence[Mapping[str, object]]) -> dict[str, dict[str, Any]]:
    """Compute D1 metrics grouped by strategy for a single split."""
    rows = validate_records(records)
    splits = {row["split"] for row in rows}
    if len(splits) > 1:
        raise EvaluationError("compute_metrics accepts one split at a time")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["strategy"]].append(row)
    return {strategy: _strategy_metrics(strategy, grouped[strategy]) for strategy in sorted(grouped)}


def _strategy_metrics(strategy: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    answered = [row for row in rows if row["action"] == "answer"]
    correct_all = sum(
        row["action"] == "answer" and row["predicted"] == row["label"]
        for row in rows
    )
    correct_answered = sum(row["predicted"] == row["label"] for row in answered)
    escalations = sum(row["escalated"] for row in rows)
    deferrals = sum(row["action"] in {"ask", "refer"} for row in rows)
    retakes = sum(row["action"] == "retake" for row in rows)
    out_of_scope = [row for row in rows if row["out_of_scope"]]
    uncertain = sum(row["action"] in {"ask", "refer", "retake"} for row in out_of_scope)

    case_costs: list[Decimal] = []
    unknown_cost = total == 0
    for row in rows:
        values = (row["tokens_in"], row["tokens_out"], row["price_in_per_1m"], row["price_out_per_1m"])
        if any(value is None for value in values):
            unknown_cost = True
            continue
        try:
            cost = (
                Decimal(row["tokens_in"]) * Decimal(str(row["price_in_per_1m"]))
                + Decimal(row["tokens_out"]) * Decimal(str(row["price_out_per_1m"]))
            ) / Decimal(1_000_000)
        except (InvalidOperation, TypeError, ValueError):
            unknown_cost = True
            continue
        if not cost.is_finite() or not math.isfinite(float(cost)):
            unknown_cost = True
            continue
        case_costs.append(cost)
    total_cost = None if unknown_cost else float(sum(case_costs, Decimal(0)))
    cost_per_task = None if unknown_cost else total_cost / total

    latencies = sorted(row["latency_ms"] for row in rows)
    scored_count = sum(row.get("score") is not None for row in rows)
    return {
        "strategy": strategy,
        "split": rows[0]["split"] if rows else None,
        "case_count": total,
        "answered_count": len(answered),
        "accuracy_answered": _ratio(correct_answered, len(answered)),
        "accuracy_all": _ratio(correct_all, total),
        "escalation_rate": _ratio(escalations, total),
        "deferral_rate": _ratio(deferrals, total),
        "coverage": _ratio(len(answered), total),
        "retake_rate": _ratio(retakes, total),
        "cost_total_usd": total_cost,
        "cost_per_task_usd": cost_per_task,
        "cost_unknown": unknown_cost,
        "latency_ms_median": _median(latencies),
        "latency_ms_p90": _nearest_rank(latencies, 0.90),
        "out_of_scope_count": len(out_of_scope),
        "out_of_scope_uncertainty_handled": _ratio(uncertain, len(out_of_scope)),
        "scored_count": scored_count,
    }


def accuracy_coverage_curve(records: Sequence[Mapping[str, object]]) -> list[dict[str, float | int | None]]:
    """Report the accuracy/coverage curve at the distinct recorded scores.

    The curve is descriptive only. It does not select or tune a threshold.
    Rows without a recorded score are excluded from the curve and counted by
    the caller's `scored_count` metric.
    """
    rows = validate_records(records)
    if len({(row["strategy"], row["split"]) for row in rows}) > 1:
        raise EvaluationError("a curve accepts one strategy and one split")
    scored = [row for row in rows if row.get("score") is not None]
    if not scored:
        return []
    thresholds = sorted({0.0, *(row["score"] for row in scored)})
    curve = []
    for threshold in thresholds:
        accepted = [row for row in scored if row["score"] >= threshold]
        correct = sum(
            row["action"] == "answer" and row["predicted"] == row["label"]
            for row in accepted
        )
        curve.append({
            "threshold": threshold,
            "coverage": len(accepted) / len(scored),
            "accuracy": _ratio(correct, len(accepted)),
            "accepted_count": len(accepted),
        })
    return curve


def dev_tuning_curves(records: Sequence[Mapping[str, object]]) -> dict[str, list[dict[str, float | int | None]]]:
    """Return dev-only curves for threshold inspection; never selects a value."""
    rows = validate_records(records)
    if any(row["split"] != "dev" for row in rows):
        raise EvaluationError("threshold tuning accepts dev records only")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["strategy"]].append(row)
    return {strategy: accuracy_coverage_curve(grouped[strategy]) for strategy in sorted(grouped)}


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) / 2


def _nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    rank = max(1, math.ceil(percentile * len(values)))
    return values[rank - 1]
