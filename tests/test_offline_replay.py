"""Offline-only regression tests for T15 replay and SQLite backup."""

import json
import socket
from dataclasses import replace

import pytest

from mydrak.kb.loader import load_safety_card
from mydrak.privacy.data_policy import DataClass, ProcessingEvidence, ProviderMode
from mydrak.replay import (
    OfflineReplayFixture,
    ReplayError,
    ReplayResult,
    cache_replay_result,
    demo_cache_key,
    run_cached_replay,
    run_replay,
)
from mydrak.trace.store import (
    CACHE_PROVENANCE,
    CACHE_SCHEMA,
    TraceCase,
    TraceError,
    TraceStep,
    TraceStore,
)
from mydrak.util.config import DemoMode, load_demo_mode, parse_demo_mode
from mydrak.workflow.coordinator import (
    OfflineCoordinationResult,
    SYNTHETIC_FIXTURE_PROVENANCE,
    SyntheticSamReplyFixture,
)

from conftest import REPO_ROOT


SAFETY = load_safety_card(REPO_ROOT / "kb" / "cards" / "general_safety.yaml")
EVIDENCE = ProcessingEvidence(
    provider_mode=ProviderMode.STANDARD,
    provider_mode_verified=True,
    rights_confirmed=True,
    public_test_provenance_verified=True,
)


def _fixture(reply_text=""):
    envelope = json.dumps({
        "output": [{"type": "message", "content": [{"type": "output_text", "text": reply_text}]}]
    })
    return OfflineReplayFixture(
        image_descriptor={"format": "jpeg", "width": 100, "height": 80, "size_bytes": 1024},
        sam_fixture=SyntheticSamReplyFixture(envelope, SYNTHETIC_FIXTURE_PROVENANCE),
        safety_card=SAFETY,
        data_policy_value="public_test",
        data_class=DataClass.PUBLIC_TEST,
        evidence=EVIDENCE,
        provenance="synthetic-offline-replay-fixture",
    )


def test_replay_runs_existing_workflow_without_network_primitives(monkeypatch):
    def deny_socket(*args, **kwargs):
        raise AssertionError("replay must not open a network socket")

    monkeypatch.setattr(socket, "socket", deny_socket)
    monkeypatch.setattr(socket, "create_connection", deny_socket)
    store = TraceStore(":memory:")
    first = run_replay(_fixture(), trace_store=store)
    second = run_replay(_fixture(), trace_store=store)
    assert first.provenance == "synthetic-offline-replay-fixture"
    assert first.result.status == second.result.status == "referred"
    assert first.result.reason == second.result.reason
    assert first.result.reply == second.result.reply
    assert store.get_case(first.result.case_id) is not None
    assert store.get_steps(first.result.case_id)


@pytest.mark.parametrize("fixture", [None, object()])
def test_replay_rejects_non_fixture_inputs(fixture):
    with pytest.raises(ReplayError):
        run_replay(fixture, trace_store=TraceStore(":memory:"))


def test_replay_rejects_unverified_provenance_before_recording():
    store = TraceStore(":memory:")
    fixture = _fixture()
    fixture = OfflineReplayFixture(
        fixture.image_descriptor,
        fixture.sam_fixture,
        fixture.safety_card,
        fixture.data_policy_value,
        fixture.data_class,
        fixture.evidence,
        fixture.language,
        "unverified",
    )
    with pytest.raises(ReplayError, match="provenance"):
        run_replay(fixture, trace_store=store)
    assert store._connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 0


def test_replay_wraps_invalid_workflow_input_without_recording():
    store = TraceStore(":memory:")
    fixture = replace(_fixture(), image_descriptor={
        "format": "webp", "width": 100, "height": 80, "size_bytes": 1024,
    })
    with pytest.raises(ReplayError, match="rejected"):
        run_replay(fixture, trace_store=store)
    assert store._connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 0


def test_replay_preserves_policy_block_as_a_traceable_outcome():
    store = TraceStore(":memory:")
    fixture = _fixture()
    blocked = OfflineReplayFixture(
        fixture.image_descriptor,
        fixture.sam_fixture,
        fixture.safety_card,
        "private",
        DataClass.PRIVATE,
        None,
        "en",
        "synthetic-offline-replay-fixture",
    )
    result = run_replay(blocked, trace_store=store).result
    assert result.status == "blocked"
    assert result.reply is None
    assert store.get_case(result.case_id)["final_action"] == "blocked"


def test_sqlite_backup_contains_cases_steps_and_scans(tmp_path):
    source_path = tmp_path / "source.sqlite"
    backup_path = tmp_path / "backup.sqlite"
    store = TraceStore(source_path)
    case_id = "000000000000000000000000000000ab"
    store.record_case(
        TraceCase(case_id, "referred", "en", "photo", "private"),
        [TraceStep("replay", "completed", 1.0)],
    )
    store.record_signals(
        case_id, s1=None, s2=None, s3=None, s4=None, score=None,
        decision="refer", escalated=False,
    )
    cache_key = "9" * 64
    store.put_cache(cache_key, _cache_payload(), timestamp="2026-01-02T03:04:05Z")
    backup = store.backup_to(backup_path)
    assert backup == backup_path
    copied = TraceStore(backup_path)
    assert copied.get_case(case_id)["final_action"] == "referred"
    assert copied.get_steps(case_id)[0]["step_name"] == "replay"
    assert copied._connection.execute("SELECT COUNT(*) FROM scans").fetchone()[0] == 0
    assert copied.get_cache(cache_key).response_code == "safe_referral"
    assert copied.get_signals(case_id)["decision"] == "refer"


def test_backup_refuses_existing_destination_without_overwriting(tmp_path):
    store = TraceStore(":memory:")
    destination = tmp_path / "already-there.db"
    destination.write_bytes(b"preserve existing file")
    with pytest.raises(TraceError, match="backup destination"):
        store.backup_to(destination)
    assert destination.read_bytes() == b"preserve existing file"


def test_backup_refuses_open_database_as_its_own_destination(tmp_path):
    database = tmp_path / "source.db"
    store = TraceStore(database)
    with pytest.raises(TraceError, match="differ"):
        store.backup_to(database)


def _cache_payload(status="referred", response_code="safe_referral"):
    return {
        "schema": CACHE_SCHEMA,
        "provenance": CACHE_PROVENANCE,
        "status": status,
        "response_code": response_code,
    }


def test_cache_insert_read_and_replay_are_repeatable_and_synthetic():
    store = TraceStore(":memory:")
    key = demo_cache_key("synthetic-referral-01")
    fixture_result = run_replay(_fixture(), trace_store=store)
    inserted = cache_replay_result(
        key, fixture_result, trace_store=store, timestamp="2026-01-02T03:04:05Z"
    )
    assert inserted.status == "referred"
    assert inserted.response_code == "safe_referral"
    assert inserted.timestamp == "2026-01-02T03:04:05.000000Z"

    first = run_cached_replay(key, trace_store=store, demo_mode="replay")
    second = run_cached_replay(key, trace_store=store, demo_mode=DemoMode.REPLAY)
    assert first == second
    assert first.provenance == "synthetic-offline-demo"
    assert "synthetic demo only" in first.reply
    assert "cannot tell" in first.reply
    assert store.get_cache(key).response_code == "safe_referral"


def test_cached_replay_missing_key_fails_closed():
    with pytest.raises(ReplayError, match="unavailable"):
        run_cached_replay("a" * 64, trace_store=TraceStore(":memory:"), demo_mode="replay")


@pytest.mark.parametrize("mode", ["live", "", "unexpected", True])
def test_cached_replay_rejects_disabled_or_invalid_modes(mode):
    store = TraceStore(":memory:")
    with pytest.raises(ReplayError, match="DEMO_MODE"):
        run_cached_replay("a" * 64, trace_store=store, demo_mode=mode)


def test_demo_mode_loader_is_fail_closed_and_does_not_load_dotenv():
    assert parse_demo_mode() is DemoMode.REPLAY
    assert load_demo_mode({"DEMO_MODE": "replay"}) is DemoMode.REPLAY
    with pytest.raises(ValueError, match="disabled"):
        load_demo_mode({"DEMO_MODE": "live"})
    with pytest.raises(ValueError, match="must be"):
        load_demo_mode({"DEMO_MODE": "Replay"})


def test_cached_replay_uses_validated_process_mode(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "live")
    with pytest.raises(ReplayError, match="live mode is disabled"):
        run_cached_replay("2" * 64, trace_store=TraceStore(":memory:"))
    monkeypatch.setenv("DEMO_MODE", "replay")
    store = TraceStore(":memory:")
    store.put_cache("2" * 64, _cache_payload())
    assert run_cached_replay("2" * 64, trace_store=store).provenance == "synthetic-offline-demo"


@pytest.mark.parametrize(
    "key", ["raw-fixture-id", "A" * 64, "a" * 63, "g" * 64, None]
)
def test_cache_keys_must_be_lowercase_sha256(key):
    with pytest.raises(TraceError, match="SHA-256"):
        TraceStore(":memory:").get_cache(key)


@pytest.mark.parametrize(
    "payload",
    [
        {**_cache_payload(), "reply": "unapproved free text"},
        {**_cache_payload(), "raw_image": "not allowed"},
        {**_cache_payload(), "user_id": "not allowed"},
        {**_cache_payload(), "findings": "unvalidated"},
        {**_cache_payload(), "provenance": "provider"},
        {**_cache_payload(), "status": "answer", "response_code": "diagnosis"},
        {**_cache_payload(), "status": []},
        {"schema": CACHE_SCHEMA},
    ],
)
def test_cache_rejects_unknown_malformed_or_unapproved_payloads(payload):
    with pytest.raises(TraceError):
        TraceStore(":memory:").put_cache("b" * 64, payload)


@pytest.mark.parametrize("timestamp", ["2026-01-02T03:04:05", "not-a-time", "x" * 65])
def test_cache_timestamp_requires_bounded_timezone_qualified_iso(timestamp):
    with pytest.raises(TraceError, match="timestamp"):
        TraceStore(":memory:").put_cache("c" * 64, _cache_payload(), timestamp=timestamp)


def test_cache_generates_timezone_qualified_timestamp_when_omitted():
    stored = TraceStore(":memory:").put_cache("c" * 64, _cache_payload())
    assert stored.timestamp.endswith("Z")


def test_duplicate_cache_key_cannot_overwrite_existing_entry():
    store = TraceStore(":memory:")
    key = "d" * 64
    original = store.put_cache(key, _cache_payload(), timestamp="2026-01-02T03:04:05Z")
    with pytest.raises(TraceError, match="already exists"):
        store.put_cache(
            key,
            _cache_payload("manual_review", "manual_review"),
            timestamp="2027-01-02T03:04:05Z",
        )
    assert store.get_cache(key) == original


@pytest.mark.parametrize(
    "raw, timestamp",
    [
        ('{"schema":"mydrak-demo-response-v1","schema":"mydrak-demo-response-v1"}', "2026-01-02T03:04:05.000000Z"),
        ("{malformed", "2026-01-02T03:04:05.000000Z"),
        ("x" * 513, "2026-01-02T03:04:05.000000Z"),
        (json.dumps(_cache_payload()), "not-a-timestamp"),
    ],
)
def test_corrupt_or_oversized_persisted_cache_rows_fail_closed(raw, timestamp):
    store = TraceStore(":memory:")
    key = "e" * 64
    store.put_cache(key, _cache_payload())
    store._connection.execute(
        'UPDATE cache SET response_json=?, ts=? WHERE "key"=?', (raw, timestamp, key)
    )
    store._connection.commit()
    with pytest.raises(TraceError):
        store.get_cache(key)
    with pytest.raises(ReplayError):
        run_cached_replay(key, trace_store=store, demo_mode="replay")


def test_cache_write_requires_a_replayed_and_traceable_synthetic_result():
    store = TraceStore(":memory:")
    result = run_replay(_fixture(), trace_store=store)
    with pytest.raises(ReplayError, match="synthetic"):
        cache_replay_result("f" * 64, replace(result, provenance="provider"), trace_store=store)
    assert store.get_cache("f" * 64) is None


@pytest.mark.parametrize(
    "status,reason,response_code",
    [
        ("blocked", "intake_policy_denied", "policy_blocked"),
        ("referred", "no_sam_detections_not_a_health_finding", "safe_referral"),
        ("manual_review", "sam_outcome_requires_manual_review", "manual_review"),
    ],
)
def test_cache_maps_only_the_three_synthetic_offline_outcomes(status, reason, response_code):
    store = TraceStore(":memory:")
    case_id = "000000000000000000000000000000cd"
    store.record_case(
        TraceCase(case_id, status, "en", "photo", "private"),
        [TraceStep("replay", "completed", 0.0)],
    )
    result = ReplayResult(OfflineCoordinationResult(status, None, reason, case_id))
    key = "7" * 64
    cached = cache_replay_result(key, result, trace_store=store)
    assert cached.response_code == response_code
    assert run_cached_replay(key, trace_store=store, demo_mode="replay").response_code == response_code


def test_cached_replay_never_calls_workflow_or_network(monkeypatch):
    import mydrak.replay.replay as replay_module

    def deny(*args, **kwargs):
        raise AssertionError("cached replay must not run workflow or access network")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(replay_module, "coordinate_offline_case", deny)
    store = TraceStore(":memory:")
    key = "1" * 64
    store.put_cache(key, _cache_payload())
    assert run_cached_replay(key, trace_store=store, demo_mode="replay").status == "referred"


def test_cached_replay_rejects_unavailable_language_and_bad_fixture_key():
    store = TraceStore(":memory:")
    key = demo_cache_key("safe-demo")
    store.put_cache(key, _cache_payload())
    with pytest.raises(ReplayError, match="language"):
        run_cached_replay(key, trace_store=store, demo_mode="replay", language="hi")
    with pytest.raises(ReplayError, match="fixture ID"):
        demo_cache_key("../user/identifier")
