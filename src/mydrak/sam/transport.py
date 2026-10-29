"""Mock-first transport scaffolding for a future SAM scan request path.

Offline-only: the only usable transport is the fake. There is no live
client here, no network import, and requesting a live transport raises
instead of returning one. Default execution therefore cannot
accidentally select a real transport.

Contract:

- ``SamScanRequest`` carries only identifiers, a scope, and a prompt: an
  image ID, a source/license reference, the authorization scope the scan
  claims, and the concept prompt. Image bytes are never accepted, logged,
  or transmitted by this module.
- ``FakeSamTransport`` returns a deterministic canned ``output_text``
  (default: empty, i.e. a zero-match). It can alternatively be configured
  to raise a timeout or return malformed text so error paths are testable
  without a network.
- ``run_scan`` accepts ONLY ``FakeSamTransport`` instances — exact type,
  subclasses included in the rejection — so an unexpected transport
  object cannot reach the scan path by accident, even one carrying a
  mock flag. Every reply is then validated against the fake's issuance
  contract (response type, ``fake-<n>`` request ID, string payload, mock
  flag) before parsing; anything unexpected is a manual-review error,
  and the attempt that fetched it stays counted. These shape checks
  catch accidents and misconfiguration — they are conventional markers,
  forgeable by same-process code, not proof of authenticity.
- These controls prevent accidental misuse in normal application flow.
  They CANNOT defend against arbitrary malicious Python code in the same
  process: such code can monkeypatch methods, forge replies, or bypass
  this module entirely. That limitation is stated plainly and is out of
  scope for an offline test scaffold.
- ``run_scan`` validates the request (including its scope), counts one
  guard attempt BEFORE dispatch, sends once, and parses the reply with
  the offline response-text parser. Results return wrapped in
  ``MockScanResult``, whose synthetic marker survives parsing and stays
  visible to callers in normal flow; same-process code can still strip,
  replace, or forge that marker, so it must not be read as proof of
  where a result came from. Timeouts and ambiguous outcomes propagate to
  the caller for manual review; this module never retries.
- A mocked reply verifies local wiring only. It never verifies live Meta
  compatibility, segmentation quality, or diagnosis.

Local bounds below are project test boundaries, not Meta limits.
"""

import re
from dataclasses import dataclass
from itertools import count
from typing import Any, Literal

from mydrak.sam.guard import LiveCampaignGuard
from mydrak.sam.response_text import SamFrame, SamResponseError, parse_response_text

#: Local request-field bounds (not Meta limits).
MAX_PROMPT_CHARS = 500
MAX_ID_CHARS = 200


class SamTransportError(ValueError):
    """Raised for transport unavailability, validation, timeouts, or replies."""


@dataclass(frozen=True)
class SamScanRequest:
    """Identifiers, claimed scope, and prompt for one scan.

    No image bytes travel here. ``scope`` must equal the guard campaign's
    authorized scope or the attempt is rejected before it is counted.
    """

    image_id: str
    image_source_license: str
    prompt: str
    scope: str = ""


@dataclass(frozen=True)
class SamScanResponse:
    """One transport reply. ``is_mock`` is always True until a live path exists."""

    request_id: str
    output_text: str
    is_mock: bool


class SamTransport:
    """Narrow transport interface: send one validated request, get one reply."""

    name = "base"

    def send(self, request: SamScanRequest) -> SamScanResponse:
        """Dispatch the request. Real transports do not exist yet."""
        raise NotImplementedError


class FakeSamTransport(SamTransport):
    """Deterministic fake for tests. No network, no randomness in replies."""

    name = "fake"

    def __init__(
        self,
        *,
        fixture_text: str = "",
        mode: Literal["ok", "timeout", "malformed"] = "ok",
    ) -> None:
        self._fixture_text = fixture_text
        self._mode = mode
        self._sent = 0
        self._ids = count(1)

    @property
    def sent_count(self) -> int:
        """Replies (or timeout failures) produced so far."""
        return self._sent

    def send(self, request: SamScanRequest) -> SamScanResponse:
        """Return the canned reply, or raise a timeout for manual review."""
        self._sent += 1
        request_id = f"fake-{next(self._ids)}"
        if self._mode == "timeout":
            raise SamTransportError(
                "fake transport timed out: attempt already counted, manual review required"
            )
        if self._mode == "malformed":
            return SamScanResponse(request_id=request_id, output_text="<0f>broken", is_mock=True)
        return SamScanResponse(
            request_id=request_id, output_text=self._fixture_text, is_mock=True
        )


def request_live_transport() -> SamTransport:
    """There is no live transport. Asking for one is an explicit error."""
    raise SamTransportError("no live SAM transport is implemented")


def default_transport() -> SamTransport:
    """Default execution path. Always the fake; never a live transport."""
    return FakeSamTransport()


#: Provenance marker carried by every offline scan result.
MOCK_PROVENANCE = "synthetic-mock"


@dataclass(frozen=True)
class MockScanResult:
    """Parsed fake-path result with a caller-visible provenance marker.

    ``provenance`` is always ``MOCK_PROVENANCE``; the constructor rejects
    anything else so this type can never be built as a live result
    through this module. Plain Python attribute assignment or
    reconstruction elsewhere can still forge one — callers must treat
    the marker as a misuse-resistant convention for normal flow, not as
    tamper-proof evidence.
    """

    frame: SamFrame
    provenance: str
    request_id: str
    scope: str

    def __post_init__(self) -> None:
        if not isinstance(self.frame, SamFrame):
            raise SamTransportError("scan result frame must be a SamFrame")
        if self.provenance != MOCK_PROVENANCE:
            raise SamTransportError("scan result provenance must be synthetic-mock")


def _validate_request(request: Any) -> SamScanRequest:
    if not isinstance(request, SamScanRequest):
        raise SamTransportError("scan request must be a SamScanRequest")
    for field_name in ("image_id", "image_source_license", "prompt", "scope"):
        value = getattr(request, field_name)
        if not isinstance(value, str) or not value:
            raise SamTransportError(f"scan request {field_name} must be a non-empty string")
        if len(value) > MAX_ID_CHARS and field_name != "prompt":
            raise SamTransportError(f"scan request {field_name} exceeds the length bound")
    if len(request.prompt) > MAX_PROMPT_CHARS:
        raise SamTransportError("scan request prompt exceeds the length bound")
    return request


def run_scan(
    *,
    guard: LiveCampaignGuard,
    transport: SamTransport,
    request: SamScanRequest,
    expected_width: int,
    expected_height: int,
) -> MockScanResult:
    """Validate, count one attempt, dispatch once, and parse the reply.

    Only ``FakeSamTransport`` — exact type, no subclasses — may dispatch
    here, so the mock-only boundary never depends on trusting a reply
    flag. The guard attempt is counted before ``transport.send`` runs, so
    a timeout or failure still consumes budget and can never cause an
    automatic second dispatch. No retries, polling, or background
    rechecks exist on this path. The parsed frame returns wrapped with
    its synthetic provenance marker.
    """
    _validate_request(request)
    if type(transport) is not FakeSamTransport:
        raise SamTransportError("only the fake transport can dispatch offline")
    if not isinstance(guard, LiveCampaignGuard):
        raise SamTransportError("scan guard must be a LiveCampaignGuard")
    attempt = guard.authorize_attempt(scope=request.scope)
    # Attempt already counted: a timeout here consumes budget and the
    # caller must review manually — no retry is attempted.
    reply = transport.send(request)
    # Validate the reply against the fake's issuance contract. The mock
    # flag alone is never trusted: type, request-ID shape, and payload
    # type must all match what FakeSamTransport produces. A rejection
    # here happens after counting — the attempt fetched this reply, so
    # its budget is spent regardless.
    if (
        not isinstance(reply, SamScanResponse)
        or not isinstance(reply.request_id, str)
        or re.fullmatch(r"fake-[0-9]+", reply.request_id) is None
        or not isinstance(reply.output_text, str)
        or reply.is_mock is not True
    ):
        raise SamTransportError(
            "reply failed provenance checks: manual review required"
        )
    try:
        frame = parse_response_text(
            reply.output_text,
            expected_width=expected_width,
            expected_height=expected_height,
        )
    except SamResponseError as exc:
        raise SamTransportError(
            f"reply failed offline parsing after attempt {attempt}: manual review required"
        ) from exc
    return MockScanResult(
        frame=frame,
        provenance=MOCK_PROVENANCE,
        request_id=reply.request_id,
        scope=request.scope,
    )
