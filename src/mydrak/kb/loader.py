"""Load safety cards and validate source-traceable B6 disease-card records."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

SAFETY_REQUIRED_KEYS = ("id", "safety_line", "referral_text", "retake_text")
DISEASE_REQUIRED_KEYS = (
    "id", "crop", "names", "symptoms", "confusable_with",
    "follow_up_questions", "low_risk_steps", "chemical_options",
    "when_to_refer", "sources", "reviewed_by", "status", "region_tags",
    "claim_sources", "review_status", "language_reviewers",
)
SOURCE_FIELDS = {
    "id", "title", "publisher", "region_tag", "tier", "local_path",
    "retrieved", "verified_by_user", "notes",
}
_LANGUAGES = ("en", "hi")
_REGIONS = {"national", "MP", "Punjab", "Tamil Nadu"}
_TIERS = {"primary", "supplementary", "cross-check", "gap"}
_STATUS = {"draft", "verified"}
_REVIEW_STATUS = {"UNREVIEWED", "REVIEWED"}
_DOSAGE_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|g|kg|ml|mL|l|L|ppm|percent)\b|"
    r"\b\d+(?:\.\d+)?\s*%|"
    r"\b\d+\s*:\s*\d+\b",
    re.IGNORECASE,
)
_MIXING_PATTERN = re.compile(
    r"\b(?:dose|dosage|mix|mixing|mixture|tank\s+mix)\b", re.IGNORECASE
)
_REGISTRY_PATH = Path(__file__).resolve().parents[3] / "kb" / "sources.yaml"


def _nonempty_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")


def _localized(card: dict, field: str, *, list_values: bool) -> None:
    value = card[field]
    if not isinstance(value, dict) or set(value) != set(_LANGUAGES):
        raise ValueError(f"{field} must contain en and hi")
    for language in _LANGUAGES:
        item = value[language]
        if list_values:
            if not isinstance(item, list) or not item:
                raise ValueError(f"{field}.{language} must be a nonempty list")
            for index, text in enumerate(item):
                _nonempty_text(text, f"{field}.{language}[{index}]")
        else:
            _nonempty_text(item, f"{field}.{language}")


def validate_source_registry(registry: object) -> dict[str, dict]:
    """Validate the project-local registry and return entries keyed by ID."""
    if isinstance(registry, dict):
        entries = list(registry.values())
        if any(not isinstance(entry, dict) or registry.get(entry.get("id")) != entry for entry in entries):
            raise ValueError("source registry mapping keys must match entry IDs")
    elif isinstance(registry, list):
        entries = registry
    else:
        raise ValueError("source registry must be a list or validated ID mapping")
    indexed: dict[str, dict] = {}
    for index, entry in enumerate(entries):
        field = f"source registry[{index}]"
        if not isinstance(entry, dict) or set(entry) != SOURCE_FIELDS:
            raise ValueError(f"{field} has missing or unknown fields")
        for key in ("id", "title", "publisher", "notes"):
            _nonempty_text(entry[key], f"{field}.{key}")
        if entry["id"] in indexed:
            raise ValueError(f"duplicate source id: {entry['id']}")
        if not isinstance(entry["region_tag"], str) or entry["region_tag"] not in _REGIONS:
            raise ValueError(f"{field}.region_tag is invalid")
        if not isinstance(entry["tier"], str) or entry["tier"] not in _TIERS:
            raise ValueError(f"{field}.tier is invalid")
        if entry["local_path"] is not None and not isinstance(entry["local_path"], str):
            raise ValueError(f"{field}.local_path must be text or null")
        for flag in ("retrieved", "verified_by_user"):
            if type(entry[flag]) is not bool:
                raise ValueError(f"{field}.{flag} must be boolean")
        indexed[entry["id"]] = entry
    return indexed


def load_source_registry(path: str | Path | None = None) -> dict[str, dict]:
    """Load and validate the local source registry; no network access is used."""
    registry_path = Path(path) if path is not None else _REGISTRY_PATH
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    return validate_source_registry(data)


def _claim_paths(card: dict) -> set[str]:
    paths = {"names.en", "names.hi", "when_to_refer"}
    paths.update(f"symptoms[{i}]" for i in range(len(card["symptoms"])))
    paths.update(f"confusable_with[{i}]" for i in range(len(card["confusable_with"])))
    for i, question in enumerate(card["follow_up_questions"]):
        paths.update((f"follow_up_questions[{i}].en", f"follow_up_questions[{i}].hi"))
    for language in _LANGUAGES:
        paths.update(
            f"low_risk_steps.{language}[{i}]"
            for i in range(len(card["low_risk_steps"][language]))
        )
    paths.update(f"chemical_options[{i}].text" for i in range(len(card["chemical_options"])))
    return paths


def _treatment_text_is_bounded(text: str, field: str) -> None:
    if _DOSAGE_PATTERN.search(text) or _MIXING_PATTERN.search(text):
        raise ValueError(f"{field} contains a dosage or mixing pattern")


def validate_disease_card(
    card: object,
    *,
    registry: object | None = None,
    allow_synthetic_test: bool = False,
) -> dict:
    """Validate a card against the project-local schema and source registry.

    The registry fields, claim-path references, review metadata and treatment
    text checks are project-local safeguards layered on top of B6. They do not
    establish factual accuracy, source quality, or reviewer qualifications.
    ``allow_synthetic_test`` is for the single test fixture only; production
    loading always rejects that marker.
    """
    if not isinstance(card, dict):
        raise ValueError("disease card must be a mapping")
    allowed = set(DISEASE_REQUIRED_KEYS) | {"test_only"}
    unknown = set(card) - allowed
    missing = set(DISEASE_REQUIRED_KEYS) - set(card)
    if missing or unknown:
        raise ValueError(f"disease card schema mismatch; missing={sorted(missing)}, unknown={sorted(unknown)}")
    synthetic = card.get("test_only") is True
    if "test_only" in card and not synthetic:
        raise ValueError("test_only must be true when present")
    if card["id"] == "SYNTHETIC_TEST" and not (allow_synthetic_test and synthetic):
        raise ValueError("SYNTHETIC_TEST card is not loadable as production content")
    if synthetic and (not allow_synthetic_test or card["id"] != "SYNTHETIC_TEST"):
        raise ValueError("synthetic test card is not loadable as production content")
    if allow_synthetic_test and not synthetic:
        raise ValueError("synthetic validation is limited to the marked test fixture")

    _nonempty_text(card["id"], "id")
    _nonempty_text(card["crop"], "crop")
    if not isinstance(card["status"], str) or card["status"] not in _STATUS:
        raise ValueError("status must be draft or verified")
    _localized(card, "names", list_values=False)
    _localized(card, "low_risk_steps", list_values=True)

    for field in ("symptoms", "confusable_with", "sources"):
        values = card[field]
        if not isinstance(values, list):
            raise ValueError(f"{field} must be a list")
        if field != "confusable_with" and not values:
            raise ValueError(f"{field} must not be empty")
        for index, value in enumerate(values):
            _nonempty_text(value, f"{field}[{index}]")

    if not isinstance(card["region_tags"], list) or not card["region_tags"]:
        raise ValueError("region_tags must be a nonempty list")
    if any(not isinstance(tag, str) or tag not in _REGIONS for tag in card["region_tags"]):
        raise ValueError("region_tags contains an invalid region")

    questions = card["follow_up_questions"]
    if not isinstance(questions, list) or not questions:
        raise ValueError("follow_up_questions must be a nonempty list")
    question_ids: set[str] = set()
    for index, question in enumerate(questions):
        field = f"follow_up_questions[{index}]"
        if not isinstance(question, dict) or set(question) != {"id", "en", "hi"}:
            raise ValueError(f"{field} must contain id, en, and hi")
        for key in ("id", "en", "hi"):
            _nonempty_text(question[key], f"{field}.{key}")
        if question["id"] in question_ids:
            raise ValueError(f"{field}.id must be unique")
        question_ids.add(question["id"])

    chemicals = card["chemical_options"]
    if not isinstance(chemicals, list):
        raise ValueError("chemical_options must be a list")
    for index, option in enumerate(chemicals):
        field = f"chemical_options[{index}]"
        if not isinstance(option, dict) or set(option) != {"text", "source", "label_instruction"}:
            raise ValueError(f"{field} must contain text, source, and label_instruction")
        for key in ("text", "source", "label_instruction"):
            _nonempty_text(option[key], f"{field}.{key}")
        if "follow the product label" not in option["label_instruction"].casefold():
            raise ValueError(f"{field}.label_instruction must say to follow the product label")
        _treatment_text_is_bounded(option["text"], f"{field}.text")
        _treatment_text_is_bounded(option["label_instruction"], f"{field}.label_instruction")

    for language in _LANGUAGES:
        for index, text in enumerate(card["low_risk_steps"][language]):
            _treatment_text_is_bounded(text, f"low_risk_steps.{language}[{index}]")

    _nonempty_text(card["when_to_refer"], "when_to_refer")
    if card["reviewed_by"] is not None and (
        not isinstance(card["reviewed_by"], str) or not card["reviewed_by"].strip()
    ):
        raise ValueError("reviewed_by must be nonempty text or null")
    review_status = card["review_status"]
    if not isinstance(review_status, dict) or set(review_status) != set(_LANGUAGES):
        raise ValueError("review_status must contain en and hi")
    if any(not isinstance(value, str) or value not in _REVIEW_STATUS for value in review_status.values()):
        raise ValueError("review_status values must be UNREVIEWED or REVIEWED")
    reviewers = card["language_reviewers"]
    if not isinstance(reviewers, dict) or set(reviewers) != set(_LANGUAGES):
        raise ValueError("language_reviewers must contain en and hi")
    for language, reviewer in reviewers.items():
        if reviewer is not None and (not isinstance(reviewer, str) or not reviewer.strip()):
            raise ValueError(f"language_reviewers.{language} must be nonempty text or null")
        if review_status[language] == "REVIEWED" and reviewer is None:
            raise ValueError(f"language_reviewers.{language} is required when marked REVIEWED")

    refs = card["claim_sources"]
    if not isinstance(refs, list) or not refs:
        raise ValueError("claim_sources must be a nonempty list")
    covered: set[str] = set()
    for index, ref in enumerate(refs):
        field = f"claim_sources[{index}]"
        if not isinstance(ref, dict) or set(ref) != {"claim", "source_id", "page", "section"}:
            raise ValueError(f"{field} must contain claim, source_id, page, and section")
        for key in ("claim", "source_id", "page", "section"):
            _nonempty_text(ref[key], f"{field}.{key}")
        if ref["claim"] in covered:
            raise ValueError(f"duplicate claim reference: {ref['claim']}")
        covered.add(ref["claim"])
    expected_claims = _claim_paths(card)
    if covered != expected_claims:
        raise ValueError(
            f"claim source coverage mismatch; missing={sorted(expected_claims - covered)}, "
            f"unknown={sorted(covered - expected_claims)}"
        )

    source_ids = set(card["sources"])
    if len(source_ids) != len(card["sources"]):
        raise ValueError("sources must not contain duplicate source IDs")
    if source_ids != {ref["source_id"] for ref in refs}:
        raise ValueError("sources must match source IDs used by claim_sources")
    for option_index, option in enumerate(chemicals):
        ref = next(ref for ref in refs if ref["claim"] == f"chemical_options[{option_index}].text")
        if option["source"] != ref["source_id"]:
            raise ValueError(f"chemical_options[{option_index}] source must match its claim citation")

    indexed_registry = validate_source_registry(registry) if registry is not None else load_source_registry()
    for source_id in source_ids:
        if source_id not in indexed_registry:
            raise ValueError(f"unknown source_id: {source_id}")
    if not synthetic:
        for ref in refs:
            source = indexed_registry[ref["source_id"]]
            if source["tier"] in {"cross-check", "gap"}:
                raise ValueError(f"source {source['id']} tier is not citable")
            if not source["retrieved"]:
                raise ValueError(f"source {source['id']} is not retrieved")
            if source["tier"] == "supplementary" and source["region_tag"] not in card["region_tags"]:
                raise ValueError(f"card must show supplementary source region {source['region_tag']}")
        if card["status"] == "verified":
            if any(value != "REVIEWED" for value in review_status.values()):
                raise ValueError("verified card cannot contain an UNREVIEWED language")
            if card["reviewed_by"] is None or any(value is None for value in reviewers.values()):
                raise ValueError("verified card requires confirmed reviewer fields")
            if any(not indexed_registry[source_id]["verified_by_user"] for source_id in source_ids):
                raise ValueError("verified card requires user-verified cited sources")
    return card


def load_card(path: str | Path) -> dict:
    """Load one YAML mapping without applying a disease-card schema."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"card {path} must contain a mapping")
    return data


def load_safety_card(path: str | Path) -> dict:
    """Load the general safety card, preserving its independent contract."""
    card = load_card(path)
    missing = [key for key in SAFETY_REQUIRED_KEYS if not card.get(key)]
    if missing:
        raise ValueError(f"safety card {path} missing keys: {missing}")
    return card


def load_disease_card(path: str | Path, *, registry_path: str | Path | None = None) -> dict:
    """Load a production disease card; synthetic fixtures are always rejected."""
    registry = load_source_registry(registry_path) if registry_path else None
    return validate_disease_card(load_card(path), registry=registry)
