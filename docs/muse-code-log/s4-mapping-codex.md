# T11 S4 confidence mapping — Codex

Date: 2026-10-30

## Requirement and decision

Master-spec B3 defines S4 as model-stated confidence supplied as a number or band in the 0–1 range, but does not define textual band values or their numeric mapping. The user approved a project-local placeholder mapping: low=0.25, medium=0.5, high=0.75, aggregating the two Glimmer samples by taking the lower value. These values and this mapping remain **UNVERIFIED** and are not calibrated. S3 remains unavailable; therefore ordinary production routing continues to refer. No quality cutoff, weight, or policy threshold was introduced or changed.

## Implementation

- `decider.signals.aggregate_stated_confidence()` is a pure function over two sample values and an explicit mapping. Mapping keys/values are strictly validated. Missing or unknown samples yield unavailable; malformed mappings raise a clear `ValueError`. Numeric sample values are range-checked and aggregated using the same lower-value rule.
- `config/thresholds.yaml` stores the user-approved placeholder mapping, explicitly labeled UNVERIFIED.
- The existing diagnosis validator accepts configured band labels when called from the workflow; the offline coordinator and photo pipeline compute S4 from both validated samples. The coordinator and pipeline still route to referral whenever S3 is unavailable.
- `quality_min` and retake routing remain disabled pending user-provided blur and brightness thresholds.

## Acceptance coverage

Focused tests cover each configured band, mixed-band lower-value aggregation, numeric aggregation, missing/invalid values, both samples missing, reading modified values from a temporary YAML file, malformed configuration, configured band validation, coordinator mapping, pipeline mapping, and referral despite available S4 because S3 is unavailable.

## Verification

Focused command: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_s4_mapping.py tests/test_signals.py tests/test_diagnosis_contract.py tests/test_decider_extraction.py tests/test_workflow_coordinator.py tests/test_workflow_pipeline.py -q` — **180 passed**.

- Full suite: `python3 -m pytest -q` — **1056 passed**.
- Syntax: `python3 -m compileall -q src tests eval` — exit 0.
- Configuration: `python3 -c 'import tomllib, pathlib, yaml; tomllib.loads(pathlib.Path("pyproject.toml").read_text()); files=list(pathlib.Path("config").glob("*.yaml"))+list(pathlib.Path("kb").glob("*.yaml"))+list(pathlib.Path("kb/cards").glob("*.yaml")); [yaml.safe_load(p.read_text()) for p in files]; print(f"TOML parsed; YAML parsed: {len(files)} files")'` — exit 0; TOML and six YAML files parsed.
- Whitespace: `git diff --check` — exit 0.
- Safe secret-pattern scan: 0 matches across 14 changed/new files; matched content is suppressed. `.env` metadata: `git check-ignore -v .env` shows `.gitignore:2`; `git ls-files -- .env` returns no path; `git status --short --ignored -- .env` reports `!! .env`. Contents not read.
- Final Git state after publication: current branch `integration/phase-2-task-1-sam-parser`; commit hash and push output are reported in the completion message.
