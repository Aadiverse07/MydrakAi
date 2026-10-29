"""Offline T12 Glimmer sampling and bounded Spark escalation contract.

Providers are injected through the existing B8 validation interface. This
module supplies no provider implementation, request format, network client,
threshold, or final Decider action.
"""

from dataclasses import dataclass
from enum import StrEnum

from mydrak.decider.extraction import SignalMeasurement, extract_agreement
from mydrak.vision.diagnosis import (
    DiagnosisProvider,
    DiagnosisResult,
    DiagnosisStatus,
    run_diagnosis_validation,
)

GLIMMER_SAMPLES_PER_CASE = 2
MAX_SPARK_ESCALATIONS_PER_CASE = 1


class SamplingStatus(StrEnum):
    SAMPLES_AGREE = "samples_agree"
    SPARK_ESCALATED = "spark_escalated"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SamplingState:
    """Caller-carried per-case count; persistence/integration is not supplied."""

    spark_escalations: int = 0


@dataclass(frozen=True)
class SamplingResult:
    """Validated sample evidence; never a final answer or policy decision."""

    status: SamplingStatus
    glimmer_samples: tuple[DiagnosisResult, ...]
    agreement: SignalMeasurement
    spark_result: DiagnosisResult | None
    state: SamplingState
    spark_escalations: int
    reason: str


def _validate_once(
    provider: DiagnosisProvider,
    *,
    supported_crops: tuple[str, ...],
    disease_ids: tuple[str, ...],
) -> DiagnosisResult:
    return run_diagnosis_validation(
        provider,
        supported_crops=supported_crops,
        disease_ids=disease_ids,
    )


def run_t12_sampling(
    glimmer_provider: DiagnosisProvider,
    spark_provider: DiagnosisProvider,
    *,
    supported_crops: tuple[str, ...],
    disease_ids: tuple[str, ...],
    state: SamplingState = SamplingState(),
) -> SamplingResult:
    """Validate two Glimmer samples and escalate once on valid disagreement.

    Each B8-invalid string can use its existing single repair attempt. Provider
    failures are not retried. A valid ``unknown`` label is not counted as
    agreement or disagreement because it is not a supported diagnosis ID.
    Spark's validated result is returned for inspection, but this task cannot
    re-score B3 because S2/S3 production measurements and approved thresholds
    are unavailable. No final answer action is made here.
    """
    if not isinstance(state, SamplingState) or type(state.spark_escalations) is not int:
        return SamplingResult(
            SamplingStatus.UNAVAILABLE,
            (),
            SignalMeasurement(None, "sampling_state_invalid"),
            None,
            SamplingState(),
            0,
            "sampling_state_invalid",
        )
    if not 0 <= state.spark_escalations <= MAX_SPARK_ESCALATIONS_PER_CASE:
        return SamplingResult(
            SamplingStatus.UNAVAILABLE,
            (),
            SignalMeasurement(None, "sampling_state_invalid"),
            None,
            state,
            state.spark_escalations,
            "sampling_state_invalid",
        )

    first = _validate_once(
        glimmer_provider,
        supported_crops=supported_crops,
        disease_ids=disease_ids,
    )
    second = _validate_once(
        glimmer_provider,
        supported_crops=supported_crops,
        disease_ids=disease_ids,
    )
    samples = (first, second)
    if any(item.status is not DiagnosisStatus.VALID or item.output is None for item in samples):
        return SamplingResult(
            SamplingStatus.UNAVAILABLE,
            samples,
            SignalMeasurement(None, "glimmer_sample_unavailable"),
            None,
            state,
            state.spark_escalations,
            "glimmer_sample_unavailable",
        )

    outputs = (first.output, second.output)
    if any(
        not output.plant_visible
        or output.crop == "unknown"
        or output.issue == "unknown"
        for output in outputs
    ):
        return SamplingResult(
            SamplingStatus.UNAVAILABLE,
            samples,
            SignalMeasurement(None, "sample_label_unknown"),
            None,
            state,
            state.spark_escalations,
            "sample_label_unknown",
        )

    agreement = extract_agreement(
        {"crop": outputs[0].crop, "disease": outputs[0].issue},
        {"crop": outputs[1].crop, "disease": outputs[1].issue},
    )
    if agreement.value == 1.0:
        return SamplingResult(
            SamplingStatus.SAMPLES_AGREE,
            samples,
            agreement,
            None,
            state,
            state.spark_escalations,
            "glimmer_samples_agree_decider_pending",
        )

    if state.spark_escalations == MAX_SPARK_ESCALATIONS_PER_CASE:
        return SamplingResult(
            SamplingStatus.UNAVAILABLE,
            samples,
            agreement,
            None,
            state,
            state.spark_escalations,
            "spark_escalation_already_used",
        )

    next_state = SamplingState(state.spark_escalations + 1)
    spark_result = _validate_once(
        spark_provider,
        supported_crops=supported_crops,
        disease_ids=disease_ids,
    )
    if spark_result.status is not DiagnosisStatus.VALID or spark_result.output is None:
        return SamplingResult(
            SamplingStatus.UNAVAILABLE,
            samples,
            agreement,
            spark_result,
            next_state,
            next_state.spark_escalations,
            "spark_result_unavailable",
        )
    return SamplingResult(
        SamplingStatus.SPARK_ESCALATED,
        samples,
        agreement,
        spark_result,
        next_state,
        next_state.spark_escalations,
        "rescore_blocked_s2_s3_and_thresholds_unavailable",
    )
