"""Offline coordinator tests; all image descriptors and SAM replies are synthetic."""

import json

import pytest

from mydrak.kb.loader import load_safety_card
from mydrak.privacy.data_policy import DataClass, ProcessingEvidence, ProviderMode
from mydrak.workflow import coordinator
from mydrak.workflow.coordinator import (
    OfflineCoordinatorError,
    SyntheticSamReplyFixture,
    coordinate_followup_answer,
    coordinate_mock_tier1_results,
    coordinate_offline_case,
)
from mydrak.workflow.followup import FollowUpState, begin_followup
from mydrak.trace.store import TraceStore
from mydrak.vision.diagnosis import DiagnosisResult, DiagnosisStatus, run_diagnosis_validation

from conftest import REPO_ROOT


SAFETY = load_safety_card(REPO_ROOT / "kb" / "cards" / "general_safety.yaml")
IMAGE = {"format": "jpeg", "width": 100, "height": 80, "size_bytes": 1024}
SYNTHETIC_WEIGHTS = {
    "s1_agreement": 0.25,
    "s2_kb_match": 0.25,
    "s3_quality": 0.25,
    "s4_stated_confidence": 0.25,
}
SYNTHETIC_THRESHOLDS = {
    "accept": 0.7, "agree_min": 0.5, "quality_min": 0.4, "max_followups": 2,
}
PUBLIC_TEST_EVIDENCE = ProcessingEvidence(
    provider_mode=ProviderMode.STANDARD,
    provider_mode_verified=True,
    rights_confirmed=True,
    public_test_provenance_verified=True,
)
SYNTHETIC_CARD = {
    "follow_up_questions": [
        {"id": "q1", "en": "Synthetic question one?"},
        {"id": "q2", "en": "Synthetic question two?"},
    ]
}


def sam_fixture(text: str, *, provenance=coordinator.SYNTHETIC_FIXTURE_PROVENANCE):
    raw = json.dumps({
        "output": [{
            "type": "message",
            "content": [{"type": "output_text", "text": text}],
        }]
    })
    return SyntheticSamReplyFixture(raw_reply=raw, provenance=provenance)


def run_allowed(fixture, trace_store=None):
    trace_store = trace_store or TraceStore(":memory:")
    return coordinate_offline_case(
        IMAGE,
        fixture,
        data_policy_value="public_test",
        data_class=DataClass.PUBLIC_TEST,
        evidence=PUBLIC_TEST_EVIDENCE,
        safety_card=SAFETY,
        trace_store=trace_store,
    )


def test_zero_detection_flow_returns_safe_referral_not_diagnosis():
    result = run_allowed(sam_fixture(""))
    assert result.status == "referred"
    assert result.sam_reason == "zero-match"
    assert result.reason == "no_sam_detections_not_a_health_finding"
    assert result.severity_pct is None
    assert result.reply == (
        "I cannot tell from this photo. If it spreads or you are unsure, call "
        "the Kisan Call Centre or your local KVK (Krishi Vigyan Kendra)."
    )
    assert "simulated leaf-spot" not in repr(result)
    assert result.case_id


def test_allowed_case_persists_sanitized_case_and_steps():
    store = TraceStore(":memory:")
    result = run_allowed(sam_fixture(""), store)
    record = store.get_case(result.case_id)
    assert record["final_action"] == "referred"
    assert record["user_hash"] is None
    assert record["image_hash"] is None
    assert record["severity_pct"] is None
    assert record["est_cost"] is None
    assert {step["step_name"] for step in store.get_steps(result.case_id)} >= {
        "intake_validate_input", "synthetic_sam_parse", "reply_compose"
    }


def test_coordinator_can_link_only_hashed_recovery_identity_metadata():
    store = TraceStore(":memory:")
    digest = "a" * 64
    result = coordinate_offline_case(
        IMAGE,
        sam_fixture(""),
        data_policy_value="public_test",
        data_class=DataClass.PUBLIC_TEST,
        evidence=PUBLIC_TEST_EVIDENCE,
        safety_card=SAFETY,
        user_hash=digest,
        image_hash="b" * 64,
        trace_store=store,
    )
    case = store.get_case(result.case_id)
    assert case["user_hash"] == digest
    assert case["image_hash"] == "b" * 64
    assert "farmer" not in repr(case)


def test_opaque_mask_flow_requires_manual_review_and_has_no_severity():
    text = (
        "<0f>0<|box;x1=1;y1=1;x2=90;y2=70;w=100;h=80|>"
        "<|mask;x=0;y=0;data=20,20,~sYntH3t1c|>"
    )
    result = run_allowed(sam_fixture(text))
    assert result.status == "manual_review"
    assert result.sam_reason == "masks-opaque"
    assert result.severity_pct is None
    assert result.reply.startswith("I cannot tell from this photo.")


def test_policy_denial_stops_before_sam_parser_and_returns_no_reply(monkeypatch):
    def unexpected_parse(*args, **kwargs):
        raise AssertionError("SAM parser must not run after policy denial")

    monkeypatch.setattr(coordinator, "run_offline_chain", unexpected_parse)
    result = coordinate_offline_case(
        IMAGE,
        sam_fixture("not valid JSON"),
        data_policy_value="private",
        safety_card=SAFETY,
            trace_store=TraceStore(":memory:"),
    )
    assert result.status == "blocked"
    assert result.reason == "intake_policy_denied"
    assert result.reply is None
    assert result.sam_reason is None


def test_invalid_image_descriptor_fails_closed():
    with pytest.raises(OfflineCoordinatorError, match="offline intake was rejected"):
        coordinate_offline_case(
            {**IMAGE, "format": "webp"},
            sam_fixture(""),
            data_policy_value="public_test",
            safety_card=SAFETY,
            data_class=DataClass.PUBLIC_TEST,
            evidence=PUBLIC_TEST_EVIDENCE,
            trace_store=TraceStore(":memory:"),
        )


def test_malformed_sam_envelope_falls_back_to_referral():
    fixture = SyntheticSamReplyFixture(
        raw_reply="{malformed",
        provenance=coordinator.SYNTHETIC_FIXTURE_PROVENANCE,
    )
    result = run_allowed(fixture)
    assert result.status == "manual_review"
    assert result.sam_reason == "unusable-envelope"
    assert result.reply.startswith("I cannot tell from this photo.")


def test_unsupported_language_and_fixture_provenance_fail_before_intake(monkeypatch):
    def unexpected_intake(*args, **kwargs):
        raise AssertionError("invalid configuration must fail before intake")

    monkeypatch.setattr(coordinator, "process_intake", unexpected_intake)
    with pytest.raises(OfflineCoordinatorError, match="language is unavailable"):
        coordinate_offline_case(
            IMAGE, sam_fixture(""), data_policy_value="public_test",
            safety_card=SAFETY, language="hi",
            trace_store=TraceStore(":memory:"),
        )
    with pytest.raises(OfflineCoordinatorError, match="provenance is invalid"):
        coordinate_offline_case(
            IMAGE, sam_fixture("", provenance="unverified"),
            data_policy_value="public_test", safety_card=SAFETY,
            trace_store=TraceStore(":memory:"),
        )


def test_followup_answer_bridge_uses_existing_bounded_state():
    first = begin_followup(
        FollowUpState(), card=SYNTHETIC_CARD, safety_card=SAFETY, question_id="q1"
    )
    second = coordinate_followup_answer(
        first.state,
        "transient synthetic answer",
        card=SYNTHETIC_CARD,
        safety_card=SAFETY,
        next_question_id="q2",
    )
    assert second.action == "ask"
    assert second.state.turns_used == 2
    final = coordinate_followup_answer(
        second.state,
        "another transient answer",
        card=SYNTHETIC_CARD,
        safety_card=SAFETY,
    )
    assert final.action == "refer"
    assert final.state.referred is True
    assert final.state.turns_used == 2


def _synthetic_tier1_result():
    class FakeTier1Provider:
        def generate(self):
            return json.dumps({
                "plant_visible": True,
                "crop": "synthetic_crop",
                "issue": "synthetic_issue",
                "alternatives": [],
                "symptoms_observed": ["leaf spot"],
                "image_issues": [],
                "stated_confidence": 0.7,
                "segment_prompts": ["synthetic prompt"],
            })

        def repair(self, invalid_output):
            raise AssertionError("valid synthetic fixture must not be repaired")

    return run_diagnosis_validation(
        FakeTier1Provider(),
        supported_crops=("synthetic_crop",),
        disease_ids=("synthetic_issue",),
    )


def test_coordinator_routes_mock_tier1_results_and_s3_fails_closed(monkeypatch):
    captured = {}
    actual_route = coordinator.route_signals

    def capture_route(signals, **kwargs):
        captured["signals"] = signals
        return actual_route(signals, **kwargs)

    monkeypatch.setattr(coordinator, "route_signals", capture_route)
    result = coordinate_mock_tier1_results(
        _synthetic_tier1_result(),
        _synthetic_tier1_result(),
        cards=[{"id": "synthetic_issue", "symptoms": ["Leaf spot.", "extra"]}],
        weights=SYNTHETIC_WEIGHTS,
        thresholds=SYNTHETIC_THRESHOLDS,
    )

    assert captured["signals"].s1.value == 1.0
    assert captured["signals"].s2.value == 1.0
    assert captured["signals"].s3.value is None
    assert result.action == "refer"
    assert result.score is None
    assert result.unavailable_signals == ("s3", "s4")


def test_coordinator_rejects_nonvalidated_tier1_result():
    invalid = DiagnosisResult(DiagnosisStatus.UNKNOWN, None, "synthetic-invalid")
    with pytest.raises(OfflineCoordinatorError, match="validated Tier-1"):
        coordinate_mock_tier1_results(
            invalid, _synthetic_tier1_result(), cards=[],
            weights=SYNTHETIC_WEIGHTS, thresholds=SYNTHETIC_THRESHOLDS,
        )


def test_coordinator_rejects_malformed_valid_result_object():
    malformed = DiagnosisResult(DiagnosisStatus.VALID, object(), "synthetic-invalid")
    with pytest.raises(OfflineCoordinatorError, match="validated Tier-1"):
        coordinate_mock_tier1_results(
            malformed, _synthetic_tier1_result(), cards=[],
            weights=SYNTHETIC_WEIGHTS, thresholds=SYNTHETIC_THRESHOLDS,
        )
