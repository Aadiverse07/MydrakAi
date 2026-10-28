"""Image-header evaluation report tests. All fixtures are synthetic bytes
built in-test under tmp_path; nothing depends on the user's local dataset,
and no report may contain absolute paths or image contents."""

import importlib.util
import json
import struct

import pytest

from conftest import REPO_ROOT

SPEC = importlib.util.spec_from_file_location(
    "image_report", REPO_ROOT / "eval" / "image_report.py"
)
image_report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(image_report)

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def synth_png(width=640, height=480):
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return PNG_SIG + struct.pack(">I", 13) + b"IHDR" + ihdr


def synth_jpeg(width=320, height=240):
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 8 + 3 * 3, 8, height, width, 3)
    sof += b"\x01\x11\x00" * 3
    return b"\xff\xd8" + sof + b"\xff\xd9"


def test_deterministic_ordering_and_metadata(tmp_path):
    data_dir = tmp_path / "dev"
    data_dir.mkdir()
    (data_dir / "zzz.png").write_bytes(synth_png())
    (data_dir / "aaa.jpg").write_bytes(synth_jpeg())
    (data_dir / "sub").mkdir()
    report = image_report.build_report(str(data_dir))
    assert [r["file"] for r in report["files"]] == ["aaa.jpg", "zzz.png"]
    by_name = {r["file"]: r for r in report["files"]}
    assert by_name["aaa.jpg"]["format"] == "jpeg"
    assert (by_name["aaa.jpg"]["width"], by_name["aaa.jpg"]["height"]) == (320, 240)
    assert by_name["zzz.png"]["size_bytes"] == len(synth_png())
    assert report["totals"] == {"inspected": 2, "accepted": 2, "rejected": 0, "unsupported": 0}


def test_rejected_files_classified(tmp_path):
    data_dir = tmp_path / "dev"
    data_dir.mkdir()
    (data_dir / "ok.png").write_bytes(synth_png())
    (data_dir / "fake.jpg").write_bytes(b"RIFF....WEBP")
    (data_dir / "short.png").write_bytes(PNG_SIG + b"\x00")
    report = image_report.build_report(str(data_dir))
    assert report["totals"] == {"inspected": 3, "accepted": 1, "rejected": 2, "unsupported": 1}
    by_name = {r["file"]: r for r in report["files"]}
    assert by_name["fake.jpg"]["reason"].startswith("unsupported image format")
    assert by_name["short.png"]["reason"]
    assert by_name["short.png"]["format"] is None


def test_missing_and_empty_directories(tmp_path, capsys):
    with pytest.raises(FileNotFoundError):
        image_report.build_report(str(tmp_path / "absent"))
    absent = tmp_path / "absent"
    assert image_report.main(["--data-dir", str(absent), "--out", str(tmp_path / "r.json")]) == 2
    assert str(absent) not in capsys.readouterr().err
    empty = tmp_path / "empty"
    empty.mkdir()
    report = image_report.build_report(str(empty))
    assert report["files"] == []
    assert report["totals"] == {"inspected": 0, "accepted": 0, "rejected": 0, "unsupported": 0}


def test_stable_json_output_without_paths_or_contents(tmp_path, monkeypatch):
    data_dir = tmp_path / "dev"
    data_dir.mkdir()
    png = synth_png()
    (data_dir / "a.png").write_bytes(png)
    (data_dir / "b.jpg").write_bytes(synth_jpeg())
    monkeypatch.chdir(tmp_path)
    assert image_report.main(["--data-dir", "dev", "--out", "report.json"]) == 0
    first = (tmp_path / "report.json").read_text(encoding="utf-8")
    assert image_report.main(["--data-dir", "dev", "--out", "report.json"]) == 0
    assert (tmp_path / "report.json").read_text(encoding="utf-8") == first
    assert str(tmp_path) not in first
    assert png.decode("latin-1") not in first
    parsed = json.loads(first)
    assert parsed["version"] == 1
    assert parsed["data_dir"] == "dev"
    assert parsed["totals"]["accepted"] == 2


def test_report_out_writes_parent_dirs(tmp_path):
    data_dir = tmp_path / "dev"
    data_dir.mkdir()
    out = tmp_path / "nested" / "dir" / "r.json"
    assert image_report.main(["--data-dir", str(data_dir), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["totals"]["inspected"] == 0


def test_absolute_data_dir_is_not_serialized(tmp_path):
    data_dir = tmp_path / "private-input" / "dev"
    data_dir.mkdir(parents=True)
    report = image_report.build_report(str(data_dir))
    serialized = json.dumps(report, sort_keys=True)
    assert str(data_dir) not in serialized
    assert report["data_dir"] == "absolute-input"
