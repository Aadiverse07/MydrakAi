"""Offline SAM client boundary: validated config plus injected session.

Offline-only scaffolding: nothing here performs network I/O, and no live
transport is constructed or returned. The eventual live request path is
prepared; it is not present.

Contract:

- ``SamClientConfig`` carries explicit model ID, endpoint, timeout, and
  the NAME of the environment variable holding the credential. Every
  field is required — there are no defaults, so no unverified model ID
  or endpoint is ever silently selected. Missing, blank, malformed, or
  ``TODO``-marked values fail closed at construction.
- The HTTP serialization boundary (`serialize_sam_body`,
  `dispatch_http`) accepts only the documented API model ID `sam-3.1` —
  not the marketing `sam-3-1` variant and no other model. The generic
  config/metadata layer (`SamClientConfig`, `prepare_call`,
  `dispatch_call`) stays model-agnostic for testability. The wider
  `sam-3.1` vs `sam-3-1` discrepancy is unresolved for the API at large,
  but inside this module `sam-3.1` is the enforced documented value.
  `TODO(verify)` placeholders are rejected outright everywhere.
- Credentials live only in the process environment (or an injected
  mapping in tests), never in YAML, never in request envelopes, never
  in JSON bodies — no provider JSON serialization exists here on
  purpose. The launcher/loading convention for `.env` is unresolved;
  this module does not load `.env` and never claims it is loaded.
- ``resolve_api_key`` reads the credential per call from the injected
  mapping (tests) or ``os.environ`` (runtime), mirroring
  ``data_policy_from_env``. Failures raise generic errors that echo no
  values. Resolved keys are never stored on objects, logged, or placed
  in envelopes.
- ``SamOutboundCall`` is credential-free request metadata only
  (endpoint, timeout, model, prompt, image reference, scope). It is NOT
  a provider JSON body. Serialization of the documented shape lives in
  the offline-only ``serialize_sam_body`` boundary below; live use
  stays unauthorized and unimplemented.
- ``SamSession`` is a minimal injected protocol. Tests use a recording
  fake; no real HTTP session is ever instantiated. ``dispatch_call``
  validates, resolves the credential, and invokes the session exactly
  once. Session failures propagate to the caller for manual review —
  no retries exist on this path.

Local validation bounds below are project test boundaries, not Meta
claims. The request-body shape below follows the official-source
findings supplied for the serialization task (model `sam-3.1`,
`POST {base}/responses`, one user message with `input_text` and
`input_image` parts, `stream: false`).

The documented API model ID `sam-3.1` is a request-format fact only. It
establishes nothing about this account's eligibility, credits, billing
exposure, or live compatibility — all of those remain UNVERIFIED and no
live request is authorized or performed here.
"""

import copy
import hashlib
import ipaddress
import json
import math
import os
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


class SamConfigError(ValueError):
    """Raised when SAM client configuration or credentials are unusable."""


#: Rejected anywhere in model/endpoint/credential-name values: unresolved
#: repository placeholders must never reach a session call.
_PLACEHOLDER_MARK = "TODO"

_ENV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _require_clean(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SamConfigError(f"SAM client {what} must be a non-empty string")
    if value != value.strip() or any(char.isspace() for char in value):
        raise SamConfigError(f"SAM client {what} must not contain whitespace")
    if _PLACEHOLDER_MARK in value:
        raise SamConfigError(f"SAM client {what} is unresolved")
    return value


#: One DNS label: alphanumerics with interior hyphens (strict ASCII
#: syntax check; non-ASCII hosts are rejected as malformed locally).
_HOST_LABEL_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")

_ASCII_DIGITS = frozenset("0123456789")


def _require_port(text: str, what: str) -> None:
    if not text or len(text) > 5 or any(char not in _ASCII_DIGITS for char in text):
        raise SamConfigError(f"SAM {what} is malformed")
    if int(text) < 1 or int(text) > 65535:
        raise SamConfigError(f"SAM {what} is malformed")


def _parse_url(value: Any, *, what: str, schemes: frozenset, scheme_error: str) -> None:
    """Strictly validate HTTP(S) URL syntax. Syntax only.

    Verifies the scheme, a non-empty hostname, absence of userinfo, and
    a numeric in-range port when present. Passing says nothing about
    public accessibility, approval for use, or reachability — those
    require separate evidence. Anything else is malformed.
    """
    if not isinstance(value, str):
        raise SamConfigError(f"SAM {what} is malformed")
    if any(char.isspace() or ord(char) < 0x20 or ord(char) == 0x7F for char in value):
        raise SamConfigError(f"SAM {what} is malformed")
    scheme, sep, rest = value.partition("://")
    if not sep or not rest or rest.startswith("/"):
        raise SamConfigError(f"SAM {what} is malformed")
    if scheme.lower() not in schemes:
        raise SamConfigError(scheme_error)
    end = len(rest)
    for mark in ("/", "?", "#"):
        idx = rest.find(mark)
        if idx != -1:
            end = min(end, idx)
    authority = rest[:end]
    if not authority or "@" in authority:
        # Empty hosts and userinfo (possible credential material) are
        # never accepted.
        raise SamConfigError(f"SAM {what} is malformed")
    if authority.startswith("["):
        close = authority.find("]")
        if close == -1:
            raise SamConfigError(f"SAM {what} is malformed")
        literal = authority[1:close]
        if not literal:
            raise SamConfigError(f"SAM {what} is malformed")
        try:
            ipaddress.IPv6Address(literal)
        except ValueError:
            raise SamConfigError(f"SAM {what} is malformed") from None
        remainder = authority[close + 1:]
        if remainder:
            if not remainder.startswith(":"):
                raise SamConfigError(f"SAM {what} is malformed")
            _require_port(remainder[1:], what)
        return
    host, colon, port_text = authority.rpartition(":")
    if colon:
        _require_port(port_text, what)
    else:
        host = authority
    if host.endswith("."):
        host = host[:-1]
    labels = host.split(".")
    if any(_HOST_LABEL_RE.fullmatch(label) is None for label in labels):
        raise SamConfigError(f"SAM {what} is malformed")


def _require_endpoint(value: Any) -> str:
    endpoint = _require_clean(value, "endpoint")
    # Local safety rule, not a Meta claim: credential-bearing calls must
    # not be constructed for plaintext transport. Revisitable with evidence.
    _parse_url(
        endpoint,
        what="client endpoint",
        schemes=frozenset({"https"}),
        scheme_error="SAM client endpoint must be an https URL",
    )
    return endpoint


def _require_timeout(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SamConfigError("SAM client timeout must be a number of seconds")
    if not math.isfinite(value) or value <= 0:
        raise SamConfigError("SAM client timeout must be finite and positive")
    return float(value)


def _require_env_name(value: Any) -> str:
    name = _require_clean(value, "credential variable")
    if _ENV_NAME_RE.fullmatch(name) is None:
        raise SamConfigError("SAM client credential variable is malformed")
    return name


@dataclass(frozen=True)
class SamClientConfig:
    """Explicit SAM client settings. All fields required, no defaults."""

    model_id: str
    endpoint: str
    timeout_s: float
    api_key_env_var: str

    def __post_init__(self) -> None:
        _require_clean(self.model_id, "model ID")
        _require_endpoint(self.endpoint)
        _require_timeout(self.timeout_s)
        _require_env_name(self.api_key_env_var)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "SamClientConfig":
        """Build from an explicit mapping (e.g. one parsed YAML section)."""
        if not isinstance(mapping, Mapping):
            raise SamConfigError("SAM client settings must be a mapping")
        expected = ("model_id", "endpoint", "timeout_s", "api_key_env_var")
        missing = [key for key in expected if key not in mapping]
        if missing:
            raise SamConfigError(f"SAM client settings missing: {', '.join(sorted(missing))}")
        extra = sorted(key for key in mapping if key not in expected)
        if extra:
            raise SamConfigError(f"SAM client settings unexpected: {', '.join(extra)}")
        return cls(
            model_id=mapping["model_id"],
            endpoint=mapping["endpoint"],
            timeout_s=mapping["timeout_s"],
            api_key_env_var=mapping["api_key_env_var"],
        )


def resolve_api_key(
    config: SamClientConfig, environ: Mapping[str, str] | None = None
) -> str:
    """Read the credential per call. Never stored, logged, or echoed."""
    if not isinstance(config, SamClientConfig):
        raise SamConfigError("SAM client configuration is required")
    values = os.environ if environ is None else environ
    try:
        key = values.get(config.api_key_env_var)
    except AttributeError:
        raise SamConfigError("SAM client environment mapping is unusable") from None
    if not isinstance(key, str) or not key.strip():
        raise SamConfigError("SAM API credential is missing or blank")
    return key


@dataclass(frozen=True)
class SamOutboundCall:
    """Credential-free request metadata. Not a provider JSON body."""

    endpoint: str
    timeout_s: float
    model_id: str
    prompt: str
    image_id: str
    scope: str


class SamSession(Protocol):
    """Minimal injected session. No real implementation exists yet."""

    def submit(self, call: SamOutboundCall, *, api_key: str) -> str: ...


def prepare_call(
    config: SamClientConfig, *, prompt: str, image_id: str, scope: str
) -> SamOutboundCall:
    """Build the credential-free metadata envelope for one call."""
    if not isinstance(config, SamClientConfig):
        raise SamConfigError("SAM client configuration is required")
    for field_name, value, bound in (
        ("prompt", prompt, 500),
        ("image_id", image_id, 200),
        ("scope", scope, 200),
    ):
        if not isinstance(value, str) or not value:
            raise SamConfigError(f"SAM call {field_name} must be a non-empty string")
        if len(value) > bound:
            raise SamConfigError(f"SAM call {field_name} exceeds the length bound")
    return SamOutboundCall(
        endpoint=config.endpoint,
        timeout_s=config.timeout_s,
        model_id=config.model_id,
        prompt=prompt,
        image_id=image_id,
        scope=scope,
    )


def dispatch_call(
    *,
    session: SamSession,
    config: SamClientConfig,
    call: SamOutboundCall,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Validate, resolve the credential, and invoke the session once.

    Preconditions fail before the session is touched, so invalid
    configuration or missing credentials cause zero session calls.
    Session failures propagate unchanged for manual review; this path
    never retries. Future sessions must keep credentials out of their
    own errors, logs, and bodies — no such implementation exists yet.
    """
    if not isinstance(config, SamClientConfig):
        raise SamConfigError("SAM client configuration is required")
    if not isinstance(call, SamOutboundCall):
        raise SamConfigError("SAM outbound call is required")
    submit = getattr(session, "submit", None)
    if not callable(submit):
        raise SamConfigError("SAM session must provide a submit method")
    api_key = resolve_api_key(config, environ)
    return submit(call, api_key=api_key)


#: Single canonical Responses base URL. Appended with the path in exactly
#: one place (below); anything else is rejected, never joined or rewritten.
SAM_API_BASE_URL = "https://api.meta.ai/v1"
RESPONSES_PATH = "/responses"

#: The documented API model ID. This is a request-format fact only: it
#: establishes nothing about account eligibility, credits, billing, or
#: live compatibility, all of which remain UNVERIFIED.
SAM_DOCUMENTED_MODEL_ID = "sam-3.1"


def canonical_responses_url() -> str:
    """The one accepted Responses endpoint. No joining, no rewriting."""
    return SAM_API_BASE_URL + RESPONSES_PATH


_B64_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
)


#: Data-URL media types accepted as image input. Any `image/*` subtype
#: is allowed (case-insensitive); non-image types are rejected. This is a
#: generic syntax rule, not a list of SAM-supported formats.
_DATA_MEDIA_RE = re.compile(r"image/[A-Za-z0-9][A-Za-z0-9!#$&^_.+\-]*", re.IGNORECASE)


def _require_image_ref(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SamConfigError("SAM image input must be a non-empty string")
    if any(char.isspace() for char in value):
        raise SamConfigError("SAM image input is malformed")
    if value.startswith("data:"):
        marker = ";base64,"
        if marker not in value:
            raise SamConfigError("SAM image input is malformed")
        mediatype, _, payload = value[len("data:"):].partition(marker)
        if not mediatype or not payload:
            raise SamConfigError("SAM image input is malformed")
        if _DATA_MEDIA_RE.fullmatch(mediatype) is None:
            raise SamConfigError("SAM image input is malformed")
        if any(char not in _B64_CHARS for char in payload):
            raise SamConfigError("SAM image input is malformed")
        if len(payload) % 4 != 0:
            raise SamConfigError("SAM image input is malformed")
        unpadded = payload.rstrip("=")
        if len(payload) - len(unpadded) > 2 or "=" in unpadded:
            raise SamConfigError("SAM image input is malformed")
        return value
    lowered = value.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        _parse_url(
            value,
            what="image input",
            schemes=frozenset({"http", "https"}),
            scheme_error="SAM image input is malformed",
        )
        return value
    raise SamConfigError("SAM image input is malformed")


def serialize_sam_body(
    *, model_id: str, prompt: str, image_ref: str, stream: bool = False
) -> dict[str, Any]:
    """Build the documented Responses JSON body. Pure and deterministic.

    Exactly one user message with the text part then the image part, plus
    top-level ``model`` and ``stream``. Only the documented API model ID
    ``sam-3.1`` is accepted here — not the marketing ``sam-3-1`` variant
    and no other model; that ID is a request-format fact only and says
    nothing about eligibility, billing, or live compatibility (all
    UNVERIFIED). Only public HTTP(S) URLs and base64 data URLs are
    accepted as image input; no SAM-specific size, dimension, or format
    limits are invented or enforced here.
    """
    model = _require_clean(model_id, "model ID")
    if model != SAM_DOCUMENTED_MODEL_ID:
        raise SamConfigError("SAM model ID must be sam-3.1")
    if not isinstance(prompt, str) or not prompt:
        raise SamConfigError("SAM prompt must be a non-empty string")
    image = _require_image_ref(image_ref)
    if not isinstance(stream, bool):
        raise SamConfigError("SAM stream flag must be a boolean")
    return {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image},
                ],
            }
        ],
        "stream": stream,
    }


def _validate_body_shape(body: Any) -> dict:
    """Revalidate a full HTTP body against the documented shape.

    Rejects unexpected keys at every level, malformed nesting, and bad
    image references. Raises value-free errors that never echo the body.
    """
    if not isinstance(body, dict):
        raise SamConfigError("SAM HTTP body must be a mapping")
    if set(body) != {"model", "input", "stream"}:
        raise SamConfigError("SAM HTTP body has unexpected keys")
    if not isinstance(body["model"], str) or not body["model"]:
        raise SamConfigError("SAM HTTP body is malformed")
    messages = body["input"]
    if not isinstance(messages, list) or len(messages) != 1:
        raise SamConfigError("SAM HTTP body is malformed")
    message = messages[0]
    if not isinstance(message, dict):
        raise SamConfigError("SAM HTTP body has unexpected keys")
    if set(message) - {"role", "content", "type"}:
        raise SamConfigError("SAM HTTP body has unexpected keys")
    if "type" in message and message["type"] != "message":
        raise SamConfigError("SAM HTTP body is malformed")
    if message["role"] != "user":
        raise SamConfigError("SAM HTTP body is malformed")
    content = message["content"]
    if not isinstance(content, list) or len(content) != 2:
        raise SamConfigError("SAM HTTP body is malformed")
    text_part, image_part = content
    if not isinstance(text_part, dict) or set(text_part) != {"type", "text"}:
        raise SamConfigError("SAM HTTP body has unexpected keys")
    if text_part["type"] != "input_text":
        raise SamConfigError("SAM HTTP body is malformed")
    if not isinstance(text_part["text"], str) or not text_part["text"]:
        raise SamConfigError("SAM HTTP body is malformed")
    if not isinstance(image_part, dict) or set(image_part) != {"type", "image_url"}:
        raise SamConfigError("SAM HTTP body has unexpected keys")
    if image_part["type"] != "input_image":
        raise SamConfigError("SAM HTTP body is malformed")
    _require_image_ref(image_part["image_url"])
    if not isinstance(body["stream"], bool):
        raise SamConfigError("SAM HTTP body is malformed")
    return body


def _body_snapshot(body: Mapping[str, Any]) -> str:
    """Canonical digest of a validated body, taken at construction.

    Change detection only, not a security claim: same-process code can
    always rebuild a request. Lets dispatch reject a body mutated after
    its request was constructed and validated.
    """
    try:
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        raise SamConfigError("SAM HTTP body is malformed") from None
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SamHttpRequest:
    """Validated HTTP call: method, canonical URL, timeout, JSON body.

    Carries no credential. The body is shape-validated, digested, and
    deep-copied at construction; the mapping itself is not frozen, but
    dispatch revalidates it against the construction snapshot and
    rejects anything mutated after construction before the session runs.
    """

    method: str
    url: str
    timeout_s: float
    body: dict
    _snapshot: str = field(default="", repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.method != "POST":
            raise SamConfigError("SAM HTTP method must be POST")
        if self.url != canonical_responses_url():
            raise SamConfigError("SAM endpoint path is unexpected")
        _require_timeout(self.timeout_s)
        if not isinstance(self.body, dict) or not self.body:
            raise SamConfigError("SAM HTTP body must be a non-empty mapping")
        _validate_body_shape(self.body)
        object.__setattr__(self, "_snapshot", _body_snapshot(self.body))
        object.__setattr__(self, "body", copy.deepcopy(self.body))


class SamHttpSession(Protocol):
    """Minimal injected HTTP session. No real implementation exists yet."""

    def post_http(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_s: float,
    ) -> str: ...


def build_http_request(
    config: SamClientConfig,
    call: SamOutboundCall,
    *,
    image_ref: str,
    stream: bool = False,
) -> SamHttpRequest:
    """Combine validated config and call metadata into one HTTP request.

    Rejects configuration/call mismatches and non-canonical endpoints
    instead of joining or rewriting paths. Pure: no network I/O, no
    client objects, no connections.
    """
    if not isinstance(config, SamClientConfig):
        raise SamConfigError("SAM client configuration is required")
    if not isinstance(call, SamOutboundCall):
        raise SamConfigError("SAM outbound call is required")
    if (call.model_id, call.endpoint, call.timeout_s) != (
        config.model_id,
        config.endpoint,
        config.timeout_s,
    ):
        raise SamConfigError("SAM call does not match its configuration")
    return SamHttpRequest(
        method="POST",
        url=config.endpoint,
        timeout_s=config.timeout_s,
        body=serialize_sam_body(
            model_id=config.model_id, prompt=call.prompt,
            image_ref=image_ref, stream=stream,
        ),
    )


def dispatch_http(
    *,
    session: SamHttpSession,
    config: SamClientConfig,
    http_request: SamHttpRequest,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Validate, resolve the credential, and invoke the session once.

    The key travels exclusively in the ``Authorization`` header metadata;
    it never enters the JSON body, logs, or errors. The full body is
    revalidated here and checked against its construction snapshot, so
    post-construction mutation can neither bypass validation nor change
    what is sent; the session receives a copy, never the stored mapping.
    Preconditions fail before the session is touched. Every
    injected-session failure — including ``SamConfigError`` — is
    converted to a fixed value-free error raised outside the handler,
    so the original stays reachable through neither ``__context__`` nor
    ``__cause__`` and session messages cannot leak the credential or
    body content; this path never retries. Returns the raw reply text
    unparsed — envelope parsing is a separate, unimplemented task.
    """
    if not isinstance(config, SamClientConfig):
        raise SamConfigError("SAM client configuration is required")
    if not isinstance(http_request, SamHttpRequest):
        raise SamConfigError("SAM HTTP request is required")
    post = getattr(session, "post_http", None)
    if not callable(post):
        raise SamConfigError("SAM session must provide a post_http method")
    if http_request.method != "POST" or http_request.url != canonical_responses_url():
        raise SamConfigError("SAM HTTP request is unexpected")
    if config.endpoint != canonical_responses_url():
        raise SamConfigError("SAM HTTP request is unexpected")
    # This boundary serves SAM only: the documented model ID is enforced
    # here as well as in `serialize_sam_body`, so hand-built bodies and
    # foreign configs cannot pass. The generic config/metadata layer
    # (`SamClientConfig`, `prepare_call`, `dispatch_call`) stays
    # model-agnostic for testability; see the module contract.
    if config.model_id != SAM_DOCUMENTED_MODEL_ID:
        raise SamConfigError("SAM model ID must be sam-3.1")
    body = _validate_body_shape(http_request.body)
    if body["model"] != config.model_id:
        raise SamConfigError("SAM HTTP body does not match its configuration")
    if http_request.timeout_s != config.timeout_s:
        raise SamConfigError("SAM HTTP request does not match its configuration")
    if _body_snapshot(body) != http_request._snapshot:
        raise SamConfigError("SAM HTTP body changed after construction")
    api_key = resolve_api_key(config, environ)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    # The sanitized error is raised OUTSIDE the except block on purpose:
    # `raise ... from None` alone still leaves the original exception
    # reachable via `__context__`. Raising here severs both `__context__`
    # and `__cause__`, so no session text, headers, credential, or body
    # content can reach the caller through the public error.
    session_failed = False
    try:
        return post(
            url=http_request.url,
            headers=headers,
            json_body=copy.deepcopy(body),
            timeout_s=http_request.timeout_s,
        )
    except Exception:
        session_failed = True
    if session_failed:
        raise SamConfigError("SAM session call failed")
