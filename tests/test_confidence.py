"""Confidence vocabulary: fixed plain words, never percentages."""

from mydrak.reply.confidence import confidence_words


def test_confidence_vocabulary():
    assert confidence_words(0.9) == "fairly sure"
    assert confidence_words(0.5) == "not sure"
    assert confidence_words(0.1) == "cannot tell"
