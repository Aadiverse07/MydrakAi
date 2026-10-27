"""Mock-only intake flow: validate -> privacy gate -> mock diagnosis -> trace.

Design notes:

- The boundary accepts image *descriptors* (format, dimensions, byte size),
  never raw image/audio bytes, so bytes cannot leak into logs or traces.
- Size/format limits below are local intake boundaries for synthetic testing.
  They are NOT Telegram, Meta API, or media-pipeline limits (all UNVERIFIED).
- The privacy gate (`require_external_processing_allowed`) runs before the
  mock diagnosis and before the optional `sender` hook. A blocked request
  never invokes `sender`.
- `sender`, when supplied, receives metadata only (no bytes, no credentials,
  no personal data). It stands in for a future external-processing client that
  does not exist yet; production senders remain unimplemented.
- Telegram intake is NOT implemented: no SDK, no update payload format is
  assumed here. A future Telegram handler must map its update onto
  `IntakeImage` and is still required to pass this gate first.
"""

import hashlib
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from mydrak.privacy.data_policy import (
    DataClass,
    DataPolicy,
    DataPolicyError,
    ProcessingEvidence,
    ProviderMode,
    parse_data_policy,
    require_external_processing_allowed,
)

# Local intake boundaries for synthetic testing (see module docstring).
SUPPORTED_FORMATS = ("jpeg", "png")
_FORMAT_ALIASES = {"jpg": "jpeg"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_DIMENSION = 20000

MOCK_LABEL = "MOCK"
MOCK_UNCERTAINTY = "cannot tell"  # A mock carries no score; never a diagnosis.


class IntakeError(ValueError):
    """Raised when a synthetic intake event fails validation."""


@dataclass(frozen=True)
class IntakeImage:
    """Descriptor for one synthetic test image. Carries no pixel data."""

    format: str
    width: int
    height: int
    size_bytes: int


@dataclass(frozen=True)
class IntakeResponse:
    """Structured mock-intake outcome with its privacy-safe trace."""

    request_id: str
    status: str  # "mock_complete" | "blocked"
    findings: dict[str, Any]
    uncertainty: str
    safety_line: str
    next_step: str
    trace: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "findings": dict(self.findings),
            "uncertainty": self.uncertainty,
            "safety_line": self.safety_line,
            "next_step": self.next_step,
            "trace": {k: (list(v) if isinstance(v, list) else v) for k, v in self.trace.items()},
        }


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def coerce_image(event: IntakeImage | Mapping[str, Any]) -> IntakeImage:
    """Coerce a dataclass or plain mapping into a validated IntakeImage."""
    if isinstance(event, IntakeImage):
        data = {"format": event.format, "width": event.width, "height": event.height, "size_bytes": event.size_bytes}
    elif isinstance(event, Mapping):
        data = dict(event)
    else:
        raise IntakeError(f"intake event must be a mapping or IntakeImage, got {type(event).__name__}")

    raw_format = data.get("format")
    if not isinstance(raw_format, str):
        raise IntakeError("image 'format' must be a string")
    fmt = _FORMAT_ALIASES.get(raw_format.lower(), raw_format.lower())
    if fmt not in SUPPORTED_FORMATS:
        raise IntakeError(f"unsupported image format: {raw_format!r} (expected one of {list(SUPPORTED_FORMATS)})")

    for key in ("width", "height"):
        value = data.get(key)
        if not _is_int(value):
            raise IntakeError(f"image {key!r} must be an integer")
        if not 1 <= value <= MAX_DIMENSION:
            raise IntakeError(f"image {key!r} out of range: {value!r}")

    size = data.get("size_bytes")
    if not _is_int(size):
        raise IntakeError("image 'size_bytes' must be an integer")
    if not 1 <= size <= MAX_IMAGE_BYTES:
        raise IntakeError(f"image 'size_bytes' out of range: {size!r} (max {MAX_IMAGE_BYTES})")

    return IntakeImage(format=fmt, width=data["width"], height=data["height"], size_bytes=size)


def mock_diagnose(image: IntakeImage) -> dict[str, Any]:
    """Deterministic mock finding, clearly labeled; never a real diagnosis."""
    fingerprint = f"{image.format}|{image.width}|{image.height}|{image.size_bytes}"
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:8]
    return {
        "label": MOCK_LABEL,
        "issue": "simulated leaf-spot pattern (not a diagnosis)",
        "pattern_id": f"mock-{digest}",
    }


def _stage(stages: list[dict[str, Any]], name: str, outcome: str, duration_ms: float) -> None:
    stages.append({"stage": name, "outcome": outcome, "duration_ms": round(duration_ms, 3)})


def process_intake(
    event: IntakeImage | Mapping[str, Any],
    *,
    data_policy_value: str | None,
    safety_card: Mapping[str, Any],
    data_class: DataClass = DataClass.PRIVATE,
    evidence: ProcessingEvidence | None = None,
    sender: Callable[[dict[str, Any]], None] | None = None,
    source: str = "synthetic",
) -> IntakeResponse:
    """Run the mock-only intake flow and return a structured safe response."""
    request_id = uuid.uuid4().hex
    started = time.perf_counter()
    stages: list[dict[str, Any]] = []

    for key in ("safety_line", "referral_text"):
        if not safety_card.get(key):
            raise IntakeError(f"safety card is missing {key!r}; refusing to reply without it")

    t0 = time.perf_counter()
    image = coerce_image(event)
    _stage(stages, "validate_input", "ok", (time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    try:
        policy = parse_data_policy(data_policy_value)
    except DataPolicyError as exc:
        _stage(stages, "policy_decision", "invalid_policy", (time.perf_counter() - t0) * 1000)
        return _blocked(request_id, source, image, data_class, "invalid_policy", str(exc), safety_card, stages, started)
    gate_evidence = evidence if evidence is not None else ProcessingEvidence(provider_mode=ProviderMode.STANDARD)
    try:
        require_external_processing_allowed(policy, data_class, gate_evidence)
    except DataPolicyError as exc:
        _stage(stages, "policy_decision", "blocked", (time.perf_counter() - t0) * 1000)
        return _blocked(request_id, source, image, data_class, policy.value, str(exc), safety_card, stages, started)
    _stage(stages, "policy_decision", "allowed_mock", (time.perf_counter() - t0) * 1000)

    if sender is not None:
        sender(
            {
                "request_id": request_id,
                "data_class": data_class.value,
                "policy": policy.value,
                "image": {
                    "format": image.format,
                    "width": image.width,
                    "height": image.height,
                    "size_bytes": image.size_bytes,
                },
            }
        )

    t0 = time.perf_counter()
    findings = mock_diagnose(image)
    _stage(stages, "mock_diagnosis", "ok", (time.perf_counter() - t0) * 1000)

    trace = _trace(request_id, source, image, data_class, policy.value, "allowed_mock", None, stages, started)
    return IntakeResponse(
        request_id=request_id,
        status="mock_complete",
        findings=findings,
        uncertainty=MOCK_UNCERTAINTY,
        safety_line=str(safety_card["safety_line"]),
        next_step=str(safety_card["referral_text"]),
        trace=trace,
    )


def _trace(
    request_id: str,
    source: str,
    image: IntakeImage,
    data_class: DataClass,
    policy: str,
    decision: str,
    reason: str | None,
    stages: list[dict[str, Any]],
    started: float,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "source": source,
        "data_class": data_class.value,
        "policy": policy,
        "decision": decision,
        "reason": reason,
        "image": {
            "format": image.format,
            "width": image.width,
            "height": image.height,
            "size_bytes": image.size_bytes,
        },
        "stages": [dict(s) for s in stages],
        "total_duration_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _blocked(
    request_id: str,
    source: str,
    image: IntakeImage,
    data_class: DataClass,
    policy: str,
    reason: str,
    safety_card: Mapping[str, Any],
    stages: list[dict[str, Any]],
    started: float,
) -> IntakeResponse:
    trace = _trace(request_id, source, image, data_class, policy, "blocked", reason, stages, started)
    return IntakeResponse(
        request_id=request_id,
        status="blocked",
        findings={"label": MOCK_LABEL, "issue": "no finding: processing blocked before diagnosis"},
        uncertainty=MOCK_UNCERTAINTY,
        safety_line=str(safety_card["safety_line"]),
        next_step=str(safety_card["referral_text"]),
        trace=trace,
    )
