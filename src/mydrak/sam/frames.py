"""Caller-side adapter: envelope output texts to parsed frames.

Connects ``envelope.parse_response_envelope`` results to
``response_text.parse_response_text``. Each text is parsed against the
same caller-supplied expected image dimensions — dimensions are never
invented here nor derived from provider output, and per-text dimension
variance is UNVERIFIED.

Empty-string texts are valid zero-match results (per the documented
grammar). An envelope with zero texts carries no evidence, so it yields
a manual-review outcome instead of an invented zero-match frame. Any
text the response parser rejects — malformed content, dimension
mismatch, or breached input caps — likewise yields manual review
carrying only the parser's fixed, value-free message, never a raised
error and never a success claim. Only a non-envelope input raises
``SamResponseError`` fail-closed, since there is nothing to adapt.

Provider behavior stays UNVERIFIED: this adapter proves no live
compatibility and performs no diagnosis.
"""

from dataclasses import dataclass
from typing import Any

from mydrak.sam.envelope import SamEnvelope
from mydrak.sam.output import SamLimits
from mydrak.sam.response_text import SamFrame, SamResponseError, parse_response_text


@dataclass(frozen=True)
class FrameAdaptation:
    """Outcome of adapting one envelope.

    ``reason`` is ``"parsed"``, ``"no-output-texts"``, or
    ``"text-rejected"``. ``detail`` carries the parser's fixed message
    for rejected texts and is empty otherwise; it never echoes provider
    text. A ``review_required`` outcome must never be read as a
    successful diagnosis.
    """

    frames: tuple[SamFrame, ...]
    review_required: bool
    reason: str
    detail: str = ""


def adapt_envelope(
    envelope: Any,
    *,
    expected_width: int,
    expected_height: int,
    limits: SamLimits | None = None,
    max_chars: int | None = None,
) -> FrameAdaptation:
    """Parse every envelope text into a frame. Pure and deterministic."""
    if not isinstance(envelope, SamEnvelope):
        raise SamResponseError("adapter input must be a SamEnvelope")
    if not envelope.texts:
        return FrameAdaptation(
            frames=(),
            review_required=True,
            reason="no-output-texts",
            detail="envelope contains no output texts",
        )
    options: dict[str, Any] = {}
    if limits is not None:
        options["limits"] = limits
    if max_chars is not None:
        options["max_chars"] = max_chars
    frames: list[SamFrame] = []
    for text in envelope.texts:
        try:
            frames.append(
                parse_response_text(
                    text,
                    expected_width=expected_width,
                    expected_height=expected_height,
                    **options,
                )
            )
        except SamResponseError as exc:
            return FrameAdaptation(
                frames=(),
                review_required=True,
                reason="text-rejected",
                detail=str(exc),
            )
    return FrameAdaptation(frames=tuple(frames), review_required=False, reason="parsed")
