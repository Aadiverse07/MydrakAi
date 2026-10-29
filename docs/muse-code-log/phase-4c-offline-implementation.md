# Phase 4C offline implementation — Muse session log

**Date:** 2026-10-28. **Branch:** `integration/phase-2-task-1-sam-parser`.
**Baseline HEAD:** `858b1b797aaadef17bff012d4d9047d0a933e622` (verified before editing).
Pre-existing uncommitted changes (including `docs/architecture.md`) preserved; nothing staged, committed, or pushed.

## Added

- `src/mydrak/sam/guard.py` — `LiveCampaignGuard`: default-off, token+scope authorization (token validated, never stored/logged), max 5 attempts counted before dispatch, breaker trips on the 5th and persists, reset requires explicit operator confirmation plus a new token and returns to unauthorized. Pure logic, no network. Billing disclaimer in docstring: the guard cannot enforce Meta billing limits.
- `src/mydrak/sam/transport.py` — `SamScanRequest`/`SamScanResponse` (IDs and prompt only, never image bytes), `SamTransport` interface, `FakeSamTransport` (deterministic canned reply, `ok`/`timeout`/`malformed` modes, per-instance counter IDs), `default_transport()` (always fake), `request_live_transport()` (raises — no live client), `run_scan` (validate → count attempt → dispatch once → parse; timeouts propagate for manual review, never retried).
- `tests/test_sam_live_guard.py` — 14 tests: default-off, token/scope rules, attempts 1–5 then breaker, timeout consumes budget without retry, five timeouts trip then reject, no auto-reset (reset needs confirm + new token, then re-authorization), default-is-fake, deterministic mock parsing, malformed-reply review, request/transport/guard validation with zero dispatch on rejection, token absence from repr/vars, no-network-import scan.
- `docs/testing/phase-4c-test-log.jsonl` — schema record + one explicitly non-executed example; zero executed records, no live records, no costs invented, no credentials/payloads.
- `docs/verification/phase-4c-privacy-notice-questions.md` — unresolved recipients/storage/retention/access/consent questions; no ZDR or deletion claims; notice not published or approved.
- `docs/DAILY_LOG.md` — Phase 4C entry (observed results only).

## Verification (observed)

- `tests/test_sam_live_guard.py` **14 passed** first run; full suite **337 passed, 0 failed** (323 + 14).
- `compileall -q src tests eval` clean; TOML + 3 YAML parse OK; `git diff --check` clean; untracked-file whitespace scan clean.
- Secret-pattern count scan: 0 matches in new source/tests/log; 0 on added doc lines (pre-existing redacted doc wording only).
- `.env` ignored + untracked via Git metadata only; never read. No API calls, uploads, credentials, credits, deps, staging, or commits.

## Limitations

- Guard is application-level only; it cannot cap spend or stop other tools. No live transport, decoder, SSE assembler, or live compatibility exists. All fixtures synthetic; no crop diagnosis.
