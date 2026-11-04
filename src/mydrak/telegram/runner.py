"""Hash-first Telegram orchestration over parsed, documented Bot API updates."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
import time
from typing import Any

from mydrak.bot.adapter import (
    ConversationStatus, OfflineTelegramAdapter, OfflineUpdate,
)
from mydrak.privacy.data_policy import ProcessingEvidence
from mydrak.reply.templates import telegram_message
from mydrak.telegram.client import TelegramClient, TelegramClientError
from mydrak.telegram.consent import CONSENT_NOTICE_VERSION
from mydrak.telegram.config import AccessMode, PublicLimits
from mydrak.telegram.delivery import TelegramDelivery
from mydrak.telegram.limits import PublicLimitStore
from mydrak.telegram.photo_flow import handle_private_photo
from mydrak.reply.preview import load_demo_draft_preview
from mydrak.telegram.updates import (
    NormalizedTelegramUpdate, RunnerOutcome, SkippedTelegramUpdate,
    digest_id, valid_normalized_update,
)
from mydrak.trace.store import TraceStore
from mydrak.workflow.modes import run_pipeline_mode


class TelegramBotRunner(TelegramDelivery):
    """Run defensively normalized updates while preserving privacy and access gates."""

    def __init__(
        self, *, client: TelegramClient, trace_store: TraceStore,
        adapter: OfflineTelegramAdapter, mode: AccessMode,
        allowed_chat_ids: frozenset[str] = frozenset(),
        limits: PublicLimits | None = None,
        limit_store: PublicLimitStore | None = None,
        stop_path: str | Path = "STOP",
        spark_config: Mapping[str, Any] | None = None,
        spark_provider_factory: Callable[..., Any] | None = None,
        processing_evidence: ProcessingEvidence | None = None,
        consent_notice_approved: bool = False,
        allow_private_upload: bool = False,
        private_tier1_allowed: bool = False,
        spend_cap_available: Callable[[], bool] | None = None,
        workflow: Callable[..., Any] = run_pipeline_mode,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if type(client) is not TelegramClient or type(trace_store) is not TraceStore:
            raise ValueError("Telegram client and local trace store are required")
        if type(adapter) is not OfflineTelegramAdapter or not isinstance(mode, AccessMode):
            raise ValueError("normalized bot adapter or access mode is invalid")
        if mode is AccessMode.ALLOWLIST and not allowed_chat_ids:
            raise ValueError("allowlist mode requires at least one chat ID")
        if mode is AccessMode.PUBLIC and (limits is None or type(limit_store) is not PublicLimitStore):
            raise ValueError("public mode requires complete limits and persistent storage")
        if mode is AccessMode.PUBLIC and not callable(spend_cap_available):
            raise ValueError("public mode requires the shared spend-ledger cap check")
        if mode is AccessMode.PUBLIC and load_demo_draft_preview():
            raise ValueError("demo draft preview is refused in public mode")
        if processing_evidence is not None and not isinstance(processing_evidence, ProcessingEvidence):
            raise ValueError("processing evidence is invalid")
        if any(type(value) is not bool for value in (
            consent_notice_approved, allow_private_upload, private_tier1_allowed,
        )):
            raise ValueError("private-photo settings must be booleans")
        self.client = client
        self.trace_store = trace_store
        self.adapter = adapter
        self.mode = mode
        self.allowed_chat_ids = allowed_chat_ids
        self.limits = limits
        self.limit_store = limit_store
        self.stop_path = Path(stop_path)
        self.spark_config = dict(spark_config or {})
        self.spark_config["allow_private_upload"] = allow_private_upload
        self.consent_notice_approved = consent_notice_approved
        self.allow_private_upload = allow_private_upload
        self.private_tier1_allowed = private_tier1_allowed
        self.spark_provider_factory = spark_provider_factory
        # Kept as a constructor compatibility argument; photos use fresh
        # consent-derived evidence in photo_flow.py, never this static value.
        self.spend_cap_available = spend_cap_available
        self.workflow = workflow
        self.sleep = sleep
        self._started_chats: set[str] = set()

    def handle_update(self, update: NormalizedTelegramUpdate) -> RunnerOutcome:
        if self.stop_path.exists():
            return RunnerOutcome("stopped", "stop_file")
        if type(update) is not NormalizedTelegramUpdate or not valid_normalized_update(update):
            return RunnerOutcome("skipped", "malformed_or_unverified_update")
        if update.chat_type != "private":
            return RunnerOutcome("ignored", "private_chats_only")
        chat_id = str(update.chat_id)
        if self.mode is AccessMode.ALLOWLIST and chat_id not in self.allowed_chat_ids:
            return RunnerOutcome("ignored", "not_allowlisted")

        chat_hash = digest_id("chat", chat_id)
        user_hash = digest_id("user", str(update.user_id))
        if update.kind == "command":
            return self._command(update, chat_hash, user_hash)
        if update.kind == "photo":
            return self._photo(update, chat_hash, user_hash)
        if update.kind == "text":
            result = self.adapter.handle_update(OfflineUpdate(chat_hash, "text", update.text))
            self._trace(user_hash, "telegram_text", result.status, "refer")
            reply = telegram_message(
                "text_unavailable" if result.status == "manual_review" else "send_photo"
            )
            return self._send(update.chat_id, user_hash, reply, "text_prompt")
        self.adapter.handle_update(OfflineUpdate(chat_hash, "unsupported", None))
        self._trace(user_hash, "telegram_unsupported", "skipped", "ask")
        return self._send(
            update.chat_id, user_hash, telegram_message("send_photo"), "unsupported_input"
        )

    def run_forever(self) -> int:
        """Poll only through a verified/injected transport; stop cleanly on SIGINT."""
        offset: int | None = None
        try:
            while not self.stop_path.exists():
                try:
                    updates = self._retry_operation(
                        lambda: self.client.get_updates(
                            offset=offset, limit=100, timeout=25,
                        )
                    )
                except TelegramClientError:
                    return 2
                for update in updates:
                    if isinstance(update, SkippedTelegramUpdate):
                        if update.update_id is None:
                            return 2
                        if offset is None or update.update_id >= offset:
                            offset = update.update_id + 1
                        continue
                    if type(update) is not NormalizedTelegramUpdate:
                        return 2
                    if offset is not None and update.update_id < offset:
                        continue
                    offset = update.update_id + 1
                    if not valid_normalized_update(update):
                        continue
                    try:
                        self.handle_update(update)
                    except Exception:
                        # Do not emit update content, exception text, or token.
                        continue
        except KeyboardInterrupt:
            return 0
        return 0

    def _command(self, update: NormalizedTelegramUpdate, chat_hash: str,
                 user_hash: str) -> RunnerOutcome:
        command = update.text or ""
        result = self.adapter.handle_update(OfflineUpdate(chat_hash, "command", command))
        parts = command.split(maxsplit=1)
        cmd = parts[0].split("@", 1)[0].lower()
        argument = parts[1] if len(parts) == 2 else ""
        start_requested = cmd == "/start" and result.status == "welcome"
        if start_requested:
            reply = telegram_message("start")
        elif cmd == "/privacy" and not argument:
            reply = telegram_message("privacy_notice")
        elif cmd == "/agree" and not argument:
            if not self.consent_notice_approved:
                reply = telegram_message("consent_unavailable")
            elif self.limit_store is None:
                reply = telegram_message("consent_storage_unavailable")
            else:
                try:
                    shown = self.limit_store.notice_was_shown(
                        user_hash, CONSENT_NOTICE_VERSION,
                    )
                    recorded = (
                        self.limit_store.record_consent(
                            user_hash, CONSENT_NOTICE_VERSION,
                        ) if shown else False
                    )
                except Exception:
                    shown, recorded = False, False
                reply = telegram_message("notice_required" if not shown else (
                    "consent_recorded" if recorded else "consent_storage_unavailable"
                ))
        elif cmd == "/withdraw" and not argument:
            try:
                withdrawn = (
                    self.limit_store.revoke_consent(user_hash)
                    if self.limit_store is not None else False
                )
            except Exception:
                withdrawn = False
            reply = telegram_message(
                "consent_withdrawn" if withdrawn else "consent_not_active"
            )
        elif cmd == "/rescan":
            reply = telegram_message("rescan_unavailable")
        elif cmd == "/help":
            reply = telegram_message("help")
        elif cmd == "/language":
            if result.status == "unsupported_language":
                reply = telegram_message("hindi_unavailable")
            elif result.reason == "language_selected":
                reply = telegram_message("language_set")
            else:
                reply = telegram_message("language_choices")
        elif result.status == "command_error":
            reply = telegram_message("command_unavailable")
        else:
            reply = result.reply or telegram_message("send_photo")
        action = "ask" if result.status not in {"command_error", "invalid_update"} else "refer"
        self._trace(user_hash, "telegram_command", result.status, action)
        sent = self._send(update.chat_id, user_hash, reply, "command")
        if start_requested and sent.sent:
            # A failed privacy-notice delivery must not grant photo processing.
            self._started_chats.add(chat_hash)
        if cmd == "/privacy" and not argument and sent.sent and self.limit_store is not None:
            try:
                self.limit_store.record_notice_shown(user_hash, CONSENT_NOTICE_VERSION)
            except Exception:
                return self._send(
                    update.chat_id, user_hash,
                    telegram_message("consent_storage_unavailable"),
                    "privacy_notice_storage_failure",
                )
        return sent

    def _photo(self, update: NormalizedTelegramUpdate, chat_hash: str,
               user_hash: str) -> RunnerOutcome:
        return handle_private_photo(self, update, chat_hash, user_hash)
