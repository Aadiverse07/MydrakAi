"""Offline validation and bounded repair for the master B8 diagnosis schema.

Provider access is only an injected protocol. This module has no default
provider, client, network path, policy action, or treatment output.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
import json
import math
from numbers import Real
from typing import Protocol, runtime_checkable

MAX_DIAGNOSIS_OUTPUT_CHARS = 65_536  # Project-local defensive parsing bound.
REPAIR_ATTEMPTS = 1  # Master B8/B11: one repair for invalid model JSON.
_REQUIRED_FIELDS = frozenset({
    "plant_visible", "crop", "issue", "alternatives", "symptoms_observed",
    "image_issues", "stated_confidence", "segment_prompts",
})
_UNKNOWN = "unknown"
_EXPLICIT_CONFIDENCE_EXAMPLE = "medium"


class DiagnosisStatus(StrEnum):
    VALID = "valid"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class DiagnosisOutput:
    """Schema-validated model claims; never contains policy or treatment fields."""

    plant_visible: bool
    crop: str
    issue: str
    alternatives: tuple[str, ...]
    symptoms_observed: tuple[str, ...]
    image_issues: tuple[str, ...]
    stated_confidence: float | str
    segment_prompts: tuple[str, ...]


@dataclass(frozen=True)
class DiagnosisResult:
    status: DiagnosisStatus
    output: DiagnosisOutput | None
    reason: str
    repair_attempts: int = 0


@runtime_checkable
class DiagnosisProvider(Protocol):
    """Injected offline-testable boundary; no concrete provider is supplied."""

    def generate(self) -> object:
        """Return a raw structured-output string or an invalid provider value."""

    def repair(self, invalid_output: str) -> object:
        """Return one repaired raw output; called at most once per run."""


class _DuplicateKey(ValueError):
    pass


def _object_without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError("non-standard JSON constant")


def _valid_vocabulary(values: Collection[str], *, field: str) -> frozenset[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Collection):
        raise ValueError(f"{field} vocabulary is invalid")
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise ValueError(f"{field} vocabulary is invalid")
    normalized = frozenset(item.strip() for item in values)
    if len(normalized) != len(values) or _UNKNOWN in normalized:
        raise ValueError(f"{field} vocabulary is ambiguous")
    return normalized


def _text_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    result = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field} contains invalid text")
        result.append(item.strip())
    if len(set(result)) != len(result):
        raise ValueError(f"{field} contains duplicates")
    return tuple(result)


def validate_diagnosis_json(
    raw: object,
    *,
    supported_crops: Collection[str],
    disease_ids: Collection[str],
) -> DiagnosisOutput:
    """Parse and validate the exact B8 object; errors never include raw output."""
    crops = _valid_vocabulary(supported_crops, field="crop")
    diseases = _valid_vocabulary(disease_ids, field="disease")
    if not isinstance(raw, str) or len(raw) > MAX_DIAGNOSIS_OUTPUT_CHARS:
        raise ValueError("diagnosis output is unavailable or exceeds the local limit")
    try:
        data = json.loads(
            raw,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, _DuplicateKey, ValueError, RecursionError):
        raise ValueError("diagnosis output is not valid JSON") from None
    if not isinstance(data, dict) or set(data) != _REQUIRED_FIELDS:
        raise ValueError("diagnosis output does not match the B8 fields")

    plant_visible = data["plant_visible"]
    if type(plant_visible) is not bool:
        raise ValueError("plant_visible must be boolean")
    crop = data["crop"]
    issue = data["issue"]
    if not isinstance(crop, str) or crop not in crops | {_UNKNOWN}:
        raise ValueError("crop is outside the configured vocabulary")
    if not isinstance(issue, str) or issue not in diseases | {_UNKNOWN}:
        raise ValueError("issue is outside the configured vocabulary")
    if not plant_visible and (crop != _UNKNOWN or issue != _UNKNOWN):
        raise ValueError("non-plant output must not assert a crop or issue")

    alternatives = _text_list(data["alternatives"], "alternatives")
    if any(item not in diseases for item in alternatives):
        raise ValueError("alternative is outside the configured disease IDs")
    symptoms = _text_list(data["symptoms_observed"], "symptoms_observed")
    image_issues = _text_list(data["image_issues"], "image_issues")
    segment_prompts = _text_list(data["segment_prompts"], "segment_prompts")
    if not plant_visible and (alternatives or symptoms or segment_prompts):
        raise ValueError("non-plant output must not assert plant symptoms or prompts")

    confidence = data["stated_confidence"]
    if isinstance(confidence, bool):
        raise ValueError("stated_confidence has an unsupported type")
    if isinstance(confidence, Real):
        try:
            valid_confidence = math.isfinite(confidence) and 0.0 <= confidence <= 1.0
        except (OverflowError, TypeError):
            valid_confidence = False
        if not valid_confidence:
            raise ValueError("stated_confidence is outside 0..1")
        confidence = float(confidence)
    elif confidence != _EXPLICIT_CONFIDENCE_EXAMPLE:
        # B8 shows "medium" but defines no complete band vocabulary.
        raise ValueError("stated_confidence band is not specified")

    return DiagnosisOutput(
        plant_visible=plant_visible,
        crop=crop,
        issue=issue,
        alternatives=alternatives,
        symptoms_observed=symptoms,
        image_issues=image_issues,
        stated_confidence=confidence,
        segment_prompts=segment_prompts,
    )


def run_diagnosis_validation(
    provider: DiagnosisProvider,
    *,
    supported_crops: Collection[str],
    disease_ids: Collection[str],
) -> DiagnosisResult:
    """Call an injected provider and allow exactly one repair for invalid JSON.

    Provider exceptions produce ``UNAVAILABLE`` without an automatic retry;
    this offline validator does not implement B11 live API backoff behavior.
    The optional callback receives only a fixed diagnostic code, never output.
    """
    if not isinstance(provider, DiagnosisProvider):
        return DiagnosisResult(DiagnosisStatus.UNAVAILABLE, None, "provider_unavailable")
    try:
        _valid_vocabulary(supported_crops, field="crop")
        _valid_vocabulary(disease_ids, field="disease")
    except ValueError:
        return DiagnosisResult(DiagnosisStatus.UNAVAILABLE, None, "schema_configuration_invalid")
    try:
        raw = provider.generate()
    except Exception:
        return DiagnosisResult(DiagnosisStatus.UNAVAILABLE, None, "provider_failure")

    try:
        output = validate_diagnosis_json(
            raw, supported_crops=supported_crops, disease_ids=disease_ids
        )
        return DiagnosisResult(DiagnosisStatus.VALID, output, "validated")
    except ValueError:
        if not isinstance(raw, str):
            return DiagnosisResult(DiagnosisStatus.UNKNOWN, None, "invalid_output", 0)
        if len(raw) > MAX_DIAGNOSIS_OUTPUT_CHARS:
            return DiagnosisResult(DiagnosisStatus.UNKNOWN, None, "output_exceeds_local_limit", 0)

    try:
        repaired = provider.repair(raw)
    except Exception:
        return DiagnosisResult(DiagnosisStatus.UNAVAILABLE, None, "repair_provider_failure", REPAIR_ATTEMPTS)
    try:
        output = validate_diagnosis_json(
            repaired, supported_crops=supported_crops, disease_ids=disease_ids
        )
    except ValueError:
        return DiagnosisResult(DiagnosisStatus.UNKNOWN, None, "invalid_after_repair", REPAIR_ATTEMPTS)
    return DiagnosisResult(DiagnosisStatus.VALID, output, "validated_after_repair", REPAIR_ATTEMPTS)
