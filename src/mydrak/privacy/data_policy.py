"""Fail-closed guard for any future external processing of user data.

This module performs no network I/O and records no supplied data. Callers must
provide verified per-request evidence; the DATA_POLICY setting alone never
authorizes transmission.
"""

from dataclasses import dataclass
from enum import StrEnum
import os
from typing import Mapping


class DataPolicyError(ValueError):
    """Raised when policy configuration or processing evidence is insufficient."""


class DataPolicy(StrEnum):
    PRIVATE = "private"
    PUBLIC_TEST = "public_test"


class DataClass(StrEnum):
    PRIVATE = "private"
    PUBLIC_TEST = "public_test"


class ProviderMode(StrEnum):
    STANDARD = "standard"
    CONTRIBUTOR = "contributor"


@dataclass(frozen=True)
class ProcessingEvidence:
    """Explicit checks a caller must establish before requesting external work.

    These booleans represent evidence verified by the calling product flow;
    this module does not collect consent, establish legal rights, or verify a
    provider's actual route itself.
    """

    provider_mode: ProviderMode
    provider_mode_verified: bool = False
    rights_confirmed: bool = False
    user_authorization_confirmed: bool = False
    privacy_notice_present: bool = False
    public_test_provenance_verified: bool = False


def parse_data_policy(value: str | None) -> DataPolicy:
    """Read a policy value, defaulting only a missing value to private."""
    if value is None:
        return DataPolicy.PRIVATE
    try:
        return DataPolicy(value)
    except ValueError as exc:
        raise DataPolicyError("DATA_POLICY must be 'private' or 'public_test'") from exc


def data_policy_from_env(environ: Mapping[str, str] | None = None) -> DataPolicy:
    """Parse DATA_POLICY without exposing environment contents in errors."""
    values = os.environ if environ is None else environ
    return parse_data_policy(values.get("DATA_POLICY"))


def require_external_processing_allowed(
    policy: DataPolicy,
    data_class: DataClass,
    evidence: ProcessingEvidence,
) -> None:
    """Return only when the proposed external processing meets every gate."""
    if not isinstance(policy, DataPolicy):
        raise DataPolicyError("DATA_POLICY has not been validated")
    if not isinstance(data_class, DataClass):
        raise DataPolicyError("data classification has not been validated")
    if evidence.provider_mode not in (ProviderMode.STANDARD, ProviderMode.CONTRIBUTOR):
        raise DataPolicyError("provider mode is not supported")
    if not evidence.provider_mode_verified:
        raise DataPolicyError("provider mode has not been verified")
    if not evidence.rights_confirmed:
        raise DataPolicyError("required data rights have not been confirmed")

    if data_class is DataClass.PRIVATE:
        if evidence.provider_mode is not ProviderMode.STANDARD:
            raise DataPolicyError("private data is blocked from Contributor services")
        if not evidence.user_authorization_confirmed:
            raise DataPolicyError("user authorization has not been confirmed")
        if not evidence.privacy_notice_present:
            raise DataPolicyError("the required privacy notice is not present")
        return

    if data_class is DataClass.PUBLIC_TEST:
        if policy is not DataPolicy.PUBLIC_TEST:
            raise DataPolicyError("public-test data requires DATA_POLICY=public_test")
        if not evidence.public_test_provenance_verified:
            raise DataPolicyError("public-test provenance has not been verified")
        return

    raise DataPolicyError("data classification is not supported")
