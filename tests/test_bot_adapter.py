"""Offline-only tests for the normalized Telegram adapter boundary."""

import ast
from pathlib import Path
import socket

import pytest

from mydrak.bot.adapter import (
    MAX_CONVERSATION_KEY_CHARS,
    ConversationStatus,
    FakeTelegramTransport,
    OfflineTelegramAdapter,
    OfflineUpdate,
)
from mydrak.privacy.data_policy import DataClass, ProcessingEvidence, ProviderMode
from mydrak.replay import registered_demo_cache_key
from mydrak.trace.store import CACHE_PROVENANCE, CACHE_SCHEMA, TraceError, TraceStore


PUBLIC_TEST_EVIDENCE = ProcessingEvidence(
    provider_mode=ProviderMode.STANDARD,
    provider_mode_verified=True,
    rights_confirmed=True,
    public_test_provenance_verified=True,
)


def update(kind="command", text="/start", key="synthetic-chat"):
    return OfflineUpdate(conversation_key=key, kind=kind, text=text)


def allowed_adapter(**kwargs):
    return OfflineTelegramAdapter(
        data_policy_value="public_test",
        data_class=DataClass.PUBLIC_TEST,
        evidence=PUBLIC_TEST_EVIDENCE,
        **kwargs,
    )


def test_start_welcomes_and_enters_awaiting_photo():
    adapter = OfflineTelegramAdapter()
    result = adapter.handle_update(update())
    assert result.status == "welcome"
    assert result.conversation_status is ConversationStatus.AWAITING_PHOTO
    assert "does not process or send photos" in result.reply
    assert adapter.state_for("synthetic-chat").language == "en"


@pytest.mark.parametrize("bad_update", [
    None,
    {},
    {"conversation_key": "synthetic-chat", "kind": "command"},
    {"conversation_key": "", "kind": "command", "text": "/start"},
    {"conversation_key": "x" * (MAX_CONVERSATION_KEY_CHARS + 1), "kind": "command", "text": "/start"},
    {"conversation_key": "synthetic-chat", "kind": "text", "text": "  "},
    {"conversation_key": "synthetic-chat", "kind": "command", "text": "start"},
    {"conversation_key": "synthetic-chat", "kind": "photo", "text": "unexpected"},
    {"conversation_key": "synthetic-chat", "kind": "photo", "text": None, "raw_bytes": b"synthetic"},
])
def test_malformed_or_incomplete_normalized_update_fails_without_echo(bad_update):
    result = OfflineTelegramAdapter().handle_update(bad_update)
    assert result.status == "invalid_update"
    assert result.reply is None
    assert result.conversation_status is None


def test_unsupported_update_type_and_missing_photo_input_are_controlled():
    adapter = OfflineTelegramAdapter()
    unsupported = adapter.handle_update({
        "conversation_key": "synthetic-chat", "kind": "callback_query", "text": None,
    })
    missing_input = adapter.handle_update({
        "conversation_key": "synthetic-chat", "kind": "empty", "text": None,
    })
    assert unsupported.status == missing_input.status == "unsupported_update"
    assert unsupported.reason == missing_input.reason == "unsupported_update_type"


def test_photo_before_start_is_an_invalid_transition_and_state_is_unchanged():
    adapter = allowed_adapter()
    result = adapter.handle_update(update(kind="photo", text=None))
    assert result.status == "invalid_transition"
    assert result.conversation_status is ConversationStatus.IDLE
    assert adapter.state_for("synthetic-chat").status is ConversationStatus.IDLE


def test_trusted_workflow_transitions_are_explicit_and_invalid_edges_rejected():
    adapter = OfflineTelegramAdapter()
    with pytest.raises(ValueError, match="analysis transition"):
        adapter.begin_analysis("synthetic-chat")
    adapter.handle_update(update())
    assert adapter.begin_analysis("synthetic-chat").status is ConversationStatus.ANALYZING
    with pytest.raises(ValueError, match="workflow outcome requires"):
        adapter.apply_workflow_outcome("other-chat", ConversationStatus.ANSWERED)
    with pytest.raises(ValueError, match="not supported"):
        adapter.apply_workflow_outcome("synthetic-chat", ConversationStatus.ANALYZING)
    assert adapter.apply_workflow_outcome(
        "synthetic-chat", ConversationStatus.RETAKE
    ).status is ConversationStatus.RETAKE


def test_allowed_photo_is_deferred_without_preprocessing_or_diagnosis():
    adapter = allowed_adapter()
    adapter.handle_update(update())
    result = adapter.handle_update(update(kind="photo", text=None))
    assert result.status == "deferred"
    assert result.reason == "preprocessing_and_diagnosis_unavailable"
    assert result.conversation_status is ConversationStatus.AWAITING_PHOTO
    assert "No photo was processed" in result.reply


def test_policy_block_stops_before_photo_processing(monkeypatch):
    adapter = OfflineTelegramAdapter()

    def forbidden(*args, **kwargs):
        raise AssertionError("downstream photo processing must not run")

    monkeypatch.setattr(adapter, "_defer_photo_processing", forbidden)
    adapter.handle_update(update())
    result = adapter.handle_update(update(kind="photo", text=None))
    assert result.status == "blocked"
    assert result.reply is None
    assert result.reason == "privacy_policy_gate_blocked"
    assert result.conversation_status is ConversationStatus.REFERRED


def test_start_language_help_rescan_and_voice_have_explicit_outcomes():
    adapter = OfflineTelegramAdapter()
    assert adapter.handle_update(update()).status == "welcome"
    assert adapter.handle_update(update(text="/language")).status == "language"
    assert adapter.handle_update(update(text="/language hi")).status == "unsupported_language"
    assert adapter.handle_update(update(text="/language en")).status == "language"
    assert adapter.handle_update(update(text="/help")).status == "help"
    rescan = adapter.handle_update(update(text="/rescan"))
    assert rescan.status == "deferred"
    assert rescan.reason == "scan_store_unavailable"
    voice = adapter.handle_update(update(kind="voice", text=None))
    assert voice.status == "deferred"
    assert voice.reason == "audio_pipeline_unavailable"


def test_followup_text_is_not_interpreted_or_echoed_and_routes_to_manual_review():
    adapter = OfflineTelegramAdapter()
    adapter.handle_update(update())
    adapter.begin_analysis("synthetic-chat")
    adapter.apply_workflow_outcome("synthetic-chat", ConversationStatus.AWAITING_FOLLOWUP)
    secret_like_answer = "synthetic-private-answer-do-not-echo"
    result = adapter.handle_update(update(kind="text", text=secret_like_answer))
    assert result.status == "manual_review"
    assert result.conversation_status is ConversationStatus.REFERRED
    assert secret_like_answer not in repr(result)
    assert secret_like_answer not in repr(adapter.state_for("synthetic-chat"))


def test_fake_transport_is_inert_by_default_and_explicitly_opt_in_only():
    transport = FakeTelegramTransport()
    adapter = OfflineTelegramAdapter(transport=transport)
    adapter.handle_update(update())
    assert transport.messages == []

    enabled = OfflineTelegramAdapter(transport=transport, outbound_enabled=True)
    result = enabled.handle_update(update())
    assert len(transport.messages) == 1
    assert transport.messages[0] == ("synthetic-chat", result.reply)


def test_non_fake_transport_cannot_be_injected_or_enabled():
    class CustomTransport(FakeTelegramTransport):
        pass

    with pytest.raises(ValueError, match="exact fake"):
        OfflineTelegramAdapter(transport=CustomTransport(), outbound_enabled=True)
    with pytest.raises(ValueError, match="requires the fake"):
        OfflineTelegramAdapter(outbound_enabled=True)


def test_no_network_or_environment_access(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network socket must not be opened")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    adapter = allowed_adapter()
    adapter.handle_update(update())
    adapter.handle_update(update(kind="photo", text=None))

    source = Path(__file__).parents[1] / "src/mydrak/bot/adapter.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not imported.intersection({"os", "requests", "urllib", "http", "telegram", "socket"})


def test_error_and_result_repr_never_include_untrusted_content(caplog):
    marker = "synthetic-sensitive-user-text"
    adapter = OfflineTelegramAdapter()
    result = adapter.handle_update(update(text=f"/unknown {marker}"))
    assert result.status == "command_error"
    assert marker not in repr(result)
    assert marker not in repr(update(text=marker))
    assert marker not in caplog.text


def _registered_replay_store():
    store = TraceStore(":memory:")
    store.put_cache(
        registered_demo_cache_key("synthetic-referral-01"),
        {
            "schema": CACHE_SCHEMA,
            "provenance": CACHE_PROVENANCE,
            "status": "referred",
            "response_code": "safe_referral",
        },
        timestamp="2026-01-02T03:04:05Z",
    )
    return store


def test_replay_command_selects_registered_fixture_and_traces_cache_reads(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "replay")
    store = _registered_replay_store()
    adapter = OfflineTelegramAdapter(trace_store=store)
    command = update(text="/replay synthetic-referral-01")

    first = adapter.handle_update(command)
    second = adapter.handle_update(command)
    assert first.status == "replayed"
    assert first == second
    assert first.reason == "cached_synthetic_replay"
    assert "synthetic demo only" in first.reply
    assert "diagnosis" not in first.reply.lower()
    reads = store._connection.execute(
        "SELECT case_id FROM cases WHERE case_id IN "
        "(SELECT case_id FROM steps WHERE step_name='replay_cache_read')"
    ).fetchall()
    assert len(reads) == 2
    assert all(store.get_steps(row["case_id"])[0]["outcome"] == "completed" for row in reads)


@pytest.mark.parametrize(
    "command_text",
    ["/replay", "/replay synthetic-unknown", "/replay synthetic-referral-01 extra"],
)
def test_replay_command_rejects_missing_or_unregistered_fixture_ids(command_text, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "replay")
    store = _registered_replay_store()
    before = store._connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    result = OfflineTelegramAdapter(trace_store=store).handle_update(update(text=command_text))
    assert result.status == "command_error"
    assert result.reason == "replay_fixture_unavailable"
    assert result.reply == "That offline replay fixture is not available."
    assert store._connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == before


def test_replay_command_fails_closed_for_missing_or_corrupt_cache(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "replay")
    store = TraceStore(":memory:")
    adapter = OfflineTelegramAdapter(trace_store=store)
    missing = adapter.handle_update(update(text="/replay synthetic-referral-01"))
    assert missing.status == "command_error"

    key = registered_demo_cache_key("synthetic-referral-01")
    store.put_cache(
        key,
        {"schema": CACHE_SCHEMA, "provenance": CACHE_PROVENANCE,
         "status": "referred", "response_code": "safe_referral"},
    )
    store._connection.execute(
        'UPDATE cache SET response_json=? WHERE "key"=?', ("{bad", key)
    )
    store._connection.commit()
    corrupt = adapter.handle_update(update(text="/replay synthetic-referral-01"))
    assert corrupt.status == "command_error"
    assert corrupt.reason == missing.reason == "replay_fixture_unavailable"


def test_replay_command_never_falls_through_when_mode_is_live_or_store_missing(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "live")
    with_store = OfflineTelegramAdapter(trace_store=_registered_replay_store())
    disabled = with_store.handle_update(update(text="/replay synthetic-referral-01"))
    no_store = OfflineTelegramAdapter().handle_update(
        update(text="/replay synthetic-referral-01")
    )
    assert disabled.status == no_store.status == "command_error"
    assert disabled.reason == no_store.reason == "replay_fixture_unavailable"


def test_replay_command_does_not_return_response_if_trace_write_fails(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "replay")
    store = _registered_replay_store()

    def fail_trace(*args, **kwargs):
        raise TraceError("trace unavailable")

    monkeypatch.setattr(store, "record_case", fail_trace)
    result = OfflineTelegramAdapter(trace_store=store).handle_update(
        update(text="/replay synthetic-referral-01")
    )
    assert result.status == "command_error"
    assert result.reply == "That offline replay fixture is not available."


def test_replay_command_is_network_isolated_and_does_not_send_by_default(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("replay caller must not use network sockets")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setenv("DEMO_MODE", "replay")
    transport = FakeTelegramTransport()
    adapter = OfflineTelegramAdapter(
        trace_store=_registered_replay_store(), transport=transport
    )
    result = adapter.handle_update(update(text="/replay synthetic-referral-01"))
    assert result.status == "replayed"
    assert transport.messages == []
