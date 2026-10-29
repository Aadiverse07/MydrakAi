# T15 — validated offline cached replay

## Requirement basis

The master specification's B9 cache table names `key`, `response_json`, and
`ts`. B10 defines `DEMO_MODE` as `live` or `replay`, with replay serving cached
responses without network access. C2 T15 requires network-disabled replay and
backup; D3 says the demo replay should run offline for all demo cases. Only the
offline behavior is implemented here. No live mode, external client, or
provider response is enabled.

## Project-local cache contract

The specification does not define a cache payload schema or lookup-key
derivation. This implementation uses a deliberately narrow project-local
contract:

- A project fixture identifier must match `[A-Za-z0-9_.-]{1,64}`. The SQLite
  key is its lowercase SHA-256 digest; arbitrary/raw user identifiers are not
  accepted as keys.
- `response_json` must contain exactly `schema`, `provenance`, `status`, and
  `response_code`. The fixed schema is `mydrak-demo-response-v1`; provenance is
  `synthetic-offline-demo`. Unknown fields, duplicate JSON keys, malformed
  values, and payloads over 512 UTF-8 bytes are rejected.
- Only three status/code pairs are accepted: blocked/policy_blocked,
  referred/safe_referral, and manual_review/manual_review. The served English
  wording is selected from fixed code-owned text. Hindi is unavailable pending
  review. No raw reply, arbitrary user text, image bytes, user ID, credential,
  provider output, or diagnosis finding enters the cache payload.
- `ts` is a timezone-qualified ISO timestamp normalized to canonical UTC. A
  duplicate key fails rather than overwriting. Missing or corrupt entries fail
  closed; there is no network fallback. Existing SQLite backup behavior
  includes the cache table.

`DEMO_MODE` is read from the process environment only; `.env` is not opened.
Unset mode defaults to replay. Invalid values and `live` are rejected by this
offline build.

## Changed files

- `src/mydrak/trace/store.py`: B9 cache table, strict insert/read validation,
  duplicate protection, UTC timestamp normalization, and bounded payload size.
- `src/mydrak/util/config.py`: validated replay-only `DEMO_MODE` loading.
- `src/mydrak/replay/replay.py` and `src/mydrak/replay/__init__.py`: hash-based
  project fixture keys, cache only trace-backed synthetic coordinator
  outcomes, and serve fixed responses from validated local rows.
- `src/mydrak/reply/templates.py`: explicitly synthetic, non-diagnostic
  English replay responses; Hindi remains unavailable.
- `tests/test_offline_replay.py`: cache persistence, repeatability, invalid
  data, timestamps, duplicate/overwrite behavior, backup inclusion, mode
  validation, and network/workflow isolation.
- `docs/verification/roadmap_reconciliation.md` and `docs/DAILY_LOG.md`:
  evidence-based T15 status and remaining gaps.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_offline_replay.py tests/test_trace_store.py` — 55 passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider` — 870 passed.
- `python3 -m compileall -q src tests eval` — passed.
- `pyproject.toml`, all three `config/*.yaml` files, and both lines in
  `docs/testing/phase-4c-test-log.jsonl` parsed successfully; executed records:
  0.
- `git diff --check` — passed. Scoped whitespace scan — 0 trailing-whitespace
  lines. Safe secret-pattern scan — 0 matches; `.env` was excluded.
- Metadata-only `.env` checks: ignored by `.gitignore`, not tracked, and shown
  as ignored by Git. Its contents were not read.

No network/API calls, uploads, credential access, dependency installation,
credit use, or Git history/staging operations occurred.

## Status and limitations

T15 remains **PARTIAL**. The cache read/write path works for the allowlisted
synthetic outcomes, and the existing SQLite backup includes it. The cache is
not integrated with Telegram/app input lookup, the repository lacks the full
approved demo-case inventory required by D3, and cache reads are not yet wired
to the broader app trace flow. There is no live/provider replay path. These
tests demonstrate offline code behavior only, not diagnosis accuracy, provider
compatibility, or real-world agricultural validity. Live SAM remains **NO-GO**.
