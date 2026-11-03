# Reply composer approval gate — Codex

Date: 2026-11-03

`compose_reply()` now enforces the farmer-facing approval gate for `answer` and
`ask`: the supplied disease card must have `status: verified`, with both `en`
and `hi` review states set to `REVIEWED`. Failure raises the existing
`ReplyError`. Referral and retake use the separately supplied general safety
card and do not require disease-card approval. `src/mydrak/workflow/followup.py`
was not changed.

Tests use an in-test synthetic approved card. The offline workflow integration
tests make a temporary in-memory approved copy of the structurally validated
`SYNTHETIC_TEST` fixture; this is test metadata only, not actual review evidence.
The fixture file and all production card YAML remain unchanged.

Verification:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_reply_composer.py -q` — exit 0, **30 passed**.
- First full-suite run exposed nine workflow-test failures because those tests rendered the draft synthetic fixture. The gate was retained; tests were updated to use synthetic approved metadata.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_reply_composer.py tests/test_workflow_pipeline.py tests/test_t18_failure_injection.py -q` — exit 0, **58 passed**.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q` — exit 0, **1274 passed**.

No card YAML, registry, claim text, or follow-up gate was changed. No staging,
commit, or push was performed.
