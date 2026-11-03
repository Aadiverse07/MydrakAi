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
            "Privacy: if you send a photo for analysis, it will be sent to an AI model. "
            "Hindi replies are not available until reviewed."
        ),
        "send_photo": "Please send a private-chat photo of the plant.",
        "photo_blocked": (
            "This photo cannot be analyzed under the current privacy and data-policy settings."
        ),
        "limited": "The bot cannot process this request right now. Please try again later.",
        "text_unavailable": (
            "Text-only symptom interpretation is unavailable. Please send a plant photo "
            "or contact a local expert."
        ),
        "rescan_unavailable": "Rescan is not implemented yet. Please send a new plant photo.",
        "start_required": "Please send /start and read the privacy note before sending a photo.",
        "help": (
            "Use /start, then send a photo. Photo analysis, voice, and rescans are "
            "not available in this offline build."
        ),
        "language_choices": (
            "Available language: English. Hindi is not available yet. Use /language en to select English."
        ),
        "language_set": "Language set to English.",
        "hindi_unavailable": "Hindi is not available yet; the current offline reply is English.",
        "command_unavailable": "That command is not available.",
    },
    "hi": None,
}


def telegram_message(key: str, language: str = "en") -> str:
    """Return a reviewed fixed Telegram message; never synthesize caller text."""
    translations = TELEGRAM_TEMPLATES.get(language)
    if translations is None or key not in translations:
        raise ValueError("Telegram message template is unavailable")
    return translations[key]

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
