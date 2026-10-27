"""Offline SAM output parser tests. Synthetic fixtures only: no network, SDK,
media, credentials, or private data anywhere in this file."""

from pathlib import Path

import pytest

from mydrak.sam.output import (
    SamLimits,
    SamOutputError,
    SamSegmentation,
    parse_sam_output,
)

FRAME = {"width": 800, "height": 600}


def mask(**over):
    base = {"width": 800, "height": 600, "encoding": "opaque-test-encoding", "data": "PAYLOAD"}
    base.update(over)
    return base


def obj(**over):
    base = {"id": "leaf-1", "box": [10, 20, 100, 200], "mask": mask()}
    base.update(over)
    return base


def doc(*objects, frame=None):
    return {"image": dict(frame or FRAME), "objects": list(objects)}


def tiny_limits(**over):
    base = dict(max_dimension=20000, max_objects=256, max_id_len=128, max_encoding_len=64, max_mask_chars=64)
    base.update(over)
    return SamLimits(**base)


# --- valid input, including boxes, mask dims, payload, zero-match ---


def test_valid_single_object():
    out = parse_sam_output(doc(obj(score=0.9)))
    assert isinstance(out, SamSegmentation)
    assert (out.image_width, out.image_height) == (800, 600)
    assert out.match_count == 1
    (found,) = out.objects
    assert found.id == "leaf-1"
    assert found.box == (10.0, 20.0, 100.0, 200.0)
    assert (found.mask.width, found.mask.height) == (800, 600)
    assert found.mask.encoding == "opaque-test-encoding"
    assert found.mask.data == "PAYLOAD"
    assert found.score == pytest.approx(0.9)


def test_valid_multiple_objects_and_crop_mask():
    out = parse_sam_output(doc(obj(), obj(id="lesion-2", box=[0, 0, 799, 599], mask=mask(width=400, height=300))))
    assert out.match_count == 2
    assert out.objects[1].mask.width == 400


def test_zero_match_result_is_valid():
    out = parse_sam_output(doc())
    assert out.match_count == 0
    assert out.objects == ()


def test_score_is_optional_and_int_score_accepted():
    assert parse_sam_output(doc(obj(score=1))).objects[0].score == 1.0
    assert parse_sam_output(doc(obj())).objects[0].score is None


def test_parse_is_deterministic_and_result_immutable():
    first = parse_sam_output(doc(obj()))
    second = parse_sam_output(doc(obj()))
    assert first == second
    with pytest.raises(Exception):
        first.objects[0].id = "mutated"  # frozen dataclass


# --- malformed top level and frame ---


@pytest.mark.parametrize("bad", [None, "text", 42, ["objects"], b"bytes"])
def test_non_mapping_document_rejected(bad):
    with pytest.raises(SamOutputError):
        parse_sam_output(bad)


def test_missing_and_unknown_top_keys_rejected():
    with pytest.raises(SamOutputError):
        parse_sam_output({"image": FRAME})
    with pytest.raises(SamOutputError):
        parse_sam_output({"image": FRAME, "objects": [], "wire": "unexpected"})


@pytest.mark.parametrize("frame", [
    {"width": 0, "height": 600}, {"width": -800, "height": 600},
    {"width": True, "height": 600}, {"width": 800.5, "height": 600},
    {"width": "800", "height": 600}, {"width": 800},
    {"width": 20001, "height": 600},
])
def test_bad_frame_rejected(frame):
    with pytest.raises(SamOutputError):
        parse_sam_output({"image": frame, "objects": []})


# --- object identity and count limits ---


def test_non_list_objects_and_non_mapping_item_rejected():
    with pytest.raises(SamOutputError):
        parse_sam_output(doc(frame=FRAME) | {"objects": {}})
    with pytest.raises(SamOutputError):
        parse_sam_output({"image": FRAME, "objects": ["leaf-1"]})


def test_too_many_objects_rejected_with_custom_limit():
    with pytest.raises(SamOutputError):
        parse_sam_output(doc(obj(), obj(id="b"), obj(id="c")), limits=tiny_limits(max_objects=2))


def test_missing_and_unknown_object_keys_rejected():
    bad = obj()
    del bad["box"]
    with pytest.raises(SamOutputError):
        parse_sam_output(doc(bad))
    with pytest.raises(SamOutputError):
        parse_sam_output(doc(obj(prompt="leaf", score=0.5)))


@pytest.mark.parametrize("bad_id", ["", 7, None, "x" * 129])
def test_bad_object_id_rejected(bad_id):
    with pytest.raises(SamOutputError):
        parse_sam_output(doc(obj(id=bad_id)))


def test_error_never_echoes_untrusted_id():
    long_id = "sensitive-" + "x" * 200
    with pytest.raises(SamOutputError) as excinfo:
        parse_sam_output(doc(obj(id=long_id)))
    assert long_id not in str(excinfo.value)


# --- boxes: source-pixel geometry ---


@pytest.mark.parametrize("box", [
    [100, 20, 10, 200],      # inverted x
    [10, 200, 100, 20],      # inverted y
    [10, 20, 10, 200],       # zero width
    [10, 20, 100, 20],       # zero height
    [-1, 20, 100, 200],      # negative
    [10, 20, 801, 200],      # past frame width
    [10, 20, 100, 601],      # past frame height
    [10, 20, 100],           # too short
    [10, 20, 100, 200, 5],   # too long
    "10,20,100,200",         # not a list
    [10, "20", 100, 200],    # string element
    [True, 20, 100, 200],    # bool element
    [float("nan"), 20, 100, 200],
    [10, 20, float("inf"), 200],
    [None, 20, 100, 200],
])
def test_malformed_boxes_rejected(box):
    with pytest.raises(SamOutputError):
        parse_sam_output(doc(obj(box=box)))


def test_float_pixel_box_accepted():
    out = parse_sam_output(doc(obj(box=[10.5, 20.25, 100.75, 200.5])))
    assert out.objects[0].box == (10.5, 20.25, 100.75, 200.5)


# --- masks: dims, opaque encoding/payload ---


@pytest.mark.parametrize("bad_mask", [
    mask(width=0), mask(height=-3), mask(width=True), mask(height=600.5),
    mask(width=801), mask(height=601),  # larger than the frame
    mask(encoding=""), mask(encoding=123), mask(encoding="e" * 65),
    mask(data=""), mask(data=None), mask(data=["PAYLOAD"]),
])
def test_malformed_masks_rejected(bad_mask):
    with pytest.raises(SamOutputError):
        parse_sam_output(doc(obj(mask=bad_mask)))


def test_oversized_payload_rejected_with_custom_limit():
    with pytest.raises(SamOutputError):
        parse_sam_output(doc(obj(mask=mask(data="P" * 65))), limits=tiny_limits(max_mask_chars=64))


def test_missing_and_unknown_mask_keys_rejected():
    short = {"width": 800, "height": 600, "encoding": "x"}
    with pytest.raises(SamOutputError):
        parse_sam_output(doc(obj(mask=short)))
    with pytest.raises(SamOutputError):
        parse_sam_output(doc(obj(mask=mask(rle="unexpected"))))


def test_payload_is_never_decoded_or_interpreted():
    blob = "!!!not-valid-base64-or-rle!!!"
    out = parse_sam_output(doc(obj(mask=mask(data=blob, encoding="unverified-encoding"))))
    assert out.objects[0].mask.data == blob


# --- scores ---


@pytest.mark.parametrize("score", [-0.1, 1.1, float("nan"), float("inf"), "high", True])
def test_bad_scores_rejected(score):
    with pytest.raises(SamOutputError):
        parse_sam_output(doc(obj(score=score)))


def test_explicit_null_score_rejected_while_omitted_stays_valid():
    with pytest.raises(SamOutputError, match="not null"):
        parse_sam_output(doc(obj(score=None)))
    assert parse_sam_output(doc(obj())).objects[0].score is None


@pytest.mark.parametrize("box", [
    [0, 0, 10**1000, 10],
    [-(10**1000), 0, 10, 10],
    [0, 0, 10, 10**1000],
    [10**1000, 10**1000, 10**1000 + 1, 10**1000 + 1],
])
def test_huge_int_box_coordinates_normalized_to_output_error(box):
    with pytest.raises(SamOutputError):
        parse_sam_output(doc(obj(box=box)))


def test_huge_int_score_normalized_to_output_error():
    with pytest.raises(SamOutputError):
        parse_sam_output(doc(obj(score=10**1000)))


# --- error type and offline guard ---


def test_error_is_a_value_error():
    assert issubclass(SamOutputError, ValueError)


def test_parser_module_uses_no_network_or_sdk():
    source = (Path(__file__).resolve().parents[1] / "src" / "mydrak" / "sam" / "output.py").read_text()
    for token in ("urllib", "http.client", "socket", "subprocess", "requests", "httpx", "openai", "telegram", "boto"):
        assert token not in source
