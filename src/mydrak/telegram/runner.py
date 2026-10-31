"""Hash-first Telegram orchestration over normalized updates.

The supplied Bot API excerpt does not define raw Update nesting. This runner
accepts only a project-local normalized record; live parsing remains blocked
until the response contract is documented.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any

from mydrak.bot.adapter import (
    ConversationStatus, OfflineTelegramAdapter, OfflineUpdate,
)
from mydrak.intake.adapter import MAX_IMAGE_BYTES
from mydrak.privacy.data_policy import (
    DataClass, DataPolicy, ProcessingEvidence, ProviderMode,
)
from mydrak.reply.templates import telegram_message
from mydrak.telegram.client import TelegramClient, TelegramClientError
from mydrak.telegram.config import AccessMode, PublicLimits
from mydrak.telegram.delivery import TelegramDelivery
from mydrak.telegram.limits import PublicLimitStore
from mydrak.telegram.updates import (
    NormalizedTelegramUpdate, RunnerOutcome, digest_id, valid_normalized_update,
)
from mydrak.trace.store import TraceStore
from mydrak.workflow.modes import run_pipeline_mode


class TelegramBotRunner(TelegramDelivery):
    """Run explicit normalized updates; never parse undocumented API mappings."""

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
        if processing_evidence is not None and not isinstance(processing_evidence, ProcessingEvidence):
            raise ValueError("processing evidence is invalid")
        self.client = client
        self.trace_store = trace_store
        self.adapter = adapter
        self.mode = mode
        self.allowed_chat_ids = allowed_chat_ids
        self.limits = limits
        self.limit_store = limit_store
        self.stop_path = Path(stop_path)
        self.spark_config = spark_config or {}
        self.spark_provider_factory = spark_provider_factory
        self.processing_evidence = processing_evidence
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
                    # urllib exceptions can contain token-bearing URLs.
                    return 2
                for update in updates:
                    if type(update) is not NormalizedTelegramUpdate:
                        # Raw Update nesting is not present in the supplied
                        # documentation. Stop rather than poll an unknown
                        # response indefinitely or guess field mappings.
                        return 2
                    if not valid_normalized_update(update):
                        continue
                    offset = update.update_id + 1
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
        cmd = command.split(maxsplit=1)[0].split("@", 1)[0].lower()
        start_requested = cmd == "/start" and result.status == "welcome"
        if start_requested:
            reply = telegram_message("start")
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
        return sent

    def _photo(self, update: NormalizedTelegramUpdate, chat_hash: str,
               user_hash: str) -> RunnerOutcome:
        if chat_hash not in self._started_chats:
            self._trace(user_hash, "telegram_photo", "start_required", "refer")
            return self._send(update.chat_id, user_hash,
                              telegram_message("start_required"),
                              "start_required")
        if update.photo_size is None or type(update.photo_size) is not int or update.photo_size < 1:
            self._trace(user_hash, "telegram_photo", "invalid_size", "retake")
            return self._send(
                update.chat_id, user_hash, telegram_message("send_photo"), "invalid_photo"
            )
        max_bytes = self.limits.max_photo_bytes if self.mode is AccessMode.PUBLIC else MAX_IMAGE_BYTES
        if update.photo_size > max_bytes:
            self._trace(user_hash, "telegram_photo", "size_limit", "retake")
            return self._send(
                update.chat_id, user_hash, telegram_message("limited"), "photo_size_limit"
            )
        if self.spend_cap_available is not None:
            try:
                has_headroom = self.spend_cap_available() is True
            except Exception:
                has_headroom = False
            if not has_headroom:
                self._trace(user_hash, "global_spend_limit", "blocked", "refer")
                return self._send(
                    update.chat_id, user_hash, telegram_message("limited"), "global_spend_limit"
                )
        if self.mode is AccessMode.PUBLIC:
            assert self.limits is not None and self.limit_store is not None
            try:
                reserved = self.limit_store.reserve_photo(
                    user_hash, limits=self.limits, photo_size=update.photo_size,
                    now=datetime.now(timezone.utc),
                )
            except Exception:
                self._trace(user_hash, "public_limit", "unavailable", "refer")
                return self._send(
                    update.chat_id, user_hash, telegram_message("limited"), "public_limit_unavailable"
                )
            if not reserved.allowed:
                self._trace(user_hash, "public_limit", reserved.reason or "blocked", "refer")
                return self._send(
                    update.chat_id, user_hash, telegram_message("limited"), "public_limit"
                )

        result = self.adapter.handle_update(OfflineUpdate(chat_hash, "photo"))
        if result.status != "deferred" or result.reason != "preprocessing_and_diagnosis_unavailable":
            self._trace(user_hash, "telegram_photo", "policy_blocked", "refer")
            return self._send(
                update.chat_id, user_hash, telegram_message("photo_blocked"), "privacy_block"
            )
        if self.spark_config.get("allow_private_upload") is not True:
            self._trace(user_hash, "telegram_photo", "private_upload_disabled", "refer")
            return self._send(
                update.chat_id, user_hash, telegram_message("photo_blocked"), "privacy_block"
            )
        if (
            self.processing_evidence is None
            or not self.processing_evidence.rights_confirmed
            or not self.processing_evidence.provider_mode_verified
            or self.processing_evidence.provider_mode is not ProviderMode.STANDARD
        ):
            self._trace(user_hash, "telegram_photo", "private_evidence_unavailable", "refer")
            return self._send(
                update.chat_id, user_hash, telegram_message("photo_blocked"), "privacy_block"
            )

        try:
            if not update.photo_file_id:
                raise TelegramClientError("photo file reference unavailable")
            file = self._retry_operation(lambda: self.client.get_file(update.photo_file_id))
            if file.file_size != update.photo_size or file.file_size > max_bytes:
                self._trace(user_hash, "telegram_photo", "file_size_limit", "retake")
                return self._send(
                    update.chat_id, user_hash, telegram_message("limited"), "photo_size_limit"
                )
            photo_bytes = self._retry_operation(
                lambda: self.client.download_file(file.file_path, max_bytes=max_bytes)
            )
            if not photo_bytes:
                raise TelegramClientError("photo bytes unavailable")
            self.adapter.begin_analysis(chat_hash)
            evidence = ProcessingEvidence(
                provider_mode=ProviderMode.STANDARD,
                provider_mode_verified=True,
                rights_confirmed=True,
                user_authorization_confirmed=True,
                privacy_notice_present=True,
            )
            result = self.workflow(
                "spark_only", photo_bytes=photo_bytes, language="en",
                trace_store=self.trace_store,
                spark_provider_factory=self.spark_provider_factory,
                provider_config=self.spark_config,
                data_policy_value=DataPolicy.PRIVATE.value,
                data_class=DataClass.PRIVATE, image_provenance="private",
                evidence=evidence, use_contributor=False,
                user_hash=user_hash,
            )
            state = {
                "answer": ConversationStatus.ANSWERED,
                "ask": ConversationStatus.AWAITING_FOLLOWUP,
                "retake": ConversationStatus.RETAKE,
                "refer": ConversationStatus.REFERRED,
                "blocked": ConversationStatus.REFERRED,
            }.get(result.action, ConversationStatus.REFERRED)
            self.adapter.apply_workflow_outcome(chat_hash, state)
            reply = result.reply or telegram_message("photo_blocked")
            overlay = getattr(result, "overlay_bytes", None)
            del photo_bytes
            return self._send(update.chat_id, user_hash, reply, "photo_result", photo=overlay)
        except Exception:
            self._trace(user_hash, "telegram_photo", "workflow_failed", "refer")
            return self._send(
                update.chat_id, user_hash, telegram_message("photo_blocked"), "workflow_failed"
            )

    def _retry_operation(self, operation: Callable[[], Any]) -> Any:
        for attempt in range(3):
            try:
                return operation()
            except TelegramClientError:
                if attempt == 2:
                    raise
                self.sleep(0.1 * (2 ** attempt))
        raise TelegramClientError("Telegram operation failed")
