# Phase 9b — User-reported Spark smoke

**Tool:** Codex
**Date:** 2026-10-31
**Scope:** Record user-provided evidence; no live request was run by Codex.

The user reports running `scripts/smoke_spark.py` with the standard
non-Contributor model and a `$0.25` cap. Reported output was:

- `status=response_received`
- `request_sent=true`
- `latency_ms=7944`
- `tokens_in=154`
- `tokens_out=1632`
- `estimated_cost_usd=0.0071285`

This is attributed to the user's report and was not independently reproduced.
The current smoke code emits `response_received` after the reply passes its
configured diagnosis-schema validator. `tokens_out` is near the tier-2
`max_tokens` value of 2048; this is the output-token bound, distinct from the
reported `$0.25` spend cap. The reported estimated cost is below that cap.

Glimmer was not tested because Together credit was unavailable. Voice,
Telegram, and SAM remain unverified. No `config/models.yaml` value was changed.
Credit balance/expiry, billing behavior, privacy/retention gates, and broader
provider compatibility remain unverified. T02 remains **PARTIAL**.

## Offline documentation verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_live_smoke_diagnostics.py tests/test_live_smoke.py tests/test_live_clients.py tests/test_live_guard.py -q` — exit 0, **62 passed**.
- `python3 -m pytest -q` — exit 0, **1118 passed**.
- `python3 -m compileall -q src tests eval` — exit 0.
- TOML/YAML parse — exit 0; `pyproject.toml` and 5 config/KB YAML files parsed.
- `git diff --check` — exit 0. Scoped whitespace scan over the three documentation files — 0 trailing-whitespace lines.
- Safe high-confidence secret-pattern scan over changed documentation additions — 0 matches. `.env` metadata only: ignored by `.gitignore`, no tracked path; contents were not read.
- No live smoke command was run by Codex. `config/models.yaml` was not edited.
