"""Sanitized internal update records parsed from the documented Bot API fields."""

from dataclasses import dataclass, field
from hashlib import sha256
from collections.abc import Mapping, Sequence
from typing import Any

MAX_DOCUMENTED_DOWNLOAD_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class NormalizedTelegramUpdate:
    """Normalized input shape used by offline runner tests only."""

    update_id: int
    chat_id: int | str = field(repr=False)
    user_id: int | str = field(repr=False)
    chat_type: str
    kind: str
    text: str | None = field(default=None, repr=False)
    photo_file_id: str | None = field(default=None, repr=False)
    photo_size: int | None = None


@dataclass(frozen=True)
class RunnerOutcome:
    status: str
    reason: str
    user_hash: str | None = None
    reply: str | None = None
    sent: bool = False


@dataclass(frozen=True)
class SkippedTelegramUpdate:
    """Malformed/unsupported update retained only to advance a safe poll offset."""

    update_id: int | None


def digest_id(namespace: str, value: str) -> str:
    """Hash a Telegram identifier before it enters local state or traces."""
    return sha256(f"mydrak-telegram-v1:{namespace}:{value}".encode("utf-8")).hexdigest()


def parse_updates(values: Sequence[Any]) -> list[NormalizedTelegramUpdate | SkippedTelegramUpdate]:
    """Normalize documented Update/Message fields; unknown fields are ignored."""
    parsed: list[NormalizedTelegramUpdate | SkippedTelegramUpdate] = []
    for raw in values:
        if isinstance(raw, NormalizedTelegramUpdate):
            parsed.append(raw)
            continue
        if not isinstance(raw, Mapping):
            parsed.append(SkippedTelegramUpdate(None))
            continue
        update_id = raw.get("update_id")
        if type(update_id) is not int or update_id < 0:
            parsed.append(SkippedTelegramUpdate(None))
            continue
        event_fields = ("message", "edited_message", "channel_post", "edited_channel_post", "callback_query")
        present = [key for key in event_fields if key in raw and raw[key] is not None]
        if len(present) != 1 or present[0] == "callback_query":
            parsed.append(SkippedTelegramUpdate(update_id))
            continue
        update = _parse_message(update_id, raw[present[0]])
        parsed.append(update if update is not None else SkippedTelegramUpdate(update_id))
    return parsed


def select_largest_photo(photo_sizes: Any) -> Mapping[str, Any] | None:
    """Select largest known-size PhotoSize that fits the documented download bound.

    ``file_size`` is optional in Telegram's object. Candidates without it are
    skipped so the runner can enforce public/photo byte bounds before fetching.
    """
    if not isinstance(photo_sizes, list):
        return None
    candidates: list[Mapping[str, Any]] = []
    for item in photo_sizes:
        if not isinstance(item, Mapping):
            continue
        file_id, width, height, size = (
            item.get("file_id"), item.get("width"), item.get("height"), item.get("file_size")
        )
        if (
            not isinstance(file_id, str) or not file_id.strip() or len(file_id) > 4096
            or not isinstance(item.get("file_unique_id"), str)
            or not item["file_unique_id"].strip() or len(item["file_unique_id"]) > 4096
            or type(width) is not int or width < 1
            or type(height) is not int or height < 1
            or type(size) is not int or not 1 <= size <= MAX_DOCUMENTED_DOWNLOAD_BYTES
        ):
            continue
        candidates.append(item)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item["width"] * item["height"])


def _parse_message(update_id: int, raw: Any) -> NormalizedTelegramUpdate | None:
    if not isinstance(raw, Mapping):
        return None
    if (
        type(raw.get("message_id")) is not int
        or type(raw.get("date")) is not int
    ):
        return None
    chat = raw.get("chat")
    sender = raw.get("from")
    if not isinstance(chat, Mapping) or not isinstance(sender, Mapping):
        return None
    chat_id, chat_type, user_id = chat.get("id"), chat.get("type"), sender.get("id")
    if (
        type(chat_id) is not int or not isinstance(chat_type, str)
        or type(user_id) is not int or type(sender.get("is_bot")) is not bool
        or not isinstance(sender.get("first_name"), str)
        or not _valid_optional_strings(
            chat, ("title", "username", "first_name", "last_name")
        )
        or not _valid_optional_strings(
            sender, ("last_name", "username", "language_code")
        )
        or ("caption" in raw and not isinstance(raw["caption"], str))
    ):
        return None
    if "photo" in raw:
        selected = select_largest_photo(raw.get("photo"))
        if selected is None:
            return None
        return NormalizedTelegramUpdate(
            update_id, chat_id, user_id, chat_type, "photo", None,
            selected["file_id"], selected["file_size"],
        )
    text = raw.get("text")
    if isinstance(text, str):
        if len(text) > 4096 or not text.strip():
            return None
        kind = "command" if text.startswith("/") and len(text) <= 128 else "text"
        if text.startswith("/") and len(text) > 128:
            return None
        return NormalizedTelegramUpdate(update_id, chat_id, user_id, chat_type, kind, text)
    if "text" in raw:
        return None
    return NormalizedTelegramUpdate(update_id, chat_id, user_id, chat_type, "other")


def _valid_optional_strings(value: Mapping[str, Any], names: tuple[str, ...]) -> bool:
    return all(name not in value or isinstance(value[name], str) for name in names)


def valid_normalized_update(update: NormalizedTelegramUpdate) -> bool:
    if (
        type(update.update_id) is not int or update.update_id < 0
        or type(update.chat_id) not in (str, int)
        or type(update.user_id) not in (str, int)
        or len(str(update.chat_id)) > 256 or not str(update.chat_id).strip()
        or len(str(update.user_id)) > 256 or not str(update.user_id).strip()
        or not isinstance(update.chat_type, str)
        or update.chat_type not in {"private", "group", "supergroup", "channel"}
        or not isinstance(update.kind, str)
        or update.kind not in {"command", "photo", "text", "other"}
        or (update.text is not None and (not isinstance(update.text, str) or len(update.text) > 4096))
        or (update.photo_file_id is not None and (
            not isinstance(update.photo_file_id, str) or not 0 < len(update.photo_file_id) <= 4096
        ))
        or (update.photo_size is not None and type(update.photo_size) is not int)
    ):
        return False
    if update.kind == "command":
        return isinstance(update.text, str) and update.text.startswith("/") and len(update.text) <= 128
    if update.kind == "text":
        return isinstance(update.text, str) and bool(update.text.strip())
    if update.kind == "photo":
        return update.photo_size is not None and update.photo_size > 0
    return True
