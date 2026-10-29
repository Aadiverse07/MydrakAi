# T04 — Image Preprocessing and Quality Gate (Blocked)

Date: 2026-10-29

## Specification scope

- B1 (master PDF p. 6): correct EXIF orientation, resize, and perform quality checks before model processing; a quality failure asks for a retake and stops processing.
- B3 (p. 7): S3 uses variance of Laplacian for blur, a brightness range, and leaf-coverage fraction mapped to a 0–1 score; below `quality_min`, the case retakes. Thresholds/weights are to be tuned on dev, never test.
- C2 (p. 12): T04 acceptance is unit tests on blurry, dark, and good images.

The specification does not provide approved blur or brightness cutoffs, leaf-coverage method/cutoff, mapping from the measurements to S3, a calibrated `quality_min`, resize long-edge target, JPEG quality, or output encoding settings. The configured `quality_min: 0.4` is explicitly a TODO placeholder. The existing intake cap of 10 MiB and maximum dimension of 20,000 are local input bounds, not quality criteria.

## Current implementation

`src/mydrak/vision/source.py` parses bounded PNG/JPEG headers and validates dimensions/structure. It explicitly does not decode pixel payloads. Existing tests use synthetic header bytes and cover malformed/truncated headers and local bounds; they do not test pixel decoding, EXIF transformation, resizing, blur, brightness, or leaf coverage. `pyproject.toml` declares PyYAML only (plus pytest for development); local module discovery found Pillow and OpenCV unavailable.

## Decision

No code or tests were changed. Safe decoding, EXIF transformation and resizing require an image-processing dependency or a new image decoder; neither is available/approved. Quality-gate outcomes cannot be implemented honestly without the missing measurement thresholds and score mapping. Header-only checks remain the current safe subset and do not complete T04. The prior assessment in `t04-preprocessing-blocker.md` is preserved.

## Required resolution

Approve a maintained image-decoding dependency before installation, and specify or approve project-local values/methods for maximum output dimensions, resize/encoding settings, blur cutoff, brightness range, leaf-coverage method/cutoff, measurement-to-S3 mapping, and `quality_min`. If these are to be calibrated, provide a licensed dev set with reviewed labels and a calibration procedure that never uses the test split. Then implement deterministic preprocessing and synthetic boundary tests; do not claim agronomic calibration from synthetic fixtures.

No live APIs, network access, media uploads, credentials, credits, dependency installs, or Git history operations occurred. Live SAM remains NO-GO.

## Verification

`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_vision_source.py tests/test_image_eval.py tests/test_offline_workflow.py tests/test_bot_adapter.py`: **66 passed** (existing behavior only). `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider`: **784 passed**. `python3 -m compileall -q src tests eval`: exit 0. `pyproject.toml` and four config/card YAML files parsed. Safe secret-pattern scan found 0 matches in this log and added DAILY_LOG lines. `.env` ignored/untracked confirmed with Git metadata only. `git diff --check` passed; new log trailing-whitespace scan found 0. No results here imply pixel decoding or image-quality behavior was tested.
