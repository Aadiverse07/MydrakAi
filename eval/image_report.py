"""Offline image-header evaluation report (Phase 2, Task 7).

Reads every regular file in an evaluation data directory with the existing
`read_local_image` header reader and writes a deterministic, machine-readable
JSON report. Standard library only. No decoding, diagnosis, segmentation,
network, uploads, or new dependencies.

Usage:
    python3 eval/image_report.py [--data-dir eval/data/dev] [--out eval/results/dev_image_headers.json]

Report stability: files are listed in sorted relative-path order, JSON is
written with sorted keys, and the report contains no timestamps, absolute
paths, or image contents — reruns over unchanged inputs are byte-identical.
A missing input directory is an error (exit 2); an empty directory yields a
zero-totals report. Per-file verdicts come solely from the reader: `accepted`
means the header parsed (format, dimensions, size); anything else is
`rejected` with the reader's controlled reason. Header acceptance never
implies decodability, segmentation, or crop health.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from mydrak.intake.adapter import IntakeError  # noqa: E402
from mydrak.vision.source import read_local_image  # noqa: E402

REPORT_VERSION = 1
DEFAULT_DATA_DIR = os.path.join("eval", "data", "dev")
DEFAULT_OUT_PATH = os.path.join("eval", "results", "dev_image_headers.json")
UNSUPPORTED_PREFIX = "unsupported image format"


def discover_images(data_dir: str) -> list[str]:
    """Return sorted relative filenames of regular files, top level only."""
    try:
        names = os.listdir(data_dir)
    except OSError:
        raise FileNotFoundError("input directory not available") from None
    if not os.path.isdir(data_dir):
        raise FileNotFoundError("input directory not available")
    return sorted(
        name
        for name in names
        if os.path.isfile(os.path.join(data_dir, name))
    )


def inspect_file(data_dir: str, relative_name: str) -> dict:
    """Run the existing reader on one file; return its report record."""
    path = os.path.join(data_dir, relative_name)
    try:
        found = read_local_image(path)
    except IntakeError as exc:
        reason = str(exc)
        try:
            size_bytes: int | None = os.path.getsize(path)
        except OSError:
            size_bytes = None
        return {
            "file": relative_name,
            "format": None,
            "width": None,
            "height": None,
            "size_bytes": size_bytes,
            "status": "rejected",
            "reason": reason,
        }
    return {
        "file": relative_name,
        "format": found.format,
        "width": found.width,
        "height": found.height,
        "size_bytes": found.size_bytes,
        "status": "accepted",
        "reason": None,
    }


def build_report(data_dir: str) -> dict:
    """Inspect every discovered file and tally totals deterministically."""
    records = [inspect_file(data_dir, name) for name in discover_images(data_dir)]
    rejected = [record for record in records if record["status"] == "rejected"]
    unsupported = [
        record for record in rejected
        if (record["reason"] or "").startswith(UNSUPPORTED_PREFIX)
    ]
    return {
        "version": REPORT_VERSION,
        "data_dir": "absolute-input" if os.path.isabs(data_dir) else data_dir,
        "files": records,
        "totals": {
            "inspected": len(records),
            "accepted": len(records) - len(rejected),
            "rejected": len(rejected),
            "unsupported": len(unsupported),
        },
    }


def write_report(report: dict, out_path: str) -> None:
    """Write the report as sorted-keys JSON. Creates parent dirs as needed."""
    parent = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(parent, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code; raises nothing."""
    parser = argparse.ArgumentParser(description="Offline image-header evaluation report.")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--out", default=DEFAULT_OUT_PATH)
    args = parser.parse_args(argv)
    try:
        report = build_report(args.data_dir)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    write_report(report, args.out)
    totals = report["totals"]
    print(
        f"inspected={totals['inspected']} accepted={totals['accepted']} "
        f"rejected={totals['rejected']} unsupported={totals['unsupported']} -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
