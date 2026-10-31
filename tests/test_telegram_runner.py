"""Offline runner tests use synthetic normalized updates and injected wire fakes."""

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from types import SimpleNamespace

import pytest

from mydrak.bot.adapter import OfflineTelegramAdapter
from mydrak.privacy.data_policy import DataClass, ProcessingEvidence, ProviderMode
from mydrak.telegram.client import TelegramClient, TelegramFile
from mydrak.telegram.config import AccessMode, PublicLimits
from mydrak.telegram.limits import PublicLimitStore
from mydrak.telegram.runner import NormalizedTelegramUpdate, TelegramBotRunner
from mydrak.trace.store import TraceStore


class FakeTransport:
    def __init__(self, *, failures=0, photo=b"synthetic-image-bytes"):
        self.calls = []
        self.failures = failures
        self.photo = photo
        self.poll_results = []
        self.poll_failures = 0

    def call(self, method, parameters, *, timeout_s):
        self.calls.append((method, dict(parameters), timeout_s))
        if method in {"sendMessage", "sendPhoto"} and self.failures:
            self.failures -= 1
            raise RuntimeError("synthetic transport failure with synthetic-token")
        if method == "getUpdates":
            if self.poll_failures:
                self.poll_failures -= 1
                raise RuntimeError("synthetic poll error with synthetic-token")
            return self.poll_results
        if method == "getFile":
            return TelegramFile("synthetic/path.jpg", len(self.photo))
        return {"ok": True}

    def download(self, file_path, *, max_bytes, timeout_s):
        self.calls.append(("download", {"file_path": file_path, "max_bytes": max_bytes}, timeout_s))
        return self.photo


PRIVATE_EVIDENCE = ProcessingEvidence(
    provider_mode=ProviderMode.STANDARD,
    provider_mode_verified=True,
    rights_confirmed=True,
    user_authorization_confirmed=True,
    privacy_notice_present=True,
)


def update(kind="command", *, update_id=1, chat_id="raw-chat-9876", user_id="raw-user-4567",
           chat_type="private", text="/start", photo_size=21, file_id="synthetic-file-id"):
    return NormalizedTelegramUpdate(update_id, chat_id, user_id, chat_type, kind,
                                    text, file_id if kind == "photo" else None,
                                    photo_size if kind == "photo" else None)


def make_runner(tmp_path, *, mode=AccessMode.ALLOWLIST, allowed=None,
                transport=None, adapter_evidence=None, limits=None, limit_store=None,
                spark_config=None, evidence=None, workflow=None, stop=None):
    transport = transport or FakeTransport()
    trace = TraceStore(":memory:")
    adapter = OfflineTelegramAdapter(
        data_policy_value="private", data_class=DataClass.PRIVATE,
        evidence=adapter_evidence,
    )
    runner = TelegramBotRunner(
        client=TelegramClient("synthetic-token-not-for-output", transport=transport),
        trace_store=trace, adapter=adapter, mode=mode,
        allowed_chat_ids=allowed or frozenset({"raw-chat-9876"}),
        limits=limits, limit_store=limit_store,
        stop_path=stop or (tmp_path / "STOP"),
        spark_config=spark_config or {}, processing_evidence=evidence,
        spend_cap_available=lambda: True,
        spark_provider_factory=lambda **kwargs: None,
        workflow=workflow or (lambda *args, **kwargs: SimpleNamespace(
            action="refer", reply="preliminary guidance; cannot tell", overlay_bytes=None,
        )),
        sleep=lambda _: None,
    )
    return runner, transport, trace


def test_start_shows_privacy_note_and_only_hashed_ids_reach_trace(tmp_path):
    runner, transport, trace = make_runner(tmp_path)
    result = runner.handle_update(update())
    assert result.sent
    assert "sent to an AI model" in result.reply
    assert "raw-user-4567" not in result.reply
    assert result.user_hash == sha256(b"mydrak-telegram-v1:user:raw-user-4567").hexdigest()
    row = trace._connection.execute("SELECT user_hash FROM cases").fetchone()
    assert row[0] == result.user_hash
    assert "raw-user-4567" not in repr(result)
    assert transport.calls[0][0] == "sendMessage"


def test_help_language_and_rescan_commands_have_controlled_outcomes(tmp_path):
    runner, transport, _ = make_runner(tmp_path)
    runner.handle_update(update(text="/start"))
    assert "Use /start" in runner.handle_update(update(update_id=2, text="/help")).reply
    hindi = runner.handle_update(update(update_id=3, text="/language hi"))
    assert hindi.sent and "Hindi is not available" in hindi.reply
    rescan = runner.handle_update(update(update_id=4, text="/rescan"))
    assert "not implemented" in rescan.reply
    assert [call[0] for call in transport.calls] == ["sendMessage"] * 4


def test_allowlist_ignores_other_chat_silently_and_groups_are_ignored(tmp_path):
    runner, transport, trace = make_runner(tmp_path)
    assert runner.handle_update(update(chat_id="other-chat")).reason == "not_allowlisted"
    assert runner.handle_update(update(chat_type="group")).reason == "private_chats_only"
    assert transport.calls == []
    assert trace._connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 0


def test_photo_before_start_is_refused_without_file_download_or_provider(tmp_path):
    called = []
    runner, transport, trace = make_runner(tmp_path, workflow=lambda *a, **k: called.append(1))
    result = runner.handle_update(update("photo", text=None))
    assert result.sent and "send /start" in result.reply
    assert not called
    assert not any(call[0] in {"getFile", "download"} for call in transport.calls)
    assert trace._connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 2


def test_private_upload_disabled_refuses_before_download_and_provider(tmp_path):
    called = []
    runner, transport, _ = make_runner(
        tmp_path, adapter_evidence=PRIVATE_EVIDENCE, evidence=PRIVATE_EVIDENCE,
        spark_config={"allow_private_upload": False},
        workflow=lambda *a, **k: called.append(1),
    )
    runner.handle_update(update())
    result = runner.handle_update(update("photo", update_id=2, text=None))
    assert result.sent and "cannot be analyzed" in result.reply
    assert not called
    assert not any(call[0] in {"getFile", "download"} for call in transport.calls)


def test_private_photo_flows_to_spark_only_with_rights_standard_and_start(tmp_path):
    captured = []
    def workflow(mode, **kwargs):
        captured.append((mode, kwargs))
        return SimpleNamespace(action="refer", reply="preliminary guidance; cannot tell",
                               overlay_bytes=b"SYNTHETIC-WATERMARK-OVERLAY")
    runner, transport, trace = make_runner(
        tmp_path, adapter_evidence=PRIVATE_EVIDENCE, evidence=PRIVATE_EVIDENCE,
        spark_config={"allow_private_upload": True}, workflow=workflow,
    )
    runner.handle_update(update())
    result = runner.handle_update(update("photo", update_id=2, text=None))
    assert result.sent
    assert len(captured) == 1
    mode, kwargs = captured[0]
    assert mode == "spark_only"
    assert kwargs["data_class"] is DataClass.PRIVATE
    assert kwargs["use_contributor"] is False
    assert kwargs["image_provenance"] == "private"
    assert kwargs["photo_bytes"] == b"synthetic-image-bytes"
    assert any(call[0] == "sendPhoto" and call[1]["photo"] == b"SYNTHETIC-WATERMARK-OVERLAY"
               for call in transport.calls)
    stored = trace._connection.execute("SELECT user_hash,image_hash FROM cases").fetchall()
    assert all(row[0] == result.user_hash for row in stored)
    assert all(row[1] is None for row in stored)
    assert b"synthetic-image-bytes" not in repr(stored).encode()


def test_missing_rights_or_unverified_provider_refuses_private_photo(tmp_path):
    evidence = ProcessingEvidence(provider_mode=ProviderMode.STANDARD,
                                  provider_mode_verified=False, rights_confirmed=False)
    called = []
    runner, transport, _ = make_runner(
        tmp_path, adapter_evidence=PRIVATE_EVIDENCE, evidence=evidence,
        spark_config={"allow_private_upload": True},
        workflow=lambda *a, **k: called.append(1),
    )
    runner.handle_update(update())
    result = runner.handle_update(update("photo", update_id=2, text=None))
    assert result.sent and "cannot be analyzed" in result.reply
    assert not called
    assert not any(call[0] == "getFile" for call in transport.calls)


def test_public_limits_refuse_request_without_provider_call(tmp_path):
    limits = PublicLimits(1, 10, Decimal("2"), 100, 0)
    store = PublicLimitStore(tmp_path / "public-limits.sqlite3")
    called = []
    runner, transport, _ = make_runner(
        tmp_path, mode=AccessMode.PUBLIC, limits=limits, limit_store=store,
        workflow=lambda *a, **k: called.append(1),
    )
    runner.handle_update(update())
    first = runner.handle_update(update("photo", update_id=2, text=None))
    second = runner.handle_update(update("photo", update_id=3, text=None))
    assert first.reason == "privacy_block"
    assert second.reason == "public_limit"
    assert not called
    store.close()


def test_spend_cap_gate_replies_without_workflow_or_photo_download(tmp_path):
    called = []
    evidence = PRIVATE_EVIDENCE
    runner, transport, _ = make_runner(
        tmp_path, adapter_evidence=evidence, evidence=evidence,
        spark_config={"allow_private_upload": True},
        workflow=lambda *a, **k: called.append(1),
    )
    runner.spend_cap_available = lambda: False
    runner.handle_update(update())
    result = runner.handle_update(update("photo", update_id=2, text=None))
    assert result.reason == "global_spend_limit"
    assert result.sent and "cannot process" in result.reply
    assert not called
    assert not any(call[0] in {"getFile", "download"} for call in transport.calls)


def test_group_channel_unknown_and_malformed_updates_are_safe(tmp_path):
    runner, transport, _ = make_runner(tmp_path)
    assert runner.handle_update(update("other")).status == "sent"
    assert runner.handle_update(update(chat_type="channel", update_id=2)).reason == "private_chats_only"
    assert runner.handle_update(update("command", update_id=3, text="")).reason == "malformed_or_unverified_update"
    assert runner.handle_update(object()).reason == "malformed_or_unverified_update"


def test_text_content_is_never_echoed_or_traced(tmp_path):
    runner, transport, trace = make_runner(tmp_path)
    secret = "synthetic-private-symptom-text-never-store"
    result = runner.handle_update(update("text", text=secret))
    assert result.sent
    assert secret not in result.reply
    assert secret not in repr(result)
    assert "sendMessage" in [call[0] for call in transport.calls]
    assert secret not in repr(trace._connection.execute("SELECT * FROM steps").fetchall())


def test_stop_file_halts_before_answer_and_failed_start_does_not_enable_photo(tmp_path):
    stop = tmp_path / "STOP"
    stop.write_text("", encoding="utf-8")
    runner, transport, _ = make_runner(tmp_path, stop=stop)
    assert runner.handle_update(update()).status == "stopped"
    assert transport.calls == []

    failed_transport = FakeTransport(failures=3)
    runner, failed_transport, _ = make_runner(
        tmp_path, transport=failed_transport, stop=tmp_path / "OTHER_STOP"
    )
    started = runner.handle_update(update())
    assert not started.sent
    photo = runner.handle_update(update("photo", update_id=2, text=None))
    assert photo.reason == "start_required"


def test_send_retries_twice_and_failure_trace_contains_no_content_or_token(tmp_path):
    transport = FakeTransport(failures=3)
    runner, _, trace = make_runner(tmp_path, transport=transport)
    result = runner.handle_update(update())
    assert result.status == "send_failed"
    assert sum(call[0] == "sendMessage" for call in transport.calls) == 3
    row = trace._connection.execute(
        "SELECT retries,error FROM steps WHERE step_name='telegram_send'"
    ).fetchone()
    assert row[0] == 2 and row[1] == "telegram_send_failure"
    contents = repr(result) + repr(row)
    assert "synthetic-token" not in contents
    assert "raw-user-4567" not in contents


def test_polling_error_retries_twice_then_exits_without_secret_output(tmp_path):
    transport = FakeTransport()
    transport.poll_failures = 3
    runner, _, _ = make_runner(tmp_path, transport=transport)
    assert runner.run_forever() == 2
    assert sum(call[0] == "getUpdates" for call in transport.calls) == 3
