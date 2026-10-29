"""Envelope-parser tests. All fixtures are synthetic and UNVERIFIED as
raw provider JSON: they exercise the offline boundary only and prove no
live compatibility."""

import json
from pathlib import Path

import pytest

from mydrak.sam.envelope import (
    MAX_OUTPUT_TEXTS,
    SamEnvelope,
    SamEnvelopeError,
    parse_response_envelope,
)


def _message(text, extra_part=None):
    parts = [{"type": "output_text", "text": text}]
    if extra_part is not None:
        parts.append(extra_part)
    return {"type": "message", "content": parts}


def test_top_level_convenience_shape():
    out = parse_response_envelope(json.dumps({"output_text": "<0f>", "id": "resp-1"}))
    assert out == SamEnvelope(texts=("<0f>",), request_id="resp-1",
                              shape="top-level-output-text")


def test_top_level_empty_text_accepted():
    out = parse_response_envelope(json.dumps({"output_text": ""}))
    assert out.texts == ("",) and out.request_id is None


def test_top_level_non_string_rejected():
    with pytest.raises(SamEnvelopeError):
        parse_response_envelope(json.dumps({"output_text": 123}))


def test_message_items_shape():
    body = {"id": "resp-2", "output": [
        _message("<0f>", {"type": "refusal", "refusal": "x"}),
        {"type": "message", "content": [{"type": "output_text", "text": ""}]},
    ]}
    out = parse_response_envelope(json.dumps(body))
    assert out.texts == ("<0f>", "")
    assert out.request_id == "resp-2"
    assert out.shape == "output-message-items"


def test_explicit_empty_output_list():
    out = parse_response_envelope(json.dumps({"output": []}))
    assert out.texts == ()


def test_missing_output_rejected():
    with pytest.raises(SamEnvelopeError, match="no output text found"):
        parse_response_envelope(json.dumps({"id": "resp-3"}))
    with pytest.raises(SamEnvelopeError, match="no output text found"):
        parse_response_envelope(json.dumps({"output": None}))


def test_non_list_output_rejected():
    with pytest.raises(SamEnvelopeError, match="malformed"):
        parse_response_envelope(json.dumps({"output": {"type": "message"}}))


def test_non_dict_item_rejected():
    with pytest.raises(SamEnvelopeError, match="malformed"):
        parse_response_envelope(json.dumps({"output": ["oops"]}))


def test_non_list_content_rejected():
    with pytest.raises(SamEnvelopeError, match="malformed"):
        parse_response_envelope(
            json.dumps({"output": [{"type": "message", "content": "x"}]}))


def test_non_string_text_rejected():
    with pytest.raises(SamEnvelopeError, match="malformed"):
        parse_response_envelope(json.dumps({"output": [_message(42)]}))


def test_zero_texts_from_nonempty_output_rejected():
    reasoning_only = {"output": [{"type": "reasoning", "content": []}]}
    with pytest.raises(SamEnvelopeError, match="no output text found"):
        parse_response_envelope(json.dumps(reasoning_only))
    empty_content = {"output": [{"type": "message", "content": []}]}
    with pytest.raises(SamEnvelopeError, match="no output text found"):
        parse_response_envelope(json.dumps(empty_content))


def test_provider_error_indicated():
    marker = "synthetic-provider-marker"
    with pytest.raises(SamEnvelopeError, match="provider error indicated"):
        parse_response_envelope(
            json.dumps({"error": {"code": "x", "message": marker}}))
    try:
        parse_response_envelope(json.dumps({"error": {"message": marker}}))
    except SamEnvelopeError as exc:
        assert marker not in str(exc)
    # Falsy error values do not mask real output.
    out = parse_response_envelope(
        json.dumps({"error": None, "output_text": "<0f>"}))
    assert out.texts == ("<0f>",)


def test_malformed_and_empty_replies_rejected():
    for raw in ("", "   ", "{oops", "[1, 2]", "42", "null"):
        with pytest.raises(SamEnvelopeError):
            parse_response_envelope(raw)
    for raw in (None, b"{}", {"output": []}, 3.5):
        with pytest.raises(SamEnvelopeError):
            parse_response_envelope(raw)


def test_oversized_reply_rejected():
    with pytest.raises(SamEnvelopeError, match="input-size cap"):
        parse_response_envelope(json.dumps({"output_text": "x" * 40}), max_chars=30)
    with pytest.raises(SamEnvelopeError, match="input-size cap"):
        parse_response_envelope("{}", max_chars=True)


def test_too_many_texts_rejected():
    body = {"output": [_message(f"<{i}f>") for i in range(MAX_OUTPUT_TEXTS + 1)]}
    with pytest.raises(SamEnvelopeError, match="too many"):
        parse_response_envelope(json.dumps(body))


def test_request_id_validation():
    with pytest.raises(SamEnvelopeError, match="identifier"):
        parse_response_envelope(json.dumps({"output": [], "id": 7}))
    with pytest.raises(SamEnvelopeError, match="identifier"):
        parse_response_envelope(json.dumps({"output": [], "id": ""}))
    with pytest.raises(SamEnvelopeError, match="identifier"):
        parse_response_envelope(json.dumps({"output": [], "id": "x" * 201}))
    out = parse_response_envelope(json.dumps({"output": [], "id": None}))
    assert out.request_id is None


def test_deterministic_and_separate_from_segmentation():
    raw = json.dumps({"output": [_message("<0f>")]})
    assert parse_response_envelope(raw) == parse_response_envelope(raw)
    source = (Path(__file__).resolve().parents[1] / "src" / "mydrak"
              / "sam" / "envelope.py").read_text()
    assert "import mydrak" not in source
    assert "from mydrak" not in source
    assert "synthetic-grid" not in source
    assert "urllib" not in source
