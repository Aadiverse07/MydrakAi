"""B11 failure injection with deterministic synthetic providers only."""

from hashlib import sha256
from io import BytesIO
from PIL import Image
import pytest

from mydrak.bot.adapter import (
    FakeTelegramTransport, OfflineTelegramAdapter, OfflineUpdate,
)
from mydrak.privacy.data_policy import ProcessingEvidence, ProviderMode
from mydrak.trace.store import TraceStore
from mydrak.workflow.mock_providers import (
    DeterministicMockDiagnosisProvider, DeterministicMockSamProvider,
    DeterministicMockTranscriber,
)
from mydrak.workflow.pipeline import TestOnlySignalOverride, run_synthetic_mock_workflow
import mydrak.workflow.pipeline_support as support


EVIDENCE = ProcessingEvidence(
    provider_mode=ProviderMode.STANDARD, provider_mode_verified=True,
    rights_confirmed=True, public_test_provenance_verified=True,
)


def _photo():
    output = BytesIO()
    Image.new("RGB", (28, 20), (40, 145, 50)).save(output, format="PNG")
    return output.getvalue()


def _diagnosis(*, plant=True, crop="synthetic_crop"):
    return {
        "plant_visible": plant,
        "crop": crop if plant else "unknown",
        "issue": "SYNTHETIC_TEST" if plant else "unknown",
        "alternatives": [],
        "symptoms_observed": ["Synthetic placeholder symptom"] if plant else [],
        "image_issues": [],
        "stated_confidence": 0.8,
        "segment_prompts": ["synthetic prompt"] if plant else [],
    }


def _run(glimmer, spark=None, sam=None, *, override=None, store=None):
    return run_synthetic_mock_workflow(
        _photo(), "en", glimmer_provider=glimmer,
        spark_provider=spark or DeterministicMockDiagnosisProvider((_diagnosis(),)),
        sam_provider=sam or DeterministicMockSamProvider(("11",), ("10",)),
        trace_store=store or TraceStore(":memory:"),
        data_policy_value="public_test", evidence=EVIDENCE,
        signal_override=override,
    )


def _rows(store, case_id):
    return store.get_case(case_id), store.get_steps(case_id), store.get_signals(case_id)


def test_provider_timeout_uses_two_backoff_retries_then_traced_spark_fallback(monkeypatch):
    waits = []
    monkeypatch.setattr(support.time, "sleep", waits.append)
    glimmer = DeterministicMockDiagnosisProvider(
        (_diagnosis(), _diagnosis()), timeout_calls=frozenset({0, 1, 2}),
    )
    store = TraceStore(":memory:")
    result = _run(glimmer, store=store)
    case, steps, signals = _rows(store, result.case_id)
    first = next(step for step in steps if step["step_name"] == "glimmer_sample_1")
    assert glimmer.generate_calls == 3 and waits == [0.01, 0.02]
    assert first["retries"] == 2 and first["error"] == "provider_failure"
    assert result.action == "refer" and result.spark_escalations == 1
    assert signals["decision"] == "refer" and case["est_cost"] is None


def test_glimmer_unavailable_skips_second_sample_and_attempts_one_spark_escalation(monkeypatch):
    monkeypatch.setattr(support.time, "sleep", lambda _: None)
    glimmer = DeterministicMockDiagnosisProvider(
        (_diagnosis(),), fail_calls=frozenset({0, 1, 2}),
    )
    spark = DeterministicMockDiagnosisProvider((_diagnosis(),))
    store = TraceStore(":memory:")
    result = _run(glimmer, spark, store=store)
    _, steps, signals = _rows(store, result.case_id)
    assert result.action == "refer" and result.spark_escalations == 1
    assert glimmer.generate_calls == 3 and spark.generate_calls == 1
    assert "glimmer_sample_2" not in {step["step_name"] for step in steps}
    assert signals["escalated"] == 1


def test_spark_unavailable_falls_back_to_tier1_referral_with_uncertainty(monkeypatch):
    monkeypatch.setattr(support.time, "sleep", lambda _: None)
    glimmer = DeterministicMockDiagnosisProvider((_diagnosis(), _diagnosis()))
    spark = DeterministicMockDiagnosisProvider(
        (_diagnosis(),), timeout_calls=frozenset({0, 1, 2}),
    )
    store = TraceStore(":memory:")
    result = _run(
        glimmer, spark, override=TestOnlySignalOverride(s2=0.0, s3=1.0, s4=0.0),
        store=store,
    )
    _, steps, signals = _rows(store, result.case_id)
    assert result.action == "refer" and result.spark_escalations == 1
    assert spark.generate_calls == 3
    assert "cannot tell" in result.reply and "Safety:" in result.reply
    spark_step = next(step for step in steps if step["step_name"] == "spark_escalation")
    assert spark_step["retries"] == 2 and signals["decision"] == "refer"


@pytest.mark.parametrize("mode", ["failed", "empty"])
def test_sam_failure_or_empty_masks_never_returns_severity_and_is_traced(mode):
    glimmer = DeterministicMockDiagnosisProvider((_diagnosis(), _diagnosis()))
    sam = DeterministicMockSamProvider(
        ("00",) if mode == "empty" else ("11",),
        ("00",) if mode == "empty" else ("10",),
        fail=mode == "failed",
    )
    store = TraceStore(":memory:")
    result = _run(
        glimmer, sam=sam,
        override=TestOnlySignalOverride(s2=1.0, s3=1.0, s4=1.0, confidence_word="fairly sure"),
        store=store,
    )
    case, steps, signals = _rows(store, result.case_id)
    assert result.action == "answer" and result.severity_pct is None and result.overlay_bytes is None
    assert "SAM overlay and severity are unavailable" in result.reply
    assert case["case_id"] and signals["decision"] == "answer"
    assert "severity_overlay" in {step["step_name"] for step in steps}


def test_invalid_json_gets_one_repair_then_unknown_and_safe_trace():
    glimmer = DeterministicMockDiagnosisProvider(("{invalid",), repair_output="still invalid")
    store = TraceStore(":memory:")
    result = _run(glimmer, store=store)
    case, steps, signals = _rows(store, result.case_id)
    assert glimmer.generate_calls == glimmer.repair_calls == 1
    assert result.action == signals["decision"] == "refer"
    assert "No diagnosis was made" in result.reply
    assert case is not None and "glimmer_sample_1" in {step["step_name"] for step in steps}


@pytest.mark.parametrize(
    "output",
    [
        _diagnosis(plant=False),
        _diagnosis(crop="unsupported_crop"),
    ],
)
def test_nonplant_or_unsupported_crop_is_not_diagnosed_and_is_traced(output):
    glimmer = DeterministicMockDiagnosisProvider((output, _diagnosis()))
    store = TraceStore(":memory:")
    result = _run(glimmer, store=store)
    case, steps, signals = _rows(store, result.case_id)
    assert result.action == signals["decision"] == "refer"
    assert "could not be confirmed as a supported plant" in result.reply
    assert "No diagnosis was made" in result.reply
    assert case is not None and steps
    assert glimmer.repair_calls == (1 if output["crop"] == "unsupported_crop" else 0)


def test_transcription_failure_asks_for_resend_and_traces_only_hashed_identity():
    store = TraceStore(":memory:")
    transcriber = DeterministicMockTranscriber(fail=True)
    adapter = OfflineTelegramAdapter(trace_store=store, transcriber=transcriber)
    adapter.handle_update(OfflineUpdate("synthetic-chat-key", "command", "/start"))
    result = adapter.handle_update(OfflineUpdate("synthetic-chat-key", "voice"))
    assert result.status == "deferred" and result.reason == "transcription_failed"
    assert "resend the voice note or type a short note" in result.reply
    assert transcriber.calls == 1
    row = store._connection.execute("SELECT * FROM cases").fetchone()
    assert row["final_action"] == "ask" and row["input_type"] == "voice"
    assert row["user_hash"] == sha256(b"synthetic-chat-key").hexdigest()
    assert "synthetic-chat-key" not in repr(store.get_case(row["case_id"]))
    assert store.get_signals(row["case_id"])["decision"] == "ask"


@pytest.mark.parametrize("failures,expected_retries,delivered", [(1, 1, True), (3, 2, False)])
def test_telegram_fake_send_retries_at_most_twice_and_traces_failure(
    failures, expected_retries, delivered, monkeypatch,
):
    from mydrak.bot import failure_support

    waits = []
    monkeypatch.setattr(failure_support.time, "sleep", waits.append)
    store = TraceStore(":memory:")
    transport = FakeTelegramTransport(failures_remaining=failures)
    adapter = OfflineTelegramAdapter(
        transport=transport, outbound_enabled=True, trace_store=store,
    )
    result = adapter.handle_update(OfflineUpdate("synthetic-chat", "command", "/start"))
    assert transport.send_calls == failures + (1 if delivered else 0)
    assert (len(transport.messages) == 1) is delivered
    assert result.reason == ("start_offline_session" if delivered else "telegram_send_failed")
    row = store._connection.execute("SELECT * FROM cases").fetchone()
    steps = store.get_steps(row["case_id"])
    assert row["user_hash"] == sha256(b"synthetic-chat").hexdigest()
    assert steps[0]["step_name"] == "telegram_send"
    assert steps[0]["retries"] == expected_retries
    assert steps[0]["error"] == "telegram_send_failure"
    assert len(waits) == expected_retries
    assert store.get_signals(row["case_id"])["decision"] == "refer"
