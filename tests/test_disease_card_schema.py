"""Offline schema, source-registry, and citation-gate tests."""

import copy
from pathlib import Path

import pytest
import yaml

from mydrak.kb.loader import (
    DISEASE_REQUIRED_KEYS,
    SOURCE_FIELDS,
    load_disease_card,
    load_safety_card,
    load_source_registry,
    validate_disease_card,
    validate_source_registry,
)

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_FIXTURE = ROOT / "tests/fixtures/kb/SYNTHETIC_TEST.yaml"
REGISTRY_PATH = ROOT / "kb/sources.yaml"


def synthetic_card() -> dict:
    return yaml.safe_load(SYNTHETIC_FIXTURE.read_text(encoding="utf-8"))


def project_registry() -> list[dict]:
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))


def eligible_test_registry() -> list[dict]:
    """Synthetic validator setup; these flags are not repository evidence."""
    entries = project_registry()
    entry = copy.deepcopy(entries[1])
    entry.update(retrieved=True, verified_by_user=True)
    return [entry]


def production_test_card() -> dict:
    card = synthetic_card()
    card.pop("test_only")
    card["id"] = "test_card"
    return card


def test_test_only_fixture_validates_only_through_explicit_synthetic_path():
    card = synthetic_card()
    assert validate_disease_card(card, allow_synthetic_test=True)["id"] == "SYNTHETIC_TEST"
    with pytest.raises(ValueError, match="not loadable"):
        validate_disease_card(card)
    with pytest.raises(ValueError, match="not loadable"):
        load_disease_card(SYNTHETIC_FIXTURE)
    unmarked_copy = copy.deepcopy(card)
    unmarked_copy.pop("test_only")
    with pytest.raises(ValueError, match="SYNTHETIC_TEST card"):
        validate_disease_card(unmarked_copy, registry=eligible_test_registry())


def test_production_yaml_loader_accepts_valid_registry_backed_card(tmp_path):
    card_path = tmp_path / "card.yaml"
    registry_path = tmp_path / "sources.yaml"
    card_path.write_text(yaml.safe_dump(production_test_card()), encoding="utf-8")
    registry_path.write_text(yaml.safe_dump(eligible_test_registry()), encoding="utf-8")
    assert load_disease_card(card_path, registry_path=registry_path)["id"] == "test_card"


def test_valid_production_shape_uses_registry_with_test_only_evidence():
    card = production_test_card()
    assert validate_disease_card(card, registry=eligible_test_registry()) is card


@pytest.mark.parametrize("field", sorted(DISEASE_REQUIRED_KEYS))
def test_missing_required_field_rejected(field):
    card = production_test_card()
    del card[field]
    with pytest.raises(ValueError, match="schema mismatch"):
        validate_disease_card(card, registry=eligible_test_registry())


def test_unknown_card_field_rejected():
    card = production_test_card()
    card["unreviewed_extra"] = "value"
    with pytest.raises(ValueError, match="unknown"):
        validate_disease_card(card, registry=eligible_test_registry())


@pytest.mark.parametrize(("field", "value"), [
    ("id", "  "), ("crop", 3), ("symptoms", "not a list"),
    ("sources", []), ("when_to_refer", ""), ("reviewed_by", 4),
    ("chemical_options", {}), ("status", "published"),
    ("region_tags", ["Mars"]),
])
def test_wrong_types_and_empty_required_values_rejected(field, value):
    card = production_test_card()
    card[field] = value
    with pytest.raises((ValueError, TypeError)):
        validate_disease_card(card, registry=eligible_test_registry())


@pytest.mark.parametrize("field", ["names", "low_risk_steps"])
def test_malformed_bilingual_mappings_rejected(field):
    card = production_test_card()
    card[field] = {"en": "English only"}
    with pytest.raises(ValueError):
        validate_disease_card(card, registry=eligible_test_registry())


def test_empty_bilingual_values_and_lists_rejected():
    for field, value in (
        ("names", {"en": "", "hi": "Synthetic"}),
        ("low_risk_steps", {"en": [], "hi": ["Synthetic"]}),
        ("low_risk_steps", {"en": ["Synthetic"], "hi": [""]}),
    ):
        card = production_test_card()
        card[field] = value
        with pytest.raises(ValueError):
            validate_disease_card(card, registry=eligible_test_registry())


@pytest.mark.parametrize("question", [
    "not a mapping", {"id": "q", "en": "English only"},
    {"id": "", "en": "Synthetic?", "hi": "Synthetic?"},
    {"id": "q", "en": " ", "hi": "Synthetic?"},
])
def test_invalid_follow_up_question_rejected(question):
    card = production_test_card()
    card["follow_up_questions"] = [question]
    with pytest.raises(ValueError):
        validate_disease_card(card, registry=eligible_test_registry())


def test_follow_up_question_ids_must_be_unique():
    card = production_test_card()
    card["follow_up_questions"].append(copy.deepcopy(card["follow_up_questions"][0]))
    with pytest.raises(ValueError, match="unique"):
        validate_disease_card(card, registry=eligible_test_registry())


@pytest.mark.parametrize("option", [
    "not a mapping", {},
    {"text": "Synthetic option", "source": "icar_iisr_soybean_bulletin_17"},
    {"text": "Synthetic option", "source": "icar_iisr_soybean_bulletin_17", "label_instruction": ""},
])
def test_malformed_chemical_option_rejected(option):
    card = production_test_card()
    card["chemical_options"] = [option]
    card["sources"] = ["icar_iisr_soybean_bulletin_17"]
    card["claim_sources"].append({
        "claim": "chemical_options[0].text", "source_id": "icar_iisr_soybean_bulletin_17",
        "page": "test page", "section": "test section",
    })
    with pytest.raises(ValueError):
        validate_disease_card(card, registry=eligible_test_registry())


def test_chemical_option_requires_registry_citation_and_label_instruction():
    card = production_test_card()
    source_id = "icar_iisr_soybean_bulletin_17"
    card["chemical_options"] = [{
        "text": "Synthetic option placeholder",
        "source": source_id,
        "label_instruction": "Follow the product label.",
    }]
    card["sources"] = [source_id]
    card["claim_sources"].append({
        "claim": "chemical_options[0].text", "source_id": source_id,
        "page": "synthetic page", "section": "synthetic section",
    })
    assert validate_disease_card(card, registry=eligible_test_registry()) is card
    card["chemical_options"][0]["label_instruction"] = "Read instructions."
    with pytest.raises(ValueError, match="follow the product label"):
        validate_disease_card(card, registry=eligible_test_registry())


@pytest.mark.parametrize("text", [
    "Apply 5 ml per litre", "mix with water before use", "Use a 1:4 mixture", "dose twice daily",
])
def test_treatment_dosage_and_mixing_patterns_rejected(text):
    card = production_test_card()
    card["low_risk_steps"]["en"][0] = text
    with pytest.raises(ValueError, match="dosage or mixing"):
        validate_disease_card(card, registry=eligible_test_registry())


def test_claim_without_source_id_is_rejected():
    card = production_test_card()
    card["claim_sources"][0].pop("source_id")
    with pytest.raises(ValueError, match="source_id"):
        validate_disease_card(card, registry=eligible_test_registry())


def test_unknown_claim_source_is_rejected():
    card = production_test_card()
    for ref in card["claim_sources"]:
        ref["source_id"] = "missing_source"
    card["sources"] = ["missing_source"]
    with pytest.raises(ValueError, match="unknown source_id"):
        validate_disease_card(card, registry=eligible_test_registry())


def test_unretrieved_source_cannot_be_cited():
    registry = eligible_test_registry()
    registry[0]["retrieved"] = False
    with pytest.raises(ValueError, match="not retrieved"):
        validate_disease_card(production_test_card(), registry=registry)


def test_cross_check_sources_cannot_be_cited():
    registry = eligible_test_registry()
    registry[0]["tier"] = "cross-check"
    with pytest.raises(ValueError, match="not citable"):
        validate_disease_card(production_test_card(), registry=registry)


def test_verified_card_requires_review_and_user_verified_sources():
    card = production_test_card()
    card["status"] = "verified"
    with pytest.raises(ValueError, match="UNREVIEWED"):
        validate_disease_card(card, registry=eligible_test_registry())
    card["review_status"] = {"en": "REVIEWED", "hi": "REVIEWED"}
    card["reviewed_by"] = "Synthetic reviewer"
    card["language_reviewers"] = {"en": "Synthetic reviewer", "hi": "Synthetic reviewer"}
    registry = eligible_test_registry()
    registry[0]["verified_by_user"] = False
    with pytest.raises(ValueError, match="user-verified"):
        validate_disease_card(card, registry=registry)


def test_reviewed_language_requires_a_confirmed_reviewer_field():
    card = production_test_card()
    card["review_status"]["en"] = "REVIEWED"
    with pytest.raises(ValueError, match="required when marked REVIEWED"):
        validate_disease_card(card, registry=eligible_test_registry())


def test_supplementary_source_requires_its_region_in_card():
    card = production_test_card()
    registry = eligible_test_registry()
    registry[0].update(region_tag="Punjab", tier="supplementary")
    with pytest.raises(ValueError, match="show supplementary source region"):
        validate_disease_card(card, registry=registry)
    card["region_tags"].append("Punjab")
    assert validate_disease_card(card, registry=registry) is card


def test_registry_integrity_unique_ids_enums_and_exact_fields():
    entries = project_registry()
    assert len(validate_source_registry(entries)) == 8
    duplicate = entries + [copy.deepcopy(entries[0])]
    with pytest.raises(ValueError, match="duplicate source id"):
        validate_source_registry(duplicate)
    for key, value in (("region_tag", "Mars"), ("tier", "best")):
        malformed = copy.deepcopy(entries)
        malformed[0][key] = value
        with pytest.raises(ValueError):
            validate_source_registry(malformed)
    malformed = copy.deepcopy(entries)
    malformed[0]["retrieved"] = "false"
    with pytest.raises(ValueError, match="must be boolean"):
        validate_source_registry(malformed)
    malformed = copy.deepcopy(entries)
    malformed[0]["unrequested_fact"] = "no"
    with pytest.raises(ValueError, match="unknown fields"):
        validate_source_registry(malformed)
    assert set(entries[0]) == SOURCE_FIELDS


def test_seeded_registry_keeps_all_candidate_sources_unverified():
    entries = load_source_registry()
    assert len(entries) == 8
    assert all(
        not item["retrieved"] and not item["verified_by_user"]
        for item in entries.values()
    )
    expected_titles = {
        "icar_cpri_gap_bulletin_108": "ICAR-CPRI GAP Bulletin 108",
        "icar_iisr_soybean_bulletin_17": "ICAR-IISR Soybean Extension Bulletin 17",
        "pau_package_of_practices": "PAU Package of Practices",
        "tnau_agritech_soybean": "TNAU Agritech Soybean",
        "icar_crida_mp_advisories": "ICAR-CRIDA MP agro-advisories",
        "wamis_mp_zone_advisories": "WAMIS MP zone advisories",
        "jnkvv_rvskvv_package": "JNKVV/RVSKVV package",
        "cpri_hindi_bulletin": "CPRI Hindi bulletin",
    }
    assert {key: entry["title"] for key, entry in entries.items()} == expected_titles
    assert entries["pau_package_of_practices"]["region_tag"] == "Punjab"
    assert entries["pau_package_of_practices"]["tier"] == "supplementary"
    assert entries["tnau_agritech_soybean"]["region_tag"] == "Tamil Nadu"
    assert entries["tnau_agritech_soybean"]["tier"] == "supplementary"
    assert entries["icar_crida_mp_advisories"]["region_tag"] == "MP"
    assert entries["icar_crida_mp_advisories"]["tier"] == "primary"
    assert entries["wamis_mp_zone_advisories"]["region_tag"] == "MP"
    assert entries["wamis_mp_zone_advisories"]["tier"] == "supplementary"
    assert entries["cpri_hindi_bulletin"]["tier"] == "cross-check"
    assert "Source gap" in entries["jnkvv_rvskvv_package"]["notes"]


def test_general_safety_card_loading_contract_is_unchanged():
    card = load_safety_card(ROOT / "kb/cards/general_safety.yaml")
    assert set(("id", "safety_line", "referral_text", "retake_text")) <= set(card)
