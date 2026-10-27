"""Local tests for fail-closed external-processing decisions."""

import pytest

from mydrak.privacy.data_policy import (
    DataClass,
    DataPolicy,
    DataPolicyError,
    ProcessingEvidence,
    ProviderMode,
    data_policy_from_env,
    parse_data_policy,
    require_external_processing_allowed,
)


def test_missing_policy_defaults_to_private():
    assert data_policy_from_env({}) is DataPolicy.PRIVATE
    assert parse_data_policy(None) is DataPolicy.PRIVATE


@pytest.mark.parametrize("value", ["", "unknown", "PRIVATE", "contributor"])
def test_invalid_policy_rejected(value):
    with pytest.raises(DataPolicyError):
        parse_data_policy(value)


def test_private_default_blocks_without_explicit_evidence():
    with pytest.raises(DataPolicyError):
        require_external_processing_allowed(
            DataPolicy.PRIVATE,
            DataClass.PRIVATE,
            ProcessingEvidence(provider_mode=ProviderMode.STANDARD),
        )


def test_gate_rejects_unparsed_policy_value():
    evidence = ProcessingEvidence(
        provider_mode=ProviderMode.STANDARD,
        provider_mode_verified=True,
        rights_confirmed=True,
        user_authorization_confirmed=True,
        privacy_notice_present=True,
    )
    with pytest.raises(DataPolicyError, match="not been validated"):
        require_external_processing_allowed("private", DataClass.PRIVATE, evidence)


def test_private_requires_standard_and_each_explicit_condition():
    complete = ProcessingEvidence(
        provider_mode=ProviderMode.STANDARD,
        provider_mode_verified=True,
        rights_confirmed=True,
        user_authorization_confirmed=True,
        privacy_notice_present=True,
    )
    require_external_processing_allowed(DataPolicy.PRIVATE, DataClass.PRIVATE, complete)

    for field in (
        "provider_mode_verified",
        "rights_confirmed",
        "user_authorization_confirmed",
        "privacy_notice_present",
    ):
        values = complete.__dict__ | {field: False}
        with pytest.raises(DataPolicyError):
            require_external_processing_allowed(
                DataPolicy.PRIVATE,
                DataClass.PRIVATE,
                ProcessingEvidence(**values),
            )


def test_private_is_never_allowed_on_contributor_services():
    evidence = ProcessingEvidence(
        provider_mode=ProviderMode.CONTRIBUTOR,
        provider_mode_verified=True,
        rights_confirmed=True,
        user_authorization_confirmed=True,
        privacy_notice_present=True,
    )
    with pytest.raises(DataPolicyError, match="Contributor"):
        require_external_processing_allowed(DataPolicy.PRIVATE, DataClass.PRIVATE, evidence)


def test_public_test_flag_alone_does_not_authorize_data():
    evidence = ProcessingEvidence(
        provider_mode=ProviderMode.CONTRIBUTOR,
        provider_mode_verified=True,
        rights_confirmed=True,
    )
    with pytest.raises(DataPolicyError, match="provenance"):
        require_external_processing_allowed(DataPolicy.PUBLIC_TEST, DataClass.PUBLIC_TEST, evidence)


def test_verified_public_test_data_can_use_verified_contributor_mode():
    evidence = ProcessingEvidence(
        provider_mode=ProviderMode.CONTRIBUTOR,
        provider_mode_verified=True,
        rights_confirmed=True,
        public_test_provenance_verified=True,
    )
    require_external_processing_allowed(DataPolicy.PUBLIC_TEST, DataClass.PUBLIC_TEST, evidence)


def test_public_test_mode_does_not_downgrade_private_classification():
    evidence = ProcessingEvidence(
        provider_mode=ProviderMode.CONTRIBUTOR,
        provider_mode_verified=True,
        rights_confirmed=True,
        public_test_provenance_verified=True,
    )
    with pytest.raises(DataPolicyError, match="private data"):
        require_external_processing_allowed(DataPolicy.PUBLIC_TEST, DataClass.PRIVATE, evidence)
