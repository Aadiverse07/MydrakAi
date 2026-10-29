"""Offline reply snapshots using synthetic KB text, never real diagnosis data."""

import math

import pytest

from mydrak.reply.composer import ReplyError, compose_reply
from mydrak.kb.loader import load_safety_card

from conftest import REPO_ROOT


# Synthetic-only card: its wording is a rendering fixture, not agronomic advice.
SYNTHETIC_CARD = {
    "crop": "sample crop",
    "names": {"en": "Sample issue"},
    "low_risk_steps": {"en": ["Synthetic step one", "Synthetic step two"]},
    "follow_up_questions": [
        {"id": "sample-question", "en": "Is the sample mark on both sides?"}
    ],
}
SYNTHETIC_SAFETY_CARD = {
    "safety_line": "Synthetic safety line.",
    "referral_text": "Synthetic referral text.",
    "retake_text": "Synthetic retake instruction.",
}
REPO_SAFETY_CARD = load_safety_card(REPO_ROOT / "kb" / "cards" / "general_safety.yaml")


def test_answer_snapshot_with_optional_severity_is_caveated_and_safety_grounded():
    actual = compose_reply(
        "answer",
        card=SYNTHETIC_CARD,
        safety_card=SYNTHETIC_SAFETY_CARD,
        confidence="fairly sure",
        severity_pct=30.0,
    )
    assert actual == (
        "Likely issue: Sample issue on sample crop.\n"
        "How sure: fairly sure.\n"
        "How bad: About 30.0% of the leaf looks affected (estimate from one photo).\n"
        "What to do now: 1) Synthetic step one 2) Synthetic step two\n"
        "Safety: Synthetic safety line.\n"
        "Synthetic referral text."
    )


def test_answer_snapshot_without_severity_does_not_fabricate_a_measurement():
    actual = compose_reply(
        "answer",
        card=SYNTHETIC_CARD,
        safety_card=SYNTHETIC_SAFETY_CARD,
        confidence="not sure",
    )
    assert "How bad:" not in actual
    assert "Safety: Synthetic safety line." in actual
    assert "Synthetic step one" in actual


def test_ask_snapshot_uses_selected_kb_question_and_optional_labels():
    actual = compose_reply(
        "ask",
        card=SYNTHETIC_CARD,
        safety_card=SYNTHETIC_SAFETY_CARD,
        question_id="sample-question",
        alternatives=("Sample issue A", "Sample issue B"),
    )
    assert actual == (
        "I am not sure yet. It could be Sample issue A or Sample issue B. "
        "One question: Is the sample mark on both sides?"
    )


def test_ask_without_alternatives_stays_uncertain():
    actual = compose_reply(
        "ask", card=SYNTHETIC_CARD, safety_card=SYNTHETIC_SAFETY_CARD,
        question_id="sample-question",
    )
    assert actual == "I am not sure yet. One question: Is the sample mark on both sides?"


def test_refer_snapshot_uses_only_safety_card_referral():
    assert compose_reply(
        "refer", card=SYNTHETIC_CARD, safety_card=SYNTHETIC_SAFETY_CARD
    ) == "I cannot tell from this photo. Synthetic referral text."


def test_retake_snapshot_uses_only_safety_card_text():
    assert compose_reply(
        "retake", card=SYNTHETIC_CARD, safety_card=SYNTHETIC_SAFETY_CARD
    ) == "Synthetic retake instruction."


def test_existing_safety_card_supports_referral_and_retake_copy():
    assert compose_reply(
        "refer", card={}, safety_card=REPO_SAFETY_CARD
    ) == "I cannot tell from this photo. If it spreads or you are unsure, call the Kisan Call Centre or your local KVK (Krishi Vigyan Kendra)."
    assert compose_reply(
        "retake", card={}, safety_card=REPO_SAFETY_CARD
    ) == "The photo is too blurry or dark. Please take a close, clear photo of one leaf in daylight."


def test_safety_only_card_cannot_become_an_answer():
    with pytest.raises(ReplyError, match="names"):
        compose_reply(
            "answer", card=REPO_SAFETY_CARD, safety_card=REPO_SAFETY_CARD,
            confidence="cannot tell",
        )


def test_hindi_fails_closed_until_reviewed_templates_exist():
    with pytest.raises(ReplyError, match="template is unavailable"):
        compose_reply(
            "refer", card=SYNTHETIC_CARD, safety_card=SYNTHETIC_SAFETY_CARD,
            language="hi",
        )


@pytest.mark.parametrize("action", ["", "diagnose", "answer ", None])
def test_unsupported_actions_are_rejected(action):
    with pytest.raises(ReplyError, match="unsupported reply action"):
        compose_reply(action, card=SYNTHETIC_CARD, safety_card=SYNTHETIC_SAFETY_CARD)


@pytest.mark.parametrize("confidence", ["high", "90%", "", None])
def test_answer_rejects_unapproved_confidence_wording(confidence):
    with pytest.raises(ReplyError, match="fixed confidence vocabulary"):
        compose_reply(
            "answer", card=SYNTHETIC_CARD, safety_card=SYNTHETIC_SAFETY_CARD,
            confidence=confidence,
        )


@pytest.mark.parametrize("severity", [True, "30", -0.1, 100.1, math.inf, math.nan])
def test_answer_rejects_invalid_severity_values(severity):
    with pytest.raises(ReplyError, match="severity_pct"):
        compose_reply(
            "answer", card=SYNTHETIC_CARD, safety_card=SYNTHETIC_SAFETY_CARD,
            confidence="cannot tell", severity_pct=severity,
        )


def test_answer_rejects_oversized_integer_severity_without_overflow():
    with pytest.raises(ReplyError, match="severity_pct"):
        compose_reply(
            "answer", card=SYNTHETIC_CARD, safety_card=SYNTHETIC_SAFETY_CARD,
            confidence="cannot tell", severity_pct=10**10000,
        )


def test_answer_requires_card_steps_and_safety_line():
    missing_steps = {**SYNTHETIC_CARD, "low_risk_steps": {"en": []}}
    with pytest.raises(ReplyError, match="low-risk steps"):
        compose_reply(
            "answer", card=missing_steps, safety_card=SYNTHETIC_SAFETY_CARD,
            confidence="fairly sure",
        )
    missing_safety = {"referral_text": "Synthetic referral text."}
    with pytest.raises(ReplyError, match="safety_line"):
        compose_reply(
            "answer", card=SYNTHETIC_CARD, safety_card=missing_safety,
            confidence="fairly sure",
        )


def test_ask_rejects_unavailable_question_id():
    with pytest.raises(ReplyError, match="unavailable in the KB card"):
        compose_reply(
            "ask", card=SYNTHETIC_CARD, safety_card=SYNTHETIC_SAFETY_CARD,
            question_id="not-in-card",
        )


def test_reply_is_deterministic():
    arguments = {
        "action": "refer",
        "card": SYNTHETIC_CARD,
        "safety_card": SYNTHETIC_SAFETY_CARD,
    }
    assert compose_reply(**arguments) == compose_reply(**arguments)
