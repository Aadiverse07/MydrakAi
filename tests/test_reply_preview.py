"""Opt-in draft preview is limited to unchanged real KB drafts and local demos."""

from hashlib import sha256
from pathlib import Path

import pytest

from mydrak.kb.loader import load_disease_card, load_safety_card
from mydrak.reply.composer import ReplyError, compose_reply
from mydrak.reply import preview
from mydrak.reply.preview import (
    DRAFT_BANNER, load_demo_draft_preview, load_private_photo_settings,
)
from mydrak.workflow.followup import FollowUpError, FollowUpState, begin_followup

ROOT = Path(__file__).resolve().parents[1]
DRAFT_PATH = ROOT / "kb" / "cards" / "tomato_early_blight.yaml"
REGISTRY_PATH = ROOT / "kb" / "sources.yaml"
SAFETY = load_safety_card(ROOT / "kb" / "cards" / "general_safety.yaml")


def _draft_card():
    return load_disease_card(DRAFT_PATH)


def _approved_synthetic_card():
    # In-test text only; approval metadata is synthetic and not reviewer evidence.
    return {
        "id": "SYNTHETIC_APPROVED_TEST_ONLY",
        "status": "verified",
        "review_status": {"en": "REVIEWED", "hi": "REVIEWED"},
        "crop": "synthetic crop",
        "names": {"en": "Synthetic issue"},
        "low_risk_steps": {"en": ["Synthetic step"]},
    }


def test_preview_config_defaults_off():
    assert load_demo_draft_preview() is False


def test_private_photo_settings_default_off_and_load_local_values(tmp_path):
    config_path = tmp_path / "reply.yaml"
    config_path.write_text("demo_draft_preview: false\n", encoding="utf-8")
    assert load_private_photo_settings(config_path) == {
        "consent_notice_approved": False,
        "allow_private_upload": False,
        "private_tier1_allowed": False,
    }
    config_path.write_text(
        "consent_notice_approved: true\nallow_private_upload: true\n"
        "private_tier1_allowed: false\n",
        encoding="utf-8",
    )
    assert load_private_photo_settings(config_path) == {
        "consent_notice_approved": True,
        "allow_private_upload": True,
        "private_tier1_allowed": False,
    }


def test_local_config_setting_enables_preview_without_an_api_override(tmp_path, monkeypatch):
    config_path = tmp_path / "reply.yaml"
    config_path.write_text("demo_draft_preview: true\n", encoding="utf-8")
    monkeypatch.setattr(preview, "CONFIG_PATH", config_path)
    card = _draft_card()
    reply = compose_reply(
        "answer", card=card, card_path=DRAFT_PATH, safety_card=SAFETY,
        confidence="not sure",
    )
    assert reply.startswith(DRAFT_BANNER + "\n")


def test_default_off_rejects_draft_cards_in_composer_and_followup():
    card = _draft_card()
    with pytest.raises(ReplyError, match="not approved"):
        compose_reply("answer", card=card, safety_card=SAFETY, confidence="not sure")
    with pytest.raises(FollowUpError, match="not approved"):
        begin_followup(
            FollowUpState(), card=card, safety_card=SAFETY,
            question_id=card["follow_up_questions"][0]["id"],
        )


def test_preview_renders_real_draft_in_english_with_banner_through_both_paths():
    card = _draft_card()
    source_hash = sha256(DRAFT_PATH.read_bytes()).hexdigest()
    registry_hash = sha256(REGISTRY_PATH.read_bytes()).hexdigest()
    answer = compose_reply(
        "answer", card=card, safety_card=SAFETY, confidence="not sure",
        demo_draft_preview=True, public_mode=False, card_path=DRAFT_PATH,
    )
    assert answer.startswith(DRAFT_BANNER + "\n")

    question = card["follow_up_questions"][0]
    prompt = begin_followup(
        FollowUpState(), card=card, safety_card=SAFETY,
        question_id=question["id"], demo_draft_preview=True,
        public_mode=False, card_path=DRAFT_PATH,
    )
    assert prompt.message.startswith(DRAFT_BANNER + "\n")
    assert sha256(DRAFT_PATH.read_bytes()).hexdigest() == source_hash
    assert sha256(REGISTRY_PATH.read_bytes()).hexdigest() == registry_hash


def test_hindi_is_rejected_for_unreviewed_draft_even_in_preview():
    with pytest.raises(ReplyError, match="Hindi card content is not reviewed"):
        compose_reply(
            "answer", card=_draft_card(), safety_card=SAFETY,
            language="hi", confidence="not sure", demo_draft_preview=True,
            card_path=DRAFT_PATH,
        )


def test_preview_is_refused_in_public_mode_for_composer_and_followup():
    card = _draft_card()
    with pytest.raises(ReplyError, match="refused in public mode"):
        compose_reply(
            "answer", card=card, safety_card=SAFETY, confidence="not sure",
            demo_draft_preview=True, public_mode=True, card_path=DRAFT_PATH,
        )
    with pytest.raises(FollowUpError, match="refused in public mode"):
        begin_followup(
            FollowUpState(), card=card, safety_card=SAFETY,
            question_id=card["follow_up_questions"][0]["id"],
            demo_draft_preview=True, public_mode=True, card_path=DRAFT_PATH,
        )


def test_verified_reviewed_synthetic_card_has_no_preview_banner():
    reply = compose_reply(
        "answer", card=_approved_synthetic_card(), safety_card=SAFETY,
        confidence="not sure", demo_draft_preview=True,
    )
    assert not reply.startswith(DRAFT_BANNER)
    assert "Synthetic issue" in reply


def test_preview_rejects_synthetic_fixture_and_non_kb_paths():
    card = {**_approved_synthetic_card(), "status": "draft",
            "review_status": {"en": "UNREVIEWED", "hi": "UNREVIEWED"}}
    card["id"] = "SYNTHETIC_TEST"
    with pytest.raises(ReplyError, match="genuine card from kb/cards"):
        compose_reply(
            "answer", card=card, safety_card=SAFETY, confidence="not sure",
            demo_draft_preview=True, card_path=ROOT / "tests/fixtures/kb/SYNTHETIC_TEST.yaml",
        )
