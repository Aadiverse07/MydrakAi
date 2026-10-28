# Muse Code session log — Phase 2, Task 4: real crop-image validation (2026-10-27)

- Task: establish reproducible evidence that the offline workflow can inspect
  a genuine crop-image file, or document the data-availability blocker
  without claiming success. No new features, no live integration.
- Search performed: case-insensitive `find` over the whole repository tree
  for jpg/jpeg/png/webp/heic/tif/bmp files. Exactly one image file exists:
  `docs/MydrakDeep.png`.
- Disqualification (evidence, not assumption): `docs/MydrakDeep.png` was
  viewed as a rendered image during Phase 0 inspection. It is the project
  infographic poster (hackathon facts, rubric, workflow diagrams), not a
  photograph of a crop or leaf. Running the header reader on it would prove
  only that a real PNG parses — it would say nothing about crop-image
  validation, so it was explicitly NOT used as a crop sample.
- `eval/data/dev`, `eval/data/test`, `eval/results` contain no images
  (gitignored by design; SOURCES.md holds sourcing rules only). No
  `farmer_images/`, `uploads/`, or private-data directories exist.
- Outcome: condition 2 — no authorized genuine crop-image file is available
  in the repository. No synthetic substitute was generated or labeled real;
  no validation claimed; no test results invented. No code or test changes
  were necessary, so the suite was not re-run (recorded state: 189 passed);
  no files were executed and no caches were created by this task.
- Readiness: the workflow path is complete and tested with synthetic
  fixtures (`read_local_image` → descriptor → gate → trace, 189 recorded
  passes). The moment a user-supplied photo arrives, the procedure is: run
  `read_local_image` on the supplied path, record format/dimensions/size and
  accept/reject reason, keep the file out of Git and un-uploaded.
- Image needed from the user: one genuine crop/leaf photograph as a local
  file (JPEG or PNG), supplied as an explicit path, with confirmation it may
  be read locally. No particular size; the 10 MiB / 20000 px caps apply.
- Checks: worktree state verified read-only (`git status`/`rev-parse` only).
  No network, API, uploads, credentials, credits, dependencies, staging,
  commits, or pushes.
