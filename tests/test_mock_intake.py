"""Mock-only intake flow: validation, privacy gate, determinism, trace safety.

Synthetic descriptors and unittest mocks only. No model, network, Telegram SDK,
credentials, or private media anywhere in this file.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from mydrak.intake.adapter import (
    MAX_IMAGE_BYTES,
    IntakeError,
    IntakeImage,
    coerce_image,
    process_intake,
)
from mydrak.kb.loader import load_safety_card
from mydrak.privacy.data_policy import (
    DataClass,
    ProcessingEvidence,
    ProviderMode,
)

from conftest import REPO_ROOT

SAFETY = load_safety_card(REPO_ROOT / "kb" / "cards" / "general_safety.yaml")

VALID_EVENT = {"format": "jpeg", "width": 800, "height": 600, "size_bytes": 120_000}

FULL_PRIVATE_EVIDENCE = ProcessingEvidence(
    provider_mode=ProviderMode.STANDARD,
    provider_mode_verified=True,
    rights_confirmed=True,
    user_authorization_confirmed=True,
    privacy_notice_present=True,
)

FULL_PUBLIC_EVIDENCE = ProcessingEvidence(
    provider_mode=ProviderMode.STANDARD,
    provider_mode_verified=True,
    rights_confirmed=True,
    public_test_provenance_verified=True,
)


def run(event=VALID_EVENT, **kwargs):
    args = dict(
        data_policy_value="public_test",
        data_class=DataClass.PUBLIC_TEST,
        evidence=FULL_PUBLIC_EVIDENCE,
        safety_card=SAFETY,
    )
    args.update(kwargs)
    if isinstance(event, IntakeImage):
        return process_intake(event, **args)
    return process_intake(dict(event), **args)


# --- valid input and successful mock diagnosis ---


def test_valid_synthetic_input_completes_with_labeled_mock():
    response = run()
    assert response.status == "mock_complete"
    assert response.findings["label"] == "MOCK"
    assert "not a diagnosis" in response.findings["issue"]
    assert response.uncertainty == "cannot tell"
    assert response.safety_line == SAFETY["safety_line"]
    assert response.next_step == SAFETY["referral_text"]
    assert response.trace["decision"] == "allowed_mock"
    assert response.trace["request_id"] == response.request_id


def test_dataclass_event_accepted():
    response = run(IntakeImage(format="png", width=100, height=100, size_bytes=1024))
    assert response.status == "mock_complete"


def test_mock_diagnosis_is_deterministic():
    first = run()
    second = run()
    assert first.findings == second.findings
    assert first.request_id != second.request_id


def test_trace_carries_stages_and_timings():
    trace = run().trace
    names = [s["stage"] for s in trace["stages"]]
    assert names == ["validate_input", "policy_decision", "mock_diagnosis"]
    for stage in trace["stages"]:
        assert stage["outcome"]
        assert stage["duration_ms"] >= 0
    assert trace["total_duration_ms"] >= 0


# --- invalid and oversized input ---


@pytest.mark.parametrize(
    "event",
    [
        {"format": "gif", "width": 100, "height": 100, "size_bytes": 1000},
        {"format": "mp3", "width": 100, "height": 100, "size_bytes": 1000},
        {"format": 42, "width": 100, "height": 100, "size_bytes": 1000},
        {"format": "jpeg", "width": 0, "height": 100, "size_bytes": 1000},
        {"format": "jpeg", "width": -5, "height": 100, "size_bytes": 1000},
        {"format": "jpeg", "width": True, "height": 100, "size_bytes": 1000},
        {"format": "jpeg", "width": 100, "height": 100, "size_bytes": 0},
        {"format": "jpeg", "width": 100, "height": 100, "size_bytes": MAX_IMAGE_BYTES + 1},
        {"format": "jpeg", "width": 100, "height": 100, "size_bytes": "big"},
        {"format": "jpeg", "width": 100, "height": 100},
        "not-a-mapping",
        None,
    ],
)
def test_invalid_and_oversized_input_rejected(event):
    with pytest.raises(IntakeError):
        coerce_image(event)


def test_invalid_input_raises_before_policy_and_sender():
    sender = Mock()
    with pytest.raises(IntakeError):
        run({"format": "bmp", "width": 10, "height": 10, "size_bytes": 10}, sender=sender)
    sender.assert_not_called()


def test_missing_safety_text_refuses_to_reply():
    with pytest.raises(IntakeError):
        run(safety_card={"safety_line": "", "referral_text": ""})


# --- policy configuration failures ---


@pytest.mark.parametrize("value", [None, "", "unknown", "PRIVATE"])
def test_missing_and_invalid_policy_block_without_sender(value):
    sender = Mock()
    response = run(data_policy_value=value, data_class=DataClass.PRIVATE, evidence=None, sender=sender)
    assert response.status == "blocked"
    assert response.trace["decision"] == "blocked"
    sender.assert_not_called()


def test_private_data_with_missing_authorization_blocked():
    sender = Mock()
    bare = ProcessingEvidence(provider_mode=ProviderMode.STANDARD)
    response = run(
        data_policy_value=None, data_class=DataClass.PRIVATE, evidence=bare, sender=sender,
    )
    assert response.status == "blocked"
    sender.assert_not_called()


def test_unverified_route_blocked():
    sender = Mock()
    evidence = ProcessingEvidence(
        provider_mode=ProviderMode.STANDARD,
        provider_mode_verified=False,
        rights_confirmed=True,
        user_authorization_confirmed=True,
        privacy_notice_present=True,
    )
    response = run(
        data_policy_value="private", data_class=DataClass.PRIVATE, evidence=evidence, sender=sender,
    )
    assert response.status == "blocked"
    sender.assert_not_called()


def test_contributor_route_cannot_take_private_data():
    sender = Mock()
    evidence = ProcessingEvidence(
        provider_mode=ProviderMode.CONTRIBUTOR,
        provider_mode_verified=True,
        rights_confirmed=True,
        user_authorization_confirmed=True,
        privacy_notice_present=True,
    )
    response = run(
        data_policy_value="private", data_class=DataClass.PRIVATE, evidence=evidence, sender=sender,
    )
    assert response.status == "blocked"
    sender.assert_not_called()


def test_public_test_without_provenance_blocked():
    sender = Mock()
    evidence = ProcessingEvidence(
        provider_mode=ProviderMode.STANDARD, provider_mode_verified=True, rights_confirmed=True,
    )
    response = run(
        data_policy_value="public_test",
        data_class=DataClass.PUBLIC_TEST,
        evidence=evidence,
        sender=sender,
    )
    assert response.status == "blocked"
    sender.assert_not_called()


def test_public_test_mode_does_not_authorize_private_data():
    sender = Mock()
    response = run(
        data_policy_value="public_test", data_class=DataClass.PRIVATE, sender=sender,
    )
    assert response.status == "blocked"
    sender.assert_not_called()


# --- allowed path and sender boundary ---


def test_allowed_mock_invokes_sender_once_with_metadata_only():
    sender = Mock()
    response = run(sender=sender)
    assert response.status == "mock_complete"
    assert sender.call_count == 1
    payload = sender.call_args.args[0]
    assert payload["request_id"] == response.request_id
    assert payload["image"] == {
        "format": "jpeg",
        "width": 800,
        "height": 600,
        "size_bytes": 120_000,
    }
    _assert_no_bytes(payload)


def test_allowed_mock_without_sender_still_completes():
    assert run(sender=None).status == "mock_complete"


def test_full_private_evidence_allows_mock():
    sender = Mock()
    response = run(
        data_policy_value="private",
        data_class=DataClass.PRIVATE,
        evidence=FULL_PRIVATE_EVIDENCE,
        sender=sender,
    )
    assert response.status == "mock_complete"
    assert sender.call_count == 1


# --- trace and payload safety ---


def _assert_no_bytes(node):
    if isinstance(node, (bytes, bytearray)):
        raise AssertionError("payload contains raw bytes")
    if isinstance(node, dict):
        for key, value in node.items():
            lowered = str(key).lower()
            assert "token" not in lowered and "secret" not in lowered and "password" not in lowered
            assert "api_key" not in lowered and "image_data" not in lowered and "audio" not in lowered
            _assert_no_bytes(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _assert_no_bytes(value)


@pytest.mark.parametrize("allowed", [True, False])
def test_response_and_trace_contain_no_bytes_or_secrets(allowed):
    if allowed:
        response = run()
    else:
        response = run(data_policy_value=None, data_class=DataClass.PRIVATE, evidence=None)
    _assert_no_bytes(response.to_dict())


def test_blocked_response_still_carries_safety_and_referral():
    response = run(data_policy_value=None, data_class=DataClass.PRIVATE, evidence=None)
    assert response.status == "blocked"
    assert response.uncertainty == "cannot tell"
    assert "no finding" in response.findings["issue"]
    assert response.safety_line == SAFETY["safety_line"]
    assert response.next_step == SAFETY["referral_text"]
    assert response.trace["reason"]


def test_mock_module_uses_no_network_or_subprocess():
    source = (Path(__file__).resolve().parents[1] / "src" / "mydrak" / "intake" / "adapter.py").read_text()
    for token in ("urllib", "http.client", "socket", "subprocess", "requests", "httpx", "openai", "telegram"):
        assert token not in source
