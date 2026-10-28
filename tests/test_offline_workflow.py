"""Offline image-workflow tests. Every image fixture is synthetic bytes built
in-test (struct/zlib) and every segmentation fixture is a hand-built mapping;
nothing here is a real crop photo, a real SAM response, or a diagnosis."""

import struct
from pathlib import Path

import pytest

from mydrak.intake.adapter import IntakeError
from mydrak.sam.output import SamLimits, SamOutputError
from mydrak.workflow.offline import (
    IMAGE_PROVENANCE,
    SEGMENTATION_PROVENANCE,
    run_offline_image_workflow,
)

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def synth_png(width=640, height=480):
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return PNG_SIG + struct.pack(">I", 13) + b"IHDR" + ihdr


def synth_fixture(*objects, frame_width=640, frame_height=480):
    return {"image": {"width": frame_width, "height": frame_height}, "objects": list(objects)}


def synth_object(id="synth-leaf-1", box=(10, 20, 100, 200), score=0.9):
    return {
        "id": id,
        "box": list(box),
        "mask": {"width": 640, "height": 480, "encoding": "synthetic-test-encoding", "data": "SYNTHETIC_MASK"},
        "score": score,
    }


def write(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_valid_image_plus_valid_fixture(tmp_path):
    result = run_offline_image_workflow(
        write(tmp_path, "leaf.png", synth_png()), synth_fixture(synth_object(), synth_object(id="synth-lesion-2"))
    )
    assert result.image.format == "png"
    assert (result.image.width, result.image.height) == (640, 480)
    assert result.segmentation.match_count == 2
    assert [s["stage"] for s in result.stages] == ["inspect_image", "parse_segmentation"]
    assert result.total_duration_ms >= 0
    body = result.to_dict()
    assert body["image"]["provenance"] == IMAGE_PROVENANCE
    assert body["segmentation"]["provenance"] == SEGMENTATION_PROVENANCE
    assert body["segmentation"]["objects"][0]["id"] == "synth-leaf-1"


def test_zero_object_fixture_is_valid(tmp_path):
    result = run_offline_image_workflow(write(tmp_path, "leaf.png", synth_png()), synth_fixture())
    assert result.segmentation.match_count == 0
    assert result.to_dict()["segmentation"]["objects"] == []


def test_fixture_frame_reported_independently_of_image_file(tmp_path):
    result = run_offline_image_workflow(
        write(tmp_path, "leaf.png", synth_png(640, 480)), synth_fixture(frame_width=800, frame_height=600)
    )
    assert (result.image.width, result.image.height) == (640, 480)
    assert (result.segmentation.image_width, result.segmentation.image_height) == (800, 600)


@pytest.mark.parametrize("data", [b"not an image", PNG_SIG + b"\x00" * 4])
def test_unsupported_and_malformed_image_rejected(tmp_path, data):
    with pytest.raises(IntakeError):
        run_offline_image_workflow(write(tmp_path, "bad.bin", data), synth_fixture())


def test_missing_and_unreadable_file_rejected_without_path_leak(tmp_path, monkeypatch):
    missing = tmp_path / "absent.png"
    with pytest.raises(IntakeError) as excinfo:
        run_offline_image_workflow(missing, synth_fixture())
    assert str(missing) not in str(excinfo.value)

    def fail_open(*args, **kwargs):
        raise OSError("simulated read failure")

    real = write(tmp_path, "r.png", synth_png())
    monkeypatch.setattr("builtins.open", fail_open)
    with pytest.raises(IntakeError) as excinfo:
        run_offline_image_workflow(real, synth_fixture())
    assert "simulated read failure" not in str(excinfo.value)


def test_oversized_image_rejected(tmp_path):
    from mydrak.vision.source import MAX_IMAGE_BYTES

    with pytest.raises(IntakeError):
        run_offline_image_workflow(write(tmp_path, "big.png", PNG_SIG + b"\x00" * MAX_IMAGE_BYTES), synth_fixture())


def test_over_limit_dimensions_rejected(tmp_path):
    with pytest.raises(IntakeError):
        run_offline_image_workflow(write(tmp_path, "wide.png", synth_png(width=20001)), synth_fixture())


@pytest.mark.parametrize("document", [
    "not-a-mapping",
    {"image": {"width": 640, "height": 480}},
    synth_fixture(synth_object(box=(90, 90, 10, 10))),
    synth_fixture({"id": "x"}),
])
def test_malformed_segmentation_rejected(tmp_path, document):
    with pytest.raises(SamOutputError):
        run_offline_image_workflow(write(tmp_path, "leaf.png", synth_png()), document)


def test_oversized_segmentation_rejected_with_limits(tmp_path):
    objects = [synth_object(id=f"synth-{i}") for i in range(3)]
    with pytest.raises(SamOutputError):
        run_offline_image_workflow(
            write(tmp_path, "leaf.png", synth_png()),
            synth_fixture(*objects),
            limits=SamLimits(max_objects=2),
        )


def test_no_network_or_sender_in_workflow():
    source = (Path(__file__).resolve().parents[1] / "src" / "mydrak" / "workflow" / "offline.py").read_text()
    for token in ("urllib", "http.client", "socket", "subprocess", "requests", "httpx", "openai", "telegram", "sender"):
        assert token not in source
