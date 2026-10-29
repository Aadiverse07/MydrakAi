# Offline evaluation core

This standard-library-only harness implements the input/metrics/reporting core
for the master specification's D1/D2 evaluation requirements. It does not
load, label, decode, or inspect images and does not invoke model providers.
The existing `image_report.py` remains a separate header-only inventory tool;
the ten files in `data/dev` are not labels or evaluation cases.

## Input contract

Labels CSV columns are exactly `case_id,split,label,out_of_scope,provenance`;
`split` is `dev` or `test`, and `out_of_scope` is `true` or `false`.
Predictions JSON is a list with one object for each label and each provided
strategy. Objects contain the metrics record fields `case_id`, `strategy`,
`predicted`, `action`, `escalated`, `tokens_in`, `tokens_out`, `latency_ms`,
`price_in_per_1m`, `price_out_per_1m`, and optional `score` in [0,1]. Actions
are `answer`, `ask`, `refer`, or `retake`. Predictions must include every case
for every strategy; missing rows are errors. `score` is an optional recorded
score, included for descriptive accuracy/coverage curves; its meaning and
threshold mapping remain project-local and are not inferred by this tool.
`provenance` should identify synthetic fixtures (for example,
`synthetic_fixture`) so all report surfaces can label them.

Example (using only repository test fixtures):

```sh
python3 eval/run_eval.py \
  --labels tests/fixtures/eval/synthetic_labels.csv \
  --predictions tests/fixtures/eval/synthetic_predictions.json \
  --mode replay --strategy all --run-id synthetic-example
```

`--strategy all` evaluates every strategy present in the supplied predictions;
single-strategy filtering is not implemented. `--mode` accepts only `replay`; live mode is rejected. Output files are placed
under `eval/results/` by default. Reporting computes metrics only for test
records. Threshold metadata is loaded only from a caller-provided frozen JSON
file matching the documented local envelope (`schema`, `frozen`,
`thresholds`). When no file exists, each output says thresholds are missing;
the tool does not tune or invent thresholds. It does not assume
`config/thresholds.yaml` placeholders are frozen thresholds.

## Metrics and limitations

- Answered accuracy compares predictions only among `answer` cases.
- All-case accuracy counts only correct `answer` cases; deferrals and retakes
  are incorrect for this metric. Coverage is `answer` cases / all cases.
- Escalation rate counts the recorded `escalated` flag or an expert referral
  (`action: refer`). Deferral rate counts
  `ask` and `refer`; retakes are reported separately.
- Cost/task uses recorded tokens and per-million input/output prices. If any
  required value is missing for any strategy row, cost is `UNKNOWN` (`null`),
  never zero. Prices must be verified before interpreting cost as real.
- Median latency uses the midpoint for an even sample; p90 uses nearest rank.
- Out-of-scope uncertainty handling counts `ask`, `refer`, or `retake` actions.
- Curves use records with recorded scores as the denominator; a row is covered
  at a cutoff only when it also has a prediction and meets that cutoff. Curve
  accuracy compares admitted predictions with labels. These descriptive
  project-local conventions do not choose a threshold.

The metric denominator choices above are explicit project-local conventions
for this harness. Synthetic fixtures validate mechanics only; they are not
diagnoses, measured model results, or provider responses. No accuracy, cost,
savings, general reliability, or agricultural safety claim follows from them.
T13 remains blocked for the specification's real licensed/labeled dataset,
actual strategy predictions, and verified token/latency/pricing evidence.
