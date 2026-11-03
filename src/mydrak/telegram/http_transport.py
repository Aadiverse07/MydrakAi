"""Standard-library Telegram HTTPS transport using the local API reference."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid

from mydrak.telegram.client import (
    MAX_FILE_DOWNLOAD_BYTES, TelegramApiError, TelegramResponseError,
    TelegramTimeoutError,
)

API_URL_PREFIX = "https://api.telegram.org/bot"
FILE_URL_PREFIX = "https://api.telegram.org/file/bot"
MAX_API_RESPONSE_BYTES = 20 * 1024 * 1024  # Project-local response memory bound.
_METHODS = frozenset({"getUpdates", "sendMessage", "sendPhoto", "getFile"})


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        # Never forward a token-bearing API URL to a redirect target.
        return None


_OPENER = build_opener(_NoRedirect())


class TelegramHttpTransport:
    """HTTPS transport; token-bearing URLs and lower-level errors stay private."""

    def __init__(self, token: str) -> None:
        self._token = token

    def __repr__(self) -> str:
        return "TelegramHttpTransport(token=<redacted>)"

    def call(self, method: str, parameters: Mapping[str, Any], *, timeout_s: float) -> Any:
        if method not in _METHODS or not isinstance(parameters, Mapping):
            raise TelegramResponseError("Telegram method request is invalid")
        url = f"{API_URL_PREFIX}{quote(self._token, safe='-._~:')}/{method}"
        try:
            if method == "sendPhoto" and isinstance(parameters.get("photo"), bytes):
                body, content_type = _multipart(parameters)
            else:
                body = json.dumps(parameters, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                content_type = "application/json"
            request = Request(
                url, data=body, method="POST",
                headers={"Content-Type": content_type, "Accept": "application/json"},
            )
        except Exception:
            raise TelegramResponseError("Telegram request could not be encoded") from None
        payload = self._read_request(request, timeout_s)
        if not isinstance(payload, Mapping) or type(payload.get("ok")) is not bool:
            raise TelegramResponseError("Telegram response wrapper is invalid")
        if payload["ok"] is False:
            # Do not expose provider description, headers, body, or request URL.
            raise TelegramApiError("Telegram API returned ok=false")
        if "result" not in payload:
            raise TelegramResponseError("Telegram response result is missing")
        return payload["result"]

    def download(self, file_path: str, *, max_bytes: int, timeout_s: float) -> bytes:
        if (
            not isinstance(file_path, str) or not file_path or len(file_path) > 1024
            or file_path.startswith("/") or ".." in file_path.split("/")
            or type(max_bytes) is not int or not 1 <= max_bytes <= MAX_FILE_DOWNLOAD_BYTES
        ):
            raise TelegramResponseError("Telegram download request is invalid")
        encoded_path = quote(file_path, safe="/-._~")
        url = f"{FILE_URL_PREFIX}{quote(self._token, safe='-._~:')}/{encoded_path}"
        request = Request(url, method="GET", headers={"Accept": "application/octet-stream"})
        data, failure = self._read_bytes(request, timeout_s, max_bytes)
        if failure == "timeout":
            raise TelegramTimeoutError("Telegram file download timed out")
        if failure:
            raise TelegramApiError("Telegram file download failed")
        if len(data) > max_bytes:
            raise TelegramResponseError("Telegram file download exceeded its bound")
        return data

    def _read_request(self, request: Request, timeout_s: float) -> Any:
        raw, failure = self._read_bytes(request, timeout_s, MAX_API_RESPONSE_BYTES)
        if failure == "timeout":
            raise TelegramTimeoutError("Telegram request timed out")
        if failure:
            raise TelegramApiError("Telegram HTTP request failed")
        if len(raw) > MAX_API_RESPONSE_BYTES:
            raise TelegramResponseError("Telegram response exceeded its local bound")
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            raise TelegramResponseError("Telegram response JSON is invalid") from None

    @staticmethod
    def _read_bytes(request: Request, timeout_s: float, maximum: int
                    ) -> tuple[bytes, str | None]:
        timeout = False
        failed = False
        data = b""
        try:
            with _OPENER.open(request, timeout=timeout_s) as response:
                data = response.read(maximum + 1)
        except TimeoutError:
            timeout = True
        except Exception as exc:
            reason = getattr(exc, "reason", None)
            timeout = isinstance(reason, TimeoutError)
            failed = not timeout
        if timeout:
            return b"", "timeout"
        if failed:
            return b"", "network"
        return data, None


def _multipart(parameters: Mapping[str, Any]) -> tuple[bytes, str]:
    photo = parameters.get("photo")
    if not isinstance(photo, bytes):
        raise ValueError("photo upload must be bytes")
    boundary = f"mydrak-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in parameters.items():
        if name == "photo":
            continue
        if not isinstance(name, str) or not isinstance(value, (str, int)) or isinstance(value, bool):
            raise ValueError("multipart text field is invalid")
        chunks.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n"
            f"{value}\r\n".encode("utf-8")
        )
    photo_header = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"photo\"\r\n"
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("ascii")
    chunks.append(photo_header + photo + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"
