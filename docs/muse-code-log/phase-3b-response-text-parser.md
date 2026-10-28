# Phase 3B: Offline SAM Output Text Parser — Muse session log

**Date:** 2026-10-28 (Asia/Kolkata). **Branch:** `integration/phase-2-task-1-sam-parser`.
**Baseline HEAD:** `65812940d0215ce147b5a13d35383c462fb693f9` (verified before editing).
Pre-existing worktree change `docs/architecture.md` preserved untouched; no staging/commit/push.

## Grammar re-verification (this turn, web-search snippets only)

- `<Nf>` frame lines; single image is `<0f>`; comma-separated
  `id<|box;x1=..;y1=..;x2=..;y2=..;w=<frameW>;h=<frameH>|><|mask;x=..;y=..;[c=..;]data=<H>,<W>,<enc>payload|>` records.
- `~` = documented default lossless encoding, `!` = documented one-bit encoding; payloads Base85 (not Base64).
- Optional `c=` confidence on box and/or mask tokens; each segment may be preceded by one comma.
- Sources: meta-sam TS/Python parser READMEs, `protocol/sam3.md`, meta-sam-parser PyPI, plus dev.meta.ai SAM overview / reading-segmentation / client-libraries / models / pricing-rate-limits / sam-3-1 product page (URLs in matrix Phase 3B note). Primary dev.meta.ai pages were not freshly fetched.
- Model-ID discrepancy (`sam-3.1` vs `sam-3-1`) left explicitly unresolved.

## Implementation

- Added `src/mydrak/sam/response_text.py` (12,536 bytes): `SamResponseError`, `SamBox`, `SamWireMask`, `SamRecord`, `SamFrame`, `parse_response_text(text, *, expected_width, expected_height, limits, max_chars)`.
- Single-image `<0f>` only; multi-line/multi-frame rejected; empty/bare-`<0f>`/`<0f>,` tolerated as zero-match (assumption, documented).
- Canonical key order enforced; records split only on `,(?=\d+<\|box;)`; one optional leading comma tolerated per parser protocol.
- Declared `w`/`h` must equal caller-supplied expected dims; coordinate ordering/bounds, mask positivity, confidence agreement (local 0..1 bound marked as such) enforced.
- Payloads charset-checked (printable non-space ASCII minus comma), never decoded, never routed to `synthetic-grid-v1`/IoU-Dice; errors never echo untrusted output.
- Local caps only (`MAX_OUTPUT_CHARS` 8 MiB, `MAX_INT_DIGITS` 10, reused `SamLimits`); no network/token imports.
- `src/mydrak/sam/output.py` unchanged. Two defects found and fixed during testing: record splitter broke on `data=H,W,…` commas; `_parse_mask` passed `body` instead of `rest` to the `y` field parser.

## Tests

- Added `tests/test_sam_response_text.py` (53 tests, all synthetic documentation fixtures): valid 1/multi-object, sparse IDs, zero-match forms, `~`/`!`, confidence absent/present/mismatch/out-of-range, boundaries, dim mismatch, ~30 malformed variants, oversize/record caps, error secrecy, video rejection, no-network import scan, synthetic-parser regression, grid-adapter boundary.
- Observed: focused `tests/test_sam_response_text.py + tests/test_sam_output.py` **124 passed**; full suite **301 passed, 0 failed** (baseline 248 + 53 new).

## Docs

- `docs/verification/official_meta_api_matrix.md`: Phase 3B note (grammar, sources, parser boundary, unresolved items, NO-GO intact).
- `docs/verification/sam_live_integration_readiness.md`: §1/§2/§3/§4/§8 corrected (two-parser distinction, Base85 `~`/`!` labels verified, decoding/live-compat still UNVERIFIED, model-ID discrepancy noted); NO-GO unchanged.
- `docs/DAILY_LOG.md`: Phase 3B entry (this file's results only).

## Verification (observed)

- `python3 -m pytest -q` → **301 passed** (exit 0).
- `python3 -m compileall -q src tests eval` → clean.
- TOML + 3 YAML configs parse → OK.
- Secret-pattern count scan on 4 touched files: source/test files 0 matches; doc files 6+6 matches, all ordinary documentation wording (`token`, `Bearer [REDACTED]`, secret-manager prose) — no values printed.
- `.env`: `check-ignore` confirms ignored; `git ls-files` count 0 (untracked). Contents never read.
- `git diff --check` → clean. `git status`: 3 modified docs + 2 new untracked files; `architecture.md` pre-existing edit intact.

## Limitations / not done

- No Base85 decoding, no client/transport, no live-sample validation, no real segmentation/diagnosis.
- UNVERIFIED: confidence range, `|>`-in-payload ambiguity, bare-`<0f>` legality, edge-inclusivity, mask-raster relation, credits/eligibility/billing, SAM still-image limits, ZDR, live compatibility, model-ID discrepancy.
- All changes left uncommitted/unpushed for Codex review. No API calls, uploads, credentials, credits, dependencies, or Git mutations.

## Phase 3C follow-up fix (2026-10-28) — Codex-confirmed defects

This section records a later fix pass; the Phase 3B description above is historical and the corrected checks below were NOT present in the earlier implementation.

- **A. Numerics:** all digit classes are ASCII-only (`[0-9]`; `\d` removed — it matched Unicode digits that `int()` would silently accept); object IDs are unsigned with the local digit cap applied before conversion; every untrusted `int()`/`float()` is wrapped so only `SamResponseError` escapes (with `from None`); `max_chars` rejects bools/non-ints.
- **B. Mask rules:** origin must be exactly `x=0;y=0`; mask dims each strictly smaller than source (equality rejected); confidence both-absent or both-present-and-equal (one-sided rejected). These rest on the Codex review of the primary grammar page; my snippet corroboration covers token spelling only.
- **C. Strict frame syntax:** bare `<0f>`, trailing `<0f>,`, and leading separators rejected; only empty output is a zero-match. The Phase 3B leading-comma tolerance (parser-protocol notes, not the primary page) is withdrawn, and its test replaced with rejection tests.
- **D. Bounded scan:** `re.split` replaced with a boundary-regex scan that parses at most `max_objects` records and raises before parsing further; whole-input cap still applied first.
- Tests grew from 53 to 69 (negative/signed/Unicode/huge IDs, Unicode box/mask digits, invalid caps, nonzero origins, equal/larger masks, boundary acceptance, one-sided confidence, strict frame syntax, zero object limit). `src/mydrak/sam/output.py` untouched; `docs/architecture.md` untouched.
- Observed: focused files **140 passed**; full suite **317 passed, 0 failed** (248 pre-Phase-3 + 69 new-module tests). No API calls, uploads, credentials, credits, deps, staging, or commits.

## Phase 3D residual fixes (2026-10-28) — Codex review follow-up

Historical Phase 3B/3C text above is unchanged; the corrections below were NOT present earlier.

- **Whitespace-only output:** only the exact empty string `""` is a zero-match; `" "`, `"   "`, `"\t\n "`, `"\n"`, `"\r\n"` are rejected with `SamResponseError` (no silent normalization). Framing whitespace around a valid frame is still stripped as before.
- **Readiness count:** `sam_live_integration_readiness.md` now reports the current counts (73 response-text tests and 71 synthetic-parser tests; the task brief cited the pre-fix 69).
- **Payload hardening (completed safely):** mask `data` parsing replaced `.split(",")` with two `partition(",")` delimiter scans — exactly the H/W delimiters are consumed and the remainder is treated as encoding marker plus opaque payload, so comma-heavy payloads allocate no fragment list. Grammar unchanged (payloads still cannot contain commas; violations fail with the same stable `SamResponseError`, never echoing payloads). New regression test uses a 5000-comma payload. Base85 alphabet variant stays UNVERIFIED.
- Tests: response-text file grew 69 → 73. `src/mydrak/sam/output.py` and `docs/architecture.md` untouched.
- Observed: `tests/test_sam_response_text.py` **73 passed**; `tests/test_sam_output.py` **71 passed**; full suite **321 passed, 0 failed** (248 pre-Phase-3 + 73). No API calls, uploads, credentials, credits, deps, staging, or commits.

## Phase 3D.1 mask-payload limit test (2026-10-28)

- Added `test_mask_payload_limit_enforced`: a 9-char valid payload parses under default limits (positive control proving all other fields valid) and raises `SamResponseError` ("malformed mask payload", payload not echoed) with `SamLimits(max_mask_chars=8)`. No parser change was needed; the limit was already enforced.
- Observed: response-text file **74 passed**; full suite **322 passed, 0 failed** (248 pre-Phase-3 + 74). Readiness counts updated to 74/71. No API calls, uploads, credentials, credits, deps, staging, or commits.
