"""Minimal YAML config loading. No network, no secrets handling."""

from collections.abc import Mapping
from enum import StrEnum
import os
from pathlib import Path

import yaml


class DemoMode(StrEnum):
    """Modes supported by this offline build; live mode is intentionally absent."""

    REPLAY = "replay"


def parse_demo_mode(value: object = None) -> DemoMode:
    """Validate DEMO_MODE; an unset setting safely defaults to replay."""
    if value is None:
        return DemoMode.REPLAY
    if isinstance(value, str) and value == "replay":
        return DemoMode.REPLAY
    if isinstance(value, str) and value == "live":
        raise ValueError("live DEMO_MODE is disabled in this offline build")
    raise ValueError("DEMO_MODE must be 'replay'")


def load_demo_mode(environ: Mapping[str, str] | None = None) -> DemoMode:
    """Read only DEMO_MODE from the process environment; `.env` is not loaded."""
    values = os.environ if environ is None else environ
    return parse_demo_mode(values.get("DEMO_MODE"))


def load_yaml(path: str | Path) -> dict:
    """Load a YAML file expected to contain a mapping.

    Raises FileNotFoundError for a missing file and ValueError when the
    top-level document is not a mapping.
    """
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"config {path} must contain a mapping, got {type(data).__name__}")
    return data
