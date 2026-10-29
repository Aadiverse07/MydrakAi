# Caller-side envelope-to-frames adapter (Phase 4 product task 2/3)

Date: 2026-10-29 (UTC). Offline-only. No API calls, uploads, credentials,
installs, staging, commits, or pushes. Live testing deferred/unauthorized.

## Baseline and inspection

Branch `integration/phase-2-task-1-sam-parser`, HEAD `858b1b79` (unchanged).
Inspected: `envelope.py` (`SamEnvelope` texts tuple), `response_text.py`
(`parse_response_text` signature, `SamFrame`, `SamResponseError`), the
existing synthetic-grid `adapter.py`, and their tests. The grid adapter
was left untouched to preserve envelope/synthetic separation, so the new
adapter lives in its own module.

## Changes

- New `src/mydrak/sam/frames.py` (no new dependencies):
  `adapt_envelope(envelope, *, expected_width, expected_height, limits,
  max_chars)` parses every text against the same caller-supplied
  dimensions (never invented, never derived from provider output;
  per-text dimension variance UNVERIFIED) and returns a frozen
  `FrameAdaptation(frames, review_required, reason, detail)`.
  Contract: `""` text → valid zero-match frame (`review_required=False`);
  zero texts → review (`"no-output-texts"`, never an invented frame);
  any rejected text (malformed content, dimension mismatch, breached
  caps) → review (`"text-rejected"`, detail carries only the parser's
  fixed value-free message); only non-envelope input raises
  (`SamResponseError`). Uniform outcomes over message-matching: no
  success is ever reported without parsed evidence. Provider behavior
  UNVERIFIED; no diagnosis performed.
- New `tests/test_sam_frames.py`: 11 tests with self-contained synthetic
  fixtures (single/multiple/empty-string texts, empty list, malformed
  text without echo, mixed valid+malformed, dimension problems,
  non-envelope input, limits pass-through, determinism).
- No changes to envelope/response-text/grid code, client, transport,
  `models.yaml`, gates, or historical logs.

## Verification (observed)

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
  tests/test_sam_frames.py tests/test_sam_envelope.py
  tests/test_sam_output.py tests/test_sam_response_text.py -q` →
  **173 passed** (11 new; first run green, no fixes needed).
- In-memory `compile()` of both new files → OK (no artifacts written).
- `git diff --check` → clean.
- Full suite DEFERRED to the next phase boundary: no shared file was
  modified and nothing existing imports the new module. `.env` never
  touched.

## Next task

Phase 4 task 3/3 (per roadmap): decide the offline integration
validation/review step that closes the offline scope — likely a
read-only readiness re-verification that the envelope→frames→severity
chain stays mock-only with live gates intact — without starting live
integration.

Phase 4 remains incomplete. **Live SAM remains NO-GO.**
