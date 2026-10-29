# SAM offline request serialization — Muse session log

**Date:** 2026-10-28. **Branch:** `integration/phase-2-task-1-sam-parser`.
**Baseline HEAD:** `858b1b797aaadef17bff012d4d9047d0a933e622` (verified before editing).
Pre-existing changes preserved; nothing staged, committed, or pushed.

## Added (all in existing `src/mydrak/sam/client.py` + `tests/test_sam_client.py`)

- `SAM_API_BASE_URL` + `RESPONSES_PATH` with `canonical_responses_url()`
  (single construction point; anything else rejected, never joined).
- `serialize_sam_body()` — pure, deterministic: top-level `model` +
  `input` (exactly one user message, `input_text` then `input_image`
  parts) + `stream`. Shape follows the task-supplied official findings,
  corroborated by recorded matrix rows (base URL, POST path, message
  parts, URL/data-URL inputs); not proof of live compatibility.
- Image validation: public HTTP(S) URLs or base64 data URLs only
  (mediatype-agnostic payload with base64 alphabet check); malformed
  inputs fail closed. No SAM-specific size/dimension/format limits
  invented or enforced.
- `SamHttpRequest` (frozen; POST-only, canonical URL, validated
  timeout, deep-copied non-empty body; carries no credential),
  `SamHttpSession` protocol, `build_http_request` (config/call
  consistency, pure), `dispatch_http` (validates, resolves key,
  invokes once; key only in `Authorization` header metadata; raw reply
  returned unparsed — envelope parsing stays a separate task).
- `run_scan`, `default_transport()`, and `config/models.yaml`
  untouched; `sam-3.1` vs `sam-3-1` still unresolved.
- 28 new tests: exact nested body, URL + data-URL inputs, 15 malformed
  image cases, blank inputs, determinism, method/URL/body validation,
  mismatch + non-canonical rejection, exact dispatch metadata,
  pre-session failure with zero calls, credential exclusion everywhere.
- `docs/DAILY_LOG.md`: dated entry (observed results only).

## Verification (observed)

- Client file **64 passed** (36 carried + 28 new; 4 first-run failures:
  3 test-side missing kwargs, 1 docstring tripping the substring
  network-token scan — both fixed, no product defect).
- Full suite **439 passed, 0 failed** (411 + 28).
- `compileall -q src tests eval` clean; TOML + 3 YAML parse OK;
  `git diff --check` clean; untracked whitespace scan clean.
- Secret-pattern count scan: 0 in changed/new files and added lines.
- `.env` ignored + untracked via metadata only; never read. No API
  calls, uploads, credentials, credits, deps, staging, or commits.

## Remaining unresolved image constraints

SAM-specific still-image formats, dimensions, and payload ceilings;
whether generic inline/upload limits apply; complete streaming/error
semantics; response-envelope parsing; billing behavior. Decoder and
overlay remain separate tasks; Phase 4 stays open.
