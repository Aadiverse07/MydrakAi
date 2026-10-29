# T13 Offline Evaluation Core — Codex

Date: 2026-10-29

## Scope and requirements

Implemented an offline standard-library-only core for the master specification's
D1/D2 evaluation path: per-case metrics, test-split reporting, descriptive
score/coverage curves, JSON and Markdown reports, and hand-written SVG charts.
Inputs are label CSV and prediction JSON; no image is opened. Synthetic fixture
data is explicitly named/labeled synthetic. `eval/image_report.py` is
unchanged.

The metric contract reports answered accuracy, all-case accuracy, recorded
escalation, ask/refer deferral, answer coverage, cost per task, median/p90
latency, and out-of-scope uncertainty handling. This implementation makes
project-local denominator decisions explicit in `eval/README.md`; it does not
claim those choices settle broader specification ambiguity. Required cost
evidence missing in any row yields JSON `null` and `cost_unknown: true`, never
zero. Tuning curves accept only dev records; CLI reporting uses test records.
Frozen-threshold metadata is reported as missing when the default frozen file
is absent. Curves describe recorded scores and never select a threshold.

## Changed files

- `eval/__init__.py`, `eval/metrics.py`, `eval/chart.py`, `eval/run_eval.py`
- `tests/fixtures/eval/synthetic_labels.csv`
- `tests/fixtures/eval/synthetic_predictions.json`
- `tests/test_eval_metrics.py`, `tests/test_eval_chart.py`
- `eval/README.md`
- `docs/verification/roadmap_reconciliation.md` (T13 is PARTIAL)
- `docs/DAILY_LOG.md`
- This session log

The existing ten `eval/data/dev` images were not accessed or treated as labeled.
No dependencies were added. No provider, API, network, upload, credential, or
live evaluation path was added.

## Verification performed

- `python3 -m pytest tests/test_eval_metrics.py tests/test_eval_chart.py -q` — exit 0; **23 passed**.
- `python3 -m pytest -q` — exit 0; **916 passed**.
- `python3 -m compileall -q src tests eval` — exit 0.
- `git diff --check` — exit 0.
- Safe secret-pattern scan over the new files and added lines in the changed tracked docs — exit 0; **0 matches** across 1,021 lines; values suppressed.
- New/untracked-file whitespace scan — **0 trailing-whitespace lines** across 9 files.
- `git check-ignore -v .env` — exit 0; `.gitignore:2:.env`.
- `git ls-files -- .env` — exit 0; no tracked path.
- `git status --short --ignored -- .env` — exit 0; `!! .env` (ignored; contents not read).

## Remaining T13 blockers

This is not full T13 completion. The master dataset and its evidence are still
absent: 30 licensed/labeled cases (20 dev/10 test), actual outcomes for the
required strategies, verified token/latency traces and prices, and approved
frozen thresholds. The current test fixtures validate mechanics only; they do
not measure model accuracy, provider compatibility, or agricultural validity.
Threshold-score mapping remains descriptive/local pending approved definitions.
Live SAM remains NO-GO and unauthorized.
