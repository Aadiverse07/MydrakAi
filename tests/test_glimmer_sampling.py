"""Offline T12 tests with synthetic B8-shaped outputs only."""

import json
import ast
from pathlib import Path

import pytest

from mydrak.vision.diagnosis import DiagnosisStatus
from mydrak.vision.sampling import (
    GLIMMER_SAMPLES_PER_CASE,
    MAX_SPARK_ESCALATIONS_PER_CASE,
    SamplingState,
    SamplingStatus,
    run_t12_sampling,
)

SYNTHETIC_CROPS = ("test_crop", "other_test_crop")
SYNTHETIC_ISSUES = ("test_issue_a", "test_issue_b")
SYNTHETIC_OUTPUT = {
    "plant_visible": True,
    "crop": "test_crop",
    "issue": "test_issue_a",
    "alternatives": [],
    "symptoms_observed": ["synthetic placeholder symptom"],
    "image_issues": [],
    "stated_confidence": 0.5,
    "segment_prompts": ["synthetic placeholder prompt"],
}


def raw(data):
    return json.dumps(data)


class QueueProvider:
    def __init__(self, *generated, repaired=None, error_at=(), error_message="synthetic provider failure"):
        self.generated = list(generated)
        self.repaired = repaired
        self.error_at = set(error_at)
        self.error_message = error_message
        self.generate_calls = 0
        self.repair_calls = 0

    def generate(self):
        index = self.generate_calls
        self.generate_calls += 1
        if index in self.error_at:
            raise RuntimeError(self.error_message)
        return self.generated[index] if index < len(self.generated) else None

    def repair(self, invalid_output):
        self.repair_calls += 1
        return self.repaired


def run(glimmer, spark):
    return run_t12_sampling(
        glimmer,
        spark,
        supported_crops=SYNTHETIC_CROPS,
        disease_ids=SYNTHETIC_ISSUES,
    )


def test_two_valid_matching_samples_return_agreement_without_escalation():
    provider = QueueProvider(raw(SYNTHETIC_OUTPUT), raw(SYNTHETIC_OUTPUT))
    spark = QueueProvider()

    result = run(provider, spark)

    assert GLIMMER_SAMPLES_PER_CASE == 2
    assert provider.generate_calls == 2
    assert result.status is SamplingStatus.SAMPLES_AGREE
    assert result.agreement.value == 1.0
    assert result.spark_escalations == spark.generate_calls == 0
    assert result.reason == "glimmer_samples_agree_decider_pending"


@pytest.mark.parametrize(
    ("second", "expected_s1"),
    [
        ({**SYNTHETIC_OUTPUT, "issue": "test_issue_b"}, 0.5),
        ({**SYNTHETIC_OUTPUT, "crop": "other_test_crop"}, 0.0),
    ],
)
def test_valid_disagreement_triggers_one_validated_spark_escalation(second, expected_s1):
    glimmer = QueueProvider(raw(SYNTHETIC_OUTPUT), raw(second))
    spark = QueueProvider(raw(SYNTHETIC_OUTPUT))

    result = run(glimmer, spark)

    assert glimmer.generate_calls == GLIMMER_SAMPLES_PER_CASE
    assert spark.generate_calls == MAX_SPARK_ESCALATIONS_PER_CASE == 1
    assert result.status is SamplingStatus.SPARK_ESCALATED
    assert result.agreement.value == expected_s1
    assert result.spark_result.status is DiagnosisStatus.VALID
    assert result.spark_escalations == 1
    assert result.reason == "rescore_blocked_s2_s3_and_thresholds_unavailable"


@pytest.mark.parametrize(
    "bad_sample",
    ["{broken", None, raw({**SYNTHETIC_OUTPUT, "issue": "unconfigured"})],
)
def test_malformed_or_missing_sample_fails_closed_without_spark(bad_sample):
    glimmer = QueueProvider(raw(SYNTHETIC_OUTPUT), bad_sample)
    spark = QueueProvider(raw(SYNTHETIC_OUTPUT))

    result = run(glimmer, spark)

    assert glimmer.generate_calls == 2
    assert result.status is SamplingStatus.UNAVAILABLE
    assert result.agreement.value is None
    assert result.spark_escalations == spark.generate_calls == 0


def test_b8_single_repair_applies_to_an_invalid_glimmer_sample():
    glimmer = QueueProvider("{broken", raw(SYNTHETIC_OUTPUT), repaired=raw(SYNTHETIC_OUTPUT))
    spark = QueueProvider()

    result = run(glimmer, spark)

    assert result.status is SamplingStatus.SAMPLES_AGREE
    assert glimmer.generate_calls == 2
    assert glimmer.repair_calls == 1
    assert result.glimmer_samples[0].repair_attempts == 1
    assert spark.generate_calls == 0


def test_valid_unknown_labels_are_not_misreported_as_agreement_or_escalation():
    unknown = {
        **SYNTHETIC_OUTPUT,
        "crop": "unknown",
        "issue": "unknown",
        "alternatives": [],
        "symptoms_observed": [],
        "segment_prompts": [],
    }
    glimmer = QueueProvider(raw(unknown), raw(unknown))
    spark = QueueProvider()

    result = run(glimmer, spark)

    assert result.status is SamplingStatus.UNAVAILABLE
    assert result.reason == "sample_label_unknown"
    assert result.agreement.value is None
    assert spark.generate_calls == 0


def test_spark_failure_consumes_the_single_escalation_and_is_sanitized():
    glimmer = QueueProvider(raw(SYNTHETIC_OUTPUT), raw({**SYNTHETIC_OUTPUT, "issue": "test_issue_b"}))
    marker = "synthetic-provider-detail"
    spark = QueueProvider(error_at=(0,), error_message=marker)

    result = run(glimmer, spark)

    assert result.status is SamplingStatus.UNAVAILABLE
    assert result.spark_escalations == spark.generate_calls == 1
    assert result.spark_result.reason == "provider_failure"
    assert marker not in repr(result)


def test_malformed_spark_result_consumes_one_escalation_and_stays_unavailable():
    glimmer = QueueProvider(
        raw(SYNTHETIC_OUTPUT),
        raw({**SYNTHETIC_OUTPUT, "issue": "test_issue_b"}),
    )
    spark = QueueProvider("{broken")

    result = run(glimmer, spark)

    assert spark.generate_calls == spark.repair_calls == 1
    assert result.status is SamplingStatus.UNAVAILABLE
    assert result.spark_escalations == 1
    assert result.spark_result.status is DiagnosisStatus.UNKNOWN


def test_sampling_module_has_no_concrete_network_or_environment_client():
    path = Path(__file__).parents[1] / "src/mydrak/vision/sampling.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imports.isdisjoint({"httpx", "requests", "urllib", "socket", "os", "dotenv"})


def test_carried_case_state_prevents_a_second_spark_escalation():
    glimmer = QueueProvider(
        raw(SYNTHETIC_OUTPUT),
        raw({**SYNTHETIC_OUTPUT, "issue": "test_issue_b"}),
    )
    spark = QueueProvider(raw(SYNTHETIC_OUTPUT))

    first = run(glimmer, spark)
    second_glimmer = QueueProvider(
        raw(SYNTHETIC_OUTPUT),
        raw({**SYNTHETIC_OUTPUT, "issue": "test_issue_b"}),
    )
    second = run_t12_sampling(
        second_glimmer,
        spark,
        supported_crops=SYNTHETIC_CROPS,
        disease_ids=SYNTHETIC_ISSUES,
        state=first.state,
    )

    assert first.state == SamplingState(spark_escalations=1)
    assert second.reason == "spark_escalation_already_used"
    assert second.spark_escalations == 1
    assert spark.generate_calls == 1


@pytest.mark.parametrize("state", [None, SamplingState(True), SamplingState(2)])
def test_invalid_or_exhausted_case_state_fails_closed(state):
    glimmer = QueueProvider(raw(SYNTHETIC_OUTPUT), raw(SYNTHETIC_OUTPUT))
    spark = QueueProvider()
    result = run_t12_sampling(
        glimmer,
        spark,
        supported_crops=SYNTHETIC_CROPS,
        disease_ids=SYNTHETIC_ISSUES,
        state=state,
    )
    assert result.status is SamplingStatus.UNAVAILABLE
    assert glimmer.generate_calls == spark.generate_calls == 0


def test_bad_vocabulary_fails_closed_without_provider_calls():
    glimmer = QueueProvider(raw(SYNTHETIC_OUTPUT), raw(SYNTHETIC_OUTPUT))
    spark = QueueProvider()
    result = run_t12_sampling(
        glimmer,
        spark,
        supported_crops=("test_crop", "test_crop"),
        disease_ids=SYNTHETIC_ISSUES,
    )
    assert result.status is SamplingStatus.UNAVAILABLE
    assert glimmer.generate_calls == spark.generate_calls == 0
