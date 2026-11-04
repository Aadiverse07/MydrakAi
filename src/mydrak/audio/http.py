"""Stdlib multipart/form-data transport for guarded one-shot voice calls."""

from __future__ import annotations

from collections.abc import Mapping
import json
import socket
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid

MAX_VOICE_RESPONSE_BYTES = 1_048_576  # Project-local bound, not a provider limit.


class VoiceTransportError(RuntimeError):
    def __init__(self, category: str) -> None:
        super().__init__("voice HTTP request failed")
        self.category = category


class MultipartTransport(Protocol):
    def post_multipart(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout_s: float,
        max_response_bytes: int,
    ) -> tuple[int, bytes]: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def encode_multipart(request_fields: Mapping[str, Any], audio: bytes,
                     *, boundary: str | None = None) -> tuple[str, bytes]:
    if not isinstance(audio, bytes) or not audio:
        raise ValueError("audio payload is invalid")
    marker = boundary or ("mydrak-" + uuid.uuid4().hex)
    if not marker.isascii() or any(ch in marker for ch in "\r\n\" "):
        raise ValueError("multipart boundary is invalid")
    request_json = json.dumps(
        request_fields, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    prefix = f"--{marker}\r\n".encode("ascii")
    body = b"".join((
        prefix,
        b'Content-Disposition: form-data; name="request"\r\n',
        b"Content-Type: application/json\r\n\r\n",
        request_json,
        b"\r\n",
        prefix,
        b'Content-Disposition: form-data; name="audio"; filename="audio.wav"\r\n',
        b"Content-Type: audio/wav\r\n\r\n",
        audio,
        b"\r\n",
        f"--{marker}--\r\n".encode("ascii"),
    ))
    return marker, body


class UrllibMultipartTransport:
    """One HTTP request, bounded response read, no redirect or retry."""

    def __init__(self) -> None:
        self._opener = build_opener(_NoRedirect())

    def post_multipart(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout_s: float,
        max_response_bytes: int = MAX_VOICE_RESPONSE_BYTES,
    ) -> tuple[int, bytes]:
        request = Request(url, data=body, headers=dict(headers), method="POST")
        try:
            response = self._opener.open(request, timeout=timeout_s)
        except HTTPError as exc:
            status = int(exc.code)
            exc.close()
            return status, b""
        except (TimeoutError, socket.timeout):
            raise VoiceTransportError("timeout") from None
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise VoiceTransportError("timeout") from None
            raise VoiceTransportError("network_error") from None
        except Exception:
            raise VoiceTransportError("network_error") from None
        try:
            with response:
                status = int(response.status)
                raw = response.read(max_response_bytes + 1)
        except (TimeoutError, socket.timeout):
            raise VoiceTransportError("timeout") from None
        except Exception:
            raise VoiceTransportError("network_error") from None
        return status, raw
