# Muse Code session log — Phase 2, Task 6: real crop-image validation (2026-10-28)

- Task: run the existing offline reader on genuine files in `eval/data/dev/`.
  Read-only; no code changes; no integration work.
- Command: `PYTHONPATH=src python3 -c` loop calling `read_local_image` per
  file, printing filename/format/dimensions/size/accept-or-reason only.
- Results (10 files, all user-supplied, sizes 18 KB–964 KB):
  ACCEPTED (6, genuine JPEG structure with SOF-parsed dimensions): Crop_1.jpg
  1158x1700, Crop_3.jpg 3071x1999, crop_04.jpg 400x533, crop_07.png 346x280
  (JPEG bytes despite .png name — content, not extension, governs),
  crop_09.jpg 440x454, crop_10.jpg 1024x683.
  REJECTED (4, correct reason): Crop_2.jpg, crop_05.jpg, crop_06.png,
  crop_08.jpg are valid WebP (RIFF `WEBP`, VP8 — confirmed by magic bytes and
  `file` container identification) misnamed as .jpg/.png. The PNG/JPEG-only
  reader correctly rejected them as unsupported format; the files are not
  corrupt. WebP support is a separate scoped decision requiring SAM-specific
  format verification first — not implemented here.
- Evidence categories: (A) real-file header validation ESTABLISHED for the 6
  JPEGs — header integrity + dimensions only, not decoding/segmentation/
  diagnosis; (B) synthetic suite unchanged (recorded 189 passed, not re-run —
  no code changed); (C) real SAM output still unproven.
- Checks: `git diff --check` clean; photos confirmed outside Git tracking
  (eval/data/ is gitignored — verified, settings untouched); no image bytes
  or contents in any log. No network, API, uploads, credentials, credits,
  deps, staging, commits, or pushes.
