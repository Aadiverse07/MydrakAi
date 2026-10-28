# Phase 2 integration review (offline scope)

**Date:** 2026-10-28. **Method:** inspected code/tests/docs as committed plus
worktree; ran the full suite, compile checks, the eval CLI twice with a
byte-compare, and import scans. No network, API, uploads, credentials, or
Git mutations. Live SAM, diagnosis, and delivery claims are out of scope and
none are made here.

## 1. Scope and repository state

Branch `integration/phase-2-task-1-sam-parser`, HEAD `3b9d234` (planning-docs
commit; parents `0df0449` parser, `86a5033` Phase 1 merge). Historical snapshot
at the Task 11 review: 2 modified docs (`DAILY_LOG.md` task entries,
`architecture.md` parser-scope clarification) plus 16 untracked Phase 2 task
files; staging was empty and there were no deletions. This describes that
snapshot only, not the current worktree; use `git status` for live state.

**External-edit note (material):** file mtimes form a clean ladder matching
the session order except `src/mydrak/sam/adapter.py` and
`tests/test_sam_grid.py`, both restamped ~17 h after their creation, i.e.
between sessions. Those two files contain a Codex review fix-pass that is
itself documented in the Task 10 `DAILY_LOG.md` entry (28→33 grid tests, full
suite 247): the adapter gained dimension-cap enforcement wired to the passed
limits plus a non-string-data guard, with 2 regression tests (cap rejection,
non-string rejection). Reviewed in full: purely defensive, no network/scope
creep, consistent errors, suite green. Without it, an unguarded non-string
payload would have raised an unhandled `TypeError` instead of
`SegmentationEvalError`.

## 2. Component matrix

| Component | Contract | Evidence | Status |
|---|---|---|---|
| Image intake | Descriptors only, never bytes | `intake/adapter.py`, 41 intake tests | Mock only |
| Header reader | PNG/JPEG headers, local caps | `vision/source.py`, 25 automated tests with generated fixtures; separate Task 6 manual header validation on 10 real development images | Offline ok |
| SAM parser | Synthetic grammar, strict keys | `sam/output.py`, 71 tests | Offline ok |
| Grid adapter | `synthetic-grid-v1` only | `sam/adapter.py`, 33 tests | Offline ok |
| IoU/Dice metrics | Explicit grids, edge rules | `sam/scores.py`, 20 tests | Offline ok |
| Offline workflow | Reader + fixture, labeled | `workflow/offline.py`, 14 tests | Offline ok |
| Eval reporter | Sorted JSON, byte-stable | `eval/image_report.py`, 6 tests | Offline ok |
| Privacy gate | Fail-closed, unwired sender | `data_policy.py`, 12 gate tests | Enforced locally |
| Telegram/bot/models | None exist | Stubs only, zero network imports | Not implemented |

## 3. Test evidence

- Focused Phase 2 command: `python3 -m pytest tests/test_image_eval.py tests/test_offline_workflow.py tests/test_sam_grid.py tests/test_sam_output.py tests/test_sam_scores.py tests/test_vision_source.py tests/test_data_policy.py tests/test_mock_intake.py` — **221 passed**.
- Full `python3 -m pytest`: **247 passed, 0 failed** (per-file counts
  reconciled: 15 grid functions incl. 2 external, 13 vision functions).
- `python3 -m compileall -q src tests eval`: clean. `git diff --check`: clean.
- Import scan: no network/SDK/DOTENV-adjacent imports in `src/` or `tests/`
  (env access is `os.environ` read inside the gate only).

## 4. Image evaluation

`python3 eval/image_report.py` → `inspected=10 accepted=6 rejected=4
unsupported=4`; rerun to a second path byte-identical (`cmp` clean).
Accepted files are genuine JPEG (SOF-parsed dims, e.g. 3071x1999, 1158x1700);
rejected files are valid WebP misnamed .jpg/.png — correctly rejected, not
corrupt. Extensions are never trusted (JPEG-bytes `.png` accepted as jpeg).
This proves header inspection only. Automated reader tests use generated
fixtures; these 10 real-image checks were a separate manual Task 6 validation,
not cases in the automated test suite.

## 5. Privacy and external integrations

Gate fails closed (missing→private, invalid rejected, all-False default
evidence blocks, Contributor+private blocked, unwired sender proven by
zero-call assertions). Live SAM, Telegram/WhatsApp, diagnosis, trace store,
and dashboard: NOT IMPLEMENTED. Credit/entitlement, billing state, ZDR,
Official Rules: UNVERIFIED per filed reports. `.env` present on disk,
ignored and untracked, never read.

## 6. Known limitations

Header validation ≠ decoding; fixture parsing ≠ SAM inference; metric scores
on synthetic grids ≠ segmentation accuracy; no disease KB beyond safety lines;
no delivery path. The adapter boundary (synthetic-grid-v1 only) and the
Task 9 stop-decision are documented in-session.

## 7. Phase 2 verdict

**READY TO CLOSE (OFFLINE SCOPE ONLY).** Every authorized offline behavior is
implemented, tested (247 green), and honestly labeled; the one externally
added hardening improves the contract without expanding scope. Nothing in the
offline scope is missing or red.

## 8. Next steps

1. Commit the reviewed batches (parser `0df0449` exists; Task 2–10 work and
   planning docs remain uncommitted) through the PR flow.
2. Task 9’s adapter-contract blocker was resolved in Task 10 by adopting
   `synthetic-grid-v1`; no box-overlap adapter was implemented.
3. Close live-integration blockers in readiness-report order before any live
   call; obtain a real photo path for a witnessed manual read.

## Follow-up corrections

- Reproduced the focused command above (**221 passed**) and full suite
  (**247 passed, 0 failed**) for the Task 11 baseline.
- The reporter now replaces absolute input-directory values with the stable
  `absolute-input` label in JSON and omits paths from missing-directory errors;
  exit code 2 is unchanged. Added an absolute-temporary-directory regression
  test. After this correction, the focused command passed **222 tests** and
  the full suite passed **248 tests, 0 failed**; exact results are recorded in
  the Task 11 correction entry in `docs/DAILY_LOG.md`.
- Reporter repeatability was rechecked with two temporary output paths; both
  runs returned identical aggregate counts and byte-identical JSON. The
  existing ignored default report was not overwritten.
