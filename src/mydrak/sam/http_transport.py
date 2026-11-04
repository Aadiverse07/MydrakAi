"""Bounded standard-library SSE POST transport for the explicit SAM client.

This transport is never selected by ``sam.transport.default_transport`` and
is used only by the guarded SAM live client. Its input/output contract is
easy to replace with a fake in offline tests.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from typing import Any, Protocol
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class SamSseTransportError(RuntimeError):
    """Safe HTTP failure metadata; never contains a body or request URL."""

    def __init__(self, category: str, *, status: int | None = None) -> None:
        super().__init__("SAM streaming request failed")
        self.category = category
        self.status = status


class SseTransport(Protocol):
    def post_sse(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_s: float,
        max_response_bytes: int,
    ) -> Iterator[bytes]: ...


class _NoRedirect(HTTPRedirectHandler):
    """Do not forward bearer credentials to a redirect target."""

    def redirect_request(self, *_args, **_kwargs):
        return None


class UrllibSseTransport:
    """POST JSON and yield bounded response chunks without retaining a body."""

    def __init__(self) -> None:
        self._opener = build_opener(_NoRedirect())

    def post_sse(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_s: float,
        max_response_bytes: int,
    ) -> Iterator[bytes]:
        request = Request(
            url,
            data=json.dumps(json_body, separators=(",", ":")).encode("utf-8"),
            headers=dict(headers),
            method="POST",
        )
        try:
            response = self._opener.open(request, timeout=timeout_s)
        except HTTPError as exc:
            status = int(exc.code)
            exc.close()
            raise SamSseTransportError("http_error", status=status) from None
        except TimeoutError:
            raise SamSseTransportError("timeout") from None
        except Exception:
            raise SamSseTransportError("network_error") from None

        def chunks() -> Iterator[bytes]:
            total = 0
            try:
                with response:
                    while True:
                        chunk = response.read(min(8192, max_response_bytes - total + 1))
                        if not chunk:
                            return
                        total += len(chunk)
                        if total > max_response_bytes:
                            raise SamSseTransportError("response_too_large")
                        yield chunk
            except SamSseTransportError:
                raise
            except TimeoutError:
                raise SamSseTransportError("timeout") from None
            except Exception:
                raise SamSseTransportError("network_error") from None

        return chunks()
