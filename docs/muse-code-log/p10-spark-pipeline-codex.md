# Phase 10 — Spark-only image pipeline wiring (Codex)

## Scope and source basis

Implemented the B11 “Glimmer unavailable: go directly to Spark” route as an explicit `spark_only` mode. B1 ordering is preserved for the selected branch: intake and data-policy checks, local preprocessing, cache lookup, signal extraction, Decider, synthetic/mock-only SAM stage, KB lookup, fixed reply composition, and SQLite trace. B3 S1/S2/S3 remain unavailable in this production path, so the unchanged Decider routes to referral. B12 public-test Contributor restrictions and standard-model private-data requirements remain enforced by the existing evidence gate plus the new image marker/config checks.

The JPEG image request follows only the Chat Completions image example in the user-supplied `docs/providers/meta_spark.md`: a user message with text then an `image_url` block whose URL is a JPEG base64 data URL. This repository document is not independently verified provider documentation. No undocumented `response_format` parameter was added. The existing B8 prompt requests JSON only; the existing validator checks the fixed schema and performs one repair request before returning unknown.

## Implemented

- Added image input to `SparkClient`, requiring preprocessed JPEG bytes and an exact `public-test` or `private` marker. Private image transmission requires `allow_private_upload: true`, standard provider mode, and existing authorization/privacy evidence; the setting is absent from the current config and defaults to refusal. Contributor selection remains restricted by `require_external_processing_allowed()` to explicitly evidenced public-test data.
- Added `tier2.diagnosis_max_tokens: 512` as a project-local conservative diagnosis JSON bound. Existing 2048 max, model IDs, endpoints, and prices were preserved. Guard reservation uses the diagnosis cap for image requests.
- Added explicit `run_pipeline_mode("spark_only", ...)` dispatch. The live branch requires the concrete guarded Spark client; an arbitrary injected client cannot claim live provenance or add an alternate network implementation. The Spark client still takes its HTTP transport by injection for offline tests.
- A single logical Spark escalation is recorded. Its HTTP request uses the existing maximum of two retries; the B8 repair is one separate repair operation with its own bounded HTTP retry policy. No Glimmer requests, mock/replay fallback, or provider-result caching occurs.
- The result contains no model crop/disease claims, and no answer/ask path can use test-only KB cards. The synthetic SAM provider is explicitly mock-only; its result is discarded, and the returned `overlay_bytes` and `severity_pct` are always `None`.
- Added a guarded local-image CLI. It requires an explicit public-test and rights confirmation plus the existing `--live-authorized`, `MYDRAK_LIVE=1`, spend cap, credential, and persistent-ledger gates. Its output is fixed metadata only.

## Limits and status

- The 2026-10-31 standard-model Spark smoke was reported by the user and was text-only. It does not verify image payload compatibility or this pipeline end to end. This task did not make a live request.
- Glimmer has not been tested because Together credit was unavailable. The pipeline uses B11's Glimmer-unavailable route; it does not implement two Glimmer samples or live disagreement-based escalation.
- Production crop/disease vocabularies and reviewed disease-card content are unavailable; the CLI therefore validates only outputs allowed by the empty production vocabulary and safely refers. S3 remains unavailable, so normal production routing refers even if S4 is present.
- Hindi replies remain unavailable pending review. Private upload remains blocked until the local config explicitly enables it and all evidence gates pass. SAM remains mock-only and Live SAM remains **NO-GO**.
- T05 and T12 remain **PARTIAL**; no C2 task is marked complete by this slice.

## Files changed

- `src/mydrak/live/clients.py`, `src/mydrak/live/spark_client.py`, `src/mydrak/live/guard.py`
- `src/mydrak/workflow/spark_only.py`, `src/mydrak/workflow/modes.py`
- `scripts/run_spark_case.py`
- `tests/test_live_clients.py`, `tests/test_live_guard.py`, `tests/test_spark_only_pipeline.py`, `tests/test_spark_case_script.py`
- `config/models.yaml` (one new diagnosis token bound; prior user-supplied values retained)
- `docs/verification/roadmap_reconciliation.md`, `docs/DAILY_LOG.md`

## Verification

- `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_live_clients.py tests/test_live_guard.py tests/test_spark_only_pipeline.py tests/test_spark_case_script.py tests/test_workflow_pipeline.py -q` — exit 0, **84 passed**.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q` — exit 0, **1139 passed**.
- `PYTHONPATH=src python3 -m compileall -q src tests eval` — exit 0.
- TOML/YAML parse script — exit 0; `pyproject.toml` and **6** `config/`/`kb/` YAML files parsed.
- Safe secret-pattern scan over the Phase 10 source, tests, config, and docs (assignment, private-key, and bearer patterns) — exit 0; **0 matches**. `.env` was excluded and never read.
- Metadata-only `.env` checks: `git check-ignore -v .env` showed `.gitignore:2:.env`; `git ls-files -- .env` returned no path; `git status --short --ignored -- .env` reported `!! .env`.
- New Phase 10 untracked files: **7 checked, 0 trailing-whitespace lines**. A separate whole-untracked-file scan found one pre-existing trailing-whitespace line in the user-provided, untracked `docs/providers/together_glimmer.md`; it was left untouched.
- `git diff --check` — exit 0 after removing an extra blank line at the end of this task's daily-log entry.

No network/API call, upload, credential read, credit use, dependency installation, or live test was performed. The existing user changes in `config/models.yaml` and the untracked `docs/providers/` references are preserved separately from Phase 10's committed changes.
