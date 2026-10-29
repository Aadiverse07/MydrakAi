# T05 — Offline Diagnosis Output Contract and Validation

Date: 2026-10-29

## Specification basis

Master B8 (PDF page 9) gives the diagnosis JSON fields `plant_visible`, `crop`, `issue`, `alternatives`, `symptoms_observed`, `image_issues`, `stated_confidence`, and `segment_prompts`; models must choose configured crops/KB IDs or `unknown`, and must not emit treatment advice, dosage, or chemical names. Invalid JSON gets one repair retry, then fallback. B11 (page 10) separately describes up to two retries with backoff for API timeout/error and says invalid model JSON gets one repair then unknown. T05's C2 acceptance (page 12) is invalid JSON falling back to unknown.

## Implemented contract

- Added a strict exact-key schema validator and typed result object. It validates booleans, allowlisted crop/disease IDs, list-of-text fields, numeric finite confidence in 0..1, duplicate JSON keys, nonstandard JSON constants, and a local 65,536-character parsing bound. Unknown model fields including action/policy/routing fields are rejected. As a project-local consistency rule, `plant_visible: false` requires crop/issue `unknown` and empty alternatives, observed symptoms, and segment prompts.
- B8 only provides the sample confidence string `medium`; no complete band vocabulary is defined. The validator accepts that explicitly shown string or finite numeric confidence; T11 S4 can consume only the numeric form. No reply confidence is mapped from the model string.
- Supported crops and disease IDs are supplied by the trusted caller; no allowlist is invented or sourced from missing disease cards. Invalid configuration prevents the provider call.
- Provider access is only an injected protocol. There is no default client or request schema. Invalid JSON or schema-invalid structured output receives exactly one repair call, then `unknown`; provider/repair exceptions return sanitized `unavailable` without retry. The generic B11 API-error retry/backoff policy is deferred to a future provider implementation; this module performs no API calls.
- Validated output contains no action/policy field and is not connected to a workflow route. Prompt-rule compliance for arbitrary natural-language text cannot be proven by structural schema validation; this module does not generate replies or treatment advice.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_diagnosis_contract.py tests/test_decider_extraction.py tests/test_decider_policy.py tests/test_signals.py` — 121 passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider` — 768 passed, 0 failed.
- In-memory syntax checks, TOML/YAML configuration parsing, and `git diff --check` passed.

Fixtures contain synthetic values only; they establish parsing and control flow, not provider compatibility, model accuracy, or agronomic safety. No network, credentials, uploads, credits, dependency changes, or Git history operations. Live SAM remains NO-GO.
