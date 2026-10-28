"""Response-text parser tests. Every fixture is a hand-built synthetic
documentation fixture following the published grammar shape; none is a real
SAM response, and none proves wire compatibility."""

from pathlib import Path

import pytest

from mydrak.sam.adapter import grid_mask_to_binary
from mydrak.sam.output import SamLimits
from mydrak.sam.response_text import (
    MAX_OUTPUT_CHARS,
    SamFrame,
    SamResponseError,
    parse_response_text,
)
from mydrak.sam.scores import SegmentationEvalError

W, H = 640, 480
# Mask raster dims must be strictly smaller than the source dims.
MH, MW = 120, 160


def box(x1=10, y1=20, x2=100, y2=200, w=W, h=H, conf=None):
    text = f"<|box;x1={x1};y1={y1};x2={x2};y2={y2};w={w};h={h}"
    return text + (f";c={conf}" if conf is not None else "") + "|>"


def mask(h=MH, w=MW, enc="~", payload="sYntH3t1c", conf=None, x=0, y=0):
    text = f"<|mask;x={x};y={y};"
    if conf is not None:
        text += f"c={conf};"
    return text + f"data={h},{w},{enc}{payload}|>"


def doc(*records):
    return "<0f>" + ",".join(records)


def rec(id=0, box_text=None, mask_text=None):
    return f"{id}" + (box_text or box()) + (mask_text or mask())


def parse(text, width=W, height=H, **kwargs):
    return parse_response_text(text, expected_width=width, expected_height=height, **kwargs)


def test_valid_single_object():
    out = parse(doc(rec()))
    assert isinstance(out, SamFrame)
    assert (out.frame_index, out.image_width, out.image_height) == (0, W, H)
    assert out.match_count == 1
    (found,) = out.objects
    assert found.object_id == 0
    assert (found.box.x1, found.box.y1, found.box.x2, found.box.y2) == (10, 20, 100, 200)
    assert (found.box.width, found.box.height) == (W, H)
    assert found.box.confidence is None
    assert (found.mask.origin_x, found.mask.origin_y) == (0, 0)
    assert (found.mask.height, found.mask.width) == (MH, MW)
    assert found.mask.encoding == "~"
    assert found.mask.payload == "sYntH3t1c"
    assert found.mask.confidence is None


def test_valid_multiple_objects_sparse_ids():
    out = parse(doc(rec(id=0), rec(id=7), rec(id=42)))
    assert [obj.object_id for obj in out.objects] == [0, 7, 42]
    assert out.match_count == 3


def test_zero_match_empty_output():
    out = parse("", width=320, height=240)
    assert out.match_count == 0
    assert out.objects == ()
    assert (out.image_width, out.image_height) == (320, 240)


@pytest.mark.parametrize("text", [" ", "   ", "\t\n ", "\n", "\r\n"])
def test_whitespace_only_output_rejected(text):
    with pytest.raises(SamResponseError):
        parse(text)


def test_incomplete_frame_syntax_rejected():
    # Only an empty output is a zero-match: a bare marker, a trailing
    # separator, and a leading separator are all malformed.
    with pytest.raises(SamResponseError, match="no records"):
        parse("<0f>")
    with pytest.raises(SamResponseError, match="no records"):
        parse("<0f>   ")
    with pytest.raises(SamResponseError):
        parse("<0f>,")
    with pytest.raises(SamResponseError, match="malformed object id"):
        parse("<0f>," + rec())
    with pytest.raises(SamResponseError):
        parse("<0f>,," + rec())


def test_tilde_and_bang_encodings():
    assert parse(doc(rec(mask_text=mask(enc="~")))).objects[0].mask.encoding == "~"
    assert parse(doc(rec(mask_text=mask(enc="!")))).objects[0].mask.encoding == "!"


def test_confidence_present_and_agreeing():
    out = parse(doc(rec(box_text=box(conf="0.9"), mask_text=mask(conf="0.9"))))
    assert out.objects[0].box.confidence == pytest.approx(0.9)
    assert out.objects[0].mask.confidence == pytest.approx(0.9)


def test_confidence_mismatch_rejected():
    with pytest.raises(SamResponseError, match="disagree"):
        parse(doc(rec(box_text=box(conf="0.9"), mask_text=mask(conf="0.7"))))


@pytest.mark.parametrize("conf", ["1.5", "-0.1", "abc", "1e2", "nan"])
def test_confidence_out_of_range_or_malformed(conf):
    with pytest.raises(SamResponseError):
        parse(doc(rec(box_text=box(conf=conf))))


def test_one_sided_confidence_rejected():
    with pytest.raises(SamResponseError, match="one-sided"):
        parse(doc(rec(box_text=box(conf="0.9"))))
    with pytest.raises(SamResponseError, match="one-sided"):
        parse(doc(rec(mask_text=mask(conf="0.9"))))


def test_confidence_equal_values_accepted():
    out = parse(doc(rec(box_text=box(conf="0.90"), mask_text=mask(conf="0.9"))))
    assert out.objects[0].box.confidence == pytest.approx(0.9)


def test_nonzero_mask_origin_rejected():
    with pytest.raises(SamResponseError, match="nonzero mask origin"):
        parse(doc(rec(mask_text=mask(x=5))))
    with pytest.raises(SamResponseError, match="nonzero mask origin"):
        parse(doc(rec(mask_text=mask(y=3))))


@pytest.mark.parametrize("kwargs", [{"h": H, "w": MW}, {"h": MH, "w": W}, {"h": H, "w": W},
                                       {"h": H + 1, "w": MW}, {"h": MH, "w": W + 1}])
def test_mask_dimensions_must_be_smaller_than_source(kwargs):
    with pytest.raises(SamResponseError, match="not smaller than source"):
        parse(doc(rec(mask_text=mask(**kwargs))))


def test_mask_dimensions_just_smaller_than_source_accepted():
    out = parse(doc(rec(mask_text=mask(h=H - 1, w=W - 1))))
    assert (out.objects[0].mask.height, out.objects[0].mask.width) == (H - 1, W - 1)


@pytest.mark.parametrize("bad_id", ["-5", "+5", "٣", "1_0", "0x10", "９"])
def test_non_ascii_or_signed_ids_rejected(bad_id):
    with pytest.raises(SamResponseError, match="malformed object id"):
        parse("<0f>" + bad_id + box() + mask())


def test_extremely_long_id_rejected_without_builtin_leak():
    with pytest.raises(SamResponseError, match="malformed object id"):
        parse("<0f>" + "9" * 5000 + box() + mask())


def test_unicode_digits_in_box_and_mask_rejected():
    with pytest.raises(SamResponseError):
        parse(doc(rec(box_text=box().replace("x1=10", "x1=١٠"))))
    with pytest.raises(SamResponseError):
        parse(doc(rec(mask_text=mask().replace("data=120,", "data=١٢٠,"))))


def test_bool_and_invalid_input_size_cap_rejected():
    with pytest.raises(SamResponseError):
        parse("", max_chars=True)
    with pytest.raises(SamResponseError):
        parse("", max_chars=0)


def test_zero_object_limit_rejects_any_record():
    with pytest.raises(SamResponseError, match="more records"):
        parse(doc(rec()), limits=SamLimits(max_objects=0))


def test_valid_coordinate_boundaries():
    out = parse(doc(rec(box_text=box(x1=0, y1=0, x2=W, y2=H))))
    assert (out.objects[0].box.x1, out.objects[0].box.y2) == (0, H)


def test_source_dimension_mismatch_rejected():
    with pytest.raises(SamResponseError, match="source dimensions"):
        parse(doc(rec()), width=800, height=600)


@pytest.mark.parametrize("text", [
    "<1f>" + rec()[4:],
    "<0x>" + rec()[4:],
    rec(),
    "<0f",
    "<0f>>" + rec()[4:],
    doc(rec()) + "\n" + doc(rec()),
    "<0f>" + rec() + ",",
    "<0f>" + rec() + ",," + rec(),
    "<0f>a" + rec()[5:],
    "<0f>1.5" + rec()[5:],
    "<0f>0<|box;x1=10;y1=20;x2=100;y2=200;w=640|>" + mask(),
    "<0f>0<|box;y1=20;x1=10;x2=100;y2=200;w=640;h=480|>" + mask(),
    "<0f>0<|box;x1=10;y1=20;x2=100;y2=200;w=640;h=480;z=9|>" + mask(),
    "<0f>0<|box;x1=-1;y1=20;x2=100;y2=200;w=640;h=480|>" + mask(),
    "<0f>0<|box;x1=100;y1=20;x2=10;y2=200;w=640;h=480|>" + mask(),
    "<0f>0<|box;x1=10;y1=20;x2=641;y2=200;w=640;h=480|>" + mask(),
    "<0f>0" + box() + "<|mask;x=0;y=0;data=480,640|>",
    "<0f>0" + box() + "<|mask;x=0;y=0;data=480,640,?abc|>",
    "<0f>0" + box() + "<|mask;x=0;y=0;data=480,640,~|>",
    "<0f>0" + box() + "<|mask;x=0;y=0;data=0,640,~abc|>",
    "<0f>0" + box() + "<|mask;x=0;y=0;data=480,640,~a b|>",
    "<0f>0" + box() + "<|mask;x=0;y=0>",
    "<0f>0" + box() + "<|mask;x=0;y=0;data=480,640,~abc",
    "<0f>0" + box() + "<|mask;x=-1;y=0;data=480,640,~abc|>",
    "<0f>0" + box() + "<|mask;x=0;y=0;c=high;data=480,640,~abc|>",
    "<0f>0" + box() + "<|mask;x=0;y=0;data=480,640,~abc|>"[:-5],
])
def test_malformed_inputs_rejected(text):
    with pytest.raises(SamResponseError):
        parse(text)


def test_oversized_input_rejected_with_custom_cap():
    with pytest.raises(SamResponseError, match="input-size cap"):
        parse(doc(rec()), max_chars=64)


def test_too_many_records_rejected_with_custom_limits():
    big = doc(*[rec(id=i) for i in range(3)])
    with pytest.raises(SamResponseError, match="more records"):
        parse(big, limits=SamLimits(max_objects=2))


def test_mask_payload_limit_enforced():
    # Same input parses under default limits, proving every other field is
    # valid; only the configured payload cap rejects it.
    text = doc(rec(mask_text=mask(payload="a" * 9)))
    assert parse(text).match_count == 1
    with pytest.raises(SamResponseError, match="malformed mask payload") as excinfo:
        parse(text, limits=SamLimits(max_mask_chars=8))
    assert "aaaaaaaaa" not in str(excinfo.value)


def test_errors_never_echo_payloads():
    payload = "s3cr3t-payL0ad-VALUE"
    text = doc(rec(mask_text=mask(payload=payload))[:-2] + " ")
    with pytest.raises(SamResponseError) as excinfo:
        parse(text)
    assert payload not in str(excinfo.value)


def test_comma_heavy_payload_rejected_without_leak():
    payload = "~" + "a," * 5000 + "z"
    text = doc(rec(mask_text=mask(h=MH, w=MW, enc="~", payload=payload[1:])))
    with pytest.raises(SamResponseError) as excinfo:
        parse(text)
    assert "a,a,a" not in str(excinfo.value)


def test_unsupported_video_shapes_rejected():
    with pytest.raises(SamResponseError, match="multi-frame"):
        parse("<2f>" + rec()[4:])


def test_wire_payload_rejected_by_grid_adapter():
    payload = parse(doc(rec())).objects[0].mask
    with pytest.raises(SegmentationEvalError, match="must be a SamMask"):
        grid_mask_to_binary(payload)


def test_non_string_input_rejected():
    with pytest.raises(SamResponseError):
        parse(None)
    with pytest.raises(SamResponseError):
        parse(b"<0f>")


def test_expected_dimensions_validated():
    with pytest.raises(SamResponseError):
        parse("", width=0, height=H)
    with pytest.raises(SamResponseError):
        parse("", width=True, height=H)


def test_parser_module_uses_no_network_or_sdk():
    source = (Path(__file__).resolve().parents[1] / "src" / "mydrak" / "sam" / "response_text.py").read_text()
    for token in ("urllib", "http.client", "socket", "subprocess", "requests", "httpx", "openai", "telegram"):
        assert token not in source
