"""Offline end-to-end photo workflow using deterministic mocks only."""

from dataclasses import dataclass
from pathlib import Path
import time
import uuid

from mydrak.decider.extraction import (
    DecisionResult, SignalSet, extract_agreement,
    extract_kb_match, extract_quality, route_signals, unavailable,
)
from mydrak.intake.adapter import coerce_image
from mydrak.kb.loader import load_card, load_safety_card, validate_disease_card
from mydrak.privacy.data_policy import (
    DataClass, DataPolicyError, ProcessingEvidence, parse_data_policy,
    require_external_processing_allowed,
)
from mydrak.sam.overlay import T08Result
from mydrak.trace.store import (
    CachedResponse, TraceError, TraceStep, TraceStore, WORKFLOW_CACHE_PROVENANCE,
)
from mydrak.vision.diagnosis import (
    DiagnosisOutput, DiagnosisStatus,
)
from mydrak.vision.preprocessing import preprocess_image_bytes
from mydrak.vision.source import describe_image_bytes
from mydrak.workflow.mock_providers import (
    DeterministicMockDiagnosisProvider, DeterministicMockSamProvider,
    SYNTHETIC_MOCK_LABEL, SyntheticSamProvider,
)
from mydrak.workflow.pipeline_support import (
    OfflineWorkflowResult, TestOnlySignalOverride, apply_signal_override,
    cache_key, diagnosis_labels as _labels, is_valid_diagnosis as _valid,
    load_router_config, make_step, record_workflow_trace,
    reply_for_action as _reply, run_diagnosis_with_retries, run_mock_sam,
    unsupported_plant_reply, validate_pipeline_dependencies, workflow_cache_payload,
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
    data_policy_value: str | None,
    evidence: ProcessingEvidence | None,
    signal_override: TestOnlySignalOverride | None = None,
    user_hash: str | None = None,
    voice_hint: str | None = None,
) -> OfflineWorkflowResult:
    """Run the offline path: intake, preprocess, cache, mock models, reply, trace.

    This entry point accepts only deterministic mock providers. The optional
    signal override is a typed test-only input, never loaded from config.
    """
    try:
        validate_pipeline_dependencies(
            language, trace_store, glimmer_provider, spark_provider,
            sam_provider, signal_override, user_hash, voice_hint,
        )
    except ValueError as exc:
        raise WorkflowPipelineError(str(exc)) from None
    state = _RunState(
        uuid.uuid4().hex, time.perf_counter(), language,
        data_policy_value if isinstance(data_policy_value, str) and data_policy_value in {"private", "public_test"} else None,
        user_hash, [],
    )
    signals = SignalSet()
    decision = DecisionResult("refer", None, "not_started")

    cache_digest: str | None = None

    def finish(action: str, reason: str, reply: str | None,
               overlay: T08Result | None = None, *, escalated: bool = False,
               sparks: int = 0, kb_id: str | None = None,
               cache_hit: bool = False, cached: CachedResponse | None = None) -> OfflineWorkflowResult:
        state.steps.append(TraceStep("workflow_outcome", action, 0.0, model="synthetic_mock"))
        elapsed = max(0.0, (time.perf_counter() - state.started) * 1000)
        measured = sum(item.latency_ms for item in state.steps)
        if elapsed > measured:
            state.steps.append(TraceStep("workflow_overhead", "completed", elapsed - measured))
        result = OfflineWorkflowResult(
            action, reply, reason, state.case_id,
            cached.severity_pct if cached else overlay.severity_pct if overlay else None,
            cached.severity_band if cached else overlay.severity_band if overlay else None,
            overlay.overlay_bytes if overlay else None,
            overlay.overlay_mime_type if overlay else None,
            cache_hit=cache_hit, spark_escalations=sparks,
        )
        if not cache_hit and cache_digest is not None and reply is not None and action in {"answer", "ask", "refer", "retake"}:
            try:
                trace_store.put_cache(cache_digest, workflow_cache_payload(result))
            except TraceError:
                state.steps.append(TraceStep("cache_write", "failed", 0.0, model="synthetic_mock", error_code="cache_write_failed"))
        record_workflow_trace(
            trace_store, result, language, state.policy, user_hash,
            state.image_hash, state.steps, signals, decision.score, escalated, kb_id,
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

    key = cache_key(image.image_hash, language, voice_hint)
    cache_digest = key
    started = time.perf_counter()
    try:
        cached = trace_store.get_cache(key)
    except TraceError:
        cached = None
        state.steps.append(make_step("cache_lookup", "invalid", started))
        return finish("blocked", "cache_entry_invalid", None, cache_hit=True)
    state.steps.append(make_step("cache_lookup", "hit" if cached else "miss", started))
    if cached is not None:
        if cached.provenance != WORKFLOW_CACHE_PROVENANCE or cached.reply is None or cached.reason is None:
            return finish("blocked", "cache_entry_incompatible", None, cache_hit=True)
        decision = DecisionResult(cached.status, None, "persistent_synthetic_cache")
        cached_reply = cached.reply
        if cached.severity_pct is not None:
            cached_reply += "\nThe synthetic overlay image is not stored in persistent cache."
        return finish(
            cached.status, cached.reason, cached_reply, cache_hit=True, cached=cached,
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
    first, first_retries = run_diagnosis_with_retries(
        glimmer_provider, supported_crops=crops, disease_ids=diseases,
    )
    first_step = make_step("glimmer_sample_1", first.status.value, started)
    state.steps.append(TraceStep(first_step.step_name, first_step.outcome, first_step.latency_ms,
                                 model="synthetic_mock", retries=first_retries,
                                 error_code="provider_failure" if first.status is DiagnosisStatus.UNAVAILABLE else None,
                                 started_at=first_step.started_at))
    if first.status is DiagnosisStatus.UNKNOWN:
        decision = DecisionResult("refer", None, "invalid_glimmer_output_unknown")
        return finish("refer", "invalid_glimmer_output_unknown",
                      unsupported_plant_reply(safety))
    if first.status is DiagnosisStatus.UNAVAILABLE:
        spark_provider.bind_image(image.image_hash)
        spark_started = time.perf_counter()
        spark, spark_retries = run_diagnosis_with_retries(
            spark_provider, supported_crops=crops, disease_ids=diseases,
        )
        spark_step = make_step("spark_escalation", spark.status.value, spark_started)
        state.steps.append(TraceStep(spark_step.step_name, spark_step.outcome, spark_step.latency_ms,
                                     model="synthetic_mock", retries=spark_retries,
                                     error_code="provider_failure" if spark.status is DiagnosisStatus.UNAVAILABLE else None,
                                     started_at=spark_step.started_at))
        decision = DecisionResult("refer", None, "glimmer_unavailable")
        return finish(
            "refer", "glimmer_unavailable", _reply("refer", safety, None, "cannot tell", None),
            escalated=True, sparks=_MAX_SPARK_ESCALATIONS,
        )

    second_started = time.perf_counter()
    second, second_retries = run_diagnosis_with_retries(
        glimmer_provider, supported_crops=crops, disease_ids=diseases,
    )
    second_step = make_step("glimmer_sample_2", second.status.value, second_started)
    state.steps.append(TraceStep(second_step.step_name, second_step.outcome, second_step.latency_ms,
                                 model="synthetic_mock", retries=second_retries,
                                 error_code="provider_failure" if second.status is DiagnosisStatus.UNAVAILABLE else None,
                                 started_at=second_step.started_at))
    if second.status is DiagnosisStatus.UNKNOWN:
        decision = DecisionResult("refer", None, "invalid_glimmer_output_unknown")
        return finish("refer", "invalid_glimmer_output_unknown",
                      unsupported_plant_reply(safety))
    if second.status is DiagnosisStatus.UNAVAILABLE:
        spark_provider.bind_image(image.image_hash)
        spark_started = time.perf_counter()
        spark, spark_retries = run_diagnosis_with_retries(
            spark_provider, supported_crops=crops, disease_ids=diseases,
        )
        spark_step = make_step("spark_escalation", spark.status.value, spark_started)
        state.steps.append(TraceStep(spark_step.step_name, spark_step.outcome, spark_step.latency_ms,
                                     model="synthetic_mock", retries=spark_retries,
                                     error_code="provider_failure" if spark.status is DiagnosisStatus.UNAVAILABLE else None,
                                     started_at=spark_step.started_at))
        decision = DecisionResult("refer", None, "glimmer_unavailable")
        return finish("refer", "glimmer_unavailable",
                      _reply("refer", safety, None, "cannot tell", None),
                      escalated=True, sparks=_MAX_SPARK_ESCALATIONS)
    left, right = first.output, second.output
    assert isinstance(left, DiagnosisOutput) and isinstance(right, DiagnosisOutput)
    if not left.plant_visible or not right.plant_visible or left.crop == "unknown" or right.crop == "unknown":
        decision = DecisionResult("refer", None, "unsupported_plant_or_crop")
        return finish("refer", "unsupported_plant_or_crop",
                      unsupported_plant_reply(safety))
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
        spark, spark_retries = run_diagnosis_with_retries(
            spark_provider, supported_crops=crops, disease_ids=diseases,
        )
        spark_step = make_step("spark_escalation", spark.status.value, started)
        state.steps.append(TraceStep(spark_step.step_name, spark_step.outcome, spark_step.latency_ms,
                                     model="synthetic_mock", retries=spark_retries,
                                     error_code="provider_failure" if spark.status is DiagnosisStatus.UNAVAILABLE else None,
                                     started_at=spark_step.started_at))
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
        overlay, sam_reason = run_mock_sam(sam_provider, image)
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




_MASK_FAILURES = frozenset({
    "mask_decode_failed", "empty_leaf_mask", "empty_lesion_mask",
    "leaf_mask_missing", "lesion_mask_missing", "mask_size_mismatch",
    "sam_provider_failed",
})
