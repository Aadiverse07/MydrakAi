# Phase 4C.2 safety-gate hardening — Muse session log

**Date:** 2026-10-28. **Branch:** `integration/phase-2-task-1-sam-parser`.
**Baseline HEAD:** `858b1b797aaadef17bff012d4d9047d0a933e622` (verified before editing).
Pre-existing changes (including `docs/architecture.md`, matrix, readiness,
`tests/test_sam_response_text.py`) preserved; nothing staged, committed, or pushed.

## Fixes (Codex-confirmed Phase 4C.1 audit failures)

1. **State loss / rollback** (`guard.py`): in-process registry remembers
   the highest observed budget state (attempts, breaker, token
   fingerprints) per campaign, so a deleted or replaced state file is
   rejected while the process lives; missing file, lower attempt count,
   cleared breaker, and shrunk token history each fail closed with a
   distinct message. `reset_campaign` on a missing file is the explicit
   recovery path: it re-seeds on-disk history from memory (old tokens
   stay dead) and starts a new epoch at zero without recovering lost
   budget; corrupt-but-present files still refuse reset (manual removal
   required). One self-found ordering defect fixed during testing (reset
   consumed the follow-up token). Cross-process deletion/rollback after
   restart is undetectable locally — narrowed threat model documented in
   the module docstring, not claimed as a guarantee.
2. **Filesystem/locking**: state dir resolved via realpath (symlink
   spellings share one entry); temp names documented safe under the
   held mutex; stale locks fail closed with no auto-recovery (explicit
   operator removal); orphan temp files truncated under lock; no
   permission changes to pre-existing directories (documented).
3. **Mock-only boundary** (`transport.py`): replies validated against
   the fake's issuance contract (type, `fake-<n>` ID, string payload,
   mock flag) — the flag alone is never trusted; in-process
   monkeypatching past these checks is documented as equivalent to code
   modification and out of scope. `run_scan` still exact-types the fake
   before counting.
4. **Provenance** (`MockScanResult`): constructor enforcement kept;
   docstring states the marker is a normal-flow convention, not
   tamper-proof; `run_scan` results asserted as `SamFrame` instances.
5. **Cost schema**: unchanged this phase (4C.1 wording stands); JSONL
   still holds zero executed records.

## Verification (observed)

- `tests/test_sam_live_guard.py` **43 passed** (31 carried + 12 new:
  rollback ×2, token-reuse-after-loss, symlink sharing, stale lock,
  orphan temp, cross-process contention, 4 forged-reply rejections,
  provenance negatives; thread-contention test restored after an
  editing accident that dropped its def line, then re-verified).
- Full suite: **366 passed, 0 failed** (323 + 43).
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider`,
  no-write `compile()` syntax pass, TOML + 3 YAML parse, JSONL
  line-by-line validation all observed OK; secret-pattern count scan 0;
  `.env` ignored + untracked (metadata only); `git diff --check` and
  untracked whitespace scan clean.
- No API calls, uploads, credentials, credits, deps, staging, commits.

## Tested vs reasoned

- Tested: everything above via deterministic unit/subprocess tests.
- Reasoned only (stated, not claimed): power-loss durability, hostile
  state-dir actors, malicious in-process code, cross-restart deletion.
