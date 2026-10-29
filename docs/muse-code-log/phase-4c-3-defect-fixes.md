# Phase 4C.3 defect fixes — Muse session log

**Date:** 2026-10-28. **Branch:** `integration/phase-2-task-1-sam-parser`.
**Baseline HEAD:** `858b1b797aaadef17bff012d4d9047d0a933e622` (verified before editing).
Pre-existing changes (including `docs/architecture.md`) preserved; nothing staged, committed, or pushed.

## Defects (Codex-confirmed, both fixed)

- **A. Invalid `MockScanResult` construction** (`src/mydrak/sam/transport.py`):
  the constructor accepted `frame=None` with valid provenance. `__post_init__`
  now requires `frame` to be a `SamFrame` instance, raising the module's
  existing `SamTransportError`. Regression test covers `None`, a string, a
  dict, an int, and a list, plus a valid-`SamFrame` control.
- **B. State-dir creation error masking** (`src/mydrak/sam/guard.py`):
  `_write()` assigned `tmp_path` after `mkdir()`, so a mkdir failure made
  the `finally` cleanup raise `UnboundLocalError`, masking the intended
  `LiveGuardError`. Smallest fix: `tmp_path = None` before `try`, guarded
  cleanup. Regression test fails the second `Path.mkdir` call and asserts
  the exact `LiveGuardError` type, unauthorized state, no state file, and
  a closed scan path (`sent_count == 0`).
- **Authenticity claims narrowed** (docstrings only): shape checks and the
  mock marker are conventional, forgeable-by-same-process-code markers for
  accident prevention — not proof of authenticity. Added a boundary test
  proving a shape-valid forged reply parses (the documented limit).

## Verification (observed)

- Focused file: **46 passed** (43 carried + 3 new), exit 0.
- Full suite: **369 passed, 0 failed** (366 + 3), exit 0.
- In-memory `compile()` over `src`/`tests`/`eval`: 48 files OK.
- TOML + 3 YAML parse OK; JSONL schema/example valid, 0 executed records.
- Secret-pattern count scan: 0 in changed/new files and added doc lines.
- `.env`: `check-ignore -v` confirms ignored, `ls-files` empty,
  `status --ignored` untracked-or-absent; never read.
- `git diff --check` clean; untracked whitespace scan clean.

## Limitations / UNVERIFIED

Same-process forgery indistinguishable by design; cross-restart
deletion/rollback undetectable locally; no billing enforcement; no live
transport/decoder/diagnosis. Strictly offline: no API calls, uploads,
credentials, installs, staging, commits, or pushes.
