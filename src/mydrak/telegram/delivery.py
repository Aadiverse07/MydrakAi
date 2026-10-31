"""Sanitized Telegram delivery retries and privacy-safe trace rows."""

from __future__ import annotations

import uuid

from mydrak.telegram.client import TelegramClientError
from mydrak.telegram.updates import RunnerOutcome
from mydrak.trace.store import TraceCase, TraceStep


class TelegramDelivery:
    """Mixin for runner state; never stores message text or raw IDs."""

    def _send(self, chat_id: int | str, user_hash: str, text: str,
              outcome: str, *, photo: bytes | None = None) -> RunnerOutcome:
        if self.stop_path.exists():
            return RunnerOutcome("stopped", "stop_file", user_hash)
        sent = False
        retries = 0
        for attempt in range(3):
            try:
                if photo:
                    self.client.send_photo(chat_id, photo, caption=text)
                else:
                    self.client.send_message(chat_id, text)
                sent = True
                break
            except TelegramClientError:
                if attempt == 2:
                    break
                retries += 1
                self.sleep(0.05 * (2 ** (retries - 1)))
        self._trace(user_hash, "telegram_send", "sent" if sent else "failed",
                    "ask" if sent else "refer", retries=retries,
                    error=None if sent else "telegram_send_failure")
        return RunnerOutcome("sent" if sent else "send_failed", outcome, user_hash, text, sent)

    def _trace(self, user_hash: str, step: str, result: str, action: str,
               *, retries: int = 0, error: str | None = None) -> None:
        case_id = uuid.uuid4().hex
        self.trace_store.record_case(
            TraceCase(case_id, action, "en",
                      "photo" if "photo" in step or step in {"public_limit", "global_spend_limit"} else "text",
                      "private", user_hash=user_hash),
            [TraceStep(step, result, 0.0, model="telegram_bot", retries=retries, error_code=error)],
        )
