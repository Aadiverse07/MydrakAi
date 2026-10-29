"""Offline renderer for structured, KB-grounded farmer reply outcomes.

This module formats supplied facts only. It does not diagnose, choose a KB
card, calculate severity, translate text, or send messages. Synthetic tests
exercise the rendering contract; they are not evidence of field accuracy.
"""

from collections.abc import Mapping, Sequence
import math
from typing import Any

from mydrak.reply.templates import TEMPLATES

CONFIDENCE_WORDS = frozenset({"fairly sure", "not sure", "cannot tell"})
SUPPORTED_ACTIONS = frozenset({"answer", "ask", "refer", "retake"})


class ReplyError(ValueError):
    """Raised when an outcome cannot be rendered safely from supplied data."""


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReplyError(f"{name} must be a non-empty string")
    return value.strip()


def _localized(card: Mapping[str, Any], key: str, language: str) -> Mapping[str, Any]:
    values = card.get(key)
    if not isinstance(values, Mapping):
        raise ReplyError(f"reply data is missing {key}")
    return values


def _steps(card: Mapping[str, Any]) -> str:
    localized = _localized(card, "low_risk_steps", "en")
    raw_steps = localized.get("en")
    if not isinstance(raw_steps, Sequence) or isinstance(raw_steps, (str, bytes)) or not raw_steps:
        raise ReplyError("reply data is missing English low-risk steps")
    return " ".join(f"{index}) {_text(step, 'step')}" for index, step in enumerate(raw_steps, 1))


def _safety_text(safety_card: Mapping[str, Any], key: str) -> str:
    return _text(safety_card.get(key), key)


def _severity(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReplyError("severity_pct must be a finite number from 0 to 100")
    if not 0 <= value <= 100 or not math.isfinite(value):
        raise ReplyError("severity_pct must be a finite number from 0 to 100")
    # str() preserves the supplied numeric value; this renderer does not
    # calculate or round the severity estimate.
    return f"How bad: About {value}% of the leaf looks affected (estimate from one photo).\n"


def _follow_up(card: Mapping[str, Any], question_id: str) -> str:
    questions = card.get("follow_up_questions")
    if not isinstance(questions, Sequence) or isinstance(questions, (str, bytes)):
        raise ReplyError("reply data is missing follow-up questions")
    for question in questions:
        if isinstance(question, Mapping) and question.get("id") == question_id:
            localized = question.get("en")
            if isinstance(localized, str):
                return _text(localized, "follow-up question")
            break
    raise ReplyError("requested follow-up question is unavailable in the KB card")


def compose_reply(
    action: str,
    *,
    card: Mapping[str, Any],
    safety_card: Mapping[str, Any],
    language: str = "en",
    confidence: str | None = None,
    severity_pct: int | float | None = None,
    question_id: str | None = None,
    alternatives: Sequence[str] = (),
) -> str:
    """Render one English reply from validated structured/KB data.

    ``card`` must contain approved English KB strings for the selected action.
    A caller remains responsible for loading that content from the KB; this
    pure formatter does not assert provenance. Hindi is refused until reviewed
    bilingual templates exist.
    """
    if not isinstance(action, str) or action not in SUPPORTED_ACTIONS:
        raise ReplyError("unsupported reply action")
    if not isinstance(language, str) or language not in TEMPLATES:
        raise ReplyError("unsupported reply language")
    if TEMPLATES[language] is None:
        raise ReplyError("requested language template is unavailable")
    if not isinstance(card, Mapping) or not isinstance(safety_card, Mapping):
        raise ReplyError("reply and safety cards must be mappings")
    templates = TEMPLATES[language]

    if action == "answer":
        names = _localized(card, "names", language)
        issue = _text(names.get(language), "English issue name")
        crop = _text(card.get("crop"), "crop")
        steps = _steps(card)
        if not isinstance(confidence, str) or confidence not in CONFIDENCE_WORDS:
            raise ReplyError("confidence must use the fixed confidence vocabulary")
        confidence_value = confidence
        safety_line = _safety_text(safety_card, "safety_line")
        referral_text = _safety_text(safety_card, "referral_text")
        values = {
            "issue": issue,
            "crop": crop,
            "confidence": confidence_value,
            "steps": steps,
            "safety_line": safety_line,
            "referral_text": referral_text,
        }
        if severity_pct is None:
            return templates["answer_without_severity"].format(**values)
        values["severity"] = _severity(severity_pct)
        return templates["answer"].format(**values)

    if action == "ask":
        if not isinstance(question_id, str) or not question_id:
            raise ReplyError("question_id is required for an ask reply")
        question = _follow_up(card, question_id)
        if isinstance(alternatives, (str, bytes)) or not isinstance(alternatives, Sequence):
            raise ReplyError("alternatives must be a sequence of KB labels")
        labels = [_text(value, "alternative") for value in alternatives]
        if labels:
            return templates["ask_with_alternatives"].format(
                alternatives=" or ".join(labels), question=question
            )
        return templates["ask"].format(question=question)

    if action == "refer":
        return templates["refer"].format(
            referral_text=_safety_text(safety_card, "referral_text")
        )

    return templates["retake"].format(
        retake_text=_safety_text(safety_card, "retake_text")
    )
