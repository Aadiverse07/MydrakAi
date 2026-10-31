"""Sanitized project-local update record; not the raw Bot API schema."""

from dataclasses import dataclass, field
from hashlib import sha256


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


def digest_id(namespace: str, value: str) -> str:
    """Hash a Telegram identifier before it enters local state or traces."""
    return sha256(f"mydrak-telegram-v1:{namespace}:{value}".encode("utf-8")).hexdigest()


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
