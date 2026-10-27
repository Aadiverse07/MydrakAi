"""Loader for KB cards. Phase 0 ships only general_safety.yaml."""

from pathlib import Path

import yaml

SAFETY_REQUIRED_KEYS = ("id", "safety_line", "referral_text", "retake_text")


def load_card(path: str | Path) -> dict:
    """Load one card file and return its mapping (no schema beyond mapping)."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"card {path} must contain a mapping")
    return data


def load_safety_card(path: str | Path) -> dict:
    """Load the general safety card, requiring its safety/referral lines."""
    card = load_card(path)
    missing = [k for k in SAFETY_REQUIRED_KEYS if not card.get(k)]
    if missing:
        raise ValueError(f"safety card {path} missing keys: {missing}")
    return card
