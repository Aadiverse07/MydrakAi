"""Offline-testable Telegram method boundary.

The repository's provider excerpt lists method fields but omits HTTP request
encoding and nested response schemas. The default transport therefore refuses
wire dispatch; injected tests can exercise the documented method contract.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import os
from typing import Any, Protocol


class TelegramClientError(RuntimeError):
    """Sanitized Telegram client error; never contains token or response text."""


class TelegramContractUnverified(TelegramClientError):
    """Wire serialization is blocked pending documented request/response shapes."""


@dataclass(frozen=True)
class TelegramFile:
    """Project-local normalized File supplied by offline tests only.

    Mapping the Bot API File object is TODO(verify): the provided excerpt does
    not document its response fields or envelope.
    """

    file_path: str
    file_size: int


class TelegramTransport(Protocol):
    def call(self, method: str, parameters: Mapping[str, Any], *, timeout_s: float) -> Any: ...
    def download(self, file_path: str, *, max_bytes: int, timeout_s: float) -> bytes: ...


class UnverifiedTelegramTransport:
    """Fail-closed default; it never opens a socket."""

    def call(self, method: str, parameters: Mapping[str, Any], *, timeout_s: float) -> Any:
        raise TelegramContractUnverified(
            "TODO(verify): Telegram HTTP method, body encoding, and response envelope are undocumented"
        )

    def download(self, file_path: str, *, max_bytes: int, timeout_s: float) -> bytes:
        raise TelegramContractUnverified(
            "TODO(verify): Telegram File response schema and download transport are undocumented"
        )


class TelegramClient:
    """Build documented Telegram method parameters without exposing its token."""

    def __init__(self, token: str, *, transport: TelegramTransport | None = None,
                 timeout_s: float = 30.0) -> None:
        if not isinstance(token, str) or not token.strip() or any(ch.isspace() for ch in token):
            raise TelegramClientError("Telegram bot token is missing or malformed")
        if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or timeout_s <= 0:
            raise TelegramClientError("Telegram timeout is invalid")
        # The provider excerpt does not document authenticated wire
        # serialization, so this boundary validates but never retains the
        # credential. The fail-closed default cannot dispatch requests.
        self._transport = transport or UnverifiedTelegramTransport()
        self._timeout_s = float(timeout_s)

    @classmethod
    def from_environment(cls, *, transport: TelegramTransport | None = None,
                         environ: Mapping[str, str] | None = None,
                         timeout_s: float = 30.0) -> TelegramClient:
        values = os.environ if environ is None else environ
        token = values.get("TELEGRAM_BOT_TOKEN")
        if not isinstance(token, str) or not token:
            raise TelegramClientError("TELEGRAM_BOT_TOKEN is required")
        return cls(token, transport=transport, timeout_s=timeout_s)

    def __repr__(self) -> str:
        return "TelegramClient(token=<redacted>)"

    def get_updates(self, *, offset: int | None = None, limit: int = 100,
                    timeout: int = 25, allowed_updates: Sequence[str] | None = None) -> list[Any]:
        if offset is not None and (type(offset) is not int or offset < 0):
            raise TelegramClientError("Telegram update offset is invalid")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise TelegramClientError("Telegram update limit is outside the documented range")
        if type(timeout) is not int or timeout < 0:
            raise TelegramClientError("Telegram polling timeout is invalid")
        params: dict[str, Any] = {"limit": limit, "timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        if allowed_updates is not None:
            if not isinstance(allowed_updates, Sequence) or isinstance(allowed_updates, (str, bytes)):
                raise TelegramClientError("allowed_updates must be a sequence")
            if any(not isinstance(item, str) or not item for item in allowed_updates):
                raise TelegramClientError("allowed_updates contains an invalid value")
            params["allowed_updates"] = list(allowed_updates)
        result = self._call("getUpdates", params)
        if not isinstance(result, list):
            raise TelegramContractUnverified("TODO(verify): getUpdates response envelope/schema is not recorded")
        return result

    def send_message(self, chat_id: int | str, text: str) -> Any:
        _validate_chat_id(chat_id)
        if not isinstance(text, str) or not 1 <= len(text) <= 4096:
            raise TelegramClientError("Telegram message text is outside the documented range")
        return self._call("sendMessage", {"chat_id": chat_id, "text": text})

    def send_photo(self, chat_id: int | str, photo: bytes | str, *, caption: str | None = None) -> Any:
        _validate_chat_id(chat_id)
        if not isinstance(photo, (bytes, str)) or not photo:
            raise TelegramClientError("Telegram photo input is invalid")
        if isinstance(photo, bytes) and len(photo) > 10 * 1024 * 1024:
            raise TelegramClientError("Telegram photo exceeds the documented 10 MB limit")
        if isinstance(photo, str) and len(photo) > 4096:
            raise TelegramClientError("Telegram photo reference is too long")
        if caption is not None and (not isinstance(caption, str) or len(caption) > 1024):
            raise TelegramClientError("Telegram caption is outside the documented range")
        params: dict[str, Any] = {"chat_id": chat_id, "photo": photo}
        if caption is not None:
            params["caption"] = caption
        return self._call("sendPhoto", params)

    def get_file(self, file_id: str) -> Any:
        if not isinstance(file_id, str) or not file_id.strip() or len(file_id) > 4096:
            raise TelegramClientError("Telegram file identifier is invalid")
        result = self._call("getFile", {"file_id": file_id})
        if type(result) is not TelegramFile:
            raise TelegramContractUnverified(
                "TODO(verify): getFile response envelope and File field mapping are not recorded"
            )
        if (
            not isinstance(result.file_path, str) or not result.file_path
            or len(result.file_path) > 1024
            or type(result.file_size) is not int or not 1 <= result.file_size <= 20 * 1024 * 1024
        ):
            raise TelegramClientError("Telegram file metadata is invalid")
        return result

    def download_file(self, file_path: str, *, max_bytes: int) -> bytes:
        if not isinstance(file_path, str) or not file_path or len(file_path) > 1024:
            raise TelegramClientError("Telegram file path is invalid")
        if type(max_bytes) is not int or not 1 <= max_bytes <= 20 * 1024 * 1024:
            raise TelegramClientError("Telegram download bound is invalid")
        try:
            data = self._transport.download(file_path, max_bytes=max_bytes, timeout_s=self._timeout_s)
        except TelegramClientError:
            raise
        except Exception:
            raise TelegramClientError("Telegram file download failed") from None
        if not isinstance(data, bytes) or len(data) > max_bytes:
            raise TelegramClientError("Telegram file download exceeded its bound")
        return data

    def _call(self, method: str, parameters: Mapping[str, Any]) -> Any:
        try:
            return self._transport.call(method, dict(parameters), timeout_s=self._timeout_s)
        except TelegramClientError:
            raise
        except Exception:
            raise TelegramClientError("Telegram method call failed") from None


def _validate_chat_id(value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise TelegramClientError("Telegram chat identifier is invalid")
    if isinstance(value, str) and (not value.strip() or len(value) > 256):
        raise TelegramClientError("Telegram chat identifier is invalid")
