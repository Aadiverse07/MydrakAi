"""Telegram Bot API client with bounded validation and redacted credentials."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import os
from typing import Any, Protocol

from mydrak.telegram.updates import NormalizedTelegramUpdate, SkippedTelegramUpdate, parse_updates

MAX_PHOTO_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_FILE_DOWNLOAD_BYTES = 20 * 1024 * 1024


class TelegramClientError(RuntimeError):
    """Safe client failure; messages must not include request or response data."""


class TelegramApiError(TelegramClientError):
    """Telegram returned an ``ok: false`` wrapper; description is suppressed."""


class TelegramTimeoutError(TelegramClientError):
    """A Telegram HTTP operation timed out."""


class TelegramResponseError(TelegramClientError):
    """Telegram returned invalid JSON or an invalid response wrapper."""


@dataclass(frozen=True)
class TelegramFile:
    """Validated fields consumed from the documented Bot API File object."""

    file_path: str
    file_size: int | None


class TelegramTransport(Protocol):
    def call(self, method: str, parameters: Mapping[str, Any], *, timeout_s: float) -> Any: ...
    def download(self, file_path: str, *, max_bytes: int, timeout_s: float) -> bytes: ...


class TelegramClient:
    """Build documented method parameters and sanitize all transport failures."""

    def __init__(self, token: str, *, transport: TelegramTransport | None = None,
                 timeout_s: float = 30.0) -> None:
        if not isinstance(token, str) or not token.strip() or any(ch.isspace() for ch in token):
            raise TelegramClientError("Telegram bot token is missing or malformed")
        if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or timeout_s <= 0:
            raise TelegramClientError("Telegram timeout is invalid")
        if transport is None:
            from mydrak.telegram.http_transport import TelegramHttpTransport
            transport = TelegramHttpTransport(token)
        self._transport = transport
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
                    timeout: int = 25, allowed_updates: Sequence[str] | None = None
                    ) -> list[NormalizedTelegramUpdate | SkippedTelegramUpdate]:
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
            raise TelegramResponseError("Telegram getUpdates result is invalid")
        return parse_updates(result)

    def send_message(self, chat_id: int | str, text: str) -> Any:
        _validate_chat_id(chat_id)
        if not isinstance(text, str) or not 1 <= len(text) <= 4096:
            raise TelegramClientError("Telegram message text is outside the documented range")
        return self._call("sendMessage", {"chat_id": chat_id, "text": text})

    def send_photo(self, chat_id: int | str, photo: bytes | str, *, caption: str | None = None) -> Any:
        _validate_chat_id(chat_id)
        if not isinstance(photo, (bytes, str)) or not photo:
            raise TelegramClientError("Telegram photo input is invalid")
        if isinstance(photo, bytes) and len(photo) > MAX_PHOTO_UPLOAD_BYTES:
            raise TelegramClientError("Telegram photo exceeds the documented 10 MB limit")
        if isinstance(photo, str) and len(photo) > 4096:
            raise TelegramClientError("Telegram photo reference is too long")
        if caption is not None and (not isinstance(caption, str) or len(caption) > 1024):
            raise TelegramClientError("Telegram caption is outside the documented range")
        params: dict[str, Any] = {"chat_id": chat_id, "photo": photo}
        if caption is not None:
            params["caption"] = caption
        return self._call("sendPhoto", params)

    def get_file(self, file_id: str) -> TelegramFile:
        if not isinstance(file_id, str) or not file_id.strip() or len(file_id) > 4096:
            raise TelegramClientError("Telegram file identifier is invalid")
        result = self._call("getFile", {"file_id": file_id})
        if not isinstance(result, Mapping):
            raise TelegramResponseError("Telegram getFile result is invalid")
        file_id, unique_id = result.get("file_id"), result.get("file_unique_id")
        path = result.get("file_path")
        size = result.get("file_size")
        if (
            not isinstance(file_id, str) or not file_id.strip() or len(file_id) > 4096
            or not isinstance(unique_id, str) or not unique_id.strip() or len(unique_id) > 4096
            or not isinstance(path, str) or not path or len(path) > 1024
            or (size is not None and (type(size) is not int or not 1 <= size <= MAX_FILE_DOWNLOAD_BYTES))
        ):
            raise TelegramResponseError("Telegram file metadata is invalid")
        return TelegramFile(path, size)

    def download_file(self, file_path: str, *, max_bytes: int) -> bytes:
        if not isinstance(file_path, str) or not file_path or len(file_path) > 1024:
            raise TelegramClientError("Telegram file path is invalid")
        if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_FILE_DOWNLOAD_BYTES:
            raise TelegramClientError("Telegram download bound is invalid")
        failure: str | None = None
        data = b""
        try:
            data = self._transport.download(file_path, max_bytes=max_bytes, timeout_s=self._timeout_s)
        except TimeoutError:
            failure = "timeout"
        except TelegramTimeoutError:
            failure = "timeout"
        except Exception:
            failure = "download"
        if failure == "timeout":
            raise TelegramTimeoutError("Telegram file download timed out")
        if failure:
            raise TelegramClientError("Telegram file download failed")
        if not isinstance(data, bytes) or len(data) > max_bytes:
            raise TelegramResponseError("Telegram file download exceeded its bound")
        return data

    def _call(self, method: str, parameters: Mapping[str, Any]) -> Any:
        failure: str | None = None
        result: Any = None
        try:
            result = self._transport.call(method, dict(parameters), timeout_s=self._timeout_s)
        except TimeoutError:
            failure = "timeout"
        except TelegramTimeoutError:
            failure = "timeout"
        except TelegramApiError:
            failure = "api"
        except TelegramResponseError:
            failure = "response"
        except Exception:
            failure = "request"
        if failure == "timeout":
            raise TelegramTimeoutError("Telegram request timed out")
        if failure == "api":
            raise TelegramApiError("Telegram API returned an error")
        if failure == "response":
            raise TelegramResponseError("Telegram response is invalid")
        if failure:
            raise TelegramClientError("Telegram method call failed")
        return result


def _validate_chat_id(value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise TelegramClientError("Telegram chat identifier is invalid")
    if isinstance(value, str) and (not value.strip() or len(value) > 256):
        raise TelegramClientError("Telegram chat identifier is invalid")
