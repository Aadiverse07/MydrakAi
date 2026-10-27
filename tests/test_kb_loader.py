"""KB loader: safety card loads; incomplete cards are rejected."""

import pytest

from mydrak.kb.loader import load_safety_card

from conftest import REPO_ROOT


def test_general_safety_card_loads():
    card = load_safety_card(REPO_ROOT / "kb" / "cards" / "general_safety.yaml")
    assert card["id"] == "general_safety"
    assert card["safety_line"]
    assert card["referral_text"]
    assert card["retake_text"]


def test_safety_card_missing_keys_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("id: x\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_safety_card(bad)
