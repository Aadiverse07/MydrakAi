"""Chain tests. Every fixture is synthetic; outcomes prove offline
wiring only, never live behavior or diagnosis."""

import json
from pathlib import Path

import pytest

from mydrak.sam.chain import ChainOutcome, run_offline_chain

W, H = 640, 480


def doc(*records):
    return "<0f>" + ",".join(records)


def rec(id=0):
    return (f"{id}<|box;x1=10;y1=20;x2=100;y2=200;w={W};h={H}|>"
            f"<|mask;x=0;y=0;data=120,160,~sYntH3t1c|>")


def run(raw, **kwargs):
    return run_offline_chain(raw, expected_width=W, expected_height=H, **kwargs)


def test_valid_frames_need_review_masks_opaque():
    out = run(json.dumps({"output_text": doc(rec(), rec(1))}))
    assert out == ChainOutcome(decision="manual-review", severity_pct=None,
                               frames_found=2, review_required=True,
                               reason="masks-opaque", detail=out.detail)
    assert out.detail != ""


def test_zero_match_is_no_findings_not_diagnosis():
    out = run(json.dumps({"output": [{"type": "message",
                                      "content": [{"type": "output_text",
                                                   "text": ""}]}]}))
    assert out.decision == "no-findings"
    assert out.review_required is False
    assert out.frames_found == 0 and out.severity_pct is None


def test_empty_output_requires_review():
    out = run(json.dumps({"output": []}))
    assert (out.decision, out.review_required, out.reason) == (
        "manual-review", True, "no-output-texts")


def test_rejected_text_requires_review_without_echo():
    marker = "synthetic-chain-marker"
    out = run(json.dumps({"output_text": "<0f>," + marker}))
    assert out.reason == "text-rejected"
    assert out.review_required is True and out.frames_found == 0
    assert marker not in out.detail


def test_malformed_envelope_requires_review():
    out = run("{oops")
    assert out.reason == "unusable-envelope"
    assert out.review_required is True
    out = run(json.dumps({"error": {"message": "synthetic-provider-boom"}}))
    assert out.reason == "unusable-envelope"
    assert "synthetic-provider-boom" not in out.detail


def test_invalid_dimensions_require_review():
    out = run_offline_chain(json.dumps({"output_text": doc(rec())}),
                            expected_width=0, expected_height=H)
    assert out.reason == "text-rejected" and out.review_required is True


def test_severity_never_fabricated():
    raws = [
        json.dumps({"output_text": doc(rec())}),
        json.dumps({"output_text": ""}),
        json.dumps({"output": []}),
        json.dumps({"output_text": "<0f>,junk"}),
        "{oops",
    ]
    for raw in raws:
        assert run(raw).severity_pct is None


def test_no_mask_synthesis_in_chain():
    source = (Path(__file__).resolve().parents[1] / "src" / "mydrak"
              / "sam" / "chain.py").read_text()
    imports = [line for line in source.splitlines()
               if line.startswith(("import ", "from "))]
    assert not any("BinaryMask" in line for line in imports)
    assert not any("mask_severity" in line for line in imports)
    assert not any("synthetic" in line for line in imports)


def test_deterministic():
    raw = json.dumps({"output_text": doc(rec(3))})
    assert run(raw) == run(raw)


def test_envelope_cap_plumbed():
    out = run_offline_chain(json.dumps({"output_text": "x" * 40}),
                            expected_width=W, expected_height=H,
                            envelope_max_chars=30)
    assert out.reason == "unusable-envelope" and out.review_required is True
    out = run_offline_chain(json.dumps({"output_text": doc(rec())}),
                            expected_width=W, expected_height=H,
                            envelope_max_chars=True)
    assert out.reason == "unusable-envelope"
