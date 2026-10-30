"""Small trace, cache, and reply helpers for the synthetic workflow."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
import time

from mydrak.decider.extraction import SignalMeasurement, SignalSet, unavailable
from mydrak.reply.composer import CONFIDENCE_WORDS, compose_reply
from mydrak.sam.overlay import T08Result
from mydrak.trace.store import TraceCase, TraceStep, TraceStore
from mydrak.util.config import load_yaml
from mydrak.workflow.mock_providers import SYNTHETIC_MOCK_LABEL


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


@dataclass(frozen=True)
class WorkflowSnapshot:
    action: str
    reply: str | None
    reason: str
    severity_pct: float | None
    severity_band: str | None
    overlay_bytes: bytes | None
    overlay_mime_type: str | None
    signals: tuple[float | None, float | None, float | None, float | None, float | None]
    escalated: bool
    kb_card_id: str | None
    spark_escalations: int


class MockWorkflowCache:
    """Process-local result cache for the synthetic workflow; never persistent."""

    def __init__(self) -> None:
        self._entries: dict[str, WorkflowSnapshot] = {}

    def get(self, key: str) -> WorkflowSnapshot | None:
        return self._entries.get(key)

    def put(self, key: str, value: WorkflowSnapshot) -> None:
        self._entries.setdefault(key, value)


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


def make_snapshot(result: OfflineWorkflowResult, signals: SignalSet,
                  escalated: bool, kb_id: str | None,
                  score: float | None) -> WorkflowSnapshot:
    return WorkflowSnapshot(
        result.action, result.reply, result.reason, result.severity_pct,
        result.severity_band, result.overlay_bytes, result.overlay_mime_type,
        (_value(signals.s1), _value(signals.s2), _value(signals.s3), _value(signals.s4), score),
        escalated, kb_id, result.spark_escalations,
    )


def signal_set_from_values(values: tuple[float | None, ...]) -> SignalSet:
    return SignalSet(*[
        SignalMeasurement(value, "cached_synthetic") if value is not None else unavailable("cached_unavailable")
        for value in values[:4]
    ])


def cached_overlay(snapshot: WorkflowSnapshot) -> T08Result | None:
    if snapshot.overlay_bytes is None:
        return None
    return T08Result(snapshot.severity_pct, snapshot.severity_band, snapshot.overlay_bytes,
                     snapshot.overlay_mime_type, "cached", "synthetic-fixture", "SYNTHETIC FIXTURE")


def cache_key(image_hash: str, language: str, policy: str | None,
              override: TestOnlySignalOverride | None, user_hash: str | None = None) -> str:
    fields = [image_hash, language, policy or "unknown", user_hash or "anonymous"]
    if override is not None:
        fields.extend(str(getattr(override, name)) for name in ("s2", "s3", "s4", "confidence_word"))
    return sha256("|".join(fields).encode("utf-8")).hexdigest()


def load_router_config(path) -> tuple[Mapping[str, object], Mapping[str, object]]:
    values = load_yaml(path)
    return values.get("weights", {}), values


def make_step(name: str, outcome: str, started: float) -> TraceStep:
    return TraceStep(name, outcome, max(0.0, (time.perf_counter() - started) * 1000))


def _value(measurement: SignalMeasurement) -> float | None:
    return measurement.value if isinstance(measurement, SignalMeasurement) else None
