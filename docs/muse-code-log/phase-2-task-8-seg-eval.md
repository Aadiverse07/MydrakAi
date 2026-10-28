# Muse Code session log — Phase 2, Task 8: mock-first seg eval (2026-10-28)

- Task: offline IoU/Dice evaluation contract on explicit prediction/truth
  pairs. No live SAM, no diagnosis claims.
- Key design point (§3): `sam/output.py` mask payloads are opaque strings and
  cannot support overlap math, so the contract uses validated synthetic
  `BinaryMask` grids instead; the boundary is documented in the module
  docstring. Multi-object handled as individually evaluated cases (no
  combined-mask merging, no silent alignment). Empty/empty scores 1.0 by
  documented convention; one-sided emptiness scores 0.0.
- Built: `src/mydrak/sam/scores.py` (`BinaryMask`, `intersection`, `iou`,
  `dice`, `evaluate_case`, `mark_invalid`, `summarize` with METRICS_VERSION)
  and `tests/test_sam_scores.py` (20 tests, hand-verified metric values).
- Checks (all ran): new file 20 passed first run; full suite green;
  `compileall -q src tests`, `git diff --check`, secret-pattern scan clean.
  Pre-existing worktree preserved; nothing staged, committed, or pushed. No
  network, API, uploads, credentials, credits, or dependencies.
