"""Offline Responses-envelope parsing: raw reply text to output texts.

Conservative, offline-only extraction of ``output_text`` strings from a
provider reply such as the raw text returned by ``dispatch_http``. The
exact raw-HTTP-JSON envelope schema is UNVERIFIED — no live sample
exists in this repository — so this module supports only two
explicitly labeled shapes and rejects everything else fail-closed:

- ``top-level-output-text``: a top-level ``"output_text"`` string. This
  mirrors the SDK-style convenience field; it is NOT established as raw
  HTTP JSON and is accepted here only as an explicitly marked fallback.
- ``output-message-items``: a top-level ``"output"`` list whose
  ``"message"`` items carry ``"content"`` parts, collecting the
  ``"text"`` of parts typed ``"output_text"``. The message/output-text
  vocabulary follows the documented request/response shape; the exact
  envelope framing is UNVERIFIED.

Collected strings are returned unparsed. Feeding them to
``response_text.parse_response_text`` is a separate, caller-side step;
this module never imports the segmentation parser or the synthetic
fixture grammar, so envelope handling cannot be mistaken for decoded
segmentation. Extra keys (identifiers aside), usage metadata, and
non-text parts are ignored, never interpreted.
"""

import json
from dataclasses import dataclass
from typing import Any


class SamEnvelopeError(ValueError):
    """Raised when a provider reply envelope is unusable."""


#: Local defensive bounds, not provider limits.
MAX_ENVELOPE_CHARS = 8 * 1024 * 1024
MAX_OUTPUT_TEXTS = 256
MAX_REQUEST_ID_CHARS = 200


@dataclass(frozen=True)
class SamEnvelope:
    """One parsed reply: output texts plus an optional request ID.

    ``shape`` names the recognized structure (see the module docstring).
    ``request_id`` comes from a top-level ``"id"`` string when present;
    the key name itself is UNVERIFIED against raw HTTP JSON.
    """

    texts: tuple[str, ...]
    request_id: str | None
    shape: str


def _require_cap(max_chars: int) -> None:
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 1:
        raise SamEnvelopeError("input-size cap is invalid")


def _request_id(obj: dict) -> str | None:
    if "id" not in obj or obj["id"] is None:
        return None
    rid = obj["id"]
    if not isinstance(rid, str) or not rid or len(rid) > MAX_REQUEST_ID_CHARS:
        raise SamEnvelopeError("request identifier is malformed")
    return rid


def _collect_message_texts(items: list) -> tuple[str, ...]:
    texts: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            raise SamEnvelopeError("output items are malformed")
        if "type" in item and item["type"] != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            raise SamEnvelopeError("message content is malformed")
        for part in content:
            if not isinstance(part, dict):
                raise SamEnvelopeError("message content is malformed")
            if part.get("type") != "output_text":
                continue
            text = part.get("text")
            if not isinstance(text, str):
                raise SamEnvelopeError("output text part is malformed")
            texts.append(text)
            if len(texts) > MAX_OUTPUT_TEXTS:
                raise SamEnvelopeError("too many output texts")
    return tuple(texts)


def parse_response_envelope(raw: Any, *, max_chars: int = MAX_ENVELOPE_CHARS) -> SamEnvelope:
    """Parse raw reply text into output texts. Pure and deterministic.

    Empty replies, malformed JSON, non-object envelopes, indicated
    provider errors, and envelopes with no recognizable output text all
    raise ``SamEnvelopeError`` with fixed messages that never echo the
    reply. An explicit empty ``"output"`` list yields zero texts; any
    other shape that produces zero texts is rejected rather than treated
    as a zero match.
    """
    _require_cap(max_chars)
    if not isinstance(raw, str):
        raise SamEnvelopeError("reply must be a string")
    if not raw.strip():
        raise SamEnvelopeError("reply is empty")
    if len(raw) > max_chars:
        raise SamEnvelopeError("reply exceeds the input-size cap")
    try:
        obj = json.loads(raw)
    except ValueError:
        raise SamEnvelopeError("reply is not valid JSON") from None
    if not isinstance(obj, dict):
        raise SamEnvelopeError("envelope must be a JSON object")
    if obj.get("error"):
        raise SamEnvelopeError("provider error indicated")
    if "output_text" in obj and obj["output_text"] is not None:
        text = obj["output_text"]
        if not isinstance(text, str):
            raise SamEnvelopeError("output text part is malformed")
        return SamEnvelope(texts=(text,), request_id=_request_id(obj), shape="top-level-output-text")
    if "output" not in obj or obj["output"] is None:
        raise SamEnvelopeError("no output text found")
    items = obj["output"]
    if not isinstance(items, list):
        raise SamEnvelopeError("output items are malformed")
    if not items:
        return SamEnvelope(texts=(), request_id=_request_id(obj), shape="output-message-items")
    texts = _collect_message_texts(items)
    if not texts:
        raise SamEnvelopeError("no output text found")
    return SamEnvelope(texts=texts, request_id=_request_id(obj), shape="output-message-items")
