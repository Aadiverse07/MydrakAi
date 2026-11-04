"""Fail-closed configuration and provenance checks for local draft preview."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from mydrak.kb.loader import load_disease_card
from mydrak.util.config import load_yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "config" / "reply.yaml"
KB_CARDS_PATH = REPO_ROOT / "kb" / "cards"
DRAFT_BANNER = (
    "DEMO DRAFT: not reviewed by an agronomist. "
    "Do not use for real farming decisions."
)


def load_demo_draft_preview(path: str | Path | None = None) -> bool:
    """Load the local reply settings; absent safety switches default off."""
    try:
        values = load_yaml(path or CONFIG_PATH)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError):
        raise ValueError("reply configuration is missing or invalid") from None
    allowed = {
        "demo_draft_preview", "consent_notice_approved", "allow_private_upload",
        "private_tier1_allowed",
    }
    if not isinstance(values, Mapping) or set(values) - allowed:
        raise ValueError("reply config has unknown fields")
    for key, value in values.items():
        if type(value) is not bool:
            raise ValueError(f"reply config field {key} must be boolean")
    return values.get("demo_draft_preview", False)


def load_private_photo_settings(path: str | Path | None = None) -> dict[str, bool]:
    """Read opt-in private-photo controls; all omissions resolve to false."""
    try:
        values = load_yaml(path or CONFIG_PATH)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError):
        raise ValueError("reply configuration is missing or invalid") from None
    allowed = {
        "demo_draft_preview", "consent_notice_approved", "allow_private_upload",
        "private_tier1_allowed",
    }
    if not isinstance(values, Mapping) or set(values) - allowed:
        raise ValueError("reply config has unknown fields")
    if any(type(value) is not bool for value in values.values()):
        raise ValueError("reply config switches must be boolean")
    return {
        "consent_notice_approved": values.get("consent_notice_approved", False),
        "allow_private_upload": values.get("allow_private_upload", False),
        "private_tier1_allowed": values.get("private_tier1_allowed", False),
    }


def resolve_preview_enabled(enabled: object, *, public_mode: object) -> bool:
    if type(public_mode) is not bool:
        raise ValueError("public mode flag is invalid")
    if enabled is None:
        enabled = load_demo_draft_preview()
    if type(enabled) is not bool:
        raise ValueError("demo_draft_preview must be boolean")
    if enabled and public_mode:
        raise ValueError("demo draft preview is refused in public mode")
    return enabled


def approved_for_farmer(card: Mapping[str, Any]) -> bool:
    review = card.get("review_status")
    return (
        card.get("status") == "verified"
        and isinstance(review, Mapping)
        and review.get("en") == "REVIEWED"
        and review.get("hi") == "REVIEWED"
    )


def draft_preview_banner(
    card: Mapping[str, Any], *, action: str, language: str,
    enabled: bool, card_path: str | Path | None,
) -> str | None:
    """Return the banner only for an unchanged, real draft under ``kb/cards``."""
    if approved_for_farmer(card):
        return None
    if not enabled or action not in {"answer", "ask"}:
        raise ValueError("KB card is not approved for farmer-facing replies")
    review = card.get("review_status")
    if language == "hi" and (not isinstance(review, Mapping) or review.get("hi") != "REVIEWED"):
        raise ValueError("Hindi card content is not reviewed")
    if language != "en":
        raise ValueError("draft preview is English-only; Hindi remains review-gated")
    if card.get("status") != "draft":
        raise ValueError("only draft cards may use draft preview")
    if card.get("id") == "SYNTHETIC_TEST" or not isinstance(card_path, (str, Path)):
        raise ValueError("draft preview requires a genuine card from kb/cards")
    source = Path(card_path).resolve()
    cards_root = KB_CARDS_PATH.resolve()
    if not source.is_relative_to(cards_root) or not source.is_file():
        raise ValueError("draft preview requires a genuine card from kb/cards")
    try:
        persisted = load_disease_card(source)
    except (OSError, UnicodeError, ValueError):
        raise ValueError("draft preview card failed KB validation") from None
    if dict(card) != persisted:
        raise ValueError("draft preview card differs from its validated KB file")
    return DRAFT_BANNER
