"""Offline-only tests for the B9 case/step persistence boundary."""

from decimal import Decimal

import pytest

from mydrak.trace.store import TraceCase, TraceError, TraceStep, TraceStore, estimate_token_cost


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
    assert [step["step_name"] for step in store.get_steps("00000000000000000000000000000001")] == [
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
