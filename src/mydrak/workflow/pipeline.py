"""Offline end-to-end photo workflow using deterministic mocks only."""

from dataclasses import dataclass
from pathlib import Path
import re
import time
import uuid

from mydrak.decider.extraction import (
    DecisionResult, SignalMeasurement, SignalSet, extract_agreement,
    extract_kb_match, extract_quality, route_signals, unavailable,
)
from mydrak.intake.adapter import coerce_image
from mydrak.kb.loader import load_card, load_safety_card, validate_disease_card
from mydrak.privacy.data_policy import (
    DataClass, DataPolicyError, ProcessingEvidence, parse_data_policy,
    require_external_processing_allowed,
)
from mydrak.sam.output import SamLimits, SamSegmentation, parse_sam_output
from mydrak.sam.overlay import T08Result, decode_synthetic_grid, render_synthetic_fixture
from mydrak.trace.store import TraceStep, TraceStore
from mydrak.vision.diagnosis import (
    DiagnosisOutput, DiagnosisResult, DiagnosisStatus, run_diagnosis_validation,
)
from mydrak.vision.preprocessing import PreprocessedImage, preprocess_image_bytes
from mydrak.vision.source import describe_image_bytes
from mydrak.workflow.mock_providers import (
    DeterministicMockDiagnosisProvider, DeterministicMockSamProvider,
    MockSamResponse, SYNTHETIC_MOCK_LABEL, SyntheticSamProvider,
)
from mydrak.workflow.pipeline_support import (
    MockWorkflowCache, OfflineWorkflowResult, TestOnlySignalOverride,
    apply_signal_override, cache_key, cached_overlay, load_router_config,
    make_snapshot, make_step, record_workflow_trace, render_workflow_reply,
    signal_set_from_values, validate_signal_override,
)

_ROOT = Path(__file__).resolve().parents[3]
_TEST_CARD = _ROOT / "tests" / "fixtures" / "kb" / "SYNTHETIC_TEST.yaml"
_SAFETY_CARD = _ROOT / "kb" / "cards" / "general_safety.yaml"
_THRESHOLDS = _ROOT / "config" / "thresholds.yaml"
_MAX_SPARK_ESCALATIONS = 1


class WorkflowPipelineError(ValueError):
    """Invalid offline workflow dependency or input."""


@dataclass
class _RunState:
    case_id: str
    started: float
    language: str
    policy: str | None
    user_hash: str | None
    steps: list[TraceStep]
    image_hash: str | None = None


def run_synthetic_mock_workflow(
    photo_bytes: bytes,
    language: str,
    *,
    glimmer_provider: DeterministicMockDiagnosisProvider,
    spark_provider: DeterministicMockDiagnosisProvider,
    sam_provider: SyntheticSamProvider,
    trace_store: TraceStore,
    cache: MockWorkflowCache,
    data_policy_value: str | None,
    evidence: ProcessingEvidence | None,
    signal_override: TestOnlySignalOverride | None = None,
    user_hash: str | None = None,
) -> OfflineWorkflowResult:
    """Run the offline path: intake, preprocess, cache, mock models, reply, trace.

    This entry point accepts only deterministic mock providers. The optional
    signal override is a typed test-only input, never loaded from config.
    """
    _validate_dependencies(language, trace_store, cache, glimmer_provider,
                           spark_provider, sam_provider, signal_override, user_hash)
    state = _RunState(
        uuid.uuid4().hex, time.perf_counter(), language,
        data_policy_value if isinstance(data_policy_value, str) and data_policy_value in {"private", "public_test"} else None,
        user_hash, [],
    )
    signals = SignalSet()
    decision = DecisionResult("refer", None, "not_started")

    def finish(action: str, reason: str, reply: str | None,
               overlay: T08Result | None = None, *, escalated: bool = False,
               sparks: int = 0, kb_id: str | None = None,
               cache_hit: bool = False) -> OfflineWorkflowResult:
        state.steps.append(TraceStep("workflow_outcome", action, 0.0, model="synthetic_mock"))
        elapsed = max(0.0, (time.perf_counter() - state.started) * 1000)
        measured = sum(item.latency_ms for item in state.steps)
        if elapsed > measured:
            state.steps.append(TraceStep("workflow_overhead", "completed", elapsed - measured))
        result = OfflineWorkflowResult(
            action, reply, reason, state.case_id,
            overlay.severity_pct if overlay else None,
            overlay.severity_band if overlay else None,
            overlay.overlay_bytes if overlay else None,
            overlay.overlay_mime_type if overlay else None,
            cache_hit=cache_hit, spark_escalations=sparks,
        )
        record_workflow_trace(
            trace_store, result, language, state.policy, user_hash,
            state.image_hash, state.steps, signals, decision.score, escalated, kb_id,
        )
        if not cache_hit and state.image_hash is not None:
            cache.put(
                cache_key(state.image_hash, language, state.policy, signal_override, user_hash),
                make_snapshot(result, signals, escalated, kb_id, decision.score),
            )
        return result

    started = time.perf_counter()
    try:
        descriptor = coerce_image(describe_image_bytes(photo_bytes))
    except (TypeError, ValueError):
        state.steps.append(make_step("intake_gate", "rejected", started))
        return finish("blocked", "invalid_image", None)
    try:
        policy = parse_data_policy(data_policy_value)
        if not isinstance(evidence, ProcessingEvidence):
            raise DataPolicyError("public-test processing evidence is unavailable")
        require_external_processing_allowed(policy, DataClass.PUBLIC_TEST, evidence)
    except DataPolicyError:
        state.steps.append(make_step("intake_gate", "blocked", started))
        return finish("blocked", "intake_policy_denied", None)
    state.steps.append(make_step("intake_gate", "allowed", started))

    started = time.perf_counter()
    try:
        image = preprocess_image_bytes(photo_bytes)
    except (TypeError, ValueError, OSError):
        state.steps.append(make_step("preprocessing", "failed", started))
        return finish("blocked", "preprocessing_failed", None)
    state.image_hash = image.image_hash
    state.steps.append(make_step("preprocessing", "completed", started))

    key = cache_key(image.image_hash, language, state.policy, signal_override, user_hash)
    started = time.perf_counter()
    cached = cache.get(key)
    state.steps.append(make_step("cache_lookup", "hit" if cached else "miss", started))
    if cached is not None:
        signals = signal_set_from_values(cached.signals)
        decision = DecisionResult(cached.action, cached.signals[4], "cached_synthetic_result")
        return finish(
            cached.action, cached.reason, cached.reply, cached_overlay(cached),
            escalated=cached.escalated, sparks=cached.spark_escalations,
            kb_id=cached.kb_card_id, cache_hit=True,
        )
    if language == "hi":
        return finish("refer", "hindi_review_unavailable", None)

    try:
        card = validate_disease_card(load_card(_TEST_CARD), allow_synthetic_test=True)
        safety = load_safety_card(_SAFETY_CARD)
    except (OSError, TypeError, ValueError):
        state.steps.append(TraceStep("kb_signal_match", "unavailable", 0.0, model="synthetic_test"))
        return finish("blocked", "offline_content_unavailable", None)
    state.steps.append(TraceStep("kb_signal_match", "synthetic_test_card", 0.0, model="synthetic_test"))

    glimmer_provider.bind_image(image.image_hash)
    started = time.perf_counter()
    crops, diseases = (card["crop"],), (card["id"], "SYNTHETIC_OTHER")
    first = run_diagnosis_validation(glimmer_provider, supported_crops=crops, disease_ids=diseases)
    second = run_diagnosis_validation(glimmer_provider, supported_crops=crops, disease_ids=diseases)
    valid_samples = _valid(first) and _valid(second)
    sample_step = make_step("glimmer_samples", "completed" if valid_samples else "unavailable", started)
    state.steps.append(TraceStep(sample_step.step_name, sample_step.outcome, sample_step.latency_ms, model="synthetic_mock"))
    if not valid_samples:
        spark_provider.bind_image(image.image_hash)
        spark_started = time.perf_counter()
        spark = run_diagnosis_validation(spark_provider, supported_crops=crops, disease_ids=diseases)
        spark_step = make_step("spark_escalation", "completed" if _valid(spark) else "unavailable", spark_started)
        state.steps.append(TraceStep(spark_step.step_name, spark_step.outcome, spark_step.latency_ms, model="synthetic_mock"))
        decision = DecisionResult("refer", None, "glimmer_unavailable")
        return finish(
            "refer", "glimmer_unavailable", _reply("refer", safety, None, "cannot tell", None),
            escalated=True, sparks=_MAX_SPARK_ESCALATIONS,
        )

    left, right = first.output, second.output
    assert isinstance(left, DiagnosisOutput) and isinstance(right, DiagnosisOutput)
    s1 = extract_agreement(_labels(left), _labels(right))
    same = (left.crop, left.issue) == (right.crop, right.issue)
    s2 = extract_kb_match(left.issue, [card], left.symptoms_observed) if same else unavailable("tier1_labels_disagree")
    signals = apply_signal_override(
        SignalSet(s1, s2, extract_quality(), unavailable("s4_mapping_unresolved")), signal_override,
    )
    try:
        weights, thresholds = load_router_config(_THRESHOLDS)
    except (OSError, TypeError, ValueError):
        weights, thresholds = {}, {}
    started = time.perf_counter()
    decision = route_signals(
        signals, weights=weights, thresholds=thresholds,
        escalated=False, followups_used=0,
    )
    state.steps.append(make_step("decider", decision.action, started))

    escalated = False
    spark_calls = 0
    if decision.action == "escalate":
        escalated, spark_calls = True, 1
        spark_provider.bind_image(image.image_hash)
        started = time.perf_counter()
        spark = run_diagnosis_validation(spark_provider, supported_crops=crops, disease_ids=diseases)
        spark_step = make_step("spark_escalation", "completed" if _valid(spark) else "unavailable", started)
        state.steps.append(TraceStep(spark_step.step_name, spark_step.outcome, spark_step.latency_ms, model="synthetic_mock"))
        if _valid(spark):
            output = spark.output
            assert isinstance(output, DiagnosisOutput)
            spark_s2 = extract_kb_match(output.issue, [card], output.symptoms_observed)
            signals = apply_signal_override(
                SignalSet(s1, spark_s2, signals.s3, signals.s4), signal_override, keep_s2=True,
            )
            decision = route_signals(
                signals, weights=weights, thresholds=thresholds,
                escalated=True, followups_used=0,
            )
        else:
            decision = DecisionResult("refer", None, "spark_unavailable_fallback")
        state.steps.append(TraceStep("decider_rescore", decision.action, 0.0))

    # A retake decision is terminal per B3; other outcomes continue through the SAM/KB demo path.
    overlay = None
    sam_reason = ""
    if decision.action != "retake":
        started = time.perf_counter()
        overlay, sam_reason = _run_sam(sam_provider, image)
        state.steps.extend([
            TraceStep("sam_parse", "completed" if overlay.reason_code != "sam_provider_failed" else "failed", max(0.0, time.perf_counter() - started) * 1000, model="synthetic_mock"),
            TraceStep("mask_decode", "completed" if overlay.reason_code not in _MASK_FAILURES else "failed", 0.0, model="synthetic_grid_v1"),
            TraceStep("severity_overlay", "completed" if overlay.severity_pct is not None else "unavailable", 0.0, model="synthetic_mask"),
        ])
    state.steps.append(TraceStep("kb_lookup", "synthetic_test_card", 0.0, model="synthetic_test"))
    action = decision.action
    if action == "answer":
        reply = _reply("answer", safety, card, signal_override.confidence_word if signal_override else "cannot tell", overlay.severity_pct if overlay else None, overlay_reason=sam_reason)
        kb_id = card["id"]
    elif action == "ask":
        reply = _reply("ask", safety, card, "not sure", None, question_id="synthetic_question", overlay_reason=sam_reason)
        kb_id = card["id"]
    elif action == "retake":
        reply = _reply("retake", safety, None, "not sure", None)
        kb_id = None
    else:
        action = "refer"
        reply = _reply("refer", safety, None, "cannot tell", None, overlay_reason=sam_reason)
        kb_id = None
    state.steps.append(TraceStep("reply_compose", "completed", 0.0, model="synthetic_mock"))
    return finish(action, "decider_" + action, reply, overlay,
                  escalated=escalated, sparks=spark_calls, kb_id=kb_id)


def _validate_dependencies(language, store, cache, glimmer, spark, sam, override, user_hash) -> None:
    if type(store) is not TraceStore or type(cache) is not MockWorkflowCache:
        raise WorkflowPipelineError("offline trace store and mock cache are required")
    if type(glimmer) is not DeterministicMockDiagnosisProvider or type(spark) is not DeterministicMockDiagnosisProvider:
        raise WorkflowPipelineError("only deterministic mock diagnosis providers are accepted")
    if type(sam) is not DeterministicMockSamProvider or sam.provenance != SYNTHETIC_MOCK_LABEL:
        raise WorkflowPipelineError("only the deterministic mock SAM provider is accepted")
    if not isinstance(language, str) or language not in {"en", "hi"}:
        raise WorkflowPipelineError("language is unsupported")
    if user_hash is not None and (not isinstance(user_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", user_hash)):
        raise WorkflowPipelineError("user identity must be a SHA-256 digest")
    try:
        validate_signal_override(override)
    except ValueError as exc:
        raise WorkflowPipelineError(str(exc)) from None


def _run_sam(provider: SyntheticSamProvider, image: PreprocessedImage) -> tuple[T08Result, str]:
    try:
        response = provider.generate(image)
        if not isinstance(response, MockSamResponse) or response.provenance != SYNTHETIC_MOCK_LABEL:
            raise ValueError
        segmentation: SamSegmentation = parse_sam_output(response.payload)
        masks = {item.id: item.mask for item in segmentation.objects}
        for role in ("leaf", "lesion"):
            decode_synthetic_grid(masks[role], SamLimits())
        result = render_synthetic_fixture(segmentation, image, leaf_object_id="leaf", lesion_object_id="lesion")
        return result, "" if result.severity_pct is not None else result.reason_code
    except (ValueError, TypeError, RuntimeError, KeyError, OSError):
        return T08Result(None, None, None, None, "sam_provider_failed", "synthetic-fixture", None), "sam_provider_failed"


def _reply(action, safety, card, confidence, severity, *, question_id=None, overlay_reason=""):
    return render_workflow_reply(
        action, safety, card, confidence, severity,
        question_id=question_id, overlay_reason=overlay_reason,
    )


def _labels(output: DiagnosisOutput) -> dict[str, str]:
    return {"crop": output.crop, "disease": output.issue}


def _valid(result: DiagnosisResult) -> bool:
    return result.status is DiagnosisStatus.VALID and isinstance(result.output, DiagnosisOutput)


_MASK_FAILURES = frozenset({
    "mask_decode_failed", "empty_leaf_mask", "empty_lesion_mask",
    "leaf_mask_missing", "lesion_mask_missing", "mask_size_mismatch",
    "sam_provider_failed",
})
