"""Adapter tests. Fixtures are synthetic documentation-grammar strings;
they prove offline wiring only, not live provider behavior."""

import pytest

from mydrak.sam.envelope import SamEnvelope
from mydrak.sam.frames import FrameAdaptation, adapt_envelope
from mydrak.sam.response_text import SamFrame, SamResponseError

W, H = 640, 480


def doc(*records):
    return "<0f>" + ",".join(records)


def rec(id=0):
    return (f"{id}<|box;x1=10;y1=20;x2=100;y2=200;w={W};h={H}|>"
            f"<|mask;x=0;y=0;data=120,160,~sYntH3t1c|>")


def envelope(*texts):
    return SamEnvelope(texts=tuple(texts), request_id=None, shape="test")


def adapt(texts, **kwargs):
    return adapt_envelope(envelope(*texts), expected_width=W,
                         expected_height=H, **kwargs)


def test_single_text_parses():
    out = adapt([doc(rec())])
    assert out == FrameAdaptation(
        frames=out.frames, review_required=False, reason="parsed", detail="")
    (frame,) = out.frames
    assert isinstance(frame, SamFrame)
    assert (frame.image_width, frame.image_height, frame.match_count) == (W, H, 1)


def test_multiple_texts_parse_in_order():
    out = adapt([doc(rec(0)), doc(rec(7)), ""])
    assert [f.match_count for f in out.frames] == [1, 1, 0]
    assert out.review_required is False


def test_empty_string_text_is_zero_match():
    out = adapt([""])
    (frame,) = out.frames
    assert frame.match_count == 0
    assert out.review_required is False


def test_empty_text_list_requires_review():
    out = adapt([])
    assert out == FrameAdaptation(frames=(), review_required=True,
                                  reason="no-output-texts", detail=out.detail)
    assert out.detail != ""


def test_malformed_text_requires_review_without_echo():
    marker = "synthetic-bad-marker"
    out = adapt(["<0f>," + marker])
    assert out.frames == ()
    assert out.review_required is True
    assert out.reason == "text-rejected"
    assert marker not in out.detail
    assert out.detail != ""


def test_mixed_valid_and_malformed_requires_review():
    out = adapt([doc(rec()), "not a frame"])
    assert out.frames == ()
    assert out.review_required is True


def test_dimension_problems_require_review():
    for kwargs in ({"expected_width": 0, "expected_height": H},
                   {"expected_width": "640", "expected_height": H},
                   {"expected_width": 800, "expected_height": H}):
        out = adapt_envelope(envelope(doc(rec())), **kwargs)
        assert out.frames == ()
        assert out.review_required is True
        assert out.reason == "text-rejected"


def test_non_envelope_input_rejected():
    with pytest.raises(SamResponseError):
        adapt_envelope({"texts": []}, expected_width=W, expected_height=H)


def test_limits_preserved():
    for kwargs in ({"max_chars": True}, {"max_chars": 10}):
        out = adapt([doc(rec())], **kwargs)
        assert out.reason == "text-rejected" and out.review_required is True
        assert out.frames == ()


def test_deterministic():
    assert adapt([doc(rec()), ""]) == adapt([doc(rec()), ""])
