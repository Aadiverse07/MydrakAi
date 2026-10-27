"""Routing policy: signals in, action out (spec B3). Pure function."""

from typing import Literal

Action = Literal["retake", "answer", "escalate", "ask", "refer"]


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
    if s3 < quality_min:
        return "retake"
    if score >= accept and s1 > agree_min:
        return "answer"
    if not escalated:
        return "escalate"
    if followups_used < max_followups:
        return "ask"
    return "refer"
