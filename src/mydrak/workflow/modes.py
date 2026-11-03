"""Explicit workflow mode selection; no implicit provider fallback."""

from typing import Any

from mydrak.workflow.pipeline import run_synthetic_mock_workflow
from mydrak.workflow.spark_only import run_spark_only_workflow


def run_pipeline_mode(mode: str, **kwargs: Any):
    """Select mock or explicitly requested Spark-only execution.

    Replay remains on its registered cache-only entry point. Unknown/live-like
    mode names fail closed and never redirect to a different provider path.
    """
    if mode == "mock":
        return run_synthetic_mock_workflow(**kwargs)
    if mode == "spark_only":
        return run_spark_only_workflow(**kwargs)
    raise ValueError("workflow mode is unsupported")
