"""Load the general safety card and validate B6 disease-card records."""

from pathlib import Path

import yaml

SAFETY_REQUIRED_KEYS = ("id", "safety_line", "referral_text", "retake_text")
DISEASE_REQUIRED_KEYS = (
    "id",
    "crop",
    "names",
    "symptoms",
    "confusable_with",
    "follow_up_questions",
    "low_risk_steps",
    "chemical_options",
    "when_to_refer",
    "sources",
    "reviewed_by",
)
_LANGUAGES = ("en", "hi")


def _nonempty_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"disease card field {field} must be nonempty text")


def _localized(card: dict, field: str, *, list_values: bool) -> None:
    value = card[field]
    if not isinstance(value, dict) or set(value) != set(_LANGUAGES):
        raise ValueError(f"disease card field {field} must contain en and hi")
    for language in _LANGUAGES:
        item = value[language]
        if list_values:
            if not isinstance(item, list) or not item:
                raise ValueError(
                    f"disease card field {field}.{language} must be a nonempty list"
                )
            for index, text in enumerate(item):
                _nonempty_text(text, f"{field}.{language}[{index}]")
        else:
            _nonempty_text(item, f"{field}.{language}")


def validate_disease_card(card: object) -> dict:
    """Validate a B6 disease-card mapping and return it unchanged.

    B6 gives no field names for a non-empty chemical option. This local
    minimum requires ``text``, ``source``, and ``label_instruction`` strings;
    it validates shape only, not citation quality or safety.
    """
    if not isinstance(card, dict):
        raise ValueError("disease card must be a mapping")
    missing = [key for key in DISEASE_REQUIRED_KEYS if key not in card]
    if missing:
        raise ValueError(f"disease card missing required fields: {missing}")

    _nonempty_text(card["id"], "id")
    _nonempty_text(card["crop"], "crop")
    _localized(card, "names", list_values=False)
    _localized(card, "low_risk_steps", list_values=True)

    for field in ("symptoms", "confusable_with", "sources"):
        values = card[field]
        if not isinstance(values, list):
            raise ValueError(f"disease card field {field} must be a list")
        if field != "confusable_with" and not values:
            raise ValueError(f"disease card field {field} must not be empty")
        for index, value in enumerate(values):
            _nonempty_text(value, f"{field}[{index}]")

    questions = card["follow_up_questions"]
    if not isinstance(questions, list) or not questions:
        raise ValueError("disease card field follow_up_questions must be a nonempty list")
    question_ids: set[str] = set()
    for index, question in enumerate(questions):
        field = f"follow_up_questions[{index}]"
        if not isinstance(question, dict) or set(question) != {"id", "en", "hi"}:
            raise ValueError(f"disease card {field} must contain id, en, and hi")
        for key in ("id", "en", "hi"):
            _nonempty_text(question[key], f"{field}.{key}")
        if question["id"] in question_ids:
            raise ValueError(f"disease card {field}.id must be unique")
        question_ids.add(question["id"])

    chemicals = card["chemical_options"]
    if not isinstance(chemicals, list):
        raise ValueError("disease card field chemical_options must be a list")
    for index, option in enumerate(chemicals):
        field = f"chemical_options[{index}]"
        if not isinstance(option, dict):
            raise ValueError(f"disease card {field} must be a mapping")
        for key in ("text", "source", "label_instruction"):
            if key not in option:
                raise ValueError(f"disease card {field} missing {key}")
            _nonempty_text(option[key], f"{field}.{key}")

    _nonempty_text(card["when_to_refer"], "when_to_refer")
    _nonempty_text(card["reviewed_by"], "reviewed_by")
    return card


def load_card(path: str | Path) -> dict:
    """Load one card file and return its mapping (no schema beyond mapping)."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"card {path} must contain a mapping")
    return data


def load_safety_card(path: str | Path) -> dict:
    """Load the general safety card, requiring its safety/referral lines."""
    card = load_card(path)
    missing = [k for k in SAFETY_REQUIRED_KEYS if not card.get(k)]
    if missing:
        raise ValueError(f"safety card {path} missing keys: {missing}")
    return card


def load_disease_card(path: str | Path) -> dict:
    """Load one YAML disease card and validate its B6 structure."""
    return validate_disease_card(load_card(path))
