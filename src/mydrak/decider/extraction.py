"""B3 signal evidence extraction and fail-closed Decider routing.

Only directly specified, structurally supported measurements are produced.
Image quality (S3), symptom overlap for a matching KB card (S2), and textual
confidence-band mappings remain unavailable until their upstream contracts are
defined. Nothing in this module infers agronomic findings.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
from numbers import Real
from typing import Literal

from mydrak.decider.policy import Action, decide
from mydrak.decider.signals import combine
from mydrak.trace.store import TraceError, TraceStore


@dataclass(frozen=True)
class SignalMeasurement:
    """A normalized signal or an explicit reason it is unavailable."""

    value: float | None
    reason: str = ""

    @property
    def available(self) -> bool:
        return self.value is not None


def unavailable(reason: str) -> SignalMeasurement:
    return SignalMeasurement(None, reason)


def extract_agreement(
    first: Mapping[str, object] | None,
    second: Mapping[str, object] | None,
) -> SignalMeasurement:
    """Extract B3 S1 from two structured ``crop``/``disease`` samples."""
    if not isinstance(first, Mapping) or not isinstance(second, Mapping):
        return unavailable("two_model_samples_unavailable")
    values = []
    for sample in (first, second):
        crop, disease = sample.get("crop"), sample.get("disease")
        if not isinstance(crop, str) or not crop.strip():
            return unavailable("sample_crop_missing_or_invalid")
        if not isinstance(disease, str) or not disease.strip():
            return unavailable("sample_disease_missing_or_invalid")
        values.append((crop.strip().casefold(), disease.strip().casefold()))
    if values[0] == values[1]:
        return SignalMeasurement(1.0)
    if values[0][0] == values[1][0]:
        return SignalMeasurement(0.5)
    return SignalMeasurement(0.0)


def extract_kb_match(
    predicted_label: object,
    cards: Sequence[Mapping[str, object]] | None,
) -> SignalMeasurement:
    """Extract only B3's unambiguous no-card S2 case.

    For a matching card, B3 requires symptom keyword overlap but does not
    define tokenization, normalization, or the overlap denominator. That case
    remains unavailable rather than applying a guessed matcher.
    """
    if not isinstance(predicted_label, str) or not predicted_label.strip():
        return unavailable("predicted_label_unavailable")
    if cards is None or isinstance(cards, (str, bytes)) or not isinstance(cards, Sequence):
        return unavailable("kb_cards_unavailable")
    card_ids: list[str] = []
    for card in cards:
        if not isinstance(card, Mapping):
            return unavailable("kb_card_contract_invalid")
        card_id = card.get("id")
        if not isinstance(card_id, str) or not card_id.strip():
            return unavailable("kb_card_contract_invalid")
        card_ids.append(card_id.strip().casefold())
    if len(card_ids) != len(set(card_ids)):
        return unavailable("kb_card_ids_ambiguous")
    label = predicted_label.strip().casefold()
    if label not in card_ids:
        return SignalMeasurement(0.0)
    return unavailable("symptom_overlap_contract_unresolved")


def extract_quality() -> SignalMeasurement:
    """Return unavailable S3 until T04 defines decoded image metrics."""
    return unavailable("image_quality_unavailable_t04")


def extract_confidence(value: object) -> SignalMeasurement:
    """Extract numeric B3 S4; band-to-number mapping is unspecified."""
    if value is None:
        return unavailable("model_confidence_unavailable_t05")
    if isinstance(value, str):
        return unavailable("confidence_band_mapping_unresolved")
    if isinstance(value, bool) or not isinstance(value, Real):
        return unavailable("model_confidence_invalid")
    try:
        valid = math.isfinite(value) and 0.0 <= value <= 1.0
    except (OverflowError, TypeError):
        valid = False
    if not valid:
        return unavailable("model_confidence_out_of_range")
    return SignalMeasurement(float(value))


@dataclass(frozen=True)
class SignalSet:
    """B3 signals kept separate from combination and policy selection."""

    s1: SignalMeasurement = field(default_factory=lambda: unavailable("s1_unavailable"))
    s2: SignalMeasurement = field(default_factory=lambda: unavailable("s2_unavailable"))
    s3: SignalMeasurement = field(default_factory=extract_quality)
    s4: SignalMeasurement = field(default_factory=lambda: unavailable("s4_unavailable"))


@dataclass(frozen=True)
class DecisionResult:
    """Policy result with an explicit safe fallback when evidence is incomplete."""

    action: Action
    score: float | None
    reason: str
    unavailable_signals: tuple[str, ...] = ()


def route_signals(
    signals: SignalSet,
    *,
    weights: Mapping[str, float],
    thresholds: Mapping[str, object],
    escalated: bool,
    followups_used: int,
    trace_store: TraceStore | None = None,
    case_id: str | None = None,
) -> DecisionResult:
    """Combine signals and apply B3; optionally persist the B9 decision row.

    Trace context is opt-in to preserve existing pure callers. When requested,
    both an existing case ID and the local TraceStore are required. Missing or
    malformed signals are recorded as SQL NULL, never as fabricated scores.
    """
    if (trace_store is None) != (case_id is None):
        raise TraceError("trace store and case ID must be supplied together")
    if trace_store is not None and type(trace_store) is not TraceStore:
        raise TraceError("only the local SQLite trace store is supported")

    def finish(result: DecisionResult) -> DecisionResult:
        if trace_store is not None and case_id is not None:
            trace_store.record_signals(
                case_id,
                s1=_trace_value(getattr(signals, "s1", None)),
                s2=_trace_value(getattr(signals, "s2", None)),
                s3=_trace_value(getattr(signals, "s3", None)),
                s4=_trace_value(getattr(signals, "s4", None)),
                score=result.score,
                decision=result.action,
                escalated=escalated,
            )
        return result

    if not isinstance(signals, SignalSet):
        return finish(DecisionResult("refer", None, "signal_set_invalid", ("s1", "s2", "s3", "s4")))
    measurements = {name: getattr(signals, name) for name in ("s1", "s2", "s3", "s4")}
    missing = tuple(
        name for name, measurement in measurements.items()
        if not isinstance(measurement, SignalMeasurement) or measurement.value is None
    )
    if missing:
        return finish(DecisionResult("refer", None, "signal_evidence_unavailable", missing))
    try:
        score = combine(
            measurements["s1"].value,
            measurements["s2"].value,
            measurements["s3"].value,
            measurements["s4"].value,
            weights,
        )
        action = decide(
            score=score,
            s1=measurements["s1"].value,
            s3=measurements["s3"].value,
            accept=thresholds["accept"],
            agree_min=thresholds["agree_min"],
            quality_min=thresholds["quality_min"],
            escalated=escalated,
            followups_used=followups_used,
            max_followups=thresholds["max_followups"],
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        return finish(DecisionResult("refer", None, "signal_or_policy_input_invalid"))
    return finish(DecisionResult(action, score, "policy_action"))


def _trace_value(measurement: object) -> float | None:
    if not isinstance(measurement, SignalMeasurement):
        return None
    value = measurement.value
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    try:
        if not math.isfinite(value) or not 0 <= value <= 1:
            return None
    except (OverflowError, TypeError):
        return None
    return float(value)
