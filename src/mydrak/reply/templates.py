"""User-facing reply templates. English is available; Hindi awaits review."""

TEMPLATES = {
    "en": {
        "answer": (
            "Likely issue: {issue} on {crop}.\n"
            "How sure: {confidence}.\n"
            "{severity}"
            "What to do now: {steps}\n"
            "Safety: {safety_line}\n"
            "{referral_text}"
        ),
        "answer_without_severity": (
            "Likely issue: {issue} on {crop}.\n"
            "How sure: {confidence}.\n"
            "What to do now: {steps}\n"
            "Safety: {safety_line}\n"
            "{referral_text}"
        ),
        "ask": "I am not sure yet. One question: {question}",
        "ask_with_alternatives": (
            "I am not sure yet. It could be {alternatives}. One question: {question}"
        ),
        "refer": "I cannot tell from this photo. {referral_text}",
        "retake": "{retake_text}",
    },
    # Do not put unreviewed translations in user-visible output. The master
    # specification requires Hindi text to be pre-written and native-reviewed.
    "hi": None,
}

# Telegram runner prompts are kept with other user-visible text. English is
# available; Hindi strings remain unavailable until reviewed.
TELEGRAM_TEMPLATES = {
    "en": {
        "start": (
            "Welcome. Choose English or Hindi with /language en or /language hi. "
            "Use /privacy to read the photo notice and /agree to give consent. "
            "Photo processing stays blocked until all privacy settings are approved. "
            "Hindi replies are not available until reviewed."
        ),
        "send_photo": "Please send a private-chat photo of the plant.",
        "photo_blocked": (
            "This photo cannot be analyzed under the current privacy and data-policy settings. "
            "Use /privacy to review the photo notice."
        ),
        "limited": "The bot cannot process this request right now. Please try again later.",
        "text_unavailable": (
            "Text-only symptom interpretation is unavailable. Please send a plant photo "
            "or contact a local expert."
        ),
        "rescan_unavailable": "Rescan is not implemented yet. Please send a new plant photo.",
        "start_required": "Please send /start and read the privacy note before sending a photo.",
        "help": (
            "Use /start, then /privacy and /agree before sending a photo. Use /withdraw "
            "to block future photo processing. Voice and rescans are not available."
        ),
        "privacy_notice": (
            "DRAFT privacy notice for photos. If this notice is approved and you agree, "
            "the photo is sent to Meta's Model API using the standard muse-spark-1.3 "
            "model (not the Contributor variant) for analysis. This build uses only "
            "synthetic/mock SAM segmentation locally; it does not send photos to a live "
            "SAM service. Any result is preliminary guidance, not a diagnosis. Provider "
            "retention terms are set by the providers and are UNVERIFIED by this project. "
            "The Meta Model API pricing-page information supplied by the project owner "
            "says the standard model is not used to improve Meta's products, while the "
            "Contributor variant is; this project has not independently rechecked that "
            "source page. This bot selects only the standard model.\n\n"
            "Locally, the trace database stores hashed user IDs; case language, input "
            "type, image hash, quality measurements, final action, KB card ID, severity, "
            "latency, estimated cost and data-policy label; step name, model, start time, "
            "latency, token/cost fields, error code, retry count and outcome; signal values "
            "and decision/escalation state; image measurements; and scan rows containing hashed user ID, "
            "plant label, timestamp, image hash and severity. Its cache stores validated "
            "synthetic replay response JSON and timestamps. The local limits database "
            "stores hashed user/day photo counts and last-request times plus daily global "
            "counts. Separate rows store this user's notice version/shown time and consent "
            "version/consent time/revocation time. In-memory conversation state stores a "
            "hashed chat key with status/language and a hashed started-chat key. The trace "
            "database also has an eval-runs metadata table (run ID, strategy, optional Git "
            "hash, timestamp, metrics JSON) that this Telegram runner does not write. "
            "It does not store photo bytes or "
            "message text in these trace/cache/consent records. Local SQLite files persist; no "
            "retention period or deletion command is implemented. Use /withdraw to block "
            "future photo processing.\n\n"
            "To agree, send /agree. It confirms that you took the photo or have the right "
            "to submit it and authorizes this processing. This text remains a project draft."
        ),
        "consent_unavailable": (
            "Photo consent is not available because the notice has not been approved. "
            "No photo will be processed."
        ),
        "notice_required": "Please use /privacy and read the current notice before /agree.",
        "consent_recorded": (
            "Consent recorded for the current notice. You confirmed that you took the "
            "photo or have the right to submit it."
        ),
        "consent_storage_unavailable": "Consent could not be recorded; photo processing remains blocked.",
        "consent_withdrawn": "Consent withdrawn. Future photo processing is blocked.",
        "consent_not_active": "No active photo consent was found. Future photo processing remains blocked.",
        "language_choices": (
            "Available language: English. Hindi is not available yet. Use /language en to select English."
        ),
        "language_set": "Language set to English.",
        "hindi_unavailable": "Hindi is not available yet; the current offline reply is English.",
        "command_unavailable": "That command is not available.",
    },
    "hi": {
        "privacy_notice": {"text": None, "review_status": "UNREVIEWED"},
    },
}

TELEGRAM_TEMPLATE_REVIEW_STATUS = {
    "privacy_notice": {"en": "DRAFT", "hi": "UNREVIEWED"},
}


def telegram_message(key: str, language: str = "en") -> str:
    """Return a reviewed fixed Telegram message; never synthesize caller text."""
    translations = TELEGRAM_TEMPLATES.get(language)
    if translations is None or key not in translations:
        raise ValueError("Telegram message template is unavailable")
    value = translations[key]
    if not isinstance(value, str):
        raise ValueError("Telegram message template is unavailable")
    return value

# Fixed, non-diagnostic responses for offline demo cache entries. These do not
# contain caller/model text and are not used for treatment guidance.
OFFLINE_DEMO_RESPONSES = {
    "en": {
        "synthetic_answer": (
            "SYNTHETIC / MOCK — preliminary guidance only. This cached fixture "
            "demonstrates an answer route; it is not a diagnosis and contains no treatment advice."
        ),
        "synthetic_ask": (
            "SYNTHETIC / MOCK — preliminary guidance only. This cached fixture "
            "demonstrates an ask route: is this synthetic example photo clear?"
        ),
        "synthetic_referral": (
            "SYNTHETIC / MOCK — preliminary guidance only. I cannot tell from this "
            "fixture; please show a local agriculture expert."
        ),
        "synthetic_retake": (
            "SYNTHETIC / MOCK — preliminary guidance only. This cached fixture "
            "demonstrates a retake route; no diagnosis was made."
        ),
        "safe_referral": (
            "Offline replay — synthetic demo only: I cannot tell from this photo. "
            "If unsure, contact the Kisan Call Centre or your local KVK."
        ),
        "manual_review": (
            "Offline replay — synthetic demo only: this case needs manual review; "
            "it is not a diagnosis. If unsure, contact the Kisan Call Centre or your local KVK."
        ),
        "policy_blocked": (
            "Offline replay — synthetic demo only: processing was blocked by the local policy gate. "
            "No image was processed. This is not a diagnosis."
        ),
    },
    # Hindi remains unavailable until reviewed translation is supplied.
    "hi": None,
}
