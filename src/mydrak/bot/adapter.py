"""Offline-first adapter for normalized, synthetic Telegram-like updates.

This is a project-local update contract, not Telegram's wire schema. It accepts
no media bytes and imports no Telegram or networking client. Photo, voice, and
rescan work stop with explicit deferred outcomes because their downstream
product capabilities are not available at this boundary.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from mydrak.privacy.data_policy import (
    DataClass,
    DataPolicyError,
    ProcessingEvidence,
    parse_data_policy,
    require_external_processing_allowed,
)
from mydrak.trace.store import TraceStore
from mydrak.bot.failure_support import record_bot_failure, retry_fake_send
from mydrak.workflow.mock_providers import DeterministicMockTranscriber

MAX_CONVERSATION_KEY_CHARS = 128  # Project-local bound for opaque synthetic keys.


class ConversationStatus(StrEnum):
    IDLE = "idle"
    AWAITING_PHOTO = "awaiting_photo"
    ANALYZING = "analyzing"
    ANSWERED = "answered"
    AWAITING_FOLLOWUP = "awaiting_followup"
    RETAKE = "retake"
    REFERRED = "referred"


@dataclass(frozen=True)
class OfflineUpdate:
    """Normalized test input; ``text`` is excluded from repr and all outputs."""

    conversation_key: str
    kind: str
    text: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class ConversationState:
    """Minimal in-memory state; never contains message or media content."""

    status: ConversationStatus = ConversationStatus.IDLE
    language: str = "en"


@dataclass(frozen=True)
class BotOutcome:
    """A controlled adapter outcome suitable for inspection or fake delivery."""

    status: Literal[
        "welcome", "help", "language", "unsupported_language", "deferred",
        "blocked", "manual_review", "invalid_update", "unsupported_update",
        "invalid_transition", "command_error", "replayed",
    ]
    conversation_status: ConversationStatus | None
    reply: str | None = None
    reason: str = ""


class FakeTelegramTransport:
    """In-memory sink used only by deterministic offline tests."""

    def __init__(self, *, failures_remaining: int = 0) -> None:
        if type(failures_remaining) is not int or not 0 <= failures_remaining <= 3:
            raise ValueError("fake transport failure count is invalid")
        self.messages: list[tuple[str, str]] = []
        self.failures_remaining = failures_remaining
        self.send_calls = 0

    def send(self, conversation_key: str, text: str) -> None:
        self.send_calls += 1
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise RuntimeError("synthetic fake Telegram send failure")
        self.messages.append((conversation_key, text))


class OfflineTelegramAdapter:
    """Handle normalized updates without initializing or contacting Telegram."""

    def __init__(
        self,
        *,
        data_policy_value: str | None = None,
        data_class: DataClass = DataClass.PRIVATE,
        evidence: ProcessingEvidence | None = None,
        transport: FakeTelegramTransport | None = None,
        outbound_enabled: bool = False,
        trace_store: TraceStore | None = None,
        transcriber: DeterministicMockTranscriber | None = None,
    ) -> None:
        if type(outbound_enabled) is not bool:
            raise ValueError("outbound_enabled must be boolean")
        if transport is not None and type(transport) is not FakeTelegramTransport:
            raise ValueError("only the exact fake Telegram transport is supported")
        if outbound_enabled and transport is None:
            raise ValueError("enabled offline delivery requires the fake transport")
        if not isinstance(data_class, DataClass):
            raise ValueError("data classification is invalid")
        if evidence is not None and not isinstance(evidence, ProcessingEvidence):
            raise ValueError("processing evidence is invalid")
        if trace_store is not None and type(trace_store) is not TraceStore:
            raise ValueError("only the local SQLite trace store is supported")
        if transcriber is not None and type(transcriber) is not DeterministicMockTranscriber:
            raise ValueError("only the deterministic mock transcriber is supported")
        self._data_policy_value = data_policy_value
        self._data_class = data_class
        self._evidence = evidence
        self._transport = transport
        self._outbound_enabled = outbound_enabled
        self._trace_store = trace_store
        self._transcriber = transcriber
        self._states: dict[str, ConversationState] = {}

    def state_for(self, conversation_key: str) -> ConversationState:
        """Return state without exposing or echoing any user message content."""
        return self._states.get(conversation_key, ConversationState())

    def begin_analysis(self, conversation_key: str) -> ConversationState:
        """Trusted workflow hook; normalized update fields cannot invoke it."""
        if not isinstance(conversation_key, str) or not conversation_key.strip():
            raise ValueError("conversation key is invalid")
        state = self.state_for(conversation_key)
        if state.status not in {ConversationStatus.AWAITING_PHOTO, ConversationStatus.RETAKE}:
            raise ValueError("analysis transition is not allowed in the current state")
        next_state = ConversationState(ConversationStatus.ANALYZING, state.language)
        self._states[conversation_key] = next_state
        return next_state

    def apply_workflow_outcome(
        self, conversation_key: str, outcome: ConversationStatus
    ) -> ConversationState:
        """Apply a trusted downstream status; this does not accept update data."""
        if not isinstance(conversation_key, str) or not conversation_key.strip():
            raise ValueError("conversation key is invalid")
        if not isinstance(outcome, ConversationStatus):
            raise ValueError("workflow outcome is invalid")
        state = self.state_for(conversation_key)
        if state.status is not ConversationStatus.ANALYZING:
            raise ValueError("workflow outcome requires analyzing state")
        if outcome not in {
            ConversationStatus.ANSWERED,
            ConversationStatus.AWAITING_FOLLOWUP,
            ConversationStatus.RETAKE,
            ConversationStatus.REFERRED,
        }:
            raise ValueError("workflow outcome is not supported")
        next_state = ConversationState(outcome, state.language)
        self._states[conversation_key] = next_state
        return next_state

    def handle_update(self, update: OfflineUpdate | Mapping[str, object] | None) -> BotOutcome:
        """Validate and handle one normalized event; errors never echo input."""
        parsed, error = self._coerce_update(update)
        if error is not None:
            return self._deliver(None, error)
        assert parsed is not None
        state = self._states.get(parsed.conversation_key, ConversationState())

        if parsed.kind == "command":
            outcome, next_state = self._command(parsed, state)
        elif parsed.kind == "photo":
            outcome, next_state = self._photo(state)
        elif parsed.kind == "voice":
            if state.status is ConversationStatus.AWAITING_PHOTO:
                try:
                    if self._transcriber is None:
                        raise RuntimeError("mock transcription boundary is unavailable")
                    self._transcriber.transcribe()
                except Exception:
                    outcome = BotOutcome(
                        "deferred", state.status,
                        "Transcription failed in this offline mock. Please resend the voice note or type a short note.",
                        "transcription_failed",
                    )
                    record_bot_failure(
                        self._trace_store, conversation_key=parsed.conversation_key,
                        language=state.language, input_type="voice", outcome="failed",
                        action="ask", error_code="transcription_failed",
                    )
                else:
                    outcome = BotOutcome(
                        "deferred", state.status,
                        "Mock transcription completed, but voice text processing is not available in this offline build.",
                        "voice_text_processing_unavailable",
                    )
            else:
                outcome = self._invalid_transition(state)
            next_state = state
        elif parsed.kind == "text":
            if state.status is ConversationStatus.AWAITING_FOLLOWUP:
                outcome = BotOutcome(
                    "manual_review", ConversationStatus.REFERRED, None,
                    "followup_interpretation_unavailable",
                )
                next_state = ConversationState(ConversationStatus.REFERRED, state.language)
            else:
                outcome = self._invalid_transition(state)
                next_state = state
        else:
            outcome = BotOutcome("unsupported_update", state.status, None, "unsupported_update_type")
            next_state = state

        self._states[parsed.conversation_key] = next_state
        return self._deliver(parsed.conversation_key, outcome, language=state.language)

    def _coerce_update(
        self, update: OfflineUpdate | Mapping[str, object] | None
    ) -> tuple[OfflineUpdate | None, BotOutcome | None]:
        if isinstance(update, OfflineUpdate):
            values = {
                "conversation_key": update.conversation_key,
                "kind": update.kind,
                "text": update.text,
            }
        elif isinstance(update, Mapping):
            if set(update) != {"conversation_key", "kind", "text"}:
                return None, BotOutcome("invalid_update", None, None, "malformed_update")
            values = dict(update)
        else:
            return None, BotOutcome("invalid_update", None, None, "missing_or_malformed_update")

        key = values["conversation_key"]
        kind = values["kind"]
        text = values["text"]
        if (
            not isinstance(key, str) or not key.strip()
            or len(key) > MAX_CONVERSATION_KEY_CHARS
            or not isinstance(kind, str)
        ):
            return None, BotOutcome("invalid_update", None, None, "invalid_update_metadata")
        if kind not in {"command", "photo", "voice", "text"}:
            return None, BotOutcome("unsupported_update", None, None, "unsupported_update_type")
        if kind in {"command", "text"}:
            if not isinstance(text, str) or not text.strip():
                return None, BotOutcome("invalid_update", None, None, "missing_message_text")
            if len(text) > 4096:
                return None, BotOutcome("invalid_update", None, None, "message_too_long")
            if kind == "command" and (not text.startswith("/") or len(text) > 128):
                return None, BotOutcome("invalid_update", None, None, "malformed_command")
        elif text is not None:
            return None, BotOutcome("invalid_update", None, None, "unexpected_message_text")
        return OfflineUpdate(key, kind, text), None

    def _command(
        self, update: OfflineUpdate, state: ConversationState
    ) -> tuple[BotOutcome, ConversationState]:
        parts = (update.text or "").split(maxsplit=1)
        command = parts[0].split("@", maxsplit=1)[0].lower()
        argument = parts[1].strip().lower() if len(parts) == 2 else ""
        if command == "/start" and not argument:
            next_state = ConversationState(ConversationStatus.AWAITING_PHOTO, "en")
            outcome = BotOutcome(
                "welcome", next_state.status,
                "Welcome. Choose English or Hindi with /language en or /language hi. "
                "English is available; Hindi is not available yet. This offline adapter "
                "does not process or send photos.",
                "start_offline_session",
            )
            return outcome, next_state
        if command == "/help" and not argument:
            return BotOutcome(
                "help", state.status,
                "Use /start, then send a photo. Photo analysis, voice, and rescans are not available in this offline build.",
                "help_offline_capabilities",
            ), state
        if command == "/language" and not argument:
            return BotOutcome(
                "language", state.status,
                "Available language: English. Hindi is not available yet. Use /language en to select English.",
                "language_choices",
            ), state
        if command == "/language" and argument == "en":
            next_state = ConversationState(state.status, "en")
            return BotOutcome("language", state.status, "Language set to English.", "language_selected"), next_state
        if command == "/language" and argument == "hi":
            return BotOutcome(
                "unsupported_language", state.status,
                "Hindi is not available yet; the current offline reply is English.",
                "language_unavailable",
            ), state
        if command == "/rescan" and not argument:
            return BotOutcome(
                "deferred", state.status,
                "Rescan is not available because scan history is not configured.",
                "scan_store_unavailable",
            ), state
        if command == "/replay":
            if not argument or self._trace_store is None:
                return BotOutcome(
                    "command_error", state.status,
                    "That offline replay fixture is not available.",
                    "replay_fixture_unavailable",
                ), state
            # Import on demand so the ordinary update path remains independent
            # of replay orchestration. This function has no provider fallback.
            from mydrak.replay import ReplayError, run_registered_cached_replay

            try:
                replayed = run_registered_cached_replay(
                    argument, trace_store=self._trace_store
                )
            except ReplayError:
                return BotOutcome(
                    "command_error", state.status,
                    "That offline replay fixture is not available.",
                    "replay_fixture_unavailable",
                ), state
            return BotOutcome(
                "replayed", state.status, replayed.reply,
                "cached_synthetic_replay",
            ), state
        return BotOutcome("command_error", state.status, "That command is not available.", "unknown_or_malformed_command"), state

    def _photo(self, state: ConversationState) -> tuple[BotOutcome, ConversationState]:
        if state.status not in {ConversationStatus.AWAITING_PHOTO, ConversationStatus.RETAKE}:
            return self._invalid_transition(state), state
        try:
            policy = parse_data_policy(self._data_policy_value)
            if self._evidence is None:
                raise DataPolicyError("processing evidence is unavailable")
            require_external_processing_allowed(policy, self._data_class, self._evidence)
        except DataPolicyError:
            next_state = ConversationState(ConversationStatus.REFERRED, state.language)
            return BotOutcome(
                "blocked", next_state.status, None, "privacy_policy_gate_blocked",
            ), next_state

        # No bytes or media metadata enter the workflow. T04/T05 are not
        # available here, so the adapter explicitly defers instead of guessing.
        return self._defer_photo_processing(state)

    @staticmethod
    def _defer_photo_processing(state: ConversationState) -> tuple[BotOutcome, ConversationState]:
        return BotOutcome(
            "deferred", state.status,
            "Photo preprocessing and diagnosis are not available yet. No photo was processed.",
            "preprocessing_and_diagnosis_unavailable",
        ), state

    @staticmethod
    def _invalid_transition(state: ConversationState) -> BotOutcome:
        return BotOutcome("invalid_transition", state.status, None, "event_not_allowed_in_current_state")

    def _deliver(self, key: str | None, outcome: BotOutcome, *, language: str = "en") -> BotOutcome:
        if self._outbound_enabled and key is not None and outcome.reply is not None:
            # Exact-type validation at construction prevents custom/networking
            # transports from being selected, even if a caller opts in.
            assert type(self._transport) is FakeTelegramTransport
            delivered, retries = retry_fake_send(self._transport, key, outcome.reply)
            if retries or not delivered:
                action = outcome.status if outcome.status in {"answer", "ask", "refer", "retake"} else "refer"
                record_bot_failure(
                    self._trace_store, conversation_key=key,
                    language=language, input_type="text",
                    outcome="completed" if delivered else "failed",
                    action=action, error_code="telegram_send_failure",
                    retries=retries,
                )
            if not delivered:
                return BotOutcome(
                    "deferred", outcome.conversation_status, outcome.reply,
                    "telegram_send_failed",
                )
        return outcome
