# Offline SAM response-envelope parsing (Phase 4 product task)

Date: 2026-10-29 (UTC). Offline-only. No API calls, uploads, credentials,
installs, staging, commits, or pushes. Live testing deferred/unauthorized.

## Baseline and evidence

Branch `integration/phase-2-task-1-sam-parser`, HEAD `858b1b79` (unchanged).
Inspected: `client.py` (`dispatch_http` returns raw reply text, envelope
parsing explicitly unimplemented), `response_text.py` (documented
`output_text` line grammar, `SamResponseError(ValueError)`, size caps),
`transport.py` error conventions, readiness checklist row 58 and
contract §D.

Repo evidence supports the `output_text` line grammar (VERIFIED) but not
the raw-HTTP-JSON envelope schema or error-object shape (both UNVERIFIED
open questions, no live sample). Built accordingly: conservative,
explicitly labeled, fail-closed.

## Changes

- New `src/mydrak/sam/envelope.py` (stdlib `json` only):
  `SamEnvelopeError(ValueError)`; `parse_response_envelope(raw,
  max_chars=8MiB)` returning frozen `SamEnvelope(texts, request_id,
  shape)`. Supports exactly two labeled shapes — `top-level-output-text`
  (SDK-style convenience fallback, NOT established as raw HTTP JSON) and
  `output-message-items` (message/content/`output_text` vocabulary;
  exact framing UNVERIFIED). Empty string/whitespace replies, malformed
  JSON, non-object envelopes, indicated provider errors (`"error"`
  truthy; `null` treated as absent), missing output, and non-empty
  output yielding zero texts all raise fixed value-free errors that
  never echo the reply. Explicit `"output": []` is the only empty
  success. Non-message items and non-text parts skipped (documented);
  extra keys ignored; top-level `"id"` accepted as `request_id` only if
  a short non-empty string (key name UNVERIFIED). Local caps
  (`MAX_OUTPUT_TEXTS = 256`) are defensive project bounds, not provider
  limits. No import of the segmentation parser or synthetic grammar;
  texts are returned unparsed for a separate caller-side step.
- New `tests/test_sam_envelope.py`: 17 tests, all fixtures labeled
  synthetic/UNVERIFIED (both shapes, empty/missing output, malformed
  JSON/shapes, error indication without echo, caps, request-ID rules,
  determinism, parser-separation source scan).
- No changes to `client.py`, `transport.py`, `run_scan`, fake default,
  existing parsers, `models.yaml`, readiness gates, or historical logs.

## Verification (observed)

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
  tests/test_sam_envelope.py tests/test_sam_output.py
  tests/test_sam_response_text.py tests/test_sam_client.py -q` →
  **307 passed** (17 new; 1 first-run failure was the test's own
  `response_text` token assertion tripping on the module docstring —
  fixed by asserting no `mydrak` import instead of no prose mention).
- In-memory `compile()` of both new files → OK (no artifacts written).
- `git diff --check` → clean.
- Full suite DEFERRED to the next phase boundary: no shared file was
  modified and nothing existing imports the new module (stated clearly
  per task). `.env` never touched (no metadata check needed; nothing
  reads env here).

## Next task

Wire the conservative handoff in a caller-side adapter: envelope texts
→ `parse_response_text` with caller-supplied expected dimensions,
including the empty-texts case (zero-match vs manual-review decision),
still offline with synthetic fixtures only.

Phase 4 remains incomplete. **Live SAM remains NO-GO.**
