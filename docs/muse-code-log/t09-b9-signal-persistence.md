# T09/T11 — B9 Decider signal persistence

## Scope and source

Master-spec B9 defines `signals(case_id,s1,s2,s3,s4,score,decision,escalated)`;
B3 defines normalized 0–1 signals and the Decider actions. T09 is an MVP trace
task. This slice persists actual routed output only when a caller supplies an
existing trace case and the local SQLite store. It does not introduce signal
measurements or thresholds.

## Implementation

- Added the B9 `signals` table to the existing `TraceStore` database and
  `record_signals()` / `get_signals()` methods. `case_id` references an
  existing case; numeric values must be finite and within 0–1; unavailable
  values use SQL `NULL`; decision and escalation values are validated. Duplicate
  rows fail instead of overwriting a prior record. Existing SQLite backups
  include signal rows.
- Added opt-in B9 tracing to `route_signals()`. Existing callers remain pure
  when no trace context is supplied. With trace enabled, complete, unavailable,
  and malformed signal sets record the final safe route and only valid numeric
  values. Measurement reason strings, provider text, user data, and raw input
  are not stored.
- The offline workflow coordinator is not wired to this path because it has no
  validated model samples, symptom overlap, image-quality scores, or confidence
  measurement. No signal value is fabricated to fill that gap.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_trace_store.py tests/test_decider_extraction.py tests/test_decider_policy.py tests/test_offline_replay.py` — 145 passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider` — 893 passed.
- `python3 -m compileall -q src tests eval` — exit 0.
- TOML, three YAML configs, and JSONL parsed; 2 JSONL rows, 0 executed.
- `git diff --check` — passed. Scoped whitespace scan — 0 findings.
- Safe secret-pattern scan — 0 matches; `.env` excluded. Git metadata confirms
  `.env` is ignored and untracked; contents were not read.

## Status

T09 remains **PARTIAL**: `eval_runs`, per-step `started_at`, complete
application event traces, provider token usage, and verified pricing are still
absent. T11 remains **PARTIAL** because T04 quality measurements, matching-card
S2 overlap rules, confidence-band mapping, and real diagnosis inputs remain
unavailable. Synthetic unit tests establish storage and routing contracts,
not agronomic accuracy. Live SAM remains **NO-GO**.

No API/network calls, uploads, credentials, installs, credits, or Git history
operations occurred.
