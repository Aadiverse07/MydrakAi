# Phase 8 — T09 trace, T15 replay, T18 failure injection (Codex)

Date: 2026-10-30

## Scope and acceptance

Implemented the offline B9 trace additions, persistent replay cache integration, and injected B11 failure paths requested for Phase 8. Acceptance checks cover legacy SQLite migration and six B9 tables; populated `started_at` on new steps with unknown cost/token values left NULL; persistence across TraceStore instances; cache key inputs and synthetic provenance; answer/ask/refer/retake replay with sockets blocked and no provider calls; and safe traced outcomes for each requested failure injection.

## Changes

- Trace store: added `eval_runs`, migration for `steps.started_at`, eval-run record/read operations, and bounded workflow response cache validation in the existing B9 SQLite `cache` table. Existing cache payloads remain readable. Unknown historical timestamps, tokens, and prices are not fabricated.
- Workflow: replaced process-local caching with persistent cache lookup keyed by SHA-256 of normalized image hash, language, and voice hint. Cache payloads retain only a fixed synthetic action/reason/reply/severity summary; no raw image, overlay bytes, user content, or voice hint is stored.
- Replay: registered synthetic answer, ask, refer, and retake fixtures and connected them to the current offline bot command. Replay reads only validated local rows and has no live fallback.
- Failure injection: mock diagnosis boundaries exercise two retry attempts after the initial call with short project-local delays; Glimmer exhaustion triggers one Spark escalation; Spark exhaustion refers safely; invalid output gets one repair; SAM, transcription, unsupported-plant, and mock Telegram-send failures return safe outcomes with privacy-safe trace rows.

## Status and limitations

T09, T15, and T18 remain **PARTIAL**. Token counts and prices are unknown and remain NULL. D3 does not define a complete approved fixture inventory; only four bounded synthetic cases are supported. There is no real Telegram, Glimmer, Spark, SAM, or transcription client. Retry delays are project-local offline test behavior because B11 specifies a retry bound but no timing values. This work does not verify provider compatibility or agronomic validity. Live SAM remains **NO-GO**.

## Verification

- Focused command: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_trace_store.py tests/test_workflow_pipeline.py tests/test_offline_replay.py tests/test_bot_adapter.py tests/test_t18_failure_injection.py -q` — **137 passed** after correcting a workflow cache return mapping and updating legacy assertions to the explicit per-sample trace names and B11 bounded retry behavior.
- Full suite: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q` — **1032 passed**.
- Syntax: `python3 -m compileall -q src tests eval` — exit 0.
- Configuration: `python3 -c 'import tomllib, pathlib, yaml; tomllib.loads(pathlib.Path("pyproject.toml").read_text()); files=list(pathlib.Path("config").glob("*.yaml"))+list(pathlib.Path("kb").glob("*.yaml"))+list(pathlib.Path("kb/cards").glob("*.yaml")); [yaml.safe_load(p.read_text()) for p in files]; print(f"TOML parsed; YAML parsed: {len(files)} files")'` — exit 0; TOML and 6 YAML files parsed.
- Whitespace: `git diff --check` — exit 0.
- Safe secret-pattern scan over 17 changed/new files — **0 matches**; the scan reported count and locations only. `.env` metadata: `git check-ignore -v .env` — exit 0 (`.gitignore:2`); `git ls-files -- .env` — exit 0, no paths; `git status --short --ignored -- .env` — exit 0 (`!! .env`). `.env` contents were not read.
- Repository began on `integration/phase-2-task-1-sam-parser` at `2b4856a902a9772305c4e14e4f5e851b75e8df47`; `docs/architecture.md` was clean and remains untouched. Commit/push results are reported separately after the authorized explicit-path publication.

No network/API calls, media uploads, credentials, `.env` reads, dependency installs, or credit use occurred.
