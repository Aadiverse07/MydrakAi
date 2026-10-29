"""Offline integration chain: reply text to review/decision outcome.

Demonstrates the connected offline path ``synthetic reply text →
parse_response_envelope → adapt_envelope → parsed frames → decision``.
Severity is a declined stage here, not a computed one: wire masks are
opaque and never decoded, so no ``BinaryMask`` exists to feed the
existing ``mask_severity_pct`` implementation. Every outcome therefore
carries ``severity_pct=None``; severity itself stays covered by the
separate synthetic-grid tests. This module synthesizes no masks,
decodes nothing, and performs no diagnosis.

Decisions: ``"no-findings"`` means the parsed output contains zero
detections — absence of detections in this output, NOT a health claim.
``"manual-review"`` covers everything else: unusable envelopes,
missing or rejected texts, detections with opaque masks, and dimension
problems. Missing evidence never becomes a success. Provider behavior
remains UNVERIFIED throughout.
"""

from dataclasses import dataclass
from typing import Any

from mydrak.sam.envelope import SamEnvelopeError, parse_response_envelope
from mydrak.sam.frames import adapt_envelope
from mydrak.sam.output import SamLimits


@dataclass(frozen=True)
class ChainOutcome:
    """One chain result. ``severity_pct`` is always None offline.

    ``reason`` is ``"zero-match"``, ``"masks-opaque"``,
    ``"unusable-envelope"``, ``"no-output-texts"``, or
    ``"text-rejected"``. ``detail`` carries only fixed, value-free
    messages. ``frames_found`` counts detected objects across frames.
    """

    decision: str
    severity_pct: float | None
    frames_found: int
    review_required: bool
    reason: str
    detail: str = ""


def run_offline_chain(
    raw_reply: Any,
    *,
    expected_width: int,
    expected_height: int,
    limits: SamLimits | None = None,
    max_chars: int | None = None,
    envelope_max_chars: int | None = None,
) -> ChainOutcome:
    """Run the offline chain. Pure and deterministic; never raises."""
    envelope_options: dict[str, Any] = {}
    if envelope_max_chars is not None:
        envelope_options["max_chars"] = envelope_max_chars
    try:
        envelope = parse_response_envelope(raw_reply, **envelope_options)
    except SamEnvelopeError as exc:
        return ChainOutcome(
            decision="manual-review",
            severity_pct=None,
            frames_found=0,
            review_required=True,
            reason="unusable-envelope",
            detail=str(exc),
        )
    text_options: dict[str, Any] = {}
    if limits is not None:
        text_options["limits"] = limits
    if max_chars is not None:
        text_options["max_chars"] = max_chars
    adaptation = adapt_envelope(
        envelope,
        expected_width=expected_width,
        expected_height=expected_height,
        **text_options,
    )
    if adaptation.review_required:
        return ChainOutcome(
            decision="manual-review",
            severity_pct=None,
            frames_found=0,
            review_required=True,
            reason=adaptation.reason,
            detail=adaptation.detail,
        )
    found = sum(frame.match_count for frame in adaptation.frames)
    if found == 0:
        return ChainOutcome(
            decision="no-findings",
            severity_pct=None,
            frames_found=0,
            review_required=False,
            reason="zero-match",
        )
    return ChainOutcome(
        decision="manual-review",
        severity_pct=None,
        frames_found=found,
        review_required=True,
        reason="masks-opaque",
        detail="wire masks are not decoded offline",
    )
