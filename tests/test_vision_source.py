"""Local image-header reader tests. Fixtures are byte strings built in-test
with struct/zlib and written to tmp_path; no binaries in Git, no real media,
no network. Fixtures intentionally stop after the header, matching the
header-only scope: the reader never looks past dimensions."""

import os
import struct
import traceback
import zlib
from pathlib import Path
from unittest.mock import Mock

import pytest

from mydrak.intake.adapter import IntakeError, process_intake
from mydrak.kb.loader import load_safety_card
from mydrak.privacy.data_policy import DataClass, ProcessingEvidence, ProviderMode
from mydrak.vision.source import MAX_IMAGE_BYTES, read_local_image

from conftest import REPO_ROOT

SAFETY = load_safety_card(REPO_ROOT / "kb" / "cards" / "general_safety.yaml")

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def png_bytes(width=800, height=600, chunk=b"IHDR", length=13):
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return PNG_SIG + struct.pack(">I", length) + chunk + ihdr


def sof_segment(marker=0xC0, width=800, height=600, precision=8, components=3):
    body = struct.pack(">BHHB", precision, height, width, components)
    body += b"\x01\x11\x00" * components
    return b"\xff" + bytes((marker,)) + struct.pack(">H", 8 + 3 * components) + body


def jpeg_bytes(width=800, height=600, marker=0xC0, prefix=b"", components=3):
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"\x00" * 14
    return b"\xff\xd8" + prefix + app0 + sof_segment(marker, width, height, components=components) + b"\xff\xd9"


def write(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_valid_png_dimensions(tmp_path):
    out = read_local_image(write(tmp_path, "a.png", png_bytes(800, 600) + b"\x00" * 100))
    assert (out.format, out.width, out.height) == ("png", 800, 600)
    assert out.size_bytes == 29 + 100


def test_valid_jpeg_baseline_and_progressive(tmp_path):
    assert read_local_image(write(tmp_path, "b.jpg", jpeg_bytes(marker=0xC0))).width == 800
    out = read_local_image(write(tmp_path, "c.jpg", jpeg_bytes(marker=0xC2, width=100, height=50)))
    assert (out.format, out.width, out.height) == ("jpeg", 100, 50)


@pytest.mark.parametrize("data", [
    b"not an image",
    PNG_SIG + b"\x00" * 10,
    PNG_SIG + struct.pack(">I", 13) + b"IDAT" + b"\x00" * 13,
    PNG_SIG + struct.pack(">I", 12) + b"IHDR" + b"\x00" * 12,
    png_bytes(width=0),
    png_bytes(width=20001),
    b"\xff\xd9",
    b"\xff\xc0" + b"\x00" * 20,
    b"\xff\xd8\xff\xd9",
    b"\xff\xd8\xff\xda\x00\x08" + b"\x00" * 6,
    b"\xff\xd8\xff\xc0\x00",
    b"\xff\xd8\xff\xc0\x00\x06" + b"\x00" * 4,
    b"\xff\xd8\xff\xc4" + struct.pack(">H", 30) + b"\x00" * 28 + b"\xff\xd9",
])
def test_malformed_inputs_rejected(tmp_path, data):
    with pytest.raises(IntakeError):
        read_local_image(write(tmp_path, "bad.bin", data))


def test_sof_structure_mismatch_rejected(tmp_path):
    good = bytearray(jpeg_bytes())
    length_pos = good.index(b"\xff\xc0") + 1
    struct.pack_into(">H", good, length_pos, 14)
    with pytest.raises(IntakeError):
        read_local_image(write(tmp_path, "m.jpg", bytes(good)))


def test_bad_precision_and_component_count_rejected(tmp_path):
    with pytest.raises(IntakeError):
        read_local_image(write(tmp_path, "p.jpg", b"\xff\xd8" + sof_segment(precision=4)))
    with pytest.raises(IntakeError):
        read_local_image(write(tmp_path, "q.jpg", b"\xff\xd8" + sof_segment(components=0)))


def test_nested_soi_rejected_with_specific_message(tmp_path):
    nested = b"\xff\xd8" + b"\xff\xd8\x00\x02" + sof_segment() + b"\xff\xd9"
    with pytest.raises(IntakeError, match="nested Start Of Image"):
        read_local_image(write(tmp_path, "nested.jpg", nested))


def _formatted_traceback(excinfo):
    return "".join(traceback.format_exception(excinfo.value))


def test_stat_failure_normalized_to_intake_error(tmp_path, monkeypatch):
    path = write(tmp_path, "s.png", png_bytes())
    def fail_stat(p):
        raise OSError("simulated stat failure")
    monkeypatch.setattr(os.path, "getsize", fail_stat)
    with pytest.raises(IntakeError, match="could not be inspected") as excinfo:
        read_local_image(path)
    text = _formatted_traceback(excinfo)
    assert "simulated stat failure" not in text
    assert str(path) not in text


def test_read_failure_normalized_to_intake_error(tmp_path, monkeypatch):
    path = write(tmp_path, "r.png", png_bytes())
    def fail_open(*args, **kwargs):
        raise OSError("simulated read failure")
    monkeypatch.setattr("builtins.open", fail_open)
    with pytest.raises(IntakeError, match="could not be read") as excinfo:
        read_local_image(path)
    text = _formatted_traceback(excinfo)
    assert "simulated read failure" not in text
    assert str(path) not in text


def test_read_bounded_to_cap_plus_one_and_opened_once(tmp_path, monkeypatch):
    """The cap must hold from one bounded read even when stat reports small."""
    blob = png_bytes() + b"\x00" * (MAX_IMAGE_BYTES + 2 - 29)
    path = write(tmp_path, "grown.png", blob)
    monkeypatch.setattr(os.path, "getsize", lambda p: 64)
    real_open = open
    calls = {"opens": 0, "sizes": []}

    class CountingHandle:
        def __init__(self, handle):
            self._handle = handle
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            self._handle.close()
            return False
        def read(self, size=-1):
            calls["sizes"].append(size)
            return self._handle.read(size)

    def counting_open(p, mode="r", *args, **kwargs):
        handle = real_open(p, mode, *args, **kwargs)
        if mode != "rb" or str(p) != str(path):
            return handle
        calls["opens"] += 1
        return CountingHandle(handle)

    monkeypatch.setattr("builtins.open", counting_open)
    with pytest.raises(IntakeError, match="exceeds the size cap"):
        read_local_image(path)
    assert calls["opens"] == 1
    assert calls["sizes"] == [MAX_IMAGE_BYTES + 1]


def test_oversize_missing_and_directory_rejected(tmp_path):
    with pytest.raises(IntakeError):
        read_local_image(write(tmp_path, "big.png", PNG_SIG + b"\x00" * MAX_IMAGE_BYTES))
    with pytest.raises(IntakeError):
        read_local_image(tmp_path / "absent.png")
    with pytest.raises(IntakeError):
        read_local_image(tmp_path)
    with pytest.raises(IntakeError):
        read_local_image(42)


def test_payload_garbage_after_valid_header_passes_by_design(tmp_path):
    """Control test: header-only scope cannot see payload corruption."""
    out = read_local_image(write(tmp_path, "g.png", png_bytes() + b"\xff" * 5000))
    assert (out.width, out.height) == (800, 600)


def test_descriptor_reaches_gate_blocked_by_default_private(tmp_path):
    sender = Mock()
    image = read_local_image(write(tmp_path, "d.png", png_bytes(640, 480)))
    response = process_intake(
        {"format": image.format, "width": image.width, "height": image.height, "size_bytes": image.size_bytes},
        data_policy_value=None,
        safety_card=SAFETY,
        sender=sender,
    )
    assert response.status == "blocked"
    assert response.trace["decision"] == "blocked"
    assert response.trace["image"] == {"format": "png", "width": 640, "height": 480, "size_bytes": image.size_bytes}
    sender.assert_not_called()


def test_descriptor_reaches_gate_allowed_with_documented_synthetic_evidence(tmp_path):
    """Allowed-path wiring check. Evidence flags are synthetic test doubles
    mirroring the gate's own documented allow-configuration
    (tests/test_data_policy.py); they stand in for, and are not, real user
    consent, rights, or provider verification."""
    sender = Mock()
    image = read_local_image(write(tmp_path, "e.jpg", jpeg_bytes(320, 240)))
    evidence = ProcessingEvidence(
        provider_mode=ProviderMode.STANDARD,
        provider_mode_verified=True,
        rights_confirmed=True,
        user_authorization_confirmed=True,
        privacy_notice_present=True,
    )
    response = process_intake(
        image,
        data_policy_value="private",
        data_class=DataClass.PRIVATE,
        evidence=evidence,
        safety_card=SAFETY,
        sender=sender,
    )
    assert response.status == "mock_complete"
    assert response.trace["decision"] == "allowed_mock"
    assert response.findings["label"] == "MOCK"
    assert [s["stage"] for s in response.trace["stages"]] == ["validate_input", "policy_decision", "mock_diagnosis"]
    sender.assert_called_once()
