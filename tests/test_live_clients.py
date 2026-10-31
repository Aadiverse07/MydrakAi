"""Offline tests for explicitly guarded Glimmer/Spark clients."""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
import json

import pytest

from mydrak.live.clients import GlimmerClient, LiveDiagnosisError, SparkClient
from mydrak.privacy.data_policy import (
    DataClass, DataPolicy, DataPolicyError, ProcessingEvidence, ProviderMode,
)
from mydrak.trace.store import TraceStep
from mydrak.vision.diagnosis import DiagnosisStatus, run_diagnosis_validation
from mydrak.trace.store import TraceStore
from mydrak.workflow.mock_providers import (
    DeterministicMockDiagnosisProvider, DeterministicMockSamProvider,
)
from mydrak.workflow.pipeline_support import validate_pipeline_dependencies

SECRET = "SYNTHETIC_SECRET_NEVER_PRINT"
CONFIG = {
    "model_id": "test-model", "endpoint": "https://example.test/v1",
    "timeout_s": 3, "max_input_tokens_estimate": 1000, "max_tokens": 1000,
    "price_input_per_1m": 2, "price_output_per_1m": 4,
}
ENV = {"MYDRAK_LIVE": "1", "TOGETHER_API_KEY": SECRET, "META_API_KEY": SECRET}
VALID = json.dumps({
    "plant_visible": True, "crop": "tomato", "issue": "leaf_spot",
    "alternatives": [], "symptoms_observed": ["spots"], "image_issues": [],
    "stated_confidence": "medium", "segment_prompts": [],
})


class FakeTransport:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = []

    def post_json(self, url, *, headers, body, timeout_s):
        self.calls.append((url, dict(headers), json.loads(json.dumps(body)), timeout_s))
        if self.error:
            raise self.error
        return 200, json.dumps(self.responses.pop(0)).encode()


def response(content=VALID, prompt_tokens=11, completion_tokens=7):
    return {"choices": [{"message": {"content": content}}], "usage": {
        "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
    }}


def glimmer(tmp_path, transport, *, authorized=True, env=None, callback=None, sleep=lambda _: None):
    return GlimmerClient(
        CONFIG, image_bytes=b"\xff\xd8\xffsynthetic", data_policy=DataPolicy.PUBLIC_TEST,
        data_class=DataClass.PUBLIC_TEST, public_test_marker="public-test", rights_confirmed=True,
        cli_authorized=authorized, max_spend_usd="1", ledger_path=str(tmp_path / "ledger.sqlite"),
        environ=ENV if env is None else env, transport=transport,
        trace_callback=callback or (lambda _: None), retry_delays_s=(0.01, 0.02), sleep=sleep,
        supported_crops=("tomato",), disease_ids=("leaf_spot",),
    )


def spark(tmp_path, transport, *, contributor=False, data_class=DataClass.PUBLIC_TEST,
          policy=DataPolicy.PUBLIC_TEST, evidence=None, config=None):
    mode = ProviderMode.CONTRIBUTOR if contributor else ProviderMode.STANDARD
    if evidence is None:
        evidence = ProcessingEvidence(
            provider_mode=mode, provider_mode_verified=True, rights_confirmed=True,
            public_test_provenance_verified=True,
            user_authorization_confirmed=data_class is DataClass.PRIVATE,
            privacy_notice_present=data_class is DataClass.PRIVATE,
        )
    values = CONFIG | {"model_id_contributor": "test-contributor"}
    if config:
        values.update(config)
    return SparkClient(
        values, context=None, data_policy=policy, data_class=data_class, evidence=evidence,
        use_contributor=contributor, cli_authorized=True, max_spend_usd="1",
        ledger_path=str(tmp_path / "ledger.sqlite"), environ=ENV, transport=transport,
        trace_callback=lambda _: None, retry_delays_s=(), sleep=lambda _: None,
        supported_crops=("tomato",), disease_ids=("leaf_spot",),
    )


def test_glimmer_serializes_documented_multimodal_shape_and_traces_tokens(tmp_path):
    trace = []
    transport = FakeTransport([response()])
    client = glimmer(tmp_path, transport, callback=trace.append)
    assert client.generate() == VALID
    url, headers, body, timeout = transport.calls[0]
    assert url == "https://example.test/v1/chat/completions"
    assert headers["Authorization"] == f"Bearer {SECRET}"
    assert body["messages"][0]["content"][0]["type"] == "text"
    image = body["messages"][0]["content"][1]
    assert image["type"] == "image_url"
    assert image["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert body["max_tokens"] == 1000 and body["temperature"] == 0.2
    assert timeout == 3
    assert trace == [TraceStep(
        "glimmer_together", "completed", trace[0].latency_ms,
        model="test-model", tokens_in=11, tokens_out=7,
        est_cost=Decimal("0.00005"), error_code=None,
    )]
    assert SECRET not in repr(trace)
    assert SECRET not in json.dumps(body)


def test_spark_serializes_text_only_and_selects_contributor_only_for_public_test(tmp_path):
    transport = FakeTransport([response()])
    client = spark(tmp_path, transport, contributor=True)
    client.generate()
    _, _, body, _ = transport.calls[0]
    assert body["model"] == "test-contributor"
    assert isinstance(body["messages"][0]["content"], str)
    assert "image_url" not in body["messages"][0]["content"]


def test_spark_standard_variant_accepts_authorized_private_data(tmp_path):
    evidence = ProcessingEvidence(
        provider_mode=ProviderMode.STANDARD, provider_mode_verified=True,
        rights_confirmed=True, user_authorization_confirmed=True,
        privacy_notice_present=True,
    )
    transport = FakeTransport([response()])
    client = spark(
        tmp_path, transport, data_class=DataClass.PRIVATE, policy=DataPolicy.PRIVATE,
        evidence=evidence,
    )
    client.generate()
    assert transport.calls[0][2]["model"] == "test-model"


@pytest.mark.parametrize("data_class,policy,evidence", [
    (DataClass.PRIVATE, DataPolicy.PRIVATE, ProcessingEvidence(
        provider_mode=ProviderMode.CONTRIBUTOR, provider_mode_verified=True,
        rights_confirmed=True, user_authorization_confirmed=True, privacy_notice_present=True,
    )),
    (DataClass.PUBLIC_TEST, DataPolicy.PUBLIC_TEST, ProcessingEvidence(
        provider_mode=ProviderMode.CONTRIBUTOR, provider_mode_verified=True,
        rights_confirmed=True, public_test_provenance_verified=False,
    )),
])
def test_contributor_requires_explicit_verified_public_test(tmp_path, data_class, policy, evidence):
    transport = FakeTransport([response()])
    with pytest.raises(DataPolicyError):
        spark(tmp_path, transport, contributor=True, data_class=data_class,
              policy=policy, evidence=evidence)
    assert transport.calls == []


def test_guard_refusal_precedes_transport_call(tmp_path):
    transport = FakeTransport([response()])
    client = glimmer(tmp_path, transport, authorized=False)
    with pytest.raises(Exception, match="live-authorized"):
        client.generate()
    assert transport.calls == []


def test_offline_workflow_rejects_live_client_instead_of_falling_back_or_dispatching(tmp_path):
    transport = FakeTransport([response()])
    live_client = glimmer(tmp_path, transport)
    store = TraceStore(tmp_path / "trace.sqlite")
    try:
        with pytest.raises(ValueError, match="only deterministic mock"):
            validate_pipeline_dependencies(
                "en", store, live_client, DeterministicMockDiagnosisProvider([]),
                DeterministicMockSamProvider(("1",), ("1",)), None, None, None,
            )
    finally:
        store.close()
    assert transport.calls == []


def test_retry_timeout_then_success_is_bounded_and_traced(tmp_path):
    class SometimesTimeout(FakeTransport):
        def post_json(self, *args, **kwargs):
            if len(self.calls) < 2:
                self.calls.append("timeout")
                raise TimeoutError(SECRET)
            return super().post_json(*args, **kwargs)

    transport = SometimesTimeout([response()])
    delays = []
    trace = []
    client = glimmer(tmp_path, transport, callback=trace.append, sleep=delays.append)
    assert client.generate() == VALID
    assert len(transport.calls) == 3
    assert delays == [0.01, 0.02]
    assert [step.outcome for step in trace] == ["transport_failed", "transport_failed", "completed"]
    assert all(SECRET not in repr(step) for step in trace)


def test_exhausted_transport_failure_is_sanitized_and_trace_has_unknown_cost(tmp_path):
    transport = FakeTransport(error=RuntimeError(SECRET))
    trace = []
    client = glimmer(tmp_path, transport, callback=trace.append)
    with pytest.raises(LiveDiagnosisError) as caught:
        client.generate()
    assert len(transport.calls) == 3
    assert "provider unavailable" in str(caught.value)
    assert SECRET not in repr(caught.value)
    assert all(SECRET not in repr(step) for step in trace)
    assert all(step.est_cost is None for step in trace)


def test_exhausted_provider_errors_use_existing_unknown_fallback(tmp_path):
    transport = FakeTransport(error=TimeoutError("synthetic timeout"))
    client = glimmer(tmp_path, transport)
    client._retry_delays_s = ()
    result = run_diagnosis_validation(
        client, supported_crops=("tomato",), disease_ids=("leaf_spot",),
        confidence_bands=("low", "medium", "high"),
    )
    assert result.status is DiagnosisStatus.UNAVAILABLE
    assert result.reason == "provider_failure"
    assert len(transport.calls) == 1


def test_malformed_transport_response_fails_closed_before_parsing(tmp_path):
    class MalformedTransport:
        def __init__(self):
            self.calls = 0

        def post_json(self, *args, **kwargs):
            self.calls += 1
            return "200", b"not-json"

    transport = MalformedTransport()
    client = glimmer(tmp_path, transport)
    client._retry_delays_s = ()
    with pytest.raises(LiveDiagnosisError, match="provider unavailable"):
        client.generate()
    assert transport.calls == 1


def test_b8_validator_repairs_one_schema_invalid_output_and_then_validates(tmp_path):
    bad = json.loads(VALID) | {"treatment": "forbidden extra field"}
    transport = FakeTransport([response(json.dumps(bad)), response()])
    client = glimmer(tmp_path, transport)
    result = run_diagnosis_validation(
        client, supported_crops=("tomato",), disease_ids=("leaf_spot",),
        confidence_bands=("low", "medium", "high"),
    )
    assert result.status is DiagnosisStatus.VALID
    assert result.repair_attempts == 1
    assert len(transport.calls) == 2


def test_b8_validator_returns_unknown_after_invalid_repair(tmp_path):
    transport = FakeTransport([response("not json"), response("still not json")])
    client = glimmer(tmp_path, transport)
    result = run_diagnosis_validation(
        client, supported_crops=("tomato",), disease_ids=("leaf_spot",),
        confidence_bands=("low", "medium", "high"),
    )
    assert result.status is DiagnosisStatus.UNKNOWN
    assert result.repair_attempts == 1


def test_response_echoing_credential_is_rejected_without_trace_leak(tmp_path):
    transport = FakeTransport([response(SECRET)])
    trace = []
    client = glimmer(tmp_path, transport, callback=trace.append)
    with pytest.raises(LiveDiagnosisError):
        client.generate()
    assert SECRET not in repr(trace)
    assert SECRET not in repr(client.last_step)


def test_missing_usage_stays_unknown_cost_and_bad_schema_does_not_become_valid(tmp_path):
    transport = FakeTransport([response(VALID, None, None)])
    trace = []
    client = glimmer(tmp_path, transport, callback=trace.append)
    output = client.generate()
    assert output == VALID
    assert trace[0].tokens_in is None and trace[0].tokens_out is None
    assert trace[0].est_cost is None

    malformed = FakeTransport([response("{}"), response("{}")])
    result = run_diagnosis_validation(
        glimmer(tmp_path, malformed), supported_crops=("tomato",),
        disease_ids=("leaf_spot",), confidence_bands=("low", "medium", "high"),
    )
    assert result.status is DiagnosisStatus.UNKNOWN
