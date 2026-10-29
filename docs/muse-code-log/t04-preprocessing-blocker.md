# T04 — Image Preprocessing Assessment (Blocked)

Date: 2026-10-29

## Specification findings

- Master specification B1 (PDF page 6) calls for EXIF correction, resizing, and quality checking before model processing; a quality failure stops with a retake request.
- B3 (PDF page 7) names variance of Laplacian for blur, brightness range, and leaf coverage fraction as S3 inputs; values are mapped to a score, and below `quality_min` the case retakes. `config/thresholds.yaml` labels `quality_min: 0.4` and related values as TODO/placeholder, not validated criteria.
- C2 (PDF page 12) defines T04 acceptance as unit tests on blurry, dark, and good images. It does not specify numeric blur, brightness, coverage, pixel, resize-long-edge, or JPEG quality thresholds. B5's default 3 percentage-point margin is for recovery severity, not image quality.

## Existing implementation and blocker

`src/mydrak/vision/source.py` already reads a bounded PNG/JPEG header and returns `IntakeImage`; it does not validate full decode integrity, expose pixels, read/apply EXIF orientation, resize/recompress, or compute image-quality metrics. `src/mydrak/intake/adapter.py` has local caps of 10 MiB and 20,000 per dimension; these are project-local input bounds, not master-spec image limits. T03 accepts only normalized synthetic events and does not accept media bytes. `Pillow` and OpenCV are unavailable in the current Python environment; neither is declared in `pyproject.toml`. NumPy is present locally but is not a declared decoder dependency.

No safe pixel-decoding implementation can be completed with the current declared dependencies without writing a PNG/JPEG decoder or guessing image thresholds. Neither was attempted. The existing header reader remains the only implemented safe subset; the T04 checks below do not demonstrate T04 completion.

## Verification performed

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_vision_source.py tests/test_image_eval.py tests/test_offline_workflow.py tests/test_bot_adapter.py` — 66 passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider` — 660 passed, 0 failed.
- Dependency availability checked through Python module discovery only: Pillow absent, OpenCV absent, NumPy present but undeclared.

## Decision required before implementation

Approve adding a maintained local image library such as Pillow (no installation performed), and decide whether T04 should use explicit project-local defaults for resize and quality thresholds or wait for dev-image calibration. Required choices include maximum output long edge/JPEG quality, blur cutoff, brightness range, and a method/threshold for leaf coverage. These values cannot be derived from the current master specification or validated against the absent dev image set. No Telegram or model connection, image upload, or live SAM operation occurred. Live SAM remains NO-GO.
