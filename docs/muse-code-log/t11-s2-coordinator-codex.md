# T11 S2 and Coordinator Bridge — Codex

Date: 2026-10-29

## Scope

Implemented the S2 rule specified in the approved Phase 2 task and connected
the existing `route_signals()` through an offline coordinator entry point. The
master B3 defines S2 as KB-card symptom overlap; the detailed phrase
normalization and denominator below are the project-local decision supplied
for this task.

S2 counts distinct observed phrases that exactly match phrases from the
selected card, divided by distinct normalized observed phrases. Normalization
casefolds/lowercases, trims, collapses whitespace, and treats Unicode
punctuation as a word boundary. Repeated observations count once; extra card
symptoms do not affect the denominator. No observations yields unavailable
(`None`); a nonempty observation list with no matching card or an empty card
symptom list yields `0.0`. Malformed phrase lists are unavailable through the
extractor and rejected by the pure helper.

`coordinate_mock_tier1_results()` accepts only two valid T05 `DiagnosisResult`
objects. It extracts S1, computes S2 only when crop and issue agree, and calls
`route_signals()`. For this synthetic bridge, the first sample supplies
`symptoms_observed`; no farmer answer or disease conclusion is inferred. S3
remains unavailable pending T04 measurements and S4 aggregation remains
unresolved, so the route fails closed to referral. Tests use synthetic IDs,
card phrases, and policy constants only. No model/provider call or weight or
threshold tuning occurs.

## Changed files

- `src/mydrak/decider/signals.py`, `src/mydrak/decider/extraction.py`
- `src/mydrak/workflow/coordinator.py`
- `tests/test_decider_extraction.py`, `tests/test_workflow_coordinator.py`
- `docs/verification/roadmap_reconciliation.md`
- `docs/verification/t06-disease-card-content-plan.md`
- `docs/DAILY_LOG.md`
- This session log

The roadmap test reference now points to the actual `tests/test_decider_policy.py`
and includes `tests/test_signals.py`; the nonexistent `tests/test_decider.py`
reference was removed. T06/T11 remain partial because no reviewed production
disease-card corpus or S3 measurements are available.

## Verification

- `python3 -m pytest tests/test_signals.py tests/test_decider_extraction.py tests/test_decider_policy.py tests/test_workflow_coordinator.py -q` — exit 0; **107 passed**.
- `python3 -m pytest -q` — exit 0; **937 passed**.
- `python3 -m compileall -q src tests eval` — exit 0.
- TOML/YAML parsing — exit 0; `pyproject.toml` and all 3 `config/*.yaml` files parsed.
- Safe secret-pattern scan — exit 0; 0 matches across 9 changed/untracked files; `.env` explicitly excluded and never read.
- `.env` metadata: `git check-ignore -v .env` exit 0 (`.gitignore:2:.env`); `git ls-files -- .env` exit 0 with no tracked path; `git status --short --ignored -- .env` exit 0 (`!! .env`).
- `git diff --check` — exit 0; new-file whitespace scan — exit 0; 0 trailing-whitespace lines.

No live calls, network access, uploads, credentials, credits, or dependency
installation were used. Live SAM remains **NO-GO**.
