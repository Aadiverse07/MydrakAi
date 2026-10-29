# Phase 4C.1 safety-gate hardening — Muse session log

**Date:** 2026-10-28. **Branch:** `integration/phase-2-task-1-sam-parser`.
**Baseline HEAD:** `858b1b797aaadef17bff012d4d9047d0a933e622` (verified before editing).
Pre-existing changes (including `docs/architecture.md`, matrix, readiness,
`tests/test_sam_response_text.py`) preserved; nothing staged, committed, or pushed.

## Fixes (Codex-confirmed Phase 4C defects)

1. **Durable budget** (`src/mydrak/sam/guard.py` rewritten around a state
   file): one JSON document per campaign under a configurable local dir
   (default XDG `mydrak/guard/`, never the repo); campaign IDs restricted
   to `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`. Every operation reloads under a
   lock-directory mutex (contention fails closed); writes are temp +
   fsync + atomic rename. Corrupt/inconsistent/unreadable/unwritable
   state raises `LiveGuardError` — the counter is never silently reset.
   Tested: recreation/restart sharing, attempts 1–5, 6th rejected,
   corruption, inconsistency, post-use deletion, write failure
   (monkeypatched `os.replace`), 8-thread contention (exactly 5 counted).
   Lock covers process-crash races, not OS/power loss (documented).
2. **Operator-gate authorization:** token checked for shape and single-use
   via SHA-256 fingerprints (never stored); authorizations bind campaign
   ID + scope + expiry (`valid_seconds`, finite, `>=` comparison so 0 is
   immediately expired). Missing/mismatched/expired/reused/malformed all
   rejected before counting. Reset needs explicit confirmation plus an
   unused token, clears operational state but keeps the token history,
   and requires fresh authorization after. One real defect found in
   review of my own first draft (reset consumed the token so the
   follow-up authorize failed) and fixed: reset verifies distinctness,
   authorize records use. Mechanism labeled a local operator gate, not
   authentication, in module docstring and tests.
3. **Mock-only transport** (`src/mydrak/sam/transport.py`): `run_scan`
   accepts exactly `FakeSamTransport` — subclasses rejected before
   `send()` runs and before any attempt is counted (regression tests with
   a mock-flag-fabricating subclass and a fake subclass). `is_mock` is no
   longer trusted for the boundary. `default_transport()` still fake;
   `request_live_transport()` still raises.
4. **Provenance** (`MockScanResult`): frozen wrapper with
   `provenance == "synthetic-mock"` enforced in `__post_init__`;
   `run_scan` returns it with request ID and scope. Malformed replies
   still raise for manual review. Tests assert the marker survives
   parsing and is caller-visible.
5. **Cost schema** (`docs/testing/phase-4c-test-log.jsonl`): `actual_usd`
   null = unknown/unverified/unavailable; numeric 0 = verified zero only;
   `cost_verified` three states defined consistently. Example still
   non-executed; zero executed records; nothing invented.

## Verification (observed)

- `tests/test_sam_live_guard.py` **31 passed** (14 pre-existing contract
  tests updated to the new signatures plus 17 new regression tests;
  three first-run failures investigated: one genuine reset/authorize
  ordering defect fixed in `guard.py`, two wrong test-side mutations
  corrected).
- Full suite: **354 passed, 0 failed** (323 + 31).
- `compileall -q src tests eval` clean; TOML + 3 YAML parse OK;
  `git diff --check` clean; untracked whitespace scan clean.
- Secret-pattern count scan: 0 in new/changed files; 0 on added doc lines.
- `.env` ignored + untracked via Git metadata only; never read. No API
  calls, uploads, credentials, credits, deps, staging, or commits.

## Limitations

- File lock does not survive `kill -9` (stale `.lock` needs explicit
  operator removal, documented); no defense against OS/power loss.
- SHA-256 fingerprints do not make low-entropy operator tokens
  cryptographic authentication — labeled as such.
- Readiness test-count lines now trail the new total; left untouched per
  minimal-scope rule and disclosed here. No live transport, decoder,
  billing enforcement, or diagnosis exists.
