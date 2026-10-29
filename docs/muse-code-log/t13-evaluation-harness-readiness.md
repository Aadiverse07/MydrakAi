# T13 — Evaluation Harness Readiness (Blocked)

Date: 2026-10-29

## Exact master-spec scope

- **C2, T13 acceptance (master PDF p. 12):** “Produces metrics JSON for 3 strategies + cost/accuracy chart.” Priority: MVP.
- **D1 (pp. 14–15):** use 30 labeled images, split dev 20 / test 10; document dataset sources and licenses; include 4–5 deliberate out-of-scope examples. Compare Always Spark, Always Glimmer (single intermediate model), and Mydrak confidence-based routing/escalation. Report crop-and-disease diagnostic accuracy among answered cases and over all cases, escalation rate, deferral/coverage, accuracy versus coverage as acceptance varies, estimated cost from token counts and `config/models.yaml` prices, median/p90 latency, injected-failure recovery, and out-of-scope uncertainty handling. Show failures transparently and do not claim broad reliability from the 10-image test set.
- **D2 (p. 15):** `python eval/run_eval.py --strategy all` writes `eval/results/<run_id>.json`, a Markdown table, accuracy-versus-coverage chart, and cost/accuracy chart.
- **D8 (p. 17):** do not state accuracy, cost, or savings figures that the evaluation harness did not produce.

The example figures on p. 15 (approximately 85%/$0.12, 62%/$0.02, and 82%/$0.04) are not repository measurements and must not be copied into generated results.

## Repository comparison

- `eval/run_eval.py`, a metrics JSON/Markdown/chart producer, strategy prediction records, and T13 tests are absent.
- Current `eval/image_report.py` only inspects local image headers. It reports file metadata and accepted/rejected counts; it does not load labels, compare predictions, calculate diagnostic metrics, or estimate cost.
- The current inventory contains 10 files under `eval/data/dev`; there is no `eval/data/test` image set or `labels.csv`. `eval/data/SOURCES.md` says no images are sourced and their licenses remain UNVERIFIED, which is inconsistent with the 10 files present. Existing `eval/results/dev_image_headers.json` is only a header report, not model evaluation.
- T05 validates structured diagnosis output but has only an injected provider protocol, not actual strategy prediction records or clients. T11 has partial pure signal/policy logic; S2/S3 remain unavailable. T12 samples via injected interfaces but has no model request/context format or real Spark/Glimmer results. These modules cannot supply three measured strategy runs.
- `config/models.yaml` retains TODO model IDs, prices, limits, and host choice. The repo has no trace/cost data source with token counts or per-case latency. Filling cost bars from specification examples or public prices would not satisfy D1's actual-token-count calculation.
- D1's “deferral rate (coverage)” wording and all-cases accuracy treatment for unanswered/out-of-scope cases need a precise computation contract before implementation. No threshold sweep scores are currently available.

## Decision and required inputs

No T13 code or tests were added. Producing the specified artifacts now would require fabricated labels/predictions/costs or a guessed result-input schema, and would misrepresent header inspection as model evaluation. This task is therefore blocked at the evidence/input boundary.

Before implementing the harness, provide or approve: licensed and source-recorded labeled data with dev 20/test 10 and out-of-scope labels; a stable per-image ground-truth/prediction/route record for each of the three strategies (including failure and uncertainty outcomes); token and latency traces; verified model prices in `config/models.yaml`; and exact denominator/coverage rules. Keep the test split report-only. Then implement offline metrics and chart generation against those recorded inputs with synthetic unit fixtures that are explicitly test-only.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_image_eval.py`: **6 passed**. This covers the existing header-report utility only, not T13.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider`: **784 passed**. No new tests were added because no T13 implementation was safe to define.
- `python3 -m compileall -q src tests eval`: exit 0.
- `pyproject.toml` plus all four config/card YAML files parsed successfully.
- Safe pattern scan: 0 matches in this log and added DAILY_LOG lines. `.env` was ignored and untracked by Git metadata (`git check-ignore -v .env`, `git ls-files -- .env`, `git status --short --ignored -- .env`); contents were not read.
- `git diff --check`: exit 0; this new log had no trailing whitespace.

No live APIs, network, media uploads, credentials, credits, dependency installs, or Git history operations were used. No T13 metrics or model-performance claims were generated.
