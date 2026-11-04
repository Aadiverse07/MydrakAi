# Telegram consent gate and smoke diagnostics — Codex

Date: 2026-11-04. Offline code and tests only.

## Work

- Raised the ignored local public-mode lifetime shared-ledger cap to `$15` and
  added the requested comment. No other value in `config/bot_limits.yaml` was
  changed. The README and test for the real local config now expect `$15`.
- Read-only Telegram path review found no non-photo route to Glimmer, Spark,
  SAM, or Voice. Text/follow-up messages, commands, unsupported media, and
  edited non-photo updates only produce fixed Telegram replies. See the final
  response for per-update behavior, resource growth, and offset limitations.
- Added `/privacy`, `/agree`, and `/withdraw`; consent and notice views persist
  in the existing local SQLite limits database keyed by hashed user ID. The
  consent table contains only `user_hash`, `consent_version`, `consented_at`,
  and nullable `revoked_at`. Notice views are a separate three-column table.
  Each photo request builds fresh policy evidence from current, non-revoked
  consent and the configured standard Spark model, then calls
  `require_external_processing_allowed(PRIVATE, PRIVATE, evidence)` before
  downloading the file. Approval and upload settings default off. The private
  route is `spark_only`; enabling `private_tier1_allowed` currently fails
  closed because no private Glimmer route is available.
- The notice remains labeled DRAFT. The requested assertion that photos are
  transmitted to SAM was not made: inspected code runs synthetic/mock SAM
  locally and records live SAM as unavailable/NO-GO. The project-owner-supplied
  Meta pricing-page statement about product improvement is identified as
  supplied information, not independently rechecked. Provider retention
  conditions remain UNVERIFIED. Hindi notice slot is UNREVIEWED and not served.
- Added sanitized `guard_condition` output to the SAM and Voice smoke scripts;
  shared Glimmer/Spark smoke output uses the same allowlisted condition-ID
  helper. Conditions appear only with `failure_category=guard_refused`.

## Verification

- Baseline before Part 1: `python3 -m pytest -q` — **1365 passed**.
- After Part 1: `python3 -m pytest -q` — **1365 passed**.
- After read-only Part 2: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q` — **1365 passed**.
- Part 3 focused runner/transport/limits/reply-preview suite — **48 passed**;
  full suite — **1377 passed**.
- Final focused command: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q tests/test_telegram_runner.py tests/test_telegram_http_transport.py tests/test_telegram_limits.py tests/test_reply_preview.py tests/test_live_smoke_diagnostics.py tests/test_sam_live_client.py tests/test_audio_live_client.py` — **133 passed**.
- Final full suite: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q` — **1381 passed**.
- `python3 -m compileall -q src tests eval` — exit 0.
- `git diff --check` — exit 0. `pyproject.toml` parsed with `tomllib`; changed YAML files parsed with PyYAML.
- Safe secret-pattern scan emitted no values. The final scan covered 53
  modified/untracked review files (excluding `.env`, `incoming/`, and
  `docs/providers/`) and found five candidate lines, all in test files with
  explicit synthetic/fake/test markers. `.env` was excluded from scanning and
  checked only by Git metadata.

No smoke script, external network request, API call, upload, real credential,
spend-ledger access, dependency install, staging, commit, or push was performed.
