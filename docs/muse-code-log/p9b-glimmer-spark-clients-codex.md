# Phase 9b — Glimmer and Spark client boundaries

**Tool:** Codex
**Scope:** Offline implementation and tests only. No live execution.

## Pre-edit scope and acceptance

Files planned for this slice: `src/mydrak/live/guard.py`, `retry.py`, new
`http.py`, `provider_contract.py`, and `clients.py`; new Glimmer/Spark smoke
scripts; focused client, smoke, and guard tests; `README.md`,
`scripts/README.md`, `docs/verification/roadmap_reconciliation.md`,
`docs/DAILY_LOG.md`, and this session log. The user-edited `config/models.yaml`
and supplied `docs/providers/` references were inspected but are preserved and
excluded from staging.

Acceptance checked offline: documented JSON request shapes are serialized;
response envelope and usage fields are parsed; cost requires input estimate,
output max, and both prices; guard refuses before transport when a gate is
missing; retries are capped at two; B8's existing diagnosis validator performs
one repair and returns unknown/unavailable safely; credentials remain out of
body, trace, user-visible output, and safe errors; Contributor requires verified
public-test evidence; smoke CLIs refuse without explicit authorization; offline
workflow callers accept only deterministic mock providers.

## Source and implementation boundaries

The files under `docs/providers/` were treated as user-supplied request and
response references, not as independently verified official documentation.
They show Together's `/v1/chat/completions` multimodal user content array with a
JPEG data URL, `max_tokens`, and temperature, and Meta's same endpoint shape
with text-only user content and `max_tokens`. Both examples show a
`choices[0].message.content` response and prompt/completion token usage. The
clients implement only those fields; no unshown response-format, image field for
Spark, or other provider setting was added. Configured IDs, endpoint values,
prices, input-token estimates, timeouts, account access, and compatibility remain
UNVERIFIED.

Added standard-library HTTP transport, provider response parsing, guarded
Together Glimmer and Meta Spark implementations, and one-logical-request smoke
CLIs using synthetic input. Every HTTP attempt reserves worst-case estimated
cost first. Actual token/cost trace values remain `None` when usage is absent or
invalid. The retry helper retries only bounded provider transport/status/envelope
errors; authorization/config/policy and trace errors do not retry. The existing
`run_diagnosis_validation()` caller applies B8 validation and its one repair to
raw returned content. The clients do not make the offline workflow select live
providers. No Voice, Telegram, or SAM client was added.

The Glimmer smoke sample is a tiny source-embedded synthetic JPEG. Spark's
provided reference is text-only, so its smoke input is fixed synthetic text and
contains no image. The scripts print only status, latency, token counts, and
estimated cost. They were not run against a provider. A local spend reservation
is an estimate and cannot guarantee zero billing; the first live cap and a
separate explicit live authorization remain with the user.

## Verification

Commands and results:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_live_clients.py tests/test_live_smoke.py tests/test_live_guard.py -q` — exit 0, **48 passed**.
- `python3 -m pytest -q` — exit 0, **1104 passed**.
- `python3 -m compileall -q src tests eval` — exit 0.
- In-memory TOML/YAML parse of `pyproject.toml`, all `config/*.yaml`, and all `kb/*.yaml` — exit 0; **1 TOML and 5 YAML files parsed**.
- AST-based extraction and in-memory Pillow verification of the embedded smoke fixture — exit 0; fixture verifies as JPEG.
- `git diff --check` — exit 0; no output. Scoped whitespace scan across the 16 changed/new files — **0 trailing-whitespace lines**.
- High-confidence secret-pattern scan over changed implementation, tests, scripts,
  and docs (excluding `.env`, user-edited `config/models.yaml`, and the supplied
  provider references) — **0 matches**; no matched values were printed.
- `git check-ignore -v .env` — exit 0, `.gitignore:2:.env`.
- `git ls-files -- .env` — exit 0, no tracked path returned.
- `git status --short --ignored -- .env` — exit 0, reports ignored `.env` metadata only (`!! .env`); contents were not read.

Offline tests used injected in-memory transports only. No API, network, media
upload, credential, credit, dependency installation, `.env` read, or Git history
operation was used. `config/models.yaml` and `docs/providers/` remain
pre-existing user-supplied, unstaged work. Live SAM remains **NO-GO**.
