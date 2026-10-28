# Muse Code session log — Phase 2, Task 9: adapter blocker (2026-10-28)

- Task: build a prediction→`BinaryMask` adapter if the contract suffices;
  otherwise stop and report the incompatibility (§2 stop-clause).
- Evidence (code search over `src/mydrak/sam/`): the only grid representation
  anywhere is `scores.py`'s own synthetic `BinaryMask` (rows of "0"/"1").
  `SamMask` (`output.py`) exposes exactly `{width, height, encoding, data}`
  where `encoding`/`data` are arbitrary non-empty strings with length caps
  only — no content constraints, no documented string→cell mapping, and an
  explicit never-decode rule in both modules' docstrings.
- Verdict: INSUFFICIENT. No total truthful `SamMask → BinaryMask` function
  exists: it would have to reject every payload (useless) or invent a decoder
  for an undocumented encoding (forbidden by the task, the parser contract,
  and AGENTS.md). Box→grid rasterization was considered and rejected for this
  task: boxes are verified parser fields, but §3 limits conversion to mask
  representations and box-overlap is different semantics requiring its own
  explicitly scoped contract.
- Smallest clarification proposal: (a, recommended) extend the fixture grammar
  with an OPTIONAL documented grid encoding, e.g. `encoding ==
  "synthetic-grid-v1"` carrying validated `"0"/"1"` rows, with the adapter
  converting only that encoding and rejecting all others; (b) alternatively,
  a separate explicitly-labeled box-overlap contract, never presented as mask
  evaluation. Either needs approval before implementation.
- Checks: `git diff --check` clean; nothing staged, committed, or pushed. No
  network, API, uploads, credentials, credits, or dependencies.
