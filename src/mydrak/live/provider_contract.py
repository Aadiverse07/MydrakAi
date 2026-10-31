"""Small parsers for the user-supplied chat-completions example envelopes."""

from __future__ import annotations

from collections.abc import Collection, Mapping
import json
from typing import Any
from urllib.parse import urlsplit


def parse_chat_response(raw: bytes, *, max_bytes: int) -> tuple[str, int | None, int | None]:
    if not isinstance(raw, bytes) or len(raw) > max_bytes:
        raise ValueError
    document = json.loads(raw.decode("utf-8"))
    choices = document["choices"]
    if not isinstance(choices, list) or not choices:
        raise ValueError
    content = choices[0]["message"]["content"]
    if not isinstance(content, str):
        raise ValueError
    usage = document.get("usage")
    return content, _usage_count(usage, "prompt_tokens"), _usage_count(usage, "completion_tokens")


def chat_completions_url(endpoint: Any) -> str:
    value = require_text(endpoint, "endpoint")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or parsed.path not in {"", "/", "/v1"}):
        raise ValueError("provider endpoint is malformed")
    return value.rstrip("/") + "/chat/completions"


def require_text(value: Any, name: str) -> str:
    if (not isinstance(value, str) or not value.strip() or value != value.strip()
            or "TODO" in value.upper()):
        raise ValueError(f"provider {name} is missing or unresolved")
    return value


def validate_vocabulary(values: Collection[str], name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Collection):
        raise ValueError(f"{name} vocabulary is invalid")
    result = tuple(values)
    if any(not isinstance(value, str) or not value.strip() for value in result):
        raise ValueError(f"{name} vocabulary is invalid")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} vocabulary contains duplicates")
    return result


def _usage_count(usage: Any, field: str) -> int | None:
    value = usage.get(field) if isinstance(usage, Mapping) else None
    return value if type(value) is int and value >= 0 else None
