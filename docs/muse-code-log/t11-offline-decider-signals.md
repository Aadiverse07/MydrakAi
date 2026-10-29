# T11 — Offline Signal Extraction and Decider Integration

Date: 2026-10-29

## Specification basis

B3 (master PDF page 7) defines S1 sample agreement as 1.0 for same crop and disease, 0.5 for same crop only, and 0 otherwise; S2 requires a KB card and symptom keyword overlap; S3 uses blur, brightness range, and leaf coverage mapped to a score; S4 is model-stated numeric confidence or a band in 0..1. The weighted score uses four weights summing to 1. Policy order is quality retake, confident answer, one escalation, bounded follow-up, then referral. C2 (page 12) says T11 table-driven tests cover every B3 branch.

## Implementation and availability

- `extract_agreement()` computes S1 from synthetic/upstream mappings with nonempty `crop` and `disease` fields. Missing or malformed samples are unavailable.
- `extract_confidence()` accepts a finite numeric value in 0..1 as S4. Missing/invalid values and confidence bands are unavailable because band-to-number mapping is not specified.
- `extract_kb_match()` returns 0 when the predicted label has no corresponding card. If a card matches, S2 remains unavailable: B3 does not define tokenization/normalization or the overlap denominator, and no matcher currently supplies this signal.
- `extract_quality()` marks S3 unavailable pending T04. No blur, brightness, or leaf-coverage values are invented.
- `route_signals()` refers without a score if any signal is unavailable or invalid. With a complete validated set, it calls the existing weighted `combine()` and B3 `decide()` policy.
- `combine()` now validates finite nonboolean signals, exact B3 weight keys, finite nonnegative weights, and sum-to-one. `decide()` validates finite unit-range inputs, booleans, follow-up bounds, and rejects follow-up use before escalation.
- The workflow coordinator remains unchanged: its current input contract has no two model samples, KB overlap measurement, T04 quality signal, or T05 confidence output. `config/thresholds.yaml` values remain placeholders; test thresholds are synthetic branch fixtures only.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_decider_extraction.py tests/test_signals.py tests/test_decider_policy.py` — 79 passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider` — 726 passed, 0 failed.
- In-memory syntax and TOML/YAML configuration parsing passed; `git diff --check` clean.

No API/network calls, media uploads, credentials, dependency changes, or Git history operations occurred. All new observations are synthetic test data; they do not establish model accuracy, diagnostic performance, or agronomic safety. Live SAM remains NO-GO.
