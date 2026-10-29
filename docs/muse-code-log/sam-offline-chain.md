# Offline integration chain (Phase 4 final offline task)

Date: 2026-10-29 (UTC). Offline-only. No API calls, uploads, credentials,
installs, staging, commits, or pushes. Live testing deferred/unauthorized.

## Baseline and inspection

Branch `integration/phase-2-task-1-sam-parser`, HEAD `858b1b79` (unchanged).
Inspected: `envelope.py`, `frames.py`, `response_text.py`, `output.py`,
`severity.py` (`mask_severity_pct` needs decoded `BinaryMask` inputs),
their tests, and the readiness checklist (§10 gates, row 58).

## Changes

- New `src/mydrak/sam/chain.py` (no new dependencies):
  `run_offline_chain(raw_reply, *, expected_width, expected_height,
  limits, max_chars, envelope_max_chars)` returns frozen
  `ChainOutcome(decision, severity_pct, frames_found, review_required,
  reason, detail)`. Decisions: `"no-findings"` only for parsed
  zero-match frames (absence of detections, never a diagnosis);
  `"manual-review"` for unusable envelopes, missing/rejected texts,
  detections with opaque masks (`"masks-opaque"`), and dimension
  problems. `severity_pct` is always `None` offline — wire masks are
  never decoded, so no `BinaryMask` exists; severity stays covered by
  the separate synthetic-grid tests. Nothing is synthesized, decoded,
  retried, or diagnosed. Details carry only fixed value-free messages.
- New `tests/test_sam_chain.py`: 11 tests (valid frames → review,
  zero-match → no-findings, empty/missing/rejected/malformed →
  review without echo, invalid dims → review, severity `None` across
  all envelope-driven paths, no mask-synthesis imports, determinism,
  cap plumbing).
- `sam_live_integration_readiness.md` row 58: evidence note appended
  (offline parser/adapter/chain exist and are tested); label stays
  UNVERIFIED, gates and NO-GO untouched.
- No changes to envelope/frames/parsers, client, transport, `run_scan`,
  fake default, `models.yaml`, `architecture.md`, or historical logs.

## Verification (observed)

- Focused + affected: chain, frames, envelope, output, response-text,
  severity, grid files → **227 passed** (11 new; 2 first-run failures
  were the test's own source-token assertions tripping on module
  prose — fixed by asserting on import lines instead).
- Full suite at phase boundary:
  `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q`
  → **556 passed, 0 failed**.
- In-memory `compile()` of new files → OK. TOML + 3 YAML + JSONL line
  parse → OK (0 executed live records). `git diff --check` → clean.
- Secret scan (value-safe) on new files → 0 real secrets (reason
  strings and synthetic markers only). `.env` metadata-only: ignored
  (`!!`), untracked, never opened.

## Verdict and next product task

The offline chain is demonstrably connected end-to-end with explicit
review outcomes and no fabricated severity. Missing offline capability:
mask decoding (wire payloads stay opaque by design) — so live SAM
integration, which also needs eligibility, billing, retention, and
authorization gates, remains BLOCKED. Phase 4 offline scope is
validated; **live SAM remains NO-GO**. Next product-level task beyond
Phase 4: pursue the §10 live gates (account eligibility, billing
protection, retention/consent, authorized single-request smoke test) —
only under separate explicit authorization, never as part of offline
work.
