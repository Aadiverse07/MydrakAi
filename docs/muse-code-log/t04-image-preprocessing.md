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

## 2026-10-30 follow-up — offline measurement-only implementation (Codex)

The earlier blocker is preserved as historical context. After the user confirmed Pillow imports, Pillow 13.0.0 was available; no package installation was performed. Pillow was added to `pyproject.toml` for T04 only.

Implemented `preprocess_local_image()` to read bounded local PNG/JPEG bytes, fully decode pixels, reject corrupt/truncated payloads, apply EXIF orientation, cap the configured long edge, flatten transparency onto white, normalize to JPEG, and return a SHA-256 of those normalized bytes. Measurements are: signed four-neighbor Laplacian variance, mean grayscale brightness on the 0–255 scale, and green-hue/saturation pixel fraction. The latter is explicitly named `unverified_green_hue_pixel_proxy`; it is not botanical segmentation. The image measurements are persisted in a separate SQLite table when the caller supplies an existing trace case; they do not populate `quality_scores` or B3 signals.

Project-local settings in `config/image_preprocessing.yaml` are all unverified where appropriate: long-edge cap 2048, JPEG quality 85, hue range 35–150, saturation minimum 40. They are operational choices for this offline slice, not calibrated thresholds, approved output requirements, or Meta image constraints. Retake routing is hard-disabled. No quality score or S3 calculation is implemented; measured values are not used for routing.

Synthetic regression coverage includes PNG/JPEG, zero-byte/non-image/truncated/corrupt bytes, sharp and blurred patterns, dark and bright images, EXIF orientation 6, resize boundary behavior, deterministic normalized-byte hash, measurement trace persistence, trace input validation, and disabled retake configuration.

Verification commands and results:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_vision_preprocessing.py tests/test_trace_store.py tests/test_vision_source.py -q` — exit 0, **65 passed**.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q` — exit 0, **982 passed**.
- No live calls, network requests, image uploads, credentials, `.env` access, dependency installation, or Git history operations. T04 remains PARTIAL; live SAM remains NO-GO.

## Verification

`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_vision_source.py tests/test_image_eval.py tests/test_offline_workflow.py tests/test_bot_adapter.py`: **66 passed** (existing behavior only). `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider`: **784 passed**. `python3 -m compileall -q src tests eval`: exit 0. `pyproject.toml` and four config/card YAML files parsed. Safe secret-pattern scan found 0 matches in this log and added DAILY_LOG lines. `.env` ignored/untracked confirmed with Git metadata only. `git diff --check` passed; new log trailing-whitespace scan found 0. No results here imply pixel decoding or image-quality behavior was tested.
