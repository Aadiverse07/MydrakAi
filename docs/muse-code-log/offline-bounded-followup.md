# Offline bounded follow-up loop

Date: 2026-10-29

## Task and specification basis

Implemented the next offline farmer-workflow slice from master-spec T16
(Should-Have), B3, and B7: ask up to two selected KB follow-up questions,
then refer. This reuses the English reply composer and card question/referral
text. Existing mock intake and SAM parsing do not interpret answers or provide
diagnostic evidence, so they are not treated as a source for question choice.

## Acceptance and result

- A prompt is rendered only from a question ID and English text present in the
  supplied KB card.
- A second prompt cannot be issued until the first answer is accepted; answer
  input must be a non-empty string.
- At most two prompts are issued. After the second answer, the next transition
  uses the existing safety-card referral reply and marks the state terminal.
- Invalid states, missing questions, and unavailable referral text fail
  closed. Answer text is neither retained in state nor echoed in errors.
- This module does not interpret answers, infer a diagnosis, call services,
  persist conversation data, or implement Telegram delivery.

## Files and checks

- Added `src/mydrak/workflow/followup.py` and `tests/test_followup.py`.
- Focused workflow/reply/KB suite: 45 passed.
- Full suite: 599 passed, with bytecode and pytest cache generation disabled.
