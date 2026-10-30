"""Small trace, cache, and reply helpers for the synthetic workflow."""

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
import time
from datetime import datetime, timedelta, timezone

from mydrak.decider.extraction import SignalMeasurement, SignalSet
from mydrak.decider.signals import validate_confidence_band_mapping
from mydrak.reply.composer import CONFIDENCE_WORDS, compose_reply
from mydrak.sam.output import SamLimits, SamSegmentation, parse_sam_output
from mydrak.sam.overlay import T08Result, decode_synthetic_grid, render_synthetic_fixture
from mydrak.trace.store import (
    TraceCase, TraceStep, TraceStore, WORKFLOW_CACHE_PROVENANCE,
    WORKFLOW_CACHE_SCHEMA,
)
from mydrak.util.config import load_yaml
from mydrak.workflow.mock_providers import (
    DeterministicMockDiagnosisProvider, DeterministicMockSamProvider,
    MockSamResponse, SYNTHETIC_MOCK_LABEL,
)
from mydrak.vision.diagnosis import (
    DiagnosisOutput, DiagnosisProvider, DiagnosisResult, DiagnosisStatus,
    run_diagnosis_validation,
)
from mydrak.vision.preprocessing import PreprocessedImage


@dataclass(frozen=True)
class TestOnlySignalOverride:
    """Explicit synthetic values; never loaded from production configuration."""

    __test__ = False

    s2: float | None = None
    s3: float | None = None
    s4: float | None = None
    confidence_word: str = "not sure"
    provenance: str = field(default=SYNTHETIC_MOCK_LABEL, init=False)


@dataclass(frozen=True)
class OfflineWorkflowResult:
    action: str
    reply: str | None
    reason: str
    case_id: str
    severity_pct: float | None
    severity_band: str | None
    overlay_bytes: bytes | None = field(repr=False)
    overlay_mime_type: str | None
    provenance: str = SYNTHETIC_MOCK_LABEL
    cache_hit: bool = False
    spark_escalations: int = 0


def validate_signal_override(override: TestOnlySignalOverride | None) -> None:
    import math

    if override is None:
        return
    if type(override) is not TestOnlySignalOverride or override.provenance != SYNTHETIC_MOCK_LABEL:
        raise ValueError("signal override is test-only")
    for name in ("s2", "s3", "s4"):
        value = getattr(override, name)
        try:
            valid = value is None or (
                type(value) in {int, float} and math.isfinite(value) and 0 <= value <= 1
            )
        except (OverflowError, TypeError):
            valid = False
        if not valid:
            raise ValueError("test-only signal value is invalid")
    if not isinstance(override.confidence_word, str) or override.confidence_word not in CONFIDENCE_WORDS:
        raise ValueError("test-only confidence wording is invalid")


def apply_signal_override(signals: SignalSet, override: TestOnlySignalOverride | None,
                          *, keep_s2: bool = False) -> SignalSet:
    if override is None:
        return signals
    s2 = signals.s2 if keep_s2 or override.s2 is None else SignalMeasurement(override.s2, "synthetic_test_override")
    s3 = signals.s3 if override.s3 is None else SignalMeasurement(override.s3, "synthetic_test_override")
    s4 = signals.s4 if override.s4 is None else SignalMeasurement(override.s4, "synthetic_test_override")
    return SignalSet(signals.s1, s2, s3, s4)


def render_workflow_reply(action: str, safety: Mapping[str, object],
                          card: Mapping[str, object] | None, confidence: str,
                          severity: float | None, *, question_id: str | None = None,
                          overlay_reason: str = "") -> str:
    body = compose_reply(
        action, card=card or {}, safety_card=safety, language="en",
        confidence=confidence, severity_pct=severity, question_id=question_id,
    )
    text = f"{SYNTHETIC_MOCK_LABEL} — preliminary guidance.\nConfidence: {confidence}.\n{body}"
    safety_line = str(safety["safety_line"])
    if safety_line not in text:
        text += f"\nSafety: {safety_line}"
    if overlay_reason:
        text += "\nSAM overlay and severity are unavailable for this synthetic result."
    return text


def record_workflow_trace(store: TraceStore, result: OfflineWorkflowResult,
                          language: str, policy: str | None, user_hash: str | None,
                          image_hash: str | None, steps: list[TraceStep],
                          signals: SignalSet, score: float | None,
                          escalated: bool, kb_card_id: str | None) -> None:
    store.record_case(TraceCase(
        result.case_id, result.action, language, "photo", policy,
        user_hash=user_hash, image_hash=image_hash,
        kb_card_id=kb_card_id, severity_pct=result.severity_pct,
    ), steps)
    store.record_signals(
        result.case_id,
        s1=_value(signals.s1), s2=_value(signals.s2), s3=_value(signals.s3),
        s4=_value(signals.s4), score=score,
        decision=result.action if result.action != "blocked" else "refer",
        escalated=escalated,
    )


def cache_key(image_hash: str, language: str, voice_hint: str | None = None) -> str:
    """Hash the preprocessed image digest, language, and optional voice hint."""
    if not isinstance(image_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", image_hash):
        raise ValueError("preprocessed image hash is invalid")
    if language not in {"en", "hi"}:
        raise ValueError("cache language is unsupported")
    if voice_hint is not None and (
        not isinstance(voice_hint, str) or len(voice_hint) > 1024
        or any(ord(char) < 32 and char not in "\t\n" for char in voice_hint)
    ):
        raise ValueError("voice hint is invalid")
    material = json.dumps([image_hash, language, voice_hint], ensure_ascii=False, separators=(",", ":"))
    return sha256(material.encode("utf-8")).hexdigest()


def workflow_cache_payload(result: OfflineWorkflowResult) -> dict[str, object]:
    """Keep only bounded synthetic reply metadata; never cache source/overlay bytes."""
    return {
        "schema": WORKFLOW_CACHE_SCHEMA,
        "provenance": WORKFLOW_CACHE_PROVENANCE,
        "action": result.action,
        "reason": result.reason,
        "reply": result.reply,
        "severity_pct": result.severity_pct,
        "severity_band": result.severity_band,
    }


def run_diagnosis_with_retries(
    provider: DiagnosisProvider,
    *,
    supported_crops,
    disease_ids,
    confidence_bands: Collection[str] | None = None,
    sleeper=None,
) -> tuple[DiagnosisResult, int]:
    """Apply B11's two-retry maximum; B8's single repair remains separate."""
    retries = 0
    while True:
        result = run_diagnosis_validation(
            provider, supported_crops=supported_crops, disease_ids=disease_ids,
            confidence_bands=confidence_bands,
        )
        if result.status is not DiagnosisStatus.UNAVAILABLE or result.reason not in {
            "provider_failure", "repair_provider_failure", "provider_unavailable",
        } or retries >= 2:
            return result, retries
        # B11 does not specify timing; this is a small project-local exponential delay.
        (sleeper or time.sleep)(0.01 * (2 ** retries))
        retries += 1


def run_mock_sam(provider: DeterministicMockSamProvider,
                 image: PreprocessedImage) -> tuple[T08Result, str]:
    """Parse only the local synthetic mask grammar; failures carry no result."""
    try:
        response = provider.generate(image)
        if not isinstance(response, MockSamResponse) or response.provenance != SYNTHETIC_MOCK_LABEL:
            raise ValueError
        segmentation: SamSegmentation = parse_sam_output(response.payload)
        masks = {item.id: item.mask for item in segmentation.objects}
        for role in ("leaf", "lesion"):
            decode_synthetic_grid(masks[role], SamLimits())
        result = render_synthetic_fixture(
            segmentation, image, leaf_object_id="leaf", lesion_object_id="lesion",
        )
        reason = "" if result.severity_pct is not None else result.reason_code
        return result, reason
    except (ValueError, TypeError, RuntimeError, KeyError, OSError):
        result = T08Result(None, None, None, None, "sam_provider_failed", "synthetic-fixture", None)
        return result, "sam_provider_failed"


def validate_pipeline_dependencies(language, store, glimmer, spark, sam, override,
                                   user_hash, voice_hint) -> None:
    if type(store) is not TraceStore:
        raise ValueError("offline trace store is required")
    if type(glimmer) is not DeterministicMockDiagnosisProvider or type(spark) is not DeterministicMockDiagnosisProvider:
        raise ValueError("only deterministic mock diagnosis providers are accepted")
    if type(sam) is not DeterministicMockSamProvider or sam.provenance != SYNTHETIC_MOCK_LABEL:
        raise ValueError("only the deterministic mock SAM provider is accepted")
    if not isinstance(language, str) or language not in {"en", "hi"}:
        raise ValueError("language is unsupported")
    if user_hash is not None and not re.fullmatch(r"[0-9a-f]{64}", user_hash if isinstance(user_hash, str) else ""):
        raise ValueError("user identity must be a SHA-256 digest")
    if voice_hint is not None and (
        not isinstance(voice_hint, str) or len(voice_hint) > 1024
        or any(ord(char) < 32 and char not in "\t\n" for char in voice_hint)
    ):
        raise ValueError("voice hint is invalid")
    validate_signal_override(override)


def reply_for_action(action, safety, card, confidence, severity, *, question_id=None,
                     overlay_reason="") -> str:
    return render_workflow_reply(
        action, safety, card, confidence, severity,
        question_id=question_id, overlay_reason=overlay_reason,
    )


def is_valid_diagnosis(result: DiagnosisResult) -> bool:
    return result.status is DiagnosisStatus.VALID and isinstance(result.output, DiagnosisOutput)


def diagnosis_labels(output: DiagnosisOutput) -> dict[str, str]:
    return {"crop": output.crop, "disease": output.issue}


def unsupported_plant_reply(safety: Mapping[str, object]) -> str:
    return (
        f"{SYNTHETIC_MOCK_LABEL} — preliminary guidance.\nConfidence: cannot tell.\n"
        "This photo could not be confirmed as a supported plant. No diagnosis was made.\n"
        f"Safety: {safety['safety_line']}"
    )


def load_router_config(path) -> tuple[Mapping[str, object], Mapping[str, object]]:
    values = load_yaml(path)
    validate_confidence_band_mapping(values.get("confidence_bands"))
    return values.get("weights", {}), values


def make_step(name: str, outcome: str, started: float) -> TraceStep:
    ended = time.perf_counter()
    elapsed = max(0.0, ended - started)
    timestamp = (datetime.now(timezone.utc) - timedelta(seconds=elapsed)).isoformat(timespec="microseconds").replace("+00:00", "Z")
    return TraceStep(name, outcome, elapsed * 1000, started_at=timestamp)


def _value(measurement: SignalMeasurement) -> float | None:
    return measurement.value if isinstance(measurement, SignalMeasurement) else None
