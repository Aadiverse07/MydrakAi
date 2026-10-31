"""Offline tests for explicit Spark-only routing; fake HTTP only."""

from decimal import Decimal
from io import BytesIO
import json
import socket

from PIL import Image
import pytest

from mydrak.live.clients import SparkClient
from mydrak.privacy.data_policy import DataClass, ProcessingEvidence, ProviderMode
from mydrak.kb.loader import load_safety_card
from mydrak.trace.store import TraceStore
from mydrak.workflow.modes import run_pipeline_mode


def photo_bytes():
    image = Image.new("RGB", (32, 24), (42, 151, 53))
    target = BytesIO()
    image.save(target, format="PNG")
    return target.getvalue()


def valid_output():
    return json.dumps({
        "plant_visible": True, "crop": "tomato", "issue": "leaf_spot",
        "alternatives": [], "symptoms_observed": ["synthetic spot"],
        "image_issues": [], "stated_confidence": 0.8,
        "segment_prompts": [],
    })


def http_response(content):
    return 200, json.dumps({
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 40, "completion_tokens": 30},
    }).encode()


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post_json(self, url, *, headers, body, timeout_s):
        self.calls.append((url, dict(headers), json.loads(json.dumps(body)), timeout_s))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def run(tmp_path, *, marker="public-test", data_class=DataClass.PUBLIC_TEST,
        config=None, response_contents=None, responses=None, language="en", evidence=None,
        policy_value=None,
        cli_authorized=True, environ=None):
    store = TraceStore(tmp_path / "trace.sqlite")
    made = []
    transports = []
    provider_values = {
        "model_id": "synthetic-spark", "model_id_contributor": "synthetic-contributor",
        "endpoint": "https://api.example.test/v1", "timeout_s": 2,
        "max_input_tokens_estimate": 1000, "max_tokens": 2048,
        "diagnosis_max_tokens": 512, "price_input_per_1m": 1.25,
        "price_output_per_1m": 4.25,
    } | (config or {})
    if responses is not None:
        fake_responses = list(responses)
    else:
        fake_responses = [http_response(value) for value in (response_contents or [valid_output()])]
    if not fake_responses:
        fake_responses = [http_response(valid_output())]

    def factory(**kwargs):
        assert kwargs["image_bytes"].startswith(b"\xff\xd8\xff")
        transport = FakeTransport(fake_responses)
        transports.append(transport)
        client = SparkClient(
            kwargs["config"] | provider_values, context=None,
            data_policy=kwargs["data_policy"], data_class=kwargs["data_class"],
            evidence=kwargs["evidence"], image_bytes=kwargs["image_bytes"],
            image_provenance=kwargs["image_provenance"],
            use_contributor=kwargs["use_contributor"],
            cli_authorized=cli_authorized, max_spend_usd="0.25",
            ledger_path=str(tmp_path / "ledger.sqlite"),
            environ=environ or {"MYDRAK_LIVE": "1", "META_API_KEY": "SYNTHETIC_KEY"},
            transport=transport, trace_callback=kwargs["trace_callback"],
            supported_crops=("tomato",), disease_ids=("leaf_spot",),
            confidence_bands=("low", "medium", "high"),
            retry_delays_s=(0.01, 0.02), sleep=lambda _: None,
        )
        made.append(client)
        return client

    selected_class = data_class
    default_evidence = ProcessingEvidence(
        provider_mode=ProviderMode.STANDARD, provider_mode_verified=True,
        rights_confirmed=True, user_authorization_confirmed=selected_class is DataClass.PRIVATE,
        privacy_notice_present=selected_class is DataClass.PRIVATE,
        public_test_provenance_verified=selected_class is DataClass.PUBLIC_TEST,
    )
    result = run_pipeline_mode(
        "spark_only", photo_bytes=photo_bytes(), language=language,
        trace_store=store, spark_provider_factory=factory,
        provider_config=provider_values,
        data_policy_value=policy_value or (
            "public_test" if selected_class is DataClass.PUBLIC_TEST else "private"
        ),
        data_class=selected_class, image_provenance=marker,
        evidence=evidence or default_evidence,
        supported_crops=("tomato",), disease_ids=("leaf_spot",),
    )
    return result, made, transports, store


def test_spark_only_runs_once_routes_fail_closed_and_traces_cost_and_steps(tmp_path, monkeypatch):
    def no_socket(*args, **kwargs):
        raise AssertionError("offline test must not open a socket")

    monkeypatch.setattr(socket, "socket", no_socket)
    monkeypatch.setattr(socket, "create_connection", no_socket)
    result, clients, transports, store = run(tmp_path)
    assert result.action == "refer"
    assert result.reason == "decider_fail_closed_missing_signals"
    assert result.spark_escalations == 1
    assert result.overlay_bytes is None and result.severity_pct is None
    assert result.provenance == "injected-transport"
    assert result.confidence_word == "cannot tell"
    assert "preliminary guidance" in result.reply
    assert "cannot tell" in result.reply
    assert load_safety_card("kb/cards/general_safety.yaml")["safety_line"] in result.reply
    assert len(transports[0].calls) == 1
    assert clients[0].last_request_sent is True
    assert result.tokens_in == 40 and result.tokens_out == 30
    assert result.estimated_cost_usd == Decimal("0.0001775")
    case = store.get_case(result.case_id)
    signals = store.get_signals(result.case_id)
    assert case["severity_pct"] is None and case["kb_card_id"] is None
    assert signals["s1"] is None and signals["s2"] is None and signals["s3"] is None
    assert signals["s4"] == 0.8 and signals["decision"] == "refer"
    names = [item["step_name"] for item in store.get_steps(result.case_id)]
    expected = ["intake_gate", "preprocessing", "cache_lookup", "glimmer",
                "spark_meta", "spark_validation", "decider", "sam_mock",
                "severity_overlay", "kb_lookup", "reply_compose"]
    positions = [names.index(name) for name in expected]
    assert positions == sorted(positions)
    spark_trace = [item for item in store.get_steps(result.case_id) if item["step_name"] == "spark_meta"]
    assert len(spark_trace) == 1 and spark_trace[0]["est_cost"] == "0.0001775"
    assert "synthetic spot" not in repr((case, store.get_steps(result.case_id)))
    store.close()


def test_spark_only_rejects_unmarked_public_image_before_provider(tmp_path):
    result, clients, transports, store = run(tmp_path, marker=None)
    assert result.action == "blocked" and result.reason == "intake_or_data_policy_denied"
    assert result.spark_escalations == 0 and clients == [] and transports == []
    assert store.get_case(result.case_id) is not None
    store.close()


def test_private_photo_requires_explicit_config_allowance_before_provider(tmp_path):
    result, clients, transports, store = run(
        tmp_path, marker="private", data_class=DataClass.PRIVATE,
    )
    assert result.reason == "intake_or_data_policy_denied"
    assert clients == [] and transports == [] and result.spark_escalations == 0
    store.close()


def test_private_image_uses_standard_model_when_config_allows_upload(tmp_path):
    result, clients, transports, store = run(
        tmp_path, marker="private", data_class=DataClass.PRIVATE,
        config={"allow_private_upload": True},
        evidence=ProcessingEvidence(
            provider_mode=ProviderMode.STANDARD, provider_mode_verified=True,
            rights_confirmed=True, user_authorization_confirmed=True,
            privacy_notice_present=True,
        ),
    )
    assert result.action == "refer" and clients and transports[0].calls
    assert transports[0].calls[0][2]["model"] == "synthetic-spark"
    store.close()


def test_private_data_policy_mismatch_is_blocked_before_provider(tmp_path):
    result, clients, transports, store = run(
        tmp_path, marker="private", data_class=DataClass.PRIVATE,
        config={"allow_private_upload": True}, policy_value="public_test",
        evidence=ProcessingEvidence(
            provider_mode=ProviderMode.STANDARD, provider_mode_verified=True,
            rights_confirmed=True, user_authorization_confirmed=True,
            privacy_notice_present=True,
        ),
    )
    assert result.action == "blocked" and clients == [] and transports == []
    store.close()


def test_hi_language_fails_closed_without_provider_call(tmp_path):
    result, clients, transports, store = run(tmp_path, language="hi")
    assert result.reason == "hindi_reply_review_unavailable"
    assert clients == [] and transports == []
    store.close()


def test_invalid_treatment_field_uses_one_schema_repair_then_refers(tmp_path):
    invalid = json.loads(valid_output()) | {"treatment": "synthetic chemical advice"}
    result, clients, transports, store = run(
        tmp_path, response_contents=[json.dumps(invalid), valid_output()],
    )
    assert result.action == "refer"
    assert clients[0].last_request_sent and len(transports[0].calls) == 2
    assert "synthetic chemical advice" not in (result.reply or "")
    store.close()


def test_invalid_output_after_repair_becomes_unknown_and_refers(tmp_path):
    result, clients, transports, store = run(
        tmp_path, response_contents=["not json", "still not json"],
    )
    assert result.reason == "spark_output_unknown"
    assert clients[0].last_request_sent and len(transports[0].calls) == 2
    assert result.action == "refer"
    store.close()


def test_unavailable_spark_retries_are_bounded_then_referral_is_traced(tmp_path):
    result, clients, transports, store = run(
        tmp_path, responses=[TimeoutError("synthetic timeout") for _ in range(3)],
    )
    assert result.action == "refer"
    assert result.spark_escalations == 1
    assert len(transports[0].calls) == 3  # one HTTP attempt and at most two retries
    assert store.get_case(result.case_id) is not None
    assert result.estimated_cost_usd is None
    assert result.tokens_in is None and result.tokens_out is None
    store.close()


def test_live_guard_refusal_happens_before_http_dispatch(tmp_path):
    result, clients, transports, store = run(
        tmp_path, cli_authorized=False,
    )
    assert result.action == "refer" and len(transports[0].calls) == 0
    assert clients[0].last_guard_condition == "cli_authorization"
    assert clients[0].last_request_sent is False
    store.close()


def test_unknown_workflow_mode_does_not_fall_through_to_any_provider():
    called = []
    with pytest.raises(ValueError, match="unsupported"):
        run_pipeline_mode("live", provider_factory=lambda: called.append(True))
    assert called == []
