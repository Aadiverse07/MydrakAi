"""Explicit Spark-only pipeline branch with fail-closed production routing."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
import re
import time
import uuid
from pathlib import Path
from typing import Any

from mydrak.decider.extraction import (
    DecisionResult, SignalSet, extract_confidence, extract_quality,
    route_signals, unavailable,
)
from mydrak.intake.adapter import coerce_image
from mydrak.kb.loader import load_safety_card
from mydrak.live.clients import SparkClient
from mydrak.privacy.data_policy import (
    DataClass, DataPolicy, DataPolicyError, ProcessingEvidence,
    ProviderMode, parse_data_policy, require_external_processing_allowed,
)
from mydrak.reply.composer import compose_reply
from mydrak.trace.store import TraceCase, TraceError, TraceStep, TraceStore
from mydrak.vision.diagnosis import DiagnosisStatus, run_diagnosis_validation
from mydrak.vision.preprocessing import PreprocessedImage, preprocess_image_bytes
from mydrak.vision.source import describe_image_bytes
from mydrak.workflow.mock_providers import DeterministicMockSamProvider
from mydrak.workflow.pipeline_support import (
    cache_key, load_router_config, make_step, run_mock_sam,
)

_ROOT = Path(__file__).resolve().parents[3]
_SAFETY = _ROOT / "kb" / "cards" / "general_safety.yaml"
_THRESHOLDS = _ROOT / "config" / "thresholds.yaml"


@dataclass(frozen=True)
class SparkOnlyResult:
    """Sanitized result: validated model claims are never returned as diagnosis."""

    action: str
    reason: str
    case_id: str
    reply: str | None
    provenance: str = "live-spark"
    confidence_word: str = "cannot tell"
    spark_escalations: int = 0
    overlay_bytes: None = None
    severity_pct: None = None
    latency_ms: float = 0.0
    tokens_in: int | None = None
    tokens_out: int | None = None
    estimated_cost_usd: Decimal | None = None


def run_spark_only_workflow(
    photo_bytes: bytes,
    language: str,
    *,
    trace_store: TraceStore,
    spark_provider_factory: Callable[..., SparkClient],
    provider_config: Mapping[str, Any],
    data_policy_value: str | None,
    data_class: DataClass,
    image_provenance: str | None,
    evidence: ProcessingEvidence,
    use_contributor: bool = False,
    supported_crops: tuple[str, ...] = (),
    disease_ids: tuple[str, ...] = (),
    user_hash: str | None = None,
    voice_hint: str | None = None,
) -> SparkOnlyResult:
    """Run only when explicitly selected; it never falls through to mock/replay.

    The absence of Glimmer selects the B11 direct-to-Spark path. S1/S2/S3 are
    unavailable in production, so calling the unchanged B3 policy always
    fails closed. Synthetic SAM output is parsed only for step accounting and
    is deliberately omitted from the returned result.
    """
    if type(trace_store) is not TraceStore:
        raise ValueError("local trace store is required")
    if not isinstance(provider_config, Mapping):
        raise ValueError("Spark configuration is invalid")
    if language not in {"en", "hi"}:
        raise ValueError("language is unsupported")
    if user_hash is not None and not re.fullmatch(r"[0-9a-f]{64}", user_hash if isinstance(user_hash, str) else ""):
        raise ValueError("user identity must be a SHA-256 digest")
    if not callable(spark_provider_factory):
        raise ValueError("Spark provider factory is required")
    if type(use_contributor) is not bool:
        raise ValueError("Spark provider mode is invalid")

    case_id = uuid.uuid4().hex
    started = time.perf_counter()
    steps: list[TraceStep] = []
    policy_value = (
        data_policy_value
        if isinstance(data_policy_value, str) and data_policy_value in {"private", "public_test"}
        else None
    )
    image_hash: str | None = None
    signals = SignalSet(
        s1=unavailable("glimmer_unavailable_b11_direct_to_spark"),
        s2=unavailable("production_kb_match_unavailable"),
        s3=extract_quality(),
    )
    decision = DecisionResult("refer", None, "signal_evidence_unavailable")
    spark_attempted = False
    provenance = "not_dispatched"

    def finish(reason: str, *, action: str = "refer", reply: str | None = None) -> SparkOnlyResult:
        steps.append(TraceStep("workflow_outcome", action, 0.0, model="spark_only_pipeline"))
        elapsed_ms = max(0.0, (time.perf_counter() - started) * 1000)
        measured_ms = sum(item.latency_ms for item in steps)
        if elapsed_ms > measured_ms:
            steps.append(TraceStep("workflow_overhead", "completed", elapsed_ms - measured_ms))
        spark_steps = [step for step in steps if step.step_name == "spark_meta"]
        tokens_in = None if not spark_steps or any(step.tokens_in is None for step in spark_steps) else sum(
            step.tokens_in for step in spark_steps if step.tokens_in is not None
        )
        tokens_out = None if not spark_steps or any(step.tokens_out is None for step in spark_steps) else sum(
            step.tokens_out for step in spark_steps if step.tokens_out is not None
        )
        costs = [step.est_cost for step in spark_steps]
        total_cost = None if not costs or any(cost is None for cost in costs) else sum(
            (cost for cost in costs if cost is not None), Decimal(0)
        )
        result = SparkOnlyResult(
            action=action, reason=reason, case_id=case_id, reply=reply,
            provenance=provenance,
            spark_escalations=int(spark_attempted), latency_ms=elapsed_ms,
            tokens_in=tokens_in, tokens_out=tokens_out, estimated_cost_usd=total_cost,
        )
        trace_store.record_case(
            TraceCase(
                case_id, action, language, "photo", policy_value,
                user_hash=user_hash, image_hash=image_hash, severity_pct=None,
            ),
            steps,
        )
        trace_store.record_signals(
            case_id, s1=_signal_value(signals.s1), s2=_signal_value(signals.s2),
            s3=_signal_value(signals.s3), s4=_signal_value(signals.s4),
            score=decision.score, decision=action if action != "blocked" else "refer",
            escalated=spark_attempted,
        )
        return result

    intake_started = time.perf_counter()
    try:
        coerce_image(describe_image_bytes(photo_bytes))
        policy = parse_data_policy(data_policy_value)
        if data_class not in {DataClass.PUBLIC_TEST, DataClass.PRIVATE}:
            raise DataPolicyError("image classification is invalid")
        if not isinstance(evidence, ProcessingEvidence):
            raise DataPolicyError("external processing evidence is unavailable")
        expected_marker = "public-test" if data_class is DataClass.PUBLIC_TEST else "private"
        if image_provenance != expected_marker:
            raise DataPolicyError("image provenance marker is missing or mismatched")
        if (
            data_class is DataClass.PUBLIC_TEST and policy is not DataPolicy.PUBLIC_TEST
            or data_class is DataClass.PRIVATE and policy is not DataPolicy.PRIVATE
        ):
            raise DataPolicyError("data policy does not match the image classification")
        if data_class is DataClass.PRIVATE:
            if provider_config.get("allow_private_upload") is not True:
                raise DataPolicyError("private image upload is not enabled in provider config")
            if evidence.provider_mode is not ProviderMode.STANDARD:
                raise DataPolicyError("private images require the standard Spark model")
        require_external_processing_allowed(policy, data_class, evidence)
    except (TypeError, ValueError, OSError):
        steps.append(make_step("intake_gate", "blocked", intake_started))
        return finish("intake_or_data_policy_denied", action="blocked")
    steps.append(make_step("intake_gate", "allowed", intake_started))

    prep_started = time.perf_counter()
    try:
        image = preprocess_image_bytes(photo_bytes)
    except (TypeError, ValueError, OSError):
        steps.append(make_step("preprocessing", "failed", prep_started))
        return finish("preprocessing_failed", action="blocked")
    image_hash = image.image_hash
    steps.append(make_step("preprocessing", "completed", prep_started))

    cache_started = time.perf_counter()
    try:
        cache_digest = cache_key(image.image_hash, language, voice_hint)
        cached = trace_store.get_cache(cache_digest)
    except (TraceError, ValueError):
        steps.append(make_step("cache_lookup", "invalid", cache_started))
        return finish("cache_lookup_invalid", action="blocked")
    # The shared cache currently stores synthetic/mock responses only. It is
    # never reused as a live result and this branch never falls back to replay.
    steps.append(make_step("cache_lookup", "miss" if cached is None else "non_live_entry_ignored", cache_started))
    if language == "hi":
        steps.append(TraceStep("language_gate", "unreviewed", 0.0, model="reply_templates"))
        return finish("hindi_reply_review_unavailable")

    try:
        weights, thresholds = load_router_config(_THRESHOLDS)
        safety = load_safety_card(_SAFETY)
    except (OSError, TypeError, ValueError, KeyError):
        steps.append(TraceStep("local_config", "unavailable", 0.0, model="local_config"))
        return finish("local_workflow_configuration_invalid", action="blocked")

    steps.append(TraceStep("glimmer", "unavailable_direct_to_spark", 0.0, model="tier1_glimmer"))
    try:
        provider = spark_provider_factory(
            config=provider_config, image_bytes=image.image_bytes,
            image_provenance=image_provenance, data_policy=policy,
            data_class=data_class, evidence=evidence,
            use_contributor=use_contributor, trace_callback=steps.append,
        )
        if type(provider) is not SparkClient:
            raise TypeError("spark_only requires the guarded SparkClient implementation")
    except Exception:
        steps.append(TraceStep("spark_meta", "guard_or_config_refused", 0.0,
                               model="muse-spark-1.3", error_code="provider_setup_refused"))
        return finish("provider_setup_refused")

    spark_attempted = True
    provenance = provider.execution_provenance
    diagnosis_started = time.perf_counter()
    diagnosis = run_diagnosis_validation(
        provider, supported_crops=supported_crops, disease_ids=disease_ids,
        confidence_bands=tuple(thresholds.get("confidence_bands", {})),
    )
    steps.append(make_step(
        "spark_validation", diagnosis.status.value,
        diagnosis_started,
    ))
    if diagnosis.status is DiagnosisStatus.VALID and diagnosis.output is not None:
        output = diagnosis.output
        if output.plant_visible and output.crop != "unknown" and output.issue != "unknown":
            signals = SignalSet(
                s1=unavailable("glimmer_unavailable_b11_direct_to_spark"),
                s2=unavailable("production_kb_match_unavailable"),
                s3=extract_quality(),
                s4=extract_confidence(output.stated_confidence),
            )
        else:
            diagnosis = diagnosis.__class__(DiagnosisStatus.UNKNOWN, None, "unsupported_plant_or_crop")

    decision = route_signals(
        signals, weights=weights, thresholds=thresholds,
        escalated=True, followups_used=0,
    )
    steps.append(TraceStep("decider", decision.action, 0.0, model="b3_decider"))

    # Call only the explicitly synthetic SAM provider for observable stage
    # ordering. The mask-derived result is discarded on this live Spark path.
    sam_provider = DeterministicMockSamProvider(("1",), ("1",), fail=True)
    sam_started = time.perf_counter()
    sam_result, sam_reason = run_mock_sam(sam_provider, image)
    del sam_result
    steps.extend((
        make_step("sam_mock", "failed" if sam_reason else "synthetic_only", sam_started),
        TraceStep("severity_overlay", "unavailable_live_sam_disabled", 0.0,
                  model="synthetic_mock", error_code="live_sam_no_go"),
    ))

    steps.append(TraceStep("kb_lookup", "no_production_disease_cards", 0.0, model="production_kb"))
    reason = (
        "spark_output_unknown" if diagnosis.status is DiagnosisStatus.UNKNOWN
        else "spark_unavailable" if diagnosis.status is DiagnosisStatus.UNAVAILABLE
        else "decider_fail_closed_missing_signals"
    )
    try:
        body = compose_reply(
            "refer", card={}, safety_card=safety, language="en", confidence="cannot tell",
        )
        safety_line = str(safety["safety_line"])
        spark_variant = "contributor Spark" if use_contributor else "standard Spark"
        reply = (
            "This is preliminary guidance. Confidence: cannot tell.\n"
            + body
            + "\nSafety: " + safety_line
            + "\nPhoto handling: the preprocessed JPEG is attached only to the guarded "
              f"{spark_variant} request."
            + "\nSAM overlay and severity are unavailable because live SAM is disabled."
        )
    except (TypeError, ValueError):
        reply = None
        reason = "reply_composition_unavailable"
    steps.append(TraceStep("reply_compose", "completed" if reply else "unavailable",
                           0.0, model="fixed_template"))
    return finish(reason, reply=reply)


def _signal_value(signal: Any) -> float | None:
    return signal.value if hasattr(signal, "value") else None
