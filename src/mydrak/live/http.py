"""Standard-library JSON POST transport for explicitly gated live clients."""

from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any, Protocol
from urllib.request import Request, urlopen

MAX_RESPONSE_BYTES = 1_048_576  # Project-local defensive parsing bound.


class JsonTransport(Protocol):
    def post_json(
        self, url: str, *, headers: Mapping[str, str], body: Mapping[str, Any], timeout_s: float,
    ) -> tuple[int, bytes]: ...


class UrllibJsonTransport:
    """Nothing calls this transport unless a provider client passes its live guard."""

    def post_json(
        self, url: str, *, headers: Mapping[str, str], body: Mapping[str, Any], timeout_s: float,
    ) -> tuple[int, bytes]:
        request = Request(
            url, data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
            headers=dict(headers), method="POST",
        )
        with urlopen(request, timeout=timeout_s) as response:
            return response.status, response.read(MAX_RESPONSE_BYTES + 1)
