"""Offline B8 schema/repair tests using clearly synthetic records only."""

import json
import math
import ast
from pathlib import Path

import pytest

from mydrak.decider.extraction import extract_confidence
from mydrak.vision.diagnosis import (
    DiagnosisStatus,
    REPAIR_ATTEMPTS,
    run_diagnosis_validation,
    validate_diagnosis_json,
)


SYNTHETIC_CROPS = ("test_crop",)
SYNTHETIC_DISEASE_IDS = ("test_issue", "test_alternative")
SYNTHETIC_OUTPUT = {
    "plant_visible": True,
    "crop": "test_crop",
    "issue": "test_issue",
    "alternatives": ["test_alternative"],
    "symptoms_observed": ["synthetic symptom placeholder"],
    "image_issues": [],
    "stated_confidence": 0.7,
    "segment_prompts": ["synthetic prompt placeholder"],
}


class FakeDiagnosisProvider:
    def __init__(self, generated=None, repaired=None, *, generate_error=None, repair_error=None):
        self.generated = generated
        self.repaired = repaired
        self.generate_error = generate_error
        self.repair_error = repair_error
        self.generate_calls = 0
        self.repair_calls = 0
        self.repair_input = None

    def generate(self):
        self.generate_calls += 1
        if self.generate_error:
            raise self.generate_error
        return self.generated

    def repair(self, invalid_output):
        self.repair_calls += 1
        self.repair_input = invalid_output
        if self.repair_error:
            raise self.repair_error
        return self.repaired


def raw_output(data=None):
    return json.dumps(SYNTHETIC_OUTPUT if data is None else data, allow_nan=True)


def validate(raw):
    return validate_diagnosis_json(
        raw,
        supported_crops=SYNTHETIC_CROPS,
        disease_ids=SYNTHETIC_DISEASE_IDS,
    )


def run(provider, **kwargs):
    return run_diagnosis_validation(
        provider,
        supported_crops=SYNTHETIC_CROPS,
        disease_ids=SYNTHETIC_DISEASE_IDS,
        **kwargs,
    )


def test_valid_synthetic_b8_output_is_structured_and_numeric_confidence_aligns_with_s4():
    output = validate(raw_output())
    assert output.crop == "test_crop"
    assert output.issue == "test_issue"
    assert output.alternatives == ("test_alternative",)
    assert output.stated_confidence == 0.7
    assert extract_confidence(output.stated_confidence).value == 0.7
    assert not hasattr(output, "action")


def test_only_explicitly_demonstrated_confidence_band_is_accepted_but_unmapped_to_s4():
    data = {**SYNTHETIC_OUTPUT, "stated_confidence": "medium"}
    output = validate(raw_output(data))
    assert output.stated_confidence == "medium"
    assert extract_confidence(output.stated_confidence).value is None
    with pytest.raises(ValueError, match="band is not specified"):
        validate(raw_output({**data, "stated_confidence": "high"}))


@pytest.mark.parametrize("field", sorted({
    "plant_visible", "crop", "issue", "alternatives", "symptoms_observed",
    "image_issues", "stated_confidence", "segment_prompts",
}))
def test_missing_required_b8_field_rejected(field):
    data = dict(SYNTHETIC_OUTPUT)
    del data[field]
    with pytest.raises(ValueError):
        validate(raw_output(data))


def test_unexpected_policy_or_routing_fields_are_rejected():
    for field in ("action", "policy", "route", "confidence_override"):
        with pytest.raises(ValueError, match="B8 fields"):
            validate(raw_output({**SYNTHETIC_OUTPUT, field: "answer"}))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("plant_visible", "true"),
        ("crop", True),
        ("issue", "not-in-kb"),
        ("alternatives", ["not-in-kb"]),
        ("symptoms_observed", [""]),
        ("image_issues", "not a list"),
        ("segment_prompts", [None]),
    ],
)
def test_wrong_types_or_unallowed_vocabulary_rejected(field, value):
    with pytest.raises(ValueError):
        validate(raw_output({**SYNTHETIC_OUTPUT, field: value}))


@pytest.mark.parametrize("confidence", [True, -0.01, 1.01, math.nan, math.inf, 10**1000])
def test_confidence_must_be_finite_numeric_value_in_unit_range(confidence):
    with pytest.raises(ValueError):
        validate(raw_output({**SYNTHETIC_OUTPUT, "stated_confidence": confidence}))


@pytest.mark.parametrize("raw", ["{broken", "[]", "null", "NaN", "{}{}"])
def test_malformed_or_wrong_top_level_json_rejected(raw):
    with pytest.raises(ValueError):
        validate(raw)


def test_validation_error_does_not_echo_raw_untrusted_output():
    marker = "synthetic-untrusted-output-marker"
    with pytest.raises(ValueError) as caught:
        validate(f"{{broken {marker}")
    assert marker not in str(caught.value)
    assert caught.value.__cause__ is None


def test_duplicate_json_keys_and_nonstandard_constants_rejected():
    duplicate = raw_output()[:-1] + ', "issue": "second"}'
    for raw in (duplicate, raw_output({**SYNTHETIC_OUTPUT, "stated_confidence": math.inf})):
        with pytest.raises(ValueError):
            validate(raw)


def test_nonplant_must_not_assert_crop_or_disease():
    with pytest.raises(ValueError, match="must not assert"):
        validate(raw_output({**SYNTHETIC_OUTPUT, "plant_visible": False}))
    safe = {
        **SYNTHETIC_OUTPUT,
        "plant_visible": False,
        "crop": "unknown",
        "issue": "unknown",
        "alternatives": [],
        "symptoms_observed": [],
        "segment_prompts": [],
    }
    assert validate(raw_output(safe)).plant_visible is False


def test_configured_vocabulary_is_required_to_avoid_inventing_crop_or_card_lists():
    with pytest.raises(ValueError, match="outside the configured"):
        validate_diagnosis_json(raw_output(), supported_crops=(), disease_ids=())


def test_invalid_json_gets_exactly_one_repair_then_validates():
    provider = FakeDiagnosisProvider(generated="{invalid", repaired=raw_output())
    result = run(provider)
    assert REPAIR_ATTEMPTS == 1
    assert result.status is DiagnosisStatus.VALID
    assert result.reason == "validated_after_repair"
    assert result.repair_attempts == 1
    assert provider.generate_calls == provider.repair_calls == 1
    assert provider.repair_input == "{invalid"


def test_repair_invalid_output_falls_back_to_unknown_without_second_repair():
    provider = FakeDiagnosisProvider(generated="{invalid", repaired="still invalid")
    result = run(provider)
    assert result.status is DiagnosisStatus.UNKNOWN
    assert result.output is None
    assert result.reason == "invalid_after_repair"
    assert result.repair_attempts == 1
    assert provider.repair_calls == 1


def test_schema_invalid_json_is_repaired_once_then_unknown():
    provider = FakeDiagnosisProvider(
        generated=raw_output({**SYNTHETIC_OUTPUT, "action": "answer"}),
        repaired=raw_output({**SYNTHETIC_OUTPUT, "issue": "unknown"}),
    )
    result = run(provider)
    assert result.status is DiagnosisStatus.VALID
    assert result.output.issue == "unknown"
    assert result.repair_attempts == 1


def test_provider_failure_is_unavailable_and_not_retried_or_leaked():
    marker = "synthetic-private-provider-detail"
    provider = FakeDiagnosisProvider(generate_error=RuntimeError(marker))
    result = run(provider)
    assert result.status is DiagnosisStatus.UNAVAILABLE
    assert result.reason == "provider_failure"
    assert marker not in repr(result)
    assert provider.generate_calls == 1
    assert provider.repair_calls == 0


def test_repair_provider_failure_is_unavailable_and_sanitized():
    marker = "synthetic-repair-provider-detail"
    provider = FakeDiagnosisProvider(generated="{invalid", repair_error=RuntimeError(marker))
    result = run(provider)
    assert result.status is DiagnosisStatus.UNAVAILABLE
    assert result.reason == "repair_provider_failure"
    assert result.repair_attempts == 1
    assert marker not in repr(result)


def test_non_string_provider_output_is_unknown_without_repair():
    provider = FakeDiagnosisProvider(generated={"raw": "synthetic"}, repaired=raw_output())
    result = run(provider)
    assert result.status is DiagnosisStatus.UNKNOWN
    assert provider.repair_calls == 0


def test_oversized_output_is_unknown_without_repair():
    provider = FakeDiagnosisProvider(generated="x" * 65_537, repaired=raw_output())
    result = run(provider)
    assert result.status is DiagnosisStatus.UNKNOWN
    assert result.reason == "output_exceeds_local_limit"
    assert provider.repair_calls == 0


def test_invalid_schema_configuration_prevents_provider_call():
    provider = FakeDiagnosisProvider(generated=raw_output())
    result = run_diagnosis_validation(provider, supported_crops=["x", "x"], disease_ids=[])
    assert result.status is DiagnosisStatus.UNAVAILABLE
    assert result.reason == "schema_configuration_invalid"
    assert provider.generate_calls == 0


def test_contract_module_has_no_network_or_environment_client_imports():
    source = Path(__file__).parents[1] / "src/mydrak/vision/diagnosis.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not imports.intersection({"os", "requests", "urllib", "http", "openai", "telegram"})
