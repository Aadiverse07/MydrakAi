"""Synthetic-only B3 signal extraction and routing contract tests.

Policy fixture numbers below are test inputs, not measurements or tuned
agronomic thresholds.
"""

import math

import pytest

from mydrak.decider.extraction import (
    SignalMeasurement,
    SignalSet,
    extract_agreement,
    extract_confidence,
    extract_kb_match,
    extract_quality,
    route_signals,
    unavailable,
)
from mydrak.decider.policy import decide
from mydrak.decider.signals import combine
from mydrak.trace.store import TraceCase, TraceError, TraceStep, TraceStore


WEIGHTS = {
    "s1_agreement": 0.25,
    "s2_kb_match": 0.25,
    "s3_quality": 0.25,
    "s4_stated_confidence": 0.25,
}
TEST_THRESHOLDS = {"accept": 0.7, "agree_min": 0.5, "quality_min": 0.4, "max_followups": 2}


def _policy_fixture(s1=0.5, s2=0.5, s3=0.9, s4=0.5):
    """Synthetic values solely to exercise combination and routing branches."""
    return SignalSet(*(SignalMeasurement(v, "synthetic-test-input") for v in (s1, s2, s3, s4)))


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ({"crop": "tomato", "disease": "issue-a"}, {"crop": " TOMATO ", "disease": "ISSUE-A"}, 1.0),
        ({"crop": "tomato", "disease": "issue-a"}, {"crop": "tomato", "disease": "issue-b"}, 0.5),
        ({"crop": "tomato", "disease": "issue-a"}, {"crop": "potato", "disease": "issue-a"}, 0.0),
    ],
)
def test_s1_agreement_formula(first, second, expected):
    assert extract_agreement(first, second).value == expected


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (None, {"crop": "crop", "disease": "issue"}),
        ({"crop": "crop"}, {"crop": "crop", "disease": "issue"}),
        ({"crop": True, "disease": "issue"}, {"crop": "crop", "disease": "issue"}),
        ({"crop": "crop", "disease": ""}, {"crop": "crop", "disease": "issue"}),
    ],
)
def test_s1_missing_or_malformed_samples_are_unavailable(first, second):
    result = extract_agreement(first, second)
    assert result.value is None
    assert result.reason


def test_s2_only_explicit_no_card_case_is_zero():
    assert extract_kb_match("unknown-label", []).value == 0.0
    assert extract_kb_match("issue-a", [{"id": "other"}]).value == 0.0


def test_s2_matching_card_stays_unavailable_until_overlap_contract_is_defined():
    result = extract_kb_match("issue-a", [{"id": "issue-a", "symptoms": ["synthetic"]}])
    assert result.value is None
    assert result.reason == "symptom_overlap_contract_unresolved"


@pytest.mark.parametrize(
    ("label", "cards"),
    [
        (None, []),
        ("label", None),
        ("label", [None]),
        ("label", [{"symptoms": ["missing id"]}]),
        ("label", [{"id": "duplicate"}, {"id": "duplicate"}]),
    ],
)
def test_s2_malformed_or_missing_evidence_is_unavailable(label, cards):
    result = extract_kb_match(label, cards)
    assert result.value is None
    assert result.reason


def test_s3_is_explicitly_unavailable_until_t04_measurements_exist():
    result = extract_quality()
    assert result.value is None
    assert result.reason == "image_quality_unavailable_t04"


@pytest.mark.parametrize("value", [0, 0.4, 1])
def test_s4_accepts_numeric_model_confidence_boundaries(value):
    assert extract_confidence(value).value == float(value)


@pytest.mark.parametrize("value", [None, "fairly sure", "not sure", "cannot tell"])
def test_s4_missing_or_unmapped_confidence_band_is_unavailable(value):
    result = extract_confidence(value)
    assert result.value is None
    assert result.reason


@pytest.mark.parametrize("value", [True, -0.01, 1.01, math.nan, math.inf, 10**1000, "0.7"])
def test_s4_invalid_numeric_confidence_is_unavailable(value):
    result = extract_confidence(value)
    assert result.value is None
    assert result.reason


def test_incomplete_signal_set_routes_to_referral_without_score():
    result = route_signals(
        SignalSet(s1=SignalMeasurement(1.0), s4=SignalMeasurement(1.0)),
        weights=WEIGHTS,
        thresholds=TEST_THRESHOLDS,
        escalated=False,
        followups_used=0,
    )
    assert result.action == "refer"
    assert result.score is None
    assert result.unavailable_signals == ("s2", "s3")


@pytest.mark.parametrize(
    ("signals", "escalated", "followups", "expected"),
    [
        (_policy_fixture(s1=1, s2=1, s3=0.2, s4=1), False, 0, "retake"),
        (_policy_fixture(s1=1, s2=1, s3=1, s4=1), False, 0, "answer"),
        (_policy_fixture(), False, 0, "escalate"),
        (_policy_fixture(), True, 0, "ask"),
        (_policy_fixture(), True, 2, "refer"),
        (_policy_fixture(s1=0.5, s2=1, s3=1, s4=1), False, 0, "escalate"),
    ],
)
def test_routing_wrapper_preserves_b3_policy_order(signals, escalated, followups, expected):
    result = route_signals(
        signals,
        weights=WEIGHTS,
        thresholds=TEST_THRESHOLDS,
        escalated=escalated,
        followups_used=followups,
    )
    assert result.action == expected
    assert result.score is not None


@pytest.mark.parametrize(
    "signals",
    [
        _policy_fixture(s1=math.nan),
        _policy_fixture(s2=True),
        _policy_fixture(s3=1.2),
        SignalSet(s1=SignalMeasurement("bad"), s2=SignalMeasurement(0.5),
                  s3=SignalMeasurement(0.5), s4=SignalMeasurement(0.5)),
    ],
)
def test_malformed_signal_values_fail_closed_to_referral(signals):
    result = route_signals(
        signals, weights=WEIGHTS, thresholds=TEST_THRESHOLDS,
        escalated=False, followups_used=0,
    )
    assert result.action == "refer"
    assert result.score is None
    assert result.reason == "signal_or_policy_input_invalid"


def test_bad_thresholds_and_weights_fail_closed_to_referral():
    result = route_signals(
        _policy_fixture(),
        weights={**WEIGHTS, "s1_agreement": math.nan},
        thresholds={**TEST_THRESHOLDS, "quality_min": 0.4},
        escalated=False,
        followups_used=0,
    )
    assert result.action == "refer"
    assert result.reason == "signal_or_policy_input_invalid"


def _trace_case(store, case_id):
    store.record_case(
        TraceCase(case_id, "manual_review", "en", "photo", "public_test"),
        [TraceStep("intake", "completed", 0.0)],
    )


def test_route_signals_persists_decision_to_existing_b9_case():
    store = TraceStore(":memory:")
    case_id = "00000000000000000000000000000031"
    _trace_case(store, case_id)
    result = route_signals(
        _policy_fixture(s1=1.0, s2=0.5, s3=0.8, s4=0.8),
        weights=WEIGHTS,
        thresholds=TEST_THRESHOLDS,
        escalated=False,
        followups_used=0,
        trace_store=store,
        case_id=case_id,
    )
    row = store.get_signals(case_id)
    assert result.action == row["decision"] == "answer"
    assert row["s1"] == 1.0 and row["s3"] == 0.8
    assert row["score"] == pytest.approx(result.score)
    assert row["escalated"] == 0


def test_route_signals_traces_unavailable_values_as_null_not_guesses():
    store = TraceStore(":memory:")
    case_id = "00000000000000000000000000000032"
    _trace_case(store, case_id)
    signals = SignalSet(s1=SignalMeasurement(1.0), s4=SignalMeasurement(0.7))
    result = route_signals(
        signals,
        weights=WEIGHTS,
        thresholds=TEST_THRESHOLDS,
        escalated=False,
        followups_used=0,
        trace_store=store,
        case_id=case_id,
    )
    row = store.get_signals(case_id)
    assert result.action == row["decision"] == "refer"
    assert result.score is row["score"] is None
    assert row["s2"] is row["s3"] is None


def test_route_signals_traces_malformed_measurement_as_null_and_refers():
    store = TraceStore(":memory:")
    case_id = "00000000000000000000000000000033"
    _trace_case(store, case_id)
    result = route_signals(
        _policy_fixture(s1=math.nan),
        weights=WEIGHTS,
        thresholds=TEST_THRESHOLDS,
        escalated=False,
        followups_used=0,
        trace_store=store,
        case_id=case_id,
    )
    row = store.get_signals(case_id)
    assert result.action == row["decision"] == "refer"
    assert row["s1"] is None and row["score"] is None


def test_route_signals_requires_complete_trace_context_when_enabled():
    with pytest.raises(TraceError, match="supplied together"):
        route_signals(
            _policy_fixture(), weights=WEIGHTS, thresholds=TEST_THRESHOLDS,
            escalated=False, followups_used=0,
            trace_store=TraceStore(":memory:"),
        )


def test_route_signals_fails_if_requested_case_does_not_exist():
    with pytest.raises(TraceError, match="no case"):
        route_signals(
            _policy_fixture(), weights=WEIGHTS, thresholds=TEST_THRESHOLDS,
            escalated=False, followups_used=0,
            trace_store=TraceStore(":memory:"),
            case_id="00000000000000000000000000000034",
        )


@pytest.mark.parametrize("value", [True, math.nan, math.inf, 10**1000, -0.1, 1.1, "0.5"])
def test_combine_rejects_malformed_nonfinite_and_out_of_range_signals(value):
    with pytest.raises(ValueError):
        combine(value, 0.5, 0.5, 0.5, WEIGHTS)


@pytest.mark.parametrize("weight", [True, math.nan, math.inf, 10**1000, -0.1, "0.2"])
def test_combine_rejects_malformed_weights(weight):
    with pytest.raises(ValueError):
        combine(0.5, 0.5, 0.5, 0.5, {**WEIGHTS, "s1_agreement": weight})


@pytest.mark.parametrize(
    "weights",
    [
        {"s1_agreement": 1.0},
        {**WEIGHTS, "extra": 0.0},
        {**WEIGHTS, "s1_agreement": 0.5},
    ],
)
def test_combine_rejects_missing_extra_or_inconsistent_weights(weights):
    with pytest.raises(ValueError):
        combine(0.5, 0.5, 0.5, 0.5, weights)


@pytest.mark.parametrize(
    "overrides",
    [
        {"score": math.nan},
        {"s1": True},
        {"s3": math.inf},
        {"accept": 1.1},
        {"escalated": 1},
        {"followups_used": 3},
        {"followups_used": 1, "max_followups": 0},
        {"followups_used": 1, "escalated": False},
        {"max_followups": 3},
    ],
)
def test_policy_rejects_invalid_or_contradictory_inputs(overrides):
    args = dict(
        score=0.5, s1=0.5, s3=0.5, accept=0.7, agree_min=0.5,
        quality_min=0.4, escalated=False, followups_used=0, max_followups=2,
    )
    args.update(overrides)
    with pytest.raises(ValueError):
        decide(**args)
