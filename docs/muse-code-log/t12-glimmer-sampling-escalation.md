# T12 — Offline Glimmer Sampling and Escalation Contract

Date: 2026-10-29

## Scope and source requirements

The master specification's B1 says Glimmer is sampled twice per case, structured JSON is evaluated by the Decider, and disagreement/escalation-band outcomes can go once to Spark with SAM crops before re-scoring. B3 defines S1's values (1.0 for same crop and disease, 0.5 for same crop only, otherwise 0.0), and caps escalation at one per case. C2 Task T12 acceptance is: “Disagreement triggers exactly one escalation.” T05's existing B8 validator permits one repair attempt for invalid structured output.

## Implemented offline slice

- Added `src/mydrak/vision/sampling.py`; it obtains two Glimmer `DiagnosisResult`s through the existing injected B8 `DiagnosisProvider` interface and validates them with `run_diagnosis_validation()`.
- Reuses T11 `extract_agreement()` after mapping B8's `issue` ID to the S1 extractor's `disease` field. Same supported crop+issue yields S1=1.0; same crop/different issue yields 0.5; different crop yields 0.0.
- Valid disagreement invokes the injected Spark provider exactly once. Invalid/missing samples and provider errors fail closed without Spark. A valid B8 `unknown` label is not treated as agreement or as a disease disagreement.
- `SamplingState` carries a per-case escalation count. Reusing the returned state prevents another Spark invocation. This state is transient and caller-carried; there is no durable case-state integration.
- B8 schema validation and its one repair attempt are reused. A repair is not a second Spark escalation. No client, request serialization, network code, provider-specific output format, disease content, or SAM crop data is added.

## Explicitly incomplete / unverified

This is a limited T12 contract, not full T12 or live integration. B3's score-driven escalation condition is not wired because S2 card-overlap behavior and S3 image-quality measurements are unavailable, and the configured thresholds are marked placeholders. The Spark result is schema-validated, but no re-score or final answer action is produced. The repository has no supported Spark request/prompt contract or SAM-crop evidence input; those cannot be guessed. The caller must preserve `SamplingState` for the case; process-restart durability is not provided. Synthetic tests establish control flow only, not model quality or compatibility.

## Verification

Focused command `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_glimmer_sampling.py tests/test_diagnosis_contract.py tests/test_decider_extraction.py`: **124 passed**. Full suite `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider`: **784 passed**. `python3 -m compileall -q src tests eval` passed. TOML plus four YAML files parsed. Safe secret-pattern scan found 0 matches in changed files/additions. `.env` was confirmed ignored and untracked through Git metadata only. `git diff --check` and trailing-whitespace scan of three new files passed. No API calls, media uploads, credentials, dependency installs, or Git history operations occurred. Live SAM remains NO-GO.
