"""Photo-consent versioning and per-request private processing evidence."""

from mydrak.privacy.data_policy import ProcessingEvidence, ProviderMode
from mydrak.telegram.limits import ConsentRecord

CONSENT_NOTICE_VERSION = "private-photo-v1"
STANDARD_SPARK_MODEL_ID = "muse-spark-1.3"


def processing_evidence_for(
    record: ConsentRecord | None,
    *,
    notice_approved: bool,
    standard_model_id: object,
    contributor_model_id: object,
) -> ProcessingEvidence:
    """Build fail-closed evidence for this hashed user's current request."""
    record_current = (
        isinstance(record, ConsentRecord)
        and record.consent_version == CONSENT_NOTICE_VERSION
        and record.revoked_at is None
        and bool(record.consented_at)
    )
    mode_verified = (
        standard_model_id == STANDARD_SPARK_MODEL_ID
        and isinstance(contributor_model_id, str)
        and bool(contributor_model_id)
        and contributor_model_id != standard_model_id
    )
    return ProcessingEvidence(
        provider_mode=ProviderMode.STANDARD,
        provider_mode_verified=mode_verified,
        rights_confirmed=record_current,
        user_authorization_confirmed=record_current,
        privacy_notice_present=(
            notice_approved is True
            and record_current
            and record is not None
            and record.consent_version == CONSENT_NOTICE_VERSION
        ),
    )
