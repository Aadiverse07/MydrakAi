"""Offline follow-up loop tests with synthetic KB text."""

import pytest

from mydrak.kb.loader import load_safety_card
from mydrak.workflow.followup import (
    MAX_FOLLOWUP_TURNS,
    FollowUpError,
    FollowUpState,
    accept_followup_answer,
    begin_followup,
)

from conftest import REPO_ROOT


# Clearly synthetic prompt fixture; wording is not agronomic guidance.
SYNTHETIC_CARD = {
    "follow_up_questions": [
        {"id": "q1", "en": "Synthetic question one?"},
        {"id": "q2", "en": "Synthetic question two?"},
    ]
}
SAFETY_CARD = load_safety_card(REPO_ROOT / "kb" / "cards" / "general_safety.yaml")


def test_two_kb_questions_then_referral_end_to_end():
    first = begin_followup(
        FollowUpState(), card=SYNTHETIC_CARD, safety_card=SAFETY_CARD, question_id="q1"
    )
    assert first.action == "ask"
    assert first.message == "I am not sure yet. One question: Synthetic question one?"
    assert first.state == FollowUpState(turns_used=1, awaiting_answer=True)

    ready = accept_followup_answer(first.state, "synthetic answer one")
    second = begin_followup(
        ready, card=SYNTHETIC_CARD, safety_card=SAFETY_CARD, question_id="q2"
    )
    assert second.action == "ask"
    assert second.message == "I am not sure yet. One question: Synthetic question two?"
    assert second.state == FollowUpState(turns_used=2, awaiting_answer=True)

    completed = accept_followup_answer(second.state, "synthetic answer two")
    final = begin_followup(completed, card=SYNTHETIC_CARD, safety_card=SAFETY_CARD)
    assert MAX_FOLLOWUP_TURNS == 2
    assert final.action == "refer"
    assert final.message == (
        "I cannot tell from this photo. If it spreads or you are unsure, call "
        "the Kisan Call Centre or your local KVK (Krishi Vigyan Kendra)."
    )
    assert final.state.referred is True
    assert final.state.turns_used == 2


def test_answer_text_is_not_retained_in_state_or_error():
    prompt = begin_followup(
        FollowUpState(), card=SYNTHETIC_CARD, safety_card=SAFETY_CARD, question_id="q1"
    )
    marker = "unique synthetic answer"
    next_state = accept_followup_answer(prompt.state, marker)
    assert marker not in repr(next_state)
    assert next_state == FollowUpState(turns_used=1)


def test_cannot_ask_again_before_answering():
    prompt = begin_followup(
        FollowUpState(), card=SYNTHETIC_CARD, safety_card=SAFETY_CARD, question_id="q1"
    )
    with pytest.raises(FollowUpError, match="answer is still pending"):
        begin_followup(
            prompt.state, card=SYNTHETIC_CARD, safety_card=SAFETY_CARD, question_id="q2"
        )
    assert prompt.state == FollowUpState(turns_used=1, awaiting_answer=True)


@pytest.mark.parametrize("answer", ["", "   ", None, 7])
def test_empty_or_invalid_answer_does_not_advance(answer):
    prompt = begin_followup(
        FollowUpState(), card=SYNTHETIC_CARD, safety_card=SAFETY_CARD, question_id="q1"
    )
    with pytest.raises(FollowUpError, match="non-empty string"):
        accept_followup_answer(prompt.state, answer)
    assert prompt.state == FollowUpState(turns_used=1, awaiting_answer=True)


def test_invalid_question_fails_without_changing_state():
    state = FollowUpState()
    with pytest.raises(FollowUpError, match="selected KB follow-up question is unavailable"):
        begin_followup(
            state, card=SYNTHETIC_CARD, safety_card=SAFETY_CARD, question_id="not-in-card"
        )
    assert state == FollowUpState()


def test_missing_question_id_fails_controlled():
    with pytest.raises(FollowUpError, match="KB question id is required"):
        begin_followup(FollowUpState(), card=SYNTHETIC_CARD, safety_card=SAFETY_CARD)


def test_referred_state_is_terminal():
    state = FollowUpState(turns_used=2, referred=True)
    with pytest.raises(FollowUpError, match="already complete"):
        begin_followup(state, card=SYNTHETIC_CARD, safety_card=SAFETY_CARD)


@pytest.mark.parametrize(
    "state",
    [
        FollowUpState(turns_used=True),
        FollowUpState(turns_used=3),
        FollowUpState(turns_used=0, awaiting_answer=True),
        FollowUpState(turns_used=1, awaiting_answer=True, referred=True),
        FollowUpState(turns_used=1, referred=True),
    ],
)
def test_inconsistent_or_out_of_range_state_is_rejected(state):
    with pytest.raises(FollowUpError, match="state is"):
        begin_followup(state, card=SYNTHETIC_CARD, safety_card=SAFETY_CARD, question_id="q1")


def test_bad_referral_card_fails_closed_after_limit():
    state = FollowUpState(turns_used=2)
    with pytest.raises(FollowUpError, match="referral reply is unavailable"):
        begin_followup(state, card=SYNTHETIC_CARD, safety_card={}, question_id="ignored")
    assert state == FollowUpState(turns_used=2)
