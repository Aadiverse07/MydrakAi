"""Fixed confidence vocabulary (spec B7): fairly sure / not sure / cannot tell.

Cutoffs are UNVERIFIED placeholders pending dev-set tuning. Never report a
percentage to the farmer.
"""


def confidence_words(score: float, sure_min: float = 0.7, doubt_min: float = 0.4) -> str:
    """Map a decider score to the fixed plain-word vocabulary."""
    if score >= sure_min:
        return "fairly sure"
    if score >= doubt_min:
        return "not sure"
    return "cannot tell"
