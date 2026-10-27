"""Minimal YAML config loading. No network, no secrets handling."""

from pathlib import Path

import yaml


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
