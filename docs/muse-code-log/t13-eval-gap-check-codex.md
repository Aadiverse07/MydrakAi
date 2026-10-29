# T13 Evaluation Gap Check — Codex

Date: 2026-10-29

## Scope and findings

Compared the existing offline evaluator with the master specification's D1, D2,
D3, and D8 and the earlier T13 acceptance list. This was a focused gap check;
the metrics and chart modules were not rewritten, and `eval/chart.py` was not
changed.

| Requirement | Status | Evidence |
|---|---|---|
| Accuracy among answered and across all cases | MET | `eval/metrics.py` computes both; `tests/test_eval_metrics.py` covers all-correct, all-deferred, and non-answer behavior. |
| Escalation rate includes Spark escalation and expert referral | MET after fix | `eval/metrics.py` counts `escalated` or `action == "refer"`; regression test uses `refer` with `escalated=False`. |
| Deferral and coverage rates | MET | Ask/refer deferral and answer coverage are tested in `tests/test_eval_metrics.py`. |
| Cost per task unknown if any required token or price is missing | MET | Missing each of tokens-in, tokens-out, input price, and output price yields `None` and `cost_unknown=True`; zero is never substituted. |
| Median and p90 latency | MET | Median and nearest-rank p90 are implemented and tested for singleton, even, and five-item inputs. |
| Out-of-scope uncertainty handling | MET | Ask/refer/retake handling is tested with synthetic out-of-scope cases. |
| Accuracy-versus-coverage curve from recorded scores | MET after fix | Curves require a prediction for coverage, retain all scored rows in the denominator, and are exercised with all-deferred and mixed cases. Threshold interpretation remains project-local. |
| Tuning rejects test records | MET | `dev_tuning_curves()` raises for any non-dev row; tested. |
| Missing frozen-threshold file is reported | MET | CLI reports `status: missing` and the Markdown report states threshold status; tested with an absent path. |
| Synthetic chart marker and unknown-cost label | MET | Both hand-written SVGs show the synthetic marker; cost chart labels unknown cost; tests parse both SVGs. |
| D1/D2 specification example figures are absent | MET | Search across evaluator, synthetic fixtures, roadmap, and daily log found no use of the example outcome/cost figures. |
| D2 `--strategy all` invocation | MET after fix | CLI accepts `--strategy all` and evaluates all strategy records present in the supplied files; synthetic CLI test invokes this flag. |
| D3 all demo cases available as offline replay | NOT MET (outside T13 fix scope) | `src/mydrak/replay/replay.py` currently registers only `synthetic-referral-01`; roadmap T15 records the missing full D3 inventory. No fixture inventory was invented here. |
| D8 real failure examples/thumbnails and real performance evidence | UNVERIFIED | Evaluator consumes labels and recorded predictions, not images; there is no real labeled dataset in this work. No image or performance claim was added. |

T13 remains **PARTIAL** for its offline core and **BLOCKED** for real-data
evaluation. Synthetic fixtures validate mechanics only. The 10 existing files
under `eval/data/dev` were neither opened nor treated as labels.

## Changed files

- `eval/metrics.py` — two narrow metric corrections.
- `eval/run_eval.py` — explicit `--strategy all` option.
- `tests/test_eval_metrics.py`, `tests/test_eval_chart.py` — regressions.
- `eval/README.md` — project-local metric and CLI contract.
- `docs/verification/roadmap_reconciliation.md`, `docs/DAILY_LOG.md` — status and factual record.
- This session log.

## Verification

- `python3 -m pytest tests/test_eval_metrics.py tests/test_eval_chart.py -q` — exit 0; **30 passed**.
- `python3 -m pytest -q` — exit 0; **923 passed**.
- `python3 -m compileall -q src tests eval` — exit 0.
- TOML/YAML/fixture parse — exit 0; `pyproject.toml`, 3 YAML files, and 1 evaluation JSON fixture parsed.
- Safe secret-pattern scan — exit 0; 0 matches across 8 changed/untracked files; `.env` explicitly excluded and never read.
- `.env` metadata: `git check-ignore -v .env` exit 0 (`.gitignore:2:.env`); `git ls-files -- .env` exit 0 with no tracked path; `git status --short --ignored -- .env` exit 0 (`!! .env`).
- `git diff --check` — exit 0; untracked-file whitespace scan — exit 0; 0 trailing-whitespace lines in this session log.
- Forbidden D1/D2 example-figure search — exit 1 (no matches).

No network/API calls, image access, uploads, credentials, credit use, dependency
installation, or Git history operations were performed. Live SAM remains
**NO-GO**.
