"""End-to-end offline workflow tests; all images and provider outputs are synthetic."""

from io import BytesIO
from pathlib import Path
import ast
import socket

from PIL import Image
import pytest

from mydrak.kb.loader import load_safety_card
from mydrak.privacy.data_policy import ProcessingEvidence, ProviderMode
from mydrak.trace.store import TraceStore
from mydrak.workflow.mock_providers import (
    DeterministicMockDiagnosisProvider, DeterministicMockSamProvider,
    SYNTHETIC_MOCK_LABEL,
)
from mydrak.workflow.pipeline import (
    MockWorkflowCache, TestOnlySignalOverride, WorkflowPipelineError,
    run_synthetic_mock_workflow,
)
from mydrak.workflow import pipeline
from mydrak.util.config import load_yaml

ROOT = Path(__file__).parents[1]
SAFETY = load_safety_card(ROOT / "kb/cards/general_safety.yaml")
EVIDENCE = ProcessingEvidence(
    provider_mode=ProviderMode.STANDARD,
    provider_mode_verified=True,
    rights_confirmed=True,
    public_test_provenance_verified=True,
)


def _photo(color=(40, 150, 45)):
    image = Image.new("RGB", (32, 24), color)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _diagnosis(issue="SYNTHETIC_TEST"):
    return {
        "plant_visible": True,
        "crop": "synthetic_crop",
        "issue": issue,
        "alternatives": [],
        "symptoms_observed": ["Synthetic placeholder symptom"],
        "image_issues": [],
        "stated_confidence": 0.8,
        "segment_prompts": ["synthetic leaf prompt"],
    }


def _providers(*, disagreement=False, sam_fail=False, empty_masks=False):
    glimmer = DeterministicMockDiagnosisProvider(
        (_diagnosis(), _diagnosis("SYNTHETIC_OTHER" if disagreement else "SYNTHETIC_TEST"))
    )
    spark = DeterministicMockDiagnosisProvider((_diagnosis("SYNTHETIC_OTHER"),))
    rows = ("00", "00") if empty_masks else ("11", "11")
    lesions = ("00", "00") if empty_masks else ("10", "00")
    sam = DeterministicMockSamProvider(rows, lesions, fail=sam_fail)
    return glimmer, spark, sam


def _run(*, override=None, policy="public_test", evidence=EVIDENCE, photo=None,
         providers=None, cache=None, store=None, language="en", user_hash=None):
    glimmer, spark, sam = providers or _providers()
    cache = cache or MockWorkflowCache()
    store = store or TraceStore(":memory:")
    result = run_synthetic_mock_workflow(
        photo if photo is not None else _photo(), language,
        glimmer_provider=glimmer, spark_provider=spark, sam_provider=sam,
        trace_store=store, cache=cache, data_policy_value=policy,
        evidence=evidence, signal_override=override, user_hash=user_hash,
    )
    if result.reply is not None:
        assert result.reply.startswith(SYNTHETIC_MOCK_LABEL)
        assert "preliminary guidance" in result.reply
        assert any(word in result.reply for word in ("fairly sure", "not sure", "cannot tell"))
        assert SAFETY["safety_line"] in result.reply
    return result, (glimmer, spark, sam), cache, store


def _override(*, s2=1.0, s3=1.0, s4=1.0, word="fairly sure"):
    return TestOnlySignalOverride(s2=s2, s3=s3, s4=s4, confidence_word=word)


def test_answer_uses_only_synthetic_test_card_and_has_safe_labels_and_trace():
    digest = "a" * 64
    result, (glimmer, spark, sam), _, store = _run(
        override=_override(), user_hash=digest,
    )
    assert result.action == "answer"
    assert result.provenance == SYNTHETIC_MOCK_LABEL
    assert "SYNTHETIC / MOCK" in result.reply
    assert "preliminary guidance" in result.reply
    assert "fairly sure" in result.reply
    assert SAFETY["safety_line"] in result.reply
    assert result.overlay_bytes and result.severity_pct == 25.0
    assert result.severity_band == "moderate"
    assert glimmer.generate_calls == 2 and spark.generate_calls == 0 and sam.generate_calls == 1
    case = store.get_case(result.case_id)
    assert case["kb_card_id"] == "SYNTHETIC_TEST"
    assert case["user_hash"] == digest and len(case["image_hash"]) == 64
    assert glimmer.bound_image_hash == case["image_hash"]
    assert spark.bound_image_hash is None
    assert store.get_signals(result.case_id)["decision"] == "answer"
    names = [step["step_name"] for step in store.get_steps(result.case_id)]
    assert names.index("intake_gate") < names.index("preprocessing") < names.index("cache_lookup")
    assert names.index("cache_lookup") < names.index("kb_signal_match") < names.index("glimmer_samples")
    assert names.index("cache_lookup") < names.index("glimmer_samples") < names.index("decider")
    assert names.index("decider") < names.index("sam_parse") < names.index("mask_decode")
    assert names.index("severity_overlay") < names.index("kb_lookup") < names.index("reply_compose")
    trace_steps = store.get_steps(result.case_id)
    assert {step["model"] for step in trace_steps if step["step_name"] in {"glimmer_samples", "sam_parse", "reply_compose"}} == {"synthetic_mock"}
    rendered_trace = repr((case, store.get_steps(result.case_id), store.get_signals(result.case_id)))
    assert "Synthetic placeholder symptom" not in rendered_trace
    assert _photo().hex() not in rendered_trace


def test_ask_outcome_escalates_once_then_uses_synthetic_kb_question():
    result, (glimmer, spark, _), _, store = _run(
        override=_override(s2=0.0, s4=0.0, word="not sure"),
    )
    assert result.action == "ask"
    assert "not sure" in result.reply and "preliminary guidance" in result.reply
    assert "Synthetic placeholder question?" in result.reply
    assert SAFETY["safety_line"] in result.reply
    assert glimmer.generate_calls == 2 and spark.generate_calls == 1
    assert result.spark_escalations == 1
    assert store.get_signals(result.case_id)["escalated"] == 1


def test_production_like_missing_s3_s4_refers_without_using_placeholder_thresholds_as_evidence():
    result, (_, spark, _), _, store = _run(override=None)
    assert result.action == "refer"
    signals = store.get_signals(result.case_id)
    assert signals["s3"] is None and signals["s4"] is None
    assert spark.generate_calls == 0
    assert "cannot tell" in result.reply
    assert SAFETY["safety_line"] in result.reply


def test_retake_outcome_is_only_exercised_by_explicit_test_override():
    result, (_, spark, _), _, store = _run(override=_override(s3=0.0, word="not sure"))
    assert result.action == "retake"
    assert result.overlay_bytes is None and result.severity_pct is None
    assert "not sure" in result.reply and SAFETY["safety_line"] in result.reply
    assert spark.generate_calls == 0
    assert store.get_signals(result.case_id)["s3"] == 0.0


def test_glimmer_disagreement_triggers_exactly_one_spark_escalation():
    result, (glimmer, spark, _), _, store = _run(
        providers=_providers(disagreement=True),
        override=_override(s2=0.0, word="not sure"),
    )
    assert glimmer.generate_calls == 2
    assert spark.generate_calls == result.spark_escalations == 1
    assert result.action == "ask"
    assert store.get_signals(result.case_id)["escalated"] == 1


def test_glimmer_unavailable_goes_directly_to_one_spark_then_refers():
    glimmer, spark, sam = _providers()
    glimmer.fail_calls = frozenset({0})
    result, _, _, store = _run(providers=(glimmer, spark, sam))
    assert result.action == "refer"
    assert glimmer.generate_calls == 2 and spark.generate_calls == 1
    assert result.spark_escalations == 1 and sam.generate_calls == 0
    assert "cannot tell" in result.reply
    assert store.get_signals(result.case_id)["escalated"] == 1


def test_spark_failure_falls_back_to_tier1_referral_without_untrusted_claims():
    glimmer, _, sam = _providers()
    spark = DeterministicMockDiagnosisProvider((_diagnosis(),), fail_calls=frozenset({0}))
    result, _, _, store = _run(
        providers=(glimmer, spark, sam),
        override=_override(s2=0.0, s4=0.0, word="not sure"),
    )
    assert result.action == "refer"
    assert result.spark_escalations == spark.generate_calls == 1
    assert "cannot tell" in result.reply
    assert store.get_signals(result.case_id)["decision"] == "refer"


@pytest.mark.parametrize("mode", ["failure", "empty"])
def test_sam_failure_or_empty_mask_has_no_severity_overlay_and_explains_unavailability(mode):
    providers = _providers(sam_fail=mode == "failure", empty_masks=mode == "empty")
    result, _, _, _ = _run(override=_override(), providers=providers)
    assert result.action == "answer"
    assert result.severity_pct is None and result.overlay_bytes is None
    assert "SAM overlay and severity are unavailable" in result.reply


def test_repeated_image_and_language_uses_cache_without_provider_calls_but_traces_both_runs():
    store, cache = TraceStore(":memory:"), MockWorkflowCache()
    providers = _providers()
    first, _, _, _ = _run(override=_override(), store=store, cache=cache, providers=providers)
    counts = tuple(provider.generate_calls for provider in providers)
    second, _, _, _ = _run(override=_override(), store=store, cache=cache, providers=providers)
    assert first.action == second.action == "answer"
    assert second.cache_hit is True and first.case_id != second.case_id
    assert second.overlay_bytes == first.overlay_bytes
    assert second.severity_pct == first.severity_pct and second.severity_band == first.severity_band
    assert tuple(provider.generate_calls for provider in providers) == counts
    assert store.get_case(first.case_id) is not None and store.get_case(second.case_id) is not None
    assert store.get_signals(second.case_id)["decision"] == "answer"
    assert "cache_lookup" in {step["step_name"] for step in store.get_steps(second.case_id)}


def test_local_pipeline_and_mocks_cannot_open_network_sockets(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("offline workflow attempted a network socket")

    monkeypatch.setattr(socket, "socket", denied)
    result, _, _, _ = _run(override=_override())
    assert result.action == "answer"
    for path in (
        ROOT / "src/mydrak/workflow/pipeline.py",
        ROOT / "src/mydrak/workflow/mock_providers.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert imports.isdisjoint({"socket", "requests", "httpx", "urllib", "http", "aiohttp"})


def test_policy_denial_stops_before_preprocessing_or_any_provider_and_is_traced(monkeypatch):
    def forbidden_preprocess(*args, **kwargs):
        raise AssertionError("preprocessing must stop after policy denial")

    def forbidden_kb(*args, **kwargs):
        raise AssertionError("KB/model stages must stop after policy denial")

    monkeypatch.setattr(pipeline, "preprocess_image_bytes", forbidden_preprocess)
    monkeypatch.setattr(pipeline, "load_card", forbidden_kb)
    result, providers, _, store = _run(policy="private", evidence=None)
    assert result.action == "blocked" and result.reply is None
    assert tuple(provider.generate_calls for provider in providers) == (0, 0, 0)
    case = store.get_case(result.case_id)
    assert case is not None and case["image_hash"] is None
    assert store.get_signals(result.case_id)["decision"] == "refer"


def test_invalid_photo_is_fail_closed_and_still_gets_case_steps_and_signal_trace():
    result, providers, _, store = _run(photo=b"not an image")
    assert result.action == "blocked" and result.reply is None
    assert tuple(provider.generate_calls for provider in providers) == (0, 0, 0)
    assert store.get_case(result.case_id) is not None
    assert store.get_signals(result.case_id)["decision"] == "refer"


def test_truncated_image_that_passes_header_gate_fails_preprocessing_and_is_traced():
    truncated = _photo()[:30]
    result, providers, _, store = _run(photo=truncated)
    assert result.action == "blocked" and result.reply is None
    assert tuple(provider.generate_calls for provider in providers) == (0, 0, 0)
    assert store.get_case(result.case_id) is not None
    assert "preprocessing" in {step["step_name"] for step in store.get_steps(result.case_id)}
    assert store.get_signals(result.case_id) is not None


def test_hindi_stays_unavailable_and_no_unreviewed_translation_is_emitted():
    result, providers, _, store = _run(language="hi", override=_override())
    assert result.action == "refer" and result.reply is None
    assert tuple(provider.generate_calls for provider in providers) == (0, 0, 0)
    assert store.get_case(result.case_id)["lang"] == "hi"
    assert store.get_signals(result.case_id) is not None


def test_production_provider_and_malformed_test_override_are_rejected():
    providers = _providers()
    with pytest.raises(WorkflowPipelineError, match="deterministic mock"):
        run_synthetic_mock_workflow(
            _photo(), "en", glimmer_provider=object(), spark_provider=providers[1],
            sam_provider=providers[2], trace_store=TraceStore(":memory:"),
            cache=MockWorkflowCache(), data_policy_value="public_test", evidence=EVIDENCE,
        )
    with pytest.raises(WorkflowPipelineError, match="signal value"):
        _run(override=TestOnlySignalOverride(s3=1.5))
    assert "test_signal_override" not in load_yaml(ROOT / "config/thresholds.yaml")
