"""Offline coordination for guarded intake, synthetic SAM, and safe replies.

The intake policy gate runs before the synthetic SAM parser. Intake's MOCK
finding is deliberately discarded: neither it nor the offline SAM chain is a
diagnosis. All accepted parser outcomes therefore produce a referral or
manual-review result with no severity. No sender, transport, or network path
is exposed here.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import time
import re
from typing import Any, Literal
import uuid

from mydrak.decider.extraction import (
    DecisionResult,
    SignalSet,
    extract_agreement,
    extract_kb_match,
    extract_quality,
    route_signals,
    unavailable,
)
from mydrak.intake.adapter import IntakeError, process_intake
from mydrak.privacy.data_policy import DataClass, ProcessingEvidence
from mydrak.reply.composer import ReplyError, compose_reply
from mydrak.sam.chain import ChainOutcome, run_offline_chain
from mydrak.trace.store import TraceCase, TraceStep, TraceStore
from mydrak.vision.diagnosis import DiagnosisOutput, DiagnosisResult, DiagnosisStatus
from mydrak.workflow.followup import (
    FollowUpError,
    FollowUpState,
    FollowUpStep,
    accept_followup_answer,
    begin_followup,
)

SYNTHETIC_FIXTURE_PROVENANCE = "synthetic-offline-fixture"


class OfflineCoordinatorError(ValueError):
    """Raised when offline workflow inputs cannot be safely coordinated."""


@dataclass(frozen=True)
class SyntheticSamReplyFixture:
    """Explicitly labeled synthetic response-envelope text for local parsing."""

    raw_reply: str = field(repr=False)
    provenance: str = ""


@dataclass(frozen=True)
class OfflineCoordinationResult:
    """Safe user-facing outcome without mock findings or raw SAM text."""

    status: Literal["blocked", "referred", "manual_review"]
    reply: str | None
    reason: str
    case_id: str
    sam_reason: str | None = None
    severity_pct: None = None


def coordinate_offline_case(
    image_descriptor: Mapping[str, Any],
    sam_fixture: SyntheticSamReplyFixture,
    *,
    data_policy_value: str | None,
    safety_card: Mapping[str, Any],
    data_class: DataClass = DataClass.PRIVATE,
    evidence: ProcessingEvidence | None = None,
    language: str = "en",
    user_hash: str | None = None,
    image_hash: str | None = None,
    trace_store: TraceStore,
) -> OfflineCoordinationResult:
    """Gate a descriptor, parse a synthetic SAM reply, and choose a safe reply.

    ``process_intake`` performs descriptor and policy validation. Its
    deterministic mock finding is never returned or used. Private or otherwise
    denied inputs stop before the SAM parser. Parser outcomes cannot establish
    a disease, so they route to the existing expert-referral text.
    """
    started = time.perf_counter()
    case_id = uuid.uuid4().hex
    if not isinstance(trace_store, TraceStore):
        raise OfflineCoordinatorError("trace store is required")
    for digest in (user_hash, image_hash):
        if digest is not None and (
            not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            raise OfflineCoordinatorError("trace identity must be a SHA-256 digest")
    if language != "en":
        raise OfflineCoordinatorError("requested reply language is unavailable")
    if not isinstance(sam_fixture, SyntheticSamReplyFixture):
        raise OfflineCoordinatorError("an explicitly labeled synthetic SAM fixture is required")
    if sam_fixture.provenance != SYNTHETIC_FIXTURE_PROVENANCE:
        raise OfflineCoordinatorError("SAM fixture provenance is invalid")
    if not isinstance(sam_fixture.raw_reply, str):
        raise OfflineCoordinatorError("synthetic SAM fixture is invalid")
    if not isinstance(safety_card, Mapping):
        raise OfflineCoordinatorError("safety card is invalid")

    try:
        intake = process_intake(
            image_descriptor,
            data_policy_value=data_policy_value,
            safety_card=safety_card,
            data_class=data_class,
            evidence=evidence,
            sender=None,
        )
    except IntakeError:
        raise OfflineCoordinatorError("offline intake was rejected") from None

    if intake.status == "blocked":
        result = OfflineCoordinationResult(
            status="blocked",
            reply=None,
            reason="intake_policy_denied",
            case_id=case_id,
        )
        _record_result(trace_store, result, language, data_policy_value, started,
                       _intake_steps(intake.trace, blocked=True), user_hash, image_hash)
        return result
    if intake.status != "mock_complete":
        raise OfflineCoordinatorError("offline intake returned an unsupported status")

    try:
        dimensions = intake.trace["image"]
        width = dimensions["width"]
        height = dimensions["height"]
    except (KeyError, TypeError):
        raise OfflineCoordinatorError("validated intake dimensions are unavailable") from None
    if type(width) is not int or type(height) is not int:
        raise OfflineCoordinatorError("validated intake dimensions are invalid")

    sam_started = time.perf_counter()
    outcome: ChainOutcome = run_offline_chain(
        sam_fixture.raw_reply,
        expected_width=width,
        expected_height=height,
    )
    sam_elapsed = (time.perf_counter() - sam_started) * 1000
    reply_started = time.perf_counter()
    try:
        reply = compose_reply("refer", card={}, safety_card=safety_card)
    except ReplyError:
        raise OfflineCoordinatorError("safe referral reply is unavailable") from None
    reply_elapsed = (time.perf_counter() - reply_started) * 1000
    steps = _intake_steps(intake.trace, blocked=False)
    steps.extend([
        TraceStep("synthetic_sam_parse", "completed", sam_elapsed),
        TraceStep("reply_compose", "completed", reply_elapsed),
    ])

    if outcome.decision == "no-findings":
        result = OfflineCoordinationResult(
            status="referred",
            reply=reply,
            reason="no_sam_detections_not_a_health_finding",
            case_id=case_id,
            sam_reason=outcome.reason,
        )
        _record_result(trace_store, result, language, data_policy_value, started, steps,
                       user_hash, image_hash)
        return result
    result = OfflineCoordinationResult(
        status="manual_review",
        reply=reply,
        reason="sam_outcome_requires_manual_review",
        case_id=case_id,
        sam_reason=outcome.reason,
    )
    _record_result(trace_store, result, language, data_policy_value, started, steps,
                   user_hash, image_hash)
    return result


def _intake_steps(trace: Mapping[str, Any], *, blocked: bool) -> list[TraceStep]:
    stages = trace.get("stages", [])
    result: list[TraceStep] = []
    if isinstance(stages, list):
        for stage in stages:
            if not isinstance(stage, Mapping):
                continue
            name = stage.get("stage")
            duration = stage.get("duration_ms")
            if isinstance(name, str) and isinstance(duration, (int, float)):
                result.append(TraceStep(
                    f"intake_{name[:48]}",
                    "blocked" if blocked and name == "policy_decision" else "completed",
                    float(duration),
                ))
    return result or [TraceStep("intake", "blocked" if blocked else "completed", 0.0)]


def _record_result(
    store: TraceStore,
    result: OfflineCoordinationResult,
    language: str,
    policy_value: str | None,
    started: float,
    steps: list[TraceStep],
    user_hash: str | None,
    image_hash: str | None,
) -> None:
    policy = policy_value if policy_value in {"private", "public_test"} else None
    elapsed = max(0.0, (time.perf_counter() - started) * 1000)
    steps.append(TraceStep("workflow_outcome", result.status, 0.0))
    # Coordinator work after measured substeps is included as a bounded remainder.
    measured = sum(step.latency_ms for step in steps)
    if elapsed > measured:
        steps.append(TraceStep("workflow_overhead", "completed", elapsed - measured))
    case = TraceCase(
        case_id=result.case_id,
        final_action=result.status,
        lang=language,
        input_type="photo",
        data_policy=policy,
        user_hash=user_hash,
        image_hash=image_hash,
    )
    store.record_case(case, steps)


def coordinate_followup_answer(
    state: FollowUpState,
    answer: str,
    *,
    card: Mapping[str, Any],
    safety_card: Mapping[str, Any],
    next_question_id: str | None = None,
    alternatives: Sequence[str] = (),
) -> FollowUpStep:
    """Advance one transient answer using a caller-selected KB question.

    This does not inspect or retain the answer. The caller must select the
    next question from approved evidence; after two questions the shared
    follow-up state machine returns the referral regardless of that selection.
    """
    try:
        ready = accept_followup_answer(state, answer)
        return begin_followup(
            ready,
            card=card,
            safety_card=safety_card,
            question_id=next_question_id,
            alternatives=alternatives,
        )
    except FollowUpError:
        raise OfflineCoordinatorError("follow-up transition was rejected") from None


def coordinate_mock_tier1_results(
    first: DiagnosisResult,
    second: DiagnosisResult,
    *,
    cards: Sequence[Mapping[str, object]],
    weights: Mapping[str, float],
    thresholds: Mapping[str, object],
    escalated: bool = False,
    followups_used: int = 0,
) -> DecisionResult:
    """Route two validated synthetic Tier-1 results through the Decider.

    The first result supplies the observed-symptom phrases for this offline
    adapter. S4 aggregation is unavailable, and S3 remains unavailable until
    T04 provides measured image quality; therefore route_signals fails closed.
    No provider is created or invoked here.
    """
    results = (first, second)
    if any(
        not isinstance(result, DiagnosisResult)
        or result.status is not DiagnosisStatus.VALID
        or not isinstance(result.output, DiagnosisOutput)
        for result in results
    ):
        raise OfflineCoordinatorError("two validated Tier-1 results are required")
    left, right = first.output, second.output
    assert isinstance(left, DiagnosisOutput) and isinstance(right, DiagnosisOutput)
    s1 = extract_agreement(
        {"crop": left.crop, "disease": left.issue},
        {"crop": right.crop, "disease": right.issue},
    )
    if (left.crop, left.issue) != (right.crop, right.issue):
        s2 = unavailable("tier1_labels_disagree")
    else:
        s2 = extract_kb_match(left.issue, cards, left.symptoms_observed)
    return route_signals(
        SignalSet(
            s1=s1,
            s2=s2,
            s3=extract_quality(),
            s4=unavailable("tier1_confidence_aggregation_unresolved"),
        ),
        weights=weights,
        thresholds=thresholds,
        escalated=escalated,
        followups_used=followups_used,
    )
