"""Batch 1 draft disease cards: structure, citation and review-gate checks (offline)."""
import copy
from pathlib import Path

import pytest
import yaml

from mydrak.kb.loader import load_disease_card, load_source_registry, validate_disease_card

ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT / "kb" / "cards"
EXPECTED_IDS = {
    "tomato_early_blight", "tomato_septoria_leaf_spot", "tomato_leaf_curl",
    "tomato_bacterial_wilt", "tomato_fusarium_wilt",
    "potato_late_blight", "potato_early_blight",
    "soybean_charcoal_rot", "soybean_yellow_mosaic", "soybean_rust",
}
BATCH1_SOURCES = {
    "icar_tomato_hort_ecourse", "icar_iivr_viruses_tb75",
    "icar_cpri_gap_bulletin_108", "icar_iisr_soybean_bulletin_17",
}


def _card_paths():
    return sorted(p for p in CARDS_DIR.glob("*.yaml") if p.name != "general_safety.yaml")


def _raw(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_exactly_ten_batch1_cards_present():
    assert {p.stem for p in _card_paths()} == EXPECTED_IDS


@pytest.mark.parametrize("path", _card_paths(), ids=lambda p: p.stem)
def test_card_loads_with_production_loader(path):
    card = load_disease_card(path)
    assert card["id"] == path.stem


@pytest.mark.parametrize("path", _card_paths(), ids=lambda p: p.stem)
def test_card_review_gates_stay_closed(path):
    card = _raw(path)
    registry = load_source_registry()
    assert card["status"] == "draft"
    assert card["review_status"] == {"en": "UNREVIEWED", "hi": "UNREVIEWED"}
    assert card["reviewed_by"] is None
    assert card["language_reviewers"] == {"en": None, "hi": None}
    assert card["chemical_options"] == []
    assert all(registry[source_id]["verified_by_user"] is True for source_id in card["sources"])


@pytest.mark.parametrize("path", _card_paths(), ids=lambda p: p.stem)
def test_card_sources_resolve_and_are_user_verified(path):
    registry = load_source_registry()
    card = _raw(path)
    for source_id in card["sources"]:
        entry = registry[source_id]
        assert source_id in BATCH1_SOURCES
        assert entry["retrieved"] and entry["title_verified"]
        assert entry["verified_by_user"] is True
    assert {r["source_id"] for r in card["claim_sources"]} == set(card["sources"])


@pytest.mark.parametrize("path", _card_paths(), ids=lambda p: p.stem)
def test_card_citations_have_printed_page_and_section(path):
    for ref in _raw(path)["claim_sources"]:
        assert ref["page"].strip() and ref["section"].strip()
        assert ref["page"] != "UNVERIFIED"


def test_registry_records_discrepancies_and_authorship_caveat():
    registry = load_source_registry()
    assert "Bulletin No. 16" in registry["icar_iisr_soybean_bulletin_17"]["notes"]
    notes = registry["icar_tomato_hort_ecourse"]["notes"]
    assert "RVSKVV" in notes and "NOT" in notes


def test_leaf_curl_and_yellow_mosaic_do_not_name_a_virus_species():
    forbidden = ("ToLCV", "New Delhi virus", "MYMIV", "MYMV", "Mungbean")
    for stem in ("tomato_leaf_curl", "soybean_yellow_mosaic"):
        text = (CARDS_DIR / f"{stem}.yaml").read_text(encoding="utf-8")
        assert not any(term in text for term in forbidden)


@pytest.mark.parametrize("path", _card_paths(), ids=lambda p: p.stem)
def test_missing_citation_fails_safely(path):
    card = _raw(path)
    card["claim_sources"].pop()
    with pytest.raises(ValueError, match="claim source coverage mismatch"):
        validate_disease_card(card)


@pytest.mark.parametrize("path", _card_paths(), ids=lambda p: p.stem)
def test_unknown_source_id_fails_safely(path):
    card = _raw(path)
    card["claim_sources"][0]["source_id"] = "not_in_registry"
    card["sources"] = sorted({r["source_id"] for r in card["claim_sources"]})
    with pytest.raises(ValueError, match="unknown source_id"):
        validate_disease_card(card)


@pytest.mark.parametrize("path", _card_paths(), ids=lambda p: p.stem)
def test_draft_cannot_be_promoted_while_hindi_unreviewed(path):
    card = copy.deepcopy(_raw(path))
    card["status"] = "verified"
    with pytest.raises(ValueError, match="verified card cannot contain an UNREVIEWED language"):
        validate_disease_card(card)


def test_general_safety_card_is_untouched_and_still_loads():
    from mydrak.kb.loader import load_safety_card
    assert load_safety_card(CARDS_DIR / "general_safety.yaml")["id"] == "general_safety"
