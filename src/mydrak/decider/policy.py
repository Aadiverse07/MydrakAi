"""Routing policy: signals in, action out (spec B3). Pure function."""

from typing import Literal
import math
from numbers import Real

Action = Literal["retake", "answer", "escalate", "ask", "refer"]


def _check_unit(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number within 0..1")
    try:
        valid = math.isfinite(value) and 0.0 <= value <= 1.0
    except (OverflowError, TypeError):
        valid = False
    if not valid:
        raise ValueError(f"{name} must be a finite number within 0..1")


def decide(
    *,
    score: float,
    s1: float,
    s3: float,
    accept: float,
    agree_min: float,
    quality_min: float,
    escalated: bool,
    followups_used: int,
    max_followups: int,
) -> Action:
    """Pick the next action. Every path ends in answer, retake, or refer.

    Order: retake (bad quality) -> answer (score >= accept and S1 strictly
    above agree_min) -> escalate (once) -> ask (while follow-ups remain) ->
    refer.
    """
    for name, value in (
        ("score", score), ("s1", s1), ("s3", s3), ("accept", accept),
        ("agree_min", agree_min), ("quality_min", quality_min),
    ):
        _check_unit(name, value)
    if type(escalated) is not bool:
        raise ValueError("escalated must be boolean")
    if type(max_followups) is not int or not 0 <= max_followups <= 2:
        raise ValueError("max_followups must be an integer from 0 to 2")
    if type(followups_used) is not int or not 0 <= followups_used <= max_followups:
        raise ValueError("followups_used is inconsistent with max_followups")
    if not escalated and followups_used > 0:
        raise ValueError("follow-ups cannot precede the escalation step")
    if s3 < quality_min:
        return "retake"
    if score >= accept and s1 > agree_min:
        return "answer"
    if not escalated:
        return "escalate"
    if followups_used < max_followups:
        return "ask"
    return "refer"
