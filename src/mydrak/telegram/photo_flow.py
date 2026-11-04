"""Consent-gated private-photo path for the Telegram runner."""

from datetime import datetime, timezone
from typing import Any

from mydrak.bot.adapter import ConversationStatus, OfflineUpdate
from mydrak.intake.adapter import MAX_IMAGE_BYTES
from mydrak.privacy.data_policy import (
    DataClass, DataPolicy, DataPolicyError, require_external_processing_allowed,
)
from mydrak.reply.templates import telegram_message
from mydrak.telegram.client import TelegramClientError
from mydrak.telegram.config import AccessMode
from mydrak.telegram.consent import processing_evidence_for
from mydrak.telegram.updates import NormalizedTelegramUpdate, RunnerOutcome


def handle_private_photo(
    runner: Any,
    update: NormalizedTelegramUpdate,
    chat_hash: str,
    user_hash: str,
) -> RunnerOutcome:
    if chat_hash not in runner._started_chats:
        runner._trace(user_hash, "telegram_photo", "start_required", "refer")
        return runner._send(
            update.chat_id, user_hash, telegram_message("start_required"), "start_required"
        )
    if update.photo_size is None or type(update.photo_size) is not int or update.photo_size < 1:
        runner._trace(user_hash, "telegram_photo", "invalid_size", "retake")
        return runner._send(
            update.chat_id, user_hash, telegram_message("send_photo"), "invalid_photo"
        )
    max_bytes = runner.limits.max_photo_bytes if runner.mode is AccessMode.PUBLIC else MAX_IMAGE_BYTES
    if update.photo_size > max_bytes:
        runner._trace(user_hash, "telegram_photo", "size_limit", "retake")
        return runner._send(
            update.chat_id, user_hash, telegram_message("limited"), "photo_size_limit"
        )
    if runner.spend_cap_available is not None:
        try:
            has_headroom = runner.spend_cap_available() is True
        except Exception:
            has_headroom = False
        if not has_headroom:
            runner._trace(user_hash, "global_spend_limit", "blocked", "refer")
            return runner._send(
                update.chat_id, user_hash, telegram_message("limited"), "global_spend_limit"
            )
    if runner.mode is AccessMode.PUBLIC:
        assert runner.limits is not None and runner.limit_store is not None
        try:
            reserved = runner.limit_store.reserve_photo(
                user_hash, limits=runner.limits, photo_size=update.photo_size,
                now=datetime.now(timezone.utc),
            )
        except Exception:
            runner._trace(user_hash, "public_limit", "unavailable", "refer")
            return runner._send(
                update.chat_id, user_hash, telegram_message("limited"), "public_limit_unavailable"
            )
        if not reserved.allowed:
            runner._trace(user_hash, "public_limit", reserved.reason or "blocked", "refer")
            return runner._send(
                update.chat_id, user_hash, telegram_message("limited"), "public_limit"
            )

    record = None
    if runner.limit_store is not None:
        try:
            record = runner.limit_store.get_consent(user_hash)
        except Exception:
            record = None
    evidence = processing_evidence_for(
        record,
        notice_approved=runner.consent_notice_approved,
        standard_model_id=runner.spark_config.get("model_id"),
        contributor_model_id=runner.spark_config.get("model_id_contributor"),
    )
    try:
        require_external_processing_allowed(DataPolicy.PRIVATE, DataClass.PRIVATE, evidence)
    except DataPolicyError:
        runner._trace(user_hash, "telegram_photo", "consent_or_policy_blocked", "refer")
        return runner._send(
            update.chat_id, user_hash, telegram_message("photo_blocked"), "privacy_block"
        )
    result = runner.adapter.handle_update(
        OfflineUpdate(chat_hash, "photo"), processing_evidence=evidence,
    )
    if result.status != "deferred" or result.reason != "preprocessing_and_diagnosis_unavailable":
        runner._trace(user_hash, "telegram_photo", "policy_blocked", "refer")
        return runner._send(
            update.chat_id, user_hash, telegram_message("photo_blocked"), "privacy_block"
        )
    if not runner.allow_private_upload:
        runner._trace(user_hash, "telegram_photo", "private_upload_disabled", "refer")
        return runner._send(
            update.chat_id, user_hash, telegram_message("photo_blocked"), "privacy_block"
        )
    if runner.private_tier1_allowed:
        runner._trace(user_hash, "telegram_photo", "private_tier1_path_unavailable", "refer")
        return runner._send(
            update.chat_id, user_hash, telegram_message("photo_blocked"), "privacy_block"
        )

    try:
        if not update.photo_file_id:
            raise TelegramClientError("photo file reference unavailable")
        file = runner._retry_operation(lambda: runner.client.get_file(update.photo_file_id))
        if (
            (file.file_size is not None and file.file_size != update.photo_size)
            or update.photo_size > max_bytes
            or (file.file_size is not None and file.file_size > max_bytes)
        ):
            runner._trace(user_hash, "telegram_photo", "file_size_limit", "retake")
            return runner._send(
                update.chat_id, user_hash, telegram_message("limited"), "photo_size_limit"
            )
        photo_bytes = runner._retry_operation(
            lambda: runner.client.download_file(file.file_path, max_bytes=max_bytes)
        )
        if not photo_bytes:
            raise TelegramClientError("photo bytes unavailable")
        runner.adapter.begin_analysis(chat_hash)
        result = runner.workflow(
            "spark_only", photo_bytes=photo_bytes, language="en",
            trace_store=runner.trace_store,
            spark_provider_factory=runner.spark_provider_factory,
            provider_config=runner.spark_config,
            data_policy_value=DataPolicy.PRIVATE.value,
            data_class=DataClass.PRIVATE, image_provenance="private",
            evidence=evidence, use_contributor=False, user_hash=user_hash,
        )
        next_state = {
            "answer": ConversationStatus.ANSWERED,
            "ask": ConversationStatus.AWAITING_FOLLOWUP,
            "retake": ConversationStatus.RETAKE,
            "refer": ConversationStatus.REFERRED,
            "blocked": ConversationStatus.REFERRED,
        }.get(result.action, ConversationStatus.REFERRED)
        runner.adapter.apply_workflow_outcome(chat_hash, next_state)
        reply = result.reply or telegram_message("photo_blocked")
        overlay = getattr(result, "overlay_bytes", None)
        del photo_bytes
        return runner._send(update.chat_id, user_hash, reply, "photo_result", photo=overlay)
    except Exception:
        runner._trace(user_hash, "telegram_photo", "workflow_failed", "refer")
        return runner._send(
            update.chat_id, user_hash, telegram_message("photo_blocked"), "workflow_failed"
        )
