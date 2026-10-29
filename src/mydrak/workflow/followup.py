"""Bounded, offline follow-up state transitions using KB questions.

The state stores only how many prompts were used and whether an answer is
currently expected. Farmer answer text is validated but never retained. This
module does not interpret answers or produce diagnoses; the caller selects a
KB question for each prompt.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from mydrak.reply.composer import ReplyError, compose_reply

MAX_FOLLOWUP_TURNS = 2


class FollowUpError(ValueError):
    """Raised when a follow-up transition or prompt is invalid."""


@dataclass(frozen=True)
class FollowUpState:
    """Minimal state; no farmer answer, identity, or image data is stored."""

    turns_used: int = 0
    awaiting_answer: bool = False
    referred: bool = False


@dataclass(frozen=True)
class FollowUpStep:
    """One prompt or referral message and its next immutable state."""

    action: Literal["ask", "refer"]
    message: str
    state: FollowUpState


def _validate_state(state: FollowUpState) -> None:
    if not isinstance(state, FollowUpState):
        raise FollowUpError("follow-up state is invalid")
    if type(state.turns_used) is not int or not 0 <= state.turns_used <= MAX_FOLLOWUP_TURNS:
        raise FollowUpError("follow-up state is invalid")
    if type(state.awaiting_answer) is not bool or type(state.referred) is not bool:
        raise FollowUpError("follow-up state is invalid")
    if state.awaiting_answer and (state.referred or state.turns_used == 0):
        raise FollowUpError("follow-up state is inconsistent")
    if state.referred and (state.awaiting_answer or state.turns_used != MAX_FOLLOWUP_TURNS):
        raise FollowUpError("follow-up state is inconsistent")


def begin_followup(
    state: FollowUpState,
    *,
    card: Mapping[str, Any],
    safety_card: Mapping[str, Any],
    question_id: str | None = None,
    alternatives: Sequence[str] = (),
) -> FollowUpStep:
    """Ask one selected KB question or refer after two completed asks.

    The caller must select the question from the KB context. If another
    question is requested before the prior answer arrives, or the selected
    question cannot be rendered from the card, this fails without changing
    the immutable input state.
    """
    _validate_state(state)
    if state.referred:
        raise FollowUpError("follow-up is already complete")
    if state.awaiting_answer:
        raise FollowUpError("the previous follow-up answer is still pending")
    if state.turns_used == MAX_FOLLOWUP_TURNS:
        try:
            message = compose_reply("refer", card=card, safety_card=safety_card)
        except ReplyError:
            raise FollowUpError("referral reply is unavailable") from None
        next_state = FollowUpState(
            turns_used=state.turns_used,
            awaiting_answer=False,
            referred=True,
        )
        return FollowUpStep("refer", message, next_state)

    if not isinstance(question_id, str) or not question_id:
        raise FollowUpError("a KB question id is required")
    try:
        message = compose_reply(
            "ask",
            card=card,
            safety_card=safety_card,
            question_id=question_id,
            alternatives=alternatives,
        )
    except ReplyError:
        raise FollowUpError("selected KB follow-up question is unavailable") from None
    next_state = FollowUpState(
        turns_used=state.turns_used + 1,
        awaiting_answer=True,
        referred=False,
    )
    return FollowUpStep("ask", message, next_state)


def accept_followup_answer(state: FollowUpState, answer: str) -> FollowUpState:
    """Advance after a non-empty answer without retaining its contents."""
    _validate_state(state)
    if state.referred:
        raise FollowUpError("follow-up is already complete")
    if not state.awaiting_answer:
        raise FollowUpError("no follow-up answer is currently expected")
    if not isinstance(answer, str) or not answer.strip():
        raise FollowUpError("follow-up answer must be a non-empty string")
    return FollowUpState(
        turns_used=state.turns_used,
        awaiting_answer=False,
        referred=False,
    )
