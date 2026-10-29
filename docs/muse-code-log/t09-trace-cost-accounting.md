# T09 — Offline trace and cost-accounting slice

## Scope and acceptance

Master-spec C2 T09 requires trace/cost accounting with the acceptance “every
case writes steps and totals.” B9 defines case and step fields. This slice
adds SQLite persistence for accepted offline coordinator cases: a case row,
its stage rows, total measured latency, and a cost total only when every step
has a known estimate. SQLite transactions keep case and steps atomic. The
coordinator's existing privacy gate still precedes synthetic SAM parsing.

## Implementation

- Added `src/mydrak/trace/store.py`: local SQLite `cases` and `steps` tables,
  validated dataclasses, atomic insert, readback for tests, and a pure token
  cost helper using per-million rates. Unknown, missing, malformed, or
  `TODO(verify)` prices produce `None`, persisted as SQL `NULL`; explicit
  verified zero rates remain distinct.
- Integrated the store into `coordinate_offline_case()`. Accepted outcomes
  (policy-blocked, referral, manual review) receive a generated case ID and
  safe fixed-name stage rows. No user hash, image hash, mask, reply content,
  synthetic response, mock finding, raw exception, or token count is invented.
- Added `tests/test_trace_store.py` and extended
  `tests/test_workflow_coordinator.py` with storage, atomicity, unknown-cost,
  privacy-boundary, and workflow-integration checks. All fixture data is
  synthetic.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_trace_store.py tests/test_workflow_coordinator.py` — **18 passed**.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider` — **795 passed**.
- `python3 -m compileall -q src tests eval` — exit 0.
- Python TOML/YAML/JSONL parse — exit 0; 1 `pyproject.toml`, 4 YAML files,
  and 1 JSONL file parsed.
- `git diff --check` — exit 0; scoped whitespace scan — 0 findings.
- Safe pattern scan — 0 matches; `.env` ignored and untracked, verified using
  `git check-ignore`, `git ls-files`, and `git status` metadata only. `.env`
  was not opened.
- No API/network calls, uploads, credentials, credits, installs, or Git history
  operations occurred.

## Remaining scope

T09 remains **PARTIAL**: this implementation records offline coordinator
outcomes only. It does not provide event coverage for all future app paths,
token counts, verified provider prices, latency/cost for model calls, or the
per-step `started_at`, other B9 tables (`signals`, `cache`, `eval_runs`). `config/models.yaml`
still marks prices and model settings `TODO(verify)`. Unknown costs stay
unknown. No live SAM or other provider integration is included or authorized.

T17/B5 recovery-history persistence was subsequently implemented in the
shared SQLite store by `src/mydrak/recovery/history.py`; its current limits and
verification are recorded in
`docs/muse-code-log/t17-recovery-history-persistence.md`.
