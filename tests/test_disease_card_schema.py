"""Synthetic-only tests for the B6 disease-card structure; no disease content."""

import copy

import pytest

from mydrak.kb.loader import load_disease_card, validate_disease_card


# Test-only placeholder text asserts shape, never agronomic facts or advice.
SYNTHETIC_DISEASE_CARD = {
    "id": "test_card",
    "crop": "test_crop",
    "names": {"en": "Synthetic name", "hi": "Synthetic reviewed-name placeholder"},
    "symptoms": ["Synthetic symptom placeholder"],
    "confusable_with": ["other_test_card"],
    "follow_up_questions": [
        {"id": "q_test", "en": "Synthetic question?", "hi": "Synthetic question placeholder?"}
    ],
    "low_risk_steps": {
        "en": ["Synthetic low-risk step placeholder"],
        "hi": ["Synthetic low-risk step placeholder"],
    },
    "chemical_options": [],
    "when_to_refer": "Synthetic referral condition placeholder",
    "sources": ["Synthetic citation placeholder"],
    "reviewed_by": "Synthetic reviewer placeholder",
}


def test_valid_synthetic_disease_card_is_returned_unchanged():
    card = copy.deepcopy(SYNTHETIC_DISEASE_CARD)
    assert validate_disease_card(card) is card


@pytest.mark.parametrize("field", [
    "id", "crop", "names", "symptoms", "confusable_with",
    "follow_up_questions", "low_risk_steps", "chemical_options",
    "when_to_refer", "sources", "reviewed_by",
])
def test_missing_required_field_rejected(field):
    card = copy.deepcopy(SYNTHETIC_DISEASE_CARD)
    del card[field]
    with pytest.raises(ValueError):
        validate_disease_card(card)


@pytest.mark.parametrize(("field", "value"), [
    ("id", "  "),
    ("crop", 3),
    ("symptoms", "not a list"),
    ("sources", []),
    ("when_to_refer", ""),
    ("reviewed_by", None),
    ("chemical_options", {}),
])
def test_wrong_types_and_empty_required_values_rejected(field, value):
    card = copy.deepcopy(SYNTHETIC_DISEASE_CARD)
    card[field] = value
    with pytest.raises(ValueError):
        validate_disease_card(card)


@pytest.mark.parametrize("field", ["names", "low_risk_steps"])
def test_malformed_bilingual_mappings_rejected(field):
    card = copy.deepcopy(SYNTHETIC_DISEASE_CARD)
    card[field] = {"en": "English only"}
    with pytest.raises(ValueError):
        validate_disease_card(card)


def test_empty_bilingual_values_and_lists_rejected():
    for field, value in (
        ("names", {"en": "", "hi": "Synthetic"}),
        ("low_risk_steps", {"en": [], "hi": ["Synthetic"]}),
        ("low_risk_steps", {"en": ["Synthetic"], "hi": [""]}),
    ):
        card = copy.deepcopy(SYNTHETIC_DISEASE_CARD)
        card[field] = value
        with pytest.raises(ValueError):
            validate_disease_card(card)


@pytest.mark.parametrize("question", [
    "not a mapping",
    {"id": "q", "en": "English only"},
    {"id": "", "en": "Synthetic?", "hi": "Synthetic?"},
    {"id": "q", "en": " ", "hi": "Synthetic?"},
])
def test_invalid_follow_up_question_rejected(question):
    card = copy.deepcopy(SYNTHETIC_DISEASE_CARD)
    card["follow_up_questions"] = [question]
    with pytest.raises(ValueError):
        validate_disease_card(card)


def test_follow_up_question_ids_must_be_unique():
    card = copy.deepcopy(SYNTHETIC_DISEASE_CARD)
    card["follow_up_questions"].append(copy.deepcopy(card["follow_up_questions"][0]))
    with pytest.raises(ValueError, match="unique"):
        validate_disease_card(card)


@pytest.mark.parametrize("option", [
    "not a mapping",
    {},
    {"text": "Synthetic option", "source": "Synthetic citation"},
    {"text": "Synthetic option", "source": "Synthetic citation", "label_instruction": ""},
])
def test_malformed_chemical_option_rejected(option):
    card = copy.deepcopy(SYNTHETIC_DISEASE_CARD)
    card["chemical_options"] = [option]
    with pytest.raises(ValueError):
        validate_disease_card(card)


def test_nonempty_chemical_option_with_local_minimum_shape_is_accepted():
    card = copy.deepcopy(SYNTHETIC_DISEASE_CARD)
    card["chemical_options"] = [{
        "text": "Synthetic option placeholder",
        "source": "Synthetic citation placeholder",
        "label_instruction": "Synthetic label instruction placeholder",
    }]
    assert validate_disease_card(card) is card


def test_disease_card_yaml_loader_validates_record(tmp_path):
    import yaml

    path = tmp_path / "synthetic_test_only.yaml"
    path.write_text(yaml.safe_dump(SYNTHETIC_DISEASE_CARD), encoding="utf-8")
    assert load_disease_card(path)["id"] == "test_card"

    bad_path = tmp_path / "malformed_test_only.yaml"
    bad_path.write_text("id: incomplete\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_disease_card(bad_path)
