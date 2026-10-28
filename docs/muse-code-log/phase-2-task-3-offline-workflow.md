# Muse Code session log — Phase 2, Task 3: offline image workflow (2026-10-27)

- Task: compose the existing header reader and SAM-output parser into one
  honest offline workflow. No live SAM, no diagnosis claims, no new dependency.
- Design: new `src/mydrak/workflow/offline.py` reuses `read_local_image` and
  `parse_sam_output` unchanged (no duplicated validation). A separate module
  rather than an `intake` extension, because `process_intake` carries mock
  diagnosis + external-processing gate semantics this workflow must not imply.
  `OfflineResult` keeps validated image metadata and supplied fixture data in
  separate labeled sections; the fixture frame is reported independently, not
  cross-checked. Reader/parser errors propagate unchanged (no path/OS leaks).
- Tests: `tests/test_offline_workflow.py`, 14 tests, all fixtures synthetic
  (struct-built bytes in tmp_path, hand-built mappings). Covers every required
  path including zero-match, frame independence, failure propagation without
  path leaks, limit regressions, and a no-network/sender source guard.
- Checks (all ran): new file 14 passed first run; full suite green (exact total
  in DAILY_LOG after the final run below); `compileall -q src tests`,
  `git diff --check`, secret-pattern scan clean. Pre-existing worktree changes
  preserved; nothing staged, committed, or pushed. No network, API, uploads,
  credentials, credits, or dependency activity.
