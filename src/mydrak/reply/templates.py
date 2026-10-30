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
