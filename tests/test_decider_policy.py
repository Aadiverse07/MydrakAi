"""Table-driven tests for every policy branch in spec B3."""

import pytest

from mydrak.decider.policy import decide

BASE = dict(accept=0.7, agree_min=0.5, quality_min=0.4, max_followups=2)


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        # Quality failure stops the case before anything else.
        (dict(score=0.95, s1=1.0, s3=0.2, escalated=False, followups_used=0), "retake"),
        # Confident tier-1 answer.
        (dict(score=0.8, s1=1.0, s3=0.9, escalated=False, followups_used=0), "answer"),
        # Score exactly at accept still answers (spec: "at or above").
        (dict(score=0.7, s1=1.0, s3=0.9, escalated=False, followups_used=0), "answer"),
        # S1 merely equal to agree_min is NOT "above" -> escalate, not answer.
        (dict(score=0.9, s1=0.5, s3=0.9, escalated=False, followups_used=0), "escalate"),
        # First uncertainty with no escalation used -> exactly one escalation.
        (dict(score=0.5, s1=0.5, s3=0.9, escalated=False, followups_used=0), "escalate"),
        # Already escalated, follow-ups remain -> ask.
        (dict(score=0.5, s1=0.5, s3=0.9, escalated=True, followups_used=0), "ask"),
        (dict(score=0.5, s1=0.5, s3=0.9, escalated=True, followups_used=1), "ask"),
        # Follow-ups exhausted -> refer to an expert.
        (dict(score=0.5, s1=0.5, s3=0.9, escalated=True, followups_used=2), "refer"),
        # Low score with escalation already spent and no follow-ups left.
        (dict(score=0.0, s1=0.0, s3=0.9, escalated=True, followups_used=2), "refer"),
    ],
)
def test_policy_branches(kwargs, expected):
    assert decide(**kwargs, **BASE) == expected
