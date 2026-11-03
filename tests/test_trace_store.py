"""Offline-only tests for the B9 case/step persistence boundary."""

from decimal import Decimal
import json
import sqlite3

import pytest

from mydrak.trace.store import (
    TraceCase, TraceError, TraceStep, TraceStore,
    WORKFLOW_CACHE_PROVENANCE, WORKFLOW_CACHE_SCHEMA, estimate_token_cost,
)


def _case(case_id="00000000000000000000000000000001"):
    return TraceCase(
        case_id=case_id,
        final_action="manual_review",
        lang="en",
        input_type="photo",
        data_policy="public_test",
    )


def test_case_and_steps_are_persisted_atomically_with_total_latency_and_unknown_cost():
    store = TraceStore(":memory:")
    steps = [
        TraceStep("intake_validate", "completed", 1.25),
        TraceStep("offline_sam", "manual_review", 2.75),
    ]
    store.record_case(_case(), steps)
    case = store.get_case("00000000000000000000000000000001")
    assert case["latency_ms_total"] == pytest.approx(4.0)
    assert case["est_cost"] is None
    stored_steps = store.get_steps("00000000000000000000000000000001")
    assert all(step["started_at"] for step in stored_steps)
    assert all(step["tokens_in"] is None and step["tokens_out"] is None for step in stored_steps)
    assert [step["step_name"] for step in stored_steps] == [
        "intake_validate", "offline_sam"
    ]


def test_invalid_step_does_not_leave_partial_case_record():
    store = TraceStore(":memory:")
    with pytest.raises(TraceError):
        store.record_case(_case(), [TraceStep("ok", "completed", 1), object()])
    assert store.get_case("00000000000000000000000000000001") is None
    assert store.get_steps("00000000000000000000000000000001") == []


def test_token_cost_uses_configured_rates_and_unknown_placeholder_is_null():
    assert estimate_token_cost(1000, 500, 2, 4) == Decimal("0.004")
    assert estimate_token_cost(1000, 500, "TODO(verify)", 4) is None
    assert estimate_token_cost(1000, 500, None, 4) is None


@pytest.mark.parametrize("tokens", [-1, True, 1.5])
def test_token_cost_rejects_invalid_counts(tokens):
    with pytest.raises(TraceError):
        estimate_token_cost(tokens, 0, 1, 1)


@pytest.mark.parametrize("unsafe", ["raw-user-text", "not-a-hash", "A" * 12])
def test_trace_rejects_unhashed_identity_values(unsafe):
    store = TraceStore(":memory:")
    case = TraceCase(
        case_id="safe-id",
        final_action="referred",
        lang="en",
        input_type="photo",
        data_policy="private",
        user_hash=unsafe,
    )
    with pytest.raises(TraceError):
        store.record_case(case, [TraceStep("workflow", "completed", 0)])


def test_verified_zero_cost_is_distinct_from_unknown_cost():
    store = TraceStore(":memory:")
    step = TraceStep("offline", "completed", 0, est_cost=Decimal(0))
    store.record_case(_case("00000000000000000000000000000002"), [step])
    assert store.get_case("00000000000000000000000000000002")["est_cost"] == "0"


def test_b9_signal_row_persists_normalized_values_for_an_existing_case():
    store = TraceStore(":memory:")
    case_id = "00000000000000000000000000000003"
    store.record_case(_case(case_id), [TraceStep("decider", "completed", 1.0)])
    store.record_signals(
        case_id, s1=1.0, s2=0.0, s3=0.75, s4=0.8,
        score=0.6375, decision="escalate", escalated=False,
    )
    assert store.get_signals(case_id) == {
        "case_id": case_id, "s1": 1.0, "s2": 0.0, "s3": 0.75,
        "s4": 0.8, "score": 0.6375, "decision": "escalate", "escalated": 0,
    }


def test_b9_signal_row_accepts_null_for_unavailable_measurements():
    store = TraceStore(":memory:")
    case_id = "00000000000000000000000000000004"
    store.record_case(_case(case_id), [TraceStep("decider", "completed", 0.0)])
    store.record_signals(
        case_id, s1=1.0, s2=None, s3=None, s4=None,
        score=None, decision="refer", escalated=False,
    )
    row = store.get_signals(case_id)
    assert row["s1"] == 1.0
    assert row["s2"] is row["s3"] is row["s4"] is row["score"] is None
    assert row["decision"] == "refer"


@pytest.mark.parametrize(
    "values",
    [
        {"s1": True}, {"s2": -0.1}, {"s3": 1.1}, {"s4": float("nan")},
        {"score": float("inf")}, {"decision": []}, {"escalated": 1},
    ],
)
def test_b9_signal_row_rejects_invalid_values(values):
    store = TraceStore(":memory:")
    case_id = "00000000000000000000000000000005"
    store.record_case(_case(case_id), [TraceStep("decider", "completed", 0.0)])
    args = {
        "s1": 0.5, "s2": 0.5, "s3": 0.5, "s4": 0.5,
        "score": 0.5, "decision": "ask", "escalated": True,
    }
    args.update(values)
    with pytest.raises(TraceError):
        store.record_signals(case_id, **args)
    assert store.get_signals(case_id) is None


def test_b9_signal_row_requires_existing_case_and_rejects_duplicate():
    store = TraceStore(":memory:")
    args = dict(s1=None, s2=None, s3=None, s4=None, score=None,
                decision="refer", escalated=False)
    with pytest.raises(TraceError, match="no case"):
        store.record_signals("00000000000000000000000000000006", **args)
    case_id = "00000000000000000000000000000007"
    store.record_case(_case(case_id), [TraceStep("decider", "completed", 0.0)])
    store.record_signals(case_id, **args)
    with pytest.raises(TraceError, match="duplicate"):
        store.record_signals(case_id, **args)


def test_t04_image_measurements_are_separate_validated_observations():
    store = TraceStore(":memory:")
    case_id = "00000000000000000000000000000091"
    store.record_case(_case(case_id), [TraceStep("preprocess", "completed", 0.0)])
    store.record_image_measurements(
        case_id, laplacian_variance=12.5, mean_brightness=123.0,
        leaf_coverage_fraction=0.25,
        leaf_coverage_method="unverified_green_hue_pixel_proxy",
    )
    assert store.get_image_measurements(case_id)["leaf_coverage_fraction"] == 0.25
    assert store.get_signals(case_id) is None
    assert store.get_case(case_id)["quality_scores"] is None
    with pytest.raises(TraceError):
        store.record_image_measurements(
            case_id, laplacian_variance=12.5, mean_brightness=123.0,
            leaf_coverage_fraction=0.25,
            leaf_coverage_method="unverified_green_hue_pixel_proxy",
        )


@pytest.mark.parametrize(
    "values",
    [
        (float("nan"), 1.0, 0.5), (1.0, float("inf"), 0.5),
        (1.0, 1.0, 1.1), (-1.0, 1.0, 0.5), (1.0, 256.0, 0.5),
        (True, 1.0, 0.5), (10**1000, 1.0, 0.5),
    ],
)
def test_t04_image_measurements_reject_invalid_numbers(values):
    store = TraceStore(":memory:")
    with pytest.raises(TraceError):
        store.record_image_measurements(
            "00000000000000000000000000000092",
            laplacian_variance=values[0], mean_brightness=values[1],
            leaf_coverage_fraction=values[2],
            leaf_coverage_method="unverified_green_hue_pixel_proxy",
        )


def test_eval_runs_table_and_round_trip_are_created_in_shared_store():
    store = TraceStore(":memory:")
    tables = {row[0] for row in store._connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert {"cases", "steps", "signals", "scans", "cache", "eval_runs"} <= tables
    run = store.record_eval_run(
        run_id="a" * 32, strategy="router", git_sha="b" * 40,
        metrics={"accuracy": None, "cost_per_task": None},
        timestamp="2026-10-30T12:00:00Z",
    )
    assert store.get_eval_run("a" * 32) == run
    assert json.loads(run.metrics_json)["cost_per_task"] is None
    with pytest.raises(TraceError, match="already exists"):
        store.record_eval_run(run_id="a" * 32, strategy="router", git_sha=None, metrics={"x": 1})


def test_workflow_cache_payload_is_synthetic_and_excludes_media_and_overlay_bytes():
    store = TraceStore(":memory:")
    key = "f" * 64
    payload = {
        "schema": WORKFLOW_CACHE_SCHEMA,
        "provenance": WORKFLOW_CACHE_PROVENANCE,
        "action": "answer",
        "reason": "decider_answer",
        "reply": "SYNTHETIC / MOCK — preliminary guidance. Safe test reply.",
        "severity_pct": 25.0,
        "severity_band": "moderate",
    }
    cached = store.put_cache(key, payload)
    assert cached.provenance == WORKFLOW_CACHE_PROVENANCE
    assert cached.reply == payload["reply"] and cached.severity_pct == 25.0
    raw = store._connection.execute('SELECT response_json FROM cache WHERE "key"=?', (key,)).fetchone()[0]
    assert json.loads(raw)["provenance"] == WORKFLOW_CACHE_PROVENANCE
    assert "image_bytes" not in raw and "overlay_bytes" not in raw
    with pytest.raises(TraceError):
        store.put_cache("e" * 64, {**payload, "overlay_bytes": "not permitted"})


def test_legacy_database_migrates_started_at_without_losing_existing_rows(tmp_path):
    database = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(database)
    connection.executescript("""
        CREATE TABLE cases (
            case_id TEXT PRIMARY KEY, ts TEXT, user_hash TEXT, lang TEXT NOT NULL,
            input_type TEXT NOT NULL, image_hash TEXT, quality_scores TEXT,
            final_action TEXT NOT NULL, kb_card_id TEXT, severity_pct REAL,
            latency_ms_total REAL NOT NULL, est_cost TEXT, data_policy TEXT
        );
        CREATE TABLE steps (
            case_id TEXT NOT NULL, ordinal INTEGER NOT NULL, step_name TEXT NOT NULL,
            model TEXT, latency_ms REAL NOT NULL, tokens_in INTEGER, tokens_out INTEGER,
            est_cost TEXT, error TEXT, retries INTEGER NOT NULL, outcome TEXT NOT NULL,
            PRIMARY KEY(case_id, ordinal)
        );
        INSERT INTO cases(case_id,lang,input_type,final_action,latency_ms_total)
          VALUES('000000000000000000000000000000aa','en','photo','refer',1.0);
        INSERT INTO steps(case_id,ordinal,step_name,latency_ms,retries,outcome)
          VALUES('000000000000000000000000000000aa',0,'legacy',1.0,0,'completed');
    """)
    connection.commit()
    connection.close()
    store = TraceStore(database)
    assert store.get_case("000000000000000000000000000000aa") is not None
    assert store.get_steps("000000000000000000000000000000aa")[0]["started_at"] is None
    store.record_case(
        _case("000000000000000000000000000000ab"),
        [TraceStep("new_step", "completed", 0.5)],
    )
    assert store.get_steps("000000000000000000000000000000ab")[0]["started_at"]
